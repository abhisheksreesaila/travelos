// The forest (F-206), after Meng To's threejs-landscape (MIT): instanced conifers with variation and snow on their branches, granite boulders, and a
// little wind, all shaped in the vertex shader so wind costs the CPU nothing. Tahoe's red and white firs are built tier by tier: drooping, jagged
// branch skirts round a tapering trunk, snow lying on whatever faces up (more on the trees that caught more). Close-up sets of crafted trees stand
// round the two places the camera comes close (the cabin and the pier); a light set of simple firs covers the rest of the south shore; beyond it the
// ground's own canopy shading carries the forest (terrain.js), by the same planting rule (data.js forestAt).
import { InstancedMesh, InstancedBufferAttribute, MeshLambertMaterial, IcosahedronGeometry, CylinderGeometry, Matrix4, Quaternion, Euler, Vector3, Color, Group, BufferGeometry, Float32BufferAttribute } from 'three';
import { mulberry32, clamp, lerp } from './core.js';
import { EXAG } from './data.js';

const BARK = 0x5a4130, NEEDLE = 0x35523d;

// One fir (Tahoe's red and white firs), unit height, base at 0, indexed so its normals are smooth: per tier an apex, a ring partway down and a
// star-shaped bottom edge, long at the branch tips and short between them, drooping at the tips, with a dark underside. Seeded per variant.
function firGeometry(tiers, seg, seed, opts = {}) {
  const rnd = mulberry32(seed), P = [], C = [], I = [], c = new Color();
  const v = (x, y, z, col, k = 1) => { P.push(x, y, z); c.set(col).multiplyScalar(k); C.push(c.r, c.g, c.b); return P.length / 3 - 1; };
  if (opts.trunk !== false) {
    const tb = [], tt = [];
    for (let i = 0; i < 7; i++) { const a = (i / 7) * Math.PI * 2; tb.push(v(Math.cos(a) * 0.04, -0.05, Math.sin(a) * 0.04, BARK)); tt.push(v(Math.cos(a) * 0.016, 0.42, Math.sin(a) * 0.016, BARK, 0.9)); }
    for (let i = 0; i < 7; i++) { const j = (i + 1) % 7; I.push(tb[i], tt[i], tb[j], tb[j], tt[i], tt[j]); }
  }
  for (let t = 0; t < tiers; t++) {
    const f = t / Math.max(1, tiers - 1);
    const yTop = 0.2 + f * 0.8 + 0.05, yBot = Math.max(0.1, yTop - (0.27 - f * 0.12));
    const rBot = (0.34 * Math.pow(1 - f * 0.92, 1.05) + 0.03) * (0.9 + rnd() * 0.2), rMid = rBot * 0.55;
    const shade = 0.82 + rnd() * 0.28;
    const apex = v(0, yTop, 0, NEEDLE, shade * 1.05);
    const mid = [], tip = [], n2 = seg * 2;
    for (let i = 0; i < seg; i++) { const a = (i / seg) * Math.PI * 2 + rnd() * 0.2; mid.push(v(Math.cos(a) * rMid, lerp(yTop, yBot, 0.5) + rnd() * 0.01, Math.sin(a) * rMid, NEEDLE, shade)); }
    for (let i = 0; i < n2; i++) {
      const a = (i / n2) * Math.PI * 2 + rnd() * 0.12, long = i % 2 === 0, r = rBot * (long ? 0.94 + rnd() * 0.16 : 0.66 + rnd() * 0.12);
      const y = yBot - (long ? 0.02 + rnd() * 0.03 + r * 0.1 : 0.005);
      tip.push(v(Math.cos(a) * r, y, Math.sin(a) * r, NEEDLE, shade * (long ? 0.95 : 0.85)));
    }
    for (let i = 0; i < seg; i++) I.push(apex, mid[(i + 1) % seg], mid[i]);
    for (let i = 0; i < seg; i++) {
      const m0 = mid[i], m1 = mid[(i + 1) % seg], a = tip[i * 2], b = tip[i * 2 + 1], d = tip[(i * 2 + 2) % n2];
      I.push(m0, m1, b, m0, b, a, m1, d, b);
    }
    if (opts.under !== false) { const cu = v(0, yBot + 0.04, 0, NEEDLE, 0.45); for (let i = 0; i < n2; i++) I.push(tip[i], tip[(i + 1) % n2], cu); }
  }
  const g = new BufferGeometry();
  g.setAttribute('position', new Float32BufferAttribute(P, 3)); g.setAttribute('color', new Float32BufferAttribute(C, 3)); g.setIndex(I);
  g.computeVertexNormals(); g.computeBoundingSphere();
  return g;
}

