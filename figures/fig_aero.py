import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from style import *
from flockmap import aero, vlm
from flockmap.config import AC

setup()
B = AC.b
DIV = LinearSegmentedColormap.from_list("div", [C["orange"], "#f0efec", C["blue"]])   # orange = downwash, blue = upwash
P = "data/processed"


def sheet_field_plane(dx, ys, zs, va=18.0):
    """w (up +) on a y-z plane at distance dx behind the leader (planar vortex-sheet VLM)."""
    W = vlm._wing(AC, 60); s = W.isolated(va, AC.mass * 9.80665)
    Y, Z = np.meshgrid(ys, zs); Q = np.stack([np.full(Y.size, W.xb + dx), Y.ravel(), Z.ravel()], 1)
    v = np.zeros_like(Q)
    for j in range(W.n):
        v += s["gamma"][j] * vlm._horseshoe(Q, W.edges[j], W.edges[j + 1], W.xb, 0.02)
    return v[:, 2].reshape(Y.shape)


def lo_plane(dx, ys, zs, va=18.0):
    iso = aero.isolated(va); rc = aero.core_radius(dx, va)
    Y, Z = np.meshgrid(ys, zs)
    w, _ = aero.lamb_oseen_pair(Y, Z, aero.gamma0_elliptic(va, iso["cl"]), AC.b0, rc)
    return w


def wing_poly(x0, y0, z0=0.0):
    """Simplified swept flying-wing planform (NOT the exact Skywalker X8 outline), span 2.12 m, ~0.8 m^2."""
    hb = B / 2
    pts = np.array([[0.30, 0], [0.0, -0.12], [-0.38, -hb], [-0.58, -hb], [-0.50, -0.18], [-0.50, 0.18], [-0.58, hb], [-0.38, hb], [0.0, 0.12]])
    return np.column_stack([pts[:, 0] + x0, pts[:, 1] + y0, np.full(len(pts), z0)])


# ------------------------------------------------------------------------------------------- Fig 1: 3-D wake
def fig01():
    fig = plt.figure(figsize=(7.2, 4.6)); ax = fig.add_subplot(111, projection="3d")
    dx, dy = 3 * B, 0.85 * B
    for (x0, y0, c) in ((0, 0, C["violet"]), (-dx, -dy, C["aqua"]), (-dx, dy, C["aqua"])):
        ax.add_collection3d(Poly3DCollection([wing_poly(x0, y0)], facecolor=c, edgecolor=C["ink"], linewidth=0.7, alpha=1.0, zorder=10))
    ax.text(0.2, 0, 0.55, "Leader", fontsize=7.5, ha="center", zorder=20)
    ax.text(-dx, -dy - 0.9, 0.55, "Follower 1", fontsize=7.5, ha="center", zorder=20); ax.text(-dx, dy + 0.9, 0.55, "Follower 2", fontsize=7.5, ha="center", zorder=20)
    iso = aero.isolated(18.0)
    xs = np.linspace(0, -11, 60)
    for sgn in (-1, 1):
        rc = np.array([aero.core_radius(abs(x), 18.0) for x in xs])
        ax.plot(xs, sgn * AC.b0 / 2 * np.ones_like(xs), np.zeros_like(xs), color=C["red"], lw=1.8, zorder=8)
        th = np.linspace(0, 2 * np.pi, 24)
        for k in (10, 30, 50):
            ax.plot(np.full(24, xs[k]), sgn * AC.b0 / 2 + rc[k] * 5 * np.cos(th), rc[k] * 5 * np.sin(th), color=C["red"], lw=0.7, alpha=0.7)
    ys = np.linspace(-3.8, 3.8, 90); zs = np.linspace(-1.6, 1.6, 50)
    w = lo_plane(dx, ys, zs); Yg, Zg = np.meshgrid(ys, zs)
    norm = TwoSlopeNorm(0, -0.8, 0.8)
    ax.plot_surface(np.full_like(Yg, -dx), Yg, Zg, facecolors=DIV(norm(w)), shade=False, alpha=0.92, rstride=1, cstride=1, linewidth=0, zorder=1)
    ax.quiver(1.6, 0, -1.4, 2.0, 0, 0, color=C["ink"], arrow_length_ratio=0.3, lw=1.2); ax.text(3.4, 0, -1.2, "flight", fontsize=7)
    ax.set_xlim(3.5, -11); ax.set_ylim(-4, 4); ax.set_zlim(-1.8, 1.8); ax.set_box_aspect((2.4, 1.3, 0.75))
    ax.set_xlabel("$x$ downstream (m)", labelpad=2); ax.set_ylabel("$y$ (m)", labelpad=2); ax.set_zlabel("$z$ (m)", labelpad=0)
    ax.view_init(22, -62); ax.grid(False)
    for a_ in (ax.xaxis, ax.yaxis, ax.zaxis): a_.pane.set_alpha(0.0)
    sm = plt.cm.ScalarMappable(norm=norm, cmap=DIV)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", shrink=0.5, pad=0.02, aspect=30); cb.set_label("vertical induced velocity $w$ in the followers' plane, $d_x=3b$ (m/s); upwash $+$")
    save(fig, "fig01_wake_3d")


