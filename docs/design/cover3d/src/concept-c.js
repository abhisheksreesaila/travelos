// Concept C (wildcard) · The road trip. Scroll is the accelerator: the camera rides behind the family's car
// (a chase camera, the way a driving game frames a road), the shared trip glows on the road ahead like a route,
// and the fork is a literal fork in the road. The plan's widgets stamp onto the glass as you drive past their
// places, the family sleds at golden hour, and the photos fly down the valley to the next car coming up.
import { Vector3 } from 'three';
import { createScene } from './scene.js';
import { buildTrail, fractionAt, setTrailLook, buildPins, buildPostcards, renderPostcards, KIND } from './fx.js';
import { STATES, mixState, buildCar, buildSled } from './world.js';
import { P, landH, LOOP, loopPath, IDX, ROAD_RENO, ROAD_HOPE, ROAD_SPOONER } from './geo.js';
import { smooth, lerp, clamp, band, damp, easeIO, Spring } from './core.js';
import { label, dot, flyCards } from './story.js';

const G = window.GA_COVER;
// keep the sled run and the view down it clear of trees
const S = createScene({ trees: { clear: (x, z) => Math.hypot(x - 14, z - 86) < 7 || (Math.abs(x - 11) < 4 && z > 72 && z < 86) } });
const { W } = S;
const dark = () => G.mode === 'dark';
const phoneL = () => G.layout === 'phone';
const L = (i) => LOOP[(i + LOOP.length) % LOOP.length];
const rev = (a) => a.slice().reverse();

/* ---------- the roads: the family's trip, your fork, and the stretch the car actually drives ---------- */
const RENO_IN = rev(ROAD_RENO);
const ORIG = [...RENO_IN.slice(0, -1), ...loopPath(IDX.state, IDX.cabin - 1), P.cabin, ...loopPath(IDX.cabin + 2, IDX.emerald), ...loopPath(IDX.emerald + 1, IDX.tahoe - 1), P.tahoeCity];
const FORK = [L(IDX.hope), ...ROAD_HOPE.slice(1)];
const DRIVE = [[66, 45.6], [56, 47.6], ...loopPath(IDX.state, IDX.hope), ...ROAD_HOPE.slice(1)];
const trail = buildTrail(ORIG, { width: 0.3, step: 0.3 });
const fork = buildTrail(FORK, { width: 0.3, step: 0.3 });
const drive = buildTrail(DRIVE, { width: 0.3, step: 0.3, lift: 0.05 }); drive.visible = false; // the car's path (never drawn)
S.scene.add(trail, fork);
const jF = fractionAt(drive, L(IDX.hope)[0], L(IDX.hope)[1]); // where the road forks, along the drive
const pin = (x, z, color, lift = 0.1) => ({ x, y: landH(x, z) + lift, z, color });
const DAYS = [
  { ...pin(P.cabin[0], P.cabin[1] - 1.2, KIND.stay, 1.7), name: 'Day 1 · The cabin' },
  { ...pin(P.emerald[0], P.emerald[1], KIND.see), name: 'Day 2 · Emerald Bay' },
  { ...pin(P.tahoeCity[0], P.tahoeCity[1], KIND.food), name: 'Day 3 · Tahoe City' },
];
const SLED = { ...pin(P.sledHill[0], P.sledHill[1], KIND.tix), name: 'Your day 2 · Sled hill' };
// the network for the last chapter: other families' trips, each with its car on the road
const NET = [
  [P.nextCabin, ...loopPath(IDX.next, IDX.emerald + 14)], [...loopPath(IDX.tahoe, IDX.tahoe + 40), [40, -64], [52, -72]], [P.stateline, P.heavenlyBase, [52, 80]],
  [P.sandHarbor, ...loopPath(IDX.sand + 2, IDX.spoon), ...ROAD_SPOONER.slice(1)], [P.tahoeCity, [-34, -60], [-46, -70], [-60, -84]], [L(2), [46, -4], [60, -6], [78, -9]],
];
const netTrails = NET.map((pts) => { const t = buildTrail(pts, { width: 1, step: 0.5 }); S.scene.add(t); return t; });
const netCars = NET.map((_, i) => { const c = buildCar([0x4338ca, 0x8b2fc9, 0xc2410c, 0x0f766e, 0xc92a5e, 0x0369a1][i]); c.scale.setScalar(4.5); W.riseGroup.add(c); return c; });
const pinList = [...DAYS, SLED];
const pins = buildPins(pinList); S.scene.add(pins); W.pins = pins;
const dayAt = DAYS.map((d) => fractionAt(trail, d.x, d.z));

