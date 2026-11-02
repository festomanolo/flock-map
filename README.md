# FlockMap — reproducible study of wake-aware adaptive V-formation for fixed-wing UAV mapping

Everything in `manuscript/main.pdf` (every number, table cell and figure) is generated from the code and raw data in this folder.

```
src/flockmap/      models: aero.py (analytic wake + strip theory, "published" and "corrected"), vlm.py (independent
                   vortex-lattice), freewake.py (unsteady free-wake vortex rings, wake roll-up), viz3d.py (3-D X8-class mesh), control.py (guidance-level NMPC + relative-degree-3 HOCBF), energy.py, mission.py,
                   photo.py (geometric coverage), dubins.py, battery.py, stats.py
experiments/       run_extra (dz, kappa map, tornado/Sobol, station-keeping, coverage, power, CBF ablation), make_numbers_extra, make_cfd_section, run_aero / run_control / run_reconfig / run_mission / run_sensitivity / analyse / make_numbers
audit/             faithful re-implementation of the preliminary manuscript's Sec. 6.2 code + findings (AUDIT.md)
cfd/               OpenFOAM v1912 campaign: make_case.py (case generator), run_all.py (mesh+solve+post), postproc.py (Python force integration), analyze_cfd.py, derive.py, render_cfd.py, env.sh; cases/*/ keep logs, summary.json, convergence/VTK extracts
figures/           fig_aero.py, fig_mission.py, fig_extra.py, fig_cfd.py -> figures/out/*.pdf|png;  fig3d.py, anim3d.py -> figures/out3d/*.png|gif (PyVista, needs xvfb-run)
data/raw/          per-trial outputs (control_trials.csv, control_ts.npz, mission_trials.csv)  <- the evidence
data/processed/    derived tables
manuscript/        main.tex (Elsevier elsarticle) + sections/*.tex, numbers*.tex + tables/ (auto-generated), references.bib, make_docx.py -> FlockMap_manuscript.docx
tests/             pytest (closed-form checks and audit findings)
docs/              FIGURE_MAP.md, JOURNAL_FORMAT.md, NEXT_STEPS.md
```

Run `make test` (14 tests), `make reproduce` (~25 min, 4 cores). Python 3.13, numpy 2.5, scipy 1.18, casadi 3.8.

## What this is and is not
A simulation study with an independent aerodynamic cross-check and steady-RANS CFD (OpenFOAM, `make cfd`, ~1.5 h on 3 cores). **Not done:** PX4/Gazebo SITL, HITL, SfM
reconstruction/checkpoint RMSE, flight tests, wind-tunnel validation. Parameters tagged `[MS]` in `src/flockmap/config.py` come from the preliminary manuscript and were not independently measured; `[ASM]` values are assumptions introduced here.

CFD caveats: the OpenFOAM v1912 binaries shipped with Ubuntu crash on any function object, so forces are integrated in Python from `foamToVTK` patch fields (`cfd/postproc.py`); wall-function meshes without prism layers; the absolute drag is not mesh-converged (see manuscript Sec. 5.7), only differences between flows on the same mesh family are used.
