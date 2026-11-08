// Concept B · One place, four seasons. The camera stays on one tripod above Emerald Bay (Meng To's "layered
// reveal": the same place changes through time instead of the camera travelling), and each chapter is a different
// family's shared trip in a different season: winter, a spring fork of it, a summer plan, a fall golden hour, the
// next winter, and at the end every trip rises off the map into a fork tree.
import { Vector3, CatmullRomCurve3, TubeGeometry, Mesh, MeshBasicMaterial, Group } from 'three';
import { createScene } from './scene.js';
import { buildTrail, fractionAt, setTrailLook, buildPins, buildPostcards, renderPostcards, buildLeaves, KIND } from './fx.js';
import { STATES, mixState, buildAspens } from './world.js';
import { P, landH, LOOP, IDX, placeAt } from './geo.js';
import { smooth, lerp, clamp, band, easeIO, mixHex } from './core.js';
import { label, dot, widgets, flyCards } from './story.js';

const G = window.GA_COVER;
// keep the fall view (behind the family on the beach at the bay's mouth) clear of trees
const S = createScene({ trees: { clear: (x, z) => Math.hypot(x + 18, z - 37.4) < 5 || Math.hypot(x + 22.2, z - 36.4) < 2.5 } });
const { W } = S;
const dark = () => G.mode === 'dark';
const phoneL = () => G.layout === 'phone';

/* ---------- aspens around the bay: bare in winter, green in spring and summer, gold in fall ---------- */
const aspens = buildAspens(S.q, W.TU, [[-30, 27.5, 3.5, 26], [-37, 29.5, 3.5, 24], [-42.5, 32, 3, 18], [-24.5, 37.5, 2.5, 14], [-44, 40.5, 3, 18], [-22, 27, 2.5, 12]]);
W.riseGroup.add(aspens);
const leaves = buildLeaves(phoneL() ? 120 : 220); S.scene.add(leaves);

/* ---------- places around Emerald Bay ---------- */
const L = (i) => LOOP[(i + LOOP.length) % LOOP.length];
const over = P.emerald, castle = [-39.4, 36.4], falls = [-42.6, 39.6], eagleLake = [-47, 42], island = P.island, beach = placeAt(133, 0.9), mouth = [-22.6, 31.6];
const fam = [-22.2, 36.4];
const pin = (x, z, color, lift = 0.1) => ({ x, y: Math.max(0, landH(x, z)) + lift, z, color });

/* ---------- four families' trips, one per season ---------- */
const TRIPS = [
  { who: 'Lena & Sam', season: 'Winter', pts: [over, [-32, 42], [-35.5, 40.2], [-38, 38.2], castle, [-36.4, 37.6], [-33, 39.4], [-30.4, 41.6], over], pins: [[...over, KIND.see], [...castle, KIND.see]] },
  { who: 'Priya', season: 'Spring fork', pts: [castle, [-41, 37.6], falls, [-45, 40.6], eagleLake], pins: [[...falls, KIND.see], [...eagleLake, KIND.see]] },
  { who: 'The Okafors', season: 'Summer', pts: [[-38.2, 36.6, 0.16], [-35.8, 35.6, 0.16], [-33.6, 34.2, 0.16], [-31, 34, 0.16], [-27, 32.8, 0.16], mouth.concat(0.16), [-21.6, 28, 0.16], [beach[0] + 1.2, beach[1], 0.16]], pins: [[...castle, KIND.tix], [...island, KIND.see], [...beach, KIND.food]] },
  { who: 'The Garcias', season: 'Fall', pts: [L(IDX.emerald - 9), L(IDX.emerald - 4), over, L(IDX.emerald + 4), L(IDX.emerald + 9), L(IDX.emerald + 15)], pins: [[...L(IDX.emerald - 9), KIND.see], [...L(IDX.emerald + 15), KIND.food]] },
];
const trails = TRIPS.map((t) => { const m = buildTrail(t.pts, { width: 0.42, step: 0.2 }); S.scene.add(m); return m; });
const pinList = TRIPS.flatMap((t, ti) => t.pins.map(([x, z, c]) => ({ ...pin(x, z, c), trip: ti })));
const pins = buildPins(pinList); S.scene.add(pins); W.pins = pins;

