#!/usr/bin/env python3
"""Paired mission Monte Carlo.  One trial = one environment realisation (wind speed U(2,6), direction U(0,2pi),
one recorded station-keeping series bootstrapped from the control campaign).  Every strategy and aero model is
evaluated on the SAME realisation, so trial-wise differences are the paired outcomes."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
from flockmap import mission as M, energy as E

N = int(os.environ.get("N_MISSION", 200))
SEED = 20260101


def load_reconfig(model, t_out_max=0.5 * 2500 / 18.0):
    """Planner picks, for each manoeuvre, the peak lateral velocity that minimises the follower's energy overhead
    relative to remaining in formation, subject to the window taking <= 50 % of a one-way transit."""
    j = json.load(open("data/processed/reconfig.json"))
    p_fol = E.p_follower_steady(model)
    best = {}
    fastest = {}
    for k, v in j.items():
        kind, Y, vlat, m = k.split("|")
        if m != model: continue
        key = (kind, float(Y))
        if key not in fastest or v["T"] < fastest[key]["T"]:
            fastest[key] = dict(T=v["T"], E_f=v["E_f"], vlat=float(vlat))
        if v["T"] > t_out_max: continue
        over = v["E_f"] - p_fol * v["T"] / 3600.0
        key = (kind, float(Y))
        if key not in best or over < best[key][0]:
            best[key] = (over, dict(T=v["T"], E_f=v["E_f"], vlat=float(vlat)))
    out = dict(fastest)           # fall back to the fastest simulated manoeuvre when the transit is too short
    out.update({k: v[1] for k, v in best.items()})
    return out


if __name__ == "__main__":
    ts = np.load("data/raw/control_ts.npz")
    keys = sorted({k.split("|")[2] for k in ts.files if k.startswith("S1_turbulence|NMPC+CBF|")}, key=int)
    series = [(ts[f"S1_turbulence|NMPC+CBF|{s}|ex"].astype(float), ts[f"S1_turbulence|NMPC+CBF|{s}|ey"].astype(float)) for s in keys]
    rng = np.random.default_rng(SEED)
    rcs = {m: load_reconfig(m) for m in E.AERO_MODELS}
    cache = {}
    rows = []
    for trial in range(N):
        env = M.Env(wind=rng.uniform(2, 6), wind_dir=rng.uniform(0, 2 * math.pi), err_series=series[rng.integers(len(series))])
        for model in E.AERO_MODELS:
            for strat in M.STRATEGIES:
                r = M.run(strat, env, model, rcs[model], cache)
                row = dict(trial=trial, model=model, strategy=strat, wind=env.wind, wind_dir=env.wind_dir,
                           e_load_Wh=r.e_load, e_cell_Wh=r.e_cell, t_end_min=r.t_end_min, accepted_ha=r.accepted_ha,
                           coverage=r.coverage, feasible=int(r.feasible), n_strips=r.n_strips, saving_frac=r.saving_frac,
                           e_area_Wh_ha=r.e_load / max(r.accepted_ha, 1e-9), e_uav_max_Wh=max(r.e_uav),
                           e_uav_min_Wh=min(r.e_uav))
                row.update({f"ph_{k}": v for k, v in r.phases.items()})
                rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv("data/raw/mission_trials.csv", index=False)
    print(df[df.model == "vlm_sheet"].groupby("strategy")[["e_load_Wh", "e_cell_Wh", "t_end_min", "accepted_ha", "e_area_Wh_ha", "feasible"]].mean().round(3))
