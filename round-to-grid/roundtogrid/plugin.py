"""The KiCad action: selection -> step -> rounded board -> report."""

import json
import os

import pcbnew
import wx

from . import dialog, rounding

MM = 1000000
SETTINGS = "roundtogrid.json"


class RoundToGridPlugin(pcbnew.ActionPlugin):

    def defaults(self):
        self.name = "Round Selection to Grid"
        self.category = "Modify"
        self.description = ("Round the selected items' points, widths, "
            "thicknesses, radii and text sizes to a grid step")
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

        dlg = dialog.StepDialog(frame, self.name, _load_step(), len(items))
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            step_mm = dlg.step_mm()
        finally:
            dlg.Destroy()
        _save_step(step_mm)

        report = rounding.round_items(board, items,
            int(round(step_mm * MM)))
        pcbnew.Refresh()
        wx.MessageBox("\n".join(report.lines(step_mm)), self.name,
            wx.OK | wx.ICON_INFORMATION, frame)


def _settings_path():
    return os.path.join(pcbnew.SETTINGS_MANAGER.GetUserSettingsPath(),
        SETTINGS)


def _load_step():
    """The last step used, 0.25 mm at first; a missing or broken file
    reads as the default."""
    try:
        with open(_settings_path()) as f:
            step = float(json.load(f)["step_mm"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0.25
    return step if step > 0 else 0.25


def _save_step(step_mm):
    try:
        with open(_settings_path(), "w") as f:
            json.dump({"step_mm": step_mm}, f)
    except OSError:
        pass
