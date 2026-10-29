#!/usr/bin/env python3
"""Free-wake runs: (a) fine wake (dt=0.02 s, 0.36 m rows, ~38 m long) used for follower evaluation at 2-6 b;
(b) coarse far-wake run (dt=0.06 s, ~1.1 m rows, ~120 m) to quantify roll-up distance.  Outputs data/processed/freewake_*.npz"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
from flockmap.freewake import FreeWake

os.makedirs("data/processed", exist_ok=True)
for name, dt, K, steps in (("far", 0.06, 110, 125), ("fine", 0.02, 110, 130)):
    t0 = time.time(); fw = FreeWake(n_span=24, dt=dt, n_rows=K); fw.run(steps)
    fw.save(f"data/processed/freewake_{name}.npz")
    tr = fw.vortex_track()
    print(name, "lift/W %.4f" % (fw.lift() / fw.L), "rows", len(fw.rows), "%.0fs" % (time.time() - t0), flush=True)
    np.save(f"data/processed/freewake_{name}_track.npy", tr)
    b0_th = np.pi / 4 * fw.ac.b
    for x in (5, 10, 20, 40, 80, 110):
        k = np.argmin(np.abs(tr[:, 0] - x))
        if abs(tr[k, 0] - x) < 3: print("  x=%.0f m (%.0f b): vortex spacing %.3f m (theory rolled %.3f), z %.3f, gamma %.3f" % (tr[k, 0], tr[k, 0] / fw.ac.b, 2 * tr[k, 1], b0_th, tr[k, 2], tr[k, 3]), flush=True)
