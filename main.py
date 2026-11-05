"""
Bubu & Dudu: Picnic Adventure
A two-player co-op platformer for one keyboard, with procedurally
generated levels.

  Bubu (panda):  W A D  + S (crouch)
  Dudu (bear):   Arrows + Down (crouch)
  Left/Right Shift = switch day <-> night
  R = restart level    N = new level    Esc = quit

Reach the picnic blanket TOGETHER. Collect hearts, stomp grumpy bees
(or crouch and let them fly over you), ride the moving platforms,
bounce on mushrooms, and work together at the plate-bridge!

Run:  python main.py
Assets: python make_assets.py
"""
import json
import math
import os
import random
import sys
from array import array

import pygame

VW, VH = 960, 540
GROUND_Y = 480
GRAV, MOVE, JUMP = 2300, 265, 760
SPRING_VY = -1150
FPS = 60
GOAL_W = 190

FROZEN = getattr(sys, "frozen", False)
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(BASE, "assets")

# ------------------------------------------------------------------ level generator
def generate_level(seed, n=1):
    """Builds a random but always-beatable level; higher n = longer & harder."""
    rng = random.Random(seed)
    L = dict(grounds=[], woods=[], movers=[], springs=[], bees=[], hearts=[],
             honeys=[], powerups=[], checkpoints=[], bamboo=[], trees=[])
    target = rng.randint(5200, 6200) + min(3400, (n - 1) * 260)
    bee_extra = min(85, (n - 1) * 5)          # bees get faster on later levels
    bee_prob = min(.58, .40 + (n - 1) * .012) # ...and more common
    if n % 10 == 0:                           # challenge level!
        bee_extra += 90
        bee_prob = .80
    x = 0
    first = True
    did_bridge = False
    did_mover_gap = False
    bridge, plates = None, []
    last_cp = 0
    level_w = target

    while True:
        seg_w = rng.randint(600, 750) if first else rng.randint(500, 850)
        is_last = x + seg_w >= target
        if is_last:
            seg_w = max(seg_w, 700)
        L["grounds"].append((x, seg_w))
        s0, s1 = x, x + seg_w

        # checkpoint at the start of a segment every ~1200px
        if not first and s0 - last_cp > 1200:
            L["checkpoints"].append(s0 + 60)
            last_cp = s0

        # decor
        dx = s0 + rng.randint(40, 120)
        while dx < s1 - 60:
            if rng.random() < .55:
                L["trees"].append(dx)
            else:
                L["bamboo"].append((dx, rng.choice([120, 140, 160])))
            dx += rng.randint(280, 440)

        # ground features (springs / bees / hearts), quiet zone before the goal
        fx = s0 + (260 if first else rng.randint(70, 150))
        f_end = s1 - (680 if is_last else 90)
        while fx < f_end:
            roll = rng.random()
            if roll < .18:
                L["springs"].append((fx, GROUND_Y))
                L["hearts"].append((fx, rng.randint(155, 200)))
                L["hearts"].append((fx, rng.randint(245, 290)))
            elif roll < bee_prob and seg_w > 450:
                lo = max(s0 + 60, fx - 60)
                hi = min(s1 - 60, fx + rng.randint(260, 380))
                if hi - lo > 180:
                    L["bees"].append(dict(x1=lo, x2=hi, y=442,
                                          spd=rng.randint(70, 110) + bee_extra))
            elif roll < .62:
                L["hearts"].append((fx, 430))
            elif roll < .74:
                L["powerups"].append((fx, 428, rng.choice(POWERUP_KINDS)))
            fx += rng.randint(210, 330)

        # floating platforms above the segment
        if seg_w > 420 and not is_last:
            for _ in range(rng.randint(0, 2)):
                px_ = rng.randint(s0 + 40, s1 - 180)
                py_ = rng.choice([260, 300, 340, 380])
                pw_ = rng.randint(100, 140)
                L["woods"].append((px_, py_, pw_))
                r2 = rng.random()
                if r2 < .5:
                    L["hearts"].append((px_ + pw_ // 2, py_ - 60))
                elif r2 < .58:
                    L["honeys"].append((px_ + pw_ // 2, py_ - 60))
                elif r2 < .70:
                    L["powerups"].append((px_ + pw_ // 2, py_ - 60,
                                          rng.choice(POWERUP_KINDS)))
                elif r2 < .8:
                    L["bees"].append(dict(x1=px_ - 40, x2=px_ + pw_ + 40,
                                          y=py_ - 40, spd=rng.randint(80, 120) + bee_extra))

        if is_last:
            level_w = s1
            break
        x = s1
        first = False

        # choose the gap to the next segment
        if not did_bridge and x > target * .5:
            gap = rng.randint(190, 230)                      # co-op bridge gap
            bridge = dict(x=x - 10, y=GROUND_Y - 10, w=gap + 20, h=12)
            plates = [x - 70, x + gap + 70]
            did_bridge = True
        elif not did_mover_gap and x > target * .2 and rng.random() < .4:
            gap = rng.randint(210, 260)                      # moving platform gap
            y_ = rng.randint(390, 420)
            L["movers"].append(dict(x0=x - 50, y0=y_, x1=x + gap - 40, y1=y_,
                                    w=90, period=rng.uniform(2.8, 3.6)))
            did_mover_gap = True
        elif rng.random() < .4:
            gap = rng.randint(150, 190)                      # stepping platform gap
            L["woods"].append((x + gap // 2 - 45, rng.randint(390, 420), 90))
            L["hearts"].append((x + gap // 2, rng.randint(300, 350)))
        else:
            gap = rng.randint(90, 135)                       # plain jumpable gap
            if rng.random() < .5:
                L["hearts"].append((x + gap // 2, rng.randint(330, 390)))
        x += gap

    # one vertical elevator to a high honey pot
    cands = [g for g in L["grounds"][1:-1] if g[1] > 520]
    if cands:
        gx0, gw = rng.choice(cands)
        ex = gx0 + rng.randint(150, gw - 240)
        L["movers"].append(dict(x0=ex, y0=380, x1=ex, y1=160, w=90,
                                period=rng.uniform(4.0, 5.0)))
        L["honeys"].append((ex + 45, 120))

    # guarantee some honey
    while len(L["honeys"]) < 2 and L["woods"]:
        wx, wy, ww = rng.choice(L["woods"])
        L["honeys"].append((wx + ww // 2, wy - 60))

    # every 10th level is a CHALLENGE level: swarms of fast bees,
    # fewer checkpoints and springs - dramatically harder
    if n % 10 == 0:
        for gx0, gw in L["grounds"][1:]:
            if gw > 400:
                L["bees"].append(dict(x1=gx0 + 40, x2=gx0 + gw - 40,
                                      y=rng.choice([300, 340, 380]),
                                      spd=rng.randint(150, 210)))
        L["checkpoints"] = L["checkpoints"][::2]
        L["springs"] = L["springs"][::2]

    # ---- de-overlap pass: nothing spawns on top of something else -------
    def clear_x(x, xs, d):
        return all(abs(x - o) >= d for o in xs)

    # springs off the bridge plates, checkpoint flags and other springs
    springs = []
    for sx, sy in L["springs"]:
        if clear_x(sx, plates, 75) and clear_x(sx, L["checkpoints"], 75) \
                and clear_x(sx, [s[0] for s in springs], 70):
            springs.append((sx, sy))
    L["springs"] = springs

    # bonus platforms out of the moving platforms' path
    def hits_mover(wx, wy, ww):
        for mv in L["movers"]:
            x0, x1 = min(mv["x0"], mv["x1"]), max(mv["x0"], mv["x1"]) + mv["w"]
            y0, y1 = min(mv["y0"], mv["y1"]) - 6, max(mv["y0"], mv["y1"]) + 20
            if wx < x1 and wx + ww > x0 and y0 < wy + 16 and y1 > wy:
                return True
        return False
    L["woods"] = [w for w in L["woods"] if not hits_mover(*w)]

    # pickups stuck inside a platform, or ground hearts sitting on a plate
    def in_platform(ix, iy):
        for wx, wy, ww in L["woods"]:
            if wx - 6 < ix < wx + ww + 6 and wy - 12 < iy < wy + 26:
                return True
        return False
    L["hearts"] = [h for h in L["hearts"] if not in_platform(*h)
                   and not (h[1] > 400 and any(abs(h[0] - px) < 60 for px in plates))]
    L["honeys"] = [h for h in L["honeys"] if not in_platform(*h)]
    L["powerups"] = [pu for pu in L["powerups"] if not in_platform(pu[0], pu[1])
                     and clear_x(pu[0], plates, 60) and clear_x(pu[0], L["checkpoints"], 60)
                     and clear_x(pu[0], [s[0] for s in L["springs"]], 60)]

    # keep pickups from spawning on top of each other
    def far_enough(p, others, d):
        return all((p[0] - o[0]) ** 2 + (p[1] - o[1]) ** 2 >= d * d for o in others)

    powerups = []
    for pu in L["powerups"]:
        if far_enough(pu, powerups, 60):
            powerups.append(pu)
    L["powerups"] = powerups
    honeys = []
    for hp in L["honeys"]:
        if far_enough(hp, honeys, 52) and far_enough(hp, powerups, 56):
            honeys.append(hp)
    L["honeys"] = honeys
    hearts = []
    for hp in L["hearts"]:
        if far_enough(hp, hearts, 38) and far_enough(hp, honeys, 52) \
                and far_enough(hp, powerups, 56):
            hearts.append(hp)
    L["hearts"] = hearts

    # ---- night-only content: moon platforms with a star on top, bats, owls.
    # Uses its own rng so the daytime layout of every level stays the same.
    nrng = random.Random(seed * 7 + 3)
    moons, stars, bats, owls = [], [], [], []

    def hits_wood(mx, my, mw):
        return any(mx < wx + ww + 40 and mx + mw > wx - 40 and abs(my - wy) < 80
                   for wx, wy, ww in L["woods"])

    for gx0, gw in L["grounds"][1:-1]:
        if gw < 450:
            continue
        if nrng.random() < .6:
            # low step reachable from the ground + a higher one with the star
            mw = nrng.randint(100, 130)
            mx = nrng.randint(gx0 + 40, gx0 + gw - mw - 40)
            hw = nrng.randint(90, 110)
            hx = mx + nrng.choice([-1, 1]) * nrng.randint(90, 130)
            hx = max(gx0 + 20, min(gx0 + gw - hw - 20, hx))
            pair = [(mx, 372, mw), (hx, 262, hw)]
            if not any(hits_wood(*m) or hits_mover(*m) for m in pair):
                moons += pair
                stars.append((hx + hw // 2, 215))
        if nrng.random() < min(.85, .45 + n * .03):
            bats.append(dict(x1=gx0 + 60, x2=gx0 + gw - 60,
                             y=nrng.choice([230, 255, 280]),
                             spd=nrng.randint(70, 100) + min(60, n * 3)))
    # challenge levels: the bees sleep at night, so a bat swarm takes over -
    # otherwise Shift would simply switch the swarm off
    if n % 10 == 0:
        for gx0, gw in L["grounds"][1:]:
            if gw > 400:
                for _ in range(2):
                    bats.append(dict(x1=gx0 + 40, x2=gx0 + gw - 40,
                                     y=nrng.choice([220, 250, 280]),
                                     spd=nrng.randint(130, 180)))
    owl_p = .7 if n % 10 == 0 else .35
    for tx in L["trees"]:
        if 500 < tx < level_w - 500 and nrng.random() < owl_p:
            owls.append(tx)
    L["moons"], L["stars"], L["bats"], L["owls"] = moons, stars, bats, owls

    L["bridge"] = bridge
    L["plates"] = plates
    L["level_w"] = level_w
    L["goal_x"] = level_w - 220
    return L

LEVEL_W = 0
GROUNDS = WOODS = MOVER_DEFS = SPRINGS = BEE_DEFS = None
HEART_SPOTS = HONEY_SPOTS = CHECKPOINTS = None
DECOR_TREES = DECOR_BAMBOO = None
BRIDGE, PLATES, GOAL_X = None, [], 0
SOLIDS = []
MOONS = STAR_SPOTS = BAT_DEFS = OWL_SPOTS = None
SHIFT_CD = 1.2         # seconds between day/night switches

LEVELS_PER_PAGE = 20   # level-select grid page size; levels themselves are endless
POWERUP_KINDS = ["shield", "feather", "magnet", "berry"]
FX_DURATION = 12.0     # seconds a power-up effect lasts

def seed_for(n):
    """Level n is always generated from the same seed - like a real campaign."""
    return 20260702 + n * 1013

def apply_level(n):
    global LEVEL_W, GROUNDS, WOODS, MOVER_DEFS, SPRINGS, BEE_DEFS
    global HEART_SPOTS, HONEY_SPOTS, POWERUP_SPOTS, CHECKPOINTS
    global DECOR_TREES, DECOR_BAMBOO
    global BRIDGE, PLATES, GOAL_X, SOLIDS, level_num
    global MOONS, STAR_SPOTS, BAT_DEFS, OWL_SPOTS
    level_num = n
    L = generate_level(seed_for(n), n)
    MOONS, STAR_SPOTS = L["moons"], L["stars"]
    BAT_DEFS, OWL_SPOTS = L["bats"], L["owls"]
    POWERUP_SPOTS = L["powerups"]
    LEVEL_W = L["level_w"]
    GROUNDS = L["grounds"]
    WOODS = L["woods"]
    MOVER_DEFS = L["movers"]
    SPRINGS = L["springs"]
    BEE_DEFS = L["bees"]
    HEART_SPOTS = L["hearts"]
    HONEY_SPOTS = L["honeys"]
    CHECKPOINTS = L["checkpoints"]
    DECOR_TREES = L["trees"]
    DECOR_BAMBOO = L["bamboo"]
    BRIDGE = L["bridge"]
    PLATES = L["plates"]
    GOAL_X = L["goal_x"]
    SOLIDS = ([dict(x=x, y=GROUND_Y, w=w, h=200, oneway=False) for x, w in GROUNDS] +
              [dict(x=x, y=y, w=w, h=16, oneway=True) for x, y, w in WOODS])

# ------------------------------------------------------------------ init
pygame.mixer.pre_init(22050, -16, 1, 256)
pygame.init()
try:
    pygame.mixer.init()
    AUDIO = True
except pygame.error:
    AUDIO = False

# ---- persistent settings (music/sfx volume, fullscreen)
if FROZEN:
    _cfg_dir = os.path.join(os.environ.get("APPDATA", BASE), "BubuDudu")
    os.makedirs(_cfg_dir, exist_ok=True)
    SETTINGS_PATH = os.path.join(_cfg_dir, "settings.json")
else:
    SETTINGS_PATH = os.path.join(BASE, "settings.json")
SETTINGS = {"music": 0.6, "sfx": 0.9, "fullscreen": False, "unlocked": 1}
try:
    with open(SETTINGS_PATH, encoding="utf-8") as _f:
        SETTINGS.update(json.load(_f))
except (OSError, ValueError):
    pass

def save_settings():
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f)
    except OSError:
        pass

def apply_display(first=False):
    global screen
    want_fs = SETTINGS["fullscreen"]
    if not first:
        cur = pygame.display.get_surface()
        if cur is not None:
            if bool(cur.get_flags() & pygame.FULLSCREEN) != want_fs:
                try:
                    pygame.display.toggle_fullscreen()
                except pygame.error:
                    SETTINGS["fullscreen"] = not want_fs
            return
    try:
        flags = pygame.SCALED | (pygame.FULLSCREEN if want_fs else 0)
        screen = pygame.display.set_mode((VW, VH), flags)
    except pygame.error:
        SETTINGS["fullscreen"] = False
        screen = pygame.display.set_mode((VW, VH))

_icon = os.path.join(ASSETS, "icon.png")
if os.path.isfile(_icon):
    pygame.display.set_icon(pygame.image.load(_icon))
apply_display(first=True)
pygame.display.set_caption("Bubu & Dudu: Picnic Adventure")
clock = pygame.time.Clock()

def load(name):
    return pygame.image.load(os.path.join(ASSETS, name + ".png")).convert_alpha()

if not os.path.isdir(ASSETS):
    sys.exit("assets/ folder not found - run make_assets.py + extract_sprites.py")

IMG = {n: load(n) for n in
       ["bubu_idle1", "bubu_idle2", "bubu_walk1", "bubu_walk2", "bubu_walk3",
        "bubu_jump", "bubu_hurt", "bubu_cheer", "bubu_slide",
        "bubu_wave1", "bubu_wave2",
        "dudu_idle1", "dudu_idle2", "dudu_walk1", "dudu_walk2", "dudu_walk3",
        "dudu_walk4", "dudu_jump", "dudu_cheer", "dudu_slide",
        "dudu_wave1", "dudu_wave2",
        "stack_bubu_on_dudu1", "stack_bubu_on_dudu2", "stack_bubu_on_dudu_c",
        "stack_dudu_on_bubu1", "stack_dudu_on_bubu2", "stack_dudu_on_bubu_c",
        "bee1", "bee2", "heart", "heart_pale", "heart_white", "honey",
        "tree", "tree2", "tree3", "bamboo",
        "cloud", "cloud2", "cloud3", "cloud4", "flag_off", "flag_on",
        "basket", "sign", "balloon"]}

def fit_box(img, w, h, anchor="center"):
    """img scaled (aspect kept) into a w x h canvas - newer art keeps the old
    sprite's box so every position in the code stays the same."""
    k = min(w / img.get_width(), h / img.get_height())
    s = pygame.transform.smoothscale(img, (max(1, round(img.get_width() * k)),
                                           max(1, round(img.get_height() * k))))
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    if anchor == "bottomleft":
        out.blit(s, (0, h - s.get_height()))
    else:
        out.blit(s, ((w - s.get_width()) // 2, (h - s.get_height()) // 2))
    return out

# second-round art from import_sheets.py replaces the first-generation sprites
for _old, _new, _anchor in (("heart", "heart_new", "center"), ("honey", "honey_new", "center"),
                            ("bee1", "bee_new1", "center"), ("bee2", "bee_new2", "center"),
                            ("flag_off", "cp_flag_off", "bottomleft"),
                            ("flag_on", "cp_flag_on", "bottomleft")):
    if os.path.isfile(os.path.join(ASSETS, _new + ".png")):
        IMG[_old] = fit_box(load(_new), *IMG[_old].get_size(), _anchor)
        if _old == "heart":   # the pale HUD/menu heart is a lighter copy of it
            IMG["heart_pale"] = IMG["heart"].copy()
            IMG["heart_pale"].fill((80, 80, 80), special_flags=pygame.BLEND_RGB_ADD)
for _old, _new, _w in (("cloud", "cloud_new1", 90), ("cloud2", "cloud_new2", 130),
                       ("cloud3", "cloud_new3", 170), ("cloud4", "cloud_new4", 150)):
    if os.path.isfile(os.path.join(ASSETS, _new + ".png")):
        _c = load(_new)
        IMG[_old] = pygame.transform.smoothscale(
            _c, (_w, round(_c.get_height() * _w / _c.get_width())))
FLIP = {k: pygame.transform.flip(v, True, False) for k, v in IMG.items()}
_menu_bg = os.path.join(ASSETS, "menu_bg.png")
MENU_BG = pygame.image.load(_menu_bg).convert() if os.path.isfile(_menu_bg) else None
# pickup icons from import_items.py (code-drawn fallback when missing)
ITEM_IMG = {k: load(f) for k, f in (("shield", "pu_shield"), ("feather", "pu_feather"),
                                    ("magnet", "pu_magnet"), ("berry", "pu_berry"),
                                    ("star", "star"))
            if os.path.isfile(os.path.join(ASSETS, f + ".png"))}
# creatures, platforms, terrain and sky from import_sheets.py (optional too)
ART = {n: load(n) for n in
       ["bat1", "bat2", "owl_sit", "owl_fly", "owl_sit_eyes", "owl_fly_eyes",
        "plank_wood", "plank_pink", "plank_moon", "mushroom", "mushroom_squash",
        "plate_up", "plate_down", "blanket", "ground", "sun", "moon",
        "prop_basket", "prop_sign", "prop_balloon", "prop_bamboo", "blanket_flat",
        "bamboo_s", "bamboo_m", "bamboo_l", "hill_far", "hill_near"] +
       [f"bf_{c}_{f}" for c in ("pink", "lilac", "yellow") for f in ("open", "closed")]
       if os.path.isfile(os.path.join(ASSETS, n + ".png"))}

def fit_h(img, h):
    return pygame.transform.smoothscale(img, (max(1, round(img.get_width() * h / img.get_height())), h))

_stretch_cache = {}
def stretch(name, w, h):
    """ART[name] scaled to exactly w x h (cached - platforms come in few sizes)."""
    key = (name, w, h)
    if key not in _stretch_cache:
        _stretch_cache[key] = pygame.transform.smoothscale(ART[name], (max(1, w), max(1, h)))
    return _stretch_cache[key]

def ground_strip(w):
    """Grass strip of any width. The sprite's ends don't line up, so it is
    tiled mirrored (every other copy flipped) - no seams - and the block gets
    its own outlined, rounded sides."""
    key = ("ground", w)
    if key not in _stretch_cache:
        g = fit_h(ART["ground"], 74)
        gh = g.get_height()
        mid = g.subsurface((4, 0, g.get_width() - 8, gh))   # drop the ragged ends
        pair = (mid, pygame.transform.flip(mid, True, False))
        s = pygame.Surface((w, gh), pygame.SRCALPHA)
        x, i = 0, 0
        while x < w:
            s.blit(pair[i % 2], (x, 0))
            x += mid.get_width()
            i += 1
        # round the top corners off and outline the sides like the top edge
        mask = pygame.Surface((w, gh), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 2, w, gh + 20), border_radius=10)
        s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        pygame.draw.rect(s, (92, 62, 44), (0, 2, w, gh + 20), 3, border_radius=10)
        _stretch_cache[key] = s.convert_alpha()
    return _stretch_cache[key]

MOB_ART = {}
if "bat1" in ART:
    MOB_ART["bat"] = [fit_h(ART["bat1"], 42), fit_h(ART["bat2"], 36)]
if "owl_sit" in ART:
    MOB_ART["owl"] = [fit_h(ART["owl_sit"], 52), fit_h(ART["owl_fly"], 60)]
    MOB_ART["owl_eyes"] = [fit_h(ART["owl_sit_eyes"], 52), fit_h(ART["owl_fly_eyes"], 60)]
SUN_IMG = fit_h(ART["sun"], 112) if "sun" in ART else None
MOON_IMG = fit_h(ART["moon"], 96) if "moon" in ART else None
HUD_SUN = fit_h(ART["sun"], 30) if "sun" in ART else None
HUD_MOON = fit_h(ART["moon"], 28) if "moon" in ART else None
def mirrored_pair(img):
    """img + its mirror image: tiles seamlessly even when the ends don't match."""
    s = pygame.Surface((img.get_width() * 2, img.get_height()), pygame.SRCALPHA)
    s.blit(img, (0, 0))
    s.blit(pygame.transform.flip(img, True, False), (img.get_width(), 0))
    return s.convert_alpha()

# parallax hill layers: (tile, scroll factor); the far one is drawn first
HILLS = [(mirrored_pair(fit_h(ART[n], h)), k) for n, h, k in
         (("hill_far", 200, .3), ("hill_near", 150, .55)) if n in ART]
# decor bamboo by height (120 / 140 / 160): 3 clumps, or the single stalk
_bam = [ART.get(n) for n in ("bamboo_s", "bamboo_m", "bamboo_l")]
if all(_bam):
    BAMBOO_IMG = {h: fit_h(b, h) for h, b in zip((120, 140, 160), _bam)}
elif "prop_bamboo" in ART:
    BAMBOO_IMG = {h: fit_h(ART["prop_bamboo"], h) for h in (120, 140, 160)}
else:
    BAMBOO_IMG = {}
# butterfly sprites keyed by the colour reset() picks: (wings open, wings closed)
BF_COLORS = {(255, 150, 180): "pink", (190, 160, 255): "lilac", (255, 220, 120): "yellow"}
BF_ART = {col: (fit_h(ART[f"bf_{n}_open"], 18), fit_h(ART[f"bf_{n}_closed"], 19))
          for col, n in BF_COLORS.items() if f"bf_{n}_open" in ART}
GOAL_ART = {}
if "prop_basket" in ART:
    GOAL_ART = dict(basket=fit_h(ART["prop_basket"], 58), sign=fit_h(ART["prop_sign"], 84),
                    balloon=fit_h(ART["prop_balloon"], 120))
HEART_S = pygame.transform.smoothscale(IMG["heart"], (18, 17))
HEART_HUD = pygame.transform.smoothscale(IMG["heart_pale"], (15, 14))

_fonts = {}
def font(size):
    if size not in _fonts:    # SysFont is slow - build each size only once
        _fonts[size] = pygame.font.SysFont("comicsansms", size, bold=True)
    return _fonts[size]

# ------------------------------------------------------------------ tiny synth sfx
def tone(freq, dur, shape="square", vol=0.14, slide=0.0):
    sr = 22050
    n = int(sr * dur)
    a = array("h")
    ph = 0.0
    for i in range(n):
        f = freq + slide * (i / n)
        ph += f / sr
        env = 1.0 - i / n
        p = ph % 1.0
        if shape == "square":
            v = 1.0 if p < 0.5 else -1.0
        elif shape == "sine":
            v = math.sin(2 * math.pi * ph)
        elif shape == "tri":
            v = 4 * abs(p - 0.5) - 1
        else:  # saw
            v = 2 * p - 1
        a.append(int(32767 * vol * env * v))
    return a

def silence(dur):
    return array("h", [0] * int(22050 * dur))

def sound(*parts):
    if not AUDIO:
        return None
    buf = array("h")
    for p in parts:
        buf.extend(p)
    return pygame.mixer.Sound(buffer=buf.tobytes())

SFX = {
    "jump":   sound(tone(320, .18, "square", .10, 260)),
    "heart":  sound(tone(780, .09, "sine", .16), tone(1180, .12, "sine", .16)),
    "honey":  sound(tone(520, .1, "tri", .18), tone(660, .1, "tri", .18), tone(880, .16, "tri", .18)),
    "stomp":  sound(tone(180, .16, "square", .18, -90)),
    "hurt":   sound(tone(150, .28, "saw", .13, -60)),
    "fall":   sound(tone(400, .5, "saw", .11, -320)),
    "check":  sound(tone(600, .1, "sine", .15), tone(900, .18, "sine", .15)),
    "spring": sound(tone(240, .22, "square", .15, 420)),
    "click":  sound(tone(300, .07, "square", .13, 80)),
    "life":   sound(tone(660, .1, "sine", .16), tone(880, .1, "sine", .16),
                    tone(1100, .16, "sine", .16)),
    "power":  sound(tone(440, .08, "tri", .17), tone(587, .08, "tri", .17),
                    tone(880, .14, "tri", .17, 120)),
    "night":  sound(tone(660, .1, "sine", .14), tone(440, .1, "sine", .14),
                    tone(330, .24, "sine", .14, -60)),
    "day":    sound(tone(440, .1, "sine", .14), tone(660, .1, "sine", .14),
                    tone(880, .2, "sine", .14, 80)),
    "star":   sound(tone(988, .07, "sine", .15), tone(1319, .07, "sine", .15),
                    tone(1760, .16, "sine", .15)),
    "win":    sound(*sum([[tone(f, .22, "sine", .16), silence(.04)]
                          for f in (523, 659, 784, 1047, 1319)], [])),
}

def play(name):
    s = SFX.get(name)
    if s:
        s.set_volume(SETTINGS["sfx"])
        s.play()

# ------------------------------------------------------------------ background music
NOTE = {"C3": 130.81, "F2": 87.31, "G2": 98.0, "A2": 110.0, "F3": 174.61,
        "G3": 196.0, "A3": 220.0, "G4": 392.0, "A4": 440.0, "B4": 493.88,
        "C5": 523.25, "D5": 587.33, "E5": 659.26, "F5": 698.46, "G5": 783.99,
        "A5": 880.0}

def build_music():
    """A quiet 16-second lullaby loop (C - Am - F - G), synthesized in code."""
    sr = 22050
    beat = 0.5
    melody = [("C5", 1), ("E5", 1), ("G5", 1), ("E5", 1),
              ("A4", 1), ("C5", 1), ("E5", 1.5), ("D5", .5),
              ("A4", 1), ("F5", 1), ("E5", 1), ("C5", 1),
              ("D5", 1), ("B4", 1), ("G4", 2),
              ("E5", 1), ("G5", 1), ("A5", 1), ("G5", 1),
              ("E5", 1), ("C5", 1), ("A4", 2),
              ("F5", 1), ("E5", 1), ("D5", 1), ("C5", 1),
              ("D5", 2), ("C5", 2)]
    bass = ["C3", "A2", "F3", "G3", "C3", "A2", "F3", "G3"]
    total = int(32 * beat * sr)
    buf = [0] * total

    def note(start_s, freq, dur_s, vol, tri=False):
        i0 = int(start_s * sr)
        n = int(dur_s * sr)
        atk = max(1, int(.02 * sr))
        rel = max(1, int(n * .3))
        ph = 0.0
        for i in range(n):
            ph += freq / sr
            if tri:
                p = ph % 1.0
                v = 4 * abs(p - .5) - 1
            else:
                v = math.sin(2 * math.pi * ph)
            env = 1.0
            if i < atk:
                env = i / atk
            if i > n - rel:
                env = (n - i) / rel
            idx = i0 + i
            if idx < total:
                buf[idx] += int(32767 * vol * env * v)

    t = 0.0
    for name, beats in melody:
        note(t, NOTE[name], beats * beat * .95, .10)
        t += beats * beat
    for bar, root in enumerate(bass):
        note(bar * 4 * beat, NOTE[root], 4 * beat * .95, .07, tri=True)

    clipped = array("h", (max(-32767, min(32767, v)) for v in buf))
    return pygame.mixer.Sound(buffer=clipped.tobytes())

MUSIC = build_music() if AUDIO else None

def apply_music_volume():
    if MUSIC:
        MUSIC.set_volume(SETTINGS["music"] * 0.6)

if MUSIC:
    apply_music_volume()
    MUSIC.play(loops=-1)

# ------------------------------------------------------------------ game state
class Player:
    def __init__(self, kind, x):
        self.kind = kind                 # "bubu" or "dudu"
        self.x, self.y = x, GROUND_Y - 60
        self.w, self.h = 44, 54
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.facing = 1
        self.walk = 0.0
        self.squash = 0.0
        self.invuln = 0.0
        self.checkpoint = 60
        self.crouch = False
        self.idle_t = 0.0
        self.prev_x = x
        self.fx = {}           # active power-up effects: name -> seconds left
        self.air_jumps = 0     # extra jumps granted by the feather
        self.jump_held = False

class Bee:
    def __init__(self, d):
        self.x1, self.x2, self.y, self.spd = d["x1"], d["x2"], d["y"], d["spd"]
        self.x = self.x1
        self.dir = 1
        self.dead = False

class NightMob:
    """Bats patrol and swoop at nearby bears; owls sit on a tree top and dive
    when a bear walks underneath. They only exist at night."""
    def __init__(self, kind, d):
        self.kind = kind
        if kind == "bat":
            self.x1, self.x2, self.hy, self.spd = d["x1"], d["x2"], d["y"], d["spd"]
            self.hx = self.x1
        else:                                  # owl: d is the tree's x
            self.hx, self.hy = d, GROUND_Y - 112
        self.dead = False
        self.home()

    def home(self):
        self.x, self.y = self.hx, self.hy
        self.mode = "idle"
        self.cd = 1.0          # grace time before the first attack
        self.dir = 1
        self.t = random.random() * 6
        self.tx = self.ty = 0.0
        self.dive_t = 0.0

    def move_to(self, tx, ty, spd, dt):
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        if d < 1:
            return True
        step = min(d, spd * dt)
        self.x += dx / d * step
        self.y += dy / d * step
        if abs(dx) > 2:
            self.dir = 1 if dx > 0 else -1
        return step >= d - 1

    def update(self, dt, bears):
        self.t += dt
        self.cd -= dt
        bat = self.kind == "bat"
        if self.mode == "dive":
            self.dive_t -= dt
            if self.move_to(self.tx, self.ty, 290 if bat else 330, dt) or self.dive_t <= 0:
                self.mode = "back"
        elif self.mode == "back":
            hx = max(self.x1, min(self.x2, self.x)) if bat else self.hx
            if self.move_to(hx, self.hy, 160 if bat else 190, dt):
                self.mode = "idle"
                self.cd = 2.2 if bat else 3.5
        else:
            if bat:
                self.x += self.spd * self.dir * dt
                if self.x > self.x2: self.dir = -1
                if self.x < self.x1: self.dir = 1
                self.y = self.hy + math.sin(self.t * 3) * 12
            if self.cd <= 0:
                reach = 170 if bat else 100
                for p in bears:
                    cx, cy = p.x + p.w / 2, p.y + p.h / 2
                    if abs(cx - self.x) < reach and cy > self.y:
                        self.mode = "dive"
                        self.tx, self.ty = cx, cy
                        self.dive_t = 1.1
                        break

    def hitbox(self):
        if self.kind == "bat":
            return dict(x=self.x - 15, y=self.y - 10, w=30, h=20)
        return dict(x=self.x - 16, y=self.y - 18, w=32, h=36)

class Mover:
    def __init__(self, d):
        self.d = d
        self.w = d["w"]
        self.x, self.y = d["x0"], d["y0"]
        self.dx = self.dy = 0.0

    def update(self, t):
        k = (math.sin(math.tau * t / self.d["period"]) + 1) / 2
        nx = self.d["x0"] + (self.d["x1"] - self.d["x0"]) * k
        ny = self.d["y0"] + (self.d["y1"] - self.d["y0"]) * k
        self.dx, self.dy = nx - self.x, ny - self.y
        self.x, self.y = nx, ny

level_num = 1
apply_level(SETTINGS.get("unlocked", 1))

def reset():
    global players, bees, hearts, honeys, cam, lives, heart_count
    global state, win_t, shake_t, particles, check_flags
    global movers, spring_t, bridge_active, run_time, butterflies, next_life_at
    global just_unlocked
    just_unlocked = False
    next_life_at = 10
    global powerups, night, night_k, shift_cd, mobs, stars
    night, night_k, shift_cd = False, 0.0, 0.0
    mobs = [NightMob("bat", d) for d in BAT_DEFS] + [NightMob("owl", x) for x in OWL_SPOTS]
    stars = [dict(x=x, y=y, got=False) for x, y in STAR_SPOTS]
    players = [Player("bubu", 60), Player("dudu", 130)]
    bees = [Bee(d) for d in BEE_DEFS]
    hearts = [dict(x=x, y=y, got=False, t=random.random() * 6) for x, y in HEART_SPOTS]
    honeys = [dict(x=x, y=y, got=False) for x, y in HONEY_SPOTS]
    powerups = [dict(x=x, y=y, kind=k, got=False) for x, y, k in POWERUP_SPOTS]
    movers = [Mover(d) for d in MOVER_DEFS]
    spring_t = [0.0] * len(SPRINGS)
    bridge_active = False
    cam = 0.0
    lives = 5
    heart_count = 0
    state = "menu"
    win_t = 0.0
    shake_t = 0.0
    run_time = 0.0
    particles = []
    check_flags = [dict(x=x, hit=False) for x in CHECKPOINTS]
    butterflies = [dict(bx=random.uniform(150, LEVEL_W - 150),
                        by=random.uniform(120, 360),
                        t=random.uniform(0, 20),
                        col=random.choice([(255, 150, 180), (190, 160, 255), (255, 220, 120)]))
                   for _ in range(max(6, LEVEL_W // 800))]

def start_level(n):
    global state, can_continue
    apply_level(n)
    reset()
    state = "play"
    can_continue = True

reset()
time_s = 0.0
menu_sel = 0
settings_sel = 0
levels_sel = 0
can_continue = False

DEFAULT_CONTROLS = [
    dict(l=pygame.K_a, r=pygame.K_d, u=pygame.K_w, dn=pygame.K_s, sh=pygame.K_LSHIFT),
    dict(l=pygame.K_LEFT, r=pygame.K_RIGHT, u=pygame.K_UP, dn=pygame.K_DOWN,
         sh=pygame.K_RSHIFT),
]
CONTROLS = [dict(c) for c in DEFAULT_CONTROLS]
for _i, _saved in enumerate(SETTINGS.get("controls", [])[:2]):
    for _k in ("l", "r", "u", "dn", "sh"):
        if isinstance(_saved.get(_k), int):
            CONTROLS[_i][_k] = _saved[_k]

def save_controls():
    SETTINGS["controls"] = [dict(c) for c in CONTROLS]
    save_settings()

def rects_hit(px, py, pw, ph, s):
    return px < s["x"] + s["w"] and px + pw > s["x"] and py < s["y"] + s["h"] and py + ph > s["y"]

def burst(x, y, color, n=10, heart_p=False):
    for _ in range(n):
        a = random.random() * math.tau
        sp = 60 + random.random() * 160
        particles.append(dict(x=x, y=y, vx=math.cos(a) * sp, vy=math.sin(a) * sp - 80,
                              life=.7 + random.random() * .4, color=color, heart=heart_p))

def add_hearts(n, x, y):
    """Collected hearts also earn an extra life every 10."""
    global heart_count, lives, next_life_at
    heart_count += n
    while heart_count >= next_life_at:
        lives += 1
        next_life_at += 10
        play("life")
        burst(x, y - 24, (126, 224, 129), 10, True)

def safe_ground_x(want, lo, hi, w):
    """Nearest x to want inside [lo, hi] where the whole body sits on ground.
    Keeps a respawning bear from being leash-clamped over a pit."""
    best = None
    for gx, gw in GROUNDS:
        a, b = max(gx, lo), min(gx + gw - w, hi)
        if a > b:
            continue
        c = max(a, min(b, want))
        if best is None or abs(c - want) < abs(best - want):
            best = c
    return want if best is None else best

def toggle_night():
    """Either bear's Shift flips day <-> night (short cooldown between flips)."""
    global night, shift_cd
    if shift_cd > 0:
        return
    night = not night
    shift_cd = SHIFT_CD
    play("night" if night else "day")
    for m in mobs:           # night creatures (re)start from their perches
        m.home()

def hurt_player(p, src_x):
    """Knock-back and lose a life; returns True when it was the last one."""
    global lives, shake_t
    play("hurt")
    p.invuln = 1.6
    shake_t = .25
    p.vy = -380
    p.x += -46 if p.x + p.w / 2 < src_x else 46
    lives -= 1
    burst(p.x + p.w / 2, p.y, (255, 95, 143), 5, True)
    return lives <= 0

def plate_pressed(px_):
    for p in players:
        if p.on_ground and abs(p.x + p.w / 2 - px_) < 32 and abs(p.y + p.h - GROUND_Y) < 4:
            return True
    return False

# ------------------------------------------------------------------ update
def update(dt, keys):
    global cam, lives, heart_count, state, win_t, shake_t, time_s
    global bridge_active, run_time
    time_s += dt
    if state in ("menu", "settings", "levels", "help", "controls"):
        return
    if shake_t > 0:
        shake_t -= dt

    if state in ("play", "win"):
        for b in bees:
            if b.dead or night:       # bees sleep at night
                continue
            b.x += b.spd * b.dir * dt
            if b.x > b.x2: b.dir = -1
            if b.x < b.x1: b.dir = 1
        for bf in butterflies:
            bf["t"] += dt
        for i in range(len(spring_t)):
            if spring_t[i] > 0:
                spring_t[i] -= dt

    if state == "win":
        win_t += dt
        p1, p2 = players
        mid = (p1.x + p2.x) / 2
        for p in players:
            target = mid - p.x + (-24 if p is p1 else 24)
            p.x += max(-60, min(60, target * 2)) * dt
            p.facing = 1 if p is p1 else -1
            p.walk += dt * 6
        if random.random() < .12:
            burst(mid + 22 + (random.random() - .5) * 120,
                  players[0].y - 20 - random.random() * 60, (255, 95, 143), 1, True)
        update_particles(dt)
        return
    if state != "play":
        update_particles(dt)
        return

    run_time += dt

    # ---- day / night
    global shift_cd, night_k
    shift_cd = max(0.0, shift_cd - dt)
    target_k = 1.0 if night else 0.0
    night_k += max(-dt * 2.5, min(dt * 2.5, target_k - night_k))
    if night:
        for m in mobs:
            if not m.dead:
                m.update(dt, players)

    # ---- moving platforms + carry riders
    for mv in movers:
        old_x, old_y = mv.x, mv.y
        mv.update(time_s)
        for p in players:
            if p.on_ground and p.x + p.w > old_x and p.x < old_x + mv.w \
                    and abs(p.y + p.h - old_y) < 6:
                p.x += mv.dx
                p.y = mv.y - p.h

    # ---- co-op bridge plates
    was_active = bridge_active
    bridge_active = bool(PLATES) and any(plate_pressed(px_) for px_ in PLATES)
    if bridge_active and not was_active:
        play("click")

    solids_now = SOLIDS + [dict(x=mv.x, y=mv.y, w=mv.w, h=14, oneway=True) for mv in movers]
    if bridge_active and BRIDGE:
        solids_now = solids_now + [dict(x=BRIDGE["x"], y=BRIDGE["y"], w=BRIDGE["w"],
                                        h=BRIDGE["h"], oneway=True)]
    if night:                 # moon platforms only exist at night
        solids_now = solids_now + [dict(x=x, y=y, w=w, h=14, oneway=True)
                                   for x, y, w in MOONS]

    for p in players:
        p.prev_x = p.x

    for i, p in enumerate(players):
        c = CONTROLS[i]
        # power-up timers
        for k in list(p.fx):
            p.fx[k] -= dt
            if p.fx[k] <= 0:
                del p.fx[k]
        if p.on_ground:
            p.air_jumps = 1

        p.crouch = bool(keys[c["dn"]]) and p.on_ground
        boost = 1.45 if "honey" in p.fx else 1.0
        ax = 0
        if not p.crouch:
            if keys[c["l"]]: ax = -1; p.facing = -1
            if keys[c["r"]]: ax = 1; p.facing = 1
        p.vx = ax * MOVE * boost
        jump_v = JUMP * (1.12 if "honey" in p.fx else 1.0)
        press = keys[c["u"]] and not p.jump_held
        p.jump_held = bool(keys[c["u"]])
        if press and p.on_ground and not p.crouch:
            p.vy = -jump_v
            p.on_ground = False
            p.squash = -.25
            play("jump")
        elif press and not p.on_ground and "feather" in p.fx and p.air_jumps > 0:
            p.vy = -jump_v * .92          # feather double jump!
            p.air_jumps -= 1
            p.squash = -.2
            play("jump")
            burst(p.x + p.w / 2, p.y + p.h, (140, 190, 255), 6)
        p.vy = min(p.vy + GRAV * dt, 900)
        if ax != 0 and p.on_ground:
            p.walk += dt * 11
        elif p.on_ground:
            p.walk = 0
        if p.on_ground and ax == 0 and not p.crouch:
            p.idle_t += dt
            if p.idle_t > 10:
                p.idle_t = 0
        else:
            p.idle_t = 0
        if p.invuln > 0:
            p.invuln -= dt
        p.squash *= math.pow(.001, dt)

        # horizontal move + collide with solid ground blocks
        p.x += p.vx * dt
        for s in solids_now:
            if s["oneway"]:
                continue
            if rects_hit(p.x, p.y, p.w, p.h, s):
                p.x = s["x"] - p.w if p.vx > 0 else s["x"] + s["w"]
        # bears are solid to each other - you can't walk through your partner
        # (small vertical overlaps are ignored so landing on the head still works)
        o = players[1 - i]
        v_overlap = min(p.y + p.h, o.y + o.h) - max(p.y, o.y)
        if v_overlap > 22 and p.x < o.x + o.w and p.x + p.w > o.x:
            if p.vx > 0 and p.x + p.w / 2 <= o.x + o.w / 2:
                p.x = o.x - p.w
            elif p.vx < 0 and p.x + p.w / 2 >= o.x + o.w / 2:
                p.x = o.x + o.w
            else:   # somehow inside each other - separate gently
                p.x += (60 * dt) if p.x + p.w / 2 >= o.x + o.w / 2 else (-60 * dt)

        # keep both bears on screen together (co-op leash)
        p.x = max(cam + 6, min(cam + VW - p.w - 6, max(0, min(LEVEL_W - p.w, p.x))))

        # vertical move + collide
        was_falling = p.vy > 0
        prev_bottom = p.y + p.h
        prev_top = p.y
        p.y += p.vy * dt
        p.on_ground = False
        for s in solids_now:
            if not rects_hit(p.x, p.y, p.w, p.h, s):
                continue
            if s["oneway"]:
                if was_falling and prev_bottom <= s["y"] + 8:
                    p.y = s["y"] - p.h
                    p.vy = 0
                    p.on_ground = True
            else:
                if was_falling and prev_bottom <= s["y"] + 8:
                    fall_speed = p.vy
                    p.y = s["y"] - p.h
                    p.vy = 0
                    p.on_ground = True
                    # squash only on a real landing, not while standing
                    # (gravity re-triggers this branch every frame)
                    if fall_speed > 300 and abs(p.squash) < .05:
                        p.squash = .2
                elif p.vy < 0 and prev_top >= s["y"] + s["h"] - 8:
                    p.y = s["y"] + s["h"]
                    p.vy = 0

        # land on your partner's head (one-way, like a platform)
        o = players[1 - i]
        head = dict(x=o.x + 4, y=o.y, w=o.w - 8, h=14)
        if was_falling and prev_bottom <= o.y + 10 and rects_hit(p.x, p.y, p.w, p.h, head):
            p.y = o.y - p.h
            p.vy = 0
            p.on_ground = True

        # ---- mushroom springs
        for si, (sx_, sy_) in enumerate(SPRINGS):
            if p.on_ground and abs(p.x + p.w / 2 - sx_) < 28 and abs(p.y + p.h - sy_) < 6:
                p.vy = SPRING_VY
                p.on_ground = False
                p.squash = -.3
                spring_t[si] = .35
                play("spring")

        # fell into a pit
        if p.y > VH + 60:
            play("fall")
            lives -= 1
            shake_t = .3
            if lives <= 0:
                state = "over"
                return
            # offset per player so the two bears never respawn inside each other;
            # the co-op leash will clamp them on screen, so pick a spot that is
            # both visible AND over solid ground (never above a pit)
            lo, hi = cam + 6, cam + VW - p.w - 6
            want = max(lo, min(hi, max(lo, min(hi, p.checkpoint)) + i * 56))
            p.x, p.y = safe_ground_x(want, lo, hi, p.w), GROUND_Y - 120
            p.vx = p.vy = 0
            p.invuln = 2
            p.fx.clear()          # death wipes all active boosts
            p.air_jumps = 0

        # checkpoints
        for cf in check_flags:
            if not cf["hit"] and p.x + p.w / 2 > cf["x"]:
                cf["hit"] = True
                play("check")
                burst(cf["x"], GROUND_Y - 70, (126, 224, 129), 8)
            if cf["hit"]:
                p.checkpoint = max(p.checkpoint, cf["x"])

        # hearts & honey
        for h in hearts:
            if not h["got"] and abs(p.x + p.w / 2 - h["x"]) < 30 and abs(p.y + p.h / 2 - h["y"]) < 34:
                h["got"] = True
                add_hearts(1, h["x"], h["y"])
                play("heart")
                burst(h["x"], h["y"], (255, 95, 143), 7, True)
        for h in honeys:
            if not h["got"] and abs(p.x + p.w / 2 - h["x"]) < 30 and abs(p.y + p.h / 2 - h["y"]) < 34:
                h["got"] = True
                add_hearts(1, h["x"], h["y"])
                p.fx["honey"] = FX_DURATION          # honey rush: speed + jump
                play("honey")
                burst(h["x"], h["y"], (255, 185, 54), 12)
        for pu in powerups:
            if not pu["got"] and abs(p.x + p.w / 2 - pu["x"]) < 30 and abs(p.y + p.h / 2 - pu["y"]) < 34:
                pu["got"] = True
                p.fx[pu["kind"]] = FX_DURATION
                play("power")
                burst(pu["x"], pu["y"], (255, 210, 62), 10)
        if night:             # night stars are worth 3 hearts
            for st in stars:
                if not st["got"] and abs(p.x + p.w / 2 - st["x"]) < 30 \
                        and abs(p.y + p.h / 2 - st["y"]) < 34:
                    st["got"] = True
                    add_hearts(3, st["x"], st["y"])
                    play("star")
                    burst(st["x"], st["y"], (255, 235, 120), 12)
        # magnet: nearby hearts fly to the bear
        if "magnet" in p.fx:
            pcx, pcy = p.x + p.w / 2, p.y + p.h / 2
            for h in hearts:
                if h["got"]:
                    continue
                dx, dy = pcx - h["x"], pcy - h["y"]
                d2 = dx * dx + dy * dy
                if 1 < d2 < 160 * 160:
                    d = d2 ** .5
                    h["x"] += dx / d * 320 * dt
                    h["y"] += dy / d * 320 * dt
        # honey rush leaves a golden sparkle trail
        if "honey" in p.fx and p.on_ground and p.vx != 0 and random.random() < .3:
            particles.append(dict(x=p.x + p.w / 2 - p.facing * 20, y=p.y + p.h - 6,
                                  vx=-p.facing * 40, vy=-random.uniform(10, 60),
                                  life=.5, color=(255, 200, 80), heart=False))

        # bees
        for b in bees:
            if b.dead or night:
                continue
            bb = dict(x=b.x - 20, y=b.y - 16, w=40, h=32)
            if not rects_hit(p.x, p.y, p.w, p.h, bb):
                continue
            if p.vy > 120 and p.y + p.h < b.y + 6:          # stomp!
                b.dead = True
                p.vy = -JUMP * .55
                play("stomp")
                burst(b.x, b.y, (255, 210, 62), 10)
                add_hearts(1, b.x, b.y)
            elif "berry" in p.fx:                            # big berry bear squishes bees
                b.dead = True
                play("stomp")
                burst(b.x, b.y, (255, 210, 62), 10)
                add_hearts(1, b.x, b.y)
            elif "shield" in p.fx:                           # honeycomb shield - bee bounces off
                if (b.dir > 0) == (b.x < p.x + p.w / 2):
                    b.dir *= -1
            elif p.crouch:                                   # ducked - bee flies over
                pass
            elif p.invuln <= 0:                              # ouch - costs a life
                if hurt_player(p, b.x):
                    state = "over"
                    return

        # night mobs - crouching doesn't help, they dive at you
        for m in mobs:
            if m.dead or not night:
                continue
            if not rects_hit(p.x, p.y, p.w, p.h, m.hitbox()):
                continue
            if (p.vy > 120 and p.y + p.h < m.y + 8) or "berry" in p.fx:   # stomp / squish
                m.dead = True
                if p.vy > 120:
                    p.vy = -JUMP * .55
                play("stomp")
                burst(m.x, m.y, (170, 150, 230), 10)
                add_hearts(1, m.x, m.y)
            elif "shield" in p.fx:                           # bounces off the shield
                m.mode = "back"
            elif p.invuln <= 0:
                m.mode = "back"
                if hurt_player(p, m.x):
                    state = "over"
                    return

    # riding: the top bear moves along with the bottom one; when the rider
    # gives no input, gently center them so the stacked artwork lines up
    for i, p in enumerate(players):
        o = players[1 - i]
        if p.on_ground and abs(p.y + p.h - o.y) < 4 \
                and p.x + p.w > o.x and p.x < o.x + o.w:
            p.x += o.x - o.prev_x
            c = CONTROLS[i]
            if not keys[c["l"]] and not keys[c["r"]]:
                p.x += (o.x - p.x) * min(1, dt * 6)

    # camera follows the midpoint of the two bears
    mid_x = (players[0].x + players[1].x) / 2 + 22
    cam += ((mid_x - VW / 2) - cam) * min(1, dt * 6)
    cam = max(0, min(LEVEL_W - VW, cam))

    # win check - BOTH bears on the picnic blanket
    def on_goal(p):
        cx = p.x + p.w / 2
        return p.on_ground and GOAL_X < cx < GOAL_X + GOAL_W
    if on_goal(players[0]) and on_goal(players[1]):
        state = "win"
        win_t = 0
        play("win")
        if level_num >= SETTINGS["unlocked"]:
            global just_unlocked
            SETTINGS["unlocked"] = level_num + 1
            just_unlocked = True
            save_settings()

    update_particles(dt)

def update_particles(dt):
    global particles
    for pt in particles:
        pt["life"] -= dt
        pt["x"] += pt["vx"] * dt
        pt["y"] += pt["vy"] * dt
        pt["vy"] += 300 * dt
    particles = [p for p in particles if p["life"] > 0]

# ------------------------------------------------------------------ drawing
SKY = pygame.Surface((VW, VH))
for yy in range(VH):
    t = yy / VH
    if t < .65:
        k = t / .65
        col = (int(142 + (207 - 142) * k), int(211 + (238 - 211) * k), int(245 + (251 - 245) * k))
    else:
        k = (t - .65) / .35
        col = (int(207 + (233 - 207) * k), int(238 + (249 - 238) * k), int(251 + (255 - 251) * k))
    pygame.draw.line(SKY, col, (0, yy), (VW, yy))

NIGHT_SKY = pygame.Surface((VW, VH))
for yy in range(VH):
    k = yy / VH
    pygame.draw.line(NIGHT_SKY, (int(14 + 40 * k), int(18 + 30 * k), int(52 + 50 * k)),
                     (0, yy), (VW, yy))
_srng = random.Random(7)
SKY_STARS = [(_srng.randint(0, VW), _srng.randint(0, 330), _srng.random() * 6)
             for _ in range(70)]

# darkness at night, with a soft light circle punched out around each bear
LIGHT_R = 165
LIGHT = pygame.Surface((LIGHT_R * 2, LIGHT_R * 2), pygame.SRCALPHA)
LIGHT.fill((255, 255, 255, 255))
for _r in range(LIGHT_R, 0, -2):
    _a = int(255 * min(1.0, max(0.0, (_r - 45) / (LIGHT_R - 45))) ** 1.4)
    pygame.draw.circle(LIGHT, (255, 255, 255, _a), (LIGHT_R, LIGHT_R), _r)
DARK = pygame.Surface((VW, VH), pygame.SRCALPHA)
SKY_POS = (830, 104)          # sun / moon sprite center (clear of the level panel)

def draw_background(surf):
    if night_k < 1:
        surf.blit(SKY, (0, 0))
    if night_k > 0:           # opaque at full night - a much cheaper blit
        NIGHT_SKY.set_alpha(None if night_k >= 1 else int(255 * night_k))
        surf.blit(NIGHT_SKY, (0, 0))
        for sx, sy, ph in SKY_STARS:
            a = night_k * (.5 + .5 * math.sin(time_s * 2 + ph))
            c = int(120 + 135 * a)
            pygame.draw.circle(surf, (c, c, min(255, c + 20)), (sx, sy), 1 + (ph > 4.5))
    if SUN_IMG:               # the moon sprite is drawn over the darkness (draw_night)
        if night_k < .5:
            surf.blit(SUN_IMG, (SKY_POS[0] - SUN_IMG.get_width() / 2,
                                SKY_POS[1] - SUN_IMG.get_height() / 2))
    elif night_k < .5:
        pygame.draw.circle(surf, (255, 233, 163), (830, 80), 42)
        pygame.draw.circle(surf, (255, 243, 200), (830, 80), 30)
    else:                     # crescent moon
        pygame.draw.circle(surf, (245, 240, 210), (830, 80), 34)
        pygame.draw.circle(surf, (24, 26, 64), (846, 70), 30)
    cloud_variants = ("cloud", "cloud2", "cloud3", "cloud4")
    for i in range(8):
        span = max(LEVEL_W * .5, VW + 200)
        cx = ((i * 460 - cam * .3 + time_s * 8) % span + span) % span - 100
        cy = 60 + (i % 3) * 45
        img = IMG[cloud_variants[i % 4]]
        surf.blit(img, (cx, cy - img.get_height() // 2))
    if HILLS:
        for tile, k in HILLS:
            tw = tile.get_width()
            x = -(cam * k % tw)
            while x < VW:
                surf.blit(tile, (x, VH - tile.get_height()))
                x += tw
        return
    for i in range(11):
        hx = i * 420 - cam * .5 % 420 - 210
        pygame.draw.circle(surf, (184, 230, 176), (int(hx), GROUND_Y + 60), 190)
    for i in range(13):
        hx = i * 300 - cam * .7 % 300 - 100
        pygame.draw.circle(surf, (159, 219, 150), (int(hx), GROUND_Y + 80), 150)

def draw_butterfly(surf, bf, ox):
    x = bf["bx"] + math.sin(bf["t"] * .7) * 60 + ox
    y = bf["by"] + math.sin(bf["t"] * 1.3) * 30
    if x < -20 or x > VW + 20:
        return
    if bf["col"] in BF_ART:
        opened, closed = BF_ART[bf["col"]]
        if math.sin(bf["t"] * 14) > 0:
            img = opened
        else:                 # the folded side view looks left - turn it to the way it flies
            img = closed if math.cos(bf["t"] * .7) < 0 else pygame.transform.flip(closed, True, False)
        surf.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))
        return
    flap = abs(math.sin(bf["t"] * 14))
    w = 3 + 5 * flap
    pygame.draw.ellipse(surf, bf["col"], (x - w, y - 4, w, 8))
    pygame.draw.ellipse(surf, bf["col"], (x, y - 4, w, 8))
    pygame.draw.line(surf, (80, 60, 60), (x, y - 4), (x, y + 4), 2)

MUSH = (fit_h(ART["mushroom"], 56), fit_h(ART["mushroom_squash"], 26)) \
    if "mushroom" in ART else None

def draw_spring(surf, i, ox):
    sx_, sy_ = SPRINGS[i]
    if MUSH:
        img = MUSH[1] if spring_t[i] > .12 else MUSH[0]
        surf.blit(img, (sx_ - img.get_width() / 2 + ox, sy_ + 2 - img.get_height()))
        return
    squash = max(0.0, spring_t[i]) / .35
    ch = 20 * (1 - squash * .5)
    pygame.draw.rect(surf, (245, 235, 220), (sx_ - 8 + ox, sy_ - ch + 4, 16, ch - 4),
                     border_radius=4)
    pygame.draw.ellipse(surf, (255, 111, 145), (sx_ - 24 + ox, sy_ - ch - 12, 48, 22))
    for dx in (-12, 0, 12):
        pygame.draw.circle(surf, (255, 220, 230), (sx_ + dx + ox, sy_ - int(ch) - 2), 4)

def draw_world(surf, ox):
    # decor (culled to the view)
    for x, h in DECOR_BAMBOO:
        if -60 < x + ox < VW + 60:
            if h in BAMBOO_IMG:
                img = BAMBOO_IMG[h]
                surf.blit(img, (x - img.get_width() / 2 + ox, GROUND_Y + 4 - h))
                continue
            img = pygame.transform.smoothscale(IMG["bamboo"], (48, h)) if h != 160 else IMG["bamboo"]
            surf.blit(img, (x - 24 + ox, GROUND_Y - h))
    tree_variants = ("tree", "tree2", "tree3")
    for i, x in enumerate(DECOR_TREES):
        if -100 < x + ox < VW + 100:
            surf.blit(IMG[tree_variants[i % 3]], (x - 48 + ox, GROUND_Y - 118))
    if night_k < .5:          # at night they turn into fireflies (drawn later)
        for bf in butterflies:
            draw_butterfly(surf, bf, ox)

    # ground blocks
    for x, w in GROUNDS:
        if x + w + ox < -50 or x + ox > VW + 50:
            continue
        if "ground" in ART:
            surf.blit(ground_strip(w), (x + ox, GROUND_Y - 12))
            continue
        pygame.draw.rect(surf, (163, 112, 63), (x + ox, GROUND_Y, w, VH - GROUND_Y + 40))
        pygame.draw.rect(surf, (126, 200, 80), (x + ox, GROUND_Y - 6, w, 22), border_radius=8)
        for gx in range(x + 8, x + w - 8, 34):
            if -10 < gx + ox < VW + 10:
                pygame.draw.circle(surf, (147, 216, 103), (gx + ox, GROUND_Y + 2), 6,
                                   draw_top_left=True, draw_top_right=True)
    # wooden platforms
    for x, y, w in WOODS:
        if x + w + ox < -50 or x + ox > VW + 50:
            continue
        if "plank_wood" in ART:
            surf.blit(stretch("plank_wood", w, 20), (x + ox, y - 2))
            continue
        pygame.draw.rect(surf, (197, 143, 82), (x + ox, y, w, 16), border_radius=8)
        for gx in range(x + 12, x + w - 8, 24):
            pygame.draw.rect(surf, (163, 112, 63), (gx + ox, y + 3, 3, 10))
        pygame.draw.rect(surf, (138, 90, 46), (x + ox, y, w, 16), 2, border_radius=8)
    # moon platforms: only a faint dotted hint during the day
    if night_k < .5:
        for x, y, w in MOONS:
            if -50 < x + ox < VW + 50:
                for gx in range(x, x + w, 20):
                    pygame.draw.rect(surf, (225, 230, 250),
                                     (gx + ox, y + 4, 10, 4), border_radius=2)
    # moving platforms (slightly pink so they stand out)
    for mv in movers:
        r = pygame.Rect(int(mv.x) + ox, int(mv.y), mv.w, 14)
        if r.right < -50 or r.left > VW + 50:
            continue
        if "plank_pink" in ART:
            surf.blit(stretch("plank_pink", mv.w, 19), (r.x, r.y - 2))
            continue
        pygame.draw.rect(surf, (232, 176, 158), r, border_radius=7)
        pygame.draw.rect(surf, (188, 122, 104), r, 2, border_radius=7)
        for gx in range(r.x + 10, r.right - 6, 20):
            pygame.draw.rect(surf, (206, 142, 124), (gx, r.y + 3, 3, 8))
    # springs
    for i in range(len(SPRINGS)):
        if -60 < SPRINGS[i][0] + ox < VW + 60:
            draw_spring(surf, i, ox)
    # co-op plates + bridge
    for px_ in PLATES:
        if not (-80 < px_ + ox < VW + 80):
            continue
        pressed = plate_pressed(px_)
        ph_ = 6 if pressed else 12
        if "plate_up" in ART:
            img = stretch("plate_down" if pressed else "plate_up", 52, 30 if pressed else 38)
            surf.blit(img, (px_ - 26 + ox, GROUND_Y + 4 - img.get_height()))
            ph_ = img.get_height() - 4
        else:
            r = pygame.Rect(px_ - 28 + ox, GROUND_Y - ph_, 56, ph_)
            pygame.draw.rect(surf, (255, 111, 145) if not pressed else (211, 63, 107),
                             r, border_radius=5)
            pygame.draw.rect(surf, (211, 63, 107), r, 2, border_radius=5)
            surf.blit(HEART_S, (px_ - 9 + ox, GROUND_Y - ph_ - 20))
        t = font(11).render("step here!", True, (211, 63, 107))
        surf.blit(t, (px_ - t.get_width() // 2 + ox, GROUND_Y - ph_ - 42))
    if BRIDGE:
        if bridge_active and "plank_wood" in ART:
            surf.blit(stretch("plank_wood", BRIDGE["w"], BRIDGE["h"] + 8),
                      (BRIDGE["x"] + ox, BRIDGE["y"] - 2))
        elif bridge_active:
            r = pygame.Rect(BRIDGE["x"] + ox, BRIDGE["y"], BRIDGE["w"], BRIDGE["h"])
            pygame.draw.rect(surf, (222, 184, 135), r, border_radius=6)
            for gx in range(r.x + 8, r.right - 6, 18):
                pygame.draw.rect(surf, (188, 146, 98), (gx, r.y + 2, 3, 8))
            pygame.draw.rect(surf, (166, 124, 82), r, 2, border_radius=6)
        else:
            for gx in range(BRIDGE["x"], BRIDGE["x"] + BRIDGE["w"], 24):
                pygame.draw.rect(surf, (200, 200, 200),
                                 (gx + ox, BRIDGE["y"] + 4, 14, 4), border_radius=2)
    # checkpoint flags
    for cf in check_flags:
        if -60 < cf["x"] + ox < VW + 60:
            img = IMG["flag_on"] if cf["hit"] else IMG["flag_off"]
            surf.blit(img, (cf["x"] - 7 + ox, GROUND_Y - 94))
    # picnic goal
    gx = GOAL_X + ox
    if gx < VW + 100 and GOAL_ART:
        cx = gx + GOAL_W // 2
        if "blanket_flat" in ART:
            surf.blit(stretch("blanket_flat", GOAL_W + 16, 14), (gx - 8, GROUND_Y - 10))
        sign = GOAL_ART["sign"]
        sx = gx - 60 - sign.get_width() / 2
        surf.blit(sign, (sx, GROUND_Y + 2 - sign.get_height()))
        f = font(13)
        for i, line in enumerate(("PICNIC", "GOAL")):
            t = f.render(line, True, (160, 70, 95))
            surf.blit(t, (sx + sign.get_width() / 2 - t.get_width() / 2,
                          GROUND_Y + 2 - sign.get_height() + 7 + i * 17))
        bal = GOAL_ART["balloon"]
        by = GROUND_Y - 36 + math.sin(time_s * 2) * 5
        surf.blit(bal, (cx + 34 - bal.get_width() / 2, by - bal.get_height()))
        bk = GOAL_ART["basket"]
        surf.blit(bk, (cx - bk.get_width() / 2, GROUND_Y - 4 - bk.get_height()))
    elif gx < VW + 100:
        if "blanket" in ART:
            img = stretch("blanket", GOAL_W + 20, 50)
            surf.blit(img, (gx - 10, GROUND_Y + 10 - img.get_height()))
        else:
            pygame.draw.rect(surf, (232, 86, 79), (gx, GROUND_Y - 8, GOAL_W, 14), border_radius=5)
            for i in range(GOAL_W // 20):
                if i % 2 == 0:
                    pygame.draw.rect(surf, (255, 255, 255), (gx + i * 20 + 2, GROUND_Y - 6, 16, 10))
        surf.blit(IMG["basket"], (gx + GOAL_W // 2 - 32, GROUND_Y - 60))
        by = GROUND_Y - 148 + math.sin(time_s * 2) * 6
        surf.blit(IMG["balloon"], (gx + GOAL_W // 2 + 20, by))
        surf.blit(IMG["sign"], (gx - 96, GROUND_Y - 76))

WALK_FRAMES = {"bubu": ["bubu_walk1", "bubu_walk2", "bubu_walk3"],
               "dudu": ["dudu_walk1", "dudu_walk2", "dudu_walk3", "dudu_walk4"]}

def bear_frame(p):
    name = p.kind
    if state == "win":
        f = name + ("_cheer" if int(time_s * 3) % 2 == 0 else "_idle1")
    elif name == "bubu" and p.invuln > 1.0:
        f = "bubu_hurt"
    elif p.crouch:
        f = name + "_slide"
    elif not p.on_ground:
        f = name + "_jump"
    elif p.vx != 0:
        fr = WALK_FRAMES[name]
        f = fr[int(p.walk * 1.1) % len(fr)]
    elif p.idle_t > 6:   # waves hello after standing still a while
        f = name + ("_wave1" if int(time_s / 2.0) % 2 == 0 else "_wave2")
    else:                # very calm idle - switches pose every ~5 seconds
        f = name + ("_idle1" if int(time_s / 5.0) % 2 == 0 else "_idle2")
    return (IMG if p.facing > 0 else FLIP)[f]

def draw_bear(surf, p, ox):
    if p.invuln > 0 and int(time_s * 14) % 2 == 0 and state == "play":
        return
    img = bear_frame(p)
    sq = p.squash
    base = 1.22 if "berry" in p.fx else 1.0   # berry bear is BIG
    w = max(2, int(96 * base * (1 + sq)))
    h = max(2, int(96 * base * (1 - sq)))
    if (w, h) != (96, 96):
        img = pygame.transform.smoothscale(img, (w, h))
    cx = p.x + p.w / 2
    bottom = p.y + p.h
    surf.blit(img, (cx - w / 2 + ox, bottom - h * 94 / 96))
    if "shield" in p.fx and state == "play":  # honeycomb shield bubble
        bs = pygame.Surface((116, 116), pygame.SRCALPHA)
        pygame.draw.circle(bs, (255, 215, 90, 45), (58, 58), 54)
        pygame.draw.circle(bs, (255, 215, 90, 130), (58, 58), 54, 3)
        surf.blit(bs, (cx - 58 + ox, bottom - 104))

def draw_powerup(surf, kind, x, y, s=1.0):
    """Small pickup icons (also reused as status icons)."""
    if kind in ITEM_IMG:
        d = max(2, int(32 * s))
        surf.blit(pygame.transform.smoothscale(ITEM_IMG[kind], (d, d)), (x - d / 2, y - d / 2))
        return
    if kind == "shield":     # honeycomb piece
        pts = [(x + 12 * s * math.cos(a), y + 12 * s * math.sin(a))
               for a in [math.pi / 6 + i * math.pi / 3 for i in range(6)]]
        pygame.draw.polygon(surf, (255, 195, 60), pts)
        pygame.draw.polygon(surf, (170, 120, 30), pts, max(1, int(2 * s)))
        for dx, dy in ((-5, -3), (5, -3), (0, 5)):
            pygame.draw.circle(surf, (255, 225, 130),
                               (int(x + dx * s), int(y + dy * s)), max(1, int(3 * s)))
    elif kind == "feather":  # blue feather
        r = pygame.Rect(x - 5 * s, y - 13 * s, 10 * s, 26 * s)
        pygame.draw.ellipse(surf, (150, 200, 255), r)
        pygame.draw.ellipse(surf, (90, 150, 230), r, max(1, int(1.5 * s)))
        pygame.draw.line(surf, (90, 150, 230), (x, y - 12 * s), (x, y + 13 * s),
                         max(1, int(1.5 * s)))
    elif kind == "magnet":   # red horseshoe magnet
        r = pygame.Rect(x - 11 * s, y - 12 * s, 22 * s, 22 * s)
        pygame.draw.arc(surf, (230, 60, 70), r, 0, math.pi, max(2, int(7 * s)))
        pygame.draw.rect(surf, (230, 60, 70), (x - 11 * s, y - 2 * s, 7 * s, 10 * s))
        pygame.draw.rect(surf, (230, 60, 70), (x + 4 * s, y - 2 * s, 7 * s, 10 * s))
        pygame.draw.rect(surf, (240, 240, 245), (x - 11 * s, y + 4 * s, 7 * s, 5 * s))
        pygame.draw.rect(surf, (240, 240, 245), (x + 4 * s, y + 4 * s, 7 * s, 5 * s))
    elif kind == "berry":    # strawberry
        pygame.draw.ellipse(surf, (232, 66, 82), (x - 9 * s, y - 6 * s, 18 * s, 19 * s))
        pygame.draw.ellipse(surf, (110, 190, 90), (x - 8 * s, y - 12 * s, 16 * s, 9 * s))
        for dx, dy in ((-5, 0), (0, 4), (5, 0), (-2, 8), (3, 8)):
            pygame.draw.circle(surf, (255, 230, 180),
                               (int(x + dx * s), int(y + dy * s)), max(1, int(1.5 * s)))
    elif kind == "honey":
        img = pygame.transform.smoothscale(IMG["honey"], (int(28 * s), int(28 * s)))
        surf.blit(img, (x - 14 * s, y - 14 * s))

def draw_fx_icons(surf, p, ox, beside=False):
    """Active effect icons above the bear's head, blinking when about to end.
    beside=True puts them next to the body (bottom bear of a stack - its head
    spot is taken by the partner)."""
    if not p.fx or state != "play":
        return
    keys_ = sorted(p.fx.keys())
    if beside:
        x0 = p.x + p.w + 18 + ox
        yy = p.y + 10
    else:
        x0 = p.x + p.w / 2 + ox - (len(keys_) - 1) * 11
        yy = p.y - 38
    for i, k in enumerate(keys_):
        if p.fx[k] < 2.5 and int(time_s * 6) % 2 == 0:
            continue
        draw_powerup(surf, k, x0 + i * 22, yy, .55)

def stacked_pair():
    """Returns (top, bottom) when one bear stands neatly on the other."""
    if state != "play":
        return None
    for i, p in enumerate(players):
        o = players[1 - i]
        if p.on_ground and not p.crouch and abs(p.y + p.h - o.y) < 4 \
                and abs(p.x - o.x) < 14:
            return p, o
    return None

def draw_stack(surf, top, bot, ox):
    sb = 1.22 if "berry" in bot.fx else 1.0   # berry bears stay BIG in a stack
    st = 1.22 if "berry" in top.fx else 1.0
    alt = 1 + int(time_s / 5.0) % 2
    cx = bot.x + bot.w / 2 + ox
    ground = bot.y + bot.h
    head_h = (58 if bot.crouch else 74) * sb          # bottom bear's visual height
    top_feet = ground - head_h + 4 * sb
    blink = int(time_s * 14) % 2 == 0 and state == "play"
    hide_bot = bot.invuln > 0 and blink
    hide_top = top.invuln > 0 and blink
    walking = bot.vx != 0 and not bot.crouch
    if sb == st == 1.0 and not (hide_bot or hide_top or walking):
        if bot.crouch:
            f = f"stack_{top.kind}_on_{bot.kind}_c"
        else:
            f = f"stack_{top.kind}_on_{bot.kind}{alt}"
        img = (IMG if bot.facing > 0 else FLIP)[f]
        surf.blit(img, (bot.x + bot.w / 2 - 48 + ox, bot.y + bot.h - 158))
    else:
        # compose live from the solo frames so each bear keeps its own size,
        # blinks individually and the bottom bear walks for real
        if bot.crouch:
            bot_f = f"{bot.kind}_slide"
        elif walking:
            fr = WALK_FRAMES[bot.kind]
            bot_f = fr[int(bot.walk * 1.1) % len(fr)]
        else:
            bot_f = f"{bot.kind}_idle{alt}"
        top_f = f"{top.kind}_idle{1 if bot.crouch else alt}"
        for f, s, feet_y, facing, hide in ((bot_f, sb, ground, bot.facing, hide_bot),
                                           (top_f, st, top_feet, top.facing, hide_top)):
            if hide:
                continue
            img = (IMG if facing > 0 else FLIP)[f]
            if s != 1.0:
                img = pygame.transform.smoothscale(img, (int(96 * s), int(96 * s)))
            surf.blit(img, (cx - 48 * s, feet_y - 94 * s))
    if state != "play":
        return
    for p, s, feet_y in ((bot, sb, ground), (top, st, top_feet)):
        if "shield" in p.fx:                  # honeycomb bubble around that bear
            r = int(54 * s)
            c = r + 4
            bs = pygame.Surface((c * 2, c * 2), pygame.SRCALPHA)
            pygame.draw.circle(bs, (255, 215, 90, 45), (c, c), r)
            pygame.draw.circle(bs, (255, 215, 90, 130), (c, c), r, 3)
            surf.blit(bs, (cx - c, feet_y - 46 * s - c))

def draw_bee(surf, b, ox):
    if b.dead:
        return
    if night:                 # asleep in mid-air: still wings, floating "z"
        img = (IMG if b.dir >= 0 else FLIP)["bee1"]
        surf.blit(img, (b.x - 28 + ox, b.y - 24))
        zy = b.y - 30 - (time_s * 12 + b.x) % 18
        surf.blit(font(12).render("z", True, (220, 220, 255)), (b.x + 10 + ox, zy))
        return
    frame = "bee1" if int(time_s * 16) % 2 == 0 else "bee2"
    img = (IMG if b.dir >= 0 else FLIP)[frame]
    y = b.y + math.sin(time_s * 6 + b.x * .01) * 3
    surf.blit(img, (b.x - 28 + ox, y - 24))

def mob_frame(m, layer=""):
    """Sprite for a mob (bat flaps, owl spreads its wings while swooping)."""
    if m.kind == "bat":
        img = MOB_ART["bat"][int(m.t * 9) % 2]
    else:
        img = MOB_ART["owl" + layer][0 if m.mode == "idle" else 1]
    return pygame.transform.flip(img, True, False) if m.dir < 0 else img

def draw_mob(surf, m, ox):
    if m.dead:
        return
    x, y = m.x + ox, m.y
    if not -60 < x < VW + 60:
        return
    if m.kind in MOB_ART:
        img = mob_frame(m)
        surf.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))
        return
    if m.kind == "bat":
        flap = math.sin(m.t * 18)
        c = (72, 52, 98)
        for s in (-1, 1):
            pygame.draw.polygon(surf, c, [(x + s * 7, y - 4), (x + s * 30, y - 6 - 12 * flap),
                                          (x + s * 25, y + 4), (x + s * 17, y + 1),
                                          (x + s * 10, y + 6)])
            pygame.draw.polygon(surf, c, [(x + s * 3, y - 7), (x + s * 8, y - 15),
                                          (x + s * 9, y - 5)])
        pygame.draw.ellipse(surf, c, (x - 10, y - 9, 20, 18))
    else:
        body, belly = (128, 92, 64), (196, 166, 124)
        if m.mode != "idle":   # wings out while swooping
            for s in (-1, 1):
                pygame.draw.ellipse(surf, body, (x + (2 if s > 0 else -32), y - 12, 30, 14))
        for s in (-1, 1):
            pygame.draw.polygon(surf, body, [(x + s * 6, y - 14), (x + s * 15, y - 26),
                                             (x + s * 15, y - 10)])
        pygame.draw.ellipse(surf, body, (x - 16, y - 20, 32, 40))
        pygame.draw.ellipse(surf, belly, (x - 10, y - 2, 20, 20))
        pygame.draw.polygon(surf, (230, 170, 60), [(x - 3, y - 4), (x + 3, y - 4), (x, y + 2)])

def draw_mob_eyes(surf, m, ox):
    """Drawn on top of the darkness so the eyes glow."""
    if m.dead or not -60 < m.x + ox < VW + 60:
        return
    x, y = int(m.x + ox), int(m.y)
    if m.kind == "owl" and "owl_eyes" in MOB_ART:
        img = mob_frame(m, "_eyes")
        surf.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))
        return
    if m.kind == "bat" and "bat" in MOB_ART:   # a faint silhouette in the dark
        img = mob_frame(m).copy()
        img.set_alpha(80)
        surf.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))
        return
    if m.kind == "bat":
        for dx in (-4, 4):
            pygame.draw.circle(surf, (255, 230, 90), (x + dx, y - 2), 2)
    else:
        for dx in (-7, 7):
            pygame.draw.circle(surf, (255, 214, 70), (x + dx, y - 10), 6)
            pygame.draw.circle(surf, (30, 20, 20), (x + dx + m.dir, y - 10), 3)

def draw_star(surf, x, y, r, col=(255, 228, 110)):
    if "star" in ITEM_IMG:
        d = int(r * 2.6)
        surf.blit(pygame.transform.smoothscale(ITEM_IMG["star"], (d, d)), (x - d / 2, y - d / 2))
        return
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * .45
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    pygame.draw.polygon(surf, col, pts)
    pygame.draw.polygon(surf, (200, 150, 40), pts, 2)

def draw_night(surf, ox):
    """Darkness + everything that glows in it."""
    a = int(205 * night_k)
    DARK.fill((12, 14, 40, a))
    for p in players:
        DARK.blit(LIGHT, (p.x + p.w / 2 + ox - LIGHT_R, p.y + p.h / 2 - LIGHT_R),
                  special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(DARK, (0, 0))
    if night_k < .5:
        return
    if MOON_IMG:
        surf.blit(MOON_IMG, (SKY_POS[0] - MOON_IMG.get_width() / 2,
                             SKY_POS[1] - MOON_IMG.get_height() / 2))
    for x, y, w in MOONS:     # moon platforms glow softly
        if -50 < x + ox < VW + 50:
            r = pygame.Rect(x + ox, y, w, 14)
            glow = pygame.Surface((w + 16, 30), pygame.SRCALPHA)
            pygame.draw.rect(glow, (170, 200, 255, 60), glow.get_rect(), border_radius=14)
            surf.blit(glow, (r.x - 8, y - 8))
            if "plank_moon" in ART:
                surf.blit(stretch("plank_moon", w, 20), (r.x, y - 3))
                continue
            pygame.draw.rect(surf, (196, 214, 255), r, border_radius=7)
            pygame.draw.rect(surf, (120, 140, 230), r, 2, border_radius=7)
            for gx in range(r.x + 12, r.right - 8, 22):
                pygame.draw.circle(surf, (255, 255, 255), (gx, y + 7), 2)
    for st in stars:
        if not st["got"] and -40 < st["x"] + ox < VW + 40:
            sy = st["y"] + math.sin(time_s * 3 + st["x"]) * 4
            draw_star(surf, st["x"] + ox, sy, 15 + math.sin(time_s * 5) * 1.5)
    for m in mobs:
        draw_mob_eyes(surf, m, ox)
    for bf in butterflies:    # fireflies
        x = bf["bx"] + math.sin(bf["t"] * .7) * 60 + ox
        y = bf["by"] + math.sin(bf["t"] * 1.3) * 30
        if -20 < x < VW + 20:
            g = .5 + .5 * math.sin(bf["t"] * 4)
            pygame.draw.circle(surf, (190, 230, 110), (int(x), int(y)), 2 + int(g * 2))

def draw_daynight_icon(surf):
    cx, cy = VW // 2, 32
    panel = pygame.Surface((48, 40), pygame.SRCALPHA)
    pygame.draw.rect(panel, (255, 255, 255, 190), panel.get_rect(), border_radius=12)
    surf.blit(panel, (cx - 24, 12))
    icon = HUD_MOON if night else HUD_SUN
    if icon:
        surf.blit(icon, (cx - icon.get_width() / 2, cy - icon.get_height() / 2))
    elif night:
        pygame.draw.circle(surf, (235, 215, 120), (cx, cy), 12)
        pygame.draw.circle(surf, (255, 255, 255), (cx + 6, cy - 4), 10)
    else:
        for i in range(8):
            a = i * math.pi / 4
            pygame.draw.line(surf, (255, 180, 50), (cx + math.cos(a) * 10, cy + math.sin(a) * 10),
                             (cx + math.cos(a) * 15, cy + math.sin(a) * 15), 2)
        pygame.draw.circle(surf, (255, 200, 60), (cx, cy), 8)
    if shift_cd > 0:          # cooldown ring
        pygame.draw.arc(surf, (150, 150, 170), (cx - 18, cy - 18, 36, 36),
                        math.pi / 2, math.pi / 2 + math.tau * shift_cd / SHIFT_CD, 3)

def outline_text(surf, txt, cx, y, size, col):
    f = font(size)
    dark = f.render(txt, True, (60, 30, 60))
    light = f.render(txt, True, col)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
        surf.blit(dark, (cx - dark.get_width() // 2 + dx, y + dy))
    surf.blit(light, (cx - light.get_width() // 2, y))

def draw_hud(surf):
    f18, f14 = font(18), font(14)
    t_count = f18.render(f"x {heart_count}", True, (211, 63, 107))
    t_lbl = f14.render("Lives:", True, (74, 107, 138))
    many = lives > 6            # with lots of lives switch to "♥ x N"
    t_lives = f14.render(f"x {lives}", True, (211, 63, 107)) if many else None
    lives_w = (18 + t_lives.get_width()) if many else max(0, lives) * 16
    wp = 12 + 26 + 8 + t_count.get_width() + 16 + t_lbl.get_width() + 8 + lives_w + 14
    panel = pygame.Surface((wp, 40), pygame.SRCALPHA)
    pygame.draw.rect(panel, (255, 255, 255, 190), (0, 0, wp, 40), border_radius=12)
    surf.blit(panel, (14, 12))
    x = 26
    surf.blit(pygame.transform.smoothscale(IMG["heart"], (26, 24)), (x, 20))
    x += 26 + 8
    surf.blit(t_count, (x, 20))
    x += t_count.get_width() + 16
    surf.blit(t_lbl, (x, 23))
    x += t_lbl.get_width() + 8
    if many:
        surf.blit(HEART_HUD, (x, 25))
        surf.blit(t_lives, (x + 18, 23))
    else:
        for i in range(lives):
            surf.blit(HEART_HUD, (x + i * 16, 25))
    # level + timer top-right
    if state in ("play", "win"):
        m, s = divmod(int(run_time), 60)
        tag = " !!!" if level_num % 10 == 0 else ""
        t = font(18).render(f"Level {level_num}{tag}   {m:02d}:{s:02d}", True,
                            (200, 60, 70) if tag else (74, 107, 138))
        panel2 = pygame.Surface((t.get_width() + 24, 34), pygame.SRCALPHA)
        pygame.draw.rect(panel2, (255, 255, 255, 190), panel2.get_rect(), border_radius=12)
        surf.blit(panel2, (VW - panel2.get_width() - 14, 12))
        surf.blit(t, (VW - t.get_width() - 26, 16))
        draw_daynight_icon(surf)

def overlay(surf, alpha):
    ov = pygame.Surface((VW, VH), pygame.SRCALPHA)
    ov.fill((35, 25, 60, int(alpha * 255)))
    surf.blit(ov, (0, 0))

def menu_items():
    return (["Continue"] if can_continue else []) + \
        ["Select Level", "How to Play", "Settings", "Quit"]

def draw_menu(surf):
    overlay(surf, .12 if MENU_BG else .45)
    for i in range(12):
        hx = (i * 173 + time_s * 22) % VW
        hy = VH - ((time_s * 32 + i * 217) % (VH + 40))
        s = 18 + (i % 3) * 8
        img = pygame.transform.smoothscale(IMG["heart_pale"], (s, int(s * .93)))
        img.set_alpha(120)
        surf.blit(img, (hx, hy))
    outline_text(surf, "Bubu & Dudu", VW // 2, 56, 54, (255, 217, 230))
    outline_text(surf, "Picnic Adventure", VW // 2, 128, 36, (255, 233, 163))
    items = menu_items()
    y0 = 224
    for i, it in enumerate(items):
        sel = i == menu_sel
        col = (126, 224, 129) if sel else (255, 255, 255)
        size = 27 if sel else 23
        outline_text(surf, it, VW // 2, y0 + i * 46, size, col)
        if sel:
            hw = font(size).size(it)[0]
            img = pygame.transform.smoothscale(IMG["heart"], (24, 22))
            surf.blit(img, (VW // 2 - hw // 2 - 38, y0 + i * 46 + 8))
            surf.blit(img, (VW // 2 + hw // 2 + 14, y0 + i * 46 + 8))
    outline_text(surf, "Bubu: {} {} {} + {}      Dudu: {} {} {} + {}".format(
                     *[key_label(CONTROLS[i][k]) for i in (0, 1)
                       for k in ("u", "l", "r", "dn")]),
                 VW // 2, y0 + len(items) * 46 + 16, 14, (207, 238, 251))
    if not MENU_BG:   # the picnic background already stars the bears
        surf.blit(IMG["bubu_wave1" if int(time_s * 2) % 2 == 0 else "bubu_wave2"],
                  (VW // 2 - 150, 428))
        surf.blit(FLIP["dudu_wave1" if int(time_s * 2) % 2 == 1 else "dudu_wave2"],
                  (VW // 2 + 54, 428))

def levels_total_cells():
    """Grid cells to navigate: all pages that contain an unlocked level."""
    return ((SETTINGS["unlocked"] - 1) // LEVELS_PER_PAGE + 1) * LEVELS_PER_PAGE

def draw_levels(surf):
    overlay(surf, .38 if MENU_BG else .55)
    outline_text(surf, "Select Level", VW // 2, 36, 40, (255, 233, 163))
    cols = 5
    cw_, ch_, gap = 150, 82, 14
    gx0 = (VW - cols * cw_ - (cols - 1) * gap) // 2
    gy0 = 118
    unlocked = SETTINGS["unlocked"]
    total = levels_total_cells()
    page = levels_sel // LEVELS_PER_PAGE
    pages = total // LEVELS_PER_PAGE
    start = page * LEVELS_PER_PAGE
    for k in range(LEVELS_PER_PAGE):
        i = start + k
        r, c = divmod(k, cols)
        x = gx0 + c * (cw_ + gap)
        y = gy0 + r * (ch_ + gap)
        is_open = i + 1 <= unlocked
        challenge = (i + 1) % 10 == 0
        sel = i == levels_sel
        cell = pygame.Surface((cw_, ch_), pygame.SRCALPHA)
        if is_open:
            col = (255, 205, 205, 225) if challenge else (255, 255, 255, 215)
        else:
            col = (170, 140, 145, 170) if challenge else (150, 150, 160, 160)
        pygame.draw.rect(cell, col, (0, 0, cw_, ch_), border_radius=14)
        surf.blit(cell, (x, y))
        if sel:
            pygame.draw.rect(surf, (126, 224, 129), (x, y, cw_, ch_), 4, border_radius=14)
        if is_open:
            t = font(28).render(str(i + 1), True, (211, 63, 107))
            surf.blit(t, (x + cw_ // 2 - t.get_width() // 2, y + 14))
            if i + 1 < unlocked:      # completed levels get a little heart
                surf.blit(HEART_S, (x + cw_ // 2 - 9, y + ch_ - 26))
        else:
            t = font(24).render(str(i + 1), True, (100, 100, 110))
            surf.blit(t, (x + cw_ // 2 - t.get_width() // 2, y + 8))
            # lock
            lx, ly = x + cw_ // 2, y + ch_ - 24
            pygame.draw.rect(surf, (90, 90, 100), (lx - 8, ly, 16, 12), border_radius=3)
            pygame.draw.arc(surf, (90, 90, 100), (lx - 6, ly - 9, 12, 14),
                            0, math.pi, 3)
    if pages > 1:
        outline_text(surf, f"Page {page + 1} / {pages}", VW // 2,
                     gy0 + 4 * (ch_ + gap) + 4, 16, (255, 217, 230))
    outline_text(surf, "arrows = select      Enter = play      Esc = back",
                 VW // 2, gy0 + 4 * (ch_ + gap) + 28, 15, (207, 238, 251))

def handle_levels_key(key):
    global levels_sel, state
    cols = 5
    total = levels_total_cells()
    if key in (pygame.K_LEFT, pygame.K_a):
        levels_sel = (levels_sel - 1) % total
    elif key in (pygame.K_RIGHT, pygame.K_d):
        levels_sel = (levels_sel + 1) % total
    elif key in (pygame.K_UP, pygame.K_w):
        levels_sel = (levels_sel - cols) % total
    elif key in (pygame.K_DOWN, pygame.K_s):
        levels_sel = (levels_sel + cols) % total
    elif key in (pygame.K_RETURN, pygame.K_SPACE):
        if levels_sel + 1 <= SETTINGS["unlocked"]:
            start_level(levels_sel + 1)
        else:
            play("hurt")
    elif key == pygame.K_ESCAPE:
        state = "menu"

SETTING_ROWS = ["Music", "Sound", "Fullscreen", "Controls", "Back"]

# ---- controls remap screen
BIND_ROWS = [(0, "l", "Bubu - left"), (0, "r", "Bubu - right"),
             (0, "u", "Bubu - jump"), (0, "dn", "Bubu - crouch"),
             (0, "sh", "Bubu - day/night"),
             (1, "l", "Dudu - left"), (1, "r", "Dudu - right"),
             (1, "u", "Dudu - jump"), (1, "dn", "Dudu - crouch"),
             (1, "sh", "Dudu - day/night")]
controls_sel = 0
controls_wait = False    # True while waiting for the new key press

def key_label(k):
    n = pygame.key.name(k)
    return {"up": "Up", "down": "Down", "left": "Left", "right": "Right",
            "space": "Space", "return": "Enter", "left shift": "LShift",
            "right shift": "RShift", "left ctrl": "LCtrl",
            "right ctrl": "RCtrl"}.get(n, n.upper())

def draw_controls(surf):
    overlay(surf, .38 if MENU_BG else .55)
    outline_text(surf, "Controls", VW // 2, 30, 40, (255, 233, 163))
    y0, step = 96, 31
    for i, (pi, kk, label) in enumerate(BIND_ROWS):
        sel = i == controls_sel
        col = (126, 224, 129) if sel else (255, 255, 255)
        outline_text(surf, label, 340, y0 + i * step, 20 if sel else 18, col)
        if sel and controls_wait:
            outline_text(surf, "press a key...", 620, y0 + i * step, 20, (255, 111, 145))
        else:
            outline_text(surf, key_label(CONTROLS[pi][kk]), 620, y0 + i * step,
                         20 if sel else 18, (255, 217, 230))
    for j, label in enumerate(("Reset to defaults", "Back")):
        i = len(BIND_ROWS) + j
        sel = i == controls_sel
        col = (126, 224, 129) if sel else (255, 255, 255)
        outline_text(surf, label, VW // 2, y0 + i * step + 10, 20 if sel else 18, col)
    outline_text(surf, "Enter = change key      Esc = back",
                 VW // 2, 514, 15, (207, 238, 251))

def handle_controls_key(key):
    global controls_sel, controls_wait, state
    n = len(BIND_ROWS) + 2
    if controls_wait:
        if key != pygame.K_ESCAPE:
            pi, kk, _ = BIND_ROWS[controls_sel]
            old = CONTROLS[pi][kk]
            # key already used by another action? swap so nothing is lost
            for c in CONTROLS:
                for k2 in c:
                    if c[k2] == key and not (c is CONTROLS[pi] and k2 == kk):
                        c[k2] = old
            CONTROLS[pi][kk] = key
            save_controls()
            play("check")
        controls_wait = False
    elif key in (pygame.K_UP, pygame.K_w):
        controls_sel = (controls_sel - 1) % n
    elif key in (pygame.K_DOWN, pygame.K_s):
        controls_sel = (controls_sel + 1) % n
    elif key in (pygame.K_RETURN, pygame.K_SPACE):
        if controls_sel < len(BIND_ROWS):
            controls_wait = True
        elif controls_sel == len(BIND_ROWS):
            for c, d in zip(CONTROLS, DEFAULT_CONTROLS):
                c.update(d)
            save_controls()
            play("heart")
        else:
            state = "settings"
    elif key == pygame.K_ESCAPE:
        state = "settings"

def draw_settings(surf):
    overlay(surf, .38 if MENU_BG else .55)
    outline_text(surf, "Settings", VW // 2, 60, 44, (255, 233, 163))
    y0 = 180
    for i, name in enumerate(SETTING_ROWS):
        sel = i == settings_sel
        col = (126, 224, 129) if sel else (255, 255, 255)
        outline_text(surf, name, 300, y0 + i * 62, 25 if sel else 22, col)
        if name in ("Music", "Sound"):
            frac = SETTINGS["music" if name == "Music" else "sfx"]
            for j in range(10):
                c = (255, 111, 145) if j < round(frac * 10) else (255, 255, 255)
                pygame.draw.rect(surf, (60, 30, 60), (478 + j * 24, y0 + i * 62 + 6, 22, 22),
                                 border_radius=5)
                pygame.draw.rect(surf, c, (480 + j * 24, y0 + i * 62 + 8, 18, 18),
                                 border_radius=5)
        elif name == "Fullscreen":
            outline_text(surf, "On" if SETTINGS["fullscreen"] else "Off",
                         560, y0 + i * 62, 24, (255, 217, 230))
    outline_text(surf, "Up/Down select      Left/Right change      Esc back",
                 VW // 2, y0 + len(SETTING_ROWS) * 62 + 26, 15, (207, 238, 251))

def handle_menu_key(key):
    global menu_sel, state, can_continue
    items = menu_items()
    if key in (pygame.K_UP, pygame.K_w):
        menu_sel = (menu_sel - 1) % len(items)
    elif key in (pygame.K_DOWN, pygame.K_s):
        menu_sel = (menu_sel + 1) % len(items)
    elif key in (pygame.K_RETURN, pygame.K_SPACE):
        it = items[menu_sel]
        if it == "Continue":
            state = "play"
        elif it == "Select Level":
            global levels_sel
            levels_sel = SETTINGS["unlocked"] - 1
            state = "levels"
        elif it == "How to Play":
            state = "help"
        elif it == "Settings":
            state = "settings"
        else:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
    elif key == pygame.K_ESCAPE:
        pygame.event.post(pygame.event.Event(pygame.QUIT))

def draw_help(surf):
    overlay(surf, .5 if MENU_BG else .6)
    outline_text(surf, "How to Play", VW // 2, 26, 38, (255, 233, 163))
    rules = [
        "Reach the picnic TOGETHER - both bears on the blanket!",
        "Bubu: {} {} {} + {} (crouch)      Dudu: {} {} {} + {} (crouch)".format(
            *[key_label(CONTROLS[i][k]) for i in (0, 1) for k in ("u", "l", "r", "dn")]),
        "10 hearts = +1 life   ·   bee sting = -1 life",
        "Falling in a pit = -1 life, back to the flag and you LOSE your boosts!",
        "Crouch and bees fly over you  ·  jump on your partner = bear tower",
        "The plate bridge takes teamwork  ·  every 10th level is a CHALLENGE",
        "{} / {} = day <-> night: bees sleep, but bats & owls hunt!".format(
            key_label(CONTROLS[0]["sh"]), key_label(CONTROLS[1]["sh"])),
        "Night shows glowing moon platforms and stars (+3 hearts)",
    ]
    for i, r in enumerate(rules):
        outline_text(surf, r, VW // 2, 76 + i * 26, 15, (255, 255, 255))
    outline_text(surf, "Power-ups (12 seconds, they stack!)", VW // 2, 290, 20, (255, 217, 230))
    boosts = [
        ("honey", "Honey - run faster, jump higher (+1 heart)"),
        ("shield", "Honeycomb - shield: bees bounce off you"),
        ("feather", "Blue feather - double jump in the air"),
        ("magnet", "Magnet - hearts fly to you by themselves"),
        ("berry", "Strawberry - grow big and squish bees by touch"),
    ]
    for i, (kind, desc) in enumerate(boosts):
        y = 334 + i * 34
        draw_powerup(surf, kind, VW // 2 - 300, y, .85)
        outline_text(surf, desc, VW // 2 + 20, y - 10, 15, (207, 238, 251))
    outline_text(surf, "Esc = back", VW // 2, 510, 15, (126, 224, 129))

def handle_help_key(key):
    global state
    if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
        state = "menu"

def handle_settings_key(key):
    global settings_sel, state
    if key in (pygame.K_UP, pygame.K_w):
        settings_sel = (settings_sel - 1) % len(SETTING_ROWS)
    elif key in (pygame.K_DOWN, pygame.K_s):
        settings_sel = (settings_sel + 1) % len(SETTING_ROWS)
    elif key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
        d = -1 if key in (pygame.K_LEFT, pygame.K_a) else 1
        name = SETTING_ROWS[settings_sel]
        if name == "Music":
            SETTINGS["music"] = round(min(1, max(0, SETTINGS["music"] + d * .1)), 2)
            apply_music_volume()
        elif name == "Sound":
            SETTINGS["sfx"] = round(min(1, max(0, SETTINGS["sfx"] + d * .1)), 2)
            play("heart")
        elif name == "Fullscreen":
            SETTINGS["fullscreen"] = not SETTINGS["fullscreen"]
            apply_display()
    elif key in (pygame.K_RETURN, pygame.K_SPACE):
        name = SETTING_ROWS[settings_sel]
        if name == "Back":
            save_settings()
            state = "menu"
        elif name == "Fullscreen":
            SETTINGS["fullscreen"] = not SETTINGS["fullscreen"]
            apply_display()
        elif name == "Controls":
            global controls_sel, controls_wait
            controls_sel = 0
            controls_wait = False
            state = "controls"
    elif key == pygame.K_ESCAPE:
        save_settings()
        state = "menu"

def draw_win(surf):
    overlay(surf, .25)
    outline_text(surf, "PICNIC TIME!", VW // 2, 96, 46, (255, 217, 230))
    m, s = divmod(int(run_time), 60)
    outline_text(surf, f"Level {level_num} - {heart_count} hearts in {m:02d}:{s:02d}!",
                 VW // 2, 168, 22, (255, 255, 255))
    outline_text(surf, "Bubu & Dudu live happily ever after", VW // 2, 208, 18, (255, 233, 163))
    if just_unlocked:
        outline_text(surf, f"Level {level_num + 1} unlocked!", VW // 2, 248, 20, (255, 217, 230))
    if level_num + 1 <= SETTINGS["unlocked"]:
        outline_text(surf, "N = next level      R = retry      Esc = menu",
                     VW // 2, 292, 16, (126, 224, 129))
    else:
        outline_text(surf, "R = retry      Esc = menu", VW // 2, 292, 16, (126, 224, 129))

_over_img = os.path.join(ASSETS, "gameover.png")
OVER_IMG = load("gameover") if os.path.isfile(_over_img) else None
# eye spots in the 96px idle frames (facing right)
EYES = {"bubu": ((36, 49), (56, 49)), "dudu": ((42, 49), (62, 49))}

def draw_tear(surf, x, y, r, a):
    t = pygame.Surface((r * 2 + 2, r * 3 + 2), pygame.SRCALPHA)
    c = (120, 190, 255, int(a * 230))
    pygame.draw.circle(t, c, (r + 1, r * 2 + 1), r)
    pygame.draw.polygon(t, c, [(r + 1, 0), (1, r * 2 + 1), (r * 2 + 1, r * 2 + 1)])
    pygame.draw.circle(t, (235, 248, 255, int(a * 230)), (r - 1, r * 2), max(1, r // 3))
    surf.blit(t, (x - r - 1, y - r * 2 - 1))

def draw_sad_bears(surf, cx, bottom):
    """The bears stand side by side with tears running down their cheeks."""
    s = 1.9
    size = int(96 * s)
    for kind, dx, facing in (("bubu", -95, 1), ("dudu", 95, -1)):
        bob = math.sin(time_s * 3 + dx) * 2           # little sobs
        img = pygame.transform.smoothscale(IMG[kind + "_idle1"], (size, size))
        if facing < 0:
            img = pygame.transform.flip(img, True, False)
        x0, y0 = cx + dx - size / 2, bottom - size + bob
        surf.blit(img, (x0, y0))
        for k, (ex, ey) in enumerate(EYES[kind]):
            if facing < 0:
                ex = 96 - ex
            ex, ey = x0 + ex * s, y0 + ey * s
            # watery eyes: a pool of tears under each eye
            pygame.draw.ellipse(surf, (150, 205, 255), (ex - 9, ey + 3, 18, 7))
            for j in range(2):                         # drops rolling down
                ph = (time_s * .8 + j * .5 + k * .27 + (dx > 0) * .13) % 1.0
                draw_tear(surf, ex + (-3 if k == 0 else 3), ey + 14 + ph * 70, 5,
                          1.0 - ph * ph)

def draw_over(surf):
    overlay(surf, .55)
    outline_text(surf, "Oh no!", VW // 2, 56, 50, (255, 143, 168))
    outline_text(surf, "The bears ran out of lives...", VW // 2, 128, 22, (255, 255, 255))
    if OVER_IMG:
        img = OVER_IMG
        k = min(250 / img.get_height(), 520 / img.get_width())
        img = pygame.transform.smoothscale(img, (int(img.get_width() * k),
                                                 int(img.get_height() * k)))
        surf.blit(img, (VW // 2 - img.get_width() // 2, 448 - img.get_height()))
    else:
        draw_sad_bears(surf, VW // 2, 448)
    outline_text(surf, "R = try again      Esc = menu", VW // 2, 472, 20, (126, 224, 129))

def draw():
    if state in ("menu", "settings", "levels", "help", "controls") and MENU_BG:
        screen.blit(MENU_BG, (0, 0))
        if state == "menu":
            draw_menu(screen)
        elif state == "levels":
            draw_levels(screen)
        elif state == "help":
            draw_help(screen)
        elif state == "controls":
            draw_controls(screen)
        else:
            draw_settings(screen)
        pygame.display.flip()
        return
    draw_background(screen)
    ox = -int(cam)
    if shake_t > 0:
        ox += random.randint(-4, 4)
    draw_world(screen, ox)
    for h in hearts:
        if not h["got"] and -40 < h["x"] + ox < VW + 40:
            hy = h["y"] + math.sin(time_s * 3 + h["t"]) * 4
            s = 1.5 + math.sin(time_s * 5 + h["t"]) * .15
            img = pygame.transform.smoothscale(IMG["heart"], (int(21 * s), int(20 * s)))
            screen.blit(img, (h["x"] - img.get_width() // 2 + ox, hy - img.get_height() // 2))
    for h in honeys:
        if not h["got"] and -40 < h["x"] + ox < VW + 40:
            hy = h["y"] + math.sin(time_s * 3 + h["x"] * .01) * 3
            screen.blit(IMG["honey"], (h["x"] - 20 + ox, hy - 18))
    for pu in powerups:
        if not pu["got"] and -40 < pu["x"] + ox < VW + 40:
            py_ = pu["y"] + math.sin(time_s * 3 + pu["x"] * .013) * 4
            draw_powerup(screen, pu["kind"], pu["x"] + ox, py_)
    for b in bees:
        if -80 < b.x + ox < VW + 80:
            draw_bee(screen, b, ox)
    if night_k > .5:
        for m in mobs:
            draw_mob(screen, m, ox)
    pair = stacked_pair()
    if pair:
        draw_stack(screen, pair[0], pair[1], ox)
    else:
        for p in players:
            draw_bear(screen, p, ox)
    for p in players:
        # bottom bear of a stack shows its icons beside its own body
        draw_fx_icons(screen, p, ox, beside=bool(pair and p is pair[1]))
    for pt in particles:
        a = max(0, min(1, pt["life"]))
        if pt["heart"]:
            img = HEART_S.copy()
            img.set_alpha(int(a * 255))
            screen.blit(img, (pt["x"] - 9 + ox, pt["y"] - 8))
        else:
            s = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(s, (*pt["color"], int(a * 255)), (4, 4), 4)
            screen.blit(s, (pt["x"] - 4 + ox, pt["y"] - 4))
    if night_k > 0:
        draw_night(screen, ox)
    draw_hud(screen)
    if state == "menu":
        draw_menu(screen)
    elif state == "levels":
        draw_levels(screen)
    elif state == "help":
        draw_help(screen)
    elif state == "settings":
        draw_settings(screen)
    elif state == "controls":
        draw_controls(screen)
    elif state == "win" and win_t > 1.2:
        draw_win(screen)
    elif state == "over":
        draw_over(screen)
    pygame.display.flip()

# ------------------------------------------------------------------ main loop
def main():
    global state, can_continue, menu_sel
    smoke = "--smoke" in sys.argv
    frames = 0
    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, .033)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if state == "menu":
                    handle_menu_key(e.key)
                elif state == "settings":
                    handle_settings_key(e.key)
                elif state == "controls":
                    handle_controls_key(e.key)
                elif state == "levels":
                    handle_levels_key(e.key)
                elif state == "help":
                    handle_help_key(e.key)
                elif state == "play" and e.key in (CONTROLS[0]["sh"], CONTROLS[1]["sh"]):
                    toggle_night()
                elif e.key == pygame.K_ESCAPE:
                    can_continue = state == "play"
                    menu_sel = 0
                    state = "menu"
                elif e.key == pygame.K_r:
                    reset()
                    state = "play"
                    can_continue = True
                elif e.key == pygame.K_n:
                    if level_num + 1 <= SETTINGS["unlocked"]:
                        start_level(level_num + 1)
        update(dt, pygame.key.get_pressed())
        draw()
        frames += 1
        if smoke and frames > 90:
            running = False
    pygame.quit()

if __name__ == "__main__":
    main()
