// The cover's world (F-206): concept A, one continuous fly-through over the real Lake Tahoe in December, with concept B's fork tree as its last
// chapter (docs/design/cover3d/; the founder's pick, docs/briefs/free-and-polished.md "The line"). The guidebook's printed map rises into the real
// bowl; a family's five days draw themselves along the real roads; the camera comes down to their cabin up Ski Run Boulevard among snowy firs, and
// your trail forks off to the sled hill at Taylor Creek with the SUV driving it; the trip's widgets stamp into the world while it snows; the sun
// sets behind Mt Tallac while the family stands at the end of the pier; postcards fly to the next family's cabin and a thank-you comes back; and
// every trip people shared draws across the lake while a fork tree grows out of it.
import { Vector3, Group, CatmullRomCurve3, TubeGeometry, Mesh, MeshBasicMaterial, Color, Object3D } from 'three';
import { loadTahoe, EXAG } from './data.js';
import { createScene, makeRig, makeAnchors, makeLoop } from './scene.js';
import { buildSky, buildStars, skyUniforms, applySky, STATES, mixState, sunDir } from './sky.js';
import { buildTerrain } from './terrain.js';
import { buildWater, planarReflection } from './water.js';
import { buildForest } from './forest.js';
import { buildCabin, buildPier, buildCar, buildFamily, buildTowns, buildRoads, buildGondola, buildSmoke } from './props.js';
import { buildTrail, fractionAt, setTrailLook, buildPins, buildSnow, buildSparkle, buildPostcards, renderPostcards, KIND } from './fx.js';
import { buildBook, setPage } from './book.js';
import { smooth, lerp, clamp, band, Spring, pxAt } from './core.js';

const G = window.GA_COVER;
main().catch((e) => { console.warn('cover world:', e); G.weak(); });

