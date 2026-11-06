"""3-D renders driven by the simulations (PyVista, off-screen).  Run:  xvfb-run -a python3 figures/fig3d.py [scene ...]"""
import sys, os, math, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
import pyvista as pv
from flockmap import viz3d, aero, vlm
from flockmap.freewake import FreeWake
from flockmap.config import AC, CAM, MIS

pv.OFF_SCREEN = True
B = AC.b; OUT = "figures/out3d"; os.makedirs(OUT, exist_ok=True)
INK = "#0b0b0b"; BLUE = "#2a78d6"; ORANGE = "#eb6834"; AQUA = "#1baf7a"; VIOLET = "#6250d6"; RED = "#e34948"; YEL = "#eda100"
CMAP_DIV = None


def div_cmap():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("div", [ORANGE, "#f0efec", BLUE])


def plotter(w=2000, h=1100, bg=("#ffffff", "#dfe3ea")):
    p = pv.Plotter(off_screen=True, window_size=(w, h))
    p.set_background(bg[0], top=bg[1])
    p.enable_anti_aliasing("ssaa")
    return p


def load_fw(name="fine"):
    path = f"data/processed/freewake_{name}.npz"
    if os.path.exists(path):
        return FreeWake.load(path)
    z = np.load("/tmp/fw_test.npz")
    fw = FreeWake(n_span=z["G"].shape[1], dt=0.02, n_rows=len(z["G"]))
    fw.rows, fw.G_rows, fw.gamma = z["rows"], z["G"], z["G"][0]
    return fw


XTE_FW = AC.chord                      # trailing-edge x in the solver frame
TE_BODY = -0.50                        # trailing-edge x of the mesh in body coordinates (approx. root -0.32 / tip -0.5)


def to_world(P):
    """solver frame (x downstream) -> render world (x = flight direction, leader's wake at -x)."""
    P = np.asarray(P, float).copy()
    out = P.copy(); out[..., 0] = -(P[..., 0] - XTE_FW) + TE_BODY
    return out


def from_world(Pw):
    P = np.asarray(Pw, float).copy(); P[..., 0] = XTE_FW - (Pw[..., 0] - TE_BODY)
    return P


def vel_world(fw, Pw):
    v = fw.velocity(from_world(Pw)); v[:, 0] *= -1.0
    return v


def wake_surface(fw, upto=None):
    rows = fw.rows[: (upto or len(fw.rows))]
    te = np.asarray(fw.te)[None]
    allr = np.concatenate([te, rows], 0)
    W = to_world(allr)
    g = pv.StructuredGrid(W[:, :, 0], W[:, :, 1], W[:, :, 2])
    return g.extract_surface()


def save(p, name, cam=None, zoom=None):
    if cam is not None: p.camera_position = cam
    if zoom: p.camera.zoom(zoom)
    p.show(screenshot=f"{OUT}/{name}.png", auto_close=True)
    print("wrote", name, flush=True)


# ---------------------------------------------------------------------------------- scene A: free wake and formation
def bars(title, y, x=0.05, w=0.32):
    return dict(title=title, vertical=False, position_x=x, position_y=y, width=w, height=0.055, color=INK, title_font_size=20, label_font_size=16, n_labels=5)


def w_plane(fw, x_plane, ys, zs):
    Y, Z = np.meshgrid(ys, zs, indexing="ij")
    Pw = np.stack([np.full(Y.size, x_plane), Y.ravel(), Z.ravel()], 1)
    v = vel_world(fw, Pw)
    g = pv.StructuredGrid(np.full_like(Y, x_plane), Y, Z)
    g.point_data["w"] = v[:, 2].ravel(order="F") if False else v[:, 2].reshape(Y.shape).ravel(order="F")
    g.point_data["vec"] = np.column_stack([np.zeros(len(v)), v[:, 1], v[:, 2]]).reshape(Y.shape + (3,)).transpose(1, 0, 2).reshape(-1, 3)
    return g


def horiz_plane(fw, xs, ys, z0=0.0):
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    Pw = np.stack([X.ravel(), Y.ravel(), np.full(X.size, z0)], 1)
    v = vel_world(fw, Pw)
    g = pv.StructuredGrid(X, Y, np.full_like(X, z0))
    g.point_data["w"] = v[:, 2].reshape(X.shape).ravel(order="F")
    return g


