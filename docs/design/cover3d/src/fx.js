// What the story draws on the world: glowing trails (a shared trip is a line with pins, like a git branch),
// kind-coloured pins, snowfall, the thank-you sparkle, and postcards made from real renders of the world.
import {
  BufferGeometry, Float32BufferAttribute, InstancedBufferGeometry, InstancedBufferAttribute, Mesh, Points, Group,
  ShaderMaterial, MeshBasicMaterial, PlaneGeometry, SphereGeometry, ConeGeometry, CircleGeometry, RingGeometry,
  CatmullRomCurve3, Vector3, Color, DoubleSide, AdditiveBlending, NormalBlending, WebGLRenderTarget, PerspectiveCamera,
  InstancedMesh, MeshLambertMaterial, CanvasTexture as CT2, Matrix4, Quaternion, Euler,
} from 'three';
import { landH } from './geo.js';
import { mulberry32, srgb, clamp, lerp, TAU, Kit, M } from './core.js';

export const KIND = { flight: 0x4338ca, stay: 0x8b2fc9, car: 0x15803d, tix: 0xc2410c, wx: 0x0369a1, food: 0xc92a5e, see: 0x0f766e, ride: 0xffd43b };

/* ------------------------------------------------------------------ trails */
// A ribbon laid on the ground along a smoothed path. One mesh per trail: a crisp core in the middle of a soft
// halo, drawn on by uDraw (0..1 of its length) with a bright head where the line is growing.
export function buildTrail(pts, opts = {}) {
  const lift = opts.lift ?? 0.16;
  const curve = new CatmullRomCurve3(pts.map((p) => new Vector3(p[0], p.length > 2 ? p[2] : 0, p[1])), false, 'centripetal', 0.5);
  const len = curve.getLength(), n = Math.max(8, Math.ceil(len / (opts.step || 0.35)));
  const sp = curve.getSpacedPoints(n);
  const pos = [], side = [], dir = [], u = [], idx = [];
  for (let i = 0; i <= n; i++) {
    const p = sp[i], a = sp[Math.max(0, i - 1)], b = sp[Math.min(n, i + 1)];
    let dx = b.x - a.x, dz = b.z - a.z; const l = Math.hypot(dx, dz) || 1; dx /= l; dz /= l;
    const y = pts[0].length > 2 ? p.y : landH(p.x, p.z) + lift;
    for (const s of [-1, 1]) { pos.push(p.x, Math.max(y, lift), p.z); side.push(s); dir.push(-dz, dx); u.push(i / n); }
    if (i < n) { const k = i * 2; idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
  }
  const g = new BufferGeometry();
  g.setAttribute('position', new Float32BufferAttribute(pos, 3)); g.setAttribute('aSide', new Float32BufferAttribute(side, 1));
  g.setAttribute('aDir', new Float32BufferAttribute(dir, 2)); g.setAttribute('aU', new Float32BufferAttribute(u, 1)); g.setIndex(idx);
  const U = {
    uWidth: { value: opts.width || 0.5 }, uDraw: { value: 0 }, uFrom: { value: 0 }, uColor: { value: srgb(0x0b0b0d) }, uHalo: { value: srgb(0x0b0b0d) },
    uHaloA: { value: 0.18 }, uOpacity: { value: 1 }, uTime: { value: 0 }, uLen: { value: len }, uHead: { value: 1 }, uPulse: { value: srgb(0x8c8c96) }, uDash: { value: opts.dash ? 1 : 0 },
  };
  const mat = new ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false, side: DoubleSide,
    polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
    vertexShader: `uniform float uWidth; attribute float aSide; attribute vec2 aDir; attribute float aU; varying float vS; varying float vU;
      void main(){ vS = aSide; vU = aU; vec3 p = position + vec3(aDir.x, 0.0, aDir.y) * aSide * uWidth; p.y += uWidth * 0.3;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0); }`,
    fragmentShader: `uniform float uDraw, uFrom, uHaloA, uOpacity, uTime, uLen, uHead, uDash; uniform vec3 uColor, uHalo, uPulse; varying float vS; varying float vU;
      void main(){
        float a = abs(vS);
        float core = 1.0 - smoothstep(0.30, 0.42, a);
        float halo = pow(1.0 - a, 2.0) * uHaloA;
        float d = (uDraw - vU) * uLen;           // distance behind the growing head, in world units
        float drawn = smoothstep(-0.05, 0.25, d) * smoothstep(-0.05, 0.25, (vU - uFrom) * uLen);
        if (uDash > 0.5) core *= step(0.45, fract(vU * uLen / 1.1));
        float pulse = smoothstep(0.92, 1.0, 1.0 - abs(fract(vU * uLen / 14.0 - uTime * 0.25) - 0.5) * 2.0);
        vec3 col = mix(uColor, uPulse, pulse * 0.55 * core);
        float head = exp(-d * d / 0.8) * uHead * step(0.0, uDraw - 0.001) * step(uDraw, 0.999);
        float alpha = (core + halo * (1.0 - core)) * drawn;
        col = mix(mix(uHalo, col, core), uPulse, head * 0.7);
        alpha = max(alpha, head * (1.0 - a) * 0.9);
        if (alpha < 0.01) discard;
        gl_FragColor = vec4(col, alpha * uOpacity);
      }`,
  });
  const mesh = new Mesh(g, mat); mesh.renderOrder = 3; mesh.frustumCulled = false;
  mesh.userData = { U, curve, len, at: (t, out = new Vector3()) => { curve.getPointAt(clamp(t, 0, 1), out); if (pts[0].length <= 2) out.y = landH(out.x, out.z) + lift; return out; } };
  return mesh;
}
// arc-length fraction of the closest point on a trail to a world point (to know when the head reaches a pin)
export function fractionAt(trail, x, z) {
  const c = trail.userData.curve, n = 400, v = new Vector3(); let best = 1e9, bt = 0;
  for (let i = 0; i <= n; i++) { c.getPointAt(i / n, v); const d = Math.hypot(v.x - x, v.z - z); if (d < best) { best = d; bt = i / n; } }
  return bt;
}
export function setTrailLook(trail, dark, dim = 0) {
  const U = trail.material.uniforms;
  U.uColor.value.copy(srgb(dark ? 0xf5f5f7 : 0x0b0b0d)).lerp(srgb(dark ? 0x6b7186 : 0x9a9aa4), dim);
  U.uHalo.value.copy(srgb(dark ? 0xbcd2ff : 0x0b0b0d));
  U.uHaloA.value = dark ? 0.55 : 0.16;
  U.uPulse.value.copy(srgb(dark ? 0xffffff : 0x8c8c96));
}

