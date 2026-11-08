// The guidebook the cover opens on. Its right-hand page is the world itself (the terrain draws itself as a
// printed map until it rises); the left-hand page is text, and its sheets peel off and fly away.
import { Group, Mesh, BoxGeometry, PlaneGeometry, MeshBasicMaterial, CanvasTexture, SRGBColorSpace, DoubleSide, Vector3, Color } from 'three';
import { PAGE } from './world.js';
import { mulberry32, clamp, smooth, lerp } from './core.js';

const W = PAGE.x1 - PAGE.x0, H = PAGE.z1 - PAGE.z0, SPINE = PAGE.x0;

const COPY = [
  ['Getting there', 'Most visitors fly into Reno-Tahoe International and drive about an hour and twenty minutes over the Mount Rose Highway or Kingsbury Grade. Carry chains from November to April; the passes close in storms and reopen when the plows have been through.'],
  ['Where to stay', 'South Lake Tahoe has the most beds and the liveliest evenings. Cabins along Pioneer Trail book out for the holidays by September. Ask for a wood stove and a driveway the plow can reach.'],
  ['Skiing', 'Heavenly straddles two states, with long cruisers on the California side and steeper trees in Nevada. The gondola from the village climbs 2.4 miles above the lake. Lessons fill up fast on weekends.'],
  ['Emerald Bay', 'The road along the bay closes after big snow, but the walk from the overlook down to Vikingsholm is worth it on a still morning. Fannette Island is the only island in the lake.'],
  ['Eating out', 'Breakfast lines start early on Saturdays. For dinner with a view, try the west shore, and book ahead.'],
];
function wrap(x, text, maxW) { const out = []; let line = ''; for (const w of text.split(' ')) { const t = line ? line + ' ' + w : w; if (x.measureText(t).width > maxW && line) { out.push(line); line = w; } else line = t; } if (line) out.push(line); return out; }

function textPage(seed, dark, opts = {}) {
  const cw = 900, ch = 1200, cv = document.createElement('canvas'); cv.width = cw; cv.height = ch;
  const x = cv.getContext('2d'), rnd = mulberry32(seed);
  x.fillStyle = dark ? '#e6dcc6' : '#f7f2e8'; x.fillRect(0, 0, cw, ch);
  const ink = dark ? '#2b241b' : '#232a33', ink2 = dark ? '#5c5244' : '#5b6370';
  let y = 92;
  if (opts.title) {
    x.fillStyle = ink2; x.font = '600 22px Georgia, serif'; x.fillText('CHAPTER 12 · CALIFORNIA AND NEVADA', 70, y); y += 70;
    x.fillStyle = ink; x.font = 'bold 76px Georgia, serif'; x.fillText('Lake Tahoe', 70, y); y += 46;
    x.font = 'italic 30px Georgia, serif'; x.fillStyle = ink2; x.fillText('The complete winter guide', 70, y); y += 40;
    x.fillStyle = dark ? '#b9ad94' : '#d9d0bf'; x.fillRect(70, y, 760, 3); y += 52;
  }
  // a small photo box and a star rating, like every guidebook
  if (opts.photo) {
    x.fillStyle = dark ? '#c9bea6' : '#dfe6ee'; x.fillRect(470, y, 360, 240);
    x.fillStyle = dark ? '#8f866f' : '#9fb3c8'; x.beginPath(); x.moveTo(470, y + 240); x.lineTo(560, y + 120); x.lineTo(640, y + 190); x.lineTo(720, y + 90); x.lineTo(830, y + 240); x.closePath(); x.fill();
    x.fillStyle = ink2; x.font = 'italic 19px Georgia, serif'; x.fillText('The lake from Inspiration Point.', 470, y + 272);
  }
  const col = (x0, maxW, startY, items) => {
    let yy = startY;
    for (const [head, body] of items) {
      if (yy > ch - 120) break;
      x.fillStyle = ink; x.font = 'bold 30px Georgia, serif'; x.fillText(head, x0, yy); yy += 40;
      x.font = '22px Georgia, serif'; x.fillStyle = ink2;
      for (const l of wrap(x, body, maxW)) { if (yy > ch - 110) break; x.fillText(l, x0, yy); yy += 33; }
      x.fillStyle = '#c2410c'; x.font = '22px Georgia, serif'; x.fillText('★★★★☆', x0, yy + 4); yy += 58;
    }
  };
  const order = [...COPY].sort(() => rnd() - 0.5);
  col(70, opts.photo ? 360 : 760, y, order);
  x.fillStyle = ink2; x.font = '18px Georgia, serif'; x.fillText(String(200 + (seed % 15)), 70, ch - 50);
  // the gutter shadow by the spine (on the right edge of a left-hand page)
  const g = x.createLinearGradient(cw - 90, 0, cw, 0); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, dark ? 'rgba(0,0,0,.28)' : 'rgba(40,30,20,.16)');
  x.fillStyle = g; x.fillRect(cw - 90, 0, 90, ch);
  const t = new CanvasTexture(cv); t.colorSpace = SRGBColorSpace; t.anisotropy = 4;
  return t;
}

function shadowTex() {
  const cv = document.createElement('canvas'); cv.width = 256; cv.height = 256; const x = cv.getContext('2d');
  const g = x.createRadialGradient(128, 128, 30, 128, 128, 128); g.addColorStop(0, 'rgba(10,10,20,.28)'); g.addColorStop(1, 'rgba(10,10,20,0)');
  x.fillStyle = g; x.fillRect(0, 0, 256, 256); return new CanvasTexture(cv);
}

