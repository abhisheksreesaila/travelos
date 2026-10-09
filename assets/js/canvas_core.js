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
  var RANK = { week: 0, day: 1, block: 2, step: 3 };
  var KEY = /^[a-z]{3}-[A-Za-z0-9-]+$/;
  var CZ = { stage: stage, held: false, onSwap: [] };      // `held` is true while the day grid (day_grid.js) holds a block
  var STALE = 5000;        // a level shown from a copy older than this is fetched again in idle time and quietly updated if it changed (someone else may have edited)
  var FRESH = 60000;       // how long a fetched level may be shown without asking again (F-099); every write empties the cache
  var cache = {};          // url -> { at, promise }: a level fetched ahead of time (idle, or as the finger went down), used by the tap that follows
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
  function fetchLevel(u) {
    if (handed && handed.u === u && handed.e === epoch) return Promise.resolve(handed.html);
    var now = Date.now(), hit = cache[u];
    if (hit && now - hit.at < FRESH) return hit.promise;
    var p = fetch(fragUrl(u), { credentials: 'same-origin', headers: { 'X-Canvas': '1' } }).then(function (r) {
      if (!r.ok) throw new Error('level ' + r.status);
      return r.text();
    });
    cache[u] = { at: now, promise: p };
    p.catch(function () { delete cache[u]; });
    return p;
  }

  // F-099: while the canvas sits idle the next levels are fetched, so Day | Week, a date, a flick and Back swap with nothing to wait for. The week fetches every day;
  // a day fetches its neighbours, the week and the other dates. Fragments only, two at a time, in idle time, never on Data Saver or a slow link.
  var pq = [], pActive = 0, pPlanned = 0;
  var idle = window.requestIdleCallback ? function (fn) { window.requestIdleCallback(fn, { timeout: 1500 }); } : function (fn) { setTimeout(fn, 200); };
  function frugal() {
    var c = navigator.connection;
    return !!(c && (c.saveData || /(^|-)2g$/.test(c.effectiveType || '')));
  }
  function fresh(u) { var h = cache[u]; return !!h && Date.now() - h.at < FRESH; }
  function nextLevels() {
    var v = view(), out = [];
    if (!v) return out;
    var add = function (u) { if (u && out.indexOf(u) < 0) out.push(u); };
    if (v.dataset.level === 'week') {
      v.querySelectorAll('a.cz-row-link[data-zoom="in"]').forEach(function (a) { add(path(a.href)); });
    } else if (v.dataset.level === 'day') {
      add(v.dataset.next && path(v.dataset.next));
      add(v.dataset.prev && path(v.dataset.prev));
      var wk = v.querySelector('#cz-z-week');
      if (wk) add(path(wk.href));
      v.querySelectorAll('.cz-dpills a[href]').forEach(function (a) { add(path(a.href)); });
    } else if (v.dataset.level === 'block') {      // F-132: the sheets of the steps on the screen (about 4 KB each on the wire), so a tap on one opens it with nothing to wait for
      var h = window.innerHeight;
      Array.prototype.slice.call(v.querySelectorAll('a.cz-step[data-zoom="in"]')).filter(function (a) {
        var r = a.getBoundingClientRect();
        return r.bottom > 0 && r.top < h;
      }).slice(0, 8).forEach(function (a) { add(path(a.href)); });
    }
    var now = here();
    return out.filter(function (u) { return u !== now; });
  }
  function pump() {
    while (pActive < 2 && pq.length) {
      var u = pq.shift();
      if (fresh(u)) continue;
      pActive++;
      fetchLevel(u).catch(function () {}).then(function () { pActive--; if (pq.length) idle(pump); });
    }
  }
  function prefetch() {
    if (frugal() || document.hidden) return;
    var mine = ++pPlanned;
    idle(function () {
      if (mine !== pPlanned) return;      // a newer level was shown meanwhile
      pq = nextLevels().filter(function (u) { return !fresh(u); });
      pump();
    });
  }
  document.addEventListener('visibilitychange', function () { if (!document.hidden) prefetch(); });
  var scrolled = 0;      // a block's steps that come into view are fetched too
  window.addEventListener('scroll', function () { clearTimeout(scrolled); scrolled = setTimeout(function () { var v = view(); if (v && v.dataset.level === 'block') prefetch(); }, 300); }, { passive: true });
  // A level is fetched as soon as a finger goes down on a link to it, so the tap that follows has nothing to wait for.
  document.addEventListener('pointerdown', function (e) {
    var a = e.target.closest ? e.target.closest('a[data-zoom]') : null;
    if (a && stage.contains(a) && a.dataset.zoom !== 'out') fetchLevel(path(a.href)).catch(function () {});
  }, { passive: true });

  // ---- swapping ---------------------------------------------------------------------------------------------------------------
  var curMode = '';        // how the level being shown was reached (push, replace, stay, pop), for the day grid's scroll
  var quietSwap = false;   // a swap that only brings the level up to date: nothing moves, and focus stays where it was
  var shown = '';          // the fragment on the stage, to see whether a fresh copy differs
  // F-122: `inPlace` updates what is already on the screen to the fresh copy, changing only what differs (vendor/idiomorph.js): nothing is rebuilt, so nothing flashes.
  // F-131: what the scripts own rides through it: their classes on an element the server also draws (the compact bar shown, a block selected, a filter's highlight), the
  // compact bar's inert state, and the hold menu (a node the server never draws). Without that the morph took them off and the scripts put them back a moment later, after
  // a layout in between: the compact bar faded in again and the selected block re-grew on every refresh.
  var OWN = ['is-on', 'is-selected', 'is-menu', 'is-wiggle', 'is-hit', 'is-dim', 'is-off', 'is-thin', 'is-bare', 'cz-flt-on'];
  var MORPH = {
    morphStyle: 'innerHTML', ignoreActiveValue: true,
    callbacks: {
      beforeNodeMorphed: function (old, fresh) {
        if (old.nodeType !== 1 || fresh.nodeType !== 1 || !old.classList) return true;
        for (var i = 0; i < OWN.length; i++) if (old.classList.contains(OWN[i])) fresh.classList.add(OWN[i]);
        if (old.classList.contains('cz-fold')) ['inert', 'aria-hidden'].forEach(function (a) { if (old.hasAttribute(a)) fresh.setAttribute(a, old.getAttribute(a)); else fresh.removeAttribute(a); });
        return true;
      },
      beforeNodeRemoved: function (old) { return !(old.classList && old.classList.contains('cz-menu')); }
    }
  };
  function swap(html, dir, inPlace) {
    shown = html;
    if (inPlace && window.Idiomorph) Idiomorph.morph(stage, html, MORPH);
    else stage.innerHTML = html;
    var v = view();
    if (!v) return;
    if (v.dataset.title) document.title = 'GitAway · ' + v.dataset.title;
    var focus = quietSwap ? null : v.querySelector('#cz-sheet-title') || v.querySelector('#cz-title');
    if (focus) { try { focus.focus({ preventScroll: true }); } catch (e) { focus.focus(); } }
    if (dir && !(document.startViewTransition && !reduced.matches)) {
      v.classList.add('cz-in-' + dir);
      v.addEventListener('animationend', function () { v.classList.remove('cz-in-' + dir); }, { once: true });
    }
    settled();
    stage.dispatchEvent(new CustomEvent('cz:swap', { detail: { quiet: quietSwap, mode: curMode } }));      // the day grid (day_grid.js) starts its scroll and its focus here
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
  function hero(key) { return stage.querySelector('.cz-sheet[data-zk="' + key + '"]') || stage.querySelector('[data-zk="' + key + '"]'); }
  function run(html, dir, key, after) {
    var animate = !reduced.matches && typeof document.startViewTransition === 'function';
    var from = animate && key && KEY.test(key) ? hero(key) : null;
    if (!animate) { swap(html, reduced.matches ? '' : dir); if (after) after(); return Promise.resolve(); }
    root.dataset.czDir = dir;
    if (from) from.style.viewTransitionName = 'cz-hero';
    var t = document.startViewTransition(function () {
      if (from) from.style.viewTransitionName = '';
      swap(html, '');
      if (after) after();
      var to = key && KEY.test(key) ? hero(key) : null;
      if (to) to.style.viewTransitionName = 'cz-hero';
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
  // The open day sits in the middle of the dates across the top (they scroll sideways on a phone).
  function centreDay() {
    var bar = stage.querySelector('.cz-dpills'), open = bar && bar.querySelector('.is-open');
    if (open && bar.scrollWidth > bar.clientWidth) bar.scrollLeft = open.offsetLeft - (bar.clientWidth - open.offsetWidth) / 2;
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
  function revalidate(u, old) {
    idle(function () {
      if (here() !== u || !calm()) return;
      delete cache[u];
      var e0 = epoch;
      fetchLevel(u).then(function (html) {
        if (e0 === epoch && html !== old && html !== shown && here() === u && shown === old && calm()) morphIn(html);
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
        cache = {};
        var e0 = epoch, u = here();
        fetchLevel(u).then(function (html) {
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

  function goto(u, o) {
    o = o || {};
    if (busy) { if (o.mode === 'pop') waiting = u; return Promise.resolve(); }
    busy = true;
    var dir = o.dir || directionTo(u);
    curMode = o.mode || '';
    var v = view(), y0 = window.scrollY;
    var key = o.key !== undefined ? o.key : (dir === 'out' && v ? v.dataset.zout : null);
    var age = cache[u] ? Date.now() - cache[u].at : 0, copy = null;
    return fetchLevel(u).then(function (html) {
      if (age > STALE) copy = html;
      var remember = function () {
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
      };
      return run(html, dir, key, remember);
    }).catch(function () { location.href = u; }).then(function () {
      busy = false;
      rememberToday();
      if (copy !== null && levelOf(u) !== 'step' && levelOf(u) !== 'block') revalidate(u, copy);
      if (waiting) { waiting = null; goto(here(), { mode: 'pop' }); }     // the address bar is the truth: show what it says
      drain();
    });
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
    goto(u, { dir: dir, key: dir === 'in' && from ? from.dataset.zk : null, mode: 'push' });
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
    epoch++;
    return send(url, body).then(function (r) {
      epoch++;
      handed = r && typeof r.level === 'string' && r.url ? { u: path(r.url), html: r.level, e: epoch } : null;
      return r;
    }, function (e) { epoch++; handed = null; throw e; });
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
  CZ.forget = function () { cache = {}; };      // the Ask sheet (ask_sheet.js) changed the plan: no level fetched before may be shown
  window.CZ = CZ;

  // The level the page opened with. (Each module applies its own part of it when it loads, right after this one: the filters, say.)
  centreDay();
  askHere();
  prefetch();
  rememberToday();
  if (root.hasAttribute('data-ga-stale')) revalidate(here(), '');      // F-116: opened at once from the saved copy (sw.js): bring it up to date quietly
})();