/* ------------------------------------------------------------------ pins */
// Instanced map pins in kind colours: a ball on a short stem with a white dot, and a soft ring on the ground.
export function buildPins(list) {
  const n = list.length;
  const k = new Kit().withExtra();
  k.add(new ConeGeometry(0.11, 0.42, 10), 0xffffff, M(0, 0.21, 0, Math.PI), 0);
  k.add(new SphereGeometry(0.3, 16, 12), 0xffffff, M(0, 0.62, 0), 0);
  k.add(new SphereGeometry(0.11, 10, 8), 0xffffff, M(0, 0.66, 0.24), 1);
  const base = k.geometry();
  const g = new InstancedBufferGeometry(); g.index = null;
  g.setAttribute('position', base.attributes.position); g.setAttribute('normal', base.attributes.normal); g.setAttribute('aWhite', base.attributes.aExtra);
  const aPos = new Float32Array(n * 3), aCol = new Float32Array(n * 3), aScale = new Float32Array(n);
  list.forEach((p, i) => { aPos.set([p.x, p.y, p.z], i * 3); const c = srgb(p.color); aCol.set([c.x, c.y, c.z], i * 3); aScale[i] = 0; });
  g.setAttribute('aPos', new InstancedBufferAttribute(aPos, 3)); g.setAttribute('aCol', new InstancedBufferAttribute(aCol, 3));
  const scaleAttr = new InstancedBufferAttribute(aScale, 1); g.setAttribute('aScale', scaleAttr); g.instanceCount = n;
  const U = { uPin: { value: 1 }, uNight: { value: 0 }, uLight: { value: new Vector3(-0.5, 0.7, 0.5).normalize() } };
  const mat = new ShaderMaterial({
    uniforms: U,
    vertexShader: `uniform float uPin; attribute vec3 aPos; attribute vec3 aCol; attribute float aScale; attribute float aWhite; varying vec3 vC; varying float vW; varying vec3 vN;
      void main(){ vC = aCol; vW = aWhite; vN = normal; vec3 p = aPos + position * aScale * uPin; gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0); }`,
    fragmentShader: `uniform vec3 uLight; uniform float uNight; varying vec3 vC; varying float vW; varying vec3 vN;
      void main(){ float l = 0.78 + 0.22 * max(dot(normalize(vN), uLight), 0.0); vec3 c = mix(vC, vec3(1.0), vW) * l;
        c = mix(c, c * 1.15 + 0.05, uNight); gl_FragColor = vec4(c, 1.0); }`,
  });
  const mesh = new Mesh(g, mat); mesh.frustumCulled = false; mesh.renderOrder = 4;
  // ground rings
  const rg = new InstancedBufferGeometry(); const ring = new RingGeometry(0.34, 0.62, 28); ring.rotateX(-Math.PI / 2);
  rg.index = ring.index; rg.setAttribute('position', ring.attributes.position); rg.setAttribute('uv', ring.attributes.uv);
  rg.setAttribute('aPos', g.attributes.aPos); rg.setAttribute('aCol', g.attributes.aCol); rg.setAttribute('aScale', scaleAttr); rg.instanceCount = n;
  const rmat = new ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -6, polygonOffsetUnits: -6,
    vertexShader: `uniform float uPin; attribute vec3 aPos; attribute vec3 aCol; attribute float aScale; varying vec3 vC; varying float vA;
      void main(){ vC = aCol; vA = aScale; vec3 p = aPos + vec3(0.0, 0.05, 0.0) + position * aScale * uPin * 1.2; gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0); }`,
    fragmentShader: `varying vec3 vC; varying float vA; void main(){ gl_FragColor = vec4(vC, 0.5 * clamp(vA, 0.0, 1.0)); }`,
  });
  const rings = new Mesh(rg, rmat); rings.frustumCulled = false; rings.renderOrder = 3;
  const group = new Group(); group.add(rings, mesh);
  const springs = list.map(() => ({ v: 0, vel: 0, t: 0 }));
  group.userData = {
    U, list,
    set(i, target) { springs[i].t = target; },
    snap(i, v) { springs[i].v = springs[i].t = v; springs[i].vel = 0; },
    step(dt) {
      let any = false;
      for (let i = 0; i < n; i++) {
        const s = springs[i]; if (Math.abs(s.v - s.t) < 1e-3 && Math.abs(s.vel) < 1e-3) { if (aScale[i] !== s.t) { aScale[i] = s.t; any = true; } continue; }
        const steps = Math.ceil(dt / (1 / 120)), h = dt / steps;
        for (let k2 = 0; k2 < steps; k2++) { const acc = -220 * (s.v - s.t) - 15 * s.vel; s.vel += acc * h; s.v += s.vel * h; }
        aScale[i] = Math.max(0, s.v); any = true;
      }
      if (any) scaleAttr.needsUpdate = true;
    },
  };
  return group;
}

