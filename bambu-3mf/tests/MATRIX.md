# Test matrix

Every cell has a covering test, or a deferral with its reason.

## Triangulation and extrusion (test_core.py)

Dimensions: ring shape x holes x degeneracy x size. Every cell checks
exact cap area, a closed edge-manifold mesh (each directed edge has
exactly one opposite) and volume = area x height exactly.

| Cell | Case                                              | Test |
|------|---------------------------------------------------|------|
| E1   | convex ring, either winding                       | test_e1_* |
| E2   | concave ring (comb)                               | test_e2_concave_comb |
| E3   | one hole, either winding                          | test_e3_* |
| E4   | many holes                                        | test_e4_many_holes |
| E5   | rings touching at a point: hole-outline, hole-hole | test_e5_* |
| E6   | duplicate and collinear points                    | test_e6_* |
| E7   | below and above earcut's 80-vertex hashing switch | test_e7_* |
| E8   | several polygons per call; negative and offset z  | test_e8_* |
| E9   | 60 seeded random polygons with holes              | test_e9_* |
| E10  | self-intersecting rings                           | deferred: KiCad's boolean output never has them |
| E11  | a vertex on the inside of another ring's edge     | deferred: not seen in KiCad's boolean output; if it occurs the walls follow the cap boundary (still closed) and the export summary names the part |

## 3MF writer (test_core.py)

| Cell | Case                                              | Test |
|------|---------------------------------------------------|------|
| W1   | exact nm to mm decimal strings                    | test_w1_mm_is_exact |
| W2   | package entries and relationship                  | test_w2_package_layout |
| W3   | ids, components, build item, vertices, triangles, escaped names | test_w3_model_round_trip |
| W4   | object and part filaments, object print settings  | test_w4_filaments_per_part |

## Layer regions (test_kicad.py)

Dimensions: shape kind x fill closed x stroke width x nesting.

| Cell | Case                                              | Test |
|------|---------------------------------------------------|------|
| R1   | stroke width and round ends                       | test_r1_* |
| R2   | outline of lines and arcs, filled and not         | test_r2_* |
| R3   | three nested outlines alternate solid, hole, solid | test_r3_* |
| R4   | text never filled; text inside a fill is covered  | test_r4_* |
| R5   | open chain stays a stroke                         | test_r5_* |
| R6   | zero-width outline with a 5 um gap still fills    | test_r6_* |
| R7   | shapes KiCad fills are solid                      | test_r7_* |
| R8   | text box border and text; border off              | test_r8_* |
| R9   | items on other layers ignored                     | test_r9_* |
| R10  | tables, dimensions, knockout text                 | deferred: drawn by KiCad's own conversion; add fixtures when they are used |

## Selection (test_kicad.py)

| Cell | Case                                              | Test |
|------|---------------------------------------------------|------|
| F1   | groups open; an item selected twice counts once   | test_f1_* |
| F2   | footprints open; hidden fields drop               | test_f2_* |
| F3   | layers limited to enabled ones, in KiCad's order  | test_f3_* |

## Stacking (test_kicad.py)

Dimensions: z relation (inside, touching, partial, through) x xy
relation (inside, disjoint) x volume order (smaller, tie). Every cell
also checks that slabs never overlap and that their volume is the
volume of the union.

| Cell | Case                                              | Test |
|------|---------------------------------------------------|------|
| S1   | inlay at the top                                  | test_s1_top_inlay |
| S2   | inlay at the bottom                               | test_s2_bottom_inlay |
| S3   | inlay through the full height                     | test_s3_through_inlay |
| S4   | raised: z ranges touch, no split                  | test_s4_* |
| S5   | disjoint in xy, no split                          | test_s5_* |
| S6   | equal volumes: first listed wins, other dropped   | test_s6_* |
| S7   | smaller but taller solid wins                     | test_s7_* |
| S8   | three nested layers; equal slabs merge            | test_s8_* |
| S9   | partial z overlap                                 | test_s9_* |

## Export (test_kicad.py, test_bambu.py)

| Cell | Case                                              | Test |
|------|---------------------------------------------------|------|
| X1   | parts, names and filaments; every mesh closed     | test_x1_* |
| X2   | mesh volumes equal the slab regions               | test_x2_* |
| X3   | nothing on the chosen layers is an error          | test_x3_* |
| B1   | Bambu Studio slice: two filaments, filament 2 only on the inlay's layers, ironing, object settings kept | test_b1_* |
| G1   | the dialog inside running KiCad                   | deferred: needs a click-through; the dialog is constructed and read back headless during development |
| G2   | Bambu Studio GUI import                           | deferred: traced in its source (Plater::priv::load_files); open as project keeps object settings, import geometry only keeps filaments |
