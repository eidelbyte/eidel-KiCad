# Test matrix

Every cell has a covering test, or a deferral with its reason.

## Grid math (test_snap.py)

| Cell | Case                                              | Test |
|------|---------------------------------------------------|------|
| Q1   | nearest multiple, halves up, tiny to zero         | test_q1_* |
| Q2   | negative values, odd steps                        | test_q2_* |
| Q3   | points from a non-zero grid origin                | test_q3_* |
| Q4   | smallest multiple at least v                      | test_q4_* |
| A1   | arc already on the grid is unchanged              | test_a1_* |
| A2   | off-grid short arc                                | test_a2_* |
| A3   | long arc (270 degrees) stays long                 | test_a3_* |
| A4   | semicircle                                        | test_a4_* |
| A5   | radius grows to span the rounded ends             | test_a5_* |
| A6   | ends meet, or radius rounds to zero: collapse     | test_a6_* |
| A7   | 300 seeded random arcs: ends on grid, radius on step within what three integer points can hold, sides kept | test_a7_* |
| P1   | ring points rounded                               | test_p1_* |
| P2   | repeated points dropped, including around the end | test_p2_* |
| P3   | ring collapsing to a point or a line              | test_p3_* |
| P4   | signed area                                       | test_p4_* |

## KiCad items (test_rounding.py)

Dimensions: item kind x outcome (rounded, deleted, value set to zero,
left alone).

| Cell | Case                                              | Test |
|------|---------------------------------------------------|------|
| K1   | segment; zero length and 0.001 mm width deleted; hairline stays | test_k1_* |
| K2   | rectangle corners and corner radius; radius clamped to the side; flat one deleted; filled border to zero kept | test_k2_* |
| K3   | circle; radius to zero deleted                    | test_k3_* |
| K4   | arc through KiCad's own geometry                  | test_k4_* |
| K5   | off-grid outline of lines and arcs stays connected | test_k5_* |
| K6   | polygon; collapsed polygon deleted                | test_k6_* |
| K7   | bezier                                            | test_k7_* |
| K8   | text position, size, thickness; tiny text deleted; footprint field never deleted | test_k8_* |
| K9   | text box corners; border to zero switches off     | test_k9_* |
| K10  | track, track arc, via; drill and width to zero deleted | test_k10_* |
| K11  | zone outline rounded and unfilled                 | test_k11_* |
| K12  | footprint moves by anchor, inside keeps its shape | test_k12_* |
| K13  | locked items and dimensions left alone; groups open and lose deleted members | test_k13_* |
| K14  | grid origin                                       | test_k14_* |
| K15  | positions only: thickness untouched, nothing deleted for it | test_k15_* |
| K16  | thickness only: points and zones untouched, short line kept | test_k16_* |
| K17  | separate steps for positions and thickness        | test_k17_* |
| K18  | items already on the grid count as unchanged; zone stays filled | test_k18_* |
| K19  | a zero-length dot rounding did not make is kept   | test_k19_* |
| K20  | pads selected on their own                        | deferred: same anchor move as K12; pads are rarely selected alone |
| K21  | undo in the running KiCad                         | deferred: KiCad records an action plugin's changes for undo; needs a click-through |

## Layers (test_rounding.py)

Dimensions: where an item's layer comes from x the steps of its layer
(both, one, none) x items on two layers that meet.

| Cell | Case                                              | Test |
|------|---------------------------------------------------|------|
| L1   | an item's layer, the first it is on: its own; a via its top layer; a footprint or SMD pad its side, flipped included; a through-hole pad the front; a zone on several layers the first | test_l1_* |
| L2   | the selection's layers, each once, in KiCad's layer order | test_l2_* |
| L3   | each layer on its own position and thickness steps | test_l3_* |
| L4   | a layer with nothing to round is left alone and reported; one with only thickness keeps its points | test_l4_* |
| L5   | items on two layers that meet stay joined on equal position steps and part on unequal ones | test_l5_* |
| L6   | summary: one row for all layers, a row per layer, a layer left alone | test_l6_* |

## Remembered choices (test_plugin.py)

| Cell | Case                                              | Test |
|------|---------------------------------------------------|------|
| S1   | no file, or a broken one: all layers, 0.25 mm for each kind | test_s1_* |
| S2   | a file from before layers: its two options are the all-layers row | test_s2_* |
| S3   | layer rows from what was remembered under the standard layer name, a renamed layer included; else from the all-layers row | test_s3_* |
| S4   | a broken layer entry reads as the all-layers row  | test_s4_* |
| S5   | saving keeps layers not on this board and round trips | test_s5_* |
| S6   | the steps and summary rows handed on: all layers, or per layer | test_s6_* |
| S7   | the whole action in the running KiCad             | deferred: needs the PCB editor; run it by hand after install |

## Dialog (test_dialog.py)

| Cell | Case                                              | Test |
|------|---------------------------------------------------|------|
| D1   | All layers ticked: only its row shows; values read back | test_d1_* |
| D2   | All layers unticked: a row per layer, in order, with its own values | test_d2_* |
| D3   | Round needs a tick in a row that shows            | test_d3_* |
| D4   | a kind's checkbox enables its step                | test_d4_* |
| D5   | look and layout on screen                         | deferred: needs a display; check by hand after install |
