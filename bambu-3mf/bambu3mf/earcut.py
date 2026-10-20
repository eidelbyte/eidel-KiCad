# Polygon triangulation by ear clipping with hole bridging.
#
# A Python port of mapbox/earcut (https://github.com/mapbox/earcut).
#
# ISC License
#
# Copyright (c) 2016, Mapbox
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND ISC DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL ISC BE LIABLE FOR ANY
# SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
# Port notes: coordinates are expected to be integers (KiCad nanometres),
# so every orientation test is exact. Triangles only ever reference input
# vertices; no Steiner points are added. That is what lets mesh.py build
# the side walls from the boundary edges of the cap triangulation.


class _Node(object):
    __slots__ = ("i", "x", "y", "prev", "next", "z", "prevZ", "nextZ",
            "steiner")

    def __init__(self, i, x, y):
        self.i = i
        self.x = x
        self.y = y
        self.prev = None
        self.next = None
        self.z = 0
        self.prevZ = None
        self.nextZ = None
        self.steiner = False


def earcut(coords, hole_starts=()):
    """Triangulate one polygon with holes.

    coords is a flat list of (x, y) pairs: the outer ring first, then each
    hole. hole_starts holds the vertex index at which each hole begins.
    Ring orientation does not matter. Returns a list of (a, b, c) vertex
    index triples, all wound the same way.
    """
    outer_len = hole_starts[0] if hole_starts else len(coords)
    outer = _linked_list(coords, 0, outer_len, True)
    tris = []
    if outer is None or outer.next is outer.prev:
        return tris

    if hole_starts:
        outer = _eliminate_holes(coords, hole_starts, outer)

    min_x = min_y = inv_size = 0
    if len(coords) > 80:
        xs = [p[0] for p in coords[:outer_len]]
        ys = [p[1] for p in coords[:outer_len]]
        min_x, min_y = min(xs), min(ys)
        size = max(max(xs) - min_x, max(ys) - min_y)
        inv_size = 32767.0 / size if size else 0

    _earcut_linked(outer, tris, min_x, min_y, inv_size, 0)
    return tris


def _linked_list(coords, start, end, clockwise):
    last = None
    if clockwise == (_signed_area(coords, start, end) > 0):
        for i in range(start, end):
            last = _insert_node(i, coords[i][0], coords[i][1], last)
    else:
        for i in range(end - 1, start - 1, -1):
            last = _insert_node(i, coords[i][0], coords[i][1], last)
    if last is not None and _equals(last, last.next):
        _remove_node(last)
        last = last.next
    return last


def _filter_points(start, end=None):
    """Drop duplicate and collinear points."""
    if start is None:
        return start
    if end is None:
        end = start
    p = start
    while True:
        again = False
        if not p.steiner and (_equals(p, p.next) or
                _area(p.prev, p, p.next) == 0):
            _remove_node(p)
            p = end = p.prev
            if p is p.next:
                break
            again = True
        else:
            p = p.next
        if not again and p is end:
            break
    return end


def _earcut_linked(ear, tris, min_x, min_y, inv_size, pass_):
    if ear is None:
        return
    if not pass_ and inv_size:
        _index_curve(ear, min_x, min_y, inv_size)

    stop = ear
    while ear.prev is not ear.next:
        prev = ear.prev
        nxt = ear.next
        if (_is_ear_hashed(ear, min_x, min_y, inv_size) if inv_size
                else _is_ear(ear)):
            tris.append((prev.i, ear.i, nxt.i))
            _remove_node(ear)
            # Skipping the next vertex leaves fewer slivers.
            ear = nxt.next
            stop = nxt.next
            continue

        ear = nxt
        if ear is stop:
            # No ear left: filter, then cure local self-intersections,
            # then split the remainder in two.
            if not pass_:
                _earcut_linked(_filter_points(ear), tris, min_x, min_y,
                        inv_size, 1)
            elif pass_ == 1:
                ear = _cure_local_intersections(_filter_points(ear),
                        tris)
                _earcut_linked(ear, tris, min_x, min_y, inv_size, 2)
            elif pass_ == 2:
                _split_earcut(ear, tris, min_x, min_y, inv_size)
            break


