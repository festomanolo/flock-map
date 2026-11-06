import sys, os, math, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from style import *
from flockmap import aero, vlm, energy as E, mission as M, battery
from flockmap.config import AC, CAM

setup(); P = "data/processed"
DIV = LinearSegmentedColormap.from_list("div", [C["orange"], "#f0efec", C["blue"]])
SEQ = LinearSegmentedColormap.from_list("seq", ["#f0f4fb", C["blue"], "#0d366b"])


def X1_dz():
    z = np.load(f"{P}/extra_dz.npz"); dy, dz = z["dy"], z["dz"]
    fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.7), gridspec_kw=dict(width_ratios=[1, 1, 0.9]))
    for ax, key, ttl, l in ((axs[0], "pct_sheet", "VLM planar sheet", "a"), (axs[1], "pct_free", "VLM free wake", "b")):
        v = z[key]; cf = ax.contourf(dy, dz, v, levels=np.linspace(-8, 8, 17), cmap=DIV, norm=TwoSlopeNorm(0, -8, 8), extend="both")
        ax.contour(dy, dz, v, levels=[0], colors=C["ink"], linewidths=1.0); ax.plot(0.85, 0.0, "ko", ms=3.5)
        ax.set_xlabel("$d_y/b$"); ax.set_title(ttl, fontsize=8); panel(ax, l)
    axs[0].set_ylabel("vertical offset $d_z/b$ (+ above)"); cb = fig.colorbar(cf, ax=axs[:2], shrink=0.9, pad=0.01); cb.set_label("follower power saving (%)")
    ax = axs[2]; panel(ax, "c"); j = np.argmin(abs(dy - 0.85))
    ax.plot(dz, z["pct_sheet"][:, j], color=C["blue"], label="sheet"); ax.plot(dz, z["pct_free"][:, j], color=C["violet"], label="free wake")
    ax.axhline(0, color=C["axis"], lw=0.8); ax.set_xlabel("$d_z/b$ ($d_y=0.85b$)"); ax.set_ylabel("saving (%)"); ax.legend()
    save(fig, "X1_vertical_offset")


def X2_kappa():
    d = pd.read_csv(f"{P}/extra_kappa_map.csv"); sw = pd.read_csv(f"{P}/aero_sweep_dy.csv")
    pk = {m: sw[(sw.model == m) & (sw.dy_b <= 1.6)].pct_power.max() for m in ("vlm_sheet", "vlm_free", "strip_corrected")}
    kfree = pk["vlm_free"] / pk["vlm_sheet"]; kstrip = pk["strip_corrected"] / pk["vlm_sheet"]
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.0), sharey=True)
    for ax, col, ttl, l in ((axs[0], "saving17_Wh", "17-strip route (S3 vs S1)", "a"), (axs[1], "saving14_Wh", "14-strip route (S4 vs D1)", "b")):
        t = d.pivot(index="D", columns="kappa", values=col); K, D = np.meshgrid(t.columns.values, t.index.values / 1000)
        lim = float(np.abs(t.values).max()); cf = ax.contourf(K, D, t.values, levels=np.linspace(-lim, lim, 21), cmap=DIV, norm=TwoSlopeNorm(0, -lim, lim))
        ax.contour(K, D, t.values, levels=[0], colors=C["ink"], linewidths=1.4)
        for kv, lab in ((1.0, "sheet"), (kfree, "free wake"), (kstrip, "strip")):
            ax.axvline(kv, color=C["ink2"], ls=":", lw=0.9); ax.text(kv, 19.2, lab, rotation=90, fontsize=6.5, va="top", ha="right", color=C["ink2"])
        ax.set_yscale("log"); ax.set_yticks([1, 2, 5, 10, 20]); ax.set_yticklabels(["1", "2", "5", "10", "20"]); ax.set_xlabel("wake effectiveness $\\kappa$ (1 = planar sheet)"); ax.set_title(ttl, fontsize=8); panel(ax, l)
        fig.colorbar(cf, ax=ax, shrink=0.9, pad=0.02).set_label("fleet saving (Wh)")
    axs[0].set_ylabel("one-way transit distance (km)")
    save(fig, "X2_kappa_distance_map")


