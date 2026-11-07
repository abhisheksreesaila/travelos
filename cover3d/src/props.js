// What people made (F-206), at true size and crafted rather than boxed (Meng To's 3d-high-poly-models, MIT): proportions first, then a rounded arris on
// every edge so it catches the light, curve segments where the camera looks, boards that each carry their own grain (wood.js). The family's cabin
// up Ski Run Boulevard, the pier at its lake end, the family's SUV, the family, the next family's cabin, the towns' houses along the real roads with
// their windows lit at night, Heavenly's gondola, and the roads themselves, draped over the ground.
import {
  BufferGeometry, Float32BufferAttribute, BoxGeometry, CylinderGeometry, SphereGeometry, LatheGeometry, TorusGeometry, ConeGeometry, Mesh, Group, InstancedMesh,
  InstancedBufferAttribute, MeshStandardMaterial, MeshPhysicalMaterial, MeshLambertMaterial, ShaderMaterial, Points, Vector2, Vector3, Matrix4, Quaternion, Euler, Color,
  AdditiveBlending, DoubleSide,
} from 'three';
import { M, mulberry32, clamp, lerp, Spring } from './core.js';
import { woodMaterial } from './wood.js';

/* ---------------------------------------------------------------- geometry helpers */
// a box with rounded edges and corners (the RoundedBox construction): every vertex of a subdivided box is pulled to the inner box, then pushed out r
export function roundedBox(w, h, d, r, seg = 2) {
  const g = new BoxGeometry(1, 1, 1, seg * 2 + 1, seg * 2 + 1, seg * 2 + 1);
  r = Math.min(r, w / 2 - 1e-4, h / 2 - 1e-4, d / 2 - 1e-4);
  const p = g.attributes.position, n = g.attributes.normal, hw = w / 2 - r, hh = h / 2 - r, hd = d / 2 - r, v = new Vector3(), c = new Vector3();
  for (let i = 0; i < p.count; i++) {
    v.set(p.getX(i) * w, p.getY(i) * h, p.getZ(i) * d);
    c.set(clamp(v.x, -hw, hw), clamp(v.y, -hh, hh), clamp(v.z, -hd, hd));
    const off = v.clone().sub(c);
    if (off.lengthSq() < 1e-12) off.set(n.getX(i), n.getY(i), n.getZ(i));
    off.normalize();
    p.setXYZ(i, c.x + off.x * r, c.y + off.y * r, c.z + off.z * r);
    n.setXYZ(i, off.x, off.y, off.z);
  }
  return g;
}

// merges parts into one geometry: position, normal, colour, and the wood attributes (grain axis, seed) the timber shader reads
class Kit {
  constructor() { this.p = []; this.n = []; this.c = []; this.w = []; }
  add(geo, matrix, color = 0xffffff, axis = 1, seed = 0) {
    const g = (geo.index ? geo.toNonIndexed() : geo.clone());
    if (matrix) g.applyMatrix4(matrix);
    if (!g.attributes.normal) g.computeVertexNormals();
    const P = g.attributes.position.array, N = g.attributes.normal.array, col = new Color(color);
    for (let i = 0; i < P.length; i += 3) { this.p.push(P[i], P[i + 1], P[i + 2]); this.n.push(N[i], N[i + 1], N[i + 2]); this.c.push(col.r, col.g, col.b); this.w.push(axis, seed); }
    return this;
  }
  geometry() {
    const g = new BufferGeometry();
    g.setAttribute('position', new Float32BufferAttribute(this.p, 3)); g.setAttribute('normal', new Float32BufferAttribute(this.n, 3));
    g.setAttribute('color', new Float32BufferAttribute(this.c, 3)); g.setAttribute('aWood', new Float32BufferAttribute(this.w, 2));
    g.computeBoundingSphere();
    return g;
  }
}

// snow: soft, bright, a little blue in its own shadow, sparkling where it faces the light
export function snowMaterial() {
  return new MeshStandardMaterial({ color: 0xf6f9fd, roughness: 0.82, metalness: 0, emissive: 0x2a3550, emissiveIntensity: 0.06 });
}
// glass that lights up from inside at dusk
function glassMaterial(U) {
  const m = new MeshStandardMaterial({ color: 0x141a22, roughness: 0.08, metalness: 0.2, emissive: 0xffb45c, emissiveIntensity: 0 });
  m.userData.glow = true;
  return m;
}

