"""Draw roundtogrid/icon.png, the 24 x 24 toolbar icon: a stroke snapped
between grid points.

    python3 tools/make_icon.py
"""

import math
import os
import struct
import zlib

SIZE = 24
SS = 4  # supersamples per axis

DOT = (140, 140, 140)
LINE = (40, 120, 220)
GRID = (4.5, 9.5, 14.5, 19.5)


def dist_to_segment(x, y, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) /
        float(dx * dx + dy * dy)))
    return math.hypot(x - ax - t * dx, y - ay - t * dy)


def colour(x, y):
    # The stroke runs from one grid point to another, round-ended.
    if dist_to_segment(x, y, (GRID[0], GRID[3]), (GRID[3], GRID[1])) <= 1.9:
        return LINE
    for gx in GRID:
        for gy in GRID:
            if math.hypot(x - gx, y - gy) <= 1.1:
                return DOT
    return None


def pixels():
    rows = []
    for py in range(SIZE):
        row = bytearray([0])
        for px in range(SIZE):
            acc = [0, 0, 0]
            hits = 0
            for sy in range(SS):
                for sx in range(SS):
                    c = colour(px + (sx + 0.5) / SS, py + (sy + 0.5) / SS)
                    if c is not None:
                        hits += 1
                        for i in range(3):
                            acc[i] += c[i]
            if hits:
                row += bytes(int(round(a / float(hits))) for a in acc)
            else:
                row += b"\0\0\0"
            row.append(int(round(255.0 * hits / (SS * SS))))
        rows.append(bytes(row))
    return b"".join(rows)


def chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + \
        struct.pack(">I", zlib.crc32(body) & 0xffffffff)


def main():
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(pixels(), 9))
    png += chunk(b"IEND", b"")
    path = os.path.join(os.path.dirname(__file__), "..", "roundtogrid",
        "icon.png")
    with open(path, "wb") as f:
        f.write(png)


if __name__ == "__main__":
    main()