/* ------------------------------------------------------------------ snow */
// GPU snowfall wrapped around the camera: no per-frame CPU work (positions wrap in the vertex shader), and
// recycled ahead of the lens so the count is what one screenful needs (Kage's leaf-fall lesson).
export function buildSnow(count) {
  const rnd = mulberry32(44), B = 60;
  const pos = new Float32Array(count * 3), seed = new Float32Array(count);
  for (let i = 0; i < count; i++) { pos[i * 3] = rnd() * B; pos[i * 3 + 1] = rnd() * B; pos[i * 3 + 2] = rnd() * B; seed[i] = rnd(); }
  const g = new BufferGeometry(); g.setAttribute('position', new Float32BufferAttribute(pos, 3)); g.setAttribute('aSeed', new Float32BufferAttribute(seed, 1));
  const U = { uTime: { value: 0 }, uCam: { value: new Vector3() }, uAmt: { value: 0 }, uSize: { value: 1 }, uColor: { value: srgb(0xffffff) }, uB: { value: B }, uWind: { value: 0.6 }, uSpeed: { value: 1 }, uFlake: { value: 1 } };
  const mat = new ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false,
    vertexShader: `uniform float uTime, uAmt, uSize, uB, uWind, uSpeed, uFlake; uniform vec3 uCam; attribute float aSeed; varying float vA;
      void main(){
        vec3 p = position;
        p.y -= uTime * (1.1 + aSeed * 1.4) * uSpeed;
        p.x += uTime * uWind * (0.6 + aSeed * 0.5) + sin(uTime * (0.6 + aSeed) + aSeed * 40.0) * 0.9;
        p.z += cos(uTime * 0.5 + aSeed * 23.0) * 0.6;
        p = mod(p - uCam + uB * 0.5, uB) + uCam - uB * 0.5;
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        float depth = -mv.z;
        vA = step(aSeed, uAmt) * smoothstep(0.6, 3.0, depth) * (1.0 - smoothstep(uB * 0.32, uB * 0.5, depth));
        gl_PointSize = uSize * uFlake * (2.0 + aSeed * 3.0) * 60.0 / max(depth, 0.5);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `uniform vec3 uColor; varying float vA; void main(){ float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.15, d) * vA; if (a < 0.01) discard; gl_FragColor = vec4(uColor, a * 0.9); }`,
  });
  const pts = new Points(g, mat); pts.frustumCulled = false; pts.renderOrder = 6;
  pts.userData.U = U;
  return pts;
}

/* ------------------------------------------------------------------ the thank-you sparkle */
export function buildSparkle(n = 46) {
  const rnd = mulberry32(12), cols = Object.values(KIND);
  const pos = new Float32Array(n * 3), seed = new Float32Array(n * 3), col = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { seed.set([rnd(), rnd(), rnd()], i * 3); const c = srgb(cols[i % cols.length]); col.set([c.x, c.y, c.z], i * 3); }
  const g = new BufferGeometry(); g.setAttribute('position', new Float32BufferAttribute(pos, 3)); g.setAttribute('aSeed', new Float32BufferAttribute(seed, 3)); g.setAttribute('aCol', new Float32BufferAttribute(col, 3));
  const U = { uA: { value: new Vector3() }, uB: { value: new Vector3() }, uT: { value: 0 }, uTime: { value: 0 }, uSize: { value: 1 }, uArc: { value: 4 } };
  const mat = new ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false, depthTest: false,
    vertexShader: `uniform vec3 uA, uB; uniform float uT, uTime, uSize, uArc; attribute vec3 aSeed; attribute vec3 aCol; varying vec3 vC; varying float vA;
      void main(){
        float t = clamp(uT * 1.25 - aSeed.x * 0.25, 0.0, 1.0);
        vec3 p = mix(uA, uB, t); p.y += sin(t * 3.14159) * uArc;
        float spread = sin(t * 3.14159) * 1.4 + (t > 0.97 ? (t - 0.97) * 30.0 : 0.0);
        p += (aSeed - 0.5) * spread * vec3(1.6, 1.0, 1.6);
        vC = aCol; vA = smoothstep(0.0, 0.08, t) * (1.0 - smoothstep(0.92, 1.0, uT)) * (0.6 + 0.4 * sin(uTime * 9.0 + aSeed.y * 30.0));
        vec4 mv = viewMatrix * vec4(p, 1.0); gl_PointSize = uSize * (8.0 + aSeed.z * 10.0) * 30.0 / max(-mv.z, 1.0); gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `varying vec3 vC; varying float vA;
      void main(){ vec2 q = gl_PointCoord - 0.5; float star = max(1.0 - abs(q.x) * 9.0 - abs(q.y) * 2.2, 1.0 - abs(q.y) * 9.0 - abs(q.x) * 2.2); float a = clamp(star, 0.0, 1.0) * vA + smoothstep(0.22, 0.0, length(q)) * vA;
        if (a < 0.02) discard; gl_FragColor = vec4(mix(vC, vec3(1.0), 0.25), a); }`,
  });
  const p = new Points(g, mat); p.frustumCulled = false; p.renderOrder = 8; p.userData.U = U;
  return p;
}

