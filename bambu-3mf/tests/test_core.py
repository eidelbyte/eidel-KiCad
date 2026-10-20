"""Triangulation, extrusion and 3MF writing; no KiCad needed.

Cells (see MATRIX.md): E1-E9 triangulation and extrusion, W1-W4 writer.
"""

import io
import math
import os
import random
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bambu3mf import mesh, threemf  # noqa: E402
from bambu3mf.earcut import earcut  # noqa: E402

MM = 1000000
NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def circle(cx, cy, r, n):
    return [(cx + int(round(r * math.cos(2 * math.pi * k / n))),
        cy + int(round(r * math.sin(2 * math.pi * k / n)))) for k in range(n)]


def reverse(ring):
    return list(reversed(ring))


class ExtrudeCase(unittest.TestCase):

    def check(self, polygons, z0=0, z1=3 * MM):
        """Area, closure and volume must all be exact."""
        for rings in polygons:
            coords = [p for r in rings for p in r]
            starts = []
            n = 0
            for r in rings[:-1]:
                n += len(r)
                starts.append(n)
            tris = earcut(coords, starts)
            got = abs(sum(mesh._cross(coords, t) for t in tris))
            self.assertEqual(got, mesh.polygon_area2(rings))
        m = mesh.Mesh()
        self.assertEqual(mesh.extrude(polygons, z0, z1, m), 0)
        self.assertEqual(mesh.unpaired_edges(m.triangles), [])
        area2 = sum(mesh.polygon_area2(r) for r in polygons)
        self.assertEqual(mesh.volume6(m), 3 * area2 * (z1 - z0))
        self.assertEqual({v[2] for v in m.vertices}, {z0, z1})
        return m


