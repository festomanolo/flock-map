"""X8-class flying-wing planform shared by the CFD campaign (OpenFOAM) and the planform vortex-lattice model.
Body axes: x forward, y starboard (half-model uses y >= 0), z up.  Planform: linear chord taper, constant LE sweep,
symmetric NACA-0009-type section (no camber, no twist, no winglets, no pod) -- a deliberately simple, clean geometry."""
from __future__ import annotations
import numpy as np

B = 2.12; HALF = B / 2
C_ROOT, C_TIP = 0.52, 0.25
SWEEP_LE = np.radians(22.0)             # leading-edge sweep
T_REL = 0.09                            # thickness ratio of the section
XI_TE = 0.985                           # blunt trailing edge position (fraction of chord)


def chord(y):
    s = np.abs(np.asarray(y, float)) / HALF
    return C_ROOT + (C_TIP - C_ROOT) * s


def x_le(y):                            # leading-edge x (body, forward positive), root LE at x = 0
    return -np.abs(np.asarray(y, float)) * np.tan(SWEEP_LE)


def area():
    yy = np.linspace(-HALF, HALF, 2001); return float(np.trapezoid(chord(yy), yy))


def mac():
    yy = np.linspace(-HALF, HALF, 2001); c = chord(yy); return float(np.trapezoid(c ** 2, yy) / np.trapezoid(c, yy))


def quarter_chord_x(y):                 # body-axis x of the local quarter chord
    return x_le(y) - 0.25 * chord(y)


def thickness(xi, t=T_REL):
    return 5 * t * (0.2969 * np.sqrt(xi) - 0.1260 * xi - 0.3516 * xi ** 2 + 0.2843 * xi ** 3 - 0.1015 * xi ** 4)


def wing_triangles(n_span=60, n_chord=60, half=False, alpha_deg=0.0, pivot=None, y_min=None):
    """Watertight triangulated wing; if half=True only y>=0 (symmetry-plane model, root face on y=0 left open on purpose).
    The surface is rotated by alpha about the y axis through `pivot` (default: root quarter chord): positive alpha = nose up."""
    ys = np.linspace((0.0 if y_min is None else y_min) if half else -HALF, HALF, n_span + 1)
    xi = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n_chord)))
    xi = xi * XI_TE
    rings = []
    for y in ys:
        c = chord(y); xl = float(x_le(y)); th = thickness(xi / XI_TE * XI_TE) * c
        up = np.stack([xl - xi * c, np.full_like(xi, y), th], 1)
        lo = np.stack([xl - xi[::-1] * c, np.full_like(xi, y), -th[::-1]], 1)
        rings.append(np.vstack([up, lo[1:]]))              # closed loop LE -> TE (upper) -> TE -> LE (lower), blunt TE joins
    P = np.array(rings)                                    # (ns+1, m, 3), m = 2*n_chord-1
    ns1, m, _ = P.shape
    if pivot is None: pivot = np.array([float(quarter_chord_x(0.0)), 0.0, 0.0])
    a = np.radians(alpha_deg); R = np.array([[np.cos(a), 0, -np.sin(a)], [0, 1, 0], [np.sin(a), 0, np.cos(a)]])   # nose-up rotation about y
    P = (P - pivot) @ R.T + pivot
    tris = []
    idx = lambda i, j: P[i, j % (m)]
    for i in range(ns1 - 1):
        for j in range(m):
            a_, b_, c_, d_ = idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)
            tris += [(a_, b_, c_), (a_, c_, d_)]
    # blunt TE: loop is closed (j = m-1 -> j = 0 would wrap LE); close the TE seam explicitly between upper/lower TE points
    # (upper TE point index n_chord-1 and lower TE point index n_chord) are adjacent in the loop already; the LE wrap is closed by j % m.
    def cap(i, flip):
        ring = P[i]; ctr = ring.mean(0)
        for j in range(m):
            p, q = ring[j], ring[(j + 1) % m]
            tris.append((ctr, q, p) if flip else (ctr, p, q))
    cap(ns1 - 1, flip=False)
    if (not half) or (y_min is not None and y_min < 0): cap(0, flip=True)
    return np.array(tris)


def write_stl(path, tris, name="wing"):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]); nn = np.linalg.norm(n, axis=1, keepdims=True); n = n / np.maximum(nn, 1e-30)
    with open(path, "w") as f:
        f.write(f"solid {name}\n")
        for t, nv in zip(tris, n):
            f.write(f" facet normal {nv[0]:.6e} {nv[1]:.6e} {nv[2]:.6e}\n  outer loop\n")
            for v in t: f.write(f"   vertex {v[0]:.7e} {v[1]:.7e} {v[2]:.7e}\n")
            f.write("  endloop\n endfacet\n")
        f.write(f"endsolid {name}\n")
