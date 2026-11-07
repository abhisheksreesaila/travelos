// The sky (F-206): one sky function shared by the dome, the lake's reflections and the haze that fills distance, so water meets sky with no line and far
// ridges fade into the colour the sky has behind them (Meng To's 3d-sky-background and threejs-landscape, MIT). One sun direction drives the disc, the
// glow, the light and the rays. The rays are crepuscular rays drawn into the sky itself, fanning from a low sun behind the ridges (3d-sky-rays' look
// without its full-screen pass, which a phone cannot spare). Times of day are full states mixed continuously, never switched.
import { Mesh, SphereGeometry, ShaderMaterial, BackSide, Vector3, Color, Points, BufferGeometry, Float32BufferAttribute, AdditiveBlending } from 'three';
import { mulberry32, lerp, TAU } from './core.js';

// toward the sun from azimuth (degrees from north, clockwise) and elevation; world x is east and z is south
export const sunDir = (az, el) => { const a = (az * Math.PI) / 180, e = (el * Math.PI) / 180; return [Math.sin(a) * Math.cos(e), Math.sin(e), -Math.cos(a) * Math.cos(e)]; };

export const SKY_GLSL = /* glsl */ `
uniform vec3 uZen, uMid, uHor, uHaze, uSunDir, uSunCol, uMoonDir;
uniform float uGlow, uSunDisc, uMoon, uRays, uHazeDensity, uHazeHeight, uCirrus;
uniform sampler2D uNoise;
vec3 skyColor(vec3 d) {
  float h = d.y;
  vec3 c = mix(uHor, uMid, smoothstep(-0.02, 0.2, h));
  c = mix(c, uZen, smoothstep(0.16, 0.8, h));
  c = mix(c, uHaze, smoothstep(0.0, -0.12, h));
  float g = max(dot(d, uSunDir), 0.0);
  float low = 1.0 - smoothstep(0.02, 0.32, uSunDir.y);                 // how low the sun is: golden hour and dusk
  c += uSunCol * (pow(g, 5.0) * 0.20 + pow(g, 42.0) * 0.32 + pow(g, 600.0) * 0.9) * uGlow;
  c += uSunCol * pow(g, 1.6) * (1.0 - smoothstep(0.0, 0.32, abs(h))) * (0.10 + 0.32 * low) * uGlow;
  // crepuscular rays: bright and dark spokes round a low sun, close to it and just above the horizon
  if (uRays > 0.001) {
    vec3 t = normalize(cross(uSunDir, vec3(0.0, 1.0, 0.0)));
    vec3 b = cross(t, uSunDir);
    float ang = atan(dot(d, b), dot(d, t));
    float spokes = smoothstep(0.4, 0.7, texture2D(uNoise, vec2(ang * 0.31831 * 3.0, 0.37)).g) * 0.7 + smoothstep(0.45, 0.62, texture2D(uNoise, vec2(ang * 0.31831 * 9.0, 0.81)).b) * 0.3;
    float near = pow(g, 14.0) * smoothstep(-0.01, 0.04, h) * (1.0 - smoothstep(0.04, 0.32, h)) * low;
    c += uSunCol * (spokes - 0.3) * near * 0.35 * uRays;
  }
  // a few high winter cirrus, very faint, lit by the sun
  if (uCirrus > 0.001 && h > 0.02) {
    vec2 p = d.xz / (h + 0.08) * 0.11;
    float n = texture2D(uNoise, p).r * 0.6 + texture2D(uNoise, p * 3.1 + 0.3).g * 0.4;
    float cl = smoothstep(0.56, 0.78, n) * smoothstep(0.02, 0.2, h) * (1.0 - smoothstep(0.5, 0.95, h));
    c = mix(c, mix(vec3(1.0), uSunCol, 0.35 + 0.4 * low) * (0.85 + 0.5 * pow(g, 4.0)), cl * 0.22 * uCirrus);
  }
  float mg = max(dot(d, uMoonDir), 0.0);
  c += vec3(0.55, 0.62, 0.8) * (pow(mg, 24.0) * 0.16 + pow(mg, 300.0) * 0.3) * uMoon;
  return c;
}
// distance fills with the colour of the sky behind it: height-thinned exponential haze integrated along the ray
vec3 hazed(vec3 col, vec3 wp, vec3 cam) {
  vec3 v = wp - cam; float d = length(v);
  float k = 1.0 / uHazeHeight, h0 = max(cam.y, -50.0), h1 = max(wp.y, -50.0);
  float dens = abs(h1 - h0) > 1.0 ? (exp(-h0 * k) - exp(-h1 * k)) / ((h1 - h0) * k) : exp(-h0 * k);
  float f = 1.0 - exp(-d * uHazeDensity * dens);
  vec3 dir = v / max(d, 1e-3);
  vec3 hz = skyColor(vec3(dir.x, max(dir.y, 0.0) * 0.35, dir.z));
  return mix(col, hz, clamp(f, 0.0, 1.0));
}`;

