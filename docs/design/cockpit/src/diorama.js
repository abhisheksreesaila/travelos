/* Direction 1's map: a toy diorama of the real Tahoe basin, drawn with three.js (tree-shaken r187).
   Ground: the AWS Terrain Tiles elevation grid (data/dem.js) as a chunky low-poly tile, coloured by height and slope
   (valley, forest, snow, rock) with exaggerated relief, so the passes that need chains read at a glance.
   Water: OpenStreetMap lake outlines. Roads and the day's route: OpenStreetMap and OSRM lines draped on the ground.
   Weather happens in the scene: snow falls (density is a draw range over one pool, as in Meng To's threejs-weather),
   clouds drift, wind leans the snow; dark mode turns the diorama to night with the towns' lights on.
   Render loop after Meng To's ThreeUI Gallery: pause off screen and in hidden tabs, one still frame under reduced motion,
   pixel ratio capped at 2. Labels are DOM (crisp, 16 px, accessible), placed by projecting each pin every frame. */
import {
  WebGLRenderer, Scene, PerspectiveCamera, BufferGeometry, BufferAttribute, Mesh, MeshLambertMaterial, MeshPhongMaterial,
  MeshBasicMaterial, HemisphereLight, DirectionalLight, Color, Vector3, Shape, ShapeGeometry, InstancedMesh, ConeGeometry,
  CylinderGeometry, SphereGeometry, BoxGeometry, Object3D, Points, PointsMaterial, Group, IcosahedronGeometry,
  CanvasTexture, PlaneGeometry, Fog, SRGBColorSpace,
} from 'three';

const G = window.GEO, D = window.DEM;
const [W0, S0, E0, N0] = G.bbox;
const KW = D.km[0], KH = D.km[1], EX = 2.4, BASE = 1250;
const X = (lon) => ((lon - W0) / (E0 - W0) - .5) * KW;
const Z = (lat) => ((N0 - lat) / (N0 - S0) - .5) * KH;
const YH = (h) => (h - BASE) / 1000 * EX;
const LAKE_H = 1897;

// ---- elevation ----
const raw = atob(D.data), q = new Uint16Array(raw.length / 2);
for (let i = 0; i < q.length; i++) q[i] = raw.charCodeAt(i * 2) | (raw.charCodeAt(i * 2 + 1) << 8);
const H = new Float32Array(q.length);
for (let i = 0; i < q.length; i++) H[i] = D.min + q[i] / 65535 * (D.max - D.min);
function hAt(lon, lat) {
  const gx = Math.max(0, Math.min(D.w - 1.001, (lon - W0) / (E0 - W0) * D.w - .5));
  const gy = Math.max(0, Math.min(D.h - 1.001, (N0 - lat) / (N0 - S0) * D.h - .5));
  const x0 = gx | 0, y0 = gy | 0, fx = gx - x0, fy = gy - y0, i = y0 * D.w + x0;
  return H[i] * (1 - fx) * (1 - fy) + H[i + 1] * fx * (1 - fy) + H[i + D.w] * (1 - fx) * fy + H[i + D.w + 1] * fx * fy;
}
const yAt = (lon, lat) => YH(hAt(lon, lat));
function inPoly(lon, lat, ring) {
  let c = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) c = !c;
  }
  return c;
}
const TAHOE = G.lakes.tahoe[0];
const inLake = (lon, lat) => Object.values(G.lakes).some((rs) => rs.some((r) => inPoly(lon, lat, r)));
function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
// smooth value noise in km: patches of snow and stands of trees instead of per-face speckle
function hash(i, j) { let h = (i * 374761393 + j * 668265263) | 0; h = (h ^ (h >>> 13)) * 1274126177; return ((h ^ (h >>> 16)) >>> 0) / 4294967296; }
function vnoise(x, y) { const i = Math.floor(x), j = Math.floor(y), fx = x - i, fy = y - j, sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
  const a = hash(i, j), b = hash(i + 1, j), c = hash(i, j + 1), d = hash(i + 1, j + 1); return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy; }