/* ---------------------------------------------------------------- the cabin */
// A Tahoe chalet, about 10 x 8 m: board-and-batten cedar on a stone base, a steep gable roof under a thick cap of snow with icicles on the eaves,
// a big glazed gable facing downhill, a deck on posts, a chimney of rounded stones with its smoke. Built facing +z, set by `placeCabin`.
export function buildCabin(renderer, opts = {}) {
  const rnd = mulberry32(opts.seed ?? 7), W = 10, D = 8, wallH = 3.1, pitch = 0.78, roofRise = (W / 2) * Math.tan(pitch) * 0.62;
  const siding = new Kit(), stone = new Kit(), trim = new Kit(), snow = new Kit(), glass = new Kit(), dark = new Kit();
  let seed = 1;
  // stone base
  for (let x = -W / 2; x < W / 2; x += 0.62) for (const z of [-D / 2, D / 2]) stone.add(roundedBox(0.6, 0.46 + rnd() * 0.12, 0.42, 0.08, 1), M(x + 0.3, 0.26, z), lerpGrey(rnd));
  for (let z = -D / 2; z < D / 2; z += 0.62) for (const x of [-W / 2, W / 2]) stone.add(roundedBox(0.42, 0.46 + rnd() * 0.12, 0.6, 0.08, 1), M(x, 0.26, z + 0.3), lerpGrey(rnd));
  // walls: vertical cedar boards with battens over the joints
  const board = (len, x, y, z, ry) => { siding.add(roundedBox(0.19, len, 0.04, 0.012, 1), M(x, y, z, 0, ry), 0xffffff, 1, seed++ * 0.37); };
  for (let x = -W / 2 + 0.1; x < W / 2; x += 0.2) { board(wallH, x, 0.5 + wallH / 2, D / 2, 0); board(wallH, x, 0.5 + wallH / 2, -D / 2, 0); }
  for (let z = -D / 2 + 0.1; z < D / 2; z += 0.2) {
    for (const sx of [-1, 1]) {
      const gable = Math.max(0, (1 - Math.abs(z) / (D / 2)) * roofRise * 1.0);
      board(wallH + gable, sx * W / 2, 0.5 + (wallH + gable) / 2, z, Math.PI / 2);
    }
  }
  // the glazed gable on the front (+z): a tall window wall under the ridge, framed in red trim
  const gw = 4.4, gh = wallH + roofRise * 0.55;
  glass.add(new BoxGeometry(gw, gh - 0.6, 0.03), M(0, 0.5 + (gh - 0.6) / 2 + 0.25, D / 2 + 0.04));
  for (let i = 0; i <= 4; i++) trim.add(roundedBox(0.09, gh - 0.4, 0.1, 0.02, 1), M(-gw / 2 + (i * gw) / 4, 0.5 + (gh - 0.4) / 2 + 0.15, D / 2 + 0.06), 0xffffff, 1, seed++ * 0.31);
  for (const y of [0.65, 0.5 + wallH * 0.62, 0.5 + gh - 0.2]) trim.add(roundedBox(gw + 0.12, 0.09, 0.1, 0.02, 1), M(0, y, D / 2 + 0.06), 0xffffff, 0, seed++ * 0.29);
  // side windows
  for (const [x, z, ry] of [[-W / 2 - 0.03, -1.6, Math.PI / 2], [-W / 2 - 0.03, 1.6, Math.PI / 2], [W / 2 + 0.03, 0, Math.PI / 2], [-2.6, -D / 2 - 0.03, 0], [2.6, -D / 2 - 0.03, 0]]) {
    glass.add(new BoxGeometry(1.3, 1.4, 0.03), M(x, 2.2, z, 0, ry));
    trim.add(roundedBox(1.5, 0.1, 0.12, 0.02, 1), M(x, 1.45, z, 0, ry), 0xffffff, 0, seed++);
    trim.add(roundedBox(1.5, 0.1, 0.12, 0.02, 1), M(x, 2.95, z, 0, ry), 0xffffff, 0, seed++);
  }
  // the roof: two planes of dark standing-seam metal, each under a thick rounded cap of snow that overhangs the eaves
  const slopeLen = (W / 2 + 0.7) / Math.cos(pitch * 0.62), ridgeY = 0.5 + wallH + roofRise;
  for (const s of [-1, 1]) {
    const ang = s * pitch * 0.62;
    const cx = s * (slopeLen / 2) * Math.cos(pitch * 0.62), cy = ridgeY - (slopeLen / 2) * Math.sin(pitch * 0.62);
    dark.add(roundedBox(slopeLen, 0.18, D + 1.4, 0.04, 1), M(cx, cy, 0, 0, 0, -ang), 0x2c2f33);
    snow.add(roundedBox(slopeLen + 0.25, 0.55, D + 1.55, 0.24, 3), M(cx + s * 0.08, cy + 0.34, 0, 0, 0, -ang));
    // icicles along the eave
    const eaveX = s * (slopeLen * Math.cos(pitch * 0.62)), eaveY = ridgeY - slopeLen * Math.sin(pitch * 0.62);
    for (let z = -D / 2 - 0.5; z < D / 2 + 0.6; z += 0.22 + rnd() * 0.25) {
      const L = 0.12 + Math.pow(rnd(), 2) * 0.6;
      glass.add(new ConeGeometry(0.035, L, 5), M(eaveX - s * 0.05, eaveY - L / 2 - 0.05, z, Math.PI, 0, 0));
    }
  }
  snow.add(new CylinderGeometry(0.34, 0.34, D + 1.55, 10), M(0, ridgeY + 0.5, 0, Math.PI / 2, 0, 0));   // the snow's rounded ridge
  // the deck on posts, downhill in front of the window wall, with a railing
  const dz = D / 2 + 1.7;
  for (let x = -W / 2 + 0.6; x <= W / 2 - 0.5; x += 0.16) siding.add(roundedBox(0.14, 0.05, 3.2, 0.01, 1), M(x, 0.45, dz), 0xffffff, 2, seed++ * 0.41);
  for (const x of [-W / 2 + 0.6, 0, W / 2 - 0.6]) for (const z of [dz - 1.5, dz + 1.5]) siding.add(roundedBox(0.16, 1.4, 0.16, 0.02, 1), M(x, -0.25, z), 0xffffff, 1, seed++ * 0.5);
  for (let x = -W / 2 + 0.6; x <= W / 2 - 0.6; x += 0.5) trim.add(roundedBox(0.06, 0.95, 0.06, 0.012, 1), M(x, 0.95, dz + 1.55), 0xffffff, 1, seed++);
  trim.add(roundedBox(W - 1.0, 0.08, 0.12, 0.02, 1), M(0, 1.45, dz + 1.55), 0xffffff, 0, seed++);
  snow.add(roundedBox(W - 1.1, 0.12, 0.2, 0.05, 2), M(0, 1.54, dz + 1.55));
  snow.add(roundedBox(W - 1.4, 0.16, 3.0, 0.07, 2), M(0, 0.55, dz - 0.05));
  // the chimney: rounded stones stacked up the side wall and above the roof
  for (let y = 0.2; y < ridgeY + 1.6; y += 0.36) for (let k = 0; k < 2; k++) stone.add(roundedBox(0.55 + rnd() * 0.18, 0.32, 0.5, 0.07, 1), M(W / 2 + 0.38, y, -1.4 + (k - 0.5) * 0.58 + (rnd() - 0.5) * 0.06), lerpGrey(rnd));
  snow.add(roundedBox(0.9, 0.16, 1.4, 0.07, 2), M(W / 2 + 0.38, ridgeY + 1.72, -1.4));
  // the door under the deck's roofline
  trim.add(roundedBox(1.05, 2.1, 0.08, 0.02, 1), M(W / 2 - 1.4, 1.55, D / 2 + 0.03), 0xffffff, 1, seed++);

  const g = new Group();
  const woodC = woodMaterial(renderer, opts.wood || 'cedar');
  const trimM = woodMaterial(renderer, 'trim');
  const parts = [
    [siding.geometry(), woodC], [trim.geometry(), trimM], [stone.geometry(), new MeshStandardMaterial({ vertexColors: true, roughness: 0.92 })],
    [dark.geometry(), new MeshStandardMaterial({ vertexColors: true, roughness: 0.5, metalness: 0.4 })], [snow.geometry(), snowMaterial()], [glass.geometry(), glassMaterial()],
  ];
  for (const [geo, mat] of parts) { const m = new Mesh(geo, mat); m.castShadow = true; m.receiveShadow = true; g.add(m); }
  g.userData.glass = parts[5][1];
  g.userData.chimney = new Vector3(W / 2 + 0.38, ridgeY + 1.9, -1.4);
  g.userData.size = [W, D];
  return g;
}
const lerpGrey = (r) => new Color().setHSL(0.08, 0.06, 0.38 + r() * 0.2).getHex();

