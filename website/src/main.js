import './styles.css';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { createScene } from './scene.js';
import { AC, BAT, CAM, flight, energy, rollResponse, camera as camGeo, gamma, followerUpwash, upwash, coreRadius, fmt } from './physics.js';

gsap.registerPlugin(ScrollTrigger);
gsap.ticker.lagSmoothing(0);          // slow frames must not stretch entrance animations
document.documentElement.classList.add('js');
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const mobile = () => matchMedia('(max-width: 900px)').matches;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));

// ------------------------------------------------------------------------------------------- theme
const root = document.documentElement;
const themeBtn = $('#themeBtn');
const isDark = () => root.dataset.theme === 'dark' || (root.dataset.theme === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
try { const t = localStorage.getItem('fm-theme'); if (t === 'dark' || t === 'light') root.dataset.theme = t; } catch {}
const labelTheme = () => { themeBtn.textContent = isDark() ? 'Light' : 'Dark'; };
labelTheme();

// ------------------------------------------------------------------------------------------- scene
const canvas = $('#gl');
const S = createScene(canvas);
const resizeAll = () => { S.resize(); redrawAll(); };
S.setTheme(isDark());
themeBtn.addEventListener('click', () => {
  root.dataset.theme = isDark() ? 'light' : 'dark';
  try { localStorage.setItem('fm-theme', root.dataset.theme); } catch {}
  labelTheme(); S.setTheme(isDark()); redrawAll();
});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { S.setTheme(isDark()); labelTheme(); redrawAll(); });

// ------------------------------------------------------------------------------------------- camera presets (one table, scroll picks the row)
const PRESET = {
  hero: () => ({ theta: 2.55, phi: 1.2, r: mobile() ? 7.4 : 4.7, tx: 0, ty: 0, tz: 0.05, shiftX: mobile() ? 0 : 0.2, shiftY: mobile() ? 0.17 : 0, groundY: -1.15, alpha: 1, mode: 'single', bank: 0, float: 1 }),
  teardown: () => ({ theta: 2.35, phi: 1.08, r: 5.6, tx: 0, ty: 0.05, tz: 0.3, shiftX: mobile() ? 0 : 0.17, shiftY: mobile() ? 0.12 : 0, groundY: -1.55, alpha: 1, mode: 'single', bank: 0, float: 0 }),
  off: () => ({ alpha: 0 }),
  control: () => ({ theta: 0.28, phi: 1.32, r: 5.6, tx: 0, ty: 0, tz: 0.05, shiftX: mobile() ? 0 : 0.22, shiftY: mobile() ? -0.2 : 0, groundY: -1.05, alpha: 1, mode: 'single', float: 0 }),
  wake: () => ({ theta: -0.62, phi: 1.02, r: mobile() ? 21 : 14.5, tx: 0, ty: 0, tz: 3.2, shiftX: mobile() ? 0 : 0.2, shiftY: mobile() ? -0.2 : 0, groundY: -1.6, alpha: 1, mode: 'formation', float: 0.6 }),
};
function applyPreset(name) { Object.assign(S.view, PRESET[name]()); S.view.preset = name; }
applyPreset('hero');
Object.assign(S.cur, S.view);

const sections = [['#hero', 'hero'], ['#teardown', 'teardown'], ['#lift', 'off'], ['#control', 'control'], ['#energy', 'off'], ['#camera', 'off'], ['#wake', 'wake'], ['#gallery', 'off'], ['#evidence', 'off']];
let lastPreset = 'hero';
function bindPresets() {
  sections.forEach(([sel, name]) => ScrollTrigger.create({
    trigger: sel, start: 'top 55%', end: 'bottom 55%',
    onToggle: (self) => { if (self.isActive) { lastPreset = name; if (name === 'off') S.view.alpha = 0; else applyPreset(name); if (name === 'teardown') tdUpdate(tdProgress); } },
  }));
}

// ------------------------------------------------------------------------------------------- orbit by drag
function bindOrbit(el, guard) {
  let last = null;
  el.addEventListener('pointerdown', (e) => { if (guard && !guard(e)) return; if (e.pointerType === 'mouse' && e.button !== 0) return; S.orbit.drag = true; last = [e.clientX, e.clientY]; el.setPointerCapture?.(e.pointerId); });
  el.addEventListener('pointermove', (e) => {
    if (!S.orbit.drag || !last) return;
    const dx = e.clientX - last[0], dy = e.clientY - last[1]; last = [e.clientX, e.clientY];
    S.orbit.theta -= dx * 0.006; S.orbit.phi -= dy * 0.004; S.orbit.vt = -dx * 0.3; S.orbit.vp = -dy * 0.2;
  });
  const end = () => { S.orbit.drag = false; last = null; };
  el.addEventListener('pointerup', end); el.addEventListener('pointercancel', end);
}
bindOrbit($('#tdStage'));
['#control', '#wake'].forEach((s) => bindOrbit($(s), (e) => !e.target.closest('.panel')));

