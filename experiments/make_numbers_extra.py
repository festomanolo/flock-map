#!/usr/bin/env python3
"""Macros for the extra analyses and the CFD campaign -> manuscript/numbers_extra.tex (+ tables/tab_cfd*.tex)"""
import sys, os, json, math, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
from flockmap import vlm, aero, energy as E, mission as M, cfdgeom as G, stats as ST
from flockmap.config import AC, CAM

W = dict(zip("0123456789", ["Zero","One","Two","Three","Four","Five","Six","Seven","Eight","Nine"]))
P = "data/processed"; mac = {}
def put(n, v, f="{:.2f}"): mac[n] = f.format(v) if not isinstance(v, str) else v

iso = aero.isolated(18.0); put("cdiShare", 100 * iso["cdi"] / iso["cd"], "{:.1f}")
put("Pwait", M.P_WAIT, "{:.0f}"); put("nPwait", M.P_WAIT, "{:.0f}")
# ---- dz
z = np.load(f"{P}/extra_dz.npz"); dy, dz = z["dy"], z["dz"]; j = int(np.argmin(abs(dy - 0.85)))
for nm in ("sheet", "free"):
    col = z[f"pct_{nm}"][:, j]; pk = col.max(); half = dz[col >= 0.5 * pk]
    K = "Sheet" if nm == "sheet" else "Free"
    put(f"dzHalf{K}", 0.5 * (half.max() - half.min()), "{:.2f}"); put(f"dzPeak{K}", pk, "{:.1f}")
    put(f"dzAtPt2{K}", float(np.interp(0.2, dz, col)), "{:.1f}"); put(f"dzAtPt4{K}", float(np.interp(0.4, dz, col)), "{:.1f}")
put("dzHalfM", float(mac["dzHalfFree"]) * AC.b, "{:.2f}")
# ---- station-keeping error
d = pd.read_csv(f"{P}/extra_skerr.csv")
for m, K in (("vlm_sheet", "Sheet"), ("vlm_free", "Free"), ("strip_corrected", "Strip")):
    s = d[(d.model == m) & (d.dy_b == 0.85)].set_index("sigma_m").saving_pct
    put(f"skZero{K}", s[0.0], "{:.1f}"); put(f"skFifteen{K}", s[0.15], "{:.1f}"); put(f"skFortyK{K}", s[0.4], "{:.1f}"); put(f"skSixty{K}", s[0.6], "{:.1f}")
put("skRetain", 100 * d[(d.model == "vlm_sheet") & (d.dy_b == 0.85) & (d.sigma_m == 0.15)].saving_pct.iloc[0] / d[(d.model == "vlm_sheet") & (d.dy_b == 0.85) & (d.sigma_m == 0.0)].saving_pct.iloc[0], "{:.0f}")
# ---- power curve
pw = pd.read_csv(f"{P}/extra_power.csv"); put("powMinV", pw.va[pw.p_elec.idxmin()], "{:.1f}"); put("powRangeV", pw.va[pw.e_per_km_Wh.idxmin()], "{:.1f}")
put("powMinP", pw.p_elec.min(), "{:.0f}"); put("powRangeE", pw.e_per_km_Wh.min(), "{:.2f}"); put("powLDmax", pw.ld.max(), "{:.1f}"); put("powLDV", pw.va[pw.ld.idxmax()], "{:.1f}")
put("powE18", float(np.interp(18.0, pw.va, pw.e_per_km_Wh)), "{:.2f}"); put("powExcess", 100 * (float(np.interp(18.0, pw.va, pw.e_per_km_Wh)) / pw.e_per_km_Wh.min() - 1), "{:.1f}")
# ---- coverage
c = pd.read_csv(f"{P}/extra_coverage.csv"); c0 = c[c.crab_deg == 0.0]
ok = c0[c0.accepted_ha >= 99.9]; put("covMinOverlap", 100 * ok.side_overlap.max() if len(ok) else float("nan"), "{:.0f}")
put("covStrips58", int(c0[np.isclose(c0.side_overlap, 0.58)].n_strips.iloc[0]), "{:d}"); put("covStrips65", int(c0[np.isclose(c0.side_overlap, 0.65)].n_strips.iloc[0]), "{:d}")
put("covTrackSave", float(c0[np.isclose(c0.side_overlap, 0.65)].track_km.iloc[0] - c0[np.isclose(c0.side_overlap, 0.58)].track_km.iloc[0]), "{:.1f}")
bad = c0[c0.accepted_ha < 99.9]; put("covFailWindow", ", ".join(f"{100*v:.0f}" for v in bad.side_overlap.values[:6]) if len(bad) else "none", "{}")
# ---- kappa map
km = pd.read_csv(f"{P}/extra_kappa_map.csv")
def be(col, kap):
    g = km[np.isclose(km.kappa, kap)].sort_values("D"); D = g.D.values.astype(float); y = g[col].values
    for i in range(len(D) - 1):
        if y[i] < 0 <= y[i + 1]: return math.exp(np.interp(0, [y[i], y[i + 1]], np.log([D[i], D[i + 1]]))) / 1000.0
    return float("nan")
