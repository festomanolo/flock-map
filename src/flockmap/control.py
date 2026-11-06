"""Guidance-level formation simulation: point-mass kinematics with bank / acceleration actuator lags.

NOT a 6-DOF model and NOT PX4/Gazebo SITL.  Wake forces are not fed back into the dynamics (open-loop wake);
altitude is held (d_z = 0).  See manuscript Sec. 'Limitations'.

States (follower j):  x = [px, py, V, chi, phi, a]     (a = V_dot, first-order lag tau_a)
Inputs:               u = [a_cmd, phi_cmd]
Wind:                 ground velocity = V*[cos chi, sin chi] + w_eff, w_eff low-pass filtered (tau_g)
Controllers:          "P"        proportional-derivative lateral/longitudinal law
                      "NMPC"     casadi/IPOPT multiple-shooting NMPC, N=25, dt=0.1 s (10 Hz)
                      "NMPC+CBF" NMPC nominal + relative-degree-3 HOCBF-QP safety filter at 50 Hz
"""
from __future__ import annotations
import dataclasses, math, time
import numpy as np
from scipy.optimize import minimize
from .config import AC, G

TAU_PHI, TAU_A, TAU_G = AC.tau_phi, 0.30, 1.0
A_MAX, PHI_MAX = 3.0, math.radians(AC.bank_max_deg)
V_MIN, V_MAX = AC.va_min, AC.va_max
DT_SIM, DT_MPC, NP = 0.02, 0.1, 25


# --------------------------------------------------------------------------------------- NMPC
def _build_nmpc():
    import casadi as ca
    N = NP
    X = ca.SX.sym("X", 6, N + 1); U = ca.SX.sym("U", 2, N)
    P = ca.SX.sym("P", 6 + 2 + 4 * (N + 1) + 2)   # x0, w_hat, ref(px,py,vx,vy)*(N+1), u_prev
    x0 = P[0:6]; w = P[6:8]; ref = P[8:8 + 4 * (N + 1)]; uprev = P[-2:]

    def f(x, u):
        px, py, V, chi, phi, a = [x[i] for i in range(6)]
        return ca.vertcat(V * ca.cos(chi) + w[0], V * ca.sin(chi) + w[1], a, G * ca.tan(phi) / V,
                          (u[1] - phi) / TAU_PHI, (u[0] - a) / TAU_A)

    def rk4(x, u, h):
        k1 = f(x, u); k2 = f(x + h / 2 * k1, u); k3 = f(x + h / 2 * k2, u); k4 = f(x + h * k3, u)
        return x + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)

    Qp = ca.diag(ca.DM([1.0, 6.0])); Qv = ca.diag(ca.DM([0.4, 0.8])); R = ca.diag(ca.DM([0.2, 3.0]))
    Rd = ca.diag(ca.DM([0.5, 8.0]))
    cost = 0; g = [X[:, 0] - x0]
    up = uprev
    for k in range(N):
        g.append(X[:, k + 1] - rk4(X[:, k], U[:, k], DT_MPC))
        r = ref[4 * k:4 * k + 4]
        ep = X[0:2, k] - r[0:2]
        ev = ca.vertcat(X[2, k] * ca.cos(X[3, k]) + w[0], X[2, k] * ca.sin(X[3, k]) + w[1]) - r[2:4]
        cost += ep.T @ Qp @ ep + ev.T @ Qv @ ev + U[:, k].T @ R @ U[:, k] + (U[:, k] - up).T @ Rd @ (U[:, k] - up)
        up = U[:, k]
    r = ref[4 * N:4 * N + 4]; ep = X[0:2, N] - r[0:2]
    cost += 10 * ep.T @ Qp @ ep
    w_ = ca.vertcat(ca.reshape(X, -1, 1), ca.reshape(U, -1, 1))
    nlp = dict(x=w_, p=P, f=cost, g=ca.vertcat(*g))
    opts = {"ipopt.print_level": 0, "print_time": 0, "ipopt.max_iter": 60, "ipopt.tol": 1e-4,
            "ipopt.acceptable_tol": 1e-3, "ipopt.warm_start_init_point": "yes", "ipopt.sb": "yes",
            "ipopt.mu_init": 1e-3, "expand": True}
    solver = ca.nlpsol("nmpc", "ipopt", nlp, opts)
    nx, nu = 6 * (N + 1), 2 * N
    lbx = np.concatenate([np.tile([-1e9, -1e9, V_MIN, -1e9, -PHI_MAX, -A_MAX], N + 1),
                          np.tile([-A_MAX, -PHI_MAX], N)])
    ubx = np.concatenate([np.tile([1e9, 1e9, V_MAX, 1e9, PHI_MAX, A_MAX], N + 1), np.tile([A_MAX, PHI_MAX], N)])
    return solver, lbx, ubx