/* ---------------------------------------------------------------- the pier */
// 110 m of weathered planks on paired pilings straight out from the shore, a wider platform at the end with a bench and a lamp. Built along +z.
export function buildPier(renderer, len = 110, q = {}) {
  const deck = new Kit(), piles = new Kit(), metal = new Kit(), snow = new Kit(), glow = new Kit();
  const wDeck = 2.4, y = 1.35, rnd = mulberry32(19);
  const pw = q.planks === false ? 0.6 : 0.152;
  let seed = 3;
  for (let z = 0.2; z < len; z += pw) {
    const wide = z > len - 6 ? 6.2 : wDeck;
    const g = q.planks === false ? new BoxGeometry(wide, 0.05, pw - 0.02) : roundedBox(wide - rnd() * 0.04, 0.045, pw - 0.012, 0.01, 1);
    deck.add(g, M((rnd() - 0.5) * 0.02, y, z, 0, (rnd() - 0.5) * 0.006, 0), 0xffffff, 0, seed++ * 0.613);
  }
  for (const x of [-wDeck / 2 + 0.12, wDeck / 2 - 0.12]) deck.add(roundedBox(0.16, 0.3, len - 6, 0.02, 1), M(x, y - 0.2, (len - 6) / 2), 0xffffff, 2, seed++);
  for (const x of [-3, 3]) deck.add(roundedBox(0.16, 0.3, 6.2, 0.02, 1), M(x, y - 0.2, len - 3.1), 0xffffff, 2, seed++);
  const pileGeo = new CylinderGeometry(0.15, 0.17, 1, 10);
  for (let z = 1.5; z < len; z += 3.6) {
    const xs = z > len - 6 ? [-3, -1.1, 1.1, 3] : [-wDeck / 2 + 0.05, wDeck / 2 - 0.05];
    for (const x of xs) piles.add(pileGeo, M(x, y / 2 - 3.4, z, (rnd() - 0.5) * 0.02, rnd() * 3, 0, 1, y + 6.8, 1), 0xffffff, 1, seed++ * 0.27);
  }
  // the bench and the lamp at the end
  for (let k = 0; k < 4; k++) deck.add(roundedBox(1.8, 0.04, 0.13, 0.01, 1), M(-1.8, y + 0.47, len - 2.2 + k * 0.15), 0xffffff, 0, seed++);
  for (const x of [-2.55, -1.05]) for (const dz of [-0.2, 0.2]) metal.add(roundedBox(0.045, 0.46, 0.045, 0.01, 1), M(x, y + 0.24, len - 2 + dz), 0x3a3d42);   // cast-iron legs, front and back
  metal.add(new CylinderGeometry(0.05, 0.07, 3.6, 10), M(2.6, y + 1.8, len - 0.6), 0x26282b);
  metal.add(roundedBox(0.34, 0.08, 0.34, 0.02, 1), M(2.6, y + 3.95, len - 0.6), 0x26282b);
  glow.add(new CylinderGeometry(0.13, 0.11, 0.42, 10), M(2.6, y + 3.7, len - 0.6));
  // snow drifted along the deck's edges and on the bench; the middle has been walked clear
  for (let z = 1; z < len - 6; z += 1.6 + rnd()) for (const s of [-1, 1]) snow.add(roundedBox(0.36 + rnd() * 0.2, 0.06 + rnd() * 0.05, 1.3 + rnd() * 0.8, 0.03, 2), M(s * (wDeck / 2 - 0.22), y + 0.04, z));
  snow.add(roundedBox(1.7, 0.06, 0.55, 0.03, 2), M(-1.8, y + 0.52, len - 2));
  const g = new Group();
  const woodP = woodMaterial(renderer, 'pier');
  woodP.userData.snow = 0;
  const pileM = woodMaterial(renderer, 'log');
  pileM.onBeforeCompile = ((orig) => (sh) => { orig(sh); sh.fragmentShader = sh.fragmentShader.replace('#include <map_fragment>', '#include <map_fragment>\ndiffuseColor.rgb *= mix(vec3(0.42, 0.45, 0.36), vec3(1.0), smoothstep(-0.1, 0.35, vWP.y));'); })(pileM.onBeforeCompile);
  const parts = [[deck.geometry(), woodP], [piles.geometry(), pileM], [metal.geometry(), new MeshStandardMaterial({ vertexColors: true, roughness: 0.55, metalness: 0.35 })], [snow.geometry(), snowMaterial()]];
  parts.forEach(([geo, mat], k) => { const m = new Mesh(geo, mat); m.castShadow = k >= 2; m.receiveShadow = true; g.add(m); });     // nothing under the deck takes a shadow, so the boards and piles cast none
  const lamp = new MeshStandardMaterial({ color: 0xfff1d0, emissive: 0xffc77a, emissiveIntensity: 0.2, roughness: 0.3 });
  g.add(new Mesh(glow.geometry(), lamp));
  g.userData = { lamp, deckY: y, len };
  return g;
}

