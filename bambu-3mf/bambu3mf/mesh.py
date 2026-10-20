"""Extrude 2D polygons with holes into closed triangle meshes.

All coordinates are integers (KiCad nanometres), so every test below is
exact. A polygon is a list of rings, outer ring first, then its holes;
a ring is a list of (x, y) points with the closing edge implied.

The side walls are the ring edges and the caps are earcut triangles made
to conform to them: every ring vertex is a cap vertex, every ring edge a
cap edge. Two things in earcut's output need repair for that. It drops
collinear points, including ones a hole bridge makes collinear, which
leaves a cap edge running through a ring vertex; such triangles are split
at the vertex. And where rings touch at a point, the polygon's interior
there is several wedges, each between an outgoing and an incoming ring
edge that may come from different rings; each wedge gets its own copy of
the point, so the solid stays edge-manifold at the pinch.
"""

import collections
import functools

from .earcut import earcut


class Mesh(object):
    """Vertices are (x, y, z) tuples; triangles are vertex index triples
    wound counter-clockwise when seen from outside the solid."""

    def __init__(self):
        self.vertices = []
        self.triangles = []


def ring_area2(ring):
    """Twice the signed area of a ring, positive when counter-clockwise."""
    s = 0
    x0, y0 = ring[-1]
    for x1, y1 in ring:
        s += x0 * y1 - x1 * y0
        x0, y0 = x1, y1
    return s


def polygon_area2(rings):
    """Twice the area of a polygon: its outer ring less its holes."""
    return abs(ring_area2(rings[0])) - sum(abs(ring_area2(h))
        for h in rings[1:])


def extrude(polygons, z0, z1, mesh):
    """Append a prism from z0 to z1 for each polygon to mesh.

    Returns the number of polygons whose caps could not be made to cover
    exactly the polygon; those are still closed solids, walled along the
    caps' own boundary, but may differ from the polygon.
    """
    bad = 0
    for rings in polygons:
        rings = _normalized(rings)
        if not rings:
            continue
        coords, ring_edges = _flatten(rings)
        tris, walls = _cap(coords, rings, ring_edges)
        ok = sorted(_unpaired(tris)) == sorted(walls)
        bad += not ok
        if not tris:
            continue
        if not ok:
            walls = _unpaired(tris)

        index = {}
        base = len(mesh.vertices)
        for n, i in enumerate(sorted({i for t in tris for i in t})):
            index[i] = base + 2 * n
            x, y = coords[i]
            mesh.vertices.append((x, y, z0))
            mesh.vertices.append((x, y, z1))

        out = mesh.triangles
        for a, b, c in tris:
            a, b, c = index[a], index[b], index[c]
            out.append((a + 1, b + 1, c + 1))
            out.append((a, c, b))
        for a, b in walls:
            a, b = index[a], index[b]
            out.append((b + 1, a + 1, a))
            out.append((b + 1, a, b))
    return bad


def _normalized(rings):
    """Rings without repeated points or zero area, the outer one
    counter-clockwise and the holes clockwise; [] if no outer ring."""
    out = []
    for k, ring in enumerate(rings):
        ring = [p for i, p in enumerate(ring) if p != ring[i - 1]]
        area2 = ring_area2(ring) if len(ring) >= 3 else 0
        if not area2:
            if not k:
                return []
            continue
        if (area2 > 0) != (k == 0):
            ring.reverse()
        out.append(ring)
    return out


def _flatten(rings):
    coords = []
    edges = []
    for ring in rings:
        base = len(coords)
        n = len(ring)
        coords.extend(ring)
        edges.extend((base + i, base + (i + 1) % n) for i in range(n))
    return coords, edges


def _cap(coords, rings, ring_edges):
    """Triangulate, then conform the triangles to the ring edges.
    Returns the triangles and the wall edges they should be bounded by."""
    starts = []
    n = 0
    for ring in rings[:-1]:
        n += len(ring)
        starts.append(n)
    tris = earcut(coords, starts)
    if sum(_cross(coords, t) for t in tris) < 0:
        tris = [(a, c, b) for a, b, c in tris]

    # Work on one id per point; pinched points get their copies back.
    first = {}
    for i, p in enumerate(coords):
        first.setdefault(p, i)
    canon = [first[p] for p in coords]
    tris = [(canon[a], canon[b], canon[c]) for a, b, c in tris]
    tris = [t for t in tris if len(set(t)) == 3]
    ring_set = {(canon[a], canon[b]) for a, b in ring_edges}
    tris = _split_through_vertices(coords, tris, ring_set,
        sorted(set(canon)))
    return _split_pinches(coords, tris, ring_edges, canon)