// ------------------------------------------------------------------------------------------- teardown
const STAGES = [
  { id: ['top'], at: 0.0, name: 'Upper shell', text: 'The outer skin that holds the airfoil shape. Lift it and the equipment bay is open.', anchor: 'top',
    specs: [['Wingspan', '2.12 m', 'MS'], ['Wing area', '0.80 m²', 'MS'], ['Mean chord', `${fmt(AC.chord, 3)} m`, 'DER'], ['Aspect ratio', fmt(AC.AR, 2), 'DER'], ['Leading-edge sweep', 'about 23°', 'MODEL']] },
  { id: ['bottom'], at: 0.13, name: 'Lower shell', text: 'Mirrors the upper shell. Together they set the thickness: about 11.5 % of chord at the root, 8.5 % at the tip.', anchor: 'bottom',
    specs: [['Root thickness', '11.5 %', 'MODEL'], ['Tip thickness', '8.5 %', 'MODEL'], ['Airfoil', 'NACA 4-digit form', 'MODEL']] },
  { id: ['spar'], at: 0.27, name: 'Carbon spar', text: 'A tube along the quarter-chord line carries the bending load of the wing. Ribs keep the shells apart.', anchor: 'spar',
    specs: [['Position', 'about 30 % chord', 'MODEL'], ['Structure data', 'not in the study', 'ASM']] },
  { id: ['elevons', 'servos'], at: 0.37, name: 'Elevons and servos', text: 'Elevons act as ailerons and elevators at once. Moving them in opposite directions rolls the aircraft.', anchor: 'elevons',
    specs: [['Roll derivative', '0.15 /rad', 'MS'], ['Roll time constant', '0.25 s', 'MS'], ['Trim-drag factor', '0.035 /rad²', 'MS'], ['Turn bank, limit', '25°, 35°', 'MS']] },
  { id: ['battery'], at: 0.47, name: 'Battery pack', text: 'Six cells in series hold all the energy. The study keeps a 20 % reserve.', anchor: 'battery',
    specs: [['Cells, capacity', '6S, 10 Ah', 'MS'], ['Energy at 3.7 V a cell', `${fmt(BAT.energyWh, 0)} Wh`, 'DER'], ['Usable (80 %)', `${fmt(BAT.usableWh, 0)} Wh`, 'MS'], ['Internal resistance', '0.020 Ω', 'ASM']] },
  { id: ['avionics'], at: 0.55, name: 'Flight computer', text: 'Flight controller, GPS and radio sit here. Control is a guidance-level NMPC with a relative-degree-3 safety filter.', anchor: 'avionics',
    specs: [['Hotel load', '28 W (12 + 6 + 10)', 'MS'], ['Controller', 'NMPC + HOCBF', 'MODEL']] },
  { id: ['camera'], at: 0.63, name: 'Mapping camera', text: 'A nadir camera takes the survey images. Its optics fix the ground footprint and resolution.', anchor: 'camera',
    specs: [['Image', '5472 × 3648 px', 'MS'], ['Sensor', '13.2 × 8.8 mm', 'MS'], ['Lens', '9 mm', 'MS'], ['Pixel size on ground, 120 m', `${fmt(camGeo(120).gsd * 100, 1)} cm`, 'DER'], ['Overlap fwd, side', '75 %, 65 %', 'MS']] },
  { id: ['motor', 'prop'], at: 0.72, name: 'Motor and pusher propeller', text: 'Drives the aircraft from behind. The study uses one constant efficiency for the whole chain.', anchor: 'prop',
    specs: [['Propulsive efficiency', '0.68', 'MS'], ['Cruise speed', '18 m/s', 'MS'], ['Speed range', '12 to 26 m/s', 'MS'], ['Real efficiency varies with load', 'open issue', 'ASM']] },
  { id: ['winglets'], at: 0.85, name: 'Winglets', text: 'Upturned plates at each tip. In the wake model each tip vortex rolls up a fixed distance inboard of the tips.', anchor: 'winglets',
    specs: [['Vortex spacing πb/4', `${fmt(AC.b0, 2)} m`, 'MS'], ['Core radius 0.05 b', `${fmt(0.05 * AC.b, 3)} m`, 'MS'], ['Circulation at 18 m/s', `${fmt(gamma(), 2)} m²/s`, 'DER']] },
];
const stopsEl = $('#stops');
STAGES.forEach((s, i) => {
  const li = document.createElement('li'); const b = document.createElement('button'); b.type = 'button'; b.textContent = s.name;
  b.addEventListener('click', () => scrollToStage(i)); li.append(b); stopsEl.append(li);
});
const stopBtns = $$('button', stopsEl);
const card = $('#card'), cardName = $('#cardName'), cardText = $('#cardText'), cardSpecs = $('#cardSpecs');
const tdSection = $('#teardown');
let tdProgress = 0, tdTarget = 0, tdActive = -1;

