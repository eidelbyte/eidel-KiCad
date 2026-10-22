"""The step dialog, built but not shown. Run with KiCad's Python. Cells
D1-D4 in MATRIX.md."""

import os
import sys
import unittest

import wx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from roundtogrid import dialog  # noqa: E402

FINE = {"positions": (True, 0.1), "thickness": (False, 0.05)}
COARSE = {"positions": (True, 1.0), "thickness": (True, 0.5)}
OFF = {"positions": (False, 0.25), "thickness": (False, 0.25)}
LAYERS = [(0, "F.Cu"), (25, "Edge.Cuts"), (39, "Ink")]


def click(box, on):
    """Tick or untick box as a click would, its handler included."""
    box.SetValue(on)
    e = wx.CommandEvent(wx.wxEVT_CHECKBOX, box.GetId())
    e.SetEventObject(box)
    e.SetInt(int(on))
    box.GetEventHandler().ProcessEvent(e)


class TestDialog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = wx.App(False)

    def make(self, all_layers, every=FINE, layers=None):
        layers = layers or {0: COARSE, 25: FINE, 39: OFF}
        self.dlg = dialog.StepDialog(None, "Round", LAYERS,
            {"all_layers": all_layers, "all": every, "layers": layers}, 3)
        return self.dlg

    def tearDown(self):
        self.dlg.Destroy()

    def shown_rows(self, dlg):
        rows = [dlg._every] + list(dlg._rows.values())
        return [w[0].GetLabel() for w, _ in rows if w[0].IsShown()]

    def test_d1_all_layers_row_only(self):
        dlg = self.make(True)
        self.assertEqual(self.shown_rows(dlg), ["All layers"])
        self.assertEqual(dlg.values(), {"all_layers": True, "all": FINE,
            "layers": {0: COARSE, 25: FINE, 39: OFF}})

    def test_d2_a_row_per_layer(self):
        dlg = self.make(True)
        click(dlg._all, False)
        self.assertEqual(self.shown_rows(dlg), ["F.Cu", "Edge.Cuts", "Ink"])
        use, spin = dlg._rows[39][1]["thickness"]
        click(use, True)
        spin.SetValue(0.2)
        got = dlg.values()
        self.assertFalse(got["all_layers"])
        self.assertEqual(got["layers"][39],
            {"positions": (False, 0.25), "thickness": (True, 0.2)})
        self.assertEqual(got["layers"][0], COARSE)
        click(dlg._all, True)
        self.assertEqual(self.shown_rows(dlg), ["All layers"])

    def test_d3_round_needs_a_tick_in_a_shown_row(self):
        dlg = self.make(True, every=OFF, layers={0: COARSE, 25: OFF,
            39: OFF})
        self.assertFalse(dlg.ready())
        click(dlg._all, False)
        self.assertTrue(dlg.ready())
        click(dlg._rows[0][1]["positions"][0], False)
        click(dlg._rows[0][1]["thickness"][0], False)
        self.assertFalse(dlg.ready())
        click(dlg._all, True)
        click(dlg._every[1]["thickness"][0], True)
        self.assertTrue(dlg.ready())

    def test_d4_checkbox_enables_its_step(self):
        dlg = self.make(False)
        use, spin = dlg._rows[25][1]["thickness"]
        self.assertFalse(spin.IsEnabled())
        click(use, True)
        self.assertTrue(spin.IsEnabled())
        click(use, False)
        self.assertFalse(spin.IsEnabled())


if __name__ == "__main__":
    unittest.main()
