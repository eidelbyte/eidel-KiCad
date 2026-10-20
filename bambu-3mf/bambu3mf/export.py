"""From selected KiCad items to a multi-filament 3MF.

Each chosen layer becomes a region: the union of its items' shapes, with
strokes at their real width and text as glyphs. A layer can also fill
its closed outlines, nested the way Edge.Cuts nests: inside an odd
number of outlines is solid, inside an even number is a hole.

Each region is extruded over the layer's z range. Where two layers'
solids overlap, the smaller solid (by volume) keeps the space and cuts
into the larger one, which is what an inlay needs: the thin lines carve
their channel into the thick tile. A layer that is cut only over part
of its height becomes a stack of slabs, one 3MF part each.
"""

import pcbnew

from . import mesh, threemf

# Print settings seeded on the object; Bambu Studio shows them as the
# object's own settings, so they are changed there, not here. Shipped
# process presets use 5 top and 3 bottom shell layers, no ironing and the
# classic wall generator.
PRINT_SETTINGS = (
    # Thicker solid skins, so colours stay strong on the top face and on
    # the bed face of a print laid face down.
    ("top_shell_layers", "7"),
    ("top_shell_thickness", "1.4"),
    ("bottom_shell_layers", "5"),
    ("bottom_shell_thickness", "1"),
    # A smooth finish on large flat tops.
    ("ironing_type", "top"),
    # Variable-width walls print strokes and traces narrower than the
    # nozzle's line, which the classic generator drops.
    ("wall_generator", "arachne"),
)

# Closed outlines are found on strokes grown by this much, and the filled
# region is shrunk back by the same amount: ends up to the stroke width
# plus twice this apart still close an outline, and zero-width lines
# still enclose their area.
CLOSE_NM = 10000


class ExportError(Exception):
    pass


class Job(object):
    """One KiCad layer to extrude, as chosen in the dialog."""

    def __init__(self, layer, name, filament, fill_closed, depth_nm, z_nm):
        self.layer = layer
        self.name = name
        self.filament = filament
        self.fill_closed = fill_closed
        self.depth_nm = depth_nm
        self.z_nm = z_nm


def flatten(items):
    """The drawable items in items: footprints and groups opened up,
    hidden text dropped, each item once."""
    seen = set()
    out = []
    stack = list(items)
    while stack:
        it = _concrete(stack.pop())
        key = it.m_Uuid.AsString()
        if key in seen:
            continue
        seen.add(key)
        if isinstance(it, pcbnew.FOOTPRINT):
            stack.extend(it.GraphicalItems())
            stack.extend(it.Pads())
            stack.extend(it.Zones())
            stack.extend(it.GetFields())
        elif isinstance(it, pcbnew.PCB_GROUP):
            stack.extend(it.GetItems())
        elif not isinstance(it, pcbnew.PCB_TEXT) or it.IsVisible():
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
        # A class pcbnew cannot name; it still draws as a BOARD_ITEM.
        return it


def layers_of(board, items):
    """[(layer, name)] for the board's layers that items are on, in the
    order KiCad lists them."""
    enabled = board.GetEnabledLayers()
    used = set()
    for it in items:
        used.update(it.GetLayerSet().Seq())
    used &= set(enabled.Seq())
    order = list(enabled.UIOrder())
    order += [layer for layer in enabled.Seq() if layer not in order]
    return [(layer, board.GetLayerName(layer)) for layer in order
        if layer in used]


def layer_region(items, layer, fill_closed, max_error):
    """The area items cover on layer, as a SHAPE_POLY_SET."""
    grow = CLOSE_NM if fill_closed else 0
    shapes = pcbnew.SHAPE_POLY_SET()
    text = pcbnew.SHAPE_POLY_SET()
    for it in items:
        if not it.IsOnLayer(layer):
            continue
        if isinstance(it, pcbnew.PCB_TEXT):
            it.TransformTextToPolySet(text, 0, max_error,
                pcbnew.ERROR_INSIDE)
        elif isinstance(it, pcbnew.PCB_TEXTBOX):
            # Its own polygon is the whole box; draw just the border.
            if it.IsBorderEnabled():
                border = pcbnew.PCB_SHAPE(None, pcbnew.SHAPE_T_POLY)
                border.SetPolyPoints(it.GetCorners())
                border.SetWidth(it.GetBorderWidth())
                border.TransformShapeToPolygon(shapes, layer, grow,
                    max_error, pcbnew.ERROR_INSIDE)
            it.TransformTextToPolySet(text, 0, max_error,
                pcbnew.ERROR_INSIDE)
        else:
            it.TransformShapeToPolygon(shapes, layer, grow, max_error,
                pcbnew.ERROR_INSIDE)
    shapes.Simplify()
    if fill_closed:
        shapes.BooleanAdd(_odd_holes(shapes))
        shapes.Inflate(-grow, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS,
            max_error)
    text.Simplify()
    shapes.BooleanAdd(text)
    return shapes


