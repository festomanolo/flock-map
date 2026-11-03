import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { createDrone } from './drone.js';
import { createWake } from './wake.js';
import { AC } from './physics.js';

const damp = (a, b, k, dt) => a + (b - a) * (1 - Math.exp(-k * dt));

export function createScene(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.VSMShadowMap;
  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.75;

  const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 200);

  const sun = new THREE.DirectionalLight(0xfff4e6, 2.1);
  sun.position.set(-4, 7, 5); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -6, right: 6, top: 6, bottom: -6, near: 0.5, far: 24 });
  sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.025; sun.shadow.radius = 9; sun.shadow.blurSamples = 16;
  scene.add(sun);
  scene.add(new THREE.HemisphereLight(0xdfe8f4, 0x8a8f96, 0.55));

  // ground: soft shadow catcher + faint studio rings
  const catcher = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.ShadowMaterial({ opacity: 0.2, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
  catcher.rotation.x = -Math.PI / 2; catcher.receiveShadow = true; scene.add(catcher);
  const rings = new THREE.Mesh(new THREE.PlaneGeometry(26, 26), new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 }));
  rings.rotation.x = -Math.PI / 2; scene.add(rings);
  function paintRings(dark) {
    const c = document.createElement('canvas'); c.width = c.height = 1024; const x = c.getContext('2d');
    const col = dark ? '233,237,241' : '17,21,26';
    for (let i = 1; i <= 8; i++) { x.beginPath(); x.arc(512, 512, i * 62, 0, Math.PI * 2); x.strokeStyle = `rgba(${col},${0.10 - i * 0.008})`; x.lineWidth = i % 4 === 0 ? 2 : 1; x.stroke(); }
    x.strokeStyle = `rgba(${col},0.07)`; x.lineWidth = 1; x.beginPath(); x.moveTo(512, 0); x.lineTo(512, 1024); x.moveTo(0, 512); x.lineTo(1024, 512); x.stroke();
    const g = x.createRadialGradient(512, 512, 120, 512, 512, 512); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,1)');
    x.globalCompositeOperation = 'destination-out'; x.fillStyle = g; x.fillRect(0, 0, 1024, 1024);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; rings.material.map?.dispose(); rings.material.map = t; rings.material.needsUpdate = true;
  }

  const drone = createDrone(); scene.add(drone.root);
  const followers = [createDrone(), createDrone()]; followers.forEach((f) => { f.root.visible = false; scene.add(f.root); });
  const wake = createWake(); wake.group.visible = false; scene.add(wake.group);

  // ---- view state (targets set by scroll chapters, damped into the live camera)
  const view = { theta: 2.4, phi: 1.2, r: 7.2, tx: 0, ty: 0, tz: 0.1, shiftX: 0, groundY: -1.4, alpha: 1, mode: 'single', shiftY: 0,
    fx: 0.85, dx: 3 * AC.b, bank: 0, float: 1, spinRate: 26 };
  const cur = { ...view };
  const orbit = { theta: 0, phi: 0, vt: 0, vp: 0, drag: false };
  let size = { w: 1, h: 1 };
  let dark = false;

  // quality tiers: 0 full, 1 cheaper shadows and pixel ratio, 2 no shadows, half the wake particles
  let tier = 0;
  const TIER_DPR = [2, 1.25, 1];
  function setQuality(t) {
    tier = Math.min(2, t);
    if (tier === 1) { renderer.shadowMap.type = THREE.PCFSoftShadowMap; sun.shadow.mapSize.set(1024, 1024); sun.shadow.map?.dispose(); sun.shadow.map = null; }
    if (tier === 2) { renderer.shadowMap.enabled = false; catcher.visible = false; }
    wake.setLow(tier >= 2);
    scene.traverse((o) => { if (o.material) o.material.needsUpdate = true; });
    resize();
  }

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    size = { w, h };
    renderer.setPixelRatio(Math.min(devicePixelRatio, TIER_DPR[tier]));
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
  }

  function setTheme(isDark) {
    dark = isDark; paintRings(isDark);
    catcher.material.opacity = isDark ? 0.45 : 0.2;
    wake.set({ dark: isDark });
  }

  const tmp = new THREE.Vector3();
  function project(v3, part) {
    tmp.copy(v3);
    if (part) { part.group.updateWorldMatrix(true, false); tmp.applyMatrix4(part.group.matrixWorld); }
    tmp.project(camera);
    return { x: (tmp.x * 0.5 + 0.5) * size.w, y: (-tmp.y * 0.5 + 0.5) * size.h, z: tmp.z };
  }

  let time = 0, simTime = 0;
  function frame(dt, reduced) {
    time += dt; if (!reduced) simTime += dt;
    for (const k of ['theta', 'phi', 'r', 'tx', 'ty', 'tz', 'shiftX', 'shiftY', 'groundY', 'alpha', 'fx', 'dx', 'bank', 'float']) cur[k] = damp(cur[k], view[k], reduced ? 60 : 5.5, dt);
    cur.mode = view.mode;
    // orbit inertia
    if (!orbit.drag) { orbit.theta += orbit.vt * dt; orbit.phi += orbit.vp * dt; orbit.vt *= Math.exp(-3 * dt); orbit.vp *= Math.exp(-3 * dt); }
    if (!orbit.drag) { orbit.theta *= Math.exp(-0.45 * dt); orbit.phi *= Math.exp(-0.45 * dt); }
    orbit.phi = THREE.MathUtils.clamp(orbit.phi, -0.6, 0.6);

    const th = cur.theta + orbit.theta, ph = THREE.MathUtils.clamp(cur.phi + orbit.phi, 0.25, 2.2);
    camera.position.set(cur.tx + cur.r * Math.sin(ph) * Math.sin(th), cur.ty + cur.r * Math.cos(ph), cur.tz + cur.r * Math.sin(ph) * Math.cos(th));
    camera.lookAt(cur.tx, cur.ty, cur.tz);
    camera.setViewOffset(size.w, size.h, -cur.shiftX * size.w, cur.shiftY * size.h, size.w, size.h);

    // drone pose
    const bob = reduced ? 0 : Math.sin(time * 0.9) * 0.025 * cur.float;
    drone.root.position.y = bob;
    drone.setBank(cur.bank + (reduced ? 0 : Math.sin(time * 0.6) * 2.2 * cur.float));
    drone.tick(reduced ? 0 : dt, view.spinRate);
    const formation = cur.mode === 'formation';
    followers.forEach((f, i) => {
      f.root.visible = formation; if (!formation) return;
      const sgn = i === 0 ? 1 : -1;
      f.root.position.set(sgn * cur.fx * AC.b, bob * (i ? -1 : 1), cur.dx + 0.0);
      f.setBank(0); f.tick(reduced ? 0 : dt, 26);
    });
    wake.group.visible = formation;
    if (formation) { wake.set({ dxMeters: cur.dx }); wake.update(simTime); }

    catcher.position.y = rings.position.y = cur.groundY;
    rings.position.y += 0.002;
    sun.position.set(-4 + cur.tx, 7, 5 + cur.tz); sun.target.position.set(cur.tx, 0, cur.tz); sun.target.updateMatrixWorld();
    sun.shadow.camera.left = -(formation ? 9 : 4); sun.shadow.camera.right = formation ? 9 : 4; sun.shadow.camera.top = formation ? 9 : 4; sun.shadow.camera.bottom = -(formation ? 9 : 4); sun.shadow.camera.updateProjectionMatrix();
    canvas.style.opacity = cur.alpha.toFixed(3);
    if (cur.alpha > 0.01) renderer.render(scene, camera);
  }

  return { renderer, scene, camera, drone, followers, wake, view, cur, orbit, resize, frame, project, setTheme, setQuality, get tier() { return tier; } };
}
