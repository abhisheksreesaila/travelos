// The page side of every cover concept (a small classic script, loaded first): picks light or dark and phone or
// wide, decides between the live 3D world and the calm stills, runs the scroll conductor, and loads the scene
// script only when the live world is wanted. Native scroll is the source of truth; the scene reads an exact
// value for the DOM and a damped one for the camera (Meng To's scroll conductor, MIT, adapted).
(function () {
  const Q = new URLSearchParams(location.search);
  const root = document.documentElement;
  const concept = root.dataset.concept;
  const REDUCE = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);

  /* ---------- light or dark, phone or wide ---------- */
  let mode = Q.get('mode') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const layoutOf = () => (innerWidth < 760 || innerWidth / innerHeight < 0.85 ? 'phone' : 'wide');
  let layout = layoutOf();
  const setClasses = () => {
    root.classList.remove('light', 'dark', 'phone', 'wide');
    root.classList.add(mode, layout);
    if (Q.has('clean') || Q.has('shot')) root.classList.add('clean');
    if (Q.has('capture')) root.classList.add('capture');
  };
  setClasses();

  /* ---------- live world or calm stills ---------- */
  const glOK = (() => { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (e) { return false; } })();
  const weak = (navigator.deviceMemory && navigator.deviceMemory <= 2) || (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 2);
  let still = Q.has('still') || REDUCE || !glOK || (weak && !Q.has('measure'));
  root.classList.add(still ? 'still' : 'live');

  const chapters = [...document.querySelectorAll('[data-chapter]')];
  const N = chapters.length;
  const stage = document.querySelector('.stage');
  const stillSrc = (i) => `stills/${concept}-${i}-${layout}-${mode}.webp`;

  // the poster: chapter 0's still, shown at once so the page is never empty
  const poster = stage.querySelector('.poster img');
  const setPoster = () => { const want = stillSrc(0); if (!poster.src.endsWith(want)) poster.src = want; };
  setPoster();

  /* ---------- the conductor ---------- */
  // Each chapter has a dwell (its card is pinned and its action plays: local 0 → 1) and then a travel to the next
  // chapter (cards swap, the camera flies). One scalar T = 2i + local during a dwell, 2i + 1 + travel after it.
  let anchors = [], maxY = 1, exact = 0, smooth = 0, widthAt = 0, active = -1;
  function measure() {
    const vh = innerHeight; maxY = Math.max(1, document.documentElement.scrollHeight - vh); widthAt = innerWidth;
    anchors = chapters.map((el) => { const top = el.offsetTop, h = el.offsetHeight; return { s: top, e: top + Math.max(1, h - vh) }; });
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
  function read() {
    exact = Math.min(tAt(scrollY), 2 * (N - 1) + 1);
    const i = clamp(Math.floor(exact / 2 + 0.25), 0, N - 1); // the card you are reading
    if (i !== active) {
      active = i;
      chapters.forEach((c, k) => c.classList.toggle('is-on', k === i));
      railBtns.forEach((b, k) => (k === i ? b.setAttribute('aria-current', 'step') : b.removeAttribute('aria-current')));
      if (still) showStill(i);
    }
    const foot = document.querySelector('.foot');
    const vis = !foot || foot.getBoundingClientRect().top > 2;
    if (vis !== api.visible) { api.visible = vis; api.emit('visible', vis); }
  }
  const state = () => {
    const i = Math.min(N - 1, Math.floor(smooth / 2)), f = smooth - 2 * i;
    return { exact, smooth, chapter: i, local: f <= 1 ? f : 1, travel: f > 1 ? f - 1 : 0, cam: f <= 1 ? i : i + (f - 1), N, active };
  };

  /* ---------- stills (reduced motion, no WebGL, weak phones) ---------- */
  const stills = stage.querySelector('.stills');
  const loaded = {};
  function showStill(i) {
    const add = (k) => { if (k < 0 || k >= N) return; const src = stillSrc(k); if (loaded[src]) return loaded[src]; const im = new Image(); im.alt = ''; im.decoding = 'async'; im.src = src; stills.appendChild(im); loaded[src] = im; return im; };
    const im = add(i); add(i + 1);
    [...stills.children].forEach((c) => c.classList.toggle('on', c === im));
    poster.style.opacity = i === 0 ? 1 : 0;
  }

  /* ---------- rail ---------- */
  const rail = document.querySelector('.rail');
  const railBtns = [];
  if (rail) chapters.forEach((c, i) => {
    const b = document.createElement('button'); b.type = 'button';
    b.innerHTML = `<i></i><span>${c.dataset.name || 'Chapter ' + (i + 1)}</span>`; b.setAttribute('aria-label', c.dataset.name || 'Chapter ' + (i + 1));
    b.onclick = () => scrollTo({ top: anchors[i].s + (anchors[i].e - anchors[i].s) * (i === 0 ? 0 : 0.8), behavior: REDUCE ? 'auto' : 'smooth' });
    rail.appendChild(b); railBtns.push(b);
  });

  /* ---------- press feedback (omxqua: everything tappable squashes) ---------- */
  document.addEventListener('pointerdown', (e) => { const b = e.target.closest('.btn, .chip'); if (b && !REDUCE) { b.classList.add('pressed'); const up = () => { b.classList.remove('pressed'); removeEventListener('pointerup', up); removeEventListener('pointercancel', up); }; addEventListener('pointerup', up); addEventListener('pointercancel', up); } });

  /* ---------- light / dark toggle ---------- */
  const toggle = document.querySelector('.js-mode');
  const paintToggle = () => { if (toggle) toggle.innerHTML = mode === 'dark' ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>' : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"/></svg>'; if (toggle) toggle.setAttribute('aria-label', mode === 'dark' ? 'Switch to the day scene' : 'Switch to the night scene'); };
  paintToggle();
  if (toggle) toggle.onclick = () => {
    mode = mode === 'dark' ? 'light' : 'dark'; setClasses(); paintToggle(); setPoster();
    if (still) { stills.innerHTML = ''; for (const k in loaded) delete loaded[k]; showStill(active); }
    api.mode = mode; api.emit('mode', mode);
    const u = new URL(location.href); u.searchParams.set('mode', mode); history.replaceState(null, '', u);
  };

  /* ---------- prototype switcher (←/→ cycles the concepts) ---------- */
  const order = ['a', 'b', 'c'];
  const go = (d) => { const k = order[(order.indexOf(concept) + d + order.length) % order.length]; location.href = `${k}.html?mode=${mode}`; };
  addEventListener('keydown', (e) => { if (e.target.closest('input, textarea, [contenteditable]')) return; if (e.key === 'ArrowRight' && e.altKey === false && e.shiftKey) go(1); if (e.key === 'ArrowLeft' && e.shiftKey) go(-1); });
  document.querySelectorAll('.proto [data-go]').forEach((a) => (a.onclick = (e) => { e.preventDefault(); go(+a.dataset.go); }));

  /* ---------- the api the scene script uses ---------- */
  const listeners = {};
  const api = window.GA_COVER = {
    concept, Q, REDUCE, mode, layout, still, visible: true, N,
    quality: Q.get('q') || (matchMedia('(pointer: coarse)').matches || innerWidth < 760 ? 'low' : 'high'),
    on(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); },
    emit(ev, v) { (listeners[ev] || []).forEach((f) => f(v)); },
    tick(dt) { smooth = REDUCE ? exact : smooth + (exact - smooth) * (1 - Math.exp(-5.2 * dt)); if (Math.abs(smooth - exact) < 1e-4) smooth = exact; return state(); },
    state, measure, read, yFor, anchors: () => anchors,
    jump(T) { measure(); scrollTo(0, yFor(T)); read(); smooth = exact; },
    ready() { stage.querySelector('canvas').classList.add('on'); setTimeout(() => (poster.style.opacity = 0), 520); },
    weak() { if (still) return; still = api.still = true; root.classList.remove('live'); root.classList.add('still'); stage.querySelector('canvas').classList.remove('on'); active = -1; read(); api.emit('weak'); },
  };

  /* ---------- wire up ---------- */
  measure(); read(); smooth = exact;
  addEventListener('scroll', read, { passive: true });
  addEventListener('resize', () => {
    const L = layoutOf(); const coarse = matchMedia('(pointer: coarse)').matches;
    if (L !== layout) { layout = L; api.layout = L; setClasses(); setPoster(); api.emit('layout', L); }
    else if (coarse && innerWidth === widthAt) return; // ignore the URL bar showing and hiding
    measure(); read();
  }, { passive: true });
  document.fonts && document.fonts.ready.then(() => { measure(); read(); });
  addEventListener('load', () => { measure(); read(); });
  document.addEventListener('visibilitychange', () => api.emit('hidden', document.hidden));

  // ?shot=<chapter>&local=<0..1> lands on a chapter deterministically (for captures and review links)
  if (Q.has('shot')) { const i = clamp(+Q.get('shot') || 0, 0, N - 1), l = Q.has('local') ? +Q.get('local') : 0.92; requestAnimationFrame(() => api.jump(2 * i + l)); }

  if (!still) {
    const s = document.createElement('script'); s.src = root.dataset.scene; s.async = true;
    s.onerror = () => api.weak();
    document.body.appendChild(s);
  } else {
    showStill(Math.max(0, active));
  }
})();
