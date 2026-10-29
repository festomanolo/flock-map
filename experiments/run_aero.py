#!/usr/bin/env python3
"""Aerodynamic experiments: model comparison, manuscript-table audit, (dx,dy) map, airspeed scaling,
VLM verification, and parametric/epistemic uncertainty propagation."""
import sys, os, json, dataclasses
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
from flockmap import aero, vlm
from flockmap.config import AC, WK, G

OUT = "data/processed"; os.makedirs(OUT, exist_ok=True)
DY = np.round(np.concatenate([np.arange(0.5, 1.51, 0.05), [1.75, 2.0, 2.5]]), 3)

# ---- 1. lateral sweep, all models ---------------------------------------------------------------------------
rows = []
for dy in DY:
    for name, f in (("published", lambda d: aero.strip_follower(3.0, d, variant="published")),
                    ("strip_corrected", lambda d: aero.strip_follower(3.0, d, variant="corrected")),
                    ("vlm_analytic", lambda d: vlm.follower(3.0, d, wake="analytic")),
                    ("vlm_rolled", lambda d: vlm.follower(3.0, d, wake="rolled")),
                    ("vlm_sheet", lambda d: vlm.follower(3.0, d, wake="sheet")),
                    ("vlm_free", lambda d: vlm.follower(3.0, d, wake="free"))):
        r = f(dy); rows.append(dict(model=name, dy_b=dy, pct_power=r["pct_power"], pct_drag=r["pct_drag"], cl_roll=r["cl_roll"],
                                    elevon_deg=r["elevon_deg"], p_foll=r["p_foll"], p_iso=r["p_iso"], dcd_net=r["dcd_net"]))
pd.DataFrame(rows).to_csv(f"{OUT}/aero_sweep_dy.csv", index=False)

# ---- 2. manuscript table vs its own equations ---------------------------------------------------------------
tab = {0.50: (-0.1200, 0.1298, -81.38), 0.70: (0.0526, 0.0722, -22.00), 0.75: (0.1412, 0.0241, 2.35), 0.80: (0.1748, 0.0054, 6.05),
       0.85: (0.1715, -0.0048, 5.95), 0.90: (0.1541, -0.0092, 5.06), 1.00: (0.1149, -0.0098, 3.62), 1.25: (0.0588, -0.0049, 1.97),
       1.50: (0.0355, -0.0024, 1.24), 2.00: (0.0178, -0.0008, 0.62), 2.50: (0.0108, -0.0004, 0.39)}
rows = []
for k, (w, cl, pp) in tab.items():
    r = aero.strip_follower(3.0, k, variant="published")
    rows.append(dict(dy_b=k, w_table=w, w_recomputed=r["w_mean"], cl_table=cl, cl_recomputed=r["cl_roll"],
                     pct_table=pp, pct_recomputed=r["pct_power"], w_match=abs(w - r["w_mean"]) < 5e-4))
pd.DataFrame(rows).to_csv(f"{OUT}/audit_table33.csv", index=False)

# ---- 3. (dx, dy) map -----------------------------------------------------------------------------------------
dxs = np.linspace(1.5, 6.0, 19); dys = np.linspace(0.5, 1.6, 45)
P = np.zeros((len(dxs), len(dys))); CL = np.zeros_like(P)
for i, dx in enumerate(dxs):
    for j, dy in enumerate(dys):
        r = vlm.follower(dx, dy, wake="sheet"); P[i, j] = r["p_foll"] - r["p_iso"]; CL[i, j] = r["cl_roll"]
np.savez(f"{OUT}/aero_map_dxdy.npz", dx=dxs, dy=dys, dP=P, cl=CL)

