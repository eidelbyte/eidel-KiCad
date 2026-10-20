# KiCad selection to Bambu 3MF

A KiCad 10 action plugin that turns the selected items into a 3MF for
Bambu Studio: each KiCad layer is extruded to its own depth and printed
with its own filament, so a drawing becomes a multi-colour tile, inlay
or printed board without repainting anything in the slicer.

## Workflow

1. Select the items in the PCB editor (lines, arcs, circles, rectangles,
   polygons, text, text boxes, footprints, groups, tracks, pads, zones).
2. Run **Export Selection to Bambu 3MF** (toolbar button, or Tools >
   External Plugins).
3. The dialog lists each layer the selection is on:

   | Column             | Meaning                                         |
   |--------------------|-------------------------------------------------|
   | Layer              | export this layer or not                        |
   | Filament           | filament number; layers may share one          |
   | Fill closed shapes | fill closed outlines, nested like Edge.Cuts     |
   | Depth (mm)         | thickness of the layer's solid                  |
   | Z offset (mm)      | height of the solid's bottom                    |

4. Choose the output file and press Export. A summary lists the parts
   written. The choices are remembered per board.

For the eagle tile: F.Silkscreen with Fill closed shapes, depth 5,
filament 1; User.Drawings depth 2.5, Z offset 2.5, filament 2. The lines,
on the higher number, then sit in a 2.5 mm deep channel in the top of
the tile.

## What gets extruded

- Strokes keep their real width and round ends, the way KiCad draws
  them. Text is extruded as its glyphs.
- **Fill closed shapes** fills every area that the layer's strokes
  enclose, whether one shape or a chain of lines and arcs drawn end to
  end. Nesting alternates as on Edge.Cuts: an outline inside a filled
  outline is a hole, one inside that is solid again. The fill reaches the
  outer edge of the strokes. Ends up to the stroke width plus 0.02 mm
  apart still close. Text is never filled (the hole in an "O" stays a
  hole), and shapes KiCad already fills are always solid.
- **Overlaps**: where two layers' solids overlap, the higher filament
  number keeps the space, like a z-index. That is what makes inlays
  work: lines on filament 2 carve their channel out of a tile on
  filament 1, and where two layers of lines cross, the higher number
  runs through. The numbers are only labels until you map them to real
  filaments in Bambu Studio, so ordering them costs nothing. Layers on
  the same number are the same material; the one listed first takes the
  overlap.
- A layer cut only over part of its height becomes a stack of parts, for
  example "F.Silkscreen 0-2.5 mm" and "F.Silkscreen 2.5-5 mm".
- The model reads as KiCad shows it from the front. Back layers are not
  mirrored.

## In Bambu Studio

- Open the file on an empty plate, or pick "Open as project". Bambu
  Studio says the 3MF is not from Bambu Lab and loads geometry and colour
  data only. That is expected: your printer, process and filaments stay
  as they are.
- The file holds one object whose parts are already grouped by filament
  number. Map the numbers to real filaments in the filament list; the
  project needs at least as many filament slots as the highest number.
  To regroup, change a part's filament in the object list.
- "Import geometry only" into an existing project keeps the parts and
  their filaments, adds filament slots as needed, but drops the object
  print settings below. This is Bambu Studio's rule for imports.

### Print settings set on the object

They show as the object's own settings and can be changed or removed
there. Shipped Bambu process presets use 5 top and 3 bottom shell
layers, no ironing and the classic wall generator.

| Setting                                    | Value      | Why                                   |
|--------------------------------------------|------------|---------------------------------------|
| top_shell_layers / top_shell_thickness     | 7 / 1.4 mm | strong colour on the top face         |
| bottom_shell_layers / bottom_shell_thickness | 5 / 1.0 mm | the same on a face-down print's face |
| ironing_type                               | top        | smooth finish on large flat tops      |
| wall_generator                             | arachne    | prints strokes thinner than the nozzle line |

## Tips

- Use depths and offsets that are multiples of the layer height. With
  0.2 mm layers a 2.5 mm boundary falls mid-layer, so an inlay drawn
  2.5 mm deep prints 2.4 mm deep.
- With Arachne's defaults, strokes narrower than 85% of the nozzle
  (0.34 mm on a 0.4 mm nozzle) print as one bead widened to that, and
  strokes under 25% of the nozzle do not print. Use a 0.2 mm nozzle, wider strokes, or scale
  the object up in the slicer.
- To print face down (the coloured face on the plate: flat, with the
  plate's finish and crisp colour edges), export with the inlay at the
  top as usual and flip the object 180 degrees about X in the slicer.
  Do not move the inlay to Z offset 0 instead: seen from the face, the
  drawing would come out mirrored. Face down, the top is the back:
  the ironing preset smooths the back, which only costs time; set the
  object's ironing type to "no ironing" if the back does not matter.
  A smooth plate gives a glossy face, a textured plate a matte one.

## Install

Link the plugin package into KiCad's scripting plugins folder, then
restart the PCB editor (or Tools > External Plugins > Refresh Plugins):

    ln -s ~/kicad-bambu-3mf/bambu3mf \
        ~/Documents/KiCad/10.0/scripting/plugins/bambu3mf

The toolbar button can be switched on or off on the plugins page of the
PCB editor's preferences. The plugin needs nothing beyond what KiCad
ships. The remembered choices live in
`~/Library/Preferences/kicad/10.0/bambu3mf.json`.

## Headless export

`tools/export_window.py` exports everything inside a window of a board,
without the GUI; see its help. Run it with KiCad's Python.

## Tests

    tests/run.sh

runs the geometry core, the KiCad layer and, when Bambu Studio is
installed, a real slice through its command line. `tests/MATRIX.md` maps
the problem space to the tests.

## Limits

- Pad drill holes are not cut; a pad is extruded as solid copper shape.
- Tables, dimensions and knockout text are drawn with KiCad's own shape
  conversion and are not covered by tests.

## Layout

    bambu3mf/earcut.py    triangulation (port of mapbox/earcut, ISC)
    bambu3mf/mesh.py      closed prisms from polygons with holes
    bambu3mf/threemf.py   the 3MF package and Bambu's model settings
    bambu3mf/export.py    selection -> layer regions -> stacked slabs
    bambu3mf/dialog.py    the dialog
    bambu3mf/plugin.py    the KiCad action
    bambu3mf/settings.py  remembered choices