def X3_sens():
    t = pd.read_csv(f"{P}/extra_tornado.csv"); s = pd.read_csv(f"{P}/extra_sobol.csv")
    fig, axs = plt.subplots(1, 2, figsize=(7.6, 2.9), gridspec_kw=dict(width_ratios=[1.32, 1], wspace=0.52))
    ax = axs[0]; panel(ax, "a"); base = t.base_Wh.iloc[0]
    order = t.assign(a=t.delta_Wh.abs()).groupby("factor").a.max().sort_values().index
    for i, f in enumerate(order):
        for lab, c in (("low", C["orange"]), ("high", C["blue"])):
            r = t[(t.factor == f) & (t.setting == lab)].iloc[0]; ax.barh(i, r.delta_Wh, color=c, height=0.6, edgecolor="white")
            if abs(r.delta_Wh) < 0.08:
                dx_txt = -0.14 if lab == "low" else 0.14
                ha_txt = "right" if lab == "low" else "left"
            else:
                dx_txt = 0.14 if r.delta_Wh >= 0 else -0.14
                ha_txt = "left" if r.delta_Wh >= 0 else "right"
            ax.text(r.delta_Wh + dx_txt, i, f"{r.value:g}", fontsize=6, va="center", ha=ha_txt, color=C["ink2"])
    ax.set_xlim(-4.35, 5.1)
    ax.set_yticks(range(len(order))); ax.set_yticklabels(order, fontsize=6.5); ax.axvline(0, color=C["ink"], lw=0.8); ax.set_xlabel(f"change in fleet saving S3 vs S1 (Wh); baseline {base:.2f} Wh"); ax.grid(axis="y", visible=False)
    ax = axs[1]; panel(ax, "b"); y = np.arange(len(s)); o = np.argsort(s.ST.values)
    ax.barh(y - 0.18, s.S1.values[o], height=0.34, color=C["blue"], label="first order $S_i$"); ax.barh(y + 0.18, s.ST.values[o], height=0.34, color=C["aqua"], label="total $S_{Ti}$")
    ax.set_yticks(y); ax.set_yticklabels(s.factor.values[o], fontsize=6.5); ax.set_xlabel("Sobol index"); ax.legend(fontsize=6.5); ax.grid(axis="y", visible=False)
    save(fig, "X3_tornado_sobol")


def X4_skerr():
    d = pd.read_csv(f"{P}/extra_skerr.csv"); fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.7))
    ax = axs[0]; panel(ax, "a")
    for m, c in (("vlm_sheet", C["blue"]), ("vlm_free", C["violet"]), ("strip_corrected", C["orange"])):
        s = d[(d.model == m) & (d.dy_b == 0.85)]; ax.plot(s.sigma_m, s.saving_pct, "o-", ms=3, color=c, label=MODEL[m][0].replace("VLM follower, ", "VLM ").replace("Strip theory, corrected", "Strip, corrected"))
    ax.set_xlabel("station-keeping error $\\sigma_y$ (m), $d_y=0.85b$"); ax.set_ylabel("expected saving (%)"); ax.legend(fontsize=6.3)
    ax = axs[1]; panel(ax, "b")
    for dy, ls in ((0.80, "--"), (0.85, "-"), (0.90, ":")):
        s = d[(d.model == "vlm_sheet") & (d.dy_b == dy)]; ax.plot(s.sigma_m, s.saving_pct, ls, color=C["blue"], label=f"$d_y/b={dy:.2f}$")
    ax.set_xlabel("$\\sigma_y$ (m), VLM planar sheet"); ax.legend(fontsize=6.5)
    save(fig, "X4_station_keeping_error")


def X5_coverage():
    d = pd.read_csv(f"{P}/extra_coverage.csv"); fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.7))
    ax = axs[0]; panel(ax, "a")
    for crab, c in ((0.0, C["red"]), (3.0, C["orange"]), (6.0, C["yellow"]), (12.0, C["aqua"]), (19.0, C["blue"])):
        s = d[d.crab_deg == crab]; ax.plot(s.side_overlap * 100, s.accepted_ha, color=c, label=f"crab {crab:g}°")
    ax.set_xlabel("side overlap (%)"); ax.set_ylabel("accepted area (ha)"); ax.legend(fontsize=6); ax.set_ylim(60, 103)
    ax = axs[1]; panel(ax, "b"); s = d[d.crab_deg == 0.0]
    ax.step(s.side_overlap * 100, s.n_strips, where="mid", color=C["violet"]); ax.set_xlabel("side overlap (%)"); ax.set_ylabel("strips for 1 km", color=C["violet"]); ax.tick_params(axis="y", labelcolor=C["violet"])
    ax = axs[2]; panel(ax, "c"); ax.plot(s.side_overlap * 100, s.BH, color=C["blue"], label="$B/H$ (adjacent strips)"); ax.plot(s.side_overlap * 100, s.min_mult / 10.0, color=C["red"], label="min. rays/10")
    ax.axvline(58, color=C["ink2"], ls=":", lw=0.8); ax.axvline(65, color=C["ink2"], ls=":", lw=0.8); ax.set_xlabel("side overlap (%)"); ax.legend(fontsize=6)
    save(fig, "X5_overlap_sweep")


