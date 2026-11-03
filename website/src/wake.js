// Trailing-vortex visualisation driven by the same Lamb-Oseen model as the study (src/flockmap/aero.py family).
// Particles live on rings around each rolled-up tip vortex; their swirl angle is the physical omega(r) * (distance / V),
// so the geometry is exact while the flow-through speed is slowed for the eye.
import * as THREE from 'three';
import { AC, WK, gamma, coreRadius, upwash } from './physics.js';

const N_PER = 1500;
const L = 9.0;                       // visible wake length, m
const Z0 = 0.48;                     // release plane just aft of the trailing edge (Z aft)

function softSprite() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const x = c.getContext('2d'); const g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.45, 'rgba(255,255,255,0.55)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

export function createWake() {
  const group = new THREE.Group();
  const total = N_PER * 2;
  const pos = new Float32Array(total * 3), col = new Float32Array(total * 4);
  const seed = [];
  let k = 0;
  const rnd = (() => { let s = 7; return () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646; })();
  for (let v = 0; v < 2; v++) for (let i = 0; i < N_PER; i++, k++) {
    seed.push({ v, r0: 0.03 + Math.pow(rnd(), 1.7) * 0.5, th0: rnd() * Math.PI * 2, s0: rnd() });
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 4));
  const mat = new THREE.PointsMaterial({ size: 0.055, map: softSprite(), vertexColors: true, transparent: true, depthWrite: false, sizeAttenuation: true });
  const pts = new THREE.Points(geo, mat); pts.frustumCulled = false; group.add(pts);

  // upwash heat-plane at the follower station
  const NY = 90, NZ = 28;
  const pg = new THREE.PlaneGeometry(8, 2.4, NY - 1, NZ - 1);
  const pc = new Float32Array(NY * NZ * 4);
  pg.setAttribute('color', new THREE.BufferAttribute(pc, 4));
  const plane = new THREE.Mesh(pg, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, side: THREE.DoubleSide, depthWrite: false }));
  group.add(plane);

  let params = { dxMeters: 3 * AC.b, speed: 2.6, dark: false };
  const acc = new THREE.Color(0xe8470f), inkL = new THREE.Color(0x2a3440), inkD = new THREE.Color(0xa9b7c6);

  function paintPlane() {
    const rc = coreRadius(params.dxMeters);
    const p = pg.getAttribute('position'), c = pg.getAttribute('color');
    const neg = params.dark ? inkD : inkL;
    for (let i = 0; i < p.count; i++) {
      const y = p.getX(i), z = p.getY(i);
      const w = upwash(y, z, rc);
      const m = Math.min(1, Math.abs(w) / 0.55);
      const col = w >= 0 ? acc : neg;
      c.setXYZW(i, col.r, col.g, col.b, 0.5 * Math.pow(m, 0.8));
    }
    c.needsUpdate = true;
  }
  plane.position.set(0, 0, params.dxMeters);

  function set(p) {
    const dxChanged = p.dxMeters !== undefined && p.dxMeters !== params.dxMeters;
    const darkChanged = p.dark !== undefined && p.dark !== params.dark;
    Object.assign(params, p);
    if (dxChanged || darkChanged || !set._init) { plane.position.z = params.dxMeters + 0.1; paintPlane(); set._init = true; }
  }

  const G0 = gamma(), V = AC.va, yv = AC.b0 / 2, rc0 = WK.rc0Frac * AC.b;
  let low = false;
  const setLow = (v) => { low = v; };
  function update(t) {
    const p = geo.getAttribute('position'), c = geo.getAttribute('color');
    for (let i = 0; i < total; i++) {
      const sd = seed[i];
      const s = (sd.s0 + t * params.speed / L) % 1;
      const dist = s * L;
      const rc = Math.sqrt(rc0 * rc0 + 4 * WK.nuEff * (dist / V));
      const r = sd.r0 * Math.sqrt(rc / rc0) * 0.9;
      const om = (G0 / (2 * Math.PI * r * r)) * (1 - Math.exp(-(r * r) / (rc * rc)));
      const sign = sd.v === 0 ? 1 : -1;                       // v0 = starboard vortex (+y), v1 = port
      const th = sd.th0 + sign * om * (dist / V);
      const y = (sd.v === 0 ? yv : -yv) + r * Math.cos(th);
      p.setXYZ(i, y, r * Math.sin(th) + 0.0, Z0 + dist);
      const fade = Math.min(1, s * 8) * (1 - Math.pow(s, 3));
      const core = 1 - Math.min(1, r / 0.55);
      c.setXYZW(i, acc.r, acc.g, acc.b, fade * (0.28 + 0.5 * core));
    }
    p.needsUpdate = true; c.needsUpdate = true;
  }

  return { group, set, update, plane, paintPlane };
}