def formation(p, dx, dy, scale=1.0, loading=None):
    viz3d.add_x8(p, (0, 0, 0), accent=VIOLET)
    for sgn in (-1, 1):
        viz3d.add_x8(p, (-dx, sgn * dy, 0), accent=AQUA)


def scene_wake():
    fw = load_fw("fine"); b = B; dx, dy = 3 * b, 0.85 * b
    nrow = int(14.0 / (fw.va * fw.dt))
    ws = wake_surface(fw, nrow); ws["z"] = ws.points[:, 2]
    CL = dict(clim=(-0.6, 0.6), cmap=div_cmap())
    p = pv.Plotter(off_screen=True, window_size=(2400, 1500), shape=(2, 2))
    # (a) oblique overview
    p.subplot(0, 0); p.set_background("white", top="#dfe3ea")
    p.add_mesh(ws, scalars="z", cmap="coolwarm_r", opacity=0.45, show_edges=True, edge_color="#8a8a8a", line_width=0.3, smooth_shading=True, scalar_bar_args=bars("wake-sheet height z (m)", 0.1, 0.35))
    for col in (0, fw.n):
        pts = to_world(np.concatenate([np.asarray(fw.te)[None], fw.rows[:nrow]], 0)[:, col, :]); p.add_mesh(pv.Spline(pts, 300).tube(radius=0.015), color=RED)
    formation(p, dx, dy)
    pl = w_plane(fw, -dx - 0.3, np.linspace(-3.4, 3.4, 90), np.linspace(-1.3, 1.3, 50))
    p.add_mesh(pl, scalars="w", opacity=0.8, lighting=False, show_scalar_bar=True, scalar_bar_args=bars("w at follower plane (m/s)", 0.04, 0.02), **CL)
    p.add_text("(a) free-wake sheet and follower plane", font_size=14, position="upper_left", color=INK)
    p.camera_position = [(-9.5, -8.0, 3.6), (-4.8, 0.0, -0.2), (0, 0, 1)]
    # (b) plan view of w on the flight-level plane
    p.subplot(0, 1); p.set_background("white", top="#dfe3ea")
    hp = horiz_plane(fw, np.linspace(-14, 1.0, 110), np.linspace(-4.0, 4.0, 70))
    p.add_mesh(hp, scalars="w", lighting=False, show_scalar_bar=True, scalar_bar_args=bars("w at flight level (m/s)", 0.04, 0.35), **CL)
    formation(p, dx, dy)
    p.add_text("(b) plan view: upwash lobes outboard of the tip vortices", font_size=14, position="upper_left", color=INK)
    p.camera_position = [(-6.5, 0.0, 20.0), (-6.5, 0.0, 0.0), (1, 0, 0)]
    # (c) rear view with swirl arrows
    p.subplot(1, 0); p.set_background("white", top="#dfe3ea")
    pl2 = w_plane(fw, -dx - 0.3, np.linspace(-3.4, 3.4, 90), np.linspace(-1.3, 1.3, 50))
    p.add_mesh(pl2, scalars="w", lighting=False, show_scalar_bar=True, scalar_bar_args=bars("w (m/s)", 0.04, 0.35), **CL)
    sub = w_plane(fw, -dx - 0.3, np.linspace(-3.4, 3.4, 17), np.linspace(-1.2, 1.2, 9))
    gl = sub.glyph(orient="vec", scale=False, factor=0.28, geom=pv.Arrow(tip_length=0.4, tip_radius=0.12, shaft_radius=0.04))
    p.add_mesh(gl, color=INK)
    for sgn in (-1, 1): viz3d.add_x8(p, (-dx, sgn * dy, 0), accent=AQUA)
    p.add_text("(c) rear view: cross-flow (v,w) at the followers' plane", font_size=14, position="upper_left", color=INK)
    p.camera_position = [(-dx - 9.0, 0.0, 0.6), (-dx, 0.0, 0.0), (0, 0, 1)]
    # (d) follower wing loading
    p.subplot(1, 1); p.set_background("white", top="#dfe3ea")
    r = vlm.follower(3.0, 0.85, wake="free")
    ym, gam, gam0 = r["_ym"], r["_gam"], r["_gam_iso"]
    dG = 100 * (gam - gam0) / gam0.max()
    def loading(mesh, sgn=1):
        return np.interp(mesh.points[:, 1] - sgn * dy, ym, dG)
    ms = viz3d.add_x8(p, (-dx, dy, 0), scalars=lambda m: loading(m), cmap="PuOr_r", clim=(-25, 25), show_scalar_bar=True, bar_args=bars("circulation change vs isolated (%)", 0.04, 0.3, 0.4))
    viz3d.add_x8(p, (-dx, -dy, 0), accent=AQUA)
    viz3d.add_x8(p, (0, 0, 0), accent=VIOLET)
    pts = np.array([[-dx, dy + y, 0.05] for y in np.linspace(-B / 2 * 0.95, B / 2 * 0.95, 11)])
    vv = vel_world(fw, pts)
    arr = pv.PolyData(pts); arr["v"] = np.column_stack([np.zeros(len(pts)), np.zeros(len(pts)), vv[:, 2]]); arr["mag"] = np.abs(vv[:, 2])
    p.add_mesh(arr.glyph(orient="v", scale="mag", factor=2.0, geom=pv.Arrow(tip_length=0.35, tip_radius=0.1, shaft_radius=0.03)), color=BLUE)
    p.add_scalar_bar("circulation change vs isolated (%)") if False else None
    p.add_text("(d) follower wing: circulation change (colour) and induced w (arrow length 2 m per m/s)", font_size=10, position="upper_left", color=INK)
    p.camera_position = [(-dx - 3.2, dy - 3.0, 2.2), (-dx - 0.2, dy, 0.1), (0, 0, 1)]
    save(p, "A1_freewake_formation")




