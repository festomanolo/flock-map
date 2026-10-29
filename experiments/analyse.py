#!/usr/bin/env python3
"""All reported numbers derive from data/raw/*.csv through this script."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
from flockmap import stats as ST

OUT = "data/processed"
df = pd.read_csv("data/raw/mission_trials.csv")
PAIRS = [("S4_wake_aware", "S1_independent", "A: S4 vs S1 (full framework)"),
         ("S3_adaptive_geometric", "S1_independent", "B: S3 vs S1 (formation transit only, same 17-strip route)"),
         ("S2_rigid_V", "S1_independent", "C: S2 vs S1 (rigid V)"),
         ("S3_adaptive_geometric", "S2_rigid_V", "D: S3 vs S2 (adaptive vs rigid)"),
         ("S4_wake_aware", "D1_independent_14", "E: S4 vs D1 (formation effect, same 14-strip route)"),
         ("D1_independent_14", "S1_independent", "F: D1 vs S1 (route/overlap effect, no formation)")]
rows = []; summ = []
for model, g in df.groupby("model"):
    piv = {m: g.pivot(index="trial", columns="strategy", values=m) for m in ("e_load_Wh", "e_area_Wh_ha", "t_end_min", "e_cell_Wh")}
    for s in g.strategy.unique():
        for m in piv:
            v = piv[m][s].values
            summ.append(dict(model=model, strategy=s, metric=m, mean=v.mean(), sd=v.std(ddof=1), p05=np.percentile(v, 5), p95=np.percentile(v, 95)))
        summ.append(dict(model=model, strategy=s, metric="accepted_ha", mean=g[g.strategy == s].accepted_ha.mean(), sd=g[g.strategy == s].accepted_ha.std(ddof=1), p05=np.nan, p95=np.nan))
        summ.append(dict(model=model, strategy=s, metric="feasible_frac", mean=g[g.strategy == s].feasible.mean(), sd=np.nan, p05=np.nan, p95=np.nan))
    for metric in ("e_area_Wh_ha", "e_load_Wh", "t_end_min"):
        fam = []
        for a, b, label in PAIRS:
            r = ST.paired(piv[metric][a].values, piv[metric][b].values); r.update(model=model, metric=metric, comparison=label); fam.append(r)
        adj = ST.holm([r["p_t"] if r["p_t"] == r["p_t"] else 1.0 for r in fam])
        for r, p in zip(fam, adj): r["p_t_holm"] = p
        rows += fam
pd.DataFrame(summ).to_csv(f"{OUT}/strategy_summary.csv", index=False)
pt = pd.DataFrame(rows); pt.to_csv(f"{OUT}/paired_tests.csv", index=False)

# factorial decomposition of the S1 -> S4 energy difference (load-side Wh), per model
dec = []
for model, g in df.groupby("model"):
    p = g.pivot(index="trial", columns="strategy", values="e_load_Wh")
    aero_ = p.S1_independent - p.S3_adaptive_geometric          # formation transit alone (17 strips)
    plan_ = p.S1_independent - p.D1_independent_14              # route/overlap alone (no formation)
    both = p.S1_independent - p.S4_wake_aware
    inter = both - aero_ - plan_
    for name, v in (("formation transit only", aero_), ("route/overlap only", plan_), ("interaction", inter), ("total (S4 vs S1)", both)):
        rng = np.random.default_rng(5); idx = rng.integers(0, len(v), (10000, len(v))); bm = v.values[idx].mean(1)
        dec.append(dict(model=model, component=name, saving_Wh=v.mean(), ci_lo=np.percentile(bm, 2.5), ci_hi=np.percentile(bm, 97.5),
                        saving_pct=100 * v.mean() / p.S1_independent.mean()))
pd.DataFrame(dec).to_csv(f"{OUT}/decomposition.csv", index=False)
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
m = "vlm_sheet"
print(pt[(pt.model == m) & (pt.metric == "e_area_Wh_ha")][["comparison", "mean_a", "mean_b", "mean_diff", "ci_lo", "ci_hi", "rel_change_pct", "p_t_holm", "p_wilcoxon", "dz"]].round(4).to_string())
print(pd.DataFrame(dec).query("model=='vlm_sheet'").round(3).to_string())
print(pd.DataFrame(summ).query("model=='vlm_sheet' and metric in ['e_load_Wh','accepted_ha','t_end_min','feasible_frac']").round(2).to_string())
