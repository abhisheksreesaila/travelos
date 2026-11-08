// What the story draws on the world (F-206; from the prototype's fx.js, made for true scale): a shared trip is a line on the real roads with pins at
// its days, like a git branch, and both keep the same width and size on screen whether the camera is over the pier or thirty kilometres up; snow that
// falls round the lens; the thank-you sparkle; postcards whose photos are real renders of this world.
import {
  BufferGeometry, Float32BufferAttribute, InstancedBufferGeometry, InstancedBufferAttribute, Mesh, Points, Group, ShaderMaterial, MeshBasicMaterial, PlaneGeometry,
  SphereGeometry, ConeGeometry, RingGeometry, CatmullRomCurve3, Vector3, Color, DoubleSide, WebGLRenderTarget, PerspectiveCamera,
} from 'three';
import { mulberry32, clamp, Kit, M } from './core.js';

export const KIND = { flight: 0x4338ca, stay: 0x8b2fc9, car: 0x15803d, tix: 0xc2410c, wx: 0x0369a1, food: 0xc92a5e, see: 0x0f766e };
const LOGV = '#include <common>\n#include <logdepthbuf_pars_vertex>\n', LOGF = '#include <common>\n#include <logdepthbuf_pars_fragment>\n';

/* ------------------------------------------------------------------ trails */
// A ribbon laid on the ground (or the lake) along a smoothed path: a crisp core in a soft halo, `uPx` pixels wide wherever it is, drawn on by
// uDraw (0..1 of its length) with a bright head where it grows. `pts` are [x, z] (on the ground) or [x, z, y] (y given, for a path on the water).
export function buildTrail(T, pts, opts = {}) {
  const lift = opts.lift ?? 1.2;
  const yAt = (x, z) => { const w = T.waterY(x, z); return Math.max(T.landH(x, z), w ?? -1e9) + lift; };
  const curve = new CatmullRomCurve3(pts.map((p) => new Vector3(p[0], p.length > 2 ? p[2] : 0, p[1])), false, 'centripetal', 0.5);
  const len = curve.getLength(), n = Math.max(16, Math.min(4000, Math.ceil(len / (opts.step || 18))));
  const sp = curve.getSpacedPoints(n);
  const pos = [], side = [], dir = [], u = [], idx = [];
  for (let i = 0; i <= n; i++) {
    const p = sp[i], a = sp[Math.max(0, i - 1)], b = sp[Math.min(n, i + 1)];
    let dx = b.x - a.x, dz = b.z - a.z; const l = Math.hypot(dx, dz) || 1; dx /= l; dz /= l;
    const y = pts[0].length > 2 ? p.y : yAt(p.x, p.z);
    for (const s of [-1, 1]) { pos.push(p.x, y, p.z); side.push(s); dir.push(-dz, dx); u.push(i / n); }
    if (i < n) { const k = i * 2; idx.push(k, k + 2, k + 1, k + 1, k + 2, k + 3); }
  }
  const g = new BufferGeometry();
  g.setAttribute('position', new Float32BufferAttribute(pos, 3)); g.setAttribute('aSide', new Float32BufferAttribute(side, 1));
  g.setAttribute('aDir', new Float32BufferAttribute(dir, 2)); g.setAttribute('aU', new Float32BufferAttribute(u, 1)); g.setIndex(idx);
  const U = {
    uPx: { value: opts.px || 5 }, uRes: { value: 900 }, uTanFov: { value: 0.36 }, uRise: { value: 1 }, uDraw: { value: 0 }, uColor: { value: new Color(0x0b0b0d) }, uHalo: { value: new Color(0x0b0b0d) },
    uHaloA: { value: 0.18 }, uOpacity: { value: 1 }, uTime: { value: 0 }, uLen: { value: len }, uPulse: { value: new Color(0x8c8c96) }, uMinW: { value: opts.minW ?? 0.6 },
  };
  const mat = new ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false, side: DoubleSide,
    vertexShader: LOGV + `uniform float uPx, uRes, uTanFov, uRise, uMinW; attribute float aSide; attribute vec2 aDir; attribute float aU; varying float vS; varying float vU;
      void main(){ vS = aSide; vU = aU; vec3 p = position; p.y *= uRise;
        float d = length((viewMatrix * vec4(p, 1.0)).xyz);
        float w = max(uMinW, uPx * d * uTanFov * 2.0 / uRes) * 0.5;      // half the width, in metres, for uPx pixels at this distance
        p += vec3(aDir.x, 0.0, aDir.y) * aSide * w; p.y += w * 0.15;
        gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: LOGF + `uniform float uDraw, uHaloA, uOpacity, uTime, uLen; uniform vec3 uColor, uHalo, uPulse; varying float vS; varying float vU;
      void main(){
        #include <logdepthbuf_fragment>
        float a = abs(vS);
        float core = 1.0 - smoothstep(0.32, 0.46, a);
        float halo = pow(1.0 - a, 2.0) * uHaloA;
        float d = (uDraw - vU) * uLen;
        float drawn = smoothstep(-uLen * 0.0005, uLen * 0.002, d);
        float pulse = smoothstep(0.92, 1.0, 1.0 - abs(fract(vU * uLen / 1400.0 - uTime * 0.25) - 0.5) * 2.0);
        vec3 col = mix(uColor, uPulse, pulse * 0.55 * core);
        float head = exp(-d * d / (uLen * uLen * 0.00002)) * step(0.0, uDraw - 0.001) * step(uDraw, 0.999);
        float alpha = (core + halo * (1.0 - core)) * drawn;
        col = mix(mix(uHalo, col, core), uPulse, head * 0.7);
        alpha = max(alpha, head * (1.0 - a) * 0.9);
        if (alpha < 0.01) discard;
        gl_FragColor = vec4(col, alpha * uOpacity);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const mesh = new Mesh(g, mat); mesh.renderOrder = 3; mesh.frustumCulled = false;
  mesh.userData = { U, curve, len, at: (t, out = new Vector3()) => { curve.getPointAt(clamp(t, 0, 1), out); out.y = pts[0].length > 2 ? out.y : yAt(out.x, out.z); return out; } };
  return mesh;
}
export function fractionAt(trail, x, z) {
  const c = trail.userData.curve, n = 600, v = new Vector3(); let best = 1e18, bt = 0;
  for (let i = 0; i <= n; i++) { c.getPointAt(i / n, v); const d = (v.x - x) ** 2 + (v.z - z) ** 2; if (d < best) { best = d; bt = i / n; } }
  return bt;
}
export function setTrailLook(trail, dark, dim = 0) {
  const U = trail.material.uniforms;
  U.uColor.value.set(dark ? 0xf5f5f7 : 0x0b0b0d).lerp(new Color(dark ? 0x6b7186 : 0x9a9aa4), dim);
  U.uHalo.value.set(dark ? 0xbcd2ff : 0x0b0b0d);
  U.uHaloA.value = dark ? 0.55 : 0.16;
  U.uPulse.value.set(dark ? 0xffffff : 0x8c8c96);
}

/* ------------------------------------------------------------------ pins */
// Kind-coloured map pins, a ball on a short stem with a white dot and a soft ring on the ground, `uPx` pixels tall wherever they are.
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
  const c = new Color();
  list.forEach((p, i) => { aPos.set([p.x, p.y, p.z], i * 3); c.set(p.color); aCol.set([c.r, c.g, c.b], i * 3); });
  g.setAttribute('aPos', new InstancedBufferAttribute(aPos, 3)); g.setAttribute('aCol', new InstancedBufferAttribute(aCol, 3));
  const scaleAttr = new InstancedBufferAttribute(aScale, 1); g.setAttribute('aScale', scaleAttr); g.instanceCount = n;
  const U = { uPx: { value: 26 }, uRes: { value: 900 }, uTanFov: { value: 0.36 }, uNight: { value: 0 }, uRise: { value: 1 }, uLight: { value: new Vector3(-0.5, 0.7, 0.5).normalize() } };
  const pinV = `uniform float uPx, uRes, uTanFov, uRise; attribute vec3 aPos; attribute vec3 aCol; attribute float aScale;
    float pinSize(vec3 at) { float d = length((viewMatrix * vec4(at, 1.0)).xyz); return uPx * d * uTanFov * 2.0 / uRes; }`;
  const mat = new ShaderMaterial({
    uniforms: U,
    vertexShader: LOGV + pinV + `attribute float aWhite; varying vec3 vC; varying float vW; varying vec3 vN;
      void main(){ vC = aCol; vW = aWhite; vN = normal; vec3 at = aPos * vec3(1.0, uRise, 1.0); vec3 p = at + position * aScale * pinSize(at); gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: LOGF + `uniform vec3 uLight; uniform float uNight; varying vec3 vC; varying float vW; varying vec3 vN;
      void main(){
        #include <logdepthbuf_fragment>
        float l = 0.78 + 0.22 * max(dot(normalize(vN), uLight), 0.0); vec3 c = mix(vC, vec3(1.0), vW) * l;
        c = mix(c, c * 1.15 + 0.05, uNight); gl_FragColor = vec4(c, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const mesh = new Mesh(g, mat); mesh.frustumCulled = false; mesh.renderOrder = 4;
  const rg = new InstancedBufferGeometry(); const ring = new RingGeometry(0.34, 0.62, 28); ring.rotateX(-Math.PI / 2);
  rg.index = ring.index; rg.setAttribute('position', ring.attributes.position);
  rg.setAttribute('aPos', g.attributes.aPos); rg.setAttribute('aCol', g.attributes.aCol); rg.setAttribute('aScale', scaleAttr); rg.instanceCount = n;
  const rmat = new ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false,
    vertexShader: LOGV + pinV + `varying vec3 vC; varying float vA;
      void main(){ vC = aCol; vA = aScale; vec3 at = aPos * vec3(1.0, uRise, 1.0); float s = pinSize(at); vec3 p = at + vec3(0.0, 0.05 * s, 0.0) + position * aScale * s * 1.2; gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: LOGF + `varying vec3 vC; varying float vA; void main(){
        #include <logdepthbuf_fragment>
        gl_FragColor = vec4(vC, 0.5 * clamp(vA, 0.0, 1.0));
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
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
        const s = springs[i];
        if (Math.abs(s.v - s.t) < 1e-3 && Math.abs(s.vel) < 1e-3) { if (aScale[i] !== s.t) { aScale[i] = s.t; any = true; } continue; }
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
// Snowfall wrapped round the camera: positions wrap in the vertex shader (no CPU work per frame) and the count is what one view needs (Kage's
// leaf-fall lesson). Flakes near the lens are soft and big, far ones fine points; `uAmt` is how much falls.
export function buildSnow(count) {
  const rnd = mulberry32(44), B = 70;
  const pos = new Float32Array(count * 3), seed = new Float32Array(count);
  for (let i = 0; i < count; i++) { pos[i * 3] = rnd() * B; pos[i * 3 + 1] = rnd() * B; pos[i * 3 + 2] = rnd() * B; seed[i] = rnd(); }
  const g = new BufferGeometry(); g.setAttribute('position', new Float32BufferAttribute(pos, 3)); g.setAttribute('aSeed', new Float32BufferAttribute(seed, 1));
  const U = { uTime: { value: 0 }, uCam: { value: new Vector3() }, uAmt: { value: 0 }, uSize: { value: 1 }, uColor: { value: new Color(0xffffff) }, uB: { value: B }, uWind: { value: 0.7 } };
  const mat = new ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false,
    vertexShader: LOGV + `uniform float uTime, uAmt, uSize, uB, uWind; uniform vec3 uCam; attribute float aSeed; varying float vA; varying float vSoft;
      void main(){
        vec3 p = position;
        p.y -= uTime * (0.9 + aSeed * 1.2);
        p.x += uTime * uWind * (0.6 + aSeed * 0.5) + sin(uTime * (0.6 + aSeed) + aSeed * 40.0) * 0.9;
        p.z += cos(uTime * 0.5 + aSeed * 23.0) * 0.6;
        p = mod(p - uCam + uB * 0.5, uB) + uCam - uB * 0.5;
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        float depth = -mv.z;
        vA = step(aSeed, uAmt) * smoothstep(0.4, 2.5, depth) * (1.0 - smoothstep(uB * 0.32, uB * 0.5, depth));
        vSoft = 1.0 - smoothstep(1.5, 8.0, depth);
        gl_PointSize = uSize * (1.6 + aSeed * 2.6) * 60.0 / max(depth, 0.4);
        gl_Position = projectionMatrix * mv;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: LOGF + `uniform vec3 uColor; varying float vA; varying float vSoft; void main(){
        #include <logdepthbuf_fragment>
        float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, mix(0.15, 0.0, vSoft), d) * vA * mix(1.0, 0.45, vSoft); if (a < 0.01) discard; gl_FragColor = vec4(uColor, a * 0.9);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const pts = new Points(g, mat); pts.frustumCulled = false; pts.renderOrder = 6;
  pts.userData.U = U;
  return pts;
}

/* ------------------------------------------------------------------ the thank-you sparkle */
export function buildSparkle(n = 46) {
  const rnd = mulberry32(12), cols = Object.values(KIND), c = new Color();
  const pos = new Float32Array(n * 3), seed = new Float32Array(n * 3), col = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { seed.set([rnd(), rnd(), rnd()], i * 3); c.set(cols[i % cols.length]); col.set([c.r, c.g, c.b], i * 3); }
  const g = new BufferGeometry(); g.setAttribute('position', new Float32BufferAttribute(pos, 3)); g.setAttribute('aSeed', new Float32BufferAttribute(seed, 3)); g.setAttribute('aCol', new Float32BufferAttribute(col, 3));
  const U = { uA: { value: new Vector3() }, uB: { value: new Vector3() }, uT: { value: 0 }, uTime: { value: 0 }, uSize: { value: 1 }, uArc: { value: 4 }, uSpread: { value: 1.4 } };
  const mat = new ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false, depthTest: false,
    vertexShader: LOGV + `uniform vec3 uA, uB; uniform float uT, uTime, uSize, uArc, uSpread; attribute vec3 aSeed; attribute vec3 aCol; varying vec3 vC; varying float vA;
      void main(){
        float t = clamp(uT * 1.25 - aSeed.x * 0.25, 0.0, 1.0);
        vec3 p = mix(uA, uB, t); p.y += sin(t * 3.14159) * uArc;
        float spread = sin(t * 3.14159) * uSpread + (t > 0.97 ? (t - 0.97) * 30.0 * uSpread / 1.4 : 0.0);
        p += (aSeed - 0.5) * spread * vec3(1.6, 1.0, 1.6);
        vC = aCol; vA = smoothstep(0.0, 0.08, t) * (1.0 - smoothstep(0.92, 1.0, uT)) * (0.6 + 0.4 * sin(uTime * 9.0 + aSeed.y * 30.0));
        vec4 mv = viewMatrix * vec4(p, 1.0); gl_PointSize = uSize * (8.0 + aSeed.z * 10.0) * 30.0 / max(-mv.z, 1.0); gl_Position = projectionMatrix * mv;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: LOGF + `varying vec3 vC; varying float vA;
      void main(){
        #include <logdepthbuf_fragment>
        vec2 q = gl_PointCoord - 0.5; float star = max(1.0 - abs(q.x) * 9.0 - abs(q.y) * 2.2, 1.0 - abs(q.y) * 9.0 - abs(q.x) * 2.2); float a = clamp(star, 0.0, 1.0) * vA + smoothstep(0.22, 0.0, length(q)) * vA;
        if (a < 0.02) discard; gl_FragColor = vec4(mix(vC, vec3(1.0), 0.25), a);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const p = new Points(g, mat); p.frustumCulled = false; p.renderOrder = 8; p.userData.U = U;
  return p;
}

/* ------------------------------------------------------------------ postcards */
// Four postcards whose photos are real renders of this world from the family's spots, made once into small render targets (no readback).
export function buildPostcards(views, size = 1.4) {
  const group = new Group(), cards = [], targets = [];
  views.forEach(() => {
    const rt = new WebGLRenderTarget(384, 268); targets.push(rt);
    const card = new Group();
    const frame = new Mesh(new PlaneGeometry(size, size * 0.76), new MeshBasicMaterial({ color: 0xfbfaf7, side: DoubleSide, toneMapped: false }));
    const photo = new Mesh(new PlaneGeometry(size * 0.9, size * 0.63), new MeshBasicMaterial({ map: rt.texture, side: DoubleSide, toneMapped: false }));
    photo.position.set(0, size * 0.035, 0.004);
    card.add(frame, photo); card.visible = false; group.add(card); cards.push(card);
  });
  group.userData = { cards, targets, views };
  return group;
}
export function renderPostcards(renderer, scene, group, prep) {
  const cam = new PerspectiveCamera(46, 384 / 268, 0.2, 90000);
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
