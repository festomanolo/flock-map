#!/usr/bin/env python3
"""Aggregate the OpenFOAM campaign into tables/figures data (data/processed/cfd_*.csv|npz)."""
import sys, os, json, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
import pyvista as pv
from flockmap import vlm, aero, cfdgeom as G
from flockmap.config import AC

HERE = os.path.dirname(os.path.abspath(__file__)); CASES = os.path.join(HERE, "cases"); OUT = os.path.join(HERE, "..", "data", "processed")
B = G.B; S = G.area(); Q = 0.5 * 1.225 * 18.0 ** 2


def load():
    rows = []
    for d in sorted(glob.glob(os.path.join(CASES, "*"))):
        f = os.path.join(d, "summary.json")
        if not os.path.exists(f): continue
        s = json.load(open(f)); m = s["meta"]; t = json.load(open(os.path.join(d, "timing.json"))) if os.path.exists(os.path.join(d, "timing.json")) else {}
        r = dict(case=s["case"], alpha=m["alpha"], level=m["level"], dy_b=(m["follower"][0] if m["follower"] else np.nan), dx_b=(m["follower"][1] if m["follower"] else np.nan),
                 cells=s["n_cells"], iters=s["n_iter"] // 2 if s["n_iter"] > m["iters"] + 5 else s["n_iter"],
                 CL=s["leader"]["CL"], CD=s["leader"]["CD"], CDp=s["leader"]["CD_pressure"], CDv=s["leader"]["CD_viscous"], yplus=s["leader"]["yplus_mean"],
                 yp05=s["leader"]["yplus_p05"], yp95=s["leader"]["yplus_p95"],
                 res_p=s["residuals_last"]["p"], res_U=s["residuals_last"]["Ux"], res_k=s["residuals_last"]["k"], res_w=s["residuals_last"]["omega"],
                 t_solve_s=t.get("solve", {}).get("s", np.nan), t_mesh_s=t.get("snappy", {}).get("s", np.nan))
        if "follower" in s:
            f_ = s["follower"]; r.update(fCL=f_["CL"], fCD=f_["CD"], fCDp=f_["CD_pressure"], fCDv=f_["CD_viscous"], fCl=f_["Cl_roll"], fCm=f_["Cm_pitch"], fyplus=f_["yplus_mean"])
        rows.append(r)
    return pd.DataFrame(rows)


def vlm_planform():
    W = vlm.planform_wing(80); rows = []
    for a in (0, 1.5, 3, 4.5, 6):
        r = W.isolated_alpha(18.0, a); rows.append(dict(alpha=a, CL_vlm=r["CL"], CDi_vlm=r["CDi"]))
    return pd.DataFrame(rows)


def formation_vlm(alpha=3.0):
    W = vlm.planform_wing(80); iso = W.isolated_alpha(18.0, alpha); rows = []
    for dxb in (2.0, 3.0, 4.5):
        for dyb in (0.7, 0.85, 1.0, 1.3):
            f = W.follower_alpha(dxb * B, dyb * B, 18.0, alpha); rows.append(dict(dx_b=dxb, dy_b=dyb, dCL_vlm=f["CL"] - iso["CL"], dCDi_vlm=f["CDi"] - iso["CDi"], Cl_vlm=f["Cl_roll"]))
    return pd.DataFrame(rows)


def wake_profile(case="iso_a3_L1", x=None):
    d = os.path.join(CASES, case); vtk = sorted(x for x in glob.glob(os.path.join(d, "VTK", "*_*")) if os.path.isdir(x))[-1]
    I = pv.read(os.path.join(vtk, "internal.vtu")); meta = json.load(open(os.path.join(d, "case.json")))
    x = x if x is not None else 3.0 * B
    ys = np.linspace(0.0, 3.4, 69); zs = np.linspace(-1.0, 1.0, 41)
    from postproc import sample_plane
    Y, Z, U, valid = sample_plane(vtk, x, ys, zs, internal=I)
    return Y, Z, U, valid, x


if __name__ == "__main__":
    df = load(); df.to_csv(os.path.join(OUT, "cfd_summary.csv"), index=False); print(df.round(4).to_string())
    vlm_planform().to_csv(os.path.join(OUT, "cfd_vlm_polar.csv"), index=False); formation_vlm().to_csv(os.path.join(OUT, "cfd_vlm_formation.csv"), index=False)
    try:
        Y, Z, U, valid, x = wake_profile(); np.savez(os.path.join(OUT, "cfd_wake_plane.npz"), Y=Y, Z=Z, U=U, valid=valid, x=x)
    except Exception as e:
        print("wake profile failed:", e)
