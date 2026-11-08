// The cover's page side (cover v3, docs/decisions.md D-380..): day or night, the screenshots in the visitor's layout and mode, calm reveals as
// the story reaches the screen, and the booking tour (three beats over one screenshot: the words change, a ring shows the part they speak of,
// and on a phone the screen zooms to it). Native scroll is the source of truth; nothing here loads anything but the screenshots. Without this
// script every word and picture still shows (cover_boot.js sets html.cv-run before the first paint and takes it back if this never ran).
(function () {
  const root = document.documentElement, main = document.getElementById('main');
  if (!main || !root.classList.contains('cv-root')) return;
  const Q = new URLSearchParams(location.search);
  const DEBUG = main.dataset.debug === '1';
  const CALM = root.classList.contains('cv-calm');
  const PHONE = matchMedia(main.dataset.phone);
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const sysDark = matchMedia('(prefers-color-scheme: dark)');
  const modeNow = () => (window.cvMode ? window.cvMode() : sysDark.matches ? 'dark' : 'light');
  let mode = modeNow(), layout = PHONE.matches ? 'phone' : 'wide';
  const setMode = () => { root.classList.toggle('cv-dark', mode === 'dark'); root.classList.toggle('cv-light', mode !== 'dark'); };
  setMode();
  root.classList.add('cv-run');

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

  /* ---------- calm reveals ---------- */
  const rv = [...document.querySelectorAll('.cv-rv')];
  if (CALM || !('IntersectionObserver' in window)) rv.forEach((e) => e.classList.add('in'));
  else {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }),
      { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    rv.forEach((e) => io.observe(e));
  }

  /* ---------- the booking tour ---------- */
  const tour = document.querySelector('.cv-tour');
  const pin = tour && tour.querySelector('.cv-tour-pin');
  const lens = tour && tour.querySelector('.cv-lens');
  const inner = lens && lens.querySelector('.cv-lens-in');
  const beats = tour ? [...tour.querySelectorAll('.cv-beat')] : [];
  const parts = tour ? [...tour.querySelectorAll('.cv-ring, .cv-steps li')] : [];
  const N = beats.length;
  const SHORT = matchMedia('(max-height: 559px)');      // too short to pin a screen and its words: the beats become a plain list (cover.css)
  let beat = -1, forced = Q.has('beat') && DEBUG ? clamp(+Q.get('beat') || 0, 0, N - 1) : null;
  const ASPECT = 960 / 817;                                 // the booking crop (cover.py BOOK_SIZE)

  function fit() {
    // the lens takes the room the words leave: the whole screenshot on a laptop, a 4:5 window on a phone
    if (!tour) return;
    lens.style.width = lens.style.height = '';
    if (SHORT.matches) return;
    const cs = getComputedStyle(pin), padY = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom), gap = parseFloat(cs.rowGap) || 0;
    const steps = tour.querySelector('.cv-steps');
    const room = pin.clientHeight - padY - tour.querySelector('.cv-beats').offsetHeight - (steps.offsetHeight || 0) - 2 * gap;
    const maxW = lens.offsetWidth;                                   // what cover.css allows it: min(75rem, the column)
    const a = layout === 'phone' ? 4 / 5 : ASPECT;
    let w = maxW, h = w / a;
    if (h > room) { h = Math.max(120, room); w = h * a; }
    lens.style.width = `${Math.round(w)}px`; lens.style.height = `${Math.round(h)}px`;
  }
  function zoom() {
    // a phone zooms the screenshot to the beat's part (cover.py BEATS); a laptop shows it whole and only the rings move
    if (!inner) return;
    if (layout !== 'phone' || SHORT.matches || beat < 0) { inner.style.transform = ''; inner.style.setProperty('--k', 1); return; }
    const [x, y, w, h] = lens.dataset[`zoom-${beat}`].split(',').map(Number);
    const Fw = lens.clientWidth, Fh = lens.clientHeight, Ih = Fw / ASPECT;
    const k = Math.min(Fw / (w * Fw), Fh / (h * Ih), 2.8);
    let tx = Fw / 2 - (x + w / 2) * Fw * k, ty = Fh / 2 - (y + h / 2) * Ih * k;
    tx = clamp(tx, Fw - Fw * k, 0);
    ty = Ih * k > Fh ? clamp(ty, Fh - Ih * k, 0) : (Fh - Ih * k) / 2;
    inner.style.transform = `translate(${tx.toFixed(1)}px, ${ty.toFixed(1)}px) scale(${k.toFixed(3)})`;
    inner.style.setProperty('--k', k.toFixed(3));
  }
  function setBeat(i) {
    if (i === beat) return;
    beat = i;
    tour.dataset.beat = i;
    beats.forEach((b) => b.classList.toggle('on', +b.dataset.beat === i));
    parts.forEach((p) => p.classList.toggle('on', +p.dataset.beat === i));
    zoom();
  }
  function readTour() {
    if (!tour) return;
    if (forced !== null) return setBeat(forced);
    const r = tour.getBoundingClientRect(), span = Math.max(1, r.height - innerHeight);
    setBeat(clamp(Math.floor((-r.top / span) * N), 0, N - 1));
  }
  // where beat i shows (the review tools and the tests): the middle of its stretch of the tour
  const beatY = (i) => { const top = tour.getBoundingClientRect().top + scrollY, span = tour.offsetHeight - innerHeight; return top + (span * (i + 0.5)) / N; };

  /* ---------- which scene is on screen (html[data-cv-scene]) ---------- */
  const scenes = [...document.querySelectorAll('[data-scene]')];
  let active = -1;
  function readScene() {
    const y = innerHeight * 0.45;
    let i = 0;
    scenes.forEach((s, k) => { if (s.getBoundingClientRect().top <= y) i = k; });
    if (i !== active) { active = i; root.dataset.cvScene = i; }
  }

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
  let ticking = false;
  const read = () => { ticking = false; readTour(); readScene(); };
  const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(read); } };
  let widthAt = innerWidth;
  const coarse = matchMedia('(pointer: coarse)').matches;
  function relayout() {
    const L = PHONE.matches ? 'phone' : 'wide';
    if (L === layout && coarse && innerWidth === widthAt) return;      // the phone's address bar showing and hiding: keep everything where it is
    widthAt = innerWidth;
    if (L !== layout) { layout = L; if (shotsOwned) setShots(); }
    fit(); zoom(); read();
  }
  addEventListener('scroll', onScroll, { passive: true });
  addEventListener('resize', relayout, { passive: true });
  if (document.fonts) document.fonts.ready.then(() => { fit(); zoom(); read(); });
  fit(); read(); zoom();

  window.GA_COVER = {
    get layout() { return layout; }, get mode() { return mode; }, calm: CALM, debug: DEBUG,
    beat: () => beat, beats: N, beatY,
    scenes: () => scenes.map((s) => s.getBoundingClientRect().top + scrollY),
  };
  // ?scene=<n> lands on a scene (review links, scripts/cover_story_report.py); ?beat=<n> (off production) holds the booking tour on a beat
  if (Q.has('scene')) requestAnimationFrame(() => { const s = scenes[clamp(+Q.get('scene') || 0, 0, scenes.length - 1)]; scrollTo(0, s.getBoundingClientRect().top + scrollY); read(); });
})();