function scrollToStage(i) {
  const range = tdSection.offsetHeight - innerHeight;
  const p = Math.min(0.97, STAGES[i].at / 0.9 + 0.025);
  window.scrollTo({ top: tdSection.offsetTop + p * range, behavior: reduced ? 'auto' : 'smooth' });
}
function showStage(i) {
  if (i === tdActive) return; tdActive = i;
  const s = STAGES[i];
  stopBtns.forEach((b, k) => { b.classList.toggle('on', k === i); b.setAttribute('aria-current', k === i ? 'step' : 'false'); });
  S.drone.setActive(s.id);
  gsap.fromTo(card, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: reduced ? 0 : 0.5, ease: 'expo.out' });
  cardName.textContent = s.name; cardText.textContent = s.text;
  cardSpecs.replaceChildren(...s.specs.map(([k, v, tag]) => { const d = document.createElement('div'); const dt = document.createElement('dt'); dt.textContent = k; const dd = document.createElement('dd'); dd.textContent = v; const t = document.createElement('span'); t.className = `tag ${tag}`; t.textContent = tag; dd.append(t); d.append(dt, dd); return d; }));
}
function tdUpdate(p) {
  tdProgress = p;
  tdTarget = clamp(p / 0.9, 0, 1);
  let idx = 0; STAGES.forEach((s, i) => { if (tdTarget >= s.at) idx = i; });
  showStage(idx);
  $('#tdBar').style.width = `${(p * 100).toFixed(1)}%`;
  if (S.view.preset === 'teardown') { S.view.theta = 2.35 + tdTarget * 0.7; S.view.r = 5.4 + 1.9 * Math.min(1, tdTarget * 1.4); S.view.phi = 1.18 - 0.1 * tdTarget; }
}
ScrollTrigger.create({ trigger: tdSection, start: 'top top', end: 'bottom bottom', onUpdate: (self) => tdUpdate(self.progress), onRefresh: (self) => tdUpdate(self.progress) });
let exCur = 0;

const leader = $('#leaderPath'), leaderDot = $('#leaderDot'), stage = $('#tdStage');
function updateLeader() {
  const sec = tdSection.getBoundingClientRect();
  const inside = sec.top <= 10 && sec.bottom >= innerHeight - 10;
  const s = STAGES[Math.max(0, tdActive)];
  if (!inside || S.cur.alpha < 0.5) { leader.setAttribute('d', ''); leaderDot.setAttribute('r', 0); return; }
  const part = S.drone.parts[s.anchor];
  const a = S.project(S.drone.anchors[s.anchor], part);
  const sr = stage.getBoundingClientRect(), cr = card.getBoundingClientRect();
  const m = mobile();
  const p0 = m ? [cr.left + cr.width / 2, cr.top] : [cr.left, cr.top + 30];
  const mid = m ? [a.x, p0[1] - 30] : [a.x + (a.x < p0[0] ? 40 : -40), p0[1]];
  const rel = (p) => [p[0] - sr.left, p[1] - sr.top];
  const [x0, y0] = rel(p0), [x1, y1] = rel(mid), [x2, y2] = rel([a.x, a.y]);
  leader.setAttribute('d', m ? `M${x0},${y0} L${x2},${y2}` : `M${x0},${y0} L${x1},${y1} L${x2},${y2}`);
  leaderDot.setAttribute('cx', x2); leaderDot.setAttribute('cy', y2); leaderDot.setAttribute('r', 4);
}

