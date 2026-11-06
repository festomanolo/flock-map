"""Independent cross-check: planar horseshoe vortex-lattice (Weissinger-type) model.

A single chordwise horseshoe per spanwise panel; bound vortex at c/4, control point at 3c/4.
The follower is solved in the leader's wake velocity field (three wake representations):
  "sheet"   : the leader's own trailing-vortex sheet from its VLM solution (no roll-up),
  "rolled"  : leader's circulation concentrated into a Lamb-Oseen pair with VLM-derived (Gamma0, b0),
  "analytic": manuscript's Lamb-Oseen pair with elliptical (Gamma0, b0=pi/4 b).
Rectangular planform of equal span and area: swept/tapered X8 geometry is NOT represented (limitation).
Coordinates: x downstream (flow direction), y starboard, z up.  w is positive up.
"""
from __future__ import annotations
import numpy as np
from .config import AC, WK, Aircraft
from . import aero

LEG = 5000.0   # m, finite stand-in for semi-infinite trailing legs


def _seg(P, A, B, core):
    """Velocity at points P (n,3) due to unit-circulation segment A->B (3,)."""
    r1 = P - A; r2 = P - B; r0 = B - A
    c = np.cross(r1, r2)
    c2 = np.sum(c * c, axis=1) + core ** 2 * np.dot(r0, r0)
    n1 = np.linalg.norm(r1, axis=1); n2 = np.linalg.norm(r2, axis=1)
    f = (r1 @ r0) / np.maximum(n1, 1e-12) - (r2 @ r0) / np.maximum(n2, 1e-12)
    return (f / (4 * np.pi * c2))[:, None] * c


def _horseshoe(P, y0, y1, xb, core):
    A = np.array([xb, y0, 0.0]); B = np.array([xb, y1, 0.0])
    Af = A + np.array([LEG, 0, 0]); Bf = B + np.array([LEG, 0, 0])
    return _seg(P, Af, A, core) + _seg(P, A, B, core) + _seg(P, B, Bf, core)


class Wing:
    def __init__(self, ac: Aircraft = AC, n: int = 60, x0: float = 0.0, y0: float = 0.0, z0: float = 0.0):
        self.ac, self.n = ac, n
        self.edges = np.linspace(-ac.b / 2, ac.b / 2, n + 1)   # uniform panels (cosine spacing was tested; see tests)
        self.ym = 0.5 * (self.edges[:-1] + self.edges[1:])
        self.dy = np.diff(self.edges)
        self.xb = x0 + 0.25 * ac.chord
        self.xc = x0 + 0.75 * ac.chord
        self.core = 1e-4 * ac.b   # tiny regularisation only; 0.02 b biases e_oswald by +18 % (see tests)
        self.y0, self.z0 = y0, z0
        self.cp = np.stack([np.full(n, self.xc), self.ym + 0, np.zeros(n)], 1)
        self.bd = np.stack([np.full(n, self.xb), self.ym, np.zeros(n)], 1)   # bound-segment midpoints
        self.A = np.zeros((n, n)); self.Ab = np.zeros((n, n))
        for j in range(n):
            self.A[:, j] = _horseshoe(self.cp, self.edges[j], self.edges[j + 1], self.xb, self.core)[:, 2]
            v = _horseshoe(self.bd, self.edges[j], self.edges[j + 1], self.xb, self.core)[:, 2]
            self.Ab[:, j] = v
        # remove singular self-contribution of the bound segment at its own midpoint (collinear -> 0)
        self.Ainv = np.linalg.inv(self.A)

    # ------------------------------------------------------------------
    def solve(self, va, w_ext_cp, w_ext_bd, lift_req):
        """Return alpha, Gamma, forces for a prescribed external vertical velocity (up +)."""
        rho = self.ac.rho
        g1 = -self.Ainv @ (va * np.ones(self.n))          # per unit alpha
        ge = -self.Ainv @ w_ext_cp
        l1 = rho * va * np.sum(g1 * self.dy)
        le = rho * va * np.sum(ge * self.dy)
        alpha = (lift_req - le) / l1
        gam = g1 * alpha + ge
        lift = rho * va * np.sum(gam * self.dy)
        w_self = self.Ab @ gam
        w_tot = w_self + w_ext_bd
        drag_i = -rho * np.sum(gam * self.dy * w_tot)       # near-field induced drag
        roll = rho * va * np.sum(gam * self.dy * self.ym)   # rolling moment about x axis
        return dict(alpha=alpha, gamma=gam, lift=lift, drag_i=drag_i, roll=roll, w_self=w_self)

    def isolated(self, va, lift_req):
        z = np.zeros(self.n)
        return self.solve(va, z, z, lift_req)


