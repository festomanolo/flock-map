"""Power / energy bookkeeping shared by the mission model and the reconfiguration analysis."""
from __future__ import annotations
import math, functools
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from .config import AC, G, BAT
from . import aero, vlm, battery
from .dubins import dubins_length

AERO_MODELS = ("published", "strip_corrected", "vlm_rolled", "vlm_sheet", "vlm_free")


def p_level(va, bank_deg=0.0, dcd=0.0, ac=AC):
    """Electrical load [W] at airspeed va, bank, with additional drag-coefficient change dcd (negative = saving)."""
    n = 1.0 / math.cos(math.radians(bank_deg))
    q = 0.5 * ac.rho * va ** 2
    cl = ac.mass * G * n / (q * ac.S)
    cd = ac.cd0 + ac.k0 * cl ** 2 + dcd
    return q * ac.S * cd * va / ac.eta_prop + ac.p_hotel


def p_climb(va, roc, ac=AC):
    return p_level(va) + ac.mass * G * roc / ac.eta_prop


class SavingTable:
    """dCD_net(dx_m, dy_m) for one aero model at one airspeed (positive = drag reduction), interpolated."""
    def __init__(self, model: str, va: float = 18.0, ac=AC):
        self.model, self.va = model, va
        b = ac.b
        self.dx = np.linspace(1.5, 5.0, 8) * b
        self.dy = np.linspace(0.35, 2.6, 46) * b
        T = np.zeros((len(self.dx), len(self.dy)))
        for i, dx in enumerate(self.dx):
            for j, dy in enumerate(self.dy):
                T[i, j] = self._eval(dx / b, dy / b)
        self.f = RegularGridInterpolator((self.dx, self.dy), T, bounds_error=False, fill_value=None)

    def _eval(self, dxb, dyb):
        if self.model == "published":
            return aero.strip_follower(dxb, dyb, 0.0, self.va, variant="published")["dcd_net"]
        if self.model == "strip_corrected":
            return aero.strip_follower(dxb, dyb, 0.0, self.va, variant="corrected")["dcd_net"]
        if self.model == "vlm_rolled":
            return vlm.follower(dxb, dyb, 0.0, self.va, wake="rolled")["dcd_net"]
        if self.model == "vlm_sheet":
            return vlm.follower(dxb, dyb, 0.0, self.va, wake="sheet")["dcd_net"]
        if self.model == "vlm_free":
            return vlm.follower(dxb, dyb, 0.0, self.va, wake="free")["dcd_net"]
        raise ValueError(self.model)

    def __call__(self, dx_m, dy_m):
        dx = np.clip(np.atleast_1d(dx_m).astype(float), self.dx[0], self.dx[-1])
        dyy = np.abs(np.atleast_1d(dy_m).astype(float))
        out = self.f(np.stack([dx, np.clip(dyy, self.dy[0], self.dy[-1])], -1))
        return np.where(dyy > self.dy[-1], 0.0, out)      # no wake benefit beyond the tabulated lateral range


class ScaledTable:
    """Wake-effectiveness scaling kappa applied to a tabulated drag-coefficient reduction (model name 'base@kappa')."""
    def __init__(self, base: SavingTable, kappa: float):
        self.base, self.kappa = base, kappa
    def __call__(self, dx_m, dy_m):
        return self.kappa * self.base(dx_m, dy_m)


@functools.lru_cache(maxsize=None)
def table(model: str, va: float = 18.0):
    if "@" in model:
        base, k = model.split("@"); return ScaledTable(table(base, va), float(k))
    return SavingTable(model, va)


def p_follower_steady(model, dx=6.36, dy=1.70, va=18.0):
    return p_level(va, 0.0, -float(table(model, va)(dx, dy)[0]))


# ------------------------------------------------------------------ turns (Dubins) in a boustrophedon
@functools.lru_cache(maxsize=None)
def turn_path_len(spacing: float, va: float = 18.0, bank_deg: float = 25.0) -> float:
    """Shortest path between the end of one strip (heading N) and the start of the next (heading S) at lateral
    offset `spacing` with turn radius R = V^2/(g tan phi); includes the straight run-in to the polygon edge."""
    R = va ** 2 / (G * math.tan(math.radians(bank_deg)))
    best = 1e18
    for ye in np.linspace(0, 4 * R, 161):
        L = dubins_length((0.0, 0.0, math.pi / 2), (spacing, ye, -math.pi / 2), R) + ye
        best = min(best, L)
    return best


def turn_bank_equivalent(va=18.0, bank_deg=25.0):
    return bank_deg


# ------------------------------------------------------------------ reconfiguration from a simulation record
def reconfig_energy(ts: dict, t_a: float, t_b: float, model: str, va=18.0, dt=0.1):
    """Energy [Wh] of the follower between t_a and t_b from a control time series (V, bank, dx, dy)."""
    t = ts["t"]; m = (t >= t_a) & (t <= t_b)
    tab = table(model, va)
    V = ts["V"][m]; phi = ts["phi"][m]
    dcd = -tab(ts["dx"][m], ts["dy"][m])
    # power at each sample (V varies a little => use level-flight polar with load factor)
    P = np.array([p_level(float(v), float(abs(p)), float(d)) for v, p, d in zip(V, phi, dcd)])
    tt = t[m]
    E = float(np.trapezoid(P, tt) / 3600.0)
    return E, float(tt[-1] - tt[0])
