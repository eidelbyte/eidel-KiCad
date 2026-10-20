"""Export the items inside a window of a board without the KiCad GUI.

Run with KiCad's Python, for example on macOS:

  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/\\
Versions/Current/bin/python3 tools/export_window.py Ur.kicad_pcb \\
      --window 98.8 62.8 111.2 75.2 \\
      --layer F.Silkscreen:1:5:0:fill --layer User.Drawings:2:2.5:2.5 \\
      -o tile.3mf

The window is in KiCad millimetres; an item is taken when its bounding
box lies inside it. Each --layer is NAME:FILAMENT:DEPTH[:Z][:fill], with
depth and z in millimetres.
"""

import argparse
import os
import sys

import pcbnew

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bambu3mf import export  # noqa: E402

MM = 1000000


def parse_layer(board, spec):
    fields = spec.split(":")
    fill = fields[-1] == "fill"
    if fill:
        fields.pop()
    if len(fields) not in (3, 4):
        raise SystemExit("bad --layer %r" % spec)
    layer = board.GetLayerID(fields[0])
    if layer < 0:
        raise SystemExit("no layer %r" % fields[0])
    z = float(fields[3]) if len(fields) == 4 else 0.0
    return export.Job(layer, fields[0], int(fields[1]), fill,
        int(round(float(fields[2]) * MM)), int(round(z * MM)))


def window_items(board, x0, y0, x1, y1):
    items = list(board.GetDrawings()) + list(board.GetFootprints()) + \
        list(board.GetTracks()) + list(board.Zones())
    out = []
    for it in items:
        bb = it.GetBoundingBox()
        if bb.GetX() >= x0 and bb.GetRight() <= x1 and \
            bb.GetY() >= y0 and bb.GetBottom() <= y1:
            out.append(it)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board")
    ap.add_argument("--window", nargs=4, type=float, required=True,
        metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--layer", action="append", required=True)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.board)
    jobs = [parse_layer(board, s) for s in args.layer]
    x0, y0, x1, y1 = (int(round(v * MM)) for v in args.window)
    items = export.flatten(window_items(board, x0, y0, x1, y1))
    title = os.path.splitext(os.path.basename(args.board))[0]
    for line in export.export(board, items, jobs, args.output, title):
        print(line)


if __name__ == "__main__":
    main()