def X6_power():
    d = pd.read_csv(f"{P}/extra_power.csv"); fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.7))
    ax = axs[0]; panel(ax, "a"); ax.plot(d.va, d.p_elec, color=C["blue"], label="electrical"); ax.plot(d.va, d.p_aero, color=C["aqua"], label="aerodynamic")
    i = d.p_elec.idxmin(); ax.plot(d.va[i], d.p_elec[i], "ko", ms=4); ax.text(d.va[i] + 0.4, d.p_elec[i] + 12, f"min {d.p_elec[i]:.0f} W\nat {d.va[i]:.1f} m/s", fontsize=6.3)
    ax.set_xlabel("airspeed (m/s)"); ax.set_ylabel("power (W)"); ax.legend(fontsize=6.3)
    ax = axs[1]; panel(ax, "b"); ax.plot(d.va, d.e_per_km_Wh, color=C["violet"]); j = d.e_per_km_Wh.idxmin(); ax.plot(d.va[j], d.e_per_km_Wh[j], "ko", ms=4)
    ax.text(d.va[j] + 0.4, d.e_per_km_Wh[j] + 0.6, f"best range {d.va[j]:.1f} m/s\n{d.e_per_km_Wh[j]:.1f} Wh/km", fontsize=6.3); ax.set_xlabel("airspeed (m/s)"); ax.set_ylabel("energy per km (Wh/km)")
    ax = axs[2]; panel(ax, "c")
    for k, c, l in (("sav_sheet", C["blue"], "sheet"), ("sav_free", C["violet"], "free wake"), ("sav_strip", C["orange"], "strip")): ax.plot(d.va, d[k], color=c, label=l)
    ax.set_xlabel("airspeed (m/s)"); ax.set_ylabel("formation saving (%)"); ax.legend(fontsize=6.3)
    save(fig, "X6_power_curve")


def X7_reconfig():
    j = json.load(open(f"{P}/reconfig.json")); rows = []
    for k, v in j.items():
        kind, Y, vl, m = k.split("|")
        if m == "vlm_sheet": rows.append(dict(kind=kind, Y=float(Y), vlat=float(vl), T=v["T"], over=v["E_f"] - E.p_level(18.0) * v["T"] / 3600.0, bank=v["max_bank_deg"], sd=v["E_f_sd"]))
    d = pd.DataFrame(rows); fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.6))
    for ax, l in zip(axs, "abc"): panel(ax, l)
    for Y, c in ((60.0, C["aqua"]), (369.6, C["violet"])):
        for kind, mk in (("split", "o"), ("merge", "s")):
            s = d[(d.kind == kind) & (d.Y == Y)].sort_values("T"); axs[0].plot(s["T"], s.over, mk + "-", ms=3, color=c, label=f"{kind} Y={Y:g} m"); axs[1].plot(s.vlat, s.over, mk + "-", ms=3, color=c); axs[2].plot(s.vlat, s.bank, mk + "-", ms=3, color=c)
    axs[0].set_xlabel("window $T$ (s)"); axs[0].set_ylabel("energy above isolated cruise (Wh)"); axs[0].legend(fontsize=5.8); axs[1].set_xlabel("peak lateral speed (m/s)"); axs[2].set_xlabel("peak lateral speed (m/s)"); axs[2].set_ylabel("max bank (deg)")
    save(fig, "X7_reconfiguration_law")


def X8_mc():
    d = pd.read_csv("data/raw/mission_trials.csv"); d = d[d.model == "vlm_sheet"]
    pv_ = d.pivot(index="trial", columns="strategy", values="e_load_Wh"); fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.8))
    ax = axs[0]; panel(ax, "a"); diff = (pv_["S3_adaptive_geometric"] - pv_["S1_independent"]).values; n = np.arange(1, len(diff) + 1)
    rm = np.cumsum(diff) / n; rng = np.random.default_rng(0)
    ci = [np.percentile([rng.choice(diff[:k], k).mean() for _ in range(300)], [2.5, 97.5]) for k in (5, 10, 20, 40, 80, 120, 160, 200)]
    ax.plot(n, rm, color=C["blue"]); ax.fill_between([5, 10, 20, 40, 80, 120, 160, 200], [c[0] for c in ci], [c[1] for c in ci], color=C["blue"], alpha=0.25, lw=0)
    ax.set_xlabel("trials $N$"); ax.set_ylabel("mean S3 − S1 (Wh)")
    ax = axs[1]; panel(ax, "b"); w = d[d.strategy == "S1_independent"].set_index("trial")
    sc = ax.scatter(w.wind, pv_["S1_independent"], c=np.degrees(w.wind_dir) % 360, cmap="twilight", s=8, lw=0); ax.set_xlabel("wind speed (m/s)"); ax.set_ylabel("S1 fleet energy (Wh)")
    cb = fig.colorbar(sc, ax=ax); cb.set_label("wind direction (deg)")
    ax = axs[2]; panel(ax, "c"); ax.remove(); ax = fig.add_subplot(1, 3, 3, projection="polar")
    th = w.wind_dir.values; ax.scatter(th, diff, s=6, color=C["violet"]); ax.set_title("S3 − S1 (Wh) vs wind direction", fontsize=7); ax.tick_params(labelsize=6)
    fig.tight_layout(); save(fig, "X8_monte_carlo_diagnostics")


