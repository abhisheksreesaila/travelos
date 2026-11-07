// The page around the 3D story: opener, day chips, day plan, Book lane, fork graph, Thank and Fork.
// Loads the scene script (three.js inside) only when the stage nears the screen, and only with WebGL and
// no reduced-motion preference; otherwise it shows a calm still of the same scene. Throwaway prototype code.
import { TRIP, DAYS, LANE, FORKS, ICON, KIND_COLOR } from './trip.js';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const I = (n, cls = '') => `<svg class="i ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${ICON[n]}"/></svg>`;
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const q = new URLSearchParams(location.search);
const root = document.documentElement;
const PROTO = root.dataset.proto;
const PROTOS = [['diorama', 'Toy diorama'], ['postcards', 'Postcards'], ['globe', 'Globe to street']];
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const desk = () => innerWidth >= 1020;

/* ---------- light / dark ---------- */
let mode = q.get('mode') || localStorage.getItem('ga3d-mode') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
const applyMode = () => { root.classList.toggle('dark', mode === 'dark'); root.classList.toggle('light', mode !== 'dark'); };
applyMode();

/* ---------- markup ---------- */
const mark = `<span class="mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round"><path class="l" d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9M12 12v3"/><circle class="a" cx="6" cy="6" r="2.6"/><circle class="b" cx="18" cy="6" r="2.6"/><circle class="c" cx="12" cy="18" r="2.6"/></svg></span>`;
const thankBtn = () => `<button class="btn tonal thank js-thank" aria-pressed="false">${I('star', 'star')}<span>Thank</span><span class="count num js-tcount">${TRIP.thanks.toLocaleString('en-US')}</span></button>`;
const forkBtn = (short) => `<button class="btn fill fork js-fork">${I('fork')}<span class="js-flabel" data-short="${short ? 1 : ''}">${short ? 'Fork' : 'Fork this trip'}</span><span class="count num js-fcount">${TRIP.forks}</span></button>`;

document.body.innerHTML = `
<header class="top">
  <a class="brand" href="index.html">${mark}<span>GitAway</span></a>
  <nav class="protos" aria-label="Prototypes">${PROTOS.map(([k, n], i) => `<a class="${k === PROTO ? 'on' : ''}" href="${k}.html${q.get('mode') ? `?mode=${mode}` : ''}"><b>${i + 1}</b><span>${n}</span></a>`).join('')}</nav>
  <button class="btn tonal icon mode js-mode" aria-label="Switch light or dark">${I(mode === 'dark' ? 'sun' : 'moon')}</button>
</header>
<main>
  <section class="open">
    <a class="creator" href="#"><span class="cav">${TRIP.initial}</span><span><b>${esc(TRIP.who)}</b><span>${TRIP.handle} · shared this trip</span></span></a>
    <h1 class="h-story">${TRIP.title} <em>${TRIP.titleEm}</em></h1>
    <p class="lede">${TRIP.story}</p>
    <div class="meta">${TRIP.meta.map((m) => `<span class="chip">${m}</span>`).join('')}</div>
    <div class="acts">${thankBtn()}${forkBtn()}</div>
  </section>
  <section class="stage-wrap" aria-label="The trip as a story">
    <div class="stage" id="stage">
      <picture><source media="(min-width: 1020px)" class="js-still-wide"><img class="still" alt="" decoding="async"></picture>
      <div class="stage-hint js-hint">${I('swipe')}Swipe for the next day</div>
      <div class="stage-tools"><button class="btn tonal icon play js-play" aria-label="Pause the story">${I('pause')}</button></div>
      <div class="cap js-cap" aria-live="polite"></div>
    </div>
    <div class="daychips" role="tablist" aria-label="Days">${DAYS.map((d, i) => `<button class="dchip" role="tab" data-day="${i}"><b>Day ${i + 1} · ${d.d}</b><span>${d.tag}</span></button>`).join('')}</div>
  </section>
  <section class="plan" aria-live="polite"><div class="plan-l js-planl"></div><div class="side js-side"></div></section>
  <section class="forks"><h2>Where this trip went</h2><p><span class="js-fcount2">${TRIP.forks}</span> families forked it. Here’s where some of them took it.</p><div class="graph js-graph"></div></section>
  <p class="proto-note">Prototype · sample trip, people and prices. Booking is links only; GitAway never takes payment.</p>
</main>
<nav class="sharebar" aria-label="Share">${thankBtn()}${forkBtn(true)}</nav>
<div class="toast js-toast" role="status"></div>`;

