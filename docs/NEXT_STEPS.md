# What still has to be done before the physics can be called validated

1. **Higher-fidelity CFD** (a steady RANS campaign with wall functions is already included, see `cfd/`; still needed: prism layers, URANS/scale-resolving, propeller + fuselage, benchmark; earlier plan: the free-wake model in `freewake.py` is a stepping stone, not a replacement — its core radius is uncalibrated and moves the saving between 3.1 and 4.4 %; RANS k-ω SST, then URANS): X8-class planform at d_y/b ∈ {0.6,0.8,1.0,1.5,2.0}, d_x = 3b; mesh-independence (≥3 meshes),
   wake-region refinement, benchmark against a published formation case; compare ΔP with `vlm_sheet`/`vlm_rolled`. Replace the planar wake.
2. **Aircraft data**: measure C_D0, e, η_prop(J), battery curve/resistance, elevon C_lδ and trim drag, inertia; replace all `[MS]`/`[ASM]` entries.
3. **6-DOF SITL** (PX4 + Gazebo) with a wake-force plugin; rerun `run_control.py` scenarios; report solver times on the target computer.
4. **Photogrammetry**: fly or render imagery for 17@65 %, 14@58 % single-aircraft and formation acquisition over a surveyed range
   (12 GCP, ≥30 independent checkpoints), process in ODM/Metashape, report RMSE_H/V, orthomosaic, DSM residual maps. Only then fill criteria (3)–(4).
5. **Flight test**: staged (single → 2-UAV with vertical buffer → co-altitude), measured electrical power vs offset.
6. **Wildlife material** (FlockGuard, Secs. 10–14 of the preliminary document): separate paper with its own literature, ecological evaluation and welfare protocol.