// ------------------------------------------------------------------------------------------- 2D chart helpers
const css = () => { const s = getComputedStyle(root); const g = (k) => s.getPropertyValue(k).trim(); return { ink: g('--ink'), muted: g('--muted'), line: g('--line'), strong: g('--line-strong'), accent: g('--accent'), bg: g('--panel-solid') }; };
function prep(c) {
  const r = c.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
  const w = Math.max(20, Math.round(r.width)), h = Math.max(20, Math.round(r.height));
  if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
  const x = c.getContext('2d'); x.setTransform(dpr, 0, 0, dpr, 0, 0); x.clearRect(0, 0, w, h);
  return { x, w, h };
}
function axes(x, w, h, m, xr, yr, xt, yt, col, xl, yl) {
  x.font = '11px "Geist Mono Variable", ui-monospace, monospace'; x.fillStyle = col.muted; x.strokeStyle = col.line; x.lineWidth = 1;
  x.textAlign = 'center'; x.textBaseline = 'top';
  xt.forEach((v) => { const px = m.l + ((v - xr[0]) / (xr[1] - xr[0])) * (w - m.l - m.r); x.beginPath(); x.moveTo(px, m.t); x.lineTo(px, h - m.b); x.stroke(); x.fillText(String(v), px, h - m.b + 6); });
  x.textAlign = 'right'; x.textBaseline = 'middle';
  yt.forEach((v) => { const py = h - m.b - ((v - yr[0]) / (yr[1] - yr[0])) * (h - m.t - m.b); x.beginPath(); x.moveTo(m.l, py); x.lineTo(w - m.r, py); x.stroke(); x.fillText(String(v), m.l - 8, py); });
  x.textAlign = 'right'; x.textBaseline = 'bottom'; x.fillText(xl, w - m.r, h - 2);
  x.textAlign = 'left'; x.textBaseline = 'top'; x.fillText(yl, m.l, 2);
}
const mapper = (w, h, m, xr, yr) => ({ X: (v) => m.l + ((v - xr[0]) / (xr[1] - xr[0])) * (w - m.l - m.r), Y: (v) => h - m.b - ((v - yr[0]) / (yr[1] - yr[0])) * (h - m.t - m.b) });
const dot = (x, px, py, c, r = 6) => { x.fillStyle = c; x.beginPath(); x.arc(px, py, r, 0, 7); x.fill(); x.strokeStyle = 'rgba(255,255,255,.9)'; x.lineWidth = 2; x.beginPath(); x.arc(px, py, r, 0, 7); x.stroke(); };

// ------------------------------------------------------------------------------------------- lift & power
const vLift = $('#vLift'), vEn = $('#vEn');
let V = AC.va;
const liftRead = $('#liftRead');
const mkRead = (el, items) => { el.replaceChildren(...items.map(([k, id, cls]) => { const d = document.createElement('div'); if (cls) d.className = cls; d.innerHTML = `<dt>${k}</dt><dd id="${id}"></dd>`; return d; })); };
mkRead(liftRead, [['Lift coefficient', 'rCL'], ['Lift to drag', 'rLD'], ['Drag', 'rD'], ['Total power', 'rP', 'acc']]);
const setDD = (id, v, u = '') => { const e = document.getElementById(id); e.innerHTML = u ? `${v}<small>${u}</small>` : v; };
let pMin = { V: 14, P: 1e9 }; for (let v = AC.vaMin; v <= AC.vaMax; v += 0.05) { const p = flight(v).pTotal; if (p < pMin.P) pMin = { V: v, P: p }; }
function drawLift() {
  const f = flight(V);
  setDD('rCL', fmt(f.CL, 3)); setDD('rLD', fmt(f.LD, 1)); setDD('rD', fmt(f.D, 2), 'N'); setDD('rP', fmt(f.pTotal, 0), 'W');
  $('#vLiftOut').textContent = `${fmt(V, 1)} m/s`;
  const c = $('#liftChart'); const { x, w, h } = prep(c); const col = css();
  const m = { l: 46, r: 16, t: 28, b: 36 }, xr = [AC.vaMin, AC.vaMax], yr = [0, 360];
  axes(x, w, h, m, xr, yr, [12, 14, 16, 18, 20, 22, 24, 26], [0, 100, 200, 300], col, 'airspeed m/s', 'power W');
  const { X, Y } = mapper(w, h, m, xr, yr);
  const line = (fn, st, lw, dash) => { x.beginPath(); for (let v = xr[0]; v <= xr[1] + 1e-6; v += 0.2) { const px = X(v), py = Y(fn(v)); v === xr[0] ? x.moveTo(px, py) : x.lineTo(px, py); } x.strokeStyle = st; x.lineWidth = lw; x.setLineDash(dash || []); x.stroke(); x.setLineDash([]); };
  line(() => AC.pHotel, col.muted, 1.5, [2, 5]);
  line((v) => flight(v).pShaft, col.muted, 1.5, [7, 5]);
  line((v) => flight(v).pTotal, col.ink, 2.5);
  x.font = '11px "Geist Mono Variable", monospace'; x.fillStyle = col.muted; x.textAlign = 'left'; x.textBaseline = 'bottom';
  x.fillText('hotel load 28 W', X(20.2), Y(AC.pHotel) - 6); x.fillText('propulsion', X(22.4), Y(flight(22.4).pShaft) - 8);
  x.fillStyle = col.ink; x.fillText('total', X(23.6), Y(flight(23.6).pTotal) - 10);
  x.strokeStyle = col.accent; x.lineWidth = 1.5; x.setLineDash([3, 4]); x.beginPath(); x.moveTo(X(V), Y(f.pTotal)); x.lineTo(X(V), h - m.b); x.stroke(); x.setLineDash([]);
  dot(x, X(V), Y(f.pTotal), col.accent);
  x.strokeStyle = col.ink; x.lineWidth = 1.5; x.beginPath(); x.arc(X(pMin.V), Y(pMin.P), 4, 0, 7); x.stroke();
  x.fillStyle = col.ink; x.textAlign = 'left'; x.textBaseline = 'top'; x.fillText(`minimum ${fmt(pMin.P, 0)} W at ${fmt(pMin.V, 1)} m/s`, X(pMin.V) + 10, Y(pMin.P) + 8);
}