/* ---------------------------------------------------------------- the family's SUV */
export function buildCar(color = 0x15803d) {
  const body = new Kit(), dark = new Kit(), chrome = new Kit(), snow = new Kit(), glassK = new Kit(), lightsF = new Kit(), lightsR = new Kit();
  body.add(roundedBox(4.7, 0.78, 1.9, 0.18, 3), M(0, 0.78, 0), color);
  body.add(roundedBox(2.95, 0.62, 1.74, 0.16, 3), M(-0.35, 1.42, 0), color);
  glassK.add(roundedBox(2.75, 0.5, 1.78, 0.12, 2), M(-0.35, 1.44, 0));
  glassK.add(roundedBox(0.08, 0.46, 1.6, 0.03, 1), M(1.12, 1.4, 0, 0, 0, 0.55));
  dark.add(roundedBox(4.78, 0.22, 1.94, 0.08, 1), M(0, 0.42, 0), 0x202326);
  for (const x of [-1.45, 1.45]) for (const z of [-0.86, 0.86]) {
    dark.add(roundedBox(1.0, 0.5, 0.2, 0.1, 2), M(x, 0.68, z * 1.04), 0x1b1d20);
    const tire = new LatheGeometry([0.2, 0.33, 0.37, 0.38, 0.38, 0.37, 0.33, 0.2].map((r, i) => new Vector2(r, (i / 7 - 0.5) * 0.27)), 20);
    dark.add(tire, M(x, 0.38, z, Math.PI / 2, 0, 0), 0x16171a);
    chrome.add(new CylinderGeometry(0.22, 0.22, 0.28, 16), M(x, 0.38, z * 1.01, Math.PI / 2, 0, 0), 0xb8bcc2);
  }
  dark.add(roundedBox(1.9, 0.1, 1.5, 0.03, 1), M(-0.35, 1.78, 0), 0x18191b);
  dark.add(roundedBox(1.7, 0.36, 0.9, 0.16, 3), M(-0.45, 2.02, 0), 0x18191b);
  snow.add(roundedBox(1.66, 0.12, 0.86, 0.06, 2), M(-0.45, 2.24, 0));
  snow.add(roundedBox(1.2, 0.06, 1.5, 0.03, 2), M(1.75, 1.2, 0));
  for (const z of [-0.62, 0.62]) { lightsF.add(roundedBox(0.06, 0.12, 0.34, 0.03, 1), M(2.35, 0.95, z)); lightsR.add(roundedBox(0.06, 0.18, 0.3, 0.03, 1), M(-2.35, 0.98, z)); }
  const g = new Group();
  const paint = new MeshPhysicalMaterial({ vertexColors: true, roughness: 0.32, metalness: 0.15, clearcoat: 1, clearcoatRoughness: 0.12 });
  const head = new MeshStandardMaterial({ color: 0xfafcff, emissive: 0xfff6dd, emissiveIntensity: 0.2 }), tail = new MeshStandardMaterial({ color: 0x7a0b0b, emissive: 0xff2a1a, emissiveIntensity: 0.25 });
  for (const [k, mat] of [[body, paint], [dark, new MeshStandardMaterial({ vertexColors: true, roughness: 0.75 })], [chrome, new MeshStandardMaterial({ vertexColors: true, roughness: 0.25, metalness: 0.9 })], [snow, snowMaterial()],
    [glassK, new MeshStandardMaterial({ color: 0x0d1117, roughness: 0.06, metalness: 0.3 })], [lightsF, head], [lightsR, tail]]) {
    const m = new Mesh(k.geometry(), mat); m.castShadow = true; m.receiveShadow = true; g.add(m);
  }
  g.userData.lights = [head, tail];
  return g;
}

