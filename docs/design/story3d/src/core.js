// Shared 3D plumbing for the three story prototypes: the render loop (paused offscreen and when the tab is
// hidden, adapted from ThreeUI's Gallery lifecycle, MIT, see CREDITS.md), a frame-time guard that drops the
// pixel ratio and then falls back to the still, springs, a vertex-colour merge (all static scenery is one
// draw call), and the low-poly props the scenes share.
import {
  WebGLRenderer, Scene, PerspectiveCamera, HemisphereLight, DirectionalLight, Color, Group, Mesh, Matrix4, Vector3, Quaternion, Euler,
  BufferGeometry, Float32BufferAttribute, MeshLambertMaterial, MeshBasicMaterial,
  BoxGeometry, CylinderGeometry, ConeGeometry, SphereGeometry, IcosahedronGeometry, TorusGeometry, CircleGeometry, DodecahedronGeometry,
} from 'three';

export const KIND = { flight: 0x4338CA, stay: 0x8B2FC9, car: 0x15803D, tix: 0xC2410C, food: 0xC92A5E, see: 0x0F766E, ride: 0xFFD43B, weather: 0x0369A1 };

/* ---------- stage ---------- */
export function createStage(host, api, { fov = 34, near = 0.1, far = 200 } = {}) {
  const canvas = document.createElement('canvas');
  host.prepend(canvas);
  const renderer = new WebGLRenderer({ canvas, antialias: (devicePixelRatio || 1) < 2, alpha: true, powerPreference: 'high-performance', preserveDrawingBuffer: !!api.capture });
  renderer.setClearColor(0x000000, 0);
  const scene = new Scene();
  const camera = new PerspectiveCamera(fov, 1, near, far);
  const hemi = new HemisphereLight(0xffffff, 0xb9a98f, 1.6);
  const sun = new DirectionalLight(0xfff1dc, 2.2); sun.position.set(-6, 12, 8);
  scene.add(hemi, sun);

  let dpr = Math.min(devicePixelRatio || 1, 2), w = 1, h = 1;
  const frames = [], work = []; window.__frames = frames; window.__work = work; // frame deltas and main-thread ms per frame, for the measurement
  let raf = 0, prev = 0, visible = true, docVisible = !document.hidden, dead = false;
  const onFrame = [];
  const guard = { n: 0, deltas: [], stage: 0 };

  function resize() {
    const r = host.getBoundingClientRect(); w = Math.max(1, Math.round(r.width)); h = Math.max(1, Math.round(r.height));
    renderer.setPixelRatio(dpr); renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    stage.aspect = w / h; stage.resized?.();
    renderer.render(scene, camera);
  }
  function tick(t) {
    raf = 0;
    if (dead || !visible || !docVisible) { prev = 0; return; }
    const dt = prev ? Math.min((t - prev) / 1000, 0.05) : 1 / 60;
    if (prev) { const d = t - prev; frames.push(d); if (frames.length > 600) frames.shift(); watch(d); }
    prev = t; stage.time += dt;
    const w0 = performance.now();
    for (const f of onFrame) f(dt, stage.time);
    renderer.render(scene, camera);
    work.push(performance.now() - w0); if (work.length > 600) work.shift();
    raf = requestAnimationFrame(tick);
  }
  // Weak-device guard: after 90 frames, a median over 30 ms drops the pixel ratio to 1; if it stays over 40 ms, show the still.
  function watch(d) {
    if (guard.stage > 1 || api.capture || api.measure) return;
    guard.deltas.push(d);
    if (guard.deltas.length < 90) return;
    const m = guard.deltas.sort((a, b) => a - b)[45]; guard.deltas = [];
    if (guard.stage === 0 && m > 30 && dpr > 1) { dpr = 1; resize(); guard.stage = 1; }
    else if (m > 40) { guard.stage = 2; api.onWeak(); }
    else guard.stage = guard.stage === 0 ? 1 : 2;
  }
  const start = () => { if (!raf && visible && docVisible && !dead) raf = requestAnimationFrame(tick); };
  const stop = () => { if (raf) cancelAnimationFrame(raf); raf = 0; prev = 0; };
  const ro = new ResizeObserver(resize);
  const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; visible ? start() : stop(); });
  const vis = () => { docVisible = !document.hidden; docVisible ? start() : stop(); };
  ro.observe(host); io.observe(host); document.addEventListener('visibilitychange', vis);

  const stage = {
    renderer, scene, camera, canvas, hemi, sun, aspect: 1, time: 0, onFrame, start, stop,
    show() { resize(); requestAnimationFrame(() => canvas.classList.add('on')); start(); },
    dispose() { dead = true; stop(); ro.disconnect(); io.disconnect(); document.removeEventListener('visibilitychange', vis); renderer.dispose(); },
  };
  return stage;
}

