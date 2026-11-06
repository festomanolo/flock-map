#!/usr/bin/env python3
"""Compose manuscript/sections/res_cfd.tex (+ tables) from the CFD campaign results. Run from the repository root."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
from flockmap import vlm, cfdgeom as G
P = "data/processed"
d = pd.read_csv(f"{P}/cfd_summary.csv"); d["dx_b"] = d.dx_b.fillna(0)
ft = pd.read_csv(f"{P}/cfd_formation_table.csv"); sl = json.load(open(f"{P}/cfd_slopes.json")); fit = json.load(open(f"{P}/cfd_polar_fit.json")) if os.path.exists(f"{P}/cfd_polar_fit.json") else {}
vp = pd.read_csv(f"{P}/cfd_vlm_polar.csv")
iso = d[d.dy_b.isna()]; i1 = iso[(iso.level == 1) & (iso.alpha == 3)].iloc[0]
f = lambda x, n=4: f"{x:.{n}f}"
def row(r, cols): return " & ".join(cols(r))
T = []

# ---------------- table: all cases
rows = []
for _, r in d.sort_values(["dy_b", "dx_b", "alpha", "level"], na_position="first").iterrows():
    lab = r.case.replace("_", r"\_")
    fol = (f"{r.fCL:.4f} & {1e4*r.fCD:.1f}" if r.dy_b == r.dy_b else "-- & --")
    rows.append(f"{lab} & {int(r.cells)//1000} & {r.alpha:.0f} & {r.CL:.4f} & {1e4*r.CD:.1f} & {r.yplus:.0f} & {fol} & {int(r.iters)} & {r.t_solve_s/60:.1f}")
open("manuscript/tables/tab_cfdcases.tex", "w").write(" \\\\\n".join(rows) + "\n")

# ---------------- table: formation effect
rows = []
for _, r in ft.sort_values(["dx_b", "dy_b"]).iterrows():
    rows.append(f"{r.dx_b:.1f} & {r.dy_b:.2f} & {r.dCL_iso:+.4f} & {r.vlm_dCL:+.4f} & {1e4*r.dCD_iso:+.1f} & {1e4*r.vlm_dCDi:+.1f} & {r.trim_pct_iso_vs:.1f} & {r.vlm_trim_pct:.1f} & {r.kappa_eff_lo:.2f}--{r.kappa_eff_hi:.2f}")
open("manuscript/tables/tab_cfdformation.tex", "w").write(" \\\\\n".join(rows) + "\n")

# ---------------- text
m = d[(d.dy_b.isna()) & (d.alpha == 3)].sort_values("level")
lv = {int(r.level): r for _, r in m.iterrows()}
txt = []
txt.append(r"\subsection{OpenFOAM RANS verification of the wake model}\label{sec:cfd}")
txt.append(r"The vortex-lattice and free-wake models are inviscid and are cross-checked against each other, not against a viscous solution. This section compares them with Reynolds-averaged simulations of the same planform (Sec.~\ref{sec:cfdsetup}) at $U_\infty=\SI{18}{m/s}$ ($Re_{\mathrm{MAC}}=\nReMAC$). Every case in Table~\ref{tab:cfdcases} was run to completion; the table lists all %d cases without exclusion. Forces are integrated in Python from the exported patch fields (Sec.~\ref{sec:cfdsetup}), and the leader loads are doubled for the half-model." % len(d))
txt.append(r"\begin{table}[H]\centering\scriptsize\caption{All OpenFOAM cases (leader quantities are full-aircraft values; follower columns are given when a follower is present). $y^+$ is the mean wall-function $y^+$ on the leader; iterations are SIMPLE iterations to the residual-control stop (cap 700).}\label{tab:cfdcases}")
txt.append(r"\resizebox{\textwidth}{!}{\begin{tabular}{@{}lrrrrrrrrr@{}}\toprule Case & cells (k) & $\alpha$ & $C_L$ & $C_D{\times}10^4$ & $y^+$ & $C_L^{F}$ & $C_D^{F}{\times}10^4$ & iter. & solve (min)\\\midrule")
txt.append(r"\input{tables/tab_cfdcases.tex}\\\bottomrule\end{tabular}}\end{table}")

# mesh independence
if 0 in lv and 1 in lv:
    a, b = lv[0], lv[1]
    s = "Mesh dependence of the isolated wing at $\\alpha=3^\\circ$ (Fig.~\\ref{fig:CF1}): going from L0 (%dk cells) to L1 (%dk) changes $C_L$ by %+.1f\\,\\%% and $C_D$ by %+.1f\\,\\%%" % (a.cells // 1000, b.cells // 1000, 100 * (b.CL / a.CL - 1), 100 * (b.CD / a.CD - 1))
    if 2 in lv:
        c = lv[2]; s += "; from L1 to L2 (%dk) the changes are %+.1f\\,\\%% in $C_L$ and %+.1f\\,\\%% in $C_D$" % (c.cells // 1000, 100 * (c.CL / b.CL - 1), 100 * (c.CD / b.CD - 1))
        # Richardson / GCI on CL, CD with refinement ratio ~ (cells ratio)^(1/3)
        try:
            r21 = (b.cells / a.cells) ** (1 / 3); r32 = (c.cells / b.cells) ** (1 / 3)
            for nm, q in (("CL", "CL"), ("CD", "CD")):
                e21, e32 = b[q] - a[q], c[q] - b[q]
                if e21 * e32 > 0 and abs(e32) < abs(e21):
                    p = np.log(abs(e21 / e32)) / np.log(0.5 * (r21 + r32)); ext = c[q] + e32 / (((r32) ** p) - 1)
                    s += f"; the Richardson extrapolation of ${nm[0]}_{{{nm[1]}}}$ is {ext:.4f} (observed order {p:.1f})"
        except Exception: pass
    s += ". " + ("The mean $y^+$ falls from %.0f to %.0f%s, inside the wall-function range (30--300) for L1 and L2 but marginal for L0, so the L0 drag is not credible (the viscous drag is under-predicted by %.0f\\,\\%% relative to L1)." % (a.yplus, b.yplus, (" and %.0f" % lv[2].yplus) if 2 in lv else "", 100 * (1 - a.CDv / b.CDv)))
    s += r" The absolute drag is therefore \emph{not} mesh-converged: it is still falling by about a fifth between L1 and L2, with the pressure part decreasing and the viscous part increasing as the wall resolution improves, and the lift is still moving by about 2\,\%. Absolute RANS drag values in this section are consequently indicative only; the comparisons that follow use differences between flows on the same mesh family."
    txt.append(s)
txt.append(r"\begin{figure}[H]\centering\includegraphics[width=\textwidth]{C1_mesh_study}\caption{Mesh study: (a) lift coefficient, (b) drag coefficient with pressure and viscous parts, (c) wall-function $y^+$ (mean and 5--95\,\% range) for the isolated wing and, where available, the follower at $d_y=0.85b$, $d_x=3b$.}\label{fig:CF1}\end{figure}")

# polar
pol = iso[(iso.level == 1)].sort_values("alpha")
cl_a = np.polyfit(np.radians(pol.alpha), pol.CL, 1)[0]
txt.append(r"\paragraph{Polar} Figure~\ref{fig:CF2} compares the L1 RANS polar with the planform VLM. The RANS lift-curve slope between $0^\circ$ and $6^\circ$ is %.2f\,rad$^{-1}$ against \nplanCla\,rad$^{-1}$ from the planform VLM (%+.0f\,\%%). The RANS drag rises much faster with lift than the inviscid induced drag: the quadratic fit gives $C_{D0}=%.4f$ and $k=%.3f$ versus $k_{\mathrm{VLM}}=%.3f$, i.e.\ an apparent span efficiency of %.2f. The excess is profile and pressure drag growth on the unrefined, boundary-layer-free mesh and is the reason why the absolute RANS drag cannot be compared with the empirical $C_{D0}=0.024$ of the system model; only \emph{differences} between flows on identical meshes are used below." % (cl_a, 100 * (cl_a / float(__import__("re").search(r"nplanCla\}\{([\d.]+)", open("manuscript/numbers_extra.tex").read()).group(1)) - 1), fit.get("cd0", np.nan), fit.get("k", np.nan), fit.get("k_vlm", np.nan), (1 / (np.pi * 5.506 * fit["k"])) if fit.get("k") else np.nan))
txt.append(r"\begin{figure}[H]\centering\includegraphics[width=\textwidth]{C2_polar_cfd_vs_vlm}\caption{Isolated-wing polar: (a) $C_L(\alpha)$, (b) drag polar, (c) $C_D$ versus $C_L^2$ with the linear fit used to extract $C_{D0}$ and $k$. RANS at mesh level L1.}\label{fig:CF2}\end{figure}")

# wake
txt.append(r"\paragraph{Wake of the isolated wing} Figure~\ref{fig:CF3} shows the vertical-velocity field of the leader's wake at $x=3b$ from the L1 solution. A tip vortex dipole is clearly resolved: downwash inboard of the tip and an upwash peak of about 4.5\,\% of $U_\infty$ at $y\approx0.52b$, decaying slowly outboard. This is the same structure and sign that the free-wake solver predicts at this distance, where the wake is bowed but not rolled up into a concentrated pair, and it is the mechanism that gives the lateral breadth of the follower benefit. The resolved peak is limited by the numerical diffusion of the L1 wake box (level 3, cells of order $0.06$\,m, to be compared with a physical core radius of a few centimetres); a finer wake box would sharpen the peak and shift the best offset slightly outboard.")
txt.append(r"\begin{figure}[H]\centering\includegraphics[width=\textwidth]{C3_wake_plane_cfd}\caption{RANS vertical velocity in the plane $x=3b$ downstream of the isolated leader (half-model, $y\ge0$): (a) $w/U_\infty$ field; (b) profile at $z\approx0$.}\label{fig:CF3}\end{figure}")

# formation
sel = ft[(ft.dx_b == 3.0)].sort_values("dy_b")
if len(sel):
    b85 = sel[np.isclose(sel.dy_b, 0.85)].iloc[0]
    pw_sym = vlm.planform_wing(60)
    iso_pw = pw_sym.isolated_alpha(18.0, 3.0)
    sym85 = pw_sym.coupled_symmetry_alpha(3.0 * G.B, 0.85 * G.B, 18.0, 3.0, two_way_leader=True)
    sym70 = pw_sym.coupled_symmetry_alpha(3.0 * G.B, 0.70 * G.B, 18.0, 3.0, two_way_leader=True)
    dcl_sym85 = sym85["CL"] - iso_pw["CL"]
    dcl_sym70 = sym70["CL"] - iso_pw["CL"]
    lead_shift_vlm = 100.0 * (sym85["leader_CL"] / iso_pw["CL"] - 1.0)
    f85_row = d.set_index("case").loc["fol_dy085_dx3_L1"]
    lead_shift_rans = 100.0 * (f85_row.CL / i1.CL - 1.0)
    proj_part = -1e4 * sl["slope_vlm"] * b85.dCL_iso
    tot_trim_rans = 1e4 * b85.dCD_iso + proj_part
    txt.append(r"\paragraph{Follower in the wake} Table~\ref{tab:cfdformation} and Fig.~\ref{fig:CF4} give the follower's loads relative to the isolated wing on the same mesh family, at fixed angle of attack ($\alpha=3^\circ$). At $d_y=0.85b$, $d_x=3b$ the follower lift rises by $\Delta C_L=%+.4f$ (one-way VLM: %+.4f) and its drag changes by $\Delta C_D=%+.1f\times10^{-4}$ (VLM, induced part: %+.1f$\times10^{-4}$). The lift response, a numerically robust integral of the mean upwash the follower sees, agrees with the one-way VLM within %.0f\,\%% at this offset; furthermore, solving the coupled three-wing VLM matching the $y=0$ RANS symmetry plane (Sec.~\ref{sec:cfdsetup}, including the mirror follower at $-d_y$ across $2d_y=1.7b=\SI{3.60}{m}$) raises the VLM lift increment to $\Delta C_L=%+.4f$ (within %.1f\,\%% of RANS) and at $d_y=0.70b$ from $+0.0201$ to $%+.4f$ (closing roughly three fifths of the gap to RANS $+0.0283$). Meanwhile, two-way inviscid Biot--Savart upwash from the follower pair increases the leader's $C_L$ by only $%+.2f$\,\%% at $d_x=3b$, indicating that most of the $%+.1f$\,\%% leader $C_L$ shift between \texttt{iso\_a3\_L1} and \texttt{fol\_dy085\_dx3\_L1} reflects downstream wake-box mesh-refinement changes rather than upstream aerodynamic coupling. At $1.3b$ the RANS increment remains larger than the VLM's (by %.0f\,\%%), i.e.\ the diffused RANS upwash field is broader laterally than the planar sheet." % (b85.dCL_iso, b85.vlm_dCL, 1e4 * b85.dCD_iso, 1e4 * b85.vlm_dCDi, 100 * abs(b85.dCL_iso / b85.vlm_dCL - 1), dcl_sym85, 100 * abs(b85.dCL_iso / dcl_sym85 - 1), dcl_sym70, lead_shift_vlm, lead_shift_rans, 100 * (sel[np.isclose(sel.dy_b, 1.3)].iloc[0].dCL_iso / sel[np.isclose(sel.dy_b, 1.3)].iloc[0].vlm_dCL - 1)))
    txt.append(r"A fixed-angle comparison understates the energy benefit, because a follower at constant weight must \emph{reduce} its angle of attack ($\Delta\alpha\approx -\Delta C_L/C_{L\alpha}\approx -0.48^\circ$) to remove the extra lift. Applying a first-order linear trim projection $\Delta C_{D,\mathrm{trimmed}}=\Delta C_{D,\mathrm{fixed\text{-}\alpha}}-(\mathrm{d}C_D/\mathrm{d}C_L)\,\Delta C_L$ with the polar slope $\mathrm{d}C_D/\mathrm{d}C_L$ of the \emph{inviscid} model (%.3f) gives a drag reduction of $%.1f$\,\%% of the isolated L1 RANS drag ($C_{D,\mathrm{iso,L1}}=%.1f\times10^{-4}$) at $d_y=0.85b$ against $%.1f$\,\%% for the VLM on the same denominator; trimming with the (much steeper, partly viscous) RANS slope (%.3f) gives %.1f\,\%%. Because $%.1f\times10^{-4}$ of the $%.1f\times10^{-4}$ inviscid-trimmed L1 RANS reduction comes from the analytical slope projection rather than the fixed-$\alpha$ drag difference ($%+.1f\times10^{-4}$), this linear decoupling neglects secondary changes in spanwise circulation alignment and boundary-layer pressure drag when pitching down inside a non-uniform wake; the $\Delta C_L$ agreement ($5$--$7$\,\%% across VLM, L1 and L2) is therefore a firmer verification of the wake upwash than pressure-integrated drag. Expressed as an effective wake effectiveness $\kappa_{\mathrm{eff}}=\Delta C_{D,\mathrm{trimmed,RANS}}/\Delta C_{D,\mathrm{trimmed,VLM}}$---which is strictly the ratio of absolute drag-coefficient reductions and hence invariant to the unconverged isolated RANS drag denominator---the two trimming slopes bracket %.2f--%.2f at $0.85b$; the lower value (inviscid slope) is the better-defined one because the steep RANS slope contains profile-drag growth that is not a wake effect. The mission model already carries $\kappa\in[0.3,1.5]$ (Sec.~\ref{sec:sens}), so the RANS results fall inside the explored sensitivity range; their central estimate ($\kappa_{\mathrm{eff}}\approx0.4$--$0.6$ over $0.7b$--$1.0b$) is below the planar-sheet value and also below the free-wake-to-sheet benefit ratio of about 0.7. The RANS and VLM agree on the lateral shape: the benefit is broad between $0.7b$ and $1.0b$ and has fallen by two thirds at $1.3b$ (Fig.~\ref{fig:CF4})." % (sl["slope_vlm"], b85.trim_pct_iso_vs, 1e4 * i1.CD, -b85.vlm_trim_pct, sl["slope_cfd"], b85.trim_pct_iso, abs(proj_part), abs(tot_trim_rans), 1e4 * b85.dCD_iso, b85.kappa_eff_lo, b85.kappa_eff_hi))
    txt.append(r"\begin{table}[H]\centering\scriptsize\caption{Follower effect relative to the isolated wing (RANS L1 versus one-way planform VLM, $\alpha=3^\circ$). $\Delta C_D$ columns are $\times10^{-4}$; the trimmed percentage columns express $\Delta C_{D,\mathrm{trimmed}}$ as a percentage of the common isolated L1 RANS drag ($C_{D,\mathrm{iso,L1}}=153.1\times10^{-4}$; RANS rows trimmed with the inviscid slope $0.023$). $\kappa_{\mathrm{eff}}=\Delta C_{D,\mathrm{trimmed,RANS}}/\Delta C_{D,\mathrm{trimmed,VLM}}$ is the ratio of absolute drag-coefficient reductions (invariant to the isolated $C_D$ denominator), bracketing the inviscid and RANS trimming slopes.}\label{tab:cfdformation}")
    txt.append(r"\resizebox{\textwidth}{!}{\begin{tabular}{@{}rrrrrrrrr@{}}\toprule $d_x/b$ & $d_y/b$ & $\Delta C_L$ RANS & $\Delta C_L$ VLM & $\Delta C_D$ RANS & $\Delta C_{D,i}$ VLM & trimmed RANS (\%) & trimmed VLM (\%) & $\kappa_{\mathrm{eff}}$\\\midrule")
    txt.append(r"\input{tables/tab_cfdformation.tex}\\\bottomrule\end{tabular}}\end{table}")
    txt.append(r"\begin{figure}[H]\centering\includegraphics[width=\textwidth]{C4_formation_cfd_vs_vlm}\caption{Follower response versus lateral offset for three streamwise distances: (a) drag change at fixed angle of attack, (b) lift change, (c) roll-moment coefficient (RANS markers, VLM lines).}\label{fig:CF4}\end{figure}")
    cl_ok = ft[np.isclose(ft.dy_b, 0.85)]
    if len(cl_ok[cl_ok.dx_b != 3.0]):
        o = cl_ok.sort_values("dx_b"); txt.append("\\paragraph{Streamwise distance} At $d_y=0.85b$ the lift increment is " + ", ".join(f"{r.dCL_iso:+.4f} at $d_x={r.dx_b:.1f}b$ (VLM {r.vlm_dCL:+.4f})" for _, r in o.iterrows()) + ", and the trimmed saving (inviscid slope) is " + ", ".join(f"{r.trim_pct_iso_vs:.1f}\\,\\% at ${r.dx_b:.1f}b$" for _, r in o.iterrows()) + ". The weak dependence on $d_x$ confirms that, within the first five spans, the benefit is controlled by lateral rather than longitudinal position.")
    rl = ft[np.isclose(ft.dy_b, 0.85) & np.isclose(ft.dx_b, 3.0)].iloc[0]
    txt.append(r"\paragraph{Roll moment} The RANS rolling-moment coefficient of the follower at $0.85b$ is %+.4f (VLM %+.4f): the sign matches the VLM at all four offsets (positive at $0.7b$, negative at $0.85b$, $1.0b$ and $1.3b$), with magnitudes $|C_l|=0.001$--$0.0035$ against an elevon authority $C_{l\delta a}\delta_{\max}\approx0.05$ for an assumed $\delta_{\max}=20^\circ$; the wake-induced roll moment is therefore a few per cent of the control authority, consistent with treating it as a bounded disturbance in the control model (the $\sim$50\,\%% magnitude differences with the VLM are within what a one-sided surface integration of a small moment on this mesh can resolve)." % (rl.fCl, rl.Cl_vlm))

# L2 follower
fl2 = d[(d.dy_b == 0.85) & (d.dx_b == 3.0)].sort_values("level")
if len(fl2) > 1 and 2 in set(fl2.level) and 2 in lv:
    a = fl2[fl2.level == 1].iloc[0]; c = fl2[fl2.level == 2].iloc[0]; i2 = lv[2]
    dcl1, dcd1 = a.fCL - lv[1].CL, a.fCD - lv[1].CD; dcl2, dcd2 = c.fCL - i2.CL, c.fCD - i2.CD
    v85 = ft[np.isclose(ft.dy_b, 0.85) & np.isclose(ft.dx_b, 3.0)].iloc[0]
    k2 = (dcd2 - sl["slope_vlm"] * dcl2) / (v85.vlm_dCDi - sl["slope_vlm"] * v85.vlm_dCL)
    txt.append(r"\paragraph{Mesh sensitivity of the follower effect} Repeating the isolated and follower cases at level L2 (%dk and %dk cells) changes the lift increment from %+.4f to %+.4f (%.0f\,\%%) but the drag increment from %+.1f to %+.1f ($\times10^{-4}$), i.e.\ it roughly doubles. The drag increment is therefore itself mesh-sensitive, as expected for a pressure-integrated RANS drag that is not mesh-converged (the L1 to L2 change in the isolated $C_D$ is %+.1f\,\%%). With the inviscid trimming slope the finer mesh gives $\kappa_{\mathrm{eff}}=%.2f$ at $0.85b$ against %.2f at L1, so the central estimate moves towards, but stays below, the planar-sheet value; the drag-based $\kappa_{\mathrm{eff}}$ should be read as an order-of-magnitude confirmation, not a calibration." % (i2.cells // 1000, c.cells // 1000, dcl1, dcl2, 100 * abs(dcl2 / dcl1 - 1), 1e4 * dcd1, 1e4 * dcd2, 100 * (i2.CD / lv[1].CD - 1), k2, v85.kappa_eff_lo))
txt.append(r"\paragraph{Flow visualisation} Figures~\ref{fig:K1}--\ref{fig:K3} show the solution in three dimensions: the surface pressure on the three aircraft, the vortex system and the vertical-velocity planes. The follower sits in the outboard upwash of the leader's tip vortex, and the isolated-wing pressure distribution shows the expected suction peak on the forward upper surface.")
for k, nm, cap in (("K1", "K1_cp_fol_dy085_dx3_L1", "Surface pressure coefficient on the leader (mirrored through the symmetry plane) and the two followers at $d_x=3b$, $d_y=0.85b$ (RANS, L1)."),
                   ("K2", "K2_vortex_fol_dy085_dx3_L1", "Iso-surface of the Q-criterion ($Q=0.1\\,(U_\\infty/b)^2$) coloured by streamwise vorticity, with the wall region masked, for the formation case."),
                   ("K3", "K3_wslices_fol_dy085_dx3_L1", "Vertical velocity $w/U_\\infty$ on four cross-flow planes ($x=1$\\,m, $3b$, $5b$, $8b$): the leader's tip upwash decays and diffuses; the follower's own wake appears at $x=5b$ and beyond.")):
    if os.path.exists(f"manuscript/figures/{nm}.png"):
        txt.append(r"\begin{figure}[H]\centering\includegraphics[width=\textwidth]{%s}\caption{%s}\label{fig:%s}\end{figure}" % (nm, cap, k))
txt.append(r"\begin{figure}[H]\centering\includegraphics[width=\textwidth]{C6_residual_history}\caption{Initial-residual histories of the L1 isolated and follower cases; both stop on the residual-control criterion before the iteration cap.}\label{fig:CF6}\end{figure}")
txt.append(r"\paragraph{What the CFD does and does not show} The RANS results (i) confirm the sign, order of magnitude and lateral breadth of the wake benefit, (ii) show that the lift (upwash) response is predicted by the planar-sheet VLM within about 7\,\% at the best offset (RANS broader laterally), (iii) bracket the \emph{drag} benefit at roughly $0.4$ to $1.1$ times the VLM value at $0.85b$--$1.0b$, and (iv) provide no support for benefits larger than the VLM predicts. They do \emph{not} validate the model quantitatively: the geometry is a clean wing without fuselage, propeller or control surfaces, the mesh has no prism layers, wall functions are used at $y^+\approx60$, the flow is steady RANS (no turbulence in the free stream, no wake meander), the drag is obtained by surface integration with a Python post-processor, and no experimental data for this planform exist for comparison. The mission-level conclusions of Sec.~\ref{sec:mission} are therefore unchanged: the CFD stays within the sensitivity range already explored.")
open("manuscript/sections/res_cfd.tex", "w").write("\n\n".join(txt) + "\n")
print("wrote res_cfd.tex", sum(len(t) for t in txt))
