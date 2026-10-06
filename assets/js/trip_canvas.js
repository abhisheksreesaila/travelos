// The trip canvas (F-081): week > day > block > step as one surface that zooms.
//
// Every level is a page of its own (gitaway/pages/tripcanvas.py), so with no script it is plain links and forms. With script, a tap on a link marked data-zoom
// ("in", "out" or "side"), the Day | Week toggle, or the browser's Back fetches that level as a fragment (?frag=1) and swaps it inside a View Transition (pinch is gone, F-092). The element
// that was tapped (data-zk="day-2" | "blk-a3" | "stp-<id>") is named `cz-hero` before and after the swap, so it grows into the next level's heading or sheet and
// shrinks back on zoom out. No View Transitions: the new level scales and fades in (CSS .cz-in-*). Reduced motion: an instant swap.
// A write from the sheet (Mark done, Set aside, Put back, Not done) posts with X-Canvas and the server answers 204 + X-Canvas-Url; we then zoom out to that level.
//
// F-082, touch: hold a step (about 350 ms) to lift it; a chip follows the finger, and the parts, the days across the top and the Set aside tray light up as drop
// targets; letting go posts a move and swaps the level in place, with a toast that has Undo. Swipe a step left for Done and Set aside; swipe right (or tap elsewhere) to
// put them away. Filter chips highlight the steps that match and dim the rest, remembered per person in localStorage. The Move menu on the step sheet does everything
// dragging does with buttons.
//
// F-093: a booking's sheet and the SOS sheet are levels like the step sheet (?booked=, ?sos=1; the page behind stays); the All | Plans | Hotels | Flights | Car | Chats row
// (applyKinds) shows only what matches on the week and the day, one choice, remembered per person and trip.
(function () {
  var stage = document.getElementById('cz');
  if (!stage) return;
  var root = document.documentElement;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var RANK = { week: 0, day: 1, block: 2, step: 3 };
  var KEY = /^[a-z]{3}-[A-Za-z0-9-]+$/;
  var CZ = { stage: stage, held: false };      // what the day grid's script (day_grid.js) uses; `held` is true while it holds a block
  var STALE = 5000;        // a level shown from a copy older than this is fetched again in idle time and quietly updated if it changed (someone else may have edited)
  var FRESH = 60000;       // how long a fetched level may be shown without asking again (F-099); every write empties the cache
  var cache = {};          // url -> { at, promise }: a level fetched ahead of time (idle, or as the finger went down), used by the tap that follows
  var busy = false;
  var waiting = null;      // the browser's Back or Forward pressed while a zoom was running: run it when that zoom is done
  var idleQ = [];          // work that needs the zoom to be finished (a refresh after a drop)
  function whenIdle(fn) { if (busy) idleQ.push(fn); else fn(); }

  function path(u) { var a = document.createElement('a'); a.href = u; return a.pathname + a.search; }
  function fragUrl(u) { return u + (u.indexOf('?') < 0 ? '?' : '&') + 'frag=1'; }
  function view() { return stage.querySelector('.cz-view'); }
  function levelOf(u) {
    var q = path(u).split('?')[1] || '';
    return /(^|&)step=/.test(q) || /(^|&)add=1/.test(q) || /(^|&)booked=/.test(q) || /(^|&)sos=1/.test(q) ? 'step' : /(^|&)block=/.test(q) ? 'block' : /(^|&)day=/.test(q) ? 'day' : 'week';
  }

  function fetchLevel(u) {
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
  // a day fetches its neighbours, the week and the other dates. Fragments only, two at a time, in idle time, never on Data Saver or a slow link. Every write empties `cache`.
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
    }
    var here = path(location.href);
    return out.filter(function (u) { return u !== here; });
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

  var curMode = '';        // how the level being shown was reached (push, replace, stay, pop), for the day grid's scroll
  var quietSwap = false;   // a swap that only brings the level up to date after a write: nothing moves, and focus stays where it was
  var shown = '';          // the fragment on the stage, to see whether a fresh copy differs
  function swap(html, dir) {
    shown = html;
    stage.innerHTML = html;
    var v = view();
    if (!v) return;
    if (v.dataset.title) document.title = 'GitAway · ' + v.dataset.title;
    var focus = quietSwap ? null : v.querySelector('#cz-sheet-title') || v.querySelector('#cz-title');
    if (focus) { try { focus.focus({ preventScroll: true }); } catch (e) { focus.focus(); } }
    if (dir && !(document.startViewTransition && !reduced.matches)) {
      v.classList.add('cz-in-' + dir);
      v.addEventListener('animationend', function () { v.classList.remove('cz-in-' + dir); }, { once: true });
    }
    applyFilter();
    applyKinds();
    centreDay();
    askHere();
    prefetch();
    stage.dispatchEvent(new CustomEvent('cz:swap', { detail: { quiet: quietSwap, mode: curMode } }));      // the day grid (day_grid.js) starts its scroll and its focus here
  }

  // Name the element that zooms, run the swap inside a View Transition, and clear the name afterwards.
  function run(html, dir, key, after) {
    var animate = !reduced.matches && typeof document.startViewTransition === 'function';
    var from = animate && key && KEY.test(key) ? stage.querySelector('[data-zk="' + key + '"]') : null;
    if (!animate) { swap(html, reduced.matches ? '' : dir); if (after) after(); return Promise.resolve(); }
    root.dataset.czDir = dir;
    if (from) from.style.viewTransitionName = 'cz-hero';
    var t = document.startViewTransition(function () {
      if (from) from.style.viewTransitionName = '';
      swap(html, '');
      if (after) after();
      var to = key && KEY.test(key) ? stage.querySelector('[data-zk="' + key + '"]') : null;
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

  // Nothing is moving, held, open or being typed: only then may a fresh copy replace what is on the screen.
  function calm() {
    var a = document.activeElement, v = view();
    return !busy && !CZ.held && !g && !flick && count() === 0 && !!v && (v.dataset.level === 'week' || v.dataset.level === 'day') &&
      !stage.querySelector('.cz-sheet-wrap, .cz-lift, .cz-dragging') && !(a && stage.contains(a) && a.matches('input, textarea, select, [contenteditable]')) && !(CZ.editing && CZ.editing());
  }
  function quietShow(html) {
    var y = window.scrollY, back = CZ.beforeQuiet ? CZ.beforeQuiet() : null;
    quietSwap = true;
    try { swap(html, ''); } finally { quietSwap = false; }
    if (back) back();
    window.scrollTo(0, y);
  }
  function revalidate(u, old) {
    idle(function () {
      if (path(location.href) !== u || !calm()) return;
      delete cache[u];
      fetchLevel(u).then(function (html) {
        if (html !== old && html !== shown && path(location.href) === u && shown === old && calm()) quietShow(html);
      }).catch(function () {});
    });
  }

  function directionTo(u) {
    var here = view() ? view().dataset.level : 'week';
    var a = RANK[here], b = RANK[levelOf(u)];
    return b > a ? 'in' : b < a ? 'out' : 'side';
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
          history.pushState({ cz: 1, from: path(location.href) }, '', u);
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
      if (copy !== null && levelOf(u) !== 'step' && levelOf(u) !== 'block') revalidate(u, copy);
      if (waiting) { waiting = null; goto(path(location.href), { mode: 'pop' }); }     // the address bar is the truth: show what it says
      while (idleQ.length && !busy) idleQ.shift()();
    });
  }

  // ---- taps and keys ----------------------------------------------------------------------------------------------------
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
    var hero = a.closest('[data-zk]');
    goto(u, { dir: dir, key: dir === 'in' && hero ? hero.dataset.zk : null, mode: 'push' });
  });

  // F-093: SOS opens from the page itself, with no network: the emergency sheet sits inert in a <template> in every week and day page. It adds no history entry; close,
  // the scrim and Escape take it away again. (With no template, the sheet is already the level and the link is a plain zoom.)
  document.addEventListener('click', function (e) {
    if (e.button || !e.target.closest || !stage.contains(e.target)) return;
    var open = e.target.closest('a.cz-sos');
    if (open) {
      var v = view(), tpl = v && v.querySelector('#cz-sos-tpl');
      if (!tpl) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      if (v.querySelector('.cz-sheet-wrap[data-local]')) return;
      var frag = tpl.content.cloneNode(true);
      frag.querySelector('.cz-sheet-wrap').setAttribute('data-local', '1');
      v.appendChild(frag);
      var h = v.querySelector('.cz-sheet-wrap[data-local] #cz-sheet-title');
      if (h) { try { h.focus({ preventScroll: true }); } catch (err) { h.focus(); } }
      return;
    }
    if (e.target.closest('.cz-sheet-wrap[data-local] .cz-close, .cz-sheet-wrap[data-local] .cz-scrim')) {
      e.preventDefault();
      e.stopImmediatePropagation();
      var w = stage.querySelector('.cz-sheet-wrap[data-local]');
      if (w) w.remove();
      var b = stage.querySelector('#cz-sos');
      if (b) b.focus();
    }
  }, true);

  // The way up: the sheet's close button when a sheet is open, else the heading's back button.
  function up() { return stage.querySelector('.cz-close') || stage.querySelector('.cz-back'); }

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || e.defaultPrevented) return;
    var u = up();
    if (u) { e.preventDefault(); u.click(); }
  });

  window.addEventListener('popstate', function () {
    var u = path(location.href);
    if (!/^\/trip\/canvas/.test(u)) return;
    goto(u, { mode: 'pop' });
  });
  history.replaceState(Object.assign({ cz: 1 }, history.state), '');
  // Back or forward from the bfcache (after adding a plan in Ask, say): the page comes back as it was left, so fetch it again.
  window.addEventListener('pageshow', function (e) { if (e.persisted) { cache = {}; CZ.quiet(); } });

  // A level is fetched as soon as a finger goes down on a link to it, so the tap that follows has nothing to wait for.
  document.addEventListener('pointerdown', function (e) {
    var a = e.target.closest ? e.target.closest('a[data-zoom]') : null;
    if (a && stage.contains(a) && a.dataset.zoom !== 'out') fetchLevel(path(a.href)).catch(function () {});
  }, { passive: true });

  // ---- writes ------------------------------------------------------------------------------------------------------------
  // Every write posts with X-Canvas. The server answers 204 + X-Canvas-Url (a tick, a note), or JSON {url, toast, undo} (a move, an add, an undo), or 422 {error}.
  function post(url, body) {
    var ctl = typeof AbortController === 'function' ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, 12000) : 0;      // a write that never answers must not leave the day waiting for ever
    return fetch(url, { method: 'POST', body: body, credentials: 'same-origin', headers: { 'X-Canvas': '1' }, signal: ctl ? ctl.signal : undefined }).then(function (r) {
      clearTimeout(timer);
      if (r.status === 422) return r.json().then(function (j) { var e = new Error('refused'); e.soft = j.error || 'That did not work.'; throw e; });
      if (r.status === 204) { var next = r.headers.get('X-Canvas-Url'); if (!next) throw new Error('write'); return { url: next }; }
      if (!r.ok) throw new Error('write ' + r.status);
      return r.json();
    });
  }
  function here() { return path(location.href); }
  function refresh() {      // a drop or an Undo that lands during a zoom waits for it, then shows the level as it is now
    return new Promise(function (done) { whenIdle(function () { cache = {}; goto(here(), { dir: "side", mode: "stay", key: null }).then(done, done); }); });
  }

  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f.matches || !f.matches('form[data-cz-form]') || e.defaultPrevented) return;
    e.preventDefault();
    if (f.dataset.sent) return;
    f.dataset.sent = '1';
    var body = new URLSearchParams(new FormData(f));
    var buttons = f.querySelectorAll('button');
    buttons.forEach(function (b) { b.disabled = true; });
    post(f.action, body).then(function (res) {
      cache = {};
      if (res.toast) showToast(res.toast, res.undo);
      if (f.hasAttribute('data-cz-stay')) goto(res.url, { dir: 'side', mode: 'stay', key: null });
      else zoomOutTo(res.url);
    }).catch(function (err) {
      if (err && err.soft) {            // refused with a reason: say it where the person is looking, and let them try again
        var box = f.querySelector('.cz-error');
        if (box) box.textContent = err.soft; else showToast(err.soft);
        buttons.forEach(function (b) { b.disabled = false; });
        delete f.dataset.sent;
        return;
      }
      f.submit();     // the plain form post does the same write and redirects to the level
    });
  });

  // ---- the toast, and Undo ----------------------------------------------------------------------------------------------
  var toast = null, toastTimer = 0;
  function hideToast() {
    clearTimeout(toastTimer);
    if (toast && toast.parentNode) toast.parentNode.removeChild(toast);
    toast = null;
  }
  function showToast(text, undo) {
    hideToast();
    toast = document.createElement('div');
    toast.className = 'cz-toast';
    toast.id = 'cz-toast';
    toast.setAttribute('role', 'status');
    var t = document.createElement('span');
    t.className = 'cz-toast-t';
    t.textContent = text;
    toast.appendChild(t);
    if (undo) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'cz-toast-undo';
      b.textContent = 'Undo';
      b.addEventListener('click', function () { if (typeof undo === 'function') { hideToast(); undo(); } else doUndo(undo); });      // a function is the day grid's own Undo
      toast.appendChild(b);
    }
    (document.getElementById('main') || document.body).appendChild(toast);
    toastTimer = setTimeout(hideToast, undo ? 9000 : 4500);
  }
  function tripBody(fields) {
    var body = new URLSearchParams();
    Object.keys(fields).forEach(function (k) { if (fields[k] !== undefined && fields[k] !== null) body.append(k, fields[k]); });
    if (stage.dataset.trip) body.append('trip', stage.dataset.trip);
    return body;
  }
  function doUndo(undo) {
    hideToast();
    post('/trip/canvas/undo', tripBody({ undo: JSON.stringify(undo), next: here() })).then(function (res) {
      return refresh().then(function () { showToast(res.toast || 'Moved back'); });
    }).catch(function (err) { showToast(err && err.soft ? err.soft : 'Could not undo that.'); });
  }

  // ---- filters: highlight what matches, dim the rest, remember the choice for this person ------------------------------------
  function filterKey() { return 'cz-filter:' + (stage.dataset.trip || '') + ':' + (stage.dataset.me || ''); }
  var chosen = null;      // the choice made on this page; storage may be missing (a private window), and then the filter still lasts until the page is left
  function getFilter() {
    if (chosen !== null) return chosen;
    try { return localStorage.getItem(filterKey()) || 'all'; } catch (e) { return 'all'; }
  }
  function setFilter(v) {
    chosen = v;
    try { if (v === 'all') localStorage.removeItem(filterKey()); else localStorage.setItem(filterKey(), v); } catch (e) { /* not stored */ }
  }
  function matches(n, f) {
    if (f.indexOf('list:') === 0) return (n.dataset.lists || '').split(' ').indexOf(f.slice(5)) >= 0;
    var who = [];
    try { who = JSON.parse(n.dataset.who || '[]'); } catch (e) { who = []; }
    return who.length === 0 || who.indexOf(f.slice(4)) >= 0;      // a step for everyone is for each person
  }
  function applyFilter() {
    var v = view();
    var bar = v && v.querySelector('.cz-filters');
    if (!bar) return;
    var chips = Array.prototype.slice.call(bar.querySelectorAll('[data-f]'));
    var f = getFilter();
    if (!chips.some(function (c) { return c.dataset.f === f; })) f = 'all';
    chips.forEach(function (c) { c.setAttribute('aria-pressed', c.dataset.f === f ? 'true' : 'false'); });
    var on = f !== 'all';
    v.classList.toggle('cz-flt-on', on);
    v.querySelectorAll('[data-who][data-lists]').forEach(function (n) {
      var hit = on && matches(n, f);
      n.classList.toggle('is-hit', hit);
      n.classList.toggle('is-dim', on && !hit);
    });
    v.querySelectorAll('.cz-listmore').forEach(function (n) { n.hidden = f !== 'list:' + n.dataset.list; });
  }
  document.addEventListener('click', function (e) {
    var chip = e.target.closest ? e.target.closest('.cz-fchip') : null;
    if (!chip || !stage.contains(chip)) return;
    setFilter(chip.getAttribute('aria-pressed') === 'true' ? 'all' : chip.dataset.f);
    applyFilter();
  });

  // ---- F-093: All | Plans | Hotels | Flights | Car | Chats on the week and the day. One choice, remembered per person and trip; the week and the day show only what matches ----
  var KIND_WORD = { plan: 'plans', hotel: 'hotels', flight: 'flights', car: 'the car', chat: 'chats' };
  var CAP = 3;            // with no filter a week row shows its first three entries and "and N more"
  function kindKey() { return 'cz-kind:' + (stage.dataset.trip || '') + ':' + (stage.dataset.me || ''); }
  var kindChosen = null;
  function getKind() {
    if (kindChosen !== null) return kindChosen;
    try { return localStorage.getItem(kindKey()) || 'all'; } catch (e) { return 'all'; }
  }
  function setKind(v) {
    kindChosen = v;
    try { if (v === 'all') localStorage.removeItem(kindKey()); else localStorage.setItem(kindKey(), v); } catch (e) { /* not stored */ }
  }
  function applyKinds() {
    var v = view();
    var bar = v && v.querySelector('.cz-kinds');
    if (!bar) return;
    bar.hidden = false;                   // drawn hidden: without script the buttons would do nothing
    var k = getKind();
    if (!bar.querySelector('[data-k="' + k + '"]')) k = 'all';
    bar.querySelectorAll('[data-k]').forEach(function (c) { c.setAttribute('aria-pressed', c.dataset.k === k ? 'true' : 'false'); });
    v.dataset.k = k;
    var on = k !== 'all';
    var hit = function (n) { return k === 'chat' ? n.dataset.chat === '1' : n.dataset.kind === k; };
    v.querySelectorAll('.cz-row').forEach(function (row) {      // the week: a row with nothing to show is a thin line
      var shown = 0;
      row.querySelectorAll('[data-kind]').forEach(function (n) {
        var ok = on ? hit(n) : parseInt(n.dataset.n || '0', 10) < CAP;
        n.classList.toggle('is-off', !ok);
        if (ok) shown++;
      });
      var more = row.querySelector('.cz-more');
      if (more) more.hidden = on;
      var link = row.querySelector('.cz-row-link');
      if (!link) return;
      var thin = on && shown === 0;
      link.classList.toggle('is-bare', link.querySelectorAll('[data-kind]:not(.is-off)').length === 0);
      link.classList.toggle('is-thin', thin);
      row.classList.toggle('is-thin', thin);
      var t = link.querySelector('.cz-thin-t');
      if (t) t.textContent = thin ? 'Nothing for ' + (KIND_WORD[k] || k) : '';
    });
    var main = v.querySelector('.cz-day-main');                  // the day
    if (main) {
      var seen = 0;
      v.querySelectorAll('.cz-day-body [data-kind], .cz-now[data-kind]').forEach(function (n) {
        var ok = !on || (n.dataset.kind !== 'now' && n.dataset.kind !== 'empty' && hit(n));
        n.classList.toggle('is-off', !ok);
        if (ok && on) seen++;
      });
      v.querySelectorAll('.cz-part').forEach(function (p) { p.classList.toggle('is-off', k === 'chat' && p.dataset.chat !== '1'); });
      var none = main.querySelector('.cz-kind-none');
      if (none) none.hidden = !(on && seen === 0);
    }
  }
  document.addEventListener('click', function (e) {
    var chip = e.target.closest ? e.target.closest('.cz-kchip') : null;
    if (!chip || !stage.contains(chip)) return;
    setKind(chip.dataset.k);
    applyKinds();
  });

  // ---- the add-a-step sheet: Everyone and the people are one choice ----------------------------------------------------------
  document.addEventListener('change', function (e) {
    var input = e.target;
    if (!input.matches || !input.matches('input[name="who"]') || !input.form) return;
    var all = input.form.querySelector('input[name="who"][value="all"]');
    var others = Array.prototype.filter.call(input.form.querySelectorAll('input[name="who"]'), function (x) { return x !== all; });
    if (!all) return;
    if (input === all) { if (all.checked) others.forEach(function (x) { x.checked = false; }); else all.checked = true; }
    else if (input.checked) all.checked = false;
    else if (!others.some(function (x) { return x.checked; })) all.checked = true;
  });

  // ---- fingers on the canvas ------------------------------------------------------------------------------------------------
  // F-092: pinch to zoom is gone (it did not work reliably on the captain's iPhone); Day | Week is the way between the views. The fingers are still counted, so
  // two fingers never start a flick or a drag, and the page's own pinch zoom is left alone.
  var pts = {};
  function count() { return Object.keys(pts).length; }
  stage.addEventListener('pointerdown', function (e) { pts[e.pointerId] = { x: e.clientX, y: e.clientY }; });
  function lift(e) { delete pts[e.pointerId]; }
  stage.addEventListener('pointerup', lift);
  stage.addEventListener('pointercancel', lift);
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

  // ---- F-090: one day at a time. A day to the right slides in from the right; a flick left is the next day, right the previous one ----------------------------
  function dayOf(u) { var m = /[?&]day=(\d+)/.exec(u || ''); return m ? parseInt(m[1], 10) : null; }
  function sideways(u) {
    var v = view(), from = v && v.dataset.level === 'day' ? parseInt(v.dataset.day, 10) : null, to = dayOf(u);
    return from === null || to === null || from === to ? 'side' : to > from ? 'next' : 'prev';
  }
  var flick = null;
  var FLICK = 60;
  stage.addEventListener('pointerdown', function (e) {
    flick = null;
    var v = view();
    if (!v || v.dataset.level !== 'day' || e.pointerType === 'mouse' || count() > 1) return;
    if (e.target.closest && e.target.closest('.cz-dpills, .cz-strip, .cz-filters, .cz-kinds, .cz-sheet, input, textarea, select')) return;
    flick = { id: e.pointerId, x: e.clientX, y: e.clientY, at: Date.now(), v: v };
  });
  stage.addEventListener('pointermove', function (e) {
    if (!flick || e.pointerId !== flick.id) return;
    if (count() > 1 || (g && g.mode === 'drag') || CZ.held) { flick.v.style.transform = ''; flick = null; return; }      // a held block (day_grid.js) never flicks
    var dx = e.clientX - flick.x, dy = e.clientY - flick.y;
    if (!reduced.matches && Math.abs(dx) > Math.abs(dy) * 1.5 && Math.abs(dx) > 12) {
      var edge = (dx < 0 && !flick.v.dataset.next) || (dx > 0 && !flick.v.dataset.prev);
      flick.v.style.transform = 'translateX(' + (dx * (edge ? 0.08 : 0.25)) + 'px)';   // follows the finger a little; barely at the first or last day
    }
  });
  function endFlick(e) {
    if (!flick || e.pointerId !== flick.id) return;
    var f = flick;
    flick = null;
    f.v.style.transform = '';
    if (e.type !== 'pointerup' || busy || (g && g.mode === 'drag') || CZ.held) return;
    var dx = e.clientX - f.x, dy = e.clientY - f.y;
    if (Math.abs(dx) < FLICK || Math.abs(dx) < Math.abs(dy) * 1.5 || Date.now() - f.at > 900) return;
    var u = dx < 0 ? f.v.dataset.next : f.v.dataset.prev;
    if (!u) return;
    clickGuard = Date.now() + 250;
    guardItem = f.v;      // the click the lifting finger makes is not a tap on what it lifted from
    goto(path(u), { dir: dx < 0 ? 'next' : 'prev', key: null, mode: 'replace' });
  }
  stage.addEventListener('pointerup', endFlick);
  stage.addEventListener('pointercancel', endFlick);

  // ---- hold to move, swipe for Done and Set aside (editors only) ------------------------------------------------------------
  // One gesture at a time, from pointerdown on a step (data-drag) or on a list chip (data-add-title):
  //   wait   the finger is down and still. After HOLD ms the step is lifted (drag). Moving more than SLOP first is a scroll (or, sideways on a row, a swipe).
  //   drag   a chip follows the finger; the part under it, a day in the bar at the top, or the Set aside tray is the target. Letting go posts the move.
  //   swipe  the row slides left over its Done and Set aside buttons, and settles open or shut.
  var edit = stage.dataset.edit === '1';
  var HOLD = 350, SLOP = 10;
  var g = null;                 // the gesture in progress
  var clickGuard = 0, guardItem = null;     // the click that follows a drag or a swipe, on the step that was held, is not a tap

  function dragLabel(item) {
    if (item.dataset.addTitle) return item.dataset.addTitle;
    var t = item.querySelector('.cz-chip-t, .cz-step-t');
    return t ? t.textContent.trim() : 'Step';
  }
  function closeSwipes(except) {
    stage.querySelectorAll('.cz-swipe.is-open').forEach(function (n) {
      if (n === except) return;
      n.classList.remove('is-open');
      var r = n.querySelector('.cz-step');
      if (r) r.style.marginRight = '';
    });
  }
  function endGesture() {
    if (!g) return;
    clearTimeout(g.timer);
    cancelAnimationFrame(g.raf || 0);
    if (g.lift && g.lift.parentNode) g.lift.parentNode.removeChild(g.lift);
    if (g.item) g.item.classList.remove('is-lifted');
    stage.classList.remove('cz-dragging');
    clearMarks();
    g = null;
  }
  function clearMarks() {
    stage.querySelectorAll('.is-target, .is-before, .is-end').forEach(function (n) { n.classList.remove('is-target', 'is-before', 'is-end'); });
  }

  stage.addEventListener('pointerdown', function (e) {
    if (!edit || e.button > 0 || count() !== 1) { if (g && count() > 1) endGesture(); return; }
    var item = e.target.closest ? e.target.closest('[data-drag], .cz-addchip[data-add-title]') : null;
    var onActs = e.target.closest ? e.target.closest('.cz-swipe-acts') : null;
    if (!onActs) closeSwipes(item && item.classList.contains('cz-swipe') ? item : null);
    if (!item || !stage.contains(item) || onActs) return;
    endGesture();
    g = { id: e.pointerId, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, item: item, mode: 'wait', adding: !item.hasAttribute('data-drag'), swipe: item.classList.contains('cz-swipe') };
    g.timer = setTimeout(pickUp, HOLD);
  });

  function pickUp() {
    if (!g || g.mode !== 'wait') return;
    g.mode = 'drag';
    var lift = document.createElement('div');
    lift.className = 'cz-lift';
    lift.setAttribute('aria-hidden', 'true');
    lift.textContent = dragLabel(g.item);
    var hint = document.createElement('span');
    hint.className = 'cz-lift-when';
    lift.appendChild(hint);
    (document.getElementById('main') || document.body).appendChild(lift);
    g.lift = lift;
    g.item.classList.add('is-lifted');
    stage.classList.add('cz-dragging');
    stage.querySelectorAll('.cz-dd').forEach(function (n) { n.classList.toggle('is-here', !g.adding && n.dataset.dropAct === g.item.dataset.act); });     // the day it is already on
    try { if (navigator.vibrate) navigator.vibrate(12); } catch (err) { /* no buzz */ }
    place();
    scroller();
  }

  function place() {
    if (!g || !g.lift) return;
    var w = g.lift.offsetWidth, h = g.lift.offsetHeight;
    var x = Math.min(Math.max(g.x - w / 2, 8), window.innerWidth - w - 8);
    g.lift.style.transform = 'translate(' + x + 'px,' + (g.y - h - 18) + 'px) rotate(-2deg)';
    var t = targetAt(g.x, g.y);
    clearMarks();
    g.target = t;
    var when = '';
    if (t) {
      t.el.classList.add('is-target');
      if (t.kind === 'part') {
        if (t.beforeEl) { t.beforeEl.classList.add('is-before'); if (t.beforeEl.dataset.time) when = ' · ' + clock12(t.beforeEl.dataset.time); }
        else t.el.classList.add('is-end');
      }
    }
    g.lift.classList.toggle('is-on-target', !!t);
    g.lift.firstElementChild.textContent = t ? (t.kind === 'aside' ? 'Set aside' : t.kind === 'day' ? 'Move to this day' : 'Drop here' + when) : '';
  }
  function clock12(v) {
    var m = /^(\d{1,2}):(\d{2})$/.exec(v || '');
    if (!m) return '';
    var h = parseInt(m[1], 10);
    return ((h % 12) || 12) + ':' + m[2] + ' ' + (h < 12 ? 'AM' : 'PM');
  }

  // What is under the finger. A step is dropped on a part (before the step the finger is above, else at the end), on a day in the bar (that day's plan), or on the tray.
  function targetAt(x, y) {
    var el = document.elementFromPoint(x, y);
    if (!el || !el.closest) return null;
    var day = el.closest('[data-drop-act]');
    if (day && !g.adding) return day.dataset.dropAct === g.item.dataset.act ? null : { kind: 'day', el: day, act: day.dataset.dropAct };
    var tray = el.closest('[data-drop-aside]');
    if (tray && !g.adding) return g.item.dataset.aside === '1' ? null : { kind: 'aside', el: tray };
    var part = el.closest('[data-part]');
    if (!part && el.closest('.cz-gb-open')) {          // on the day grid a park block's link covers its part labels: the label under the finger is the part
      part = document.elementsFromPoint(x, y).filter(function (n) { return n.matches && n.matches('.cz-gb-part'); })[0] || null;
    }
    if (!part || !part.dataset.act || !stage.contains(part)) return null;
    var items = Array.prototype.filter.call(part.querySelectorAll('[data-drag]'), function (n) { return n !== g.item && !n.classList.contains('cz-chip-aside'); });
    var pr = part.getBoundingClientRect(), before = null;
    for (var i = 0; i < items.length; i++) {
      var r = items[i].getBoundingClientRect();
      var wide = r.width > pr.width * 0.6;
      if (y < r.top || (wide ? y < r.top + r.height / 2 : (y <= r.bottom && x < r.left + r.width / 2))) { before = items[i]; break; }
    }
    return { kind: 'part', el: part, beforeEl: before, act: part.dataset.act, part: part.dataset.part, before: before ? before.dataset.drag : '' };
  }

  // The page scrolls while a lifted step is held near the top or the bottom edge (unless it is over the days or the tray).
  function scroller() {
    if (!g || g.mode !== 'drag') return;
    var dy = 0;
    if (!g.target || g.target.kind === 'part' || !g.target.kind) {
      if (g.y < 110) dy = -Math.ceil((110 - g.y) / 6);
      else if (g.y > window.innerHeight - 56) dy = Math.ceil((g.y - (window.innerHeight - 56)) / 3);
    }
    if (dy) { window.scrollBy(0, dy); place(); }
    g.raf = requestAnimationFrame(scroller);
  }

  document.addEventListener('pointermove', function (e) {
    if (!g || e.pointerId !== g.id) return;
    g.x = e.clientX;
    g.y = e.clientY;
    var dx = g.x - g.x0, dy = g.y - g.y0;
    if (g.mode === 'wait' && Math.hypot(dx, dy) > SLOP) {
      if (g.swipe && Math.abs(dx) > Math.abs(dy) * 1.2) { clearTimeout(g.timer); g.mode = 'swipe'; g.open = g.item.classList.contains('is-open'); g.item.classList.add('is-swiping'); }
      else { endGesture(); return; }       // it is a scroll
    }
    if (g.mode === 'drag') { place(); }
    else if (g.mode === 'swipe') {
      var acts = g.item.querySelector('.cz-swipe-acts'), row = g.item.querySelector('.cz-step');
      var w = acts ? acts.offsetWidth : 0;
      var off = Math.max(-w, Math.min(0, (g.open ? -w : 0) + dx));
      g.off = off;
      g.w = w;
      if (row) row.style.marginRight = (-off) + 'px';
    }
  });
  // A held finger on a phone is still a pointermove-less stretch; once a step is lifted the browser must not scroll under it.
  document.addEventListener('touchmove', function (e) { if (g && g.mode !== 'wait' && e.cancelable) e.preventDefault(); }, { passive: false });
  document.addEventListener('dragstart', function (e) { if (g && e.target.closest && e.target.closest('[data-drag], .cz-addchip')) e.preventDefault(); });   // a mouse would start dragging the link itself
  document.addEventListener('contextmenu', function (e) { if (g && e.target.closest && e.target.closest('[data-drag], .cz-addchip')) e.preventDefault(); });

  function dropOn() {
    var t = g.target, item = g.item, adding = g.adding;
    if (!t) return;
    var fields;
    if (adding) {
      if (t.kind !== 'part') return;
      fields = { act: t.act, part: t.part, title: item.dataset.addTitle, note: item.dataset.addNote || '' };
      post('/trip/canvas/add', tripBody(fields)).then(function (res) { return refresh().then(function () { showToast(res.toast || 'Added'); }); }).catch(function (err) { showToast(err && err.soft ? err.soft : 'Could not add that.'); });
      return;
    }
    if (t.kind === 'part') fields = { step: item.dataset.drag, part: t.part, before: t.before };
    else if (t.kind === 'day') fields = { step: item.dataset.drag, act: t.act };
    else fields = { step: item.dataset.drag, aside: '1' };
    fields.next = here();
    post('/trip/canvas/move', tripBody(fields)).then(function (res) {
      return refresh().then(function () { if (res.toast) showToast(res.toast, res.undo); });
    }).catch(function (err) { showToast(err && err.soft ? err.soft : 'Could not move that.'); });
  }

  function settle() {
    var item = g.item, row = item.querySelector('.cz-step');
    item.classList.remove('is-swiping');
    var open = g.off !== undefined && g.off < -g.w / 2;
    item.classList.toggle('is-open', open);
    if (row) row.style.marginRight = open ? g.w + 'px' : '';
  }

  function finish(e) {
    if (!g || e.pointerId !== g.id) return;
    var mode = g.mode;
    if (mode === 'drag') { clickGuard = Date.now() + 200; guardItem = g.item; if (e.type === 'pointerup') dropOn(); }
    else if (mode === 'swipe') { clickGuard = Date.now() + 200; guardItem = g.item; settle(); }
    endGesture();
  }
  document.addEventListener('pointerup', finish);
  document.addEventListener('pointercancel', finish);

  // The click that ends a drag or a swipe is not a tap; a tap on an open row puts its buttons away instead of opening the step.
  document.addEventListener('click', function (e) {
    if (!stage.contains(e.target)) return;
    if (Date.now() < clickGuard && guardItem && guardItem.contains(e.target) && !e.target.closest(".cz-swipe-acts")) { e.preventDefault(); e.stopImmediatePropagation(); return; }
    var open = e.target.closest ? e.target.closest('.cz-swipe.is-open') : null;
    if (open && !e.target.closest('.cz-swipe-acts')) { e.preventDefault(); e.stopImmediatePropagation(); closeSwipes(); }
  }, true);

  // The day grid's script needs a few of these. `quiet` brings the level up to date after a write with no animation, the scroll kept and the focus left alone.
  CZ.view = view; CZ.post = post; CZ.tripBody = tripBody; CZ.showToast = showToast; CZ.hideToast = hideToast; CZ.here = here; CZ.reduced = reduced; CZ.goto = goto; CZ.path = path;
  CZ.busy = function () { return busy; };
  CZ.guard = function (ms, el) { clickGuard = Date.now() + ms; guardItem = el; };      // the click a lifting finger makes is not a tap on what it lifted from
  CZ.quiet = function () {
    return new Promise(function (done) {
      whenIdle(function () {
        cache = {};
        var y = window.scrollY;
        fetchLevel(here()).then(function (html) {
          var back = CZ.beforeQuiet ? CZ.beforeQuiet() : null;      // the day grid puts the focus back on the block that had it
          quietSwap = true;
          try { swap(html, ''); } finally { quietSwap = false; }
          if (back) back();
          window.scrollTo(0, y);
          done(true);
        }).catch(function () { done(false); });
      });
    });
  };
  window.CZ = CZ;

  applyFilter();
  applyKinds();
  centreDay();
  askHere();
  prefetch();
})();