// The far firs: two plain cones of `seg` sides (10 triangles), enough for a tree a few pixels tall that still holds snow on top.
function coneTree(tiers, seg, seed) {
  const rnd = mulberry32(seed), P = [], C = [], I = [], c = new Color();
  for (let t = 0; t < tiers; t++) {
    const f = t / Math.max(1, tiers - 1), yTop = 0.45 + f * 0.6, yBot = 0.12 + f * 0.42, r = 0.32 * (1 - f * 0.55);
    const k = P.length / 3; c.set(NEEDLE).multiplyScalar(0.9 + rnd() * 0.2);
    P.push(0, yTop, 0); C.push(c.r, c.g, c.b);
    for (let i = 0; i < seg; i++) { const a = (i / seg) * Math.PI * 2; P.push(Math.cos(a) * r, yBot, Math.sin(a) * r); C.push(c.r * 0.85, c.g * 0.85, c.b * 0.85); }
    for (let i = 0; i < seg; i++) I.push(k, k + 1 + ((i + 1) % seg), k + 1 + i);
  }
  const g = new BufferGeometry();
  g.setAttribute('position', new Float32BufferAttribute(P, 3)); g.setAttribute('color', new Float32BufferAttribute(C, 3)); g.setIndex(I);
  g.computeVertexNormals(); g.computeBoundingSphere();
  return g;
}

// One Jeffrey pine: a tall bare trunk and an open, clumped crown of needle tufts, each tuft a jittered, flattened ball that holds snow on top.
function pineGeometry(seed, tufts = 9, detail = 1) {
  const rnd = mulberry32(seed), parts = [];
  const trunk = new IcosahedronGeometry(1, 0);
  const tb = cylGeo(0.022, 0.034, 0.72, 7); tb.translate(0, 0.33, 0); paint(tb, BARK, 1); parts.push(tb);
  for (let k = 0; k < tufts; k++) {
    const h = 0.48 + rnd() * 0.5, a = rnd() * Math.PI * 2, rr = (1 - h) * 0.36 + 0.03 + rnd() * 0.05;
    const g = new IcosahedronGeometry(0.1 + rnd() * 0.07, detail);
    const pp = g.attributes.position;
    for (let i = 0; i < pp.count; i++) { const f = 0.8 + rnd() * 0.4; pp.setXYZ(i, pp.getX(i) * f * 1.25, pp.getY(i) * f * 0.62, pp.getZ(i) * f * 1.25); }
    g.translate(Math.cos(a) * rr, h, Math.sin(a) * rr); paint(g, NEEDLE, 0.85 + rnd() * 0.3); parts.push(g);
  }
  trunk.dispose();
  return mergeGeos(parts);
}
function cylGeo(rt, rb, h, seg) { const g = new CylinderGeometry(rt, rb, h, seg, 1, true); return g; }
function paint(g, hex, k) { const col = new Color(hex).multiplyScalar(k), n = g.attributes.position.count, a = new Float32Array(n * 3); for (let i = 0; i < n; i++) a.set([col.r, col.g, col.b], i * 3); g.setAttribute('color', new Float32BufferAttribute(a, 3)); }
function mergeGeos(list) {
  let nv = 0, ni = 0; for (const g of list) { nv += g.attributes.position.count; ni += g.index ? g.index.count : g.attributes.position.count; }
  const P = new Float32Array(nv * 3), N = new Float32Array(nv * 3), C = new Float32Array(nv * 3), I = []; let o = 0;
  for (const g of list) {
    if (!g.attributes.normal) g.computeVertexNormals();
    P.set(g.attributes.position.array, o * 3); N.set(g.attributes.normal.array, o * 3); C.set(g.attributes.color.array, o * 3);
    if (g.index) for (const k of g.index.array) I.push(k + o); else for (let k = 0; k < g.attributes.position.count; k++) I.push(k + o);
    o += g.attributes.position.count;
  }
  const out = new BufferGeometry();
  out.setAttribute('position', new Float32BufferAttribute(P, 3)); out.setAttribute('normal', new Float32BufferAttribute(N, 3)); out.setAttribute('color', new Float32BufferAttribute(C, 3)); out.setIndex(I);
  out.computeBoundingSphere();
  return out;
}