/* ------------------------------------------------------------------ postcards */
// Four postcards whose photos are real renders of this world from the family's spots, made once into small
// render targets (no readback), so the cards that fly away really are the trip's photos.
export function buildPostcards(views) {
  const group = new Group(), cards = [], targets = [];
  views.forEach((v, i) => {
    const rt = new WebGLRenderTarget(320, 224); targets.push(rt);
    const card = new Group();
    const frame = new Mesh(new PlaneGeometry(1.0, 0.76), new MeshBasicMaterial({ color: 0xfbfaf7, side: DoubleSide }));
    const photo = new Mesh(new PlaneGeometry(0.9, 0.63), new MeshBasicMaterial({ map: rt.texture, side: DoubleSide }));
    photo.position.set(0, 0.035, 0.003);
    card.add(frame, photo); card.visible = false; group.add(card); cards.push(card);
  });
  group.userData = { cards, targets, views };
  return group;
}
export function renderPostcards(renderer, scene, group, prep) {
  const cam = new PerspectiveCamera(46, 320 / 224, 0.1, 600);
  const { targets, views, cards } = group.userData;
  const vis = cards.map((c) => c.visible); cards.forEach((c) => (c.visible = false));
  views.forEach((v, i) => {
    cam.position.set(...v.p); cam.lookAt(...v.t); cam.updateMatrixWorld();
    prep && prep(cam);
    renderer.setRenderTarget(targets[i]); renderer.render(scene, cam);
  });
  renderer.setRenderTarget(null);
  cards.forEach((c, i) => (c.visible = vis[i]));
}