// ------------------------------------------------------------------------------------------- energy
const cellsEl = $('#cells');
for (let i = 0; i < 6; i++) { const c = document.createElement('div'); c.className = 'cell-b'; c.innerHTML = '<i></i><i></i>'; cellsEl.append(c); }
function drawEnergy() {
  const e = energy(V);
  $('#enMin').textContent = fmt(e.minutes, 1); $('#enKm').textContent = fmt(e.rangeKm, 1); $('#enV').textContent = fmt(V, 1); $('#vEnOut').textContent = `${fmt(V, 1)} m/s`;
  $('#enWh').textContent = fmt(BAT.usableWh, 0);
  const c = $('#enChart'); const { x, w, h } = prep(c); const col = css();
  const m = { l: 40, r: 14, t: 22, b: 34 }, xr = [AC.vaMin, AC.vaMax], yr = [0, 120];
  axes(x, w, h, m, xr, yr, [12, 16, 20, 24], [0, 40, 80, 120], col, 'airspeed m/s', 'minutes');
  const { X, Y } = mapper(w, h, m, xr, yr);
  x.beginPath(); for (let v = xr[0]; v <= xr[1]; v += 0.2) { const px = X(v), py = Y(energy(v).minutes); v === xr[0] ? x.moveTo(px, py) : x.lineTo(px, py); } x.strokeStyle = col.ink; x.lineWidth = 2.2; x.stroke();
  dot(x, X(V), Y(e.minutes), col.accent, 5);
}
function setV(v) { V = clamp(+v, AC.vaMin, AC.vaMax); vLift.value = vEn.value = V; drawLift(); drawEnergy(); }
vLift.addEventListener('input', (e) => setV(e.target.value)); vEn.addEventListener('input', (e) => setV(e.target.value));

// ------------------------------------------------------------------------------------------- control
const ctrl = { from: 0, to: 25, t: 5, now: 0 };
const bankIn = $('#bank'); mkRead($('#ctrlRead'), [['Bank angle now', 'cNow', 'acc'], ['Time to 90 %', 'cT90'], ['Elevon, drawn', 'cEl']]);
function startStep(from, to) { ctrl.from = from; ctrl.to = to; ctrl.t = 0; }
bankIn.addEventListener('input', () => { $('#bankOut').textContent = `${bankIn.value}°`; startStep(ctrl.now, +bankIn.value); });
$('#stepBtn').addEventListener('click', () => { ctrl.now = 0; startStep(0, +bankIn.value); });
$('#levelBtn').addEventListener('click', () => { bankIn.value = 0; $('#bankOut').textContent = '0°'; startStep(ctrl.now, 0); });
function drawStep() {
  const c = $('#stepChart'); const { x, w, h } = prep(c); const col = css();
  const m = { l: 34, r: 12, t: 22, b: 34 }, xr = [0, 2], span = ctrl.to - ctrl.from, lim = Math.max(10, Math.abs(ctrl.from), Math.abs(ctrl.to));
  const yr = [-lim, lim];
  axes(x, w, h, m, xr, yr, [0, 0.5, 1, 1.5, 2], [-lim, 0, lim].map(Math.round), col, 'seconds', '');
  const { X, Y } = mapper(w, h, m, xr, yr);
  x.strokeStyle = col.muted; x.setLineDash([5, 5]); x.beginPath(); x.moveTo(X(0), Y(ctrl.to)); x.lineTo(X(2), Y(ctrl.to)); x.stroke(); x.setLineDash([]);
  x.beginPath(); for (let t = 0; t <= 2.001; t += 0.02) { const v = ctrl.from + span * (1 - Math.exp(-t / AC.tauPhi)); t === 0 ? x.moveTo(X(t), Y(v)) : x.lineTo(X(t), Y(v)); } x.strokeStyle = col.ink; x.lineWidth = 2.2; x.stroke();
  x.strokeStyle = col.strong; x.beginPath(); x.moveTo(X(AC.tauPhi), m.t); x.lineTo(X(AC.tauPhi), h - m.b); x.stroke();
  x.fillStyle = col.muted; x.font = '11px "Geist Mono Variable", monospace'; x.textAlign = 'left'; x.textBaseline = 'top'; x.fillText('τ = 0.25 s', X(AC.tauPhi) + 6, m.t + 2);
  const tt = Math.min(ctrl.t, 2); dot(x, X(tt), Y(ctrl.from + span * (1 - Math.exp(-tt / AC.tauPhi))), col.accent, 5);
}