const fbm = (x, z) => vnoise(x / 3.2, z / 3.2) * .65 + vnoise(x / 1.1 + 9, z / 1.1 - 4) * .35;

const PAL = {
  light: { valley: '#D6CAB4', sage: '#B9B39A', forest: '#3F604B', snow: '#F3F6F9', rock: '#A7ADB7', bed: '#5A7FA8', side: '#8C7E6F', side2: '#6D6156',
    water: '#3E7DC8', road: '#6E6E78', route: '#0B0B0D', routeCase: '#FFFFFF', tree: '#2F5B44', cap: '#F4F7FA', hemiSky: '#FFFFFF', hemiGround: '#B8AE9E', hemi: 1.15, sun: '#FFF4E0', sunI: 1.45 },
  dark: { valley: '#3C372F', sage: '#3F4238', forest: '#1E3326', snow: '#8F9AAE', rock: '#545A66', bed: '#203A57', side: '#3A332D', side2: '#2A2420',
    water: '#1D4A7C', road: '#7C7C88', route: '#F5F5F7', routeCase: '#0B0B0D', tree: '#1A2C21', cap: '#B9C3D6', hemiSky: '#8FA6D6', hemiGround: '#2A2620', hemi: .62, sun: '#B8CBFF', sunI: .7 },
};

function terrain(p) {
  const step = 2, w = Math.floor((D.w - 1) / step) + 1, h = Math.floor((D.h - 1) / step) + 1;
  const vx = [], r = rng(5);
  const pos = [], col = [];
  const c = (hex) => new Color(hex);
  const C = Object.fromEntries(Object.entries(p).filter(([k, v]) => typeof v === 'string' && v[0] === '#').map(([k, v]) => [k, c(v)]));
  const pt = (i, j) => {
    const lon = W0 + (i * step + .5) / D.w * (E0 - W0), lat = N0 - (j * step + .5) / D.h * (N0 - S0);
    return [X(lon), YH(H[Math.min(D.h - 1, j * step) * D.w + Math.min(D.w - 1, i * step)]), Z(lat), lon, lat];
  };
  const grid = []; for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) grid.push(pt(i, j));
  const tmp = new Color();
  const face = (a, b, d) => {
    pos.push(a[0], a[1], a[2], b[0], b[1], b[2], d[0], d[1], d[2]);
    const hm = ((a[1] + b[1] + d[1]) / 3) / EX * 1000 + BASE;
    // face normal for slope
    const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2], wx = d[0] - a[0], wy = d[1] - a[1], wz = d[2] - a[2];
    const nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx, nl = Math.hypot(nx, ny, nz) || 1;
    const up = Math.abs(ny / nl);
    const lon = (a[3] + b[3] + d[3]) / 3, lat = (a[4] + b[4] + d[4]) / 3;
    const cx = (a[0] + b[0] + d[0]) / 3, cz = (a[2] + b[2] + d[2]) / 3, n = fbm(cx, cz), jit = (r() - .5) * .05;
    if (hm < LAKE_H + 3 && inPoly(lon, lat, TAHOE)) tmp.copy(C.bed);
    else if (up < .55 && hm > 2200) tmp.copy(C.rock).lerp(C.snow, .25);
    else if (hm < 1540) tmp.copy(C.valley).lerp(C.sage, n * .5);
    else if (hm < 1820) tmp.copy(C.valley).lerp(C.snow, Math.min(1, Math.max(0, (hm - 1540) / 280 + (n - .5) * .9)));
    else tmp.copy(C.snow).lerp(C.rock, up < .7 ? .18 : 0);
    tmp.offsetHSL(0, 0, jit);
    for (let k = 0; k < 3; k++) col.push(tmp.r, tmp.g, tmp.b);
  };
  for (let j = 0; j < h - 1; j++) for (let i = 0; i < w - 1; i++) {
    const a = grid[j * w + i], b = grid[j * w + i + 1], d = grid[(j + 1) * w + i], e = grid[(j + 1) * w + i + 1];
    if ((i + j) % 2) { face(a, d, b); face(b, d, e); } else { face(a, d, e); face(a, e, b); }
  }
  const g = new BufferGeometry();
  g.setAttribute('position', new BufferAttribute(new Float32Array(pos), 3));
  g.setAttribute('color', new BufferAttribute(new Float32Array(col), 3));
  g.computeVertexNormals();
  const mesh = new Mesh(g, new MeshLambertMaterial({ vertexColors: true, flatShading: true }));
  // the toy tile's sides: earth walls down to a base
  const side = [], sc = [], cs = c(p.side), cs2 = c(p.side2), snowc = c(p.snow);
  const wall = (pts) => {
    for (let k = 0; k < pts.length - 1; k++) {
      const a = pts[k], b = pts[k + 1], y0 = -1.1;
      side.push(a[0], a[1], a[2], a[0], y0, a[2], b[0], b[1], b[2], b[0], b[1], b[2], a[0], y0, a[2], b[0], y0, b[2]);
      for (const cc of [snowc, cs2, snowc, snowc, cs2, cs2]) sc.push(cc.r, cc.g, cc.b);
    }
  };
  wall(grid.slice(0, w)); wall(grid.slice((h - 1) * w).reverse());
  wall(Array.from({ length: h }, (_, j) => grid[j * w]).reverse()); wall(Array.from({ length: h }, (_, j) => grid[j * w + w - 1]));
  const sg = new BufferGeometry();
  sg.setAttribute('position', new BufferAttribute(new Float32Array(side), 3));
  sg.setAttribute('color', new BufferAttribute(new Float32Array(sc), 3));
  sg.computeVertexNormals();
  const walls = new Mesh(sg, new MeshLambertMaterial({ vertexColors: true, side: 2 }));
  return { mesh, walls };
}