// the next family's car, coming up the valley in the share chapter, and the sled
const next = buildCar(0x4338ca); next.scale.setScalar(2.4); W.riseGroup.add(next);
const sled = buildSled(); sled.scale.setScalar(1.6); W.family.add(sled); sled.position.set(0, 0.0, 0.05); sled.rotation.y = Math.PI / 2; sled.scale.set(1.6, 1.6, 1.9);
const slope = (t) => { const a = new Vector3(P.sledHill[0] - 2.5, 0, P.sledHill[1] + 3.5), b = new Vector3(P.sledHill[0] - 1.5, 0, P.sledHill[1] - 5.5); const v = a.lerp(b, t); v.y = landH(v.x, v.z) + 0.08; return v; };

/* ---------- postcards (photos rendered from this world) ---------- */
const cards = buildPostcards([
  { p: [P.sledHill[0] + 4, landH(...P.sledHill) + 2.2, P.sledHill[1] - 6], t: [P.sledHill[0], landH(...P.sledHill), P.sledHill[1]] },
  { p: [P.cabin[0] - 3.4, 2.2, P.cabin[1] - 5.2], t: [P.cabin[0], 0.8, P.cabin[1]] },
  { p: [12, 30, 92], t: [4, 0, 30] },
  { p: [-40, 14, 47], t: [-29, 0, 33] },
]);
S.scene.add(cards);
let cardsDone = '';

/* ---------- the camera: fixed frames for the book, the sled hill, the valley and the aerial; a chase camera in between ---------- */
const sy = landH(...P.sledHill);
const RIG = [
  { p: [-60, 430, 388], t: [-60, 0, 36], fov: 30, shift: [0, -0.27], phone: { p: [-60, 1080, 0.1], t: [-60, 0, 0], fov: 30, up: [-1, 0, 0], shift: [0, -0.2] } },
  { p: [70, 6, 46], t: [50, 2, 48], fov: 54, shift: [0.12, 0], phone: { p: [70, 6, 46], t: [50, 2, 48], fov: 62, shift: [0, 0.18] } },
  { p: [20, 10, 50], t: [10, 2, 56], fov: 56, shift: [0.12, 0], phone: { p: [20, 10, 50], t: [10, 2, 56], fov: 64, shift: [0, 0.18] } },
  { p: [16, 12, 66], t: [18, 3, 76], fov: 56, shift: [-0.04, 0], phone: { p: [16, 12, 66], t: [18, 3, 76], fov: 64, shift: [0, 0.22] } },
  { p: [P.sledHill[0] + 2.5, sy + 3.2, P.sledHill[1] + 9.5], t: [P.sledHill[0] - 3, sy - 3.5, P.sledHill[1] - 12], fov: 52, shift: [0.12, 0], drift: [0.2, 0.2, -0.6], phone: { p: [P.sledHill[0] + 2, sy + 4.4, P.sledHill[1] + 11], t: [P.sledHill[0] - 3, sy - 4, P.sledHill[1] - 12], fov: 64, shift: [0, 0.18] } },
  { p: [P.sledHill[0] + 3, sy + 7, P.sledHill[1] + 8], t: [12, 0, 56], fov: 50, shift: [0.12, 0], drift: [0.4, 0.3, 0.4], phone: { p: [P.sledHill[0] + 2, sy + 10, P.sledHill[1] + 10], t: [12, 0, 56], fov: 62, shift: [0, 0.18] } },
  { p: [10, 200, 205], t: [4, 0, 6], fov: 38, shift: [0, 0.12], drift: [0, 8, 6], phone: { p: [6, 300, 160], t: [2, 0, -2], fov: 44, shift: [0, 0.22] } },
];
S.setRig(RIG); G.on('layout', () => S.setRig(RIG));
// how far along the drive the car is at each point of the story
function carU(st) {
  const { chapter: c, local, travel } = st;
  if (c === 0) return 0;
  if (c === 1) return lerp(0, jF - 0.16, local) + travel * 0.08;
  if (c === 2) return lerp(jF - 0.08, jF + 0.1, local) + travel * 0.04;
  if (c === 3) return lerp(jF + 0.14, 0.9, local) + travel * 0.1;
  return 1;
}
const CHASE = [null, { d: 8, h: 3.4, a: 9 }, { d: 9.5, h: 6, a: 8 }, { d: 10.5, h: 6, a: 9 }];
const chaseW = (cam) => (cam < 1 ? smooth(0.35, 1, cam) : cam <= 3 ? 1 : 1 - smooth(3, 3.75, cam));
const carPos = new Vector3(), carFwd = new Vector3(0, 0, -1), _f = new Vector3(), _a = new Vector3();
let heading = null;