// ------------------------------------------------------------------------------------------- camera map
let os = CAM.osBase, agl = CAM.agl;
const aglIn = $('#agl'); mkRead($('#camRead'), [['Ground pixel', 'kG', 'acc'], ['Footprint', 'kF'], ['Strip spacing', 'kS'], ['Shutter interval', 'kT']]);
function updateCamRead() {
  const g = camGeo(agl, os);
  setDD('kG', fmt(g.gsd * 100, 1), 'cm'); setDD('kF', `${fmt(g.Wg, 0)} × ${fmt(g.Hg, 0)}`, 'm'); setDD('kS', fmt(g.dys, 1), 'm'); setDD('kT', fmt(g.trigger, 2), 's');
  $('#aglOut').textContent = `${agl} m`;
}
aglIn.addEventListener('input', () => { agl = +aglIn.value; updateCamRead(); });
$$('.seg button').forEach((b) => b.addEventListener('click', () => { os = +b.dataset.os; $$('.seg button').forEach((k) => k.classList.toggle('on', k === b)); updateCamRead(); }));
let camT = 0;
function drawCam(dt) {
  const c = $('#camMap'); if (!c.offsetParent) return; camT += dt;
  const { x, w, h } = prep(c); const col = css(); const g = camGeo(agl, os);
  const widthM = 2 * g.dys + g.Wg + 30, sc = w / widthM, heightM = h / sc;
  const cx = [-g.dys, 0, g.dys], cxp = (m) => w / 2 + m * sc;
  const adv = (camT * AC.va * 4) % (g.dxp * 6), yUav = heightM * 0.78 - 0; // keep the aircraft near the upper part, world scrolls
  // field: row hatching
  x.strokeStyle = col.line; x.lineWidth = 1; for (let i = -40; i < 40; i++) { const px = cxp(i * 12); x.beginPath(); x.moveTo(px, 0); x.lineTo(px, h); x.stroke(); }
  const base = adv;                                  // world offset so footprints slide down
  cx.forEach((cm, si) => {
    for (let k = -1; k < 12; k++) {
      const yw = k * g.dxp - base;                      // metres relative to aircraft
      const top = h * 0.3 - (yw + g.Hg / 2) * sc, hh = g.Hg * sc;
      if (yw > 0.01 && k > 0) continue;
      const cur = k === 0 && false;
      x.fillStyle = col.ink; x.globalAlpha = 0.07; x.fillRect(cxp(cm - g.Wg / 2), top, g.Wg * sc, hh);
      x.globalAlpha = 0.35; x.strokeStyle = col.ink; x.lineWidth = 1; x.strokeRect(cxp(cm - g.Wg / 2) + .5, top + .5, g.Wg * sc, hh);
      x.globalAlpha = 1;
    }
    // aircraft glyph + live footprint
    const ay = h * 0.3, ax = cxp(cm);
    x.fillStyle = col.accent; x.globalAlpha = 0.16; x.fillRect(cxp(cm - g.Wg / 2), ay - (g.Hg / 2) * sc, g.Wg * sc, g.Hg * sc); x.globalAlpha = 1;
    x.strokeStyle = col.accent; x.lineWidth = 2; x.strokeRect(cxp(cm - g.Wg / 2), ay - (g.Hg / 2) * sc, g.Wg * sc, g.Hg * sc);
    const s = Math.max(10, 2.12 * sc * 6);
    x.fillStyle = col.ink; x.beginPath(); x.moveTo(ax, ay - s * 0.35); x.lineTo(ax + s * 0.5, ay + s * 0.18); x.lineTo(ax + s * 0.5, ay + s * 0.3); x.lineTo(ax, ay + s * 0.1); x.lineTo(ax - s * 0.5, ay + s * 0.3); x.lineTo(ax - s * 0.5, ay + s * 0.18); x.closePath(); x.fill();
  });
  // dimension: strip spacing
  x.strokeStyle = col.ink; x.fillStyle = col.ink; x.lineWidth = 1.5; x.font = '12px "Geist Mono Variable", monospace'; x.textAlign = 'center'; x.textBaseline = 'bottom';
  const dy0 = h - 38; x.beginPath(); x.moveTo(cxp(cx[0]), dy0); x.lineTo(cxp(cx[1]), dy0); x.moveTo(cxp(cx[0]), dy0 - 6); x.lineTo(cxp(cx[0]), dy0 + 6); x.moveTo(cxp(cx[1]), dy0 - 6); x.lineTo(cxp(cx[1]), dy0 + 6); x.stroke();
  x.fillText(`${fmt(g.dys, 1)} m`, (cxp(cx[0]) + cxp(cx[1])) / 2, dy0 - 8);
  x.textBaseline = 'top'; x.fillText(`footprint ${fmt(g.Wg, 0)} m wide`, w / 2, dy0 + 12);
}