class TestExtrude(ExtrudeCase):

    def test_e1_convex(self):
        self.check([[rect(0, 0, 10 * MM, 5 * MM)]])

    def test_e1_either_winding(self):
        self.check([[reverse(rect(0, 0, 10 * MM, 5 * MM))]])

    def test_e2_concave_comb(self):
        ring = [(0, 0), (9 * MM, 0), (9 * MM, 4 * MM)]
        for k in range(4, 0, -1):
            ring += [(2 * k * MM, 4 * MM), (2 * k * MM, 1 * MM),
                ((2 * k - 1) * MM, 1 * MM), ((2 * k - 1) * MM, 4 * MM)]
        ring.append((0, 4 * MM))
        self.check([[ring]])

    def test_e3_one_hole(self):
        self.check([[rect(0, 0, 10 * MM, 10 * MM),
            reverse(rect(3 * MM, 3 * MM, 7 * MM, 7 * MM))]])

    def test_e3_hole_same_winding_as_outer(self):
        self.check([[rect(0, 0, 10 * MM, 10 * MM),
            rect(3 * MM, 3 * MM, 7 * MM, 7 * MM)]])

    def test_e4_many_holes(self):
        holes = [reverse(rect(i * 2 * MM + MM // 2, j * 2 * MM + MM // 2,
            i * 2 * MM + 3 * MM // 2, j * 2 * MM + 3 * MM // 2))
            for i in range(5) for j in range(5)]
        self.check([[rect(0, 0, 10 * MM, 10 * MM)] + holes])

    def test_e5_hole_pinched_to_outline(self):
        # The hole's corner sits exactly on the outer ring's vertex.
        outer = [(0, 0), (10 * MM, 0), (10 * MM, 10 * MM), (5 * MM, 10 * MM),
            (0, 10 * MM)]
        hole = [(5 * MM, 10 * MM), (7 * MM, 6 * MM), (3 * MM, 6 * MM)]
        self.check([[outer, hole]])

    def test_e5_holes_pinched_together(self):
        a = [(2 * MM, 2 * MM), (5 * MM, 5 * MM), (2 * MM, 8 * MM)]
        b = [(5 * MM, 5 * MM), (8 * MM, 2 * MM), (8 * MM, 8 * MM)]
        self.check([[rect(0, 0, 10 * MM, 10 * MM), a, b]])

    def test_e6_duplicate_and_collinear_points(self):
        ring = [(0, 0), (0, 0), (5 * MM, 0), (10 * MM, 0), (10 * MM, 10 * MM),
            (10 * MM, 10 * MM), (0, 10 * MM), (0, 5 * MM)]
        self.check([[ring]])

    def test_e7_circle_below_hash_threshold(self):
        self.check([[circle(0, 0, 5 * MM, 40)]])

    def test_e7_circle_with_holes_hashed(self):
        self.check([[circle(0, 0, 20 * MM, 400),
            circle(-8 * MM, 0, 4 * MM, 120), circle(8 * MM, 0, 4 * MM, 120),
            circle(0, 9 * MM, 3 * MM, 90)]])

    def test_e8_disjoint_polygons_one_call(self):
        m = self.check([[rect(0, 0, MM, MM)], [rect(2 * MM, 0, 3 * MM, MM)]])
        self.assertEqual(len(m.vertices), 16)

    def test_e8_negative_and_offset_z(self):
        self.check([[rect(-5 * MM, -5 * MM, 5 * MM, 5 * MM)]],
            -2 * MM, 500000)

    def test_e9_random_polygons_with_holes(self):
        rng = random.Random(1234)
        for _ in range(60):
            # n >= 4 keeps every edge over 13 mm from the centre, clear
            # of the holes, which reach out to 11 mm.
            n = rng.randint(4, 160)
            outer = []
            for k in range(n):
                a = 2 * math.pi * k / n
                r = rng.uniform(15, 30) * MM
                outer.append((int(r * math.cos(a)), int(r * math.sin(a))))
            holes = []
            for h in range(rng.randint(0, 4)):
                a = 2 * math.pi * h / 4 + rng.uniform(-0.3, 0.3)
                cx = int(8 * MM * math.cos(a))
                cy = int(8 * MM * math.sin(a))
                # Centres are at least 7.46 mm apart, so r <= 3 mm
                # keeps the holes disjoint.
                holes.append(circle(cx, cy, rng.uniform(1, 3) * MM,
                    rng.randint(3, 60)))
            self.check([[outer] + holes])


class TestWriter(unittest.TestCase):

    def test_w1_mm_is_exact(self):
        self.assertEqual(threemf.mm(0), "0")
        self.assertEqual(threemf.mm(1), "0.000001")
        self.assertEqual(threemf.mm(-1500000), "-1.5")
        self.assertEqual(threemf.mm(123456789), "123.456789")
        self.assertEqual(threemf.mm(-7 * MM), "-7")

    def build(self):
        a = mesh.Mesh()
        mesh.extrude([[rect(0, 0, 10 * MM, 10 * MM)]], 0, 5 * MM, a)
        b = mesh.Mesh()
        mesh.extrude([[rect(2 * MM, 2 * MM, 3 * MM, 8 * MM)]], 5 * MM,
            6 * MM, b)
        parts = [threemf.Part('Tile & "base"', 3, a),
            threemf.Part("Lines", 1, b)]
        buf = io.BytesIO()
        threemf.write(buf, "Ur <10>", parts, (("top_shell_layers", "7"),
            ("ironing_type", "top")))
        return parts, zipfile.ZipFile(io.BytesIO(buf.getvalue()))

    def test_w2_package_layout(self):
        _, z = self.build()
        self.assertEqual(sorted(z.namelist()), ["3D/3dmodel.model",
            "Metadata/model_settings.config", "[Content_Types].xml",
            "_rels/.rels"])
        rels = ET.fromstring(z.read("_rels/.rels"))
        self.assertEqual(rels[0].get("Target"), "/3D/3dmodel.model")

    def test_w3_model_round_trip(self):
        parts, z = self.build()
        root = ET.fromstring(z.read("3D/3dmodel.model"))
        objs = root.findall("m:resources/m:object", NS)
        self.assertEqual([o.get("id") for o in objs], ["1", "2", "3"])
        for part, obj in zip(parts, objs):
            self.assertEqual(obj.get("name"), part.name)
            verts = obj.findall("m:mesh/m:vertices/m:vertex", NS)
            got = [tuple(int(round(float(v.get(k)) * MM)) for k in "xyz")
                for v in verts]
            self.assertEqual(got, part.mesh.vertices)
            tris = obj.findall("m:mesh/m:triangles/m:triangle", NS)
            self.assertEqual([tuple(int(t.get(k)) for k in ("v1", "v2", "v3"))
                for t in tris], part.mesh.triangles)
        comps = objs[2].findall("m:components/m:component", NS)
        self.assertEqual([c.get("objectid") for c in comps], ["1", "2"])
        item = root.find("m:build/m:item", NS)
        self.assertEqual(item.get("objectid"), "3")
        self.assertEqual(objs[2].get("name"), "Ur <10>")

    def test_w4_filaments_per_part(self):
        _, z = self.build()
        cfg = ET.fromstring(z.read("Metadata/model_settings.config"))
        obj = cfg.find("object")
        self.assertEqual(obj.get("id"), "3")
        meta = {m.get("key"): m.get("value") for m in obj.findall("metadata")}
        self.assertEqual(meta, {"name": "Ur <10>", "extruder": "3",
            "top_shell_layers": "7", "ironing_type": "top"})
        got = []
        for p in obj.findall("part"):
            md = {m.get("key"): m.get("value") for m in p.findall("metadata")}
            got.append((p.get("id"), p.get("subtype"), md["name"],
                md["extruder"]))
        self.assertEqual(got, [("1", "normal_part", 'Tile & "base"', "3"),
            ("2", "normal_part", "Lines", "1")])


if __name__ == "__main__":
    unittest.main()
