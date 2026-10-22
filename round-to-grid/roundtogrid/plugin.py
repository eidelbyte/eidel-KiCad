"""The KiCad action: selection -> steps per layer -> rounded board ->
report."""

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
            "and their thickness, to grid steps, for all layers or per layer")
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

        layers = rounding.layers(items)
        saved = _load()
        dlg = dialog.StepDialog(frame, self.name,
            [(n, board.GetLayerName(n)) for n in layers],
            choices(board, layers, saved), len(items))
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            values = dlg.values()
        finally:
            dlg.Destroy()
        _save(remember(board, saved, values))

        steps, rows = plan(board, layers, values)
        report = rounding.round_items(board, items, steps)
        pcbnew.Refresh()
        wx.MessageBox("\n".join(report.lines(rows)), self.name,
            wx.OK | wx.ICON_INFORMATION, frame)


def choices(board, layers, saved):
    """The dialog's values: what was saved, each layer's row from what was
    remembered under its standard name, or else the all-layers row."""
    return {"all_layers": saved["all_layers"], "all": saved["all"],
        "layers": {n: saved["layers"].get(board.GetStandardLayerName(n),
            saved["all"]) for n in layers}}


def remember(board, saved, values):
    """saved with the dialog's values taken in; layers not in the dialog
    keep what they had."""
    out = {"all_layers": values["all_layers"], "all": values["all"],
        "layers": dict(saved["layers"])}
    for n, steps in values["layers"].items():
        out["layers"][board.GetStandardLayerName(n)] = steps
    return out


def plan(board, layers, values):
    """What the dialog's values ask for: each layer's (position,
    thickness) steps in nanometres, and the summary's rows, (name,
    position, thickness) in mm. A step is None where it is unticked."""
    if values["all_layers"]:
        mm = _mm(values["all"])
        return {n: _nm(mm) for n in layers}, [("All layers",) + mm]
    mm = [(n, _mm(values["layers"][n])) for n in layers]
    return ({n: _nm(m) for n, m in mm},
        [(board.GetLayerName(n),) + m for n, m in mm])


def _mm(steps):
    return tuple(step if on else None
        for on, step in (steps["positions"], steps["thickness"]))


def _nm(mm):
    return tuple(int(round(v * MM)) if v else None for v in mm)


def parse(data):
    """The saved choices from the settings file's data. The all-layers row
    sits at the top, as it did before layers; layers follow under their
    standard names. Anything missing or broken reads as the default, in a
    layer's row as the all-layers row."""
    if not isinstance(data, dict):
        data = {}
    every = _kinds(data, DEFAULTS)
    layers = data.get("layers")
    if not isinstance(layers, dict):
        layers = {}
    on = data.get("all_layers")
    return {"all_layers": on if isinstance(on, bool) else True,
        "all": every,
        "layers": {name: _kinds(steps, every)
            for name, steps in layers.items() if isinstance(steps, dict)}}


def _kinds(data, base):
    out = dict(base)
    for key in base:
        try:
            on, step = data[key]
            if float(step) > 0:
                out[key] = (bool(on), float(step))
        except (KeyError, TypeError, ValueError):
            pass
    return out


def dump(saved):
    """The settings file's data for saved; parse() reads it back."""
    data = {k: list(v) for k, v in saved["all"].items()}
    data["all_layers"] = saved["all_layers"]
    data["layers"] = {name: {k: list(v) for k, v in steps.items()}
        for name, steps in saved["layers"].items()}
    return data


def _settings_path():
    return os.path.join(pcbnew.SETTINGS_MANAGER.GetUserSettingsPath(),
        SETTINGS)


def _load():
    try:
        with open(_settings_path()) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    return parse(data)


def _save(saved):
    try:
        with open(_settings_path(), "w") as f:
            json.dump(dump(saved), f)
    except OSError:
        pass