def _tri_bbox(a, b, c):
    return (min(a.x, b.x, c.x), min(a.y, b.y, c.y),
            max(a.x, b.x, c.x), max(a.y, b.y, c.y))


def _blocks_ear(p, a, b, c, x0, y0, x1, y1):
    return (x0 <= p.x <= x1 and y0 <= p.y <= y1 and
            _point_in_triangle(a.x, a.y, b.x, b.y, c.x, c.y, p.x, p.y) and
            _area(p.prev, p, p.next) >= 0)


def _is_ear(ear):
    a, b, c = ear.prev, ear, ear.next
    if _area(a, b, c) >= 0:
        return False  # reflex
    x0, y0, x1, y1 = _tri_bbox(a, b, c)
    p = c.next
    while p is not a:
        if _blocks_ear(p, a, b, c, x0, y0, x1, y1):
            return False
        p = p.next
    return True


def _is_ear_hashed(ear, min_x, min_y, inv_size):
    a, b, c = ear.prev, ear, ear.next
    if _area(a, b, c) >= 0:
        return False  # reflex
    x0, y0, x1, y1 = _tri_bbox(a, b, c)
    min_z = _z_order(x0, y0, min_x, min_y, inv_size)
    max_z = _z_order(x1, y1, min_x, min_y, inv_size)

    p = ear.prevZ
    n = ear.nextZ
    while p is not None and p.z >= min_z and n is not None and \
            n.z <= max_z:
        if p is not a and p is not c and \
                _blocks_ear(p, a, b, c, x0, y0, x1, y1):
            return False
        p = p.prevZ
        if n is not a and n is not c and \
                _blocks_ear(n, a, b, c, x0, y0, x1, y1):
            return False
        n = n.nextZ
    while p is not None and p.z >= min_z:
        if p is not a and p is not c and \
                _blocks_ear(p, a, b, c, x0, y0, x1, y1):
            return False
        p = p.prevZ
    while n is not None and n.z <= max_z:
        if n is not a and n is not c and \
                _blocks_ear(n, a, b, c, x0, y0, x1, y1):
            return False
        n = n.nextZ
    return True


def _cure_local_intersections(start, tris):
    p = start
    while True:
        a = p.prev
        b = p.next.next
        if not _equals(a, b) and _intersects(a, p, p.next, b) and \
                _locally_inside(a, b) and _locally_inside(b, a):
            tris.append((a.i, p.i, b.i))
            _remove_node(p)
            _remove_node(p.next)
            p = start = b
        p = p.next
        if p is start:
            break
    return _filter_points(p)


def _split_earcut(start, tris, min_x, min_y, inv_size):
    a = start
    while True:
        b = a.next.next
        while b is not a.prev:
            if a.i != b.i and _is_valid_diagonal(a, b):
                c = _split_polygon(a, b)
                a = _filter_points(a, a.next)
                c = _filter_points(c, c.next)
                _earcut_linked(a, tris, min_x, min_y, inv_size, 0)
                _earcut_linked(c, tris, min_x, min_y, inv_size, 0)
                return
            b = b.next
        a = a.next
        if a is start:
            break


def _eliminate_holes(coords, hole_starts, outer):
    queue = []
    for k, start in enumerate(hole_starts):
        end = hole_starts[k + 1] if k + 1 < len(hole_starts) \
                else len(coords)
        lst = _linked_list(coords, start, end, False)
        if lst is None:
            continue
        if lst is lst.next:
            lst.steiner = True
        queue.append(_get_leftmost(lst))
    queue.sort(key=lambda n: (n.x, n.y))
    for hole in queue:
        outer = _eliminate_hole(hole, outer)
    return outer


