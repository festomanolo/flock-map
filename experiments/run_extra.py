#!/usr/bin/env python3
"""Additional analyses (all from the same models/data as the main study):
  dz   : wake benefit over (d_y, d_z) at d_x = 3b            -> data/processed/extra_dz.npz
  kmap : net formation effect over wake effectiveness kappa x transit distance (mission simulator) -> extra_kappa_map.csv
  tor  : one-at-a-time tornado and Sobol indices of the net formation effect                         -> extra_tornado.csv, extra_sobol.csv
  skerr: saving vs station-keeping error sigma               -> extra_skerr.csv
  cov  : accepted area / strips vs side overlap and crab     -> extra_coverage.csv
  power: isolated power curve and formation saving vs speed  -> extra_power.csv
  ctl  : HOCBF margin ablation and step responses            -> extra_cbf_ablation.csv, extra_step.csv
Usage: python experiments/run_extra.py [section ...]"""
import sys, os, json, math, itertools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
from flockmap import aero, vlm, energy as E, mission as M, photo, control as C, stats as ST
from flockmap.config import AC, CAM, MIS, G
OUT = "data/processed"; os.makedirs(OUT, exist_ok=True)


def load_env_series():
    ts = np.load("data/raw/control_ts.npz")
    keys = sorted({k.split("|")[2] for k in ts.files if k.startswith("S1_turbulence|NMPC+CBF|")}, key=int)
    return [(ts[f"S1_turbulence|NMPC+CBF|{s}|ex"].astype(float), ts[f"S1_turbulence|NMPC+CBF|{s}|ey"].astype(float)) for s in keys]


def load_rc(model, t_out_max=0.5 * 2500 / 18.0):
    from run_mission import load_reconfig
    return load_reconfig(model.split("@")[0], t_out_max)


# ------------------------------------------------------------------------------------------------------------- dz
def sec_dz():
    dys = np.linspace(0.5, 1.6, 23); dzs = np.linspace(-0.6, 0.6, 13)
    out = {}
    for name, kw in (("sheet", dict(wake="sheet")), ("free", dict(wake="free"))):
        P = np.zeros((len(dzs), len(dys))); CL = np.zeros_like(P)
        for i, dz in enumerate(dzs):
            for j, dy in enumerate(dys):
                r = vlm.follower(3.0, dy, dz, 18.0, **kw); P[i, j] = r["pct_power"]; CL[i, j] = r["cl_roll"]
        out[f"pct_{name}"] = P; out[f"cl_{name}"] = CL
    np.savez(f"{OUT}/extra_dz.npz", dy=dys, dz=dzs, **out); print("dz done")


# ------------------------------------------------------------------------------------------------------------- kappa map
def mission_delta(kappa, D, rho_over=1.0, err_scale=1.0, wind=(3.0, 1.0), n_env=12, seed=5, model="vlm_sheet", wait_scale=1.0):
    series = load_env_series(); rng = np.random.default_rng(seed); cache = {}
    mname = f"{model}@{kappa}"
    rc = load_rc(model, 0.5 * D / 18.0)
    if rho_over != 1.0:
        p_iso = E.p_level(18.0)
        rc = {k: dict(T=v["T"], E_f=p_iso * v["T"] / 3600 + rho_over * (v["E_f"] - p_iso * v["T"] / 3600)) for k, v in rc.items()}
    d3, d4 = [], []
    for _ in range(n_env):
        ex, ey = series[rng.integers(len(series))]
        env = M.Env(rng.uniform(2, 6), rng.uniform(0, 2 * math.pi), (ex * err_scale, ey * err_scale))
        r = {s: M.run(s, env, mname, rc, cache, d_transit=float(D)).e_load for s in ("S1_independent", "S3_adaptive_geometric", "D1_independent_14", "S4_wake_aware")}
        d3.append(r["S1_independent"] - r["S3_adaptive_geometric"]); d4.append(r["D1_independent_14"] - r["S4_wake_aware"])
    return float(np.mean(d3)), float(np.mean(d4))


def sec_kmap():
    kap = np.round(np.arange(0.3, 1.501, 0.1), 2); Ds = [1000, 2000, 2500, 3500, 5000, 7500, 10000, 15000, 20000]
    rows = []
    for k in kap:
        for D in Ds:
            a, b = mission_delta(k, D); rows.append(dict(kappa=k, D=D, saving17_Wh=a, saving14_Wh=b))
    pd.DataFrame(rows).to_csv(f"{OUT}/extra_kappa_map.csv", index=False); print("kmap done")


