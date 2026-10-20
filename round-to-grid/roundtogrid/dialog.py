"""The dialog: which kinds of value to round, and to what step."""

import wx

HELP = ("Points snap to the grid, counted from the board's grid origin. "
    "An item whose length, radius, area, thickness or text size rounds to "
    "zero is deleted. Footprints move by their anchor only; locked items "
    "are left alone.")

KINDS = (
    ("positions", "Positions and sizes",
        "points, radii, corner radii, text sizes, via diameter and drill"),
    ("thickness", "Thickness",
        "line, track and border widths, text stroke thickness"),
)


class StepDialog(wx.Dialog):
    """values maps each kind to (enabled, step in mm); values() returns
    the user's choices in the same shape."""

    def __init__(self, parent, title, values, count):
        wx.Dialog.__init__(self, parent, title=title)
        grid = wx.FlexGridSizer(cols=3, vgap=4, hgap=8)
        self._rows = {}
        for key, label, what in KINDS:
            on, step = values[key]
            use = wx.CheckBox(self, label=label)
            use.SetValue(on)
            spin = wx.SpinCtrlDouble(self, min=0.001, max=100, initial=step,
                inc=0.05)
            spin.SetDigits(3)
            spin.Enable(on)
            use.Bind(wx.EVT_CHECKBOX,
                lambda e, s=spin: s.Enable(e.IsChecked()))
            grid.Add(use, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(spin, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(wx.StaticText(self, label="mm"), 0,
                wx.ALIGN_CENTER_VERTICAL)
            grid.Add(wx.StaticText(self, label="    " + what), 0,
                wx.BOTTOM, 6)
            grid.AddSpacer(0)
            grid.AddSpacer(0)
            self._rows[key] = (use, spin)

        what = wx.StaticText(self, label="%d selected item(s)." % count)
        note = wx.StaticText(self, label=HELP)
        note.Wrap(440)

        buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        self.FindWindowById(wx.ID_OK).SetLabel("Round")
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

        top = wx.BoxSizer(wx.VERTICAL)
        top.Add(grid, 0, wx.ALL, 12)
        top.Add(what, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        top.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        top.Add(buttons, 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizerAndFit(top)
        self.CentreOnParent()

    def values(self):
        return {key: (use.GetValue(), spin.GetValue())
            for key, (use, spin) in self._rows.items()}

    def _on_ok(self, event):
        if not any(use.GetValue() for use, _ in self._rows.values()):
            wx.MessageBox("Choose what to round.", self.GetTitle(),
                wx.OK | wx.ICON_WARNING, self)
        else:
            event.Skip()
