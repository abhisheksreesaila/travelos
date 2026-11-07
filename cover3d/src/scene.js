// The live side (F-206; from the prototype's scene.js, after Meng To's build-threejs-scroll-worlds, MIT): one renderer, one scene and one camera for
// the whole page; a render loop that stops when the closing screen covers the stage or the tab is hidden; a governor that trades pixels for frame
// rate before it ever gives up on the world (then the calm stills take over); the camera rig (Catmull-Rom through chapter endpoints composed per
// layout, with a lens shift so the subject is never under the words); and the in-world DOM anchors. Quality tiers decide how much world a device
// gets: a laptop the full set at up to 2x on a retina screen, a strong phone less, any other phone less again (Meng To's 3d-retina-resolution and
// optimize-threejs-games: measure, cap the pixel ratio, step down before giving up).
import { WebGLRenderer, Scene, PerspectiveCamera, Vector3, CatmullRomCurve3, ACESFilmicToneMapping, SRGBColorSpace, PCFShadowMap, DirectionalLight, HemisphereLight, Color, Object3D } from 'three';
import { clamp, lerp, damp, easeIO, Governor, pxAt } from './core.js';
import { buildSky, buildStars, skyUniforms, applySky, STATES, mixState } from './sky.js';

const FOREST_BOX = [-11500, -2500, 8000, 9500];      // the south shore, from Taylor Creek to Heavenly: where the simple firs stand
export const QUALITY = {
  high: { grid: 32, lodK: 5, tiles: 700, shadowSteps: 16, sparkle: 1, treeFar: 6500, heroR: 300, craftR: 90, heroCell: 9.5, midCell: 85, rocks: 240, houses: 2600, houseDensity: 1, dpr: 2, shadow: 2048, stars: 3600, snow: 2600, reflect: true, forestBox: FOREST_BOX },
  mid: { grid: 24, lodK: 4, tiles: 460, shadowSteps: 10, sparkle: 0.6, treeFar: 4200, heroR: 200, craftR: 60, heroCell: 13, midCell: 130, rocks: 140, houses: 1400, houseDensity: 0.75, dpr: 1.5, shadow: 1024, stars: 2000, snow: 1500, reflect: false, forestBox: FOREST_BOX },
  low: { grid: 16, lodK: 3.2, tiles: 300, shadowSteps: 0, sparkle: 0, treeFar: 2600, heroR: 140, craftR: 0, heroCell: 16, midCell: 190, rocks: 60, houses: 700, houseDensity: 0.5, dpr: 1.25, shadow: 0, stars: 1200, snow: 900, reflect: false, forestBox: FOREST_BOX },
};

export function createScene(G) {
  const q = { ...(QUALITY[G.tier] || QUALITY.high) };
  const capture = G.Q.has('capture'), measureMode = G.Q.has('measure');
  const canvas = document.querySelector('.cv-stage canvas');
  const dpr0 = Math.min(devicePixelRatio || 1, q.dpr);
  const renderer = new WebGLRenderer({ canvas, antialias: dpr0 < 1.6, alpha: false, logarithmicDepthBuffer: true, powerPreference: 'high-performance', preserveDrawingBuffer: capture });
  if (!renderer.capabilities.isWebGL2) throw new Error('the cover world needs WebGL2');
  renderer.toneMapping = ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.shadowMap.enabled = q.shadow > 0; renderer.shadowMap.type = PCFShadowMap; renderer.shadowMap.autoUpdate = false;
  const scene = new Scene();
  const camera = new PerspectiveCamera(40, 1, 0.05, 600000);

  const sun = new DirectionalLight(0xffffff, 3);
  const hemi = new HemisphereLight(0xcfe0ff, 0x8f9db4, 1);
  scene.add(sun, sun.target, hemi);
  if (q.shadow) {
    sun.castShadow = true; sun.shadow.mapSize.set(q.shadow, q.shadow); sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.04; sun.shadow.radius = 3;
    Object.assign(sun.shadow.camera, { near: 1, far: 1600, left: -90, right: 90, top: 90, bottom: -90 });
  }
  // the shadow box follows whatever the camera is close to (the cabin, the pier); far away there is nothing small to shade
  const shadowFocus = new Vector3();
  let shadowDirty = true;

  return { renderer, scene, camera, q, sun, hemi, capture, measureMode, canvas, dpr0, shadowFocus, setShadowDirty: () => (shadowDirty = true), get shadowDirty() { return shadowDirty; }, set shadowDirty(v) { shadowDirty = v; } };
}