# ------------------------------------------------------------------------------------------------------------- tornado / Sobol
FACT = [("wake effectiveness kappa", 0.6, 1.2, 1.0), ("reconfiguration overhead x", 0.6, 1.6, 1.0), ("station-keeping error x", 0.5, 3.0, 1.0),
        ("wind speed range centre (m/s)", 1.0, 6.0, 4.0), ("transit distance D (m)", 1500.0, 10000.0, 2500.0)]


def f_eval(x):
    kappa, rho, err, wind, D = x
    return mission_delta(kappa, D, rho_over=rho, err_scale=err, wind=(wind, 1.0), n_env=4, seed=11)[0]


def sec_tor():
    rows = []
    base = np.array([f[3] for f in FACT]); f0 = f_eval(base)
    for i, (nm, lo, hi, b) in enumerate(FACT):
        for lab, v in (("low", lo), ("high", hi)):
            x = base.copy(); x[i] = v; rows.append(dict(factor=nm, setting=lab, value=v, delta_Wh=f_eval(x) - f0, base_Wh=f0))
    pd.DataFrame(rows).to_csv(f"{OUT}/extra_tornado.csv", index=False)
    # Sobol (pick-freeze, Saltelli 2010 estimators)
    rng = np.random.default_rng(2); N = 250; d = len(FACT)
    lo = np.array([f[1] for f in FACT]); hi = np.array([f[2] for f in FACT])
    A = lo + (hi - lo) * rng.random((N, d)); B = lo + (hi - lo) * rng.random((N, d))
    fA = np.array([f_eval(a) for a in A]); fB = np.array([f_eval(b) for b in B]); V = np.var(np.r_[fA, fB], ddof=1)
    S1, ST_ = [], []
    for i in range(d):
        ABi = A.copy(); ABi[:, i] = B[:, i]; fAB = np.array([f_eval(x) for x in ABi])
        S1.append(np.mean(fB * (fAB - fA)) / V); ST_.append(0.5 * np.mean((fA - fAB) ** 2) / V)
    pd.DataFrame(dict(factor=[f[0] for f in FACT], S1=S1, ST=ST_, var=V)).to_csv(f"{OUT}/extra_sobol.csv", index=False); print("tornado/sobol done")


# ------------------------------------------------------------------------------------------------------------- station-keeping error
def sec_skerr():
    """Expected follower electrical-power saving under Gaussian lateral error N(0, sigma_y^2).
    Evaluates the static saving curve on the Lifanov Cauchy-midpoint lattice dy/b = m/n (m = 0..150, n = 60 panels)
    so collocation points never land on singular 1/r trailing vortex filaments, then integrates via 61-point
    Gauss-Hermite quadrature."""
    rows = []
    n_pan = 60
    xg, wg = np.polynomial.hermite.hermgauss(61)
    wg = wg / np.sqrt(np.pi)
    for model, kw in (("vlm_sheet", dict(wake="sheet")), ("vlm_free", dict(wake="free")), ("strip_corrected", None)):
        g_abs = np.arange(0, 51) * 0.05 if model == "vlm_free" else np.arange(0, int(2.5 * n_pan) + 1) / float(n_pan)
        curve = np.array([
            (vlm.follower(3.0, float(d), 0.0, 18.0, n=n_pan, **kw)["pct_power"] if kw
             else aero.strip_follower(3.0, float(d), 0.0, 18.0, variant="corrected")["pct_power"])
            for d in g_abs
        ])
        for dyb in (0.80, 0.85, 0.90):
            for sig in (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.60):
                z = rng.standard_normal(60) * sig if sig > 0 else np.zeros(1)
                vals = [(vlm.follower(3.0, dyb, 0.0, 18.0, y_err=e, **kw)["pct_power"] if kw else aero.strip_follower(3.0, dyb, 0.0, 18.0, variant="corrected", y_err=e)["pct_power"]) for e in z]
                rows.append(dict(model=model, dy_b=dyb, sigma_m=sig, saving_pct=float(np.mean(vals))))
    pd.DataFrame(rows).to_csv(f"{OUT}/extra_skerr.csv", index=False); print("skerr done")


