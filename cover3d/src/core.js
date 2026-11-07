// Small shared helpers for the cover world (F-206; from the prototype docs/design/cover3d/src/core.js): seeded noise (2-D simplex with fBm and a ridged variant, after
// Meng To's threejs-landscape demo, MIT), easing, springs, and a vertex-colour merge so static scenery is
// one draw call (from the story3d prototype's Kit).
import { BufferGeometry, Float32BufferAttribute, Color, Matrix4, Quaternion, Euler, Vector3, Vector2 } from 'three';

export const TAU = Math.PI * 2;
export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const sat = (v) => clamp(v, 0, 1);
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (e0, e1, x) => { const t = sat((x - e0) / (e1 - e0)); return t * t * (3 - 2 * t); };
export const easeIO = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
export const easeOut = (t) => 1 - Math.pow(1 - t, 3);
// frame-rate independent damping (Kage's rig uses rate 5.2)
export const damp = (cur, to, rate, dt) => lerp(cur, to, 1 - Math.exp(-rate * dt));
// a window: 0 before a, rises to 1 by b, holds, falls back to 0 between c and d
export const band = (x, a, b, c, d) => smooth(a, b, x) * (1 - smooth(c, d, x));

export function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* 2-D simplex noise, fBm and ridged multifractal */
const perm = (() => {
  const p = new Uint8Array(256), out = new Uint8Array(512), r = mulberry32(1337);
  for (let i = 0; i < 256; i++) p[i] = i;
  for (let i = 255; i > 0; i--) { const j = (r() * (i + 1)) | 0; const t = p[i]; p[i] = p[j]; p[j] = t; }
  for (let i = 0; i < 512; i++) out[i] = p[i & 255];
  return out;
})();
const G = [[1, 1], [-1, 1], [1, -1], [-1, -1], [1, 0], [-1, 0], [0, 1], [0, -1]];
const F2 = 0.5 * (Math.sqrt(3) - 1), G2 = (3 - Math.sqrt(3)) / 6;
export function snoise(xin, yin) {
  const s = (xin + yin) * F2;
  let i = Math.floor(xin + s), j = Math.floor(yin + s);
  const t = (i + j) * G2, x0 = xin - (i - t), y0 = yin - (j - t);
  const i1 = x0 > y0 ? 1 : 0, j1 = x0 > y0 ? 0 : 1;
  const x1 = x0 - i1 + G2, y1 = y0 - j1 + G2, x2 = x0 - 1 + 2 * G2, y2 = y0 - 1 + 2 * G2;
  i &= 255; j &= 255;
  let n = 0, tt, g;
  tt = 0.5 - x0 * x0 - y0 * y0; if (tt > 0) { tt *= tt; g = G[perm[i + perm[j]] & 7]; n += tt * tt * (g[0] * x0 + g[1] * y0); }
  tt = 0.5 - x1 * x1 - y1 * y1; if (tt > 0) { tt *= tt; g = G[perm[i + i1 + perm[j + j1]] & 7]; n += tt * tt * (g[0] * x1 + g[1] * y1); }
  tt = 0.5 - x2 * x2 - y2 * y2; if (tt > 0) { tt *= tt; g = G[perm[i + 1 + perm[j + 1]] & 7]; n += tt * tt * (g[0] * x2 + g[1] * y2); }
  return 70 * n;
}
export function fbm(x, y, oct = 4, gain = 0.5) {
  let a = 1, f = 1, s = 0, n = 0;
  for (let i = 0; i < oct; i++) { s += snoise(x * f, y * f) * a; n += a; a *= gain; f *= 2.02; }
  return s / n;
}
export function ridged(x, y, oct = 3) {
  let a = 1, f = 1, s = 0, n = 0;
  for (let i = 0; i < oct; i++) { const v = 1 - Math.abs(snoise(x * f, y * f)); s += v * v * a; n += a; a *= 0.5; f *= 2.07; }
  return s / n;
}

/* springs: an underdamped spring for small things that pop (pins, stamps) */
export class Spring {
  constructor(v = 0, k = 170, c = 14) { this.v = v; this.t = v; this.vel = 0; this.k = k; this.c = c; }
  step(dt) {
    const n = Math.ceil(dt / (1 / 120)), h = dt / n;
    for (let i = 0; i < n; i++) { const a = -this.k * (this.v - this.t) - this.c * this.vel; this.vel += a * h; this.v += this.vel * h; }
    return this.v;
  }
  snap(v) { this.v = this.t = v; this.vel = 0; return this; }
}