/* ---------- motion ---------- */
// A critically damped follow (no overshoot): camera, ring and glide. omega ~ how fast it settles.
export function damp(cur, target, omega, dt) { return target + (cur - target) * Math.exp(-omega * dt); }
// An underdamped spring for small things that pop (pins, props, the burst): k stiffness, c damping.
export class Spring {
  constructor(v = 0, k = 170, c = 12) { this.v = v; this.t = v; this.vel = 0; this.k = k; this.c = c; }
  step(dt) { const n = Math.ceil(dt / (1 / 120)), h = dt / n; for (let i = 0; i < n; i++) { const a = -this.k * (this.v - this.t) - this.c * this.vel; this.vel += a * h; this.v += this.vel * h; } return this.v; }
  kick(v) { this.vel += v; return this; }
}
export const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

/* ---------- one draw call for static scenery: merge geometries with vertex colours ---------- */
export class Kit {
  constructor() { this.pos = []; this.nor = []; this.col = []; }
  add(geo, color, matrix) {
    const g = geo.index ? geo.toNonIndexed() : geo; if (matrix) g.applyMatrix4(matrix);
    g.computeVertexNormals();
    const p = g.attributes.position.array, n = g.attributes.normal.array, c = new Color(color);
    for (let i = 0; i < p.length; i++) { this.pos.push(p[i]); this.nor.push(n[i]); }
    for (let i = 0; i < p.length / 3; i++) this.col.push(c.r, c.g, c.b);
    return this;
  }
  // add with per-face colours from a function (terrain, globe)
  addFaces(geo, faceColor) {
    const g = geo.index ? geo.toNonIndexed() : geo; g.computeVertexNormals();
    const p = g.attributes.position.array, n = g.attributes.normal.array, c = new Color();
    for (let i = 0; i < p.length; i += 9) {
      faceColor(c, (p[i] + p[i + 3] + p[i + 6]) / 3, (p[i + 1] + p[i + 4] + p[i + 7]) / 3, (p[i + 2] + p[i + 5] + p[i + 8]) / 3);
      for (let k = 0; k < 9; k++) { this.pos.push(p[i + k]); this.nor.push(n[i + k]); }
      for (let k = 0; k < 3; k++) this.col.push(c.r, c.g, c.b);
    }
    return this;
  }
  mesh(mat) {
    const g = new BufferGeometry();
    g.setAttribute('position', new Float32BufferAttribute(this.pos, 3));
    g.setAttribute('normal', new Float32BufferAttribute(this.nor, 3));
    g.setAttribute('color', new Float32BufferAttribute(this.col, 3));
    return new Mesh(g, mat || new MeshLambertMaterial({ vertexColors: true, flatShading: true }));
  }
}
const _m = new Matrix4(), _q = new Quaternion(), _e = new Euler(), _s = new Vector3(), _p = new Vector3();
export function M(x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, sx = 1, sy = sx, sz = sx) {
  return new Matrix4().compose(_p.set(x, y, z), _q.setFromEuler(_e.set(rx, ry, rz)), _s.set(sx, sy, sz));
}
export const lambert = (color, opts = {}) => new MeshLambertMaterial({ color, flatShading: true, ...opts });
export const basic = (color, opts = {}) => new MeshBasicMaterial({ color, ...opts });

