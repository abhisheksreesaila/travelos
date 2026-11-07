// Concept A · One continuous fly-through. The guidebook's map rises into Lake Tahoe and a single camera flies
// chapter by chapter: arrive over the lake, see a family's shared trip as a trail, fork it, plan it (the trip's
// widgets stamp into the world while it snows), go (the sun sets over the pier), share it back, and pull up to
// every trip people shared.
import { Vector3 } from 'three';
import { createScene } from './scene.js';
import { buildTrail, fractionAt, setTrailLook, buildPins, buildPostcards, renderPostcards, KIND } from './fx.js';
import { STATES, mixState } from './world.js';
import { P, landH, LOOP, loopPath, IDX, ROAD_RENO, ROAD_HOPE, ROAD_SPOONER } from './geo.js';
import { smooth, lerp, clamp, band, damp, Spring } from './core.js';

const G = window.GA_COVER;
const S = createScene();
const { W } = S;
const dark = () => G.mode === 'dark';
const px = P.pierEnd[0], pz = P.pierEnd[1];

/* ---------- the family's trip (Lena & Sam, five days) and your fork, laid along the real roads ---------- */
const rev = (a) => a.slice().reverse();
const RENO_IN = rev(ROAD_RENO);
const ORIG = [
  ...RENO_IN.slice(0, -1), ...loopPath(IDX.state, IDX.cabin - 1), P.cabin, ...loopPath(IDX.cabin + 2, IDX.emerald),
  ...loopPath(IDX.emerald + 1, IDX.tahoe - 1), P.tahoeCity, ...loopPath(IDX.tahoe + 2, IDX.sand - 1), P.sandHarbor,
  ...loopPath(IDX.sand + 2, IDX.state), P.heavenlyBase, P.heavenlyTop,
];
const FORK = [P.cabin, LOOP[IDX.hope + 1], ...ROAD_HOPE.slice(1)];
const ROUTE = [...RENO_IN.slice(0, -1), ...loopPath(IDX.state, IDX.cabin - 1), P.cabin, LOOP[IDX.hope + 1], ...ROAD_HOPE.slice(1)];
const trail = buildTrail(ORIG, { width: 0.9 });
const fork = buildTrail(FORK, { width: 0.6 });
const route = buildTrail(ROUTE, { width: 0.8 });
S.scene.add(trail, fork, route);

