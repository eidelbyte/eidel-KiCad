"""Round the selected KiCad items to a grid step, in place.

Points go to the nearest grid point, measured from the board's grid
origin; widths, thicknesses, radii and text sizes go to the nearest
multiple of the step. An item is deleted when something it cannot exist
without rounds to zero: a length, a radius, a side, an area, a stroke
thickness, a text size, a via's diameter or drill. Values that may be
zero just become zero: a filled shape's border, a rectangle's corner
radius, a text box's border.

Footprints are moved by their anchor only, so their insides keep their
shape. Locked items are left alone.
"""

import collections

import pcbnew

from . import snap


class Delete(Exception):
    """Raised by a handler, before it changes anything, when the item
    would round away; the message says what rounded to zero."""


class Skip(Exception):
    """Raised by a handler, before it changes anything, for an item it
    leaves as it is; the message says why."""


class Report(object):

    def __init__(self):
        self.rounded = 0
        self.deleted = collections.Counter()
        self.skipped = collections.Counter()
        self.unfilled = 0

    def lines(self, step_mm):
        out = ["Rounded %d item(s) to %g mm." % (self.rounded, step_mm)]
        if self.deleted:
            out.append("Deleted %d item(s) that rounded to zero: %s." %
                (sum(self.deleted.values()), _counts(self.deleted)))
        if self.skipped:
            out.append("Left %d item(s) unchanged: %s." %
                (sum(self.skipped.values()), _counts(self.skipped)))
        if self.unfilled:
            out.append("Unfilled %d zone(s); refill with B." % self.unfilled)
        return out


def _counts(counter):
    return ", ".join("%d %s" % (n, what) for what, n in
        sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))


def round_items(board, items, step):
    """Round items (BOARD_ITEMs, groups opened) to step nanometres."""
    ds = board.GetDesignSettings()
    o = ds.GetGridOrigin()
    g = _Grid(step, (o.x, o.y), ds.m_MaxError)
    report = Report()
    for it in flatten(items):
        try:
            if it.IsLocked():
                raise Skip("locked")
            handler = _handler(it)
            if handler is None:
                raise Skip(it.GetClass())
            if handler(g, it):
                report.unfilled += 1
            report.rounded += 1
        except Skip as e:
            report.skipped[str(e)] += 1
        except Delete as e:
            if it.GetClass() == "PCB_FIELD":
                # KiCad keeps a footprint's fields; it cannot lose one.
                report.skipped["footprint field"] += 1
                continue
            _remove(board, it)
            report.deleted[str(e)] += 1
    return report


def flatten(items):
    """items with groups opened up, each once. Footprints stay whole."""
    seen = set()
    out = []
    stack = list(items)
    while stack:
        it = _concrete(stack.pop())
        key = it.m_Uuid.AsString()
        if key in seen:
            continue
        seen.add(key)
        if isinstance(it, pcbnew.PCB_GROUP):
            stack.extend(it.GetItems())
        else:
            out.append(it)
    return out


def _concrete(it):
    """it as its own class; selections hand out bare BOARD_ITEMs."""
    if type(it) is not pcbnew.BOARD_ITEM:
        return it
    if it.GetClass() == "PCB_FIELD":
        return pcbnew.Cast_to_PCB_TEXT(it)
    try:
        return it.Cast()
    except TypeError:
        # A class pcbnew cannot name; it is reported as left unchanged.
        return it


def _remove(board, it):
    group = it.GetParentGroup()
    if group is not None:
        group.RemoveItem(it)
    parent = it.GetParentFootprint()
    (parent if parent is not None else board).Remove(it)


class _Grid(object):

    def __init__(self, step, origin, max_error):
        self.step = step
        self.origin = origin
        self.max_error = max_error

    def point(self, v):
        x, y = snap.point((v.x, v.y), self.step, self.origin)
        return pcbnew.VECTOR2I(x, y)

    def length(self, v, what):
        """A length that must stay above zero."""
        r = snap.nearest(v, self.step)
        if v and not r:
            raise Delete(what)
        return r

    def optional(self, v):
        """A length that may become zero."""
        return snap.nearest(v, self.step)

    def ring(self, chain):
        if chain.ArcCount():
            raise Skip("polygon with arcs")
        return snap.ring([(p.x, p.y) for p in chain.CPoints()], self.step,
            self.origin)

    def polygons(self, polys, what):
        """The rounded SHAPE_POLY_SET; rings that collapse are dropped."""
        out = pcbnew.SHAPE_POLY_SET()
        for i in range(polys.OutlineCount()):
            outline = self.ring(polys.Outline(i))
            holes = [self.ring(polys.Hole(i, j))
                for j in range(polys.HoleCount(i))]
            if outline is None:
                continue
            n = out.AddOutline(_chain(outline))
            for h in holes:
                if h is not None:
                    out.AddHole(_chain(h), n)
        if not out.OutlineCount():
            raise Delete(what)
        return out


def _chain(points):
    c = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in points:
        c.Append(x, y)
    c.SetClosed(True)
    return c


def _handler(it):
    for cls, fn in _HANDLERS:
        if isinstance(it, cls):
            return fn
    return None


def _stroke(g, shape):
    """The shape's new width: a stroke must stay, a filled border may
    go to zero."""
    if shape.IsAnyFill():
        return g.optional(shape.GetWidth())
    return g.length(shape.GetWidth(), "thickness")


