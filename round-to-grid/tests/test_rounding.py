"""Rounding real KiCad items on in-memory boards. Run with KiCad's
Python. Cells K1-K19 and L1-L6 in MATRIX.md."""

import math
import os
import sys
import unittest

import pcbnew

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from roundtogrid import rounding  # noqa: E402

MM = 1000000
STEP = 250000
SILK = pcbnew.F_SilkS


def v(x, y):
    return pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))


def xy(p):
    return (p.x, p.y)


def on_grid(p, origin=(0, 0)):
    return (p.x - origin[0]) % STEP == 0 and (p.y - origin[1]) % STEP == 0


class Case(unittest.TestCase):

    def setUp(self):
        self.board = pcbnew.BOARD()

    def shape(self, kind, w=0.3, layer=SILK):
        s = pcbnew.PCB_SHAPE(self.board, kind)
        s.SetWidth(int(round(w * MM)))
        s.SetLayer(layer)
        self.board.Add(s)
        return s

    def line(self, x0, y0, x1, y1, w=0.3):
        s = self.shape(pcbnew.SHAPE_T_SEGMENT, w)
        s.SetStart(v(x0, y0))
        s.SetEnd(v(x1, y1))
        return s

    def arc(self, cx, cy, r, a0, a1, w=0.3):
        pts = [v(cx + r * math.cos(math.radians(a)),
            cy + r * math.sin(math.radians(a)))
            for a in (a0, (a0 + a1) / 2.0, a1)]
        s = self.shape(pcbnew.SHAPE_T_ARC, w)
        s.SetArcGeometry(*pts)
        return s

    def run_round(self, items, position=STEP, thickness=STEP):
        """Round items on the same steps on every layer."""
        layers = rounding.layers(rounding.flatten(items))
        return rounding.round_items(self.board, items,
            {n: (position, thickness) for n in layers})

    def on_board(self, item):
        uuid = item.m_Uuid.AsString()
        pools = [self.board.GetDrawings(), self.board.GetTracks(),
            self.board.Zones()]
        for fp in self.board.GetFootprints():
            pools.append(fp.GraphicalItems())
        return any(i.m_Uuid.AsString() == uuid for p in pools for i in p)