# ------------------------------------------------------------------------------------------- Fig 2: contours
def fig02():
    ys = np.linspace(-3.6, 3.6, 181); zs = np.linspace(-1.8, 1.8, 91)
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
    for ax, (lab, w) in zip(axs, (("Lamb–Oseen pair (corrected $\\Gamma_0$)", lo_plane(3 * B, ys, zs)), ("Vortex-lattice planar sheet", sheet_field_plane(3 * B, ys, zs)))):
        norm = TwoSlopeNorm(0, -0.6, 0.6)
        cf = ax.contourf(ys, zs, np.clip(w, -0.6, 0.6), levels=np.linspace(-0.6, 0.6, 25), cmap=DIV, norm=norm)
        ax.contour(ys, zs, w, levels=[0], colors=C["ink"], linewidths=0.8)
        for s in (-1, 1):
            ax.plot(s * AC.b0 / 2, 0, "o", ms=4, mfc="none", mec=C["ink"])
            ax.add_patch(plt.Rectangle((s * 0.85 * B - B / 2, -0.04), B, 0.08, color=C["aqua"], ec=C["ink"], lw=0.6, zorder=5))
        ax.set_title(lab); ax.set_xlabel("$y$ (m)"); ax.set_aspect("equal"); ax.grid(False)
    axs[0].set_ylabel("$z$ (m)")
    cb = fig.colorbar(cf, ax=axs, shrink=0.8, pad=0.02); cb.set_label("$w$ (m/s), upwash $+$")
    fig.text(0.5, -0.04, "Open circles: vortex centres ($b_0=\\pi b/4$). Green bars: follower wings at $d_y/b=0.85$. $d_x=3b$, $V_a=18$ m/s.", ha="center", fontsize=7, color=C["ink2"])
    save(fig, "fig02_wake_contours")


