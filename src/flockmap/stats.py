"""Paired-trial statistics computed from raw per-trial CSVs.  No number in the manuscript is typed by hand;
every table cell is produced by `experiments/analyse.py` through these functions."""
from __future__ import annotations
import numpy as np
from scipy import stats


def paired(a, b, n_boot=20000, seed=1, alpha=0.05):
    """Paired comparison of outcome a (treatment) against b (reference); trial-wise difference d = a - b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a - b
    n = len(d)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, (n_boot, n))
    bm = d[idx].mean(1)
    lo, hi = np.percentile(bm, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    sd = d.std(ddof=1)
    out = dict(n=n, mean_a=a.mean(), mean_b=b.mean(), mean_diff=d.mean(), sd_diff=sd, ci_lo=lo, ci_hi=hi,
               rel_change_pct=100 * d.mean() / b.mean())
    rel = d / b
    rl, rh = np.percentile(rel[idx].mean(1), [100 * alpha / 2, 100 * (1 - alpha / 2)])
    out.update(rel_ci_lo_pct=100 * rl, rel_ci_hi_pct=100 * rh, rel_p05_pct=100 * np.percentile(rel, 5), rel_p95_pct=100 * np.percentile(rel, 95))
    if sd > 0:
        t = stats.ttest_rel(a, b)
        out.update(t=t.statistic, p_t=t.pvalue, dz=d.mean() / sd)
    else:
        out.update(t=np.nan, p_t=np.nan, dz=np.nan)
    try:
        out["p_wilcoxon"] = stats.wilcoxon(d).pvalue if np.any(d != 0) else 1.0
    except ValueError:
        out["p_wilcoxon"] = np.nan
    out["shapiro_p"] = stats.shapiro(d).pvalue if (n >= 3 and sd > 0) else np.nan
    out["frac_trials_a_lower"] = float(np.mean(d < 0))
    return out


def holm(pvals):
    p = np.asarray(pvals, float); m = len(p)
    order = np.argsort(p); adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (m - rank) * p[i]); adj[i] = min(1.0, run)
    return adj


def src(X, y):
    """Standardised regression coefficients and R^2 (global sensitivity of y to columns of X)."""
    Xs = (X - X.mean(0)) / X.std(0); ys = (y - y.mean()) / y.std()
    beta, *_ = np.linalg.lstsq(Xs, ys, rcond=None)
    r2 = 1 - np.sum((ys - Xs @ beta) ** 2) / np.sum(ys ** 2)
    return beta, r2
