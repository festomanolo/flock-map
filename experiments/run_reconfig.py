#!/usr/bin/env python3
"""Formation split / merge manoeuvres simulated with the NMPC; energy integrated with the full power model."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
from multiprocessing import Pool
from flockmap import control as C, energy as E

YS = [60.0, 369.6, 370.0]
T0, SETTLE = 5.0, 5.0                 # start of move [s], settling [s]
VLATS = [3.0, 4.0, 6.0, 8.0, 12.0]    # peak lateral velocity menu [m/s]
NSEED = 6


def job(a):
    kind, Y, vlat, seed = a
    T = max(10.0, 1.875 * Y / vlat)
    rng = np.random.default_rng(777 + seed)
    wind, wdir = rng.uniform(2, 6), rng.uniform(0, 2 * math.pi)
    if kind == "split":
        sc = C.Scenario("reconf", T0 + T + SETTLE + 5, wind, wdir, slot=(6.36, 1.70), slot_sched=((T0, T, 6.36, Y),))
    else:
        sc = C.Scenario("reconf", T0 + T + SETTLE + 5, wind, wdir, slot=(6.36, Y), slot_sched=((T0, T, 6.36, 1.70),))
    r = C.simulate(sc, "NMPC", seed=seed)
    ts = {k: r[k] for k in ("t", "V", "phi", "dx", "dy")}
    out = {}
    for m in E.AERO_MODELS:
        e, w = E.reconfig_energy(ts, T0, T0 + T + SETTLE, m)
        out[m] = (e, w)
    return kind, Y, vlat, seed, T + SETTLE, out, float(np.abs(r["phi"]).max()), float(np.abs(r["ey"][(r["t"] > T0 + T + SETTLE)]).mean())


if __name__ == "__main__":
    jobs = [(k, Y, v, s) for k in ("split", "merge") for Y in YS for v in VLATS for s in range(NSEED)]
    with Pool(4) as p:
        res = p.map(job, jobs)
    tab = {}
    for kind, Y, vlat, seed, W, out, maxphi, resid in res:
        for m, (e, w) in out.items():
            tab.setdefault(f"{kind}|{Y}|{vlat}|{m}", []).append((e, w, maxphi, resid))
    summ = {}
    for k, v in tab.items():
        v = np.array(v)
        summ[k] = dict(E_f=float(v[:, 0].mean()), E_f_sd=float(v[:, 0].std(ddof=1)), T=float(v[:, 1].mean()),
                       max_bank_deg=float(v[:, 2].mean()), settle_err_m=float(v[:, 3].mean()), n=len(v))
    os.makedirs("data/processed", exist_ok=True)
    json.dump(summ, open("data/processed/reconfig.json", "w"), indent=1)
    for k in sorted(summ):
        if k.endswith("vlm_sheet") and k.startswith("split|369.6"):
            p = E.p_level(18.0); print(k, {a: round(b, 3) for a, b in summ[k].items() if a in ("E_f","T","max_bank_deg")}, "overhead vs iso cruise Wh:", round(summ[k]["E_f"] - p * summ[k]["T"] / 3600, 3))