/* ---------- labels and the heads-up widgets ---------- */
DAYS.forEach((d, i) => label(S, `${dot(d.color)}${d.name}`, new Vector3(d.x, d.y + 1.5, d.z), { ax: -50, ay: -100, show: (st) => (phoneL() && i ? 0 : st.chapter === 1 ? smooth(0.15 + i * 0.15, 0.3 + i * 0.15, st.local) * (1 - smooth(0.4, 0.9, st.travel)) : 0) }));
label(S, `${dot(0x9a9aa4)}Lena &amp; Sam went straight on`, (v) => trail.userData.at(Math.min(1, dayAt[0] + 0.06), v).add(new Vector3(0, 1, 0)), { ax: -50, ay: -100, show: (st) => (st.chapter === 2 ? smooth(0.2, 0.35, st.local) * (1 - smooth(0.8, 1, st.local)) : 0) });
label(S, 'Your fork', (v) => v.copy(carPos).add(new Vector3(0, 2.2, 0)), { ax: -50, ay: -100, show: (st) => (st.chapter === 2 ? smooth(0.3, 0.45, st.local) * (1 - smooth(0.4, 0.9, st.travel)) : 0) }, 'lbl ink');
label(S, `${dot(KIND.flight)}Ana &amp; Luis <small>forked your trip</small>`, (v) => v.copy(next.position).add(new Vector3(0, 2, 0)), { ax: -50, ay: -100, show: (st) => (st.chapter === 5 ? smooth(0.15, 0.3, st.local) * (1 - smooth(0.4, 0.9, st.travel)) : 0) });
// widgets on the glass (laptop): stamped in as the car passes each place, each with a leader to it
const HUD = [
  { sel: '.wd.wx', at: [0.86, 0.17], th: 0.05, to: null },
  { sel: '.wd.up', at: [0.86, 0.36], th: 0.18, to: () => drive.userData.at(Math.min(1, carU(G.state()) + 0.12), new Vector3()) },
  { sel: '.wd.flight', at: [0.66, 0.17], th: 0.32, to: null },
  { sel: '.wd.stay', at: [0.66, 0.4], th: 0.44, to: () => new Vector3(P.cabin[0], 1.4, P.cabin[1]) },
  { sel: '.wd.car', at: [0.66, 0.63], th: 0.56, to: () => carPos.clone().add(new Vector3(0, 0.8, 0)) },
  { sel: '.wd.tix', at: [0.86, 0.6], th: 0.7, to: () => new Vector3(SLED.x, SLED.y + 0.8, SLED.z) },
];
const svgNS = 'http://www.w3.org/2000/svg', layer = document.querySelector('.anchors');
const svg = document.createElementNS(svgNS, 'svg'); svg.setAttribute('class', 'leaders'); layer.prepend(svg);
const hud = HUD.map((w) => {
  const src = document.querySelector(`[data-chapter="3"] ${w.sel}`); if (!src) return null;
  const el = src.cloneNode(true); el.setAttribute('aria-hidden', 'true'); layer.appendChild(el);
  const sp = new Spring(0, 260, 16), tickets = /flight|stay|car|tix/.test(w.sel), line = document.createElementNS(svgNS, 'path'); svg.appendChild(line);
  S.anchor(el, null, { screen: w.at, ax: -50, ay: -50, show: () => (phoneL() ? 0 : clamp(sp.v * 4, 0, 1)), scale: () => (tickets ? 1.2 - 0.3 * sp.v : 0.72 + 0.18 * sp.v), rot: () => (tickets ? -6 * (1 - sp.v) - 1.2 : 0) });
  return { w, el, sp, line };
}).filter(Boolean);

/* ---------- chapter states ---------- */
const atm = {};
const LOOK = [{ fog: [3000, 6000], w: 0.9, pin: 3 }, { fog: [60, 360], w: 0.32, pin: 1.4 }, { fog: [60, 360], w: 0.34, pin: 1.4 }, { fog: [60, 340], w: 0.34, pin: 1.4 }, { fog: [50, 320], w: 0.3, pin: 1.1 }, { fog: [60, 360], w: 0.32, pin: 1.2 }, { fog: [220, 820], w: 1.7, pin: 4 }];
const lookAt = (cam, k) => { const i = clamp(Math.floor(cam), 0, LOOK.length - 1), j = Math.min(LOOK.length - 1, i + 1), f = easeIO(clamp(cam - i, 0, 1)); const a = LOOK[i][k], b = LOOK[j][k]; return Array.isArray(a) ? [lerp(a[0], b[0], f), lerp(a[1], b[1], f)] : lerp(a, b, f); };