_cache: dict = {}


def _wing(ac, n=60):
    key = (id(ac), n)
    if key not in _cache:
        _cache[key] = Wing(ac, n)
    return _cache[key]


def leader_wake_params(va, ac: Aircraft = AC, n=60):
    """Gamma0 and b0 of an equivalent vortex pair from the leader's VLM solution."""
    W = _wing(ac, n)
    lift = ac.mass * 9.80665
    s = W.isolated(va, lift)
    gam = s["gamma"]
    # circulation shed at node k: dGamma between panels; first moment gives centroid of vorticity
    g_ext = np.concatenate([[0], gam, [0]])
    dG = -np.diff(g_ext)                    # shed strength at each node (positive on one side)
    nodes = W.edges
    half = nodes > 0
    gamma0 = np.sum(dG[half])               # total circulation shed from the starboard half
    y_c = np.sum(dG[half] * nodes[half]) / gamma0
    return dict(gamma0=float(abs(gamma0)), b0=float(2 * y_c), induced_drag=float(s['drag_i']), gam=gam, nodes=nodes)


def leader_sheet_field(P, va, ac: Aircraft, dx: float, n=60, dy_lead=0.0, dz_lead=0.0):
    """Velocity induced at points P (follower frame, x measured from the follower quarter-chord origin)
    by the leader's complete horseshoe system (bound + trailing legs) located dx upstream."""
    W = _wing(ac, n)
    lift = ac.mass * 9.80665
    s = W.isolated(va, lift)
    gam = s["gamma"]
    vel = np.zeros_like(P)
    # leader at x = -dx (its bound vortex), displaced (dy_lead, dz_lead) -> shift points instead
    Q = P - np.array([-dx, dy_lead, dz_lead]) - np.array([0.0, 0.0, 0.0])
    for j in range(W.n):
        vel += gam[j] * _horseshoe(Q, W.edges[j], W.edges[j + 1], W.xb, W.core)
    return vel


_FW = {}


def _freewake():
    if "fw" not in _FW:
        import os
        from .freewake import FreeWake
        path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed", "freewake_fine.npz")
        _FW["fw"] = FreeWake.load(path)
    return _FW["fw"]


