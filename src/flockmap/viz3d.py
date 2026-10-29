"""3-D geometry helpers (PyVista): a Skywalker-X8-class flying-wing mesh with airfoil thickness, winglets, centre pod and
pusher-prop disc; scene helpers.  The mesh is an approximate model built from the span/area used in the study
(b = 2.12 m, S ~ 0.81 m^2, 23 deg LE sweep); it is NOT a CAD copy of the commercial airframe."""
from __future__ import annotations
import numpy as np
import pyvista as pv

# planform: LE x(y), TE x(y) in body frame (nose +x)
ROOT_LE, ROOT_TE, TIP_LE, TIP_TE, HALF = 0.20, -0.32, -0.25, -0.50, 1.06


def _naca(xi, t=0.09):
    return 5 * t * (0.2969 * np.sqrt(xi) - 0.1260 * xi - 0.3516 * xi ** 2 + 0.2843 * xi ** 3 - 0.1036 * xi ** 4)


def wing_surface(n_span=41, n_chord=24, with_winglets=True):
    s = np.linspace(-1, 1, n_span)
    xi = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n_chord)))          # LE->TE clustered
    le = ROOT_LE + (TIP_LE - ROOT_LE) * np.abs(s); te = ROOT_TE + (TIP_TE - ROOT_TE) * np.abs(s)
    ch = le - te
    t_loc = 0.115 - 0.03 * np.abs(s)                                  # thicker at root
    pts = []
    for i, sv in enumerate(s):
        x = le[i] - xi * ch[i]; th = _naca(xi, 1.0) * t_loc[i] / 0.09 * 0.09 * ch[i] / 0.5 * 0.5
        camber = 0.012 * ch[i] * np.sin(np.pi * xi) * 0.0
        up = np.stack([x, np.full_like(x, sv * HALF), th], 1)
        lo = np.stack([x[::-1], np.full_like(x, sv * HALF), -th[::-1]], 1)
        pts.append(np.vstack([up, lo[1:]]))
    pts = np.array(pts)                                              # (n_span, 2*n_chord-1, 3)
    # twist (washout) small
    grid = pv.StructuredGrid(pts[:, :, 0].T, pts[:, :, 1].T, pts[:, :, 2].T)
    surf = grid.extract_surface().clean()
    return surf


def winglet(sign):
    y = sign * HALF
    h = 0.15
    x0, x1 = TIP_LE - 0.02, TIP_TE
    pts = np.array([[x0, y, 0.0], [x1, y, 0.0], [x1 - 0.06, y, h], [x0 - 0.10, y, h]])
    th = 0.006
    quad = np.vstack([pts + [0, -th, 0], pts + [0, th, 0]])
    faces = [[4, 0, 1, 2, 3], [4, 4, 5, 6, 7], [4, 0, 1, 5, 4], [4, 1, 2, 6, 5], [4, 2, 3, 7, 6], [4, 3, 0, 4, 7]]
    return pv.PolyData(quad, np.hstack(faces))


def pod():
    e = pv.ParametricEllipsoid(0.34, 0.075, 0.085, u_res=32, v_res=32, w_res=32)
    e.translate([-0.10, 0, 0.012], inplace=True)
    return e


def prop_disc(r=0.14):
    d = pv.Disc(center=(-0.57, 0, 0.0), inner=0.0, outer=r, normal=(1, 0, 0), r_res=1, c_res=48)
    return d


def x8(pos=(0, 0, 0), heading_deg=0.0, bank_deg=0.0, pitch_deg=0.0, scale=1.0, body_color="#f2f2f0", accent="#2a78d6"):
    """Return dict of meshes (body, winglets, prop) posed in world coordinates (x fwd, y starboard, z up)."""
    parts = {"wing": wing_surface(), "pod": pod(), "wl_r": winglet(1), "wl_l": winglet(-1), "prop": prop_disc()}
    out = {}
    for k, m in parts.items():
        m = m.copy()
        m.points = m.points * scale
        m.rotate_x(bank_deg, point=(0, 0, 0), inplace=True)
        m.rotate_y(-pitch_deg, point=(0, 0, 0), inplace=True)
        m.rotate_z(-heading_deg, point=(0, 0, 0), inplace=True)   # heading measured clockwise from +x toward +y
        m.translate(np.asarray(pos, float), inplace=True)
        out[k] = m
    return out


def add_x8(plotter, pos, heading_deg=0.0, bank_deg=0.0, pitch_deg=0.0, scale=1.0, color="#f2f2f0", accent="#2a78d6",
           scalars=None, cmap=None, clim=None, show_scalar_bar=False, bar_args=None):
    ms = x8(pos, heading_deg, bank_deg, pitch_deg, scale)
    if scalars is not None:
        ms["wing"]["s"] = scalars(ms["wing"]) if callable(scalars) else scalars
        plotter.add_mesh(ms["wing"], scalars="s", cmap=cmap, clim=clim, smooth_shading=True, specular=0.3, show_scalar_bar=show_scalar_bar, scalar_bar_args=bar_args or {})
    else:
        plotter.add_mesh(ms["wing"], color=color, smooth_shading=True, specular=0.4, specular_power=20)
    plotter.add_mesh(ms["pod"], color=accent, smooth_shading=True, specular=0.4)
    for k in ("wl_r", "wl_l"):
        plotter.add_mesh(ms[k], color=accent, smooth_shading=False)
    plotter.add_mesh(ms["prop"], color="#383835", opacity=0.25)
    return ms
