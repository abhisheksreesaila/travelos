// The cover's page side (F-206): day or night, phone or laptop, the live 3D world or the calm stills, and the scroll conductor. Adapted from the
// prototype (docs/design/cover3d/src/page.js), after Meng To's scroll conductor (build-threejs-scroll-worlds, MIT).
// It is the only script that ever fetches the world: three.js, assets/js/cover/world.js and the terrain, and only when the live world is wanted.
// Native scroll is the source of truth; the world reads an exact value for the DOM and a damped one for its camera.
(function () {
  const root = document.documentElement, main = document.getElementById('main');
  if (!main || !root.classList.contains('cv-root')) return;
  const Q = new URLSearchParams(location.search);
  const REDUCE = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const PHONE = matchMedia(main.dataset.phone);
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const sysDark = matchMedia('(prefers-color-scheme: dark)');
  const modeNow = () => (window.cvMode ? window.cvMode() : sysDark.matches ? 'dark' : 'light');
  let mode = modeNow(), layout = PHONE.matches ? 'phone' : 'wide';
  const setMode = () => { root.classList.toggle('cv-dark', mode === 'dark'); root.classList.toggle('cv-light', mode !== 'dark'); };
  setMode();

  /* ---------- the live world or the calm stills ---------- */
  // The stills: reduced motion, ?still, no WebGL, no ES modules or DecompressionStream (the terrain is gzip), weak phones (2 GB or 2 cores or fewer),
  // and Save-Data or a 2G connection: none of them download three.js or the world.
  const glOK = (() => {
    try {
      const c = document.createElement('canvas'), gl = c.getContext('webgl2') || c.getContext('webgl');
      if (gl) { const x = gl.getExtension('WEBGL_lose_context'); if (x) x.loseContext(); }
      return !!gl;
    } catch (e) { return false; }
  })();
  const nav = navigator, net = nav.connection || {};
  const weakDevice = (nav.deviceMemory && nav.deviceMemory <= 2) || (nav.hardwareConcurrency && nav.hardwareConcurrency <= 2);
  const thrifty = net.saveData || /(^|-)2g$/.test(net.effectiveType || '');
  const able = 'noModule' in HTMLScriptElement.prototype && 'DecompressionStream' in window;
  let still = root.classList.contains('cv-still') || !glOK || !able || (!Q.has('measure') && (weakDevice || thrifty));
  root.classList.toggle('cv-still', still); root.classList.toggle('cv-live', !still);
  // How much world this device gets: a laptop the full set, a strong phone the lighter terrain and fewer trees, any other phone less again.
  // The world's governor then trades resolution for frame rate, and gives up for the stills if even that is not enough.
  const coarse = matchMedia('(pointer: coarse)').matches;
  const strong = (nav.deviceMemory || 4) >= 4 && (nav.hardwareConcurrency || 4) >= 6;
  const tier = Q.get('q') || (!coarse && !PHONE.matches ? 'high' : strong ? 'mid' : 'low');

  const chapters = [...document.querySelectorAll('[data-chapter]')];
  const N = chapters.length;
  const stage = document.querySelector('.cv-stage');
  const canvas = stage.querySelector('canvas');
  const STILLS = main.dataset.stills;
  const stillSrc = (i) => `${STILLS}/a-${i}-${layout}-${mode}.webp`;

  // The poster is chapter 0's still. The <picture> already chose day or night and phone or laptop without a script; from here this script owns it,
  // so the site's own day/night switch (which a media query cannot see) is followed too.
  const poster = stage.querySelector('.cv-poster img');
  const setPoster = () => {
    const want = stillSrc(0);
    if ((poster.currentSrc || poster.src).endsWith(want)) return;                // the <picture> already chose it: leave it, no second download
    stage.querySelectorAll('.cv-poster source').forEach((s) => s.remove());
    poster.src = want;
  };
  setPoster();

  /* ---------- the conductor ---------- */
  // Each chapter has a dwell (its card is pinned while its action plays: local 0 → 1) and then a travel to the next one (the cards swap,
  // the camera flies). One number T = 2i + local during a dwell, 2i + 1 + travel after it.
  let anchors = [], exact = 0, smooth = 0, widthAt = 0, active = -1;
  function measure() {
    const vh = innerHeight; widthAt = innerWidth;
    anchors = chapters.map((el) => { const top = el.getBoundingClientRect().top + scrollY, h = el.offsetHeight; return { s: top, e: top + Math.max(1, h - vh) }; });
    anchors.forEach((a, i) => { a.t = i < N - 1 ? Math.max(a.e + 1, anchors[i + 1].s) : a.e; });
  }
  function tAt(y) {
    for (let i = 0; i < N; i++) {
      const a = anchors[i];
      if (y <= a.e || i === N - 1) return 2 * i + clamp((y - a.s) / (a.e - a.s), 0, 1);
      if (y < a.t) return 2 * i + 1 + (y - a.e) / (a.t - a.e);
    }
    return 2 * (N - 1) + 1;
  }
  const yFor = (T) => { const i = Math.floor(T / 2), f = T - 2 * i, a = anchors[clamp(i, 0, N - 1)]; return f <= 1 ? a.s + (a.e - a.s) * f : a.e + (a.t - a.e) * (f - 1); };
  const close = document.querySelector('.cv-close');
  function read() {
    exact = Math.min(tAt(scrollY), 2 * (N - 1) + 1);
    const i = clamp(Math.floor(exact / 2 + 0.25), 0, N - 1);      // the card you are reading
    if (i !== active) {
      active = i;
      chapters.forEach((c, k) => c.classList.toggle('is-on', k === i));
      railBtns.forEach((b, k) => (k === i ? b.setAttribute('aria-current', 'step') : b.removeAttribute('aria-current')));
      root.dataset.cvChapter = i;
      if (still || !worldReady) showStill(i);
    }
    // the closing screen covers the whole stage: nothing behind it needs drawing
    const vis = !close || close.getBoundingClientRect().top > 2;
    if (vis !== api.visible) { api.visible = vis; api.emit('visible', vis); }
  }
  const state = () => {
    const i = Math.min(N - 1, Math.floor(smooth / 2)), f = smooth - 2 * i;
    return { exact, smooth, chapter: i, local: f <= 1 ? f : 1, travel: f > 1 ? f - 1 : 0, cam: f <= 1 ? i : i + (f - 1), N, active };
  };

  /* ---------- stills: the calm version, and what shows while the world is still loading ---------- */
  const stills = stage.querySelector('.cv-stills');
  const loaded = {};
  function showStill(i) {
    if (!still && i === 0) return;                                  // the poster is chapter 0
    const add = (k) => {
      if (k < 0 || k >= N) return null;
      const src = stillSrc(k);
      if (!loaded[src]) { const im = new Image(); im.alt = ''; im.decoding = 'async'; im.src = src; stills.appendChild(im); loaded[src] = im; }
      return loaded[src];
    };
    const im = add(i); if (still) add(i + 1);                       // the next one ahead, so a scroll never waits
    [...stills.children].forEach((c) => c.classList.toggle('on', c === im));
    poster.classList.toggle('off', i !== 0);
  }
  const resetStills = () => { stills.textContent = ''; for (const k in loaded) delete loaded[k]; };

  /* ---------- the chapter rail (laptop) ---------- */
  const rail = document.querySelector('.cv-rail');
  const railBtns = chapters.map((c, i) => {
    const b = document.createElement('button'); b.type = 'button';
    b.innerHTML = '<i></i><span></span>'; b.lastChild.textContent = c.dataset.name; b.setAttribute('aria-label', c.dataset.name);
    b.addEventListener('click', () => scrollTo({ top: anchors[i].s + (anchors[i].e - anchors[i].s) * (i === 0 ? 0 : 0.8), behavior: REDUCE ? 'auto' : 'smooth' }));
    rail.appendChild(b);
    return b;
  });

  /* ---------- press feedback: everything tappable squashes (omxqua) ---------- */
  document.addEventListener('pointerdown', (e) => {
    const b = !REDUCE && e.target.closest('.cv-btn');
    if (!b) return;
    b.classList.add('pressed');
    const up = () => { b.classList.remove('pressed'); removeEventListener('pointerup', up); removeEventListener('pointercancel', up); };
    addEventListener('pointerup', up); addEventListener('pointercancel', up);
  });

  /* ---------- day or night follows the site's switch and the system ---------- */
  function followMode() {
    const m = modeNow();
    if (m === mode) return;
    mode = m; api.mode = m; setMode(); setPoster();
    resetStills(); if (still || !worldReady) showStill(Math.max(0, active));
    api.emit('mode', m);
  }
  sysDark.addEventListener('change', followMode);
  const watch = new MutationObserver(followMode);
  const attrs = { attributes: true, attributeFilter: ['class', 'data-theme', 'data-mode', 'data-color-scheme'] };
  watch.observe(root, attrs); watch.observe(document.body, attrs);

  /* ---------- the api the world uses (window.GA_COVER) ---------- */
  const listeners = {};
  let worldReady = false;
  const api = window.GA_COVER = {
    Q, REDUCE, mode, layout, still, tier, visible: true, N, assets: main.dataset.assets,
    on(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); },
    emit(ev, v) { (listeners[ev] || []).forEach((f) => f(v)); },
    tick(dt) { smooth = REDUCE ? exact : smooth + (exact - smooth) * (1 - Math.exp(-5.2 * dt)); if (Math.abs(smooth - exact) < 1e-4) smooth = exact; return state(); },
    state, measure, read, yFor, anchors: () => anchors,
    jump(T) { measure(); scrollTo(0, yFor(T)); read(); smooth = exact; },
    // the first frame is drawn: the canvas fades in over the poster (and any still), which then step aside
    ready() {
      worldReady = true; root.classList.add('cv-ready');
      canvas.classList.add('on');
      const done = () => { poster.classList.add('off'); stills.querySelectorAll('img.on').forEach((im) => im.classList.remove('on')); };
      canvas.addEventListener('transitionend', done, { once: true });
      if (getComputedStyle(canvas).transitionDuration === '0s') done();
    },
    // too slow even at the lowest resolution, or the world failed: the calm stills take over for the rest of the visit
    weak() {
      if (still) return;
      still = api.still = true; worldReady = false;
      root.classList.remove('cv-live', 'cv-ready'); root.classList.add('cv-still');
      canvas.classList.remove('on'); poster.classList.remove('off');
      active = -1; read();
      api.emit('weak');
    },
  };

  /* ---------- wire up ---------- */
  measure(); read(); smooth = exact;
  addEventListener('scroll', read, { passive: true });
  addEventListener('resize', () => {
    const L = PHONE.matches ? 'phone' : 'wide';
    if (L !== layout) { layout = L; api.layout = L; setPoster(); resetStills(); api.emit('layout', L); measure(); active = -1; read(); return; }
    if (coarse && innerWidth === widthAt) return;                   // the phone's address bar showing and hiding: keep the story where it is
    measure(); read();
  }, { passive: true });
  if (document.fonts) document.fonts.ready.then(() => { measure(); read(); });
  addEventListener('load', () => { measure(); read(); });
  document.addEventListener('visibilitychange', () => api.emit('hidden', document.hidden));

  // ?shot=<chapter>&local=<0..1> lands on a chapter exactly (captures, review links and tests)
  if (Q.has('shot')) { const i = clamp(+Q.get('shot') || 0, 0, N - 1), l = Q.has('local') ? +Q.get('local') : 0.92; requestAnimationFrame(() => api.jump(2 * i + l)); }

  if (still) { showStill(Math.max(0, active)); return; }
  // The live world: preload three.js beside the world so neither waits on the other, then run the world as a module. Until its first frame the
  // poster and (if you scroll before then) the stills keep the page full.
  for (const href of [main.dataset.three, main.dataset.world]) {
    if (!href) continue;
    const l = document.createElement('link'); l.rel = 'modulepreload'; l.href = href; document.head.appendChild(l);
  }
  const s = document.createElement('script'); s.type = 'module'; s.src = main.dataset.world;
  s.onerror = () => api.weak();
  document.body.appendChild(s);
})();