# ------------------------------------------------------------------------------------------- Fig 3: loading
def fig03():
    fig, axs = plt.subplots(2, 2, figsize=(7.2, 4.9))
    cols = {0.70: C["orange"], 0.85: C["blue"], 1.00: C["aqua"], 1.30: C["violet"]}
    ax = axs[0, 0]; panel(ax, "a")
    for dy, c in cols.items():
        r = vlm.follower(3.0, dy, wake="rolled")
        ax.plot(r["_ym"] / B, r["_w_cp"], color=c, label=f"$d_y/b={dy:.2f}$")
    ax.axhline(0, color=C["axis"], lw=0.8); ax.set_xlabel("follower span station $\\eta=y/b$"); ax.set_ylabel("upwash $w$ at follower (m/s)"); ax.legend(loc="upper right", ncol=2)
    ax = axs[0, 1]; panel(ax, "b")
    for dy, c in cols.items():
        r = vlm.follower(3.0, dy, wake="rolled")
        ax.plot(r["_ym"] / B, (r["_gam"] - r["_gam_iso"]) / r["_gam_iso"].max() * 100, color=c)
    ax.axhline(0, color=C["axis"], lw=0.8); ax.set_xlabel("$\\eta=y/b$"); ax.set_ylabel("circulation change $\\Delta\\Gamma/\\Gamma_{max,iso}$ (%)")
    d = pd.read_csv(f"{P}/aero_sweep_dy.csv"); d = d[d.dy_b <= 1.6]
    ax = axs[1, 0]; panel(ax, "c")
    for m in ("published", "strip_corrected", "vlm_sheet", "vlm_free"):
        s = d[d.model == m]; ax.plot(s.dy_b, s.cl_roll, color=MODEL[m][1], label=MODEL[m][0])
    ax.axhline(0, color=C["axis"], lw=0.8); ax.set_xlabel("$d_y/b$"); ax.set_ylabel("wake rolling-moment coeff. $C_{l,wake}$"); ax.legend()
    ax = axs[1, 1]; panel(ax, "d")
    for m in ("published", "strip_corrected", "vlm_sheet", "vlm_free"):
        s = d[d.model == m]; ax.plot(s.dy_b, s.elevon_deg, color=MODEL[m][1])
    ax.axhspan(-25, 25, color=C["grid"], alpha=0.5, lw=0); ax.text(1.55, 23, "±25° (assumed travel)", fontsize=6.5, ha="right", va="top", color=C["ink2"])
    ax.set_ylim(-60, 60); ax.set_xlabel("$d_y/b$"); ax.set_ylabel("required elevon trim (deg)")
    fig.tight_layout(); save(fig, "fig03_spanwise_loading")


# ------------------------------------------------------------------------------------------- Fig 4: map
def fig04():
    z = np.load(f"{P}/aero_map_dxdy.npz"); dx, dy, dP, cl = z["dx"], z["dy"], z["dP"], z["cl"]
    ctrl = pd.read_csv("data/raw/control_trials.csv"); s1 = ctrl[(ctrl.scenario == "S1_turbulence") & (ctrl.controller == "NMPC+CBF")]
    sx, sy = s1.rms_ex.mean() / B, s1.rms_ey.mean() / B
    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    norm = TwoSlopeNorm(0, dP.min(), max(dP.max(), 0.5) if dP.max() > 0 else 0.5)
    cf = ax.contourf(dy, dx, dP, levels=21, cmap=DIV.reversed(), norm=TwoSlopeNorm(0, dP.min(), max(dP.max(), 1e-3)))
    if dP.max() > 0:
        cs = ax.contour(dy, dx, dP, levels=[0], colors=C["ink"], linewidths=1.4); ax.clabel(cs, fmt={0: "net benefit = 0"}, fontsize=6.5)
    c2 = ax.contour(dy, dx, np.abs(cl), levels=[0.005, 0.01], colors=C["violet"], linestyles=["--", ":"], linewidths=1.0)
    ax.clabel(c2, fmt=lambda v: f"{v:g}", fontsize=6)
    DY, DX = np.meshgrid(dy, dx); ax.contourf(dy, dx, np.hypot(DX, DY), levels=[0, 2.0], colors="none", hatches=["////"])
    ax.contour(dy, dx, np.hypot(DX, DY), levels=[2.0], colors=C["red"], linewidths=1.2)
    ax.text(0.52, 1.65, "inside $D_{safe}=2b$", color=C["red"], fontsize=6.5)
    ax.plot(0.80, 3.0, "k^", ms=6, label="manuscript optimum"); ax.plot(0.85, 3.0, "ko", ms=5, mfc="w", label="nominal slot (this study)")
    from matplotlib.patches import Ellipse
    ax.add_patch(Ellipse((0.85, 3.0), 2 * sy, 2 * sx, fill=False, ec=C["ink"], lw=0.8, ls="-"))
    ax.set_xlabel("lateral offset $d_y/b$"); ax.set_ylabel("longitudinal offset $d_x/b$"); ax.legend(loc="upper right", fontsize=6.5)
    cb = fig.colorbar(cf, ax=ax); cb.set_label("follower electrical power change $\\Delta P$ (W)  [negative = saving]")
    ax.set_title("Dashed/dotted violet: $|C_{l,wake}|=0.005, 0.01$; ellipse: 1-$\\sigma$ station-keeping error", fontsize=7); ax.grid(False)
    save(fig, "fig04_sensitivity_map")