# ====================================================================================== trajectory / mission scenes
def course_to_heading(course_deg):          # compass bearing (deg from north, clockwise) -> viz3d heading for an ENU world
    return course_deg - 90.0


def add_uav(p, E, N, U, course_deg=0.0, bank_deg=0.0, scale=1.0, accent=BLUE, color="#f2f2f0"):
    return viz3d.add_x8(p, (E, N, U), heading_deg=course_to_heading(course_deg), bank_deg=bank_deg, scale=scale, accent=accent, color=color)


def trail(p, pts, colors=None, scalars=None, cmap=None, clim=None, radius=0.2, color=INK, name=None, bar=None):
    pts = np.asarray(pts, float)
    if len(pts) < 2: return
    sp = pv.Spline(pts, len(pts) * 2)
    if scalars is not None:
        sp["s"] = np.interp(np.linspace(0, 1, sp.n_points), np.linspace(0, 1, len(scalars)), scalars)
        p.add_mesh(sp.tube(radius=radius), scalars="s", cmap=cmap, clim=clim, smooth_shading=True, show_scalar_bar=bar is not None,
                   scalar_bar_args=bar or {})
    else:
        p.add_mesh(sp.tube(radius=radius), color=color, smooth_shading=True)


def scene_safety():
    z = np.load("data/raw/cases3d.npz")
    cols = {"P": ORANGE, "NMPC": BLUE, "NMPC+CBF": VIOLET}
    p = pv.Plotter(off_screen=True, window_size=(2600, 950), shape=(1, 3))
    for k, (case, ttl, tw) in enumerate((("S3_braking_dropout", "S3: leader braking 4 m/s + 250 ms dropout", (14, 26)),
                                         ("S5_combined", "S5: combined disturbance", (14, 28)),
                                         ("S6_overcapability", "S6: braking beyond follower authority", (14, 24)))):
        p.subplot(0, k); p.set_background("white", top="#dfe3ea")
        sph = pv.Sphere(radius=4.24, center=(0, 0, 0), theta_resolution=64, phi_resolution=64)
        p.add_mesh(sph, color=RED, opacity=0.18, smooth_shading=True)
        p.add_mesh(pv.Circle(radius=4.24, resolution=128).rotate_z(0), color=RED, style="wireframe", line_width=2)
        add_uav(p, 0, 0, 0, 90.0, accent=VIOLET)               # leader heading east (+x) in this local frame: course 90
        # nominal slot ghost
        viz3d.add_x8(p, (-6.36, 1.70, 0), accent="#b9c1cc", color="#d9dde3")
        mins = []
        for c in ("P", "NMPC", "NMPC+CBF"):
            t = z[f"{case}|{c}|t"]; dxr = z[f"{case}|{c}|dx"]; dyr = z[f"{case}|{c}|dy"]; d = z[f"{case}|{c}|dist"]
            # leader frame: x forward, y = +east-like; follower relative position (-dx, +dy)
            m = (t >= tw[0]) & (t <= tw[1])
            pts = np.column_stack([-dxr[m], dyr[m], np.full(m.sum(), 0.05)])
            trail(p, pts, radius=0.07, color=cols[c])
            i = np.argmin(d); mins.append((c, d[i]))
            add_uav(p, -dxr[i], dyr[i], 0.0, 90.0, bank_deg=0.0, accent=cols[c])
            p.add_mesh(pv.Sphere(radius=0.18, center=(-dxr[i], dyr[i], 0.2)), color=cols[c])
        txt = "\n".join(f"{c}: min separation {m:.2f} m" for c, m in mins)
        p.add_text(f"{ttl}\n{txt}", font_size=9, position="upper_left", color=INK)
        p.camera_position = [(-22.0, -26.0, 17.0), (-3.0, 0.8, 0.0), (0, 0, 1)]
    save(p, "B1_safety_sphere")


