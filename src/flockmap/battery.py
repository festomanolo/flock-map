"""Pack model: open-circuit voltage vs SoC and internal resistance. All values [ASM] except cell count/capacity."""
from __future__ import annotations
import numpy as np
from .config import BAT

_soc = np.array([0.0, 0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 0.90, 1.0])
_voc = np.array([3.30, 3.50, 3.62, 3.70, 3.78, 3.86, 3.98, 4.08, 4.20])  # V/cell, generic LiPo curve


def voc(soc, bat=BAT):
    return bat.cells * np.interp(soc, _soc, _voc)


def draw(p_load_w, soc, dt_s, bat=BAT):
    """Return (cell_energy_Wh, new_soc) for a constant load power over dt."""
    v = voc(soc, bat)
    disc = v * v - 4.0 * bat.r_int * p_load_w
    if np.any(disc <= 0):
        raise ValueError("load exceeds maximum power transfer of pack model")
    i = (v - np.sqrt(disc)) / (2.0 * bat.r_int)
    e_wh = v * i * dt_s / 3600.0
    cap_wh_nominal = bat.capacity_ah * v      # charge-based SoC update
    new = soc - (i * dt_s / 3600.0) / bat.capacity_ah
    return e_wh, new
