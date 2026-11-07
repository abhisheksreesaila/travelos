// Prototype 1 · Toy diorama: a low-poly tile of the LA coast. Each day's route draws across it, pins pop up at
// the stops, and a toy car with the family aboard drives the line. Tap a day to fly there; tap a pin for the stop.
// At the end (and when you fork), dashed branches show where other families took the trip.
import { PlaneGeometry, CatmullRomCurve3, TubeGeometry, Raycaster, Vector2, CanvasTexture, SRGBColorSpace } from 'three';
import {
  createStage, damp, Spring, Kit, M, props, ferrisWheel, pin, family, blobs, confetti, applyLight, lambert, basic, KIND,
  Group, Mesh, Vector3, BoxGeometry, CylinderGeometry, SphereGeometry, IcosahedronGeometry, MeshBasicMaterial,
} from './core.js';

window.GA3D.register((host, api) => {
  const stage = createStage(host, api, { fov: 32 });
  const { scene, camera } = stage;
  const DAYS = api.days;

  /* ---------- the land: a coast, the Santa Monica Mountains, Griffith, the basin ---------- */
  const COAST = [[-6, -0.75], [-5, -0.6], [-4.55, -0.25], [-4.22, 0.28], [-3.92, -0.28], [-3.2, -0.48], [-2, -0.38], [-1.1, -0.12], [-0.78, 0.5], [-0.52, 1.3], [-0.22, 2.2], [0.28, 3.2], [0.78, 4.5]];
  const LAND = [...COAST, [6, 4.5], [6, -4.5], [-6, -4.5]];
  const inside = (x, z) => { let c = false; for (let i = 0, j = LAND.length - 1; i < LAND.length; j = i++) { const [xi, zi] = LAND[i], [xj, zj] = LAND[j]; if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) c = !c; } return c; };
  const coastDist = (x, z) => { let m = 9; for (let i = 0; i < COAST.length - 1; i++) { const [ax, az] = COAST[i], [bx, bz] = COAST[i + 1]; const dx = bx - ax, dz = bz - az; const t = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz))); m = Math.min(m, Math.hypot(x - ax - t * dx, z - az - t * dz)); } return m; };
  const sm = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
  function height(x, z) {
    if (!inside(x, z)) return -0.3;
    const d = coastDist(x, z);
    let h = d < 0.3 ? 0.04 + d * 0.25 : 0.12;
    const zr = -2.3 + 0.35 * Math.sin(x * 1.1) + (x < -3 ? 0.45 : 0);
    h += Math.max(0, 1 - ((z - zr) / 1.25) ** 2) * (0.7 + 0.3 * Math.sin(x * 2.3 + 1)) * sm(2.2, 0.6, x) * sm(0.15, 0.9, d);
    h += Math.max(0, 1 - Math.hypot(x - 3.1, z + 1.85) / 1.25) ** 1.4 * 0.95; // Griffith (at 3.1, -1.85)
    return h;
  }
  const hAt = (x, z) => Math.max(0.02, height(x, z));

  const ground = new Kit();
  const terrain = new PlaneGeometry(12, 9, 60, 45); terrain.rotateX(-Math.PI / 2);
  const tp = terrain.attributes.position;
  for (let i = 0; i < tp.count; i++) tp.setY(i, height(tp.getX(i), tp.getZ(i)));
  const hash = (x, z) => { const s = Math.sin(x * 12.9898 + z * 78.233) * 43758.5453; return s - Math.floor(s); };
  ground.addFaces(terrain, (c, x, y, z) => {
    if (y < -0.1) return c.set(0x3E9BD0);
    const d = coastDist(x, z), r = hash(x, z);
    if (d < 0.32 && y < 0.2) return c.set(r > 0.5 ? 0xF6DEAA : 0xF0D49B);
    if (y > 0.62) return c.set(r > 0.5 ? 0xC9B47A : 0xB7A56C);
    if (y > 0.3) return c.set(r > 0.5 ? 0x7DB45A : 0x6FA84F);
    return c.set([0xA9D77C, 0x9DCE70, 0xB3DC86][Math.floor(r * 3)]);
  });
  // the toy base under the tile
  ground.add(new BoxGeometry(12, 0.6, 9), 0xE6D8BE, M(0, -0.66, 0));
  ground.add(new BoxGeometry(12.35, 0.12, 9.35), 0xFFFFFF, M(0, -1.0, 0));
  // places: the pier and its palms, Venice houses and canals, the airport, downtown, the Getty, the observatory
  props.pier(ground, -1.0, 0.06, 1.05, 1.5, -0.95);
  const BEACH = [[-1.0, 0.25], [-0.82, 1.5], [-0.62, 1.9], [-0.42, 2.5], [-0.1, 3.0], [-2.4, -0.2], [-3.4, -0.35], [-5.3, -0.45], [-4.75, -0.3]];
  BEACH.forEach(([x, z], i) => props.palm(ground, x + 0.18, hAt(x + 0.18, z), z, 0.7 + (i % 3) * 0.08, i));
  [[-0.3, 0.1], [-0.15, 0.45], [0.05, 0.2], [0.3, 0.55]].forEach(([x, z], i) => props.house(ground, x, hAt(x, z), z, 0.9, 0xFFFFFF, [0xF08A5D, 0x5DA9F0, 0xF2C14E, 0xE76F9A][i], i * 0.4));
  for (let i = 0; i < 6; i++) { const x = -0.05 + (i % 3) * 0.32, z = 2.0 + Math.floor(i / 3) * 0.45; props.house(ground, x, hAt(x, z), z, 0.7, [0xFFE3C2, 0xD8F0FF, 0xFFD6E5][i % 3], [0x4FA3E3, 0xF07D5D, 0x6CC57C][i % 3], 0.2); }
  ground.add(new BoxGeometry(0.9, 0.02, 0.05), 0x59B8EA, M(0.25, hAt(0.25, 2.22) + 0.01, 2.22)).add(new BoxGeometry(0.9, 0.02, 0.05), 0x59B8EA, M(0.25, hAt(0.25, 2.62) + 0.01, 2.62));
  ground.add(new BoxGeometry(2.0, 0.03, 0.34), 0x5E6470, M(1.6, hAt(1.6, 3.75) + 0.02, 3.75, 0, 0.1, 0));
  for (let i = 0; i < 6; i++) ground.add(new BoxGeometry(0.16, 0.035, 0.03), 0xFFFFFF, M(0.85 + i * 0.3, hAt(1.6, 3.75) + 0.03, 3.75 - (0.85 + i * 0.3 - 1.6) * 0.1, 0, 0.1, 0));
  ground.add(new BoxGeometry(0.5, 0.22, 0.3), 0xE9EEF3, M(1.3, hAt(1.3, 3.25) + 0.11, 3.25));
  [[3.6, 0.8, 1.2], [3.95, 0.6, 0.9], [4.25, 1.0, 1.5], [3.8, 1.15, 0.7], [4.5, 0.75, 0.8]].forEach(([x, z, h]) => props.tower(ground, x, hAt(x, z), z, h, [0xDDE3EA, 0xC8D3E0, 0xE8E2D8][Math.floor(x * 10) % 3]));
  props.getty(ground, -0.2, hAt(-0.2, -1.45), -1.45, 0.9);
  props.observatory(ground, 3.1, hAt(3.1, -1.85), -1.85, 0.9);
  for (let i = 0; i < 26; i++) { const x = -5.6 + hash(i, 3) * 9.5, z = -4 + hash(i, 7) * 2.8; if (Math.hypot(x - 3.1, z + 1.85) > 0.45 && Math.hypot(x + 0.2, z + 1.45) > 0.5) props.tree(ground, x, hAt(x, z), z, 0.8 + hash(i, 1) * 0.5, hash(i, 2) > 0.5 ? 0x4E9F3D : 0x5DB04A); }
  for (let i = 0; i < 14; i++) { const x = 1 + hash(i, 9) * 4.6, z = -0.4 + hash(i, 5) * 3.6; if (x > 3.3 && z < 1.4 && z > 0.3) continue; props.house(ground, x, hAt(x, z), z, 0.6, 0xFFFFFF, [0xF08A5D, 0x5DA9F0, 0xF2C14E][i % 3], hash(i, 4) * 3); }
  [[-4.22, 0.2], [-4.35, 0.1], [-4.05, 0.12], [-4.15, 0.32]].forEach(([x, z], i) => props.rock(ground, x, 0.02, z, 0.8 + i * 0.15));
  props.starfish(ground, -4.28, 0.05, 0.36); props.starfish(ground, -4.0, 0.05, 0.3, 0.8, 0xFF5D8F);
  scene.add(ground.mesh());

  // the sea: a box of water the land rises out of
  const seaMat = lambert(0x59B8EA);
  const sea = new Mesh(new BoxGeometry(12, 0.34, 9), seaMat); sea.position.y = -0.17; scene.add(sea);
  const waves = new Group(); const waveMat = basic(0xFFFFFF, { transparent: true, opacity: 0.7 });
  for (let i = 0; i < 12; i++) { const w = new Mesh(new BoxGeometry(0.34, 0.01, 0.04), waveMat); w.userData.p = [-5.5 + hash(i, 11) * 5.8, 0.8 + hash(i, 13) * 3.4, hash(i, 17) * 6]; waves.add(w); }
  scene.add(waves);
  const wheel = ferrisWheel(0.62); wheel.position.set(-1.18, 0.09, 1.35); wheel.rotation.y = 0.62; scene.add(wheel);
  const clouds = new Group(); [[-3, 3.2, -1.2, 1], [2.4, 3.6, -2.6, 0.8], [4.6, 3.0, 1.8, 0.7]].forEach(([x, y, z, s]) => { const k = new Kit(); props.cloud(k, 0, 0, 0, s); const m = k.mesh(); m.position.set(x, y, z); m.userData.x = x; clouds.add(m); });
  scene.add(clouds);
  // dusk details (dark mode): stars over Griffith and lamps along the pier and downtown
  const night = new Group();
  const lampK = new Kit(); for (let i = 0; i < 7; i++) lampK.add(new SphereGeometry(0.03, 6, 4), 0xFFE08A, M(-0.62 - i * 0.21 * Math.sin(0.95), 0.18, 0.62 + i * 0.21 * Math.cos(0.95)));
  [[3.6, 0.8, 1.2], [3.95, 0.6, 0.9], [4.25, 1.0, 1.5], [3.8, 1.15, 0.7], [4.5, 0.75, 0.8]].forEach(([x, z, h]) => { for (let k = 1; k < h * 4; k++) lampK.add(new BoxGeometry(0.06, 0.05, 0.31), 0xFFD66B, M(x, hAt(x, z) + k * 0.25, z)); });
  night.add(lampK.mesh(new MeshBasicMaterial({ vertexColors: true })));
  const starK = new Kit(); for (let i = 0; i < 40; i++) starK.add(new IcosahedronGeometry(0.035, 0), 0xFFFFFF, M(-5 + hash(i, 21) * 10, 3.2 + hash(i, 23) * 2.2, -4.4 + hash(i, 25) * 3));
  night.add(starK.mesh(new MeshBasicMaterial({ vertexColors: true })));
  scene.add(night);

  /* ---------- the trip: routes, pins, the car ---------- */
  const PL = { lax: [0.95, 3.45], tacos: [0.35, 0.95], tidewater: [-0.38, 0.32], pier: [-0.7, 0.82], pony: [2.55, -0.95], ferndell: [3.5, -1.15], observatory: [3.1, -1.6],
    bikes: [-0.55, 1.35], abbot: [0.0, 1.75], canals: [0.45, 2.42], dume: [-4.2, 0.05], malibufarm: [-3.05, -0.32], zuma: [-5.15, -0.42], getty: [-0.3, -1.25], gettylunch: [0.12, -1.3], laxcar: [1.45, 3.15], laxfly: [0.75, 3.55] };
  const P3 = (k) => new Vector3(PL[k][0], hAt(PL[k][0], PL[k][1]), PL[k][1]);
  const routeMats = [], routes = [], pins = [], pinMeshes = [];
  const routeColor = () => (api.mode === 'dark' ? 0xF5F5F7 : 0x1B1B22);
  DAYS.forEach((d, di) => {
    const keys = (di === 0 ? [] : ['tidewater']).concat(d.stops.map((s) => s[5]));
    const pts = [], stopAt = [];
    keys.forEach((k, i) => {
      if (i === 0) { pts.push(P3(k).setY(hAt(...PL[k]) + 0.07)); return; }
      const a = PL[keys[i - 1]], b = PL[k], n = Math.max(4, Math.round(Math.hypot(b[0] - a[0], b[1] - a[1]) * 7));
      for (let s = 1; s <= n; s++) { const t = s / n, x = a[0] + (b[0] - a[0]) * t, z = a[1] + (b[1] - a[1]) * t; pts.push(new Vector3(x, hAt(x, z) + 0.07 + Math.sin(t * Math.PI) * 0.12, z)); }
      if (i >= (di === 0 ? 0 : 1)) stopAt.push(pts.length - 1);
    });
    if (di === 0) stopAt.unshift(0);
    const curve = new CatmullRomCurve3(pts);
    const seg = pts.length * 4;
    const geo = new TubeGeometry(curve, seg, 0.042, 5, false);
    const mat = basic(routeColor(), { transparent: true, opacity: 1 }); routeMats.push(mat);
    const mesh = new Mesh(geo, mat); geo.setDrawRange(0, 0); scene.add(mesh);
    routes.push({ curve, geo, mesh, mat, total: geo.index.count, per: 5 * 6, seg, prog: 0, target: 0, stopFrac: stopAt.map((i) => i / (pts.length - 1)) });
    d.stops.forEach((s, si) => {
      const p = pin(KIND[s[2]], 0.9); p.position.copy(P3(s[5])); p.scale.setScalar(0.0001); p.visible = false;
      p.userData = { ...p.userData, di, si, spring: new Spring(0, 200, 13), base: 0.9 };
      p.children[0].userData = { di, si }; pinMeshes.push(p.children[0]); pins.push(p); scene.add(p);
    });
  });
  const shadowMat = new MeshBasicMaterial({ color: 0x1a1a2e, transparent: true, opacity: 0.16, depthWrite: false });
  scene.add(blobs([[-1.18, 0.07, 1.35, 0.3]], shadowMat));

  // the toy car with the family's four heads, and the family on foot for the no-car day
  const car = new Group();
  { const k = new Kit(); k.add(new BoxGeometry(0.42, 0.12, 0.22), KIND.car, M(0, 0.1, 0)).add(new BoxGeometry(0.2, 0.05, 0.2), 0xDDF7E6, M(0.1, 0.18, 0, 0, 0, -0.5));
    for (const [x, z] of [[-0.13, 0.11], [0.13, 0.11], [-0.13, -0.11], [0.13, -0.11]]) k.add(new CylinderGeometry(0.05, 0.05, 0.04, 8), 0x222222, M(x, 0.05, z, Math.PI / 2));
    car.add(k.mesh()); }
  const heads = [[-0.02, 0.06, 0xE8B48A, 1], [-0.02, -0.06, 0x8D5A3B, 1], [-0.14, 0.06, 0xC68B5E, 0.8], [-0.14, -0.06, 0xE8B48A, 0.75]].map(([x, z, c, s]) => {
    const h = new Mesh(new SphereGeometry(0.045 * s, 10, 8), lambert(c, { flatShading: false })); h.position.set(x, 0.2, z); h.userData = { y: 0.2, hop: new Spring(0, 260, 9) }; car.add(h); return h; });
  car.scale.setScalar(1.15); scene.add(car);
  const fam = family(0.55); fam.visible = false; scene.add(fam);
  const conf = confetti(scene);

  /* ---------- fork branches: where other families took it ---------- */
  const forkGroup = new Group(); scene.add(forkGroup);
  function label(text, sub) {
    const c = document.createElement('canvas'), x = c.getContext('2d'); const W = 360, H = sub ? 112 : 72; c.width = W; c.height = H;
    const draw = () => {
      const dark = api.mode === 'dark'; x.clearRect(0, 0, W, H);
      x.fillStyle = dark ? '#1C1C1F' : '#FFFFFF'; x.beginPath(); x.roundRect(4, 4, W - 8, H - 8, (H - 8) / 2.4); x.fill();
      x.fillStyle = dark ? '#F5F5F7' : '#0B0B0D'; x.font = '650 30px Geist, system-ui'; x.textBaseline = 'middle'; x.fillText(text, 26, sub ? 40 : H / 2 + 1);
      if (sub) { x.fillStyle = dark ? '#A1A1AA' : '#5C5C66'; x.font = '500 24px Geist, system-ui'; x.fillText(sub, 26, 76); }
      tex.needsUpdate = true;
    };
    const tex = new CanvasTexture(c); tex.colorSpace = SRGBColorSpace; draw();
    const m = new Mesh(new PlaneGeometry(W / 200, H / 200), new MeshBasicMaterial({ map: tex, transparent: true, depthTest: false }));
    m.renderOrder = 5; m.userData.redraw = draw; m.userData.bill = true; return m;
  }
  function dashed(from, to, lift = 0.5, color = 0x8E8E99) {
    const mid = from.clone().lerp(to, 0.5); mid.y += lift;
    const c = new CatmullRomCurve3([from, mid, to]); const k = new Kit(); const n = 22;
    for (let i = 0; i < n; i += 1) { if (i % 2) continue; const a = c.getPointAt(i / n), b = c.getPointAt((i + 1) / n); const len = a.distanceTo(b); const g = new CylinderGeometry(0.03, 0.03, len, 5); const mid2 = a.clone().lerp(b, 0.5); const mm = new Mesh(g); mm.position.copy(mid2); mm.lookAt(b); mm.rotateX(Math.PI / 2); mm.updateMatrix(); k.add(g, color, mm.matrix); }
    return k.mesh(new MeshBasicMaterial({ vertexColors: true }));
  }
  const FORK_TO = [['San Diego', '18 forks · Ana & Luis', P3('canals'), new Vector3(3.2, 0.3, 4.4)], ['Disneyland', '9 forks · Mei & Jun', P3('laxcar'), new Vector3(5.6, 0.3, 3.0)], ['Universal', '4 forks · the Okafors', P3('observatory'), new Vector3(1.6, 0.9, -3.4)]];
  const forkItems = FORK_TO.map(([name, sub, a, b]) => { const g = new Group(); g.add(dashed(a, b, 0.7)); const l = label(name + ' →', sub); l.position.copy(b).add(new Vector3(0, 0.55, 0)); g.add(l); g.scale.setScalar(0.0001); g.userData.spring = new Spring(0, 160, 14); forkGroup.add(g); return g; });
  let youFork = null;

  /* ---------- camera ---------- */
  const rig = { tx: -0.2, ty: 0, tz: 0.4, d: 16, a: -0.22, e: 0.95 };
  const want = { ...rig };
  function frame(i) {
    const portrait = stage.aspect < 1, fit = portrait ? 1 / Math.max(0.5, stage.aspect * 1.25) : 1;
    if (i < 0) { Object.assign(want, portrait ? { tx: 1.6, ty: 0, tz: 1.6, d: 29, a: 0.95, e: 1.1 } : { tx: -0.2, ty: 0, tz: 0.35, d: 19.5, a: -0.22, e: 0.9 }); return; }
    const ks = DAYS[i].stops.map((s) => P3(s[5])); const c = ks.reduce((a, b) => a.add(b), new Vector3()).multiplyScalar(1 / ks.length);
    const r = Math.max(...ks.map((p) => p.distanceTo(c)));
    Object.assign(want, { tx: c.x, ty: c.y, tz: c.z + 0.2, d: Math.max(6.2, r * 3.4 + 3.2) * Math.min(1.7, fit), a: [-0.15, 0.25, -0.35, -0.55, 0.05][i], e: 0.78 });
  }
  stage.resized = () => frame(cur);

  /* ---------- state ---------- */
  let cur = -1, revealed = api.capture ? 4 : -1, cheerT = 0, wheelBoost = 0;
  function setDay(i, instant = false) {
    cur = i; if (i > revealed) revealed = i;
    frame(i); if (instant) Object.assign(rig, want);
    routes.forEach((r, di) => {
      const show = di <= revealed;
      r.mesh.visible = show;
      if (di === i) { r.prog = instant ? 1 : 0; r.target = 1; } else { r.target = show ? 1 : 0; if (instant || di !== i) r.prog = r.target; }
      r.mat.opacity = i < 0 || di === i ? 1 : di < i ? 0.55 : 0.28;
    });
    pins.forEach((p) => {
      const { di } = p.userData; const show = di <= revealed && (i < 0 || di <= i || di <= revealed);
      p.userData.on = show; p.userData.big = i < 0 ? 0.75 : di === i ? 1 : 0.6;
      if (di === i && !instant) { p.userData.spring.v = 0.0001; p.userData.spring.t = 0; p.userData.wait = true; }
      else { p.userData.wait = false; p.userData.spring.t = show ? p.userData.big : 0; if (instant) p.userData.spring.v = p.userData.spring.t; }
    });
    const end = i < 0 && revealed >= 4;
    forkItems.forEach((g, k) => setTimeout(() => { g.userData.spring.t = end || youFork ? 1 : 0; }, end ? 400 + k * 180 : 0));
    car.visible = i !== 2; fam.visible = i === 2 || i < 0;
    if (i < 0) { fam.position.copy(P3(revealed >= 0 ? 'tidewater' : 'lax')).add(new Vector3(0.25, 0, 0.15)); car.position.copy(P3(revealed >= 4 ? 'laxcar' : revealed >= 0 ? 'tidewater' : 'lax')).add(new Vector3(-0.2, 0, 0.2)); car.visible = true; }
  }

  /* ---------- the loop ---------- */
  const tmp = new Vector3(), tan = new Vector3();
  stage.onFrame.push((dt, t) => {
    for (const k of ['tx', 'ty', 'tz', 'd', 'a', 'e']) rig[k] = damp(rig[k], want[k], 2.6, dt);
    const a = rig.a + Math.sin(t * 0.25) * 0.03, e = rig.e;
    camera.position.set(rig.tx + rig.d * Math.sin(a) * Math.cos(e), rig.ty + rig.d * Math.sin(e), rig.tz + rig.d * Math.cos(a) * Math.cos(e));
    camera.lookAt(rig.tx, rig.ty, rig.tz);
    routes.forEach((r, di) => {
      if (r.prog < r.target) r.prog = Math.min(r.target, r.prog + dt / 2.2);
      const n = Math.floor(r.prog * r.seg) * r.per; r.geo.setDrawRange(0, Math.min(r.total, n));
      if (di === cur) {
        r.stopFrac.forEach((f, si) => { const p = pins.find((q) => q.userData.di === di && q.userData.si === si); if (p?.userData.wait && r.prog >= f - 0.01) { p.userData.wait = false; p.userData.spring.t = p.userData.big; p.userData.spring.kick(4); } });
        const token = di === 2 ? fam : car;
        r.curve.getPointAt(Math.min(1, r.prog), tmp); r.curve.getTangentAt(Math.min(0.999, r.prog), tan);
        token.position.copy(tmp).setY(tmp.y - 0.07 + (token === car ? 0.02 : 0));
        token.rotation.y = Math.atan2(-tan.z, tan.x) + (token === fam ? Math.PI / 2 : 0);
      }
    });
    pins.forEach((p) => { const s = p.userData.spring.step(dt); p.visible = s > 0.01; p.scale.setScalar(Math.max(0.0001, s)); p.rotation.y += dt * 0.6; });
    forkItems.forEach((g) => { const s = g.userData.spring.step(dt); g.visible = s > 0.01; g.scale.setScalar(Math.max(0.0001, s)); });
    if (youFork) { const s = youFork.userData.spring.step(dt); youFork.scale.setScalar(Math.max(0.0001, s)); }
    scene.traverse((o) => { if (o.userData.bill) { o.quaternion.copy(camera.quaternion); o.scale.setScalar(Math.max(0.6, rig.d / 14)); } });
    heads.forEach((h) => { h.position.y = h.userData.y + Math.max(0, h.userData.hop.step(dt)) * 0.12; });
    fam.userData.step(dt);
    wheelBoost = damp(wheelBoost, 0, 1.2, dt);
    wheel.userData.wheel.rotation.z -= dt * (0.25 + wheelBoost * 4);
    waves.children.forEach((w) => { const [x, z, ph] = w.userData.p; const u = (t * 0.12 + ph) % 1; w.position.set(x - u * 0.8, 0.005, z + u * 0.3); w.material.opacity = Math.sin(u * Math.PI) * 0.75; });
    clouds.children.forEach((c, i) => { c.position.x = c.userData.x + Math.sin(t * 0.08 + i * 2) * 0.8; });
    conf.step(dt);
  });

  function setMode(m) {
    applyLight(stage, m);
    seaMat.color.set(m === 'dark' ? 0x2A5F93 : 0x59B8EA);
    night.visible = m === 'dark';
    routeMats.forEach((mm) => mm.color.set(routeColor()));
    forkGroup.traverse((o) => o.userData.redraw?.()); youFork?.traverse((o) => o.userData.redraw?.());
  }
  setMode(api.mode);

  const ray = new Raycaster(), v2 = new Vector2();
  const sceneApi = {
    overviewLabel: 'The whole trip · 5 days on one map',
    setDay(i, instant) { setDay(i, instant); },
    setMode,
    tap(x, y) {
      v2.set(x, y); ray.setFromCamera(v2, camera);
      const hit = ray.intersectObjects(pinMeshes.filter((m) => m.parent.visible), false)[0];
      if (!hit) return;
      const { di, si } = hit.object.userData; const p = hit.object.parent;
      p.userData.spring.kick(5); api.onStop(di, si);
      Object.assign(want, { tx: p.position.x, ty: p.position.y, tz: p.position.z + 0.1, d: Math.max(4.8, want.d * 0.75) });
    },
    cheer() {
      heads.forEach((h, i) => setTimeout(() => h.userData.hop.kick(4), i * 70)); fam.userData.cheer();
      wheelBoost = 1; conf.fire((car.visible ? car : fam).position.clone().add(new Vector3(0, 0.3, 0)));
    },
    fork(home) {
      if (youFork) return;
      const from = cur >= 0 ? P3(DAYS[cur].stops[DAYS[cur].stops.length - 1][5]) : P3('laxcar');
      const to = new Vector3(5.2, 0.3, -2.6);
      youFork = new Group(); youFork.add(dashed(from, to, 1.0, routeColor()));
      const l = label('Your fork', `from ${home.name} · just now`); l.position.copy(to).add(new Vector3(0, 0.6, 0)); youFork.add(l);
      const p = pin(api.mode === 'dark' ? 0xF5F5F7 : 0x0B0B0D, 1.1); p.position.copy(to); youFork.add(p);
      youFork.userData.spring = new Spring(0.0001, 140, 11); youFork.userData.spring.t = 1; scene.add(youFork);
      forkItems.forEach((g) => { g.userData.spring.t = 1; });
      frame(-1); api.onCaption(`<span class="eyebrow">Your fork · from ${home.name}</span><h2>It branches from here</h2><p>The dashed lines are where other families took it next.</p>`);
    },
    dispose() { stage.dispose(); },
  };
  setDay(-1, true);
  stage.show();
  return sceneApi;
});