/* ---------- the day plan ---------- */
let day = Math.max(0, Math.min(4, +(q.get('day') || 1) - 1));
let litStop = -1;
const WD = ['Fri', 'Sat', 'Sun', 'Mon', 'Tue'];
function renderPlan() {
  const d = DAYS[day];
  $('.js-planl').innerHTML = `<span class="eyebrow">Day ${day + 1} of 5 · ${d.d} Oct</span>
    <h2>${d.title}</h2><p class="note">“${d.note}” <b>– ${TRIP.who}</b></p>
    <ol class="rail">${d.stops.map(([t, ap, k, n, s], i) => `<li style="--n:${i}"><time><b class="num">${t}</b><em>${ap}</em></time><span class="dot"></span>
      <div class="blk k-${k} ${i === litStop ? 'lit' : ''}" data-stop="${i}"><span class="kt">${I(k)}</span><div><b>${esc(n)}</b><span>${esc(s)}</span></div></div></li>`).join('')}</ol>`;
  const [wi, t, hi, lo, sub] = d.wx;
  $('.js-side').innerHTML = `<div class="wgrid">
      <article class="w wide k-weather"><div class="w-head"><span class="eyebrow">${day === 3 ? 'Malibu' : day === 1 ? 'Griffith Park' : 'Santa Monica'} · ${d.d}</span>${I(wi)}</div>
        <b class="big num">${t}°</b><div class="w-sub">${sub}</div><div class="w-meta num">H ${hi}° · L ${lo}° · last year’s weather on these dates</div>
        <div class="wx-row">${DAYS.map((x, i) => `<span class="${i === day ? 'on' : ''}"><em>${WD[i]}</em>${I(x.wx[0])}<b class="num">${x.wx[1]}°</b></span>`).join('')}</div></article>
      <article class="w k-stay"><div class="w-head"><span class="eyebrow">Stay</span>${I('stay')}</div><b class="w-name">The Tidewater</b><div class="w-meta">Santa Monica · 4 nights · 2 rooms</div></article>
      <article class="w k-car"><div class="w-head"><span class="eyebrow">Car</span>${I('car')}</div><b class="w-name">${day === 2 ? 'No car today' : 'Minivan, 2 seats'}</b><div class="w-meta">${day === 2 ? 'Bikes and the beach path' : 'LAX, Oct 16 → 20'}</div></article>
    </div>
    <div class="card"><h3>Book it your way <small>4 lanes</small></h3>
      <div class="lane">${LANE.map(([k, lane, a, b, why]) => `<a href="#" class="k-${k}"><span class="kt">${I(k)}</span><span><b>${lane} · ${a}</b><span>${b}</span><em class="why">${why}</em></span>${I('ext', 'ext')}</a>`).join('')}</div>
      <p class="honest">Every booking happens on the partner’s site, under their terms and their support.</p></div>`;
}

/* ---------- caption on the stage ---------- */
let capTimer = 0;
function setCaption(html) {
  const cap = $('.js-cap');
  cap.classList.add('swap'); clearTimeout(capTimer);
  capTimer = setTimeout(() => { cap.innerHTML = html; cap.classList.remove('swap'); }, reduced ? 0 : 160);
}
const dayCaption = (i) => i < 0
  ? `<span class="eyebrow">${scene?.overviewLabel || 'The whole trip'}</span><h2>${TRIP.title} ${TRIP.titleEm}</h2><p>5 days · 17 stops · tap a day</p>`
  : `<span class="eyebrow">Day ${i + 1} · ${DAYS[i].d}</span><h2>${DAYS[i].title}</h2><p>“${DAYS[i].note}”</p>`;
const stopCaption = (di, si) => { const [t, ap, k, n, s] = DAYS[di].stops[si]; return `<span class="eyebrow">Day ${di + 1} · ${t} ${ap}</span><div class="stop"><span class="kt k-${k}">${I(k)}</span><h2>${esc(n)}</h2></div><p>${esc(s)}</p>`; };

/* ---------- choosing a day (chips, swipe, scene, autoplay) ---------- */
let scene = null;
function selectChip() { $$('.dchip').forEach((c) => { const on = +c.dataset.day === day; c.classList.toggle('on', on); c.setAttribute('aria-selected', on); if (on) { const row = c.parentElement; const x = c.offsetLeft - row.offsetLeft - 16; if (x < row.scrollLeft || x + c.offsetWidth + 32 > row.scrollLeft + row.clientWidth) row.scrollTo({ left: x, behavior: reduced ? 'auto' : 'smooth' }); } }); }
function goDay(i, from = 'ui') {
  i = Math.max(-1, Math.min(DAYS.length - 1, i));
  litStop = -1;
  if (i >= 0 && i !== day) { day = i; renderPlan(); }
  if (i >= 0) selectChip(); else $$('.dchip').forEach((c) => c.classList.remove('on'));
  shown = i;
  setCaption(dayCaption(i));
  if (scene && from !== 'scene') scene.setDay(i);
}
let shown = day;
$$('.dchip').forEach((c) => c.addEventListener('click', () => { stopAuto(); goDay(+c.dataset.day); }));