// ------------------------------------------------------------------------------------------- wake
const dyIn = $('#dy'); let dyb = 0.85;
mkRead($('#wakeRead'), [['Circulation', 'wG'], ['Core radius there', 'wRc'], ['Mean upwash', 'wW', 'acc'], ['Angle-of-attack gain', 'wA']]);
function drawWake() {
  const dx = 3 * AC.b, yc = dyb * AC.b;
  const f = followerUpwash(yc, dx);
  setDD('wG', fmt(gamma(), 2), 'm²/s'); setDD('wRc', fmt(f.rc * 100, 1), 'cm'); setDD('wW', (f.mean >= 0 ? '+' : '') + fmt(f.mean, 2), 'm/s'); setDD('wA', (f.dAlphaDeg >= 0 ? '+' : '') + fmt(f.dAlphaDeg, 2), '°');
  $('#dyOut').textContent = fmt(dyb, 2);
  S.view.fx = dyb; S.view.dx = dx;
  const c = $('#wakeChart'); const { x, w, h } = prep(c); const col = css();
  const m = { l: 36, r: 12, t: 22, b: 34 }, xr = [-1.5, 4.5], yr = [-0.6, 0.6];
  axes(x, w, h, m, xr, yr, [-1, 0, 1, 2, 3, 4], [-0.5, 0, 0.5], col, 'lateral y (m)', 'w (m/s)');
  const { X, Y } = mapper(w, h, m, xr, yr);
  x.fillStyle = col.accent; x.globalAlpha = 0.14; x.fillRect(X(yc - AC.b / 2), m.t, X(yc + AC.b / 2) - X(yc - AC.b / 2), h - m.t - m.b); x.globalAlpha = 1;
  x.strokeStyle = col.strong; x.beginPath(); x.moveTo(m.l, Y(0)); x.lineTo(w - m.r, Y(0)); x.stroke();
  x.beginPath(); for (let y = xr[0]; y <= xr[1]; y += 0.02) { const px = X(y), py = Y(clamp(upwash(y, 0, f.rc), -0.6, 0.6)); y === xr[0] ? x.moveTo(px, py) : x.lineTo(px, py); } x.strokeStyle = col.ink; x.lineWidth = 2.2; x.stroke();
  x.strokeStyle = col.accent; x.lineWidth = 2; x.setLineDash([5, 4]); x.beginPath(); x.moveTo(X(yc - AC.b / 2), Y(f.mean)); x.lineTo(X(yc + AC.b / 2), Y(f.mean)); x.stroke(); x.setLineDash([]);
  x.fillStyle = col.ink; for (const yv of [AC.b0 / 2, -AC.b0 / 2]) if (yv > xr[0]) { x.beginPath(); x.arc(X(yv), Y(0), 3.5, 0, 7); x.fill(); }
}
dyIn.addEventListener('input', () => { dyb = +dyIn.value; drawWake(); });

// ------------------------------------------------------------------------------------------- redraw + loop
function redrawAll() { drawLift(); drawEnergy(); drawStep(); updateCamRead(); drawWake(); }