const pin = (x, z, color, lift = 0.1) => ({ x, y: landH(x, z) + lift, z, color });
const DAYS = [
  { ...pin(P.cabin[0], P.cabin[1] - 1.2, KIND.stay, 1.7), name: 'Day 1 · The cabin', at: P.cabin, side: 1 },
  { ...pin(P.emerald[0], P.emerald[1], KIND.see), name: 'Day 2 · Emerald Bay', at: P.emerald, side: 1 },
  { ...pin(P.tahoeCity[0], P.tahoeCity[1], KIND.food), name: 'Day 3 · Dinner in Tahoe City', at: P.tahoeCity, side: -1 },
  { ...pin(P.sandHarbor[0], P.sandHarbor[1], KIND.see), name: 'Day 4 · Sand Harbor', at: P.sandHarbor, side: 1 },
  { ...pin(P.heavenlyBase[0], P.heavenlyBase[1], KIND.tix), name: 'Day 5 · First chair, Heavenly', at: P.heavenlyBase, side: 1 },
];
const SLED = { ...pin(P.sledHill[0], P.sledHill[1], KIND.tix), name: 'Your day 2 · Sled hill' };
const FLY = { ...pin(98, 38.2, KIND.flight), name: 'From Reno airport' };
// the network: other families' shared trips and their forks, for the last chapter
const L = (i) => LOOP[(i + LOOP.length) % LOOP.length];
const NET = [
  { pts: [P.nextCabin, ...loopPath(IDX.next, IDX.emerald + 14)], pins: [[...L(IDX.emerald + 14), KIND.see], [...L(IDX.emerald + 4), KIND.food]], who: 'Ana & Luis', forks: 18 },
  { pts: [...loopPath(IDX.tahoe, IDX.tahoe + 40), [40, -64], [52, -72]], pins: [[...L(IDX.tahoe + 22), KIND.stay], [...L(IDX.tahoe + 38), KIND.food], [52, -72, KIND.tix]], who: 'The Kims', forks: 6 },
  { pts: [P.stateline, P.heavenlyBase, P.heavenlyTop, [64, 96], [72, 108]], pins: [[...P.heavenlyBase, KIND.stay], [72, 108, KIND.tix]], who: 'Mia’s ski week', forks: 41 },
  { pts: [[-37.2, 36.2, 0.16], [-34.6, 34, 0.16], [-31, 34.2, 0.16], [-26.5, 32.8, 0.16], [-21.5, 31.4, 0.16]], pins: [[...P.island, KIND.see]], who: 'Emerald Bay by kayak', forks: 12 },
  { pts: [P.tahoeCity, [-34, -60], [-46, -70], [-60, -84]], pins: [[-46, -70, KIND.tix], [-60, -84, KIND.stay]], who: 'Palisades weekend', forks: 9 },
  { pts: [P.sandHarbor, ...loopPath(IDX.sand + 2, IDX.spoon), ...ROAD_SPOONER.slice(1)], pins: [[...P.spooner, KIND.tix]], who: 'Spooner sled day', forks: 3 },
  { pts: [L(IDX.cabin + 8), [-12, 62], [-16, 70], [-22, 80]], pins: [[-22, 80, KIND.see]], who: 'Fallen Leaf walk', forks: 5 },
  { pts: [L(2), [46, -4], [60, -6], [78, -9]], pins: [[78, -9, KIND.food]], who: 'Carson day trip', forks: 2 },
];
const netTrails = NET.map((n) => { const t = buildTrail(n.pts, { width: 0.9 }); S.scene.add(t); return t; });
const pinList = [...DAYS, SLED, FLY, ...NET.flatMap((n) => n.pins.map(([x, z, c]) => pin(x, z, c)))];
const pins = buildPins(pinList); S.scene.add(pins); W.pins = pins;
const dayAt = DAYS.map((d) => fractionAt(trail, d.at[0], d.at[1]));

/* ---------- postcards: the trip's photos, really rendered from this world ---------- */
const cards = buildPostcards([
  { p: [P.cabin[0] - 3.4, 2.2, P.cabin[1] - 5.2], t: [P.cabin[0], 0.8, P.cabin[1]] },
  { p: [-40, 14, 47], t: [-29, 0, 33] },
  { p: [px + 1.6, 1.3, pz + 1.2], t: [px - 20, 2.6, pz - 8] },
  { p: [50, 44, 79], t: [5, 0, 24] },
]);
S.scene.add(cards);
let cardsDone = '';

/* ---------- the camera, chapter by chapter ---------- */
const RIG = [
  { p: [-60, 430, 388], t: [-60, 0, 36], fov: 30, shift: [0, -0.27], phone: { p: [-60, 1080, 0.1], t: [-60, 0, 0], fov: 30, up: [-1, 0, 0], shift: [0, -0.2] } },
  { p: [-2, 168, 176], t: [16, 0, 12], fov: 38, shift: [0.13, 0.0], drift: [-2, -4, -4], phone: { p: [10, 380, 110], t: [8, 0, 0], fov: 40, shift: [0, 0.27] } },
  { p: [-8, 52, 22], t: [14, 0, 70], fov: 46, shift: [0.14, 0], drift: [1.5, -2, 1], phone: { p: [-2, 78, 16], t: [14, 0, 66], fov: 54, shift: [0, 0.2] } },
  { p: [30, 150, 84], t: [30, 0, 57], fov: 40, shift: [0.12, 0], phone: { p: [22, 232, 88], t: [22, 0, 61], fov: 42, shift: [0, 0.22] } },
  { p: [px + 5.2, 1.6, pz + 2.6], t: [px - 18, 3.0, pz - 3.5], fov: 48, shift: [0.12, 0.02], drift: [0.4, 0.05, 0.5], phone: { p: [px + 4.6, 2.2, pz + 3.8], t: [px - 14, 1.2, pz - 9], fov: 62, shift: [0, 0.2] } },
  { p: [px + 9, 6.5, pz - 11], t: [px - 9, 1.0, pz + 2.5], fov: 48, shift: [0.11, 0], drift: [0.5, 0.4, -0.5], phone: { p: [px + 8, 8.5, pz - 12], t: [px - 13, 0.8, pz + 2.5], fov: 60, shift: [0, 0.16] } },
  { p: [10, 200, 205], t: [4, 0, 6], fov: 38, shift: [0, 0.12], drift: [0, 8, 6], phone: { p: [6, 300, 160], t: [2, 0, -2], fov: 44, shift: [0, 0.22] } },
];
S.setRig(RIG);
G.on('layout', () => S.setRig(RIG));

