"""The dialog's choices, remembered per board in KiCad's settings folder.

The file maps a board's path to {"layers": {name: row}, "output": path}.
Reading or writing it never stops an export: a missing or broken file
reads as empty, and a failed write is ignored.
"""

import json
import os

import pcbnew

FILE = "bambu3mf.json"


def _path():
    return os.path.join(pcbnew.SETTINGS_MANAGER.GetUserSettingsPath(), FILE)


def _read():
    try:
        with open(_path()) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load(board):
    entry = _read().get(board)
    return entry if isinstance(entry, dict) else {}


def save(board, entry):
    data = _read()
    data[board] = entry
    try:
        with open(_path(), "w") as f:
            json.dump(data, f, indent=1, sort_keys=True)
    except OSError:
        pass
