#!/usr/bin/env python3
"""Showcase trajectories (absolute positions) for the 3-D renders: S3 braking+dropout for the three controllers, the
S5 combined case, and a 370 m split manoeuvre.  Same simulator and parameters as the control campaign."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
from flockmap import control as C
sys.path.insert(0, os.path.dirname(__file__))
from run_control import scenarios

out = {}
for name, seed in (("S3_braking_dropout", 4), ("S5_combined", 0), ("S6_overcapability", 1)):
    sc = scenarios(np.random.default_rng(10_000 + seed))[name]
    for ctl in ("P", "NMPC", "NMPC+CBF"):
        r = C.simulate(sc, ctl, seed=seed)
        for k in ("t", "pfx", "pfy", "plx", "ply", "chi", "phi", "V", "dx", "dy", "dist", "h"):
            out[f"{name}|{ctl}|{k}"] = r[k].astype(np.float64)
sc = C.Scenario("split", 125.0, 3.0, 1.0, slot=(6.36, 1.70), slot_sched=((5.0, 62.7, 6.36, 369.6),))
for sgn, nm in ((1, "R"), (-1, "L")):
    pass
r = C.simulate(sc, "NMPC", seed=1)
for k in ("t", "pfx", "pfy", "plx", "ply", "chi", "phi", "V", "dx", "dy"):
    out[f"split|NMPC|{k}"] = r[k].astype(np.float64)
np.savez_compressed("data/raw/cases3d.npz", **out)
print("saved", len(out))
