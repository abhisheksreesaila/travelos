// The live side of every concept: one renderer, one scene, one camera for the whole page (Meng To's
// build-threejs-scroll-worlds: "one persistent Three.js world + one normalized reversible scroll state"),
// the render loop that pauses when the stage is covered or the tab is hidden, a quality governor that trades
// pixels for frame rate before it ever gives up on the world, the camera rig, and the in-world DOM anchors.
import { WebGLRenderer, Scene, PerspectiveCamera, Group, Vector3, Color, CatmullRomCurve3, NoToneMapping } from 'three';
import { buildTerrain, buildSky, skyUniforms, buildStars, buildWater, buildTrees, buildCabin, buildPier, buildTown, buildRoads, buildLift, buildDetails, buildFamily, buildCar, buildLights, STATES, mixState, PAGE } from './world.js';
import { buildBook } from './book.js';
import { buildSnow, buildSparkle } from './fx.js';
import { clamp, lerp, damp, easeIO, smooth, srgb } from './core.js';
import { landH, P } from './geo.js';

export const QUALITY = {
  high: { terrain: 230, trees: 2600, houses: 120, snow: 2600, stars: 2400, waterStep: 0.9, dpr: 1.75 },
  low: { terrain: 140, trees: 1150, houses: 70, snow: 1200, stars: 1300, waterStep: 1.4, dpr: 1.5 },
};