class TestShapes(Case):

    def test_k1_segment(self):
        s = self.line(0.1, 0.12, 5.13, 2.4, 0.33)
        r = self.run_round([s])
        self.assertEqual((xy(s.GetStart()), xy(s.GetEnd()), s.GetWidth()),
            ((0, 0), (5250000, 2500000), 250000))
        self.assertEqual(r.changed, 1)

    def test_k1_zero_length_and_thin_lines_deleted(self):
        short = self.line(1.0, 1.0, 1.05, 1.0)
        thin = self.line(0, 0, 5, 0, 0.001)
        r = self.run_round([short, thin])
        self.assertFalse(self.on_board(short))
        self.assertFalse(self.on_board(thin))
        self.assertEqual(dict(r.deleted), {"length": 1, "thickness": 1})

    def test_k1_hairline_stays(self):
        s = self.line(0, 0, 5, 0, 0)
        self.run_round([s])
        self.assertTrue(self.on_board(s))
        self.assertEqual(s.GetWidth(), 0)

    def test_k2_rectangle_corners_and_radius(self):
        s = self.shape(pcbnew.SHAPE_T_RECTANGLE)
        s.SetStart(v(0.1, 0.1))
        s.SetEnd(v(2.4, 5.1))
        s.SetCornerRadius(int(1.15 * MM))
        self.run_round([s])
        self.assertEqual((xy(s.GetStart()), xy(s.GetEnd())),
            ((0, 0), (2500000, 5000000)))
        # 1.15 rounds to 1.25, the most a 2.5 mm side allows.
        self.assertEqual(s.GetCornerRadius(), 1250000)

    def test_k2_corner_radius_clamped(self):
        s = self.shape(pcbnew.SHAPE_T_RECTANGLE)
        s.SetStart(v(0, 0))
        s.SetEnd(v(2.3, 5))
        s.SetCornerRadius(int(1.15 * MM))
        self.run_round([s])
        self.assertEqual(s.GetEnd().x, 2250000)
        self.assertEqual(s.GetCornerRadius(), 1000000)

    def test_k2_flat_rectangle_deleted_filled_border_kept(self):
        flat = self.shape(pcbnew.SHAPE_T_RECTANGLE)
        flat.SetStart(v(0, 0))
        flat.SetEnd(v(5, 0.1))
        filled = self.shape(pcbnew.SHAPE_T_RECTANGLE, 0.1)
        filled.SetStart(v(0, 1))
        filled.SetEnd(v(5, 3))
        filled.SetFilled(True)
        r = self.run_round([flat, filled])
        self.assertFalse(self.on_board(flat))
        self.assertTrue(self.on_board(filled))
        self.assertEqual(filled.GetWidth(), 0)
        self.assertEqual(dict(r.deleted), {"side": 1})

    def test_k3_circle(self):
        c = self.shape(pcbnew.SHAPE_T_CIRCLE)
        c.SetCenter(v(5.1, 5.1))
        c.SetRadius(int(2.1 * MM))
        tiny = self.shape(pcbnew.SHAPE_T_CIRCLE)
        tiny.SetCenter(v(1, 1))
        tiny.SetRadius(int(0.1 * MM))
        self.run_round([c, tiny])
        self.assertEqual((xy(c.GetCenter()), c.GetRadius()),
            ((5000000, 5000000), 2000000))
        self.assertFalse(self.on_board(tiny))

    def test_k4_arc(self):
        a = self.arc(3.1, 2.07, 1.93, 10, 100)
        self.run_round([a])
        self.assertTrue(on_grid(a.GetStart()) and on_grid(a.GetEnd()))
        self.assertLess(abs(a.GetRadius() - 2000000), 100)
        for p in (a.GetStart(), a.GetEnd(), a.GetArcMid()):
            d = math.hypot(p.x - a.GetCenter().x, p.y - a.GetCenter().y)
            self.assertLess(abs(d - a.GetRadius()), 100)

    def test_k5_outline_chain_stays_connected(self):
        # A rounded rectangle drawn slightly off the grid.
        x0, y0, x1, y1, r = 0.04, 0.03, 12.06, 11.97, 1.02
        items = [self.line(x0 + r, y0, x1 - r, y0),
            self.arc(x1 - r, y0 + r, r, 270, 360),
            self.line(x1, y0 + r, x1, y1 - r),
            self.arc(x1 - r, y1 - r, r, 0, 90),
            self.line(x1 - r, y1, x0 + r, y1),
            self.arc(x0 + r, y1 - r, r, 90, 180),
            self.line(x0, y1 - r, x0, y0 + r),
            self.arc(x0 + r, y0 + r, r, 180, 270)]
        ends = [(xy(i.GetStart()), xy(i.GetEnd())) for i in items]
        self.run_round(items)
        got = [(xy(i.GetStart()), xy(i.GetEnd())) for i in items]
        # Every point that two items shared, they still share.
        before = {}
        for k, (s, e) in enumerate(ends):
            before.setdefault(s, []).append((k, 0))
            before.setdefault(e, []).append((k, 1))
        self.assertEqual(sorted(len(u) for u in before.values()), [2] * 8)
        for users in before.values():
            self.assertEqual(len({got[k][end] for k, end in users}), 1)
        for i in items[1::2]:
            self.assertLess(abs(i.GetRadius() - MM), 100)

    def test_k6_polygon(self):
        s = self.shape(pcbnew.SHAPE_T_POLY)
        s.SetPolyPoints([v(0.1, 0), v(3.1, 0.05), v(3.1, 2.1), v(3.05, 2.1)])
        self.run_round([s])
        pts = s.GetPolyShape().Outline(0).CPoints()
        self.assertEqual([xy(p) for p in pts],
            [(0, 0), (3000000, 0), (3000000, 2000000)])

    def test_k6_collapsed_polygon_deleted(self):
        s = self.shape(pcbnew.SHAPE_T_POLY)
        s.SetPolyPoints([v(0, 0), v(0.1, 0), v(0.1, 0.1)])
        r = self.run_round([s])
        self.assertFalse(self.on_board(s))
        self.assertEqual(dict(r.deleted), {"area": 1})

    def test_k7_bezier(self):
        s = self.shape(pcbnew.SHAPE_T_BEZIER)
        s.SetStart(v(0.1, 0))
        s.SetBezierC1(v(1.1, 2.1))
        s.SetBezierC2(v(2.9, 2.1))
        s.SetEnd(v(4.1, 0))
        s.RebuildBezierToSegmentsPointsList(MM // 200)
        self.run_round([s])
        self.assertEqual([xy(p) for p in (s.GetStart(), s.GetBezierC1(),
            s.GetBezierC2(), s.GetEnd())], [(0, 0), (1000000, 2000000),
            (3000000, 2000000), (4000000, 0)])


class TestText(Case):

    def text(self, x, y, size, thick, parent=None):
        t = pcbnew.PCB_TEXT(parent or self.board)
        t.SetText("AB")
        t.SetLayer(SILK)
        t.SetPosition(v(x, y))
        t.SetTextSize(v(size, size))
        t.SetTextThickness(int(round(thick * MM)))
        (parent or self.board).Add(t)
        return t

    def test_k8_text_position_size_thickness(self):
        t = self.text(1.1, 1.13, 1.1, 0.15)
        self.run_round([t])
        self.assertEqual((xy(t.GetPosition()), xy(t.GetTextSize()),
            t.GetTextThickness()), ((1000000, 1250000), (1000000, 1000000),
            250000))

    def test_k8_tiny_text_deleted(self):
        t = self.text(1, 1, 0.1, 0.02)
        r = self.run_round([t])
        self.assertFalse(self.on_board(t))
        self.assertEqual(sum(r.deleted.values()), 1)

    def test_k8_footprint_field_is_never_deleted(self):
        fp = pcbnew.FOOTPRINT(self.board)
        self.board.Add(fp)
        ref = fp.Reference()
        ref.SetTextSize(v(0.1, 0.1))
        r = self.run_round([ref])
        self.assertEqual(dict(r.skipped), {"footprint field": 1})
        self.assertEqual(fp.Reference().GetTextSize().x, 100000)

    def test_k9_textbox_border_switches_off(self):
        tb = pcbnew.PCB_TEXTBOX(self.board)
        tb.SetLayer(SILK)
        tb.SetStart(v(0.1, 0.1))
        tb.SetEnd(v(10.1, 5.1))
        tb.SetText("X")
        tb.SetTextSize(v(1, 1))
        tb.SetTextThickness(int(0.25 * MM))
        tb.SetBorderWidth(int(0.1 * MM))
        self.board.Add(tb)
        self.run_round([tb])
        self.assertEqual((xy(tb.GetStart()), xy(tb.GetEnd())),
            ((0, 0), (10000000, 5000000)))
        self.assertFalse(tb.IsBorderEnabled())


class TestCopper(Case):

    def test_k10_track_and_track_arc(self):
        t = pcbnew.PCB_TRACK(self.board)
        t.SetStart(v(0.1, 0))
        t.SetEnd(v(5.1, 0.1))
        t.SetWidth(int(0.2 * MM))
        self.board.Add(t)
        a = pcbnew.PCB_ARC(self.board)
        a.SetStart(v(0.1, 0))
        a.SetMid(v(1.1, 1.05))
        a.SetEnd(v(2.1, 0))
        a.SetWidth(int(0.3 * MM))
        self.board.Add(a)
        self.run_round([t, a])
        self.assertEqual((xy(t.GetStart()), xy(t.GetEnd()), t.GetWidth()),
            ((0, 0), (5000000, 0), 250000))
        self.assertTrue(on_grid(a.GetStart()) and on_grid(a.GetEnd()))
        self.assertEqual(a.GetWidth(), 250000)

    def test_k10_via_and_thin_track(self):
        via = pcbnew.PCB_VIA(self.board)
        via.SetPosition(v(3.1, 3.1))
        via.SetWidth(int(0.6 * MM))
        via.SetDrill(int(0.3 * MM))
        self.board.Add(via)
        small = pcbnew.PCB_VIA(self.board)
        small.SetPosition(v(5, 5))
        small.SetWidth(int(0.6 * MM))
        small.SetDrill(int(0.1 * MM))
        self.board.Add(small)
        thin = pcbnew.PCB_TRACK(self.board)
        thin.SetStart(v(0, 0))
        thin.SetEnd(v(5, 0))
        thin.SetWidth(int(0.1 * MM))
        self.board.Add(thin)
        r = self.run_round([via, small, thin])
        self.assertEqual((xy(via.GetPosition()), via.GetWidth(pcbnew.F_Cu),
            via.GetDrill()), ((3000000, 3000000), 500000, 250000))
        self.assertFalse(self.on_board(small))
        self.assertFalse(self.on_board(thin))
        self.assertEqual(dict(r.deleted), {"drill": 1, "width": 1})

    def test_k11_zone(self):
        z = pcbnew.ZONE(self.board)
        z.SetLayer(pcbnew.F_Cu)
        c = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in ((0.1, 0), (5.1, 0.1), (5.1, 5.1)):
            c.Append(int(x * MM), int(y * MM))
        c.SetClosed(True)
        z.Outline().AddOutline(c)
        self.board.Add(z)
        r = self.run_round([z])
        self.assertEqual([xy(p) for p in z.Outline().Outline(0).CPoints()],
            [(0, 0), (5000000, 0), (5000000, 5000000)])
        self.assertEqual(r.unfilled, 1)

    def test_k12_footprint_moves_by_anchor(self):
        fp = pcbnew.FOOTPRINT(self.board)
        self.board.Add(fp)
        fp.SetPosition(v(20.1, 20.1))
        s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(v(20.13, 20.1))
        s.SetEnd(v(21.13, 20.1))
        s.SetWidth(int(0.12 * MM))
        fp.Add(s)
        self.run_round([fp])
        self.assertEqual(xy(fp.GetPosition()), (20000000, 20000000))
        # The inside moved with the anchor and kept its shape.
        self.assertEqual((xy(s.GetStart()), xy(s.GetEnd()), s.GetWidth()),
            ((20030000, 20000000), (21030000, 20000000), 120000))


class TestSelection(Case):

    def test_k13_locked_items_and_others_left_alone(self):
        s = self.line(0.1, 0.1, 5.1, 0.1)
        s.SetLocked(True)
        dim = pcbnew.PCB_DIM_ALIGNED(self.board, pcbnew.PCB_DIM_ALIGNED_T)
        self.board.Add(dim)
        r = self.run_round([s, dim])
        self.assertEqual(xy(s.GetStart()), (100000, 100000))
        self.assertEqual(dict(r.skipped), {"locked": 1, "dimension": 1})

    def test_k13_groups_open_and_lose_deleted_members(self):
        keep = self.line(0.1, 0.1, 5.1, 0.1)
        gone = self.line(0, 1, 0.05, 1)
        g = pcbnew.PCB_GROUP(self.board)
        self.board.Add(g)
        g.AddItem(keep)
        g.AddItem(gone)
        self.run_round([g])
        self.assertEqual(xy(keep.GetStart()), (0, 0))
        self.assertEqual([i.m_Uuid.AsString() for i in g.GetItems()],
            [keep.m_Uuid.AsString()])

    def test_k14_grid_origin(self):
        self.board.GetDesignSettings().SetGridOrigin(v(0.1, 0.05))
        s = self.line(0.2, 0.2, 5.3, 0.1)
        self.run_round([s])
        self.assertEqual((xy(s.GetStart()), xy(s.GetEnd())),
            ((100000, 300000), (5350000, 50000)))


class TestOptions(Case):

    def zone(self, pts):
        z = pcbnew.ZONE(self.board)
        z.SetLayer(pcbnew.F_Cu)
        c = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in pts:
            c.Append(int(round(x * MM)), int(round(y * MM)))
        c.SetClosed(True)
        z.Outline().AddOutline(c)
        self.board.Add(z)
        return z

    def test_k15_positions_only(self):
        s = self.line(0.1, 0.1, 5.1, 0.1, 0.33)
        thin = self.line(0, 1, 5, 1, 0.001)
        r = self.run_round([s, thin], thickness=None)
        self.assertEqual((xy(s.GetStart()), xy(s.GetEnd()), s.GetWidth()),
            ((0, 0), (5000000, 0), 330000))
        self.assertTrue(self.on_board(thin))
        self.assertEqual((r.changed, r.unchanged, dict(r.deleted)),
            (1, 1, {}))
        self.assertEqual(r.lines([("All layers", 0.25, None)])[0],
            "All layers: positions and sizes to 0.25 mm.")

    def test_k16_thickness_only(self):
        s = self.line(0.1, 0.1, 5.1, 0.1, 0.33)
        short = self.line(1, 2, 1.05, 2, 0.25)
        z = self.zone(((0.1, 0), (5.1, 0.1), (5.1, 5.1)))
        r = self.run_round([s, short, z], position=None)
        self.assertEqual((xy(s.GetStart()), xy(s.GetEnd()), s.GetWidth()),
            ((100000, 100000), (5100000, 100000), 250000))
        self.assertTrue(self.on_board(short))
        self.assertEqual(xy(z.Outline().Outline(0).CPoint(0)), (100000, 0))
        self.assertEqual((r.changed, r.unchanged, r.unfilled), (1, 2, 0))

    def test_k17_separate_steps(self):
        s = self.line(0.1, 0.1, 5.1, 0.1, 0.33)
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText("A")
        t.SetPosition(v(1.1, 1.1))
        t.SetTextSize(v(1.1, 1.1))
        t.SetTextThickness(int(0.17 * MM))
        self.board.Add(t)
        self.run_round([s, t], STEP, 50000)
        self.assertEqual((xy(s.GetEnd()), s.GetWidth()), ((5000000, 0),
            350000))
        self.assertEqual((xy(t.GetPosition()), t.GetTextSize().x,
            t.GetTextThickness()), ((1000000, 1000000), 1000000, 150000))

    def test_k18_on_grid_items_are_unchanged(self):
        s = self.line(0, 0, 5, 0, 0.25)
        z = self.zone(((0, 0), (5, 0), (5, 5)))
        r = self.run_round([s, z])
        self.assertEqual((r.changed, r.unchanged, r.unfilled), (0, 2, 0))
        self.assertEqual(r.lines([("All layers", 0.25, 0.25)])[1],
            "Changed 0 item(s); 2 already on the grid.")

    def test_k19_zero_rounding_did_not_make_stays(self):
        dot = self.line(1, 1, 1, 1, 0.5)
        r = self.run_round([dot])
        self.assertTrue(self.on_board(dot))
        self.assertEqual(dict(r.deleted), {})


class TestLayers(Case):

    def on(self, layer, s):
        s.SetLayer(layer)
        return s

    def track(self, layer, a, b, w=0.2):
        t = pcbnew.PCB_TRACK(self.board)
        t.SetLayer(layer)
        t.SetStart(v(*a))
        t.SetEnd(v(*b))
        t.SetWidth(int(round(w * MM)))
        self.board.Add(t)
        return t

    def zone(self, *layers):
        z = pcbnew.ZONE(self.board)
        ls = pcbnew.LSET()
        for n in layers:
            ls.AddLayer(n)
        z.SetLayerSet(ls)
        self.board.Add(z)
        return z

    def test_l1_item_layers(self):
        edge = self.on(pcbnew.Edge_Cuts, self.line(0, 0, 1, 0))
        track = self.track(pcbnew.B_Cu, (0, 0), (1, 0))
        via = pcbnew.PCB_VIA(self.board)
        self.board.Add(via)
        fp = pcbnew.FOOTPRINT(self.board)
        self.board.Add(fp)
        smd = pcbnew.PAD(fp)
        smd.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        smd.SetLayerSet(smd.SMDMask())
        fp.Add(smd)
        through = pcbnew.PAD(fp)
        fp.Add(through)
        fp.SetLayerAndFlip(pcbnew.B_Cu)
        got = [rounding.layer(i) for i in (edge, track, via, fp, smd,
            through, self.zone(pcbnew.F_Cu),
            self.zone(pcbnew.F_Cu, pcbnew.B_Cu),
            self.zone(pcbnew.B_Cu, pcbnew.In1_Cu))]
        self.assertEqual(got, [pcbnew.Edge_Cuts, pcbnew.B_Cu, pcbnew.F_Cu,
            pcbnew.B_Cu, pcbnew.B_Cu, pcbnew.F_Cu, pcbnew.F_Cu, pcbnew.F_Cu,
            pcbnew.In1_Cu])

    def test_l2_layers_once_in_kicad_order(self):
        items = [self.on(n, self.line(0, 0, 1, 0)) for n in (pcbnew.Edge_Cuts,
            pcbnew.B_Cu, pcbnew.F_SilkS, pcbnew.F_Cu, pcbnew.In1_Cu,
            pcbnew.F_Cu)]
        self.assertEqual(rounding.layers(items), [pcbnew.F_Cu, pcbnew.In1_Cu,
            pcbnew.B_Cu, pcbnew.F_SilkS, pcbnew.Edge_Cuts])

    def test_l3_each_layer_on_its_own_steps(self):
        silk = self.line(0.1, 0.12, 5.13, 2.4, 0.33)
        edge = self.on(pcbnew.Edge_Cuts, self.line(0.1, 0.12, 5.13, 2.4, 0.33))
        rounding.round_items(self.board, [silk, edge],
            {SILK: (STEP, 50000), pcbnew.Edge_Cuts: (MM, None)})
        self.assertEqual((xy(silk.GetStart()), xy(silk.GetEnd()),
            silk.GetWidth()), ((0, 0), (5250000, 2500000), 350000))
        self.assertEqual((xy(edge.GetStart()), xy(edge.GetEnd()),
            edge.GetWidth()), ((0, 0), (5000000, 2000000), 330000))

    def test_l4_layer_left_alone_and_thickness_only(self):
        silk = self.line(0.1, 0.1, 5.1, 0.1, 0.33)
        locked = self.line(0.1, 1.1, 5.1, 1.1, 0.33)
        locked.SetLocked(True)
        edge = self.on(pcbnew.Edge_Cuts, self.line(0.1, 0.1, 5.1, 0.1, 0.33))
        r = rounding.round_items(self.board, [silk, locked, edge],
            {SILK: (None, None), pcbnew.Edge_Cuts: (None, STEP)})
        self.assertEqual((xy(silk.GetStart()), silk.GetWidth()),
            ((100000, 100000), 330000))
        self.assertEqual((xy(edge.GetStart()), edge.GetWidth()),
            ((100000, 100000), 250000))
        self.assertEqual((r.changed, dict(r.skipped)),
            (1, {"on a layer left alone": 1, "locked": 1}))

    def joint(self):
        """A track on each copper side meeting at a via, off the grid."""
        top = self.track(pcbnew.F_Cu, (0, 0), (2.12, 0.12))
        via = pcbnew.PCB_VIA(self.board)
        via.SetPosition(v(2.12, 0.12))
        via.SetWidth(int(0.6 * MM))
        via.SetDrill(int(0.3 * MM))
        self.board.Add(via)
        bottom = self.track(pcbnew.B_Cu, (2.12, 0.12), (5, 0))
        return top, via, bottom

    def test_l5_joined_on_equal_steps(self):
        top, via, bottom = self.joint()
        rounding.round_items(self.board, [top, via, bottom],
            {pcbnew.F_Cu: (STEP, None), pcbnew.B_Cu: (STEP, None)})
        self.assertEqual({xy(top.GetEnd()), xy(via.GetPosition()),
            xy(bottom.GetStart())}, {(2000000, 0)})

    def test_l5_parted_on_unequal_steps(self):
        top, via, bottom = self.joint()
        rounding.round_items(self.board, [top, via, bottom],
            {pcbnew.F_Cu: (STEP, None), pcbnew.B_Cu: (100000, None)})
        # The via rounds with its top layer; the bottom track leaves it.
        self.assertEqual((xy(top.GetEnd()), xy(via.GetPosition()),
            xy(bottom.GetStart())), ((2000000, 0), (2000000, 0),
            (2100000, 100000)))

    def test_l6_summary_all_layers(self):
        s = self.line(0.1, 0.1, 5.1, 0.1)
        gone = self.line(0, 0, 5, 0, 0.001)
        r = self.run_round([s, gone])
        self.assertEqual(r.lines([("All layers", 0.25, 0.25)]), [
            "All layers: positions and sizes to 0.25 mm and thickness to "
            "0.25 mm.",
            "Changed 1 item(s).",
            "Deleted 1 item(s) that rounded to zero: 1 thickness."])

    def test_l6_summary_per_layer(self):
        silk = self.line(0.1, 0.1, 5.1, 0.1)
        edge = self.on(pcbnew.Edge_Cuts, self.line(0.1, 0.1, 5.1, 0.1))
        r = rounding.round_items(self.board, [silk, edge],
            {SILK: (STEP, 100000), pcbnew.Edge_Cuts: (None, None)})
        self.assertEqual(r.lines([("F.Silkscreen", 0.25, 0.1),
            ("Edge.Cuts", None, None)]), [
            "F.Silkscreen: positions and sizes to 0.25 mm and thickness to "
            "0.1 mm.",
            "Edge.Cuts: left alone.",
            "Changed 1 item(s).",
            "Left 1 item(s) unchanged: 1 on a layer left alone."])


if __name__ == "__main__":
    unittest.main()