/* one draw call for static scenery: merge geometries with vertex colours */
export class Kit {
  constructor() { this.pos = []; this.nor = []; this.col = []; this.extra = null; }
  add(geo, color, matrix, extraVal) {
    const g = geo.index ? geo.toNonIndexed() : geo.clone();
    if (matrix) g.applyMatrix4(matrix);
    g.computeVertexNormals();
    const p = g.attributes.position.array, n = g.attributes.normal.array, c = new Color(color);
    for (let i = 0; i < p.length; i++) { this.pos.push(p[i]); this.nor.push(n[i]); }
    for (let i = 0; i < p.length / 3; i++) { this.col.push(c.r, c.g, c.b); if (this.extra) this.extra.push(extraVal || 0); }
    return this;
  }
  // per-vertex colour from a function (snow on the tops of cones, etc.)
  addFn(geo, matrix, colorFn) {
    const g = geo.index ? geo.toNonIndexed() : geo.clone();
    if (matrix) g.applyMatrix4(matrix);
    g.computeVertexNormals();
    const p = g.attributes.position.array, n = g.attributes.normal.array, c = new Color();
    for (let i = 0; i < p.length; i += 3) {
      const e = colorFn(c, p[i], p[i + 1], p[i + 2], n[i], n[i + 1], n[i + 2]);
      this.pos.push(p[i], p[i + 1], p[i + 2]); this.nor.push(n[i], n[i + 1], n[i + 2]); this.col.push(c.r, c.g, c.b);
      if (this.extra) this.extra.push(e || 0);
    }
    return this;
  }
  withExtra() { this.extra = []; return this; }
  geometry() {
    const g = new BufferGeometry();
    g.setAttribute('position', new Float32BufferAttribute(this.pos, 3));
    g.setAttribute('normal', new Float32BufferAttribute(this.nor, 3));
    g.setAttribute('color', new Float32BufferAttribute(this.col, 3));
    if (this.extra) g.setAttribute('aExtra', new Float32BufferAttribute(this.extra, 1));
    return g;
  }
}
const _q = new Quaternion(), _e = new Euler(), _s = new Vector3(), _p = new Vector3();
export function M(x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, sx = 1, sy = sx, sz = sx) {
  return new Matrix4().compose(_p.set(x, y, z), _q.setFromEuler(_e.set(rx, ry, rz)), _s.set(sx, sy, sz));
}

/* colours for custom shaders are authored in sRGB and used as-is (the custom shaders work in display space) */
export const srgb = (hex) => new Vector3(((hex >> 16) & 255) / 255, ((hex >> 8) & 255) / 255, (hex & 255) / 255);
export const mixHex = (a, b, t) => {
  const ar = (a >> 16) & 255, ag = (a >> 8) & 255, ab = a & 255, br = (b >> 16) & 255, bg = (b >> 8) & 255, bb = b & 255;
  return (Math.round(lerp(ar, br, t)) << 16) | (Math.round(lerp(ag, bg, t)) << 8) | Math.round(lerp(ab, bb, t));
};
export { Vector2, Vector3, Color };

/* The quality governor (Kage's, after Meng To's build-threejs-scroll-worlds): after a warm-up it averages frame times every second or every 45 frames,
   steps the resolution scale down while frames take longer than 23 ms (faster when over 45 ms), back up below 17.5 ms, and gives up for the calm
   stills after three windows in a row over 45 ms at the lowest scale. Pure, so a test can feed it frame times. */
export class Governor {
  constructor({ min = 0.55, warm = 2.5, onScale = () => {}, onGiveUp = () => {} } = {}) {
    Object.assign(this, { min, warm, onScale, onGiveUp, scale: 1, t: 0, acc: 0, n: 0, bad: 0, done: false });
  }
  feed(raw) {
    if (this.done) return;
    this.t += raw;
    if (this.t < this.warm) return;
    this.acc += raw; this.n++;
    if (this.n < 45 && this.acc < 1) return;
    const avg = this.acc / this.n; this.acc = 0; this.n = 0;
    const was = this.scale;
    if (avg > 0.023 && this.scale > this.min) this.scale = Math.max(this.min, this.scale * (avg > 0.045 ? 0.7 : 0.86));
    else if (avg < 0.0175 && this.scale < 1) this.scale = Math.min(1, this.scale + 0.06);      // 17.5 ms: a 60 Hz screen never shows a frame faster than 16.7
    if (this.scale !== was) this.onScale(this.scale);
    if (avg > 0.045 && this.scale <= this.min + 0.01) { if (++this.bad >= 3) { this.done = true; this.onGiveUp(); } } else this.bad = 0;
  }
}

/* the world size of `px` screen pixels at distance `d` from a camera with vertical field of view `fovDeg` on a viewport `vh` pixels tall */
export const pxAt = (px, d, fovDeg, vh) => (px * 2 * d * Math.tan((fovDeg * Math.PI) / 360)) / vh;