# ------------------------------------------------------------------------------------------------------------- coverage
def sec_cov():
    rows = []
    for os_ in np.round(np.arange(0.50, 0.701, 0.01), 2):
        sp = CAM.Wg * (1 - os_); n = math.ceil(MIS.side / sp)
        for crab in (0.0, 3.0, 6.0, 12.0, 19.0):
            c = photo.strip_centres(n, sp); cr = math.radians(crab)
            m = photo.multiplicity_map(c, None, crab=[cr if i % 2 == 0 else -cr for i in range(n)])
            acc, cov, d = photo.accepted_area(m)
            rows.append(dict(side_overlap=os_, spacing=sp, n_strips=n, crab_deg=crab, accepted_ha=acc, coverage=cov, min_mult=int(m.min()), mean_mult=float(m.mean()),
                             track_km=n * MIS.side / 1000.0, BH=sp / CAM.agl))
    pd.DataFrame(rows).to_csv(f"{OUT}/extra_coverage.csv", index=False); print("cov done")


# ------------------------------------------------------------------------------------------------------------- power curve
def sec_power():
    rows = []
    for v in np.linspace(12, 26, 57):
        iso = aero.isolated(float(v)); r_s = vlm.follower(3.0, 0.85, 0.0, float(v), wake="sheet"); r_f = vlm.follower(3.0, 0.85, 0.0, float(v), wake="free")
        r_c = aero.strip_follower(3.0, 0.85, 0.0, float(v), variant="corrected")
        rows.append(dict(va=v, cl=iso["cl"], ld=iso["cl"] / iso["cd"], p_aero=iso["p_aero"], p_elec=iso["p_elec"], e_per_km_Wh=iso["p_elec"] / v * 1000 / 3600,
                         sav_sheet=r_s["pct_power"], sav_free=r_f["pct_power"], sav_strip=r_c["pct_power"], cdi_share=100 * iso["cdi"] / iso["cd"]))
    pd.DataFrame(rows).to_csv(f"{OUT}/extra_power.csv", index=False); print("power done")


# ------------------------------------------------------------------------------------------------------------- control extras
def _cbf_job(a):
    from run_control import scenarios
    name, margin, seed = a
    rng = np.random.default_rng(10_000 + seed); sc = scenarios(rng)[name]
    r = C.simulate(sc, "NMPC+CBF", seed=seed, d_eff_extra=margin)
    tab = E.table("vlm_sheet", 18.0); sav = float(np.mean(tab(r["dx"], r["dy"])))
    return dict(scenario=name, margin=margin, seed=seed, rms_ey=float(np.sqrt(np.mean(r["ey"] ** 2))), min_sep=float(r["dist"].min()), violated=int((r["h"] < 0).any()),
                active=r["meta"]["cbf_active_frac"], mean_dcd=sav)


def _step_job(a):
    ctl, seed = a
    sc = C.Scenario("step", 40.0, 0.0, 0.0, sigma_ind=0.0, rtk_sigma=0.0, delay=0.0, slot=(6.36, 1.70), slot_sched=((5.0, 0.4, 6.36, 2.70),))
    r = C.simulate(sc, ctl, seed=seed); t = r["t"]; e = r["dy"] - 1.70
    y = e / 1.0; i0 = np.searchsorted(t, 5.0)
    post = y[i0:]; tt = t[i0:] - 5.0
    over = max(0.0, float(post.max() - 1.0)) * 100
    idx = np.where(np.abs(post - 1.0) > 0.02)[0]; ts = float(tt[idx[-1]]) if len(idx) else 0.0
    r10 = float(tt[np.argmax(post >= 0.1)]); r90 = float(tt[np.argmax(post >= 0.9)]) if (post >= 0.9).any() else np.nan
    return dict(controller=ctl, overshoot_pct=over, settle2_s=ts, rise_s=r90 - r10, max_bank=float(np.abs(r["phi"]).max()))


def sec_ctl():
    from multiprocessing import Pool
    jobs = [(n, m, s) for n in ("S3_braking_dropout", "S5_combined", "S6_overcapability") for m in (0.0, 0.5, 1.0, 2.0) for s in range(16)]
    with Pool(1) as p: res = p.map(_cbf_job, jobs)
    pd.DataFrame(res).to_csv(f"{OUT}/extra_cbf_ablation.csv", index=False)
    with Pool(1) as p: st = p.map(_step_job, [(c, s) for c in ("P", "NMPC", "NMPC+CBF") for s in range(3)])
    pd.DataFrame(st).to_csv(f"{OUT}/extra_step.csv", index=False); print("ctl done")


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["dz", "skerr", "cov", "power", "kmap", "tor", "ctl"]):
        globals()["sec_" + s]()
