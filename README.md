# Bubu & Dudu: Picnic Adventure

> **Disclaimer**
> This is an unofficial, non-commercial **fan project**. The Bubu & Dudu characters
> belong to their original creator; this project is not affiliated with or endorsed
> by them. The game is free and must not be sold.
> Most of the artwork was generated with AI image tools for this project.
> The **source code** is open source under the license in [`LICENSE`](LICENSE);
> the **artwork in `assets/` is not covered by that license**.

A cozy two-player co-op platformer for one keyboard, written in Python with
[pygame](https://www.pygame.org/). Bubu and Dudu race through endless,
procedurally generated levels to reach their picnic blanket — together.

## Features

- **Local co-op** — two players on one keyboard; the camera keeps both bears on screen.
- **Day / night with Shift** — either player can flip the world:
  - at night the bees fall asleep, but **bats** swoop and **owls** dive from the trees;
  - glowing **moon platforms** appear (only at night!) with **stars** worth 3 hearts;
  - it's dark — you only see what's near the bears.
- **Endless levels** — every level is generated from a fixed seed, so level 7 is
  always the same level 7. Difficulty grows, and every 10th level is a **challenge**.
- **Teamwork** — stand on your partner's head to build a bear tower; one bear holds
  down a heart plate so the bridge appears for the other.
- **Power-ups** (12 s, they stack): honey (speed + jump), honeycomb shield,
  feather (double jump), magnet (pulls hearts), strawberry (grow big, squish bees).
- 10 hearts = an extra life. Progress, settings and key bindings are saved.

## Controls

| | Bubu | Dudu |
|---|---|---|
| Move | `A` `D` | `←` `→` |
| Jump | `W` | `↑` |
| Crouch | `S` | `↓` |
| Day / night | `Left Shift` | `Right Shift` |

`R` restart level · `N` next level · `Esc` menu.
All player keys can be changed in **Settings → Controls**.

## Run from source

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python main.py
```

## Build the Windows installer

```bash
pip install pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --name BubuDudu --icon assets\icon.ico --add-data "assets;assets" main.py
```

Then compile [`installer.iss`](installer.iss) with [Inno Setup 6](https://jrsoftware.org/isinfo.php);
the result is `installer\BubuDudu-Setup.exe`.

## Project layout

| Path | What it is |
|---|---|
| `main.py` | The whole game: level generator, physics, enemies, drawing, menus |
| `assets/` | Sprites, icon and menu background used by the game |
| `assets/_*_src.png` | Original generated art sheets the import scripts cut sprites from |
| `import_items.py` | Cuts the power-up icon sheet into sprites |
| `import_sheets.py` | Cuts the other art sheets (enemies, terrain, sky, props, …) |
| `extract_sprites.py`, `compose_stack.py`, `import_assets.py` | Earlier asset pipeline for the bear sprites, trees and stacks |
| `make_assets.py` | Simple placeholder art (only needed without the real art) |
| `make_icon.py` | Builds the window / installer icon |
| `make_motion_sheet.py` | Builds `assets/motion_sheet.png`, the style reference for generating new art |
| `installer.iss` | Inno Setup script for the Windows installer |

The import scripts need `pip install pillow numpy` (the game itself does not).
If a sprite file is missing, the game falls back to drawing it in code.
