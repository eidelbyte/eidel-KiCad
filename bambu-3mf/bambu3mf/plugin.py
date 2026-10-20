"""The KiCad action: selection -> dialog -> 3MF -> report."""

import os

import pcbnew
import wx

from . import dialog, export, settings

MM = 1000000
ROW_KEYS = ("export", "filament", "fill_closed", "depth", "z")


class Bambu3mfPlugin(pcbnew.ActionPlugin):

    def defaults(self):
        self.name = "Export Selection to Bambu 3MF"
        self.category = "Export"
        self.description = ("Extrude the selected items layer by layer, "
            "one filament per layer, into a 3MF for Bambu Studio")
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__),
            "icon.png")

    def Run(self):
        board = pcbnew.GetBoard()
        frame = wx.FindWindowByName("PcbFrame")
        items = export.flatten(pcbnew.GetCurrentSelection())
        layers = export.layers_of(board, items)
        if not layers:
            wx.MessageBox("Select the items to export first.", self.name,
                wx.OK | wx.ICON_INFORMATION, frame)
            return

        board_path = board.GetFileName()
        saved = settings.load(board_path)
        saved_rows = saved.get("layers", {})
        rows = []
        for n, (layer, name) in enumerate(layers):
            row = {"export": True, "filament": n + 1,
                "fill_closed": layer == pcbnew.Edge_Cuts, "depth": 1.0,
                "z": 0.0}
            old = saved_rows.get(name, {})
            row.update((k, old[k]) for k in ROW_KEYS if k in old)
            row.update(layer=layer, name=name)
            rows.append(row)
        last_output = saved.get("output", "")
        output = last_output or (os.path.splitext(board_path)[0] + ".3mf"
            if board_path else os.path.expanduser("~/selection.3mf"))

        dlg = dialog.ExportDialog(frame, self.name, rows, output,
            last_output)
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            rows = dlg.rows()
            output = dlg.output()
        finally:
            dlg.Destroy()

        saved_rows.update((r["name"], {k: r[k] for k in ROW_KEYS})
            for r in rows)
        settings.save(board_path, {"layers": saved_rows, "output": output})

        jobs = [export.Job(r["layer"], r["name"], r["filament"],
            r["fill_closed"], int(round(r["depth"] * MM)),
            int(round(r["z"] * MM))) for r in rows if r["export"]]
        title = os.path.splitext(os.path.basename(board_path))[0] or "KiCad"
        try:
            with wx.BusyCursor():
                lines = export.export(board, items, jobs, output, title)
        except export.ExportError as e:
            wx.MessageBox(str(e), self.name, wx.OK | wx.ICON_WARNING, frame)
            return
        wx.MessageBox("Wrote %s\n\n%s" % (output, "\n".join(lines)),
            self.name, wx.OK | wx.ICON_INFORMATION, frame)
