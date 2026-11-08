// The cover's conductor (cover v4, docs/decisions.md D-400..): a camera over the app's real screens, scroll by scroll.
// Each chapter is a stage (gitaway/pages/cover.py): a tall section whose screen stays (position: sticky) while the scroll passes under it. One
// passive scroll listener asks for one frame; the frame reads scrollY once, turns it into each stage's progress p (0..1) and lets that stage's
// director write transforms and opacity (never layout) and toggle classes for the moments that play on their own (a pin dropping, a counter, a
// stamp: those run on the --motion-* tokens in cover.css). Native scroll is the source of truth: nothing here ever stops or steers it.
// Without this script, under reduced motion (html.cv-calm) or on a screen under 560 px tall, every stage is a still (cover.css).
(function () {
  const root = document.documentElement, main = document.getElementById('main');
  if (!main || !root.classList.contains('cv-root')) return;
  const Q = new URLSearchParams(location.search);
  const DEBUG = main.dataset.debug === '1';
  const CALM = root.classList.contains('cv-calm');
  const PHONE = matchMedia(main.dataset.phone);
  const TALL = matchMedia('(min-height: 560px)');           // cover.css pins the stages only from here
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (t) => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));
  const lin = (p, a, b) => clamp((p - a) / (b - a), 0, 1);
  const seg = (p, a, b) => smooth((p - a) / (b - a));
  const sysDark = matchMedia('(prefers-color-scheme: dark)');
  const modeNow = () => (window.cvMode ? window.cvMode() : sysDark.matches ? 'dark' : 'light');
  let mode = modeNow(), layout = PHONE.matches ? 'phone' : 'wide';
  const setMode = () => { root.classList.toggle('cv-dark', mode === 'dark'); root.classList.toggle('cv-light', mode !== 'dark'); };
  setMode();
  root.classList.add('cv-run');
  const film = () => !CALM && TALL.matches;
  root.classList.toggle('cv-film', !CALM);

  /* ---------- the screenshots: their <picture>s choose by the system's mode; when the site's own switch says otherwise this takes over ---------- */
  let shotsOwned = false;
  function setShots() {
    if (!shotsOwned && mode === (sysDark.matches ? 'dark' : 'light')) return;
    shotsOwned = true;
    document.querySelectorAll('picture.cv-shot').forEach((pic) => {
      const img = pic.querySelector('img');
      pic.querySelectorAll('source').forEach((s) => s.remove());
      img.sizes = pic.dataset[layout === 'phone' ? 'sizesPhone' : 'sizesWide'];
      img.srcset = pic.dataset[mode + (layout === 'phone' ? 'Phone' : 'Wide')];
    });
  }
  setShots();

  /* ---------- writing: only what changed, transforms and opacity ---------- */
  const memo = new Map();
  function put(el, t, o) {
    if (!el) return;
    let m = memo.get(el);
    if (!m) memo.set(el, (m = {}));
    if (t !== m.t) { el.style.transform = t; m.t = t; }
    if (o !== undefined) { o = Math.round(clamp(o, 0, 1) * 1000) / 1000; if (o !== m.o) { el.style.opacity = o; m.o = o; } }
  }
  const tf = (x = 0, y = 0, s = 1, r = 0) => `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)` + (s !== 1 ? ` scale(${s.toFixed(4)})` : '') + (r ? ` rotate(${r.toFixed(2)}deg)` : '');
  const flag = (el, on, cls = 'on') => { if (el && el.classList.contains(cls) !== on) el.classList.toggle(cls, on); };
  function clearAll() { memo.forEach((m, el) => { el.style.transform = ''; el.style.opacity = ''; }); memo.clear(); }
  // where an element sits inside `ref`, ignoring every transform (offsets, not client rects), so a measure never reads a moving camera
  function rel(el, ref) {
    let x = 0, y = 0, e = el;
    while (e && e !== ref) { x += e.offsetLeft; y += e.offsetTop; e = e.offsetParent; }
    return { x, y, w: el.offsetWidth, h: el.offsetHeight };
  }
  const nums = (s) => s.split(',').map(Number);
  // a morph: how the frame at rest must move and scale to sit on the card it grows out of (both measured at rest, the film's own moves undone)
  function morphFrom(s, from) {
    const els = [s.deal, s.morph, from], keep = els.map((e) => e.style.transform);
    els.forEach((e) => { e.style.transform = 'none'; });
    const c = from.getBoundingClientRect(), m = s.morph.getBoundingClientRect();
    els.forEach((e, i) => { e.style.transform = keep[i]; });
    s.mf = { sc: c.width / m.width, dx: c.left + c.width / 2 - (m.left + m.width / 2), dy: c.top + c.height / 2 - (m.top + m.height / 2) };
  }
  // a counter plays on its own, on the tokens: three screen moves long
  const DUR = (parseFloat(getComputedStyle(root).getPropertyValue('--motion-screen-dur')) || 1) * 3;
  function count(el, on) {
    if (!el) return;
    const to = +el.dataset.to;
    if (!on) { el.dataset.run = ''; el.textContent = '0'; return; }
    if (el.dataset.run) return;
    el.dataset.run = '1';
    const t0 = performance.now();
    const step = (t) => { const k = clamp((t - t0) / DUR, 0, 1); el.textContent = String(Math.round(to * (1 - (1 - k) ** 3))); if (k < 1 && el.dataset.run) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }

  /* ---------- the directors: one for each stage ---------- */
  const D = {};

  // 0. the opening: a laptop and a phone, tilted and big under the line; the scroll sets them down
  D.hero = {
    init(s) { s.copy = s.q('.cv-hero-copy'); s.dev = s.q('.cv-devices'); s.ph = s.q('.cv-phone'); s.stk = s.qa('.cv-stk'); s.hint = s.q('.cv-hint'); },
    run(s, p) {
      const e = seg(p, 0, 0.8), W = s.W, H = s.H, ph = layout === 'phone';
      put(s.dev, `perspective(${Math.round(H * 2)}px) translate3d(0, ${((1 - e) * H * (ph ? 0.2 : 0.3)).toFixed(1)}px, 0) rotateX(${(lerp(ph ? 18 : 30, 0, e)).toFixed(2)}deg) scale(${lerp(ph ? 1.04 : 1.12, 1, e).toFixed(4)})`);
      put(s.copy, tf(0, -e * H * 0.22, 1 - 0.06 * e), 1 - seg(p, 0.1, 0.42));
      put(s.ph, tf((1 - e) * W * (ph ? 0 : 0.1), (1 - e) * H * 0.06, 1, lerp(ph ? 0 : 9, ph ? 0 : -3, e)));
      s.stk.forEach((k, i) => put(k, tf(0, (1 - e) * H * (0.12 + 0.07 * i) * (i % 2 ? 1 : -0.6), lerp(0.7, 1, e), (1 - e) * (i % 2 ? 14 : -14)), 0.35 + 0.65 * e));
      put(s.hint, '', 1 - lin(p, 0, 0.08));
    },
  };

  // 1. book: the camera over the booking screen
  const ASPECT = 960 / 817;                                     // the booking crop (cover.py BOOK_SIZE)
  const ALL = [0, 0, 1, 1], MID = [0.12, 0, 0.88, 0.72];
  D.book = {
    init(s) {
      s.lens = s.q('.cv-lens'); s.cam = s.q('.cv-cam'); s.img = s.q('.cv-cam img'); s.field = s.q('.cv-field');
      s.spots = s.qa('.cv-spot'); s.rings = s.qa('.cv-ring'); s.calls = s.qa('.cv-call'); s.chips = s.qa('.cv-chip');
      s.words = s.qa('.cv-beat'); s.steps = s.qa('.cv-steps li'); s.counts = s.calls.map((c) => c.querySelector('.cv-count'));
      const d = s.lens.dataset; s.R = { all: ALL, mid: MID, fs: nums(d.camFs), fsPhone: nums(d.camFsPhone), wx: nums(d.camWx), drive: nums(d.camDrive) };
      s.plan = [[0, 'all'], [0.1, 'all'], [0.22, 'fs'], [0.35, 'fs'], [0.4, 'mid'], [0.46, 'wx'], [0.53, 'wx'], [0.6, 'drive'], [0.67, 'drive'], [0.75, 'all'], [1, 'all']];
    },
    fit(s, r) {
      const W = s.LW, H = s.LH, IW = W, IH = W / ASPECT;
      const k0 = Math.min(1, H / IH);
      const k = Math.max(k0, Math.min(W / (r[2] * IW), H / (r[3] * IH)) * 0.94);
      let tx = W / 2 - (r[0] + r[2] / 2) * IW * k, ty = H / 2 - (r[1] + r[3] / 2) * IH * k;
      tx = IW * k > W ? clamp(tx, W - IW * k, 0) : (W - IW * k) / 2;
      ty = IH * k > H ? clamp(ty, H - IH * k, 0) : (H - IH * k) / 2;
      return [tx, ty, k];
    },
    measure(s) {
      s.LW = s.lens.clientWidth; s.LH = s.lens.clientHeight;
      s.keys = s.plan.map(([p, k]) => [p, s.R[k === 'fs' && layout === 'phone' ? 'fsPhone' : k]]);
      const L = rel(s.lens, s.el.firstElementChild), [tx, ty, k] = this.fit(s, ALL), IW = s.LW;
      s.fly = s.chips.map((c) => {
        const [x, y, w, h] = nums(c.dataset.from), to = rel(c, s.el.firstElementChild);
        const sx = L.x + tx + (x + w / 2) * IW * k, sy = L.y + ty + (y + h / 2) * (IW / ASPECT) * k;
        return { dx: sx - (to.x + to.w / 2), dy: sy - (to.y + to.h / 2), sc: clamp((w * IW * k) / to.w, 0.5, 1.6) };
      });
    },
    run(s, p) {
      let i = 0;
      while (i < s.keys.length - 2 && p > s.keys[i + 1][0]) i++;
      const [p0, a] = s.keys[i], [p1, b] = s.keys[i + 1], t = seg(p, p0, p1);
      const [tx, ty, k] = this.fit(s, a.map((v, j) => lerp(v, b[j], t)));
      put(s.cam, `translate3d(${tx.toFixed(1)}px, ${ty.toFixed(1)}px, 0) scale(${k.toFixed(4)})`);
      const e = seg(p, 0, 0.1);
      put(s.lens, tf(0, (1 - e) * s.H * 0.16, 0.94 + 0.06 * e, (1 - e) * -2.5));
      put(s.field, tf((1 - e) * s.W * 0.08, (1 - e) * s.H * 0.1, 1, (1 - e) * 4), 1);
      const focus = p >= 0.19 && p < 0.37 ? 'fs' : p >= 0.43 && p < 0.555 ? 'wx' : p >= 0.575 && p < 0.69 ? 'drive' : p >= 0.8 ? 'go' : '';
      s.spots.forEach((l) => flag(l, l.dataset.spot === focus));
      s.rings.forEach((l) => flag(l, focus === 'go'));
      s.calls.forEach((c, j) => { const on = focus === (j ? 'drive' : 'wx'); flag(c, on); count(s.counts[j], on); });
      const word = p < 0.13 ? '' : p < 0.38 ? '0' : p < 0.7 ? '1' : p < 0.79 ? 'all' : '2';
      s.words.forEach((w) => flag(w, w.dataset.beat === word));
      s.field.dataset.k = focus === 'wx' ? 'wx' : focus === 'drive' ? 'car' : word === 'all' ? 'stay' : focus === 'go' ? 'tix' : 'flight';
      const step = word === '' || word === '0' ? 0 : word === '1' ? 1 : word === 'all' ? 2 : 3;
      s.steps.forEach((d, j) => flag(d, j === step));
      s.chips.forEach((c, j) => {
        const f = s.fly[j], m = seg(p, 0.8 + j * 0.012, 0.88 + j * 0.012);
        put(c, tf(f.dx * (1 - m), f.dy * (1 - m), lerp(f.sc, 1, m), (1 - m) * (j % 2 ? 10 : -10)), p < 0.8 ? 0 : clamp(m * 5, 0, 1));
      });
    },
  };

  // 2. a head start: trips deal in, one is imported, it becomes Lena and Sam's trip
  D.head = {
    init(s) {
      s.cards = s.qa('.cv-trip'); s.headr = s.q('.cv-ill-head'); s.pick = s.q('.cv-trip.pick'); s.btn = s.q('.cv-trip.pick .cv-fake-btn');
      s.burst = s.q('.cv-burst'); s.stamp = s.q('.cv-stamp'); s.deal = s.q('.cv-deal'); s.morph = s.q('.cv-morph'); s.copy = s.q('.cv-copy');
    },
    measure(s) {
      morphFrom(s, s.pick);
    },
    run(s, p) {
      s.cards.forEach((c, i) => { const d = seg(p, 0.02 + 0.07 * i, 0.18 + 0.07 * i); put(c, tf((1 - d) * s.W * 0.6, (1 - d) * s.H * 0.05, 1, (1 - d) * (7 + 3 * i)), d); });
      put(s.headr, '', seg(p, 0, 0.06));
      flag(s.btn, p >= 0.4 && p < 0.46, 'pressed');
      flag(s.pick, p >= 0.45, 'done');
      flag(s.burst, p >= 0.45);
      flag(s.stamp, p >= 0.48);
      const m = seg(p, 0.58, 0.8), f = s.mf;
      put(s.deal, tf(0, -m * s.H * 0.04, 1 - 0.1 * m), 1 - m);
      put(s.morph, tf(f.dx * (1 - m), f.dy * (1 - m), lerp(f.sc, 1, m)), clamp(m * 3, 0, 1));
      if (layout === 'phone') put(s.copy, tf(0, -seg(p, 0.5, 0.62) * s.H * 0.08), 1 - seg(p, 0.5, 0.62));
      else put(s.copy, '', 1);
    },
  };

  // 3. then it comes with you: the cockpit dives into a day, the day becomes Ask, then the family chat
  D.with = {
    init(s) {
      const d = s.q('.cv-devices').dataset;
      s.sets = [['wide', s.q('.cv-laptop .cv-screen')], ['phone', s.q('.cv-phone .cv-screen')]].map(([lay, scr]) => {
        const L = {}; scr.querySelectorAll('.cv-layer').forEach((l) => (L[l.dataset.layer] = l));
        return { lay, scr, L, r: nums(d[lay === 'wide' ? 'todayWide' : 'todayPhone']) };
      });
      s.feats = s.qa('.cv-feat'); s.ask = s.q('.cv-ask'); s.typed = s.q('.cv-typed'); s.text = s.typed.dataset.text; s.bubs = s.qa('.cv-bub'); s.n = -1;
    },
    measure(s) {
      s.sets.forEach((x) => {
        x.w = x.scr.clientWidth; x.h = x.scr.clientHeight;
        const [rx, ry, rw, rh] = x.r, o = `${((rx + rw / 2) * 100).toFixed(2)}% ${((ry + rh / 2) * 100).toFixed(2)}%`;
        x.L.cockpit.style.transformOrigin = x.L.day.style.transformOrigin = o;
        x.kin = 1 / Math.max(rw, rh);
      });
    },
    run(s, p) {
      const z = seg(p, 0.18, 0.32), a = seg(p, 0.44, 0.5), f = seg(p, 0.7, 0.76);
      s.sets.forEach((x) => {
        if (x.lay === 'wide' && layout === 'phone') return;
        const L = x.L, r = x.r;
        put(L.cockpit, z ? `scale(${lerp(1, x.kin, z).toFixed(4)})` : '', 1 - seg(p, 0.25, 0.32));
        put(L.day, `scale(${lerp(Math.max(r[2], r[3]), 1, z).toFixed(4)})`, seg(p, 0.2, 0.27));
        put(L.ask, tf(0, (1 - a) * x.h * 0.3), a);
        put(L.family, tf((1 - f) * x.w * 0.35, 0), f);
      });
      const n = Math.round(lin(p, 0.52, 0.64) * s.text.length);
      if (n !== s.n) { s.n = n; s.typed.textContent = s.text.slice(0, n); }
      flag(s.ask, p >= 0.5 && p < 0.72);
      flag(s.ask, n === s.text.length, 'sent');
      s.bubs.forEach((b, i) => flag(b, p >= 0.78 + 0.06 * i));
      const k = p < 0.27 ? 0 : p < 0.47 ? 1 : p < 0.72 ? 2 : 3;
      s.feats.forEach((e, i) => flag(e, i === k));
    },
  };

  // 4. things a search won't tell you: the roads draw themselves and the pins drop, each with its tip
  D.tips = {
    init(s) { s.roads = s.qa('.cv-draw'); s.pins = s.qa('.cv-mpin'); s.cards = s.qa('.cv-tip'); s.at = [0.14, 0.3, 0.48, 0.7]; },
    run(s, p) {
      const d = [lin(p, 0.04, 0.52), lin(p, 0.5, 0.74)];
      s.roads.forEach((r, i) => { const v = (1 - d[i]).toFixed(4); if (r.dataset.v !== v) { r.dataset.v = v; r.style.strokeDashoffset = v; } });
      let cur = -1;
      s.at.forEach((t, i) => { const on = p >= t; if (on) cur = i; flag(s.pins[i], on); flag(s.cards[i], on); });
      s.cards.forEach((c, i) => flag(c, i === cur, 'cur'));
    },
  };

  // 5. leave a trail: published, the thanks tick up, the hearts rise
  D.trail = {
    init(s) { s.card = s.q('.cv-trail .cv-deal'); s.stamp = s.q('.cv-stamp'); s.big = s.q('.cv-bigwrap'); s.cnt = s.q('.cv-count'); s.quote = s.q('.cv-quote'); s.copy = s.q('.cv-copy'); },
    run(s, p) {
      const e = seg(p, 0, 0.22);
      put(s.card, tf((1 - e) * -s.W * 0.12, (1 - e) * s.H * 0.15, 0.92 + 0.08 * e, (1 - e) * -5), 0.2 + 0.8 * e);
      flag(s.stamp, p >= 0.24);
      flag(s.big, p >= 0.3);
      count(s.cnt, p >= 0.3);
      flag(s.quote, p >= 0.52);
    },
  };

  // 6. for creators: the post becomes a trip
  D.creators = {
    init(s) { s.post = s.q('.cv-post'); s.deal = s.q('.cv-deal'); s.morph = s.q('.cv-morph'); s.stamp = s.q('.cv-stamp'); s.copy = s.q('.cv-copy'); },
    measure(s) {
      morphFrom(s, s.post);
    },
    run(s, p) {
      const e = seg(p, 0, 0.2), m = seg(p, 0.36, 0.64), f = s.mf;
      put(s.post, tf((1 - e) * s.W * 0.3, (1 - e) * s.H * 0.05, 1, (1 - e) * 8), e);
      put(s.deal, tf(0, 0, 1 - 0.15 * m, -6 * m), 1 - m);
      put(s.morph, tf(f.dx * (1 - m), f.dy * (1 - m), lerp(f.sc, 1, m), (1 - m) * 6), clamp(m * 3, 0, 1));
      flag(s.stamp, p >= 0.68);
      if (layout === 'phone') put(s.copy, tf(0, -seg(p, 0.3, 0.42) * s.H * 0.06), 1 - seg(p, 0.3, 0.42));
      else put(s.copy, '', 1);
    },
  };

  // the close: the beach opens out behind the line and the doors
  D.end = {
    init(s) { s.img = s.q('.cv-photo img'); s.last = s.q('.cv-last'); s.stk = s.qa('.cv-stk'); },
    run(s, p) {
      const e = seg(p, 0, 0.7);
      put(s.img, `scale(${lerp(1.3, 1, e).toFixed(4)})`);
      put(s.last, tf(0, (1 - e) * s.H * 0.12, 0.94 + 0.06 * e), 0.3 + 0.7 * e);
      s.stk.forEach((k, i) => flag(k, p >= 0.25 + 0.06 * i));
    },
  };

  /* ---------- the stages ---------- */
  const stages = [...document.querySelectorAll('.cv-stage')].map((el) => {
    const s = { el, key: el.dataset.stage, p: -1, q: (sel) => el.querySelector(sel), qa: (sel) => [...el.querySelectorAll(sel)] };
    s.d = D[s.key];
    if (s.d && s.d.init) s.d.init(s);
    return s;
  }).filter((s) => s.d);
  const scenes = [...document.querySelectorAll('[data-scene]')];
  const fill = document.querySelector('.cv-rail-fill');
  let docH = 0, vh = innerHeight, active = -1, held = null;

  function measure() {
    vh = innerHeight; docH = document.documentElement.scrollHeight;
    const on = film();
    stages.forEach((s) => {
      s.top = s.el.getBoundingClientRect().top + scrollY; s.len = Math.max(1, s.el.offsetHeight - vh);
      const st = s.el.firstElementChild; s.W = st.clientWidth; s.H = st.clientHeight;
      if (on && s.d.measure) s.d.measure(s);
      s.p = -1;
    });
  }
  // ?p= (off production) holds the stage at the top of the screen on one progress: the review tools' frames
  const hold = DEBUG && Q.has('p') ? clamp(+Q.get('p') || 0, 0, 1) : null;
  function frame() {
    ticking = false;
    const y = scrollY, on = film();
    if (on) stages.forEach((s) => {
      if (y + vh < s.top - vh * 0.5 || y > s.top + s.len + vh * 1.5) return;          // far off screen: leave it as it is
      const p = held === s && hold !== null ? hold : clamp((y - s.top) / s.len, 0, 1);
      if (p !== s.p) { s.p = p; s.d.run(s, p); }
    });
    if (fill) put(fill, layout === 'phone' ? `scaleX(${clamp(y / Math.max(1, docH - vh), 0, 1).toFixed(4)})` : `scaleY(${clamp(y / Math.max(1, docH - vh), 0, 1).toFixed(4)})`);
    const line = vh * 0.45;
    let i = 0;
    scenes.forEach((s, k) => { if (s.getBoundingClientRect().top <= line) i = k; });
    if (i !== active) { active = i; root.dataset.cvScene = i; root.dataset.cvTint = (scenes[i].querySelector('.cv-stage') || scenes[i]).dataset.stage || 'end'; }
  }
  let ticking = false;
  const ask = () => { if (!ticking) { ticking = true; requestAnimationFrame(frame); } };

  /* ---------- press feedback: a pill squashes a little under the finger ---------- */
  document.addEventListener('pointerdown', (e) => {
    const b = !CALM && e.target.closest('.cv-btn');
    if (!b) return;
    b.classList.add('pressed');
    const up = () => { b.classList.remove('pressed'); removeEventListener('pointerup', up); removeEventListener('pointercancel', up); };
    addEventListener('pointerup', up); addEventListener('pointercancel', up);
  });

  /* ---------- day or night follows the site's switch and the system ---------- */
  function followMode() {
    const m = modeNow();
    if (m === mode) return;
    mode = m; setMode(); setShots();
  }
  sysDark.addEventListener('change', followMode);
  const watch = new MutationObserver(followMode);
  const attrs = { attributes: true, attributeFilter: ['class', 'data-theme', 'data-mode', 'data-color-scheme'] };
  watch.observe(root, attrs); watch.observe(document.body, attrs);

  /* ---------- wire up ---------- */
  let widthAt = innerWidth, heightAt = innerHeight;
  const coarse = matchMedia('(pointer: coarse)').matches;
  function relayout() {
    const L = PHONE.matches ? 'phone' : 'wide';
    if (L === layout && coarse && innerWidth === widthAt && Math.abs(innerHeight - heightAt) < 160) return;   // the phone's address bar: keep still
    widthAt = innerWidth; heightAt = innerHeight;
    if (L !== layout) { layout = L; if (shotsOwned) setShots(); }
    clearAll(); measure(); frame();
  }
  addEventListener('scroll', ask, { passive: true });
  addEventListener('resize', relayout, { passive: true });
  TALL.addEventListener('change', relayout);
  addEventListener('load', () => { measure(); frame(); });
  if (document.fonts) document.fonts.ready.then(() => { measure(); frame(); });
  measure(); frame();

  const yAt = (key, p) => { const s = stages.find((x) => x.key === key); return s.top + s.len * p; };
  const BEAT_P = [0.28, 0.49, 0.9];
  window.GA_COVER = {
    get layout() { return layout; }, get mode() { return mode; }, calm: CALM, debug: DEBUG, get film() { return film(); },
    progress: (key) => { const s = stages.find((x) => x.key === key); return s ? s.p : -1; },
    yAt, beats: BEAT_P.length, beatY: (i) => yAt('book', BEAT_P[i]),
    beat: () => { const s = stages.find((x) => x.key === 'book'); const w = s && s.el.querySelector('.cv-beat.on'); return w ? w.dataset.beat : null; },
    scenes: () => scenes.map((s) => s.getBoundingClientRect().top + scrollY),
  };
  // ?scene=<n> lands on a scene (review links, scripts/cover_story_report.py); with ?p=<0..1> (off production) at that point of its stage
  if (Q.has('scene')) requestAnimationFrame(() => {
    const sc = scenes[clamp(+Q.get('scene') || 0, 0, scenes.length - 1)], s = stages.find((x) => sc.contains(x.el) || x.el === sc);
    if (s && Q.has('p') && DEBUG) { held = s; scrollTo(0, yAt(s.key, hold)); } else scrollTo(0, sc.getBoundingClientRect().top + scrollY);
    frame();
  });
})();
