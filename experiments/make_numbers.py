#!/usr/bin/env python3
"""Generate manuscript/numbers.tex (macros) and manuscript/tables/*.tex from processed data.  No manual numbers."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
from flockmap import aero, vlm, energy as E, photo
from flockmap.config import AC, CAM

P = "data/processed"; OUT = "manuscript"; os.makedirs(f"{OUT}/tables", exist_ok=True)
mac = {}
def put(name, val, fmt="{:.2f}"):
    mac[name] = fmt.format(val) if not isinstance(val, str) else val

# ------------------------------------------------------------------ audit of the preliminary version
o = json.load(open("audit/original_reproduction_output.json"))
put("auditHthreeT", abs(o["H3_full"]["t"]), "{:.0f}"); put("auditHthreeD", abs(o["H3_full"]["cohen_dz"]), "{:.1f}")
put("auditCorr", o["corr_E_S1_vs_S4_across_trials"], "{:.6f}")
put("auditEoneMean", o["S1"]["E"][0], "{:.2f}"); put("auditEoneSD", o["S1"]["E"][1], "{:.2f}")
t33 = pd.read_csv(f"{P}/audit_table33.csv")
put("nTabMatch", int(t33.w_match.sum()), "{:d}"); put("nTabAll", len(t33), "{:d}")
put("auditMaxPctErr", float(np.max(np.abs(t33.pct_table - t33.pct_recomputed))), "{:.1f}")
sw = pd.read_csv(f"{P}/aero_sweep_dy.csv")
pub = sw[sw.model == "published"].set_index("dy_b")
put("pubDropNinety", pub.loc[0.9, "pct_power"], "{:.1f}"); put("pubAtEighty", pub.loc[0.8, "pct_power"], "{:.2f}")
put("pubAtEightyFive", pub.loc[0.85, "pct_power"], "{:.1f}")
iso = aero.isolated(18.0)
put("gammaPub", aero.gamma0_published(18, iso["cl"]), "{:.3f}"); put("gammaTrue", aero.gamma0_elliptic(18, iso["cl"]), "{:.3f}")
put("clPubOverCorr", aero.strip_follower(3, 0.8, variant="published")["cl_roll"] / aero.strip_follower(3, 0.8, variant="corrected")["cl_roll"], "{:.1f}")
put("pIso", iso["p_elec"], "{:.2f}"); put("CLiso", iso["cl"], "{:.4f}"); put("LoverD", iso["cl"] / iso["cd"], "{:.1f}")
put("pTurn", E.p_level(18, 25), "{:.2f}")

# ------------------------------------------------------------------ aero
for m in ("strip_corrected", "vlm_rolled", "vlm_sheet", "vlm_analytic", "vlm_free"):
    s = sw[(sw.model == m) & (sw.dy_b <= 1.6)]; r = s.loc[s.pct_power.idxmax()]
    k = {"strip_corrected": "Strip", "vlm_rolled": "Rolled", "vlm_sheet": "Sheet", "vlm_analytic": "Analytic", "vlm_free": "Free"}[m]
    put(f"peak{k}", r.pct_power, "{:.1f}"); put(f"peak{k}Dy", r.dy_b, "{:.2f}")
    put(f"atEighty{k}", s[np.isclose(s.dy_b, 0.8)].pct_power.iloc[0], "{:.1f}")
    put(f"pw{k}", float(((s.pct_power > 0.5 * r.pct_power)).sum() * 0.05), "{:.2f}")        # width (in d_y/b) above half-peak
v = pd.read_csv(f"{P}/vlm_verification.csv"); r = v[v.n == 120].iloc[0]
put("vlmE", r.e_oswald, "{:.3f}"); put("vlmCla", r.cl_alpha, "{:.2f}"); put("helmCla", r.helmbold_cl_alpha, "{:.2f}"); put("llCla", r.prandtl_ll_cl_alpha, "{:.2f}")
put("vlmClaErr", 100 * (r.cl_alpha / r.helmbold_cl_alpha - 1), "{:.0f}")
av = pd.read_csv(f"{P}/aero_airspeed.csv")
for va in (13, 18, 24):
    w = {13: "Thirteen", 18: "Eighteen", 24: "TwentyFour"}[va]
    put(f"sheetV{w}", av[(av.model == "vlm_sheet") & (av.va == va)].pct_power.iloc[0], "{:.1f}")
    put(f"pubV{w}", av[(av.model == "published") & (av.va == va)].pct_power.iloc[0], "{:.1f}")
ua = pd.read_csv(f"{P}/aero_uncertainty_airspeed.csv"); u = ua[(ua.va == 18) & (ua.dy_b == 0.85)].iloc[0]
put("uncEighteenLo", u.p05, "{:.1f}"); put("uncEighteenHi", u.p95, "{:.1f}"); put("uncEighteenMean", u["mean"], "{:.1f}")
u = ua[(ua.va == 13) & (ua.dy_b == 0.85)].iloc[0]; put("uncThirteenLo", u.p05, "{:.1f}"); put("uncThirteenHi", u.p95, "{:.1f}")
z = np.load(f"{P}/aero_map_dxdy.npz"); dP = z["dP"]; put("mapMinW", -dP.min(), "{:.1f}")
put("mapDxSpread", float(np.max(np.abs(dP[:, np.argmin(np.abs(z["dy"] - 0.85))] - dP[np.argmin(np.abs(z["dx"] - 3.0), 0), np.argmin(np.abs(z["dy"] - 0.85))]))), "{:.2f}")

# ------------------------------------------------------------------ free wake
from flockmap.freewake import FreeWake
far = FreeWake.load("data/processed/freewake_far.npz"); fine = FreeWake.load("data/processed/freewake_fine.npz")
Xc = far.rows[:, :, 0].mean(1); k110 = int(np.argmin(np.abs(Xc - 110.0))); k40 = int(np.argmin(np.abs(Xc - 40.0))); k10 = int(np.argmin(np.abs(Xc - 10.0)))
zc = far.rows[:, :, 2]
put("fwSagTen", -(zc[k10, far.n // 2] - zc[k10, -1]) * 100, "{:.0f}"); put("fwSagForty", -(zc[k40, far.n // 2] - zc[k40, -1]), "{:.2f}"); put("fwSagHund", -(zc[k110, far.n // 2] - zc[k110, -1]), "{:.2f}")
put("fwCentreZ", -zc[k110, far.n // 2], "{:.2f}"); put("fwTipZ", -zc[k110, -1], "{:.2f}"); put("fwXend", Xc[k110], "{:.0f}"); put("fwXendB", Xc[k110] / AC.b, "{:.0f}")
t110 = Xc[k110] / 18.0; put("fwSink", -zc[k110, far.n // 2] / t110, "{:.2f}"); put("fwSinkTheory", fine.gamma.sum() * 0 + (far.L / (AC.rho * 18.0 * AC.b * np.pi / 4)) / (2 * AC.b), "{:.2f}")
put("fwLiftRatio", far.lift() / far.L, "{:.4f}"); put("fwGamma", float(np.sum(far.gamma * far.dy)) / (AC.b * np.pi / 4 * 0 + 1) * 0 + float(np.max(far.gamma)), "{:.2f}")
put("fwRows", len(far.rows), "{:d}"); put("fwDt", far.dt * 1000, "{:.0f}"); put("fwSpan", far.n, "{:d}")
import json as _json
core = _json.load(open("data/processed/freewake_core_sensitivity.json"))
put("coreLo", min(c["pct_0.9"] for c in core), "{:.1f}"); put("coreHi", max(c["pct_0.9"] for c in core), "{:.1f}")
put("coreSmall", core[0]["pct_0.9"], "{:.1f}"); put("coreBig", core[2]["pct_0.9"], "{:.1f}")
# ------------------------------------------------------------------ control
c = pd.read_csv("data/raw/control_trials.csv"); g = c.groupby(["scenario", "controller"]).mean(numeric_only=True)
for sc, k in (("S1_turbulence", "SOne"), ("S2_gust_doublet", "STwo"), ("S3_braking_dropout", "SThree"), ("S4_degraded_gnss", "SFour"), ("S5_combined", "SFive"), ("S6_overcapability", "SSix")):
    for ctl, kc in (("P", "P"), ("NMPC", "N"), ("NMPC+CBF", "C")):
        put(f"rmsEy{k}{kc}", g.loc[(sc, ctl), "rms_ey"], "{:.2f}"); put(f"minSep{k}{kc}", g.loc[(sc, ctl), "min_sep"], "{:.2f}")
        put(f"viol{k}{kc}", 100 * g.loc[(sc, ctl), "violated"], "{:.0f}")
        put(f"act{k}{kc}", 100 * g.loc[(sc, ctl), "cbf_active_frac"], "{:.1f}")
put("solveMean", c[c.controller != "P"].solve_ms_mean.mean(), "{:.1f}"); put("solveMax", c.solve_ms_max.max(), "{:.0f}")
put("nControl", len(c), "{:d}"); put("nSeedsControl", c.seed.nunique(), "{:d}")
put("mpcFail", int(c.n_mpc_fail.sum()), "{:d}"); put("cbfInfeas", int(c.cbf_infeasible.sum()), "{:d}")
put("rmsExSOne", g.loc[("S1_turbulence", "NMPC+CBF"), "rms_ex"], "{:.2f}")
put("rmsEyFracB", g.loc[("S1_turbulence", "NMPC+CBF"), "rms_ey"] / AC.b, "{:.3f}")

# ------------------------------------------------------------------ reconfiguration
j = json.load(open(f"{P}/reconfig.json")); pf = E.p_follower_steady("vlm_sheet")
def over(kind, Y, vl, m="vlm_sheet"):
    v = j[f"{kind}|{Y}|{vl}|{m}"]; return v["E_f"] - E.p_level(18.0) * v["T"] / 3600.0, v["T"]
o12, t12 = over("split", 369.6, 12.0); o3, t3 = over("split", 369.6, 3.0); o6, t6 = over("split", 369.6, 6.0)
put("ovFast", o12, "{:.2f}"); put("tFast", t12, "{:.0f}"); put("ovSlow", o3, "{:.2f}"); put("tSlow", t3, "{:.0f}")
put("ovMid", o6, "{:.2f}"); put("tMid", t6, "{:.0f}")
put("manuReconf", 3 * 45 * AC.p_hotel * 0 + 3 * 45 * E.p_level(18.0) / 3600, "{:.2f}")

# ------------------------------------------------------------------ mission
S = pd.read_csv(f"{P}/strategy_summary.csv"); PT = pd.read_csv(f"{P}/paired_tests.csv"); DEC = pd.read_csv(f"{P}/decomposition.csv")
mt = pd.read_csv("data/raw/mission_trials.csv")
KEY = {"S1_independent": "SOne", "S2_rigid_V": "STwo", "S3_adaptive_geometric": "SThree", "S4_wake_aware": "SFour", "D1_independent_14": "DOne", "D2_wake_aware_14_as_specified": "DTwo"}
for st, k in KEY.items():
    for metric, kk, fm in (("e_load_Wh", "E", "{:.1f}"), ("e_area_Wh_ha", "Ea", "{:.3f}"), ("t_end_min", "T", "{:.1f}")):
        r = S[(S.model == "vlm_sheet") & (S.strategy == st) & (S.metric == metric)].iloc[0]
        put(f"mis{kk}{k}", r["mean"], fm); put(f"mis{kk}{k}sd", r["sd"], fm)
    put(f"misEmax{k}", mt[(mt.model == "vlm_sheet") & (mt.strategy == st)].e_uav_max_Wh.mean(), "{:.1f}")
for lab, k in (("A:", "A"), ("B:", "B"), ("C:", "C"), ("D:", "D"), ("E:", "E"), ("F:", "F")):
    for m, km in (("vlm_sheet", "Sheet"), ("strip_corrected", "Strip"), ("published", "Pub"), ("vlm_rolled", "Rolled"), ("vlm_free", "Free")):
        r = PT[(PT.model == m) & (PT.metric == "e_area_Wh_ha") & PT.comparison.str.startswith(lab)].iloc[0]
        put(f"rel{k}{km}", r.rel_change_pct, "{:+.1f}"); put(f"relLo{k}{km}", r.rel_p05_pct, "{:+.1f}"); put(f"relHi{k}{km}", r.rel_p95_pct, "{:+.1f}")
    r = PT[(PT.model == "vlm_sheet") & (PT.metric == "e_load_Wh") & PT.comparison.str.startswith(lab)].iloc[0]
    put(f"dWh{k}", r.mean_diff, "{:+.2f}"); put(f"dWhLo{k}", r.ci_lo, "{:+.2f}"); put(f"dWhHi{k}", r.ci_hi, "{:+.2f}")
    put(f"dz{k}", abs(r.dz), "{:.0f}")
for m, km in (("vlm_sheet", "Sheet"), ("vlm_free", "Free"), ("strip_corrected", "Strip"), ("published", "Pub")):
    for comp, kc in (("formation transit only", "Form"), ("route/overlap only", "Route"), ("interaction", "Inter"), ("total (S4 vs S1)", "Tot")):
        r = DEC[(DEC.model == m) & (DEC.component == comp)].iloc[0]; put(f"dec{kc}{km}", r.saving_Wh, "{:+.2f}"); put(f"decPct{kc}{km}", r.saving_pct, "{:+.1f}")
put("absASheet", abs(float(PT[(PT.model == "vlm_sheet") & (PT.metric == "e_area_Wh_ha") & PT.comparison.str.startswith("A:")].rel_change_pct.iloc[0])), "{:.1f}")
put("nTrials", mt.trial.nunique(), "{:d}")
put("savFrac", 100 * mt[(mt.model == "vlm_sheet") & (mt.strategy == "S3_adaptive_geometric")].saving_frac.mean(), "{:.1f}")
# waiting energy
for st, k in (("S3_adaptive_geometric", "SThree"), ("S4_wake_aware", "SFour")):
    put(f"wait{k}", mt[(mt.model == "vlm_sheet") & (mt.strategy == st)].ph_wait.mean(), "{:.1f}")
    put(f"reconf{k}", mt[(mt.model == "vlm_sheet") & (mt.strategy == st)].ph_reconfig.mean(), "{:.1f}")
put("climbLand", mt[(mt.model == "vlm_sheet") & (mt.strategy == "S1_independent")][["ph_climb", "ph_landing"]].sum(axis=1).mean(), "{:.1f}")
put("turnsOne", mt[(mt.model == "vlm_sheet") & (mt.strategy == "S1_independent")].ph_turns.mean(), "{:.1f}")

# break-even distance (zero crossing of the mean, log-D interpolation)
be = pd.read_csv(f"{P}/breakeven_distance.csv")
def cross(model, col):
    g = be[be.model == model].groupby("D")[col].mean(); D = g.index.values.astype(float); y = g.values
    for i in range(len(D) - 1):
        if y[i] < 0 <= y[i + 1]: return math.exp(np.interp(0, [y[i], y[i + 1]], np.log([D[i], D[i + 1]]))) / 1000.0
    return float("nan")
for m, km in (("vlm_sheet", "Sheet"), ("vlm_free", "Free"), ("strip_corrected", "Strip"), ("published", "Pub")):
    for col, kc in (("aero17", "Sev"), ("aero14", "Fourteen")):
        x = cross(m, col); put(f"be{kc}{km}", "never" if np.isnan(x) else f"{x:.1f}")
src = pd.read_csv(f"{P}/sensitivity_src.csv")
for _, r in src.iterrows():
    k = {"transit distance D": "D", "reconfiguration time T": "T", "airspeed Va": "V", "eddy viscosity nu_eff": "Nu", "wake circulation scale": "G", "wind speed (dummy)": "W"}[r.factor]
    put(f"src{k}", r.src, "{:+.2f}")
put("srcRtwo", src.r2.iloc[0], "{:.2f}")

# ------------------------------------------------------------------ geometry
put("gsd", CAM.gsd * 100, "{:.2f}"); put("Wg", CAM.Wg, "{:.1f}"); put("Hg", CAM.Hg, "{:.1f}")
put("dyBase", CAM.Wg * (1 - CAM.os_base), "{:.1f}"); put("dyOpt", CAM.Wg * (1 - CAM.os_opt), "{:.2f}")
c14 = photo.strip_centres(14, CAM.Wg * (1 - CAM.os_opt)); m14 = photo.multiplicity_map(c14, None)
put("minMultFourteen", int(m14.min()), "{:d}"); put("meanMultFourteen", float(m14.mean()), "{:.1f}")
c17 = photo.strip_centres(17, CAM.Wg * (1 - CAM.os_base)); m17 = photo.multiplicity_map(c17, None)
put("minMultSeven", int(m17.min()), "{:d}"); put("meanMultSeven", float(m17.mean()), "{:.1f}")
put("accFourteen", photo.accepted_area(m14)[0], "{:.0f}")
put("BHbase", CAM.Wg * (1 - CAM.os_base) / CAM.agl, "{:.2f}"); put("BHopt", CAM.Wg * (1 - CAM.os_opt) / CAM.agl, "{:.2f}")
put("edgeFailM", (c14[1] - CAM.Wg / 2) , "{:.1f}")
put("MarginOverlap", 100 * (1 - 74.0 / CAM.Wg), "{:.2f}")

# ------------------------------------------------------------------ write macros
def tex_name(n): return "\\" + "n" + n
with open(f"{OUT}/numbers.tex", "w") as f:
    f.write("% AUTO-GENERATED by experiments/make_numbers.py -- do not edit by hand\n")
    for k, v in sorted(mac.items()):
        f.write(f"\\newcommand{{\\n{k}}}{{{v}}}\n")
print(len(mac), "macros")

# ------------------------------------------------------------------ tables
def esc(s): return s.replace("_", "\\_").replace("%", "\\%")
rows = []
for st, k in list(KEY.items())[:5]:
    g = S[(S.model == "vlm_sheet") & (S.strategy == st)].set_index("metric")
    lab = {"S1_independent": "S1 Independent", "S2_rigid_V": "S2 Rigid V", "S3_adaptive_geometric": "S3 Adaptive geometric V", "S4_wake_aware": "S4 Wake-aware adaptive V", "D1_independent_14": "D1 Independent, 14-strip route"}[st]
    rows.append(f"{lab} & {g.loc['e_load_Wh','mean']:.1f} $\\pm$ {g.loc['e_load_Wh','sd']:.1f} & {mt[(mt.model=='vlm_sheet')&(mt.strategy==st)].e_uav_max_Wh.mean():.1f} & {g.loc['t_end_min','mean']:.1f} & {g.loc['accepted_ha','mean']:.0f} & {g.loc['e_area_Wh_ha','mean']:.3f} $\\pm$ {g.loc['e_area_Wh_ha','sd']:.3f} ")
open(f"{OUT}/tables/tab_strategies.tex", "w").write(" \\\\\n".join(rows) + "\n")
rows = []
for lab, k in (("A:", "A"), ("B:", "B"), ("C:", "C"), ("D:", "D"), ("E:", "E"), ("F:", "F")):
    name = {"A": "S4 vs S1 (full framework)", "B": "S3 vs S1 (formation only)", "C": "S2 vs S1 (rigid V)", "D": "S3 vs S2 (adaptive vs rigid)", "E": "S4 vs D1 (formation, 14-strip route)", "F": "D1 vs S1 (route/overlap only)"}[k]
    cells = []
    for m in ("vlm_sheet", "vlm_rolled", "vlm_free", "strip_corrected", "published"):
        r = PT[(PT.model == m) & (PT.metric == "e_area_Wh_ha") & PT.comparison.str.startswith(lab)].iloc[0]
        cells.append(f"{r.rel_change_pct:+.1f} ({r.rel_p05_pct:+.1f}, {r.rel_p95_pct:+.1f})")
    rows.append(f"{name} & " + " & ".join(cells))
open(f"{OUT}/tables/tab_paired.tex", "w").write(" \\\\\n".join(rows) + "\n")
rows = []
order = ["S1_turbulence", "S2_gust_doublet", "S3_braking_dropout", "S4_degraded_gnss", "S5_combined", "S6_overcapability"]
nm = {"S1_turbulence": "S1 turbulence", "S2_gust_doublet": "S2 gust doublet 8.5 m/s", "S3_braking_dropout": "S3 leader braking + dropout", "S4_degraded_gnss": "S4 degraded GNSS", "S5_combined": "S5 combined", "S6_overcapability": "S6 over-capability braking"}
for sc in order:
    cells = []
    for ctl in ("P", "NMPC", "NMPC+CBF"):
        r = g_ = c[(c.scenario == sc) & (c.controller == ctl)]
        cells.append(f"{r.rms_ey.mean():.2f} / {r.min_sep.min():.2f} / {100*r.violated.mean():.0f}")
    rows.append(f"{nm[sc]} & " + " & ".join(cells))
open(f"{OUT}/tables/tab_control.tex", "w").write(" \\\\\n".join(rows) + "\n")
rows = []
for _, r in t33.iterrows():
    rows.append(f"{r.dy_b:.2f} & {r.w_table:+.4f} & {r.w_recomputed:+.4f} & {r.cl_table:+.4f} & {r.cl_recomputed:+.4f} & {r.pct_table:+.2f} & {r.pct_recomputed:+.2f}")
open(f"{OUT}/tables/tab_audit33.tex", "w").write(" \\\\\n".join(rows) + "\n")
print("tables written")
