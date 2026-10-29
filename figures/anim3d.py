"""Animated GIFs of the simulated manoeuvres (same data as the still images)."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pyvista as pv
from fig3d import *

pv.OFF_SCREEN = True


def anim_split():
    z = np.load("data/raw/cases3d.npz")
    t = z["split|NMPC|t"]; pfx, pfy, plx, ply = (z[f"split|NMPC|{k}"] for k in ("pfx", "pfy", "plx", "ply")); phi = z["split|NMPC|phi"]
    El, Nl = ply - ply[0], plx - plx[0]; Er, Nr = pfy - ply[0], pfx - plx[0]; Elf = 2 * El - Er; Nlf = Nr
    def course(E_, N_, i):
        j = min(i + 3, len(E_) - 1); i0 = max(j - 6, 0)
        return math.degrees(math.atan2(E_[j] - E_[i0], N_[j] - N_[i0])) % 360
    p = pv.Plotter(off_screen=True, window_size=(1300, 760)); p.open_gif("figures/out3d/anim_split_manoeuvre.gif", fps=12)
    frames = list(range(0, len(t) - 4, 12))
    for i in frames:
        p.clear(); p.set_background("white", top="#cfd8e6")
        p.add_mesh(pv.Plane(center=(0, 1000, -2), direction=(0, 0, 1), i_size=1500, j_size=2600), color="#e6eadf", lighting=False)
        for k in range(-4, 5): p.add_mesh(pv.Line((k * 150.0, -200, -1.5), (k * 150.0, 2400, -1.5)), color="#c8cec0", line_width=1)
        sl = slice(0, i + 1)
        def W(E_, N_): return np.column_stack([E_, N_, np.zeros(len(E_))])
        if i > 3:
            trail(p, W(El[sl], Nl[sl]), radius=1.6, color="#555555"); trail(p, W(Er[sl], Nr[sl]), radius=2.0, color=AQUA); trail(p, W(Elf[sl], Nlf[sl]), radius=2.0, color=AQUA)
        add_uav(p, El[i], Nl[i], 0.0, course(El, Nl, i), scale=40, accent="#7d8794")
        add_uav(p, Er[i], Nr[i], 0.0, course(Er, Nr, i), bank_deg=phi[i], scale=40, accent=AQUA)
        add_uav(p, Elf[i], Nlf[i], 0.0, course(Elf, Nlf, i), bank_deg=-phi[i], scale=40, accent=AQUA)
        p.add_text(f"t = {t[i]:5.1f} s   lateral separation of followers: {abs(Er[i]-Elf[i]):6.1f} m", font_size=11, position="upper_left", color=INK)
        p.camera_position = [(950, Nl[i] - 650, 760), (0, Nl[i] + 300, 0), (0, 0, 1)]
        p.write_frame()
    p.close(); print("gif split", len(frames))


def anim_safety():
    z = np.load("data/raw/cases3d.npz"); case = "S3_braking_dropout"
    cols = {"P": ORANGE, "NMPC": BLUE, "NMPC+CBF": VIOLET}
    t = z[f"{case}|P|t"]; m = np.where((t >= 12) & (t <= 28))[0]
    p = pv.Plotter(off_screen=True, window_size=(1300, 760)); p.open_gif("figures/out3d/anim_safety_braking.gif", fps=12)
    for idx, i in enumerate(m):
        p.clear(); p.set_background("white", top="#dfe3ea")
        p.add_mesh(pv.Sphere(radius=4.24, theta_resolution=48, phi_resolution=48), color=RED, opacity=0.16, smooth_shading=True)
        add_uav(p, 0, 0, 0, 90.0, accent=VIOLET); viz3d.add_x8(p, (-6.36, 1.70, 0), accent="#b9c1cc", color="#d9dde3")
        txt = []
        for c in ("P", "NMPC", "NMPC+CBF"):
            dxr = z[f"{case}|{c}|dx"]; dyr = z[f"{case}|{c}|dy"]; d = z[f"{case}|{c}|dist"]
            sl = np.arange(m[0], i + 1)
            if len(sl) > 3: trail(p, np.column_stack([-dxr[sl], dyr[sl], np.full(len(sl), 0.05)]), radius=0.06, color=cols[c])
            add_uav(p, -dxr[i], dyr[i], 0.0, 90.0, accent=cols[c]); txt.append(f"{c}: {d[i]:.2f} m")
        p.add_text(f"t = {t[i]:.1f} s  separation  " + "  |  ".join(txt) + "   (safe >= 4.24 m)", font_size=10, position="upper_left", color=INK)
        p.camera_position = [(-20.0, -22.0, 15.0), (-3.0, 0.8, 0.0), (0, 0, 1)]
        p.write_frame()
    p.close(); print("gif safety", len(m))


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["split", "safety"]):
        globals()["anim_" + s]()