# --------------------------------------------------------------------------------------- HOCBF (relative degree 3)
def _build_hocbf(alpha=(1.2, 1.6, 2.0)):
    r = ca.SX.sym("r", 2)                 # relative position follower - leader
    V, chi, phi, a = ca.SX.sym("V"), ca.SX.sym("chi"), ca.SX.sym("phi"), ca.SX.sym("a")
    vL = ca.SX.sym("vL", 2); wf = ca.SX.sym("wf", 2)     # leader ground velocity, follower wind estimate
    D = ca.SX.sym("D"); uu = ca.SX.sym("u", 2)
    x = ca.vertcat(r, V, chi, phi, a)
    rd = ca.vertcat(V * ca.cos(chi) + wf[0] - vL[0], V * ca.sin(chi) + wf[1] - vL[1])
    xdot = ca.vertcat(rd, a, G * ca.tan(phi) / V, (uu[1] - phi) / TAU_PHI, (uu[0] - a) / TAU_A)

    def lie(psi):
        return ca.jacobian(psi, x) @ xdot
    h = r[0] ** 2 + r[1] ** 2 - D ** 2
    p1 = lie(h) + alpha[0] * h
    p2 = lie(p1) + alpha[1] * p1
    p3 = lie(p2) + alpha[2] * p2
    A = ca.jacobian(p3, uu)
    c = ca.substitute(p3, uu, ca.SX.zeros(2))
    fA = ca.Function("A", [r, V, chi, phi, a, vL, wf, D], [A, c, h, p1, p2])
    return fA


@dataclasses.dataclass
class Scenario:
    name: str
    duration: float = 60.0
    wind: float = 4.0              # common wind speed [m/s]
    wind_dir: float = 0.0          # rad, direction wind blows toward
    sigma_ind: float = 0.4         # individual (differential) gust std [m/s]
    tau_ind: float = 2.0
    doublet: float = 0.0           # differential lateral doublet amplitude on follower [m/s]
    doublet_t: float = 15.0
    doublet_sign: float = -1.0     # -1: pushes follower toward leader (inboard)
    rtk_sigma: float = 0.03        # relative-position measurement noise [m]
    rtk_bias: float = 0.0          # slowly varying bias std [m] (degraded GNSS)
    delay: float = 0.05            # leader-state latency [s]
    dropouts: tuple = ()           # ((t0, dur), ...) intervals with no leader update
    leader_decel: tuple = ()       # (t0, dt, dV)
    slot: tuple = (6.36, 1.70)     # (dx, dy) formation slot [m], follower on +y side
    slot_sched: tuple = ()         # ((t_start, T, dx_new, dy_new), ...) min-jerk moves
    d_safe: float = 4.24


def _minjerk(s):
    s = min(max(s, 0.0), 1.0)
    return 10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5


def _slot_at(t, sc: Scenario):
    dx, dy = sc.slot
    for (t0, T, dxn, dyn) in sc.slot_sched:
        s = _minjerk((t - t0) / T)
        dx, dy = dx + s * (dxn - dx), dy + s * (dyn - dy)
    return dx, dy