def _split_through_vertices(coords, tris, ring_set, points):
    """Split triangles whose unpaired edge is not a ring edge but runs
    through ring vertices, fanning from the opposite corner."""
    while True:
        owner = {}
        for n, (a, b, c) in enumerate(tris):
            owner.setdefault((a, b), n)
            owner.setdefault((b, c), n)
            owner.setdefault((c, a), n)
        split = {}
        for (u, v), n in owner.items():
            if (v, u) in owner or (u, v) in ring_set or n in split:
                continue
            on = [k for k in points if _strictly_on(coords, u, v, k)]
            if on:
                ux, uy = coords[u]
                on.sort(key=lambda k: (coords[k][0] - ux) ** 2 +
                    (coords[k][1] - uy) ** 2)
                split[n] = (u, v, on)
        if not split:
            return tris
        out = []
        for n, t in enumerate(tris):
            if n not in split:
                out.append(t)
                continue
            u, v, on = split[n]
            w = t[(t.index(v) + 1) % 3]
            chain = [u] + on + [v]
            out.extend((chain[i], chain[i + 1], w)
                for i in range(len(chain) - 1))
        tris = out


def _split_pinches(coords, tris, ring_edges, canon):
    """Give every interior wedge at a shared point its own vertex.

    Ring edges keep the interior on their left, so around a point the
    edge directions alternate out, in, out, in counter-clockwise, and
    each wedge sweeps from an outgoing edge to the next incoming one.
    The wedge takes the id of its outgoing edge's start. Returns the
    relabelled triangles and ring edges.
    """
    copies = collections.defaultdict(list)
    for i, c in enumerate(canon):
        copies[c].append(i)
    edges = [(canon[a], canon[b]) for a, b in ring_edges]
    shared = {c for c, v in copies.items() if len(v) > 1}
    wedges = {}
    end_id = {}
    for c in shared:
        vx, vy = coords[c]
        rays = []
        for n, (a, b) in enumerate(ring_edges):
            if canon[a] == c:
                rays.append((coords[b][0] - vx, coords[b][1] - vy, 0, n))
            if canon[b] == c:
                rays.append((coords[a][0] - vx, coords[a][1] - vy, 1, n))
        rays.sort(key=functools.cmp_to_key(_by_angle))
        wedges[c] = []
        for k, (x, y, kind, n) in enumerate(rays):
            if kind:
                continue
            nx, ny, nkind, m = rays[(k + 1) % len(rays)]
            wid = ring_edges[n][0]
            wedges[c].append(((x, y), (nx, ny), wid))
            if nkind:
                end_id[m] = wid

    if not shared:
        return tris, edges
    walls = []
    for n, (a, b) in enumerate(edges):
        if a in shared:
            a = ring_edges[n][0]
        if b in shared:
            b = end_id.get(n, ring_edges[n][1])
        walls.append((a, b))

    def pick(c, b, d):
        vx, vy = coords[c]
        w = (coords[b][0] + coords[d][0] - 2 * vx,
            coords[b][1] + coords[d][1] - 2 * vy)
        for d0, d1, wid in wedges[c]:
            if _in_wedge(d0, d1, w):
                return wid
        return c

    out = []
    for a, b, c in tris:
        out.append((pick(a, b, c) if a in shared else a,
            pick(b, c, a) if b in shared else b,
            pick(c, a, b) if c in shared else c))
    return out, walls


def _by_angle(p, q):
    hp = 0 if p[1] > 0 or (p[1] == 0 and p[0] > 0) else 1
    hq = 0 if q[1] > 0 or (q[1] == 0 and q[0] > 0) else 1
    if hp != hq:
        return hp - hq
    return -_sign(p[0] * q[1] - p[1] * q[0])


def _sign(v):
    return (v > 0) - (v < 0)


def _in_wedge(d0, d1, w):
    """Whether direction w lies strictly inside the counter-clockwise
    sweep from d0 to d1."""
    if _cross2(d0, d1) > 0:
        return _cross2(d0, w) > 0 and _cross2(w, d1) > 0
    return not (_cross2(d1, w) >= 0 and _cross2(w, d0) >= 0)


def _strictly_on(coords, u, v, k):
    (ux, uy), (vx, vy), (px, py) = coords[u], coords[v], coords[k]
    dx, dy = vx - ux, vy - uy
    ex, ey = px - ux, py - uy
    if dx * ey - dy * ex:
        return False
    dot = dx * ex + dy * ey
    return 0 < dot < dx * dx + dy * dy


def _cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _cross(coords, tri):
    (ax, ay), (bx, by), (cx, cy) = (coords[i] for i in tri)
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _unpaired(tris):
    edges = set()
    for a, b, c in tris:
        edges.add((a, b))
        edges.add((b, c))
        edges.add((c, a))
    return [e for e in edges if (e[1], e[0]) not in edges]


def unpaired_edges(triangles):
    """Directed edges that lack exactly one opposite edge. A closed,
    consistently wound, edge-manifold mesh has none."""
    count = collections.Counter()
    for a, b, c in triangles:
        count[(a, b)] += 1
        count[(b, c)] += 1
        count[(c, a)] += 1
    return [e for e, n in count.items()
        if n != 1 or count.get((e[1], e[0])) != 1]


def volume6(mesh):
    """Six times the signed volume enclosed by mesh."""
    v = mesh.vertices
    s = 0
    for a, b, c in mesh.triangles:
        x1, y1, z1 = v[a]
        x2, y2, z2 = v[b]
        x3, y3, z3 = v[c]
        s += (x1 * (y2 * z3 - z2 * y3) - y1 * (x2 * z3 - z2 * x3) +
            z1 * (x2 * y3 - y2 * x3))
    return s
