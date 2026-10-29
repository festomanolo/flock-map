"""Geometric coverage / ray-multiplicity model (flat terrain, nadir pinhole camera, rigid mount).

This is a *planning-level geometric model*.  It does NOT run structure-from-motion, so it cannot produce
checkpoint RMSE_H / RMSE_V.  "Geometrically accepted area" below uses only acceptance criteria (1) coverage >= 99 %
and (2) tie-ray multiplicity >= 5 over 95 % of a 1-ha tile; criteria (3)-(4) (RMSE) are NOT evaluated.
"""
from __future__ import annotations
import math
import numpy as np
from .config import CAM, MIS, Camera

CELL = 2.0   # m


def strip_centres(n_strips, spacing, side=MIS.side):
    c = side / 2 + (np.arange(n_strips) - (n_strips - 1) / 2) * spacing
    return c


def footprint_corners(cx, cy, W, H, yaw):
    """Corners of a W (cross-track) x H (along-track) rectangle centred at (cx, cy), rotated by yaw [rad]
    (yaw=0: along-track = +y)."""
    hw, hh = W / 2, H / 2
    pts = np.array([[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]])
    c, s = math.cos(yaw), math.sin(yaw)
    R = np.array([[c, s], [-s, c]])         # rotate about vertical axis
    return pts @ R.T + np.array([cx, cy])


def multiplicity_map(strip_x, strip_dir_sign, cam: Camera = CAM, side=MIS.side, crab=None, ground_speed_jitter=0.0,
                     rng=None, extra_images=1.0):
    """Count images covering each cell.  strip_x: cross-track centres [m]; crab: per-strip crab angle [rad]."""
    n = int(side / CELL)
    xs = (np.arange(n) + 0.5) * CELL
    X, Y = np.meshgrid(xs, xs, indexing="xy")
    mult = np.zeros((n, n), np.int16)
    dxp = cam.Hg * (1 - cam.of)
    y0 = -cam.Hg / 2 * extra_images; y1 = side + cam.Hg / 2 * extra_images
    ys = np.arange(y0, y1 + 1e-9, dxp)
    half = math.hypot(cam.Wg, cam.Hg) / 2 + CELL
    for i, cx in enumerate(strip_x):
        yaw = 0.0 if crab is None else crab[i]
        c, s = math.cos(yaw), math.sin(yaw)
        j0, j1 = max(0, int((cx - half) / CELL)), min(n, int((cx + half) / CELL) + 1)
        for cy in ys:
            i0, i1 = max(0, int((cy - half) / CELL)), min(n, int((cy + half) / CELL) + 1)
            if i0 >= i1 or j0 >= j1: continue
            Xw, Yw = X[i0:i1, j0:j1], Y[i0:i1, j0:j1]
            u = (Xw - cx) * c - (Yw - cy) * s
            v = (Xw - cx) * s + (Yw - cy) * c
            mult[i0:i1, j0:j1] += (np.abs(u) <= cam.Wg / 2) & (np.abs(v) <= cam.Hg / 2)
    return mult


def accepted_area(mult, tile=100.0, min_mult=5, cov_min=0.99, frac_min=0.95, side=MIS.side):
    """Return (accepted_ha, coverage_frac, per-tile table)."""
    t = int(tile / CELL); nt = int(side / tile)
    ok = np.zeros((nt, nt), bool); cov = np.zeros((nt, nt)); good = np.zeros((nt, nt))
    for i in range(nt):
        for j in range(nt):
            blk = mult[i * t:(i + 1) * t, j * t:(j + 1) * t]
            cov[i, j] = np.mean(blk >= 1); good[i, j] = np.mean(blk >= min_mult)
            ok[i, j] = (cov[i, j] >= cov_min) and (good[i, j] >= frac_min)
    return float(ok.sum() * (tile ** 2) / 1e4), float(np.mean(mult >= 1)), dict(ok=ok, cov=cov, good=good)


def gsd_stats(cam: Camera = CAM):
    return dict(gsd_cm=cam.gsd * 100, Wg=cam.Wg, Hg=cam.Hg, dx_photo=cam.Hg * (1 - cam.of),
                dy_65=cam.Wg * (1 - cam.os_base), dy_58=cam.Wg * (1 - cam.os_opt),
                n17=math.ceil(MIS.side / (cam.Wg * (1 - cam.os_base))),
                n14=math.ceil(MIS.side / (cam.Wg * (1 - cam.os_opt))),
                B_over_H_65=cam.Wg * (1 - cam.os_base) / cam.agl, B_over_H_58=cam.Wg * (1 - cam.os_opt) / cam.agl,
                B_over_H_fwd=cam.Hg * (1 - cam.of) / cam.agl, blur_px=lambda v, t: v * t / cam.gsd)
