"""Draw bambu3mf/icon.png, the 24 x 24 toolbar icon: a tile with an inlay.

    python3 tools/make_icon.py
"""

import os
import struct
import zlib

SIZE = 24
SS = 4  # supersamples per axis

TILE = (233, 196, 106)
EDGE = (150, 112, 30)
INLAY = (255, 255, 255)


def in_rounded(x, y, x0, y0, x1, y1, r):
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def in_inlay(x, y):
    # Three strokes stepping down to the right, like the drawn lines.
    for k in range(3):
        y0 = 7.0 + 4.5 * k
        if 6.0 + 2 * k <= x <= 18.0 and y0 <= y <= y0 + 2.0:
            return True
    return False


def colour(x, y):
    if not in_rounded(x, y, 2, 2, 22, 22, 4):
        return None
    if not in_rounded(x, y, 3.2, 3.2, 20.8, 20.8, 2.8):
        return EDGE
    return INLAY if in_inlay(x, y) else TILE


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
    path = os.path.join(os.path.dirname(__file__), "..", "bambu3mf",
        "icon.png")
    with open(path, "wb") as f:
        f.write(png)


if __name__ == "__main__":
    main()