let last = performance.now();
let slow = 0;
const forcedQ = new URLSearchParams(location.search).get('q');      // ?q=0|1|2 pins a quality tier (testing)
if (forcedQ !== null) S.setQuality(+forcedQ);
function loop(now) {
  const raw = (now - last) / 1000;
  const dt = Math.min(0.05, raw); last = now;
  // quality governor: sustained slow frames step the renderer down a tier (see scene.js setQuality)
  if (forcedQ === null && S.cur.alpha > 0.05 && !document.hidden) {
    slow = raw > 0.04 ? slow + 1 : Math.max(0, slow - 2);
    if (slow >= 8 && S.tier < 2) { S.setQuality(S.tier + 1); slow = 0; }
  }
  // teardown explode follows scroll with a light lag
  const exGoal = S.view.preset === 'teardown' ? tdTarget : 0;          // reassembles when the chapter ends
  exCur += (exGoal - exCur) * (1 - Math.exp(-(reduced ? 80 : 7) * dt));
  S.drone.setExplode(exCur);
  // roll dynamics
  if (ctrl.t < 3) { ctrl.t += dt; ctrl.now = ctrl.from + (ctrl.to - ctrl.from) * (1 - Math.exp(-ctrl.t / AC.tauPhi)); }
  const inCtl = S.view.preset === 'control';
  if (inCtl) { S.view.bank = ctrl.now; S.cur.bank = ctrl.now; setDD('cNow', fmt(ctrl.now, 1), '°'); setDD('cT90', fmt(AC.tauPhi * Math.log(10), 2), 's'); setDD('cEl', fmt((ctrl.now / 35) * 14, 1), '°'); drawStep(); }
  else { S.view.bank = 0; }
  S.frame(dt, reduced);
  if (S.view.preset === 'teardown') updateLeader(); else if (leader.getAttribute('d')) { leader.setAttribute('d', ''); leaderDot.setAttribute('r', 0); }
  drawCam(dt);
  requestAnimationFrame(loop);
}

// ------------------------------------------------------------------------------------------- page chrome
const nav = $('#nav');
ScrollTrigger.create({ start: 40, onUpdate: (s) => nav.classList.toggle('solid', s.scroll() > 40) });
const navMap = { teardown: 'teardown', lift: 'lift', control: 'lift', energy: 'lift', camera: 'lift', wake: 'wake', gallery: 'gallery', evidence: 'evidence' };
const navLinks = $$('.nav nav a');
const navIO = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { const t = navMap[e.target.id]; navLinks.forEach((a) => a.classList.toggle('on', a.getAttribute('href') === `#${t}`)); } }), { rootMargin: '-45% 0px -50% 0px' });
Object.keys(navMap).forEach((id) => { const el = document.getElementById(id); if (el) navIO.observe(el); });

// reveal: hierarchy only (panels and media arrive in reading order, once)
if (!reduced) ScrollTrigger.batch('.reveal', { start: 'top 90%', once: true, onEnter: (b) => gsap.to(b, { opacity: 1, y: 0, duration: 0.9, stagger: 0.08, ease: 'expo.out', overwrite: true }) });

// gallery videos play only while visible
const vio = new IntersectionObserver((es) => es.forEach((e) => {
  const v = e.target;
  if (e.isIntersecting) { if (!v.src && v.dataset.src) v.src = v.dataset.src; if (!reduced) v.play().catch(() => {}); } else v.pause();
}), { threshold: 0.35 });
$$('.cell video').forEach((v) => vio.observe(v));

// hero entrance + magnetic primary button (motion values, no framework state)
if (!reduced) {
  gsap.from('.hero-copy h1', { y: 36, opacity: 0, duration: 1.1, ease: 'expo.out', delay: 0.15 });
  gsap.from('.hero-copy .lead, .hero-copy .cta', { y: 24, opacity: 0, duration: 1, ease: 'expo.out', stagger: 0.12, delay: 0.4 });
  gsap.from('.nav', { y: -20, opacity: 0, duration: 0.8, ease: 'expo.out', delay: 0.6 });
  $$('[data-magnetic]').forEach((el) => {
    const qx = gsap.quickTo(el, 'x', { duration: 0.5, ease: 'expo.out' }), qy = gsap.quickTo(el, 'y', { duration: 0.5, ease: 'expo.out' });
    el.addEventListener('pointermove', (e) => { const r = el.getBoundingClientRect(); qx((e.clientX - r.left - r.width / 2) * 0.22); qy((e.clientY - r.top - r.height / 2) * 0.3); });
    el.addEventListener('pointerleave', () => { qx(0); qy(0); });
  });
}

// smooth in-page anchors
$$('a[href^="#"]').forEach((a) => a.addEventListener('click', (e) => { const t = document.querySelector(a.getAttribute('href')); if (!t) return; e.preventDefault(); window.scrollTo({ top: t.offsetTop, behavior: reduced ? 'auto' : 'smooth' }); }));

// ------------------------------------------------------------------------------------------- start
addEventListener('resize', resizeAll);
resizeAll(); bindPresets(); setV(AC.va); bankIn.dispatchEvent(new Event('input')); drawWake(); showStage(0);
document.fonts?.ready.then(() => { resizeAll(); ScrollTrigger.refresh(); });
requestAnimationFrame(loop);
window.__fm = { S, ScrollTrigger };
