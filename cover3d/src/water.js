// The lake (F-206): Lake Tahoe's own colours, turquoise shallows over pale sand where the floor shows through water clear enough to see boulders,
// deepening to cobalt within a couple of hundred metres of the shore. Shaded per pixel (after Meng To's 3d-ultra-realistic-water, MIT): ripple
// normals from the analytic derivatives of a small wave sum, each wave faded out at its own pixel footprint so the far lake never boils; baked micro
// detail; wind streaks that read as calm and rippled patches from the air; Schlick Fresnel with water's F0 of 0.02 against the shared sky (the
// reflection clamped above the horizon) or, on a strong laptop near the water, a planar reflection of the scene; sun and moon glitter; a lapping
// line at the shore; and the same haze as the sky, so the lake meets it with no line.
import { Mesh, PlaneGeometry, ShaderMaterial, Vector3, Vector4, Color, Matrix4, Plane, Vector2, PerspectiveCamera, WebGLRenderTarget, HalfFloatType, LinearFilter, DoubleSide } from 'three';
import { SKY_GLSL } from './sky.js';
import { GROUND_GLSL } from './terrain.js';

const VS = /* glsl */ `
#include <common>
#include <logdepthbuf_pars_vertex>
uniform float uLevel; varying vec3 vW; varying vec4 vClip;
void main() {
  vW = vec3(position.x, uLevel, position.y);
  gl_Position = projectionMatrix * viewMatrix * vec4(vW, 1.0);
  vClip = gl_Position;
  #include <logdepthbuf_vertex>
}`;

