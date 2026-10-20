"""The export dialog: for each layer, whether and how to extrude it."""

import os

import wx

HELP = ("Depth is a layer's thickness and Z offset the height of its "
    "bottom, both in mm. Fill closed shapes fills every closed outline the "
    "way Edge.Cuts does: an outline inside another one is a hole. Where "
    "solids overlap, the higher filament number keeps the space, like a "
    "z-index: give an inlay a higher number than the tile it cuts into.")

COLUMNS = ("Layer", "Filament", "Fill closed shapes", "Depth (mm)",
    "Z offset (mm)")


class ExportDialog(wx.Dialog):
    """rows are dicts with name, export, filament, fill_closed, depth and
    z; rows() returns them with the user's values."""

    def __init__(self, parent, title, rows, output, last_output):
        wx.Dialog.__init__(self, parent, title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._last_output = last_output

        grid = wx.FlexGridSizer(cols=len(COLUMNS), vgap=4, hgap=12)
        for label in COLUMNS:
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_BOTTOM)
        self._rows = []
        for row in rows:
            use = wx.CheckBox(self, label=row["name"])
            use.SetValue(row["export"])
            filament = wx.SpinCtrl(self, min=1, max=32,
                initial=row["filament"])
            fill = wx.CheckBox(self)
            fill.SetValue(row["fill_closed"])
            depth = wx.SpinCtrlDouble(self, min=0.01, max=1000,
                initial=row["depth"], inc=0.1)
            depth.SetDigits(2)
            z = wx.SpinCtrlDouble(self, min=-1000, max=1000,
                initial=row["z"], inc=0.1)
            z.SetDigits(2)
            controls = (filament, fill, depth, z)
            for c in controls:
                c.Enable(row["export"])
            use.Bind(wx.EVT_CHECKBOX,
                lambda e, cs=controls: [c.Enable(e.IsChecked()) for c in cs])
            grid.Add(use, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(filament, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(fill, 0, wx.ALIGN_CENTER)
            grid.Add(depth, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(z, 0, wx.ALIGN_CENTER_VERTICAL)
            self._rows.append((row, use, filament, fill, depth, z))

        note = wx.StaticText(self, label=HELP)
        note.Wrap(560)

        self._output = wx.FilePickerCtrl(self, path=output,
            message="Export to", wildcard="3MF files (*.3mf)|*.3mf",
            style=wx.FLP_SAVE | wx.FLP_USE_TEXTCTRL)
        out_row = wx.BoxSizer(wx.HORIZONTAL)
        out_row.Add(wx.StaticText(self, label="Output file"), 0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        out_row.Add(self._output, 1, wx.EXPAND)

        buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        self.FindWindowById(wx.ID_OK).SetLabel("Export")
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

        top = wx.BoxSizer(wx.VERTICAL)
        top.Add(grid, 0, wx.ALL, 12)
        top.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        top.Add(out_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        top.Add(buttons, 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizerAndFit(top)
        self.CentreOnParent()

    def rows(self):
        return [dict(row, export=use.GetValue(), filament=filament.GetValue(),
            fill_closed=fill.GetValue(), depth=depth.GetValue(),
            z=z.GetValue())
            for row, use, filament, fill, depth, z in self._rows]

    def output(self):
        path = os.path.expanduser(self._output.GetPath().strip())
        if path and not path.lower().endswith(".3mf"):
            path += ".3mf"
        return path

    def _on_ok(self, event):
        title = self.GetTitle()
        path = self.output()
        if not any(r[1].GetValue() for r in self._rows):
            wx.MessageBox("Choose at least one layer to export.", title,
                wx.OK | wx.ICON_WARNING, self)
        elif not path:
            wx.MessageBox("Choose an output file.", title,
                wx.OK | wx.ICON_WARNING, self)
        elif not os.path.isdir(os.path.dirname(path)):
            wx.MessageBox("The folder %s does not exist." %
                os.path.dirname(path), title, wx.OK | wx.ICON_WARNING, self)
        elif os.path.exists(path) and path != self._last_output and \
            wx.MessageBox("%s exists. Replace it?" % path, title,
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES:
            pass
        else:
            event.Skip()
