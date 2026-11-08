// The real Lake Tahoe (F-206): loads what cover3d/tools/bake_tahoe.py baked from the trip cockpit's data (elevation from AWS Terrain Tiles, lakes, roads
// and places from OpenStreetMap, drives from OSRM) and answers questions about it. World space is metres: x east, z south of the pier at the end of
// Ski Run Boulevard, y up from the surface of Lake Tahoe. Heights are drawn EXAG times taller than they are, so the bowl reads from the air.
// The textures the shaders sample and the numbers the placement code reads come from the same quantised values, so nothing floats or sinks.
import { DataTexture, RedFormat, HalfFloatType, UnsignedByteType, LinearFilter, LinearMipmapLinearFilter, ClampToEdgeWrapping, RepeatWrapping, DataUtils, NoColorSpace } from 'three';
import { mulberry32, clamp, lerp } from './core.js';

export const EXAG = 1.55;
export const NOISE_TILE = 1024;               // metres one tile of the shared detail noise covers
const NOISE_N = 256;

async function gunzip(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return new Uint8Array(await new Response(res.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());
}

function decodeHeights(bytes, esc, w, h, step) {
  const q = new Int32Array(w * h);
  let k = 0;
  for (let j = 0; j < h; j++) {
    for (let i = 0; i < w; i++) {
      const n = j * w + i, b = bytes[n];
      const r = b === 255 ? esc[k++] : b & 1 ? -((b + 1) >> 1) : b >> 1;
      q[n] = r + (j > 0 && i > 0 ? q[n - 1] + q[n - w] - q[n - w - 1] : i > 0 ? q[n - 1] : j > 0 ? q[n - w] : 0);
    }
  }
  // round through half floats, the texture's own precision, so the CPU and the GPU read the same ground
  const half = new Uint16Array(w * h), f = new Float32Array(w * h);
  for (let n = 0; n < w * h; n++) { half[n] = DataUtils.toHalfFloat(q[n] * step); f[n] = DataUtils.fromHalfFloat(half[n]); }
  return { half, f };
}

function decodeSdf(bytes, w, h) {
  const v = new Uint8Array(w * h);
  for (let j = 0; j < h; j++) {
    let acc = 0;
    for (let i = 0; i < w; i++) { const n = j * w + i; acc = (i === 0 ? bytes[n] : acc + bytes[n]) & 255; v[n] = acc; }
  }
  return v;
}

// A grid sampled bilinearly at cell centres, clamped at the edges: the CPU twin of a LinearFilter texture.
function sampler(data, w, h, x0, z0, x1, z1, scale = 1, bias = 0) {
  const sx = w / (x1 - x0), sz = h / (z1 - z0);
  return (x, z) => {
    const fx = clamp((x - x0) * sx - 0.5, 0, w - 1.001), fz = clamp((z - z0) * sz - 0.5, 0, h - 1.001);
    const i = fx | 0, j = fz | 0, ax = fx - i, az = fz - j, n = j * w + i;
    const a = data[n], b = data[n + 1], c = data[n + w], d = data[n + w + 1];
    return ((a * (1 - ax) + b * ax) * (1 - az) + (c * (1 - ax) + d * ax) * az) * scale + bias;
  };
}

// The shared detail noise: periodic fBm in one byte per texel. The terrain adds it to the ground near the camera, the forest thins by it,
// the snow sparkles with it; the CPU reads the same bytes for placements.
function detailNoise() {
  const N = NOISE_N, rnd = mulberry32(9), g = new Float32Array(64 * 64 * 2);
  for (let i = 0; i < 64 * 64; i++) { const a = rnd() * Math.PI * 2; g[i * 2] = Math.cos(a); g[i * 2 + 1] = Math.sin(a); }
  const grad = (ix, iy, P) => { const k = (((iy % P) + P) % P) * 64 + (((ix % P) + P) % P); return [g[k * 2], g[k * 2 + 1]]; };
  const perlin = (x, y, P) => {
    const ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy;
    const u = fx * fx * fx * (fx * (fx * 6 - 15) + 10), v = fy * fy * fy * (fy * (fy * 6 - 15) + 10);
    const d = (gx, gy, dx, dy) => { const q = grad(gx, gy, P); return q[0] * dx + q[1] * dy; };
    return lerp(lerp(d(ix, iy, fx, fy), d(ix + 1, iy, fx - 1, fy), u), lerp(d(ix, iy + 1, fx, fy - 1), d(ix + 1, iy + 1, fx - 1, fy - 1), u), v);
  };
  const out = new Uint8Array(N * N * 4);
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      let s = 0, a = 0.5, f = 4, t = 0;
      for (let o = 0; o < 5; o++) { s += perlin((x / N) * f, (y / N) * f, f) * a; t += a; a *= 0.5; f *= 2; }
      const r = perlin((x / N) * 16, (y / N) * 16, 16), b = perlin((x / N) * 32 + 0.5, (y / N) * 32 + 0.5, 32);
      const n = (y * N + x) * 4;
      out[n] = clamp(128 + (s / t) * 170, 0, 255); out[n + 1] = clamp(128 + r * 180, 0, 255); out[n + 2] = clamp(128 + b * 180, 0, 255); out[n + 3] = (rnd() * 255) | 0;
    }
  }
  return out;
}