def scene_split():
    z = np.load("data/raw/cases3d.npz")
    t = z["split|NMPC|t"]; pfx, pfy, plx, ply = (z[f"split|NMPC|{k}"] for k in ("pfx", "pfy", "plx", "ply"))
    phi = z["split|NMPC|phi"]
    from flockmap import energy as E
    tab = E.table("vlm_sheet", 18.0)
    sav = np.array([E.p_level(18.0) - E.p_level(18.0, 0.0, -float(c)) for c in tab(z["split|NMPC|dx"], z["split|NMPC|dy"])])
    p = pv.Plotter(off_screen=True, window_size=(2400, 1200)); p.set_background("white", top="#cfd8e6")
    El, Nl = ply - ply[0], plx - plx[0]
    Er, Nr = pfy - ply[0], pfx - plx[0]
    Elf, Nlf = 2 * El - Er, Nr                                    # port follower: mirror image about the leader track
    ground = pv.Plane(center=(0, 1000, -2), direction=(0, 0, 1), i_size=1500, j_size=2600)
    p.add_mesh(ground, color="#e6eadf", lighting=False)
    for k in range(-4, 5):
        p.add_mesh(pv.Line((k * 150.0, -200, -1.5), (k * 150.0, 2400, -1.5)), color="#c8cec0", line_width=1)
    def W(E_, N_): return np.column_stack([E_, N_, np.zeros(len(E_))])
    trail(p, W(El, Nl), radius=1.6, color="#555555")
    bar = dict(title="follower aerodynamic power saving (W)", vertical=False, position_x=0.35, position_y=0.05, width=0.3, height=0.05, color=INK, title_font_size=14, label_font_size=12, n_labels=5)
    trail(p, W(Er, Nr), scalars=sav, cmap="viridis", clim=(0, 8.5), radius=2.2, bar=bar)
    trail(p, W(Elf, Nlf), scalars=sav, cmap="viridis", clim=(0, 8.5), radius=2.2)
    def course(E_, N_, i):
        j = min(i + 3, len(E_) - 1); i0 = max(j - 6, 0)
        return math.degrees(math.atan2(E_[j] - E_[i0], N_[j] - N_[i0])) % 360
    for ti in (0.0, 25.0, 50.0, 75.0, 100.0, 122.0):
        i = min(np.argmin(np.abs(t - ti)), len(t) - 4)
        add_uav(p, El[i], Nl[i], 0.0, course(El, Nl, i), scale=40, accent="#7d8794")
        add_uav(p, Er[i], Nr[i], 0.0, course(Er, Nr, i), bank_deg=phi[i], scale=40, accent=AQUA)
        add_uav(p, Elf[i], Nlf[i], 0.0, course(Elf, Nlf, i), bank_deg=-phi[i], scale=40, accent=AQUA)
    p.add_text("Formation split into zones, 370 m lateral displacement (NMPC, VLM-sheet wake saving along the paths); aircraft drawn 40x", font_size=10, position="upper_left", color=INK)
    p.camera_position = [(1000, -520, 800), (0, 950, 0), (0, 0, 1)]
    save(p, "B2_split_manoeuvre")