export function createScene(opts = {}) {
  const G = window.GA_COVER;
  const q = QUALITY[G.quality] || QUALITY.high;
  const capture = G.Q.has('capture'), measureMode = G.Q.has('measure');
  const canvas = document.querySelector('.stage canvas');
  const dpr0 = Math.min(devicePixelRatio || 1, q.dpr);
  const renderer = new WebGLRenderer({ canvas, antialias: dpr0 < 1.6, alpha: false, powerPreference: 'high-performance', preserveDrawingBuffer: capture });
  renderer.toneMapping = NoToneMapping;
  const scene = new Scene();
  const camera = new PerspectiveCamera(40, 1, 0.3, 1400);
  const L = buildLights(); scene.add(L.hemi, L.sun, L.sun.target); scene.fog = L.fog;

  /* ---------- the world ---------- */
  const SKYU = skyUniforms();
  const sky = buildSky(SKYU); scene.add(sky);
  const stars = buildStars(q.stars); scene.add(stars);
  const terrain = buildTerrain(q); scene.add(terrain);
  const water = buildWater(q, SKYU); scene.add(water);
  const riseGroup = new Group(); scene.add(riseGroup); // everything standing on the ground rises with it
  const TU = { uGrow: { value: 1 }, uLeaf: { value: 1 }, uSnowColor: { value: new Color(0xf3f6fa) }, uLeafColor: { value: new Color(0x7fb24a) }, uTreeSnow: { value: 1 } };
  const trees = buildTrees(q, TU, opts.trees || {}); riseGroup.add(trees);
  const cabin = buildCabin(1); cabin.position.set(P.cabin[0], landH(P.cabin[0], P.cabin[1]), P.cabin[1]); riseGroup.add(cabin);
  const nextCabin = buildCabin(0.8, 0x5e6f7a); nextCabin.position.set(P.nextCabin[0], landH(P.nextCabin[0], P.nextCabin[1]), P.nextCabin[1]); nextCabin.rotation.y = 0.35; riseGroup.add(nextCabin);
  const pier = buildPier(); riseGroup.add(pier);
  const town = buildTown(q); riseGroup.add(town);
  const roads = buildRoads(); riseGroup.add(roads);
  const lift = buildLift(); riseGroup.add(lift);
  const details = buildDetails(); riseGroup.add(details);
  const family = buildFamily(1.15); riseGroup.add(family);
  const car = buildCar(); car.scale.setScalar(2.4); riseGroup.add(car);
  const snow = buildSnow(q.snow); scene.add(snow);
  const sparkle = buildSparkle(); scene.add(sparkle);
  let book = opts.book === false ? null : buildBook(G.mode === 'dark'); if (book) scene.add(book);
  const W = { terrain, water, sky, stars, trees, cabin, nextCabin, pier, town, roads, lift, details, family, car, snow, sparkle, book, riseGroup, TU, SKYU, lights: L };

  /* ---------- the book rising into the world ---------- */
  function setRise(r, lit = r, grow = 999) {
    const U = terrain.userData.U;
    U.uRise.value = Math.max(r, 0.0005); U.uLit.value = lit; U.uGrowR.value = grow;
    riseGroup.scale.y = Math.max(r, 0.0005);
    water.material.uniforms.uRise.value = r; water.visible = r > 0.02;
    water.position.y = -0.06 * (1 - r);
  }

  /* ---------- atmosphere ---------- */
  const cur = mixState(STATES.day, STATES.day, 0);
  const tmp = new Color();
  function setAtmos(st, fog = [60, 420]) {
    Object.assign(cur, st);
    const S = SKYU;
    S.uZen.value.copy(srgb(st.zen)); S.uMid.value.copy(srgb(st.mid)); S.uHor.value.copy(srgb(st.hor)); S.uHaze.value.copy(srgb(st.haze));
    S.uSunDir.value.set(...st.sun); S.uSunCol.value.copy(srgb(st.sunCol)); S.uMoonDir.value.set(...st.moonDir);
    S.uGlow.value = st.glow; S.uSunDisc.value = st.disc; S.uMoon.value = st.moon;
    L.sun.position.set(st.sun[0] * 200, st.sun[1] * 200, st.sun[2] * 200); L.sun.color.set(st.sunCol); L.sun.intensity = st.sunI;
    L.sun.target.position.set(0, 0, 0);
    L.hemi.color.set(st.hemiSky); L.hemi.groundColor.set(st.hemiGround); L.hemi.intensity = st.hemiI;
    scene.fog.color.set(st.hor); scene.fog.near = fog[0]; scene.fog.far = fog[1];
    const wu = water.material.uniforms;
    wu.uDeep.value.copy(srgb(st.deep)); wu.uShallow.value.copy(srgb(st.shallow)); wu.uLightDir.value.set(...(st.night > 0.5 ? st.moonDir : st.sun)); wu.uLightCol.value.copy(srgb(st.sunCol)); wu.uSpec.value = st.spec;
    wu.uFogNear.value = fog[0]; wu.uFogFar.value = fog[1];
    stars.userData.set(st.stars);
    terrain.userData.U.uSnowColor.value.set(st.snow); TU.uSnowColor.value.set(st.snow); TU.uLeafColor.value.set(st.leaf);
    const n = st.night;
    const glow = tmp.set(0x2a3340).lerp(new Color(0xffc46b), smooth(0.25, 0.8, n)).getHex();
    cabin.userData.windows.color.set(glow); nextCabin.userData.windows.color.set(glow);
    town.userData.lights.opacity = smooth(0.2, 0.8, n);
    pier.userData.lamp.color.set(tmp.set(0xd8d4ca).lerp(new Color(0xffd28a), smooth(0.2, 0.8, n)).getHex());
    details.userData.fire.material.opacity = smooth(0.3, 0.8, n);
    details.userData.smoke.color.set(tmp.set(0xe9edf2).lerp(new Color(0x6d7a96), n).getHex());
    snow.userData.U.uColor.value.copy(srgb(n > 0.5 ? 0xc9d6f2 : 0xffffff));
    W.pins && (W.pins.userData.U.uNight.value = n);
    renderer.setClearColor(G.mode === 'dark' ? 0x000000 : 0xf2f2f5);
    SKYU.uBg.value.copy(srgb(G.mode === 'dark' ? 0x000000 : 0xf2f2f5));
  }
  function setSky(amt) { SKYU.uSkyAmt.value = amt; stars.visible = amt > 0.5; }

  /* ---------- camera rig ---------- */
  // Chapter endpoints are composed per layout before anything is interpolated; position and target each run
  // on a Catmull–Rom curve, and the lens shift moves the subject out from under the story card.
  let rig = null;
  function setRig(chapters) {
    const phone = G.layout === 'phone';
    const pick = (c) => (phone && c.phone ? { ...c, ...c.phone } : c);
    const cs = chapters.map(pick);
    rig = {
      cs,
      P: new CatmullRomCurve3(cs.map((c) => new Vector3(...c.p)), false, 'centripetal', 0.5),
      T: new CatmullRomCurve3(cs.map((c) => new Vector3(...c.t)), false, 'centripetal', 0.5),
    };
  }
  const _p = new Vector3(), _t = new Vector3(), _up = new Vector3();
  const par = { x: 0, y: 0, tx: 0, ty: 0 };
  if (matchMedia('(hover: hover) and (pointer: fine)').matches && !G.REDUCE) addEventListener('pointermove', (e) => { par.tx = (e.clientX / innerWidth) * 2 - 1; par.ty = (e.clientY / innerHeight) * 2 - 1; }, { passive: true });
  let shift = [0, 0];
  function placeCamera(cam, local, dt, extra) {
    const n = rig.cs.length - 1, i = clamp(Math.floor(cam), 0, n - 1), f = clamp(cam - i, 0, 1), e = easeIO(f);
    const u = clamp((i + e) / n, 0, 1);
    rig.P.getPoint(u, _p); rig.T.getPoint(u, _t);
    const A = rig.cs[i], B = rig.cs[Math.min(n, i + 1)];
    const atEnd = cam >= n;
    const C = atEnd ? rig.cs[n] : null;
    let fov = atEnd ? C.fov : lerp(A.fov, B.fov, e);
    // a slow drift while a card is pinned, so the world stays alive under the words
    const D = rig.cs[Math.round(cam)];
    if (D && D.drift && Math.abs(cam - Math.round(cam)) < 1e-3) { _p.x += D.drift[0] * local; _p.y += D.drift[1] * local; _p.z += D.drift[2] * local; }
    if (extra) extra(_p, _t);
    if (DBG) { _p.set(DBG[0], DBG[1], DBG[2]); _t.set(DBG[3], DBG[4], DBG[5]); fov = DBG[6] || fov; }
    par.x = damp(par.x, par.tx, 2.6, dt); par.y = damp(par.y, par.ty, 2.6, dt);
    _p.x += par.x * 0.8; _p.y -= par.y * 0.4;
    cam_.position.copy(_p);
    // the near plane follows the camera's height: from the book (hundreds of units up) a fixed 0.3 runs the depth
    // buffer out of precision and the map page z-fights the page block under it
    cam_.near = clamp(_p.y * 0.012, 0.3, 12);
    const ua = A.up || [0, 1, 0], ub = (atEnd ? C : B).up || [0, 1, 0];
    _up.set(lerp(ua[0], ub[0], e), lerp(ua[1], ub[1], e), lerp(ua[2], ub[2], e)).normalize();
    cam_.up.copy(_up); cam_.lookAt(_t);
    const sa = A.shift || [0, 0], sb = (atEnd ? C : B).shift || [0, 0];
    shift = [lerp(sa[0], sb[0], e), lerp(sa[1], sb[1], e)];
    if (Math.abs(cam_.fov - fov) > 1e-4) cam_.fov = fov;
    applyShift();
  }
  const cam_ = camera;
  const DBG = G.Q.get('cam') ? G.Q.get('cam').split(',').map(Number) : null; // ?cam=x,y,z,tx,ty,tz,fov frames a test view
  function cameraAt(cam) {
    const c = camera.clone(), n = rig.cs.length - 1, i = clamp(Math.floor(cam), 0, n - 1), f = clamp(cam - i, 0, 1), e = easeIO(f);
    const u = clamp((i + e) / n, 0, 1); rig.P.getPoint(u, c.position); const t = new Vector3(); rig.T.getPoint(u, t);
    const A = rig.cs[Math.round(cam)]; c.up.set(...(A.up || [0, 1, 0])); c.lookAt(t); c.fov = A.fov; c.aspect = vw / vh;
    const sh = A.shift || [0, 0]; if (sh[0] || sh[1]) c.setViewOffset(vw, vh, -sh[0] * vw, sh[1] * vh, vw, vh); else c.clearViewOffset();
    c.updateProjectionMatrix(); c.updateMatrixWorld(); return c;
  }
  let vw = 1, vh = 1;
  function applyShift() {
    camera.aspect = vw / vh;
    if (shift[0] || shift[1]) camera.setViewOffset(vw, vh, -shift[0] * vw, shift[1] * vh, vw, vh); else camera.clearViewOffset();
    camera.updateProjectionMatrix();
  }

  /* ---------- DOM anchors: labels and widgets that live at a place in the world ---------- */
  const anchors = [];
  const _v = new Vector3();
  function anchor(el, pos, opts = {}) { const a = { el, pos, o: -1, opts }; anchors.push(a); return a; }
  function updateAnchors(st) {
    for (const a of anchors) {
      const o = a.opts.show ? a.opts.show(st) : 0;
      if (o <= 0.001) { if (a.o !== 0) { a.el.style.opacity = 0; a.el.style.visibility = 'hidden'; a.o = 0; } continue; }
      let x, y;
      if (a.opts.screen) { x = a.opts.screen[0] * vw; y = a.opts.screen[1] * vh; } // fixed on the glass, like a heads-up display
      else {
        typeof a.pos === 'function' ? a.pos(_v) : _v.copy(a.pos);
        _v.project(camera);
        if (_v.z > 1) { a.el.style.visibility = 'hidden'; a.o = 0; continue; }
        x = (_v.x * 0.5 + 0.5) * vw + (a.opts.dx || 0); y = (-_v.y * 0.5 + 0.5) * vh + (a.opts.dy || 0);
      }
      const s = a.opts.scale ? a.opts.scale(st) : 1;
      a.el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(${a.opts.ax ?? -50}%, ${a.opts.ay ?? -100}%) scale(${s.toFixed(3)})${a.opts.rot ? ` rotate(${a.opts.rot(st).toFixed(2)}deg)` : ''}`;
      if (a.o !== o) { a.el.style.opacity = o.toFixed(3); a.el.style.visibility = 'visible'; a.o = o; }
    }
  }

  /* ---------- size, loop, governor ---------- */
  let scale = 1, dpr = dpr0;
  function resize() {
    const r = canvas.parentElement.getBoundingClientRect(); vw = Math.max(1, Math.round(r.width)); vh = Math.max(1, Math.round(r.height));
    renderer.setPixelRatio(dpr * scale); renderer.setSize(vw, vh, false);
    snow.userData.U.uSize.value = (vh / 900) * renderer.getPixelRatio();
    sparkle.userData.U.uSize.value = (vh / 900) * renderer.getPixelRatio();
    applyShift();
  }
  addEventListener('resize', () => resize(), { passive: true });
  const frames = [], work = []; window.__frames = frames; window.__work = work;
  const perf = { acc: 0, n: 0, bad: 0, t: 0 };
  let raf = 0, prev = 0, time = 0, running = false, update = null;
  function frame(now) {
    raf = 0;
    if (!running) return;
    const raw = prev ? (now - prev) / 1000 : 1 / 60; prev = now;
    const dt = Math.min(raw, 1 / 30);
    if (raw < 1) { frames.push(raw * 1000); if (frames.length > 1200) frames.shift(); }
    if (!measureMode && !capture) govern(raw);
    step(dt);
    raf = requestAnimationFrame(frame);
  }
  function step(dt) {
    const w0 = performance.now();
    time += dt;
    const st = G.tick(dt);
    update && update(st, dt, time);
    water.material.uniforms.uTime.value = time; snow.userData.U.uTime.value = time; snow.userData.U.uCam.value.copy(camera.position);
    sparkle.userData.U.uTime.value = time;
    lift.userData.step(time); details.userData.step(time); family.userData.step(dt);
    sky.position.copy(camera.position); stars.position.copy(camera.position);
    W.pins && W.pins.userData.step(dt);
    updateAnchors(st);
    renderer.render(scene, camera);
    work.push(performance.now() - w0); if (work.length > 1200) work.shift();
  }
  function govern(raw) {
    perf.t += raw; if (perf.t < 2.5) return;
    perf.acc += raw; perf.n++;
    if (perf.n < 45 && perf.acc < 1) return; // every 45 frames or every second, whichever comes first (Kage)
    const avg = perf.acc / perf.n; perf.acc = 0; perf.n = 0;
    if (avg > 0.023 && scale > 0.55) { scale = Math.max(0.55, scale * (avg > 0.045 ? 0.7 : 0.86)); resize(); }
    else if (avg < 0.0135 && scale < 1) { scale = Math.min(1, scale + 0.06); resize(); }
    // still slower than ~22 fps at the lowest resolution for three checks in a row: show the calm stills instead
    if (avg > 0.045 && scale <= 0.56) { if (++perf.bad >= 3) { stop(); G.weak(); } } else perf.bad = 0;
  }
  const start = () => { if (!running && G.visible && !document.hidden && !G.still) { running = true; prev = 0; raf = requestAnimationFrame(frame); } };
  const stop = () => { running = false; if (raf) cancelAnimationFrame(raf); raf = 0; };
  G.on('visible', (v) => (v ? start() : stop()));
  G.on('hidden', (h) => (h ? stop() : start()));
  G.on('weak', stop);
  canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); stop(); G.weak(); });

  const S = {
    renderer, scene, camera, W, q, setRise, setAtmos, setSky, setRig, placeCamera, anchor, resize, cur, cameraAt, size: () => [vw, vh], get time() { return time; },
    run(fn) {
      update = fn; resize();
      if (capture) { window.__cover = { step: (dt = 1 / 30) => step(dt), G, S }; step(1 / 60); G.ready(); return; }
      step(1 / 60); G.ready(); start();
      window.__cover = { G, S, stop, start, get running() { return running; } };
    },
    setBookDark(dark) { if (!book) return; const vis = book.visible; scene.remove(book); book = buildBook(dark); W.book = book; scene.add(book); book.visible = vis; },
  };
  return S;
}
