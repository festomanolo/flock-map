#!/usr/bin/env python3
"""Faithful re-implementation of the manuscript's Section 6.2 mission Monte-Carlo, used ONLY to audit it.
Everything flagged `SYNTHETIC` below is an outcome that is *assigned* rather than computed.
Run:  python audit/original_reproduction.py   ->  audit/original_reproduction_output.json"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
from scipy import stats
from flockmap import aero
from flockmap.config import AC, G


def run(n_trials=50, seed=42):
    np.random.seed(seed)
    iso_s = aero.isolated(AC.va, 0.0); iso_t = aero.isolated(AC.va, 25.0)
    foll = aero.strip_follower(3.0, 0.80, 0.0, AC.va, variant="published")
    pS, pT, pF = iso_s["p_elec"], iso_t["p_elec"], foll["p_foll"]
    pFT = pT * 1.12                                    # ASSUMED 12 % follower-turn penalty (no derivation)
    L, D = 1000.0, 2500.0
    Rt = AC.va ** 2 / (G * np.tan(np.radians(25.0))); Lt = np.pi * Rt   # semicircle of 222.6 m between 61.6 m-spaced strips
    si, so = [6, 6, 5], [5, 5, 4]
    res = {s: {m: [] for m in ("E", "Eha", "RMSEh", "RMSEv", "Acc")} for s in ("S1", "S2", "S3", "S4")}
    for _ in range(n_trials):
        env = np.random.normal(1.0, 0.02)              # the ONLY stochastic input to energy: a scalar common to all UAVs
        pi_, pf_ = pS * env, pF * env
        ttr = 2 * D / AC.va
        e1 = sum((pi_ * ttr + pi_ * (s * L / AC.va) + pT * ((s - 1) * Lt / AC.va)) / 3600 for s in si)
        acc1 = 100 * (1 - np.random.uniform(0.005, 0.015))                  # SYNTHETIC accepted area
        res["S1"]["E"].append(e1); res["S1"]["Acc"].append(acc1); res["S1"]["Eha"].append(e1 / acc1)
        res["S1"]["RMSEh"].append(np.random.normal(3.78, 0.28)); res["S1"]["RMSEv"].append(np.random.normal(5.97, 0.38))  # SYNTHETIC
        tm, tt = 17 * L / AC.va, 16 * Lt / AC.va
        e2 = (pi_ * (ttr + tm) + pT * tt) / 3600 + 2 * (pf_ * (ttr + tm) + pFT * tt) / 3600
        acc2 = 100 * (1 - np.random.uniform(0.002, 0.008))
        res["S2"]["E"].append(e2); res["S2"]["Acc"].append(acc2); res["S2"]["Eha"].append(e2 / acc2)
        res["S2"]["RMSEh"].append(np.random.normal(3.67, 0.24)); res["S2"]["RMSEv"].append(np.random.normal(5.38, 0.32))
        e3 = (pi_ * ttr + 2 * pf_ * ttr) / 3600 + sum(si) * L / AC.va * pi_ / 3600 \
            + sum(s - 1 for s in si) * Lt / AC.va * pT / 3600 + 3 * 45 * pi_ / 3600      # 45 s of FULL cruise power added on top
        acc3 = 100 * (1 - np.random.uniform(0.005, 0.012))
        res["S3"]["E"].append(e3); res["S3"]["Acc"].append(acc3); res["S3"]["Eha"].append(e3 / acc3)
        res["S3"]["RMSEh"].append(np.random.normal(3.82, 0.29)); res["S3"]["RMSEv"].append(np.random.normal(5.78, 0.36))
        e4 = (pi_ * ttr + 2 * pf_ * ttr) / 3600 + sum(so) * L / AC.va * pi_ / 3600 \
            + sum(s - 1 for s in so) * Lt / AC.va * pT / 3600 + 3 * 20 * pi_ / 3600
        acc4 = 100 * (1 - np.random.uniform(0.001, 0.005))
        res["S4"]["E"].append(e4); res["S4"]["Acc"].append(acc4); res["S4"]["Eha"].append(e4 / acc4)
        res["S4"]["RMSEh"].append(np.random.normal(3.27, 0.20)); res["S4"]["RMSEv"].append(np.random.normal(4.69, 0.28))
    return {k: {m: np.array(v) for m, v in d.items()} for k, d in res.items()}, foll, pS


def main():
    r, foll, pS = run()
    out = {"follower_power_saving_pct_published_model": foll["pct_power"]}
    for s in r:
        out[s] = {m: [float(np.mean(v)), float(np.std(v, ddof=1))] for m, v in r[s].items()}
    # statistics as in the manuscript: paired t on E/ha, S4 vs S1
    d = r["S4"]["Eha"] - r["S1"]["Eha"]
    t = stats.ttest_1samp(d, 0.0)
    out["H3_full"] = dict(mean_diff=float(d.mean()), sd=float(d.std(ddof=1)), t=float(t.statistic), p=float(t.pvalue),
                          cohen_dz=float(d.mean() / d.std(ddof=1)))
    # how much of the variance in E is real? all energy variation comes from ONE scalar draw `env` per trial
    corr = np.corrcoef(r["S1"]["E"], r["S4"]["E"])[0, 1]
    out["corr_E_S1_vs_S4_across_trials"] = float(corr)
    out["fraction_of_E_variance_from_common_scalar"] = float(corr ** 2)
    # RMSE columns: independent of anything physical
    out["rmse_columns_independent_of_energy"] = {s: float(np.corrcoef(r[s]["E"], r[s]["RMSEv"])[0, 1]) for s in r}
    # sensitivity of the 'significant' conclusion to the synthetic accepted-area draw only
    out["accepted_area_note"] = "Accepted_ha = 100*(1-U(a,b)); E/ha divides by this synthetic number."
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "original_reproduction_output.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