def fbm_terrain(x0, x1, y0, y1, nx=220, ny=420, amp=22.0, seed=3):
    rng = np.random.default_rng(seed)
    xs = np.linspace(x0, x1, nx); ys = np.linspace(y0, y1, ny)
    X, Y = np.meshgrid(xs, ys, indexing="ij"); Z = np.zeros_like(X)
    for k in range(14):
        lam = 2600.0 / (1.55 ** k); a = amp * 0.62 ** k
        th = rng.uniform(0, np.pi); ph = rng.uniform(0, 2 * np.pi)
        Z += a * np.sin(2 * np.pi * (X * np.cos(th) + Y * np.sin(th)) / lam + ph)
    return X, Y, Z


def scene_camera():
    """True-geometry camera frustums, footprints and overlaps for three strips (65 % side / 75 % forward)."""
    H = CAM.agl; Wg, Hg = CAM.Wg, CAM.Hg; dxp = Hg * (1 - CAM.of); dys = Wg * (1 - CAM.os_base)
    p = plotter(2200, 1250)
    ground = pv.Plane(center=(0, 120, 0), direction=(0, 0, 1), i_size=3 * dys + Wg + 60, j_size=620)
    p.add_mesh(ground, color="#dfe6d7", lighting=False)
    cols = [BLUE, ORANGE, AQUA]
    for si, xc in enumerate((-dys, 0.0, dys)):
        for k in range(5):
            yc = k * dxp
            fp = pv.Rectangle([[xc - Wg / 2, yc - Hg / 2, 0.15 + 0.12 * si + 0.03 * k], [xc + Wg / 2, yc - Hg / 2, 0.15 + 0.12 * si + 0.03 * k], [xc + Wg / 2, yc + Hg / 2, 0.15 + 0.12 * si + 0.03 * k]])
            p.add_mesh(fp, color=cols[si], opacity=0.12, lighting=False)
            p.add_mesh(fp.extract_feature_edges(), color=cols[si], line_width=1.2)
        for k in (1, 3):
            yc = k * dxp
            apex = np.array([xc, yc, H])
            cor = np.array([[xc - Wg / 2, yc - Hg / 2, 0], [xc + Wg / 2, yc - Hg / 2, 0], [xc + Wg / 2, yc + Hg / 2, 0], [xc - Wg / 2, yc + Hg / 2, 0]])
            for c in cor: p.add_mesh(pv.Line(apex, c), color=cols[si], line_width=1.0, opacity=0.6)
        for k in (1, 3):
            add_uav(p, xc, k * dxp, H, 0.0, scale=14, accent=cols[si])
    p.add_text(f"Camera geometry at {H:.0f} m AGL: footprint {Wg:.0f} x {Hg:.0f} m, GSD {CAM.gsd*100:.1f} cm, forward overlap 75 %, side overlap 65 % (aircraft drawn 14x)", font_size=10, position="upper_left", color=INK)
    save(p, "C1_camera_frustums", cam=[(-330, -330, 230), (0, 130, 40), (0, 0, 1)])



