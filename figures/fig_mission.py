import sys, os, math, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Polygon
from style import *
from flockmap import photo, mission as M, energy as E, control as CT
from flockmap.config import AC, CAM, MIS

setup(); P = "data/processed"; B = AC.b
ST = pd.read_csv(f"{P}/strategy_summary.csv"); PT = pd.read_csv(f"{P}/paired_tests.csv")
MT = pd.read_csv("data/raw/mission_trials.csv")
HEAD = "vlm_sheet"
ORDER = ["S1_independent", "S2_rigid_V", "S3_adaptive_geometric", "S4_wake_aware"]


# --------------------------------------------------------------------------------------------- Fig 5 geometry
def fig05():
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0), gridspec_kw=dict(width_ratios=[1.6, 1]))
    ax = axs[0]
    dx, dy = 3 * B, 0.85 * B
    def wing(x0, y0, c):
        hb = B / 2; pts = np.array([[0.30, 0], [0.0, -0.12], [-0.38, -hb], [-0.58, -hb], [-0.50, -0.18], [-0.50, 0.18], [-0.58, hb], [-0.38, hb], [0.0, 0.12]])
        ax.add_patch(Polygon(np.column_stack([-(pts[:, 0] + x0) * -1 * 1, pts[:, 1] + y0]) * [1, 1], closed=True, fc=c, ec=C["ink"], lw=0.7, zorder=5))
    for (x0, y0, c) in ((0, 0, C["violet"]), (-dx, -dy, C["aqua"]), (-dx, dy, C["aqua"])): wing(x0, y0, c)
    ax.plot([0, -dx], [0, dy], color=C["ink2"], lw=0.8, ls="--"); ax.plot([0, -dx], [0, -dy], color=C["ink2"], lw=0.8, ls="--")
    ax.add_patch(plt.Circle((0, 0), 2 * B, fill=False, ec=C["red"], ls=":", lw=1)); ax.text(-2 * B * 0.7, 2 * B * 0.78, "$D_{safe}=2b$", color=C["red"], fontsize=7)
    for sgn in (-1, 1): ax.plot([0, -9], [sgn * AC.b0 / 2] * 2, color=C["red"], lw=1.2, alpha=0.8)
    ax.annotate("", (-dx, -3.75), (0, -3.75), arrowprops=dict(arrowstyle="<->", lw=0.8)); ax.text(-dx / 2, -4.22, f"$d_x=3b={dx:.2f}$ m", ha="center", fontsize=7)
    ax.annotate("", (-dx - 0.95, -dy), (-dx - 0.95, dy), arrowprops=dict(arrowstyle="<->", lw=0.8)); ax.text(-dx - 1.25, 0, f"$2d_y=1.7b={2*dy:.2f}$ m", rotation=90, va="center", ha="left", fontsize=7)
    ax.annotate("", (-0.3, 0.0), (-0.3, AC.b0 / 2), arrowprops=dict(arrowstyle="<->", lw=0.6)); ax.text(0.6, AC.b0 / 4, "$b_0/2$", fontsize=6.5)
    ax.annotate("", (1.15, B / 2), (1.15, -B / 2), arrowprops=dict(arrowstyle="<->", lw=0.8)); ax.text(1.45, 0, f"$b={B}$ m", rotation=90, va="center", ha="right", fontsize=7)
    ax.text(0, -B / 2 - 0.48, "Leader", ha="center", fontsize=7); ax.text(-dx, dy + B / 2 + 0.25, "Follower 2", ha="center", fontsize=7); ax.text(-dx, -dy - B / 2 - 0.35, "Follower 1", ha="center", fontsize=7)
    ax.set_xlim(-dx - 3.8, 3.2); ax.set_ylim(-4.65, 4.2); ax.invert_xaxis(); ax.set_aspect("equal"); ax.set_xlabel("flight direction  →  (x, m; leader at 0)"); ax.set_ylabel("$y$ (m)"); ax.grid(False)
    ax.set_title("Top view (planform schematic, not the exact X8 outline)", fontsize=7.5); panel(ax, "a")
    ax = axs[1]
    for (x0, c, lab) in ((0, C["violet"], "L"), (-dx, C["aqua"], "F")):
        ax.add_patch(Rectangle((x0 - 0.5, -0.04), 1.0, 0.08, fc=c, ec=C["ink"], lw=0.6)); ax.text(x0, 0.18, lab, ha="center", fontsize=7)
    ax.annotate("", (-dx, -0.35), (0, -0.35), arrowprops=dict(arrowstyle="<->", lw=0.8)); ax.text(-dx / 2, -0.62, "$d_x$", ha="center", fontsize=7)
    ax.text(-dx / 2, 0.45, "$d_z=0$ (co-altitude)", ha="center", fontsize=7)
    ax.set_xlim(1.5, -dx - 1.5); ax.set_ylim(-1.1, 1.0); ax.set_aspect("equal"); ax.set_xlabel("$x$ (m)"); ax.set_yticks([]); ax.grid(False); ax.spines["left"].set_visible(False)
    ax.set_title("Side view", fontsize=7.5); panel(ax, "b")
    ax.text(0.5, -0.9, f"3-D centre distance leader–follower = {math.hypot(dx, dy):.2f} m  ({math.hypot(dx, dy)/(2*B):.2f}× $D_{{safe}}$)", transform=ax.transAxes, fontsize=6.5, ha="center", va="center")
    fig.tight_layout(); save(fig, "fig05_formation_geometry")


