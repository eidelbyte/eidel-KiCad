"""The remembered choices and what the dialog's values ask for. Run with
KiCad's Python. Cells S1-S6 in MATRIX.md."""

import json
import os
import sys
import unittest

import pcbnew

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from roundtogrid import plugin  # noqa: E402

DEFAULTS = {"positions": (True, 0.25), "thickness": (True, 0.25)}
FINE = {"positions": (True, 0.1), "thickness": (False, 0.05)}
COARSE = {"positions": (True, 1.0), "thickness": (True, 0.5)}


def as_json(steps):
    """A row of steps as the settings file holds it."""
    return {k: list(v) for k, v in steps.items()}


class TestSettings(unittest.TestCase):

    def setUp(self):
        self.board = pcbnew.BOARD()
        self.board.SetLayerName(pcbnew.User_1, "Ink")

    def test_s1_no_file_or_broken(self):
        first = {"all_layers": True, "all": DEFAULTS, "layers": {}}
        for data in ({}, [], "x", None, {"positions": "x", "layers": 3,
                "all_layers": "no"}):
            self.assertEqual(plugin.parse(data), first)

    def test_s2_file_from_before_layers(self):
        got = plugin.parse({"positions": [True, 0.1],
            "thickness": [False, 0.05]})
        self.assertEqual(got, {"all_layers": True, "all": FINE, "layers": {}})

    def test_s3_layer_rows_from_standard_names(self):
        saved = plugin.parse({"all_layers": False,
            "positions": [True, 0.1], "thickness": [False, 0.05],
            "layers": {"F.Cu": as_json(COARSE),
                "User.1": as_json(DEFAULTS)}})
        got = plugin.choices(self.board,
            [pcbnew.F_Cu, pcbnew.User_1, pcbnew.Edge_Cuts], saved)
        self.assertEqual(got, {"all_layers": False, "all": FINE,
            "layers": {pcbnew.F_Cu: COARSE, pcbnew.User_1: DEFAULTS,
                pcbnew.Edge_Cuts: FINE}})

    def test_s4_broken_layer_entry(self):
        saved = plugin.parse({"positions": [True, 0.1],
            "thickness": [False, 0.05],
            "layers": {"F.Cu": {"positions": "x", "thickness": [True, -1]},
                "B.Cu": 7}})
        self.assertEqual(saved["layers"], {"F.Cu": FINE})
        got = plugin.choices(self.board, [pcbnew.F_Cu, pcbnew.B_Cu], saved)
        self.assertEqual(got["layers"], {pcbnew.F_Cu: FINE,
            pcbnew.B_Cu: FINE})

    def test_s5_save_keeps_other_layers_and_round_trips(self):
        saved = plugin.parse({"layers": {"B.Mask": as_json(FINE)}})
        values = {"all_layers": False, "all": COARSE,
            "layers": {pcbnew.F_Cu: FINE, pcbnew.User_1: COARSE}}
        got = plugin.remember(self.board, saved, values)
        self.assertEqual(got, {"all_layers": False, "all": COARSE,
            "layers": {"B.Mask": FINE, "F.Cu": FINE, "User.1": COARSE}})
        self.assertEqual(plugin.parse(json.loads(json.dumps(
            plugin.dump(got)))), got)

    def test_s6_plan_all_layers(self):
        layers = [pcbnew.F_Cu, pcbnew.User_1]
        steps, rows = plugin.plan(self.board, layers, {"all_layers": True,
            "all": FINE, "layers": {n: COARSE for n in layers}})
        self.assertEqual(steps, {n: (100000, None) for n in layers})
        self.assertEqual(rows, [("All layers", 0.1, None)])

    def test_s6_plan_per_layer(self):
        layers = [pcbnew.F_Cu, pcbnew.User_1]
        off = {"positions": (False, 1.0), "thickness": (False, 1.0)}
        steps, rows = plugin.plan(self.board, layers, {"all_layers": False,
            "all": FINE, "layers": {pcbnew.F_Cu: COARSE,
                pcbnew.User_1: off}})
        self.assertEqual(steps, {pcbnew.F_Cu: (1000000, 500000),
            pcbnew.User_1: (None, None)})
        self.assertEqual(rows, [("F.Cu", 1.0, 0.5), ("Ink", None, None)])


if __name__ == "__main__":
    unittest.main()
