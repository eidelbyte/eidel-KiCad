"""Grid math on integers; no KiCad needed. Cells Q1-Q4, A1-A7, P1-P4
in MATRIX.md."""

import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from roundtogrid import snap  # noqa: E402

MM = 1000000
STEP = 250000
O = (0, 0)


def on_grid(p, step=STEP, origin=O):
    return (p[0] - origin[0]) % step == 0 and (p[1] - origin[1]) % step == 0


def circle_through(a, m, b):
    """Centre and radius of the circle through three points."""
    ax, ay = a
    bx, by = m
    cx, cy = b
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) +
        (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) +
        (cx * cx + cy * cy) * (bx - ax)) / d
    return (ux, uy), math.hypot(ax - ux, ay - uy)


def side(a, b, p):
    c = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    return (c > 0) - (c < 0)


def arc_pts(c, r, a0, a1):
    """Start, mid, end of an arc around c from angle a0 to a1 (deg)."""
    return [(c[0] + r * math.cos(math.radians(a)),
        c[1] + r * math.sin(math.radians(a))) for a in (a0, (a0 + a1) / 2,
        a1)]


class TestNearest(unittest.TestCase):

    def test_q1_rounds_to_nearest_halves_up(self):
        self.assertEqual(snap.nearest(370000, STEP), 250000)
        self.assertEqual(snap.nearest(380000, STEP), 500000)
        self.assertEqual(snap.nearest(125000, STEP), 250000)
        self.assertEqual(snap.nearest(124999, STEP), 0)
        self.assertEqual(snap.nearest(1000, STEP), 0)
        self.assertEqual(snap.nearest(500000, STEP), 500000)

    def test_q2_negative_values_and_odd_steps(self):
        self.assertEqual(snap.nearest(-370000, STEP), -250000)
        self.assertEqual(snap.nearest(-125000, STEP), 0)
        self.assertEqual(snap.nearest(-125001, STEP), -250000)
        self.assertEqual(snap.nearest(7, 3), 6)
        self.assertEqual(snap.nearest(8, 3), 9)

    def test_q3_points_from_the_grid_origin(self):
        o = (100000, -50000)
        self.assertEqual(snap.point((370000, 0), STEP, o), (350000, -50000))
        self.assertTrue(on_grid(snap.point((123456, -987654), STEP, o),
            origin=o))

    def test_q4_at_least(self):
        self.assertEqual(snap.at_least(250000, STEP), 250000)
        self.assertEqual(snap.at_least(250001, STEP), 500000)
        self.assertEqual(snap.at_least(1, STEP), 250000)


class TestArc(unittest.TestCase):

    def check(self, start, mid, end, center, step=STEP, origin=O):
        """Ends on grid, radius a multiple of step (or just enough to
        span), centre and bulge on their old sides of the chord."""
        start, mid, end, center = [tuple(int(round(v)) for v in p)
            for p in (start, mid, end, center)]
        got = snap.arc(start, mid, end, center, step, origin)
        self.assertIsNotNone(got)
        a, m, b = got
        self.assertTrue(on_grid(a, step, origin) and on_grid(b, step, origin))
        c, r = circle_through(a, m, b)
        chord = math.hypot(b[0] - a[0], b[1] - a[1])
        # KiCad keeps an arc as three integer points, so its radius comes
        # back from them; the mid point's 1 nm rounding moves it by up to
        # radius / sagitta nm, which is large on shallow arcs.
        sag = math.hypot(m[0] - (a[0] + b[0]) / 2.0,
            m[1] - (a[1] + b[1]) / 2.0)
        tol = 2 + r / sag
        if r > chord / 2 + tol:
            self.assertLess(abs(r - round(r / step) * step), tol)
        self.assertEqual(side(a, b, m), side(start, end, mid))
        # A radius grown to just span the ends leaves the centre on the
        # chord: a semicircle has no side.
        if side(start, end, center) and r > chord / 2 + tol:
            self.assertEqual(side(a, b, c), side(start, end, center))
        return a, m, b, r

    def test_a1_on_grid_arc_is_unchanged(self):
        # A tile corner: r = 1 mm, ends on a 1 mm grid.
        s, m, e = arc_pts((10 * MM, 10 * MM), MM, 270, 360)
        a, mm, b, r = self.check(s, m, e, (10 * MM, 10 * MM))
        self.assertEqual(a, (10 * MM, 9 * MM))
        self.assertEqual(b, (11 * MM, 10 * MM))
        self.assertAlmostEqual(r, MM, delta=2)

    def test_a2_off_grid_minor_arc(self):
        c = (3.1 * MM, 2.07 * MM)
        self.check(*arc_pts(c, 1.93 * MM, 10, 100), center=c)

    def test_a3_major_arc_stays_major(self):
        c = (5.03 * MM, 5.02 * MM)
        a, m, b, r = self.check(*arc_pts(c, 2.1 * MM, 0, 270), center=c)
        cc, _ = circle_through(a, m, b)
        self.assertEqual(side(a, b, cc), side(a, b, m))

    def test_a4_semicircle(self):
        c = (5 * MM, 5 * MM)
        self.check(*arc_pts(c, 2 * MM, 0, 180), center=c)

    def test_a5_radius_grows_to_span_the_ends(self):
        # Ends round to 0.5 and 1.75 mm, 1.25 mm apart, while the radius
        # rounds to 0.5 mm; it has to grow to 0.75 mm to span them.
        c = (1.1 * MM, 0)
        a, m, b, r = self.check(*arc_pts(c, 0.6 * MM, 180, 360), center=c)
        self.assertEqual((a, b), ((500000, 0), (1750000, 0)))
        self.assertAlmostEqual(r, 750000, delta=2)

    def test_a6_collapsing_arcs(self):
        self.assertIsNone(snap.arc((0, 0), (50000, 50000), (100000, 0),
            (50000, 0), STEP, O))
        self.assertIsNone(snap.arc((0, 0), (500, 500), (1000, 0), (500, 0),
            STEP, O))

    def test_a7_random_arcs(self):
        rng = random.Random(7)
        for _ in range(300):
            c = (rng.uniform(-20, 20) * MM, rng.uniform(-20, 20) * MM)
            r = rng.uniform(0.5, 10) * MM
            a0 = rng.uniform(0, 360)
            a1 = a0 + rng.uniform(20, 340)
            s, m, e = arc_pts(c, r, a0, a1)
            self.check(s, m, e, c)


class TestRing(unittest.TestCase):

    def test_p1_points_rounded(self):
        got = snap.ring([(10000, 0), (1010000, 20000), (990000, 1000000)],
            STEP, O)
        self.assertEqual(got, [(0, 0), (1000000, 0), (1000000, 1000000)])

    def test_p2_repeated_points_dropped(self):
        got = snap.ring([(0, 0), (10000, 0), (1000000, 0), (1000000, 1000000),
            (0, 1000000), (1000, 1000)], STEP, O)
        self.assertEqual(got, [(0, 0), (1000000, 0), (1000000, 1000000),
            (0, 1000000)])

    def test_p3_collapsed_ring(self):
        self.assertIsNone(snap.ring([(0, 0), (100000, 0), (100000, 100000)],
            STEP, O))
        self.assertIsNone(snap.ring([(0, 0), (500000, 0), (1000000, 10000)],
            STEP, O))

    def test_p4_area(self):
        self.assertEqual(snap.area2([(0, 0), (2, 0), (2, 2)]), 4)


if __name__ == "__main__":
    unittest.main()