/* ---------- the fork tree: every trip, and the forks of forks, rising off the map ---------- */
const treeRoot = new Vector3(island[0], 0.6, island[1]);
const branches = [];
const twig = (from, dir, len, depth, color, labelText) => {
  const to = from.clone().add(dir.clone().multiplyScalar(len));
  const mid = from.clone().lerp(to, 0.5).add(new Vector3(0, len * 0.12, 0));
  branches.push({ curve: new CatmullRomCurve3([from, mid, to]), r: 0.14 * Math.pow(0.7, depth) + 0.03, depth, color, labelText, tip: to });
  return to;
};
const trunkTop = twig(treeRoot, new Vector3(0, 1, 0), 13, 0, KIND.see, 'Lena & Sam · winter');
const kids = [
  [new Vector3(-0.85, 0.8, 0.3).normalize(), 9, KIND.see, 'Priya · spring fork'], [new Vector3(0.9, 0.8, -0.2).normalize(), 9.5, KIND.tix, 'The Okafors · summer'],
  [new Vector3(-0.2, 1, -0.7).normalize(), 8, KIND.food, 'The Garcias · fall'], [new Vector3(0.5, 0.85, 0.75).normalize(), 7, KIND.stay, 'You, next winter'],
];
kids.forEach(([d, len, c, txt], k) => {
  const start = treeRoot.clone().lerp(trunkTop, 0.55 + k * 0.12);
  const tip = twig(start, d, len, 1, c, txt);
  for (let j = 0; j < 3; j++) { const dd = d.clone().add(new Vector3(Math.sin(j * 2.1 + k) * 0.7, 0.5, Math.cos(j * 1.7 + k) * 0.7)).normalize(); twig(start.clone().lerp(tip, 0.45 + j * 0.2), dd, 3 + j * 0.7, 2, [KIND.see, KIND.food, KIND.tix, KIND.stay, KIND.car][(j + k) % 5]); }
});
const tree = new Group(); S.scene.add(tree);
const treeMat = new MeshBasicMaterial({ color: 0x0b0b0d });
branches.forEach((b) => { const g = new TubeGeometry(b.curve, 24, b.r, 6, false); b.mesh = new Mesh(g, treeMat); b.count = g.index.count; g.setDrawRange(0, 0); tree.add(b.mesh); });
const tipPins = branches.map((b) => ({ x: b.tip.x, y: b.tip.y - 1.05, z: b.tip.z, color: b.color }));
const treePins = buildPins(tipPins); S.scene.add(treePins);

/* ---------- postcards: the same view in all four seasons, rendered from this world ---------- */
const cards = buildPostcards([0, 1, 2, 3].map(() => ({ p: [-21, 9, 52], t: [-30, 0, 31] })));
S.scene.add(cards);
let cardsDone = '';
const SEASON = [STATES.day, STATES.spring, STATES.summer, STATES.fall];
const SNOWLINE = [0.1, 0.55, 0.93, 0.82], TREESNOW = [1, 0.15, 0, 0], LEAF = [0, 0.8, 1, 1];

