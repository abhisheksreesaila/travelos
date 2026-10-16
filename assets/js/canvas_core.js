// The trip canvas, core (F-081; split into modules in F-128): week > day > block > step as one surface that zooms.
//
// Every level is a page of its own (gitaway/pages/tripcanvas.py), so with no script it is plain links and forms. With script, a tap on a link marked data-zoom
// ("in", "out" or "side"), the Day | Week toggle, or the browser's Back fetches that level as a fragment (?frag=1) and swaps it inside a View Transition. The element
// that was tapped (data-zk="day-2" | "blk-a3" | "stp-<id>") is named `cz-hero` before and after the swap, so it grows into the next level's heading or sheet and
// shrinks back on zoom out. No View Transitions: the new level scales and fades in (CSS .cz-in-*). Reduced motion: an instant swap.
//
// This module owns the level on the screen: fetching (with a cache, idle prefetch and the copy a write's reply hands over), swapping (a zoom, or in place with
// idiomorph so nothing is rebuilt), history, and the one write transport (`post`). The other modules hang off `window.CZ`:
//   canvas_writes.js    forms, Done that never waits, the toast and Undo
//   canvas_filters.js   the people/list filter and the All | Plans | Hotels ... row
//   canvas_sos.js       the emergency sheet from its <template>
//   canvas_gestures.js  a flick between days, hold to move a step, swipe for Done
// Hooks: `CZ.onSwap` (run inside every swap, before the cz:swap event) and `CZ.gesturing()` (a finger is doing something: no refresh may land).
// Load order (tripcanvas.py SCRIPTS): vendor/idiomorph.js, this, then the modules, then canvas_tick.js and day_*.js.
(function () {
  var stage = document.getElementById('cz');
  if (!stage) return;
  var root = document.documentElement;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var deskQ = window.matchMedia('(min-width: 1020px) and (not (display-mode: standalone))');
  function laptop() { return window.GA && GA.motion && GA.motion.calm ? GA.motion.calm() : deskQ.matches; }      // F-156: the laptop changes level with a short fade and nothing else (GA.motion.calm: the one desktop rule)
  var RANK = { week: 0, day: 1, block: 2, step: 3 };
  var KEY = /^[a-z]{3}-[A-Za-z0-9-]+$/;
  var CZ = { stage: stage, held: false, onSwap: [] };      // `held` is true while the day grid (day_grid.js) holds a block
  var STALE = 5000;        // a level shown from a copy older than this is fetched again in idle time and quietly updated if it changed (someone else may have edited)
  var cache = {};          // url -> { at, g, promise }: a level fetched ahead of time (idle, or as the finger went down), used by the tap that follows. F-170: a copy is shown at once whatever its age
  var gen = 0;             // moves on every write and every CZ.forget: a copy with an older `g` is shown all the same, then checked behind it (revalidate) and corrected if it changed
  var busy = false;
  var waiting = null;      // the browser's Back or Forward pressed while a zoom was running: run it when that zoom is done
  var idleQ = [];          // work that needs the zoom to be finished (a refresh after a drop)
  function whenIdle(fn) { if (busy) idleQ.push(fn); else fn(); }
  function drain() { while (idleQ.length && !busy) idleQ.shift()(); }

  function path(u) { var a = document.createElement('a'); a.href = u; return a.pathname + a.search; }
  function here() { return path(location.href); }
  function fragUrl(u) { return u + (u.indexOf('?') < 0 ? '?' : '&') + 'frag=1'; }
  function view() { return stage.querySelector('.cz-view'); }
  function levelOf(u) {
    var q = path(u).split('?')[1] || '';
    return /(^|&)step=/.test(q) || /(^|&)add=1/.test(q) || /(^|&)booked=/.test(q) || /(^|&)sos=1/.test(q) ? 'step' : /(^|&)block=/.test(q) ? 'block' : /(^|&)day=/.test(q) ? 'day' : 'week';
  }

  // ---- fetching ---------------------------------------------------------------------------------------------------------------
  // `epoch` counts writes (it moves when one starts and when it ends): a copy of a level fetched before a write, which answers after it, is stale and is never shown.
  // F-124: a write's reply carries the level drawn after it (`level`), kept in `handed` until the next write, so the refresh that follows needs no second trip to the server.
  var epoch = 0, handed = null;
  // F-170: a copy we have is returned at once, of any age. `force` asks the server again and puts the answer in its place when it comes (the old copy stays usable meanwhile).
  function fetchLevel(u, force) {
    if (handed && handed.u === u && handed.e === epoch) return Promise.resolve(handed.html);
    var hit = cache[u];
    if (hit && !force) return hit.promise;
    if (hit && hit.next && hit.next.g === gen) return hit.next.p;
    var p = fetch(fragUrl(u), { credentials: 'same-origin', headers: { 'X-Canvas': '1' } }).then(function (r) {
      if (!r.ok) throw new Error('level ' + r.status);
      return r.text();
    });
    var entry = { at: Date.now(), g: gen, promise: p };
    if (!hit) { cache[u] = entry; p.catch(function () { if (cache[u] === entry) delete cache[u]; }); }
    else {
      hit.next = { p: p, g: gen };
      p.then(function () { if (!cache[u] || cache[u].g <= entry.g) cache[u] = entry; }, function () { delete hit.next; });      // (an older answer arriving late never replaces a newer copy, a write's own level included)
    }
    return p;
  }
  function old(u) { var h = cache[u]; return !!h && (h.g !== gen || Date.now() - h.at > STALE); }      // a copy that may differ from the server's
  // A block or a step sheet cannot be corrected in place after it is shown (only the day and the week morph), so a copy of one from before a write, or over a minute old, is asked for again
  // (this is the one level that still waits): a sheet shown stale would say "Mark done" for a step that is done.
  var SHEET_FRESH = 60000;
  function sheetStale(u) { var h = cache[u], l = levelOf(u); return !!h && (l === 'step' || l === 'block') && (h.g !== gen || Date.now() - h.at > SHEET_FRESH); }

  // F-099: while the canvas sits idle the next levels are fetched, so Day | Week, a date, a flick and Back swap with nothing to wait for. The desktop week fetches every day (the phone week the same (up to 14 and then what scrolls into view, F-170);
  // a day fetches its neighbours, the week and the other dates. Fragments only, two at a time, in idle time, never on Data Saver or a slow link.
  var pq = [], pActive = 0, pPlanned = 0;
  var WEEK_AHEAD = 14;     // F-170: day fragments the phone's week fetches ahead without scrolling (about 35 KB each)
  var idle = window.requestIdleCallback ? function (fn) { window.requestIdleCallback(fn, { timeout: 1500 }); } : function (fn) { setTimeout(fn, 200); };
  function frugal() {
    var c = navigator.connection;
    return !!(c && (c.saveData || /(^|-)2g$/.test(c.effectiveType || '')));
  }
  function fresh(u) { var h = cache[u]; return !!h && h.g === gen && !sheetStale(u); }      // (a copy that only grew old with time is not fetched again ahead: it is checked when it is shown)
  // The addresses worth having ahead, the likeliest first. `near` (a day's neighbours, the week's days, a block's steps) is fetched at once, `rest` a moment later.
  function nextLevels() {
    var v = view(), near = [], rest = [], now = here();
    if (!v) return { near: near, rest: rest };
    var add = function (list, u) { if (u && u !== now && near.indexOf(u) < 0 && rest.indexOf(u) < 0) list.push(u); };
    if (v.dataset.level === 'week') {
      // F-145: the desktop week's Open the day and plan rows too. F-170: only rows with a box (the phone hides the desktop columns: their plan rows are 40 KB each and never tapped)
      // F-176: a plan row is fetched once; after a write its stale copy is not fetched again (one per plan, 40 KB each), it is checked when it is opened (F-170)
      v.querySelectorAll('a.cz-wopen[data-zoom="in"], a.cz-wi.is-plan[data-zoom="in"]').forEach(function (a) { if (boxed(a) && !(a.classList.contains('cz-wi') && cache[path(a.href)])) add(near, path(a.href)); });
      // The phone's day cards (about 35 KB each; the desktop columns' plan rows are never fetched there): every day of the trip, today's and its nearest first, at most WEEK_AHEAD;
      // on a longer trip the cards that come on screen are fetched too (the scroll calls prefetch)
      var h = window.innerHeight, rows = Array.prototype.slice.call(v.querySelectorAll('a.cz-row-link[data-zoom="in"]')).filter(boxed);
      var at = Math.max(0, rows.findIndex(function (a) { return !!a.closest('.is-today'); }));
      var seen = rows.map(function (a, i) { return { a: a, d: Math.abs(i - at) }; }).sort(function (x, y) { return x.d - y.d; }).map(function (x) { return x.a; });
      seen.slice(0, WEEK_AHEAD).forEach(function (a) { add(near, path(a.href)); });
      seen.slice(WEEK_AHEAD).forEach(function (a) { var r = a.getBoundingClientRect(); if (r.bottom > 0 && r.top < h * 1.5) add(near, path(a.href)); });
    } else if (v.dataset.level === 'day') {
      add(near, v.dataset.next && path(v.dataset.next));
      add(near, v.dataset.prev && path(v.dataset.prev));
      var wk = v.querySelector('#cz-z-week');
      if (wk) add(rest, path(wk.href));
      v.querySelectorAll('.cz-hchips a[href]').forEach(function (a) { add(rest, path(a.href)); });
    } else if (v.dataset.level === 'block') {      // F-132: the sheets of the steps on the screen (about 4 KB each on the wire), so a tap on one opens it with nothing to wait for
      var h = window.innerHeight;
      Array.prototype.slice.call(v.querySelectorAll('a.cz-step[data-zoom="in"]')).filter(function (a) {
        var r = a.getBoundingClientRect();
        return r.bottom > 0 && r.top < h;
      }).slice(0, 8).forEach(function (a) { add(near, path(a.href)); });
    }
    return { near: near, rest: rest };
  }
  function pump() {
    while (pActive < 2 && pq.length) {
      var u = pq.shift();
      if (fresh(u)) continue;
      pActive++;
      fetchLevel(u, !!cache[u]).catch(function () {}).then(function () { pActive--; if (pq.length) idle(pump); });
    }
  }
  function prefetch() {
    if (frugal() || document.hidden) return;
    var mine = ++pPlanned;
    idle(function () {
      if (mine !== pPlanned) return;      // a newer level was shown meanwhile
      var n = nextLevels();
      pq = n.near.filter(function (u) { return !fresh(u); });
      pump();
      if (n.rest.length) setTimeout(function () {      // F-170: the neighbours first (after a write they are what the next tap wants), the rest once those are on their way
        if (mine !== pPlanned) return;
        pq = pq.concat(n.rest.filter(function (u) { return !fresh(u); }));
        pump();
      }, 300);
    });
  }
  document.addEventListener('visibilitychange', function () { if (!document.hidden) prefetch(); });
  var scrolled = 0;      // a block's steps that come into view are fetched too
  window.addEventListener('scroll', function () { clearTimeout(scrolled); scrolled = setTimeout(function () { var v = view(); if (v && (v.dataset.level === 'block' || v.dataset.level === 'week')) prefetch(); }, 300); }, { passive: true });
  // A level is fetched as soon as a finger goes down on a link to it, so the tap that follows has nothing to wait for.
  document.addEventListener('pointerdown', function (e) {
    var a = e.target.closest ? e.target.closest('a[data-zoom]') : null;
    if (a && stage.contains(a) && a.dataset.zoom !== 'out') fetchLevel(path(a.href), sheetStale(path(a.href))).catch(function () {});
  }, { passive: true });

  // ---- swapping ---------------------------------------------------------------------------------------------------------------
  var curMode = '';        // how the level being shown was reached (push, replace, stay, pop), for the day grid's scroll
  var quietSwap = false;   // a swap that only brings the level up to date: nothing moves, and focus stays where it was
  var shown = '';          // the fragment on the stage, to see whether a fresh copy differs
  // F-122: `inPlace` updates what is already on the screen to the fresh copy, changing only what differs (vendor/idiomorph.js): nothing is rebuilt, so nothing flashes.
  // F-131: what the scripts own rides through it: their classes on an element the server also draws (the compact bar shown, a block selected, a filter's highlight), the
  // compact bar's inert state, and the hold menu (a node the server never draws). Without that the morph took them off and the scripts put them back a moment later, after
  // a layout in between: the compact bar faded in again and the selected block re-grew on every refresh.
  var OWN = ['is-on', 'is-selected', 'is-menu', 'is-wiggle', 'is-hit', 'is-dim', 'is-off', 'is-thin', 'is-bare', 'cz-flt-on', 'is-ringed', 'is-landing'];
  var MORPH = {
    morphStyle: 'innerHTML', ignoreActiveValue: true,
    callbacks: {
      beforeNodeMorphed: function (old, fresh) {
        if (old.nodeType !== 1 || fresh.nodeType !== 1 || !old.classList) return true;
        // F-141: the docked panel (day_dock.js) is left alone while it moves; a message being written in it, and what an editor opened in it (Add a step, the Set aside list), stay as they are
        if (old.id === 'cz-dock' && CZ.dockBusy && CZ.dockBusy()) return false;
        if (old.classList.contains('cz-pp-text') && old.value) return false;
        if (old.hasAttribute('data-live')) return false;      // F-143: the Family chats in the panel are kept up to date by their own script (thread.js), a refresh of the day leaves them be
        if (old.hasAttribute('data-keep-state')) ['hidden', 'aria-expanded'].forEach(function (a) { if (old.hasAttribute(a)) fresh.setAttribute(a, old.getAttribute(a)); else fresh.removeAttribute(a); });
        for (var i = 0; i < OWN.length; i++) if (old.classList.contains(OWN[i])) fresh.classList.add(OWN[i]);
        if (old.classList.contains('is-landing') && old.style.transformOrigin) fresh.style.transformOrigin = old.style.transformOrigin;      // F-171: a block landing (GA.motion.land squashes it about its corner) keeps that pivot when the server's style attribute is synced onto it mid-move: the scale would otherwise pivot about the centre and jump
        if (old.classList.contains('cz-fold')) ['inert', 'aria-hidden'].forEach(function (a) { if (old.hasAttribute(a)) fresh.setAttribute(a, old.getAttribute(a)); else fresh.removeAttribute(a); });
        return true;
      },
      beforeNodeRemoved: function (old) { return !(old.classList && (old.classList.contains('cz-menu') || old.classList.contains('cz-g-ghost'))); }      // (F-171: the ghost at a dropped block's old slot goes when the block has landed, not when the refresh comes in)
    }
  };
  function swap(html, dir, inPlace) {
    shown = html;
    if (inPlace && window.Idiomorph) Idiomorph.morph(stage, html, MORPH);
    else stage.innerHTML = html;
    var v = view();
    if (!v) return;
    if (v.dataset.title) document.title = 'GitAway · ' + v.dataset.title;
    if (dir && laptop()) dir = 'calm';
    if (dir && !(document.startViewTransition && !reduced.matches)) {
      v.classList.add('cz-in-' + dir);
      v.addEventListener('animationend', function () { v.classList.remove('cz-in-' + dir); }, { once: true });
    }
    settled();
    stage.dispatchEvent(new CustomEvent('cz:swap', { detail: { quiet: quietSwap, mode: curMode } }));      // the day grid (day_grid.js) starts its scroll and its focus here
    // F-171: focus last. Focusing right after the write made the browser lay the new level out (about 20 ms on a slow phone) before the hooks above read it, so the layout they need is done once, here, after them
    var focus = quietSwap ? null : v.querySelector('#cz-sheet-title') || v.querySelector('#cz-title');
    if (focus) { try { focus.focus({ preventScroll: true }); } catch (e) { focus.focus(); } }
  }
  // What every level needs once it is on the screen (and once at start): the modules' hooks (the filters), the dates centred, Ask on this day, the next levels fetched.
  function settled() {
    CZ.onSwap.forEach(function (fn) { fn(); });
    if (!quietSwap) centreDay();      // (a refresh in place keeps the dates where they were: no layout to read)
    askHere();
    prefetch();
    rememberToday();
  }

  // Name the element that zooms, run the swap inside a View Transition, and clear the name afterwards.
  // The thing named `key`: a sheet over a level (a booking's) wins over the line it was opened from, which stays on the page behind it (F-109: the line grows into the sheet, the sheet folds back into the line).
  // F-137: the screens zoom about the middle of the thing that was tapped (or that is being returned to), on the screen
  function origin(el) {
    var r = el && el.getBoundingClientRect(), h = window.innerHeight;
    root.style.setProperty('--cz-ox', r ? Math.round(r.left + r.width / 2) + 'px' : '50%');
    root.style.setProperty('--cz-oy', r ? Math.round(Math.max(0, Math.min(h, r.top + Math.min(r.height, h) / 2))) + 'px' : '30%');
  }
  var via = null;          // the link that started a zoom from the desktop week's columns (its row is the origin of the zoom)
  function boxed(n) { return n.getClientRects().length > 0; }      // F-145: the week draws a phone row and a desktop column with the same key, only one has a box
  function hero(key) {
    var all = stage.querySelectorAll('[data-zk="' + key + '"]'), pick = null;
    for (var i = 0; i < all.length; i++) if (boxed(all[i]) && !pick) pick = all[i];
    return stage.querySelector('.cz-sheet[data-zk="' + key + '"]') || pick || all[0] || null;
  }
  function run(html, dir, key, after) {
    var animate = !reduced.matches && typeof document.startViewTransition === 'function', soft = laptop();
    var from = animate && !soft && key && KEY.test(key) ? hero(key) : null;      // (the laptop names no hero: nothing grows out of what was clicked)
    if (!animate) { swap(html, reduced.matches ? '' : dir); if (after) after(); return Promise.resolve(); }
    root.dataset.czDir = soft ? 'calm' : dir;
    if (!soft) origin(via && via.isConnected ? via : from);      // F-145: the desktop week zooms about the row that was clicked, the column is what grows
    if (from) from.style.viewTransitionName = 'cz-hero';
    var t = document.startViewTransition(function () {
      if (from) from.style.viewTransitionName = '';
      swap(html, '');
      if (after) after();
      var to = !soft && key && KEY.test(key) ? hero(key) : null;
      if (to) to.style.viewTransitionName = 'cz-hero';
      if (!soft && !from && to && dir === 'out') origin(to);      // zooming out: about where this level sits in the one above
    });
    var clear = function () {
      delete root.dataset.czDir;
      stage.querySelectorAll('[data-zk]').forEach(function (n) { n.style.viewTransitionName = ''; });
      if (from) from.style.viewTransitionName = '';
    };
    t.finished.then(clear, clear);
    return t.finished.catch(function () {});
  }

  // F-116: the day or week on the screen is where the Today tab comes back to (pwa.js), for the rest of this visit.
  function rememberToday() {
    var u = here();
    if (!/^\/trip\/canvas(\?(day=\d+(&trip=[0-9a-f]+)?|trip=[0-9a-f]+))?$/.test(u)) return;
    try { sessionStorage.setItem('ga-today', u); } catch (e) { /* not stored */ }
  }
  // F-092: the centre Ask is the one way to change the plan, so it opens on the day being looked at (a day, a block or a step on it).
  function askHere() {
    var tab = document.getElementById('ph-tab-ask'), v = view();
    if (tab && v) tab.setAttribute('href', v.dataset.day ? '/trip/ask?day=' + v.dataset.day : '/trip/ask');     // the week: no day, Ask places it
  }
  // The open day sits in the middle of the day chips (they scroll sideways when the trip is longer than the row).
  function centreDay() {
    var bar = stage.querySelector('.cz-hchips'), open = bar && bar.querySelector('.is-open');
    if (open && bar.scrollWidth > bar.clientWidth) bar.scrollLeft += open.getBoundingClientRect().left - bar.getBoundingClientRect().left - (bar.clientWidth - open.offsetWidth) / 2;
  }

  // ---- bringing the screen up to date in place --------------------------------------------------------------------------------
  // Nothing is moving, held, open or being typed: only then may a fresh copy someone else made replace what is on the screen.
  function calm() {
    var a = document.activeElement, v = view();
    return !busy && !CZ.held && !(CZ.landing && CZ.landing()) && !(CZ.gesturing && CZ.gesturing()) && !!v && (v.dataset.level === 'week' || v.dataset.level === 'day') &&
      !stage.querySelector('.cz-sheet-wrap, .cz-lift, .cz-dragging') && !(a && stage.contains(a) && a.matches('input, textarea, select, [contenteditable]')) && !(CZ.editing && CZ.editing());
  }
  // The level as it is now, morphed onto the screen: the scroll kept, the focus put back (the day grid), each block sent from where it was to where it is (CZ.snap).
  function morphIn(html) {
    var y = window.scrollY, back = CZ.beforeQuiet ? CZ.beforeQuiet() : null, snap = CZ.snap ? CZ.snap() : null;
    quietSwap = true;
    try { swap(html, '', true); } finally { quietSwap = false; }
    if (back) back();
    window.scrollTo(0, y);
    if (snap) snap();
  }
  // F-170: the copy on the screen was shown from the cache: ask the server and, if it differs, morph the changes in. It waits for a calm moment (nothing held, open or typed in) both
  // before asking and before applying, and gives up only when the person has moved on, a write has run (its own refresh follows) or after about 10 seconds.
  function revalidate(u, old, tries) {
    tries = tries || 0;
    var again = function () { if (tries < 25) setTimeout(function () { revalidate(u, old, tries + 1); }, 400); };
    idle(function () {
      if (here() !== u || shown !== old) return;
      if (!calm()) { again(); return; }
      var e0 = epoch;
      fetchLevel(u, true).then(function (html) {
        (function apply(n) {
          if (e0 !== epoch || here() !== u || shown !== old || html === old || html === shown) return;
          if (calm()) morphIn(html);
          else if (n < 25) setTimeout(function () { apply(n + 1); }, 400);
        })(0);
      }).catch(function () {});
    });
  }
  // After a write (or coming back to the page): the level on the screen, brought up to date in place once any zoom is over. Resolves true when it was.
  function nextFrame(fn) {
    var ran = false, go = function () { if (!ran) { ran = true; fn(); } };
    requestAnimationFrame(function () { setTimeout(go, 0); });      // after the frame in hand is drawn (a write's reply can land inside a frame, as an animation ends)
    setTimeout(go, 100);          // (no frames come while the page is hidden)
  }
  function quiet() {
    return new Promise(function (done) {
      whenIdle(function () {
        var e0 = epoch, u = here();
        fetchLevel(u, true).then(function (html) {
          nextFrame(function () {          // F-131: its own frame, not the one the toast that came with the write is drawn in (two short frames, not one long one)
            if (e0 !== epoch) { whenIdle(function () { quiet().then(done); }); return; }       // a write ran meanwhile, so this copy is already old: ask again
            if (here() !== u) { done(false); return; }
            morphIn(html);
            done(true);
          });
        }).catch(function () { done(false); });
      });
    });
  }

  // ---- moving between levels --------------------------------------------------------------------------------------------------
  function directionTo(u) {
    var at = view() ? view().dataset.level : 'week';
    var a = RANK[at], b = RANK[levelOf(u)];
    return b > a ? 'in' : b < a ? 'out' : 'side';
  }
  // F-090: one day at a time. A day to the right slides in from the right.
  function dayOf(u) { var m = /[?&]day=(\d+)/.exec(u || ''); return m ? parseInt(m[1], 10) : null; }
  function sideways(u) {
    var v = view(), from = v && v.dataset.level === 'day' ? parseInt(v.dataset.day, 10) : null, to = dayOf(u);
    return from === null || to === null || from === to ? 'side' : to > from ? 'next' : 'prev';
  }

  // ---- F-135: a tap moves at once ----------------------------------------------------------------------------------------------
  // A level not yet in hand when the finger lifts is not waited for: the zoom starts with its outline (the heading the tapped element grows into, named as the link
  // named it, and soft placeholder rows), and the level fills in place when it comes. Week and sheets wait (the week is always fetched ahead; a sheet without its
  // words is no use).
  var SLOW = 70;          // ms: a level that answers sooner swaps whole, with no outline first
  function esc(t) { return String(t || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function outline(u, o, key) {
    var lvl = levelOf(u);
    if (lvl !== 'day' && lvl !== 'block') return null;
    var back = lvl === 'day' ? 'Trip' : '';
    var bars = '';
    for (var i = 0; i < 5; i++) bars += '<div class="cz-skel-row" style="--i:' + i + '"></div>';
    return '<section class="cz-view cz-level-' + lvl + ' cz-skel" data-level="' + lvl + '" data-title="' + esc(o.title) + '" tabindex="-1" aria-busy="true">' +
      '<header class="cz-head is-deep"' + (key && KEY.test(key) ? ' data-zk="' + key + '"' : '') + '><span class="cz-back' + (back ? ' has-text' : '') + '" aria-hidden="true">' +
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>' +
      (back ? '<span class="cz-back-t">' + back + '</span>' : '') + '</span><div class="cz-head-text"><span class="cz-head-k">&nbsp;</span><h1 id="cz-title" tabindex="-1">' + esc(o.title) + '</h1></div></header>' +
      '<div class="cz-skel-body">' + bars + '</div></section>';
  }
  function soon(p, ms) {
    return Promise.race([p, new Promise(function (r) { setTimeout(function () { r(null); }, ms); })]);
  }

  // F-156: the laptop moves nothing while a level is on its way, so a slow one must not look dead: after --motion-quick with nothing back, the view says it is busy (aria-busy), the pointer shows
  // progress and the clicked row dims (opacity only). All of it goes the moment the level arrives or fails.
  function pending(level, el) {
    if (!laptop()) return;
    var wait = window.GA && GA.motion ? GA.motion.t('quick') : 160, mark = null;
    var timer = setTimeout(function () {
      var cv = view();
      if (cv) cv.setAttribute('aria-busy', 'true');
      root.classList.add('cz-pending');
      if (el && el.isConnected) { mark = el.closest('.cz-wi, .cz-wcol, .cz-hchip') || el; mark.classList.add('is-pending'); }
    }, wait);
    function clear() {
      clearTimeout(timer);
      root.classList.remove('cz-pending');
      if (mark) mark.classList.remove('is-pending');
      var cv = view();
      if (cv) cv.removeAttribute('aria-busy');
    }
    level.then(clear, clear);
  }

  function goto(u, o) {
    o = o || {};
    if (busy) { via = null; if (o.mode === 'pop') waiting = u; return Promise.resolve(); }
    busy = true;
    var dir = o.dir || directionTo(u);
    curMode = o.mode || '';
    var v = view(), y0 = window.scrollY;
    var key = o.key !== undefined ? o.key : (dir === 'out' && v ? v.dataset.zout : null);
    var sheet = levelOf(u) === 'step' || levelOf(u) === 'block', aged = !sheet && old(u), copy = null;      // F-170: a copy we have is shown at once; if it may differ from the server's, it is checked behind the zoom (revalidate)
    var e0 = epoch, level = fetchLevel(u, sheetStale(u));
    pending(level, o.el);
    var sketch = dir === 'in' && !reduced.matches && !laptop() ? outline(u, o, key) : null;      // (the laptop keeps the old level until the new one is in hand: never an outline first)
    return (sketch ? soon(level, SLOW) : level).then(function (got) {
      if (got !== null) return got;
      // nothing yet: the zoom runs now into the outline, and the level fills it when it comes
      return run(sketch, dir, key, remember).then(function () { return level; }).then(function (html) {
        if (here() !== u) return null;      // gone elsewhere meanwhile
        swap(html, '', true);
        var nv = view();
        if (nv) nv.classList.add('cz-filled');
        if (CZ.afterScroll && (o.mode === 'push' || o.mode === 'replace')) CZ.afterScroll();
        if (!sheet && (aged || e0 !== epoch)) copy = html;      // F-170: a copy fetched before a write (or kept a while) fills the outline all the same: it is checked behind the zoom like any other
        if (e0 !== epoch) quiet();          // a write landed meanwhile: this copy may be older than it
        return null;
      });
    }).then(function (html) {
      if (html === null) return;
      if (!sheet && (aged || e0 !== epoch)) copy = html;
      return run(html, dir, key, remember);
    }).catch(function () { location.href = u; }).then(function () {
      busy = false;
      via = null;      // the tapped link belongs to this zoom only, animated or not
      rememberToday();
      if (copy !== null) revalidate(u, copy);
      if (waiting) { waiting = null; goto(here(), { mode: 'pop' }); }     // the address bar is the truth: show what it says
      drain();
    });
    function remember() {
        if (o.mode === 'push') {
          history.replaceState(Object.assign({}, history.state, { y: window.scrollY }), '');
          history.pushState({ cz: 1, from: here() }, '', u);
          window.scrollTo(0, 0);
          if (CZ.afterScroll) CZ.afterScroll();       // the day grid scrolls to the day's first plan, inside the swap so the transition carries it
        } else if (o.mode === 'replace') {
          history.replaceState(Object.assign({}, history.state, { cz: 1 }), '', u);
          window.scrollTo(0, 0);
          if (CZ.afterScroll) CZ.afterScroll();
        } else if (o.mode === 'stay') {
          window.scrollTo(0, y0);
        } else if (o.mode === 'pop') {
          window.scrollTo(0, (history.state && history.state.y) || 0);
        }
    }
  }
  function zoomOutTo(u) {
    // Zooming out to where we came from is the browser's Back, so the history stays tidy; the popstate handler does the swap.
    if (history.state && history.state.from === path(u)) history.back();
    else goto(u, { dir: 'out', mode: 'replace' });
  }

  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest ? e.target.closest('a[data-zoom]') : null;
    if (!a || !stage.contains(a)) return;
    e.preventDefault();
    var dir = a.dataset.zoom, u = path(a.href);
    if (dir === 'out') { zoomOutTo(u); return; }
    if (dir === 'side') dir = sideways(u);
    var from = a.closest('[data-zk]');
    via = a.closest('.cz-wcol') ? a : null;
    goto(u, { dir: dir, key: dir === 'in' && from ? from.dataset.zk : null, mode: 'push', title: a.dataset.title || '', el: a });
  });
  // The way up: the sheet's close button when a sheet is open, else the heading's back button.
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || e.defaultPrevented) return;
    var u = stage.querySelector('.cz-close') || stage.querySelector('.cz-back');
    if (u) { e.preventDefault(); u.click(); }
  });
  window.addEventListener('popstate', function () {
    var u = here();
    if (!/^\/trip\/canvas/.test(u)) return;
    goto(u, { mode: 'pop' });
  });
  history.replaceState(Object.assign({ cz: 1 }, history.state), '');
  // Back or forward from the bfcache (after adding a plan in Ask, say): the page comes back as it was left, so fetch it again.
  window.addEventListener('pageshow', function (e) { if (e.persisted) { cache = {}; quiet(); } });

  // ---- the one write transport ------------------------------------------------------------------------------------------------
  // Every write posts with X-Canvas (and X-Canvas-Level: the reply carries the level after it). Replies: JSON {url, toast, undo, level}, 204 + X-Canvas-Url, or 422 {error}.
  function post(url, body) {
    epoch++; gen++;
    return send(url, body).then(function (r) {
      epoch++; gen++;
      handed = r && typeof r.level === 'string' && r.url ? { u: path(r.url), html: r.level, e: epoch } : null;
      if (handed) cache[handed.u] = { at: Date.now(), g: gen, promise: Promise.resolve(handed.html) };      // F-170: the level the write drew is the newest copy there is
      return r;
    }, function (e) { epoch++; gen++; handed = null; throw e; });
  }
  function send(url, body) {
    var ctl = typeof AbortController === 'function' ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, 12000) : 0;      // a write that never answers must not leave the day waiting for ever
    return fetch(url, { method: 'POST', body: body, credentials: 'same-origin', headers: { 'X-Canvas': '1', 'X-Canvas-Level': '1' }, signal: ctl ? ctl.signal : undefined }).then(function (r) {
      clearTimeout(timer);
      if (r.status === 422) return r.json().then(function (j) { var e = new Error('refused'); e.soft = j.error || 'That did not work.'; throw e; });
      if (r.status === 204) { var next = r.headers.get('X-Canvas-Url'); if (!next) throw new Error('write'); return { url: next }; }
      if (!r.ok) throw new Error('write ' + r.status);
      return r.json();
    });
  }
  function tripBody(fields) {
    var body = new URLSearchParams();
    Object.keys(fields).forEach(function (k) { if (fields[k] !== undefined && fields[k] !== null) body.append(k, fields[k]); });
    if (stage.dataset.trip) body.append('trip', stage.dataset.trip);
    return body;
  }

  // ---- what the other modules (and day_*.js) use ------------------------------------------------------------------------------
  CZ.view = view; CZ.path = path; CZ.here = here; CZ.reduced = reduced; CZ.levelOf = levelOf;
  CZ.goto = goto; CZ.zoomOutTo = zoomOutTo; CZ.sideways = sideways;
  CZ.post = post; CZ.tripBody = tripBody;
  CZ.quiet = quiet;                                                     // after a write: the level brought up to date in place
  CZ.refresh = quiet;                                                   // (a drop, an add, an Undo: the same, F-128; it used to fade the whole level in again)
  CZ.busy = function () { return busy; };
  // F-170: something changed that no write of ours drew: every copy fetched so far is checked when it is next shown. CZ.forget(true) throws them away (the Ask sheet changed the plan: a day it
  // opens must not flash its old self first).
  CZ.forget = function (hard) { gen++; if (hard) cache = {}; };
  window.CZ = CZ;

  // The level the page opened with. (Each module applies its own part of it when it loads, right after this one: the filters, say.)
  centreDay();
  askHere();
  prefetch();
  rememberToday();
  if (root.hasAttribute('data-ga-stale')) revalidate(here(), '');      // F-116: opened at once from the saved copy (sw.js): bring it up to date quietly
})();
