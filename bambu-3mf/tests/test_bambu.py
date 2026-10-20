"""Slice an exported tile with the Bambu Studio command line.

Run with KiCad's Python; skipped unless Bambu Studio is installed (or
BAMBU_STUDIO names its executable). Cell B1 in MATRIX.md.

The command line takes system presets but does not resolve their
"inherits" chains, and it gives filaments no colours; with either gap it
quietly slices everything with one filament. So the filament presets are
flattened, and given a colour each, before use.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bambu3mf import export  # noqa: E402
from test_kicad import DWGS, MM, SILK, Drawing  # noqa: E402

APP = os.environ.get("BAMBU_STUDIO",
    "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio")
PROFILES = os.path.join(os.path.dirname(os.path.dirname(APP)), "Resources",
    "profiles", "BBL")
MACHINE = "Bambu Lab X1 Carbon 0.4 nozzle"
PROCESS = "0.20mm Standard @BBL X1C"
FILAMENTS = (("Bambu PLA Basic @BBL X1C", "#F2EDA1"),
    ("Bambu PLA Matte @BBL X1C", "#FFFFFF"))


def flattened(kind, name):
    with open(os.path.join(PROFILES, kind, name + ".json")) as f:
        preset = json.load(f)
    parent = preset.get("inherits")
    if parent:
        base = flattened(kind, parent)
        base.update(preset)
        preset = base
    preset["inherits"] = ""
    return preset


@unittest.skipUnless(os.path.exists(APP), "Bambu Studio not installed")
class TestBambuSlice(unittest.TestCase):

    def test_b1_inlay_slices_with_two_filaments(self):
        d = Drawing()
        items = d.rounded(SILK, 0, 0, 12, 12, 1, 0.3)
        items += d.polyline(DWGS, [(2, 2), (2, 10), (6, 10)], 0.4,
            closed=False)
        jobs = [export.Job(SILK, "F.Silkscreen", 1, True, 5 * MM, 0),
            export.Job(DWGS, "User.Drawings", 2, False, 2400000, 2600000)]
        with tempfile.TemporaryDirectory() as tmp:
            model = os.path.join(tmp, "tile.3mf")
            export.export(d.board, items, jobs, model, "tile")
            fils = []
            for n, (name, col) in enumerate(FILAMENTS):
                preset = flattened("filament", name)
                preset["filament_colour"] = [col]
                fils.append(os.path.join(tmp, "f%d.json" % n))
                with open(fils[-1], "w") as f:
                    json.dump(preset, f)
            subprocess.run([APP, "--outputdir", tmp, "--load-settings",
                ";".join(os.path.join(PROFILES, k, n + ".json")
                for k, n in (("machine", MACHINE), ("process", PROCESS))),
                "--load-filaments", ";".join(fils), "--slice", "0",
                "--export-3mf", "sliced.3mf", model],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=600)

            with open(os.path.join(tmp, "result.json")) as f:
                result = json.load(f)
            self.assertEqual(result["return_code"], 0, result)
            plate = result["sliced_plates"][0]
            used = {f["id"]: f["total_used_g"] for f in plate["filaments"]}
            self.assertEqual(sorted(used), [1, 2])
            self.assertTrue(all(g > 0 for g in used.values()), used)
            self.assertIn("Ironing", plate["feature_type_times"])

            # Filament 2 extrudes on the inlay's layers and no others. The
            # order of filaments alternates per layer, so track the active
            # one rather than the switches.
            z = 0.0
            active = 0
            heights = set()
            with open(os.path.join(tmp, "plate_1.gcode")) as f:
                for line in f:
                    if line.startswith("; Z_HEIGHT: "):
                        z = float(line.split()[2])
                    elif line.startswith("M1020 S"):
                        active = int(line.split()[1][1:])
                    elif active == 1 and line.startswith("G1 ") and \
                        any(w.startswith("E") and float(w[1:]) > 0
                        for w in line.split()[1:]):
                        heights.add(z)
            self.assertTrue(heights)
            self.assertGreater(min(heights), 2.6)
            self.assertAlmostEqual(max(heights), 5.0, places=3)

            with zipfile.ZipFile(os.path.join(tmp, "sliced.3mf")) as z3:
                cfg = ET.fromstring(z3.read("Metadata/model_settings.config"))
            meta = {m.get("key"): m.get("value")
                for m in cfg.find("object").findall("metadata")}
            for key, value in export.PRINT_SETTINGS:
                self.assertEqual(meta.get(key), value, key)


if __name__ == "__main__":
    unittest.main()