# --------------------------------------------------------------------------------------------- Fig 6 missions
def _strip_xy(n, s, x_off=0.0):
    return photo.strip_centres(n, s) if x_off == 0 else photo.strip_centres(n, s)


def fig06():
    fig, axs = plt.subplots(1, 4, figsize=(7.4, 3.9), sharey=True)
    cfg = [("S1_independent", "17@65"), ("S2_rigid_V", "17@65"), ("S3_adaptive_geometric", "17@65"), ("S4_wake_aware", "14@57.95")]
    zc = [C["blue"], C["orange"], C["aqua"]]
    for ax, (st, plan) in zip(axs, cfg):
        pl = M.PLAN[plan]; n = pl["n"]; s = pl["spacing"]; xs = photo.strip_centres(sum(n), s)
        ax.add_patch(Rectangle((0, 0), 1000, 1000, fc="none", ec=C["ink"], lw=0.8))
        k = 0
        for u in range(3):
            cnt = sum(n) if st == "S2_rigid_V" else n[u]
            if st == "S2_rigid_V" and u > 0: break
            for i in range(cnt):
                x = xs[k]; k += 1
                ax.plot([x, x], [0, 1000], color=zc[u] if st != "S2_rigid_V" else C["violet"], lw=0.9)
                if i % 2 == 0 and i + 1 < cnt and k < len(xs): ax.plot([x, xs[k]], [1000, 1000 + 45], color=C["ink2"], lw=0.4)
        # camera footprints on 2 strips
        for x in (xs[len(xs) // 2], xs[len(xs) // 2 + 1]):
            for y0 in (400, 400 + CAM.Hg * (1 - CAM.of)):
                ax.add_patch(Rectangle((x - CAM.Wg / 2, y0 - CAM.Hg / 2), CAM.Wg, CAM.Hg, fc=C["yellow"], ec=C["ink2"], lw=0.3, alpha=0.18))
        ax.plot([500, 500], [-420, 0], color=C["ink"], lw=1.1, ls="--" if st == "S1_independent" else "-")
        if st == "S1_independent":
            for u, x in enumerate(((n[0] / 2) * s * 0 + xs[0 + 2], xs[n[0] + 2], xs[n[0] + n[1] + 1])): ax.plot([500, x], [-420, 0], color=zc[u], lw=0.8)
        elif st in ("S3_adaptive_geometric", "S4_wake_aware"):
            ax.plot([500], [-180], "D", color=C["red"], ms=4); ax.text(530, -180, "split/merge", fontsize=6, va="center")
        ax.set_xlim(-130, 1130); ax.set_ylim(-470, 1120); ax.set_aspect("equal"); ax.grid(False)
        ax.set_title({"S1_independent": "S1 independent\n17 strips, 6-6-5", "S2_rigid_V": "S2 rigid V\n17 strips ×3 aircraft", "S3_adaptive_geometric": "S3 adaptive geometric\n17 strips, 6-6-5", "S4_wake_aware": "S4 wake-aware\n14 strips, 5-5-4"}[st], fontsize=7)
        ax.set_xlabel("$x$ (m)")
    axs[0].set_ylabel("$y$ (m); transit continues south to 2500 m")
    fig.text(0.5, -0.01, "Dashed/solid vertical line: transit leg (axis truncated). Yellow: sample camera footprints (176 × 117 m). Turn arcs between strips are schematic (Dubins loops, 423–441 m long).", ha="center", fontsize=6.5, color=C["ink2"])
    fig.tight_layout(); save(fig, "fig06_mission_comparison")


# --------------------------------------------------------------------------------------------- Fig 7 control
def fig07():
    ts = np.load("data/raw/control_ts.npz")
    fig, axs = plt.subplots(3, 2, figsize=(7.2, 6.0)); axs = axs.ravel()
    cols = {"P": C["orange"], "NMPC": C["blue"], "NMPC+CBF": C["violet"]}
    clab = {"P": "PD", "NMPC": "NMPC", "NMPC+CBF": "NMPC+HOCBF"}
    seed = 0
    for c in ("P", "NMPC", "NMPC+CBF"):
        g = lambda k: ts[f"S5_combined|{c}|{seed}|{k}"]
        t = g("t"); axs[0].plot(t, g("dy"), color=cols[c], label=clab[c]); axs[1].plot(t, g("ex"), color=cols[c])
        axs[2].plot(t, g("dist"), color=cols[c]); axs[3].plot(t, g("phi"), color=cols[c]); axs[4].plot(t, g("V"), color=cols[c])
    t = ts[f"S5_combined|P|{seed}|t"]; axs[0].plot(t, np.full_like(t, 1.70), "k--", lw=0.8, label="commanded slot"); axs[2].axhline(4.24, color=C["red"], ls="--", lw=0.9)
    axs[2].text(1, 4.45, "$D_{safe}=4.24$ m", color=C["red"], fontsize=6.5)
    for a_ in axs[:5]: a_.axvspan(15, 15.5, color=C["grid"], alpha=0.8, lw=0); a_.axvspan(15, 17.0, color=C["yellow"], alpha=0.12, lw=0)
    for a, l, y in zip(axs[:5], "abcde", ("lateral offset $d_y$ (m)", "longitudinal error $e_x$ (m)", "leader–follower separation (m)", "bank angle $\\phi$ (deg)", "airspeed $V_a$ (m/s)")):
        a.set_ylabel(y); a.set_xlabel("time (s)"); panel(a, l)
    axs[0].legend(ncol=2, loc="lower left")
    # reconfiguration trace
    sc = CT.Scenario("r", 110, 3.0, 1.0, slot=(6.36, 1.70), slot_sched=((5.0, 62.7, 6.36, 369.6),))
    r = CT.simulate(sc, "NMPC", seed=1)
    ax = axs[5]; ax.plot(r["t"], r["dys"], "k--", lw=0.8, label="commanded"); ax.plot(r["t"], r["dy"], color=C["blue"], label="NMPC"); ax.set_ylabel("lateral offset (m)"); ax.set_xlabel("time (s)"); ax.legend(); panel(ax, "f")
    ax2 = ax.twinx(); ax2.plot(r["t"], r["phi"], color=C["aqua"], lw=0.9); ax2.set_ylabel("bank (deg)", color=C["aqua"]); ax2.grid(False); ax2.spines["right"].set_visible(True)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.text(0.5, 0.0, "(a)–(e): scenario S5 (8.5 m/s differential gust doublet at 15 s, 4 m/s leader braking with 250 ms dropout, RTK noise/bias). Shaded: braking/dropout window. (f): 370 m split manoeuvre. Control-surface deflection is not modelled; bank command stands in.", ha="center", fontsize=6.3, color=C["ink2"], wrap=True)
    save(fig, "fig07_control_performance")


# --------------------------------------------------------------------------------------------- Fig 9, 10, 15
def fig09():
    g = MT[MT.model == HEAD].groupby("strategy")[[c for c in MT.columns if c.startswith("ph_")]].mean()
    g = g.loc[ORDER + ["D1_independent_14"]]
    grp = [("climb + landing", ["ph_climb", "ph_landing"], C["muted"]), ("transit", ["ph_transit"], C["blue"]), ("mapping strips", ["ph_mapping"], C["aqua"]),
           ("turns (Dubins)", ["ph_turns"], C["orange"]), ("ferry + wait", ["ph_ferry", "ph_wait"], C["yellow"]), ("reconfiguration", ["ph_reconfig"], C["violet"])]
    fig, ax = plt.subplots(figsize=(7.0, 3.1)); y = np.arange(len(g)); left = np.zeros(len(g))
    for lab, cols, c in grp:
        v = g[cols].sum(1).values; ax.barh(y, v, left=left, color=c, edgecolor="white", linewidth=1.2, label=lab, height=0.62); left += v
    for i, tot in enumerate(left): ax.text(tot + 2, i, f"{tot:.1f} Wh", va="center", fontsize=7)
    ax.set_yticks(y); ax.set_yticklabels([STRAT[s][0] for s in g.index]); ax.invert_yaxis(); ax.set_xlabel("fleet energy, load side (Wh), mean of 200 paired trials"); ax.legend(ncol=3, loc="lower right", fontsize=6.5); ax.set_xlim(0, 255); ax.grid(axis="y", visible=False)
    fig.tight_layout(); save(fig, "fig09_energy_breakdown")


def fig10():
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.3), gridspec_kw=dict(width_ratios=[1.7, 1]))
    ax = axs[0]; d = MT[MT.model == HEAD].pivot(index="trial", columns="strategy", values="e_area_Wh_ha")
    ords = ["S1_independent", "D1_independent_14", "S3_adaptive_geometric", "S4_wake_aware"]
    rng = np.random.default_rng(1)
    for i, s in enumerate(ords):
        ax.scatter(i + rng.uniform(-0.18, 0.18, len(d)), d[s], s=5, color=STRAT[s][1], alpha=0.45, lw=0)
        ax.plot([i - 0.28, i + 0.28], [d[s].mean()] * 2, color=C["ink"], lw=1.6)
    for t in range(0, 200, 10): ax.plot(range(4), d.loc[t, ords].values, color=C["muted"], lw=0.35, alpha=0.6)
    ax.set_xticks(range(4)); ax.set_xticklabels(["S1\nindependent", "D1 indep.\n14-strip route", "S3\nadaptive geom.", "S4\nwake-aware"]); ax.set_ylabel("energy per accepted ha (Wh/ha)"); panel(ax, "a")
    ax.text(0.01, 0.02, "points: 200 paired trials; grey lines: every 10th trial; bars: mean", transform=ax.transAxes, fontsize=6.3, color=C["ink2"])
    ax = axs[1]; panel(ax, "b")
    pt = PT[(PT.metric == "e_area_Wh_ha") & PT.comparison.str.startswith(("A:", "B:", "E:", "F:"))]
    labs = {"A:": "S4 vs S1 (all)", "B:": "S3 vs S1 (formation)", "E:": "S4 vs D1 (formation)", "F:": "D1 vs S1 (route)"}
    mk = {"published": "x", "strip_corrected": "s", "vlm_free": "D", "vlm_rolled": "^", "vlm_sheet": "o"}; y0 = {k: i for i, k in enumerate(labs)}
    for m, mm in mk.items():
        for k, l in labs.items():
            r = pt[(pt.model == m) & pt.comparison.str.startswith(k)].iloc[0]
            ax.errorbar(r.rel_change_pct, y0[k] + (list(mk).index(m) - 2.0) * 0.11, xerr=[[r.rel_change_pct - r.rel_p05_pct], [r.rel_p95_pct - r.rel_change_pct]], fmt=mm, color=MODEL[m][1], ms=4, lw=1)
    ax.axvline(0, color=C["ink"], lw=0.8); ax.set_yticks(list(y0.values())); ax.set_yticklabels(list(labs.values())); ax.invert_yaxis(); ax.set_xlabel("change in $E_{area}$ vs reference (%); <0 = saving\n(markers: mean; bars: 5–95 % of trials)"); ax.grid(axis="y", visible=False)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker=mk[m], color=MODEL[m][1], ls="", label=MODEL[m][0].replace("VLM follower, ", "VLM ").replace("Manuscript equations (as published)", "As published").replace("Strip theory, corrected", "Strip, corrected").replace("VLM follower, free wake", "VLM free wake")) for m in mk], fontsize=5.6, loc="lower right")
    fig.tight_layout(); save(fig, "fig10_energy_efficiency")