# ------------------------------------------------------------------------------------------- Audit figures
def figA1():
    t = pd.read_csv(f"{P}/audit_table33.csv"); d = pd.read_csv(f"{P}/aero_sweep_dy.csv")
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.6))
    ax = axs[0]; panel(ax, "a")
    ax.plot(t.dy_b, t.w_table, "o-", color=C["ink2"], label="printed table"); ax.plot(t.dy_b, t.w_recomputed, "s--", color=C["red"], label="recomputed, same equations")
    ax.set_xlabel("$d_y/b$"); ax.set_ylabel("mean upwash $\\bar w$ (m/s)"); ax.legend()
    ax = axs[1]; panel(ax, "b")
    ax.plot(t.dy_b, t.cl_table, "o-", color=C["ink2"]); ax.plot(t.dy_b, t.cl_recomputed, "s--", color=C["red"]); ax.set_xlabel("$d_y/b$"); ax.set_ylabel("$C_{l,wake}$")
    ax = axs[2]; panel(ax, "c")
    ax.plot(t.dy_b, t.pct_table, "o-", color=C["ink2"]); ax.plot(t.dy_b, t.pct_recomputed, "s--", color=C["red"]); ax.set_ylim(-30, 10)
    ax.set_xlabel("$d_y/b$"); ax.set_ylabel("follower power saving (%)")
    fig.tight_layout(); save(fig, "figA1_table_audit")


def figA2():
    d = pd.read_csv(f"{P}/aero_sweep_dy.csv"); d = d[(d.dy_b >= 0.5) & (d.dy_b <= 1.6)]
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.8))
    for m in MODEL:
        s = d[d.model == m]
        axs[0].plot(s.dy_b, s.pct_power, color=MODEL[m][1], label=MODEL[m][0], lw=1.6 if m != "published" else 1.2, ls="-" if m != "published" else "--")
    axs[0].axhline(0, color=C["axis"], lw=0.8); axs[0].set_ylim(-30, 14); axs[0].set_xlabel("$d_y/b$ ($d_x=3b$, $V_a=18$ m/s)"); axs[0].set_ylabel("follower electrical-power saving (%)"); axs[0].legend(fontsize=6); panel(axs[0], "a")
    s = d[d.model.isin(["strip_corrected", "vlm_rolled", "vlm_sheet", "vlm_free"])]
    pk = s.groupby("model").apply(lambda g: g.loc[g.pct_power.idxmax()], include_groups=False)
    axs[1].barh([MODEL[m][0] for m in pk.index], pk.pct_power, color=[MODEL[m][1] for m in pk.index]); axs[1].set_xlabel("peak saving (%)"); axs[1].set_xlim(0, 8)
    for i, (m, r) in enumerate(pk.iterrows()): axs[1].text(r.pct_power + 0.1, i, f"{r.pct_power:.1f} % at $d_y/b$={r.dy_b:.2f}", va="center", fontsize=7)
    axs[1].grid(False); panel(axs[1], "b")
    fig.tight_layout(); save(fig, "figA2_model_comparison")


def figA3():
    v = pd.read_csv(f"{P}/vlm_verification.csv")
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.5))
    axs[0].plot(v.n, v.e_oswald, "o-", color=C["blue"]); axs[0].axhline(1.0, color=C["ink2"], ls="--", lw=0.8); axs[0].set_xlabel("spanwise panels"); axs[0].set_ylabel("Oswald factor (planar wing)"); panel(axs[0], "a")
    axs[1].plot(v.n, v.cl_alpha, "o-", color=C["blue"], label="VLM"); axs[1].axhline(v.helmbold_cl_alpha[0], color=C["orange"], ls="--", label="Helmbold"); axs[1].axhline(v.prandtl_ll_cl_alpha[0], color=C["aqua"], ls=":", label="lifting-line")
    axs[1].set_xlabel("spanwise panels"); axs[1].set_ylabel("$C_{L\\alpha}$ (1/rad)"); axs[1].legend(); panel(axs[1], "b")
    fig.tight_layout(); save(fig, "figA3_vlm_verification")


if __name__ == "__main__":
    for f in (fig01, fig02, fig03, fig04, figA1, figA2, figA3):
        f(); print("ok", f.__name__)
