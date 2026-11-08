// The Tahoe world: terrain (which starts life as the printed map on a guidebook page and rises into
// mountains), the lake, the sky, pines, the cabin and pier, the town, Heavenly's runs and gondola, roads,
// and the atmosphere states (day, golden hour, night, late night, and the four seasons for concept B).
import {
  BufferGeometry, Float32BufferAttribute, BufferAttribute, InstancedBufferAttribute, Mesh, InstancedMesh, Points, Group, Color,
  MeshLambertMaterial, MeshBasicMaterial, ShaderMaterial, PointsMaterial, CanvasTexture, SRGBColorSpace,
  BoxGeometry, ConeGeometry, CylinderGeometry, SphereGeometry, IcosahedronGeometry, PlaneGeometry, CircleGeometry,
  Matrix4, Vector3, Quaternion, Euler, CatmullRomCurve3, Line, LineBasicMaterial, BackSide, DoubleSide, AdditiveBlending,
  HemisphereLight, DirectionalLight, Fog,
} from 'three';
import { Kit, M, mulberry32, fbm, smooth, clamp, lerp, srgb, TAU } from './core.js';
import { landH, landN, waterSD, forest, P, ROAD_LOOP, ROAD_RENO, ROAD_SPOONER, ROAD_HOPE, LAKE } from './geo.js';

export const PAGE = { x0: -60, z0: -80, x1: 60, z1: 80 }; // the map page of the guidebook, in world units

/* ------------------------------------------------------------------ terrain */
function terrainGeometry(N) {
  // a foveated grid: dense around the south shore where the camera comes close, sparse at the rim
  const cx = 2, cz = 18, R = 172, a = 0.46;
  const warp = (u) => R * (a * u + (1 - a) * u * Math.abs(u));
  const n = N + 1, pos = new Float32Array(n * n * 3), col = new Float32Array(n * n * 3), snow = new Float32Array(n * n), fo = new Float32Array(n * n);
  const c = new Color();
  const ROCK = new Color(0x6d6a66), GRANITE = new Color(0xa29d92), FOREST = new Color(0x617047), MEADOW = new Color(0x97a95c), SAND = new Color(0xd8cba6), DIRT = new Color(0x7d6a52), SHORE = new Color(0x56524c);
  let k = 0;
  for (let j = 0; j < n; j++) for (let i = 0; i < n; i++, k++) {
    const x = cx + warp((i / N) * 2 - 1), z = cz + warp((j / N) * 2 - 1);
    const h = landH(x, z), nn = landN(x, z), slope = 1 - nn[1];
    pos[k * 3] = x; pos[k * 3 + 1] = h; pos[k * 3 + 2] = z;
    // summer albedo from what the ground is doing (slope, height, moisture), never a texture
    const t = fbm(x * 0.06, z * 0.06, 2) * 0.5 + 0.5;
    c.copy(FOREST).lerp(MEADOW, smooth(0.6, 1, t) * (1 - smooth(4, 14, h)) * 0.6);
    c.lerp(DIRT, smooth(0.25, 0.45, slope) * 0.6);
    c.lerp(GRANITE, smooth(0.38, 0.62, slope));
    c.lerp(ROCK, smooth(0.62, 0.85, slope) * 0.7);
    c.lerp(GRANITE, smooth(24, 34, h) * 0.8);
    c.lerp(SAND, (1 - smooth(0.15, 0.9, h)) * 0.85);
    c.lerp(SHORE, (1 - smooth(-0.15, 0.25, h)) * 0.8);
    col[k * 3] = c.r; col[k * 3 + 1] = c.g; col[k * 3 + 2] = c.b;
    // how readily snow sits here: higher and flatter holds it, cliffs shed it
    snow[k] = clamp(0.32 + h / 44 - slope * 1.05 + (t - 0.5) * 0.22, 0, 1) * smooth(-0.1, 0.25, h);
    fo[k] = forest(x, z);
  }
  const idx = new (n * n > 65535 ? Uint32Array : Uint16Array)(N * N * 6);
  let q = 0;
  for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
    const a0 = j * n + i, b0 = a0 + 1, a1 = a0 + n, b1 = a1 + 1;
    idx[q++] = a0; idx[q++] = a1; idx[q++] = b0; idx[q++] = b0; idx[q++] = a1; idx[q++] = b1;
  }
  const g = new BufferGeometry();
  g.setAttribute('position', new BufferAttribute(pos, 3));
  g.setAttribute('color', new BufferAttribute(col, 3));
  g.setAttribute('aSnow', new BufferAttribute(snow, 1));
  g.setAttribute('aForest', new BufferAttribute(fo, 1));
  g.setIndex(new BufferAttribute(idx, 1));
  g.computeVertexNormals();
  return g;
}

function labelCanvas(dark) {
  // the printed labels and roads of the guidebook's map page (text only; the paper, contours and lake are the shader)
  const W = 900, H = 1200, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const x = cv.getContext('2d');
  const toPx = (wx, wz) => [((wx - PAGE.x0) / (PAGE.x1 - PAGE.x0)) * W, ((wz - PAGE.z0) / (PAGE.z1 - PAGE.z0)) * H];
  const road = (pts, w) => {
    x.beginPath(); pts.forEach(([a, b], i) => { const [px, py] = toPx(a, b); i ? x.lineTo(px, py) : x.moveTo(px, py); });
    x.strokeStyle = dark ? 'rgba(170,60,40,.75)' : 'rgba(196,58,36,.85)'; x.lineWidth = w; x.setLineDash([10, 7]); x.stroke(); x.setLineDash([]);
  };
  road(ROAD_LOOP, 3); road(ROAD_RENO, 3);
  const ink = dark ? '#3b3228' : '#2c3440', blue = dark ? '#2f4f7a' : '#2b5c99';
  const label = (t, wx, wz, size, color, style = '') => { const [px, py] = toPx(wx, wz); x.font = `${style} ${size}px Georgia, 'Times New Roman', serif`; x.fillStyle = color; x.textAlign = 'center'; x.fillText(t, px, py); };
  label('Lake', 0, -12, 52, blue, 'italic'); label('Tahoe', 0, -1, 52, blue, 'italic');
  label('Emerald Bay', -27, 25.5, 22, blue, 'italic');
  label('South Lake Tahoe', 6, 60, 22, ink); label('Stateline', 41, 44, 20, ink); label('Heavenly', 50, 78, 22, ink, 'bold');
  label('Tahoe City', -36, -50, 22, ink); label('Sand Harbor', 44, -6, 20, ink); label('Spooner', 49, 16, 20, ink);
  label('DESOLATION', -48, 18, 20, ink, 'bold'); label('WILDERNESS', -48, 23, 20, ink, 'bold');
  // title strip, north arrow, scale bar, page number
  x.font = "bold 30px Georgia, serif"; x.fillStyle = ink; x.textAlign = 'left'; x.fillText('Lake Tahoe & around', 46, 70);
  x.font = "20px Georgia, serif"; x.fillText('Map 12 · Winter roads and ski areas', 46, 100);
  x.beginPath(); x.moveTo(820, 150); x.lineTo(806, 190); x.lineTo(820, 182); x.lineTo(834, 190); x.closePath(); x.fillStyle = ink; x.fill();
  x.font = "bold 22px Georgia, serif"; x.textAlign = 'center'; x.fillText('N', 820, 140);
  x.fillRect(46, 1130, 120, 5); x.font = "18px Georgia, serif"; x.textAlign = 'left'; x.fillText('5 miles', 46, 1160);
  x.textAlign = 'right'; x.fillText('215', 860, 1160);
  const t = new CanvasTexture(cv); t.colorSpace = SRGBColorSpace; t.anisotropy = 4;
  return t;
}