/* ---------- props (low-poly, toy-like) ---------- */
// each prop adds itself to a Kit at a matrix, so a scene can place dozens for one draw call
export const props = {
  palm(kit, x, y, z, s = 1, r = 0) {
    const lean = 0.12 * Math.sin(r * 7);
    kit.add(new CylinderGeometry(0.035, 0.055, 0.9, 5), 0xB58554, M(x, y + 0.45 * s, z, 0, r, lean, s));
    const top = new Vector3(x - 0.45 * s * Math.sin(lean), y + 0.9 * s, z);
    for (let k = 0; k < 5; k++) {
      const a = r + (k / 5) * Math.PI * 2;
      kit.add(new ConeGeometry(0.09, 0.55, 4), k % 2 ? 0x2F9E44 : 0x3DB356, M(top.x + Math.cos(a) * 0.2 * s, top.y - 0.04 * s, top.z + Math.sin(a) * 0.2 * s, Math.sin(a) * 1.9, 0, -Math.cos(a) * 1.9, s, s, s * 0.35));
    }
    kit.add(new SphereGeometry(0.07, 5, 4), 0x7A5230, M(top.x, top.y, top.z, 0, 0, 0, s));
  },
  tree(kit, x, y, z, s = 1, c = 0x4CAF50) {
    kit.add(new CylinderGeometry(0.04, 0.05, 0.25, 5), 0x8A6440, M(x, y + 0.12 * s, z, 0, 0, 0, s));
    kit.add(new IcosahedronGeometry(0.22, 0), c, M(x, y + 0.38 * s, z, x, z, 0, s));
  },
  house(kit, x, y, z, s = 1, wall = 0xFFFFFF, roof = 0xF08A5D, r = 0) {
    kit.add(new BoxGeometry(0.34, 0.26, 0.3), wall, M(x, y + 0.13 * s, z, 0, r, 0, s));
    kit.add(new ConeGeometry(0.29, 0.18, 4), roof, M(x, y + 0.35 * s, z, 0, r + Math.PI / 4, 0, s, s, s));
  },
  tower(kit, x, y, z, h = 1, c = 0xDDE3EA) { kit.add(new BoxGeometry(0.3, h, 0.3), c, M(x, y + h / 2, z)); kit.add(new BoxGeometry(0.32, 0.04, 0.32), 0xB9C2CC, M(x, y + h, z)); },
  rock(kit, x, y, z, s = 1, c = 0x9C8F84) { kit.add(new DodecahedronGeometry(0.2, 0), c, M(x, y + 0.08 * s, z, x * 3, z * 2, 0, s, s * 0.7, s)); },
  observatory(kit, x, y, z, s = 1) {
    kit.add(new BoxGeometry(0.9, 0.22, 0.32), 0xF4F1EA, M(x, y + 0.11 * s, z, 0, 0, 0, s));
    kit.add(new CylinderGeometry(0.17, 0.17, 0.2, 10), 0xF4F1EA, M(x, y + 0.3 * s, z, 0, 0, 0, s));
    kit.add(new SphereGeometry(0.19, 12, 6, 0, Math.PI * 2, 0, Math.PI / 2), 0x6B7C93, M(x, y + 0.4 * s, z, 0, 0, 0, s));
    for (const dx of [-0.38, 0.38]) kit.add(new SphereGeometry(0.11, 10, 5, 0, Math.PI * 2, 0, Math.PI / 2), 0x6B7C93, M(x + dx * s, y + 0.22 * s, z, 0, 0, 0, s));
  },
  getty(kit, x, y, z, s = 1) {
    kit.add(new BoxGeometry(0.7, 0.24, 0.45), 0xF7F4EC, M(x, y + 0.12 * s, z, 0, 0.3, 0, s));
    kit.add(new BoxGeometry(0.4, 0.34, 0.35), 0xFFFFFF, M(x + 0.35 * s, y + 0.17 * s, z - 0.2 * s, 0, 0.3, 0, s));
    kit.add(new CylinderGeometry(0.2, 0.2, 0.3, 14), 0xEFEBE2, M(x - 0.3 * s, y + 0.15 * s, z + 0.15 * s, 0, 0, 0, s));
    kit.add(new BoxGeometry(0.5, 0.02, 0.3), 0x7FC97F, M(x - 0.05 * s, y + 0.01, z + 0.4 * s, 0, 0.3, 0, s));
  },
  pier(kit, x, y, z, len = 1.6, r = 0) {
    kit.add(new BoxGeometry(0.34, 0.06, len), 0xC9A27A, M(x, y, z, 0, r, 0));
    for (let k = 0; k < 6; k++) { const t = -len / 2 + (k + 0.5) * (len / 6); kit.add(new CylinderGeometry(0.025, 0.025, 0.3, 4), 0x8C6A4A, M(x + Math.sin(r) * t, y - 0.15, z + Math.cos(r) * t)); }
  },
  starfish(kit, x, y, z, s = 1, c = 0xFF8A3D) { for (let k = 0; k < 5; k++) kit.add(new ConeGeometry(0.03, 0.12, 3), c, M(x + Math.cos(k * 1.257) * 0.05 * s, y, z + Math.sin(k * 1.257) * 0.05 * s, Math.PI / 2, 0, -k * 1.257 - Math.PI / 2, s)); },
  cloud(kit, x, y, z, s = 1) { for (const [dx, dy, r] of [[0, 0, 0.32], [0.3, -0.05, 0.24], [-0.3, -0.06, 0.22], [0.12, 0.14, 0.22]]) kit.add(new IcosahedronGeometry(r, 1), 0xFFFFFF, M(x + dx * s, y + dy * s, z, 0, 0, 0, s)); },
};