function lakes(p) {
  const grp = new Group();
  const mat = new MeshPhongMaterial({ color: p.water, shininess: 70, specular: new Color('#CFE2FF') });
  for (const [k, rings] of Object.entries(G.lakes)) {
    for (const ring of rings) {
      const sh = new Shape(ring.map(([lon, lat]) => ({ x: X(lon), y: -Z(lat) })));
      const g = new ShapeGeometry(sh); g.rotateX(-Math.PI / 2);
      let lvl = k === 'tahoe' ? LAKE_H : Math.min(...ring.map(([lon, lat]) => hAt(lon, lat)));
      const m = new Mesh(g, mat); m.position.y = YH(lvl) + .03; grp.add(m);
    }
  }
  return grp;
}

// a draped ribbon along a lon/lat line; returns a mesh whose drawRange can grow (the route draws itself)
function ribbon(pts, width, lift, color, onTop = 0) {
  const dense = [];
  for (let k = 0; k < pts.length - 1; k++) {
    const [a, b] = [pts[k], pts[k + 1]];
    const n = Math.max(1, Math.ceil(Math.hypot(X(b[0]) - X(a[0]), Z(b[1]) - Z(a[1])) / .25));
    for (let s = 0; s < n; s++) dense.push([a[0] + (b[0] - a[0]) * s / n, a[1] + (b[1] - a[1]) * s / n]);
  }
  dense.push(pts[pts.length - 1]);
  const P = dense.map(([lon, lat]) => new Vector3(X(lon), Math.max(yAt(lon, lat), inPoly(lon, lat, TAHOE) ? YH(LAKE_H) : -9) + lift, Z(lat)));
  const pos = [], idx = [];
  for (let k = 0; k < P.length; k++) {
    const a = P[Math.max(0, k - 1)], b = P[Math.min(P.length - 1, k + 1)];
    let dx = b.x - a.x, dz = b.z - a.z; const l = Math.hypot(dx, dz) || 1; dx /= l; dz /= l;
    pos.push(P[k].x - dz * width / 2, P[k].y, P[k].z + dx * width / 2, P[k].x + dz * width / 2, P[k].y, P[k].z - dx * width / 2);
    if (k) { const o = (k - 1) * 2; idx.push(o, o + 1, o + 2, o + 1, o + 3, o + 2); }
  }
  const g = new BufferGeometry();
  g.setAttribute('position', new BufferAttribute(new Float32Array(pos), 3));
  g.setIndex(idx);
  const m = new Mesh(g, new MeshBasicMaterial({ color, side: 2, depthTest: !onTop }));
  if (onTop) m.renderOrder = onTop;
  m.userData = { P, n: idx.length };
  return m;
}