def X9_timeline():
    from run_extra import load_env_series, load_rc
    series = load_env_series(); env = M.Env(3.5, 1.0, series[0]); rc = load_rc("vlm_sheet")
    fig, axs = plt.subplots(3, 3, figsize=(7.4, 5.2), sharex="col")
    pc = {"climb": C["muted"], "transit": C["blue"], "mapping": C["aqua"], "turns": C["orange"], "ferry": C["yellow"], "wait": C["magenta"], "reconfig": C["violet"], "landing": "#383835"}
    for k, st in enumerate(("S1_independent", "S3_adaptive_geometric", "S4_wake_aware")):
        r = M.run(st, env, "vlm_sheet", rc)
        for u in range(3):
            ax = axs[u, k]; t0 = 0.0; soc = 1.0
            for ph, p, t in r.timeline[u]:
                ax.fill_between([t0 / 60, (t0 + t) / 60], 0, p, color=pc[ph], lw=0); t0 += t
            ax.set_ylim(0, 190)
            if k == 0: ax.set_ylabel(f"UAV {u}\npower (W)")
            if u == 0: ax.set_title({"S1_independent": "S1 independent", "S3_adaptive_geometric": "S3 adaptive geometric V", "S4_wake_aware": "S4 wake-aware"}[st], fontsize=7.5)
            if u == 2: ax.set_xlabel("time (min)")
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=v, label=k) for k, v in pc.items()], ncol=8, loc="lower center", fontsize=6.3, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=[0, 0.04, 1, 1]); save(fig, "X9_power_timeline")


def X10_soc():
    d = pd.read_csv("data/raw/mission_trials.csv"); d = d[d.model == "vlm_sheet"]
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.7)); ax = axs[0]; panel(ax, "a")
    strat = ["S1_independent", "S3_adaptive_geometric", "S4_wake_aware", "D1_independent_14"]
    for i, s in enumerate(strat):
        g = d[d.strategy == s]; ax.errorbar(i - 0.12, g.e_uav_max_Wh.mean(), yerr=g.e_uav_max_Wh.std(), fmt="o", color=STRAT[s][1], ms=4, capsize=2); ax.errorbar(i + 0.12, g.e_uav_min_Wh.mean(), yerr=g.e_uav_min_Wh.std(), fmt="s", color=STRAT[s][1], ms=4, capsize=2, mfc="white")
    ax.set_xticks(range(4)); ax.set_xticklabels(["S1", "S3", "S4", "D1"]); ax.set_ylabel("per-UAV energy (Wh): max (●) / min (○)"); ax.axhline(0.8 * 22.2 * 10, color=C["red"], ls="--", lw=0.8); ax.set_yscale("linear")
    ax.text(3.4, 0.8 * 222 - 6, "usable battery 178 Wh", fontsize=6.3, ha="right", color=C["red"]); ax.set_ylim(20, 190)
    ax = axs[1]; panel(ax, "b")
    s3 = d[d.strategy == "S3_adaptive_geometric"]; pform = E.p_follower_steady("vlm_sheet"); piso = E.p_level(18.0)
    t_form = s3.ph_transit.values / (( piso + 2 * pform) / 3.0) * 3600 / 3        # per-UAV formation-transit time (s)
    imb_norot = (piso - pform) * t_form / 3600.0
    ax.hist(imb_norot, bins=18, color=C["violet"], alpha=0.8); ax.set_xlabel("leader-vs-follower energy gap without rotation (Wh)"); ax.set_ylabel("trials")
    ax.text(0.96, 0.94, "with cyclic rotation the gap\nin formation phases is zero", transform=ax.transAxes, fontsize=6.5, ha="right", va="top", bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="none", alpha=0.88))
    save(fig, "X10_leader_rotation_energy")


