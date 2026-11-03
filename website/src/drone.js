// Procedural X8-class flying wing, built from code (teardown rule: geometry comes from the numbers, not from a mesh file).
// Frame: X starboard, Y up, Z aft (nose points to -Z). Planform mirrors src/flockmap/viz3d.py (approximate model, not a CAD copy).
import * as THREE from 'three';

export const HALF = 1.06;
const ROOT_LE = 0.2, ROOT_TE = -0.32, TIP_LE = -0.25, TIP_TE = -0.5;
const le = (s) => ROOT_LE + (TIP_LE - ROOT_LE) * s;       // forward x of leading edge, s = |y| / HALF
const te = (s) => ROOT_TE + (TIP_TE - ROOT_TE) * s;
const chordAt = (s) => le(s) - te(s);
const yt = (xi, s) => {
  const t = 0.115 - 0.03 * s;
  return 5 * t * chordAt(s) * (0.2969 * Math.sqrt(xi) - 0.126 * xi - 0.3516 * xi * xi + 0.2843 * xi ** 3 - 0.1036 * xi ** 4);
};
const XI_H = 0.78;           // hinge line (fraction of chord)
const S_E0 = 0.22, S_E1 = 0.92;   // elevon span stations

const INK = 0x10151b;

// ----------------------------------------------------------------------- surfaces
function surface(sgn, s0, s1, xi0, xi1, mode, nS = 10, nC = 16) {
  const cols = mode === 'wrap' ? nC * 2 : nC;
  const pos = [];
  for (let i = 0; i <= nS; i++) {
    const s = s0 + ((s1 - s0) * i) / nS;
    for (let j = 0; j <= cols; j++) {
      const u = j / cols;
      let xi, ys;
      if (mode === 'up') { xi = xi0 + (xi1 - xi0) * u; ys = 1; }
      else if (mode === 'lo') { xi = xi0 + (xi1 - xi0) * u; ys = -1; }
      else if (u <= 0.5) { xi = xi0 + (xi1 - xi0) * (u * 2); ys = 1; }
      else { xi = xi1 - (xi1 - xi0) * ((u - 0.5) * 2); ys = -1; }
      const xf = le(s) - xi * chordAt(s);
      pos.push(sgn * s * HALF, ys * yt(xi, s), -xf);
    }
  }
  const idx = [];
  const W = cols + 1;
  for (let i = 0; i < nS; i++) for (let j = 0; j < cols; j++) {
    const a = i * W + j, b = a + 1, c = a + W, d = c + 1;
    idx.push(a, c, b, b, c, d);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  if (mode !== 'wrap') {                       // make the outward normal match the side
    g.computeVertexNormals();
    const n = g.getAttribute('normal');
    const mid = Math.floor((nS / 2) * W + cols / 2);
    const wantUp = mode === 'up';
    if ((n.getY(mid) > 0) !== wantUp) { const ix = g.index.array; for (let k = 0; k < ix.length; k += 3) { const t = ix[k + 1]; ix[k + 1] = ix[k + 2]; ix[k + 2] = t; } g.index.needsUpdate = true; }
  }
  g.computeVertexNormals();
  return g;
}

function merge(geos) {
  const pos = [], idx = [];
  let off = 0;
  for (const g of geos) {
    const p = g.getAttribute('position');
    for (let i = 0; i < p.count; i++) pos.push(p.getX(i), p.getY(i), p.getZ(i));
    for (const k of g.index.array) idx.push(k + off);
    off += p.count;
  }
  const m = new THREE.BufferGeometry();
  m.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  m.setIndex(idx);
  m.computeVertexNormals();
  return m;
}

function podHalf(top) {
  const prof = [[0, -0.26], [0.03, -0.255], [0.055, -0.23], [0.072, -0.19], [0.082, -0.12], [0.085, -0.02], [0.084, 0.1], [0.078, 0.22], [0.06, 0.34], [0.042, 0.41], [0.035, 0.44]]
    .map(([r, z]) => new THREE.Vector2(r, z));
  const g = new THREE.LatheGeometry(prof, 40, top ? Math.PI / 2 : -Math.PI / 2, Math.PI);
  g.rotateX(Math.PI / 2);
  g.scale(1, 0.92, 1);
  g.translate(0, 0.004, 0);
  return g;
}

function winglet(sgn) {
  const sh = new THREE.Shape();
  sh.moveTo(0.27, 0); sh.lineTo(0.5, 0); sh.lineTo(0.56, 0.15); sh.lineTo(0.37, 0.15); sh.closePath();
  const g = new THREE.ExtrudeGeometry(sh, { depth: 0.012, bevelEnabled: false });
  g.rotateY(-Math.PI / 2);
  g.translate(sgn * HALF, 0, 0);
  return g;
}

// ----------------------------------------------------------------------- materials
export function makeMaterials() {
  const foam = () => new THREE.MeshPhysicalMaterial({ color: 0xf1f1ed, roughness: 0.62, metalness: 0, clearcoat: 0.12, clearcoatRoughness: 0.6 });
  const foamIn = () => new THREE.MeshStandardMaterial({ color: 0xcfd2cc, roughness: 0.95, side: THREE.BackSide });
  const carbon = () => new THREE.MeshStandardMaterial({ color: 0x1b1e23, roughness: 0.38, metalness: 0.35 });
  const metal = () => new THREE.MeshStandardMaterial({ color: 0x9aa0a8, roughness: 0.34, metalness: 1 });
  const pcb = () => new THREE.MeshStandardMaterial({ color: 0x24382f, roughness: 0.55, metalness: 0.1 });
  const batt = () => new THREE.MeshStandardMaterial({ color: 0x20252c, roughness: 0.5, metalness: 0.15 });
  const accent = () => new THREE.MeshStandardMaterial({ color: 0xe8470f, roughness: 0.45 });
  const lens = () => new THREE.MeshPhysicalMaterial({ color: 0x07090c, roughness: 0.08, metalness: 0.6, clearcoat: 1 });
  return { foam, foamIn, carbon, metal, pcb, batt, accent, lens };
}

// ----------------------------------------------------------------------- the drone
export function createDrone() {
  const M = makeMaterials();
  const root = new THREE.Group();
  const parts = {};
  const lineMat = new THREE.LineBasicMaterial({ color: INK, transparent: true, opacity: 0.38 });

  const make = (id, name) => { const g = new THREE.Group(); g.name = id; root.add(g); parts[id] = { id, name, group: g, meshes: [], base: new THREE.Vector3(), dir: new THREE.Vector3(), t0: 0, t1: 1 }; return parts[id]; };
  const add = (part, geo, mat, { outline = true, shadow = true, angle = 35 } = {}) => {
    const m = new THREE.Mesh(geo, mat); m.castShadow = shadow; m.receiveShadow = true; part.group.add(m); part.meshes.push(m);
    if (outline) { const l = new THREE.LineSegments(new THREE.EdgesGeometry(geo, angle), lineMat); part.group.add(l); }
    return m;
  };
  const shell = (part, geos, up) => {
    const g = merge(geos);
    add(part, g, M.foam(), { angle: 28 });
    const inner = new THREE.Mesh(g, M.foamIn()); part.group.add(inner);
  };

  // ---- top & bottom shells
  const top = make('top', 'Upper shell'), bot = make('bottom', 'Lower shell');
  const shellPatches = (mode) => {
    const out = [];
    for (const sgn of [1, -1]) {
      out.push(surface(sgn, 0, S_E0, 0, 1, mode, 4, 18));
      out.push(surface(sgn, S_E0, S_E1, 0, XI_H, mode, 10, 18));
      out.push(surface(sgn, S_E1, 1, 0, 1, mode, 3, 18));
    }
    return out;
  };
  shell(top, shellPatches('up'), true);
  shell(bot, shellPatches('lo'), false);
  add(top, podHalf(true), M.foam(), { angle: 40 });
  const podTopInner = new THREE.Mesh(podHalf(true), M.foamIn()); top.group.add(podTopInner);
  add(bot, podHalf(false), M.foam(), { angle: 40 });
  const podBotInner = new THREE.Mesh(podHalf(false), M.foamIn()); bot.group.add(podBotInner);
  const hatch = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.005, 0.16), M.accent());
  hatch.position.set(0, 0.0785, -0.12); hatch.rotation.x = -0.1; hatch.castShadow = true; top.group.add(hatch); top.meshes.push(hatch);

  // ---- spar (30 % chord line, swept)
  const spar = make('spar', 'Carbon spar');
  const pts = [];
  for (let k = -10; k <= 10; k++) { const s = Math.abs(k) / 10; pts.push(new THREE.Vector3((k / 10) * HALF * 0.96, 0, -(le(s * 0.96) - 0.3 * chordAt(s * 0.96)))); }
  add(spar, new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.01), 90, 0.009, 10), M.carbon(), { outline: false });
  for (const sgn of [-1, 1]) for (const s of [0.3, 0.62]) {              // two ribs per side
    const c = chordAt(s) * 0.62;
    const rib = new THREE.Mesh(new THREE.BoxGeometry(0.006, yt(0.3, s) * 1.8, c), M.carbon());
    rib.position.set(sgn * s * HALF, 0, -(le(s) - 0.32 * chordAt(s)) + c * 0.05); rib.castShadow = true; spar.group.add(rib); spar.meshes.push(rib);
  }

  // ---- elevons + servos
  const ev = make('elevons', 'Elevons');
  const elevonPivots = {};
  for (const sgn of [1, -1]) {
    const sMid = (S_E0 + S_E1) / 2;
    const pivot = new THREE.Vector3(sgn * sMid * HALF, 0, -(le(sMid) - XI_H * chordAt(sMid)));
    const g = surface(sgn, S_E0, S_E1, XI_H, 1, 'wrap', 8, 8);
    g.translate(-pivot.x, -pivot.y, -pivot.z);
    const holder = new THREE.Group(); holder.position.copy(pivot); ev.group.add(holder);
    const mat = M.foam(); mat.side = THREE.DoubleSide;
    const m = new THREE.Mesh(g, mat); m.castShadow = true; m.receiveShadow = true; holder.add(m); ev.meshes.push(m);
    holder.add(new THREE.LineSegments(new THREE.EdgesGeometry(g, 28), lineMat));
    elevonPivots[sgn] = holder;
  }
  const sv = make('servos', 'Servos');
  for (const sgn of [-1, 1]) {
    const s = 0.57;
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.016, 0.026), M.batt());
    body.position.set(sgn * s * HALF, 0, -(le(s) - 0.66 * chordAt(s))); body.castShadow = true; sv.group.add(body); sv.meshes.push(body);
    const arm = new THREE.Mesh(new THREE.BoxGeometry(0.004, 0.012, 0.05), M.accent());
    arm.position.set(sgn * s * HALF, 0.003, -(le(s) - 0.74 * chordAt(s))); sv.group.add(arm); sv.meshes.push(arm);
  }

  // ---- winglets
  const wl = make('winglets', 'Winglets');
  for (const sgn of [1, -1]) {
    const g = winglet(sgn);
    const m = add(wl, g, M.foam(), { angle: 30 }); m.material.side = THREE.DoubleSide;
    const cap = new THREE.Mesh(new THREE.BoxGeometry(0.014, 0.03, 0.19), M.accent());
    cap.position.set(sgn * (HALF + 0.006), 0.135, 0.465); cap.castShadow = true; wl.group.add(cap); wl.meshes.push(cap);
  }

  // ---- battery
  const bt = make('battery', '6S 10 Ah pack');
  const cellMat = M.batt();
  for (let i = 0; i < 6; i++) {
    const c = new THREE.Mesh(new THREE.BoxGeometry(0.066, 0.052, 0.022), cellMat);
    c.position.set(0, 0, -0.17 + i * 0.026); c.castShadow = true; bt.group.add(c); bt.meshes.push(c);
  }
  const wrap = new THREE.Mesh(new THREE.BoxGeometry(0.069, 0.003, 0.15), M.accent()); wrap.position.set(0, 0.0265, -0.095); bt.group.add(wrap); bt.meshes.push(wrap);
  bt.group.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(0.068, 0.054, 0.156)), lineMat)).position.set(0, 0, -0.095);

  // ---- avionics
  const av = make('avionics', 'Flight computer');
  const fc = new THREE.Mesh(new THREE.BoxGeometry(0.052, 0.006, 0.052), M.pcb()); fc.position.set(0, -0.01, 0.1); av.group.add(fc); av.meshes.push(fc);
  const radio = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.012, 0.03), M.carbon()); radio.position.set(0, 0.004, 0.1); av.group.add(radio); av.meshes.push(radio);
  const gps = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.008, 28), M.metal()); gps.position.set(0, 0.052, 0.18); gps.castShadow = true; av.group.add(gps); av.meshes.push(gps);
  const gpsMast = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.004, 0.05, 10), M.carbon()); gpsMast.position.set(0, 0.027, 0.18); av.group.add(gpsMast);
  const wire = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([new THREE.Vector3(0, -0.01, 0.12), new THREE.Vector3(0.2, -0.015, 0.14), new THREE.Vector3(0.45, -0.014, 0.1), new THREE.Vector3(0.6, -0.01, -0.02)]), 40, 0.0035, 6), M.carbon());
  av.group.add(wire); av.meshes.push(wire);

  // ---- camera (nadir)
  const cam = make('camera', 'Mapping camera');
  const body = new THREE.Mesh(new THREE.BoxGeometry(0.078, 0.052, 0.058), M.carbon()); body.position.set(0, -0.092, -0.12); body.castShadow = true; cam.group.add(body); cam.meshes.push(body);
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.024, 0.04, 28), M.metal()); barrel.position.set(0, -0.138, -0.12); cam.group.add(barrel); cam.meshes.push(barrel);
  const glass = new THREE.Mesh(new THREE.CylinderGeometry(0.017, 0.017, 0.004, 28), M.lens()); glass.position.set(0, -0.16, -0.12); cam.group.add(glass); cam.meshes.push(glass);
  cam.group.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(0.078, 0.052, 0.058)), lineMat)).position.set(0, -0.092, -0.12);

  // ---- motor + prop
  const mo = make('motor', 'Motor and ESC');
  const can = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.06, 36), M.metal()); can.rotation.x = Math.PI / 2; can.position.set(0, 0, 0.47); can.castShadow = true; mo.group.add(can); mo.meshes.push(can);
  const bell = new THREE.Mesh(new THREE.CylinderGeometry(0.033, 0.033, 0.022, 36), M.carbon()); bell.rotation.x = Math.PI / 2; bell.position.set(0, 0, 0.51); mo.group.add(bell); mo.meshes.push(bell);
  const esc = new THREE.Mesh(new THREE.BoxGeometry(0.036, 0.016, 0.06), M.carbon()); esc.position.set(0, -0.018, 0.3); mo.group.add(esc); mo.meshes.push(esc);
  for (let i = 0; i < 5; i++) { const fin = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.003, 0.05), M.metal()); fin.position.set(0, -0.03 - i * 0.0045, 0.3); mo.group.add(fin); }

  const pr = make('prop', 'Pusher propeller');
  const spin = new THREE.Group(); spin.position.set(0, 0, 0.545); pr.group.add(spin);
  const bladeMat = new THREE.MeshStandardMaterial({ color: 0x15181c, roughness: 0.5, side: THREE.DoubleSide });
  for (const s of [1, -1]) {
    const sh = new THREE.Shape(); sh.moveTo(0.02, -0.016); sh.lineTo(0.14, -0.026); sh.lineTo(0.15, -0.004); sh.lineTo(0.14, 0.014); sh.lineTo(0.02, 0.014); sh.closePath();
    const e = new THREE.ExtrudeGeometry(sh, { depth: 0.003, bevelEnabled: false });
    const bm = new THREE.Mesh(e, bladeMat); bm.rotation.z = s > 0 ? Math.PI / 2 : -Math.PI / 2; bm.rotation.x = 0.25 * s; bm.castShadow = true; spin.add(bm); pr.meshes.push(bm);
  }
  const spinner = new THREE.Mesh(new THREE.ConeGeometry(0.027, 0.06, 28), M.accent()); spinner.rotation.x = -Math.PI / 2; spinner.position.set(0, 0, 0.02); spin.add(spinner); pr.meshes.push(spinner);
  const blur = new THREE.Mesh(new THREE.CircleGeometry(0.15, 48), new THREE.MeshBasicMaterial({ color: 0x20252c, transparent: true, opacity: 0.1, side: THREE.DoubleSide, depthWrite: false }));
  blur.position.set(0, 0, 0.003); spin.add(blur);

  // ---- clone materials per part so highlighting is independent
  for (const p of Object.values(parts)) for (const m of p.meshes) m.material = m.material.clone();

  // ---- explode choreography (offsets in metres; windows are fractions of the scroll progress)
  const E = (id, dir, t0, t1) => { const p = parts[id]; p.dir.set(...dir); p.t0 = t0; p.t1 = t1; };
  E('top', [0, 0.95, -0.15], 0.00, 0.20);
  E('bottom', [0, -0.55, 0.1], 0.08, 0.28);
  E('spar', [0, 0.22, 0], 0.26, 0.40);
  E('elevons', [0, -0.1, 0.38], 0.34, 0.48);
  E('servos', [0, 0.44, 0.1], 0.34, 0.48);
  E('battery', [0, 0.46, -0.52], 0.44, 0.58);
  E('avionics', [0, 0.52, 0.28], 0.52, 0.66);
  E('camera', [0, -0.95, -0.2], 0.60, 0.74);
  E('motor', [0, 0.1, 0.68], 0.68, 0.82);
  E('prop', [0, 0.1, 1.35], 0.74, 0.90);
  E('winglets', [0.85, 0.3, 0.1], 0.82, 0.96);

  const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
  const state = { explode: 0, active: [], bank: 0, elev: 0, spin: 0 };
  const accent = new THREE.Color(0xe8470f);

  function setExplode(t) {
    state.explode = t;
    for (const p of Object.values(parts)) {
      const k = THREE.MathUtils.clamp((t - p.t0) / (p.t1 - p.t0), 0, 1);
      p.group.position.copy(p.dir).multiplyScalar(ease(k));
    }
  }
  function setActive(ids) {
    state.active = ids;
    for (const p of Object.values(parts)) {
      const on = ids.includes(p.id);
      for (const m of p.meshes) {
        const mat = m.material; if (!mat.emissive) continue;
        if (mat.userData.baseEmissive === undefined) mat.userData.baseEmissive = mat.emissive.clone();
        mat.emissive.copy(on ? accent : mat.userData.baseEmissive).multiplyScalar(on ? 0.16 : 1);
      }
    }
  }
  function setBank(deg, elevDeg = null) {
    root.rotation.z = -THREE.MathUtils.degToRad(deg);
    const d = elevDeg === null ? (deg / 35) * 14 : elevDeg;          // illustrative deflection, drawn proportional to command
    elevonPivots[1].rotation.x = -THREE.MathUtils.degToRad(d);
    elevonPivots[-1].rotation.x = THREE.MathUtils.degToRad(d);
  }
  function tick(dt, rate = 26) { spin.rotation.z += dt * rate; }

  // screen anchors for callouts (local to each part group)
  const anchors = {
    top: new THREE.Vector3(0.5, 0.03, 0.15), bottom: new THREE.Vector3(-0.55, -0.03, 0.25), spar: new THREE.Vector3(0.62, 0, 0.08),
    elevons: new THREE.Vector3(0.62, 0, 0.42), servos: new THREE.Vector3(-0.6, 0, 0.1), battery: new THREE.Vector3(0, 0.03, -0.1),
    avionics: new THREE.Vector3(0, 0.05, 0.14), camera: new THREE.Vector3(0, -0.16, -0.12), motor: new THREE.Vector3(0, 0, 0.5),
    prop: new THREE.Vector3(0.1, 0.1, 0.55), winglets: new THREE.Vector3(1.06, 0.12, 0.45),
  };

  return { root, parts, setExplode, setActive, setBank, tick, anchors, spin, elevonPivots };
}