def follower(dx_b, dy_b, dz_b=0.0, va=18.0, *, wake="sheet", ac: Aircraft = AC, wk: Wake = WK, n=60,
             y_err=0.0, gamma_scale=1.0, nu=None, rc0_frac=None) -> dict:
    """VLM follower response.  dy_b is the lateral offset of the follower centre from the LEADER centre (wingspans)."""
    iso = aero.isolated(va, 0.0, ac)
    W = _wing(ac, n)
    lift = ac.mass * 9.80665
    base = W.isolated(va, lift)
    dx = dx_b * ac.b
    dy = dy_b * ac.b + y_err
    dz = dz_b * ac.b
    # follower points in leader-centred frame: lateral shift by dy
    def pts(P):
        P2 = P.copy(); P2[:, 1] += dy; P2[:, 2] += dz; return P2
    if wake == "free":
        fw = _freewake()
        off = np.array([dx, dy, dz])
        sc = gamma_scale * fw.va / va            # field scales with 1/V at fixed lift (Gamma ~ L/(rho V b)); wake age effect neglected
        wcp = fw.velocity(W.cp + off)[:, 2] * sc
        wbd = fw.velocity(W.bd + off)[:, 2] * sc
    elif wake == "sheet":
        # evaluate in leader frame: leader bound vortex at x=W.xb, follower pts at x + dx
        def field(P):
            Q = P.copy(); Q[:, 0] += dx; Q[:, 1] += dy; Q[:, 2] += dz
            v = np.zeros_like(Q)
            s = W.isolated(va, lift)
            for j in range(W.n):
                v += gamma_scale * s["gamma"][j] * _horseshoe(Q, W.edges[j], W.edges[j + 1], W.xb, W.core)
            return v[:, 2]
        wcp, wbd = field(W.cp), field(W.bd)
    else:
        if wake == "analytic":
            g0 = gamma_scale * aero.gamma0_elliptic(va, iso["cl"], ac); b0 = ac.b0
        elif wake == "rolled":
            p = leader_wake_params(va, ac, n); g0 = gamma_scale * p["gamma0"]; b0 = p["b0"]
        else:
            raise ValueError(wake)
        rc = aero.core_radius(dx, va, wk, ac, nu, rc0_frac)
        wcp, _ = aero.lamb_oseen_pair(W.cp[:, 1] + dy, dz, g0, b0, rc)
        wbd, _ = aero.lamb_oseen_pair(W.bd[:, 1] + dy, dz, g0, b0, rc)
    s = W.solve(va, wcp, wbd, lift)
    q = 0.5 * ac.rho * va ** 2
    d_drag = s["drag_i"] - base["drag_i"]
    cl_roll = s["roll"] / (q * ac.S * ac.b)
    dcdi_raw = -d_drag / (q * ac.S)
    out = aero._finish(iso, va, dy_b, dy, float(np.mean(wcp)), dcdi_raw, cl_roll, ac)
    out["drag_i_vlm_iso_N"] = base["drag_i"]
    out["alpha_deg_vlm"] = float(np.degrees(s["alpha"]))
    out["_ym"], out["_gam"], out["_gam_iso"], out["_w_cp"] = W.ym.copy(), s["gamma"].copy(), base["gamma"].copy(), np.asarray(wcp).copy()
    return out


# =====================================================================================================================
# Planform vortex lattice for the swept/tapered X8-class geometry used in the CFD campaign (cfdgeom.py)
# =====================================================================================================================
def _horseshoe_pts(P, A, B, core):
    Af = A + np.array([LEG, 0, 0]); Bf = B + np.array([LEG, 0, 0])
    return _seg(P, Af, A, core) + _seg(P, A, B, core) + _seg(P, B, Bf, core)


