# Reviewer's figure list → what was produced

| Reviewer item | File (figures/out) | Source data | Status |
|---|---|---|---|
| 1 3-D wingtip-vortex structure | fig01_wake_3d | analytic wake (corrected Γ0) | done |
| 2 Wake velocity contours | fig02_wake_contours | analytic + VLM sheet | done |
| 3 Spanwise loading and roll trim | fig03_spanwise_loading | VLM follower, 3 models | done |
| 4 Formation-position sensitivity map | fig04_sensitivity_map | `aero_map_dxdy.npz` | done (planar wake ⇒ weak d_x dependence; needs CFD) |
| 5 Three-UAV geometry | fig05_formation_geometry | config | done (schematic planform, not exact X8) |
| 6 Survey mission comparison | fig06_mission_comparison | mission plans | done (turn loops schematic) |
| 7 Flight-control performance | fig07_control_performance | `control_ts.npz` + split sim | done (guidance-level, not 6-DOF; bank command stands in for surface deflection) |
| 8 Orthomosaic / point cloud / DSM / checkpoint residuals | — | — | **NOT possible without SfM + imagery; fig13 shows geometric multiplicity instead** |
| 9 Energy breakdown | fig09_energy_breakdown | `mission_trials.csv` | done |
| 10 Energy per accepted ha, paired points | fig10_energy_efficiency | same | done |
| 11 Sensitivity (speed × offset, bands) | fig11_sensitivity | `aero_uncertainty_*.csv`, SRC | done |
| 12 Break-even map | fig12_breakeven | `breakeven_*.{csv,npz}` | done |
| 13 Mapping quality | fig13_mapping_geometry | `photo.py` | geometry only (no RMSE) |
| 14 Safety and tracking | fig14_safety_tracking | `control_trials.csv` | done |
| extra | fig15_decomposition, figA1–A3 | decomposition, audit, VLM verification | done |

## 3-D simulation renders (PyVista; `figures/out3d/`)

| File | What it shows | Physics / data behind it |
|---|---|---|
| A1_freewake_formation | leader + 2 followers (real-scale X8-class meshes), free-wake sheet, w at follower plane, plan view, cross-flow vectors, follower-wing loading | free-wake vortex lattice (`freewake.py`) + VLM follower |
| A2_wake_rollup | 115 m (54 b) wake, cross-sections at 10/40/80/110 m | same, long run |
| A3_vorticity_isosurface | streamwise vorticity on cross-flow planes behind the leader | Biot–Savart field of the free wake (file name kept; it is slices, not an iso-surface) |
| B1_safety_sphere | follower trajectories vs D_safe sphere, 3 controllers, 3 scenarios | `run_3d_cases.py` (same simulator as the control campaign) |
| B2_split_manoeuvre | 370 m split, paths coloured by instantaneous wake saving | NMPC sim + VLM-sheet saving table |
| C1_camera_frustums | camera frustums/footprints/overlaps at 120 m AGL | camera model |
| C2_coverage_relief | ray multiplicity as relief; failing tiles in red | `photo.py` |
| D1_mission_overview | four strategies over synthetic terrain | mission plans |
| anim_split_manoeuvre.gif, anim_safety_braking.gif | animations of B2 / B1 | same data |

Limits: these are visualisations of the simplified simulations, not CFD or flight-test imagery. Aircraft meshes are an
approximate X8-class geometry, drawn enlarged where stated. Terrain in D1 is synthetic.

## Added in the extended version
| Figure | Content | Source |
|---|---|---|
| X1–X12 (`figures/fig_extra.py`) | vertical offset, kappa-distance map, tornado + Sobol, station-keeping error, overlap sweep, power curve, reconfiguration law, MC diagnostics, power timeline, leader rotation, control statistics, CBF margin ablation + step response | `experiments/run_extra.py` |
| C1–C6 (`figures/fig_cfd.py`) | mesh study, CFD polar vs VLM, wake plane, formation response, force convergence, residual histories | `cfd/` |
| K1–K3 (`cfd/render_cfd.py`) | surface Cp, Q-criterion/vorticity iso-surface, w/U cross-flow slices from the OpenFOAM solution | OpenFOAM VTK |
