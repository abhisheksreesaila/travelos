// The one place every cover concept is built in: Lake Tahoe, stylised. 1 world unit is roughly 12 m near
// people and much more across the lake (a diorama's compression). +x is east, −z is north. The analytic
// height function is separate from any mesh, so trees, roads, pins and the camera all sample the same ground
// (Meng To's threejs-landscape rule: "keep the analytic function separate from the mesh").
import { fbm, ridged, smooth, clamp, lerp } from './core.js';

export const LAKE = { cx: 0, cz: -6, a: 30, b: 53 };

const capsule = (x, z, ax, az, bx, bz) => {
  const pax = x - ax, paz = z - az, bax = bx - ax, baz = bz - az;
  const h = clamp((pax * bax + paz * baz) / (bax * bax + baz * baz), 0, 1);
  return Math.hypot(pax - bax * h, paz - baz * h);
};
const smin = (a, b, k) => { const h = clamp(0.5 + (0.5 * (b - a)) / k, 0, 1); return lerp(b, a, h) - k * h * (1 - h); };

// signed distance to the shore in rough world units; negative is water
export function waterSD(x, z) {
  const nx = (x - LAKE.cx) / LAKE.a, nz = (z - LAKE.cz) / LAKE.b;
  let d = (Math.hypot(nx, nz) - 1) * 33;
  d += fbm(x * 0.04 + 3.1, z * 0.04 - 7.3, 3) * 3.6;
  // the south shore is flatter and straighter where the town is; the east shore has Sand Harbor's coves
  d += smooth(32, 50, z) * smooth(-16, 4, x) * 1.4;
  d -= smooth(10, 0, Math.abs(z + 8)) * smooth(24, 31, x) * 1.2;
  // Emerald Bay: an oval inlet on the south-west shore, joined to the lake by a narrow mouth
  const ca = Math.cos(0.32), sa = Math.sin(0.32), rx = (x + 31) * ca - (z - 34.2) * sa, rz = (x + 31) * sa + (z - 34.2) * ca;
  let db = (Math.hypot(rx / 7.4, rz / 3.5) - 1) * 3.8;
  db = Math.min(db, capsule(x, z, -25.5, 32.6, -20.6, 31.2) - 0.95);
  d = smin(d, db, 1.4);
  // Fannette Island
  const di = Math.hypot(x + 33, z - 35) - 0.8;
  if (di < 0) d = Math.max(d, -di * 2.2);
  return d;
}

// where the town and the cabins sit: South Lake Tahoe is flat
function flatMask(x, z) {
  const fx = smooth(-24, -12, x) * (1 - smooth(34, 46, x));
  const fz = smooth(38, 46, z) * (1 - smooth(66, 80, z));
  return fx * fz;
}

export function landH(x, z) {
  const d = waterSD(x, z);
  if (d < 0) {
    const depth = Math.min(14, 0.4 + -d * 1.4);
    const bay = Math.hypot((x + 31) / 8.6, (z - 34.2) / 4.6) < 1.1 ? 0.4 : 1; // Emerald Bay is shallower
    return -(depth * bay) * smooth(0, 1.6, -d) - 0.12;
  }
  const wx = x + fbm(x * 0.016, z * 0.016, 3) * 16, wz = z + fbm(x * 0.016 + 41, z * 0.016 - 17, 3) * 16;
  let m = fbm(wx * 0.02, wz * 0.02, 5) * 0.5 + 0.5;
  m = Math.pow(clamp(m, 0, 1), 1.25);
  const r = ridged(wx * 0.042, wz * 0.042, 3);
  // low hills at the shore, the real ranges further back; higher to the west (the Crystal Range)
  const far = smooth(4, 60, d);
  let amp = (9 + 19 * far) * (1 + 0.45 * smooth(-10, -55, x) - 0.15 * smooth(25, 60, x));
  const nearBay = 1 - smooth(8, 22, Math.hypot(x + 31, z - 34.2));
  const rise = lerp(smooth(0.6, 30, d), smooth(0.3, 12, d), nearBay);
  let h = 0.24 + d * 0.03 + (m * amp + r * 5.5 * far) * rise + nearBay * smooth(0.5, 7, d) * 3;
  // the steep glacial walls around Emerald Bay (Maggie's Peaks), on the land side only
  h += (1 - smooth(7, 18, Math.hypot(x + 31, z - 34.2))) * smooth(1.2, 9, d) * smooth(-19, -25, x) * (8 + 4 * m);
  // Heavenly: a broad mountain south-east of town, its runs facing the lake
  const hx = x - 54, hz = z - 86;
  h += 22 * Math.exp(-(hx * hx + hz * hz) / (2 * 22 * 22)) * smooth(2, 18, d);
  // the town flats, with a gentle swell
  const f = flatMask(x, z);
  h = lerp(h, 0.35 + d * 0.01 + fbm(x * 0.08, z * 0.08, 2) * 0.12, f);
  // a rim far out, so the world never shows an edge before the fog does
  const rr = Math.hypot(x - 2, z - 8);
  h += smooth(125, 175, rr) * 24;
  return h;
}