function trees(p) {
  const r = rng(9), N = 7600, cone = new ConeGeometry(.24, .72, 6), cap = new ConeGeometry(.12, .26, 6);
  cone.translate(0, .36, 0); cap.translate(0, .68, 0);
  const tm = new InstancedMesh(cone, new MeshLambertMaterial({ color: p.tree, flatShading: true }), N);
  const cm = new InstancedMesh(cap, new MeshLambertMaterial({ color: p.cap, flatShading: true }), N);
  const o = new Object3D(); let n = 0, tries = 0;
  while (n < N && tries++ < N * 12) {
    const lon = W0 + r() * (E0 - W0), lat = S0 + r() * (N0 - S0), h = hAt(lon, lat);
    if (h < 1900 || h > 2600 || inLake(lon, lat)) continue;
    if (fbm(X(lon) + 40, Z(lat) - 40) < .44 - (h < 2350 ? .06 : -.06)) continue;
    const sl = Math.abs(hAt(lon + .004, lat) - hAt(lon - .004, lat)) + Math.abs(hAt(lon, lat + .004) - hAt(lon, lat - .004));
    if (sl > 170) continue;
    const s = .7 + r() * .7;
    o.position.set(X(lon), YH(h) - .04, Z(lat)); o.scale.set(s, s * (.9 + r() * .4), s); o.rotation.y = r() * 6; o.updateMatrix();
    tm.setMatrixAt(n, o.matrix); cm.setMatrixAt(n, o.matrix); n++;
  }
  tm.count = cm.count = n;
  return [tm, cm];
}

function townLights() {
  const r = rng(3), pos = [];
  const spots = [['Reno', 160, .05], ['Carson City', 90, .035], ['Minden', 45, .03], ['South Lake Tahoe', 110, .03], ['Stateline', 40, .012], ['Tahoe City', 35, .012], ['Incline Village', 40, .015], ['Truckee', 50, .02], ['Kings Beach', 25, .01]];
  for (const [nm, n, sp] of spots) {
    const t = G.towns.find((x) => x.name === nm); if (!t) continue;
    for (let k = 0; k < n; k++) { const lon = t.lon + (r() - .5) * sp * 2.4, lat = t.lat + (r() - .5) * sp * 1.6; if (inLake(lon, lat)) continue; pos.push(X(lon), yAt(lon, lat) + .08, Z(lat)); }
  }
  const g = new BufferGeometry(); g.setAttribute('position', new BufferAttribute(new Float32Array(pos), 3));
  return new Points(g, new PointsMaterial({ color: '#FFC56B', size: .2, sizeAttenuation: true }));
}

function cloudPuffs(r) {
  const g = new Group();
  const mat = new MeshLambertMaterial({ color: '#FFFFFF', flatShading: true });
  for (let k = 0; k < 9; k++) {
    const c = new Group();
    const n = 3 + (r() * 3 | 0);
    for (let i = 0; i < n; i++) { const m = new Mesh(new IcosahedronGeometry(.9 + r() * .9, 0), mat); m.position.set(i * 1.1 - n * .5, r() * .5, (r() - .5) * .9); c.add(m); }
    c.position.set((r() - .5) * KW * 1.1, 8 + r() * 3, (r() - .5) * KH * .9); c.userData.v = .3 + r() * .5;
    g.add(c);
  }
  return g;
}