class PlanformWing(Wing):
    """One chordwise panel per span station; bound vortex on the local quarter-chord line (swept), control points at 3/4 chord."""
    def __init__(self, n=60, ac: Aircraft = AC, alpha_ref=None):
        from . import cfdgeom as G
        self.ac, self.n, self.G = ac, n, G
        self.edges = np.linspace(-G.HALF, G.HALF, n + 1)
        self.ym = 0.5 * (self.edges[:-1] + self.edges[1:]); self.dy = np.diff(self.edges)
        xle = lambda y: -G.x_le(y)                         # downstream-positive leading edge
        c = G.chord
        self.xbn = xle(self.edges) + 0.25 * c(self.edges)  # bound-vortex x at nodes
        self.xcp = xle(self.ym) + 0.75 * c(self.ym)
        self.core = 1e-4 * G.B
        self.S = G.area(); self.mac = G.mac(); self.AR = G.B ** 2 / self.S
        self.cp = np.stack([self.xcp, self.ym, np.zeros(n)], 1)
        xbm = 0.5 * (self.xbn[:-1] + self.xbn[1:])
        self.bd = np.stack([xbm, self.ym, np.zeros(n)], 1)
        self.nodesA = np.stack([self.xbn[:-1], self.edges[:-1], np.zeros(n)], 1); self.nodesB = np.stack([self.xbn[1:], self.edges[1:], np.zeros(n)], 1)
        self.A = np.zeros((n, n)); self.Ab = np.zeros((n, n))
        for j in range(n):
            self.A[:, j] = _horseshoe_pts(self.cp, self.nodesA[j], self.nodesB[j], self.core)[:, 2]
            self.Ab[:, j] = _horseshoe_pts(self.bd, self.nodesA[j], self.nodesB[j], self.core)[:, 2]
        self.Ainv = np.linalg.inv(self.A)

    def isolated_alpha(self, va, alpha_deg, rho=1.225):
        al = np.radians(alpha_deg)
        gam = -self.Ainv @ (va * al * np.ones(self.n))
        lift = rho * va * np.sum(gam * self.dy)
        w_self = self.Ab @ gam
        drag_i = -rho * np.sum(gam * self.dy * w_self)
        # Far-field Trefftz-plane induced drag (Munk stagger-invariant, free of single-panel swept bound-vortex bias)
        w_tp = np.zeros(self.n)
        for j in range(self.n):
            w_tp += gam[j] / (2.0 * np.pi) * (1.0 / (self.ym - self.edges[j + 1]) - 1.0 / (self.ym - self.edges[j]))
        drag_i_tp = -0.5 * rho * np.sum(gam * self.dy * w_tp)
        q = 0.5 * rho * va ** 2
        return dict(CL=lift / (q * self.S), CDi=drag_i / (q * self.S), CDi_trefftz=drag_i_tp / (q * self.S), gamma=gam)

    def sheet_field(self, gam, pts):
        v = np.zeros_like(pts)
        for j in range(self.n):
            v += gam[j] * _horseshoe_pts(pts, self.nodesA[j], self.nodesB[j], self.core)
        return v

    def follower_alpha(self, dx, dy, va, alpha_deg, dz=0.0, rho=1.225):
        """Follower with the same planform at fixed geometric angle of attack in the leader's planar trailing-vortex sheet
        (both wings at the same alpha).  Offsets are quarter-chord to quarter-chord at the root."""
        al = np.radians(alpha_deg)
        gl = -self.Ainv @ (va * al * np.ones(self.n))                    # leader circulation at this alpha
        off = np.array([dx, dy, dz])
        wcp = self.sheet_field(gl, self.cp + off)[:, 2]; wbd = self.sheet_field(gl, self.bd + off)[:, 2]
        # the leader's field must be evaluated in the leader frame: follower points are at +off relative to the leader
        gam = -self.Ainv @ (va * al * np.ones(self.n) + wcp)
        lift = rho * va * np.sum(gam * self.dy)
        w_tot = self.Ab @ gam + wbd
        drag_i = -rho * np.sum(gam * self.dy * w_tot)
        roll = rho * va * np.sum(gam * self.dy * self.ym)
        q = 0.5 * rho * va ** 2
        return dict(CL=lift / (q * self.S), CDi=drag_i / (q * self.S), Cl_roll=roll / (q * self.S * self.G.B), gamma=gam)

    def coupled_symmetry_alpha(self, dx, dy, va, alpha_deg, dz=0.0, rho=1.225, two_way_leader=True):
        """Symmetric 3-aircraft V-formation matching the OpenFOAM y=0 symmetry half-model:
        leader at (0,0,0), starboard follower at (+dx,+dy,dz), port mirror follower at (+dx,-dy,dz)
        with mirrored spanwise circulation gamma_port(y_j) = gamma_stbd(-y_j) = gamma_stbd[n-1-j]."""
        al = np.radians(alpha_deg)
        n = self.n
        off_s = np.array([dx, dy, dz])
        off_p = np.array([dx, -dy, dz])
        # Influence of port follower panel k (whose circulation equals starboard panel n-1-k) on starboard cp / bd:
        # Relative position of starboard point (cp + off_s) in port follower's frame (origin off_p) is cp + (0, 2*dy, 0).
        A_mir_cp = np.zeros((n, n))
        A_mir_bd = np.zeros((n, n))
        cp_from_port = self.cp + (off_s - off_p)
        bd_from_port = self.bd + (off_s - off_p)
        for k in range(n):
            col = n - 1 - k
            A_mir_cp[:, col] += _horseshoe_pts(cp_from_port, self.nodesA[k], self.nodesB[k], self.core)[:, 2]
            A_mir_bd[:, col] += _horseshoe_pts(bd_from_port, self.nodesA[k], self.nodesB[k], self.core)[:, 2]
        A_LS_cp = np.zeros((n, n))
        A_LS_bd = np.zeros((n, n))
        for j in range(n):
            A_LS_cp[:, j] = _horseshoe_pts(self.cp + off_s, self.nodesA[j], self.nodesB[j], self.core)[:, 2]
            A_LS_bd[:, j] = _horseshoe_pts(self.bd + off_s, self.nodesA[j], self.nodesB[j], self.core)[:, 2]

_PW = {}


def planform_wing(n=60):
    if n not in _PW: _PW[n] = PlanformWing(n)
    return _PW[n]
