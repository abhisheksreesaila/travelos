// Prototype 3 · Globe to street: a small toy globe turns to Los Angeles while the family's plane flies in from
// home, then dives in and becomes five little day islands on a turntable. Swipe to turn the table; tap a pin.
// Zoom back out at the end and the globe shows where the forks went: arcs to every family that took it home.
import { CatmullRomCurve3, TubeGeometry, Raycaster, Vector2, CanvasTexture, SRGBColorSpace, PlaneGeometry, Quaternion } from 'three';
import {
  createStage, damp, Spring, Kit, M, props, ferrisWheel, pin, family, confetti, applyLight, lambert, basic, KIND,
  Group, Mesh, Vector3, BoxGeometry, CylinderGeometry, ConeGeometry, SphereGeometry, IcosahedronGeometry, CircleGeometry, TorusGeometry, MeshBasicMaterial, MeshLambertMaterial,
} from './core.js';
import { FORKS } from './trip.js';

window.GA3D.register((host, api) => {
  const stage = createStage(host, api, { fov: 34 });
  const { scene, camera } = stage;
  const DAYS = api.days;
  const R = 2, D2R = Math.PI / 180;
  const toVec = (lon, lat, r = R) => new Vector3(Math.cos(lat * D2R) * Math.cos(lon * D2R) * r, Math.sin(lat * D2R) * r, -Math.cos(lat * D2R) * Math.sin(lon * D2R) * r);

  /* ---------- the toy globe: rough hand-drawn continents, raised a little ---------- */
  const LANDS = [
    [[-168, 66], [-162, 70], [-140, 70], [-115, 73], [-95, 72], [-80, 73], [-65, 62], [-60, 56], [-55, 52], [-66, 45], [-70, 42], [-76, 38], [-81, 31], [-80, 25], [-83, 29], [-90, 30], [-97, 27], [-97, 22], [-92, 18], [-87, 21], [-88, 15], [-83, 9], [-79, 8], [-82, 7], [-86, 11], [-92, 14], [-105, 20], [-110, 24], [-112, 30], [-114, 31], [-110, 23], [-117, 32], [-118, 34], [-124, 40], [-124, 48], [-130, 55], [-140, 60], [-152, 60], [-158, 57], [-165, 61]],
    [[-73, 78], [-60, 82], [-30, 83], [-20, 75], [-22, 70], [-40, 65], [-44, 60], [-52, 64], [-58, 70], [-66, 76]],
    [[-80, 9], [-75, 11], [-62, 10], [-52, 5], [-35, -5], [-39, -15], [-48, -26], [-58, -35], [-65, -42], [-68, -52], [-74, -52], [-73, -40], [-71, -30], [-70, -18], [-76, -14], [-81, -5], [-79, 1]],
    [[-17, 21], [-16, 12], [-8, 4], [6, 4], [9, -1], [13, -11], [12, -18], [15, -27], [19, -35], [26, -34], [33, -26], [40, -15], [40, -10], [39, -5], [44, 1], [51, 11], [43, 12], [37, 19], [33, 28], [32, 31], [20, 32], [10, 37], [-1, 36], [-6, 36], [-10, 30]],
    [[-10, 36], [-9, 43], [-2, 44], [-5, 48], [2, 51], [8, 54], [8, 57], [5, 62], [10, 64], [16, 69], [25, 71], [40, 68], [60, 70], [70, 73], [80, 73], [100, 77], [115, 74], [130, 72], [150, 71], [170, 70], [180, 68], [178, 63], [163, 60], [157, 51], [142, 59], [135, 54], [140, 47], [132, 43], [128, 35], [121, 40], [122, 30], [110, 21], [106, 10], [100, 13], [103, 1], [98, 8], [97, 17], [92, 22], [88, 22], [80, 15], [77, 8], [73, 18], [67, 25], [57, 25], [50, 30], [48, 29], [51, 25], [56, 26], [59, 22], [52, 16], [43, 13], [39, 21], [34, 28], [35, 31], [33, 36], [27, 37], [26, 40], [23, 36], [20, 40], [16, 38], [12, 44], [8, 44], [3, 43], [-1, 37], [-6, 36]],
    [[114, -22], [122, -18], [130, -12], [137, -12], [142, -11], [146, -19], [153, -25], [151, -34], [146, -39], [140, -38], [135, -35], [131, -31], [124, -34], [115, -34], [113, -26]],
    [[-5, 50], [1, 51], [2, 53], [-1, 55], [-2, 58], [-5, 58], [-6, 56], [-3, 54], [-5, 52]],
    [[130, 31], [135, 34], [140, 35], [142, 40], [140, 45], [145, 44], [140, 41], [136, 37], [132, 35]],
    [[44, -25], [47, -25], [50, -15], [49, -12], [44, -16]], [[109, 1], [118, 7], [119, 1], [116, -4], [110, -3]], [[95, 5], [106, -6], [104, -6], [96, 2]],
    [[166, -46], [174, -41], [178, -38], [173, -35], [172, -41]],
  ];
  const inPoly = (lon, lat, P) => { let c = false; for (let i = 0, j = P.length - 1; i < P.length; j = i++) { const [xi, yi] = P[i], [xj, yj] = P[j]; if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) c = !c; } return c; };
  const isLand = (lon, lat) => lat < -68 || LANDS.some((P) => inPoly(lon, lat, P));
  const ll = (x, y, z) => { const r = Math.hypot(x, y, z); return [Math.atan2(-z, x) / D2R, Math.asin(y / r) / D2R]; };
  const desert = (lon, lat) => (lat > 15 && lat < 32 && lon > -15 && lon < 58) || (lat > -30 && lat < -20 && lon > 118 && lon < 142) || (lat > 28 && lat < 37 && lon > -117 && lon < -104);
  const geo = new IcosahedronGeometry(R, 26);
  const gp = geo.attributes.position;
  for (let i = 0; i < gp.count; i++) { const [lon, lat] = ll(gp.getX(i), gp.getY(i), gp.getZ(i)); const s = isLand(lon, lat) ? 1.025 : 1; gp.setXYZ(i, gp.getX(i) * s, gp.getY(i) * s, gp.getZ(i) * s); }
  const hash = (a, b) => { const s = Math.sin(a * 12.9898 + b * 78.233) * 43758.5453; return s - Math.floor(s); };
  const globeKit = new Kit().addFaces(geo, (c, x, y, z) => {
    const r = Math.hypot(x, y, z), [lon, lat] = ll(x, y, z), h = hash(lon, lat);
    if (Math.abs(lat) > 70 && r > R * 1.01) return c.set(0xF4F7FA);
    if (r > R * 1.02) return c.set(desert(lon, lat) ? (h > 0.5 ? 0xEAC98A : 0xE2BE7C) : [0x8BCF6A, 0x7DC05C, 0x96D676][Math.floor(h * 3)]);
    if (r > R * 1.004) return c.set(0xF3DCA6);
    return c.set(h > 0.5 ? 0x4FB3E8 : 0x47AADF);
  });
  const globeMesh = globeKit.mesh();
  const tilt = new Group(), spin = new Group(); tilt.add(spin); spin.add(globeMesh); scene.add(tilt);
  const clouds = new Group(); spin.add(clouds);
  for (let i = 0; i < 9; i++) { const k = new Kit(); props.cloud(k, 0, 0, 0, 0.32); const m = k.mesh(); const v = toVec(hash(i, 1) * 360 - 180, hash(i, 2) * 120 - 60, R * 1.16); m.position.copy(v); m.lookAt(v.clone().multiplyScalar(2)); m.rotateX(Math.PI / 2); clouds.add(m); }

  const LA = [-118.24, 34.05];
  const laPins = [0x0B0B0D, 0xF5F5F7].map((c) => { const p = pin(c, 0.7); p.position.copy(toVec(...LA, R * 1.025)); p.lookAt(toVec(...LA, R * 3)); p.rotateX(Math.PI / 2); spin.add(p); return p; });
  const ring = new Mesh(new TorusGeometry(0.16, 0.018, 6, 28), basic(0x0B0B0D, { transparent: true })); ring.position.copy(toVec(...LA, R * 1.03)); ring.lookAt(toVec(...LA, R * 3)); spin.add(ring);

  // arcs: home → LA for the family, LA → home for every fork
  function arc(from, to, lift = 0.5) {
    const a = toVec(...from).normalize(), b = toVec(...to).normalize(), pts = [], ang = a.angleTo(b);
    for (let i = 0; i <= 48; i++) { const t = i / 48; const v = a.clone().multiplyScalar(Math.sin((1 - t) * ang) / Math.sin(ang)).add(b.clone().multiplyScalar(Math.sin(t * ang) / Math.sin(ang))); pts.push(v.multiplyScalar(R * (1.03 + Math.sin(Math.PI * t) * lift * Math.min(1, ang) * (ang > 1.6 ? 0.55 : 1)))); }
    return new CatmullRomCurve3(pts);
  }
  const CITY = { Chicago: [-87.6, 41.9], Toronto: [-79.4, 43.7], London: [-0.1, 51.5], Sydney: [151.2, -33.9], 'Mexico City': [-99.1, 19.4] };
  function arcMesh(curve, color, r = 0.018) { const g = new TubeGeometry(curve, 64, r, 5, false); const m = new Mesh(g, basic(color)); g.setDrawRange(0, 0); m.userData = { total: g.index.count, per: 30, seg: 64, prog: 0, target: 0 }; spin.add(m); return m; }
  const homeArc = arcMesh(arc(CITY.Chicago, LA, 0.45), 0x0B0B0D, 0.02);
  const homePin = pin(0xC2410C, 0.45); homePin.position.copy(toVec(...CITY.Chicago, R * 1.025)); homePin.lookAt(toVec(...CITY.Chicago, R * 3)); homePin.rotateX(Math.PI / 2); spin.add(homePin);
  const toyPlane = new Group(); { const k = new Kit(); k.add(new CylinderGeometry(0.03, 0.04, 0.28, 6), 0xFFFFFF, M(0, 0, 0, Math.PI / 2)).add(new BoxGeometry(0.3, 0.012, 0.07), 0xFFFFFF, M(0, 0, 0.01)).add(new BoxGeometry(0.1, 0.06, 0.012), KIND.flight, M(0, 0.03, 0.12)); toyPlane.add(k.mesh()); } spin.add(toyPlane);
  const forkArcs = FORKS.filter((f) => f.home && CITY[f.home] && f.home !== 'Chicago').map((f) => {
    const m = arcMesh(arc(LA, CITY[f.home], 0.6), 0x8E8E99, 0.014);
    const pk = pin(parseInt(f.av.slice(1), 16), 0.42); pk.position.copy(toVec(...CITY[f.home], R * 1.025)); pk.lookAt(toVec(...CITY[f.home], R * 3)); pk.rotateX(Math.PI / 2); pk.scale.setScalar(0.0001); pk.userData.spring = new Spring(0, 180, 12); spin.add(pk);
    m.userData.pin = pk; return m;
  });
  let youArc = null;

  /* ---------- the day islands on a turntable ---------- */
  const table = new Group(); table.visible = false; scene.add(table);
  const RING = 5.4, N = DAYS.length;
  const islands = [], pinMeshes = [];
  const SPOT = { // where each stop's pin stands on its island (local x, z)
    lax: [0.9, 0.7], tacos: [0.5, -0.6], tidewater: [0.1, -0.2], pier: [-0.7, 0.5], pony: [0.8, 0.5], ferndell: [-0.8, 0.6], observatory: [0, -0.4], bikes: [-0.8, 0.4], abbot: [0.7, -0.5], canals: [0.2, 0.5],
    dume: [-0.4, 0.3], malibufarm: [0.6, -0.6], zuma: [0.8, 0.6], getty: [-0.1, -0.3], gettylunch: [0.6, 0.2], laxcar: [0.9, 0.8], laxfly: [-0.8, 0.7],
  };
  function island(i) {
    const g = new Group(), k = new Kit(), top = new CylinderGeometry(1.7, 1.55, 0.42, 30, 1);
    const sea = (x, z) => (i === 0 && x < -0.35) || (i === 3 && z < -0.1 && x < 0.9);
    k.addFaces(top, (c, x, y, z) => c.set(y < 0.2 ? 0xE2D3B5 : sea(x, z) ? 0x59B8EA : [0xF3DCA6, 0x9DCE70, 0xA9D77C, 0xF0D8A8, 0x9BC46A][i]));
    k.add(new CylinderGeometry(1.78, 1.78, 0.08, 30), 0xFFFFFF, M(0, -0.25, 0));
    const y = 0.21;
    if (i === 0) { props.pier(k, -1.0, y + 0.02, 0.3, 1.0, 1.3); [[0.3, -1.0], [0.9, -0.2], [-0.1, 0.9]].forEach(([x, z], j) => props.palm(k, x, y, z, 0.9, j)); props.house(k, 0.1, y, -0.2, 1.3, 0xF6A6C1, 0xFFFFFF); props.house(k, 0.55, y, -0.65, 1, 0xFFE3C2, 0xE94F37); }
    if (i === 1) { k.add(new ConeGeometry(0.95, 0.75, 9), 0x7DB45A, M(0, y + 0.37, -0.35)); props.observatory(k, 0, y + 0.7, -0.4, 0.75); [[-1.1, -0.3], [1.0, -0.6], [-0.6, 0.9], [1.2, 0.2]].forEach(([x, z]) => props.tree(k, x, y, z, 1.1)); for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) k.add(new BoxGeometry(0.12, 0.01, 0.12), (r + c) % 2 ? 0xE94F37 : 0xFFFFFF, M(-0.85 + c * 0.12, y + 0.01, 0.45 + r * 0.12)); k.add(new BoxGeometry(0.3, 0.14, 0.12), 0xB5652E, M(0.8, y + 0.2, 0.5)).add(new BoxGeometry(0.1, 0.12, 0.08), 0xB5652E, M(0.97, y + 0.3, 0.5)); for (const dx of [-0.1, 0.1]) for (const dz of [-0.04, 0.04]) k.add(new CylinderGeometry(0.02, 0.02, 0.14, 4), 0xB5652E, M(0.8 + dx, y + 0.07, 0.5 + dz)); }
    if (i === 2) { for (const z of [-0.15, 0.55]) k.add(new BoxGeometry(2.9, 0.02, 0.18), 0x59B8EA, M(0, y + 0.005, z)); for (let j = 0; j < 9; j++) { const x = -1.1 + (j % 5) * 0.55, z = j < 5 ? -0.6 : 0.2; props.house(k, x, y, z, 0.9, [0xFFE3C2, 0xD8F0FF, 0xFFD6E5, 0xE3F7D3][j % 4], [0x4FA3E3, 0xF07D5D, 0x6CC57C, 0xF2C14E][j % 4]); } for (const x of [-0.9, -0.55]) { k.add(new TorusGeometry(0.07, 0.012, 4, 12), 0x333333, M(x, y + 0.08, 0.95)).add(new TorusGeometry(0.07, 0.012, 4, 12), 0x333333, M(x + 0.2, y + 0.08, 0.95)).add(new BoxGeometry(0.22, 0.015, 0.015), [0xE94F37, 0xFFC93C][x < -0.7 ? 0 : 1], M(x + 0.1, y + 0.13, 0.95)); } props.palm(k, 1.2, y, 0.9, 0.9, 2); }
    if (i === 3) { [[-0.4, 0.3], [-0.1, 0.1], [-0.6, 0.0], [0.3, -0.2], [-0.9, -0.3]].forEach(([x, z], j) => props.rock(k, x, y, z, 1.2 + j * 0.15)); for (const [x, z] of [[-0.2, 0.5], [0.1, 0.35]]) k.add(new CircleGeometry(0.16, 10), 0x7FD6E8, M(x, y + 0.012, z, -Math.PI / 2)); props.starfish(k, -0.15, y + 0.03, 0.5, 1.4); props.starfish(k, 0.15, y + 0.03, 0.35, 1.2, 0xFF5D8F); k.add(new BoxGeometry(0.28, 0.2, 0.24), 0xFFD43B, M(0.9, y + 0.42, 0.6)).add(new ConeGeometry(0.24, 0.12, 4), 0x0369A1, M(0.9, y + 0.58, 0.6, 0, Math.PI / 4)); for (const dx of [-0.1, 0.1]) k.add(new CylinderGeometry(0.02, 0.02, 0.32, 4), 0x8A5A2B, M(0.9 + dx, y + 0.16, 0.6)); props.palm(k, 1.1, y, -0.3, 0.9, 1); }
    if (i === 4) { k.add(new ConeGeometry(1.1, 0.5, 10), 0x86B35A, M(-0.1, y + 0.25, -0.3)); props.getty(k, -0.1, y + 0.45, -0.3, 0.8); k.add(new BoxGeometry(1.6, 0.02, 0.03), 0x5C5C66, M(0.5, y + 0.3, 0.5, 0, 0.6, 0.3)); k.add(new BoxGeometry(2.4, 0.02, 0.3), 0x5E6470, M(0.2, y + 0.01, 1.05, 0, -0.15)); [[-1.2, 0.2], [1.1, -0.4]].forEach(([x, z]) => props.tree(k, x, y, z, 1.1)); }
    g.add(k.mesh());
    if (i === 0) { const w = ferrisWheel(0.75); w.position.set(-1.2, y + 0.04, 0.2); w.rotation.y = 1.3; g.add(w); g.userData.wheel = w.userData.wheel; }
    if (i === 4) { const tram = new Mesh(new BoxGeometry(0.16, 0.1, 0.1), lambert(0xE94F37)); g.add(tram); g.userData.tram = tram; const pl = new Group(); const pk = new Kit(); pk.add(new CylinderGeometry(0.04, 0.05, 0.4, 6), 0xFFFFFF, M(0, 0, 0, 0, 0, Math.PI / 2)).add(new BoxGeometry(0.1, 0.012, 0.42), 0xFFFFFF).add(new BoxGeometry(0.012, 0.1, 0.1), KIND.flight, M(-0.17, 0.05, 0)); pl.add(pk.mesh()); g.add(pl); g.userData.jet = pl; }
    const fam = family(0.72); fam.position.set(...(i === 0 ? [0.55, y, 0.35] : i === 1 ? [0.3, y, 0.6] : i === 2 ? [-0.2, y, 0.95] : i === 3 ? [0.35, y, 0.45] : [0.7, y, 0.55])); fam.rotation.y = 0.3; g.add(fam); g.userData.fam = fam;
    DAYS[i].stops.forEach((s, si) => { const p = pin(KIND[s[2]], 0.75); const [x, z] = SPOT[s[5]]; p.position.set(x, y + (i === 1 && s[5] === 'observatory' ? 0.95 : i === 4 && s[5] === 'getty' ? 0.75 : 0.02), z); p.userData = { ...p.userData, di: i, si, spring: new Spring(1, 200, 12) }; p.children[0].userData = { di: i, si }; pinMeshes.push(p.children[0]); g.add(p); });
    const a = (i / N) * Math.PI * 2; g.position.set(Math.sin(a) * RING, 0, Math.cos(a) * RING); g.rotation.y = a;
    table.add(g); islands.push(g);
  }
  for (let i = 0; i < N; i++) island(i);
  const starK = new Kit(); for (let i = 0; i < 60; i++) starK.add(new IcosahedronGeometry(0.04, 0), 0xFFFFFF, M(-12 + hash(i, 3) * 24, 3 + hash(i, 4) * 6, -14 + hash(i, 5) * 10));
  const stars = starK.mesh(new MeshBasicMaterial({ vertexColors: true })); scene.add(stars);
  const conf = confetti(scene);

  // a quick dip between the globe and the islands (an opaque fade, no blur)
  const dip = document.createElement('div'); dip.style.cssText = 'position:absolute;inset:0;background:var(--stage);opacity:0;pointer-events:none;transition:opacity 220ms cubic-bezier(.2,.8,.2,1)'; stage.canvas.after(dip);

  function label(text, sub, ink) {
    const c = document.createElement('canvas'), x = c.getContext('2d'); const W = 380, H = 104; c.width = W; c.height = H;
    const tex = new CanvasTexture(c); tex.colorSpace = SRGBColorSpace;
    const draw = () => { const d = api.mode === 'dark'; x.clearRect(0, 0, W, H); x.fillStyle = ink ? (d ? '#F5F5F7' : '#0B0B0D') : d ? '#1C1C1F' : '#FFFFFF'; x.beginPath(); x.roundRect(4, 4, W - 8, H - 8, 40); x.fill(); x.fillStyle = ink ? (d ? '#0B0B0D' : '#FFFFFF') : d ? '#F5F5F7' : '#0B0B0D'; x.font = '650 30px Geist, system-ui'; x.fillText(text, 28, 46); x.globalAlpha = 0.7; x.font = '500 24px Geist, system-ui'; x.fillText(sub, 28, 80); x.globalAlpha = 1; tex.needsUpdate = true; };
    draw(); const m = new Mesh(new PlaneGeometry(W / 300, H / 300), new MeshBasicMaterial({ map: tex, transparent: true, depthTest: false })); m.renderOrder = 6; m.userData.redraw = draw; return m;
  }
  const labels = [];
  forkArcs.forEach((m, k) => { const f = FORKS.filter((q) => q.home && CITY[q.home] && q.home !== 'Chicago')[k]; const l = label(f.who, f.home); l.position.copy(toVec(...CITY[f.home], R * 1.35)); l.scale.setScalar(0.0001); m.userData.label = l; spin.add(l); labels.push(l); });

  /* ---------- state and camera ---------- */
  let mode = 'globe', cur = -1, revealed = api.capture ? 4 : -1, tableAng = 0, tableWant = 0, dragFrom = 0, dragging = false;
  let spinY = 0.6, spinWant = null, tiltX = 0.25, camD = 8.5, camWant = 8.5, intro = 0, diveT = -1;
  const laSpin = -Math.PI / 2 - LA[0] * D2R;
  const nearAngle = (from, to) => to + Math.round((from - to) / (Math.PI * 2)) * Math.PI * 2;
  const globeD = () => (stage.aspect < 1 ? 13.5 : 9.2);
  stage.resized = () => { if (mode === 'globe' && diveT < 0) camWant = globeD(); };

  function showForks(on) {
    forkArcs.forEach((m, k) => { m.userData.target = on ? 1 : 0; if (!on) m.userData.prog = 0; setTimeout(() => { m.userData.pin.userData.spring.t = on ? 1 : 0; m.userData.label.userData.on = on; }, on ? 500 + k * 220 : 0); });
  }
  function toGlobe(instant) {
    mode = 'globe'; table.visible = false; tilt.visible = true; camWant = globeD(); if (instant) camD = camWant;
    const end = revealed >= 4 || youArc;
    spinWant = nearAngle(spinY, laSpin + (end ? 0.35 : 0)); tiltX = 34.05 * D2R * 0.7;
    homeArc.userData.target = 1; if (instant) homeArc.userData.prog = end ? 1 : 0;
    showForks(!!end);
  }
  function toIsland(i, instant) {
    if (mode === 'globe' && !instant) { // dive: face LA, rush in, dip, land on the island
      spinWant = nearAngle(spinY, laSpin); diveT = 0; camWant = R * 1.25; homeArc.userData.target = 1; homeArc.userData.prog = 1;
      setTimeout(() => { dip.style.opacity = 1; }, 650);
      setTimeout(() => { mode = 'islands'; tilt.visible = false; table.visible = true; tableAng = tableWant = -(i / N) * Math.PI * 2; diveT = -1; dip.style.opacity = 0; arrive(i); }, 900);
      return;
    }
    mode = 'islands'; tilt.visible = false; table.visible = true;
    tableWant = nearAngle(tableAng, -(i / N) * Math.PI * 2); if (instant) tableAng = tableWant;
    arrive(i, instant ? 0 : 500);
  }
  function arrive(i, delay = 200) { setTimeout(() => islands[i].userData.fam.userData.cheer(), delay); islands[i].children.forEach((c) => { if (c.userData.spring) { c.userData.spring.v = 0.0001; c.userData.spring.t = 1; c.userData.spring.kick(2); } }); }

  const lookAt = new Vector3(), tmp = new Vector3(), pq = new Quaternion();
  stage.onFrame.push((dt, t) => {
    const portrait = stage.aspect < 1;
    if (mode === 'globe') {
      if (spinWant == null) spinY += dt * 0.35; else spinY = damp(spinY, spinWant + (diveT < 0 ? Math.sin(t * 0.3) * 0.05 : 0), 2.2, dt);
      spin.rotation.y = spinY; tilt.rotation.x = damp(tilt.rotation.x, tiltX, 2, dt);
      camD = damp(camD, camWant, diveT >= 0 ? 3.4 : 2.2, dt);
      camera.position.set(0, portrait ? 0.4 : 0.6, camD); camera.lookAt(0, portrait ? -0.25 : 0, 0);
      clouds.rotation.y += dt * 0.04;
      ring.scale.setScalar(1 + ((t * 0.8) % 1) * 1.6); ring.material.opacity = 1 - ((t * 0.8) % 1);
      for (const m of [homeArc, ...forkArcs, youArc].filter(Boolean)) { const u = m.userData; if (u.prog < u.target) u.prog = Math.min(1, u.prog + dt / 1.8); m.geometry.setDrawRange(0, Math.floor(u.prog * u.seg) * u.per); }
      const hp = homeArc.userData.prog; homeArc.geometry.parameters.path.getPointAt(Math.min(1, hp), tmp); toyPlane.position.copy(tmp); toyPlane.visible = hp > 0.01 && hp < 0.995;
      homeArc.geometry.parameters.path.getPointAt(Math.min(1, hp + 0.02), lookAt); toyPlane.lookAt(lookAt);
      forkArcs.forEach((m) => { const p = m.userData.pin; p.scale.setScalar(Math.max(0.0001, p.userData.spring.step(dt) * 0.42)); const l = m.userData.label; l.userData.s = damp(l.userData.s || 0, l.userData.on ? 1 : 0, 6, dt); l.scale.setScalar(Math.max(0.0001, l.userData.s)); });
      if (youArc) { const p = youArc.userData.pin; p.scale.setScalar(Math.max(0.0001, p.userData.spring.step(dt) * 0.55)); youArc.userData.label.scale.setScalar(Math.max(0.0001, p.userData.spring.v)); }
      spin.getWorldQuaternion(pq).invert(); labels.forEach((l) => { l.quaternion.copy(pq).multiply(camera.quaternion); });
    } else {
      tableAng = dragging ? tableAng : damp(tableAng, tableWant, 3, dt);
      table.rotation.y = tableAng;
      const back = portrait ? 9.6 : 6.4;
      camera.position.set(0, portrait ? 4.4 : 3.1, RING + back); camera.lookAt(0, portrait ? -1.1 : 0.1, RING);
      islands.forEach((g) => { g.userData.fam.userData.step(dt); g.children.forEach((c) => { if (c.userData.spring) { c.scale.setScalar(Math.max(0.0001, c.userData.spring.step(dt) * 0.75)); c.rotation.y += dt * 0.5; } }); });
      if (islands[0].userData.wheel) islands[0].userData.wheel.rotation.z -= dt * 0.4;
      const tr = islands[4].userData.tram, u = (t * 0.15) % 1; const k2 = (u - 0.5) * 1.5; tr.position.set(0.5 + 0.788 * k2, 0.57 + 0.296 * k2, 0.5 - 0.539 * k2); tr.rotation.set(0, 0.6, 0.3);
      const jet = islands[4].userData.jet, ju = (t * 0.2) % 1; jet.position.set(-1 + ju * 3, 0.24 + Math.max(0, ju - 0.35) * 1.6, 1.05 - ju * 0.45); jet.rotation.set(0, -0.15, ju > 0.35 ? 0.25 : 0); jet.visible = ju < 0.9;
    }
    conf.step(dt);
  });

  function setMode(m) {
    applyLight(stage, m);
    stars.visible = m === 'dark'; laPins[0].visible = m !== 'dark'; laPins[1].visible = m === 'dark';
    homeArc.material.color.set(m === 'dark' ? 0xF5F5F7 : 0x0B0B0D);
    ring.material.color.set(m === 'dark' ? 0xF5F5F7 : 0x0B0B0D);
    labels.forEach((l) => l.userData.redraw()); youArc?.userData.label.userData.redraw();
    if (youArc) youArc.material.color.set(m === 'dark' ? 0xF5F5F7 : 0x0B0B0D);
  }
  setMode(api.mode);

  const ray = new Raycaster(), v2 = new Vector2();
  const sceneApi = {
    overviewLabel: 'From Chicago to LA · and where the forks went',
    beats: [[-1, 4200], [0, 3200], [1, 3000], [2, 3000], [3, 3000], [4, 3200], [-1, 0]],
    setDay(i, instant) {
      const prev = cur; cur = i; if (i > revealed) revealed = i;
      if (i < 0) { if (prev >= 0 && !instant) { dip.style.opacity = 1; setTimeout(() => { toGlobe(false); camD = R * 1.3; dip.style.opacity = 0; }, 230); } else toGlobe(instant); if (prev < 0 && !instant) { homeArc.userData.prog = 0; spinWant = null; setTimeout(() => { if (cur < 0) spinWant = nearAngle(spinY, laSpin); }, 900); } }
      else toIsland(i, instant);
    },
    setMode,
    dragStart() { dragging = true; dragFrom = mode === 'globe' ? spinY : tableAng; },
    dragMove(f) { if (mode === 'globe') { spinWant = dragFrom + f * 3; } else tableAng = dragFrom + f * 2.4; },
    dragEnd(f, vel) {
      dragging = false;
      if (mode === 'globe') { if (Math.abs(f) < 0.05) return; if (f < 0) { api.onDay(0); sceneApi.setDay(0); } return; }
      const raw = -(tableAng - vel * 0.6) / (Math.PI * 2 / N); let i = ((Math.round(raw) % N) + N) % N;
      if (i === cur && Math.abs(f) > 0.06) i = Math.max(0, Math.min(N - 1, cur + (f < 0 ? 1 : -1)));
      cur = i; tableWant = nearAngle(tableAng, -(i / N) * Math.PI * 2); arrive(i, 300); api.onDay(i);
    },
    tap(x, y) {
      if (mode !== 'islands') { if (cur < 0) { api.onDay(0); sceneApi.setDay(0); } return; }
      v2.set(x, y); ray.setFromCamera(v2, camera);
      const hit = ray.intersectObjects(pinMeshes, false)[0]; if (!hit) return;
      const p = hit.object.parent; p.userData.spring.kick(5); api.onStop(hit.object.userData.di, hit.object.userData.si);
    },
    cheer() {
      if (mode === 'islands' && cur >= 0) { islands[cur].userData.fam.userData.cheer(); conf.fire(islands[cur].getWorldPosition(new Vector3()).add(new Vector3(0, 0.6, 0))); }
      else { ring.scale.setScalar(3); conf.fire(new Vector3(0, 1.2, 1.6)); spinWant = (spinWant ?? spinY) + Math.PI * 2; }
    },
    fork(home) {
      if (youArc) return;
      youArc = arcMesh(arc(LA, [home.lon, home.lat], 0.7), api.mode === 'dark' ? 0xF5F5F7 : 0x0B0B0D, 0.022); youArc.userData.target = 1;
      const pk = pin(api.mode === 'dark' ? 0xF5F5F7 : 0x0B0B0D, 0.55); pk.position.copy(toVec(home.lon, home.lat, R * 1.025)); pk.lookAt(toVec(home.lon, home.lat, R * 3)); pk.rotateX(Math.PI / 2); pk.scale.setScalar(0.0001); pk.userData.spring = new Spring(0, 160, 10); setTimeout(() => { pk.userData.spring.t = 1; }, 1200); spin.add(pk); youArc.userData.pin = pk;
      const l = label('You', `${home.name} · your fork`, true); l.position.copy(toVec(home.lon, home.lat, R * 1.4)); l.scale.setScalar(0.0001); spin.add(l); labels.push(l); youArc.userData.label = l;
      cur = -1; api.onDay(-1);
      if (mode === 'islands') { dip.style.opacity = 1; setTimeout(() => { toGlobe(false); dip.style.opacity = 0; spinWant = nearAngle(spinY, -Math.PI / 2 - ((home.lon + LA[0]) / 2) * D2R); }, 230); } else { toGlobe(false); spinWant = nearAngle(spinY, -Math.PI / 2 - ((home.lon + LA[0]) / 2) * D2R); }
      api.onCaption(`<span class="eyebrow">Your fork · from ${home.name}</span><h2>The trip just reached ${home.name}</h2><p>Every arc is a family who took it home and made it theirs.</p>`);
    },
    dispose() { stage.dispose(); },
  };
  toGlobe(true);
  stage.show();
  return sceneApi;
});