// A Ferris wheel that turns (its own group; not merged)
export function ferrisWheel(s = 1) {
  const g = new Group(), wheel = new Group();
  const k = new Kit();
  k.add(new TorusGeometry(0.5, 0.025, 4, 24), 0xF2F2F2);
  for (let i = 0; i < 8; i++) k.add(new BoxGeometry(0.02, 1, 0.02), 0xE8E8E8, M(0, 0, 0, 0, 0, (i / 8) * Math.PI));
  const cols = [0xFF5D5D, 0xFFC93C, 0x4FC3F7, 0x9B6DFF, 0x5BD18B, 0xFF8A3D, 0xFF6FB1, 0x4DD0C8];
  for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2; k.add(new BoxGeometry(0.1, 0.09, 0.09), cols[i], M(Math.cos(a) * 0.5, Math.sin(a) * 0.5 - 0.05, 0)); }
  wheel.add(k.mesh()); wheel.position.y = 0.62;
  const legs = new Kit();
  legs.add(new BoxGeometry(0.03, 0.66, 0.03), 0xDADADA, M(-0.17, 0.31, 0.06, 0, 0, -0.26)).add(new BoxGeometry(0.03, 0.66, 0.03), 0xDADADA, M(0.17, 0.31, 0.06, 0, 0, 0.26));
  legs.add(new BoxGeometry(0.03, 0.66, 0.03), 0xDADADA, M(-0.17, 0.31, -0.06, 0, 0, -0.26)).add(new BoxGeometry(0.03, 0.66, 0.03), 0xDADADA, M(0.17, 0.31, -0.06, 0, 0, 0.26));
  g.add(legs.mesh(), wheel); g.scale.setScalar(s); g.userData.wheel = wheel;
  return g;
}

// A map pin in a kind colour: a ball on a cone, with a white dot
export function pin(color, s = 1) {
  const g = new Group(), k = new Kit();
  k.add(new ConeGeometry(0.075, 0.26, 8), color, M(0, 0.13, 0, Math.PI));
  k.add(new SphereGeometry(0.13, 12, 8), color, M(0, 0.34, 0));
  k.add(new SphereGeometry(0.05, 8, 6), 0xFFFFFF, M(0, 0.36, 0.1));
  g.add(k.mesh(new MeshLambertMaterial({ vertexColors: true }))); g.scale.setScalar(s);
  return g;
}

