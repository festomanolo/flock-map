"""Physics-based mission energy model for the four strategies and the factorial decomposition variants.

Energies are integrals of the power model (energy.py) over explicit phases (climb, transit, mapping, Dubins turns,
ferry legs, waiting, reconfiguration, landing).  Randomness enters only through the environment (wind) and recorded
station-keeping error series (bootstrapped from the control campaign) and is common to all strategies in a trial.
"""
from __future__ import annotations
import math, dataclasses
import numpy as np
from .config import AC, CAM, MIS, BAT, G
from . import energy as E, photo, battery

VA = AC.va
P_WAIT = min(E.p_level(v, AC.bank_turn_deg) for v in np.linspace(AC.va_min, VA, 25))   # loiter at best-endurance speed
ROC, T_LAND = 2.0, 90.0                 # [ASM] climb rate [m/s]; approach-and-landing time at cruise power [s]
T_CLIMB = CAM.agl / ROC
PHASES = ("climb", "transit", "mapping", "turns", "ferry", "wait", "reconfig", "landing")

PLAN = {
    "17@65": dict(n=(6, 6, 5), spacing=CAM.Wg * (1 - CAM.os_base)),
    "14@58": dict(n=(5, 5, 4), spacing=CAM.Wg * (1 - CAM.os_opt)),       # as specified in the manuscript
    "14@57.95": dict(n=(5, 5, 4), spacing=74.0),                         # edge-optimised: meets the 5-ray rule
}
# name: (formation transit?, plan, rigid through mapping?)
STRATEGIES = {
    "S1_independent": (False, "17@65", False),
    "S2_rigid_V": (True, "17@65", True),
    "S3_adaptive_geometric": (True, "17@65", False),
    "S4_wake_aware": (True, "14@57.95", False),
    "D1_independent_14": (False, "14@57.95", False),
    "D2_wake_aware_14_as_specified": (True, "14@58", False),
}


@dataclasses.dataclass
class Env:
    wind: float
    wind_dir: float        # direction the wind blows toward (0 = +y of the polygon = north)
    err_series: tuple      # (dx_err, dy_err) arrays [m]: recorded follower station-keeping error


def ground_speed(heading, env: Env, va=VA):
    wpar = env.wind * math.cos(env.wind_dir - heading)
    wperp = env.wind * math.sin(env.wind_dir - heading)
    crab = math.asin(max(min(-wperp / va, 1.0), -1.0))
    return va * math.cos(crab) + wpar, crab


def leg_time(dist, heading, env):
    return dist / ground_speed(heading, env)[0]


def realised_dcd(model, env: Env, va=VA):
    ex, ey = env.err_series
    return float(np.mean(E.table(model, va)(6.36 + ex, 1.70 + ey)))


@dataclasses.dataclass
class Result:
    e_load: float; e_cell: float; e_uav: list; t_end_min: float; phases: dict; feasible: bool
    n_strips: int; accepted_ha: float; coverage: float; saving_frac: float
    timeline: list = None


