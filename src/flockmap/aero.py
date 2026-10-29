"""Isolated-aircraft model, analytic Lamb-Oseen wake and the manuscript's strip-theory follower model.

Two variants of the strip model are provided:
  variant="published"  reproduces the manuscript's equations/code exactly (including the roll-moment
                       normalisation 1/(b S) and the 2*pi lift slope), for audit purposes;
  variant="corrected"  uses the dimensionally consistent roll-moment coefficient
                       C_l = (a/b^2) * integral( dalpha(y) * y dy ) with the finite-wing lift slope a.
"""
from __future__ import annotations
import numpy as np
from .config import AC, WK, G, Aircraft, Wake


# ----------------------------------------------------------------------------- isolated flight
def isolated(va: float, bank_deg: float = 0.0, ac: Aircraft = AC) -> dict:
    n = 1.0 / np.cos(np.radians(bank_deg))
    q = 0.5 * ac.rho * va ** 2
    cl = ac.mass * G * n / (q * ac.S)
    cdi = ac.k0 * cl ** 2
    cd = ac.cd0 + cdi
    drag = q * ac.S * cd
    p_aero = drag * va
    return dict(va=va, cl=cl, cdi=cdi, cd=cd, drag=drag, p_aero=p_aero,
                p_elec=p_aero / ac.eta_prop + ac.p_hotel, q=q)


def p_elec_from_cd(va: float, cd: float, ac: Aircraft = AC) -> float:
    q = 0.5 * ac.rho * va ** 2
    return q * ac.S * cd * va / ac.eta_prop + ac.p_hotel


# ----------------------------------------------------------------------------- wake field
def core_radius(dx_m: float, va: float, wk: Wake = WK, ac: Aircraft = AC, nu: float | None = None,
                rc0_frac: float | None = None) -> float:
    nu = wk.nu_eff if nu is None else nu
    rc0 = (wk.rc0_frac if rc0_frac is None else rc0_frac) * ac.b
    return float(np.sqrt(rc0 ** 2 + 4.0 * nu * dx_m / va))


def lamb_oseen_pair(y, z, gamma0, b0, rc, eps=1e-6):
    """Vertical (w, +up) and lateral (v) induced velocity of a counter-rotating Lamb-Oseen pair.
    Right vortex (y=+b0/2) counter-clockwise looking downstream => upwash outboard.  Matches manuscript sign."""
    y = np.asarray(y, float); z = np.asarray(z, float)
    rr2 = (y - 0.5 * b0) ** 2 + z ** 2
    rl2 = (y + 0.5 * b0) ** 2 + z ** 2
    fr = 1.0 - np.exp(-rr2 / rc ** 2)
    fl = 1.0 - np.exp(-rl2 / rc ** 2)
    k = gamma0 / (2 * np.pi)
    w = k * ((y - 0.5 * b0) / (rr2 + eps) * fr - (y + 0.5 * b0) / (rl2 + eps) * fl)
    v = k * (-z / (rr2 + eps) * fr + z / (rl2 + eps) * fl)
    return w, v


def gamma0_elliptic(va: float, cl: float, ac: Aircraft = AC) -> float:
    """Root circulation of an elliptically loaded wing: L = rho V Gamma0 (pi/4) b  =>  Gamma0 = 2 V S CL / (pi b)."""
    return 2.0 * va * ac.S * cl / (np.pi * ac.b)


def gamma0_published(va: float, cl: float, ac: Aircraft = AC) -> float:
    """Manuscript Eq. (3.1): 4 V S CL/(pi b).  This is twice L/(rho V b0) because the 1/2 in L = q S CL was dropped."""
    return 4.0 * va * ac.S * cl / (np.pi * ac.b)


# ----------------------------------------------------------------------------- strip-theory follower
def strip_follower(dx_b: float, dy_b: float, dz_b: float = 0.0, va: float = 18.0, *, variant="corrected",
                   ac: Aircraft = AC, wk: Wake = WK, nu: float | None = None, rc0_frac: float | None = None,
                   gamma_scale: float = 1.0, n_strip: int = 51, y_err: float = 0.0, ) -> dict:
    """dx_b, dy_b, dz_b in wingspans.  y_err [m] is an additive lateral station-keeping error."""
    iso = isolated(va, 0.0, ac)
    b, S = ac.b, ac.S
    g0 = gamma_scale * (gamma0_published if variant == "published" else gamma0_elliptic)(va, iso["cl"], ac)
    rc = core_radius(dx_b * b, va, wk, ac, nu, rc0_frac)
    dy = dy_b * b + y_err
    ypts = np.linspace(dy - 0.5 * b, dy + 0.5 * b, n_strip)
    w, _ = lamb_oseen_pair(ypts, dz_b * b, g0, ac.b0, rc)
    wbar = float(np.mean(w))
    dcdi_raw = iso["cl"] * wbar / va
    arm = ypts - dy
    if variant == "published":
        cl_roll = float(np.trapezoid(2 * np.pi * (w / va) * arm, ypts) / (b * S))
    elif variant == "corrected":
        cl_roll = float(ac.cl_alpha_3d / b ** 2 * np.trapezoid((w / va) * arm, ypts))
    else:
        raise ValueError(variant)
    return _finish(iso, va, dy_b, dy, wbar, dcdi_raw, cl_roll, ac)


def _finish(iso, va, dy_b, dy, wbar, dcdi_raw, cl_roll, ac):
    d_a = -cl_roll / ac.cl_da
    cd_trim = ac.k_trim * d_a ** 2
    dcd_net = dcdi_raw - cd_trim
    cd_f = iso["cd"] - dcd_net
    pf = p_elec_from_cd(va, cd_f, ac)
    return dict(dy_b=dy_b, dy_m=dy, w_mean=wbar, dcdi_raw=dcdi_raw, cl_roll=cl_roll,
                elevon_deg=float(np.degrees(d_a)), cd_trim=cd_trim, dcd_net=dcd_net,
                pct_drag=100 * dcd_net / iso["cd"], p_iso=iso["p_elec"], p_foll=pf,
                pct_power=100 * (iso["p_elec"] - pf) / iso["p_elec"])