for kap, K in ((0.3, "Low"), (0.7, "Free"), (1.0, "One"), (1.5, "High")):
    v17, v14 = be("saving17_Wh", kap), be("saving14_Wh", kap)
    put(f"kmBe17{K}", ">20" if np.isnan(v17) else f"{v17:.1f}")
    put(f"kmBe14{K}", ">20" if np.isnan(v14) else f"{v14:.1f}")
put("kmAt25", km[(np.isclose(km.kappa, 1.0)) & (km.D == 2500)].saving17_Wh.iloc[0], "{:+.2f}"); put("kmAt25Low", km[(np.isclose(km.kappa, 0.3)) & (km.D == 2500)].saving17_Wh.iloc[0], "{:+.2f}")
put("kmAt25High", km[(np.isclose(km.kappa, 1.5)) & (km.D == 2500)].saving17_Wh.iloc[0], "{:+.2f}"); put("kmAt20k", km[(np.isclose(km.kappa, 1.0)) & (km.D == 20000)].saving17_Wh.iloc[0], "{:+.1f}")
# ---- tornado / Sobol / CBF / step (if present)
if os.path.exists(f"{P}/extra_tornado.csv"):
    t = pd.read_csv(f"{P}/extra_tornado.csv"); put("torBase", t.base_Wh.iloc[0], "{:+.2f}")
    for f_, K in (("wake effectiveness kappa", "Kappa"), ("reconfiguration overhead x", "Reconf"), ("station-keeping error x", "Err"), ("wind speed range centre (m/s)", "Wind"), ("transit distance D (m)", "Dist")):
        s = t[t.factor == f_]; put(f"tor{K}Lo", s[s.setting == "low"].delta_Wh.iloc[0], "{:+.2f}"); put(f"tor{K}Hi", s[s.setting == "high"].delta_Wh.iloc[0], "{:+.2f}")
if os.path.exists(f"{P}/extra_sobol.csv"):
    s = pd.read_csv(f"{P}/extra_sobol.csv")
    for f_, K in (("wake effectiveness kappa", "Kappa"), ("reconfiguration overhead x", "Reconf"), ("station-keeping error x", "Err"), ("wind speed range centre (m/s)", "Wind"), ("transit distance D (m)", "Dist")):
        r = s[s.factor == f_].iloc[0]; put(f"sob{K}S", r.S1, "{:.2f}"); put(f"sob{K}T", r.ST, "{:.2f}")
    put("sobSumS", s.S1.sum(), "{:.2f}")
if os.path.exists(f"{P}/extra_cbf_ablation.csv"):
    a = pd.read_csv(f"{P}/extra_cbf_ablation.csv")
    put("cbfAblSeeds", int(a.seed.nunique()), "{:d}")
    for sc, K in (("S3_braking_dropout", "Three"), ("S5_combined", "Five"), ("S6_overcapability", "Six")):
        for mg, k in ((0.0, "Mzero"), (0.5, "Mhalf"), (1.0, "Mone"), (1.5, "Monehalf"), (2.0, "Mtwo")):
            g = a[(a.scenario == sc) & (a.margin == mg)]
            if len(g):
                put(f"cbf{K}V{k}", 100 * g.violated.mean(), "{:.0f}"); put(f"cbf{K}E{k}", g.rms_ey.mean(), "{:.2f}"); put(f"cbf{K}S{k}", 1e4 * g.mean_dcd.mean(), "{:.1f}")
