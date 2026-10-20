"""Grid rounding on integer nanometres; no KiCad needed.

Points round to the nearest grid point measured from the grid origin;
lengths (widths, radii, sizes) round to the nearest multiple of the
step. Halves round up. Every function is a pure function of its inputs,
so two items that share an endpoint still share it afterwards.
"""

import math


def nearest(v, step):
    """v rounded to the nearest multiple of step, halves up."""
    return (2 * v + step) // (2 * step) * step


def point(p, step, origin):
    """p rounded to the nearest grid point."""
    return (origin[0] + nearest(p[0] - origin[0], step),
        origin[1] + nearest(p[1] - origin[1], step))


def at_least(v, step):
    """The smallest multiple of step that is at least v."""
    return -(-v // step) * step


def arc(start, mid, end, center, step, origin):
    """An arc with its ends on the grid and its radius a multiple of step.

    The radius is rounded up instead when the rounded one could not span
    the ends. The centre and the arc keep the sides of the chord they
    had, so a short arc stays short and a long one long. Returns the new
    (start, mid, end), or None when the ends meet or the radius rounds
    to zero.
    """
    a = point(start, step, origin)
    b = point(end, step, origin)
    r = nearest(int(round(math.hypot(start[0] - center[0],
        start[1] - center[1]))), step)
    if a == b or r == 0:
        return None
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    chord = math.hypot(dx, dy)
    r = max(r, at_least(int(math.ceil(chord / 2)), step))
    nx = -dy / chord
    ny = dx / chord
    # Sides are read off the old chord: rounding can carry the new chord
    # past the old mid of a shallow arc, but not turn the chord around,
    # except on a chord shorter than the step; that one flips with it.
    turn = 1 if (dx * (end[0] - start[0]) + dy * (end[1] - start[1])) >= 0 \
        else -1
    side_c = turn * _side(start, end, center)
    side_m = turn * _side(start, end, mid)
    if not side_m:
        side_m = -side_c or 1
    if not side_c:
        side_c = -side_m
    h = math.sqrt(max(r * r - chord * chord / 4, 0.0))
    cx = (a[0] + b[0]) / 2.0 + side_c * h * nx
    cy = (a[1] + b[1]) / 2.0 + side_c * h * ny
    m = (int(round(cx + side_m * r * nx)), int(round(cy + side_m * r * ny)))
    return a, m, b


def ring(points, step, origin):
    """A closed ring rounded to the grid, repeated points dropped; None
    when it no longer encloses any area."""
    out = []
    for p in points:
        q = point((p[0], p[1]), step, origin)
        if not out or q != out[-1]:
            out.append(q)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    if len(out) < 3 or not area2(out):
        return None
    return out


def area2(ring):
    """Twice the signed area of a ring."""
    s = 0
    x0, y0 = ring[-1]
    for x1, y1 in ring:
        s += x0 * y1 - x1 * y0
        x0, y0 = x1, y1
    return s


def _side(a, b, p):
    """Which side of the line a -> b point p lies on: 1, -1, or 0."""
    c = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    return (c > 0) - (c < 0)