/* ---------- the tripod: one vantage, small moves ---------- */
const fy = landH(...fam);
const RIG = [
  { p: [-60, 430, 388], t: [-60, 0, 36], fov: 30, shift: [0, -0.27], phone: { p: [-60, 1080, 0.1], t: [-60, 0, 0], fov: 30, up: [-1, 0, 0], shift: [0, -0.2] } },
  { p: [-6, 30, 22], t: [-33, 0, 37], fov: 44, shift: [0.14, 0], drift: [0.6, -0.8, 0.4], phone: { p: [-4, 44, 18], t: [-33, 0, 37], fov: 52, shift: [0, 0.2] } },
  { p: [-3, 26, 27], t: [-34, 1, 37], fov: 46, shift: [0.14, 0], drift: [-0.5, -0.5, -0.4], phone: { p: [-1, 40, 24], t: [-34, 0, 37], fov: 54, shift: [0, 0.2] } },
  { p: [-15, 50, 25], t: [-32, 0, 36], fov: 44, shift: [0.12, 0], phone: { p: [-17, 76, 24], t: [-32, 0, 36], fov: 50, shift: [0, 0.24] } },
  { p: [fam[0] + 9.5, fy + 7.5, fam[1] - 1.5], t: [-35, 1.2, 36], fov: 50, shift: [0.1, 0], drift: [0.4, 0.05, 0.2], phone: { p: [fam[0] + 8.4, fy + 4.2, fam[1] + 1.2], t: [-34, 1.4, 35.2], fov: 62, shift: [0, 0.18] } },
  { p: [-7, 31, 23], t: [-33, 0, 37], fov: 46, shift: [0.13, 0], drift: [0.5, 0.3, 0.4], phone: { p: [-5, 45, 19], t: [-33, 0, 37], fov: 54, shift: [0, 0.2] } },
  { p: [-1, 24, 26], t: [-33, 11.5, 36], fov: 50, shift: [0, 0.14], drift: [1.5, 1, 1], phone: { p: [1, 34, 22], t: [-33, 12, 36], fov: 58, shift: [0, 0.25] } },
];
S.setRig(RIG); G.on('layout', () => { S.setRig(RIG); plan.relayout(); });
// which season each chapter shows (0 winter, 1 spring, 2 summer, 3 fall); chapter 0 is the book
const CH_SEASON = [0, 0, 1, 2, 3, 0, 0];
const LOOK = [
  { fog: [3000, 6000], pin: 3, w: 0.9 }, { fog: [60, 340], pin: 1.15, w: 0.42 }, { fog: [60, 340], pin: 1.15, w: 0.42 }, { fog: [110, 480], pin: 2.0, w: 0.75 },
  { fog: [40, 260], pin: 0.9, w: 0.3 }, { fog: [60, 340], pin: 1.15, w: 0.42 }, { fog: [70, 400], pin: 1.3, w: 0.45 },
];
const lookAt = (cam, k) => { const i = clamp(Math.floor(cam), 0, LOOK.length - 1), j = Math.min(LOOK.length - 1, i + 1), f = easeIO(clamp(cam - i, 0, 1)); const a = LOOK[i][k], b = LOOK[j][k]; return Array.isArray(a) ? [lerp(a[0], b[0], f), lerp(a[1], b[1], f)] : lerp(a, b, f); };

/* ---------- labels and the summer plan's widgets ---------- */
const famPos = new Vector3(fam[0], landH(...fam) + 0.02, fam[1]);
const tripLabel = TRIPS.map((t, i) => {
  const end = t.pins[t.pins.length - 1];
  return label(S, `${dot(end[2])}${t.who} <small>· ${t.season.toLowerCase()}</small>`, new Vector3(end[0], Math.max(0, landH(end[0], end[1])) + 1.5, end[1]), { ax: 0, ay: -50, dx: 12, show: (st) => (st.chapter === [1, 2, 3, 4][i] ? smooth(0.25, 0.4, st.local) * (1 - smooth(0.5, 1, st.travel)) : 0) });
});
label(S, `${dot(KIND.stay)}A new family <small>starts from all four</small>`, famPos.clone().add(new Vector3(0, 1.3, 0)), { ax: -50, ay: -100, show: (st) => (st.chapter === 5 ? smooth(0.1, 0.25, st.local) * (1 - smooth(0.4, 1, st.travel)) : 0) });
branches.forEach((b) => { if (!b.labelText) return; label(S, `${dot(b.color)}${b.labelText}`, b.tip.clone().add(new Vector3(0, 0.6, 0)), { ax: b.tip.x < island[0] ? -100 : 0, ay: -50, dx: b.tip.x < island[0] ? -10 : 10, show: (st) => (phoneL() ? 0 : st.chapter === 6 ? smooth(0.45, 0.6, st.local) : 0) }); });
const plan = widgets(S, 3, [
  { sel: '.wd.wx', at: [0.5, 0.26], th: 0.08 },
  { sel: '.wd.up', at: [0.69, 0.25], th: 0.2, to: () => trails[3].userData.at(0.5) },
  { sel: '.wd.flight', at: [0.875, 0.27], th: 0.34 },
  { sel: '.wd.stay', at: [0.5, 0.7], th: 0.46, to: () => new Vector3(beach[0], 0.8, beach[1]) },
  { sel: '.wd.car', at: [0.69, 0.74], th: 0.58, to: () => trails[3].userData.at(0.2) },
  { sel: '.wd.tix', at: [0.875, 0.7], th: 0.7, to: () => new Vector3(castle[0], landH(...castle) + 0.8, castle[1]) },
], phoneL);