if os.path.exists(f"{P}/extra_step.csv"):
    s = pd.read_csv(f"{P}/extra_step.csv").groupby("controller").mean(numeric_only=True)
    for ctl, K in (("P", "P"), ("NMPC", "N"), ("NMPC+CBF", "C")):
        put(f"step{K}Over", s.loc[ctl, "overshoot_pct"], "{:.0f}"); put(f"step{K}Settle", s.loc[ctl, "settle2_s"], "{:.1f}"); put(f"step{K}Rise", s.loc[ctl, "rise_s"], "{:.1f}")
# ---- MC diagnostics
d = pd.read_csv("data/raw/mission_trials.csv"); d = d[d.model == "vlm_sheet"]
pv_ = d.pivot(index="trial", columns="strategy", values="e_load_Wh"); w = d[d.strategy == "S1_independent"].set_index("trial")
slope, icpt = np.polyfit(w.wind, pv_["S1_independent"], 1); r2 = np.corrcoef(w.wind, pv_["S1_independent"])[0, 1] ** 2
put("mcSlope", slope, "{:.2f}"); put("mcR2", r2, "{:.2f}"); diff = (pv_["S3_adaptive_geometric"] - pv_["S1_independent"]).values
put("mcDiffSD", diff.std(ddof=1), "{:.2f}"); put("mcDiffMean", diff.mean(), "{:+.2f}")
put("mcDirAmp", float(np.ptp(np.convolve(np.sort(diff), np.ones(5) / 5, mode="valid"))), "{:.2f}")
th = w.wind_dir.values; A_ = np.column_stack([np.ones_like(th), np.cos(th), np.sin(th), np.cos(2 * th), np.sin(2 * th)]); coef = np.linalg.lstsq(A_, diff, rcond=None)[0]
res = diff - A_ @ coef; put("mcDirR2", 1 - res.var() / diff.var(), "{:.2f}")
put("mcRange", np.ptp(pv_["S1_independent"].values), "{:.1f}"); put("mcSD1", pv_["S1_independent"].std(ddof=1), "{:.2f}")
# ---- planform VLM (CFD geometry)
Wp = vlm.planform_wing(80); r0 = Wp.isolated_alpha(18.0, 3.0); r1 = Wp.isolated_alpha(18.0, 0.0); r2_ = Wp.isolated_alpha(18.0, 6.0)
put("planCL", r0["CL"], "{:.3f}"); put("planCla", (r2_["CL"] - r1["CL"]) / np.radians(6.0), "{:.2f}"); put("planAR", Wp.AR, "{:.2f}"); put("planE", r0["CL"] ** 2 / (np.pi * Wp.AR * r0["CDi"]), "{:.2f}")
put("planETP", r0["CL"] ** 2 / (np.pi * Wp.AR * r0["CDi_trefftz"]), "{:.2f}")
rf1 = Wp.follower_alpha(3.0 * G.B, 0.85 * G.B, 18.0, 3.0); rfs = Wp.coupled_symmetry_alpha(3.0 * G.B, 0.85 * G.B, 18.0, 3.0, two_way_leader=True)
put("planOneDCL", rf1["CL"] - r0["CL"], "{:+.4f}"); put("planSymDCL", rfs["CL"] - r0["CL"], "{:+.4f}")
put("planSymPct", 100.0 * ((rfs["CL"] - r0["CL"]) / (rf1["CL"] - r0["CL"]) - 1.0), "{:+.1f}")
put("planSymLeadPct", 100.0 * (rfs["leader_CL"] / r0["CL"] - 1.0), "{:+.2f}")
put("cfdS", G.area(), "{:.3f}"); put("cfdMAC", G.mac(), "{:.3f}"); put("cfdAR", G.B ** 2 / G.area(), "{:.2f}"); put("ReMAC", 18.0 * G.mac() / 1.5e-5 / 1e5, "{:.1f}")