# ---- 4. airspeed scaling (matched airspeed, own isolated baseline) -------------------------------------------
rows = []
for va in (13, 15, 18, 21, 24):
    iso = aero.isolated(va)
    for name, f in (("published", lambda: aero.strip_follower(3.0, 0.80, va=va, variant="published")),
                    ("strip_corrected", lambda: aero.strip_follower(3.0, 0.85, va=va, variant="corrected")),
                    ("vlm_sheet", lambda: vlm.follower(3.0, 0.85, va=va, wake="sheet")),
                    ("vlm_free", lambda: vlm.follower(3.0, 0.85, va=va, wake="free"))):
        r = f(); rows.append(dict(model=name, va=va, cdi_share=100 * iso["cdi"] / iso["cd"], pct_drag=r["pct_drag"],
                                  pct_power=r["pct_power"], p_iso=iso["p_elec"], p_foll=r["p_foll"]))
pd.DataFrame(rows).to_csv(f"{OUT}/aero_airspeed.csv", index=False)

# ---- 5. VLM verification ------------------------------------------------------------------------------------
q = 0.5 * AC.rho * 18 ** 2; L = AC.mass * G; cl = L / (q * AC.S)
rows = []
for n in (10, 20, 40, 60, 80, 120):
    W = vlm.Wing(AC, n); s = W.isolated(18.0, L)
    cdi = s["drag_i"] / (q * AC.S)
    rows.append(dict(n=n, e_oswald=cl ** 2 / (np.pi * AC.AR * cdi), cl_alpha=cl / s["alpha"]))
v = pd.DataFrame(rows); v["helmbold_cl_alpha"] = 2 * np.pi * AC.AR / (2 + np.sqrt(4 + AC.AR ** 2)); v["prandtl_ll_cl_alpha"] = AC.cl_alpha_3d
v.to_csv(f"{OUT}/vlm_verification.csv", index=False)

# ---- 6. uncertainty propagation (parametric + station keeping), strip-corrected model -----------------------
rng = np.random.default_rng(7); NS = 3000
samples = []
for i in range(NS):
    ac = dataclasses.replace(AC, cd0=AC.cd0 * rng.uniform(0.9, 1.1), e0=rng.uniform(0.70, 0.90), eta_prop=rng.uniform(0.60, 0.75),
                             p_hotel=AC.p_hotel * rng.uniform(0.8, 1.2), k_trim=AC.k_trim * rng.uniform(0.5, 2.0))
    wk = dataclasses.replace(WK, nu_eff=10 ** rng.uniform(-3, -2), rc0_frac=rng.uniform(0.03, 0.08))
    samples.append((ac, wk, rng.normal(1.0, 0.15), rng.normal(0.0, 0.15)))
res = []
for va in range(13, 25):
    for dy in (0.80, 0.85, 0.90):
        vals = [aero.strip_follower(3.0 + rng.normal(0, 0.1), dy, 0.0, float(va), variant="corrected", ac=ac, wk=wk, gamma_scale=g,
                                    y_err=ye)["pct_power"] for (ac, wk, g, ye) in samples[:600]]
        res.append(dict(va=va, dy_b=dy, mean=np.mean(vals), p05=np.percentile(vals, 5), p50=np.median(vals), p95=np.percentile(vals, 95)))
pd.DataFrame(res).to_csv(f"{OUT}/aero_uncertainty_airspeed.csv", index=False)
res = []
for dy in DY[DY <= 1.6]:
    vals = [aero.strip_follower(3.0, dy, 0.0, 18.0, variant="corrected", ac=ac, wk=wk, gamma_scale=g, y_err=ye)["pct_power"]
            for (ac, wk, g, ye) in samples[:600]]
    res.append(dict(dy_b=dy, mean=np.mean(vals), p05=np.percentile(vals, 5), p50=np.median(vals), p95=np.percentile(vals, 95)))
pd.DataFrame(res).to_csv(f"{OUT}/aero_uncertainty_dy.csv", index=False)
print("aero experiments done")
print(pd.DataFrame(rows).head(0))
print(pd.read_csv(f"{OUT}/aero_airspeed.csv").round(2).to_string())
print(v.round(3).to_string())