# ====================================================================================== wake roll-up (far field)
def scene_rollup():
    fw = load_fw("far"); b = B
    nodes = np.concatenate([np.asarray(fw.te)[None], fw.rows], 0)
    W = nodes.copy(); X = W[:, 0, 0]
    p = pv.Plotter(off_screen=True, window_size=(2400, 1000), shape=(1, 2))
    p.subplot(0, 0); p.set_background("white", top="#dfe3ea")
    g = pv.StructuredGrid(W[:, :, 0], W[:, :, 1], W[:, :, 2]); g["x"] = W[:, :, 0].ravel(order="F")
    surf = g.extract_surface(algorithm="dataset_surface"); surf["z"] = surf.points[:, 2]
    p.add_mesh(surf, scalars="z", cmap="coolwarm_r", opacity=0.6, show_edges=True, edge_color="#999999", line_width=0.2, smooth_shading=True,
               scalar_bar_args=bars("wake height z (m), true scale", 0.05, 0.3, 0.4))
    for col in (0, fw.n):
        p.add_mesh(pv.Spline(nodes[:, col, :], 400).tube(radius=0.06), color=RED)
    for xs, c in ((10, BLUE), (40, AQUA), (80, YEL), (110, VIOLET)):
        k = int(np.argmin(np.abs(X - xs)))
        cs = pv.Spline(nodes[k], 100).tube(radius=0.08); p.add_mesh(cs, color=c)
    # leader, scaled for visibility
    p.add_mesh(pv.Sphere(radius=0.0001), color="w")
    p.add_text("(a) free wake 0–115 m (0–54 b): sheet bows, tips start to curl; cross-sections at 10/40/80/110 m", font_size=10, position="upper_left", color=INK)
    p.camera_position = [(-34, -26, 11), (34, 0, -0.5), (0, 0, 1)]
    p.subplot(0, 1); p.set_background("white", top="#dfe3ea")
    for xs, c in ((5, "#7a8cff"), (10, BLUE), (40, AQUA), (80, YEL), (110, VIOLET)):
        k = int(np.argmin(np.abs(X - xs))); pts = nodes[k].copy(); pts[:, 0] = 0.0
        p.add_mesh(pv.Spline(pts, 120).tube(radius=0.012), color=c)
        p.add_point_labels(pv.PolyData(pts[len(pts) // 2:len(pts) // 2 + 1] + [0, 0, -0.05]), [f"x={X[k]:.0f} m ({X[k]/b:.0f} b)"], font_size=14, text_color=INK, shape=None, show_points=False)
    p.add_mesh(pv.Line((-1.06, 0, 0), (1.06, 0, 0)), color=INK, line_width=3)
    p.add_text("(b) rear view of the sheet cross-sections (leader span in black), true vertical scale", font_size=10, position="upper_left", color=INK)
    p.camera_position = [(-6.5, 0, -0.6), (0, 0, -0.6), (0, 0, 1)]
    save(p, "A2_wake_rollup")


# ====================================================================================== mission scenes
HOME = np.array([500.0, -2500.0])


def hermite(P0, T0, P1, T1, n=60):
    t = np.linspace(0, 1, n)[:, None]
    h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
    return h00 * P0 + h10 * T0 + h01 * P1 + h11 * T1


def strip_path(xs, y_start_south=True, K=190.0):
    """boustrophedon through strips xs (first strip flown northwards); returns (N,2) polyline."""
    pts = []; north = True
    for i, x in enumerate(xs):
        a, bnd = ((x, 0.0), (x, 1000.0)) if north else ((x, 1000.0), (x, 0.0))
        pts.append(np.array([a, bnd]))
        if i + 1 < len(xs):
            P0 = np.array(bnd); P1 = np.array([xs[i + 1], bnd[1]])
            sgn = 1.0 if north else -1.0
            pts.append(hermite(P0, np.array([0, sgn * K]), P1, np.array([0, -sgn * K]), 50))
        north = not north
    return np.vstack(pts)


def point_on(poly, frac):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(poly, axis=0), axis=1))]
    s = frac * d[-1]; i = int(np.clip(np.searchsorted(d, s) - 1, 0, len(poly) - 2))
    a, bq = poly[i], poly[i + 1]; u = (s - d[i]) / max(d[i + 1] - d[i], 1e-9)
    pos = a + u * (bq - a); tang = bq - a
    course = math.degrees(math.atan2(tang[0], tang[1])) % 360.0       # compass: 0 = +N(y), 90 = +E(x)
    return pos, course


