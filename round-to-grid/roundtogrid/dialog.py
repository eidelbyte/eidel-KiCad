"""The step dialog."""

import wx

HELP = ("Points snap to the grid, counted from the board's grid origin. "
    "Widths, thicknesses, radii and text sizes round to multiples of the "
    "step. An item whose length, radius, area, thickness or text size "
    "rounds to zero is deleted. Footprints move by their anchor only; "
    "locked items are left alone.")


class StepDialog(wx.Dialog):

    def __init__(self, parent, title, step_mm, count):
        wx.Dialog.__init__(self, parent, title=title)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(self, label="Grid step (mm)"), 0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self._step = wx.SpinCtrlDouble(self, min=0.001, max=100,
            initial=step_mm, inc=0.05)
        self._step.SetDigits(3)
        row.Add(self._step, 0, wx.ALIGN_CENTER_VERTICAL)

        what = wx.StaticText(self, label="%d selected item(s)." % count)
        note = wx.StaticText(self, label=HELP)
        note.Wrap(420)

        buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        self.FindWindowById(wx.ID_OK).SetLabel("Round")

        top = wx.BoxSizer(wx.VERTICAL)
        top.Add(row, 0, wx.ALL, 12)
        top.Add(what, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        top.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        top.Add(buttons, 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizerAndFit(top)
        self.CentreOnParent()

    def step_mm(self):
        return self._step.GetValue()