/* ---------- in-world labels and the plan's widgets ---------- */
const anchorsEl = document.querySelector('.anchors');
const make = (html, cls = 'lbl') => { const el = document.createElement('div'); el.className = cls; el.innerHTML = html; anchorsEl.appendChild(el); return el; };
const dot = (c) => `<i style="background:#${c.toString(16).padStart(6, '0')}"></i>`;
const phoneL = () => G.layout === 'phone';
const ch = (st, i) => (st.chapter === i ? 1 : 0);
// day labels in chapter 1 (on a phone only the first and last, so they never pile up)
DAYS.forEach((d, i) => {
  const el = make(`${dot(d.color)}${d.name}`);
  S.anchor(el, new Vector3(d.x, d.y + 1.4, d.z), { ax: d.side < 0 ? -100 : 0, ay: -50, dx: d.side < 0 ? -12 : 12, show: (st) => (phoneL() && i !== 0 ? 0 : st.chapter === 1 ? smooth(dayAt[i] - 0.02, dayAt[i] + 0.04, drawOrig) * (1 - smooth(0.6, 1, st.travel)) : 0) });
});
const lblTheirs = make(`${dot(0x9a9aa4)}Lena &amp; Sam’s way`);
S.anchor(lblTheirs, new Vector3(L(IDX.cabin + 7)[0], landH(...L(IDX.cabin + 7)) + 0.6, L(IDX.cabin + 7)[1]), { ax: -100, ay: -100, dy: -8, dx: 24, show: (st) => (st.chapter === 2 ? smooth(0.15, 0.3, st.local) * (1 - smooth(0.4, 0.9, st.travel)) : 0) });
const lblYours = make('Your fork', 'lbl ink');
S.anchor(lblYours, (v) => W.car.getWorldPosition(v).add(new Vector3(0, 1.1, 0)), { ax: -50, ay: -100, show: (st) => (st.chapter === 2 ? smooth(0.12, 0.22, st.local) * (1 - smooth(0.4, 0.9, st.travel)) : 0) });
const lblNext = make(`${dot(KIND.stay)}Ana &amp; Luis <small>forked your trip</small>`);
S.anchor(lblNext, new Vector3(P.nextCabin[0], landH(P.nextCabin[0], P.nextCabin[1]) + 2.2, P.nextCabin[1]), { ax: -60, ay: -100, show: (st) => (st.chapter === 5 ? smooth(0.45, 0.55, st.local) * (1 - smooth(0.3, 0.8, st.travel)) : 0) });
NET.forEach((n, i) => {
  if (i > 4) return;
  const p0 = n.pins[n.pins.length - 1], el = make(`${dot(p0[2])}${n.who} <small>· ${n.forks} forks</small>`);
  S.anchor(el, new Vector3(p0[0], landH(p0[0], p0[1]) + 1.6, p0[1]), { ax: i % 2 ? -100 : 0, ay: -50, dx: i % 2 ? -14 : 14, show: (st) => (phoneL() ? 0 : st.chapter === 6 ? smooth(0.25 + i * 0.08, 0.4 + i * 0.08, st.local) : 0) });
});
// the plan's widgets. On a laptop they're laid out where they read best at the chapter's endpoint and then pinned
// to the world there (so they ride with it as the camera moves), each with a dashed leader to its place; on a
// phone they sit in the card as a bento (see the HTML).
const hope = (t) => route.userData.at(t, new Vector3());
const WIDGETS = [
  { sel: '.wd.wx', at: [0.5, 0.26], th: 0.08, to: null },
  { sel: '.wd.up', at: [0.69, 0.25], th: 0.2, to: () => hope(0.86) },
  { sel: '.wd.flight', at: [0.875, 0.27], th: 0.34, to: () => new Vector3(FLY.x, FLY.y + 0.6, FLY.z) },
  { sel: '.wd.stay', at: [0.5, 0.7], th: 0.46, to: () => new Vector3(P.cabin[0], landH(...P.cabin) + 0.8, P.cabin[1]) },
  { sel: '.wd.car', at: [0.69, 0.74], th: 0.58, to: () => hope(0.42) },
  { sel: '.wd.tix', at: [0.875, 0.7], th: 0.7, to: () => new Vector3(SLED.x, SLED.y + 0.6, SLED.z) },
];
const svgNS = 'http://www.w3.org/2000/svg';
const leaders = document.createElementNS(svgNS, 'svg'); leaders.setAttribute('class', 'leaders'); anchorsEl.prepend(leaders);
const pops = WIDGETS.map((w) => {
  const src = document.querySelector('.ch.plan ' + w.sel); if (!src) return null;
  const el = src.cloneNode(true); el.setAttribute('aria-hidden', 'true'); anchorsEl.appendChild(el);
  const sp = new Spring(0, 260, 16), tickets = /flight|stay|car|tix/.test(w.sel);
  const pos = new Vector3();
  const line = document.createElementNS(svgNS, 'path'); leaders.appendChild(line);
  S.anchor(el, pos, { ax: -50, ay: -50, show: () => (phoneL() ? 0 : clamp(sp.v * 4, 0, 1)), scale: () => (tickets ? 1.25 - 0.33 * sp.v : 0.74 + 0.18 * sp.v), rot: () => (tickets ? -6 * (1 - sp.v) - 1.2 : 0) });
  return { w, el, sp, tickets, pos, line };
}).filter(Boolean);
function layoutWidgets() {
  const c3 = S.cameraAt(3), ray = new Vector3(), o = c3.position;
  pops.forEach((p) => {
    ray.set(p.w.at[0] * 2 - 1, -(p.w.at[1] * 2 - 1), 0.5).unproject(c3).sub(o).normalize();
    const t = (3 - o.y) / ray.y; p.pos.copy(o).addScaledVector(ray, t);
  });
}
const _a = new Vector3(), _b = new Vector3();
function drawLeaders() {
  const [vw, vh] = S.size();
  pops.forEach((p) => {
    const o = phoneL() ? 0 : clamp(p.sp.v * 4, 0, 1);
    if (!p.w.to || o < 0.02) { p.line.setAttribute('opacity', 0); return; }
    _a.copy(p.pos).project(S.camera); _b.copy(p.w.to()).project(S.camera);
    const ax = (_a.x * 0.5 + 0.5) * vw, ay = (-_a.y * 0.5 + 0.5) * vh, bx = (_b.x * 0.5 + 0.5) * vw, by = (-_b.y * 0.5 + 0.5) * vh;
    p.line.setAttribute('d', `M${ax.toFixed(1)} ${ay.toFixed(1)} L${bx.toFixed(1)} ${by.toFixed(1)}`); p.line.setAttribute('opacity', o.toFixed(2));
  });
}

