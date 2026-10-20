"""KiCad action plugin: export the selection as a multi-filament 3MF.

The geometry core (earcut, mesh, threemf) imports without KiCad; the
plugin registers itself only when pcbnew is available.
"""

import importlib.util

if importlib.util.find_spec("pcbnew") is not None:
    from .plugin import Bambu3mfPlugin
    Bambu3mfPlugin().register()
