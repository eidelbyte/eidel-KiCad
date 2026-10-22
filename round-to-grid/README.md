# KiCad: round selection to grid

A KiCad 10 action plugin that rounds the selected items to grid steps:
positions and sizes on one step, thickness on another, either one or
both, the same for all layers or set layer by layer. Drawings made by
hand, imported or converted come out on clean numbers, still connected.

## Use

1. Select the items in the PCB editor.
2. Run **Round Selection to Grid** (toolbar button, or Tools > External
   Plugins).
3. Tick what to round and set each step (0.25 mm at first; the last
   choices are remembered), then press Round:
   - **Positions and sizes**: points, radii, corner radii, text sizes,
     via diameter and drill.
   - **Thickness**: line, track and border widths, text stroke
     thickness.

   With **All layers** ticked, one row of steps applies to everything.
   Untick it for a row per layer in the selection, each with its own
   steps; a row with nothing ticked leaves its layer alone. Each
   layer's steps are remembered.

   A summary says what was rounded to which steps, what changed, what
   was already on the grid, and what was deleted or left alone.

## What it does

- **Points** (ends, corners, centres, polygon and zone vertices, text
  and footprint positions, bezier controls) go to the nearest grid
  point, counted from the board's grid origin. Halves round up. The
  rounding depends only on the point, so items that shared an endpoint
  still share it.
- **Sizes** go to the nearest multiple of the position step: circle and
  arc radii, rectangle corner radii, text sizes, via diameter and drill.
- **Thickness** goes to the nearest multiple of the thickness step: line
  and track widths, text stroke thickness, text box border width.
- An option left unticked leaves its values exactly as they are, and
  nothing is deleted on its account.
- **Layers**: each item rounds on the steps of the first layer it is on,
  in KiCad's layer order: its own layer, a via's top layer, a
  footprint's or SMD pad's side, the front for a through-hole pad, the
  first layer of a zone on several. Items on two layers that meet, such
  as a B.Cu track at a through via, stay joined only where both layers
  round positions on the same step.
- **Arcs** get their ends on the grid and their radius on a multiple of
  the position step; the centre then follows, off the grid in general. If the
  rounded radius cannot span the ends, it grows to the smallest multiple
  that can. The arc keeps its bulge side and its short or long way
  round. KiCad keeps an arc as three integer-nanometre points, so a
  shallow arc's radius can read back up to some tens of nanometres off;
  KiCad shows it as the round value.
- **Deleted**: an item whose length, radius, side, area, stroke
  thickness, text size or thickness, via diameter or drill rounds to
  zero; for example a line 0.001 mm wide on a 0.25 mm thickness step.
- **Set to zero, not deleted**: a filled shape's border width (the fill
  stays), a rectangle's corner radius (sharp corners), a text box's
  border width (border switched off).
- What was zero before stays: hairlines (width 0) and zero-length lines
  (dots) are not rounding's doing.
- **Footprints** move by their anchor only, so their insides keep their
  shape. Pads selected on their own move by their position.
- **Zones** have their outline rounded and, when it moved, are
  unfilled; refill with B.
- **Left alone**, and listed in the summary: locked items, dimensions,
  rotated text boxes, polygons with arcs, footprint fields whose size
  would round to zero (KiCad cannot delete them), and anything else the
  plugin does not know.

## Install

    ln -s ~/eidel-KiCad/round-to-grid/roundtogrid \
        ~/Documents/KiCad/10.0/scripting/plugins/roundtogrid

then restart the PCB editor or use Tools > External Plugins > Refresh
Plugins. The choices are remembered in
`~/Library/Preferences/kicad/10.0/roundtogrid.json`, each layer's under
its standard name (`User.1`, even if the board calls it something
else).

## Tests

    tests/run.sh

runs the grid math (no KiCad needed), the rounding of every item kind
on in-memory boards, the remembered choices, and the dialog (built but
not shown), with KiCad's Python. `tests/MATRIX.md` maps the cases.

## Layout

    roundtogrid/snap.py      grid math on integer nanometres
    roundtogrid/rounding.py  per item kind: round, delete or leave
    roundtogrid/dialog.py    the step dialog
    roundtogrid/plugin.py    the KiCad action
