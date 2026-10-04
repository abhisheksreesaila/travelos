// The trip canvas (F-081): week > day > block > step as one surface that zooms.
//
// Every level is a page of its own (gitaway/pages/tripcanvas.py), so with no script it is plain links and forms. With script, a tap on a link marked data-zoom
// ("in", "out" or "side"), a two-finger pinch, or the browser's Back fetches that level as a fragment (?frag=1) and swaps it inside a View Transition. The element
// that was tapped (data-zk="day-2" | "blk-a3" | "stp-<id>") is named `cz-hero` before and after the swap, so it grows into the next level's heading or sheet and
// shrinks back on zoom out. No View Transitions: the new level scales and fades in (CSS .cz-in-*). Reduced motion: an instant swap.
// A write from the sheet (Mark done, Set aside, Put back, Not done) posts with X-Canvas and the server answers 204 + X-Canvas-Url; we then zoom out to that level.
//
// F-082, touch: hold a step (about 350 ms) to lift it; a chip follows the finger, and the parts, the days across the top and the Set aside tray light up as drop
// targets; letting go posts a move and swaps the level in place, with a toast that has Undo. Swipe a step left for Done and Set aside; swipe right (or tap elsewhere) to
// put them away. Filter chips highlight the steps that match and dim the rest, remembered per person in localStorage. The Move menu on the step sheet does everything
// dragging does with buttons.
(function () {
  var stage = document.getElementById('cz');
  if (!stage) return;
  var root = document.documentElement;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var RANK = { week: 0, day: 1, block: 2, step: 3 };
  var KEY = /^[a-z]{3}-[A-Za-z0-9-]+$/;
  var cache = {};          // url -> { at, promise }: a level fetched as the finger went down, used by the tap that follows
  var busy = false;
  var swallow = 0;         // a pinch ends with finger lifts that must not count as taps

  function path(u) { var a = document.createElement('a'); a.href = u; return a.pathname + a.search; }
  function fragUrl(u) { return u + (u.indexOf('?') < 0 ? '?' : '&') + 'frag=1'; }
  function view() { return stage.querySelector('.cz-view'); }
  function levelOf(u) {
    var q = path(u).split('?')[1] || '';
    return /(^|&)step=/.test(q) || /(^|&)add=1/.test(q) ? 'step' : /(^|&)block=/.test(q) ? 'block' : /(^|&)day=/.test(q) ? 'day' : 'week';
  }

  function fetchLevel(u) {
    var now = Date.now(), hit = cache[u];
    if (hit && now - hit.at < 4000) return hit.promise;
    var p = fetch(fragUrl(u), { credentials: 'same-origin', headers: { 'X-Canvas': '1' } }).then(function (r) {
      if (!r.ok) throw new Error('level ' + r.status);
      return r.text();
    });
    cache[u] = { at: now, promise: p };
    p.catch(function () { delete cache[u]; });
    return p;
  }

  function swap(html, dir) {
    stage.innerHTML = html;
    var v = view();
    if (!v) return;
    if (v.dataset.title) document.title = 'GitAway · ' + v.dataset.title;
    var focus = v.querySelector('#cz-sheet-title') || v.querySelector('#cz-title');
    if (focus) { try { focus.focus({ preventScroll: true }); } catch (e) { focus.focus(); } }
    if (dir && !(document.startViewTransition && !reduced.matches)) {
      v.classList.add('cz-in-' + dir);
      v.addEventListener('animationend', function () { v.classList.remove('cz-in-' + dir); }, { once: true });
    }
    applyFilter();
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

  function directionTo(u) {
    var here = view() ? view().dataset.level : 'week';
    var a = RANK[here], b = RANK[levelOf(u)];
    return b > a ? 'in' : b < a ? 'out' : 'side';
  }

  function goto(u, o) {
    o = o || {};
    if (busy) return Promise.resolve();
    busy = true;
    var dir = o.dir || directionTo(u);
    var v = view(), y0 = window.scrollY;
    var key = o.key !== undefined ? o.key : (dir === 'out' && v ? v.dataset.zout : null);
    return fetchLevel(u).then(function (html) {
      var remember = function () {
        if (o.mode === 'push') {
          history.replaceState(Object.assign({}, history.state, { y: window.scrollY }), '');
          history.pushState({ cz: 1, from: path(location.href) }, '', u);
          window.scrollTo(0, 0);
        } else if (o.mode === 'replace') {
          history.replaceState(Object.assign({}, history.state, { cz: 1 }), '', u);
          window.scrollTo(0, 0);
        } else if (o.mode === 'stay') {
          window.scrollTo(0, y0);
        } else if (o.mode === 'pop') {
          window.scrollTo(0, (history.state && history.state.y) || 0);
        }
      };
      return run(html, dir, key, remember);
    }).catch(function () { location.href = u; }).then(function () { busy = false; });
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
    if (e.isTrusted && swallow > Date.now()) { e.preventDefault(); return; }     // the lifting fingers of a pinch are not a tap (the pinch's own clicks are script-made)
    e.preventDefault();
    var dir = a.dataset.zoom, u = path(a.href);
    if (dir === 'out') { zoomOutTo(u); return; }
    var hero = a.closest('[data-zk]');
    goto(u, { dir: dir, key: dir === 'in' && hero ? hero.dataset.zk : null, mode: 'push' });
  });

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

  // A level is fetched as soon as a finger goes down on a link to it, so the tap that follows has nothing to wait for.
  document.addEventListener('pointerdown', function (e) {
    var a = e.target.closest ? e.target.closest('a[data-zoom]') : null;
    if (a && stage.contains(a) && a.dataset.zoom !== 'out') fetchLevel(path(a.href)).catch(function () {});
  }, { passive: true });

  // ---- writes ------------------------------------------------------------------------------------------------------------
  // Every write posts with X-Canvas. The server answers 204 + X-Canvas-Url (a tick, a note), or JSON {url, toast, undo} (a move, an add, an undo), or 422 {error}.
  function post(url, body) {
    return fetch(url, { method: 'POST', body: body, credentials: 'same-origin', headers: { 'X-Canvas': '1' } }).then(function (r) {
      if (r.status === 422) return r.json().then(function (j) { var e = new Error('refused'); e.soft = j.error || 'That did not work.'; throw e; });
      if (r.status === 204) { var next = r.headers.get('X-Canvas-Url'); if (!next) throw new Error('write'); return { url: next }; }
      if (!r.ok) throw new Error('write ' + r.status);
      return r.json();
    });
  }
  function here() { return path(location.href); }
  function refresh() { cache = {}; return goto(here(), { dir: 'side', mode: 'stay', key: null }); }

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
      b.addEventListener('click', function () { doUndo(undo); });
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

  // ---- pinch ------------------------------------------------------------------------------------------------------------
  // Two fingers moving apart zoom in (to the day, block or step under them), together zoom out. Pointer events, so a mouse-less laptop test can drive it.
  var pts = {}, base = 0, fired = false;
  function count() { return Object.keys(pts).length; }
  function spread() {
    var k = Object.keys(pts);
    var a = pts[k[0]], b = pts[k[1]];
    return { d: Math.hypot(a.x - b.x, a.y - b.y), x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  }
  function zoomInAt(x, y) {
    var el = document.elementFromPoint(x, y);
    var hero = el && el.closest ? el.closest('[data-zk]') : null;
    var link = hero ? (hero.matches('a[data-zoom="in"]') ? hero : hero.querySelector('a[data-zoom="in"]')) : null;
    if (!link) {
      // not over anything zoomable: the first link to a deeper level that is on screen
      link = Array.prototype.find.call(stage.querySelectorAll('a[data-zoom="in"]'), function (n) { var r = n.getBoundingClientRect(); return r.bottom > 0 && r.top < window.innerHeight; });
    }
    if (link) link.click();
  }
  stage.addEventListener('pointerdown', function (e) {
    pts[e.pointerId] = { x: e.clientX, y: e.clientY };
    if (count() === 2) { base = spread().d || 1; fired = false; }
  });
  stage.addEventListener('pointermove', function (e) {
    if (!pts[e.pointerId]) return;
    pts[e.pointerId] = { x: e.clientX, y: e.clientY };
    if (count() !== 2 || fired) return;
    var s = spread(), ratio = s.d / base;
    if (ratio > 1.3) {
      fired = true;
      if (view() && view().dataset.level !== 'step') zoomInAt(s.x, s.y);
      swallow = Date.now() + 500;
    } else if (ratio < 0.75) {
      fired = true;
      var u = up();
      if (u) u.click();
      swallow = Date.now() + 500;
    }
  });
  function lift(e) {
    if (count() >= 2) swallow = Date.now() + 500;
    delete pts[e.pointerId];
  }
  stage.addEventListener('pointerup', lift);
  stage.addEventListener('pointercancel', lift);

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

  applyFilter();
})();
