#!/usr/bin/env python3
"""3-D renders of the OpenFOAM solutions (PyVista).  xvfb-run -a python3 cfd/render_cfd.py [case ...]
Writes figures/out3d/K1_cp_<case>.png, K2_vortex_<case>.png, K3_wslices_<case>.png"""
import sys, os, glob, json
import numpy as np, pyvista as pv
pv.OFF_SCREEN = True
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "..", "figures", "out3d"); os.makedirs(OUT, exist_ok=True)
B = 2.12; Q0 = 0.5 * 1.225 * 18.0 ** 2


def vtkdir(case):
    d = sorted(x for x in glob.glob(os.path.join(HERE, "cases", case, "VTK", "*_*")) if os.path.isdir(x)); return d[-1]


def mirror(m):
    f = m.copy(); f.points = f.points * np.array([1, -1, 1]); f = f.compute_normals(flip_normals=True, inplace=False) if hasattr(f, "compute_normals") else f
    return f


def plotter(w=2000, h=1000):
    p = pv.Plotter(off_screen=True, window_size=(w, h)); p.set_background("#ffffff", top="#dfe3ea"); p.enable_anti_aliasing("ssaa"); return p


def load(case):
    v = vtkdir(case); I = pv.read(os.path.join(v, "internal.vtu")); meta = json.load(open(os.path.join(HERE, "cases", case, "case.json")))
    pa = {n: pv.read(os.path.join(v, "boundary", n + ".vtp")) for n in ("leader", "follower") if os.path.exists(os.path.join(v, "boundary", n + ".vtp"))}
    return I, pa, meta


def cp_scene(case):
    I, pa, meta = load(case); p = plotter()
    shown_bar = False
    sbar = dict(title="Cp", n_labels=5, vertical=False, position_x=0.33, position_y=0.05, width=0.34, height=0.07, title_font_size=20, label_font_size=16, color="black")
    for n, m in pa.items():
        m = m.cell_data_to_point_data(); cp = (np.asarray(m.point_data["p"])) / 0.5  # kinematic p -> Cp = p/(0.5 U^2)
        cp = cp / (18.0 ** 2) * 1.0; m.point_data["Cp"] = cp
        for s in (m, mirror(m)):
            p.add_mesh(s, scalars="Cp", cmap="RdBu_r", clim=(-1.0, 0.6), smooth_shading=True, show_scalar_bar=not shown_bar, scalar_bar_args=sbar if not shown_bar else None)
            shown_bar = True
    xc = 0.5 * meta["follower"][1] * B if meta.get("follower") else 0.0
    p.camera_position = [(xc - 2.5, -5.5, 4.2), (xc, 0.0, 0.0), (0, 0, 1)]
    p.add_text(f"{case}: surface pressure coefficient Cp (RANS, k-omega SST)", font_size=15, color="black", position="upper_left")
    p.screenshot(os.path.join(OUT, f"K1_cp_{case}.png")); p.close()


def vortex_scene(case):
    I, pa, meta = load(case)
    box = I.clip_box([-1.0, 13.0, 0.0, 3.2, -1.2, 1.2], invert=False).cell_data_to_point_data()
    d = box.compute_derivative(scalars="U", qcriterion=True, vorticity=True)
    from scipy.spatial import cKDTree
    wp = np.vstack([m.points for m in pa.values()]); dist = cKDTree(wp).query(box.points)[0]
    q = np.asarray(d.point_data["qcriterion"]) * (dist > 0.07); box.point_data["Q"] = q / (18.0 / B) ** 2
    iso = box.contour([0.1], scalars="Q"); iso = iso.compute_normals() if iso.n_points else iso
    vort = np.asarray(d.point_data["vorticity"]); box.point_data["wx"] = vort[:, 0] * B / 18.0; iso = iso.sample(box) if iso.n_points else iso
    p = plotter()
    for n, m in pa.items():
        for s in (m, mirror(m)): p.add_mesh(s, color="#52514e", smooth_shading=True)
    if iso.n_points:
        sbar = dict(title="wx b / U", n_labels=5, vertical=False, position_x=0.33, position_y=0.05, width=0.34, height=0.07, title_font_size=20, label_font_size=16, color="black")
        p.add_mesh(iso, scalars="wx", cmap="RdBu_r", clim=(-8, 8), opacity=0.85, smooth_shading=True, show_scalar_bar=True, scalar_bar_args=sbar)
        p.add_mesh(iso.copy().transform(np.diag([1, -1, 1, 1]), inplace=False), scalars="wx", cmap="RdBu_r", clim=(-8, 8), opacity=0.85, show_scalar_bar=False)
    p.camera_position = [(-2.0, -5.0, 3.0), (6.0, 0.6, 0.0), (0, 0, 1)]
    p.add_text(f"{case}: Q-criterion iso-surface coloured by streamwise vorticity", font_size=15, color="black", position="upper_left")
    p.screenshot(os.path.join(OUT, f"K2_vortex_{case}.png")); p.close()


def slices_scene(case):
    I, pa, meta = load(case); Ip = I.cell_data_to_point_data(); w = np.asarray(Ip.point_data["U"])[:, 2] / 18.0; Ip.point_data["w"] = w
    p = plotter()
    for n, m in pa.items():
        for s in (m, mirror(m)): p.add_mesh(s, color="#52514e", smooth_shading=True)
    shown_bar = False
    for xs in (1.0, 3.0 * B, 5.0 * B, 8.0 * B):
        sl = Ip.slice(normal="x", origin=(xs, 0, 0)).clip_box([xs - 1, xs + 1, 0.0, 3.4, -1.0, 1.0], invert=False)
        if sl.n_points: p.add_mesh(sl, scalars="w", cmap="RdBu_r", clim=(-0.06, 0.06), opacity=0.9, show_scalar_bar=False)
    p.camera_position = [(-2.0, -5.0, 3.0), (6.0, 0.6, 0.0), (0, 0, 1)]
    p.add_text(f"{case}: vertical velocity w/U at x = 1 m, 3b, 5b, 8b", font_size=11, color="black", position="upper_left")
    p.screenshot(os.path.join(OUT, f"K3_wslices_{case}.png")); p.close()


if __name__ == "__main__":
    cases = sys.argv[1:] or ["iso_a3_L1", "fol_dy085_dx3_L1"]
    for c in cases:
        for fn in (cp_scene, vortex_scene, slices_scene):
            try: fn(c); print("ok", fn.__name__, c)
            except Exception as e: print("FAIL", fn.__name__, c, repr(e))
