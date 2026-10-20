"""Layer regions, stacking and the whole export, on in-memory boards.

Run with KiCad's Python (it needs pcbnew). Cells (see MATRIX.md):
R1-R9 regions, F1-F3 selection, S1-S9 stacking, X1-X3 export.
"""

import io
import math
import os
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile

import pcbnew

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bambu3mf import export, mesh  # noqa: E402

MM = 1000000
MM2 = 1e12
NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
SILK = pcbnew.F_SilkS
DWGS = pcbnew.Dwgs_User


def v(x, y):
    return pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))


class Drawing(object):
    """A board to draw on, in millimetres."""

    def __init__(self):
        self.board = pcbnew.BOARD()
        self.err = self.board.GetDesignSettings().m_MaxError

    def add(self, item):
        self.board.Add(item)
        return item

    def line(self, layer, x0, y0, x1, y1, w):
        s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(v(x0, y0))
        s.SetEnd(v(x1, y1))
        s.SetWidth(int(round(w * MM)))
        s.SetLayer(layer)
        return self.add(s)

    def arc(self, layer, cx, cy, r, a0, a1, w):
        """Arc around (cx, cy) from angle a0 to a1, in degrees."""
        pts = [(cx + r * math.cos(math.radians(a)),
            cy + r * math.sin(math.radians(a))) for a in (a0, (a0 + a1) / 2.0,
            a1)]
        s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(*(v(x, y) for x, y in pts))
        s.SetWidth(int(round(w * MM)))
        s.SetLayer(layer)
        return self.add(s)

    def polyline(self, layer, pts, w, closed=True):
        pts = list(pts)
        n = len(pts) if closed else len(pts) - 1
        return [self.line(layer, pts[i][0], pts[i][1],
            pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1], w)
            for i in range(n)]

    def square(self, layer, x0, y0, x1, y1, w):
        return self.polyline(layer, [(x0, y0), (x1, y0), (x1, y1),
            (x0, y1)], w)

    def rounded(self, layer, x0, y0, x1, y1, r, w):
        """A rounded rectangle from 4 lines and 4 arcs, like a drawn
        Edge.Cuts outline."""
        out = [self.line(layer, x0 + r, y0, x1 - r, y0, w),
            self.line(layer, x1, y0 + r, x1, y1 - r, w),
            self.line(layer, x1 - r, y1, x0 + r, y1, w),
            self.line(layer, x0, y1 - r, x0, y0 + r, w)]
        out += [self.arc(layer, x1 - r, y0 + r, r, 270, 360, w),
            self.arc(layer, x1 - r, y1 - r, r, 0, 90, w),
            self.arc(layer, x0 + r, y1 - r, r, 90, 180, w),
            self.arc(layer, x0 + r, y0 + r, r, 180, 270, w)]
        return out

    def text(self, layer, s, x, y, size=2.0, thickness=0.3):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(s)
        t.SetLayer(layer)
        t.SetPosition(v(x, y))
        t.SetTextSize(v(size, size))
        t.SetTextThickness(int(round(thickness * MM)))
        return self.add(t)

    def filled_rect(self, layer, x0, y0, x1, y1):
        s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_RECTANGLE)
        s.SetStart(v(x0, y0))
        s.SetEnd(v(x1, y1))
        s.SetWidth(0)
        s.SetFilled(True)
        s.SetLayer(layer)
        return self.add(s)

    def area(self, items, layer, fill):
        r = export.layer_region(items, layer, fill, self.err)
        return r.Area() / MM2


def rounded_area(w, h, r):
    return w * h - (4 - math.pi) * r * r


# KiCad approximates arcs from inside, at most max_error (5 um here) off,
# so a region with curved boundary of length L loses less than L * 5 um.
def arc_tol(length_mm):
    return length_mm * 0.005


