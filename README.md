# eidel-KiCad

KiCad 10 action plugins, one per folder. Each folder holds the plugin
package, its tests and its own README.

| Folder           | Plugin                          | What it does |
|------------------|---------------------------------|--------------|
| `bambu-3mf/`     | Export Selection to Bambu 3MF   | extrudes the selection layer by layer into a multi-filament 3MF for Bambu Studio |
| `round-to-grid/` | Round Selection to Grid         | rounds the selection's positions and sizes, and its thickness, to grid steps, for all layers or per layer |

## Install

Link each plugin package into KiCad's scripting plugins folder, then
restart the PCB editor (or Tools > External Plugins > Refresh Plugins):

    ln -s ~/eidel-KiCad/bambu-3mf/bambu3mf \
        ~/Documents/KiCad/10.0/scripting/plugins/bambu3mf
    ln -s ~/eidel-KiCad/round-to-grid/roundtogrid \
        ~/Documents/KiCad/10.0/scripting/plugins/roundtogrid

Both need nothing beyond what KiCad ships.

## Tests

Each folder has `tests/run.sh`, which runs its tests with KiCad's
Python:

    bambu-3mf/tests/run.sh
    round-to-grid/tests/run.sh
