"""Unsteady free-wake vortex-lattice solver (vortex rings, wake roll-up, viscous core growth).

Frame: aircraft-fixed, freestream V along +x (downstream), y starboard, z up.  The leader wing is one row of vortex
rings (front segment at c/4, ring closed at the first free wake row); the wake is a lattice of nodes advected with the
local velocity (freestream + induced by every vortex element), i.e. the wake ROLLS UP by itself.  Ring circulation is
constant after shedding (Kelvin).  Core radius grows as r_c^2 = r_c0^2 + 4 nu t.
This replaces the assumed Lamb-Oseen pair / planar sheet used elsewhere; it is still an inviscid-core model (no
turbulence, no ambient atmosphere) and is NOT a substitute for CFD validation.
"""
from __future__ import annotations
import numpy as np
from .config import AC, WK, G, Aircraft, Wake


def seg_velocity(P, A, B, gam, core, chunk=300):
    """Velocity at points P (n,3) from straight filaments A->B (m,3) with circulation gam (m,) and core radius core (m,)."""
    out = np.zeros_like(P)
    if len(gam) == 0:
        return out
    r0 = B - A; l0 = np.einsum("ij,ij->i", r0, r0)
    for s in range(0, len(P), chunk):
        Q = P[s:s + chunk][:, None, :]
        r1 = Q - A[None]; r2 = Q - B[None]
        c = np.cross(r1, r2)
        c2 = np.einsum("nmk,nmk->nm", c, c) + (core ** 2 * l0)[None]
        n1 = np.linalg.norm(r1, axis=2); n2 = np.linalg.norm(r2, axis=2)
        f = np.einsum("nmk,mk->nm", r1, r0) / np.maximum(n1, 1e-12) - np.einsum("nmk,mk->nm", r2, r0) / np.maximum(n2, 1e-12)
        k = gam[None] * f / (4 * np.pi * c2)
        out[s:s + chunk] = np.einsum("nm,nmk->nk", k, c)
    return out