function suv() {
  const g = new Group();
  const body = new Mesh(new BoxGeometry(1.0, .34, .5), new MeshLambertMaterial({ color: '#15803D' }));
  const top = new Mesh(new BoxGeometry(.62, .26, .44), new MeshLambertMaterial({ color: '#E8F5EC' }));
  const rack = new Mesh(new BoxGeometry(.5, .06, .36), new MeshLambertMaterial({ color: '#17140A' }));
  body.position.y = .3; top.position.set(-.06, .58, 0); rack.position.set(-.06, .74, 0);
  g.add(body, top, rack);
  for (const [x, z] of [[.32, .26], [-.32, .26], [.32, -.26], [-.32, -.26]]) { const w = new Mesh(new CylinderGeometry(.13, .13, .08, 10), new MeshLambertMaterial({ color: '#17140A' })); w.rotation.x = Math.PI / 2; w.position.set(x, .13, z); g.add(w); }
  g.scale.setScalar(1.7);
  return g;
}

function shadowDisc() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d'); const gr = x.createRadialGradient(64, 64, 10, 64, 64, 64);
  gr.addColorStop(0, 'rgba(0,0,0,.32)'); gr.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = gr; x.fillRect(0, 0, 128, 128);
  const m = new Mesh(new PlaneGeometry(KW * 1.5, KH * 1.35), new MeshBasicMaterial({ map: new CanvasTexture(c), transparent: true, depthWrite: false }));
  m.rotation.x = -Math.PI / 2; m.position.y = -1.15; return m;
}