def fig15():
    d = pd.read_csv(f"{P}/decomposition.csv")
    fig, ax = plt.subplots(figsize=(6.4, 2.9)); comps = ["route/overlap only", "formation transit only", "interaction", "total (S4 vs S1)"]
    cl = [C["aqua"], C["orange"], C["muted"], C["violet"]]; mods = ["published", "strip_corrected", "vlm_free", "vlm_sheet"]
    w = 0.2
    for j, m in enumerate(mods):
        for i, c in enumerate(comps):
            r = d[(d.model == m) & (d.component == c)].iloc[0]
            ax.bar(i + (j - 1.5) * w, r.saving_pct, width=w * 0.9, color=cl[i], alpha=min(1.0, 0.35 + 0.2 * j), edgecolor="white")
    ax.axhline(0, color=C["ink"], lw=0.8); ax.set_xticks(range(4)); ax.set_xticklabels(["route / overlap\nonly (D1 vs S1)", "formation transit\nonly (S3 vs S1)", "interaction", "total\n(S4 vs S1)"])
    ax.set_ylabel("energy saving vs S1 (%, + = saving)"); ax.text(0.99, 0.97, "bars within a group: preliminary → strip-corrected → VLM free wake → VLM sheet (+ = saving)", transform=ax.transAxes, ha="right", va="top", fontsize=6.1, color=C["ink2"])
    fig.tight_layout(); save(fig, "fig15_decomposition")


