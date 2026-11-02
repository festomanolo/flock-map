#!/usr/bin/env python3
"""CFD figures C1-C5 from data/processed/cfd_*.csv|npz and cfd/cases/*/convergence.json"""
import sys, os, json, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from style import setup, save, panel, C
from flockmap import vlm, cfdgeom as G
P = "data/processed"; setup(); B = G.B


def C1_mesh():
    d = pd.read_csv(f"{P}/cfd_summary.csv"); m = d[(d.alpha == 3) & d.dy_b.isna()].sort_values("level")
    f = d[(d.alpha == 3) & (d.dy_b == 0.85) & (d.dx_b == 3.0)].sort_values("level")
    fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.4))
    ax[0].plot(m.cells / 1e3, m.CL, "o-", color=C["blue"], label="isolated"); panel(ax[0], "a"); ax[0].set_xscale("log"); ax[0].set_xlabel("cells (thousand)"); ax[0].set_ylabel("$C_L$")
    if len(f): ax[0].plot(f.cells / 1e3, f.fCL, "s--", color=C["orange"], label="follower")
    ax[0].legend()
    ax[1].plot(m.cells / 1e3, 1e4 * m.CD, "o-", color=C["blue"]); ax[1].plot(m.cells / 1e3, 1e4 * m.CDp, "^:", color=C["ink2"], label="pressure")
    ax[1].plot(m.cells / 1e3, 1e4 * m.CDv, "v:", color=C["aqua"], label="viscous"); ax[1].set_xscale("log"); ax[1].set_xlabel("cells (thousand)"); ax[1].set_ylabel("$C_D\\times10^4$"); panel(ax[1], "b"); ax[1].legend()
    ax[2].errorbar(m.level, m.yplus, yerr=[m.yplus - m.yp05, m.yp95 - m.yplus], fmt="o", color=C["violet"], capsize=3); ax[2].set_xticks(m.level); ax[2].set_xlabel("mesh level"); ax[2].set_ylabel("$y^+$ (mean, 5--95\\,\\%)"); ax[2].axhspan(30, 300, color=C["grid"], alpha=0.6, zorder=0); panel(ax[2], "c")
    fig.tight_layout(); save(fig, "C1_mesh_study")


def C2_polar():
    d = pd.read_csv(f"{P}/cfd_summary.csv"); v = pd.read_csv(f"{P}/cfd_vlm_polar.csv")
    c = d[(d.level == 1) & d.dy_b.isna()].sort_values("alpha")
    fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.4))
    ax[0].plot(v.alpha, v.CL_vlm, "-", color=C["blue"], label="planform VLM"); ax[0].plot(c.alpha, c.CL, "o", color=C["orange"], label="RANS L1"); ax[0].set_xlabel("$\\alpha$ (deg)"); ax[0].set_ylabel("$C_L$"); ax[0].legend(); panel(ax[0], "a")
    ax[1].plot(c.CL, 1e4 * c.CD, "o-", color=C["orange"], label="RANS $C_D$"); ax[1].plot(v.CL_vlm, 1e4 * v.CDi_vlm, "-", color=C["blue"], label="VLM $C_{D,i}$")
    ax[1].plot(c.CL, 1e4 * (c.CD - c.CDv), "^:", color=C["ink2"], label="RANS pressure"); ax[1].set_xlabel("$C_L$"); ax[1].set_ylabel("$C_D\\times10^4$"); ax[1].legend(); panel(ax[1], "b")
    # induced-drag factor from RANS: (CD - CD0)/CL^2 with CD0 from fit
    if len(c) >= 3:
        A = np.vstack([np.ones(len(c)), c.CL.values ** 2]).T; co = np.linalg.lstsq(A, c.CD.values, rcond=None)[0]
        x = np.linspace(0, c.CL.max() * 1.1, 50); ax[2].plot(c.CL ** 2, c.CD * 1e4, "o", color=C["orange"]); ax[2].plot(x ** 2, 1e4 * (co[0] + co[1] * x ** 2), "-", color=C["orange"], label=f"$C_{{D0}}$={co[0]:.4f}, $k$={co[1]:.3f}")
        k_v = np.polyfit(v.CL_vlm ** 2, v.CDi_vlm, 1)[0]; ax[2].plot(x ** 2, 1e4 * (co[0] + k_v * x ** 2), "--", color=C["blue"], label=f"VLM $k$={k_v:.3f}"); ax[2].legend()
        json.dump(dict(cd0=float(co[0]), k=float(co[1]), k_vlm=float(k_v)), open(f"{P}/cfd_polar_fit.json", "w"))
    ax[2].set_xlabel("$C_L^2$"); ax[2].set_ylabel("$C_D\\times10^4$"); panel(ax[2], "c")
    fig.tight_layout(); save(fig, "C2_polar_cfd_vs_vlm")