def _shape(g, s):
    kind = s.GetShape()
    if kind == pcbnew.SHAPE_T_SEGMENT:
        a, b = g.point(s.GetStart()), g.point(s.GetEnd())
        if a == b:
            raise Delete("length")
        w = _stroke(g, s)
        s.SetStart(a)
        s.SetEnd(b)
    elif kind == pcbnew.SHAPE_T_RECTANGLE:
        a, b = g.point(s.GetStart()), g.point(s.GetEnd())
        if a.x == b.x or a.y == b.y:
            raise Delete("side")
        w = _stroke(g, s)
        half = min(abs(b.x - a.x), abs(b.y - a.y)) // 2
        r = min(g.optional(s.GetCornerRadius()),
            half // g.step * g.step)
        s.SetStart(a)
        s.SetEnd(b)
        s.SetCornerRadius(r)
    elif kind == pcbnew.SHAPE_T_CIRCLE:
        c = g.point(s.GetCenter())
        r = g.length(s.GetRadius(), "radius")
        w = _stroke(g, s)
        s.SetCenter(c)
        s.SetRadius(r)
    elif kind == pcbnew.SHAPE_T_ARC:
        pts = _arc(g, s.GetStart(), s.GetArcMid(), s.GetEnd(), s.GetCenter())
        w = _stroke(g, s)
        s.SetArcGeometry(*pts)
    elif kind == pcbnew.SHAPE_T_POLY:
        polys = g.polygons(s.GetPolyShape(), "area")
        w = _stroke(g, s)
        s.SetPolyShape(polys)
    elif kind == pcbnew.SHAPE_T_BEZIER:
        pts = [g.point(v) for v in (s.GetStart(), s.GetBezierC1(),
            s.GetBezierC2(), s.GetEnd())]
        if all(p == pts[0] for p in pts):
            raise Delete("length")
        w = _stroke(g, s)
        s.SetStart(pts[0])
        s.SetBezierC1(pts[1])
        s.SetBezierC2(pts[2])
        s.SetEnd(pts[3])
        s.RebuildBezierToSegmentsPointsList(g.max_error)
    else:
        raise Skip("shape")
    s.SetWidth(w)


def _arc(g, start, mid, end, center):
    pts = snap.arc((start.x, start.y), (mid.x, mid.y), (end.x, end.y),
        (center.x, center.y), g.step, g.origin)
    if pts is None:
        raise Delete("arc")
    return [pcbnew.VECTOR2I(x, y) for x, y in pts]


def _text_size(g, t):
    size = t.GetTextSize()
    w = g.length(size.x, "text size")
    h = g.length(size.y, "text size")
    thick = g.length(t.GetTextThickness(), "text thickness")
    return pcbnew.VECTOR2I(w, h), thick


def _text(g, t):
    p = g.point(t.GetPosition())
    size, thick = _text_size(g, t)
    t.SetPosition(p)
    t.SetTextSize(size)
    t.SetTextThickness(thick)


def _textbox(g, t):
    if t.GetShape() != pcbnew.SHAPE_T_RECTANGLE:
        raise Skip("rotated text box")
    a, b = g.point(t.GetStart()), g.point(t.GetEnd())
    if a.x == b.x or a.y == b.y:
        raise Delete("side")
    size, thick = _text_size(g, t)
    border = g.optional(t.GetBorderWidth()) if t.IsBorderEnabled() else 0
    t.SetStart(a)
    t.SetEnd(b)
    t.SetTextSize(size)
    t.SetTextThickness(thick)
    if t.IsBorderEnabled():
        if border:
            t.SetBorderWidth(border)
        else:
            t.SetBorderEnabled(False)


def _track(g, t):
    a, b = g.point(t.GetStart()), g.point(t.GetEnd())
    if a == b:
        raise Delete("length")
    w = g.length(t.GetWidth(), "width")
    t.SetStart(a)
    t.SetEnd(b)
    t.SetWidth(w)


def _track_arc(g, t):
    a, m, b = _arc(g, t.GetStart(), t.GetMid(), t.GetEnd(), t.GetCenter())
    w = g.length(t.GetWidth(), "width")
    t.SetStart(a)
    t.SetMid(m)
    t.SetEnd(b)
    t.SetWidth(w)


def _via(g, v):
    p = g.point(v.GetPosition())
    w = g.length(v.GetWidth(pcbnew.F_Cu), "via diameter")
    d = g.length(v.GetDrill(), "drill")
    v.SetPosition(p)
    v.SetWidth(w)
    v.SetDrill(d)


def _zone(g, z):
    polys = g.polygons(z.Outline(), "area")
    outline = z.Outline()
    outline.RemoveAllContours()
    outline.Append(polys)
    z.UnFill()
    return True


def _anchor(g, it):
    it.SetPosition(g.point(it.GetPosition()))


def _leave(why):
    def handler(g, it):
        raise Skip(why)
    return handler


# Subclasses before their bases: a dimension is a text, a text box a
# shape, a via and a track arc are tracks, a footprint field is a text.
# A dimension lays out its own text, so rounding the text alone would
# pull it apart. (Table cells are text boxes too, but pcbnew hands them
# out only as plain BOARD_ITEMs, which no handler takes.)
_HANDLERS = (
    (pcbnew.PCB_DIMENSION_BASE, _leave("dimension")),
    (pcbnew.PCB_TEXTBOX, _textbox),
    (pcbnew.PCB_SHAPE, _shape),
    (pcbnew.PCB_TEXT, _text),
    (pcbnew.PCB_VIA, _via),
    (pcbnew.PCB_ARC, _track_arc),
    (pcbnew.PCB_TRACK, _track),
    (pcbnew.ZONE, _zone),
    (pcbnew.FOOTPRINT, _anchor),
    (pcbnew.PAD, _anchor),
)
