#!/usr/bin/env python3
"""Break-even and sensitivity analyses.
 (a) mission-simulator sweep over one-way transit distance (paired S3-S1, S4-D1);
 (b) analytic break-even surface net(D, T_reconf) with the reconfiguration energy-vs-time law taken from the simulations;
 (c) global sensitivity (standardised regression coefficients) of the net formation effect."""
import sys, os, json, math, dataclasses
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
from flockmap import mission as M, energy as E, aero, stats as ST
from flockmap.config import AC, WK
sys.path.insert(0, os.path.dirname(__file__))
from run_mission import load_reconfig

OUT = "data/processed"
ts = np.load("data/raw/control_ts.npz")
keys = sorted({k.split("|")[2] for k in ts.files if k.startswith("S1_turbulence|NMPC+CBF|")}, key=int)
series = [(ts[f"S1_turbulence|NMPC+CBF|{s}|ex"].astype(float), ts[f"S1_turbulence|NMPC+CBF|{s}|ey"].astype(float)) for s in keys]

# ---- (a) distance sweep -------------------------------------------------------------------------------------
rng = np.random.default_rng(99); cache = {}
rows = []
DS = [1000, 1500, 2000, 2500, 3500, 5000, 7500, 10000, 15000, 20000]
envs = [M.Env(rng.uniform(2, 6), rng.uniform(0, 2 * math.pi), series[rng.integers(len(series))]) for _ in range(60)]
for model in ("vlm_sheet", "vlm_free", "strip_corrected", "published"):
    for D in DS:
        rc = load_reconfig(model, t_out_max=0.5 * D / 18.0)
        for i, env in enumerate(envs):
            r = {s: M.run(s, env, model, rc, cache, d_transit=float(D)) for s in ("S1_independent", "S3_adaptive_geometric", "D1_independent_14", "S4_wake_aware")}
            rows.append(dict(model=model, D=D, trial=i, **{f"E_{s}": r[s].e_load for s in r},
                             aero17=r["S1_independent"].e_load - r["S3_adaptive_geometric"].e_load,
                             aero14=r["D1_independent_14"].e_load - r["S4_wake_aware"].e_load))
df = pd.DataFrame(rows); df.to_csv(f"{OUT}/breakeven_distance.csv", index=False)
print(df.groupby(["model", "D"])[["aero17", "aero14"]].mean().round(2).unstack(0).to_string())

# ---- (b) analytic surface net(D, T) --------------------------------------------------------------------------
j = json.load(open("data/processed/reconfig.json"))
def over_curve(model):
    pts = []
    for k, v in j.items():
        kind, Y, vl, m = k.split("|")
        if m == model and float(Y) == 369.6 and kind in ("split", "merge"):
            pts.append((v["T"], v["E_f"] - E.p_level(18.0) * v["T"] / 3600.0))
    pts = np.array(sorted(pts)); T = np.unique(pts[:, 0])
    ov = np.array([pts[pts[:, 0] == t, 1].mean() for t in T])
    return T, ov
Ds = np.linspace(1, 20, 39) * 1000; Ts = np.linspace(60, 240, 37)
surf = {}
for model in ("vlm_sheet", "strip_corrected"):
    Tc, ovc = over_curve(model)
    p_iso, p_fol = E.p_level(18.0), E.p_follower_steady(model)
    N = np.zeros((len(Ts), len(Ds)))
    for a, T in enumerate(Ts):
        ov = float(np.interp(T, Tc, ovc))
        for b, D in enumerate(Ds):
            t_tr = 2 * D / 18.0
            net_f = (p_iso - p_fol) * max(t_tr - 2 * T, 0.0) / 3600.0 - 2 * ov
            N[a, b] = 2 * net_f
    surf[model] = N
np.savez(f"{OUT}/breakeven_surface.npz", D=Ds, T=Ts, **surf)

# ---- (c) global sensitivity ---------------------------------------------------------------------------------
rng = np.random.default_rng(3); n = 3000
X = np.zeros((n, 6)); y = np.zeros(n)
Tc, ovc = over_curve("strip_corrected")
for i in range(n):
    D = rng.uniform(1000, 20000); T = rng.uniform(60, 240); va = rng.uniform(13, 24)
    nu = 10 ** rng.uniform(-3, -2); g = rng.normal(1, 0.15); wind = rng.uniform(0, 8)
    wk = dataclasses.replace(WK, nu_eff=nu)
    r = aero.strip_follower(3.0, 0.85, 0.0, va, variant="corrected", wk=wk, gamma_scale=g)
    dP = r["p_iso"] - r["p_foll"]
    vg = max(va - wind * 0.0, 5.0)
    t_tr = 2 * D / va
    ov = float(np.interp(T, Tc, ovc))
    y[i] = 2 * (dP * max(t_tr - 2 * T, 0) / 3600.0 - 2 * ov)
    X[i] = [D, T, va, nu, g, wind]
beta, r2 = ST.src(X, y)
pd.DataFrame(dict(factor=["transit distance D", "reconfiguration time T", "airspeed Va", "eddy viscosity nu_eff", "wake circulation scale", "wind speed (dummy)"],
                  src=beta, abs_src=np.abs(beta))).assign(r2=r2).to_csv(f"{OUT}/sensitivity_src.csv", index=False)
print("SRC", dict(zip(["D", "T", "Va", "nu", "gamma", "wind"], beta.round(3))), "R2", round(r2, 3))