def _eliminate_hole(hole, outer):
    bridge = _find_hole_bridge(hole, outer)
    if bridge is None:
        return outer
    bridge_reverse = _split_polygon(bridge, hole)
    _filter_points(bridge_reverse, bridge_reverse.next)
    return _filter_points(bridge, bridge.next)


def _find_hole_bridge(hole, outer):
    """David Eberly's bridge search from a hole to the outer ring."""
    p = outer
    hx = hole.x
    hy = hole.y
    qx = float("-inf")
    m = None

    # The ray from the hole's leftmost point to the left hits a segment;
    # that segment's endpoint with the lesser x is the first candidate.
    while True:
        if hy <= p.y and hy >= p.next.y and p.next.y != p.y:
            x = p.x + (hy - p.y) * (p.next.x - p.x) / \
                    float(p.next.y - p.y)
            if x <= hx and x > qx:
                qx = x
                m = p if p.x < p.next.x else p.next
                if x == hx:
                    return m  # hole touches the segment
        p = p.next
        if p is outer:
            break
    if m is None:
        return None

    # Points inside the triangle (hole point, ray hit, candidate) would
    # block the bridge; take the one with the smallest angle to the ray.
    stop = m
    mx = m.x
    my = m.y
    tan_min = float("inf")
    p = m
    while True:
        if hx >= p.x and p.x >= mx and hx != p.x and \
                _point_in_triangle(hx if hy < my else qx, hy, mx, my,
                qx if hy < my else hx, hy, p.x, p.y):
            tan = abs(hy - p.y) / float(hx - p.x)
            if _locally_inside(p, hole) and (tan < tan_min or
                    (tan == tan_min and (p.x > m.x or (p.x == m.x and
                    _sector_contains_sector(m, p))))):
                m = p
                tan_min = tan
        p = p.next
        if p is stop:
            break
    return m


def _sector_contains_sector(m, p):
    return _area(m.prev, m, p.prev) < 0 and _area(p.next, m, m.next) < 0


def _index_curve(start, min_x, min_y, inv_size):
    p = start
    while True:
        if p.z == 0:
            p.z = _z_order(p.x, p.y, min_x, min_y, inv_size)
        p.prevZ = p.prev
        p.nextZ = p.next
        p = p.next
        if p is start:
            break
    p.prevZ.nextZ = None
    p.prevZ = None
    _sort_linked(p)


def _sort_linked(lst):
    """Simon Tatham's linked-list merge sort on z."""
    in_size = 1
    while True:
        p = lst
        lst = None
        tail = None
        num_merges = 0
        while p is not None:
            num_merges += 1
            q = p
            p_size = 0
            for _ in range(in_size):
                p_size += 1
                q = q.nextZ
                if q is None:
                    break
            q_size = in_size
            while p_size > 0 or (q_size > 0 and q is not None):
                if p_size != 0 and (q_size == 0 or q is None or
                        p.z <= q.z):
                    e = p
                    p = p.nextZ
                    p_size -= 1
                else:
                    e = q
                    q = q.nextZ
                    q_size -= 1
                if tail is not None:
                    tail.nextZ = e
                else:
                    lst = e
                e.prevZ = tail
                tail = e
            p = q
        tail.nextZ = None
        in_size *= 2
        if num_merges <= 1:
            break
    return lst


def _z_order(x, y, min_x, min_y, inv_size):
    x = int((x - min_x) * inv_size)
    y = int((y - min_y) * inv_size)
    x = (x | (x << 8)) & 0x00FF00FF
    x = (x | (x << 4)) & 0x0F0F0F0F
    x = (x | (x << 2)) & 0x33333333
    x = (x | (x << 1)) & 0x55555555
    y = (y | (y << 8)) & 0x00FF00FF
    y = (y | (y << 4)) & 0x0F0F0F0F
    y = (y | (y << 2)) & 0x33333333
    y = (y | (y << 1)) & 0x55555555
    return x | (y << 1)


def _get_leftmost(start):
    p = start
    leftmost = start
    while True:
        if p.x < leftmost.x or (p.x == leftmost.x and p.y < leftmost.y):
            leftmost = p
        p = p.next
        if p is start:
            break
    return leftmost


