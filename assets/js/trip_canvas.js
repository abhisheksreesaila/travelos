// The trip canvas (F-081): week > day > block > step as one surface that zooms.
//
// Every level is a page of its own (gitaway/pages/tripcanvas.py), so with no script it is plain links and forms. With script, a tap on a link marked data-zoom
// ("in", "out" or "side"), a two-finger pinch, or the browser's Back fetches that level as a fragment (?frag=1) and swaps it inside a View Transition. The element
// that was tapped (data-zk="day-2" | "blk-a3" | "stp-<id>") is named `cz-hero` before and after the swap, so it grows into the next level's heading or sheet and
// shrinks back on zoom out. No View Transitions: the new level scales and fades in (CSS .cz-in-*). Reduced motion: an instant swap.
// A write from the sheet (Mark done, Set aside, Put back, Not done) posts with X-Canvas and the server answers 204 + X-Canvas-Url; we then zoom out to that level.
(function () {
  var stage = document.getElementById('cz');
  if (!stage) return;
  var root = document.documentElement;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var RANK = { week: 0, day: 1, block: 2, step: 3 };
  var KEY = /^[a-z]{3}-[A-Za-z0-9-]+$/;
  var cache = {};          // url -> { at, promise }: a level fetched as the finger went down, used by the tap that follows
  var busy = false;
  var waiting = null;      // the browser's Back or Forward pressed while a zoom was running: run it when that zoom is done
  var swallow = 0;         // a pinch ends with finger lifts that must not count as taps

  function path(u) { var a = document.createElement('a'); a.href = u; return a.pathname + a.search; }
  function fragUrl(u) { return u + (u.indexOf('?') < 0 ? '?' : '&') + 'frag=1'; }
  function view() { return stage.querySelector('.cz-view'); }
  function levelOf(u) {
    var q = path(u).split('?')[1] || '';
    return /(^|&)step=/.test(q) ? 'step' : /(^|&)block=/.test(q) ? 'block' : /(^|&)day=/.test(q) ? 'day' : 'week';
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
    if (busy) { if (o.mode === 'pop') waiting = u; return; }
    busy = true;
    var dir = o.dir || directionTo(u);
    var v = view();
    var key = o.key !== undefined ? o.key : (dir === 'out' && v ? v.dataset.zout : null);
    fetchLevel(u).then(function (html) {
      var remember = function () {
        if (o.mode === 'push') {
          history.replaceState(Object.assign({}, history.state, { y: window.scrollY }), '');
          history.pushState({ cz: 1, from: path(location.href) }, '', u);
          window.scrollTo(0, 0);
        } else if (o.mode === 'replace') {
          history.replaceState(Object.assign({}, history.state, { cz: 1 }), '', u);
          window.scrollTo(0, 0);
        } else if (o.mode === 'pop') {
          window.scrollTo(0, (history.state && history.state.y) || 0);
        }
      };
      return run(html, dir, key, remember);
    }).catch(function () { location.href = u; }).then(function () {
      busy = false;
      if (waiting) { waiting = null; goto(path(location.href), { mode: 'pop' }); }     // the address bar is the truth: show what it says
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

  // ---- writes from the sheet --------------------------------------------------------------------------------------------
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f.matches || !f.matches('form[data-cz-form]') || e.defaultPrevented) return;
    e.preventDefault();
    if (f.dataset.sent) return;
    f.dataset.sent = '1';
    var body = new URLSearchParams(new FormData(f));
    f.querySelectorAll('button').forEach(function (b) { b.disabled = true; });
    fetch(f.action, { method: 'POST', body: body, credentials: 'same-origin', headers: { 'X-Canvas': '1' } }).then(function (r) {
      var next = r.headers.get('X-Canvas-Url');
      if (!r.ok || !next) throw new Error('write ' + r.status);
      cache = {};
      zoomOutTo(next);
    }).catch(function () { f.submit(); });     // the plain form post does the same write and redirects to the level
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
})();