/* ---------------------------------------------------------------- the family */
// Two adults and two kids (8 and 11) in lathe-turned parkas, snow pants and boots, with beanies, scarves and mittens. True size.
export function buildFamily() {
  const people = [
    { h: 1.80, coat: 0x4338ca, hat: 0xffd43b, scarf: 0xc92a5e, skin: 0xc58c6a, hair: 0x2a1c14, x: -0.95 },
    { h: 1.66, coat: 0xc92a5e, hat: 0xf5f5f7, scarf: 0x0f766e, skin: 0xe2b896, hair: 0x5a3a22, x: -0.32 },
    { h: 1.46, coat: 0xc2410c, hat: 0x4338ca, scarf: 0xffd43b, skin: 0xd9a37f, hair: 0x3b2618, x: 0.3 },
    { h: 1.31, coat: 0x0f766e, hat: 0xc2410c, scarf: 0xf5f5f7, skin: 0xe7c2a0, hair: 0x7a5232, x: 0.85 },
  ];
  const g = new Group(), springs = [];
  const fabric = new MeshStandardMaterial({ vertexColors: true, roughness: 0.78 }), skin = new MeshStandardMaterial({ vertexColors: true, roughness: 0.55 });
  const rim = { uRim: { value: new Color(0xffb27a) }, uRimAmt: { value: 0.6 } };
  for (const m of [fabric, skin]) {
    m.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, rim);
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nuniform vec3 uRim; uniform float uRimAmt;')
        .replace('#include <opaque_fragment>', 'outgoingLight += uRim * pow(1.0 - max(dot(normalize(vViewPosition), normal), 0.0), 4.0) * uRimAmt;\n#include <opaque_fragment>');
    };
    m.customProgramCacheKey = () => 'cover-family-' + (m === fabric ? 'f' : 's');
  }
  for (const p of people) {
    const s = p.h / 1.75, k = new Kit(), f = new Kit();
    const coat = new LatheGeometry([[0.0, 0.62], [0.17, 0.64], [0.21, 0.72], [0.23, 0.95], [0.22, 1.18], [0.2, 1.36], [0.13, 1.44], [0.0, 1.46]].map(([r, y]) => new Vector2(r, y)), 18);
    k.add(coat, M(0, 0, 0, 0, 0, 0, s), p.coat);
    k.add(new TorusGeometry(0.11, 0.045, 8, 16), M(0, 1.44 * s, 0, Math.PI / 2, 0, 0, s), p.scarf);
    k.add(roundedBox(0.08, 0.32, 0.06, 0.03, 1), M(0.05, 1.3 * s, 0.13 * s, 0.1, 0, 0, s), p.scarf);
    for (const x of [-0.09, 0.09]) {
      k.add(new CylinderGeometry(0.075, 0.07, 0.62, 10), M(x * s, 0.36 * s, 0, 0, 0, 0, s), 0x23262b);
      k.add(roundedBox(0.13, 0.12, 0.26, 0.05, 2), M(x * s, 0.06 * s, 0.04 * s, 0, 0, 0, s), 0x3a2a1e);
    }
    for (const sx of [-1, 1]) {
      k.add(new CylinderGeometry(0.055, 0.065, 0.58, 10), M(sx * 0.25 * s, 1.08 * s, 0, 0, 0, sx * 0.18, s), p.coat);
      k.add(new SphereGeometry(0.06, 10, 8), M(sx * 0.31 * s, 0.8 * s, 0.02, 0, 0, 0, s), p.hat);
    }
    f.add(new SphereGeometry(0.104, 18, 14), M(0, 1.6 * s, 0.022, 0, 0, 0, s), p.skin);
    k.add(new SphereGeometry(0.112, 18, 14), M(0, 1.61 * s, -0.012, 0, 0, 0, s), p.hair);              // hair at the back, under the beanie
    k.add(new SphereGeometry(0.122, 18, 10, 0, Math.PI * 2, 0, Math.PI * 0.55), M(0, 1.63 * s, 0, 0, 0, 0, s), p.hat);
    k.add(new TorusGeometry(0.112, 0.025, 6, 18), M(0, 1.6 * s, 0, Math.PI / 2, 0, 0, s), p.hat);
    k.add(new SphereGeometry(0.045, 10, 8), M(0, 1.77 * s, 0, 0, 0, 0, s), 0xffffff);
    const person = new Group();
    for (const [kk, mat] of [[k, fabric], [f, skin]]) { const m = new Mesh(kk.geometry(), mat); m.castShadow = true; m.receiveShadow = true; person.add(m); }
    person.position.x = p.x;
    g.add(person);
    springs.push(new Spring(0, 180, 9));
  }
  g.userData = {
    rim,
    hop(i, v = 1.6) { const s = springs[i]; if (s && Math.abs(s.vel) < 0.05 && s.v < 0.01) s.vel = v; },
    step(dt) { springs.forEach((s, i) => { s.t = 0; s.step(dt); g.children[i].position.y = Math.max(0, s.v) * 0.25; }); },
  };
  return g;
}

