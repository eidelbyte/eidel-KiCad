"""The KiCad action: selection -> steps -> rounded board -> report."""

import json
import os

import pcbnew
import wx

from . import dialog, rounding

MM = 1000000
SETTINGS = "roundtogrid.json"
DEFAULTS = {"positions": (True, 0.25), "thickness": (True, 0.25)}


class RoundToGridPlugin(pcbnew.ActionPlugin):

    def defaults(self):
        self.name = "Round Selection to Grid"
        self.category = "Modify"
        self.description = ("Round the selected items' positions and sizes, "
            "and their thickness, to grid steps")
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__),
            "icon.png")

    def Run(self):
        board = pcbnew.GetBoard()
        frame = wx.FindWindowByName("PcbFrame")
        items = rounding.flatten(pcbnew.GetCurrentSelection())
        if not items:
            wx.MessageBox("Select the items to round first.", self.name,
                wx.OK | wx.ICON_INFORMATION, frame)
            return

        dlg = dialog.StepDialog(frame, self.name, _load(), len(items))
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            values = dlg.values()
        finally:
            dlg.Destroy()
        _save(values)

        mm = {k: step if on else None for k, (on, step) in values.items()}
        report = rounding.round_items(board, items,
            _nm(mm["positions"]), _nm(mm["thickness"]))
        pcbnew.Refresh()
        wx.MessageBox("\n".join(report.lines(mm["positions"],
            mm["thickness"])), self.name, wx.OK | wx.ICON_INFORMATION, frame)


def _nm(step_mm):
    return int(round(step_mm * MM)) if step_mm else None


def _settings_path():
    return os.path.join(pcbnew.SETTINGS_MANAGER.GetUserSettingsPath(),
        SETTINGS)


def _load():
    """The last choices, DEFAULTS at first; a missing or broken file, or
    a broken entry in it, reads as the default."""
    try:
        with open(_settings_path()) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    out = dict(DEFAULTS)
    for key in DEFAULTS:
        try:
            on, step = data[key]
            if float(step) > 0:
                out[key] = (bool(on), float(step))
        except (KeyError, TypeError, ValueError):
            pass
    return out


def _save(values):
    try:
        with open(_settings_path(), "w") as f:
            json.dump({k: list(v) for k, v in values.items()}, f)
    except OSError:
        pass