/* autoplay: the short film, once, the first time the stage is seen; any touch stops it */
let autoT = 0, playing = false;
function beats() { return scene?.beats || [[-1, 1600], [0, 3000], [1, 3000], [2, 3000], [3, 3000], [4, 3200], [-1, 0]]; }
function play(fromStart = true) {
  if (!scene) return;
  playing = true; setPlayIcon();
  const b = beats(); let k = fromStart ? 0 : Math.max(0, b.findIndex(([d]) => d === shown) + 1);
  const step = () => { if (!playing) return; if (k >= b.length) { stopAuto(); return; } const [d, ms] = b[k++]; goDay(d); autoT = setTimeout(step, ms); };
  step();
}
function stopAuto() { playing = false; clearTimeout(autoT); setPlayIcon(); }
function setPlayIcon() { const b = $('.js-play'); b.innerHTML = I(playing ? 'pause' : 'play'); b.setAttribute('aria-label', playing ? 'Pause the story' : 'Play the story'); }
$('.js-play').addEventListener('click', () => (playing ? stopAuto() : play(shown === -1 || shown === 4)));

/* swipe on the stage: left/right changes the day; a scene may take the drag itself (postcards glide) */
(function swipe() {
  const st = $('#stage'); let x0 = 0, y0 = 0, t0 = 0, id = null, dragging = false, moved = false;
  st.addEventListener('pointerdown', (e) => { if (e.target.closest('button')) return; id = e.pointerId; x0 = e.clientX; y0 = e.clientY; t0 = performance.now(); dragging = false; moved = false; });
  st.addEventListener('pointermove', (e) => {
    if (e.pointerId !== id) return; const dx = e.clientX - x0, dy = e.clientY - y0;
    if (!dragging && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy)) { dragging = true; moved = true; stopAuto(); hint(false); st.setPointerCapture(id); scene?.dragStart?.(); }
    if (Math.abs(dy) > 10) moved = true;
    if (dragging) scene?.dragMove?.(dx / st.clientWidth);
  });
  const end = (e) => {
    if (e.pointerId !== id) return; id = null;
    const dx = e.clientX - x0, dt = Math.max(1, performance.now() - t0);
    if (dragging) {
      const v = dx / dt; // px per ms
      if (scene?.dragEnd) scene.dragEnd(dx / st.clientWidth, v);
      else if (Math.abs(dx) > 40 || Math.abs(v) > 0.4) goDay(dx < 0 ? (shown < 0 ? 0 : shown + 1) : shown - 1);
    } else if (!moved && scene?.tap) {
      const r = st.getBoundingClientRect(); stopAuto();
      scene.tap((e.clientX - r.left) / r.width * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    }
    dragging = false;
  };
  st.addEventListener('pointerup', end); st.addEventListener('pointercancel', end);
})();
function hint(on) { $('.js-hint').classList.toggle('gone', !on); }