/* ---------------------------------------------------------------- the rig */
export function makeRig(G, camera) {
  let rig = null, vw = 1, vh = 1, shift = [0, 0], floor = null;
  const _p = new Vector3(), _t = new Vector3(), _up = new Vector3();
  const par = { x: 0, y: 0, tx: 0, ty: 0 };
  if (matchMedia('(hover: hover) and (pointer: fine)').matches && !G.REDUCE) addEventListener('pointermove', (e) => { par.tx = (e.clientX / innerWidth) * 2 - 1; par.ty = (e.clientY / innerHeight) * 2 - 1; }, { passive: true });
  const DBG = G.Q.get('cam') ? G.Q.get('cam').split(',').map(Number) : null;      // ?cam=x,y,z,tx,ty,tz,fov frames a test or close-up view
  function set(chapters) {
    const phone = G.layout === 'phone';
    const cs = chapters.map((c) => (phone && c.phone ? { ...c, ...c.phone } : c));
    rig = { cs, P: new CatmullRomCurve3(cs.map((c) => new Vector3(...c.p)), false, 'centripetal', 0.5), T: new CatmullRomCurve3(cs.map((c) => new Vector3(...c.t)), false, 'centripetal', 0.5) };
  }
  function applyShift() {
    camera.aspect = vw / vh;
    if (shift[0] || shift[1]) camera.setViewOffset(vw, vh, -shift[0] * vw, shift[1] * vh, vw, vh); else camera.clearViewOffset();
    camera.updateProjectionMatrix();
  }
  function place(cam, local, dt, extra) {
    const n = rig.cs.length - 1, i = clamp(Math.floor(cam), 0, n - 1), f = clamp(cam - i, 0, 1), e = easeIO(f);
    const u = clamp((i + e) / n, 0, 1);
    rig.P.getPoint(u, _p); rig.T.getPoint(u, _t);
    const A = rig.cs[i], B = rig.cs[Math.min(n, i + 1)], atEnd = cam >= n, C = atEnd ? rig.cs[n] : null;
    let fov = atEnd ? C.fov : lerp(A.fov, B.fov, e);
    const D = rig.cs[Math.round(cam)];
    if (D && D.drift && Math.abs(cam - Math.round(cam)) < 1e-3) { _p.x += D.drift[0] * local; _p.y += D.drift[1] * local; _p.z += D.drift[2] * local; }
    if (extra) fov = extra(_p, _t, fov) ?? fov;
    if (DBG) { _p.set(DBG[0], DBG[1], DBG[2]); _t.set(DBG[3], DBG[4], DBG[5]); fov = DBG[6] || fov; }
    if (floor) _p.y = Math.max(_p.y, floor(_p.x, _p.z) + 2.4);                    // never inside a hillside
    par.x = damp(par.x, par.tx, 2.6, dt); par.y = damp(par.y, par.ty, 2.6, dt);
    const sway = Math.min(1, _p.distanceTo(_t) / 2000) * 0.004 + 0.002;              // a slow parallax under the pointer, scaled to how far we look
    camera.position.copy(_p);
    const right = new Vector3().subVectors(_t, _p).cross(camera.up).normalize();
    camera.position.addScaledVector(right, par.x * _p.distanceTo(_t) * sway);
    camera.position.y -= par.y * _p.distanceTo(_t) * sway * 0.5;
    const ua = A.up || [0, 1, 0], ub = (atEnd ? C : B).up || [0, 1, 0];
    _up.set(lerp(ua[0], ub[0], e), lerp(ua[1], ub[1], e), lerp(ua[2], ub[2], e)).normalize();
    camera.up.copy(_up); camera.lookAt(_t);
    const sa = A.shift || [0, 0], sb = (atEnd ? C : B).shift || [0, 0];
    shift = [lerp(sa[0], sb[0], e), lerp(sa[1], sb[1], e)];
    if (Math.abs(camera.fov - fov) > 1e-4) camera.fov = fov;
    applyShift();
    return _t;
  }
  // a camera as it will be at a chapter's endpoint (for laying out the plan's widgets before the camera gets there)
  function cameraAt(cam) {
    const c = camera.clone(), n = rig.cs.length - 1, i = clamp(Math.floor(cam), 0, n - 1), f = clamp(cam - i, 0, 1), e = easeIO(f);
    const u = clamp((i + e) / n, 0, 1); rig.P.getPoint(u, c.position); const t = new Vector3(); rig.T.getPoint(u, t);
    const A = rig.cs[Math.round(cam)]; c.up.set(...(A.up || [0, 1, 0])); c.lookAt(t); c.fov = A.fov; c.aspect = vw / vh;
    const sh = A.shift || [0, 0]; if (sh[0] || sh[1]) c.setViewOffset(vw, vh, -sh[0] * vw, sh[1] * vh, vw, vh); else c.clearViewOffset();
    c.updateProjectionMatrix(); c.updateMatrixWorld(); return c;
  }
  return { set, place, cameraAt, size: (w, h) => { vw = w; vh = h; applyShift(); }, setFloor: (f) => (floor = f), get vw() { return vw; }, get vh() { return vh; } };
}

