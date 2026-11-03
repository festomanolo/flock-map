"""Photoreal-style renders of the formation (PyVista, off-screen). Run:  python3 figures/render_real.py [scene ...]
Scenes: formation (chase view), topdown (survey strips), low (low-angle sunset)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pyvista as pv
from matplotlib.colors import LinearSegmentedColormap
from flockmap import viz3d
from flockmap.config import AC

pv.OFF_SCREEN = True
B = AC.b
OUT = "figures/out3d/realistic"; os.makedirs(OUT, exist_ok=True)


def terrain(x0, x1, y0, y1, n=420, amp=3.5, seed=7):
    rng = np.random.default_rng(seed)
    xs = np.linspace(x0, x1, n); ys = np.linspace(y0, y1, n)
    X, Y = np.meshgrid(xs, ys, indexing="ij"); Z = np.zeros_like(X)
    for k in range(12):
        lam = 900.0 / (1.6 ** k); a = amp * 0.58 ** k
        th = rng.uniform(0, np.pi); ph = rng.uniform(0, 2 * np.pi)
        Z += a * np.sin(2 * np.pi * (X * np.cos(th) + Y * np.sin(th)) / lam + ph)
