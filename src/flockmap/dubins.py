"""Shortest Dubins path length (LSL, RSR, LSR, RSL, RLR, LRL) for fixed turning radius."""
from __future__ import annotations
import math


def _mod(a): return a % (2 * math.pi)


def dubins_length(q0, q1, r):
    """q = (x, y, heading[rad], x-east/y-north math convention). Returns total path length [m]."""
    dx, dy = q1[0] - q0[0], q1[1] - q0[1]
    D = math.hypot(dx, dy) / r
    th = math.atan2(dy, dx) if D > 0 else 0.0
    a, b = _mod(q0[2] - th), _mod(q1[2] - th)
    sa, ca, sb, cb = math.sin(a), math.cos(a), math.sin(b), math.cos(b)
    best = math.inf
    # LSL
    p2 = 2 + D * D - 2 * math.cos(a - b) + 2 * D * (sa - sb)
    if p2 >= 0:
        tmp = math.atan2(cb - ca, D + sa - sb)
        d1 = _mod(-a + tmp); d3 = _mod(b - tmp)
        best = min(best, d1 + math.sqrt(p2) + d3)
    # RSR
    p2 = 2 + D * D - 2 * math.cos(a - b) + 2 * D * (sb - sa)
    if p2 >= 0:
        tmp = math.atan2(ca - cb, D - sa + sb)
        d1 = _mod(a - tmp); d3 = _mod(-b + tmp)
        best = min(best, d1 + math.sqrt(p2) + d3)
    # LSR
    p2 = -2 + D * D + 2 * math.cos(a - b) + 2 * D * (sa + sb)
    if p2 >= 0:
        p = math.sqrt(p2)
        tmp = math.atan2(-ca - cb, D + sa + sb) - math.atan2(-2.0, p)
        d1 = _mod(-a + tmp); d3 = _mod(-_mod(b) + tmp)
        best = min(best, d1 + p + d3)
    # RSL
    p2 = D * D - 2 + 2 * math.cos(a - b) - 2 * D * (sa + sb)
    if p2 >= 0:
        p = math.sqrt(p2)
        tmp = math.atan2(ca + cb, D - sa - sb) - math.atan2(2.0, p)
        d1 = _mod(a - tmp); d3 = _mod(b - tmp)
        best = min(best, d1 + p + d3)
    # RLR
    tmp = (6 - D * D + 2 * math.cos(a - b) + 2 * D * (sa - sb)) / 8
    if abs(tmp) <= 1:
        p = _mod(2 * math.pi - math.acos(tmp))
        d1 = _mod(a - math.atan2(ca - cb, D - sa + sb) + p / 2)
        d3 = _mod(a - b - d1 + p)
        best = min(best, d1 + p + d3)
    # LRL
    tmp = (6 - D * D + 2 * math.cos(a - b) + 2 * D * (sb - sa)) / 8
    if abs(tmp) <= 1:
        p = _mod(2 * math.pi - math.acos(tmp))
        d1 = _mod(-a - math.atan2(ca - cb, D + sa - sb) + p / 2)
        d3 = _mod(b - a - d1 + p)
        best = min(best, d1 + p + d3)
    return best * r