/* ---------------------------------------------------------------- the towns: houses along the real roads */
export function buildTowns(T, q) {
  const rnd = mulberry32(5), houses = [], taken = new Set();
  const key = (x, z) => `${Math.round(x / 22)},${Math.round(z / 22)}`;
  for (const t of T.geo.towns) {
    const [cx, cz] = t.at;
    for (const r of T.geo.roads) {
      for (let i = 0; i < r.pts.length - 1; i++) {
        const [ax, az] = r.pts[i], [bx, bz] = r.pts[i + 1], len = Math.hypot(bx - ax, bz - az);
        if (len < 1) continue;
        const ux = (bx - ax) / len, uz = (bz - az) / len;
        for (let s = 0; s < len; s += 26 + rnd() * 24) {
          const px = ax + ux * s, pz = az + uz * s, dc = Math.hypot(px - cx, pz - cz);
          if (dc > t.r || rnd() > t.d * (1 - dc / t.r * 0.6) * q.houseDensity) continue;
          for (const side of [-1, 1]) {
            const off = 20 + rnd() * 26, hx = px - uz * off * side, hz = pz + ux * off * side;
            if (T.shore(hx, hz) < 14 || T.slopeAt(hx, hz) > 0.3 || taken.has(key(hx, hz))) continue;
            taken.add(key(hx, hz));
            houses.push({ x: hx, z: hz, y: T.landH(hx, hz), rot: Math.atan2(ux, uz) + (rnd() - 0.5) * 0.2, w: 8 + rnd() * 8, d: 8 + rnd() * 6, h: 5 + rnd() * 4, hue: rnd() });
          }
        }
      }
    }
  }
  // one house: walls with a gable roof, unit size, base at 0
  const k = new Kit();
  k.add(new BoxGeometry(1, 0.62, 1), M(0, 0.31, 0), 0xffffff);
  const roof = new BufferGeometry();
  roof.setAttribute('position', new Float32BufferAttribute([-0.56, 0.6, -0.56, -0.56, 0.6, 0.56, 0, 1, 0.56, -0.56, 0.6, -0.56, 0, 1, 0.56, 0, 1, -0.56,
    0.56, 0.6, 0.56, 0.56, 0.6, -0.56, 0, 1, -0.56, 0.56, 0.6, 0.56, 0, 1, -0.56, 0, 1, 0.56, -0.5, 0.6, 0.5, 0.5, 0.6, 0.5, 0, 1, 0.5, 0.5, 0.6, -0.5, -0.5, 0.6, -0.5, 0, 1, -0.5], 3));
  roof.computeVertexNormals();
  k.add(roof, null, 0xffffff);
  const geo = k.geometry();
  const mat = new MeshLambertMaterial({ vertexColors: true });
  const U = { uSnowCol: { value: new Color(0xf4f7fb) } };
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying float vUp; varying float vY;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvUp = normalize(mat3(instanceMatrix) * objectNormal).y; vY = position.y;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nuniform vec3 uSnowCol; varying float vUp; varying float vY;')
      .replace('#include <color_fragment>', '#include <color_fragment>\ndiffuseColor.rgb = mix(diffuseColor.rgb, uSnowCol, smoothstep(0.3, 0.6, vUp) * step(0.58, vY));');
  };
  mat.customProgramCacheKey = () => 'cover-house';
  const n = Math.min(houses.length, q.houses);
  const mesh = new InstancedMesh(geo, mat, Math.max(1, n));
  const mtx = new Matrix4(), qu = new Quaternion(), e = new Euler(), c = new Color();
  const walls = [0x7a5a40, 0x5e6b73, 0x8c4a36, 0x3f5a4a, 0xa8957c, 0x6b5848];
  const lights = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const h = houses[i];
    e.set(0, h.rot, 0); qu.setFromEuler(e); mtx.compose(new Vector3(h.x, h.y - 0.4, h.z), qu, new Vector3(h.w, h.h, h.d));
    mesh.setMatrixAt(i, mtx);
    mesh.setColorAt(i, c.set(walls[Math.floor(h.hue * walls.length)]));
    lights.set([h.x, h.y + 2.5, h.z], i * 3);
  }
  mesh.count = n; mesh.instanceMatrix.needsUpdate = true; if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  mesh.receiveShadow = true; mesh.computeBoundingSphere();
  // their windows at night: warm points that keep a few pixels however far away
  const lg = new BufferGeometry(); lg.setAttribute('position', new Float32BufferAttribute(lights, 3));
  const LU = { uOpacity: { value: 0 }, uPx: { value: 2.2 } };
  const lm = new ShaderMaterial({
    uniforms: LU, transparent: true, depthWrite: false, blending: AdditiveBlending,
    vertexShader: '#include <common>\n#include <logdepthbuf_pars_vertex>\nuniform float uPx; varying float vK; void main(){ vK = fract(sin(dot(position.xz, vec2(12.9898, 78.233))) * 43758.5453); vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_Position = projectionMatrix * mv; gl_PointSize = uPx * (0.7 + vK * 0.8) * clamp(900.0 / -mv.z, 1.0, 4.0);\n#include <logdepthbuf_vertex>\n}',
    fragmentShader: '#include <common>\n#include <logdepthbuf_pars_fragment>\nuniform float uOpacity; varying float vK; void main(){\n#include <logdepthbuf_fragment>\nfloat a = smoothstep(0.5, 0.1, length(gl_PointCoord - 0.5)); gl_FragColor = vec4(vec3(1.0, 0.72, 0.38) * a * uOpacity * (0.6 + vK * 0.6), 1.0); }',
  });
  const pts = new Points(lg, lm); pts.frustumCulled = false;
  const g = new Group(); g.add(mesh, pts);
  g.userData = { lights: LU, count: n, snow: U };
  return g;
}