def C3_wake():
    f = f"{P}/cfd_wake_plane.npz"
    if not os.path.exists(f): return
    z = np.load(f); Y, Z, U, valid = z["Y"], z["Z"], z["U"], z["valid"]
    W = np.where(valid, U[..., 2] if U.ndim == 3 else np.nan, np.nan) / 18.0
    j = int(np.argmin(abs(Z[0, :])))
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.6), gridspec_kw=dict(width_ratios=[1.3, 1]))
    cs = ax[0].pcolormesh(Y / B, Z / B, W, cmap="RdBu_r", vmin=-0.08, vmax=0.08, shading="auto"); ax[0].set_xlabel("$y/b$"); ax[0].set_ylabel("$z/b$"); ax[0].set_aspect("equal"); fig.colorbar(cs, ax=ax[0], label="$w/U_\\infty$", shrink=0.8); panel(ax[0], "a")
    ax[1].plot(Y[:, j] / B, W[:, j], color=C["orange"], label="RANS L1 ($z\\approx0$)")
    try:
        from flockmap import freewake as FW
        ax[1].axhline(0, color=C["muted"], lw=0.6)
    except Exception: pass
    ax[1].set_xlabel("$y/b$"); ax[1].set_ylabel("$w/U_\\infty$"); ax[1].legend(); panel(ax[1], "b")
    fig.tight_layout(); save(fig, "C3_wake_plane_cfd")


def C4_formation():
    d = pd.read_csv(f"{P}/cfd_summary.csv"); v = pd.read_csv(f"{P}/cfd_vlm_formation.csv")
    iso = d[(d.alpha == 3) & d.dy_b.isna() & (d.level == 1)]
    if iso.empty: return
    iso = iso.iloc[0]; f = d[(d.level == 1) & d.dy_b.notna() & (d.alpha == 3)].copy()
    f["dCL"] = f.fCL - iso.CL; f["dCD"] = f.fCD - iso.CD
    fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.5))
    for nm, a, key, vk, lab in (("a", ax[0], "dCD", "dCDi_vlm", "$\\Delta C_D\\times10^4$"), ("b", ax[1], "dCL", "dCL_vlm", "$\\Delta C_L\\times10^3$"), ("c", ax[2], "fCl", "Cl_vlm", "$C_{l}$ (roll)$\\times10^3$")):
        sc = 1e4 if key == "dCD" else 1e3
        for dx, col in ((3.0, C["blue"]), (2.0, C["aqua"]), (4.5, C["violet"])):
            g = v[v.dx_b == dx]; a.plot(g.dy_b, sc * g[vk], "-", color=col, alpha=0.8, label=f"VLM $d_x$={dx}b")
            h = f[f.dx_b == dx].sort_values("dy_b")
            if len(h): a.plot(h.dy_b, sc * h[key], "o", color=col, mfc="white", ms=5, label=f"RANS $d_x$={dx}b")
        a.axhline(0, color=C["muted"], lw=0.6); a.set_xlabel("$d_y/b$"); a.set_ylabel(lab); panel(a, nm)
    ax[0].legend(fontsize=5.5, ncol=1); fig.tight_layout(); save(fig, "C4_formation_cfd_vs_vlm")


def C5_convergence():
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.4)); n = 0
    for case, col, pre in (("iso_a3_L1", C["blue"], "leader"), ("fol_dy085_dx3_L1", C["orange"], "follower"), ("fol_dy085_dx3_L1", C["violet"], "leader")):
        f = f"cfd/cases/{case}/convergence.json"
        if not os.path.exists(f): continue
        c = pd.DataFrame(json.load(open(f))); n += 1; lab = f"{case} ({pre})"
        ax[0].plot(c["iter"], c[f"{pre}_CL"], "o-", ms=3, color=col, label=lab); ax[1].plot(c["iter"], 1e4 * c[f"{pre}_CD"], "o-", ms=3, color=col, label=lab)
    ax[0].set_xlabel("iteration"); ax[0].set_ylabel("$C_L$"); ax[1].set_xlabel("iteration"); ax[1].set_ylabel("$C_D\\times10^4$"); ax[0].legend(fontsize=5.5); panel(ax[0], "a"); panel(ax[1], "b")
    if n: fig.tight_layout(); save(fig, "C5_force_convergence")


def C6_residuals():
    sys.path.insert(0, "cfd"); from postproc import residual_history
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.4)); n = 0
    for case, a, nm in (("iso_a3_L1", ax[0], "a"), ("fol_dy085_dx3_L1", ax[1], "b")):
        d = f"cfd/cases/{case}"
        if not os.path.exists(d + "/log.simpleFoam"): continue
        r = residual_history(d); n += 1
        for k, col in (("p", C["blue"]), ("Ux", C["orange"]), ("k", C["aqua"]), ("omega", C["violet"])):
            if r.get(k):
                y = np.array(r[k]); n_ref = len(r["Ux"]); step = max(1, len(y) // max(n_ref, 1)); a.semilogy(y[::step][:n_ref], color=col, label=k)
        a.set_xlabel("iteration"); a.set_ylabel("initial residual"); a.legend(ncol=2); panel(a, nm); a.set_title(case, fontsize=7)
    if n: fig.tight_layout(); save(fig, "C6_residual_history")


if __name__ == "__main__":
    for fn in (C1_mesh, C2_polar, C3_wake, C4_formation, C5_convergence, C6_residuals):
        if len(sys.argv) > 1 and fn.__name__ not in sys.argv[1:]: continue
        try: fn()
        except Exception as e: print(fn.__name__, "failed:", repr(e))
