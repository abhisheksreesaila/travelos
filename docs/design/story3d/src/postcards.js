// Prototype 2 · Memory postcards: the trip's photos, notes and tickets as cards floating along a dotted path.
// Swipe (or drag) to glide the camera down the path through the days; tap a card to bring it close.
// A paper plane leads the way. At the end the path splits where other families forked it; your fork adds a branch.
// Card faces are drawn on canvases (Geist, Caveat); the curved-panel idea comes from ThreeUI's Gallery (MIT).
import { PlaneGeometry, CatmullRomCurve3, Raycaster, Vector2, CanvasTexture, SRGBColorSpace, DoubleSide, BufferGeometry, Float32BufferAttribute } from 'three';
import { createStage, damp, Spring, Kit, M, confetti, KIND, Group, Mesh, Vector3, CircleGeometry, MeshBasicMaterial, MeshLambertMaterial } from './core.js';
import { ICON, KIND_COLOR, TRIP } from './trip.js';

window.GA3D.register((host, api) => {
  const stage = createStage(host, api, { fov: 40 });
  const { scene, camera } = stage;
  const DAYS = api.days;
  const dark = () => api.mode === 'dark';

  /* ---------- the path ---------- */
  const px = (s) => 1.3 * Math.sin(s * 0.21) + 0.5 * Math.sin(s * 0.07);
  const path = (s, v = new Vector3()) => v.set(px(s), 0, -s);

  /* ---------- drawing card faces ---------- */
  const FONT = 'Geist, system-ui, sans-serif', HAND = 'Caveat, cursive';
  const icon = (x, name, cx, cy, size, color, width = 2) => { x.save(); x.translate(cx - size / 2, cy - size / 2); x.scale(size / 24, size / 24); x.strokeStyle = color; x.lineWidth = width; x.lineCap = 'round'; x.lineJoin = 'round'; x.stroke(new Path2D(ICON[name])); x.restore(); };
  function wrap(x, text, X, Y, maxW, lh, maxLines = 9) {
    const words = text.split(' '); let line = '', n = 0;
    for (const w of words) { const t = line ? line + ' ' + w : w; if (x.measureText(t).width > maxW && line) { x.fillText(line, X, Y + n * lh); line = w; if (++n >= maxLines) return; } else line = t; }
    x.fillText(line, X, Y + n * lh);
  }
  const rr = (x, X, Y, W, H, r) => { x.beginPath(); x.roundRect(X, Y, W, H, r); };
  // little flat illustrations for stops without a photo
  const ILLO = {
    sky(x, w, h, top, bottom, gy) { x.fillStyle = top; x.fillRect(0, 0, w, h); x.fillStyle = bottom; x.fillRect(0, gy, w, h - gy); },
    sun(x, cx, cy, r, c = '#FFD43B') { x.fillStyle = c; x.beginPath(); x.arc(cx, cy, r, 0, 7); x.fill(); },
    hill(x, cx, cy, rx, ry, c) { x.fillStyle = c; x.beginPath(); x.ellipse(cx, cy, rx, ry, 0, Math.PI, 0); x.fill(); },
    palm(x, X, Y, s) { x.strokeStyle = '#8A5A2B'; x.lineWidth = 7 * s; x.beginPath(); x.moveTo(X, Y); x.quadraticCurveTo(X + 10 * s, Y - 60 * s, X + 4 * s, Y - 110 * s); x.stroke(); x.fillStyle = '#2F9E44'; for (let k = 0; k < 5; k++) { x.save(); x.translate(X + 4 * s, Y - 110 * s); x.rotate(-2.6 + k * 0.9); x.beginPath(); x.ellipse(28 * s, 0, 32 * s, 9 * s, 0, 0, 7); x.fill(); x.restore(); } },
    tacos(x, w, h) { this.sky(x, w, h, '#FFE7A8', '#F2B84B', h * 0.72); x.fillStyle = '#E9B44C'; for (const [cx, r] of [[w * 0.32, 92], [w * 0.68, 84]]) { x.fillStyle = '#7BC96F'; x.beginPath(); x.arc(cx, h * 0.62, r * 0.9, Math.PI, 0); x.fill(); x.fillStyle = '#E94F37'; for (let k = 0; k < 5; k++) { x.beginPath(); x.arc(cx - r * 0.6 + k * r * 0.3, h * 0.6 - r * 0.55, 10, 0, 7); x.fill(); } x.fillStyle = '#F4C95D'; x.beginPath(); x.arc(cx, h * 0.62, r, Math.PI, 0); x.lineTo(cx + r * 0.75, h * 0.62); x.arc(cx, h * 0.62, r * 0.75, 0, Math.PI, true); x.fill(); } },
    tidewater(x, w, h) { this.sky(x, w, h, '#BFE6FF', '#F3DCA6', h * 0.78); this.sun(x, w * 0.8, h * 0.2, 34); x.fillStyle = '#F6A6C1'; x.fillRect(w * 0.2, h * 0.3, w * 0.5, h * 0.48); x.fillStyle = '#FFFFFF'; for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) x.fillRect(w * 0.24 + c * w * 0.115, h * 0.35 + r * h * 0.1, w * 0.07, h * 0.06); this.palm(x, w * 0.82, h * 0.8, 1.1); },
    pony(x, w, h) { this.sky(x, w, h, '#CDEBFF', '#8BCF6A', h * 0.66); this.sun(x, w * 0.18, h * 0.2, 30); x.fillStyle = '#B5652E'; x.beginPath(); x.ellipse(w * 0.5, h * 0.6, 92, 48, 0, 0, 7); x.fill(); x.beginPath(); x.ellipse(w * 0.72, h * 0.42, 34, 26, -0.6, 0, 7); x.fill(); x.fillRect(w * 0.62, h * 0.4, 30, 70); x.strokeStyle = '#B5652E'; x.lineWidth = 16; x.lineCap = 'round'; for (const dx of [-60, -30, 30, 60]) { x.beginPath(); x.moveTo(w * 0.5 + dx, h * 0.66); x.lineTo(w * 0.5 + dx, h * 0.84); x.stroke(); } x.fillStyle = '#4A2C17'; x.beginPath(); x.ellipse(w * 0.66, h * 0.36, 12, 30, -0.5, 0, 7); x.fill(); x.fillStyle = '#FFD43B'; x.beginPath(); x.arc(w * 0.47, h * 0.45, 22, 0, 7); x.fill(); },
    ferndell(x, w, h) { this.sky(x, w, h, '#D7F2E0', '#6FBF73', h * 0.55); for (let k = 0; k < 5; k++) { x.fillStyle = k % 2 ? '#2F8F4E' : '#3DAA5C'; x.beginPath(); x.arc(30 + k * 95, h * 0.5, 60, 0, 7); x.fill(); } x.strokeStyle = '#59B8EA'; x.lineWidth = 26; x.beginPath(); x.moveTo(0, h * 0.95); x.bezierCurveTo(w * 0.3, h * 0.7, w * 0.6, h * 0.95, w, h * 0.72); x.stroke(); for (let r = 0; r < 4; r++) for (let c = 0; c < 6; c++) { x.fillStyle = (r + c) % 2 ? '#E94F37' : '#FFFFFF'; x.fillRect(w * 0.25 + c * 26, h * 0.66 + r * 18, 26, 18); } },
    observatory(x, w, h) { this.sky(x, w, h, '#2B2F6B', '#3E5C3A', h * 0.7); x.fillStyle = '#FFFFFF'; for (let k = 0; k < 28; k++) { x.globalAlpha = 0.5 + (k % 3) * 0.2; x.fillRect((k * 97) % w, (k * 53) % (h * 0.55), 4, 4); } x.globalAlpha = 1; this.hill(x, w * 0.5, h * 0.74, w * 0.7, h * 0.24, '#4E7A45'); x.fillStyle = '#F4F1EA'; x.fillRect(w * 0.26, h * 0.5, w * 0.48, h * 0.14); x.fillStyle = '#8FA3BF'; for (const [cx, r] of [[0.5, 46], [0.3, 26], [0.7, 26]]) { x.beginPath(); x.arc(w * cx, h * 0.5, r, Math.PI, 0); x.fill(); } this.sun(x, w * 0.82, h * 0.16, 22, '#FFF3C4'); },
    abbot(x, w, h) { x.fillStyle = '#FFF4E6'; x.fillRect(0, 0, w, h); const c = ['#E94F37', '#FFD43B', '#4FC3F7', '#9B6DFF', '#5BD18B', '#FF6FB1']; for (let k = 0; k < 9; k++) { x.fillStyle = c[k % 6]; x.beginPath(); x.arc((k * 131) % w, ((k * 71) % h) * 0.9 + 30, 40 + (k % 3) * 22, 0, 7); x.fill(); } x.fillStyle = '#0B0B0D'; x.font = `700 64px ${HAND}`; x.fillText('Venice', w * 0.2, h * 0.58); },
    dume(x, w, h) { this.sky(x, w, h, '#BFE6FF', '#3E9BD0', h * 0.45); x.fillStyle = '#8F8378'; for (const [cx, cy, r] of [[0.2, 0.75, 90], [0.6, 0.85, 110], [0.95, 0.7, 80]]) { x.beginPath(); x.ellipse(w * cx, h * cy, r, r * 0.6, 0, 0, 7); x.fill(); } x.fillStyle = '#7FD6E8'; x.beginPath(); x.ellipse(w * 0.42, h * 0.72, 70, 26, 0, 0, 7); x.fill(); for (const [cx, cy, c] of [[0.38, 0.72, '#FF8A3D'], [0.62, 0.8, '#FF5D8F']]) { x.fillStyle = c; x.save(); x.translate(w * cx, h * cy); for (let k = 0; k < 5; k++) { x.rotate(1.2566); x.beginPath(); x.ellipse(0, -14, 7, 16, 0, 0, 7); x.fill(); } x.restore(); } },
    malibufarm(x, w, h) { this.sky(x, w, h, '#FFE3C2', '#3E9BD0', h * 0.6); this.sun(x, w * 0.5, h * 0.6, 60, '#FF9A5C'); x.fillStyle = '#3E9BD0'; x.fillRect(0, h * 0.6, w, h); x.fillStyle = '#B98A5A'; x.fillRect(0, h * 0.52, w * 0.7, 18); for (let k = 0; k < 6; k++) x.fillRect(20 + k * 52, h * 0.52, 8, 70); },
    zuma(x, w, h) { this.sky(x, w, h, '#BFE6FF', '#F3DCA6', h * 0.7); x.fillStyle = '#3E9BD0'; x.fillRect(0, h * 0.55, w, h * 0.15); x.fillStyle = '#FFD43B'; x.fillRect(w * 0.55, h * 0.4, 90, 60); x.fillStyle = '#0369A1'; x.beginPath(); x.moveTo(w * 0.53, h * 0.4); x.lineTo(w * 0.55 + 45, h * 0.3); x.lineTo(w * 0.57 + 90, h * 0.4); x.fill(); x.strokeStyle = '#8A5A2B'; x.lineWidth = 8; for (const dx of [10, 80]) { x.beginPath(); x.moveTo(w * 0.55 + dx, h * 0.5); x.lineTo(w * 0.55 + dx, h * 0.78); x.stroke(); } this.sun(x, w * 0.2, h * 0.2, 34); },
    getty(x, w, h) { this.sky(x, w, h, '#CDEBFF', '#9BC46A', h * 0.7); this.hill(x, w * 0.5, h * 0.78, w * 0.75, h * 0.3, '#86B35A'); x.fillStyle = '#FAF7EF'; x.fillRect(w * 0.18, h * 0.42, w * 0.3, h * 0.16); x.fillRect(w * 0.5, h * 0.36, w * 0.28, h * 0.22); x.fillStyle = '#EFEBE2'; x.beginPath(); x.ellipse(w * 0.5, h * 0.5, 40, 36, 0, 0, 7); x.fill(); x.strokeStyle = '#5C5C66'; x.lineWidth = 4; x.beginPath(); x.moveTo(0, h * 0.95); x.lineTo(w * 0.3, h * 0.6); x.stroke(); x.fillStyle = '#E94F37'; x.fillRect(w * 0.14, h * 0.74, 30, 18); },
    gettylunch(x, w, h) { this.sky(x, w, h, '#FFF4E6', '#E9DCC6', h * 0.7); x.fillStyle = '#4FA3E3'; x.beginPath(); x.moveTo(w * 0.2, h * 0.38); x.quadraticCurveTo(w * 0.5, h * 0.05, w * 0.8, h * 0.38); x.fill(); x.fillStyle = '#5C5C66'; x.fillRect(w * 0.495, h * 0.38, 6, h * 0.34); x.fillStyle = '#FFFFFF'; x.beginPath(); x.ellipse(w * 0.5, h * 0.72, 120, 22, 0, 0, 7); x.fill(); x.fillStyle = '#C92A5E'; x.beginPath(); x.arc(w * 0.42, h * 0.7, 14, 0, 7); x.fill(); x.fillStyle = '#5BD18B'; x.beginPath(); x.arc(w * 0.58, h * 0.7, 14, 0, 7); x.fill(); },
    laxcar(x, w, h) { this.sky(x, w, h, '#E3E3E8', '#5E6470', h * 0.7); x.fillStyle = '#15803D'; rr(x, w * 0.2, h * 0.45, w * 0.6, h * 0.2, 24); x.fill(); rr(x, w * 0.32, h * 0.32, w * 0.34, h * 0.16, 20); x.fill(); x.fillStyle = '#DDF7E6'; rr(x, w * 0.36, h * 0.35, w * 0.12, h * 0.1, 8); x.fill(); rr(x, w * 0.5, h * 0.35, w * 0.12, h * 0.1, 8); x.fill(); x.fillStyle = '#17140A'; for (const cx of [0.32, 0.68]) { x.beginPath(); x.arc(w * cx, h * 0.66, 26, 0, 7); x.fill(); } x.fillStyle = '#FFFFFF'; for (let k = 0; k < 5; k++) x.fillRect(k * 100, h * 0.86, 60, 8); },
  };
  function canvasFor(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return [c, c.getContext('2d')]; }

  const faces = []; // { draw(), tex } — redrawn when the theme or a photo changes
  function face(w, h, draw) { const [c, x] = canvasFor(w, h); const tex = new CanvasTexture(c); tex.colorSpace = SRGBColorSpace; tex.anisotropy = 4; const f = { c, x, tex, draw: () => { x.clearRect(0, 0, w, h); draw(x, w, h); tex.needsUpdate = true; } }; f.draw(); faces.push(f); return f; }

  const chapterFace = (i) => face(640, 420, (x, w, h) => {
    const d = DAYS[i], bg = dark() ? '#F5F5F7' : '#0B0B0D', fg = dark() ? '#0B0B0D' : '#FFFFFF', fg2 = dark() ? '#4A4A52' : 'rgba(255,255,255,.72)';
    x.fillStyle = bg; rr(x, 0, 0, w, h, 44); x.fill();
    x.fillStyle = fg2; x.font = `600 26px ${FONT}`; x.fillText(`DAY ${i + 1} · ${d.d.toUpperCase()}`, 44, 70);
    x.fillStyle = fg; x.font = `720 62px ${FONT}`; wrap(x, d.title, 44, 150, w - 88, 66, 2);
    icon(x, d.wx[0], 66, h - 72, 40, fg, 2.2); x.font = `700 40px ${FONT}`; x.fillText(`${d.wx[1]}°`, 100, h - 58);
    x.fillStyle = fg2; x.font = `500 26px ${FONT}`; x.fillText(d.wx[4], 190, h - 60);
    d.stops.forEach((s, k) => { x.fillStyle = KIND_COLOR[s[2]]; x.beginPath(); x.arc(w - 60 - k * 40, h - 70, 14, 0, 7); x.fill(); });
  });
  const noteFace = (i) => face(460, 420, (x, w, h) => {
    x.fillStyle = '#FFF4C2'; rr(x, 0, 0, w, h, 18); x.fill();
    x.fillStyle = 'rgba(255,212,59,.85)'; x.fillRect(w / 2 - 60, -6, 120, 34);
    x.fillStyle = '#3B2F05'; x.font = `600 44px ${HAND}`; wrap(x, '“' + DAYS[i].note + '”', 34, 92, w - 68, 46, 6);
    x.fillStyle = '#7A6420'; x.font = `600 36px ${HAND}`; x.fillText('– ' + TRIP.who, 34, h - 34);
  });
  const ticketFace = (s) => face(640, 330, (x, w, h) => {
    x.fillStyle = KIND_COLOR.flight; rr(x, 0, 0, w, h, 32); x.fill();
    x.globalCompositeOperation = 'destination-out'; for (const y of [0, h]) { x.beginPath(); x.arc(w * 0.68, y, 24, 0, 7); x.fill(); } x.globalCompositeOperation = 'source-over';
    x.strokeStyle = 'rgba(255,255,255,.45)'; x.lineWidth = 3; x.setLineDash([10, 10]); x.beginPath(); x.moveTo(w * 0.68, 32); x.lineTo(w * 0.68, h - 32); x.stroke(); x.setLineDash([]);
    const home = s[5] === 'laxfly';
    x.fillStyle = 'rgba(255,255,255,.75)'; x.font = `600 24px ${FONT}`; x.fillText(home ? 'BOARDING · GOING HOME' : 'BOARDING · ARRIVING', 40, 62);
    x.fillStyle = '#FFFFFF'; x.font = `760 84px ${FONT}`; x.fillText(home ? 'LAX' : 'ORD', 40, 160); icon(x, 'flight', 248, 132, 52, '#FFFFFF', 2); x.fillText(home ? 'ORD' : 'LAX', 286, 160);
    x.font = `600 28px ${FONT}`; x.fillText(s[4].split(' · ')[0], 40, 236); x.fillStyle = 'rgba(255,255,255,.75)'; x.font = `500 24px ${FONT}`; x.fillText(`${s[0]} ${s[1]} · 2 adults, 2 kids`, 40, 276);
    x.fillStyle = '#FFFFFF'; x.font = `700 44px ${FONT}`; x.fillText(s[0], w * 0.73, 160); x.font = `600 24px ${FONT}`; x.fillText(s[1], w * 0.73, 196);
  });
  const photos = {};
  const PHOTO = { pier: 'pier', bikes: 'venice', canals: 'venice' };
  const polaroidFace = (s, di) => face(460, 560, (x, w, h) => {
    x.fillStyle = '#FFFFFF'; rr(x, 0, 0, w, h, 14); x.fill();
    x.save(); rr(x, 20, 20, w - 40, 400, 6); x.clip(); x.translate(20, 20);
    const img = photos[PHOTO[s[5]]];
    if (img) x.drawImage(img, 0, 0, w - 40, 400);
    else if (ILLO[s[5]]) ILLO[s[5]](x, w - 40, 400);
    else { x.fillStyle = KIND_COLOR[s[2]]; x.fillRect(0, 0, w - 40, 400); icon(x, s[2], (w - 40) / 2, 200, 140, '#FFFFFF', 1.6); }
    x.restore();
    x.fillStyle = KIND_COLOR[s[2]]; x.beginPath(); x.arc(w - 58, 58, 28, 0, 7); x.fill(); icon(x, s[2], w - 58, 58, 30, s[2] === 'ride' ? '#17140A' : '#FFFFFF', 2.2);
    x.fillStyle = '#0B0B0D'; x.font = `700 44px ${HAND}`; wrap(x, s[3], 28, 476, w - 56, 42, 2);
    x.fillStyle = '#5C5C66'; x.font = `600 22px ${FONT}`; x.fillText(`${s[0]} ${s[1]} · DAY ${di + 1}`, 28, h - 22);
  });
  const coverFace = face(700, 520, (x, w, h) => {
    x.fillStyle = dark() ? '#1C1C1F' : '#FFFFFF'; rr(x, 0, 0, w, h, 40); x.fill();
    x.fillStyle = '#C2410C'; x.beginPath(); x.arc(84, 92, 40, 0, 7); x.fill(); x.fillStyle = '#FFFFFF'; x.font = `700 40px ${FONT}`; x.fillText('P', 70, 106);
    x.fillStyle = dark() ? '#F5F5F7' : '#0B0B0D'; x.font = `650 32px ${FONT}`; x.fillText(TRIP.who, 144, 86); x.fillStyle = dark() ? '#A1A1AA' : '#5C5C66'; x.font = `500 26px ${FONT}`; x.fillText(TRIP.handle, 144, 122);
    x.fillStyle = dark() ? '#F5F5F7' : '#0B0B0D'; x.font = `760 76px ${FONT}`; wrap(x, TRIP.title, 44, 236, w - 88, 76, 2);
    x.fillStyle = dark() ? '#A1A1AA' : '#5C5C66'; x.fillText(TRIP.titleEm, 44, 388);
    x.font = `600 30px ${HAND}`; x.font = `600 36px ${HAND}`; x.fillText('Swipe to start the trip →', 44, h - 44);
  });
  const forkFace = (title, sub, you) => face(560, 300, (x, w, h) => {
    const bg = you ? (dark() ? '#F5F5F7' : '#0B0B0D') : dark() ? '#1C1C1F' : '#FFFFFF', fg = you ? (dark() ? '#0B0B0D' : '#FFFFFF') : dark() ? '#F5F5F7' : '#0B0B0D', fg2 = you ? (dark() ? '#4A4A52' : 'rgba(255,255,255,.72)') : dark() ? '#A1A1AA' : '#5C5C66';
    x.fillStyle = bg; rr(x, 0, 0, w, h, 34); x.fill();
    if (!you) { x.strokeStyle = fg2; x.lineWidth = 4; x.setLineDash([14, 12]); rr(x, 6, 6, w - 12, h - 12, 30); x.stroke(); x.setLineDash([]); }
    icon(x, 'fork', 64, 70, 40, fg, 2.2); x.fillStyle = fg2; x.font = `600 24px ${FONT}`; x.fillText(you ? 'YOUR FORK' : 'FORKED', 100, 80);
    x.fillStyle = fg; x.font = `700 42px ${FONT}`; wrap(x, title, 40, 150, w - 80, 46, 2); x.fillStyle = fg2; x.font = `500 26px ${FONT}`; x.fillText(sub, 40, h - 40);
  });

  /* ---------- lay the cards along the path ---------- */
  const cards = [], blobsList = [];
  const paperBack = new MeshBasicMaterial({ color: 0xF4F1EA, side: DoubleSide });
  function addCard(f, w, s, side, y, opts = {}) {
    const h = (w * f.c.height) / f.c.width;
    const g = new Group();
    const front = new Mesh(new PlaneGeometry(w, h), new MeshBasicMaterial({ map: f.tex, transparent: true, side: DoubleSide }));
    g.add(front);
    const p = path(s); const off = 1.35 * side;
    g.position.set(p.x + off, y, p.z); g.rotation.y = -side * 0.32; g.rotation.z = (opts.tilt ?? (side ? -side * 0.05 : 0));
    g.userData = { s, off, home: g.position.clone(), rot: g.rotation.clone(), ph: cards.length * 1.7, wig: new Spring(0, 180, 7), pop: new Spring(opts.hidden ? 0 : 1, 170, 12), focus: 0, h, ...opts };
    front.userData.card = g; scene.add(g); cards.push(g);
    blobsList.push([g.position.x, 0.01, g.position.z, w * 0.3]);
    return g;
  }
  const dayS = []; let s = 0;
  addCard(coverFace, 2.3, 1.4, 0, 1.3, { kind: 'cover' });
  s = 6.5;
  DAYS.forEach((d, di) => {
    dayS.push(s);
    addCard(chapterFace(di), 2.0, s, -0.85, 1.35, { kind: 'chapter', di });
    addCard(noteFace(di), 1.35, s + 1.5, 0.9, 1.15, { kind: 'note', di, tilt: 0.06 });
    let k = 0;
    d.stops.forEach((st, si) => { const f = st[2] === 'flight' ? ticketFace(st) : polaroidFace(st, di); addCard(f, st[2] === 'flight' ? 1.9 : 1.35, s + 3.1 + k * 1.75, k % 2 ? 0.95 : -0.95, st[2] === 'flight' ? 1.2 : 1.3, { kind: 'stop', di, si }); k++; });
    s += 3.1 + k * 1.75 + 1.4;
  });
  const endS = s;

  // the dotted path on the floor, and branches where forks went
  const dotMat = new MeshBasicMaterial({ color: 0xB4B4BE });
  const dots = new Kit(); const v = new Vector3();
  for (let t = -2; t < endS + 0.5; t += 0.32) { path(t, v); dots.add(new CircleGeometry(0.05, 8), 0xffffff, M(v.x, 0.005, v.z, -Math.PI / 2)); }
  const BR = [[-1, 'Seven days, with San Diego', 'Ana & Luis · 18 forks'], [1, 'Added a Disneyland day', 'Mei & Jun · 9 forks']];
  const branchDots = (from, side, len, kit, spread = 3.2) => { const pts = []; for (let t = 0; t <= len; t += 0.32) { const u = t / len; pts.push(new Vector3(px(from + t) + side * Math.pow(u, 1.6) * spread, 0.005, -(from + t))); } pts.forEach((q) => kit.add(new CircleGeometry(0.05, 8), 0xffffff, M(q.x, q.y, q.z, -Math.PI / 2))); return pts[pts.length - 1]; };
  BR.forEach(([side, t, sub]) => { const end = branchDots(endS - 1.2, side, 4.2, dots); const c = addCard(forkFace(t, sub, false), 1.7, endS + 2.6, 0, 1.2, { kind: 'fork' }); c.position.x = end.x; c.position.z = end.z; c.userData.home.copy(c.position); c.rotation.y = -side * 0.4; c.userData.rot.copy(c.rotation); blobsList.push([end.x, 0.01, end.z, 0.7]); });
  const dotMesh = dots.mesh(dotMat); scene.add(dotMesh);
  const blobMat = new MeshBasicMaterial({ color: 0x14141f, transparent: true, opacity: 0.1, depthWrite: false });
  const bk = new Kit(); blobsList.forEach(([x, y, z, r]) => bk.add(new CircleGeometry(r, 18), 0x000000, M(x, y, z, -Math.PI / 2, 0, 0, 1, 0.45, 1)));
  const blobMesh = bk.mesh(blobMat); scene.add(blobMesh);

  // the paper plane that leads the way
  const plane = new Group();
  { const g = new BufferGeometry(); g.setAttribute('position', new Float32BufferAttribute([0, 0, -0.35, -0.24, 0.02, 0.14, 0, -0.04, 0.12, 0, 0, -0.35, 0, -0.04, 0.12, 0.24, 0.02, 0.14, 0, 0, -0.35, 0, -0.12, 0.1, 0, -0.04, 0.12], 3)); g.computeVertexNormals();
    plane.add(new Mesh(g, new MeshLambertMaterial({ color: 0xFFFFFF, emissive: 0x8A8A96, side: DoubleSide, flatShading: true }))); }
  plane.userData = { loop: 0 }; scene.add(plane);
  const conf = confetti(scene);

  // photos arrive after the scene is up (a separate file; see dist/photos.js)
  const ps = document.createElement('script'); ps.src = 'dist/photos.js';
  ps.onload = () => { let n = 0; const keys = Object.keys(window.GA_PHOTOS || {}); keys.forEach((k) => { const img = new Image(); img.onload = () => { photos[k] = img; if (++n === keys.length) faces.forEach((f) => f.draw()); }; img.src = window.GA_PHOTOS[k]; }); };
  document.head.appendChild(ps);
  document.fonts?.ready.then(() => faces.forEach((f) => f.draw()));

  /* ---------- camera: glide along the path ---------- */
  let sCam = 0, sWant = 0, cur = -1, dragFrom = 0;
  const camFor = (i) => (i < 0 ? (stage.aspect < 1 ? -3.4 : -2.8) : dayS[i] - (stage.aspect < 1 ? 4.6 : 3.8));
  function dayAt(sc) { let d = -1; dayS.forEach((ds, i) => { if (sc >= camFor(i) - 0.6) d = i; }); return d; }
  stage.resized = () => { camera.fov = stage.aspect < 1 ? 56 : 40; camera.updateProjectionMatrix(); };

  let focused = null;
  function focus(card) {
    if (focused && focused !== card) focused.userData.focus = 0;
    focused = card && card.userData.focus === 0 ? card : null;
    if (card) card.userData.focus = focused ? 1 : 0;
    if (focused && focused.userData.kind === 'stop') api.onStop(focused.userData.di, focused.userData.si);
  }

  const look = new Vector3(), cpos = new Vector3(), tmp = new Vector3(), ahead = new Vector3();
  stage.onFrame.push((dt, t) => {
    sCam = damp(sCam, sWant, 2.4, dt);
    const portrait = stage.aspect < 1;
    path(sCam, cpos); cpos.y = portrait ? 2.4 : 2.05;
    path(sCam + 4.2, look); look.y = 1.05;
    camera.position.copy(cpos); camera.lookAt(look);
    if (!dragging) { const d = dayAt(sCam); if (d !== cur && Math.abs(sCam - sWant) < 0.4) { cur = d; api.onDay(d); } }
    cards.forEach((c) => {
      const u = c.userData; const wig = u.wig.step(dt); const pop = u.pop.step(dt);
      u.f = damp(u.f || 0, u.focus, 6, dt);
      tmp.copy(u.home); if (u.kind !== 'fork') tmp.x = px(u.s) + u.off * (portrait ? 0.42 : 1); tmp.y += Math.sin(t * 1.1 + u.ph) * 0.05;
      if (u.f > 0.001) { ahead.set(0, 0, -2.2).applyQuaternion(camera.quaternion).add(camera.position); ahead.y -= 0.15; tmp.lerp(ahead, u.f); }
      c.position.copy(tmp);
      c.rotation.set(u.rot.x, u.rot.y * (1 - u.f), u.rot.z + Math.sin(t * 0.9 + u.ph) * 0.02 + wig * 0.25);
      if (u.f > 0.01) c.quaternion.slerp(camera.quaternion, u.f);
      const pass = u.f > 0.01 ? 1 : Math.max(0, Math.min(1, (u.s - sCam - (portrait ? 2.4 : 0.8)) / 1.2)); // cards fold away as you glide past
      c.scale.setScalar(Math.max(0.0001, pop * pass));
      c.visible = pop * pass > 0.01;
    });
    // the plane flies ahead, banking with the path, and loops when the day changes
    const pl = plane.userData; pl.loop = Math.max(0, pl.loop - dt / 1.1);
    path(sCam + 3.4, tmp); const sway = Math.sin(t * 0.8) * 0.35;
    const L = 1 - pl.loop, ang = pl.loop > 0 ? L * Math.PI * 2 : 0;
    plane.position.set(tmp.x + sway, (portrait ? 2.5 : 1.95) + Math.sin(t * 1.3) * 0.08 + (pl.loop > 0 ? Math.sin(ang) * 0.45 : 0), tmp.z + (pl.loop > 0 ? (1 - Math.cos(ang)) * 0.45 : 0));
    path(sCam + 4.0, ahead); plane.lookAt(ahead.x + sway, plane.position.y, ahead.z); plane.rotateX(-ang); plane.rotateZ(-Math.cos(t * 0.8) * 0.35);
    conf.step(dt);
  });
  let dragging = false;

  function setMode() {
    stage.hemi.intensity = 2.2; stage.sun.intensity = 1.2;
    dotMat.color.set(dark() ? 0x3A3A44 : 0xB4B4BE); blobMat.opacity = dark() ? 0.5 : 0.1; blobMat.color.set(dark() ? 0x000000 : 0x14141f);
    faces.forEach((f) => f.draw());
  }
  setMode();

  const ray = new Raycaster(), v2 = new Vector2();
  let youCard = null;
  stage.show();
  return {
    overviewLabel: 'Postcards from the trip · swipe through the days',
    beats: [[-1, 1800], [0, 3000], [1, 3000], [2, 3000], [3, 3000], [4, 4400]],
    setDay(i, instant) { focus(null); if (i !== cur && !instant) plane.userData.loop = 1; cur = i; sWant = camFor(i); if (instant) sCam = sWant; },
    setMode,
    dragStart() { dragging = true; dragFrom = sWant; focus(null); },
    dragMove(f) { sWant = Math.max(-1, Math.min(endS - 1, dragFrom - f * 9)); },
    dragEnd(f, vel) {
      dragging = false;
      const proj = sWant - vel * 4; let best = -1, bd = Math.abs(proj - camFor(-1));
      dayS.forEach((_, i) => { const d = Math.abs(proj - camFor(i)); if (d < bd) { bd = d; best = i; } });
      if (best === cur && Math.abs(f) > 0.06) best = Math.max(-1, Math.min(DAYS.length - 1, cur + (f < 0 ? 1 : -1)));
      if (best !== cur) plane.userData.loop = 1;
      cur = best; sWant = camFor(best); api.onDay(best);
    },
    tap(x, y) {
      v2.set(x, y); ray.setFromCamera(v2, camera);
      const hit = ray.intersectObjects(cards.filter((c) => c.visible).map((c) => c.children[0]), false)[0];
      if (!hit) { focus(null); return; }
      const c = hit.object.userData.card; c.userData.wig.kick(2); focus(c);
    },
    cheer() { cards.forEach((c, i) => setTimeout(() => c.userData.wig.kick(3 + Math.random() * 2), i * 18)); plane.userData.loop = 1; conf.fire(plane.position.clone(), 0.8); },
    fork(home) {
      if (youCard) return;
      const from = Math.max(2, sCam + 2.6), kit = new Kit();
      const end = branchDots(from, 1, stage.aspect < 1 ? 3.4 : 5.2, kit, stage.aspect < 1 ? 0.9 : 2.6); const m = kit.mesh(dotMat); scene.add(m);
      youCard = addCard(forkFace('Your copy · change anything', `from ${home.name} · just now`, true), 1.7, from + 3.6, 0, 1.3, { kind: 'fork', hidden: true });
      youCard.position.set(end.x, stage.aspect < 1 ? 1.3 : 1.7, end.z); youCard.userData.home.copy(youCard.position); youCard.rotation.y = -0.5; youCard.userData.rot.copy(youCard.rotation);
      youCard.userData.pop.t = 1; youCard.userData.pop.kick(3); focus(null); sWant = from - (stage.aspect < 1 ? 0.6 : 0.2);
      api.onCaption(`<span class="eyebrow">Your fork · from ${home.name}</span><h2>A new branch, just for you</h2><p>Priya & Dev keep the credit; you keep a copy.</p>`);
    },
    dispose() { stage.dispose(); },
  };
});