// The family: four round-headed toy people (two grown-ups, two kids). Each figure hops on its own spring.
export function family(s = 1) {
  const g = new Group(); const who = [[-0.21, 1, 0x2B59C3, 0xE8B48A], [0.21, 1, 0xE0457B, 0x8D5A3B], [-0.07, 0.68, 0xFFB020, 0xC68B5E], [0.07, 0.62, 0x22A06B, 0xE8B48A]];
  g.userData.people = who.map(([x, h, shirt, skin], i) => {
    const p = new Group(), k = new Kit();
    k.add(new CylinderGeometry(0.06 * h, 0.08 * h, 0.22 * h, 8), shirt, M(0, 0.11 * h, 0));
    k.add(new SphereGeometry(0.075 * h + 0.012, 10, 8), skin, M(0, 0.3 * h, 0));
    k.add(new SphereGeometry(0.08 * h + 0.012, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2.2), 0x2A1E17, M(0, 0.315 * h, -0.006));
    p.add(k.mesh(new MeshLambertMaterial({ vertexColors: true }))); p.position.x = x * (i < 2 ? 1 : 1.1); p.position.z = i < 2 ? 0 : 0.12;
    p.userData.hop = new Spring(0, 260, 9); g.add(p); return p;
  });
  g.scale.setScalar(s);
  g.userData.cheer = (delay = 0) => g.userData.people.forEach((p, i) => setTimeout(() => p.userData.hop.kick(3.4 + (i > 1 ? 0.8 : 0)), delay + i * 70));
  g.userData.step = (dt) => g.userData.people.forEach((p) => { p.position.y = Math.max(0, p.userData.hop.step(dt)); });
  return g;
}

// A soft blob shadow (one shared material per scene)
export function blobs(list, mat) {
  const k = new Kit();
  for (const [x, y, z, r] of list) k.add(new CircleGeometry(r, 12), 0x000000, M(x, y, z, -Math.PI / 2));
  const m = k.mesh(mat || new MeshBasicMaterial({ color: 0x1a1a2e, transparent: true, opacity: 0.16, depthWrite: false }));
  m.renderOrder = 1; return m;
}

// Little paper confetti in 3D for a thank-you (kind colours), recycled
export function confetti(scene, n = 40) {
  const cols = Object.values(KIND);
  // n tiny meshes, drawn only while they fly
  const pieces = []; const box = new BoxGeometry(0.07, 0.07, 0.012);
  const mats = cols.map((c) => new MeshBasicMaterial({ color: c }));
  for (let i = 0; i < n; i++) { const m = new Mesh(box, mats[i % mats.length]); m.visible = false; scene.add(m); pieces.push({ m, v: new Vector3(), life: 0 }); }
  return {
    fire(at, up = 1) { for (const p of pieces) { p.m.position.copy(at); const a = Math.random() * Math.PI * 2, r = 0.6 + Math.random() * 1.4; p.v.set(Math.cos(a) * r, (2.2 + Math.random() * 1.6) * up, Math.sin(a) * r); p.life = 1.6 + Math.random() * 0.6; p.m.visible = true; } },
    step(dt) { for (const p of pieces) { if (p.life <= 0) continue; p.life -= dt; p.v.y -= 5.5 * dt; p.v.multiplyScalar(1 - 1.2 * dt); p.m.position.addScaledVector(p.v, dt); p.m.rotation.x += dt * 7; p.m.rotation.y += dt * 5; if (p.life <= 0) p.m.visible = false; } },
  };
}

// Themes for the scene lighting: light mode is a sunny day; dark mode is the same place at dusk.
export function applyLight(stage, mode) {
  const dusk = mode === 'dark';
  stage.hemi.color.set(dusk ? 0xB8C2FF : 0xffffff); stage.hemi.groundColor.set(dusk ? 0x5A4E6A : 0xb9a98f);
  stage.hemi.intensity = dusk ? 1.55 : 1.6;
  stage.sun.color.set(dusk ? 0xFFB27A : 0xfff1dc); stage.sun.intensity = dusk ? 1.6 : 2.2;
  stage.sun.position.set(dusk ? -10 : -6, dusk ? 5 : 12, dusk ? 4 : 8);
}

export { Group, Mesh, Vector3, Color, BoxGeometry, CylinderGeometry, ConeGeometry, SphereGeometry, IcosahedronGeometry, CircleGeometry, TorusGeometry, MeshLambertMaterial, MeshBasicMaterial };
