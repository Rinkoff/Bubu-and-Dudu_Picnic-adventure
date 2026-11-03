"""
Cuts the generated pickup icon sheet (one row of 5 icons on a white
background) into separate sprites in ./assets:

  pu_shield.png  pu_feather.png  pu_magnet.png  pu_berry.png  star.png

Usage:  python import_items.py [sheet.png]
The sheet is copied to assets/_items_src.png so the cut can be redone later;
a contact sheet of the result is written to assets/_items.png for checking.
"""
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
SRC_COPY = os.path.join(OUT, "_items_src.png")
NAMES = ["pu_shield", "pu_feather", "pu_magnet", "pu_berry", "star"]
SIZE = 96          # every icon is saved centered in a SIZE x SIZE square


def columns(ink):
    """Split the row of icons on empty columns; small gaps (the magnet's
    motion lines, the star's sparkle) stay with their icon."""
    used = ink.any(axis=0)
    runs, x = [], 0
    while x < len(used):
        if used[x]:
            x0 = x
            while x < len(used) and used[x]:
                x += 1
            runs.append([x0, x])
        x += 1
    merged = [runs[0]]
    for r in runs[1:]:
        if r[0] - merged[-1][1] < 12:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return merged


def cut(img, x0, x1):
    a = np.asarray(img).astype(int)[:, x0:x1]
    ink = a.min(axis=2) < 232
    ys = np.where(ink.any(axis=1))[0]
    a = a[max(0, ys[0] - 4): ys[-1] + 5]
    h, w = a.shape[:2]
    # background = near-white pixels connected to the border
    near_white = (a.min(axis=2) > 225).astype(np.uint8) * 255
    m = Image.fromarray(near_white).copy()
    for x in range(w):
        for y in (0, h - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    for y in range(h):
        for x in (0, w - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    alpha = Image.fromarray(((np.asarray(m) != 128) * 255).astype(np.uint8))
    alpha = alpha.filter(ImageFilter.GaussianBlur(.6))
    rgba = Image.fromarray(a.astype(np.uint8), "RGB").convert("RGBA")
    rgba.putalpha(alpha)
    rgba = rgba.crop(alpha.getbbox())
    k = (SIZE - 4) / max(rgba.size)
    rgba = rgba.resize((max(1, round(rgba.width * k)), max(1, round(rgba.height * k))),
                       Image.LANCZOS)
    out = Image.new("RGBA", (SIZE, SIZE))
    out.paste(rgba, ((SIZE - rgba.width) // 2, (SIZE - rgba.height) // 2))
    return out


def main():
    if len(sys.argv) > 1:
        shutil.copyfile(sys.argv[1], SRC_COPY)
    img = Image.open(SRC_COPY).convert("RGB")
    ink = np.asarray(img).astype(int).min(axis=2) < 232
    cols = columns(ink)
    if len(cols) != len(NAMES):
        sys.exit(f"expected {len(NAMES)} icons, found {len(cols)} columns: {cols}")
    sheet = Image.new("RGB", (SIZE * len(NAMES) + 10 * (len(NAMES) + 1), SIZE + 20),
                      (60, 130, 80))
    for i, (name, (x0, x1)) in enumerate(zip(NAMES, cols)):
        icon = cut(img, x0, x1)
        icon.save(os.path.join(OUT, name + ".png"))
        sheet.paste(icon, (10 + i * (SIZE + 10), 10), icon)
        print(name, "<-", (x0, x1))
    sheet.save(os.path.join(OUT, "_items.png"))


if __name__ == "__main__":
    main()