def _point_in_triangle(ax, ay, bx, by, cx, cy, px, py):
    return ((cx - px) * (ay - py) >= (ax - px) * (cy - py) and
            (ax - px) * (by - py) >= (bx - px) * (ay - py) and
            (bx - px) * (cy - py) >= (cx - px) * (by - py))


def _is_valid_diagonal(a, b):
    return (a.next.i != b.i and a.prev.i != b.i and
            not _intersects_polygon(a, b) and
            ((_locally_inside(a, b) and _locally_inside(b, a) and
            _middle_inside(a, b) and
            (_area(a.prev, a, b.prev) != 0 or _area(a, b.prev, b) != 0)) or
            (_equals(a, b) and _area(a.prev, a, a.next) > 0 and
            _area(b.prev, b, b.next) > 0)))


def _area(p, q, r):
    return (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y)


def _equals(p1, p2):
    return p1.x == p2.x and p1.y == p2.y


def _sign(v):
    return (v > 0) - (v < 0)


def _intersects(p1, q1, p2, q2):
    o1 = _sign(_area(p1, q1, p2))
    o2 = _sign(_area(p1, q1, q2))
    o3 = _sign(_area(p2, q2, p1))
    o4 = _sign(_area(p2, q2, q1))
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _on_segment(p1, p2, q1):
        return True
    if o2 == 0 and _on_segment(p1, q2, q1):
        return True
    if o3 == 0 and _on_segment(p2, p1, q2):
        return True
    if o4 == 0 and _on_segment(p2, q1, q2):
        return True
    return False


def _on_segment(p, q, r):
    return (min(p.x, r.x) <= q.x <= max(p.x, r.x) and
            min(p.y, r.y) <= q.y <= max(p.y, r.y))


def _intersects_polygon(a, b):
    p = a
    while True:
        if p.i != a.i and p.next.i != a.i and p.i != b.i and \
                p.next.i != b.i and _intersects(p, p.next, a, b):
            return True
        p = p.next
        if p is a:
            break
    return False


def _locally_inside(a, b):
    if _area(a.prev, a, a.next) < 0:
        return _area(a, b, a.next) >= 0 and _area(a, a.prev, b) >= 0
    return _area(a, b, a.prev) < 0 or _area(a, a.next, b) < 0


def _middle_inside(a, b):
    p = a
    inside = False
    px = (a.x + b.x) / 2.0
    py = (a.y + b.y) / 2.0
    while True:
        if ((p.y > py) != (p.next.y > py)) and p.next.y != p.y and \
                (px < (p.next.x - p.x) * (py - p.y) / float(p.next.y - p.y) +
                p.x):
            inside = not inside
        p = p.next
        if p is a:
            break
    return inside


def _split_polygon(a, b):
    """Bridge a and b. Same ring: split in two. Hole and outer: merge."""
    a2 = _Node(a.i, a.x, a.y)
    b2 = _Node(b.i, b.x, b.y)
    an = a.next
    bp = b.prev

    a.next = b
    b.prev = a
    a2.next = an
    an.prev = a2
    b2.next = a2
    a2.prev = b2
    bp.next = b2
    b2.prev = bp
    return b2


def _insert_node(i, x, y, last):
    p = _Node(i, x, y)
    if last is None:
        p.prev = p
        p.next = p
    else:
        p.next = last.next
        p.prev = last
        last.next.prev = p
        last.next = p
    return p


def _remove_node(p):
    p.next.prev = p.prev
    p.prev.next = p.next
    if p.prevZ is not None:
        p.prevZ.nextZ = p.nextZ
    if p.nextZ is not None:
        p.nextZ.prevZ = p.prevZ


def _signed_area(coords, start, end):
    s = 0
    j = end - 1
    for i in range(start, end):
        s += (coords[j][0] - coords[i][0]) * (coords[i][1] + coords[j][1])
        j = i
    return s