# ---- CFD campaign ------------------------------------------------------------------------------------------------
cs = f"{P}/cfd_summary.csv"
rows_tab = []
if os.path.exists(cs):
    df = pd.read_csv(cs).set_index("case"); put("cfdNcases", len(df), "{:d}")
    iso_ = df[df.index.str.startswith("iso_a3_L")].sort_values("level")
    labs = {0: "L0 (coarse)", 1: "L1 (medium)", 2: "L2 (fine)"}; sl = {0: "(4,5)", 1: "(5,6)", 2: "(6,7)"}; wl = {0: 2, 1: 3, 2: 3}; tl = {0: 3, 1: 4, 2: 5}
    for lv, r in iso_.iterrows():
        L = int(r.level); rows_tab.append(f"{labs[L]} & {sl[L]} & {wl[L]} & {tl[L]} & {int(r.cells):,} & {r.yplus:.0f} ({r.yp05:.0f}--{r.yp95:.0f})".replace(",", "\\,"))
        put(f"yplus{['Zero','One','Two'][L]}", r.yplus, "{:.0f}")
    open("manuscript/tables/tab_cfdmesh.tex", "w").write(" \\\\\n".join(rows_tab) + "\n")
    for L, K in ((0, "Zero"), (1, "One"), (2, "Two")):
        s = iso_[iso_.level == L]
        if len(s):
            r = s.iloc[0]; put(f"cfdCells{K}", int(r.cells), "{:,d}".replace(",", "")); put(f"cfdCL{K}", r.CL, "{:.4f}"); put(f"cfdCD{K}", r.CD, "{:.5f}"); put(f"cfdCDp{K}", r.CDp, "{:.5f}"); put(f"cfdCDv{K}", r.CDv, "{:.5f}")
            put(f"cfdRes{K}", r.res_p, "{:.1e}"); put(f"cfdTime{K}", r.t_solve_s / 60.0, "{:.0f}")
    if len(iso_[iso_.level.isin([0, 1])]) == 2:
        a, b_ = iso_[iso_.level == 0].iloc[0], iso_[iso_.level == 1].iloc[0]
        put("cfdDCLzo", 100 * (b_.CL / a.CL - 1), "{:+.1f}"); put("cfdDCDzo", 100 * (b_.CD / a.CD - 1), "{:+.1f}")
    pol = df[df.index.str.startswith("iso_a") & df.index.str.endswith("L1") & (df.index != "iso_a3_L1x")].sort_values("alpha")
    if len(pol) >= 3:
        CL = pol.CL.values; CD = pol.CD.values; k, cd0 = np.polyfit(CL ** 2, CD, 1)[0], np.polyfit(CL ** 2, CD, 1)[1]
        put("cfdK", k, "{:.4f}"); put("cfdCDzero", cd0, "{:.4f}"); put("cfdE", 1 / (np.pi * (G.B ** 2 / G.area()) * k), "{:.2f}")
        put("cfdCla", np.polyfit(np.radians(pol.alpha.values), CL, 1)[0], "{:.2f}")
    fol = df[df.index.str.startswith("fol_dy") & df.index.str.endswith("dx3_L1")].sort_values("dy_b")
    if len(fol) and "iso_a3_L1" in df.index:
        i = df.loc["iso_a3_L1"]
        for dyb, r in fol.iterrows():
            pass
        for _, r in fol.iterrows():
            k_ = f"{int(round(r.dy_b*100)):03d}"
            put(f"cfdFdCL{k_}", r.fCL - i.CL, "{:+.4f}"); put(f"cfdFdCD{k_}", r.fCD - i.CD, "{:+.5f}"); put(f"cfdFCl{k_}", r.fCl, "{:+.4f}")
    json.dump({"ok": True}, open("data/processed/cfd_numbers_ready.json", "w"))
with open("manuscript/numbers_extra.tex", "w") as f:
    f.write("% AUTO-GENERATED by experiments/make_numbers_extra.py\n")
    for k, v in sorted(mac.items()): f.write(f"\\newcommand{{\\n{''.join(W.get(c,c) for c in k)}}}{{{v}}}\n")
print(len(mac), "extra macros")