// a sheet that hinges at the spine, curls as it lifts, then flies away
function sheet(tex, dark) {
  const geo = new PlaneGeometry(W, H, 24, 1); geo.rotateX(-Math.PI / 2); geo.translate(-W / 2, 0, 0); // x from −W (outer edge) to 0 (spine)
  const U = { uTheta: { value: 0 }, uCurl: { value: 0 }, uFly: { value: 0 }, uSpin: { value: 0 }, uPaper: { value: new Color(dark ? 0xe6dcc6 : 0xf7f2e8) } };
  const mat = new MeshBasicMaterial({ map: tex, side: DoubleSide, transparent: true });
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = 'uniform float uTheta, uCurl, uFly, uSpin;\n' + sh.vertexShader.replace('#include <begin_vertex>', `
      float s = -position.x;                                // distance from the spine
      float f = s / ${W.toFixed(1)};
      float th = uTheta + uCurl * pow(f, 1.6) * 0.7;
      vec3 transformed = vec3(-s * cos(th), s * sin(th), position.z);
      // fly: rise toward the camera, drift, and tumble
      float fl = uFly;
      transformed.xz = mat2(cos(uSpin * fl), -sin(uSpin * fl), sin(uSpin * fl), cos(uSpin * fl)) * transformed.xz;
      transformed += vec3(60.0 * fl, 210.0 * fl * fl + 40.0 * fl, 30.0 * fl * (1.0 + position.z * 0.004));`);
    // the back of a page is paper with the print just showing through
    sh.fragmentShader = 'uniform vec3 uPaper;\n' + sh.fragmentShader.replace('#include <map_fragment>', '#include <map_fragment>\n if (!gl_FrontFacing) diffuseColor.rgb = mix(uPaper, diffuseColor.rgb, 0.08);');
  };
  mat.customProgramCacheKey = () => 'cover-sheet';
  const m = new Mesh(geo, mat); m.position.set(SPINE, 0.02, (PAGE.z0 + PAGE.z1) / 2); m.renderOrder = 2;
  m.userData.U = U; m.userData.mat = mat;
  return m;
}

export function buildBook(dark) {
  const g = new Group();
  const cover = dark ? 0x23262e : 0x1f2633, edge = dark ? 0xd8ceb6 : 0xece5d6;
  const boards = new MeshBasicMaterial({ color: cover });
  const pagesMat = new MeshBasicMaterial({ color: edge });
  const L = new Mesh(new BoxGeometry(W + 6, 1.2, H + 6), boards); L.position.set(SPINE - W / 2 - 1, -3.6, (PAGE.z0 + PAGE.z1) / 2);
  const R = new Mesh(new BoxGeometry(W + 6, 1.2, H + 6), boards); R.position.set(SPINE + W / 2 + 1, -3.6, (PAGE.z0 + PAGE.z1) / 2);
  const LB = new Mesh(new BoxGeometry(W - 1, 2.9, H), pagesMat); LB.position.set(SPINE - W / 2 - 0.4, -1.55, (PAGE.z0 + PAGE.z1) / 2);
  const RB = new Mesh(new BoxGeometry(W - 1, 2.4, H), pagesMat); RB.position.set(SPINE + W / 2 + 0.4, -1.85, (PAGE.z0 + PAGE.z1) / 2); // its top sits well under the map
  const base = new Mesh(new PlaneGeometry(W, H), new MeshBasicMaterial({ map: textPage(7, dark, { photo: true }) }));
  base.rotation.x = -Math.PI / 2; base.position.set(SPINE - W / 2, -0.02, (PAGE.z0 + PAGE.z1) / 2);
  const shadow = new Mesh(new PlaneGeometry(W * 2.7, H * 1.5), new MeshBasicMaterial({ map: shadowTex(), transparent: true, depthWrite: false }));
  shadow.rotation.x = -Math.PI / 2; shadow.position.set(SPINE + 4, -4.4, (PAGE.z0 + PAGE.z1) / 2 + 6);
  g.add(shadow, L, R, LB, RB, base);
  const sheets = [sheet(textPage(3, dark, { title: true }), dark), sheet(textPage(5, dark, { photo: true }), dark), sheet(textPage(11, dark), dark)];
  sheets.forEach((s, i) => { s.position.y = 0.06 - i * 0.02; g.add(s); });
  sheets.reverse(); // index 0 is the top sheet
  g.userData = { sheets, solids: [boards, pagesMat], base, shadow, L, R, LB, RB };
  // p: 0 → 1 drives the three sheets one after another; fade fades the whole book away as the world grows
  g.userData.set = (p, fade) => {
    sheets.forEach((s, i) => {
      const t = clamp((p - i * 0.22) / 0.56, 0, 1);
      const lift = smooth(0, 0.55, t), fly = smooth(0.42, 1, t);
      s.userData.U.uTheta.value = lift * 2.0; s.userData.U.uCurl.value = Math.sin(lift * Math.PI) * 1.4 + fly * 0.8;
      s.userData.U.uFly.value = fly; s.userData.U.uSpin.value = (i % 2 ? -1 : 1) * 1.6;
      s.userData.mat.opacity = 1 - smooth(0.55, 1, t);
      s.visible = s.userData.mat.opacity > 0.01;
    });
    const o = 1 - fade;
    [boards, pagesMat, base.material].forEach((m) => { m.transparent = o < 1; m.opacity = o; });
    shadow.material.opacity = o;
    g.visible = o > 0.01;
  };
  return g;
}