export function skyUniforms(noise) {
  return {
    uZen: { value: new Color() }, uMid: { value: new Color() }, uHor: { value: new Color() }, uHaze: { value: new Color() },
    uSunDir: { value: new Vector3(0, 1, 0) }, uSunCol: { value: new Color(1, 1, 1) }, uMoonDir: { value: new Vector3(0, 0.5, -1).normalize() },
    uGlow: { value: 1 }, uSunDisc: { value: 1 }, uMoon: { value: 0 }, uRays: { value: 0 }, uCirrus: { value: 1 },
    uHazeDensity: { value: 1 / 120000 }, uHazeHeight: { value: 2600 }, uNoise: { value: noise },
    uBgOut: { value: new Vector3(0.949, 0.949, 0.961) }, uSkyAmt: { value: 1 },        // the page's grey (or black), in output colour: the book sits on exactly the canvas
  };
}

export function buildSky(U) {
  const mat = new ShaderMaterial({
    uniforms: U, side: BackSide, depthWrite: false, depthTest: false, fog: false,
    vertexShader: 'varying vec3 vD; void main(){ vD = position; vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_Position = p.xyww; }',
    fragmentShader: SKY_GLSL + /* glsl */ `
      uniform vec3 uBgOut; uniform float uSkyAmt; varying vec3 vD;
      void main(){
        vec3 d = normalize(vD); vec3 c = skyColor(d);
        float g = dot(d, uSunDir);
        c = mix(c, uSunCol * 1.4 + 0.35, smoothstep(0.99962, 0.9998, g) * uSunDisc);
        float mg = dot(d, uMoonDir);
        float disc = smoothstep(0.99948, 0.99962, mg);
        vec3 mn = normalize(d - uMoonDir * mg);
        float maria = texture2D(uNoise, mn.xz * 6.0 + 0.4).r;
        vec3 mc = vec3(0.92, 0.94, 0.99) * (0.86 + 0.14 * smoothstep(0.3, 0.7, maria));
        c = mix(c, mc, disc * uMoon);
        gl_FragColor = vec4(c, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
        gl_FragColor.rgb = mix(uBgOut, gl_FragColor.rgb, uSkyAmt);
      }`,
  });
  const mesh = new Mesh(new SphereGeometry(1000, 48, 24), mat);
  mesh.renderOrder = -10; mesh.frustumCulled = false;
  return mesh;
}

// Stars: confined to the band above the horizon the camera can see, three size classes scaled by the pixel ratio (threejs-landscape), with the
// winter Milky Way as a faint denser band. Drawn on the sky's sphere, so they stay at infinity.
export function buildStars(count, dpr) {
  const rnd = mulberry32(2026), n = count, pos = new Float32Array(n * 3), col = new Float32Array(n * 3), size = new Float32Array(n);
  const band = new Vector3(0.35, 0.55, -0.76).normalize();
  for (let i = 0; i < n; i++) {
    let v;
    do {
      const th = rnd() * TAU, u = -0.04 + Math.pow(rnd(), 0.75) * 1.0, s = Math.sqrt(Math.max(0, 1 - u * u));
      v = new Vector3(Math.cos(th) * s, u, Math.sin(th) * s);
    } while (Math.abs(v.dot(band)) > 0.35 && rnd() < 0.55);                 // thinner away from the Milky Way
    pos.set([v.x * 950, v.y * 950, v.z * 950], i * 3);
    const w = rnd(), b = 0.45 + Math.pow(rnd(), 1.8) * 0.55, c = w > 0.9 ? [1, 0.86, 0.7] : w < 0.14 ? [0.74, 0.84, 1] : [0.97, 0.97, 0.95];
    col.set([c[0] * b, c[1] * b, c[2] * b], i * 3);
    const r = rnd(); size[i] = (r < 0.72 ? 1.5 : r < 0.95 ? 2.4 : 3.8) * dpr;
  }
  const g = new BufferGeometry();
  g.setAttribute('position', new Float32BufferAttribute(pos, 3)); g.setAttribute('color', new Float32BufferAttribute(col, 3)); g.setAttribute('aSize', new Float32BufferAttribute(size, 1));
  const U = { uOpacity: { value: 0 }, uTime: { value: 0 } };
  const mat = new ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false, depthTest: false, blending: AdditiveBlending,
    vertexShader: 'attribute float aSize; attribute vec3 color; varying vec3 vC; varying float vT; uniform float uTime; void main(){ vC = color; vT = fract(sin(dot(position.xy, vec2(12.9898, 78.233))) * 43758.5453); vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_Position = p.xyww; gl_PointSize = aSize * (0.85 + 0.15 * sin(uTime * (1.0 + vT * 2.0) + vT * 40.0)); }',
    fragmentShader: 'uniform float uOpacity; varying vec3 vC; varying float vT; void main(){ vec2 q = gl_PointCoord - 0.5; float a = smoothstep(0.5, 0.0, length(q)); gl_FragColor = vec4(vC * a * uOpacity, 1.0); }',
  });
  const p = new Points(g, mat); p.renderOrder = -9; p.frustumCulled = false;
  p.userData = { U, set: (o) => { U.uOpacity.value = o; p.visible = o > 0.01; } };
  return p;
}