const FS = /* glsl */ `
#include <common>
#include <logdepthbuf_pars_fragment>
${SKY_GLSL}
${GROUND_GLSL}
uniform vec3 uCam, uDeep, uShallow, uSand, uLightDir, uLightCol;
uniform float uTime, uLevel, uRise, uSpec, uNight, uFoam, uReflAmt;
uniform vec4 uSkip;
uniform sampler2D uRefl; uniform mat4 uReflMat;
varying vec3 vW; varying vec4 vClip;

// a calm lake: eight short ripples, deep-water dispersion; each fades out once it is smaller than the pixel it falls in
vec3 ripples(vec2 p, float foot) {
  vec2 g = vec2(0.0);
  for (int i = 0; i < 8; i++) {
    float fi = float(i);
    float L = 9.0 * pow(0.68, fi);
    float a = 0.035 * pow(0.7, fi);
    float ang = 0.9 + fi * 1.37;
    vec2 k = vec2(cos(ang), sin(ang)) * (6.2831 / L);
    float w = sqrt(9.81 * length(k));
    float fade = 1.0 - smoothstep(0.18 * L, 0.5 * L, foot);
    float ph = dot(k, p) - w * uTime;
    g += k * cos(ph) * a * fade;
  }
  return vec3(-g.x, 1.0, -g.y);
}

void main() {
  #include <logdepthbuf_fragment>
  vec2 p = vW.xz;
  if (p.x > uSkip.x && p.x < uSkip.z && p.y > uSkip.y && p.y < uSkip.w) discard;
  float sd = shoreAt(p);
  if (sd > 0.5) discard;
  vec3 V = uCam - vW; float dist = length(V); V /= dist;
  float foot = 2.0 * (fwidth(p.x) + fwidth(p.y));
  vec3 n = ripples(p, foot);
  // wind streaks: the lake from the air is never one sheet, calm lanes between rippled ones
  float wind = smoothstep(0.35, 0.7, texture2D(uNoise, p / 2400.0 + vec2(uTime * 0.0004, 0.0)).g);
  // baked micro detail, two scales drifting with the wind, faded with distance
  vec2 t1 = p / 23.0 + vec2(uTime * 0.012, uTime * 0.007), t2 = p / 7.3 + vec2(-uTime * 0.02, uTime * 0.011);
  vec2 d1 = vec2(texture2D(uNoise, t1).g, texture2D(uNoise, t1 + 0.31).b) - 0.5;
  vec2 d2 = vec2(texture2D(uNoise, t2).b, texture2D(uNoise, t2 + 0.57).g) - 0.5;
  float df = (0.4 * exp(-dist / 900.0) + 0.08) * (0.55 + 0.6 * wind);
  n.xz += (d1 * 0.9 + d2 * 0.5) * df * (1.0 - smoothstep(0.6, 3.0, foot));
  n.xz *= 0.55 + 0.75 * wind;
  n = normalize(n);
  // depth from the carved lake floor (the elevation knows the shallows)
  float depth = max(uLevel - heightAt(p) * uRise, 0.0);
  float shallow = exp(-depth / 3.2);
  vec3 body = mix(uDeep, uShallow, exp(-depth / 11.0));
  body = mix(body, uSand * 0.85 * (0.85 + 0.3 * texture2D(uNoise, p / 31.0).b), shallow * 0.55);
  // sky or scene in the water
  float cosv = max(dot(n, V), 0.0);
  float F = 0.02 + 0.98 * pow(1.0 - cosv, 5.0);
  vec3 R = reflect(-V, n); R.y = abs(R.y) + 0.002;
  vec3 refl = skyColor(R);
  if (uReflAmt > 0.0) {
    vec4 rc = uReflMat * vec4(vW, 1.0);
    vec2 ruv = rc.xy / rc.w + n.xz * vec2(0.06, 0.03) * clamp(30.0 / dist, 0.2, 1.0);
    vec4 sc = texture2D(uRefl, ruv);
    refl = mix(refl, sc.rgb / max(sc.a, 1e-3), sc.a * uReflAmt);                   // the mirror pass is premultiplied where it is not opaque
  }
  vec3 col = mix(body, refl, F);
  // glitter: the sun's (or the moon's) path breaking into sparkles
  float rl = max(dot(R, uLightDir), 0.0);
  col += uLightCol * (pow(rl, 90.0) * 0.5 + pow(rl, 900.0) * 6.0 + pow(rl, 12.0) * 0.04) * uSpec * (0.4 + 0.8 * wind);
  // where the lake laps the shore: a bright wet line and a little lace
  float lace = smoothstep(0.55, 0.8, texture2D(uNoise, p / 5.0 + vec2(uTime * 0.03, 0.0)).g);
  float edge = smoothstep(-7.0, -0.5, sd) * (1.0 - smoothstep(-0.5, 0.5, sd));
  col = mix(col, vec3(0.92, 0.95, 0.97) * (0.5 + 0.5 * uLightCol), edge * (0.25 + 0.55 * lace) * uFoam);
  col = hazed(col, vW, uCam);
  float alpha = mix(0.9 - 0.62 * shallow, 1.0, F) * (1.0 - smoothstep(-0.2, 0.5, sd) * 0.6);
  gl_FragColor = vec4(col, alpha * uRise);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export function buildWater(T, SKYU, terrainU, rect, level, skip) {
  const [x0, z0, x1, z1] = rect;
  const geo = new PlaneGeometry(x1 - x0, z1 - z0, 16, 16);
  geo.translate((x0 + x1) / 2, (z0 + z1) / 2, 0);
  const U = {
    ...SKYU,
    uH: terrainU.uH, uS: terrainU.uS, uHB: terrainU.uHB, uSB: terrainU.uSB, uSdfUnit: terrainU.uSdfUnit, uExag: terrainU.uExag, uDetail: terrainU.uDetail, uNoiseTile: terrainU.uNoiseTile,
    uCam: terrainU.uCam, uRise: terrainU.uRise, uLightDir: terrainU.uLightDir, uLightCol: terrainU.uLightCol,
    uDeep: { value: new Color(0x0b2f6e) }, uShallow: { value: new Color(0x1f9fb2) }, uSand: terrainU.uSand,
    uTime: { value: 0 }, uLevel: { value: level }, uSpec: { value: 1 }, uNight: { value: 0 }, uFoam: { value: 1 },
    uSkip: { value: new Vector4(...(skip || [1e9, 1e9, -1e9, -1e9])) },
    uRefl: { value: null }, uReflMat: { value: new Matrix4() }, uReflAmt: { value: 0 },
  };
  const mat = new ShaderMaterial({ uniforms: U, vertexShader: VS, fragmentShader: FS, transparent: true, depthWrite: false, side: DoubleSide });   // the plane's local y is the world's z, which turns its faces down
  const mesh = new Mesh(geo, mat);
  mesh.renderOrder = 2; mesh.frustumCulled = false;
  mesh.userData.U = U;
  return mesh;
}

// A planar reflection for the lake: the scene mirrored in the water plane, at half resolution, only when the camera is near the water on a strong
// laptop (the pier at sunset). The water layer itself is left out of the mirror pass.
export function planarReflection(renderer, scale = 0.5) {
  const rt = new WebGLRenderTarget(2, 2, { type: HalfFloatType, magFilter: LinearFilter, minFilter: LinearFilter });
  const cam = new PerspectiveCamera();
  const clip = new Plane(new Vector3(0, 1, 0), 0.05);
  const texMat = new Matrix4(), bias = new Matrix4().set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
  const size = new Vector2();
  return {
    rt, texMat,
    render(scene, camera, hide) {
      renderer.getDrawingBufferSize(size);
      const w = Math.max(2, Math.round(size.x * scale)), h = Math.max(2, Math.round(size.y * scale));
      if (rt.width !== w || rt.height !== h) rt.setSize(w, h);
      cam.copy(camera);
      cam.position.y = -camera.position.y;
      const fwd = new Vector3(0, 0, -1).applyQuaternion(camera.quaternion); fwd.y = -fwd.y;
      const up = new Vector3(0, 1, 0).applyQuaternion(camera.quaternion); up.y = -up.y;
      cam.up.copy(up); cam.lookAt(cam.position.clone().add(fwd));
      cam.projectionMatrix.copy(camera.projectionMatrix);
      cam.updateMatrixWorld();
      texMat.multiplyMatrices(bias, cam.projectionMatrix).multiply(cam.matrixWorldInverse);
      const prevClip = renderer.clippingPlanes, prevTarget = renderer.getRenderTarget(), prevAuto = renderer.shadowMap.autoUpdate;
      renderer.clippingPlanes = [clip]; renderer.shadowMap.autoUpdate = false;
      hide.forEach((o) => (o.visible = false));
      renderer.setRenderTarget(rt); renderer.setClearColor(0x000000, 0); renderer.clear();
      renderer.render(scene, cam);
      hide.forEach((o) => (o.visible = true));
      renderer.setRenderTarget(prevTarget); renderer.clippingPlanes = prevClip; renderer.shadowMap.autoUpdate = prevAuto;
    },
  };
}