export function buildTerrain(quality) {
  const g = terrainGeometry(quality.terrain);
  const mat = new MeshLambertMaterial({ vertexColors: true });
  const U = {
    uRise: { value: 1 }, uLit: { value: 1 }, uGrowR: { value: 999 }, uPage: { value: new Vector3() }, uPage2: { value: new Vector3() },
    uSnowLine: { value: 0.12 }, uSnowColor: { value: new Color(0xf3f6fa) },
    uPaper: { value: new Color(0xf7f2e8) }, uPrintLine: { value: new Color(0xb8a98f) }, uPrintWater: { value: new Color(0x9cc3ea) }, uPrintShore: { value: new Color(0x3d6ea8) },
    uLabels: { value: labelCanvas(false) }, uLamp: { value: 0 },
  };
  U.uPage.value.set(PAGE.x0, PAGE.z0, 0); U.uPage2.value.set(PAGE.x1, PAGE.z1, 0);
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = 'uniform float uRise; attribute float aSnow; attribute float aForest; varying float vSnow; varying float vForest; varying vec3 vW;\n' + sh.vertexShader
      .replace('#include <begin_vertex>', 'vec3 transformed = vec3(position.x, position.y * uRise, position.z); vSnow = aSnow; vForest = aForest; vW = position;');
    sh.fragmentShader = `uniform float uLit, uGrowR, uSnowLine, uLamp; uniform vec3 uPage, uPage2, uSnowColor, uPaper, uPrintLine, uPrintWater, uPrintShore; uniform sampler2D uLabels; varying float vSnow; varying float vForest; varying vec3 vW;\n` + sh.fragmentShader
      .replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
        vec2 qo = max(uPage.xy - vW.xz, vW.xz - uPage2.xy); if (max(qo.x, qo.y) > uGrowR) discard;`)
      .replace('#include <color_fragment>', `#include <color_fragment>
        float snowAmt = smoothstep(uSnowLine - 0.06, uSnowLine + 0.06, vSnow);
        // snow lying under the pines reads darker and bluer, so a forest looks like a forest from the air
        vec3 snowC = uSnowColor * mix(vec3(1.0), vec3(0.62, 0.68, 0.72), vForest * 0.85);
        diffuseColor.rgb = mix(diffuseColor.rgb, snowC, snowAmt);`)
      .replace('#include <opaque_fragment>', `#include <opaque_fragment>
        if (uLit < 0.999) {
          float h = vW.y, fw = max(fwidth(h), 1e-4);
          float minor = 1.0 - smoothstep(0.0, fw * 1.25, abs(fract(h / 3.0 + 0.5) - 0.5) * 3.0);
          float major = 1.0 - smoothstep(0.0, fw * 1.8, abs(fract(h / 15.0 + 0.5) - 0.5) * 15.0);
          vec3 pc = mix(uPaper, uPrintLine, (minor * 0.5 + major * 0.4) * step(0.15, h));
          pc = mix(pc, uPrintWater, 1.0 - smoothstep(-0.06, 0.06, h));
          pc = mix(pc, uPrintShore, 1.0 - smoothstep(0.0, fw * 1.6, abs(h - 0.02)));
          vec2 puv = (vW.xz - uPage.xy) / (uPage2.xy - uPage.xy);
          vec4 lab = texture2D(uLabels, vec2(puv.x, 1.0 - puv.y));
          pc = mix(pc, lab.rgb, lab.a);
          // a reading lamp in dark mode: warm in the middle of the spread, falling off to the corners
          float lamp = 1.0 - smoothstep(30.0, 150.0, length(vW.xz - vec2(-40.0, 4.0)));
          pc *= mix(1.0, 0.42 + 0.62 * lamp, uLamp);
          gl_FragColor.rgb = mix(pc, gl_FragColor.rgb, uLit);
        }`);
  };
  mat.customProgramCacheKey = () => 'cover-terrain';
  const mesh = new Mesh(g, mat);
  mesh.userData.U = U;
  mesh.userData.setDark = (dark) => {
    U.uLabels.value.dispose(); U.uLabels.value = labelCanvas(dark);
    U.uPaper.value.set(dark ? 0xe6dcc6 : 0xf7f2e8); U.uLamp.value = dark ? 1 : 0;
  };
  return mesh;
}

/* ------------------------------------------------------------------ sky */
// One sky function in GLSL, shared by the dome and the lake's reflections and haze, so the water meets the
// sky without a line (Meng To's water rule: "fog into the same haze function the sky draws").
export const SKY_GLSL = `
uniform vec3 uZen, uMid, uHor, uHaze, uSunDir, uSunCol, uMoonDir; uniform float uGlow, uSunDisc, uMoon;
vec3 skyColor(vec3 d) {
  float h = d.y;
  vec3 c = mix(uHor, uMid, smoothstep(0.0, 0.22, h));
  c = mix(c, uZen, smoothstep(0.18, 0.75, h));
  c = mix(c, uHaze, smoothstep(0.0, -0.18, h));
  float g = max(dot(d, uSunDir), 0.0);
  c += uSunCol * (pow(g, 6.0) * 0.22 + pow(g, 48.0) * 0.35) * uGlow;
  // the horizon glows toward the sun at golden hour
  c += uSunCol * pow(g, 2.0) * (1.0 - smoothstep(0.0, 0.35, abs(h))) * 0.25 * uGlow;
  float mg = max(dot(d, uMoonDir), 0.0);
  c += vec3(0.55, 0.62, 0.8) * pow(mg, 24.0) * 0.18 * uMoon;
  return c;
}`;

export function skyUniforms() {
  return {
    uZen: { value: srgb(0x3f7fd0) }, uMid: { value: srgb(0x7faee6) }, uHor: { value: srgb(0xd6e5f4) }, uHaze: { value: srgb(0xe6eef6) },
    uSunDir: { value: new Vector3(-0.55, 0.42, 0.72).normalize() }, uSunCol: { value: srgb(0xfff3e2) }, uMoonDir: { value: new Vector3(0, 0.5, -1).normalize() },
    uGlow: { value: 1 }, uSunDisc: { value: 1 }, uMoon: { value: 0 }, uBg: { value: srgb(0xf2f2f5) }, uSkyAmt: { value: 1 },
  };
}
export function buildSky(U) {
  const mat = new ShaderMaterial({
    uniforms: U, side: BackSide, depthWrite: false, depthTest: false, fog: false,
    vertexShader: 'varying vec3 vD; void main(){ vD = position; vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_Position = p.xyww; }',
    fragmentShader: SKY_GLSL + `
      uniform vec3 uBg; uniform float uSkyAmt; varying vec3 vD;
      void main(){
        vec3 d = normalize(vD); vec3 c = skyColor(d);
        float g = max(dot(d, uSunDir), 0.0);
        c = mix(c, vec3(1.0, 0.98, 0.94), smoothstep(0.99955, 0.99975, g) * uSunDisc);
        // the moon: a disc with soft maria
        float mg = dot(d, uMoonDir);
        float disc = smoothstep(0.99935, 0.99955, mg);
        vec3 mc = vec3(0.93, 0.95, 1.0) - 0.08 * smoothstep(0.9996, 0.99985, dot(normalize(d + vec3(0.004, 0.002, 0.0)), uMoonDir));
        c = mix(c, mc, disc * uMoon);
        gl_FragColor = vec4(mix(uBg, c, uSkyAmt), 1.0);
      }`,
  });
  const mesh = new Mesh(new SphereGeometry(500, 32, 18), mat);
  mesh.renderOrder = -10; mesh.frustumCulled = false;
  mesh.userData.U = U;
  return mesh;
}

export function buildStars(count) {
  // confined to the band the camera can see, three size classes (threejs-landscape)
  const group = new Group(), rnd = mulberry32(2026), mats = [];
  const cv = document.createElement('canvas'); cv.width = cv.height = 64; const x = cv.getContext('2d');
  const gr = x.createRadialGradient(32, 32, 0, 32, 32, 32); gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.3, 'rgba(255,255,255,.8)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = gr; x.fillRect(0, 0, 64, 64);
  const tex = new CanvasTexture(cv);
  const dpr = Math.min(devicePixelRatio || 1, 2);
  [[count * 0.72, 1.6 * dpr], [count * 0.22, 2.6 * dpr], [count * 0.06, 4.2 * dpr]].forEach(([n, px]) => {
    n = Math.round(n); const pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const th = rnd() * TAU, u = -0.02 + Math.pow(rnd(), 0.8) * 0.98, s = Math.sqrt(1 - u * u), R = 460;
      pos[i * 3] = Math.cos(th) * s * R; pos[i * 3 + 1] = u * R; pos[i * 3 + 2] = Math.sin(th) * s * R;
      const w = rnd(), b = 0.5 + Math.pow(rnd(), 1.7) * 0.5, cc = w > 0.88 ? [1, 0.88, 0.72] : w < 0.15 ? [0.75, 0.85, 1] : [0.97, 0.97, 0.95];
      col[i * 3] = cc[0] * b; col[i * 3 + 1] = cc[1] * b; col[i * 3 + 2] = cc[2] * b;
    }
    const g = new BufferGeometry(); g.setAttribute('position', new Float32BufferAttribute(pos, 3)); g.setAttribute('color', new Float32BufferAttribute(col, 3));
    const m = new PointsMaterial({ size: px, map: tex, vertexColors: true, transparent: true, opacity: 0, depthWrite: false, depthTest: false, fog: false, sizeAttenuation: false, blending: AdditiveBlending });
    const p = new Points(g, m); p.renderOrder = -9; p.frustumCulled = false; group.add(p); mats.push(m);
  });
  group.userData.set = (o) => mats.forEach((m) => { m.opacity = o; m.visible = o > 0.01; });
  return group;
}

/* ------------------------------------------------------------------ lake */
export function buildWater(quality, SKYU) {
  // a grid over the basin carrying the lake depth, shaded per pixel: ripples from a small sum of waves faded at
  // their own pixel footprint, Schlick Fresnel against the shared sky, a sun or moon glitter path, and haze into
  // the same horizon colour (adapted from Meng To's 3d-ultra-realistic-water, MIT)
  const x0 = -36, x1 = 36, z0 = -57, z1 = 50, step = quality.waterStep;
  const nx = Math.ceil((x1 - x0) / step), nz = Math.ceil((z1 - z0) / step);
  const pos = [], dep = [], idx = [];
  for (let j = 0; j <= nz; j++) for (let i = 0; i <= nx; i++) {
    const x = x0 + i * step, z = z0 + j * step; pos.push(x, 0, z); dep.push(Math.max(0, -landH(x, z)));
  }
  for (let j = 0; j < nz; j++) for (let i = 0; i < nx; i++) {
    const a = j * (nx + 1) + i, b = a + 1, c = a + nx + 1, d = c + 1;
    if (dep[a] + dep[b] + dep[c] + dep[d] <= 0) continue; // all four corners on land: the ground hides it anyway
    idx.push(a, c, b, b, c, d);
  }
  const g = new BufferGeometry();
  g.setAttribute('position', new Float32BufferAttribute(pos, 3)); g.setAttribute('aDepth', new Float32BufferAttribute(dep, 1)); g.setIndex(idx);
  const U = {
    uTime: { value: 0 }, uDeep: { value: srgb(0x0e3f96) }, uShallow: { value: srgb(0x2fa7c0) }, uLightDir: { value: new Vector3(-0.55, 0.42, 0.72).normalize() },
    uLightCol: { value: srgb(0xfff3e2) }, uSpec: { value: 1 }, uFogNear: { value: 60 }, uFogFar: { value: 420 }, uRise: { value: 1 }, uPrint: { value: srgb(0x9cc3ea) },
  };
  const mat = new ShaderMaterial({
    uniforms: { ...U, ...SKYU },
    vertexShader: 'attribute float aDepth; varying float vDepth; varying vec3 vW; void main(){ vDepth = aDepth; vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }',
    fragmentShader: SKY_GLSL + `
      uniform float uTime, uSpec, uFogNear, uFogFar, uRise; uniform vec3 uDeep, uShallow, uLightDir, uLightCol, uPrint; varying float vDepth; varying vec3 vW;
      vec2 wave(vec2 p, vec2 dir, float L, float A, float sp, float foot) {
        float fade = 1.0 - smoothstep(L * 0.18, L * 0.5, foot);
        float k = 6.2831853 / L, th = k * dot(dir, p) + uTime * sp * k;
        return dir * (A * k * cos(th) * fade);
      }
      void main(){
        vec2 p = vW.xz; float foot = 2.0 * (abs(dFdx(p.x)) + abs(dFdy(p.x)) + abs(dFdx(p.y)) + abs(dFdy(p.y)));
        // cat's paws: the wind roughens the lake in slow-moving patches
        float gust = 0.35 + 0.65 * smoothstep(-0.6, 0.9, sin(p.x * 0.07 + uTime * 0.05) * sin(p.y * 0.05 - uTime * 0.04) + 0.5 * sin((p.x + p.y) * 0.11 + 1.7));
        vec2 s = (wave(p, vec2(0.83, 0.55), 3.4, 0.022, 0.9, foot) + wave(p, vec2(-0.42, 0.91), 2.3, 0.016, 0.7, foot)
               + wave(p, vec2(0.97, -0.24), 1.45, 0.011, 0.55, foot) + wave(p, vec2(-0.71, -0.7), 0.9, 0.007, 0.45, foot)
               + wave(p, vec2(0.2, 0.98), 0.55, 0.004, 0.35, foot) + wave(p, vec2(-0.95, 0.3), 1.9, 0.01, 0.6, foot)
               + wave(p, vec2(0.6, -0.8), 0.7, 0.005, 0.4, foot)) * gust;
        vec3 N = normalize(vec3(-s.x, 1.0, -s.y));
        vec3 toC = cameraPosition - vW; float dist = length(toC); vec3 V = toC / dist;
        float F = 0.02 + 0.98 * pow(1.0 - max(dot(N, V), 0.0), 5.0);
        vec3 R = reflect(-V, N); R.y = abs(R.y) + 0.002;
        vec3 body = mix(uShallow, mix(uShallow, uDeep, 0.72), smoothstep(0.0, 1.8, vDepth));
        body = mix(body, uDeep * 0.86, smoothstep(3.0, 12.0, vDepth));
        vec3 col = mix(body, skyColor(R) * 0.92, F);
        float rl = max(dot(R, uLightDir), 0.0);
        col += uLightCol * (pow(rl, 90.0) * 0.9 + pow(rl, 900.0) * 3.0 + pow(rl, 12.0) * 0.03) * uSpec;
        // a pale rim of ice and wet stones at the shore
        col = mix(col, vec3(0.86, 0.92, 0.96) * (0.45 + 0.55 * uLightCol.g), (1.0 - smoothstep(0.02, 0.16, vDepth)) * 0.5);
        float fog = smoothstep(uFogNear, uFogFar, dist);
        col = mix(col, skyColor(normalize(vec3(-V.x, 0.0, -V.z))), fog);
        col = mix(uPrint, col, smoothstep(0.0, 0.6, uRise));
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
  const mesh = new Mesh(g, mat);
  mesh.userData.U = mat.uniforms;
  return mesh;
}

/* ------------------------------------------------------------------ trees */
// a pine: trunk and three stacked cones; the upper faces of each tier carry snow (aExtra), recoloured by uniform
function pineGeometry() {
  const k = new Kit().withExtra();
  k.add(new CylinderGeometry(0.07, 0.1, 0.7, 5), 0x5a4030, M(0, 0.35, 0), 0);
  const tiers = [[0.62, 0.95, 0.55], [0.48, 0.85, 1.05], [0.32, 0.75, 1.5]];
  tiers.forEach(([r, h, y], ti) => {
    k.addFn(new ConeGeometry(r, h, 7, 1), M(0, y + h / 2 - 0.1, 0, 0, ti * 0.5, 0), (c, px, py, pz, nx, ny) => {
      const top = (py - y) / h; // 0 at the skirt, 1 at the tip
      c.set(ti === 2 ? 0x2f5a3c : ti === 1 ? 0x2a5236 : 0x264a31);
      return ny > 0.2 ? smooth(0.05, 0.55, top + ny * 0.25) : 0.0;
    });
  });
  return k.geometry();
}
function aspenGeometry() {
  const k = new Kit().withExtra();
  k.add(new CylinderGeometry(0.05, 0.07, 1.3, 5), 0xe8e2d6, M(0, 0.65, 0), 0);
  k.add(new CylinderGeometry(0.02, 0.03, 0.5, 4), 0xd8d0c2, M(0.12, 1.05, 0, 0, 0, -0.7), 0);
  k.add(new CylinderGeometry(0.02, 0.03, 0.45, 4), 0xd8d0c2, M(-0.1, 1.15, 0.05, 0.3, 0, 0.7), 0);
  k.add(new IcosahedronGeometry(0.5, 0), 0xffffff, M(0, 1.55, 0, 0, 0, 0, 1, 1.15, 1), 1);
  k.add(new IcosahedronGeometry(0.34, 0), 0xffffff, M(0.22, 1.35, 0.1, 0.4, 0.3, 0), 1);
  return k.geometry();
}

export function scatter(n, seed, ok, bounds) {
  const out = [], rnd = mulberry32(seed); let guard = 0;
  while (out.length < n && guard++ < n * 40) {
    const x = lerp(bounds[0], bounds[2], rnd()), z = lerp(bounds[1], bounds[3], rnd());
    const r = ok(x, z, rnd); if (r) out.push([x, landH(x, z), z, rnd(), r]);
  }
  return out;
}
const segDist = (x, z, pts) => {
  let best = 1e9;
  for (let i = 0; i < pts.length - 1; i++) {
    const [ax, az] = pts[i], [bx, bz] = pts[i + 1], dx = bx - ax, dz = bz - az;
    const t = clamp(((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz), 0, 1);
    best = Math.min(best, Math.hypot(x - ax - dx * t, z - az - dz * t));
  }
  return best;
};
export const RUNS = [
  [[52, 80], [47.5, 75], [42.5, 70], [37, 65]],
  [[54.5, 77.5], [51, 72], [45.5, 67.5], [39.5, 64]],
  [[49.5, 82.5], [44.5, 77.5], [40, 72], [35.5, 66.5]],
];
export const LIFT = [[35, 63.2], [52, 80.2]];

function treeMaterial(U, kind) {
  const mat = new MeshLambertMaterial({ vertexColors: true });
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = `uniform float uGrow; uniform float uLeaf; attribute float aExtra; attribute vec2 aSeed; varying float vExtra; varying float vTint;\n` + sh.vertexShader
      .replace('#include <begin_vertex>', `vec3 transformed = position;
        ${kind === 'aspen' ? 'if (aExtra > 0.5) transformed = mix(vec3(0.0, 1.5, 0.0), transformed, uLeaf);' : ''}
        float gs = smoothstep(aSeed.x * 0.55, aSeed.x * 0.55 + 0.45, uGrow);
        transformed *= gs; vExtra = aExtra; vTint = aSeed.y;`);
    sh.fragmentShader = `uniform vec3 uSnowColor, uLeafColor; uniform float uTreeSnow; varying float vExtra; varying float vTint;\n` + sh.fragmentShader
      .replace('#include <color_fragment>', `#include <color_fragment>
        ${kind === 'aspen'
          ? 'if (vExtra > 0.5) diffuseColor.rgb = uLeafColor * (0.82 + 0.36 * vTint); else diffuseColor.rgb = mix(diffuseColor.rgb, uSnowColor, uTreeSnow * 0.25);'
          : 'diffuseColor.rgb *= 0.84 + 0.32 * vTint; diffuseColor.rgb = mix(diffuseColor.rgb, uSnowColor, vExtra * uTreeSnow);'}`);
  };
  mat.customProgramCacheKey = () => 'cover-' + kind;
  return mat;
}

export function buildTrees(quality, U, opts = {}) {
  const roads = [ROAD_LOOP.filter((_, i) => i % 2 === 0), ROAD_RENO, ROAD_SPOONER, ROAD_HOPE];
  const ok = (x, z, rnd) => {
    const f = forest(x, z); if (rnd() > f) return 0;
    for (const r of roads) if (segDist(x, z, r) < 1.1) return 0;
    for (const r of RUNS) if (segDist(x, z, r) < 1.8) return 0;
    if (segDist(x, z, LIFT) < 1.0) return 0;
    if (Math.hypot(x - P.cabin[0], z - P.cabin[1]) < 3.0) return 0;
    if (Math.abs(x - P.pierStart[0]) < 1.5 && z < P.cabin[1] && z > P.pierEnd[1] - 1) return 0;
    if (Math.hypot(x - P.nextCabin[0], z - P.nextCabin[1]) < 2.4) return 0;
    if (Math.hypot(x - P.emerald[0], z - P.emerald[1]) < 1.4) return 0;
    if (Math.hypot(x - P.sledHill[0], z - P.sledHill[1]) < 3.4) return 0;
    if (opts.clear && opts.clear(x, z)) return 0;
    return 1;
  };
  const pts = scatter(quality.trees, 77, ok, [-150, -145, 155, 150]);
  // a few around the cabin, for the cozy foreground
  const [cx, cz] = P.cabin;
  [[-3.2, 1.6], [3.6, 2.4], [4.2, -1.2], [-4.4, -0.8], [-2.6, 4.6], [2.2, 5.2], [-6.5, 2.4]].forEach(([dx, dz]) => pts.push([cx + dx, landH(cx + dx, cz + dz), cz + dz, 0.5, 1]));
  const geo = pineGeometry();
  const mesh = new InstancedMesh(geo, treeMaterial(U, 'pine'), pts.length);
  const seeds = new Float32Array(pts.length * 2), m = new Matrix4(), q = new Quaternion(), e = new Euler(), v = new Vector3(), s = new Vector3();
  const r2 = mulberry32(5);
  pts.forEach(([x, y, z, r], i) => {
    const sc = (0.62 + r * 0.55) * (y > 12 ? 0.85 : 1);
    e.set(0, r2() * TAU, 0); q.setFromEuler(e); v.set(x, y - 0.05, z); s.set(sc * (0.85 + r2() * 0.3), sc * (0.9 + r2() * 0.35), sc * (0.85 + r2() * 0.3));
    m.compose(v, q, s); mesh.setMatrixAt(i, m);
    seeds[i * 2] = clamp(Math.hypot(x - 4, z - 30) / 150, 0, 1) * 0.6 + r2() * 0.4; seeds[i * 2 + 1] = r2();
  });
  geo.setAttribute('aSeed', new InstancedBufferAttribute(seeds, 2));
  mesh.frustumCulled = false;
  mesh.userData.points = pts;
  return mesh;
}

export function buildAspens(quality, U, groves) {
  const pts = [];
  const rnd = mulberry32(31);
  for (const [gx, gz, r, n] of groves) for (let i = 0; i < n; i++) {
    const a = rnd() * TAU, d = Math.sqrt(rnd()) * r, x = gx + Math.cos(a) * d, z = gz + Math.sin(a) * d, h = landH(x, z);
    if (h < 0.5 || landN(x, z)[1] < 0.8) continue;
    pts.push([x, h, z]);
  }
  const geo = aspenGeometry();
  const mesh = new InstancedMesh(geo, treeMaterial(U, 'aspen'), pts.length);
  const seeds = new Float32Array(pts.length * 2), m = new Matrix4(), q = new Quaternion(), e = new Euler(), v = new Vector3(), s = new Vector3();
  pts.forEach(([x, y, z], i) => { const sc = 0.9 + rnd() * 0.7; e.set(0, rnd() * TAU, 0); q.setFromEuler(e); v.set(x, y - 0.05, z); s.setScalar(sc); m.compose(v, q, s); mesh.setMatrixAt(i, m); seeds[i * 2] = rnd(); seeds[i * 2 + 1] = rnd(); });
  geo.setAttribute('aSeed', new InstancedBufferAttribute(seeds, 2));
  mesh.frustumCulled = false;
  return mesh;
}

/* ------------------------------------------------------------------ props */
const lambert = (o = {}) => new MeshLambertMaterial({ vertexColors: true, ...o });

export function buildCabin(scale = 1, wall = 0x7a4a2a) {
  const g = new Group(), k = new Kit(), win = new Kit();
  // log walls, an A-frame roof heavy with snow, a stone chimney, a deck facing the lake
  k.add(new BoxGeometry(1.7, 0.85, 1.25), wall, M(0, 0.43, 0));
  for (let i = 0; i < 5; i++) k.add(new BoxGeometry(1.74, 0.05, 1.29), 0x5e3820, M(0, 0.12 + i * 0.17, 0));
  const roof = (side) => {
    k.add(new BoxGeometry(1.95, 0.08, 0.98), 0x3d2a1e, M(0, 1.12, side * 0.36, side * -0.83, 0, 0));
    k.add(new BoxGeometry(1.98, 0.12, 0.96), 0xf4f7fb, M(0, 1.19, side * 0.4, side * -0.83, 0, 0));
  };
  roof(1); roof(-1);
  // gable ends
  const gable = new BufferGeometry(); gable.setAttribute('position', new Float32BufferAttribute([-0.85, 0.85, 0, 0.85, 0.85, 0, 0, 1.5, 0], 3));
  k.add(gable, wall, M(0, 0, 0.62)); k.add(gable, wall, M(0, 0, -0.62, 0, Math.PI, 0));
  k.add(new BoxGeometry(0.26, 0.9, 0.26), 0x8c8a86, M(0.55, 1.25, 0.1));
  k.add(new BoxGeometry(0.3, 0.07, 0.3), 0xf4f7fb, M(0.55, 1.72, 0.1));
  k.add(new BoxGeometry(1.9, 0.08, 0.7), 0x8a5a36, M(0, 0.06, -0.95));
  k.add(new BoxGeometry(1.9, 0.04, 0.7), 0xf0f4f8, M(0, 0.12, -0.95));
  for (const x of [-0.9, 0.9]) k.add(new BoxGeometry(0.05, 0.32, 0.7), 0x6a4226, M(x, 0.25, -0.95));
  k.add(new BoxGeometry(0.34, 0.55, 0.04), 0x4a2e1c, M(-0.42, 0.28, -0.64));
  // windows: their own mesh so they can glow at night
  win.add(new PlaneGeometry(0.34, 0.3), 0xffffff, M(0.25, 0.48, -0.632, 0, Math.PI, 0));
  win.add(new PlaneGeometry(0.3, 0.3), 0xffffff, M(0.62, 0.48, -0.632, 0, Math.PI, 0));
  win.add(new PlaneGeometry(0.36, 0.4), 0xffffff, M(0, 1.02, -0.64, 0, Math.PI, 0));
  win.add(new PlaneGeometry(0.3, 0.28), 0xffffff, M(-0.86, 0.48, 0.2, 0, -Math.PI / 2, 0));
  win.add(new PlaneGeometry(0.3, 0.28), 0xffffff, M(0.86, 0.48, -0.2, 0, Math.PI / 2, 0));
  const body = new Mesh(k.geometry(), lambert());
  const winMat = new MeshBasicMaterial({ vertexColors: false, color: 0x2a3340, side: DoubleSide });
  const windows = new Mesh(win.geometry(), winMat);
  g.add(body, windows); g.scale.setScalar(scale);
  g.userData.windows = winMat;
  return g;
}

export function buildPier() {
  const k = new Kit(); const [x, z0] = P.pierStart, z1 = P.pierEnd[1], len = z0 - z1, cz = (z0 + z1) / 2;
  k.add(new BoxGeometry(0.62, 0.07, len), 0x8b6a4c, M(x, 0.26, cz));
  k.add(new BoxGeometry(0.5, 0.03, len - 0.3), 0xf2f5f9, M(x, 0.31, cz + 0.1));
  for (let i = 0; i <= 6; i++) { const zz = z0 - (len * i) / 6; for (const dx of [-0.28, 0.28]) k.add(new CylinderGeometry(0.035, 0.035, 0.9, 5), 0x5a4330, M(x + dx, -0.15, zz)); }
  k.add(new BoxGeometry(1.4, 0.07, 0.9), 0x8b6a4c, M(x, 0.26, z1 + 0.2));
  k.add(new BoxGeometry(1.3, 0.03, 0.8), 0xf2f5f9, M(x, 0.31, z1 + 0.2));
  for (const dx of [-0.62, 0.62]) { k.add(new CylinderGeometry(0.025, 0.025, 0.7, 5), 0x2b2b2e, M(x + dx, 0.62, z1 - 0.15)); }
  const mesh = new Mesh(k.geometry(), lambert());
  // the two lamp heads glow at night
  const lamps = new Mesh(new SphereGeometry(0.07, 10, 8), new MeshBasicMaterial({ color: 0xe8e4da }));
  const l2 = lamps.clone(); lamps.position.set(x - 0.62, 1.0, z1 - 0.15); l2.position.set(x + 0.62, 1.0, z1 - 0.15); l2.material = lamps.material;
  const g = new Group(); g.add(mesh, lamps, l2); g.userData.lamp = lamps.material;
  return g;
}

export function buildTown(quality) {
  // little snowy houses along the shore road, the casino towers at Stateline, and their lights at night
  const roadPts = [...ROAD_LOOP];
  const rnd = mulberry32(9), houses = [];
  const near = (cx, cz, r, n) => { for (let i = 0; i < n; i++) { const a = rnd() * TAU, d = Math.sqrt(rnd()) * r, x = cx + Math.cos(a) * d, z = cz + Math.sin(a) * d; const h = landH(x, z); if (h > 0.25 && landN(x, z)[1] > 0.85 && segDist(x, z, roadPts) > 0.9 && Math.hypot(x - P.cabin[0], z - P.cabin[1]) > 3) houses.push([x, h, z, rnd()]); } };
  const N = quality.houses;
  near(-4, 55, 9, N * 0.22); near(18, 55, 9, N * 0.22); near(30, 52, 5, N * 0.1); near(-24, -47, 6, N * 0.14); near(-28, 2, 4, N * 0.06);
  near(30, -30, 4, N * 0.06); near(4, -56, 6, N * 0.08); near(-30, -20, 4, N * 0.06); near(36, 30, 4, N * 0.06);
  const k = new Kit();
  k.add(new BoxGeometry(0.6, 0.42, 0.5), 0xffffff, M(0, 0.21, 0));
  k.add(new ConeGeometry(0.5, 0.32, 4), 0xf4f7fb, M(0, 0.58, 0, 0, Math.PI / 4, 0, 1, 1, 0.82));
  const geo = k.geometry();
  const walls = [0x8a5a3a, 0x6b7a8f, 0xa3423a, 0x5e6f5a, 0xc9b79c, 0x7a4a2a];
  const mat = lambert();
  const mesh = new InstancedMesh(geo, mat, houses.length + 4);
  const m = new Matrix4(), q = new Quaternion(), e = new Euler(), v = new Vector3(), s = new Vector3(), c = new Color(), white = new Color(0xffffff);
  const lights = [];
  houses.forEach(([x, y, z, r], i) => {
    e.set(0, r * TAU, 0); q.setFromEuler(e); v.set(x, y - 0.03, z); s.setScalar(0.85 + r * 0.6); m.compose(v, q, s); mesh.setMatrixAt(i, m);
    mesh.setColorAt(i, c.set(walls[(r * 97) % walls.length | 0]).lerp(white, 0.05));
    lights.push(x + (r - 0.5) * 0.3, y + 0.3, z - 0.25);
  });
  // Stateline's casino towers
  [[37.5, 46.2, 3.2], [39.6, 47.6, 2.6], [36.2, 48.8, 2.2], [41.2, 45.6, 1.8]].forEach(([x, z, hh], j) => {
    const i = houses.length + j, y = landH(x, z);
    q.identity(); v.set(x, y, z); s.set(2.0, hh * 2.4, 1.6); m.compose(v, q, s); mesh.setMatrixAt(i, m); mesh.setColorAt(i, c.set(0xd8dde6));
    for (let f = 0; f < 7; f++) lights.push(x + (rnd() - 0.5) * 1.0, y + 0.3 + rnd() * hh * 0.9, z - 0.62);
  });
  mesh.frustumCulled = false;
  const lg = new BufferGeometry(); lg.setAttribute('position', new Float32BufferAttribute(lights, 3));
  const lmat = new PointsMaterial({ color: 0xffbf6b, size: 2.6 * Math.min(devicePixelRatio || 1, 2), sizeAttenuation: false, transparent: true, opacity: 0, depthWrite: false, blending: AdditiveBlending });
  const lpts = new Points(lg, lmat); lpts.frustumCulled = false;
  const g = new Group(); g.add(mesh, lpts); g.userData.lights = lmat;
  return g;
}

export function buildRoads() {
  const k = new Kit();
  const ribbon = (pts, w) => {
    const curve = new CatmullRomCurve3(pts.map(([x, z]) => new Vector3(x, 0, z)), pts[0][0] === pts[pts.length - 1][0] && pts[0][1] === pts[pts.length - 1][1], 'centripetal');
    const n = Math.ceil(curve.getLength() / 0.5), pos = [];
    const sp = curve.getSpacedPoints(n);
    for (let i = 0; i < sp.length - 1; i++) {
      const a = sp[i], b = sp[i + 1], dx = b.x - a.x, dz = b.z - a.z, l = Math.hypot(dx, dz) || 1, ox = (-dz / l) * w, oz = (dx / l) * w;
      const A = [a.x + ox, landH(a.x + ox, a.z + oz) + 0.07, a.z + oz], B = [a.x - ox, landH(a.x - ox, a.z - oz) + 0.07, a.z - oz];
      const C = [b.x + ox, landH(b.x + ox, b.z + oz) + 0.07, b.z + oz], D = [b.x - ox, landH(b.x - ox, b.z - oz) + 0.07, b.z - oz];
      pos.push(...A, ...B, ...C, ...C, ...B, ...D);
    }
    const g = new BufferGeometry(); g.setAttribute('position', new Float32BufferAttribute(pos, 3));
    k.add(g, 0x3c4048);
  };
  ribbon(ROAD_LOOP, 0.36); ribbon(ROAD_RENO, 0.36); ribbon(ROAD_SPOONER, 0.3); ribbon(ROAD_HOPE, 0.3);
  const mesh = new Mesh(k.geometry(), lambert({ polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
  return mesh;
}

export function buildLift() {
  // Heavenly's gondola: towers, the cable, and cabins that run up and down it
  const [a, b] = LIFT, k = new Kit(), n = 7;
  const ya = landH(a[0], a[1]), yb = landH(b[0], b[1]);
  const cablePts = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, x = lerp(a[0], b[0], t), z = lerp(a[1], b[1], t), y = landH(x, z), top = Math.max(y + 1.3, lerp(ya + 1.3, yb + 1.3, t));
    k.add(new BoxGeometry(0.1, top - y, 0.1), 0x4b4f57, M(x, (top + y) / 2, z));
    k.add(new BoxGeometry(0.6, 0.06, 0.08), 0x4b4f57, M(x, top, z, 0, Math.atan2(b[0] - a[0], b[1] - a[1]), 0));
    cablePts.push(new Vector3(x, top - 0.02, z));
  }
  // base and top stations
  k.add(new BoxGeometry(1.4, 0.7, 1.0), 0x9aa0aa, M(a[0] - 0.4, ya + 0.35, a[1] - 0.6)); k.add(new BoxGeometry(1.5, 0.08, 1.1), 0xf4f7fb, M(a[0] - 0.4, ya + 0.74, a[1] - 0.6));
  k.add(new BoxGeometry(1.2, 0.6, 0.9), 0x9aa0aa, M(b[0] + 0.3, yb + 0.3, b[1] + 0.4)); k.add(new BoxGeometry(1.3, 0.08, 1.0), 0xf4f7fb, M(b[0] + 0.3, yb + 0.64, b[1] + 0.4));
  const g = new Group(); g.add(new Mesh(k.geometry(), lambert()));
  const curve = new CatmullRomCurve3(cablePts);
  const line = new Line(new BufferGeometry().setFromPoints(curve.getPoints(40)), new LineBasicMaterial({ color: 0x2f3238 }));
  g.add(line);
  const cabins = new InstancedMesh(new BoxGeometry(0.22, 0.2, 0.2), new MeshLambertMaterial({ color: 0xc2410c }), 12);
  cabins.frustumCulled = false; g.add(cabins);
  const mm = new Matrix4(), v = new Vector3();
  g.userData.step = (time) => {
    for (let i = 0; i < 12; i++) {
      const up = i % 2 === 0, t = ((time * 0.018 + i / 12) % 1 + 1) % 1, u = up ? t : 1 - t;
      curve.getPoint(u, v); v.y -= 0.18; v.x += up ? 0.12 : -0.12; mm.makeTranslation(v.x, v.y, v.z); cabins.setMatrixAt(i, mm);
    }
    cabins.instanceMatrix.needsUpdate = true;
  };
  return g;
}

/* little things that make it a place: Fannette Island's tea house, a fire pit by the cabin, chimney smoke */
export function buildDetails() {
  const k = new Kit();
  const [ix, iz] = P.island, iy = landH(ix, iz);
  k.add(new BoxGeometry(0.34, 0.3, 0.3), 0x8c8a86, M(ix, iy + 0.15, iz)); k.add(new ConeGeometry(0.28, 0.2, 4), 0xf4f7fb, M(ix, iy + 0.4, iz, 0, Math.PI / 4, 0));
  const fx = P.cabin[0] - 1.6, fz = P.cabin[1] - 1.9, fy = landH(fx, fz);
  for (let i = 0; i < 8; i++) { const a = (i / 8) * TAU; k.add(new IcosahedronGeometry(0.08, 0), 0x77736e, M(fx + Math.cos(a) * 0.22, fy + 0.04, fz + Math.sin(a) * 0.22)); }
  for (const a of [0.6, 2.4, 4.2]) k.add(new BoxGeometry(0.5, 0.12, 0.14), 0x6a4226, M(fx + Math.cos(a) * 0.62, fy + 0.07, fz + Math.sin(a) * 0.62, 0, -a, 0));
  const g = new Group(); g.add(new Mesh(k.geometry(), lambert()));
  const fire = new Mesh(new ConeGeometry(0.12, 0.32, 6), new MeshBasicMaterial({ color: 0xffa23a, transparent: true, opacity: 0 }));
  fire.position.set(fx, fy + 0.18, fz); g.add(fire); g.userData.fire = fire;
  // chimney smoke: a few soft puffs that rise and fade
  const cv = document.createElement('canvas'); cv.width = cv.height = 64; const x = cv.getContext('2d');
  const gr = x.createRadialGradient(32, 32, 0, 32, 32, 32); gr.addColorStop(0, 'rgba(255,255,255,.85)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); x.fillStyle = gr; x.fillRect(0, 0, 64, 64);
  const smokeMat = new PointsMaterial({ map: new CanvasTexture(cv), size: 0.9, transparent: true, opacity: 0.55, depthWrite: false, color: 0xe9edf2 });
  const sp = new Float32Array(8 * 3); const smoke = new Points(new BufferGeometry().setAttribute('position', new BufferAttribute(sp, 3)), smokeMat);
  smoke.frustumCulled = false; g.add(smoke);
  const base = new Vector3(P.cabin[0] + 0.55, landH(P.cabin[0], P.cabin[1]) + 1.78, P.cabin[1] + 0.1);
  g.userData.step = (time) => {
    for (let i = 0; i < 8; i++) { const t = ((time * 0.12 + i / 8) % 1); sp[i * 3] = base.x + t * 1.1 + Math.sin(time + i) * 0.08; sp[i * 3 + 1] = base.y + t * 2.2; sp[i * 3 + 2] = base.z - t * 0.4; }
    smoke.geometry.attributes.position.needsUpdate = true;
    fire.scale.y = 0.85 + Math.sin(time * 11) * 0.12 + Math.sin(time * 17.3) * 0.08;
  };
  g.userData.smoke = smokeMat;
  return g;
}

/* ------------------------------------------------------------------ the family and the car */
export function buildFamily(s = 1) {
  const g = new Group();
  const who = [[-0.16, 1, 0x2b59c3, 0xe8b48a, 0x3a2a20], [0.16, 1.04, 0xc92a5e, 0x8d5a3b, 0x1c1410], [-0.05, 0.7, 0xffb020, 0xc68b5e, 0x2a1e17], [0.06, 0.64, 0x15803d, 0xe8b48a, 0x6b4a2a]];
  g.userData.people = who.map(([x, h, coat, skin, hair], i) => {
    const p = new Group(), k = new Kit();
    k.add(new CylinderGeometry(0.06 * h, 0.085 * h, 0.24 * h, 8), coat, M(0, 0.13 * h, 0));
    k.add(new SphereGeometry(0.07 * h + 0.012, 10, 8), skin, M(0, 0.32 * h, 0));
    k.add(new SphereGeometry(0.078 * h + 0.012, 10, 6, 0, TAU, 0, Math.PI / 2.1), i % 2 ? 0xffffff : hair, M(0, 0.335 * h, -0.004));
    k.add(new SphereGeometry(0.022 * h, 6, 5), i % 2 ? 0xc92a5e : 0x2b59c3, M(0, 0.42 * h, 0));
    p.add(new Mesh(k.geometry(), lambert())); p.position.x = x; p.position.z = i < 2 ? 0 : 0.1;
    p.userData.hop = { v: 0, vel: 0 }; g.add(p); return p;
  });
  g.scale.setScalar(s);
  g.userData.hop = (i, amount = 2.2) => { const p = g.userData.people[i]; if (p.position.y < 0.01) p.userData.hop.vel = amount; };
  g.userData.step = (dt) => g.userData.people.forEach((p) => { const h = p.userData.hop; h.vel -= 9.8 * dt; h.v = Math.max(0, h.v + h.vel * dt); if (h.v === 0) h.vel = Math.max(0, h.vel); p.position.y = h.v; });
  return g;
}

export function buildCar(color = 0x15803d) {
  const k = new Kit();
  k.add(new BoxGeometry(0.42, 0.16, 0.86), color, M(0, 0.17, 0));
  k.add(new BoxGeometry(0.38, 0.15, 0.5), color, M(0, 0.32, -0.02));
  k.add(new BoxGeometry(0.39, 0.1, 0.4), 0x1b2430, M(0, 0.33, -0.03));
  k.add(new BoxGeometry(0.3, 0.06, 0.5), 0xf4f7fb, M(0, 0.43, -0.02));
  k.add(new BoxGeometry(0.03, 0.02, 0.62), 0xc2410c, M(-0.08, 0.47, -0.02)); k.add(new BoxGeometry(0.03, 0.02, 0.62), 0x2b59c3, M(0.08, 0.47, -0.02));
  for (const [x, z] of [[-0.2, 0.28], [0.2, 0.28], [-0.2, -0.28], [0.2, -0.28]]) k.add(new CylinderGeometry(0.08, 0.08, 0.06, 10), 0x15171a, M(x, 0.08, z, 0, 0, Math.PI / 2));
  k.add(new BoxGeometry(0.08, 0.04, 0.02), 0xfff3c4, M(-0.13, 0.19, -0.43)); k.add(new BoxGeometry(0.08, 0.04, 0.02), 0xfff3c4, M(0.13, 0.19, -0.43));
  const g = new Group(); const body = new Mesh(k.geometry(), lambert()); body.rotation.y = Math.PI; g.add(body);
  // a blinker on each rear corner, for the turn at the fork
  const blink = new MeshBasicMaterial({ color: 0xffa21a, transparent: true, opacity: 0 });
  for (const x of [-0.17, 0.17]) { const b = new Mesh(new BoxGeometry(0.07, 0.05, 0.03), blink); b.position.set(x, 0.2, 0.44); b.userData.side = Math.sign(x); g.add(b); }
  g.userData.blink = blink;
  return g;
}
export function buildSled() {
  const k = new Kit();
  k.add(new BoxGeometry(0.62, 0.05, 0.3), 0xc2410c, M(0, 0.05, 0));
  for (const z of [-0.12, 0.12]) k.add(new BoxGeometry(0.7, 0.025, 0.03), 0x2b2b2e, M(0.02, 0.0, z));
  return new Mesh(k.geometry(), lambert());
}

/* ------------------------------------------------------------------ lights */
export function buildLights() {
  const hemi = new HemisphereLight(0xd7e7ff, 0x9aa6b8, 1.35);
  const sun = new DirectionalLight(0xfff3e2, 2.6);
  const fog = new Fog(0xd9e6f3, 60, 420);
  return { hemi, sun, fog };
}

/* ------------------------------------------------------------------ atmosphere states */
// Each state is a full description (threejs-landscape: "time of day is interpolation, not a switch").
export const STATES = {
  day: { zen: 0x3f7fd0, mid: 0x7faee6, hor: 0xd6e5f4, haze: 0xe6eef6, sun: [-0.55, 0.42, 0.72], sunCol: 0xfff3e2, sunI: 2.5, glow: 0.8, disc: 1,
    hemiSky: 0xd7e7ff, hemiGround: 0x95a3b8, hemiI: 1.35, deep: 0x113d8c, shallow: 0x2b98b3, spec: 1, stars: 0, moon: 0, moonDir: [0.3, 0.5, -0.8], night: 0, snow: 0xf3f6fa, leaf: 0x7fb24a },
  golden: { zen: 0x4a64a6, mid: 0x9c9fce, hor: 0xffc79e, haze: 0xf3c9aa, sun: [-0.95, 0.06, 0.1], sunCol: 0xffad6e, sunI: 2.4, glow: 1.3, disc: 1,
    hemiSky: 0xaab4e6, hemiGround: 0x7a7090, hemiI: 1.0, deep: 0x1d3779, shallow: 0x3d86a2, spec: 1.2, stars: 0.05, moon: 0, moonDir: [0.6, 0.2, -0.7], night: 0.1, snow: 0xfbeee6, leaf: 0xd9a03a },
  night: { zen: 0x040a1c, mid: 0x0b1736, hor: 0x1c2d52, haze: 0x152244, sun: [0.42, 0.58, -0.7], sunCol: 0xa9beff, sunI: 1.05, glow: 0.12, disc: 0,
    hemiSky: 0x4a5f96, hemiGround: 0x0e1424, hemiI: 0.9, deep: 0x030c22, shallow: 0x0d3048, spec: 0.55, stars: 1, moon: 1, moonDir: [0.42, 0.58, -0.7], night: 1, snow: 0xdfe7f5, leaf: 0x4a6a3a },
  late: { zen: 0x030817, mid: 0x0a1431, hor: 0x23365e, haze: 0x182a4e, sun: [-0.95, 0.12, 0.05], sunCol: 0xb8c8ff, sunI: 1.1, glow: 0.35, disc: 0,
    hemiSky: 0x4a5f96, hemiGround: 0x0e1424, hemiI: 0.82, deep: 0x030c22, shallow: 0x0d3048, spec: 0.9, stars: 1, moon: 1, moonDir: [-0.95, 0.12, 0.05], night: 1, snow: 0xdfe7f5, leaf: 0x4a6a3a },
  // the four seasons for concept B, all in daylight (the dark mode versions are tinted toward night by the concept)
  spring: { zen: 0x4a8ad6, mid: 0x8fbbe8, hor: 0xdfeaf0, haze: 0xe8eee8, sun: [-0.5, 0.55, 0.66], sunCol: 0xfff6e8, sunI: 2.5, glow: 0.7, disc: 1,
    hemiSky: 0xdcebff, hemiGround: 0x8e9a78, hemiI: 1.3, deep: 0x0f4a9c, shallow: 0x34b4c4, spec: 1, stars: 0, moon: 0, moonDir: [0.3, 0.5, -0.8], night: 0, snow: 0xf5f7fa, leaf: 0x9ccf5a },
  summer: { zen: 0x2f78d4, mid: 0x6faee8, hor: 0xd2e6f2, haze: 0xe2ecef, sun: [-0.35, 0.78, 0.5], sunCol: 0xfff8ec, sunI: 2.7, glow: 0.6, disc: 1,
    hemiSky: 0xd6e9ff, hemiGround: 0x7d8a5e, hemiI: 1.3, deep: 0x0b4aa6, shallow: 0x22c2c9, spec: 1.1, stars: 0, moon: 0, moonDir: [0.3, 0.5, -0.8], night: 0, snow: 0xf5f7fa, leaf: 0x4f9a3a },
  fall: { zen: 0x4d79bd, mid: 0x9bb3d8, hor: 0xf1dcc2, haze: 0xeedcc8, sun: [-0.75, 0.3, 0.58], sunCol: 0xffd9a8, sunI: 2.4, glow: 0.95, disc: 1,
    hemiSky: 0xe0e0f0, hemiGround: 0x917a5a, hemiI: 1.2, deep: 0x123f8c, shallow: 0x2d98b0, spec: 1, stars: 0, moon: 0, moonDir: [0.3, 0.5, -0.8], night: 0, snow: 0xf5f7fa, leaf: 0xe2a02c },
};
const numKeys = ['sunI', 'glow', 'disc', 'hemiI', 'spec', 'stars', 'moon', 'night'];
const colKeys = ['zen', 'mid', 'hor', 'haze', 'sunCol', 'hemiSky', 'hemiGround', 'deep', 'shallow', 'snow', 'leaf'];
const vecKeys = ['sun', 'moonDir'];
const _ca = new Color(), _cb = new Color();
export function mixState(A, B, t, out = {}) {
  for (const k of numKeys) out[k] = lerp(A[k], B[k], t);
  for (const k of colKeys) out[k] = _ca.set(A[k]).lerp(_cb.set(B[k]), t).getHex();
  for (const k of vecKeys) { const a = A[k], b = B[k]; const v = new Vector3(lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)).normalize(); out[k] = [v.x, v.y, v.z]; }
  return out;
}