/* ---------- Thank (like starring a repo) ---------- */
let thanked = false;
function burst(btn) {
  if (reduced) return;
  const r = btn.getBoundingClientRect(), cx = r.left + 26, cy = r.top + r.height / 2;
  const b = document.createElement('div'); b.className = 'burst'; b.style.left = cx + 'px'; b.style.top = cy + 'px';
  const cols = Object.values(KIND_COLOR);
  for (let k = 0; k < 16; k++) {
    const p = document.createElement('i'); if (k % 3 === 0) p.className = 'r';
    p.style.background = cols[k % cols.length]; b.appendChild(p);
    const a = (k / 16) * Math.PI * 2 + Math.random() * 0.4, d = 38 + Math.random() * 46;
    p.animate([{ transform: 'translate(0,0) scale(.4) rotate(0)', opacity: 1 }, { transform: `translate(${Math.cos(a) * d}px, ${Math.sin(a) * d - 14}px) scale(1) rotate(${Math.random() * 240 - 120}deg)`, opacity: 1, offset: 0.55 }, { transform: `translate(${Math.cos(a) * d * 1.15}px, ${Math.sin(a) * d + 18}px) scale(.6) rotate(${Math.random() * 360}deg)`, opacity: 0 }], { duration: 760 + Math.random() * 200, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'forwards' });
  }
  const p1 = document.createElement('div'); p1.className = 'plus1'; p1.textContent = '+1'; p1.style.left = (r.right - 34) + 'px'; p1.style.top = (r.top - 4) + 'px';
  document.body.append(b, p1);
  p1.animate([{ transform: 'translateY(0) scale(.6)', opacity: 0 }, { transform: 'translateY(-18px) scale(1.1)', opacity: 1, offset: 0.35 }, { transform: 'translateY(-34px) scale(1)', opacity: 0 }], { duration: 900, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'forwards' });
  setTimeout(() => { b.remove(); p1.remove(); }, 1100);
}
function rollCount(el, n) {
  const txt = n.toLocaleString('en-US');
  if (reduced) { el.textContent = txt; return; }
  el.animate([{ transform: 'translateY(0)', opacity: 1 }, { transform: 'translateY(-60%)', opacity: 0 }], { duration: 140, easing: 'ease-in' }).onfinish = () => {
    el.textContent = txt; el.animate([{ transform: 'translateY(60%)', opacity: 0 }, { transform: 'translateY(0)', opacity: 1 }], { duration: 300, easing: 'linear(0, 0.226, 0.577, 0.831, 0.964, 1.014, 1.023, 1.014, 1.004, 1)' });
  };
}
$$('.js-thank').forEach((btn) => btn.addEventListener('click', () => {
  thanked = !thanked;
  $$('.js-thank').forEach((b) => { b.classList.toggle('on', thanked); b.setAttribute('aria-pressed', thanked); $('span:not(.count)', b).textContent = thanked ? 'Thanked' : 'Thank'; });
  $$('.js-tcount').forEach((c) => rollCount(c, TRIP.thanks + (thanked ? 1 : 0)));
  if (thanked) { burst(btn); scene?.cheer?.(); }
}));

/* ---------- Fork ---------- */
let forked = false, toastT = 0;
function toast(html, ms = 5200) { const t = $('.js-toast'); t.innerHTML = html; t.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('on'), ms); }
$$('.js-fork').forEach((btn) => btn.addEventListener('click', () => {
  if (forked) { toast(`<div><b>Your copy is ready</b><span>Five sunny days in LA · yours to change</span></div><button class="btn">Open</button>`, 3000); return; }
  forked = true; stopAuto();
  $$('.js-fork').forEach((b) => { b.classList.add('done'); $('.js-flabel', b).textContent = 'Forked'; });
  $$('.js-fcount').forEach((c) => rollCount(c, TRIP.forks + 1)); rollCount($('.js-fcount2'), TRIP.forks + 1);
  FORKS.unshift({ id: 'you', lane: 1, from: 'u2', who: 'You', ini: 'Y', you: true, home: youHome().name, text: 'forked it · your copy, change anything', meta: 'Just now · Priya & Dev get the credit' });
  renderGraph();
  scene?.fork?.(youHome());
  toast(`<div><b>Forked. It’s yours now.</b><span>Priya & Dev see the thanks; you get a copy to change.</span></div><button class="btn">Open</button>`);
}));
/* where "you" are, guessed from the time zone only (no permission, nothing sent anywhere) */
function youHome() {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
  const C = { 'America/Chicago': ['Chicago', -87.6, 41.9], 'America/New_York': ['New York', -74, 40.7], 'America/Denver': ['Denver', -105, 39.7], 'America/Los_Angeles': ['Seattle', -122.3, 47.6], 'Europe/London': ['London', -0.1, 51.5], 'Europe/Paris': ['Paris', 2.35, 48.9], 'Europe/Berlin': ['Berlin', 13.4, 52.5], 'Asia/Kolkata': ['Bengaluru', 77.6, 13], 'Asia/Calcutta': ['Bengaluru', 77.6, 13], 'Asia/Tokyo': ['Tokyo', 139.7, 35.7], 'Australia/Sydney': ['Sydney', 151.2, -33.9] };
  const c = C[tz] || ['New York', -74, 40.7];
  return { name: c[0], lon: c[1], lat: c[2] };
}