/* ---------------------------------------------------------------- the roads, draped over the ground, never thinner than a pixel and a half */
export function buildRoads(T, U0) {
  const pos = [], side = [], dir = [], wid = [];
  const idx = [];
  for (const r of T.geo.roads) {
    const w = r.kind.startsWith('motorway') ? 13 : r.kind.startsWith('trunk') || r.kind.startsWith('primary') ? 9.5 : 7.5;
    const pts = [];
    for (let i = 0; i < r.pts.length - 1; i++) {
      const [ax, az] = r.pts[i], [bx, bz] = r.pts[i + 1], n = Math.max(1, Math.ceil(Math.hypot(bx - ax, bz - az) / 22));
      for (let k = 0; k < n; k++) pts.push([lerp(ax, bx, k / n), lerp(az, bz, k / n)]);
    }
    pts.push(r.pts[r.pts.length - 1]);
    const base = pos.length / 3;
    pts.forEach(([x, z], i) => {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
      let dx = b[0] - a[0], dz = b[1] - a[1]; const l = Math.hypot(dx, dz) || 1; dx /= l; dz /= l;
      const sd = T.shore(x, z);
      const y = (sd < 0 ? 0.6 : T.landH(x, z)) + 0.35;
      for (const s of [-1, 1]) { pos.push(x, y, z); side.push(s); dir.push(-dz, dx); wid.push(w); }
      if (i < pts.length - 1) { const k = base + i * 2; idx.push(k, k + 2, k + 1, k + 1, k + 2, k + 3); }
    });
  }
  const g = new BufferGeometry();
  g.setAttribute('position', new Float32BufferAttribute(pos, 3)); g.setAttribute('aSide', new Float32BufferAttribute(side, 1));
  g.setAttribute('aDir', new Float32BufferAttribute(dir, 2)); g.setAttribute('aW', new Float32BufferAttribute(wid, 1)); g.setIndex(idx);
  const U = { uCam: U0.uCam, uPxW: { value: 0.0015 }, uMinPx: { value: 1.4 }, uRise: U0.uRise, uCol: { value: new Color(0x3b3e44) }, uLit: { value: 1 } };
  const mat = new ShaderMaterial({
    uniforms: U, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
    vertexShader: `#include <common>
      #include <logdepthbuf_pars_vertex>
      attribute float aSide, aW; attribute vec2 aDir; uniform vec3 uCam; uniform float uPxW, uMinPx, uRise; varying float vS;
      void main(){ vS = aSide; vec3 p = position; p.y *= uRise; float d = distance(uCam, p); float w = max(aW * 0.5, d * uPxW * uMinPx);
        p += vec3(aDir.x, 0.0, aDir.y) * aSide * w; gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `#include <common>
      #include <logdepthbuf_pars_fragment>
      uniform vec3 uCol; uniform float uLit; varying float vS;
      void main(){
        #include <logdepthbuf_fragment>
        float edge = smoothstep(0.7, 1.0, abs(vS)); vec3 c = mix(uCol, vec3(0.86, 0.89, 0.93), edge * 0.6);
        gl_FragColor = vec4(c, uLit);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const mesh = new Mesh(g, mat); mesh.frustumCulled = false; mesh.renderOrder = 1;
  mesh.userData.U = U;
  return mesh;
}

/* ---------------------------------------------------------------- Heavenly's gondola, from the village by the lake up the mountain */
export function buildGondola(T, from, to) {
  const k = new Kit(), cab = new Kit();
  const a = new Vector3(from[0], T.landH(from[0], from[1]) + 12, from[1]), b = new Vector3(to[0], T.landH(to[0], to[1]) + 12, to[1]);
  const n = Math.max(2, Math.round(a.distanceTo(b) / 260));
  const towers = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, x = lerp(a.x, b.x, t), z = lerp(a.z, b.z, t), gy = T.landH(x, z), top = Math.max(gy + 14, lerp(a.y, b.y, t));
    k.add(roundedBox(0.7, top - gy, 0.7, 0.1, 1), M(x, gy + (top - gy) / 2, z), 0x6d7076);
    k.add(roundedBox(4, 0.4, 0.5, 0.1, 1), M(x, top, z, 0, Math.atan2(b.x - a.x, b.z - a.z), 0), 0x6d7076);
    towers.push(new Vector3(x, top, z));
  }
  cab.add(roundedBox(2.0, 2.0, 1.9, 0.35, 2), M(0, -1.4, 0), 0xc2410c);
  cab.add(new CylinderGeometry(0.04, 0.04, 1.2, 6), M(0, -0.3, 0), 0x2a2a2a);
  const g = new Group();
  g.add(new Mesh(k.geometry(), new MeshStandardMaterial({ vertexColors: true, roughness: 0.6, metalness: 0.5 })));
  const cabGeo = cab.geometry(), cabMat = new MeshStandardMaterial({ vertexColors: true, roughness: 0.4 });
  const N = 14, cabs = [];
  for (let i = 0; i < N; i++) { const m = new Mesh(cabGeo, cabMat); g.add(m); cabs.push(m); }
  const along = (u, out) => {
    const f = u * n, i = Math.min(n - 1, Math.floor(f)), t = f - i;
    out.lerpVectors(towers[i], towers[i + 1], t); out.y -= Math.sin(t * Math.PI) * 6; return out;
  };
  g.userData.step = (time) => { cabs.forEach((m, i) => { const u = ((time * 0.006 + i / N) % 1); along(u, m.position); }); };
  return g;
}

/* ---------------------------------------------------------------- chimney smoke: soft puffs that rise, drift and thin */
export function buildSmoke(at) {
  const n = 26, pos = new Float32Array(n * 3), seed = new Float32Array(n);
  for (let i = 0; i < n; i++) { seed[i] = i / n; pos.set([at.x, at.y, at.z], i * 3); }
  const g = new BufferGeometry(); g.setAttribute('position', new Float32BufferAttribute(pos, 3)); g.setAttribute('aSeed', new Float32BufferAttribute(seed, 1));
  const U = { uTime: { value: 0 }, uCol: { value: new Color(0xe9edf2) }, uOpacity: { value: 0.55 }, uScale: { value: 900 } };
  const mat = new ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false,
    vertexShader: `#include <common>
      #include <logdepthbuf_pars_vertex>
      attribute float aSeed; uniform float uTime, uScale; varying float vA;
      void main(){ float t = fract(aSeed + uTime * 0.05); vec3 p = position + vec3(t * 5.0 + sin(t * 6.0 + aSeed * 30.0) * 0.6, t * 14.0, t * 1.5);
        vA = sin(t * 3.14159) * (1.0 - t * 0.6); vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_Position = projectionMatrix * mv; gl_PointSize = (1.2 + t * 4.5) * uScale / -mv.z;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `#include <common>
      #include <logdepthbuf_pars_fragment>
      uniform vec3 uCol; uniform float uOpacity; varying float vA;
      void main(){
        #include <logdepthbuf_fragment>
        float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.0, d) * vA * uOpacity; gl_FragColor = vec4(uCol, a);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const p = new Points(g, mat); p.frustumCulled = false; p.renderOrder = 5;
  p.userData.U = U;
  return p;
}