def X11_control_stats():
    c = pd.read_csv("data/raw/control_trials.csv"); fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.7))
    cols = {"P": C["orange"], "NMPC": C["blue"], "NMPC+CBF": C["violet"]}
    clab = {"P": "PD", "NMPC": "NMPC", "NMPC+CBF": "NMPC+HOCBF"}
    ax = axs[0]; panel(ax, "a")
    for k, cc in cols.items():
        v = np.sort(c[(c.controller == k) & (c.scenario == "S5_combined")].rms_ey.values); ax.step(v, np.arange(1, len(v) + 1) / len(v), color=cc, label=clab[k])
    ax.set_xlabel("RMS lateral error, S5 (m)"); ax.set_ylabel("empirical CDF"); ax.legend(fontsize=6.3)
    ax = axs[1]; panel(ax, "b")
    for k in ("NMPC", "NMPC+CBF"):
        v = np.sort(c[(c.controller == k)].solve_ms_max.values); ax.step(v, np.arange(1, len(v) + 1) / len(v), color=cols[k], label=clab[k])
    ax.axvline(100, color=C["red"], ls="--", lw=0.8); ax.text(102, 0.1, "10 Hz budget", fontsize=6.3, color=C["red"]); ax.set_xlabel("worst solve time per run (ms)"); ax.set_xscale("log"); ax.legend(fontsize=6.3)
    ax = axs[2]; panel(ax, "c"); sc = ["S1_turbulence", "S2_gust_doublet", "S3_braking_dropout", "S4_degraded_gnss", "S5_combined", "S6_overcapability"]
    for j, k in enumerate(cols):
        ax.bar(np.arange(6) + (j - 1) * 0.27, [c[(c.controller == k) & (c.scenario == s)].max_abs_ey.mean() for s in sc], width=0.25, color=cols[k], edgecolor="white")
    ax.set_xticks(range(6)); ax.set_xticklabels([f"S{i+1}" for i in range(6)]); ax.set_ylabel("mean peak |$e_y$| (m)")
    save(fig, "X11_control_statistics")


def X12_cbf():
    d = pd.read_csv(f"{P}/extra_cbf_ablation.csv"); s = pd.read_csv(f"{P}/extra_step.csv")
    fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.7)); cols = {"S3_braking_dropout": C["blue"], "S5_combined": C["orange"], "S6_overcapability": C["red"]}
    for ax, col, yl, l in ((axs[0], "violated", "trials with $h<0$ (%)", "a"), (axs[1], "rms_ey", "RMS lateral error (m)", "b"), (axs[2], "mean_dcd", "mean $\\Delta C_D \\times 10^4$", "c")):
        panel(ax, l)
        mult = 100.0 if col == "violated" else (1e4 if col == "mean_dcd" else 1.0)
        for sc, cc in cols.items():
            g = d[d.scenario == sc].groupby("margin")[col].mean(); ax.plot(g.index, g.values * mult, "o-", ms=3.5, color=cc, label=sc.split("_")[0])
        ax.axvline(0.5, color=C["ink2"], ls=":", lw=0.8)
        ax.set_xlabel("HOCBF margin $\\Delta D$ (m)"); ax.set_ylabel(yl)
    axs[0].legend(fontsize=6.3)
    save(fig, "X12_cbf_margin_ablation")
    fig, ax = plt.subplots(figsize=(3.8, 2.5)); g = s.groupby("controller")[["overshoot_pct", "settle2_s"]].mean().reindex(["P", "NMPC", "NMPC+CBF"])
    ax.bar(np.arange(3) - 0.2, g.overshoot_pct, width=0.38, color=C["blue"], label="overshoot (%)"); ax.bar(np.arange(3) + 0.2, g.settle2_s, width=0.38, color=C["orange"], label="2 % settling time (s)")
    ax.set_xticks(range(3)); ax.set_xticklabels(["PD", "NMPC", "NMPC+HOCBF"], fontsize=7); ax.legend(fontsize=6.5); save(fig, "X12b_step_response")


if __name__ == "__main__":
    for f in (sys.argv[1:] or ["X1_dz", "X2_kappa", "X3_sens", "X4_skerr", "X5_coverage", "X6_power", "X7_reconfig", "X8_mc", "X9_timeline", "X10_soc", "X11_control_stats", "X12_cbf"]):
        try: globals()[f](); print("ok", f)
        except Exception as e:
            import traceback; traceback.print_exc(); print("FAIL", f, e)
