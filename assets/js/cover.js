/*! Parts of this file are adapted from Meng To's agent skills (build-threejs-scroll-worlds), used under the MIT License:

MIT License

Copyright (c) 2026 Meng To

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/
// The cover's page side (F-206, the agreed story since D-354): day or night, phone or laptop, the live 3D world or the calm stills, the screenshots
// in the right mode, and the scroll conductor. Adapted from the prototype (docs/design/cover3d/src/page.js), after Meng To's scroll conductor
// (build-threejs-scroll-worlds, MIT). It is the only script that ever fetches the world: three.js, assets/js/cover/world.js and the terrain, and
// only when the live world is wanted. Native scroll is the source of truth. The story's scenes are DOM sections; the windows among them
// (data-world="from,dwell,to") say which stretch of the world's own timeline T (chapter c at rest is 2c, 0..13) plays while they are on screen:
// from -> dwell while the window slides in, dwell -> to while its card is pinned. Under a paper scene the world is covered and rests.
(function () {
  const root = document.documentElement, main = document.getElementById('main');
  if (!main || !root.classList.contains('cv-root')) return;
  // The capture and measuring tools' switches (?measure skips the weak-device check and the governor, ?capture, ?q picks the tier, ?cam frames a
  // view, ?shot=<world chapter>&local= holds the world there) work only where the page says data-debug, which production never renders.
  const DEBUG = main.dataset.debug === '1';
  const Q = new URLSearchParams(location.search);
  if (!DEBUG) ['measure', 'capture', 'q', 'cam', 'shot'].forEach((k) => Q.delete(k));
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
  const coarse = matchMedia('(pointer: coarse)').matches;
  const strong = (nav.deviceMemory || 4) >= 4 && (nav.hardwareConcurrency || 4) >= 6;
  const tier = Q.get('q') || (!coarse && !PHONE.matches ? 'high' : strong ? 'mid' : 'low');

  const WN = 7;                                                     // the world's own chapters (cover3d/src/main.js RIG)
  const scenes = [...document.querySelectorAll('[data-scene]')];
  const wins = scenes.filter((s) => s.dataset.world).map((el) => { const [a, m, b] = el.dataset.world.split(',').map(Number); return { el, a, m, b }; });
  const close = document.querySelector('.cv-close');
  const covers = [...scenes.filter((s) => !s.dataset.world), close].filter(Boolean);    // opaque: the world rests while one fills the screen
  const stage = document.querySelector('.cv-stage');
  const canvas = stage.querySelector('canvas');
  const STILLS = main.dataset.stills, SHOTS = main.dataset.shots;
  const stillSrc = (i) => `${STILLS}/a-${i}-${layout}-${mode}.webp`;

  // The poster is the world's first still. The <picture> already chose day or night and phone or laptop without a script; from here this script
  // owns it, so the site's own day/night switch (which a media query cannot see) is followed too.
  const poster = stage.querySelector('.cv-poster img');
  const setPoster = () => {
    const want = stillSrc(0);
    if ((poster.currentSrc || poster.src).endsWith(want)) return;                // the <picture> already chose it: leave it, no second download
    stage.querySelectorAll('.cv-poster source').forEach((s) => s.remove());
    poster.src = want;
  };
  setPoster();

  // The screenshots: their <picture>s choose by the system's mode; when the site's own switch says otherwise, this picks the other mode's files
  // (the widths are cover.py SHOT_W).
  const SHOT_W = { phone: [600], wide: [960, 1440] };
  let shotsOwned = false;
  function setShots() {
    if (!shotsOwned && mode === (sysDark.matches ? 'dark' : 'light')) return;
    shotsOwned = true;
    document.querySelectorAll('picture.cv-shot').forEach((pic) => {
      const name = pic.dataset.shot, img = pic.querySelector('img');
      pic.querySelectorAll('source').forEach((s) => s.remove());
      img.sizes = layout === 'phone' ? '300px' : '(min-width: 1600px) 900px, 58vw';      // cover.py SIZES
      img.srcset = SHOT_W[layout].map((w) => `${SHOTS}/${name}-${layout}-${mode}-${w}.webp ${w}w`).join(', ');
    });
  }
  setShots();

  /* ---------- the conductor ---------- */
  let segs = [], tops = [], exact = 0, smooth = 0, widthAt = 0, active = -1, shown = -1, forced = null;
  function measure() {
    const vh = innerHeight; widthAt = innerWidth;
    tops = scenes.map((el) => { const s = el.getBoundingClientRect().top + scrollY; return { s, e: el.dataset.world ? s + Math.max(1, el.offsetHeight - vh) : s }; });
    segs = wins.map((w) => { const top = w.el.getBoundingClientRect().top + scrollY; return { ...w, s0: Math.max(0, top - vh), s1: top, s2: top + Math.max(1, w.el.offsetHeight - vh) }; });
  }
  function tAt(y) {
    let T = segs.length ? segs[0].a : 0;
    for (const g of segs) {
      if (y < g.s0) break;
      if (y < g.s1) { T = g.a + ((g.m - g.a) * (y - g.s0)) / Math.max(1, g.s1 - g.s0); break; }
      if (y <= g.s2) { T = g.m + ((g.b - g.m) * (y - g.s1)) / (g.s2 - g.s1); break; }
      T = g.b;
    }
    return clamp(T, 0, 2 * (WN - 1) + 1);
  }
  function read() {
    exact = forced !== null ? forced : tAt(scrollY);
    const y = scrollY + innerHeight * 0.45;
    let i = 0;
    tops.forEach((t, k) => { if (t.s <= y) i = k; });
    if (i !== active) {
      active = i;
      railBtns.forEach((b, k) => (k === i ? b.setAttribute('aria-current', 'step') : b.removeAttribute('aria-current')));
      root.dataset.cvScene = i;
    }
    if (still || !worldReady) { const k = clamp(Math.round(exact / 2), 0, WN - 1); if (k !== shown) { shown = k; showStill(k); } }
    // a paper scene or the closing screen fills the screen: nothing behind it needs drawing
    // (two paper scenes meeting mid-screen cover it together)
    const h = innerHeight;
    let reach = 0;
    covers.map((el) => el.getBoundingClientRect()).filter((r) => r.bottom > 0 && r.top < h).sort((a, b) => a.top - b.top)
      .forEach((r) => { if (r.top <= reach + 1) reach = Math.max(reach, r.bottom); });
    const vis = reach < h - 1;
    if (vis !== api.visible) { if (vis) smooth = exact; api.visible = vis; api.emit('visible', vis); }
  }
  const state = () => {
    const i = Math.min(WN - 1, Math.floor(smooth / 2)), f = smooth - 2 * i;
    return { exact, smooth, chapter: i, local: f <= 1 ? f : 1, travel: f > 1 ? f - 1 : 0, cam: f <= 1 ? i : i + (f - 1), N: WN, active };
  };

  /* ---------- stills: the calm version, and what shows while the world is still loading ---------- */
  const stills = stage.querySelector('.cv-stills');
  const loaded = {};
  function showStill(i) {
    if (!still && i === 0) return;                                  // the poster is the first one
    const add = (k) => {
      if (k < 0 || k >= WN) return null;
      const src = stillSrc(k);
      if (!loaded[src]) { const im = new Image(); im.alt = ''; im.decoding = 'async'; im.src = src; stills.appendChild(im); loaded[src] = im; }
      return loaded[src];
    };
    const im = i === 0 ? null : add(i);
    [...stills.children].forEach((c) => c.classList.toggle('on', c === im));
    poster.classList.toggle('off', i !== 0);
  }
  const resetStills = () => { stills.textContent = ''; for (const k in loaded) delete loaded[k]; shown = -1; };

  /* ---------- the scene rail (laptop) ---------- */
  const rail = document.querySelector('.cv-rail');
  const go = (i) => { measure(); const t = tops[i]; scrollTo({ top: t.s + (t.e - t.s) * (i === 0 ? 0 : 0.6), behavior: REDUCE ? 'auto' : 'smooth' }); };
  const railBtns = scenes.map((c, i) => {
    const b = document.createElement('button'); b.type = 'button';
    b.innerHTML = '<i></i><span></span>'; b.lastChild.textContent = c.dataset.name; b.setAttribute('aria-label', c.dataset.name);
    b.addEventListener('click', () => go(i));
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
    mode = m; api.mode = m; setMode(); setPoster(); setShots();
    resetStills(); read();
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
    Q, debug: DEBUG, REDUCE, mode, layout, still, tier, visible: true, N: WN, assets: main.dataset.assets,
    on(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); },
    emit(ev, v) { (listeners[ev] || []).forEach((f) => f(v)); },
    tick(dt) { smooth = REDUCE ? exact : smooth + (exact - smooth) * (1 - Math.exp(-5.2 * dt)); if (Math.abs(smooth - exact) < 1e-4) smooth = exact; return state(); },
    state, measure, read,
    scenes: () => tops,                                              // each scene's scroll span: s (its top), e (where its pinned card lets go)
    // hold the world at T whatever the scroll (the capture tools' ?shot); null hands it back to the scroll
    jump(T) { forced = T; measure(); read(); smooth = exact; },
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
      measure(); shown = -1; read();
      api.emit('weak');
    },
  };

  /* ---------- wire up ---------- */
  measure(); read(); smooth = exact;
  addEventListener('scroll', read, { passive: true });
  addEventListener('resize', () => {
    const L = PHONE.matches ? 'phone' : 'wide';
    if (L !== layout) { layout = L; api.layout = L; setPoster(); if (shotsOwned) setShots(); resetStills(); api.emit('layout', L); measure(); active = -1; read(); return; }
    if (coarse && innerWidth === widthAt) return;                   // the phone's address bar showing and hiding: keep the story where it is
    measure(); read();
  }, { passive: true });
  if (document.fonts) document.fonts.ready.then(() => { measure(); read(); });
  addEventListener('load', () => { measure(); read(); });
  document.addEventListener('visibilitychange', () => api.emit('hidden', document.hidden));

  // ?scene=<n>&local=<0..1> lands on a scene of the story (review links and the report); ?shot=<world chapter>&local= holds the world (the capture tools)
  if (Q.has('scene')) {
    const i = clamp(+Q.get('scene') || 0, 0, scenes.length - 1), l = Q.has('local') ? +Q.get('local') : 0.6;
    requestAnimationFrame(() => { measure(); const t = tops[i]; scrollTo(0, t.s + (t.e - t.s) * l); read(); smooth = exact; });
  }
  if (Q.has('shot')) { const i = clamp(+Q.get('shot') || 0, 0, WN - 1), l = Q.has('local') ? +Q.get('local') : 0.92; requestAnimationFrame(() => api.jump(2 * i + l)); }

  if (still) return;
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