class TestRegions(unittest.TestCase):

    def setUp(self):
        self.d = Drawing()

    def test_r1_stroke_width_respected(self):
        items = [self.d.line(DWGS, 0, 0, 10, 0, 0.5)]
        self.assertAlmostEqual(self.d.area(items, DWGS, False),
            10 * 0.5 + math.pi * 0.25 ** 2, places=2)

    def test_r2_rounded_outline_filled_to_stroke_edge(self):
        # The tile in the screenshot: 12 x 12, r = 1, 0.3 mm stroke.
        items = self.d.rounded(SILK, 0, 0, 12, 12, 1, 0.3)
        self.assertAlmostEqual(self.d.area(items, SILK, True),
            rounded_area(12.3, 12.3, 1.15),
            delta=arc_tol(2 * math.pi * 1.15))

    def test_r2_rounded_outline_unfilled_is_a_ring(self):
        items = self.d.rounded(SILK, 0, 0, 12, 12, 1, 0.3)
        self.assertAlmostEqual(self.d.area(items, SILK, False),
            rounded_area(12.3, 12.3, 1.15) - rounded_area(11.7, 11.7, 0.85),
            delta=arc_tol(2 * math.pi * (1.15 + 0.85)))

    def test_r3_nested_outlines_alternate(self):
        items = self.d.square(SILK, 0, 0, 20, 20, 0.2)
        items += self.d.square(SILK, 5, 5, 15, 15, 0.2)
        items += self.d.square(SILK, 7.5, 7.5, 12.5, 12.5, 0.2)
        outer = 20.2 ** 2 - (4 - math.pi) * 0.1 ** 2
        hole = 9.8 ** 2
        island = 5.2 ** 2 - (4 - math.pi) * 0.1 ** 2
        self.assertAlmostEqual(self.d.area(items, SILK, True),
            outer - hole + island, places=2)

    def test_r4_text_is_not_filled(self):
        t = [self.d.text(SILK, "O8", 30, 30)]
        self.assertGreater(self.d.area(t, SILK, False), 0)
        self.assertAlmostEqual(self.d.area(t, SILK, True),
            self.d.area(t, SILK, False), places=6)

    def test_r4_text_inside_a_filled_outline_is_covered(self):
        items = self.d.rounded(SILK, 0, 0, 12, 12, 1, 0.3)
        items.append(self.d.text(SILK, "10", 9, 10, 1.0, 0.1))
        self.assertAlmostEqual(self.d.area(items, SILK, True),
            rounded_area(12.3, 12.3, 1.15),
            delta=arc_tol(2 * math.pi * 1.15))

    def test_r5_open_chain_is_not_filled(self):
        items = self.d.polyline(SILK, [(0, 0), (10, 0), (10, 10), (0, 10)],
            0.3, closed=False)
        self.assertAlmostEqual(self.d.area(items, SILK, True),
            self.d.area(items, SILK, False), places=3)

    def test_r6_zero_width_outline_with_gap_is_filled(self):
        # Corners 5 um apart still close; zero width still encloses.
        items = self.d.polyline(SILK, [(0, 0), (10, 0), (10, 10)], 0,
            closed=False)
        items += self.d.polyline(SILK, [(10.005, 10), (0, 10), (0, 0)], 0,
            closed=False)
        self.assertAlmostEqual(self.d.area(items, SILK, True), 100, places=1)
        self.assertEqual(self.d.area(items, SILK, False), 0)

    def test_r7_filled_shapes_are_solid(self):
        items = [self.d.filled_rect(SILK, 0, 0, 4, 3)]
        self.assertAlmostEqual(self.d.area(items, SILK, False), 12, places=4)

    def test_r8_textbox_border_and_text(self):
        tb = pcbnew.PCB_TEXTBOX(self.d.board)
        tb.SetLayer(SILK)
        tb.SetStart(v(0, 0))
        tb.SetEnd(v(10, 5))
        tb.SetText("I")
        tb.SetTextSize(v(2, 2))
        tb.SetTextThickness(int(0.3 * MM))
        self.d.add(tb)
        text_only = pcbnew.SHAPE_POLY_SET()
        tb.TransformTextToPolySet(text_only, 0, self.d.err,
            pcbnew.ERROR_INSIDE)
        text_area = text_only.Area() / MM2
        w = tb.GetBorderWidth() / float(MM)
        border = (10 + w) * (5 + w) - (10 - w) * (5 - w) - \
            (4 - math.pi) * (w / 2) ** 2
        self.assertAlmostEqual(self.d.area([tb], SILK, False),
            border + text_area, places=2)
        tb.SetBorderEnabled(False)
        self.assertAlmostEqual(self.d.area([tb], SILK, False), text_area,
            places=4)

    def test_r9_other_layers_ignored(self):
        items = [self.d.line(DWGS, 0, 0, 10, 0, 0.5)]
        self.assertEqual(self.d.area(items, SILK, False), 0)