export function mount(el, opts = {}) {
  const mode = opts.mode || 'light', p = PAL[mode], calm = !!opts.calm;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const renderer = new WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.outputColorSpace = SRGBColorSpace;
  el.appendChild(renderer.domElement);
  renderer.domElement.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block;touch-action:none;';
  const lines = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); lines.setAttribute('class', 'dlines'); lines.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible'; el.appendChild(lines);
  const layer = document.createElement('div'); layer.className = 'mlayer'; el.appendChild(layer);
  const scene = new Scene();
  scene.fog = new Fog(opts.fogColor || (mode === 'dark' ? '#0F0F11' : '#E7E7EC'), 60, 240);
  const cam = new PerspectiveCamera(opts.fov || 30, 1, .5, 900);
  scene.add(new HemisphereLight(p.hemiSky, p.hemiGround, p.hemi));
  const sun = new DirectionalLight(p.sun, p.sunI); sun.position.set(-40, 38, 30); scene.add(sun);
  const T = terrain(p); scene.add(T.mesh, T.walls, shadowDisc(), lakes(p));
  const roads = new Group(); for (const r of G.roads) roads.add(ribbon(r.pts, .16, .16, p.road)); scene.add(roads);
  scene.add(...trees(p));
  if (mode === 'dark') scene.add(townLights());
  const r = rng(21);
  const clouds = cloudPuffs(r); scene.add(clouds);
  // snow: one pool, drawn as much as the day asks for
  const SN = 6000, sp = new Float32Array(SN * 3), sv = new Float32Array(SN);
  for (let i = 0; i < SN; i++) { sp[i * 3] = (r() - .5) * 80; sp[i * 3 + 1] = r() * 16; sp[i * 3 + 2] = (r() - .5) * 80; sv[i] = .5 + r(); }
  const sg = new BufferGeometry(); const sattr = new BufferAttribute(sp, 3); sg.setAttribute('position', sattr);
  const snow = new Points(sg, new PointsMaterial({ color: '#FFFFFF', size: .16, sizeAttenuation: true, transparent: true, opacity: .95, depthWrite: false }));
  snow.frustumCulled = false; scene.add(snow);
  // pins
  const pins = {};
  const KIND = { flight: '#4338CA', stay: '#8B2FC9', car: '#15803D', tix: '#C2410C', food: '#C92A5E', see: '#0F766E' };
  for (const [key, pl] of Object.entries(G.places)) {
    if (key === 'spooner') continue;
    const kind = (opts.kinds || {})[key] || 'see';
    const grp = new Group();
    const stick = new Mesh(new CylinderGeometry(.05, .05, 1.5, 6), new MeshLambertMaterial({ color: mode === 'dark' ? '#D4D4DA' : '#FFFFFF' })); stick.position.y = .75;
    const head = new Mesh(new SphereGeometry(.34, 16, 12), new MeshLambertMaterial({ color: KIND[kind], emissive: KIND[kind], emissiveIntensity: mode === 'dark' ? .55 : .18 })); head.position.y = 1.6;
    grp.add(stick, head);
    grp.position.set(X(pl.lon), Math.max(yAt(pl.lon, pl.lat), YH(LAKE_H)), Z(pl.lat));
    scene.add(grp);
    pins[key] = { grp, head, top: new Vector3() };
  }
  const car = suv(); scene.add(car); car.visible = false;
  // route of the day
  let route = null, routeCase = null, carT = 1, carPath = null;
  function setRoute(pts) {
    if (route) { scene.remove(route, routeCase); route.geometry.dispose(); routeCase.geometry.dispose(); }
    route = routeCase = null; carPath = null; car.visible = false;
    if (!pts) return;
    routeCase = ribbon(pts, .62, .3, p.routeCase, 5); route = ribbon(pts, .34, .32, p.route, 6);
    scene.add(routeCase, route);
    carPath = route.userData.P; carT = reduced ? 1 : 0; car.visible = true;
    drawT = reduced ? 1 : 0;
  }
  let drawT = 1;
  // camera
  const view = { tx: 0, ty: 0, tz: 0, dist: 120, az: -.5, el: .9 };
  let from = null, to = null, t0 = 0, dur = 1;
  const user = { az: 0, el: 0, zoom: 1 };
  function frameFor(pts, o = {}) {
    let minx = 1e9, maxx = -1e9, minz = 1e9, maxz = -1e9;
    for (const [lon, lat] of pts) { const x = X(lon), z = Z(lat); minx = Math.min(minx, x); maxx = Math.max(maxx, x); minz = Math.min(minz, z); maxz = Math.max(maxz, z); }
    const cx = (minx + maxx) / 2, cz = (minz + maxz) / 2;
    const rad = Math.max(3.5, Math.hypot(maxx - minx, maxz - minz) / 2);
    const asp = Math.max(.6, (el.clientWidth || 1) / (el.clientHeight || 1));
    const dist = rad / Math.tan(cam.fov * Math.PI / 360) * (asp < 1 ? 1.5 / asp : 1.25) * (o.pad || 1);
    return { tx: cx + (o.ox || 0), ty: YH(2000), tz: cz + (o.oz || 0), dist, az: o.az ?? (opts.az ?? -.55), el: o.el ?? (opts.el ?? .86) };
  }
  function fly(target, instant) {
    if (instant || reduced) { Object.assign(view, target); from = to = null; return; }
    from = { ...view }; to = target; t0 = performance.now(); dur = calm ? 850 : 1250;
  }
  const ease = calm ? (t) => (t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2) : (t) => 1 - Math.pow(1 - t, 4);
  // weather
  const wx = { snow: 0, wind: 0, cloud: .3, tSnow: 0, tWind: 0, tCloud: .3 };
  function setWeather(w) {
    const m = { sun: [0, .1, .15], cloud: [.03, .25, .8], snow: [w.snow && /6|9/.test(w.snow) ? 1 : .6, .45, 1], flurry: [.3, .25, .6], wind: [0, 1, .35] }[w.type] || [0, 0, .2];
    [wx.tSnow, wx.tWind, wx.tCloud] = m;
    if (reduced) { wx.snow = wx.tSnow; wx.wind = wx.tWind; wx.cloud = wx.tCloud; }
  }
  // interaction: drag to turn and tilt, wheel or pinch to zoom
  let drag = null;
  renderer.domElement.addEventListener('pointerdown', (e) => { drag = { x: e.clientX, y: e.clientY, az: user.az, el: user.el }; renderer.domElement.setPointerCapture(e.pointerId); });
  renderer.domElement.addEventListener('pointermove', (e) => { if (!drag) return; user.az = Math.max(-.9, Math.min(.9, drag.az + (e.clientX - drag.x) * .006)); user.el = Math.max(-.35, Math.min(.35, drag.el + (e.clientY - drag.y) * .004)); kick(); });
  addEventListener('pointerup', () => { drag = null; });
  renderer.domElement.addEventListener('wheel', (e) => { e.preventDefault(); user.zoom = Math.max(.5, Math.min(1.8, user.zoom * (e.deltaY > 0 ? 1.08 : .93))); kick(); }, { passive: false });
  // labels
  function setLabels(list) {
    layer.innerHTML = list.map((l) => `<div class="dl" data-k="${l.key || ''}" style="position:absolute;left:0;top:0">${l.html}</div>`).join('');
    list.forEach((l, i) => { layer.children[i]._l = l; });
  }
  const v3 = new Vector3();
  function placeLabels() {
    const w = el.clientWidth, h = el.clientHeight;
    let segs = '';
    for (const d of layer.children) {
      const l = d._l; if (!l) continue;
      if (l.key && pins[l.key]) { pins[l.key].head.getWorldPosition(v3); v3.y += l.fixed ? 0 : .4; }
      else if (l.at) v3.set(X(l.at[0]), Math.max(yAt(l.at[0], l.at[1]), YH(LAKE_H)) + (l.lift ?? .6), Z(l.at[1]));
      v3.project(cam);
      const x = (v3.x * .5 + .5) * w, y = (-v3.y * .5 + .5) * h;
      if (l.fixed) {
        // a callout: the label sits at a fixed spot on the stage and a leader line runs to its pin
        const fx = l.fixed.x < 0 ? w + l.fixed.x : l.fixed.x, fy = l.fixed.y;
        d.style.transform = `translate3d(${fx}px, ${fy}px, 0)`; d.style.visibility = 'visible';
        const r = d.firstElementChild.getBoundingClientRect(), b = el.getBoundingClientRect();
        const ex = l.fixed.x < 0 ? r.left - b.left : r.right - b.left, ey = r.top - b.top + r.height / 2;
        segs += `<path d="M${ex.toFixed(1)},${ey.toFixed(1)} C${((ex + x) / 2).toFixed(1)},${ey.toFixed(1)} ${((ex + x) / 2).toFixed(1)},${y.toFixed(1)} ${x.toFixed(1)},${y.toFixed(1)}" fill="none" stroke="var(--ink)" stroke-width="1.5" stroke-dasharray="3 4" opacity=".55"/><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4" fill="var(--ink)"/>`;
        continue;
      }
      d.style.transform = `translate3d(${(x + (l.dx || 0)).toFixed(1)}px, ${(y + (l.dy || 0)).toFixed(1)}px, 0)`;
      d.style.visibility = v3.z < 1 && x > -40 && x < w + 40 && y > -20 && y < h + 60 ? 'visible' : 'hidden';
    }
    if (lines.innerHTML !== segs) lines.innerHTML = segs;
  }
  function resize() {
    const w = el.clientWidth, h = el.clientHeight; if (!w || !h) return;
    renderer.setSize(w, h, false); cam.aspect = w / h; cam.updateProjectionMatrix();
  }
  new ResizeObserver(() => { resize(); kick(); }).observe(el);
  resize();
  // loop
  let raf = 0, last = performance.now(), visible = true;
  const io = new IntersectionObserver((e) => { visible = e[0].isIntersecting; if (visible) kick(); }); io.observe(el);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) kick(); });
  function kick() { if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); } }
  let clock = 0;
  function frame(now) {
    raf = 0;
    const dt = Math.min(.05, (now - last) / 1000); last = now; clock += dt;
    if (to) { const t = Math.min(1, (now - t0) / dur), e = ease(t); for (const k in to) view[k] = from[k] + (to[k] - from[k]) * e; if (t >= 1) { from = to = null; } }
    const k = 1 - Math.exp(-dt * 2.2);
    wx.snow += (wx.tSnow - wx.snow) * k; wx.wind += (wx.tWind - wx.wind) * k; wx.cloud += (wx.tCloud - wx.cloud) * k;
    const az = view.az + user.az, elv = Math.max(.32, Math.min(1.35, view.el + user.el)), dist = view.dist * user.zoom;
    cam.position.set(view.tx + Math.sin(az) * Math.cos(elv) * dist, view.ty + Math.sin(elv) * dist, view.tz + Math.cos(az) * Math.cos(elv) * dist);
    cam.lookAt(view.tx, view.ty, view.tz);
    scene.fog.near = dist * .7; scene.fog.far = dist * 2.4;
    // snow volume follows the view target
    const n = Math.round(SN * Math.min(1, wx.snow + (wx.wind > .7 ? .08 : 0)));
    sg.setDrawRange(0, n);
    const span = Math.max(30, dist * .9);
    for (let i = 0; i < n; i++) {
      let x = sp[i * 3], y = sp[i * 3 + 1], z = sp[i * 3 + 2];
      y -= dt * (1.6 + sv[i]) ; x += dt * (wx.wind * 7 + Math.sin(clock * .8 + i) * .3);
      if (y < 0) { y += 16; }
      if (x > 40) x -= 80;
      sp[i * 3] = x; sp[i * 3 + 1] = y; sp[i * 3 + 2] = z;
    }
    sattr.needsUpdate = true;
    snow.position.set(view.tx, YH(2000) - 2, view.tz); snow.scale.set(span / 80, Math.max(1, dist / 60), span / 80);
    snow.material.size = Math.max(.12, dist / 420);
    // clouds
    clouds.children.forEach((c, i) => { c.position.x += dt * (c.userData.v + wx.wind * 2.2); if (c.position.x > KW * .7) c.position.x = -KW * .7; c.visible = i < Math.round(2 + wx.cloud * 7); });
    sun.intensity = p.sunI * (1 - wx.cloud * .45);
    // route draws itself, then the SUV drives it
    if (route) {
      drawT = Math.min(1, drawT + dt / (calm ? .8 : 1.2));
      route.geometry.setDrawRange(0, Math.floor(route.userData.n * drawT / 6) * 6);
      routeCase.geometry.setDrawRange(0, Math.floor(routeCase.userData.n * drawT / 6) * 6);
      if (carPath && drawT >= 1) carT = Math.min(1, carT + dt / 3.2);
      const P = carPath, f = carT * (P.length - 1), i = Math.min(P.length - 2, f | 0), a = P[i], b = P[i + 1];
      car.position.lerpVectors(a, b, f - i); car.position.y += .02;
      car.rotation.y = Math.atan2(-(b.z - a.z), b.x - a.x);
    }
    renderer.render(scene, cam);
    placeLabels();
    if (!reduced && visible && !document.hidden) raf = requestAnimationFrame(frame);
  }
  const api = {
    setDay({ pts, frame: fpts, weather, labels: list, az, el: e, pad, instant }) {
      setRoute(pts);
      if (weather) setWeather(weather);
      if (list) setLabels(list);
      fly(frameFor(fpts || pts, { az, el: e, pad }), instant);
      kick();
    },
    overview(o = {}) { fly(frameFor([[W0 + .06, S0 + .04], [E0 - .06, N0 - .04]], o), o.instant); kick(); },
    setLabels(list) { setLabels(list); kick(); },
    screenPos(key) { pins[key].head.getWorldPosition(v3); v3.project(cam); return { x: (v3.x * .5 + .5) * el.clientWidth, y: (-v3.y * .5 + .5) * el.clientHeight }; },
    pulse(key) { const h = pins[key]?.head; if (!h) return; const t0 = performance.now(); const step = (now) => { const t = (now - t0) / 700; h.scale.setScalar(1 + Math.sin(Math.min(1, t) * Math.PI) * .6); kick(); if (t < 1) requestAnimationFrame(step); else h.scale.setScalar(1); }; requestAnimationFrame(step); },
    resetUser() { user.az = user.el = 0; user.zoom = 1; kick(); },
    renderer,
  };
  if (opts.onReady) requestAnimationFrame(() => { frame(performance.now()); opts.onReady(api); });
  return api;
}
window.Diorama = { mount };