class FreeWake:
    def __init__(self, ac: Aircraft = AC, wk: Wake = WK, n_span=24, va=18.0, dt=0.015, n_rows=120, rc0_frac=0.05):
        self.ac, self.wk, self.n, self.va, self.dt, self.K = ac, wk, n_span, va, dt, n_rows
        b, c = ac.b, ac.chord
        self.y = np.linspace(-b / 2, b / 2, n_span + 1)
        self.dy = np.diff(self.y); self.ym = 0.5 * (self.y[:-1] + self.y[1:])
        self.xb, self.xc, self.xte = 0.25 * c, 0.75 * c, c
        self.rc0 = rc0_frac * b
        self.L = ac.mass * G; self.rho = ac.rho
        z = np.zeros(n_span + 1)
        self.te = np.stack([np.full(n_span + 1, self.xte), self.y, z], 1)
        self.front = np.stack([np.full(n_span + 1, self.xb), self.y, z], 1)
        self.row1 = self.te + np.array([va * dt, 0.0, 0.0])
        self.cp = np.stack([np.full(n_span, self.xc), self.ym, np.zeros(n_span)], 1)
        self.rows = self.row1[None].copy()               # free node rows R_1.. (rows[0] = youngest)
        self.G_rows = np.zeros((0, n_span))              # circulation of rings between rows[i] and rows[i+1]
        self.gamma = np.zeros(n_span)
        self.t = 0.0
        self.core_u = self.rc0 * 0.2
        self._build_A()
        g1 = np.linalg.solve(self.A, -(va) * np.ones(n_span))
        self.alpha = self.L / (self.rho * va * np.sum(g1 * self.dy))     # angle of attack giving L = W in isolation

    def _ring_segments(self, j):
        a = self.front[j]; b = self.front[j + 1]; c = self.row1[j + 1]; d = self.row1[j]
        return [(a, b), (b, c), (c, d), (d, a)]

    def _unknown_filaments(self, gam):
        A, B, g = [], [], []
        for j in range(self.n):
            for (p, q) in self._ring_segments(j):
                A.append(p); B.append(q); g.append(gam[j])
        return np.array(A), np.array(B), np.array(g)

    def _build_A(self):
        n = self.n; A = np.zeros((n, n))
        for j in range(n):
            segs = self._ring_segments(j)
            v = seg_velocity(self.cp, np.array([s[0] for s in segs]), np.array([s[1] for s in segs]), np.ones(4), np.full(4, self.core_u))
            A[:, j] = v[:, 2]
        self.A = A

    def _wake_filaments(self):
        R = len(self.G_rows)
        if R == 0:
            return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0), np.zeros(0)
        nodes, Gr, n = self.rows, self.G_rows, self.n
        Gp = np.concatenate([np.zeros((R, 1)), Gr, np.zeros((R, 1))], 1)
        S = Gp[:, :-1] - Gp[:, 1:]
        A = [nodes[:-1].reshape(-1, 3)]; B = [nodes[1:].reshape(-1, 3)]; g = [S.reshape(-1)]
        age = [np.repeat((np.arange(R) + 1.0)[:, None], n + 1, 1).reshape(-1)]
        Gb = np.concatenate([Gr, np.zeros((1, n))], 0); Ga = np.concatenate([np.zeros((1, n)), Gr], 0)
        T = Gb - Ga
        A.append(nodes[:, :-1].reshape(-1, 3)); B.append(nodes[:, 1:].reshape(-1, 3)); g.append(T.reshape(-1))
        age.append(np.repeat((np.arange(R + 1) + 1.0)[:, None], n, 1).reshape(-1))
        A = np.concatenate(A); B = np.concatenate(B); g = np.concatenate(g); age = np.concatenate(age)
        core = np.sqrt(self.rc0 ** 2 + 4 * self.wk.nu_eff * age * self.dt)
        keep = np.abs(g) > 1e-9
        return A[keep], B[keep], g[keep], core[keep]

    def velocity(self, P, include_unknown=True):
        A, B, g, core = self._wake_filaments()
        v = seg_velocity(P, A, B, g, core)
        if include_unknown:
            Au, Bu, gu = self._unknown_filaments(self.gamma)
            v = v + seg_velocity(P, Au, Bu, gu, np.full(len(gu), self.core_u))
        return v

    def step(self):
        va, dt, n = self.va, self.dt, self.n
        A, B, g, core = self._wake_filaments()
        wk = seg_velocity(self.cp, A, B, g, core)[:, 2]
        self.gamma = np.linalg.solve(self.A, -(va * self.alpha * np.ones(n) + wk))
        shp = self.rows.shape
        v = self.velocity(self.rows.reshape(-1, 3)); v[:, 0] += va
        moved = (self.rows.reshape(-1, 3) + v * dt).reshape(shp)
        self.rows = np.concatenate([self.row1[None], moved], 0)
        self.G_rows = np.concatenate([self.gamma[None], self.G_rows], 0)
        if len(self.rows) > self.K + 1:
            self.rows = self.rows[:self.K + 1]; self.G_rows = self.G_rows[:self.K]
        self.alpha *= 1.0 + 0.5 * (self.L / self.lift() - 1.0)      # trim to L = W as the wake builds up
        self.t += dt

    def run(self, n_steps=None, verbose=False):
        n_steps = n_steps or self.K + 20
        for i in range(n_steps):
            self.step()
            if verbose and i % 20 == 0:
                print(i, len(self.rows), round(self.lift() / self.L, 4), flush=True)
        return self

    def lift(self):
        return self.rho * self.va * float(np.sum(self.gamma * self.dy))

    # ----- persistence and diagnostics ----------------------------------------------------------------------
    def save(self, path, **meta):
        np.savez_compressed(path, rows=self.rows, G=self.G_rows, gamma=self.gamma, alpha=self.alpha, n=self.n, va=self.va,
                            dt=self.dt, t=self.t, **meta)

    @classmethod
    def load(cls, path, ac: Aircraft = AC, wk: Wake = WK):
        z = np.load(path)
        fw = cls(ac, wk, n_span=int(z["n"]), va=float(z["va"]), dt=float(z["dt"]), n_rows=len(z["G"]))
        fw.rows, fw.G_rows, fw.gamma, fw.alpha, fw.t = z["rows"], z["G"], z["gamma"], float(z["alpha"]), float(z["t"])
        return fw

    def vortex_track(self):
        """Centroid (y,z) of trailing vorticity of the starboard half per node row, and x of the row."""
        R = len(self.G_rows)
        Gp = np.concatenate([np.zeros((R, 1)), self.G_rows, np.zeros((R, 1))], 1)
        S = Gp[:, :-1] - Gp[:, 1:]                        # trailing strength at node j (per ring row)
        half = np.arange(self.n + 1) > self.n / 2
        out = []
        for i in range(R):
            P = 0.5 * (self.rows[i] + self.rows[i + 1])
            w = S[i] * half
            if abs(w.sum()) < 1e-12: continue
            out.append((P[:, 0].mean(), (w * P[:, 1]).sum() / w.sum(), (w * P[:, 2]).sum() / w.sum(), w.sum()))
        return np.array(out)