// each data file's content hash, written in by cover3d/build.mjs: the service worker keeps /assets/ files with ?v= for good, so a new bake is a new URL
const DATA_V = __COVER_DATA__;
const dataUrl = (base, name) => `${base}${name}?v=${DATA_V[name]}`;

export async function loadTahoe(base, tier) {
  const [bin, geoBytes] = await Promise.all([gunzip(dataUrl(base, `tahoe-${tier}.bin.gz`)), gunzip(dataUrl(base, 'tahoe-geo.json.gz'))]);
  if (String.fromCharCode(...bin.subarray(0, 4)) !== 'GAT1') throw new Error('not a GitAway terrain file');
  const hl = new DataView(bin.buffer, bin.byteOffset + 4, 4).getUint32(0, true);
  const head = JSON.parse(new TextDecoder().decode(bin.subarray(8, 8 + hl)));
  let o = 8 + hl;
  const H = head.height, Sd = head.sdf;
  const hb = bin.subarray(o, o + H.bytes); o += H.bytes;
  const escBuf = bin.slice(o, o + H.esc * 2); o += H.esc * 2;            // a copy, so the Int16Array is aligned
  const esc = new Int16Array(escBuf.buffer, escBuf.byteOffset, H.esc);
  const sb = bin.subarray(o, o + Sd.bytes);
  const { half, f } = decodeHeights(hb, esc, H.w, H.h, head.step);
  const sdf = decodeSdf(sb, Sd.w, Sd.h);
  const geo = JSON.parse(new TextDecoder().decode(geoBytes));

  const hTex = new DataTexture(half, H.w, H.h, RedFormat, HalfFloatType);
  const sTex = new DataTexture(sdf, Sd.w, Sd.h, RedFormat, UnsignedByteType);
  for (const t of [hTex, sTex]) { t.magFilter = t.minFilter = LinearFilter; t.wrapS = t.wrapT = ClampToEdgeWrapping; t.colorSpace = NoColorSpace; t.needsUpdate = true; }
  const nz = detailNoise();
  const nTex = new DataTexture(nz, NOISE_N, NOISE_N);
  nTex.wrapS = nTex.wrapT = RepeatWrapping; nTex.magFilter = LinearFilter; nTex.minFilter = LinearMipmapLinearFilter; nTex.generateMipmaps = true; nTex.colorSpace = NoColorSpace; nTex.needsUpdate = true;
  // the CPU twin of texture2D(uNoise, uv).<ch> with LinearFilter and repeat: 0..1
  const noiseUV = (u, v, ch = 0) => {
    const fx = (((u % 1) + 1) % 1) * NOISE_N - 0.5, fz = (((v % 1) + 1) % 1) * NOISE_N - 0.5;
    const i = Math.floor(fx), j = Math.floor(fz), ax = fx - i, az = fz - j, w = (k) => ((k % NOISE_N) + NOISE_N) % NOISE_N;
    const t = (ii, jj) => nz[(w(jj) * NOISE_N + w(ii)) * 4 + ch];
    return ((t(i, j) * (1 - ax) + t(i + 1, j) * ax) * (1 - az) + (t(i, j + 1) * (1 - ax) + t(i + 1, j + 1) * ax) * az) / 255;
  };

  const ground = sampler(f, H.w, H.h, H.x0, H.z0, H.x1, H.z1);                                   // metres above (below) the lake
  const shore = sampler(sdf, Sd.w, Sd.h, Sd.x0, Sd.z0, Sd.x1, Sd.z1, Sd.unit, -128 * Sd.unit);   // metres from the nearest shore, negative on the water
  const noiseAt = (x, z) => noiseUV(x / NOISE_TILE, z / NOISE_TILE, 0) * 2 - 1;                // the ground's detail noise, -1..1
  const DETAIL = 2.2;                                            // metres of ground undulation the shader adds too (snow drifts, hummocks)
  const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const landH = (x, z) => ground(x, z) * EXAG + noiseAt(x, z) * DETAIL * sstep(2, 30, shore(x, z));
  const fallenY = head.fallenLeaf * EXAG;
  const fl = geo.lakes.fallen.flat(), fb = [Math.min(...fl.map((p) => p[0])) - 200, Math.min(...fl.map((p) => p[1])) - 200, Math.max(...fl.map((p) => p[0])) + 200, Math.max(...fl.map((p) => p[1])) + 200];
  const inFallen = (x, z) => x > fb[0] && x < fb[2] && z > fb[1] && z < fb[3];
  const waterY = (x, z) => (shore(x, z) >= 0 ? null : inFallen(x, z) ? fallenY : 0);          // Fallen Leaf Lake sits 48 m above Tahoe
  const cell = (H.x1 - H.x0) / H.w;
  // the forest's rule, the same one the ground's canopy shading uses (terrain.js forestAt): stands with edges, denser low, thinning to the tree line, off cliffs
  const forestAt = (x, z) => {
    const hm = ground(x, z), sd = shore(x, z);
    const gx = (ground(x - cell, z) - ground(x + cell, z)) * EXAG, gz = (ground(x, z - cell) - ground(x, z + cell)) * EXAG;
    const ny = (2 * cell) / Math.hypot(gx, 2 * cell, gz), slope = 1 - ny;
    const stand = noiseUV(x / 3600, z / 3600, 0) * 0.82 + noiseUV(x / 900 + 0.37, z / 900 + 0.37, 1) * 0.18;
    const band = sstep(4, 50, sd) * (1 - sstep(600, 820, hm)) * sstep(-260, -150, hm);
    const alt = 1 - sstep(380, 760, hm) * 0.6;
    return clamp(band * alt * (1 - sstep(0.45, 0.65, slope)) * sstep(0.3, 0.4, stand) * 1.25, 0, 1);
  };
  const slopeAt = (x, z) => { const gx = (ground(x - cell, z) - ground(x + cell, z)) * EXAG, gz = (ground(x, z - cell) - ground(x, z + cell)) * EXAG; return 1 - (2 * cell) / Math.hypot(gx, 2 * cell, gz); };
  const minmax = pyramid(f, H.w, H.h);

  return { head, geo, H, Sd, hTex, sTex, nTex, ground, shore, noiseAt, noiseUV, landH, waterY, fallenY, fallenBox: fb, forestAt, slopeAt, sstep, DETAIL, minmax, places: geo.places, bounds: geo.bounds };
}

