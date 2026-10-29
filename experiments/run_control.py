#!/usr/bin/env python3
"""Control campaign: 6 scenarios x 3 controllers x N paired trials (same seed => same disturbance realisation).
Writes data/raw/control_trials.csv (one row per run) and data/raw/control_ts.npz (time series of every run)."""
import sys, os, json, time, itertools, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
from multiprocessing import Pool
from flockmap import control as C

N = int(os.environ.get("N_CONTROL", 30))
DUR = 40.0
CTRL = ["P", "NMPC", "NMPC+CBF"]


def scenarios(rng):
    wind = rng.uniform(2.0, 6.0); wdir = rng.uniform(0, 2 * np.pi)
    S = {
     "S1_turbulence": C.Scenario("S1_turbulence", DUR, wind, wdir),
     "S2_gust_doublet": C.Scenario("S2_gust_doublet", DUR, wind, wdir, doublet=8.5),
     "S3_braking_dropout": C.Scenario("S3_braking_dropout", DUR, wind, wdir, leader_decel=((15.0, 3.0, -4.0),),
                                      dropouts=((15.0, 0.25),), delay=0.15),
     "S4_degraded_gnss": C.Scenario("S4_degraded_gnss", DUR, wind, wdir, rtk_sigma=0.5, rtk_bias=1.5),
     "S5_combined": C.Scenario("S5_combined", DUR, wind, wdir, doublet=8.5, sigma_ind=0.8,
                               leader_decel=((15.0, 3.0, -4.0),), dropouts=((15.0, 0.25),), delay=0.25,
                               rtk_sigma=0.3, rtk_bias=0.5),
     "S6_overcapability": C.Scenario("S6_overcapability", DUR, wind, wdir, leader_decel=((15.0, 1.5, -6.0),),
                                     dropouts=((15.0, 0.5),), delay=0.25),
    }
    return S


def job(args):
    name, ctrl, seed = args
    rng = np.random.default_rng(10_000 + seed)
    sc = scenarios(rng)[name]
    r = C.simulate(sc, ctrl, seed=seed)
    ey, ex = r["ey"], r["ex"]
    row = dict(scenario=name, controller=ctrl, seed=seed, wind=sc.wind, wind_dir=sc.wind_dir,
               rms_ey=float(np.sqrt(np.mean(ey ** 2))), rms_ex=float(np.sqrt(np.mean(ex ** 2))),
               max_abs_ey=float(np.abs(ey).max()), max_abs_ex=float(np.abs(ex).max()),
               min_sep=float(r["dist"].min()), n_violation_samples=int((r["h"] < 0).sum()),
               violated=int((r["h"] < 0).any()), max_bank_deg=float(np.abs(r["phi"]).max()),
               **{k: v for k, v in r["meta"].items() if k not in ("controller", "scenario", "seed")})
    ts = {k: r[k].astype(np.float32) for k in ("t", "ex", "ey", "dist", "phi", "V", "dx", "dy", "u_phi", "u_a", "cbf_active")}
    return row, (name, ctrl, seed, ts)


if __name__ == "__main__":
    jobs = [(n, c, s) for s in range(N) for n in scenarios(np.random.default_rng(0)).keys() for c in CTRL]
    t0 = time.time()
    with Pool(4) as p:
        res = p.map(job, jobs, chunksize=4)
    df = pd.DataFrame([r[0] for r in res])
    os.makedirs("data/raw", exist_ok=True)
    df.to_csv("data/raw/control_trials.csv", index=False)
    pack = {}
    for _, (n, c, s, ts) in res:
        for k, v in ts.items():
            pack[f"{n}|{c}|{s}|{k}"] = v
    np.savez_compressed("data/raw/control_ts.npz", **pack)
    print("done", len(df), "runs in %.0fs" % (time.time() - t0))
    print(df.groupby(["scenario", "controller"])[["rms_ey", "min_sep", "violated", "cbf_active_frac", "cbf_infeasible"]].mean().round(3))
