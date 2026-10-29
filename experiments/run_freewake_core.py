#!/usr/bin/env python3
"""Sensitivity of the free-wake follower saving to the (uncalibrated) vortex-core radius r_c0 and to panel count."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
from flockmap.freewake import FreeWake
from flockmap import vlm
res = []
for n, rc in ((24, 0.02), (24, 0.05), (24, 0.10), (36, 0.03)):
    fw = FreeWake(n_span=n, dt=0.03, n_rows=60, rc0_frac=rc).run(60)
    vlm._FW["fw"] = fw
    row = dict(n_span=n, rc0_frac=rc, **{f"pct_{dy}": float(vlm.follower(3.0, dy, wake="free", n=60)["pct_power"]) for dy in (0.7, 0.8, 0.9, 1.0)})
    res.append(row); print(row, flush=True)
json.dump(res, open("data/processed/freewake_core_sensitivity.json", "w"), indent=1)