/* ---------- the fork graph ---------- */
const LANE_X = (l) => 26 + l * 30;
function renderGraph() {
  const g = $('.js-graph'); const lanes = Math.max(...FORKS.map((f) => f.lane)) + 1; const indent = LANE_X(lanes - 1) + 30;
  g.innerHTML = `<svg class="lines"></svg>` + FORKS.map((f) => `<div class="grow ${f.you ? 'you' : ''}" data-id="${f.id}" style="padding-left:${indent}px">
    <span class="node ${f.commit ? 'commit' : ''}" style="position:absolute;left:${LANE_X(f.lane) - (f.commit ? 8 : 17)}px;top:50%;transform:translateY(-50%);${f.av ? `--av:${f.av}` : ''}">${f.commit ? '' : f.ini}</span>
    <div class="txt"><b>${esc(f.who)}</b> <span>${esc(f.text)}${f.home ? ` · from ${f.home}` : ''}</span><span>${f.meta}</span></div></div>`).join('');
  const svg = $('svg', g); svg.setAttribute('width', g.clientWidth); svg.setAttribute('height', g.clientHeight);
  const y = {}; $$('.grow', g).forEach((r) => { y[r.dataset.id] = r.offsetTop + r.offsetHeight / 2; });
  const byId = Object.fromEntries(FORKS.map((f) => [f.id, f]));
  svg.innerHTML = FORKS.filter((f) => f.from).map((f) => {
    const p = byId[f.from], px = LANE_X(p.lane), py = y[p.id], rx = LANE_X(f.lane), ry = y[f.id];
    const d = px === rx ? `M${px} ${py}L${rx} ${ry}` : `M${px} ${py}C${px} ${py - 30} ${rx} ${py - 12} ${rx} ${py - 42}L${rx} ${ry}`;
    const len = Math.abs(py - ry) + Math.abs(px - rx) + 20;
    return `<path class="${f.you ? 'you' : f.lane === 0 ? 'main' : ''}" style="--len:${len}" d="${d}"/>`;
  }).join('');
}

/* ---------- the stage: 3D or the calm still ---------- */
function stillSrc(wide) { return `stills/${PROTO}-${wide ? 'wide' : 'phone'}-${mode}.webp`; }
function showStill(why) {
  const st = $('#stage'); st.classList.add('is-still');
  $('.js-still-wide').srcset = stillSrc(true); const img = $('.still'); img.src = stillSrc(false);
  img.alt = `A still picture of the trip story (${why}).`; img.classList.add('on');
  stopAuto(); hint(false);
}
function webgl() { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch { return false; } }
function weakDevice() { return (navigator.deviceMemory && navigator.deviceMemory <= 2) || (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 2); }

const api = {
  days: DAYS, get mode() { return mode; }, get day() { return shown; }, desk, capture: q.has('capture'), measure: q.has('measure'),
  onDay(i) { if (i !== shown) goDay(i, 'scene'); },
  onStop(di, si) { if (di !== day) { day = di; renderPlan(); selectChip(); } litStop = si; renderPlan(); setCaption(stopCaption(di, si)); },
  onCaption(html) { setCaption(html); },
  onWeak() { scene?.dispose?.(); scene = null; $('canvas', $('#stage'))?.remove(); showStill('this device is busy, so the story stays still'); },
};
window.GA3D = { register(factory) {
  scene = factory($('#stage'), api);
  window.__story = { scene, goDay, play };
  if (q.has('day')) { goDay(day); scene.setDay(day, true); stopAuto(); return; }
  scene.setDay(-1, true);
  if (q.has('noauto') || api.capture) { goDay(-1); return; }
  const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { io.disconnect(); play(true); } }, { threshold: 0.5 });
  io.observe($('#stage'));
} };

function bootStage() {
  if (q.has('still') || reduced) return showStill(reduced ? 'reduced motion is on' : 'still mode');
  if (!webgl()) return showStill('WebGL is not available');
  if (weakDevice() && !q.has('force3d') && !q.has('measure')) return showStill('a lighter picture for this phone');
  const io = new IntersectionObserver(([e]) => {
    if (!e.isIntersecting) return; io.disconnect();
    const s = document.createElement('script'); s.src = `dist/${PROTO}.js`; s.onerror = () => showStill('the story could not load'); document.head.appendChild(s);
  }, { rootMargin: '300px' });
  io.observe($('#stage'));
}

$('.js-mode').addEventListener('click', () => {
  mode = mode === 'dark' ? 'light' : 'dark'; localStorage.setItem('ga3d-mode', mode); applyMode();
  $('.js-mode').innerHTML = I(mode === 'dark' ? 'sun' : 'moon');
  scene?.setMode?.(mode);
  if ($('#stage').classList.contains('is-still')) { $('.js-still-wide').srcset = stillSrc(true); $('.still').src = stillSrc(false); }
});
addEventListener('resize', () => renderGraph());

renderPlan(); selectChip(); setCaption(dayCaption(q.has('day') ? day : -1)); renderGraph(); bootStage();
if (reduced || q.has('still')) goDay(day);
