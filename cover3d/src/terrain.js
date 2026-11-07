// The ground (F-206): the real Lake Tahoe as a quadtree of tiles (CDLOD, after Strugar's continuous distance-dependent level of detail) that share one
// small grid and read their heights from the elevation texture in the vertex shader, morphing toward the coarser grid as they recede, so the ground
// is fine wherever the camera is (the cabin's slope, the pier's beach, the whole bowl from the air) for a few hundred thousand triangles and no pop.
// Coloured by what the ground is doing, never by a tiled texture (Meng To's threejs-landscape): December snow everywhere it can lie, granite where it
// is too steep to hold, forest canopy below the tree line (the near trees are real meshes, forest.js), a wet strip at the shore and the sandy lake
// floor under the water. Per-pixel normals from the elevation plus snow-crust detail near the camera, ridge shadows marched toward a low sun, and haze.
import { InstancedBufferGeometry, InstancedBufferAttribute, BufferAttribute, Mesh, ShaderMaterial, Vector2, Vector3, Vector4, Color, Frustum, Matrix4, Box3, UniformsLib, UniformsUtils } from 'three';
import { SKY_GLSL } from './sky.js';
import { EXAG, NOISE_TILE } from './data.js';

export const GROUND_GLSL = /* glsl */ `
uniform sampler2D uH, uS;
uniform vec4 uHB, uSB;
uniform float uExag, uDetail, uNoiseTile, uSdfUnit;
float groundAt(vec2 p) { return texture2D(uH, (p - uHB.xy) * uHB.zw).r; }
float shoreAt(vec2 p) { return (texture2D(uS, (p - uSB.xy) * uSB.zw).r * 255.0 - 128.0) * uSdfUnit; }
float detailAt(vec2 p) { return texture2D(uNoise, p / uNoiseTile).r * 2.0 - 1.0; }
float heightAt(vec2 p) { float s = shoreAt(p); return groundAt(p) * uExag + detailAt(p) * uDetail * smoothstep(2.0, 30.0, s); }
`;

const VS = /* glsl */ `
#include <common>
#include <logdepthbuf_pars_vertex>
#include <shadowmap_pars_vertex>
uniform sampler2D uNoise;
${GROUND_GLSL}
attribute vec4 aTile; attribute float aSkirt;
uniform vec3 uCam; uniform vec2 uMorph[14]; uniform float uGrid, uRise;
varying vec3 vW; varying float vSkirt;
void main() {
  vec2 g = position.xz;
  vec2 wp = aTile.xy + g * aTile.z;
  float h = heightAt(wp) * uRise;
  vec2 mr = uMorph[int(aTile.w + 0.5)];
  float m = clamp((distance(uCam, vec3(wp.x, h, wp.y)) - mr.x) / max(mr.y - mr.x, 1.0), 0.0, 1.0);
  g -= fract(g * uGrid * 0.5) * 2.0 / uGrid * m;
  wp = aTile.xy + g * aTile.z;
  h = heightAt(wp) * uRise;
  h -= aSkirt * (aTile.z * 0.03 + 4.0);
  vW = vec3(wp.x, h, wp.y); vSkirt = aSkirt;
  vec4 worldPosition = vec4(vW, 1.0);
  vec4 mvPosition = viewMatrix * worldPosition;
  gl_Position = projectionMatrix * mvPosition;
  #include <logdepthbuf_vertex>
  #include <shadowmap_vertex>
}`;