// a Lambert material taught to sway, to keep snow on upward faces, and to fade with distance
function treeMaterial(U, key) {
  const m = new MeshLambertMaterial({ vertexColors: true });
  m.userData.snowScale = 1;
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, { uTime: U.uTime, uWind: U.uWind, uSnowCol: U.uSnowCol, uCamPos: U.uCam, uFar: U.uFar, uSnowScale: { value: m.userData.snowScale } });
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', `#include <common>
        attribute vec4 aVar; uniform float uTime, uFar; uniform vec2 uWind; uniform vec3 uCamPos; varying float vSnow; varying float vUp; varying float vH; varying float vTint;`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        float sway = position.y * position.y;
        transformed.x += (sin(uTime * 0.85 + aVar.z) * 0.010 + sin(uTime * 2.6 + aVar.z * 3.1 + position.y * 6.0) * 0.0035) * sway * uWind.x;
        transformed.z += (cos(uTime * 0.7 + aVar.z * 1.7) * 0.008) * sway * uWind.y;
        vec3 ip = (instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
        float far = distance(ip, uCamPos);
        transformed *= 1.0 - smoothstep(uFar * 0.85, uFar, far);
        vSnow = aVar.x * (0.55 + 0.9 * fract(sin(dot(floor(position * 9.0 + aVar.z), vec3(12.9898, 78.233, 37.719))) * 43758.5453));   // clumps, fixed to the branch
        vTint = aVar.y; vH = position.y;
        vUp = normalize(mat3(instanceMatrix) * objectNormal).y;`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>
        uniform vec3 uSnowCol; uniform float uSnowScale; varying float vSnow; varying float vUp; varying float vH; varying float vTint;`)
      .replace('#include <color_fragment>', `#include <color_fragment>
        diffuseColor.rgb *= 0.86 + vTint * 0.28;
        float snow = clamp(smoothstep(0.05, 0.5, vUp) * vSnow * 1.15 * uSnowScale, 0.0, 1.0) * step(0.3, vH + 0.25);
        diffuseColor.rgb = mix(diffuseColor.rgb, uSnowCol, snow * 0.92);`);
  };
  m.customProgramCacheKey = () => key;
  return m;
}

function place(mesh, list, extra) {
  const mtx = new Matrix4(), q = new Quaternion(), e = new Euler(), p = new Vector3(), s = new Vector3();
  const vars = new Float32Array(list.length * 4);
  list.forEach((t, i) => {
    e.set(t.lean * Math.cos(t.rot), t.rot, t.lean * Math.sin(t.rot));
    q.setFromEuler(e); p.set(t.x, t.y, t.z); s.set(t.w * t.h, t.h, t.w * t.h);
    mtx.compose(p, q, s); mesh.setMatrixAt(i, mtx);
    vars.set([t.snow, t.tint, t.phase, 0], i * 4);
  });
  mesh.count = list.length;
  mesh.geometry.setAttribute('aVar', new InstancedBufferAttribute(vars, 4));
  mesh.instanceMatrix.needsUpdate = true;
  mesh.computeBoundingSphere();
  return mesh;
}

export function buildForest(T, q, U, keep) {
  const group = new Group();
  const P = T.places;
  const rnd = mulberry32(77);
  // where trees never grow: Heavenly's ski runs (white stripes down the dark slope), the roads, the cabin's clearing, the pier
  const runs = heavenlyRuns(P);
  const roads = T.geo.roads.filter((r) => r.pts.some(([x, z]) => x > -12000 && x < 9000 && z > -3000 && z < 10000));
  const clear = (x, z) => {
    for (const r of runs) if (segDist(r, x, z) < 26) return true;
    for (const r of roads) if (segDist(r.pts, x, z) < 14) return true;
    for (const c of keep) if (c.a ? segDist([c.a, c.b], x, z) < c.r : Math.hypot(x - c[0], z - c[1]) < c[2]) return true;   // clearings, and corridors a close-up camera looks along
    return false;
  };
  const tree = (x, z, h0, r) => {
    const dens = T.forestAt(x, z);
    if (r() > dens * 0.95 || clear(x, z)) return null;
    const hm = T.ground(x, z);
    const h = (h0 * (0.6 + r() * 0.75)) * (1 - clamp((hm - 500) / 600, 0, 0.55));
    return { x, z, y: T.landH(x, z) - 0.6, h, w: 0.78 + r() * 0.42, rot: r() * 6.283, lean: (r() - 0.5) * 0.06, snow: 0.55 + r() * 0.45, tint: r(), phase: r() * 40 };
  };
  const grid = (cx, cz, R, cell, h0, skip) => {
    const out = [];
    for (let gz = Math.floor((cz - R) / cell); gz <= Math.ceil((cz + R) / cell); gz++) {
      for (let gx = Math.floor((cx - R) / cell); gx <= Math.ceil((cx + R) / cell); gx++) {
        const r = mulberry32(((gx * 73856093) ^ (gz * 19349663) ^ (cell * 83492791)) >>> 0);
        const x = (gx + r()) * cell, z = (gz + r()) * cell;
        if (Math.hypot(x - cx, z - cz) > R || (skip && skip(x, z))) continue;
        const t = tree(x, z, h0, r); if (t) out.push(t);
      }
    }
    return out;
  };
  // the close-up sets, one per place the camera comes close to (the cabin, the pier, the next cabin), each shown only near its place:
  // crafted firs and pines within craftR of the subject, lighter ones out to heroR
  const hero = [[P.cabin, q.heroR], [[0, 0], q.heroR * 0.8], [P.nextCabin, q.heroR * 0.55]];
  const inHero = (x, z) => hero.some(([c, R]) => Math.hypot(x - c[0], z - c[1]) < R);
  const nearMat = treeMaterial(U, 'cover-fir-near');
  const pine = (t) => (t.phase * 7.3) % 1 < 0.3;
  const geos = { craftA: firGeometry(10, 9, 3), craftB: firGeometry(9, 8, 11), craftP: pineGeometry(7, 11, 1), lightF: firGeometry(5, 6, 13, { under: false }), lightP: pineGeometry(19, 6, 0) };
  const seen = new Set();
  let nearCount = 0;
  hero.forEach(([c, R], hi) => {
    const trees = grid(c[0], c[1], R, q.heroCell, 30).filter((t) => { const k = `${Math.round(t.x)},${Math.round(t.z)}`; if (seen.has(k)) return false; seen.add(k); return true; });
    nearCount += trees.length;
    const close = (t) => Math.hypot(t.x - c[0], t.z - c[1]) < q.craftR;
    const crafted = trees.filter(close), lighter = trees.filter((t) => !close(t));
    const sets = [[geos.craftA, crafted.filter((t, i) => !pine(t) && i % 2 === 0), true], [geos.craftB, crafted.filter((t, i) => !pine(t) && i % 2 === 1), true], [geos.craftP, crafted.filter(pine), true],
      [geos.lightF, lighter.filter((t) => !pine(t)), false], [geos.lightP, lighter.filter(pine), false]];
    for (const [g, list, cast] of sets) {
      if (!list.length) continue;
      const m = place(new InstancedMesh(g, nearMat, list.length), list.map((t) => (pine(t) ? { ...t, h: t.h * 0.95, w: t.w * 1.1 } : t)));
      m.castShadow = cast; m.receiveShadow = true; m.userData.hero = true; m.userData.center = c; m.userData.R = R;     // only the crafted trees round the subject cast shadows
      group.add(m);
    }
  });
  // the south shore's forest: simple firs, faded out past uFar
  const [x0, z0, x1, z1] = q.forestBox;
  const mid = [];
  const cell = q.midCell;
  for (let gz = Math.floor(z0 / cell); gz <= Math.ceil(z1 / cell); gz++) {
    for (let gx = Math.floor(x0 / cell); gx <= Math.ceil(x1 / cell); gx++) {
      const r = mulberry32(((gx * 2654435761) ^ (gz * 40503)) >>> 0);
      const x = (gx + r()) * cell, z = (gz + r()) * cell;
      if (inHero(x, z)) continue;
      const t = tree(x, z, 26, r); if (t) mid.push(t);
    }
  }
  const midMat = treeMaterial(U, 'cover-fir-mid');
  midMat.userData.snowScale = 0.25;                                 // a tree a few pixels tall shows its dark needles, not the snow on its top
  const midMesh = place(new InstancedMesh(coneTree(2, 5, 5), midMat, Math.max(1, mid.length)), mid);
  midMesh.userData.mid = true;
  group.add(midMesh);
  // granite boulders on the shore and the slopes near the camera's close-ups
  const rocks = [];
  for (const [c, R] of hero) {
    for (let i = 0; i < q.rocks; i++) {
      const a = rnd() * 6.283, d = Math.sqrt(rnd()) * R, x = c[0] + Math.cos(a) * d, z = c[1] + Math.sin(a) * d;
      const sd = T.shore(x, z);
      if (sd < 1.5 || (sd > 40 && rnd() > 0.35 + T.slopeAt(x, z))) continue;
      const s = 0.5 + Math.pow(rnd(), 2.2) * (sd < 25 ? 2.6 : 1.6);
      rocks.push({ x, z, y: Math.max(T.landH(x, z), T.waterY(x, z) ?? -1e9) - s * 0.35, s, rot: rnd() * 6.283 });
    }
  }
  const rg = new IcosahedronGeometry(1, 1);
  const rp = rg.attributes.position, rr = mulberry32(5);
  for (let i = 0; i < rp.count; i++) { const f = 0.78 + rr() * 0.4; rp.setXYZ(i, rp.getX(i) * f * 1.15, rp.getY(i) * f * 0.62, rp.getZ(i) * f); }
  rg.computeVertexNormals();
  const rockMat = new MeshLambertMaterial({ color: 0x8b867e });
  rockMat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, { uSnowCol: U.uSnowCol });
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying float vUp;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvUp = normalize(mat3(instanceMatrix) * objectNormal).y;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nuniform vec3 uSnowCol; varying float vUp;')
      .replace('#include <color_fragment>', '#include <color_fragment>\nfloat sn = smoothstep(0.35, 0.7, vUp + (fract(sin(dot(floor(gl_FragCoord.xy*0.5), vec2(12.9898,78.233)))*43758.5453) - 0.5) * 0.2);\ndiffuseColor.rgb = mix(diffuseColor.rgb * (0.8 + 0.3 * fract(vUp * 13.0)), uSnowCol, sn * 0.95);');
  };
  rockMat.customProgramCacheKey = () => 'cover-rock';
  const rockMesh = new InstancedMesh(rg, rockMat, Math.max(1, rocks.length));
  const mtx = new Matrix4(), qq = new Quaternion(), ee = new Euler();
  rocks.forEach((o, i) => { ee.set(0, o.rot, 0); qq.setFromEuler(ee); mtx.compose(new Vector3(o.x, o.y, o.z), qq, new Vector3(o.s, o.s, o.s)); rockMesh.setMatrixAt(i, mtx); });
  rockMesh.count = rocks.length; rockMesh.castShadow = rockMesh.receiveShadow = true; rockMesh.userData.rocks = true; rockMesh.computeBoundingSphere();
  group.add(rockMesh);
  group.userData = { near: nearCount, mid: mid.length, rocks: rocks.length };
  group.runs = runs;
  return group;
}

function segDist(pts, x, z) {
  let best = 1e9;
  for (let i = 0; i < pts.length - 1; i++) {
    const [ax, az] = pts[i], [bx, bz] = pts[i + 1], dx = bx - ax, dz = bz - az;
    const t = clamp(((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz || 1), 0, 1);
    best = Math.min(best, Math.hypot(ax + t * dx - x, az + t * dz - z));
  }
  return best;
}

// a few of Heavenly's runs, from the summit ridge down to California Lodge and toward the gondola, curving with the fall line
export function heavenlyRuns(P) {
  const top = P.heavenlyTop, base = P.heavenly, out = [];
  const ends = [[base[0] - 150, base[1] + 80], [base[0] + 220, base[1] - 260], [base[0] - 520, base[1] - 400], [base[0] + 600, base[1] + 120], [base[0] - 900, base[1] - 900], [base[0] + 900, base[1] - 700]];
  ends.forEach((e, i) => {
    const pts = [], s = mulberry32(31 + i);
    for (let k = 0; k <= 14; k++) {
      const t = k / 14, w = Math.sin(t * Math.PI) * (s() - 0.5) * 900;
      pts.push([lerp(top[0], e[0], t) + w * 0.6, lerp(top[1], e[1], t) + w * 0.4]);
    }
    out.push(pts);
  });
  return out;
}