export function landN(x, z) {
  const e = 0.6, hx = landH(x + e, z) - landH(x - e, z), hz = landH(x, z + e) - landH(x, z - e);
  const l = Math.hypot(hx, 2 * e, hz);
  return [-hx / l, (2 * e) / l, -hz / l];
}

// how thick the pine forest is here (0..1): a belt around the lake, gone on cliffs and high up, thinner in town
export function forest(x, z) {
  const h = landH(x, z); if (h < 0.55) return 0;
  const n = landN(x, z); if (n[1] < 0.72) return 0;
  const d = waterSD(x, z);
  let f = (1 - smooth(14, 24, h)) * (0.45 + 0.55 * smooth(1, 5, d)) * smooth(0.72, 0.86, n[1]);
  f *= 0.55 + 0.45 * smooth(-0.25, 0.35, fbm(x * 0.05 + 9, z * 0.05 - 4, 3));
  f *= 1 - 0.75 * flatMask(x, z);
  return clamp(f, 0, 1);
}

// the shore crossing walking from a point toward the lake (used to place the pier)
export function shoreAlong(x, z, dx, dz, step = 0.1, max = 70) {
  for (let t = 0; t < max; t += step) if (landH(x + dx * t, z + dz * t) < 0) return [x + dx * t, z + dz * t];
  return [x, z];
}

/* places, in world units */
const shoreZ = (x) => shoreAlong(x, 75, 0, -1)[1]; // the south shore, walking north from town
const TAU_ = Math.PI * 2;
// the point `inland` units from the outermost shore along a ray from the lake's middle (degrees: 0 east, 90 south)
export function placeAt(deg, inland = 1.5) {
  const th = (deg * Math.PI) / 180, ux = Math.cos(th), uz = Math.sin(th);
  let r = 100; while (r > 4 && waterSD(LAKE.cx + ux * r, LAKE.cz + uz * r) > inland) r -= 0.2;
  return [LAKE.cx + ux * r, LAKE.cz + uz * r];
}
export const P = {
  reno: [140, 34],
  cabin: [7, shoreZ(7) + 2.5],
  heavenlyBase: [34.5, 63],
  heavenlyTop: [52, 80],
  bay: [-31, 34.2],
  island: [-33, 35],
  tahoeCity: placeAt(-114, 1.8),
  sandHarbor: placeAt(-8, 1.0),
  spooner: [46, 13],
  nextCabin: [-13, shoreZ(-13) + 2.3],
  sledHill: [13, 80],
};
P.pierStart = [P.cabin[0], shoreZ(P.cabin[0]) + 0.9];
P.pierEnd = [P.cabin[0], shoreZ(P.cabin[0]) - 5.4];

/* the road around the lake (US-50, CA-89, NV-28): traced a fixed distance inland from the outermost shore, so it
   wraps Emerald Bay the way the real highway does, then smoothed; deeper inland through town */
function traceLoop() {
  const N = 200, raw = [];
  for (let i = 0; i < N; i++) {
    const deg = (i / N) * 360, th = (deg * Math.PI) / 180, uz = Math.sin(th);
    const inland = 2.7 + 3.2 * smooth(0.55, 0.9, uz) * smooth(-0.6, -0.2, Math.cos(th) * -1 + 0.3);
    raw.push(placeAt(deg, inland));
  }
  let pts = raw;
  for (let pass = 0; pass < 3; pass++) pts = pts.map((p, i) => { let x = 0, z = 0; for (let k = -2; k <= 2; k++) { const q = pts[(i + k + N) % N]; x += q[0]; z += q[1]; } return [x / 5, z / 5]; });
  return pts;
}
export const LOOP = traceLoop();
export const loopNear = (x, z) => { let b = 0, bd = 1e9; LOOP.forEach((p, i) => { const d = Math.hypot(p[0] - x, p[1] - z); if (d < bd) { bd = d; b = i; } }); return b; };
// the loop between two of its points, going the way the angle increases (east → south → west → north)
export const loopPath = (i0, i1) => { const out = []; const n = LOOP.length; for (let i = i0; ; i = (i + 1) % n) { out.push(LOOP[i]); if (i === i1) break; } return out; };
export const ROAD_LOOP = [...LOOP, LOOP[0]];
const iState = loopNear(30, 44);
P.stateline = LOOP[iState];
P.emerald = LOOP[loopNear(-29, 42.5)];
export const ROAD_RENO = [P.stateline, [P.stateline[0] + 10, P.stateline[1] - 2], [64, 46], [80, 42], [100, 38.5], [140, 34]];
const iHope = loopNear(12, 56);
export const ROAD_HOPE = [LOOP[iHope], [12.8, 62], [13.6, 68], [13.6, 74], P.sledHill];
const iSpoon = loopNear(37, 18);
export const ROAD_SPOONER = [LOOP[iSpoon], [41, 16], P.spooner];
export const IDX = { state: iState, hope: iHope, spoon: iSpoon, cabin: loopNear(P.cabin[0], P.cabin[1]), emerald: loopNear(P.emerald[0], P.emerald[1]), tahoe: loopNear(P.tahoeCity[0], P.tahoeCity[1]), sand: loopNear(P.sandHarbor[0], P.sandHarbor[1]), next: loopNear(P.nextCabin[0], P.nextCabin[1]) };