/* ---------- chapter states ---------- */
let drawOrig = 0, carT = 0, needLayout = true;
addEventListener('resize', () => (needLayout = true));
G.on('layout', () => (needLayout = true));
const tmpV = new Vector3();
const atm = {};
const baseState = () => (dark() ? STATES.night : STATES.day);
const evening = () => (dark() ? STATES.late : STATES.golden);
// per chapter: fog near/far, pin size, trail width, snowfall
const LOOK = [
  { fog: [3000, 6000], pin: 3, w: 0.9, snow: 0 },
  { fog: [160, 620], pin: 3.6, w: 1.25, snow: 0.1 },
  { fog: [80, 420], pin: 1.6, w: 0.6, snow: 0.12 },
  { fog: [170, 640], pin: 2.6, w: 0.95, snow: 0.95 },
  { fog: [45, 300], pin: 1.0, w: 0.3, snow: 0 },
  { fog: [55, 340], pin: 0.8, w: 0.34, snow: 0.04 },
  { fog: [220, 820], pin: 4.2, w: 1.7, snow: 0 },
];
const lookAt = (cam, k) => { const i = clamp(Math.floor(cam), 0, LOOK.length - 1), j = Math.min(LOOK.length - 1, i + 1), f = clamp(cam - i, 0, 1); const a = LOOK[i][k], b = LOOK[j][k]; return Array.isArray(a) ? [lerp(a[0], b[0], f), lerp(a[1], b[1], f)] : lerp(a, b, f); };

