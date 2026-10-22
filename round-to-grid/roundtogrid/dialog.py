"""The dialog: which kinds of value to round, and to what step, for all
layers at once or for each layer of the selection."""

import wx

HELP = ("Points snap to the grid, counted from the board's grid origin. "
    "An item whose length, radius, area, thickness or text size rounds to "
    "zero is deleted. Footprints move by their anchor only; locked items "
    "are left alone. Each item rounds on its own layer's steps: a via on "
    "its top layer, a footprint or pad on its side. Items on two layers "
    "that meet stay joined only where both layers round positions on the "
    "same step.")

KINDS = (
    ("positions", "Positions and sizes",
        "points, radii, corner radii, text sizes, via diameter and drill"),
    ("thickness", "Thickness",
        "line, track and border widths, text stroke thickness"),
)


class StepDialog(wx.Dialog):
    """layers: (layer, name) for each layer of the selection, in order.
    values: {"all_layers": bool, "all": steps, "layers": {layer: steps}},
    steps mapping each kind to (enabled, step in mm). values() returns
    the user's choices in the same shape."""

    def __init__(self, parent, title, layers, values, count):
        wx.Dialog.__init__(self, parent, title=title)
        self._all = wx.CheckBox(self, label="All layers")
        self._all.SetValue(values["all_layers"])
        self._all.Bind(wx.EVT_CHECKBOX, lambda e: self._show())

        grid = wx.FlexGridSizer(cols=1 + len(KINDS), vgap=4, hgap=12)
        grid.AddSpacer(0)
        for _, label, _ in KINDS:
            grid.Add(wx.StaticText(self, label=label))
        self._every = self._row(grid, "All layers", values["all"])
        self._rows = {n: self._row(grid, name, values["layers"][n])
            for n, name in layers}

        kinds = wx.StaticText(self, label="\n".join("%s: %s." %
            (label, what) for _, label, what in KINDS))
        selected = wx.StaticText(self, label="%d selected item(s) on %d "
            "layer(s)." % (count, len(layers)))
        note = wx.StaticText(self, label=HELP)
        note.Wrap(440)

        buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        self.FindWindowById(wx.ID_OK).SetLabel("Round")
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

        top = wx.BoxSizer(wx.VERTICAL)
        top.Add(self._all, 0, wx.ALL, 12)
        top.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        for text in (kinds, selected, note):
            top.Add(text, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        top.Add(buttons, 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizer(top)
        self._show()
        self.CentreOnParent()

    def _row(self, grid, name, steps):
        """Add a row of a checkbox and a step per kind to grid; returns the
        row's windows and its {kind: (checkbox, step)}."""
        label = wx.StaticText(self, label=name)
        grid.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
        windows = [label]
        controls = {}
        for key, _, _ in KINDS:
            on, step = steps[key]
            use = wx.CheckBox(self)
            use.SetValue(on)
            spin = wx.SpinCtrlDouble(self, min=0.001, max=100, initial=step,
                inc=0.05)
            spin.SetDigits(3)
            spin.Enable(on)
            use.Bind(wx.EVT_CHECKBOX,
                lambda e, s=spin: s.Enable(e.IsChecked()))
            mm = wx.StaticText(self, label="mm")
            cell = wx.BoxSizer(wx.HORIZONTAL)
            cell.Add(use, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
            cell.Add(spin, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
            cell.Add(mm, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(cell)
            windows += [use, spin, mm]
            controls[key] = (use, spin)
        return windows, controls

    def _show(self):
        """Show the all-layers row or the layer rows, as ticked."""
        every = self._all.GetValue()
        for w in self._every[0]:
            w.Show(every)
        for windows, _ in self._rows.values():
            for w in windows:
                w.Show(not every)
        self.Layout()
        self.Fit()

    def _shown(self):
        return [self._every] if self._all.GetValue() else \
            list(self._rows.values())

    def ready(self):
        """Whether a row that shows has something ticked."""
        return any(use.GetValue() for _, controls in self._shown()
            for use, _ in controls.values())

    def values(self):
        return {"all_layers": self._all.GetValue(),
            "all": _read(self._every[1]),
            "layers": {n: _read(c) for n, (_, c) in self._rows.items()}}

    def _on_ok(self, event):
        if not self.ready():
            wx.MessageBox("Choose what to round.", self.GetTitle(),
                wx.OK | wx.ICON_WARNING, self)
        else:
            event.Skip()


def _read(controls):
    return {key: (use.GetValue(), spin.GetValue())
        for key, (use, spin) in controls.items()}
