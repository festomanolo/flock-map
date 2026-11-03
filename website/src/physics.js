// Single source of truth for every number on the page.
// Values mirror src/flockmap/config.py. Provenance tags: MS = taken from the preliminary manuscript (unverified),
// DER = derived here from other parameters, ASM = assumption introduced by this study, MODEL = approximate geometry.

export const G = 9.80665;

export const AC = {
  mass: 3.5,        // kg   [MS]
  rho: 1.225,       // kg/m3 [MS]
  b: 2.12,          // m    [MS]
  S: 0.8,           // m2   [MS]
  cd0: 0.024,       // [MS]
  e0: 0.8,          // [MS]
  etaProp: 0.68,    // [MS] constant
  pHotel: 28,       // W    [MS] 12 + 6 + 10
  clDa: 0.15,       // 1/rad [MS]
  kTrim: 0.035,     // 1/rad2 [MS]
  va: 18,           // m/s [MS]
  vaMin: 12,
  vaMax: 26,
  bankTurn: 25,     // deg [MS]
  bankMax: 35,      // deg [MS]
  tauPhi: 0.25,     // s [MS]
};
AC.AR = AC.b ** 2 / AC.S;                         // DER
AC.chord = AC.S / AC.b;                           // DER
AC.k0 = 1 / (Math.PI * AC.AR * AC.e0);            // DER
AC.b0 = (Math.PI / 4) * AC.b;                     // DER, rolled-up vortex spacing [MS]
AC.weight = AC.mass * G;                          // DER
AC.clAlpha3d = (2 * Math.PI * AC.AR) / (AC.AR + 2); // DER lifting-line slope

export const WK = { rc0Frac: 0.05, nuEff: 0.002 };   // [MS], uncalibrated

export const BAT = { cells: 6, capacityAh: 10, rInt: 0.02, usable: 0.8, vCell: 3.7 };   // vCell is ASM
BAT.energyWh = BAT.cells * BAT.vCell * BAT.capacityAh;          // DER (needs ASM nominal cell voltage)
BAT.usableWh = BAT.energyWh * BAT.usable;

export const CAM = { pxW: 5472, pxH: 3648, sw: 13.2e-3, sh: 8.8e-3, f: 9e-3, agl: 120, of: 0.75, osBase: 0.65, osOpt: 0.58 };
CAM.pitch = CAM.sw / CAM.pxW;

// ---------------------------------------------------------------- level flight
export function flight(V) {
  const q = 0.5 * AC.rho * V * V;
  const CL = AC.weight / (q * AC.S);
  const CD = AC.cd0 + AC.k0 * CL * CL;
  const D = q * AC.S * CD;
  const pAero = D * V;
  const pShaft = pAero / AC.etaProp;
  const pTotal = pShaft + AC.pHotel;
  return { V, q, CL, CD, LD: CL / CD, D, pAero, pShaft, pTotal };
}

export function energy(V) {
  const f = flight(V);
  const hours = BAT.usableWh / f.pTotal;
  return { ...f, minutes: hours * 60, rangeKm: (V * hours * 3600) / 1000 };
}

// ---------------------------------------------------------------- roll response (first order, tau_phi)
export const rollResponse = (phiCmd, t) => phiCmd * (1 - Math.exp(-t / AC.tauPhi));

// ---------------------------------------------------------------- camera geometry
export function camera(agl, os = CAM.osBase, V = AC.va) {
  const gsd = (agl * CAM.pitch) / CAM.f;
  const Wg = (agl * CAM.sw) / CAM.f;
  const Hg = (agl * CAM.sh) / CAM.f;
  const dxp = Hg * (1 - CAM.of);        // forward spacing between exposures
  const dys = Wg * (1 - os);            // strip spacing
  return { gsd, Wg, Hg, dxp, dys, trigger: dxp / V };
}

// ---------------------------------------------------------------- wake: Lamb-Oseen trailing vortex pair
export const gamma = (V = AC.va) => AC.weight / (AC.rho * V * AC.b0);
export const coreRadius = (dxMeters, V = AC.va) => {
  const rc0 = WK.rc0Frac * AC.b;
  const t = dxMeters / V;
  return Math.sqrt(rc0 * rc0 + 4 * WK.nuEff * t);
};
const f = (r2, rc) => 1 - Math.exp(-r2 / (rc * rc));

// vertical velocity w (m/s, + up) induced by the leader's vortex pair at lateral y, height z (leader frame, y starboard)
export function upwash(y, z, rc, G0 = gamma()) {
  const yR = AC.b0 / 2, yL = -AC.b0 / 2;
  const eps = 1e-6;
  const one = (yv, s) => {
    const dy = y - yv, r2 = dy * dy + z * z + eps;
    return (s * G0 * dy * f(r2, rc)) / (2 * Math.PI * r2);
  };
  // right vortex: positive upwash outboard (dy > 0); left vortex mirrors
  return one(yR, +1) + one(yL, -1);
}

// follower centred at lateral offset yc (m): span-averaged upwash and equivalent angle of attack change
export function followerUpwash(yc, dxMeters, V = AC.va) {
  const rc = coreRadius(dxMeters, V);
  const n = 160, half = AC.b / 2;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const y = yc - half + ((i + 0.5) / n) * AC.b;
    sum += upwash(y, 0, rc);
  }
  const mean = sum / n;
  return { rc, mean, dAlphaDeg: ((mean / V) * 180) / Math.PI };
}

export const fmt = (x, d = 1) => Number(x).toFixed(d);
