# KiCad: round selection to grid

A KiCad 10 action plugin that rounds the selected items to a grid step:
every point, width, thickness, radius and text size. Drawings made by
hand, imported or converted come out on clean numbers, still connected.

## Use

1. Select the items in the PCB editor.
2. Run **Round Selection to Grid** (toolbar button, or Tools > External
   Plugins).
3. Enter the step (0.25 mm at first; the last one is remembered) and
   press Round. A summary says what was rounded, deleted and left alone.

## What it does

- **Points** (ends, corners, centres, polygon and zone vertices, text
  and footprint positions, bezier controls) go to the nearest grid
  point, counted from the board's grid origin. Halves round up. The
  rounding depends only on the point, so items that shared an endpoint
  still share it.
- **Lengths** go to the nearest multiple of the step: line and track
  widths, text thickness and size, circle and arc radii, rectangle
  corner radii, text box borders, via diameter and drill.
- **Arcs** get their ends on the grid and their radius on a multiple of
  the step; the centre then follows, off the grid in general. If the
  rounded radius cannot span the ends, it grows to the smallest multiple
  that can. The arc keeps its bulge side and its short or long way
  round. KiCad keeps an arc as three integer-nanometre points, so a
  shallow arc's radius can read back up to some tens of nanometres off;
  KiCad shows it as the round value.
- **Deleted**: an item whose length, radius, side, area, stroke
  thickness, text size or thickness, via diameter or drill rounds to
  zero; for example a 0.001 mm line on a 0.25 mm step.
- **Set to zero, not deleted**: a filled shape's border (the fill
  stays), a rectangle's corner radius (sharp corners), a text box's
  border (switched off). Hairlines (width 0) stay hairlines.
- **Footprints** move by their anchor only, so their insides keep their
  shape. Pads selected on their own move by their position.
- **Zones** have their outline rounded and are unfilled; refill with B.
- **Left alone**, and listed in the summary: locked items, dimensions,
  rotated text boxes, polygons with arcs, footprint fields whose size
  would round to zero (KiCad cannot delete them), and anything else the
  plugin does not know.

## Install

    ln -s ~/kicad-round-to-grid/roundtogrid \
        ~/Documents/KiCad/10.0/scripting/plugins/roundtogrid

then restart the PCB editor or use Tools > External Plugins > Refresh
Plugins. The step is remembered in
`~/Library/Preferences/kicad/10.0/roundtogrid.json`.

## Tests

    tests/run.sh

runs the grid math (no KiCad needed) and the rounding of every item kind
on in-memory boards, with KiCad's Python. `tests/MATRIX.md` maps the
cases.

## Layout

    roundtogrid/snap.py      grid math on integer nanometres
    roundtogrid/rounding.py  per item kind: round, delete or leave
    roundtogrid/dialog.py    the step dialog
    roundtogrid/plugin.py    the KiCad action
