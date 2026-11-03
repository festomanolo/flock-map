"""Photoreal-style renders of the formation (PyVista, off-screen). Run:  python3 figures/render_real.py [scene ...]
Scenes: formation (chase view), topdown (survey strips), low (low-angle sunset)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pyvista as pv
from matplotlib.colors import LinearSegmentedColormap
