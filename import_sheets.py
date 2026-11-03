"""
Cuts the generated art sheets (objects on a plain white background) into
sprites in ./assets. Each object is found as a connected blob of "ink" and
matched to a name by the anchor point it is closest to.

  assets/_creatures_src.png -> bat1 bat2 owl_sit owl_fly (+ owl_*_eyes glow layers)
  assets/_terrain_src.png   -> plank_wood plank_pink plank_moon mushroom
                               mushroom_squash plate_up plate_down blanket ground
  assets/_sky_src.png       -> sun moon
  assets/_props_src.png     -> prop_basket prop_sign prop_balloon prop_bamboo blanket_flat
  assets/_bamboo_src.png    -> bamboo_s bamboo_m bamboo_l   (optional)
  assets/_butterflies_src.png -> bf_{pink,lilac,yellow}_{open,closed}
  assets/_items2_src.png    -> cp_flag_off cp_flag_on heart_new honey_new
  assets/_bees_src.png      -> bee_new1 bee_new2
  assets/_clouds_src.png    -> cloud_new1..4   (light blue background)
  assets/_moonplank_src.png -> plank_moon   (flat; the terrain one is plank_moon_3d)
  assets/_hills_src.png     -> hill_far hill_near   (full-width strips, cut by rows)

Usage:  python import_sheets.py [creatures.png terrain.png sky.png props.png]
(new sheets replace the _*_src.png copies; a missing _*_src.png is skipped).
Writes assets/_sheets.png to check.
"""
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")

# sheet -> (merge distance in px, {name: anchor (x, y) in the sheet image})
SHEETS = {
    "creatures": (13, {"bat1": (72, 520), "bat2": (208, 516),
                       "owl_sit": (363, 525), "owl_fly": (527, 512)}),
    "terrain": (9, {"plank_wood": (139, 422), "plank_pink": (139, 482),
                    "plank_moon_3d": (139, 544), "mushroom": (320, 497),
                    "mushroom_squash": (400, 533), "plate_up": (495, 507),
                    "plate_down": (578, 513), "blanket": (108, 622),
                    "ground": (418, 622)}),
    "sky": (25, {"sun": (177, 515), "moon": (490, 515)}),
    "props": (9, {"prop_basket": (105, 570), "prop_sign": (292, 570),
                  "prop_balloon": (445, 540), "prop_bamboo": (560, 510),
                  "blanket_flat": (315, 747)}),
    "bamboo": (9, {"bamboo_s": (90, 600), "bamboo_m": (300, 560),
                   "bamboo_l": (520, 510)}),
    # 572x1024 sheet: one color per row, wings open (left) / closed (right)
    "butterflies": (9, {"bf_pink_open": (167, 217), "bf_pink_closed": (448, 206),
                        "bf_lilac_open": (168, 520), "bf_lilac_closed": (450, 508),
                        "bf_yellow_open": (168, 824), "bf_yellow_closed": (449, 813)}),
    # second round, replacing first-generation sprites (572x1024 sheets)
    "items2": (9, {"cp_flag_off": (154, 223), "cp_flag_on": (430, 223),
                   "heart_new": (430, 518), "honey_new": (431, 812)}),
    "bees": (9, {"bee_new1": (155, 468), "bee_new2": (417, 509)}),
    "clouds": (9, {"cloud_new1": (76, 479), "cloud_new2": (242, 479),
                   "cloud_new3": (176, 563), "cloud_new4": (447, 512)}),
    "moonplank": (9, {"plank_moon": (286, 512)}),
}
WHITE = (255, 255, 255)
SHEET_BG = {"clouds": (189, 224, 252)}      # sheets not drawn on white
# how close to the background colour still counts as background; the clouds'
# pale blue shading is near their sky-blue sheet, so they need a tight one
SHEET_TOL = {"clouds": 12}
# sprites with enclosed white gaps to punch out (the balloon string's loop)
HOLES = {"prop_balloon"}
# full-width strips: name -> (first row, last row) in the sheet
STRIPS = {"hills": {"hill_far": (356, 461), "hill_near": (547, 711)}}


def bg_diff(a, bg):
    """How far each pixel is from the sheet's background colour."""
    return np.abs(a - np.array(bg)).max(axis=2)


def filled(mask):
    """mask with its enclosed holes filled (a white heart drawn on a flag)."""
    h, w = mask.shape
    pad = np.zeros((h + 2, w + 2), np.uint8)
    pad[1:-1, 1:-1] = mask * 255
    f = Image.fromarray(pad).copy()
    ImageDraw.floodfill(f, (0, 0), 128)
    return (np.asarray(f) != 128)[1:-1, 1:-1]