function update(st, dt, time) {
  const { chapter: c, local, travel, cam } = st;
  // 0 → 1: the book. Pages peel while the headline is pinned, then fly away as the map rises into the world.
  const t01 = c === 0 ? travel : 1;
  const peel = c === 0 ? local * 0.42 + travel * 0.58 : 1;
  const rise = smooth(0.1, 0.82, t01);
  S.setRise(rise, smooth(0.12, 0.62, t01), lerp(0, 300, smooth(0.12, 0.72, t01)));
  if (W.book) { W.book.userData.set(peel, smooth(0.2, 0.55, t01)); }
  S.setSky(smooth(0.3, 0.72, t01));
  W.TU.uGrow.value = smooth(0.32, 0.95, t01);

  // light: day (or night) until the Go chapter, where time moves toward evening and stays there
  const tod = c < 4 ? 0 : c === 4 ? smooth(0.05, 0.95, local) : c === 5 ? 1 - smooth(0.2, 1, travel) : 0;
  mixState(baseState(), evening(), tod, atm);
  const fg = lookAt(cam, 'fog'), fk = phoneL() ? 1.6 : 1;
  S.setAtmos(atm, [fg[0] * fk, fg[1] * fk]);

  // 1: the shared trip draws itself across the world; pins pop as the line reaches them
  drawOrig = c === 0 ? 0 : c === 1 ? smooth(0.06, 0.8, local) : 1;
  const forkOn = c < 2 ? 0 : c === 2 ? smooth(0.05, 0.55, local) : 1;
  const tu = trail.material.uniforms; tu.uDraw.value = drawOrig; tu.uTime.value = time;
  tu.uWidth.value = lookAt(cam, 'w');
  const dim = c >= 2 ? (c === 2 ? smooth(0.0, 0.3, local) * 0.7 : c === 3 ? 0.8 : c >= 6 ? 0.25 : 0.7) : 0;
  setTrailLook(trail, dark(), 0); tu.uOpacity.value = 1 - dim;
  trail.visible = drawOrig > 0;
  DAYS.forEach((d, i) => pins.userData.set(i, drawOrig >= dayAt[i] - 0.004 && c >= 1 ? 1 : 0));
  // 2: the fork branches at the cabin, and the car drives your branch
  const fu = fork.material.uniforms; fu.uDraw.value = forkOn; fu.uTime.value = time; fu.uWidth.value = lookAt(cam, 'w') * 1.05;
  setTrailLook(fork, dark(), c >= 6 ? 0.2 : 0); fork.visible = forkOn > 0 && c !== 3;
  pins.userData.set(5, forkOn > 0.97 ? 1 : 0);
  carT = c < 2 ? 0 : c === 2 ? smooth(0.08, 0.92, local) : 1;
  W.car.visible = c === 2 || (c === 1 && travel > 0.6) || (c === 3 && travel < 0.3);
  if (W.car.visible) {
    fork.userData.at(Math.max(0.001, carT), tmpV); W.car.position.copy(tmpV); W.car.position.y = landH(tmpV.x, tmpV.z);
    const a = fork.userData.at(Math.min(1, carT + 0.01), new Vector3()); W.car.rotation.y = Math.atan2(a.x - tmpV.x, a.z - tmpV.z);
  }
  // 3: your route redraws with a running pulse while the widgets stamp in, and it really snows
  const ru = route.material.uniforms; ru.uDraw.value = c === 3 ? smooth(0.0, 0.3, local) : c === 2 && travel > 0 ? 0 : c > 3 ? 1 : 0; ru.uTime.value = time * 2.2;
  ru.uWidth.value = lookAt(cam, 'w'); setTrailLook(route, dark(), 0); route.visible = c === 3 || (c === 2 && travel > 0.5) || (c === 4 && travel === 0 && local < 0.05);
  pops.forEach((p) => { p.sp.t = c === 3 && local >= p.w.th ? 1 : 0; p.sp.step(dt); p.el.classList.toggle('in', p.sp.t === 1 && p.sp.v > 0.6); });
  if (needLayout) { layoutWidgets(); needLayout = false; }
  drawLeaders();
  W.snow.userData.U.uAmt.value = lookAt(cam, 'snow') + (c === 0 ? band(travel, 0.25, 0.5, 0.75, 1) * 0.5 : 0);

  // 4: the family at the end of the pier; 5: postcards lift off toward the next family, a thank-you comes back
  const fam = W.family; fam.visible = c >= 3 && !(c === 3 && travel < 0.4);
  fam.position.set(px, 0.31, pz + 0.2); fam.rotation.y = -Math.PI / 2 - 0.25;
  if (c === 4 && local > 0.55 && Math.floor(time * 0.7) % 3 === 0) fam.userData.hop(3, 1.6);
  const share = c === 5 ? local : c > 5 ? 1 : 0;
  if ((c === 4 && local > 0.6) || c === 5) { const key = G.mode + G.layout; if (cardsDone !== key) { cardsDone = key; renderPostcards(S.renderer, S.scene, cards, () => { trail.visible = fork.visible = route.visible = false; pins.visible = false; }); pins.visible = true; } }
  const from = new Vector3(px, 1.1, pz), to = new Vector3(P.nextCabin[0], landH(P.nextCabin[0], P.nextCabin[1]) + 1.6, P.nextCabin[1]);
  cards.userData.cards.forEach((card, i) => {
    const k = clamp((share - 0.04 - i * 0.07) / 0.42, 0, 1);
    card.visible = c === 5 && k > 0 && k < 1;
    if (!card.visible) return;
    const e = smooth(0, 1, k);
    card.position.lerpVectors(from, to, e); card.position.y += Math.sin(e * Math.PI) * (3.2 + i * 0.5); card.position.x += Math.sin(e * Math.PI) * (i - 1.5) * 0.9;
    card.lookAt(S.camera.position); card.rotateZ(Math.sin(time * 2 + i) * 0.18 + (i - 1.5) * 0.1);
    card.scale.setScalar(0.85 * (1 - smooth(0.85, 1, k)) + 0.05);
  });
  const sp = W.sparkle.userData.U; sp.uA.value.copy(to); sp.uB.value.copy(from).add(new Vector3(0, 0.4, 0)); sp.uT.value = c === 5 ? smooth(0.6, 0.95, local) : 0; sp.uArc.value = 3.5;
  W.sparkle.visible = c === 5 && local > 0.6;
  if (c === 5 && local > 0.94) fam.userData.hop(0, 2.0), fam.userData.hop(2, 2.4);

  // 6: every trip people shared, and their forks, drawn across the lake
  netTrails.forEach((t, i) => {
    const d = c === 6 ? smooth(0.05 + i * 0.05, 0.45 + i * 0.05, local) : 0;
    t.visible = d > 0; t.material.uniforms.uDraw.value = d; t.material.uniforms.uWidth.value = lookAt(cam, 'w') * 0.8; t.material.uniforms.uTime.value = time;
    setTrailLook(t, dark(), 0.35);
  });
  pins.userData.set(6, c === 3 && local > 0.3 ? 1 : 0);
  let k = 7;
  NET.forEach((n, i) => n.pins.forEach(() => { pins.userData.set(k++, c === 6 && local > 0.2 + i * 0.05 ? 1 : 0); }));
  pins.userData.U.uPin.value = lookAt(cam, 'pin');

  S.placeCamera(cam, local, dt);
}

G.on('mode', (m) => { S.setBookDark(m === 'dark'); W.terrain.userData.setDark(m === 'dark'); cardsDone = ''; });
// chips in chapter 1: tap a day to find it in the world
document.querySelectorAll('.ch [data-day]').forEach((b) => b.addEventListener('click', () => {
  const i = +b.dataset.day; document.querySelectorAll('.ch [data-day]').forEach((x) => x.classList.toggle('on', x === b));
  pins.userData.snap(i, 2.1); pins.userData.set(i, 1);
}));
W.terrain.userData.setDark(dark());
S.run(update);