def scene_mission():
    from flockmap import mission as M, photo
    X, Y, Z = fbm_terrain(-250, 1250, -2750, 1250, 150, 400)
    from scipy.interpolate import RegularGridInterpolator
    ter = RegularGridInterpolator((X[:, 0], Y[0, :]), Z)
    def H(xy): return float(ter([[xy[0], xy[1]]])[0])
    cfg = [("S1_independent", "S1 independent (17 strips, 6-6-5)"), ("S2_rigid_V", "S2 rigid V (17 strips x 3 aircraft)"),
           ("S3_adaptive_geometric", "S3 adaptive geometric V"), ("S4_wake_aware", "S4 wake-aware adaptive V (14 strips)")]
    cols = [BLUE, ORANGE, AQUA]
    p = pv.Plotter(off_screen=True, window_size=(2600, 1500), shape=(2, 2))
    for k, (st, ttl) in enumerate(cfg):
        p.subplot(k // 2, k % 2); p.set_background("white", top="#cfd8e6")
        form, plan_key, rigid = M.STRATEGIES[st]; plan = M.PLAN[plan_key]; n = plan["n"]; sp = plan["spacing"]
        xs_all = photo.strip_centres(sum(n), sp)
        terr = pv.StructuredGrid(X, Y, Z); terr["h"] = Z.ravel(order="F")
        p.add_mesh(terr, scalars="h", cmap="gist_earth", clim=(-80, 90), show_scalar_bar=False, smooth_shading=True, opacity=1.0, ambient=0.3)
        poly = np.array([[0, 0], [1000, 0], [1000, 1000], [0, 1000], [0, 0]], float)
        p.add_mesh(pv.Spline(np.column_stack([poly, [H(q) + 2 for q in poly]]), 100).tube(radius=5), color="white")
        alt = 120.0
        def to3(P): return np.column_stack([P[:, 0], P[:, 1], [H(q) + alt for q in P]])
        groups = [list(range(0, n[0])), list(range(n[0], n[0] + n[1])), list(range(n[0] + n[1], sum(n)))]
        meshes = []
        for u in range(3):
            if rigid:
                xs = xs_all
                off = (0, -1.7, 1.7)[u]
            else:
                xs = xs_all[groups[u]]
                off = 0.0
            sp_path = strip_path(xs) + np.array([off, 0.0])
            if form:
                home_leg = np.array([[500 + (0, -1.7, 1.7)[u], -2500.0], [500 + (0, -1.7, 1.7)[u], -300.0]])
                join = hermite(home_leg[-1], np.array([0, 150.0]), sp_path[0], np.array([0, 150.0]), 60)
                out = np.vstack([home_leg, join, sp_path])
            else:
                out = np.vstack([np.array([[HOME[0], HOME[1]]]), sp_path])
            trail(p, to3(out), radius=4.5, color=cols[u] if not rigid else VIOLET)
            ret = np.vstack([sp_path[-1:], [[HOME[0], HOME[1]]]])
            p.add_mesh(pv.Spline(to3(ret), 60).tube(radius=2.5), color=cols[u], opacity=0.55)
            pos, crs = point_on(out, 0.50 if not form else 0.58); meshes.append((pos, crs, u))
            d_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(out, axis=0), axis=1))]
            kk = int(np.argmin(np.abs(out[:, 1] + 700))); pos, crs = point_on(out, d_[kk] / d_[-1]); meshes.append((pos, crs, u))
        for (pos, crs, u) in meshes:
            add_uav(p, pos[0], pos[1], H(pos) + alt, crs, scale=60, accent=cols[u] if not rigid else VIOLET)
        if st in ("S3_adaptive_geometric", "S4_wake_aware"):
            p.add_mesh(pv.Sphere(radius=22, center=(500, -300, H((500, -300)) + alt)), color=RED)
        # footprints of the middle strip of each zone
        for g in (groups if not rigid else [groups[0]]):
            xc = xs_all[g[len(g) // 2]]
            for y0 in np.arange(150, 850, CAM.Hg * (1 - CAM.of)):
                rect = pv.Rectangle([[xc - CAM.Wg / 2, y0 - CAM.Hg / 2, H((xc, y0)) + 4], [xc + CAM.Wg / 2, y0 - CAM.Hg / 2, H((xc, y0)) + 4], [xc + CAM.Wg / 2, y0 + CAM.Hg / 2, H((xc, y0)) + 4]])
                p.add_mesh(rect, color=YEL, opacity=0.25, lighting=False)
        p.add_text(ttl, font_size=11, position="upper_left", color=INK)
        p.add_mesh(pv.Sphere(radius=30, center=(HOME[0], HOME[1], H(HOME) + 5)), color=INK)
        p.camera_position = [(-1400, -1500, 1250), (520, 250, 0), (0, 0, 1)]
    p.add_text("Synthetic terrain for visualisation only (the study assumes flat terrain). Aircraft drawn 60x; turns are schematic. Red = split/merge point, black = launch.", font_size=9, position="lower_left", color=INK)
    save(p, "D1_mission_overview")



# ====================================================================================== vorticity iso-surface
def scene_vorticity():
    """Streamwise vorticity omega_x = dw/dy - dv/dz on cross-flow planes behind the leader (free-wake field)."""
    fw = load_fw("far"); b = B
    p = pv.Plotter(off_screen=True, window_size=(2700, 900), shape=(1, 3))
    ys = np.linspace(-1.9, 1.9, 110); zs = np.linspace(-1.6, 0.7, 70); h = 0.01
    from matplotlib.colors import LinearSegmentedColormap
    cm = LinearSegmentedColormap.from_list("vort", [BLUE, "#f7f7f5", ORANGE])
    for k, xq in enumerate((10.0, 60.0, 110.0)):
        p.subplot(0, k); p.set_background("white", top="#dfe3ea")
        Y, Z = np.meshgrid(ys, zs, indexing="ij")
        def vel(dy_, dz_):
            P = np.stack([np.full(Y.size, xq), (Y + dy_).ravel(), (Z + dz_).ravel()], 1)
            # centre z on the local sheet height so the plane follows the sinking wake
            return fw.velocity(P)
        kx = int(np.argmin(np.abs(fw.rows[:, :, 0].mean(1) - xq))); zc = float(fw.rows[kx, :, 2].mean())
        Zs = Z + zc
        def velz(dy_, dz_):
            P = np.stack([np.full(Y.size, xq), (Y + dy_).ravel(), (Zs + dz_).ravel()], 1); return fw.velocity(P)
        wp, wm = velz(h, 0)[:, 2], velz(-h, 0)[:, 2]; vp, vm = velz(0, h)[:, 1], velz(0, -h)[:, 1]
        om = ((wp - wm) / (2 * h) - (vp - vm) / (2 * h)).reshape(Y.shape)
        lim = 0.9 * float(np.abs(om).max())
        g = pv.StructuredGrid(np.zeros_like(Y), Y, Zs); g["om"] = om.ravel(order="F")
        p.add_mesh(g, scalars="om", cmap=cm, clim=(-lim, lim), lighting=False, scalar_bar_args=bars(f"omega_x (1/s), +-{lim:.1f}", 0.03, 0.3, 0.4))
        P = fw.rows[kx]; pts = P.copy(); pts[:, 0] = -0.03
        p.add_mesh(pv.Spline(pts, 150).tube(radius=0.01), color=INK)
        p.add_text(f"x = {xq:.0f} m ({xq/b:.0f} b): black line = wake-sheet cross-section", font_size=10, position="upper_left", color=INK)
        p.camera_position = [(-5.0, 0, zc - 0.45), (0, 0, zc - 0.45), (0, 0, 1)]; p.camera.parallel_projection = True; p.camera.parallel_scale = 1.35
    save(p, "A3_vorticity_isosurface")


def scene_coverage3d():
    from flockmap import photo
    cases = [("17 strips, 65 %", 17, 61.6), ("14 strips, 58 % (as specified)", 14, 73.92), ("14 strips, 57.95 %", 14, 74.0)]
    p = pv.Plotter(off_screen=True, window_size=(2700, 950), shape=(1, 3))
    for k, (lab, n, sp) in enumerate(cases):
        p.subplot(0, k); p.set_background("white", top="#dfe3ea")
        m = photo.multiplicity_map(photo.strip_centres(n, sp), None).astype(float)
        acc, cov, d = photo.accepted_area(m)
        step = 2.0; xs = (np.arange(m.shape[1]) + 0.5) * step; ys = (np.arange(m.shape[0]) + 0.5) * step
        X, Y = np.meshgrid(xs, ys)
        g = pv.StructuredGrid(X, Y, m * 14.0); g["mult"] = m.T.ravel(order="F") if False else m.ravel(order="C").reshape(m.shape).T.ravel(order="C") if False else m.ravel()
        g = pv.StructuredGrid(X.T, Y.T, (m * 14.0).T); g["mult"] = m.T.ravel(order="F")
        p.add_mesh(g, scalars="mult", cmap="Blues", clim=(0, 12), smooth_shading=False, scalar_bar_args=bars("images per cell", 0.03, 0.3, 0.4) if k == 1 else None, show_scalar_bar=(k == 1))
        for i in range(10):
            for j in range(10):
                if not d["ok"][i, j]:
                    p.add_mesh(pv.Rectangle([[j * 100, i * 100, 175], [j * 100 + 100, i * 100, 175], [j * 100 + 100, i * 100 + 100, 175]]), color=RED, opacity=0.55, lighting=False)
        p.add_mesh(pv.Plane(center=(500, 500, 5 * 14.0), direction=(0, 0, 1), i_size=1000, j_size=1000).extract_feature_edges(), color=INK, line_width=2)
        p.add_text(f"{lab}: accepted {acc:.0f} of 100 ha (red = tiles failing the >=5-ray rule)", font_size=10, position="upper_left", color=INK)
        p.camera_position = [(-700, -900, 900), (500, 500, 40), (0, 0, 1)]
    save(p, "C2_coverage_relief")


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["wake"]):
        globals()["scene_" + s]()