# --------------------------------------------------------------------------------------------- Fig 11, 12
def fig11():
    ua = pd.read_csv(f"{P}/aero_uncertainty_airspeed.csv"); ud = pd.read_csv(f"{P}/aero_uncertainty_dy.csv"); sw = pd.read_csv(f"{P}/aero_sweep_dy.csv"); src = pd.read_csv(f"{P}/sensitivity_src.csv")
    av = pd.read_csv(f"{P}/aero_airspeed.csv")
    fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.9), gridspec_kw=dict(width_ratios=[1, 1, 0.9]))
    ax = axs[0]; panel(ax, "a")
    u = ua[ua.dy_b == 0.85]; ax.fill_between(u.va, u.p05, u.p95, color=C["orange"], alpha=0.25, lw=0, label="strip, corrected: 5–95 % band"); ax.plot(u.va, u["mean"], color=C["orange"])
    for m in ("vlm_sheet", "vlm_free", "published"):
        a = av[av.model == m]; ax.plot(a.va, a.pct_power, "o-", ms=3, color=MODEL[m][1], label=MODEL[m][0].replace("VLM follower, planar sheet", "VLM planar sheet"), ls="-" if m != "published" else "--")
    ax.set_xlabel("airspeed $V_a$ (m/s)"); ax.set_ylabel("follower power saving (%)"); ax.legend(fontsize=5.8)
    ax = axs[1]; panel(ax, "b")
    ax.fill_between(ud.dy_b, ud.p05, ud.p95, color=C["orange"], alpha=0.25, lw=0); ax.plot(ud.dy_b, ud["mean"], color=C["orange"], label="strip, corrected")
    s = sw[(sw.model == "vlm_sheet") & (sw.dy_b <= 1.6)]; ax.plot(s.dy_b, s.pct_power, color=C["blue"], label="VLM planar sheet")
    s = sw[(sw.model == "published") & (sw.dy_b <= 1.6)]; ax.plot(s.dy_b, s.pct_power, "--", color=C["red"], label="as published"); ax.set_ylim(-10, 12)
    ax.set_xlabel("$d_y/b$ ($V_a=18$ m/s)"); ax.legend(fontsize=6)
    ax = axs[2]; panel(ax, "c")
    src = src.sort_values("abs_src"); lab = [l.replace("wind speed (dummy)", "wind (null control)") for l in src.factor]
    ax.barh(lab, src.src, color=[C["blue"] if v > 0 else C["orange"] for v in src.src]); ax.set_xlabel(f"standardised regression coeff.\n($R^2$={src.r2.iloc[0]:.2f})"); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", labelsize=6.5)
    fig.tight_layout(); save(fig, "fig11_sensitivity")