// min and max ground per block of 2^k cells, for the terrain's node culling
function pyramid(f, w, h) {
  const levels = [];
  let cw = w, ch = h, mn = f, mx = f;
  for (let k = 0; k < 12 && (cw > 1 || ch > 1); k++) {
    const nw = Math.ceil(cw / 2), nh = Math.ceil(ch / 2), a = new Float32Array(nw * nh), b = new Float32Array(nw * nh);
    for (let j = 0; j < nh; j++) {
      for (let i = 0; i < nw; i++) {
        let lo = 1e9, hi = -1e9;
        for (let dj = 0; dj < 2; dj++) for (let di = 0; di < 2; di++) { const x = Math.min(cw - 1, i * 2 + di), y = Math.min(ch - 1, j * 2 + dj), n = y * cw + x; lo = Math.min(lo, mn[n]); hi = Math.max(hi, mx[n]); }
        a[j * nw + i] = lo; b[j * nw + i] = hi;
      }
    }
    levels.push({ w: nw, h: nh, mn: a, mx: b }); mn = a; mx = b; cw = nw; ch = nh;
  }
  return { w, h, levels, range(x0, z0, x1, z1, H) {
    // the ground's min and max over a box (world metres), from the coarsest level whose blocks fit it
    const sx = w / (H.x1 - H.x0), sz = h / (H.z1 - H.z0);
    const i0 = clamp(Math.floor((x0 - H.x0) * sx), 0, w - 1), i1 = clamp(Math.ceil((x1 - H.x0) * sx), 0, w - 1);
    const j0 = clamp(Math.floor((z0 - H.z0) * sz), 0, h - 1), j1 = clamp(Math.ceil((z1 - H.z0) * sz), 0, h - 1);
    let k = 0; while (k < levels.length - 1 && ((i1 - i0) >> (k + 1)) > 2) k++;
    const L = levels[k], s = 1 << (k + 1);
    let lo = 1e9, hi = -1e9;
    for (let j = j0 / s | 0; j <= Math.min(L.h - 1, j1 / s | 0); j++) for (let i = i0 / s | 0; i <= Math.min(L.w - 1, i1 / s | 0); i++) { lo = Math.min(lo, L.mn[j * L.w + i]); hi = Math.max(hi, L.mx[j * L.w + i]); }
    return [lo, hi];
  } };
}