// Times of day for Lake Tahoe in December: the low winter sun at about 22 degrees in the early afternoon, golden hour and the sunset in the west-southwest
// (just left of Mt Tallac from the pier), a moonlit night, and the late evening the night scene's Go chapter moves into.
export const STATES = {
  day: { zen: 0x1a5bb8, mid: 0x5592d8, hor: 0xb6cde8, haze: 0xc8d7e8, sun: sunDir(218, 22), sunCol: 0xfff0dc, sunI: 3.2, glow: 0.75, disc: 1, rays: 0, cirrus: 0.9,
    hemiSky: 0xb9d1f4, hemiGround: 0xd9e1eb, hemiI: 1.0, deep: 0x0b2f6e, shallow: 0x1f9fb2, spec: 1, stars: 0, moon: 0, moonDir: sunDir(120, 20), night: 0, snow: 0xf4f7fb, haze_d: 1 / 120000 },
  golden: { zen: 0x23458f, mid: 0x8a7fbf, hor: 0xff9a5c, haze: 0xeab08e, sun: sunDir(236, 1.6), sunCol: 0xffa05a, sunI: 2.4, glow: 1.5, disc: 1, rays: 1, cirrus: 1,
    hemiSky: 0x8793cf, hemiGround: 0xd9b7a6, hemiI: 0.8, deep: 0x142c66, shallow: 0x37799a, spec: 1.35, stars: 0.04, moon: 0, moonDir: sunDir(100, 12), night: 0.1, snow: 0xfbe6d8, haze_d: 1 / 70000 },
  night: { zen: 0x030919, mid: 0x0a1633, hor: 0x1a2a4d, haze: 0x13203f, sun: sunDir(150, 38), sunCol: 0xaabdff, sunI: 0.95, glow: 0.12, disc: 0, rays: 0, cirrus: 0.25,
    hemiSky: 0x3d528c, hemiGround: 0x2a3552, hemiI: 0.9, deep: 0x020a1e, shallow: 0x0b2d44, spec: 0.6, stars: 1, moon: 1, moonDir: sunDir(150, 38), night: 1, snow: 0xd9e3f4, haze_d: 1 / 90000 },
  late: { zen: 0x020715, mid: 0x08122c, hor: 0x203357, haze: 0x162847, sun: sunDir(250, 6), sunCol: 0xb6c6ff, sunI: 0.9, glow: 0.4, disc: 0, rays: 0, cirrus: 0.2,
    hemiSky: 0x3d528c, hemiGround: 0x2a3552, hemiI: 0.82, deep: 0x020a1e, shallow: 0x0b2d44, spec: 0.95, stars: 1, moon: 1, moonDir: sunDir(250, 6), night: 1, snow: 0xd9e3f4, haze_d: 1 / 80000 },
};
const NUM = ['sunI', 'glow', 'disc', 'rays', 'cirrus', 'hemiI', 'spec', 'stars', 'moon', 'night', 'haze_d'];
const COL = ['zen', 'mid', 'hor', 'haze', 'sunCol', 'hemiSky', 'hemiGround', 'deep', 'shallow', 'snow'];
const VEC = ['sun', 'moonDir'];
const _a = new Color(), _b = new Color(), _v = new Vector3();
export function mixState(A, B, t, out = {}) {
  for (const k of NUM) out[k] = lerp(A[k], B[k], t);
  for (const k of COL) out[k] = _a.set(A[k]).lerp(_b.set(B[k]), t).getHex();
  for (const k of VEC) { const a = A[k], b = B[k]; _v.set(lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)).normalize(); out[k] = [_v.x, _v.y, _v.z]; }
  return out;
}

export function applySky(U, st) {
  U.uZen.value.set(st.zen); U.uMid.value.set(st.mid); U.uHor.value.set(st.hor); U.uHaze.value.set(st.haze);
  U.uSunDir.value.set(...st.sun); U.uSunCol.value.set(st.sunCol); U.uMoonDir.value.set(...st.moonDir);
  U.uGlow.value = st.glow; U.uSunDisc.value = st.disc; U.uMoon.value = st.moon; U.uRays.value = st.rays; U.uCirrus.value = st.cirrus; U.uHazeDensity.value = st.haze_d;
}