def _slot_rate(t, sc: Scenario, h=0.05):
    a = np.array(_slot_at(t + h, sc)); b = np.array(_slot_at(t - h, sc))
    return (a - b) / (2 * h)


_NMPC = None; _HOCBF = None


def _get():
    global _NMPC, _HOCBF
    if _NMPC is None:
        _NMPC = _build_nmpc(); _HOCBF = _build_hocbf()
    return _NMPC, _HOCBF


def _cbf_qp(u0, A, c, margin):
    """min 0.5|u-u0|^2  s.t.  A u + c - margin >= 0 ; box bounds.  Returns (u, active, feasible)."""
    lb = np.array([-A_MAX, -PHI_MAX]); ub = np.array([A_MAX, PHI_MAX])
    A = np.asarray(A, float).reshape(-1); cons = float(c) - margin
    if A @ u0 + cons >= 0:
        return u0, False, True
    res = minimize(lambda u: 0.5 * np.sum((u - u0) ** 2), u0, jac=lambda u: u - u0, method="SLSQP",
                   bounds=list(zip(lb, ub)), constraints=[{"type": "ineq", "fun": lambda u: A @ u + cons,
                                                            "jac": lambda u: A}], options={"maxiter": 50, "ftol": 1e-9})
    u = np.clip(res.x, lb, ub)
    feas = (A @ u + cons) >= -1e-6
    return u, True, bool(feas)


