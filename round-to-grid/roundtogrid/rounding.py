"""Round the selected KiCad items to grid steps, in place.

Two kinds of value round on their own steps, and either can be left
alone:

- positions and sizes: points go to the nearest grid point, measured
  from the board's grid origin; radii, corner radii, text sizes and via
  diameters and drills go to the nearest multiple of the step;
- thickness: line, track and border widths and text stroke thickness go
  to the nearest multiple of the step.

An item is deleted when rounding takes something it cannot exist without
to zero: a length, a radius, a side, an area, a stroke thickness, a text
size, a via's diameter or drill. Values that may be zero just become
zero: a filled shape's border width, a rectangle's corner radius, a text
box's border width. What was zero before is not rounding's doing and
stays.

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
        self.changed = 0
        self.unchanged = 0
        self.deleted = collections.Counter()
        self.skipped = collections.Counter()
        self.unfilled = 0

    def lines(self, position_mm, thickness_mm):
        steps = []
        if position_mm:
            steps.append("positions and sizes to %g mm" % position_mm)
        if thickness_mm:
            steps.append("thickness to %g mm" % thickness_mm)
        out = ["Rounded %s." % " and ".join(steps)]
        done = "Changed %d item(s)" % self.changed
        if self.unchanged:
            done += "; %d already on the grid" % self.unchanged
        out.append(done + ".")
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


def round_items(board, items, position_step, thickness_step):
    """Round items (BOARD_ITEMs, groups opened) to the steps, in
    nanometres; a step of None leaves that kind of value alone."""
    ds = board.GetDesignSettings()
    o = ds.GetGridOrigin()
    report = Report()
    for it in flatten(items):
        g = _Grid(position_step, thickness_step, (o.x, o.y), ds.m_MaxError)
        try:
            if it.IsLocked():
                raise Skip("locked")
            handler = _handler(it)
            if handler is None:
                raise Skip(it.GetClass())
            if handler(g, it):
                report.unfilled += 1
            if g.changed:
                report.changed += 1
            else:
                report.unchanged += 1
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
    """Rounds one item's values; changed says whether any of them moved.
    A step of None returns values as they are."""

    def __init__(self, position, thickness, origin, max_error):
        self.position = position
        self.thickness_step = thickness
        self.origin = origin
        self.max_error = max_error
        self.changed = False

    def note(self, old, new):
        if old != new:
            self.changed = True
        return new

    def point(self, v):
        if not self.position:
            return v
        x, y = snap.point((v.x, v.y), self.position, self.origin)
        return self.note(v, pcbnew.VECTOR2I(x, y))

    def size(self, v, what=None):
        """A size on the position step; what names it when it must not
        round to zero, None when it may."""
        return self._length(v, self.position, what)

    def thickness(self, v, what=None):
        """A thickness on the thickness step; what as for size."""
        return self._length(v, self.thickness_step, what)

    def _length(self, v, step, what):
        if not step:
            return v
        r = snap.nearest(v, step)
        if v and not r and what:
            raise Delete(what)
        return self.note(v, r)

    def polygons(self, polys, what):
        """The rounded SHAPE_POLY_SET, collapsed rings dropped, or None
        when positions are left alone."""
        if not self.position:
            return None
        old = []
        new = []
        out = pcbnew.SHAPE_POLY_SET()
        for i in range(polys.OutlineCount()):
            chains = [polys.Outline(i)] + [polys.Hole(i, j)
                for j in range(polys.HoleCount(i))]
            if any(c.ArcCount() for c in chains):
                raise Skip("polygon with arcs")
            rings = [[(p.x, p.y) for p in c.CPoints()] for c in chains]
            done = [snap.ring(r, self.position, self.origin) for r in rings]
            old += rings
            new += done
            if done[0] is None:
                continue
            n = out.AddOutline(_chain(done[0]))
            for h in done[1:]:
                if h is not None:
                    out.AddHole(_chain(h), n)
        if not out.OutlineCount():
            raise Delete(what)
        self.note(old, new)
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
    """The shape's new width: a stroke must stay, a filled shape's border
    width may go to zero."""
    return g.thickness(shape.GetWidth(),
        None if shape.IsAnyFill() else "thickness")


def _collapsed(old_a, old_b, a, b):
    """Whether rounding made two distinct points one."""
    return a == b and old_a != old_b


def _shape(g, s):
    kind = s.GetShape()
    if kind == pcbnew.SHAPE_T_SEGMENT:
        a, b = g.point(s.GetStart()), g.point(s.GetEnd())
        if _collapsed(s.GetStart(), s.GetEnd(), a, b):
            raise Delete("length")
        w = _stroke(g, s)
        s.SetStart(a)
        s.SetEnd(b)
    elif kind == pcbnew.SHAPE_T_RECTANGLE:
        a, b = g.point(s.GetStart()), g.point(s.GetEnd())
        old_a, old_b = s.GetStart(), s.GetEnd()
        if (a.x == b.x and old_a.x != old_b.x) or \
            (a.y == b.y and old_a.y != old_b.y):
            raise Delete("side")
        w = _stroke(g, s)
        r = s.GetCornerRadius()
        if g.position:
            half = min(abs(b.x - a.x), abs(b.y - a.y)) // 2
            r = g.note(r, min(snap.nearest(r, g.position),
                half // g.position * g.position))
        s.SetStart(a)
        s.SetEnd(b)
        s.SetCornerRadius(r)
    elif kind == pcbnew.SHAPE_T_CIRCLE:
        c = g.point(s.GetCenter())
        r = g.size(s.GetRadius(), "radius")
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
        if polys is not None:
            s.SetPolyShape(polys)
    elif kind == pcbnew.SHAPE_T_BEZIER:
        old = [s.GetStart(), s.GetBezierC1(), s.GetBezierC2(), s.GetEnd()]
        pts = [g.point(v) for v in old]
        if all(p == pts[0] for p in pts) and \
            not all(p == old[0] for p in old):
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
    if not g.position:
        return [start, mid, end]
    pts = snap.arc((start.x, start.y), (mid.x, mid.y), (end.x, end.y),
        (center.x, center.y), g.position, g.origin)
    if pts is None:
        raise Delete("arc")
    out = [pcbnew.VECTOR2I(x, y) for x, y in pts]
    g.note([start, mid, end], out)
    return out


def _text_size(g, t):
    size = t.GetTextSize()
    w = g.size(size.x, "text size")
    h = g.size(size.y, "text size")
    thick = g.thickness(t.GetTextThickness(), "text thickness")
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
    old_a, old_b = t.GetStart(), t.GetEnd()
    a, b = g.point(old_a), g.point(old_b)
    if (a.x == b.x and old_a.x != old_b.x) or \
        (a.y == b.y and old_a.y != old_b.y):
        raise Delete("side")
    size, thick = _text_size(g, t)
    border = g.thickness(t.GetBorderWidth()) if t.IsBorderEnabled() else 0
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
    if _collapsed(t.GetStart(), t.GetEnd(), a, b):
        raise Delete("length")
    w = g.thickness(t.GetWidth(), "width")
    t.SetStart(a)
    t.SetEnd(b)
    t.SetWidth(w)


def _track_arc(g, t):
    a, m, b = _arc(g, t.GetStart(), t.GetMid(), t.GetEnd(), t.GetCenter())
    w = g.thickness(t.GetWidth(), "width")
    t.SetStart(a)
    t.SetMid(m)
    t.SetEnd(b)
    t.SetWidth(w)


def _via(g, v):
    p = g.point(v.GetPosition())
    w = g.size(v.GetWidth(pcbnew.F_Cu), "via diameter")
    d = g.size(v.GetDrill(), "drill")
    v.SetPosition(p)
    v.SetWidth(w)
    v.SetDrill(d)


def _zone(g, z):
    polys = g.polygons(z.Outline(), "area")
    if polys is None or not g.changed:
        return False
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