def _cell_energy(seqs):
    out = []
    for seq in seqs:
        soc, tot = 1.0, 0.0
        for p, dt in seq:
            if dt <= 0: continue
            k = max(1, int(dt // 30)); h = dt / k
            for _ in range(k):
                e, soc = battery.draw(p, soc, h); tot += e
        out.append(tot)
    return out


def run(strategy: str, env: Env, model: str, rc: dict, mult_cache: dict | None = None,
        d_transit: float | None = None) -> Result:
    """rc: reconfiguration cost table for this aero model: rc[(kind, Y)] -> dict(T, E_f) (follower Wh over window)."""
    form, plan_key, rigid = STRATEGIES[strategy]
    plan = PLAN[plan_key]; s = plan["spacing"]; nstr = plan["n"]; L = MIS.side
    p_iso = E.p_level(VA); p_turn = E.p_level(VA, AC.bank_turn_deg); p_clm = E.p_climb(VA, ROC)
    dcd = realised_dcd(model, env) if form else 0.0
    p_fol = E.p_level(VA, 0.0, -dcd)
    p_form = (p_iso + 2 * p_fol) / 3.0          # leader role rotates => each UAV pays the mean
    Lturn = E.turn_path_len(s)
    ph = {k: 0.0 for k in PHASES}
    seqs = [[] for _ in range(3)]; e_uav = [0.0] * 3; t_uav = [0.0] * 3; tl = [[] for _ in range(3)]

    def add(u, phase, p, t):
        if t <= 0: return
        e = p * t / 3600.0
        ph[phase] += e; e_uav[u] += e; t_uav[u] += t; seqs[u].append((p, t)); tl[u].append((phase, p, t))

    def strips_time(n):
        return sum(leg_time(L, 0.0 if i % 2 == 0 else math.pi, env) for i in range(n))

    for u in range(3):
        add(u, "climb", p_clm, T_CLIMB)
    zone_off = [(u - 1) * nstr[1] * s for u in range(3)]
    d = MIS.d_transit if d_transit is None else d_transit

    if not form:
        for u in range(3):
            n = nstr[u]; d_go = math.hypot(d, zone_off[u])
            add(u, "transit", p_iso, leg_time(d_go, 0.0, env))
            add(u, "mapping", p_iso, strips_time(n))
            add(u, "turns", p_turn, (n - 1) * Lturn / VA)
            if n % 2 == 1: add(u, "ferry", p_iso, leg_time(L, math.pi, env))
            add(u, "transit", p_iso, leg_time(d_go, math.pi, env))
            add(u, "landing", p_iso, T_LAND)
    else:
        def win(u, kind, Y):
            w = rc[(kind, Y)]
            add(u, "reconfig", p_iso if u == 0 else w["E_f"] * 3600 / w["T"], w["T"])
            return w["T"]

        Y = round(nstr[1] * s, 1)
        t_join = rc[("merge", 60.0)]["T"]; t_brk = rc[("split", 60.0)]["T"]
        t_spl = 0.0 if rigid else rc[("split", Y)]["T"]
        t_mrg = 0.0 if rigid else rc[("merge", Y)]["T"]
        t_out = leg_time(d, 0.0, env); t_ret = leg_time(d, math.pi, env)
        for u in range(3):                                   # R1: join-up; steady formation transit; (R2 below)
            win(u, "merge", 60.0)
            add(u, "transit", p_form, t_out - t_join - t_spl)
        if rigid:
            n = sum(nstr)
            Rt = VA ** 2 / (G * math.tan(math.radians(AC.bank_turn_deg)))
            p_out = E.p_level(VA * (1 + 1.70 / Rt), AC.bank_turn_deg)
            p_in = E.p_level(VA * (1 - 1.70 / Rt), AC.bank_turn_deg)
            for u in range(3):
                add(u, "mapping", p_form, strips_time(n))
                add(u, "turns", (p_turn + p_out + p_in) / 3.0, (n - 1) * Lturn / VA)
                if n % 2 == 1: add(u, "ferry", p_form, leg_time(L, math.pi, env))
        else:
            for u in range(3):                               # R2: disperse into zones, map own strips
                win(u, "split", Y)
                n = nstr[u]
                add(u, "mapping", p_iso, strips_time(n))
                add(u, "turns", p_turn, (n - 1) * Lturn / VA)
                if n % 2 == 1: add(u, "ferry", p_iso, leg_time(L, math.pi, env))
            tmax = max(t_uav)
            for u in range(3):
                add(u, "wait", P_WAIT, tmax - t_uav[u])      # loiter (best-endurance speed, banked) until the slowest finishes
                win(u, "merge", Y)                           # R3: re-form
        for u in range(3):
            add(u, "transit", p_form, t_ret - t_mrg - t_brk)
            win(u, "split", 60.0)                            # R4: break-up at home
            add(u, "landing", p_iso, T_LAND)
    cell = _cell_energy(seqs)
    usable = BAT.usable_frac * BAT.capacity_ah * BAT.cells * 3.7     # nominal-voltage energy of the usable window
    # ---- geometric coverage / accepted area (criteria 1 and 2 only)
    crab = ground_speed(0.0, env)[1]
    key = (plan_key, round(math.degrees(crab) * 2) / 2)
    if mult_cache is not None and key in mult_cache:
        acc, cov = mult_cache[key]
    else:
        nn = sum(nstr)
        mm = photo.multiplicity_map(photo.strip_centres(nn, s), None, crab=[crab if i % 2 == 0 else -crab for i in range(nn)])
        acc, cov, _ = photo.accepted_area(mm)
        if mult_cache is not None: mult_cache[key] = (acc, cov)
    return Result(sum(e_uav), sum(cell), e_uav, max(t_uav) / 60.0, ph, all(c <= usable for c in cell),
                  sum(nstr) if not rigid else sum(nstr), acc, cov, 1 - p_fol / p_iso, tl)