const FS = /* glsl */ `
#include <common>
#include <packing>
#include <logdepthbuf_pars_fragment>
#include <lights_pars_begin>
#include <shadowmap_pars_fragment>
#include <shadowmask_pars_fragment>
${SKY_GLSL}
${GROUND_GLSL}
uniform vec3 uCam, uSnow, uHemiSky, uHemiGround, uLightDir, uLightCol, uRock, uCanopy, uSand, uPaper, uInk, uLakeInk;
uniform float uLightI, uHemiI, uCell, uRise, uLit, uShadowSteps, uNight, uCanopyNear, uSparkle, uFallenY;
uniform vec4 uBounds;
varying vec3 vW; varying float vSkirt;

float forestAt(vec2 p, float hm, float slope, float sd) {
  // the same rule forest.js plants by (data.js forestAt): stands with edges, above the shore, denser low and thinning to the tree line, off cliffs
  float stand = texture2D(uNoise, p / 3600.0).r * 0.7 + texture2D(uNoise, p / 900.0 + 0.37).g * 0.3;
  float band = smoothstep(4.0, 50.0, sd) * (1.0 - smoothstep(600.0, 820.0, hm)) * smoothstep(-260.0, -150.0, hm);
  float alt = 1.0 - smoothstep(380.0, 760.0, hm) * 0.6;
  return clamp(band * alt * (1.0 - smoothstep(0.45, 0.65, slope)) * smoothstep(0.36, 0.5, stand) * 1.25, 0.0, 1.0);
}

void main() {
  #include <logdepthbuf_fragment>
  vec2 p = vW.xz;
  float e = uCell;
  float hl = groundAt(p - vec2(e, 0.0)), hr = groundAt(p + vec2(e, 0.0)), hd = groundAt(p - vec2(0.0, e)), hu = groundAt(p + vec2(0.0, e));
  float hm = groundAt(p);
  vec3 n = normalize(vec3((hl - hr) * uExag * uRise, 2.0 * e, (hd - hu) * uExag * uRise));
  float dist = distance(uCam, vW);
  float sd = shoreAt(p);
  float slope = 1.0 - n.y;
  // snow crust: wind ripples and drift edges the elevation is too coarse to know, only where the camera is close enough to see them
  float near = 1.0 - smoothstep(30.0, 700.0, dist);
  if (near > 0.0) {
    vec2 q = p / 23.0;
    float a = texture2D(uNoise, q).g, b = texture2D(uNoise, q + vec2(0.0039, 0.0)).g, c = texture2D(uNoise, q + vec2(0.0, 0.0039)).g;
    n = normalize(n + vec3(a - b, 0.0, a - c) * 0.9 * near);
  }
  // what covers the ground: snow wherever it can lie, granite where it is too steep (and more of it on the crest), forest below the tree line
  float crest = smoothstep(560.0, 900.0, hm);
  float steep = smoothstep(0.33 - crest * 0.1, 0.5 - crest * 0.12, slope + (texture2D(uNoise, p / 260.0).b - 0.5) * 0.2);
  vec3 col = uSnow * (0.93 + 0.07 * texture2D(uNoise, p / 600.0).r);
  float cracks = texture2D(uNoise, p / 55.0).b;
  vec3 rock = uRock * (0.62 + 0.55 * cracks);
  rock = mix(rock, uSnow * 0.92, smoothstep(0.6, 0.85, texture2D(uNoise, p / 18.0).g) * 0.55);            // snow caught in the granite's ledges
  col = mix(col, rock, steep * 0.9);
  float forest = forestAt(p, hm, slope, sd);
  float canopyFar = smoothstep(260.0, 2200.0, dist);                                                  // near the camera the real trees stand there instead
  float crowns = texture2D(uNoise, p / 7.0).a;                                                         // crown or gap, every few metres
  vec3 canopy = mix(uCanopy, uSnow * 0.9, crowns * (0.26 + 0.14 * texture2D(uNoise, p / 300.0).b));   // dark needles, snow on the branches
  col = mix(col, canopy, forest * 0.94 * canopyFar);
  // the shore: wet sand where the waves reach, then the lake floor (seen through the clear shallows)
  col = mix(col, uSand * 0.62, (1.0 - smoothstep(0.0, 9.0, sd)) * (1.0 - steep));
  if (sd < 0.0) col = mix(uSand, uSand * vec3(0.55, 0.6, 0.62), smoothstep(0.35, 0.7, texture2D(uNoise, p / 28.0).b)) * (0.75 - 0.4 * smoothstep(0.0, 30.0, -sd));
  // light: sun or moon, ridge shadows marched toward a low sun over the elevation, and the sky's blue in the shadows
  float ndl = max(dot(n, uLightDir), 0.0);
  float sh = 1.0;
  if (uShadowSteps > 0.5 && uLightDir.y < 0.45) {
    vec2 dir = normalize(uLightDir.xz); float tanE = uLightDir.y / max(length(uLightDir.xz), 1e-3);
    float h0 = vW.y + 2.0, t = 40.0;
    for (int i = 0; i < 24; i++) {
      if (float(i) >= uShadowSteps) break;
      vec2 s = p + dir * t;
      float occ = groundAt(s) * uExag * uRise - (h0 + t * tanE);
      sh = min(sh, clamp(1.0 - occ / (t * 0.035 + 8.0), 0.0, 1.0));
      t *= 1.42;
    }
  }
  sh = min(sh, mix(0.35, 1.0, getShadowMask()));                         // the trees', the cabin's and the family's own soft shadows on the snow
  vec3 hemi = mix(uHemiGround, uHemiSky, n.y * 0.5 + 0.5) * uHemiI;
  vec3 lit = col * (hemi + uLightCol * uLightI * ndl * sh) * RECIPROCAL_PI;      // three's own Lambert, so the ground and the props light alike
  // fresh snow glints in the sun, a few points at a time (only close enough to see them)
  if (uSparkle > 0.0 && near > 0.0) {
    vec3 v = normalize(uCam - vW); vec3 hv = normalize(v + uLightDir);
    float g = texture2D(uNoise, p / 1.7 + v.xz * 0.05).a;
    lit += uLightCol * uLightI * smoothstep(0.985, 1.0, g) * pow(max(dot(n, hv), 0.0), 8.0) * sh * near * uSparkle * (1.0 - steep) * 0.8;
  }
  // the book's printed map, before the world has risen: paper, a blue lake and ink contours
  vec3 map = uPaper;
  float contour = abs(fract(hm / 120.0) - 0.5);
  map = mix(map, uInk, (1.0 - smoothstep(0.0, 0.06, contour)) * 0.18 * step(0.0, sd));
  map = mix(map, uLakeInk, 1.0 - smoothstep(-6.0, 2.0, sd));
  // the world's edge fades into the air rather than ending in a cliff
  float edgeD = min(min(p.x - uBounds.x, uBounds.z - p.x), min(p.y - uBounds.y, uBounds.w - p.y));
  vec3 airc = hazed(lit, vW, uCam);
  airc = mix(airc, skyColor(normalize(vW - uCam)), 1.0 - smoothstep(0.0, 3500.0, edgeD));          // what the sky has behind it, seen from here
  vec3 outc = mix(map, airc, uLit);
  gl_FragColor = vec4(outc, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

// The quadtree: a node is drawn at its level when the next finer level's range does not reach it; ranges double per level.
export function buildTerrain(T, SKYU, q) {
  const G = q.grid, H = T.H;
  const verts = [], skirt = [], idx = [];
  const at = (i, j) => j * (G + 1) + i;
  for (let j = 0; j <= G; j++) for (let i = 0; i <= G; i++) { verts.push(i / G, 0, j / G); skirt.push(0); }
  for (let j = 0; j < G; j++) for (let i = 0; i < G; i++) { const a = at(i, j), b = at(i + 1, j), c = at(i, j + 1), d = at(i + 1, j + 1); idx.push(a, c, b, b, c, d); }
  // a skirt round the edge hides the hairline cracks where a tile meets a coarser neighbour
  const border = [];
  for (let i = 0; i < G; i++) border.push([at(i, 0), at(i + 1, 0)]);
  for (let j = 0; j < G; j++) border.push([at(G, j), at(G, j + 1)]);
  for (let i = G; i > 0; i--) border.push([at(i, G), at(i - 1, G)]);
  for (let j = G; j > 0; j--) border.push([at(0, j), at(0, j - 1)]);
  for (const [a, b] of border) {
    const base = verts.length / 3;
    verts.push(verts[a * 3], 0, verts[a * 3 + 2], verts[b * 3], 0, verts[b * 3 + 2]); skirt.push(1, 1);
    idx.push(a, base, b, b, base, base + 1);
  }
  const geo = new InstancedBufferGeometry();
  geo.setAttribute('position', new BufferAttribute(new Float32Array(verts), 3));
  geo.setAttribute('aSkirt', new BufferAttribute(new Float32Array(skirt), 1));
  geo.setIndex(idx);
  const MAX = q.tiles;
  const tiles = new InstancedBufferAttribute(new Float32Array(MAX * 4), 4);
  tiles.setUsage(35048); // DynamicDrawUsage
  geo.setAttribute('aTile', tiles);
  geo.instanceCount = 0;

  // the root square covers the world from its north-west corner; the leaf is about 220 m
  const [X0, Z0, X1, Z1] = T.bounds;
  const LEVELS = 9, side = Math.max(X1 - X0, Z1 - Z0) * 1.0002, leaf = side / 2 ** (LEVELS - 1);
  const ranges = [], morph = [];
  for (let i = 0; i < LEVELS; i++) ranges.push(leaf * 2 ** i * q.lodK);
  for (let i = 0; i < 14; i++) { const r = ranges[Math.min(i, LEVELS - 1)], prev = i ? ranges[i - 1] : 0; morph.push(new Vector2(prev + (r - prev) * 0.62, r * 0.98)); }

  const U = {
    ...UniformsUtils.clone(UniformsLib.lights),
    ...SKYU,
    uH: { value: T.hTex }, uS: { value: T.sTex }, uHB: { value: new Vector4(H.x0, H.z0, 1 / (H.x1 - H.x0), 1 / (H.z1 - H.z0)) },
    uSB: { value: new Vector4(T.Sd.x0, T.Sd.z0, 1 / (T.Sd.x1 - T.Sd.x0), 1 / (T.Sd.z1 - T.Sd.z0)) }, uSdfUnit: { value: T.Sd.unit },
    uExag: { value: EXAG }, uDetail: { value: T.DETAIL }, uNoiseTile: { value: NOISE_TILE },
    uCam: { value: new Vector3() }, uMorph: { value: morph }, uGrid: { value: G }, uRise: { value: 1 }, uLit: { value: 1 },
    uCell: { value: (H.x1 - H.x0) / H.w }, uShadowSteps: { value: q.shadowSteps }, uNight: { value: 0 }, uCanopyNear: { value: q.treeFar },
    uSparkle: { value: q.sparkle }, uFallenY: { value: T.fallenY }, uBounds: { value: new Vector4(X0, Z0, X1, Z1) },
    uSnow: { value: new Color(0xeef2f7) }, uRock: { value: new Color(0x8e8a83) }, uCanopy: { value: new Color(0x142019) }, uSand: { value: new Color(0xc8b48c) },
    uHemiSky: { value: new Color(0xcfe0ff) }, uHemiGround: { value: new Color(0x8f9db4) }, uHemiI: { value: 1 }, uLightDir: { value: new Vector3(0, 1, 0) },
    uLightCol: { value: new Color(0xffffff) }, uLightI: { value: 1 },
    uPaper: { value: new Color(0xf2efe6) }, uInk: { value: new Color(0x5c5c66) }, uLakeInk: { value: new Color(0x7fa6d6) },
  };
  const mat = new ShaderMaterial({ uniforms: U, vertexShader: VS, fragmentShader: FS, lights: true });
  const mesh = new Mesh(geo, mat);
  mesh.frustumCulled = false; mesh.receiveShadow = true;

  const frustum = new Frustum(), pv = new Matrix4(), box = new Box3(), cam = new Vector3();
  const A = tiles.array;
  let count = 0;
  function add(x0, z0, s, lod) { if (count >= MAX) return; A.set([x0, z0, s, lod], count * 4); count++; }
  function visit(x0, z0, s, lod, rise) {
    if (x0 > X1 || z0 > Z1 || x0 + s < X0 || z0 + s < Z0) return;
    const [lo, hi] = T.minmax.range(x0, z0, x0 + s, z0 + s, H);
    box.min.set(x0, Math.min(lo * EXAG * rise, 0) - 10, z0); box.max.set(x0 + s, Math.max(hi * EXAG * rise, 0) + 10, z0 + s);
    if (!frustum.intersectsBox(box)) return;
    if (lod === 0) return add(x0, z0, s, 0);
    // does the next finer level's range reach this node? then split it
    const d = box.distanceToPoint(cam);
    if (d > ranges[lod - 1]) return add(x0, z0, s, lod);
    const h = s / 2;
    visit(x0, z0, h, lod - 1, rise); visit(x0 + h, z0, h, lod - 1, rise); visit(x0, z0 + h, h, lod - 1, rise); visit(x0 + h, z0 + h, h, lod - 1, rise);
  }
  mesh.userData = {
    U, ranges, leaf,
    select(camera, rise) {
      camera.updateMatrixWorld(); pv.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse); frustum.setFromProjectionMatrix(pv);
      cam.copy(camera.position); U.uCam.value.copy(cam);
      count = 0; visit(X0, Z0, side, LEVELS - 1, Math.max(rise, 0.0005));
      geo.instanceCount = count; tiles.needsUpdate = true; tiles.clearUpdateRanges(); tiles.addUpdateRange(0, count * 4);
      return count;
    },
  };
  return mesh;
}
