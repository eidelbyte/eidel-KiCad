"""KiCad action plugin: round the selection to a grid step.

The grid math (snap) imports without KiCad; the plugin registers itself
only when pcbnew is available.
"""

import importlib.util

if importlib.util.find_spec("pcbnew") is not None:
    from .plugin import RoundToGridPlugin
    RoundToGridPlugin().register()