function update(st, dt, time) {
  const { chapter: c, local, travel, cam } = st;
  const t01 = c === 0 ? travel : 1;
  const peel = c === 0 ? local * 0.42 + travel * 0.58 : 1;
  S.setRise(smooth(0.1, 0.82, t01), smooth(0.12, 0.62, t01), lerp(0, 300, smooth(0.12, 0.72, t01)));
  if (W.book) W.book.userData.set(peel, smooth(0.2, 0.55, t01));
  S.setSky(smooth(0.3, 0.72, t01));
  W.TU.uGrow.value = smooth(0.32, 0.95, t01);
  const tod = c < 4 ? 0 : c === 4 ? smooth(0.05, 0.9, local) : c === 5 ? 1 - smooth(0.3, 1, travel) : 0;
  mixState(dark() ? STATES.night : STATES.day, dark() ? STATES.late : STATES.golden, tod, atm);
  const fg = lookAt(cam, 'fog'), fk = phoneL() ? 1.4 : 1; S.setAtmos(atm, [fg[0] * fk, fg[1] * fk]);

  // the car, scrubbed along the drive by your scroll
  const u = clamp(carU(st), 0, 1);
  drive.userData.at(u, carPos); carPos.y = landH(carPos.x, carPos.z);
  drive.userData.at(Math.min(1, u + 0.008), _a); _f.set(_a.x - carPos.x, 0, _a.z - carPos.z);
  if (_f.lengthSq() > 1e-6) { _f.normalize(); const h = Math.atan2(_f.x, _f.z); heading = heading === null ? h : heading + Math.atan2(Math.sin(h - heading), Math.cos(h - heading)) * (1 - Math.exp(-10 * dt)); }
  carFwd.set(Math.sin(heading || 0), 0, Math.cos(heading || 0));
  W.car.position.copy(carPos); W.car.rotation.y = heading || 0; W.car.visible = c >= 1 || travel > 0.5;
  // the blinker on the turn at the fork
  const turning = c === 2 && Math.abs(u - jF) < 0.05;
  W.car.userData.blink.opacity = turning && Math.floor(time * 3) % 2 === 0 ? 1 : 0;
  W.car.children.forEach((ch) => { if (ch.userData.side) ch.visible = ch.userData.side < 0 ? true : false; });

  // the trip glows on the road ahead like a route; at the fork it splits and yours lights up
  const tu = trail.material.uniforms, fu = fork.material.uniforms;
  tu.uDraw.value = c === 0 ? 0 : c === 1 ? smooth(0.0, 0.5, local) : 1; tu.uTime.value = time * 2; tu.uWidth.value = lookAt(cam, 'w');
  setTrailLook(trail, dark(), 0); tu.uOpacity.value = c >= 2 ? (c === 2 ? 1 - smooth(0.25, 0.55, local) * 0.65 : c === 6 ? 0.3 : 0.35) : 1; trail.visible = c >= 1 && c !== 6 || (c === 6 && false);
  fu.uDraw.value = c < 2 ? 0 : c === 2 ? smooth(0.2, 0.6, local) : 1; fu.uTime.value = time * 2; fu.uWidth.value = lookAt(cam, 'w') * 1.15; setTrailLook(fork, dark(), 0); fork.visible = c >= 2 && c < 6;
  DAYS.forEach((d, i) => pins.userData.set(i, c >= 1 && c < 6 && tu.uDraw.value >= dayAt[i] - 0.01 ? (c >= 2 ? 0.7 : 1) : 0));
  pins.userData.set(3, c >= 2 && c < 6 && fu.uDraw.value > 0.95 ? 1 : 0);
  pins.userData.U.uPin.value = lookAt(cam, 'pin');
  W.snow.userData.U.uAmt.value = c === 0 ? band(travel, 0.25, 0.5, 0.75, 1) * 0.5 : c === 3 ? 0.25 + smooth(0, 0.3, local) * 0.7 : c === 1 || c === 2 ? 0.12 : 0;

  // widgets on the glass while you drive
  const [vw, vh] = S.size();
  hud.forEach((p) => {
    p.sp.t = c === 3 && local >= p.w.th ? 1 : 0; p.sp.step(dt); p.el.classList.toggle('in', p.sp.t === 1 && p.sp.v > 0.6);
    const o = phoneL() ? 0 : clamp(p.sp.v * 4, 0, 1);
    if (!p.w.to || o < 0.02) { p.line.setAttribute('opacity', 0); return; }
    _a.copy(p.w.to()).project(S.camera); if (_a.z > 1) { p.line.setAttribute('opacity', 0); return; }
    p.line.setAttribute('d', `M${(p.w.at[0] * vw).toFixed(1)} ${(p.w.at[1] * vh).toFixed(1)} L${((_a.x * 0.5 + 0.5) * vw).toFixed(1)} ${((-_a.y * 0.5 + 0.5) * vh).toFixed(1)}`); p.line.setAttribute('opacity', o.toFixed(2));
  });

  // 4: go — the family sleds at golden hour; 5: their photos fly down to the next car coming up the valley
  const fam = W.family; fam.visible = c === 4 || c === 5;
  const ride = c === 4 ? smooth(0.15, 0.75, local) : c === 5 ? 1 : 0;
  const sp0 = slope(ride), sp1 = slope(Math.min(1, ride + 0.02));
  fam.position.copy(sp0); fam.rotation.y = Math.atan2(sp1.x - sp0.x, sp1.z - sp0.z) - Math.PI / 2; sled.visible = c === 4 || c === 5;
  if (c === 4 && local > 0.78 && Math.floor(time * 0.8) % 2 === 0) { fam.userData.hop(0, 1.8); fam.userData.hop(2, 2.2); }
  next.visible = c === 5;
  const nu = c === 5 ? lerp(jF + 0.12, 0.78, smooth(0, 0.9, local)) : 0;
  if (next.visible) { const a = drive.userData.at(nu, new Vector3()), b = drive.userData.at(nu + 0.01, new Vector3()); next.position.set(a.x, landH(a.x, a.z), a.z); next.rotation.y = Math.atan2(b.x - a.x, b.z - a.z); }
  if ((c === 4 && local > 0.7) || c === 5) { const key = G.mode + G.layout; if (cardsDone !== key) { cardsDone = key; const v = [trail.visible, fork.visible, pins.visible]; trail.visible = fork.visible = pins.visible = false; renderPostcards(S.renderer, S.scene, cards); [trail.visible, fork.visible, pins.visible] = v; } }
  const from = sp0.clone().add(new Vector3(0, 1, 0)), to = next.position.clone().add(new Vector3(0, 1.2, 0));
  flyCards(cards, from, to, c === 5 ? smooth(0.1, 0.75, local) : 0, time, S.camera, 1.3);
  const spk = W.sparkle.userData.U; spk.uA.value.copy(to); spk.uB.value.copy(from); spk.uT.value = c === 5 ? smooth(0.7, 0.98, local) : 0; spk.uArc.value = 4;
  W.sparkle.visible = c === 5 && local > 0.7;

  // 6: every family's car on its own shared trip
  netTrails.forEach((t, i) => { const d = c === 6 ? smooth(0.05 + i * 0.06, 0.45 + i * 0.06, local) : 0; t.visible = d > 0; t.material.uniforms.uDraw.value = d; t.material.uniforms.uWidth.value = lookAt(cam, 'w'); t.material.uniforms.uTime.value = time; setTrailLook(t, dark(), 0.2); });
  netCars.forEach((car, i) => { car.visible = c === 6; if (!car.visible) return; const k = (time * 0.025 + i * 0.17) % 1, a = netTrails[i].userData.at(k, new Vector3()), b = netTrails[i].userData.at(Math.min(1, k + 0.01), new Vector3()); car.position.set(a.x, landH(a.x, a.z), a.z); car.rotation.y = Math.atan2(b.x - a.x, b.z - a.z); });

  // the chase camera rides behind the car; the fixed frames take over for the book, the hill, the valley and the aerial
  const w = chaseW(cam);
  const ci = clamp(Math.round(cam), 1, 3), cn = CHASE[clamp(Math.floor(cam), 1, 3)], cm = CHASE[clamp(Math.floor(cam) + 1, 1, 3)], cf = easeIO(clamp(cam - Math.floor(cam), 0, 1));
  const d = lerp(cn.d, cm.d, cf) * (phoneL() ? 1.25 : 1), h = lerp(cn.h, cm.h, cf) * (phoneL() ? 1.3 : 1), ahead = lerp(cn.a, cm.a, cf);
  S.placeCamera(cam, local, dt, (p, t) => {
    if (w <= 0) return;
    const cp = carPos.clone().addScaledVector(carFwd, -d); cp.y = Math.max(carPos.y, landH(cp.x, cp.z)) + h;
    const ct = carPos.clone().addScaledVector(carFwd, ahead); ct.y = carPos.y + 0.6;
    p.lerp(cp, w); t.lerp(ct, w);
  });
}

G.on('mode', (m) => { S.setBookDark(m === 'dark'); W.terrain.userData.setDark(m === 'dark'); cardsDone = ''; });
W.terrain.userData.setDark(dark());
S.run(update);
