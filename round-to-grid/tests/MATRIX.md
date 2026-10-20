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
| K14  | grid origin; summary wording                      | test_k14_* |
| K15  | positions only: thickness untouched, nothing deleted for it | test_k15_* |
| K16  | thickness only: points and zones untouched, short line kept | test_k16_* |
| K17  | separate steps for positions and thickness        | test_k17_* |
| K18  | items already on the grid count as unchanged; zone stays filled | test_k18_* |
| K19  | a zero-length dot rounding did not make is kept   | test_k19_* |
| K20  | pads selected on their own                        | deferred: same anchor move as K12; pads are rarely selected alone |
| K21  | undo in the running KiCad                         | deferred: KiCad records an action plugin's changes for undo; needs a click-through |
