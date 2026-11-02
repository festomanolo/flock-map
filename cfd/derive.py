#!/usr/bin/env python3
"""Derived CFD quantities -> data/processed/cfd_formation_table.csv, cfd_polar_table.csv, cfd_mesh_table.csv
Follower effect at fixed alpha and at fixed C_L (trimmed with the isolated polar slope dCD/dCL of the same method)."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
from flockmap import vlm, cfdgeom as G
P = os.path.join(os.path.dirname(__file__), "..", "data", "processed"); B = G.B
d = pd.read_csv(f"{P}/cfd_summary.csv"); d["dx_b"] = d.dx_b.fillna(0)
iso = d[d.dy_b.isna() & (d.level == 1)].sort_values("alpha")
# CFD polar slope dCD/dCL at alpha=3 from the isolated alpha sweep (central difference if possible)
def slope(df, cl="CL", cd="CD"):
    if len(df) >= 3: return float(np.polyfit(df[cl].values, df[cd].values, 2)[0] * 2 * df.loc[df.alpha == 3, cl].iloc[0] + np.polyfit(df[cl].values, df[cd].values, 2)[1])
    return np.nan
s_cfd = slope(iso)
W = vlm.planform_wing(80); alphas = np.array([2.0, 3.0, 4.0]); pol = [W.isolated_alpha(18.0, a) for a in alphas]
s_vlm = float(np.polyfit([p["CL"] for p in pol], [p["CDi"] for p in pol], 1)[0])
i3 = iso[iso.alpha == 3].iloc[0]; rows = []
for _, r in d[d.dy_b.notna() & (d.level == 1) & (d.alpha == 3)].sort_values(["dx_b", "dy_b"]).iterrows():
    v_iso = W.isolated_alpha(18.0, 3.0); v_f = W.follower_alpha(r.dx_b * B, r.dy_b * B, 18.0, 3.0)
    dCL, dCD = r.fCL - i3.CL, r.fCD - i3.CD; dCLl, dCDl = r.fCL - r.CL, r.fCD - r.CD          # vs isolated mesh / vs in-case leader
    vdCL, vdCD = v_f["CL"] - v_iso["CL"], v_f["CDi"] - v_iso["CDi"]
    rows.append(dict(case=r.case, dx_b=r.dx_b, dy_b=r.dy_b, dCL_iso=dCL, dCD_iso=dCD, dCL_ldr=dCLl, dCD_ldr=dCDl,
                     dCD_pct_iso=100 * dCD / i3.CD, dCD_pct_ldr=100 * dCDl / r.CD,
                     trim_pct_iso=100 * (dCD - s_cfd * dCL) / i3.CD, trim_pct_ldr=100 * (dCDl - s_cfd * dCLl) / r.CD,
                     trim_pct_iso_vs=100 * (dCD - s_vlm * dCL) / i3.CD, trim_pct_ldr_vs=100 * (dCDl - s_vlm * dCLl) / r.CD, kappa_eff_lo=(dCD - s_vlm * dCL) / (vdCD - s_vlm * vdCL), kappa_eff_hi=(dCD - s_cfd * dCL) / (vdCD - s_vlm * vdCL),
                     vlm_dCL=vdCL, vlm_dCDi=vdCD, vlm_pct=100 * vdCD / (i3.CD), vlm_trim_pct=100 * (vdCD - s_vlm * vdCL) / i3.CD,
                     fCl=r.fCl, Cl_vlm=v_f["Cl_roll"]))
out = pd.DataFrame(rows); out.to_csv(f"{P}/cfd_formation_table.csv", index=False)
json.dump(dict(slope_cfd=s_cfd, slope_vlm=s_vlm), open(f"{P}/cfd_slopes.json", "w"))
print(out.round(5).to_string()); print("slopes", s_cfd, s_vlm)
# mesh table
m = d[(d.alpha == 3)].sort_values(["dy_b", "level"]); m.to_csv(f"{P}/cfd_mesh_table.csv", index=False)