/* ---------- chapter states ---------- */
const atm = {}, tmp = {};
function seasonState(si, out) {
  const base = SEASON[si];
  if (!dark()) return Object.assign(out, base);
  mixState(base, STATES.night, 0.82, out); out.leaf = mixHex(base.leaf, 0x1a2230, 0.45); out.snow = mixHex(base.snow, 0xdfe7f5, 0.6); out.disc = 0; return out;
}
const tripAt = TRIPS.map((t, i) => t.pins.map(([x, z]) => fractionAt(trails[i], x, z)));

function update(st, dt, time) {
  const { chapter: c, local, travel, cam } = st;
  const t01 = c === 0 ? travel : 1;
  const peel = c === 0 ? local * 0.42 + travel * 0.58 : 1;
  S.setRise(smooth(0.1, 0.82, t01), smooth(0.12, 0.62, t01), lerp(0, 300, smooth(0.12, 0.72, t01)));
  if (W.book) W.book.userData.set(peel, smooth(0.2, 0.55, t01));
  S.setSky(smooth(0.3, 0.72, t01));
  W.TU.uGrow.value = smooth(0.32, 0.95, t01);

  // the season of this chapter, blending into the next one while the cards swap
  const i0 = CH_SEASON[clamp(Math.floor(cam), 0, 6)], i1 = CH_SEASON[clamp(Math.floor(cam) + 1, 0, 6)], f = easeIO(clamp(cam - Math.floor(cam), 0, 1));
  seasonState(i0, tmp); const A = { ...tmp }; seasonState(i1, tmp); mixState(A, tmp, f, atm);
  // fall goes golden as you read it
  if (c === 4) { const g = smooth(0.1, 0.95, local) * (cam < 4.001 ? 1 : 1 - f); mixState(atm, dark() ? STATES.late : STATES.golden, g * 0.85, atm); atm.leaf = A.leaf; }
  const fg = lookAt(cam, 'fog'), fk = phoneL() ? 1.5 : 1;
  S.setAtmos(atm, [fg[0] * fk, fg[1] * fk]);
  const sl = lerp(SNOWLINE[i0], SNOWLINE[i1], f), ts = lerp(TREESNOW[i0], TREESNOW[i1], f), lf = lerp(LEAF[i0], LEAF[i1], f);
  W.terrain.userData.U.uSnowLine.value = sl; W.TU.uTreeSnow.value = ts; W.TU.uLeaf.value = Math.max(0.001, lf);

  // weather for the season: snow in winter, blossom drifting in spring, leaves in fall
  const su = W.snow.userData.U;
  const snowAmt = (i0 === 0 ? 1 - f : 0) * (i1 === 0 ? 1 : 1) * (c >= 1 ? 0.4 : band(travel, 0.25, 0.5, 0.75, 1) * 0.5) + (i1 === 0 && i0 !== 0 ? f * 0.4 : 0);
  const petal = (i0 === 1 ? 1 - f : 0) + (i1 === 1 && i0 !== 1 ? f : 0);
  su.uAmt.value = Math.max(snowAmt, petal * 0.35); su.uSpeed.value = lerp(1, 0.22, petal); su.uFlake.value = lerp(1, 0.75, petal);
  if (petal > 0.5) su.uColor.value.set(1, 0.86, 0.92);
  leaves.userData.step(dt, time, S.camera, (i0 === 3 ? 1 - f : 0) + (i1 === 3 && i0 !== 3 ? f : 0));

  // each chapter draws its family's trip; earlier ones stay as faint lines (and the spring fork grows out of winter)
  TRIPS.forEach((t, i) => {
    const ch = i + 1, u = trails[i].material.uniforms;
    const d = c < ch ? 0 : c === ch ? smooth(0.05, 0.6, local) : 1;
    u.uDraw.value = d; u.uTime.value = time; u.uWidth.value = lookAt(cam, 'w');
    setTrailLook(trails[i], dark(), 0);
    u.uOpacity.value = c === ch ? 1 : c === 2 && i === 0 ? 0.65 : c === 6 ? 0.25 * (1 - smooth(0, 0.5, local)) : 0.3;
    trails[i].visible = d > 0;
  });
  let k = 0;
  TRIPS.forEach((t, i) => t.pins.forEach((_, j) => { const ch = i + 1; pins.userData.set(k++, (c === ch && trails[i].material.uniforms.uDraw.value >= tripAt[i][j] - 0.01) || (c > ch && c < 6) ? (c === ch ? 1 : 0.7) : 0); }));
  pins.userData.U.uPin.value = lookAt(cam, 'pin');
  plan.update(st, dt);

  // the family: at the overlook in fall (go) and as the new family next winter
  W.family.visible = c === 4 || c === 5 || (c === 3 && travel > 0.5);
  W.family.position.copy(famPos); W.family.rotation.y = -Math.PI / 2;
  W.car.visible = false;
  if (c === 4 && local > 0.6 && Math.floor(time * 0.7) % 3 === 0) W.family.userData.hop(2, 1.6);

  // a year later: the four seasons' photos lift off the bay and drift to the new family; thanks go back
  if ((c === 4 && local > 0.7) || c === 5) {
    const key = G.mode + G.layout;
    if (cardsDone !== key) {
      cardsDone = key;
      const keep = { sl: W.terrain.userData.U.uSnowLine.value, ts: W.TU.uTreeSnow.value, lf: W.TU.uLeaf.value, atm: { ...atm } };
      const vis = [trails.map((t) => t.visible), pins.visible, tree.visible, treePins.visible, W.family.visible];
      trails.forEach((t) => (t.visible = false)); pins.visible = tree.visible = treePins.visible = W.family.visible = false;
      let n = 0;
      renderPostcards(S.renderer, S.scene, cards, () => {
        const si = n++; seasonState(si, tmp); S.setAtmos({ ...tmp }, [60, 340]);
        W.terrain.userData.U.uSnowLine.value = SNOWLINE[si]; W.TU.uTreeSnow.value = TREESNOW[si]; W.TU.uLeaf.value = Math.max(0.001, LEAF[si]);
      });
      W.terrain.userData.U.uSnowLine.value = keep.sl; W.TU.uTreeSnow.value = keep.ts; W.TU.uLeaf.value = keep.lf; S.setAtmos(keep.atm, [fg[0] * fk, fg[1] * fk]);
      trails.forEach((t, i) => (t.visible = vis[0][i])); pins.visible = vis[1]; tree.visible = vis[2]; treePins.visible = vis[3]; W.family.visible = vis[4];
    }
  }
  const from = new Vector3(island[0], 1.2, island[1]), to = famPos.clone().add(new Vector3(0, 0.8, 0));
  flyCards(cards, from, to, c === 5 ? local : 0, time, S.camera, 1.25);
  const spk = W.sparkle.userData.U; spk.uA.value.copy(to); spk.uB.value.copy(from); spk.uT.value = c === 5 ? smooth(0.6, 0.95, local) : 0; spk.uArc.value = 3;
  W.sparkle.visible = c === 5 && local > 0.6;
  if (c === 5 && local > 0.5 && local < 0.6) W.family.userData.hop(0, 2), W.family.userData.hop(3, 2.4);

  // the fork tree grows from Fannette Island, trunk first, then each fork, then the forks of forks
  const grow = c === 6 ? smooth(0.0, 0.75, local) : 0;
  tree.visible = treePins.visible = grow > 0;
  treeMat.color.set(dark() ? 0xf5f5f7 : 0x0b0b0d);
  branches.forEach((b, i) => {
    const start = b.depth === 0 ? 0 : b.depth === 1 ? 0.3 : 0.55, g = clamp((grow - start) / 0.35, 0, 1);
    b.mesh.geometry.setDrawRange(0, Math.floor((b.count * g) / 6) * 6); b.mesh.visible = g > 0;
    treePins.userData.set(i, g > 0.98 ? 1 : 0);
  });
  treePins.userData.U.uPin.value = 1.6; treePins.userData.U.uNight.value = atm.night; treePins.userData.step(dt);

  S.placeCamera(cam, local, dt);
}

G.on('mode', (m) => { S.setBookDark(m === 'dark'); W.terrain.userData.setDark(m === 'dark'); cardsDone = ''; });
W.terrain.userData.setDark(dark());
S.run(update);