def fig12():
    z = np.load(f"{P}/breakeven_surface.npz"); df = pd.read_csv(f"{P}/breakeven_distance.csv")
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.2))
    ax = axs[0]; panel(ax, "a")
    N = z["vlm_sheet"]; D = z["D"] / 1000; T = z["T"]
    lim = max(abs(N.min()), abs(N.max())); from matplotlib.colors import TwoSlopeNorm
    cf = ax.contourf(D, T, N, levels=np.linspace(-lim, lim, 25), cmap=plt.matplotlib.colors.LinearSegmentedColormap.from_list("d", [C["orange"], "#f0efec", C["blue"]]), norm=TwoSlopeNorm(0, -lim, lim))
    ax.contour(D, T, N, levels=[0], colors=C["ink"], linewidths=1.4)
    ax.axhline(62.7, color=C["red"], ls="--", lw=0.8); ax.text(19.8, 66, "fastest simulated split (12 m/s lateral)", color=C["red"], fontsize=6, ha="right")
    ax.set_xlabel("one-way transit distance (km)"); ax.set_ylabel("split/merge window $T$ (s)"); cb = fig.colorbar(cf, ax=ax); cb.set_label("net fleet saving (Wh); black = break-even"); ax.grid(False)
    ax = axs[1]; panel(ax, "b")
    for m, mk in (("vlm_sheet", "o"), ("vlm_free", "D"), ("strip_corrected", "s"), ("published", "x")):
        g = df[df.model == m].groupby("D").aero17.agg(["mean", lambda v: np.percentile(v, 5), lambda v: np.percentile(v, 95)])
        ax.plot(g.index / 1000, g["mean"], marker=mk, ms=3.5, color=MODEL[m][1], label=MODEL[m][0].replace("VLM follower, planar sheet", "VLM planar sheet"))
        if m == "vlm_sheet": ax.fill_between(g.index / 1000, g.iloc[:, 1], g.iloc[:, 2], color=C["blue"], alpha=0.2, lw=0)
    ax.axhline(0, color=C["ink"], lw=0.8); ax.set_xscale("log"); ax.set_xticks([1, 2, 5, 10, 20]); ax.set_xticklabels(["1", "2", "5", "10", "20"])
    ax.set_xlabel("one-way transit distance (km)"); ax.set_ylabel("fleet saving, S3 vs S1 (Wh)"); ax.legend(fontsize=6)
    fig.tight_layout(); save(fig, "fig12_breakeven")