class TestSelection(unittest.TestCase):

    def setUp(self):
        self.d = Drawing()

    def test_f1_groups_open_and_items_count_once(self):
        a = self.d.line(SILK, 0, 0, 1, 0, 0.2)
        b = self.d.line(DWGS, 0, 1, 1, 1, 0.2)
        g = pcbnew.PCB_GROUP(self.d.board)
        self.d.add(g)
        g.AddItem(a)
        g.AddItem(b)
        got = export.flatten([g, a])
        self.assertEqual(sorted(i.m_Uuid.AsString() for i in got),
            sorted(i.m_Uuid.AsString() for i in (a, b)))

    def test_f2_footprint_opens_and_hidden_fields_drop(self):
        fp = pcbnew.FOOTPRINT(self.d.board)
        fp.SetReference("R1")
        self.d.add(fp)
        s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(v(0, 0))
        s.SetEnd(v(2, 0))
        s.SetLayer(SILK)
        fp.Add(s)
        got = export.flatten([fp])
        kinds = sorted(type(i).__name__ for i in got)
        self.assertIn("PCB_SHAPE", kinds)
        names = [i.GetName() for i in got if isinstance(i, pcbnew.PCB_FIELD)]
        self.assertIn("Reference", names)
        self.assertNotIn("Datasheet", names)

    def test_f3_layers_limited_to_enabled_in_ui_order(self):
        fp = pcbnew.FOOTPRINT(self.d.board)
        self.d.add(fp)
        pad = pcbnew.PAD(fp)
        fp.Add(pad)
        items = export.flatten([pad, self.d.line(DWGS, 0, 0, 1, 0, 0.2)])
        names = [n for _, n in export.layers_of(self.d.board, items)]
        self.assertIn("F.Cu", names)
        self.assertNotIn("In1.Cu", names)
        self.assertLess(names.index("F.Cu"), names.index("B.Cu"))


def rect_set(x0, y0, x1, y1):
    s = pcbnew.SHAPE_POLY_SET()
    c = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        c.Append(int(round(x * MM)), int(round(y * MM)))
    c.SetClosed(True)
    s.AddOutline(c)
    return s


def job(name, depth, z=0.0, layer=SILK):
    return export.Job(layer, name, 1, False, int(round(depth * MM)),
        int(round(z * MM)))


class TestStack(unittest.TestCase):

    def run_stack(self, regions):
        slabs = export.stack(regions)
        self.check_disjoint(slabs)
        self.check_volume(regions, slabs)
        return [(j.name, a / float(MM), b / float(MM),
            round(r.Area() / MM2, 6)) for j, r, a, b in slabs]

    def check_disjoint(self, slabs):
        for i, (_, r1, a1, b1) in enumerate(slabs):
            for _, r2, a2, b2 in slabs[i + 1:]:
                if a1 < b2 and a2 < b1:
                    common = pcbnew.SHAPE_POLY_SET(r1)
                    common.BooleanIntersection(r2)
                    self.assertAlmostEqual(common.Area() / MM2, 0, places=9)

    def check_volume(self, regions, slabs):
        zs = sorted({z for j, _ in regions
            for z in (j.z_nm, j.z_nm + j.depth_nm)})
        union = 0.0
        for a, b in zip(zs, zs[1:]):
            u = pcbnew.SHAPE_POLY_SET()
            for j, r in regions:
                if j.z_nm < b and j.z_nm + j.depth_nm > a:
                    u.BooleanAdd(r)
            union += u.Area() * (b - a)
        got = sum(r.Area() * (b - a) for _, r, a, b in slabs)
        self.assertAlmostEqual(got / union, 1, places=9)

    def test_s1_top_inlay(self):
        got = self.run_stack([(job("tile", 5), rect_set(0, 0, 10, 10)),
            (job("lines", 2.5, 2.5), rect_set(2, 1, 4, 9))])
        self.assertEqual(got, [("tile", 0, 2.5, 100), ("tile", 2.5, 5, 84),
            ("lines", 2.5, 5, 16)])

    def test_s2_bottom_inlay(self):
        got = self.run_stack([(job("tile", 5), rect_set(0, 0, 10, 10)),
            (job("lines", 2.5), rect_set(2, 1, 4, 9))])
        self.assertEqual(got, [("tile", 0, 2.5, 84), ("tile", 2.5, 5, 100),
            ("lines", 0, 2.5, 16)])

    def test_s3_through_inlay(self):
        got = self.run_stack([(job("tile", 5), rect_set(0, 0, 10, 10)),
            (job("lines", 5), rect_set(2, 1, 4, 9))])
        self.assertEqual(got, [("tile", 0, 5, 84), ("lines", 0, 5, 16)])

    def test_s4_raised_lines_do_not_split(self):
        got = self.run_stack([(job("tile", 5), rect_set(0, 0, 10, 10)),
            (job("lines", 1, 5), rect_set(2, 1, 4, 9))])
        self.assertEqual(got, [("tile", 0, 5, 100), ("lines", 5, 6, 16)])

    def test_s5_disjoint_in_xy_do_not_split(self):
        got = self.run_stack([(job("a", 5), rect_set(0, 0, 10, 10)),
            (job("b", 2.5, 1), rect_set(20, 0, 22, 9))])
        self.assertEqual(got, [("a", 0, 5, 100), ("b", 1, 3.5, 18)])

    def test_s6_tie_goes_to_the_earlier_layer(self):
        got = self.run_stack([(job("a", 2), rect_set(0, 0, 10, 10)),
            (job("b", 2), rect_set(0, 0, 10, 10))])
        self.assertEqual(got, [("a", 0, 2, 100)])

    def test_s7_smaller_but_taller_wins(self):
        got = self.run_stack([(job("plate", 1), rect_set(0, 0, 10, 10)),
            (job("post", 6), rect_set(4, 4, 6, 6))])
        self.assertEqual(got, [("plate", 0, 1, 96), ("post", 0, 6, 4)])

    def test_s8_three_nested_layers(self):
        got = self.run_stack([(job("a", 6), rect_set(0, 0, 10, 10)),
            (job("b", 4, 2), rect_set(2, 2, 8, 8)),
            (job("c", 2, 4), rect_set(4, 4, 6, 6))])
        self.assertEqual(got, [("a", 0, 2, 100), ("a", 2, 6, 64),
            ("b", 2, 4, 36), ("b", 4, 6, 32), ("c", 4, 6, 4)])

    def test_s9_partial_overlap_in_z(self):
        got = self.run_stack([(job("a", 4), rect_set(0, 0, 10, 10)),
            (job("b", 4, 2), rect_set(5, 0, 7, 10))])
        self.assertEqual(got, [("a", 0, 2, 100), ("a", 2, 4, 80),
            ("b", 2, 6, 20)])