def blobs(img, merge, bg=WHITE, tol=30):
    """(bounding box, mask) of each ink blob (nearby pieces like sun rays merge)."""
    ink = bg_diff(np.asarray(img).astype(int), bg) > tol
    m = Image.fromarray((ink * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(merge)).copy()
    boxes, lab = [], 1
    while True:
        ys, xs = np.where(np.asarray(m) == 255)
        if not len(ys):
            return boxes
        ImageDraw.floodfill(m, (int(xs[0]), int(ys[0])), lab)
        yy, xx = np.where(np.asarray(m) == lab)
        if len(yy) > 300 and xx.max() - xx.min() < img.width - 4:   # skip frame lines
            boxes.append(((xx.min(), yy.min(), xx.max() + 1, yy.max() + 1),
                          filled(np.asarray(m) == lab)))
        lab += 1


def cut(img, box, own, holes=False, bg=WHITE, tol=30):
    x0, y0, x1, y1 = box
    a = np.asarray(img).astype(int)[max(0, y0 - 3):y1 + 3, max(0, x0 - 3):x1 + 3]
    own = own[max(0, y0 - 3):y1 + 3, max(0, x0 - 3):x1 + 3]
    h, w = a.shape[:2]
    # background = near-white pixels connected to the border
    m = Image.fromarray(((bg_diff(a, bg) < tol) * 255).astype(np.uint8)).copy()
    for x in range(w):
        for y in (0, h - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    for y in range(h):
        for x in (0, w - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    # only this blob - a neighbour poking into the crop box is dropped
    keep = (np.asarray(m) != 128) & own
    if holes:
        keep &= a.min(axis=2) <= 240
    alpha = Image.fromarray((keep * 255).astype(np.uint8))
    alpha = alpha.filter(ImageFilter.GaussianBlur(.6))
    rgba = Image.fromarray(a.astype(np.uint8), "RGB").convert("RGBA")
    rgba.putalpha(alpha)
    return rgba.crop(alpha.getbbox())


def cut_strip(img, y0, y1):
    """Hill silhouette: in every column everything below the first ink pixel."""
    a = np.asarray(img).astype(int)[y0:y1]
    ink = a.min(axis=2) < 240
    top = np.where(ink.any(axis=0), ink.argmax(axis=0), a.shape[0])
    rows = np.arange(a.shape[0])[:, None]
    alpha = Image.fromarray(((rows >= top[None, :]) * 255).astype(np.uint8))
    alpha = alpha.filter(ImageFilter.GaussianBlur(.6))
    rgba = Image.fromarray(a.astype(np.uint8), "RGB").convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def eyes_layer(rgba):
    """Only the glowing yellow eyes (drawn on top of the night darkness)."""
    a = np.asarray(rgba).astype(int)
    eye = (a[..., 0] > 225) & (a[..., 1] > 200) & (a[..., 2] < 215) & (a[..., 3] > 200)
    al = Image.fromarray((eye * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    al = al.filter(ImageFilter.GaussianBlur(1.2))
    out = rgba.copy()
    out.putalpha(al)
    return out


def main():
    srcs = sys.argv[1:4]
    for sheet, src in zip(SHEETS, srcs):
        shutil.copyfile(src, os.path.join(OUT, f"_{sheet}_src.png"))
    made = []
    for sheet, (merge, anchors) in SHEETS.items():
        path = os.path.join(OUT, f"_{sheet}_src.png")
        if not os.path.isfile(path):
            print(f"(no {path} - skipped)")
            continue
        img = Image.open(path).convert("RGB")
        bg, tol = SHEET_BG.get(sheet, WHITE), SHEET_TOL.get(sheet, 30)
        boxes = blobs(img, merge, bg, tol)
        for name, (ax, ay) in anchors.items():
            box, own = min(boxes, key=lambda b: ((b[0][0] + b[0][2]) / 2 - ax) ** 2
                           + ((b[0][1] + b[0][3]) / 2 - ay) ** 2)
            spr = cut(img, box, own, name in HOLES, bg, tol)
            spr.save(os.path.join(OUT, name + ".png"))
            made.append((name, spr))
            if name.startswith("owl"):
                eyes_layer(spr).save(os.path.join(OUT, name + "_eyes.png"))
            print(f"{name:16s} {spr.size}")
    for sheet, strips in STRIPS.items():
        path = os.path.join(OUT, f"_{sheet}_src.png")
        if not os.path.isfile(path):
            continue
        img = Image.open(path).convert("RGB")
        for name, (y0, y1) in strips.items():
            spr = cut_strip(img, y0, y1)
            spr.save(os.path.join(OUT, name + ".png"))
            made.append((name, spr))
            print(f"{name:16s} {spr.size}")
    # contact sheet on green and night-blue to spot leftover background
    W = sum(s.width for _, s in made) + 10 * (len(made) + 1)
    H = max(s.height for _, s in made) * 2 + 30
    cs = Image.new("RGB", (W, H), (60, 130, 80))
    cs.paste((25, 25, 60), (0, H // 2, W, H))
    x = 10
    for _, s in made:
        cs.paste(s, (x, 10), s)
        cs.paste(s, (x, H // 2 + 5), s)
        x += s.width + 10
    cs.save(os.path.join(OUT, "_sheets.png"))


if __name__ == "__main__":
    main()
