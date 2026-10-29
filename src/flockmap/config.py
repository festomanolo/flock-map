"""Locked parameters. Every value carries a provenance tag:
   [MS]  taken verbatim from the original manuscript's parameter table (NOT independently verified)
   [DER] derived from other parameters here
   [ASM] assumption introduced by this study (must be replaced by measurement)
"""
from __future__ import annotations
import dataclasses
import numpy as np

G = 9.80665


@dataclasses.dataclass(frozen=True)
class Aircraft:
    mass: float = 3.50          # kg   [MS] sum of dry+battery+payload
    rho: float = 1.225          # kg/m3 [MS] ISA sea level
    b: float = 2.12             # m    [MS]
    S: float = 0.80             # m2   [MS]
    cd0: float = 0.0240         # -    [MS] "wind-tunnel" value, not re-verified
    e0: float = 0.80            # -    [MS]
    eta_prop: float = 0.68      # -    [MS] constant; real chain varies with J and load
    p_hotel: float = 28.0       # W    [MS] 12 + 6 + 10, constant
    cl_da: float = 0.15         # 1/rad [MS] elevon roll-control derivative
    k_trim: float = 0.035       # 1/rad^2 [MS] trim-drag factor (unvalidated)
    va: float = 18.0            # m/s  [MS]
    bank_turn_deg: float = 25.0  # deg [MS]
    bank_max_deg: float = 35.0  # deg  [MS]
    va_min: float = 12.0        # m/s  [MS]
    va_max: float = 26.0        # m/s  [MS]
    tau_phi: float = 0.25       # s    [MS]
    tau_gamma: float = 0.30     # s    [MS]
    cl_alpha_2d: float = 2 * np.pi  # [DER] thin-airfoil

    @property
    def AR(self): return self.b ** 2 / self.S
    @property
    def k0(self): return 1.0 / (np.pi * self.AR * self.e0)
    @property
    def chord(self): return self.S / self.b
    @property
    def b0(self): return np.pi / 4 * self.b           # elliptical roll-up span [MS]
    @property
    def cl_alpha_3d(self):                              # [DER] lifting-line slope
        return self.cl_alpha_2d * self.AR / (self.AR + 2.0)


@dataclasses.dataclass(frozen=True)
class Wake:
    rc0_frac: float = 0.05      # r_c0 = 0.05 b [MS]
    nu_eff: float = 0.002       # m2/s [MS] effective eddy viscosity (uncalibrated)


@dataclasses.dataclass(frozen=True)
class Battery:
    cells: int = 6              # [MS]
    capacity_ah: float = 10.0   # [MS]
    r_int: float = 0.020        # ohm pack, [ASM]
    usable_frac: float = 0.80   # [MS] 20 % reserve policy


@dataclasses.dataclass(frozen=True)
class Camera:
    px_w: int = 5472            # [MS]
    px_h: int = 3648            # [MS]
    sw: float = 13.20e-3        # m [MS]
    sh: float = 8.80e-3         # m [MS]
    f: float = 9.00e-3          # m [MS]
    agl: float = 120.0          # m [MS]
    of: float = 0.75            # forward overlap [MS]
    os_base: float = 0.65       # side overlap, baseline [MS]
    os_opt: float = 0.58        # side overlap, claimed stereo-assisted [MS] (UNVERIFIED claim)

    @property
    def pitch(self): return self.sw / self.px_w
    @property
    def gsd(self): return self.agl * self.pitch / self.f
    @property
    def Wg(self): return self.agl * self.sw / self.f
    @property
    def Hg(self): return self.agl * self.sh / self.f


@dataclasses.dataclass(frozen=True)
class Mission:
    side: float = 1000.0        # m, square polygon [MS]
    d_transit: float = 2500.0   # m one way [MS]
    n_uav: int = 3
    wind_lo: float = 2.0        # m/s [MS]
    wind_hi: float = 6.0        # m/s [MS]


AC = Aircraft(); WK = Wake(); BAT = Battery(); CAM = Camera(); MIS = Mission()
