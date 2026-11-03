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