async function main() {
  const T = await loadTahoe(G.assets, G.tier === 'high' ? 'hi' : 'lo');
  const S = createScene(G);
  const { renderer, scene, camera, q } = S;
  const P = T.places, dark = () => G.mode === 'dark', phoneL = () => G.layout === 'phone';
  const v3 = (p, y) => new Vector3(p[0], y ?? T.landH(p[0], p[1]), p[1]);

  /* ---------- sky, ground, water ---------- */
  const SKYU = skyUniforms(T.nTex);
  const sky = buildSky(SKYU); scene.add(sky);
  const stars = buildStars(q.stars, Math.min(devicePixelRatio || 1, 2)); scene.add(stars);
  const terrain = buildTerrain(T, SKYU, q); scene.add(terrain);
  const TU = terrain.userData.U;
  const lakeRect = [T.Sd.x0, T.Sd.z0, T.Sd.x1, T.Sd.z1];
  const lake = buildWater(T, SKYU, TU, lakeRect, 0, T.fallenBox); scene.add(lake);
  const fallen = buildWater(T, SKYU, TU, T.fallenBox, T.fallenY); scene.add(fallen);
  const reflection = q.reflect ? planarReflection(renderer, 0.5) : null;
  if (reflection) { lake.userData.U.uRefl.value = reflection.rt.texture; }

  /* ---------- what people made ---------- */
  const world = new Group(); scene.add(world);                       // everything standing on the ground rises with it out of the book
  const roads = buildRoads(T, TU); world.add(roads);
  const towns = buildTowns(T, q); world.add(towns);
  const cabin = buildCabin(renderer, { seed: 7 });
  const cabinAt = v3(P.cabin);
  const slope = (x, z) => [T.landH(x + 6, z) - T.landH(x - 6, z), T.landH(x, z + 6) - T.landH(x, z - 6)];
  const [gx, gz] = slope(P.cabin[0], P.cabin[1]);
  cabin.position.copy(cabinAt).add(new Vector3(0, -0.3, 0)); cabin.rotation.y = Math.atan2(-gx, -gz);   // its glass gable faces downhill, toward the lake
  world.add(cabin);
  const next = buildCabin(renderer, { seed: 23, wood: 'log' });
  const [hx, hz] = slope(P.nextCabin[0], P.nextCabin[1]);
  next.position.copy(v3(P.nextCabin)).add(new Vector3(0, -0.3, 0)); next.rotation.y = Math.atan2(-hx, -hz); next.scale.setScalar(0.85);
  world.add(next);
  const pier = buildPier(renderer, T.geo.pier.len, { planks: G.tier === 'high' });   // board by board on a laptop, slabs with the same grain on a phone
  const pd = T.geo.pier.dir;
  pier.rotation.y = Math.atan2(pd[0], pd[1]); world.add(pier);
  const pierEnd = new Vector3(pd[0] * (T.geo.pier.len - 2.6), pier.userData.deckY, pd[1] * (T.geo.pier.len - 2.6));
  const family = buildFamily(); world.add(family);
  const car = buildCar(); world.add(car);
  const gondolaBase = [896, 160], gondolaTop = [lerp(896, P.heavenlyTop[0], 0.6), lerp(160, P.heavenlyTop[1], 0.6)];
  const gondola = buildGondola(T, gondolaBase, gondolaTop); world.add(gondola);
  world.updateMatrixWorld(true);
  const smoke = buildSmoke(cabin.localToWorld(cabin.userData.chimney.clone())); world.add(smoke);
  const smoke2 = buildSmoke(next.localToWorld(next.userData.chimney.clone())); world.add(smoke2);
  const FU = { uTime: { value: 0 }, uWind: { value: [1, 1] }, uSnowCol: { value: new Color(0xf4f7fb) }, uCam: TU.uCam, uFar: { value: q.treeFar } };
  // clearings round the cabins, the pier's foot and the gondola, and corridors from each close-up camera to what it looks at
  const [cgx, cgz] = slope(P.cabin[0], P.cabin[1]), dh0 = new Vector3(-cgx, 0, -cgz).normalize(), sd0 = new Vector3(dh0.z, 0, -dh0.x);
  const corr = (k, s2) => ({ a: [P.cabin[0] + dh0.x * k + sd0.x * s2, P.cabin[1] + dh0.z * k + sd0.z * s2], b: [P.cabin[0], P.cabin[1]], r: 24 });
  const forest = buildForest(T, q, FU, [[P.cabin[0], P.cabin[1], 30], [P.nextCabin[0], P.nextCabin[1], 18], [0, 0, 18], [gondolaBase[0], gondolaBase[1], 30], corr(62, 18), corr(70, 10)]);
  world.add(forest);
  const midForest = forest.children.find((m) => m.userData.mid);

  /* ---------- the story's marks: trails on the real roads, pins at the days ---------- */
  const ORIG = [P.cabin, ...T.geo.trails.orig, P.heavenly];
  const trail = buildTrail(T, ORIG, { px: 5 }), fork = buildTrail(T, T.geo.trails.fork, { px: 5 }), route = buildTrail(T, T.geo.trails.route, { px: 4.5 });
  scene.add(trail, fork, route);
  const pin = (p, color, lift = 3) => ({ x: p[0], y: Math.max(T.landH(p[0], p[1]), T.waterY(p[0], p[1]) ?? -1e9) + lift, z: p[1], color });
  const DAYS = [
    { ...pin(P.cabin, KIND.stay, 12), name: 'Day 1 · The cabin', at: P.cabin, side: -1 },
    { ...pin(P.emerald, KIND.see), name: 'Day 2 · Emerald Bay', at: P.emerald, side: -1 },
    { ...pin(P.tahoeCity, KIND.food), name: 'Day 3 · Dinner in Tahoe City', at: P.tahoeCity, side: -1 },
    { ...pin(P.sand, KIND.see), name: 'Day 4 · Sand Harbor', at: P.sand, side: -1 },
    { ...pin(P.heavenly, KIND.tix), name: 'Day 5 · First chair, Heavenly', at: P.heavenly, side: 1 },
  ];
  const SLED = { ...pin(P.taylor, KIND.tix), name: 'Your day 2 · Taylor Creek sled hill' };
  const FLY = { ...pin(P.renoIn, KIND.flight), name: 'From Reno airport' };
  const NET = T.geo.trails.net;
  const netTrails = NET.map((n) => { const t = buildTrail(T, n.pts, { px: 4 }); scene.add(t); return t; });
  const pinList = [...DAYS, SLED, FLY, ...NET.map((n) => pin(n.pts[n.pts.length - 1], KIND[n.end] || KIND.see))];
  const pins = buildPins(pinList); scene.add(pins);
  const dayAt = DAYS.map((d) => fractionAt(trail, d.at[0], d.at[1]));

  /* ---------- the book, snow, the thank-you, postcards ---------- */
  setPage(T.bounds);
  let book = buildBook(dark()); scene.add(book);
  const snow = buildSnow(q.snow); scene.add(snow);
  const sparkle = buildSparkle(); scene.add(sparkle);
  const famPos = (i) => family.children[i].getWorldPosition(new Vector3());
  const cards = buildPostcards([
    { p: [cabinAt.x + 46, cabinAt.y + 16, cabinAt.z + 38], t: [cabinAt.x, cabinAt.y + 5, cabinAt.z] },
    { p: [P.emerald[0], T.landH(...P.emerald) + 25, P.emerald[1]], t: [P.island[0], 30, P.island[1]] },
    { p: [pierEnd.x + 6, 3, pierEnd.z - 4], t: [pierEnd.x - 400, 60, pierEnd.z + 260] },
    { p: [P.heavenlyTop[0] - 600, T.landH(...P.heavenlyTop) + 40, P.heavenlyTop[1] - 600], t: [-8000, 0, -14000] },
  ]);
  scene.add(cards);
  let cardsDone = '', cardsNext = 0;

  /* ---------- the fork tree: every trip, and the forks of forks, rising out of the lake (concept B) ---------- */
  const SC = 520, treeRoot = new Vector3(-7800, 0, -15200), branches = [];
  const twig = (from, dir, len, depth, color, text) => {
    const to = from.clone().add(dir.clone().multiplyScalar(len * SC));
    const mid = from.clone().lerp(to, 0.5).add(new Vector3(0, len * SC * 0.12, 0));
    branches.push({ curve: new CatmullRomCurve3([from, mid, to]), r: (0.14 * Math.pow(0.7, depth) + 0.03) * SC * 1.9, depth, color, text, tip: to });
    return to;
  };
  const trunkTop = twig(treeRoot, new Vector3(0, 1, 0), 13, 0, KIND.see, 'Lena & Sam · five days');
  [[new Vector3(-0.85, 0.8, 0.3).normalize(), 9, KIND.stay, 'You · the sled hill'], [new Vector3(0.9, 0.8, -0.2).normalize(), 9.5, KIND.tix, 'Mia’s ski week'],
    [new Vector3(-0.2, 1, -0.7).normalize(), 8, KIND.food, 'The Kims · the north shore'], [new Vector3(0.5, 0.85, 0.75).normalize(), 7, KIND.see, 'Ana & Luis · from yours']].forEach(([d, len, c, txt], k) => {
    const start = treeRoot.clone().lerp(trunkTop, 0.55 + k * 0.12);
    const tip = twig(start, d, len, 1, c, txt);
    for (let j = 0; j < 3; j++) { const dd = d.clone().add(new Vector3(Math.sin(j * 2.1 + k) * 0.7, 0.5, Math.cos(j * 1.7 + k) * 0.7)).normalize(); twig(start.clone().lerp(tip, 0.45 + j * 0.2), dd, 3 + j * 0.7, 2, [KIND.see, KIND.food, KIND.tix, KIND.stay, KIND.car][(j + k) % 5]); }
  });
  const tree = new Group(); scene.add(tree);
  const treeMat = new MeshBasicMaterial({ color: 0x0b0b0d, toneMapped: false });
  branches.forEach((b) => { const g = new TubeGeometry(b.curve, 32, b.r, 8, false); b.mesh = new Mesh(g, treeMat); b.count = g.index.count; g.setDrawRange(0, 0); tree.add(b.mesh); });
  const treePins = buildPins(branches.map((b) => ({ x: b.tip.x, y: b.tip.y, z: b.tip.z, color: b.color }))); scene.add(treePins);

  /* ---------- the camera, chapter by chapter (metres; x east, z south) ---------- */
  const [X0, Z0, X1, Z1] = T.bounds, zc = (Z0 + Z1) / 2, K = (X1 - X0) / 120;
  const C = cabinAt, F = pierEnd;
  const DH = new Vector3(-gx, 0, -gz).normalize(), SD = new Vector3(DH.z, 0, -DH.x);      // downhill from the cabin (its glass gable faces it), and across
  const toSun = sunDir(236, 6);
  const away = new Vector3(-toSun[0], 0, -toSun[2]).normalize(), along = new Vector3(toSun[0], 0, toSun[2]).normalize(), sideV = new Vector3(away.z, 0, -away.x);
  const RIG = [
    { p: [X0, 430 * K, zc + 388 * K], t: [X0, 0, zc + 36 * K], fov: 30, shift: [0, -0.27], phone: { p: [X0, 1080 * K, zc + 0.1], t: [X0, 0, zc], fov: 30, up: [-1, 0, 0], shift: [0, -0.2] } },
    { p: [9500, 26000, 21000], t: [-7600, 0, -12800], fov: 38, shift: [0.13, 0], drift: [-600, -1200, -900], phone: { p: [-6200, 76000, 30000], t: [-7600, 0, -13200], fov: 40, shift: [0, 0.27] } },
    { p: [C.x + DH.x * 46 + SD.x * 16, C.y + 9, C.z + DH.z * 46 + SD.z * 16], t: [C.x, C.y + 6.5, C.z], fov: 44, shift: [0.14, 0], phone: { p: [C.x + DH.x * 56 + SD.x * 8, C.y + 12, C.z + DH.z * 56 + SD.z * 8], t: [C.x, C.y + 7, C.z], fov: 56, shift: [0, 0.2] } },
    { p: [10500, 17000, 26000], t: [1600, 0, -5200], fov: 42, shift: [0.12, 0], phone: { p: [4200, 30000, 23000], t: [400, 0, -5600], fov: 46, shift: [0, 0.22] } },
    { p: [F.x + away.x * 8 + sideV.x * 3.2, 3.1, F.z + away.z * 8 + sideV.z * 3.2], t: [F.x + along.x * 60, 9, F.z + along.z * 60], fov: 46, shift: [0.12, 0.02], drift: [0.6, 0.04, 0.6],
      phone: { p: [F.x + away.x * 10 + sideV.x * 2, 3.8, F.z + away.z * 10 + sideV.z * 2], t: [F.x + along.x * 60, 7, F.z + along.z * 60], fov: 60, shift: [0, 0.2] } },
    { p: [F.x - 160, 48, F.z - 230], t: [-60, 22, 420], fov: 46, shift: [0.11, 0], drift: [8, 3, -8], phone: { p: [F.x - 110, 70, F.z - 300], t: [-70, 20, 400], fov: 58, shift: [0, 0.16] } },
    { p: [-1500, 31000, 29000], t: [-7600, 3800, -13200], fov: 38, shift: [0, 0.12], drift: [0, 1500, 1200], phone: { p: [-4200, 52000, 25000], t: [-7600, 3800, -13200], fov: 44, shift: [0, 0.22] } },
  ];
  // chapter 2 opens at the cabin, then rises to show your trail from the cabin to the sled hill while the SUV drives it
  const FORK_VIEW = { p: new Vector3(5600, 5200, 10400), t: new Vector3(-3800, 0, 1300), fov: 40 };
  const FORK_PHONE = { p: new Vector3(2400, 9400, 9800), t: new Vector3(-4000, 0, 1600), fov: 46 };
  const rig = makeRig(G, camera);
  rig.set(RIG); G.on('layout', () => { rig.set(RIG); needLayout = true; });
  rig.setFloor((x, z) => Math.max(T.landH(x, z), T.waterY(x, z) ?? -1e9));

  /* ---------- labels and the plan's widgets ---------- */
  const anchors = makeAnchors(camera, () => [rig.vw, rig.vh]);
  const layer = document.querySelector('.cv-anchors');
  const make = (html, cls = 'cv-lbl') => { const el = document.createElement('div'); el.className = cls; el.innerHTML = html; layer.appendChild(el); return el; };
  const dot = (c) => `<i style="background:#${c.toString(16).padStart(6, '0')}"></i>`;
  let drawOrig = 0;
  DAYS.forEach((d, i) => anchors.add(make(`${dot(d.color)}${d.name}`), new Vector3(d.x, d.y + 40, d.z), { ax: d.side < 0 ? -100 : 0, ay: -50, dx: d.side < 0 ? -14 : 14, dy: i === 4 ? 22 : i === 0 ? -14 : 0,
    show: (st) => (phoneL() && i !== 0 ? 0 : st.chapter === 1 ? smooth(dayAt[i] - 0.02, dayAt[i] + 0.04, drawOrig) * (1 - smooth(0.6, 1, st.travel)) : 0) }));
  const theirs = trail.userData.at(fractionAt(trail, -2400, 2600));
  anchors.add(make(`${dot(0x9a9aa4)}Lena &amp; Sam’s way`), theirs.clone().add(new Vector3(0, 30, 0)), { ax: -100, ay: -100, dx: -10, dy: -8, show: (st) => (st.chapter === 2 ? smooth(0.45, 0.55, st.local) * (1 - smooth(0.4, 0.9, st.travel)) : 0) });
  anchors.add(make('Your trail', 'cv-lbl ink'), (v) => car.getWorldPosition(v).add(new Vector3(0, 30, 0)), { ax: -50, ay: -100, show: (st) => (st.chapter === 2 ? smooth(0.32, 0.42, st.local) * (1 - smooth(0.4, 0.9, st.travel)) : 0) });
  anchors.add(make(`${dot(KIND.stay)}Ana &amp; Luis <small>followed your trail</small>`), v3(P.nextCabin).add(new Vector3(0, 16, 0)), { ax: -60, ay: -100, show: (st) => (st.chapter === 5 ? smooth(0.45, 0.55, st.local) * (1 - smooth(0.3, 0.8, st.travel)) : 0) });
  branches.forEach((b) => { if (!b.text) return; const left = b.tip.x < treeRoot.x; anchors.add(make(`${dot(b.color)}${b.text}`), b.tip.clone().add(new Vector3(0, 420, 0)), { ax: left ? -100 : 0, ay: -50, dx: left ? -12 : 12, show: (st) => (phoneL() ? 0 : st.chapter === 6 ? smooth(0.5, 0.65, st.local) : 0) }); });
  // the plan's widgets: laid out where they read best at the chapter's endpoint, then pinned to the world there, each with a dashed leader to its place
  const svgNS = 'http://www.w3.org/2000/svg', leaders = document.createElementNS(svgNS, 'svg'); leaders.setAttribute('class', 'leaders'); layer.prepend(leaders);
  const routeAt = (t) => route.userData.at(t, new Vector3());
  const WIDGETS = [
    { sel: '.cv-wd.wx', at: [0.5, 0.25], th: 0.08, to: null },
    { sel: '.cv-wd.up', at: [0.69, 0.24], th: 0.2, to: () => fork.userData.at(0.55) },
    { sel: '.cv-wd.flight', at: [0.875, 0.27], th: 0.34, to: () => new Vector3(FLY.x, FLY.y, FLY.z) },
    { sel: '.cv-wd.stay', at: [0.5, 0.72], th: 0.46, to: () => C.clone().add(new Vector3(0, 8, 0)) },
    { sel: '.cv-wd.car', at: [0.69, 0.76], th: 0.58, to: () => routeAt(0.82) },
    { sel: '.cv-wd.tix', at: [0.875, 0.72], th: 0.7, to: () => new Vector3(SLED.x, SLED.y, SLED.z) },
  ];
  const pops = WIDGETS.map((w) => {
    const src = document.querySelector(`[data-chapter="3"] ${w.sel}`); if (!src) return null;
    const el = src.cloneNode(true); el.setAttribute('aria-hidden', 'true'); layer.appendChild(el);
    const sp = new Spring(0, 260, 16), tickets = /flight|stay|car|tix/.test(w.sel), pos = new Vector3();
    const line = document.createElementNS(svgNS, 'path'); leaders.appendChild(line);
    anchors.add(el, pos, { ax: -50, ay: -50, show: () => (phoneL() ? 0 : clamp(sp.v * 4, 0, 1)), scale: () => (tickets ? 1.25 - 0.33 * sp.v : 0.74 + 0.18 * sp.v), rot: () => (tickets ? -6 * (1 - sp.v) - 1.2 : 0) });
    return { w, el, sp, pos, line };
  }).filter(Boolean);
  let needLayout = true;
  const layoutWidgets = () => {
    const c3 = rig.cameraAt(3), ray = new Vector3(), o = c3.position;
    pops.forEach((p) => { ray.set(p.w.at[0] * 2 - 1, -(p.w.at[1] * 2 - 1), 0.5).unproject(c3).sub(o).normalize(); p.pos.copy(o).addScaledVector(ray, (1500 - o.y) / ray.y); });
  };
  const _a = new Vector3(), _b = new Vector3();
  const drawLeaders = () => {
    pops.forEach((p) => {
      const o = phoneL() ? 0 : clamp(p.sp.v * 4, 0, 1);
      if (!p.w.to || o < 0.02) { p.line.setAttribute('opacity', 0); return; }
      _a.copy(p.pos).project(camera); _b.copy(p.w.to()).project(camera);
      p.line.setAttribute('d', `M${((_a.x * 0.5 + 0.5) * rig.vw).toFixed(1)} ${((-_a.y * 0.5 + 0.5) * rig.vh).toFixed(1)} L${((_b.x * 0.5 + 0.5) * rig.vw).toFixed(1)} ${((-_b.y * 0.5 + 0.5) * rig.vh).toFixed(1)}`);
      p.line.setAttribute('opacity', o.toFixed(2));
    });
  };

  /* ---------- light and air ---------- */
  const atm = {};
  const base = () => (dark() ? STATES.night : STATES.day), evening = () => (dark() ? STATES.late : STATES.golden);
  const LOOK = [
    { pin: 30, w: 5, snow: 0 }, { pin: 30, w: 5, snow: 0.08 }, { pin: 34, w: 6, snow: 0.18 }, { pin: 30, w: 5, snow: 0.9 },
    { pin: 22, w: 4, snow: 0 }, { pin: 22, w: 4, snow: 0.05 }, { pin: 26, w: 4, snow: 0 },
  ];
  const lookAt = (cam, k) => { const i = clamp(Math.floor(cam), 0, LOOK.length - 1), j = Math.min(LOOK.length - 1, i + 1), f = clamp(cam - i, 0, 1); return lerp(LOOK[i][k], LOOK[j][k], f); };
  const snowCol = new Color(), hemiSky = new Color(), hemiGround = new Color(), sunCol = new Color();
  function setAtmos(st) {
    applySky(SKYU, st);
    snowCol.set(st.snow); hemiSky.set(st.hemiSky); hemiGround.set(st.hemiGround); sunCol.set(st.sunCol);
    const light = st.night > 0.5 ? st.moonDir : st.sun;
    TU.uLightDir.value.set(...light).normalize(); TU.uLightCol.value.copy(sunCol); TU.uLightI.value = st.sunI;
    TU.uHemiSky.value.copy(hemiSky); TU.uHemiGround.value.copy(hemiGround); TU.uHemiI.value = st.hemiI; TU.uSnow.value.copy(snowCol); TU.uNight.value = st.night;
    for (const w of [lake, fallen]) { const U = w.userData.U; U.uDeep.value.set(st.deep); U.uShallow.value.set(st.shallow); U.uSpec.value = st.spec; }
    S.sun.color.copy(sunCol); S.sun.intensity = st.sunI;
    S.hemi.color.copy(hemiSky); S.hemi.groundColor.copy(hemiGround); S.hemi.intensity = st.hemiI;
    FU.uSnowCol.value.copy(snowCol); towns.userData.snow.uSnowCol.value.copy(snowCol);
    stars.userData.set(st.stars);
    const n = st.night, glow = smooth(0.2, 0.8, n);
    [cabin, next].forEach((c) => { c.userData.glass.emissiveIntensity = glow * 1.6; });
    pier.userData.lamp.emissiveIntensity = 0.2 + glow * 3.2;
    car.userData.lights[0].emissiveIntensity = 0.2 + glow * 2.5; car.userData.lights[1].emissiveIntensity = 0.25 + glow * 2;
    towns.userData.lights.uOpacity.value = smooth(0.25, 0.8, n);
    [smoke, smoke2].forEach((s) => s.userData.U.uCol.value.set(n > 0.5 ? 0x6d7a96 : 0xe9edf2));
    renderer.setClearColor(dark() ? 0x000000 : 0xf2f2f5);
    SKYU.uBgOut.value.set(...(dark() ? [0, 0, 0] : [0.949, 0.949, 0.961]));
    snow.userData.U.uColor.value.set(n > 0.5 ? 0xc9d6f2 : 0xffffff);
    pins.userData.U.uNight.value = n; treePins.userData.U.uNight.value = n;
  }
  const sunNow = new Vector3();

  /* ---------- size ---------- */
  S.onResize = (w, h) => {
    rig.size(w, h);
    const tanF = Math.tan((camera.fov * Math.PI) / 360);
    for (const t of [trail, fork, route, ...netTrails]) { t.material.uniforms.uRes.value = h; t.material.uniforms.uTanFov.value = tanF; }
    for (const p of [pins, treePins]) { p.userData.U.uRes.value = h; p.userData.U.uTanFov.value = tanF; }
    snow.userData.U.uSize.value = (h / 900) * renderer.getPixelRatio();
    sparkle.userData.U.uSize.value = (h / 900) * renderer.getPixelRatio();
    needLayout = true;
  };

  /* ---------- chapter states ---------- */
  let carT = 0, time = 0;
  const tmpV = new Vector3(), up = new Vector3(0, 1, 0);
  function update(st, dt) {
    const { chapter: c, local, travel, cam } = st;
    time += dt;
    // 0 → 1: the book. Pages peel while the headline is pinned, then fly away as the printed map rises into the world.
    const t01 = c === 0 ? travel : 1;
    const peel = c === 0 ? local * 0.42 + travel * 0.58 : 1;
    const rise = smooth(0.1, 0.82, t01), lit = smooth(0.12, 0.62, t01);
    TU.uRise.value = Math.max(rise, 0.0005); TU.uLit.value = lit;
    world.scale.y = Math.max(rise, 0.0005); world.visible = rise > 0.35;
    lake.visible = fallen.visible = rise > 0.02;
    roads.userData.U.uLit.value = lit;
    if (book) book.userData.set(peel, smooth(0.2, 0.55, t01));
    SKYU.uSkyAmt.value = smooth(0.3, 0.72, t01); stars.visible = SKYU.uSkyAmt.value > 0.5;
    // light: day (or night) until Go, where the sun sinks behind Mt Tallac (or the moon sets) and stays down through Share it back
    const tod = c < 4 ? 0 : c === 4 ? smooth(0.05, 0.95, local) : c === 5 ? 1 - smooth(0.2, 1, travel) : 0;
    mixState(base(), evening(), tod, atm);
    if (c === 4 && !dark()) { const el = lerp(14, 2.5, smooth(0.05, 0.95, local)); atm.sun = sunDir(lerp(226, 238, smooth(0, 1, local)), el); }
    setAtmos(atm);

    // 1: the shared trip draws itself along the real roads; pins pop as the line reaches them
    drawOrig = c === 0 ? 0 : c === 1 ? smooth(0.06, 0.8, local) : 1;
    const forkOn = c < 2 ? 0 : c === 2 ? smooth(0.3, 0.7, local) : 1;
    const px = lookAt(cam, 'w');
    const tu = trail.material.uniforms; tu.uDraw.value = drawOrig; tu.uTime.value = time; tu.uPx.value = px; tu.uRise.value = TU.uRise.value;
    setTrailLook(trail, dark(), 0); tu.uOpacity.value = 1 - (c >= 2 ? (c === 2 ? smooth(0.0, 0.3, local) * 0.7 : c === 3 ? 0.8 : c >= 6 ? 0.25 : 0.7) : 0);
    trail.visible = drawOrig > 0 && !(c === 2 && local < 0.3) && !(c === 4 || c === 5);
    DAYS.forEach((d, i) => pins.userData.set(i, drawOrig >= dayAt[i] - 0.004 && c >= 1 ? 1 : 0));
    const fu = fork.material.uniforms; fu.uDraw.value = forkOn; fu.uTime.value = time; fu.uPx.value = px * 1.1;
    setTrailLook(fork, dark(), c >= 6 ? 0.2 : 0); fork.visible = forkOn > 0 && c !== 3;
    pins.userData.set(5, forkOn > 0.97 ? 1 : 0);
    // the SUV drives your trail (never smaller than a few pixels, so it reads from the air)
    carT = c < 2 ? 0 : c === 2 ? smooth(0.3, 0.92, local) : 1;
    car.visible = c === 2 || (c === 1 && travel > 0.6);
    if (car.visible) {
      fork.userData.at(Math.max(0.001, carT), tmpV); car.position.copy(tmpV); car.position.y = T.landH(tmpV.x, tmpV.z) + 0.05;
      const a = fork.userData.at(Math.min(1, carT + 0.004), new Vector3()); car.rotation.y = Math.atan2(a.x - tmpV.x, a.z - tmpV.z) - Math.PI / 2;
      const d = camera.position.distanceTo(car.position), s = Math.max(1, pxAt(14, d, camera.fov, rig.vh) / 4.7);
      car.scale.setScalar(s);
    }
    // 3: your route in from Reno redraws with a running pulse while the widgets stamp in, and it snows
    const ru = route.material.uniforms; ru.uDraw.value = c === 3 ? smooth(0.0, 0.3, local) : c > 3 ? 1 : 0; ru.uTime.value = time * 2.2; ru.uPx.value = px;
    setTrailLook(route, dark(), 0); route.visible = c === 3 || (c === 4 && travel === 0 && local < 0.05);
    pops.forEach((p) => { p.sp.t = c === 3 && local >= p.w.th ? 1 : 0; p.sp.step(dt); p.el.classList.toggle('in', p.sp.t === 1 && p.sp.v > 0.6); });
    if (needLayout) { layoutWidgets(); needLayout = false; }
    drawLeaders();
    snow.userData.U.uAmt.value = lookAt(cam, 'snow') + (c === 0 ? band(travel, 0.25, 0.5, 0.75, 1) * 0.5 : 0);
    snow.userData.U.uTime.value = time; snow.userData.U.uCam.value.copy(camera.position);
    pins.userData.set(6, c === 3 && local > 0.3 ? 1 : 0);

    // 4: the family at the end of the pier, facing the sunset; 5: postcards lift off toward the next family, a thank-you comes back
    family.visible = c >= 3 && !(c === 3 && travel < 0.4);
    family.position.copy(pier.localToWorld(new Vector3(0, pier.userData.deckY - pier.position.y, T.geo.pier.len - 2.6)));
    family.rotation.y = Math.atan2(along.x, along.z);
    if (c === 4 && local > 0.55 && Math.floor(time * 0.7) % 3 === 0) family.userData.hop(3, 1.6);
    family.userData.step(dt);
    family.userData.rim.uRim.value.copy(sunCol); family.userData.rim.uRimAmt.value = 0.25 + tod * 0.8;
    if ((c === 4 && local > 0.6) || c === 5) {
      const key = G.mode + G.layout;
      if (cardsDone !== key) {
        // one postcard per frame, so the four renders never stall one frame
        const views = cards.userData.views, i = cardsNext;
        if (i < views.length) {
          const one = { userData: { ...cards.userData, views: [views[i]], targets: [cards.userData.targets[i]], cards: cards.userData.cards } };
          const vis = [trail.visible, fork.visible, route.visible, pins.visible, tree.visible];
          trail.visible = fork.visible = route.visible = pins.visible = tree.visible = false;
          renderPostcards(renderer, scene, one);
          [trail.visible, fork.visible, route.visible, pins.visible, tree.visible] = vis;
          cardsNext++;
        } else { cardsDone = key; cardsNext = 0; }
      }
    }
    const share = c === 5 ? local : c > 5 ? 1 : 0;
    const from = pierEnd.clone().add(new Vector3(0, 1.4, 0)), to = v3(P.nextCabin).add(new Vector3(0, 10, 0));
    cards.userData.cards.forEach((card, i) => {
      const k = clamp((share - 0.04 - i * 0.07) / 0.42, 0, 1);
      card.visible = c === 5 && k > 0 && k < 1;
      if (!card.visible) return;
      const e = smooth(0, 1, k);
      card.position.lerpVectors(from, to, e); card.position.y += Math.sin(e * Math.PI) * (60 + i * 12); card.position.x += Math.sin(e * Math.PI) * (i - 1.5) * 18;
      card.lookAt(camera.position); card.rotateZ(Math.sin(time * 2 + i) * 0.18 + (i - 1.5) * 0.1);
      const d = camera.position.distanceTo(card.position);
      card.scale.setScalar(Math.max(1, pxAt(120, d, camera.fov, rig.vh) / 1.4) * (1 - smooth(0.85, 1, k)) + 0.05);
    });
    const spU = sparkle.userData.U; spU.uA.value.copy(to); spU.uB.value.copy(from); spU.uT.value = c === 5 ? smooth(0.6, 0.95, local) : 0; spU.uArc.value = 70; spU.uSpread.value = 22; spU.uTime.value = time;
    sparkle.visible = c === 5 && local > 0.6;
    if (c === 5 && local > 0.94) { family.userData.hop(0, 2.0); family.userData.hop(2, 2.4); }

    // 6: every trip people shared draws across the lake, and the fork tree grows out of it, trunk, forks, then forks of forks
    netTrails.forEach((t, i) => {
      const d = c === 6 ? smooth(0.05 + i * 0.05, 0.45 + i * 0.05, local) : 0;
      t.visible = d > 0; const u = t.material.uniforms; u.uDraw.value = d; u.uPx.value = px * 0.85; u.uTime.value = time;
      setTrailLook(t, dark(), 0.35);
    });
    let k = 7;
    NET.forEach((n, i) => pins.userData.set(k++, c === 6 && local > 0.2 + i * 0.05 ? 1 : 0));
    pins.userData.U.uPx.value = lookAt(cam, 'pin'); pins.userData.step(dt);
    pins.visible = !((c === 4 || c === 5) && travel < 0.6) && !(c === 3 && travel > 0.6) && !(c === 2 && local < 0.32) && !(c === 1 && travel > 0.7);    // no map pins in the close-ups
    const grow = c === 6 ? smooth(0.0, 0.75, local) : 0;
    tree.visible = treePins.visible = grow > 0;
    treeMat.color.set(dark() ? 0xf5f5f7 : 0x0b0b0d);
    branches.forEach((b, i) => {
      const s = b.depth === 0 ? 0 : b.depth === 1 ? 0.3 : 0.55, g = clamp((grow - s) / 0.35, 0, 1);
      b.mesh.geometry.setDrawRange(0, Math.floor((b.count * g) / 6) * 6); b.mesh.visible = g > 0;
      treePins.userData.set(i, g > 0.98 ? 1 : 0);
    });
    treePins.userData.U.uPx.value = 26; treePins.userData.step(dt);

    // the camera: chapter 2 opens at the cabin and rises to show your whole trail
    const forkView = phoneL() ? FORK_PHONE : FORK_VIEW;
    const target = rig.place(cam, local, dt, (p, t, fov) => {
      const w = c === 2 ? smooth(0.12, 0.62, local) * (cam < 2.001 ? 1 : 1 - travel) : 0;
      if (w <= 0) return fov;
      p.lerp(forkView.p, w); t.lerp(forkView.t, w);
      return lerp(fov, forkView.fov, w);
    });

    // what is near enough to draw: the close-up sets only near the camera, the forest only below cloud height
    const camH = camera.position.y;
    const nearCabin = camera.position.distanceTo(C), nearPier = camera.position.distanceTo(F);
    const close = Math.min(nearCabin, nearPier, camera.position.distanceTo(v3(P.nextCabin)));
    const camAt = camera.position;
    cabin.visible = smoke.visible = camAt.distanceTo(C) < 3500 || c === 2;
    next.visible = smoke2.visible = camAt.distanceTo(v3(P.nextCabin)) < 3500;
    forest.children.forEach((m) => {
      if (m.userData.hero) m.visible = Math.hypot(camAt.x - m.userData.center[0], camAt.z - m.userData.center[1]) < m.userData.R + 1400 && camH < 2500;
      else if (m.userData.rocks) m.visible = close < 2500;
    });
    midForest.visible = camH < 16000;
    pier.visible = nearPier < 6000;
    gondola.visible = camera.position.distanceTo(v3(gondolaBase)) < 12000;
    FU.uTime.value = time; FU.uWind.value = [1 + Math.sin(time * 0.3) * 0.3, 1];
    gondola.userData.step(time);
    smoke.userData.U.uTime.value = time; smoke2.userData.U.uTime.value = time;
    for (const w of [lake, fallen]) w.userData.U.uTime.value = time;
    stars.userData.U.uTime.value = time;
    // shadows: a small box round whatever the camera is close to, re-rendered when the light or the subject moves
    if (S.q.shadow) {
      const focus = nearPier < nearCabin ? F : C;
      const lightDir = TU.uLightDir.value;
      if (close < 900) {
        S.sun.castShadow = true;
        sunNow.copy(focus).addScaledVector(lightDir, 700); S.sun.position.copy(sunNow); S.sun.target.position.copy(focus); S.sun.target.updateMatrixWorld();
        renderer.shadowMap.needsUpdate = true;
      } else S.sun.castShadow = false;
    }
    // the lake mirrors the pier, the family and the sunset when the camera stands on the water's edge (strong laptops only)
    lake.userData.U.uReflAmt.value = reflection && camH < 250 && nearPier < 1500 ? 1 : 0;
    // keep the sky dome and stars on the camera
    sky.position.copy(camera.position); stars.position.copy(camera.position);
    anchors.update(st);
  }

  function render() {
    terrain.userData.select(camera, TU.uRise.value);
    if (lake.userData.U.uReflAmt.value > 0) {
      reflection.render(scene, camera, [lake, fallen, sky, snow, sparkle, smoke, smoke2, cards]);     // translucent effects stay out of the mirror
      lake.userData.U.uReflMat.value.copy(reflection.texMat);
    }
    renderer.render(scene, camera);
  }

  G.on('mode', (m) => { scene.remove(book); book = buildBook(m === 'dark'); scene.add(book); cardsDone = ''; cardsNext = 0; });
  const loop = makeLoop(G, S, (dt) => update(G.tick(dt), dt), render);
  loop.resize();
  // compile every program now (in parallel where the browser can), so a material seen for the first time mid-story never stalls a frame
  const hidden = []; scene.traverse((o) => { if (!o.visible) { hidden.push(o); o.visible = true; } });
  try { await renderer.compileAsync(scene, camera); } catch (e) { /* older drivers: they compile on first use */ }
  hidden.forEach((o) => (o.visible = false));
  const first = G.tick(1 / 60); update(first, 1 / 60); render();
  if (S.capture) {
    window.__cover = { G, S, T, step: (dt = 1 / 30) => { update(G.tick(dt), dt); render(); } };
    G.ready(); return;
  }
  G.ready(); loop.start();
  window.__cover = { G, S, T, loop, terrain, get running() { return loop.running; }, info: () => ({ ...renderer.info.render, tiles: terrain.geometry.instanceCount, trees: forest.userData, houses: towns.userData.count, scale: loop.scale, programs: renderer.info.programs?.length }) };
}