def read_3mf(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    root = ET.fromstring(z.read("3D/3dmodel.model"))
    cfg = ET.fromstring(z.read("Metadata/model_settings.config"))
    parts = {}
    for p in cfg.find("object").findall("part"):
        md = {m.get("key"): m.get("value") for m in p.findall("metadata")}
        parts[p.get("id")] = (md["name"], int(md["extruder"]))
    out = []
    for obj in root.findall("m:resources/m:object", NS):
        if obj.find("m:mesh", NS) is None:
            continue
        m = mesh.Mesh()
        m.vertices = [tuple(int(round(float(x.get(k)) * MM)) for k in "xyz")
            for x in obj.findall("m:mesh/m:vertices/m:vertex", NS)]
        m.triangles = [tuple(int(t.get(k)) for k in ("v1", "v2", "v3"))
            for t in obj.findall("m:mesh/m:triangles/m:triangle", NS)]
        name, extruder = parts[obj.get("id")]
        out.append((name, extruder, m))
    return out


class TestExport(unittest.TestCase):

    def tile(self):
        d = Drawing()
        items = d.rounded(SILK, 0, 0, 12, 12, 1, 0.3)
        items.append(d.text(SILK, "10", 9, 10, 1.0, 0.1))
        items += d.polyline(DWGS, [(2, 2), (2, 10), (6, 10)], 0.3,
            closed=False)
        items.append(d.arc(DWGS, 6, 6, 2, 0, 180, 0.3))
        jobs = [export.Job(SILK, "F.Silkscreen", 3, True, 5 * MM, 0),
            export.Job(DWGS, "User.Drawings", 2, False, 2500000, 2500000)]
        return d, items, jobs

    def test_x1_parts_filaments_and_closed_meshes(self):
        d, items, jobs = self.tile()
        buf = io.BytesIO()
        lines = export.export(d.board, items, jobs, buf, "tile")
        parts = read_3mf(buf.getvalue())
        self.assertEqual([(n, e) for n, e, _ in parts],
            [("F.Silkscreen 0-2.5 mm", 3), ("F.Silkscreen 2.5-5 mm", 3),
            ("User.Drawings", 2)])
        for name, _, m in parts:
            self.assertEqual(mesh.unpaired_edges(m.triangles), [], name)
            self.assertGreater(mesh.volume6(m), 0, name)
        self.assertEqual(len(lines), 3)

    def test_x2_mesh_volume_matches_regions(self):
        d, items, jobs = self.tile()
        regions = [(j, export.layer_region(items, j.layer, j.fill_closed,
            d.err)) for j in jobs]
        want = sorted(r.Area() * (b - a) for _, r, a, b in
            export.stack(regions))
        buf = io.BytesIO()
        export.export(d.board, items, jobs, buf, "tile")
        got = sorted(mesh.volume6(m) / 6.0 for _, _, m in
            read_3mf(buf.getvalue()))
        for g, w in zip(got, want):
            self.assertAlmostEqual(g / w, 1, places=6)

    def test_x3_nothing_to_export(self):
        d = Drawing()
        items = [d.line(DWGS, 0, 0, 1, 0, 0.2)]
        with self.assertRaises(export.ExportError):
            export.export(d.board, items, [job("F.Silkscreen", 1)],
                io.BytesIO(), "t")


if __name__ == "__main__":
    unittest.main()