def simulate(sc: Scenario, controller: str = "NMPC+CBF", seed: int = 0, cbf_margin: float = 0.0,
             d_eff_extra: float = 0.5, record=True) -> dict:
    rng = np.random.default_rng(seed)
    (solver, lbx, ubx), fA = _get()
    T = sc.duration; n = int(round(T / DT_SIM)); VL0 = AC.va
    # initial states: leader at origin heading 0 (north=+x), follower in slot
    dx0, dy0 = _slot_at(0.0, sc)
    xf = np.array([-dx0, dy0, VL0, 0.0, 0.0, 0.0])
    w_c = sc.wind * np.array([math.cos(sc.wind_dir), math.sin(sc.wind_dir)])
    w_eff_f = w_c.copy(); w_eff_l = w_c.copy()
    ind_f = np.zeros(2); ind_l = np.zeros(2)
    pL = np.array([0.0, 0.0]); VL = VL0
    bias = np.zeros(2); u_cur = np.zeros(2); u_nom_prev = np.zeros(2)
    warm = None; last_leader = (pL.copy(), VL0 * np.array([1.0, 0.0]) + w_c, 0.0, 0.0)
    hist_L = [(0.0, pL.copy(), VL * np.array([1.0, 0.0]) + w_c)]
    w_hat = w_c.copy(); vg_prev = None
    out = {k: [] for k in ("t", "ex", "ey", "dist", "phi", "V", "u_a", "u_phi", "cbf_active", "cbf_infeas",
                           "h", "dx", "dy", "dxs", "dys", "pfx", "pfy", "plx", "ply", "chi")}
    solve_times = []; n_cbf = 0; n_infeas = 0; n_active = 0; n_mpc_fail = 0
    sat = 0
    for k in range(n):
        t = k * DT_SIM
        # leader speed profile
        VL_now = VL0
        for (t0, dtt, dV) in sc.leader_decel:
            VL_now += dV * _minjerk((t - t0) / dtt)
        VL = VL_now
        vL_g = VL * np.array([1.0, 0.0]) + w_eff_l
        pL = pL + DT_SIM * vL_g
        # wind processes (OU for individual component)
        ind_f += DT_SIM * (-ind_f / sc.tau_ind) + math.sqrt(2 * DT_SIM / sc.tau_ind) * sc.sigma_ind * rng.standard_normal(2)
        ind_l += DT_SIM * (-ind_l / sc.tau_ind) + math.sqrt(2 * DT_SIM / sc.tau_ind) * sc.sigma_ind * rng.standard_normal(2)
        gust = np.zeros(2)
        if sc.doublet > 0 and sc.doublet_t <= t <= sc.doublet_t + 2.0:
            s = (t - sc.doublet_t) / 2.0
            gust = np.array([0.0, sc.doublet_sign * sc.doublet * math.sin(2 * math.pi * s) * 1.0])
        w_f = w_c + ind_f + gust; w_l = w_c + ind_l
        w_eff_f += DT_SIM * (w_f - w_eff_f) / TAU_G
        w_eff_l += DT_SIM * (w_l - w_eff_l) / TAU_G
        # leader info with latency/dropout
        hist_L.append((t, pL.copy(), vL_g.copy()))
        in_drop = any(t0 <= t < t0 + d for (t0, d) in sc.dropouts)
        if not in_drop:
            tt = t - sc.delay
            j = max(0, int(round(tt / DT_SIM)))
            _, pLm, VLm = hist_L[min(j, len(hist_L) - 1)]
            last_leader = (pLm.copy(), np.array(VLm, float), tt, 0.0)
        pLm, VLm, tm, _ = last_leader
        pL_est = pLm + (t - tm) * VLm      # constant-velocity extrapolation of broadcast GNSS state
        if sc.rtk_bias > 0:
            bias += DT_SIM * (-bias / 20.0) + math.sqrt(2 * DT_SIM / 20.0) * sc.rtk_bias * rng.standard_normal(2)
        meas_noise = sc.rtk_sigma * rng.standard_normal(2) + bias
        # follower's measured position of itself relative to leader (noisy)
        p_f_meas = xf[0:2] + meas_noise
        # wind estimate from ground-velocity difference (low-pass)
        vg = xf[2] * np.array([math.cos(xf[3]), math.sin(xf[3])]) + w_eff_f
        w_hat += DT_SIM * (w_eff_f - w_hat) / 1.5   # idealised wind observer (1.5 s lag on true effective wind)
        # --- nominal control (10 Hz for NMPC, 50 Hz for P)
        dxs, dys = _slot_at(t, sc)
        slot_v = _slot_rate(t, sc)
        if controller == "P":
            r_des = pL_est + np.array([-dxs, dys])
            e = r_des - p_f_meas
            vL_vec = VLm.copy()
            ev = vL_vec + np.array([-slot_v[0], slot_v[1]]) - (xf[2] * np.array([math.cos(xf[3]), math.sin(xf[3])]) + w_eff_f)
            # rotate error into follower-heading frame for lateral/longitudinal split
            ec, es = math.cos(xf[3]), math.sin(xf[3])
            e_lon = ec * e[0] + es * e[1]; e_lat = -es * e[0] + ec * e[1]
            ev_lon = ec * ev[0] + es * ev[1]; ev_lat = -es * ev[0] + ec * ev[1]
            a_c = np.clip(0.30 * e_lon + 0.9 * ev_lon, -A_MAX, A_MAX)
            ay = 0.45 * e_lat + 1.1 * ev_lat
            phi_c = np.clip(math.atan2(ay, G), -PHI_MAX, PHI_MAX)
            u_nom = np.array([a_c, phi_c])
        else:
            if k % int(round(DT_MPC / DT_SIM)) == 0:
                ref = []
                for i in range(NP + 1):
                    ti = t + i * DT_MPC
                    dxi, dyi = _slot_at(ti, sc)
                    pr = pL_est + (ti - t) * VLm + np.array([-dxi, dyi])
                    vr = VLm + np.array([-_slot_rate(ti, sc)[0], _slot_rate(ti, sc)[1]])
                    ref += [pr[0], pr[1], vr[0], vr[1]]
                x0 = np.array([p_f_meas[0], p_f_meas[1], xf[2], xf[3], xf[4], xf[5]])
                p = np.concatenate([x0, w_hat, ref, u_nom_prev])
                if warm is None:
                    guess = np.concatenate([np.tile(x0, NP + 1), np.zeros(2 * NP)])
                else:
                    guess = warm
                t0 = time.perf_counter()
                sol = solver(x0=guess, p=p, lbg=0, ubg=0, lbx=lbx, ubx=ubx)
                solve_times.append(time.perf_counter() - t0)
                stats = solver.stats()
                if not stats["success"]:
                    n_mpc_fail += 1
                z = np.array(sol["x"]).ravel()
                warm = z
                Uflat = z[6 * (NP + 1):]
                u_nom = np.array([Uflat[0], Uflat[1]])
                u_nom_prev = u_nom.copy()
                u_hold = u_nom
            u_nom = u_hold
        u = u_nom
        active = False; infeas = False
        if controller == "NMPC+CBF":
            # measured relative state (noisy position, exact otherwise)
            rrel = p_f_meas - pL_est
            Am, cm, hval, p1, p2 = fA(rrel, xf[2], xf[3], xf[4], xf[5], VLm, w_hat, sc.d_safe + d_eff_extra)
            u, active, feas = _cbf_qp(u_nom, np.array(Am).ravel(), float(cm), cbf_margin)
            n_cbf += 1; n_active += int(active); infeas = (not feas); n_infeas += int(infeas)
        # --- plant integration (Euler, 50 Hz)
        a_c, phi_c = u
        a_dot = (a_c - xf[5]) / TAU_A
        phi_dot = (phi_c - xf[4]) / TAU_PHI
        chi_dot = G * math.tan(xf[4]) / xf[2]
        xf[0] += DT_SIM * (xf[2] * math.cos(xf[3]) + w_eff_f[0])
        xf[1] += DT_SIM * (xf[2] * math.sin(xf[3]) + w_eff_f[1])
        V_new = xf[2] + DT_SIM * xf[5]
        if (V_new >= V_MAX and xf[5] > 0) or (V_new <= V_MIN and xf[5] < 0):
            xf[5] = 0.0; V_new = min(max(V_new, V_MIN), V_MAX)
        xf[2] = V_new
        xf[3] += DT_SIM * chi_dot
        xf[4] += DT_SIM * phi_dot
        xf[5] += DT_SIM * a_dot
        # true relative geometry
        rt = xf[0:2] - pL
        dxr, dyr = -rt[0], rt[1]
        if record and k % 5 == 0:
            out["t"].append(t); out["ex"].append(dxr - dxs); out["ey"].append(dyr - dys)
            out["dist"].append(float(np.hypot(*rt))); out["phi"].append(math.degrees(xf[4]))
            out["V"].append(xf[2]); out["u_a"].append(u[0]); out["u_phi"].append(math.degrees(u[1]))
            out["cbf_active"].append(int(active)); out["cbf_infeas"].append(int(infeas))
            out["dx"].append(dxr); out["dy"].append(dyr); out["dxs"].append(dxs); out["dys"].append(dys)
            out["h"].append(float(rt @ rt - sc.d_safe ** 2))
            out["pfx"].append(xf[0]); out["pfy"].append(xf[1]); out["plx"].append(pL[0]); out["ply"].append(pL[1]); out["chi"].append(xf[3])
        if abs(u[1]) >= PHI_MAX - 1e-6 or abs(u[0]) >= A_MAX - 1e-6:
            sat += 1
    res = {k: np.asarray(v) for k, v in out.items()}
    res["meta"] = dict(controller=controller, scenario=sc.name, seed=seed,
                       solve_ms_mean=float(np.mean(solve_times) * 1e3) if solve_times else 0.0,
                       solve_ms_max=float(np.max(solve_times) * 1e3) if solve_times else 0.0,
                       n_mpc_fail=n_mpc_fail, cbf_active_frac=n_active / max(n_cbf, 1),
                       cbf_infeasible=n_infeas, sat_frac=sat / n)
    return res