/* ---------------------------------------------------------------- DOM anchors: labels and widgets at a place in the world */
export function makeAnchors(camera, size) {
  const anchors = [], _v = new Vector3();
  return {
    add(el, pos, opts = {}) { const a = { el, pos, o: -1, opts }; anchors.push(a); return a; },
    update(st) {
      const [vw, vh] = size();
      for (const a of anchors) {
        const o = a.opts.show ? a.opts.show(st) : 0;
        if (o <= 0.001) { if (a.o !== 0) { a.el.style.opacity = 0; a.el.style.visibility = 'hidden'; a.o = 0; } continue; }
        typeof a.pos === 'function' ? a.pos(_v) : _v.copy(a.pos);
        _v.project(camera);
        if (_v.z > 1 || _v.z < -1) { a.el.style.visibility = 'hidden'; a.o = 0; continue; }
        const x = (_v.x * 0.5 + 0.5) * vw + (a.opts.dx || 0), y = (-_v.y * 0.5 + 0.5) * vh + (a.opts.dy || 0);
        const s = a.opts.scale ? a.opts.scale(st) : 1;
        a.el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(${a.opts.ax ?? -50}%, ${a.opts.ay ?? -100}%) scale(${s.toFixed(3)})${a.opts.rot ? ` rotate(${a.opts.rot(st).toFixed(2)}deg)` : ''}`;
        if (a.o !== o) { a.el.style.opacity = o.toFixed(3); a.el.style.visibility = 'visible'; a.o = o; }
      }
    },
  };
}

/* ---------------------------------------------------------------- the loop */
export function makeLoop(G, S, step, render) {
  const frames = [], work = []; window.__frames = frames; window.__work = work;
  let raf = 0, prev = 0, running = false, scale = 1;
  const resize = () => {
    const r = S.canvas.parentElement.getBoundingClientRect(), vw = Math.max(1, Math.round(r.width)), vh = Math.max(1, Math.round(r.height));
    S.renderer.setPixelRatio(S.dpr0 * scale); S.renderer.setSize(vw, vh, false);
    S.onResize && S.onResize(vw, vh);
  };
  const gov = new Governor({ onScale: (s) => { scale = s; resize(); }, onGiveUp: () => { stop(); G.weak(); } });
  function frame(now) {
    raf = 0;
    if (!running) return;
    const raw = prev ? (now - prev) / 1000 : 1 / 60; prev = now;
    const dt = Math.min(raw, 1 / 30);
    if (raw < 1) { frames.push(raw * 1000); if (frames.length > 1200) frames.shift(); }
    if (!S.measureMode && !S.capture) gov.feed(raw);
    const w0 = performance.now();
    step(dt); render();
    work.push(performance.now() - w0); if (work.length > 1200) work.shift();
    raf = requestAnimationFrame(frame);
  }
  const start = () => { if (!running && G.visible && !document.hidden && !G.still) { running = true; prev = 0; raf = requestAnimationFrame(frame); } };
  const stop = () => { running = false; if (raf) cancelAnimationFrame(raf); raf = 0; };
  G.on('visible', (v) => (v ? start() : stop()));
  G.on('hidden', (h) => (h ? stop() : start()));
  G.on('weak', stop);
  S.canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); stop(); G.weak(); });
  addEventListener('resize', resize, { passive: true });
  return { start, stop, resize, gov, get running() { return running; }, get scale() { return scale; } };
}

export { STATES, mixState, applySky, skyUniforms, buildSky, buildStars };