# --------------------------------------------------------------------------------------------- Fig 13 mapping
def fig13():
    fig = plt.figure(figsize=(7.6, 3.5)); gs = fig.add_gridspec(1, 6, width_ratios=[1, 1, 1, 0.06, 0.52, 1.35], wspace=0.26)
    cases = [("17 strips, 65 %", 17, 61.6), ("14 strips, 58 % (spec.)", 14, 73.92), ("14 strips, 57.95 %", 14, 74.0)]
    for k, (lab, n, s) in enumerate(cases):
        ax = fig.add_subplot(gs[k]); m = photo.multiplicity_map(photo.strip_centres(n, s), None)
        im = ax.imshow(m, origin="lower", extent=[0, 1000, 0, 1000], cmap=plt.matplotlib.colors.ListedColormap(["#c3c2b7", "#b7d3f6", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"]) if False else "Blues", vmin=0, vmax=12)
        acc, cov, d = photo.accepted_area(m)
        for i in range(10):
            for j in range(10):
                if not d["ok"][i, j]: ax.add_patch(Rectangle((j * 100, i * 100), 100, 100, fc="none", ec=C["red"], lw=1.1, hatch="///"))
        ax.set_title(f"{lab}\naccepted {acc:.0f} ha", fontsize=7); ax.set_xticks([0, 500, 1000]); ax.set_yticks([0, 500, 1000] if k == 0 else []); ax.grid(False)
        if k == 0: ax.set_ylabel("$y$ (m)")
        ax.set_xlabel("$x$ (m)")
    fig.colorbar(im, cax=fig.add_subplot(gs[3])).set_label("images per cell")
    ax = fig.add_subplot(gs[4]); panel(ax, "d")
    crabs = np.arange(0, 21, 1.0)
    for (lab, n, s), lc in zip(cases[:3], (C["blue"], C["orange"], C["violet"])):
        acc = []
        for cd in crabs:
            c = math.radians(cd); mm = photo.multiplicity_map(photo.strip_centres(n, s), None, crab=[c if i % 2 == 0 else -c for i in range(n)]); acc.append(photo.accepted_area(mm)[0])
        ax.plot(crabs, acc, marker="o", ms=2.5, label=lab, color=lc)
    ax.set_xlabel("crab angle (deg)"); ax.set_ylabel("accepted area (ha)"); ax.set_ylim(70, 105); ax.legend(fontsize=5.8, loc="lower right")
    fig.text(0.5, -0.02, "Red hatch: 1-ha tiles failing the ≥5-ray over 95 % rule at the block edge. Geometry only: criteria (3)–(4) (RMSE$_H$, RMSE$_V$) were not evaluated (no SfM run).", ha="center", fontsize=6.5, color=C["ink2"])
    save(fig, "fig13_mapping_geometry")


# --------------------------------------------------------------------------------------------- Fig 14
def fig14():
    d = pd.read_csv("data/raw/control_trials.csv"); order = ["S1_turbulence", "S2_gust_doublet", "S3_braking_dropout", "S4_degraded_gnss", "S5_combined", "S6_overcapability"]
    short = ["S1\nturb.", "S2\ngust", "S3\nbrake", "S4\nGNSS", "S5\ncomb.", "S6\nover-cap."]
    cols = {"P": C["orange"], "NMPC": C["blue"], "NMPC+CBF": C["violet"]}
    fig, axs = plt.subplots(2, 2, figsize=(7.4, 4.9)); axs = axs.ravel()
    def strip(ax, col, ylabel, log=False):
        for j, c in enumerate(cols):
            for i, s in enumerate(order):
                v = d[(d.scenario == s) & (d.controller == c)][col].values
                x = i + (j - 1) * 0.26
                ax.scatter(x + np.random.default_rng(i).uniform(-0.07, 0.07, len(v)), v, s=4, color=cols[c], alpha=0.5, lw=0)
                ax.plot([x - 0.1, x + 0.1], [np.median(v)] * 2, color=C["ink"], lw=1.2)
        ax.set_xticks(range(6)); ax.set_xticklabels(short, fontsize=6.5); ax.set_ylabel(ylabel)
        if log: ax.set_yscale("log")
    strip(axs[0], "min_sep", "minimum true separation (m)"); axs[0].axhline(4.24, color=C["red"], ls="--", lw=0.9); panel(axs[0], "a")
    strip(axs[1], "rms_ey", "RMS lateral tracking error (m)", log=True); panel(axs[1], "b")
    ax = axs[2]; panel(ax, "c")
    for j, c in enumerate(cols):
        v = [d[(d.scenario == s) & (d.controller == c)].violated.mean() * 100 for s in order]
        ax.bar(np.arange(6) + (j - 1) * 0.27, v, width=0.25, color=cols[c], label=c, edgecolor="white")
    ax.set_xticks(range(6)); ax.set_xticklabels(short, fontsize=6.5); ax.set_ylabel("trials with $h<0$ (%)"); ax.legend(fontsize=6.5, loc="upper left")
    ax = axs[3]; panel(ax, "d"); g = d[d.controller == "NMPC+CBF"]
    ax.bar(np.arange(6) - 0.15, [g[g.scenario == s].cbf_active_frac.mean() * 100 for s in order], width=0.3, color=C["violet"], label="filter active (% of time)", edgecolor="white")
    ax.bar(np.arange(6) + 0.15, [g[g.scenario == s].sat_frac.mean() * 100 for s in order], width=0.3, color=C["yellow"], label="input saturated (% of time)", edgecolor="white")
    ax.set_xticks(range(6)); ax.set_xticklabels(short, fontsize=6.5); ax.legend(fontsize=6.3); ax.set_ylabel("%")
    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([], [], marker="o", ls="", color=cols[c], label=c) for c in cols], ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.03), fontsize=7)
    fig.tight_layout(); save(fig, "fig14_safety_tracking")


if __name__ == "__main__":
    for f in sys.argv[1:] or ["fig05", "fig06", "fig07", "fig09", "fig10", "fig15", "fig11", "fig12", "fig13", "fig14"]:
        try:
            globals()[f](); print("ok", f)
        except Exception as e:
            import traceback; traceback.print_exc(); print("FAIL", f, e)
