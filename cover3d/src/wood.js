// Timber (F-206), after Meng To's 3d-wood-material (MIT): one standard material patched in onBeforeCompile, so lighting, shadows and tone mapping stay
// three's own. One small periodic noise field, baked once on the GPU and mip-filtered, is read at several stretches and scales: growth rings whose
// latewood width changes ring by ring, pores and fibres along the grain, medullary rays, open cells on end grain. They feed colour, roughness and a
// clamped derivative bump together, each fading out by its own screen footprint so nothing shimmers at a distance. Every board has its own seed and
// grain axis (vertex attributes), so no two boards repeat; `weather` turns timber silver-grey, the way Tahoe's pier wood goes.
import { MeshStandardMaterial, WebGLRenderTarget, Scene, OrthographicCamera, Mesh, PlaneGeometry, ShaderMaterial, RepeatWrapping, LinearMipmapLinearFilter, LinearFilter, Color, NoColorSpace } from 'three';

let field = null;
// The shared field: 1024 squared, periodic gradient noise in three octaves (.r base, .g fBm 0.60/0.27/0.13, .b a shifted copy).
export function woodField(renderer, size = 1024) {
  if (field) return field;
  const rt = new WebGLRenderTarget(size, size, { generateMipmaps: true, minFilter: LinearMipmapLinearFilter, magFilter: LinearFilter, wrapS: RepeatWrapping, wrapT: RepeatWrapping });
  rt.texture.colorSpace = NoColorSpace;
  const mat = new ShaderMaterial({
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
    fragmentShader: /* glsl */ `
      varying vec2 vUv;
      vec2 hash(vec2 p, float P) { p = mod(p, P); p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3))); return -1.0 + 2.0 * fract(sin(p) * 43758.5453); }
      float gnoise(vec2 x, float P) {
        vec2 i = floor(x), f = fract(x), u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
        return mix(mix(dot(hash(i, P), f), dot(hash(i + vec2(1, 0), P), f - vec2(1, 0)), u.x), mix(dot(hash(i + vec2(0, 1), P), f - vec2(0, 1)), dot(hash(i + vec2(1, 1), P), f - vec2(1, 1)), u.x), u.y);
      }
      void main() {
        vec2 p = vUv * 64.0;
        float a = gnoise(p, 64.0);
        float b = gnoise(p, 64.0) * 0.6 + gnoise(p * 2.0, 128.0) * 0.27 + gnoise(p * 4.0, 256.0) * 0.13;
        float c = gnoise(p + vec2(17.3, 41.9), 64.0);
        gl_FragColor = vec4(a * 0.5 + 0.5, b * 0.5 + 0.5, c * 0.5 + 0.5, 1.0);
      }`,
    depthTest: false, depthWrite: false,
  });
  const scene = new Scene(); scene.add(new Mesh(new PlaneGeometry(2, 2), mat));
  const prev = renderer.getRenderTarget();
  renderer.setRenderTarget(rt); renderer.render(scene, new OrthographicCamera(-1, 1, 1, -1, 0, 1)); renderer.setRenderTarget(prev);
  mat.dispose();
  field = rt.texture;
  return field;
}

// species: pale and dark colour, ring frequency (rings per metre), off-axis (small = cathedral arcs, large = quarter-sawn lines), base roughness
export const SPECIES = {
  pier: { pale: 0xc4ad8e, dark: 0x7d664c, rings: 34, off: 1.8, rough: 0.86, weather: 0.42, bump: 1.0 },
  cedar: { pale: 0xb07a4c, dark: 0x5d3a22, rings: 30, off: 1.2, rough: 0.7, weather: 0.12, bump: 0.8 },
  log: { pale: 0x9c7451, dark: 0x4a3120, rings: 22, off: 0.6, rough: 0.78, weather: 0.25, bump: 1.2 },
  trim: { pale: 0x8a3a2e, dark: 0x5c231b, rings: 34, off: 2.4, rough: 0.6, weather: 0.0, bump: 0.4 },
};