/* ------------------------------------------------------------------ falling leaves */
// Instanced leaves that tumble through face, edge and back while their sideways slip follows the tumble, recycled
// in the cone ahead of the camera (Meng To's 3d-falling-leaves and Kage's leaf fall, MIT, adapted).
export function buildLeaves(n = 220) {
  const cv = document.createElement('canvas'); cv.width = cv.height = 64; const x = cv.getContext('2d');
  x.fillStyle = '#fff'; x.beginPath(); x.moveTo(32, 4); x.bezierCurveTo(58, 14, 60, 44, 32, 60); x.bezierCurveTo(4, 44, 6, 14, 32, 4); x.fill();
  x.strokeStyle = 'rgba(0,0,0,.25)'; x.lineWidth = 2; x.beginPath(); x.moveTo(32, 8); x.lineTo(32, 60); x.stroke();
  const mat = new MeshLambertMaterial({ map: new CT2(cv), alphaTest: 0.45, side: DoubleSide });
  const mesh = new InstancedMesh(new PlaneGeometry(0.34, 0.34), mat, n);
  const rnd = mulberry32(404), cols = [0xf2b02c, 0xe58a1f, 0xf5c84a, 0xd9661c, 0xf0d050];
  const L = []; const c = new Color();
  for (let i = 0; i < n; i++) { L.push({ x: 0, y: 0, z: 0, fall: 0.5 + rnd() * 0.7, om: 1.2 + rnd() * 2.2, ph: rnd() * TAU, slip: 0.8 + rnd() * 1.2, roll: rnd() * TAU, rs: 0.6 + rnd() * 1.6, s: 0.7 + rnd() * 0.7, seeded: false }); mesh.setColorAt(i, c.set(cols[i % cols.length])); }
  mesh.frustumCulled = false; mesh.count = 0;
  const m4 = new Matrix4(), q = new Quaternion(), e = new Euler(), v = new Vector3(), sc = new Vector3(), f = new Vector3();
  mesh.userData.step = (dt, time, camera, amt) => {
    const want = Math.round(n * amt); mesh.count = want; if (!want) return;
    camera.getWorldDirection(f); f.y = 0; if (f.lengthSq() < 1e-6) f.set(0, 0, -1); f.normalize();
    const ax = camera.position.x + f.x * 9, az = camera.position.z + f.z * 9, cy = camera.position.y;
    for (let i = 0; i < want; i++) {
      const l = L[i];
      l.y -= l.fall * dt; l.roll += l.rs * dt;
      if (!l.seeded || l.y < cy - 8) { const a = Math.random() * TAU, r = Math.sqrt(Math.random()) * 9; l.x = ax + Math.cos(a) * r; l.z = az + Math.sin(a) * r; l.y = l.seeded ? cy + 7 : cy - 8 + Math.random() * 15; l.seeded = true; }
      const ang = l.ph + l.om * time, side = -(l.slip / l.om) * Math.cos(ang);
      v.set(l.x + side * f.z, l.y, l.z - side * f.x);
      e.set(ang, l.roll, Math.sin(ang) * 0.6); q.setFromEuler(e); sc.setScalar(l.s); m4.compose(v, q, sc); mesh.setMatrixAt(i, m4);
    }
    mesh.instanceMatrix.needsUpdate = true;
  };
  return mesh;
}