def _odd_holes(shapes):
    """The area inside an odd number of shapes' hole contours.

    Every closed loop of strokes leaves exactly one hole in the union of
    the strokes, so this is the even-odd fill of the closed outlines,
    without chaining any segments.
    """
    fill = pcbnew.SHAPE_POLY_SET()
    for i in range(shapes.OutlineCount()):
        for j in range(shapes.HoleCount(i)):
            hole = pcbnew.SHAPE_POLY_SET()
            hole.AddOutline(shapes.Hole(i, j).Reverse())
            fill.BooleanXor(hole)
    return fill


def stack(regions):
    """Split overlapping solids so that each point belongs to one layer.

    regions is [(job, SHAPE_POLY_SET)]. Solids are placed smallest first,
    by volume, ties going to the earlier entry; each keeps what no
    smaller solid has taken. Where what is left changes along z, the
    layer is cut into slabs at those heights. Returns non-empty
    [(job, region, z0, z1)] in input order, then by z.
    """
    order = sorted(range(len(regions)),
        key=lambda k: (regions[k][1].Area() * regions[k][0].depth_nm, k))
    placed = []
    slabs = []
    for k in order:
        job, region = regions[k]
        z0, z1 = job.z_nm, job.z_nm + job.depth_nm
        hits = []
        for other, c0, c1 in placed:
            if c0 < z1 and c1 > z0:
                common = pcbnew.SHAPE_POLY_SET(region)
                common.BooleanIntersection(other)
                if not common.IsEmpty():
                    hits.append((other, max(c0, z0), min(c1, z1)))
        cuts = sorted({z0, z1}.union(*({c0, c1} for _, c0, c1 in hits)))
        mine = []
        for a, b in zip(cuts, cuts[1:]):
            part = pcbnew.SHAPE_POLY_SET(region)
            for other, c0, c1 in hits:
                if c0 < b and c1 > a:
                    part.BooleanSubtract(other)
            if mine and mine[-1][4] == a and _same(mine[-1][3], part):
                mine[-1][4] = b
            elif not part.IsEmpty():
                mine.append([k, a, job, part, b])
        slabs += mine
        placed.append((region, z0, z1))
    slabs.sort(key=lambda s: s[:2])
    return [(job, part, a, b) for _, a, job, part, b in slabs]


def _same(p, q):
    diff = pcbnew.SHAPE_POLY_SET(p)
    diff.BooleanXor(q)
    return diff.IsEmpty()


def export(board, items, jobs, path, title):
    """Write the 3MF for items and jobs to path. Returns the report as a
    list of lines; raises ExportError when there is nothing to write."""
    max_error = board.GetDesignSettings().m_MaxError
    notes = []
    regions = []
    for job in jobs:
        region = layer_region(items, job.layer, job.fill_closed, max_error)
        if region.IsEmpty():
            notes.append("%s: the selection has no area on this layer." %
                job.name)
        else:
            regions.append((job, region))
    slabs = stack(regions)
    if not slabs:
        raise ExportError("Nothing to export: the selection has no area "
            "on the chosen layers.")

    boxes = [part.BBox() for _, part, _, _ in slabs]
    cx = (min(b.GetX() for b in boxes) + max(b.GetRight() for b in boxes)) \
        // 2
    cy = (min(b.GetY() for b in boxes) + max(b.GetBottom() for b in boxes)) \
        // 2
    zmin = min(a for _, _, a, _ in slabs)
    count = {}
    for job, _, _, _ in slabs:
        count[job] = count.get(job, 0) + 1
    carved = [job.name for job, _ in regions if job not in count]
    notes += ["%s: entirely covered by smaller solids; not exported." % n
        for n in carved]

    parts = []
    lines = []
    for job, part, a, b in slabs:
        a -= zmin
        b -= zmin
        m = mesh.Mesh()
        bad = mesh.extrude(_polygons(part, cx, cy), a, b, m)
        name = job.name
        if count[job] > 1:
            name = "%s %s-%s mm" % (name, threemf.mm(a), threemf.mm(b))
        parts.append(threemf.Part(name, job.filament, m))
        lines.append("%s: filament %d, z %s to %s mm, %d triangles" %
            (name, job.filament, threemf.mm(a), threemf.mm(b),
            len(m.triangles)))
        if bad:
            notes.append("%s: %d polygon(s) could not be triangulated "
                "exactly; check them in the slicer." % (name, bad))
    threemf.write(path, title, parts, PRINT_SETTINGS)
    return lines + notes


def _polygons(region, cx, cy):
    """region as mesh polygons centred on (cx, cy), y pointing up."""
    out = []
    for i in range(region.OutlineCount()):
        rings = [_ring(region.Outline(i), cx, cy)]
        rings += [_ring(region.Hole(i, j), cx, cy)
            for j in range(region.HoleCount(i))]
        out.append(rings)
    return out


def _ring(chain, cx, cy):
    return [(p.x - cx, cy - p.y) for p in chain.CPoints()]
