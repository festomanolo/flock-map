# Audit of the preliminary manuscript (60 pp.)

Each finding is reproduced by code in this repository (see `tests/test_core.py`, `audit/original_reproduction.py`,
`experiments/run_aero.py` -> `data/processed/audit_table33.csv`).

| # | Finding | Evidence | Effect |
|---|---------|----------|--------|
| 1 | Wake circulation Γ0 = 4VSC_L/(πb) is 2× L/(ρ V b0) (1.870 vs 0.935 m²/s) | `test_circulation_is_twice_too_large_in_manuscript` | All upwash and savings overstated ≈2× |
| 2 | Roll-moment coefficient normalised by 1/(bS) (not dimensionless) with lift slope 2π; correct is (a/b²)∫… | `aero.strip_follower(variant=…)` | C_l overstated 3.6× at 0.8b; trim drag ∝C_l² overstated >10× |
| 3 | Table in Sec. 3.3 is not reproducible from Sec. 3 equations / Sec. 6.2 code except at d_y/b = 0.50, 0.70, 0.80 | `audit_table33.csv`, Fig. A1 | The "sweet spot" at 0.80 b is a cancellation of errors 1 and 2; the code gives −15 % at 0.90 b |
| 4 | RMSE_H, RMSE_V and accepted area are assigned by `np.random.normal/uniform` | `audit/original_reproduction.py` | Mapping-quality columns are not measurements |
| 5 | All energy variance is one scalar `env_factor` shared by all strategies (corr = 1.0) → t≈−204, d_z≈29 | `original_reproduction_output.json` | Statistics are artefacts |
| 6 | Reported SDs (e.g. 1.15 Wh) smaller than the code can generate (1.57 Wh); means differ slightly | same | Table not produced by printed code |
| 7 | Wind is stated but unused; no climb/landing/reserve; Boustrophedon turns use a 222.6 m semicircle between strips 61.6 m apart (turn diameter 141.7 m) | `dubins.py`, `energy.turn_path_len` | Turn energy ≈2× higher; absolute energies ≈+45 % |
| 8 | Reconfiguration charged as 3×45 s at full cruise power on top of already-integrated time | `run_reconfig.py` (simulated overhead 0.1–0.4 Wh) | Break-even logic changes |
| 9 | HOCBF relative degree stated as 2; it is 3 with the stated bank lag | `control._build_hocbf` | Guarantee as stated does not hold |
| 10 | Turn power 146.42 W vs 145.8 W from the stated polar | `energy.p_level` | minor |
| 11 | 58 % side overlap sits 0.05 % from violating the paper's own ≥5-ray rule at the block edge (80 ha accepted at zero crab) | `photo.py`, Fig. 13 | Central 17→14-strip claim is borderline and untested |
| 12 | "Relaxed overlap needs formation/RTK stereo" – but the payload table gives RTK-GNSS to every UAV | decomposition D1 vs S1 | Route saving is available without formation |

Consequences for the headline claim: with corrected physics, formation transit alone *costs* energy at 2.5 km; the
−3.4 % total is a route effect (−7.1 %) partly cancelled by formation (+1.4 %) and an interaction (waiting).