// geometry needs `aWood` (vec2: grain axis 0, 1 or 2, and a seed per board); props.js adds it to everything it builds from boards
export function woodMaterial(renderer, kind, extra = {}) {
  const S = SPECIES[kind];
  const m = new MeshStandardMaterial({ color: 0xffffff, roughness: S.rough, metalness: 0, ...extra });
  const tex = woodField(renderer);
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, {
      uField: { value: tex }, uPale: { value: new Color(S.pale) }, uDark: { value: new Color(S.dark) }, uRings: { value: S.rings }, uOff: { value: S.off },
      uWeather: { value: S.weather }, uBump: { value: S.bump * 0.0016 }, uSnow: { value: m.userData.snow ?? 0 }, uSnowCol: { value: new Color(0xf4f7fb) },
    });
    m.userData.shader = sh;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec2 aWood; varying vec3 vOP; varying vec3 vON; varying vec2 vWood; varying vec3 vWN; varying vec3 vWP;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvOP = position; vON = normal; vWood = aWood; vWN = normalize(mat3(modelMatrix) * normal); vWP = (modelMatrix * vec4(position, 1.0)).xyz;');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', /* glsl */ `#include <common>
        uniform sampler2D uField; uniform vec3 uPale, uDark, uSnowCol; uniform float uRings, uOff, uWeather, uBump, uSnow;
        varying vec3 vOP; varying vec3 vON; varying vec2 vWood; varying vec3 vWN; varying vec3 vWP;
        float fld(vec2 p, int c) { vec4 t = texture2D(uField, p / 64.0); return c == 0 ? t.r : c == 1 ? t.g : t.b; }
        float woodH; float woodRough;
        vec3 woodColor() {
          int ax = int(vWood.x + 0.5); float seed = vWood.y;
          vec3 P = vOP + vec3(seed * 7.113, seed * 3.71, seed * 5.37);
          float along = ax == 0 ? P.x : ax == 1 ? P.y : P.z;
          vec2 cross2 = ax == 0 ? P.yz : ax == 1 ? P.xz : P.xy;
          float eg = pow(abs(ax == 0 ? vON.x : ax == 1 ? vON.y : vON.z), 6.0);
          // rings round a pith that drifts slowly along the board
          vec2 drift = vec2(fld(vec2(along * 0.9, seed * 13.0), 1) - 0.5, fld(vec2(seed * 7.0, along * 0.7), 1) - 0.5) * 0.06;
          float radius = length((cross2 + drift + vec2(0.0, uOff * 0.05 + 0.024)) * vec2(1.0, 0.56));
          float growth = radius * uRings + (fld(vec2(along * 3.0, radius * 40.0), 1) - 0.5) * 2.5;
          float phase = fract(growth), ring = floor(growth);
          float annual = fld(vec2(ring * 0.37, seed * 3.1), 0);
          float lw = 0.065 + annual * 0.21;
          float late = smoothstep(0.94 - lw, 0.97 - lw, phase) * (1.0 - smoothstep(0.965, 1.0, phase));
          float fw = fwidth(growth);
          late = mix(late, lw * 0.6, smoothstep(0.1, 0.45, fw));
          // pores and fibres run with the grain, rays across it; end grain shows open cells
          vec2 pc = vec2(cross2.x * 96.0 * 7.0, along * 7.5 * 7.0);
          float pores = smoothstep(0.59, 0.75, fld(pc, 2)) * (1.0 - smoothstep(0.12, 0.5, length(fwidth(pc))));
          vec2 fc = vec2(cross2.x * 230.0 * 7.0, along * 2.4 * 7.0);
          float fib = (fld(fc, 1) - 0.5) * (1.0 - smoothstep(0.15, 0.6, length(fwidth(fc)))) * mix(1.0, 0.25, eg);
          vec2 rc = vec2(cross2.y * 13.0 * 7.0, along * 115.0 * 7.0);
          float rays = smoothstep(0.64, 0.78, fld(rc, 0)) * 0.6 * (1.0 - smoothstep(0.15, 0.5, length(fwidth(rc))));
          float broad = fld(vec2(along * 0.5, seed * 9.0), 1);
          float tone = 0.075 + late * 0.40 + pores * 0.25 - fib * 0.16 + (broad - 0.5) * 0.23;
          tone = mix(tone, 0.24, uWeather * 0.45);                                         // weathering flattens the figure
          vec3 col = mix(uPale, uDark, clamp(tone, 0.035, 0.83)) * (0.93 + annual * 0.095);
          col *= 1.0 - eg * (0.045 + pores * 0.10);
          // weathering: silver-grey, rougher, grain raised
          float wl = dot(col, vec3(0.299, 0.587, 0.114));
          col = mix(col, vec3(wl) * vec3(0.98, 0.98, 1.0) * 1.08, uWeather);
          woodH = -late * 0.4 - pores * 0.42 + fib * 0.09 * (1.0 + uWeather);
          woodRough = 0.91 + late * 0.13 + pores * 0.19 + (broad - 0.5) * 0.2 - rays * 0.075 + eg * 0.14 + uWeather * 0.08;
          return col;
        }`)
      .replace('#include <map_fragment>', `#include <map_fragment>
        diffuseColor.rgb *= woodColor();
        float snowy = smoothstep(0.55, 0.85, vWN.y + (fld(vOP.xz * 9.0, 2) - 0.5) * 0.5) * uSnow;
        diffuseColor.rgb = mix(diffuseColor.rgb, uSnowCol, snowy);`)
      .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\nroughnessFactor = clamp(roughnessFactor * woodRough, 0.35, 1.0);')
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
        {
          // Mikkelsen's derivative bump of the wood height, its gradient clamped so a hard ring edge never turns the normal inside out
          vec3 dpx = dFdx(-vViewPosition), dpy = dFdy(-vViewPosition);
          float bumpFade = 1.0 - smoothstep(0.1, 0.45, fwidth(woodH) * 8.0);
          float dhx = dFdx(woodH) * uBump * 600.0 * bumpFade, dhy = dFdy(woodH) * uBump * 600.0 * bumpFade;
          vec3 r1 = cross(dpy, normal), r2 = cross(normal, dpx);
          float det = dot(dpx, r1);
          vec3 grad = sign(det) * (dhx * r1 + dhy * r2);
          float lim = 0.38 * abs(det);
          if (length(grad) > lim) grad = normalize(grad) * lim;
          normal = normalize(abs(det) * normal - grad);
        }`);
  };
  m.customProgramCacheKey = () => `cover-wood-${kind}`;
  return m;
}
