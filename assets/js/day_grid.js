// The day as a time grid (F-097): hold a block about 350 ms to lift it and drag it to a new time (15-minute snap, the time shown under the finger, the page scrolls at the
// top and bottom edge); hold its bottom edge to change its length, while the grid zooms in around the finger (about 2.5x, 5-minute snap) and eases back on release. Each
// change saves through the calendar's own rules (POST /trip/canvas/plan) and shows a toast with Undo. Editors only: a viewer's page has no data-edit and no gestures.
// Needs trip_canvas.js, which loads first and shares its toast, writes, quiet refresh and the flick (a held block never flicks, CZ.held).
//
// Smoothness: nothing here reads layout inside a frame. The geometry is read once when a block is lifted; after that each frame writes a `transform` (a move), one height
// on one absolutely positioned block (a resize) and the zoom's scale, all from the latest pointer position, one rAF at a time. The zoom is a scaleY on one layer
// (.cz-g-zoom) with its origin on the edge being dragged; --zk carries the same number to what has words in it, which scales back by 1/--zk, so text keeps its size.
// Reduced motion: no zoom, no easing; moves and resizes keep the 15-minute snap.
//
// F-098 adds the hold menu, the wiggle, rename in place and delete (further down).
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var stage = CZ.stage;
  var root = document.documentElement;
  var HOLD = 350, SLOP = 10, TURN = 4;
  var GRAIN = 15, FINE = 5, ZOOM = 2.5, MIN_LEN = 15, DAY_END = 22 * 60;
  var ptrs = {};          // fingers down: two fingers are never a gesture of ours
  var gg = null;          // the gesture in progress
  var Z = { k: 1, raf: 0, grid: null, zoom: null };      // the zoom, which outlives the gesture while it eases back
  var label = null;
  var busy = false;       // a block is landing: no new gesture until it has
  var tick = 0;

  function editing() { return stage.dataset.edit === '1'; }
  function grid() { return stage.querySelector('#cz-grid'); }
  function rem() { return parseFloat(getComputedStyle(root).fontSize) || 16; }
  function clamp(v, lo, hi) { return Math.min(Math.max(v, lo), hi); }
  function clock12(m) { var h = Math.floor(m / 60) % 24, mm = m % 60; return ((h % 12) || 12) + ':' + (mm < 10 ? '0' : '') + mm + ' ' + (h < 12 ? 'AM' : 'PM'); }
  function span(s, e) { var a = clock12(s), b = clock12(e); return a.slice(-2) === b.slice(-2) ? a.slice(0, -3) + ' – ' + b : a + ' – ' + b; }
  function lenText(m) { var h = Math.floor(m / 60), mm = m % 60; return h ? (mm ? h + ' h ' + mm + ' min' : h + ' h') : mm + ' min'; }
  function buzz(ms) { try { if (navigator.vibrate) navigator.vibrate(ms); } catch (e) { /* no buzz */ } }
  function blockTitle(el) { var t = el.querySelector('.cz-gb-t'); return t ? t.textContent.trim() : (el.dataset.title || 'This plan'); }

  // ---- fingers ------------------------------------------------------------------------------------------------------------
  function count() { return Object.keys(ptrs).length; }
  document.addEventListener('pointerdown', function (e) { ptrs[e.pointerId] = 1; if (count() > 1 && gg) cancel(); }, true);
  function liftFinger(e) { delete ptrs[e.pointerId]; }
  document.addEventListener('pointerup', liftFinger, true);
  document.addEventListener('pointercancel', liftFinger, true);

  stage.addEventListener('pointerdown', function (e) {
    if (!editing() || gg || busy || CZ.held || e.button > 0 || count() !== 1) return;        // CZ.held: a new plan's title is being typed (day_new.js): the grid is calm
    var el = e.target.closest ? e.target.closest('.cz-gb') : null;
    if (!el || !stage.contains(el) || e.target.closest('input, textarea')) return;
    var r = el.getBoundingClientRect();
    var edge = Math.min(clamp(r.height * 0.4, rem() * 0.75, rem() * 1.75), r.height * 0.45);        // the bottom edge: a hand's width of the block's last stretch (never more than its lower half)
    gg = { id: e.pointerId, el: el, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, mode: 'wait', resize: e.clientY > r.bottom - edge, moved: false, dirty: false };
    gg.timer = setTimeout(lift, HOLD);
  });

  document.addEventListener('pointermove', function (e) {
    if (!gg || e.pointerId !== gg.id) return;
    gg.x = e.clientX;
    gg.y = e.clientY;
    if (gg.mode === 'wait') {
      if (Math.hypot(gg.x - gg.x0, gg.y - gg.y0) > SLOP) { clearTimeout(gg.timer); gg = null; }       // it is a scroll, or the flick between days: not ours
      return;
    }
    if (!gg.moved && Math.hypot(gg.x - gg.x0, gg.y - gg.y0) > TURN) gg.moved = true;
    gg.dirty = true;
  });
  // Once a block is held the page must not scroll under the finger (it has not started to: the finger was still).
  document.addEventListener('touchmove', function (e) { if (gg && gg.mode !== 'wait' && e.cancelable) e.preventDefault(); }, { passive: false });
  document.addEventListener('dragstart', function (e) { if (e.target.closest && e.target.closest('.cz-gb')) e.preventDefault(); });
  document.addEventListener('contextmenu', function (e) { if (editing() && e.target.closest && e.target.closest('.cz-gb')) e.preventDefault(); });

  function cancel() {
    if (!gg) return;
    clearTimeout(gg.timer);
    cancelAnimationFrame(gg.raf || 0);
    var g = gg;
    gg = null;
    if (g.mode !== 'wait') { restore(g); unhold(g); }
  }
  document.addEventListener('pointercancel', function (e) { if (gg && e.pointerId === gg.id) cancel(); });

  // ---- lift: read the geometry once, then only write ------------------------------------------------------------------------
  function lift() {
    if (!gg || gg.mode !== 'wait') return;
    var el = gg.el, g = grid(), zoom = g && g.querySelector('.cz-g-zoom');
    if (!g || !zoom) { gg = null; return; }
    gg.mode = 'held';
    CZ.held = true;
    gg.g = g;
    gg.zoom = zoom;
    gg.lo = +g.dataset.lo;
    gg.hi = +g.dataset.hi;
    gg.s0 = +el.dataset.s;
    gg.e0 = +el.dataset.e;
    var sy = window.scrollY, zr = zoom.getBoundingClientRect(), br = el.getBoundingClientRect();
    gg.ppm = zoom.offsetHeight / (gg.hi - gg.lo);                        // pixels per minute
    gg.top0 = zr.top + sy;                                                // the layer's top, in page coordinates
    gg.left = el.offsetLeft;
    gg.width = el.offsetWidth;
    gg.grab = gg.y0 + sy - (gg.top0 + (gg.s0 - gg.lo) * gg.ppm);        // where on the block the finger took it (move)
    gg.off = gg.y0 + sy - (gg.top0 + (gg.e0 - gg.lo) * gg.ppm);         // and how far from the bottom edge (resize)
    gg.cur = gg.resize ? gg.e0 : gg.s0;
    gg.h0 = br.height;
    var tabs = document.querySelector('.ph-tabs');
    gg.bottom = (tabs && getComputedStyle(tabs).display !== 'none' ? tabs.getBoundingClientRect().top : window.innerHeight) - 72;      // the tab bar is not part of the page to scroll under
    el.classList.add(gg.resize ? 'is-resizing' : 'is-held');
    g.classList.add('is-editing-time');
    buzz(14);
    makeLabel();
    if (gg.resize) startZoom(); else makeGhost();
    paint(gg);
    gg.raf = requestAnimationFrame(frame);
  }

  function makeGhost() {
    var ghost = document.createElement('div');
    ghost.className = 'cz-g-ghost';
    ghost.setAttribute('aria-hidden', 'true');
    ghost.style.cssText = 'left:' + gg.left + 'px;width:' + gg.width + 'px;top:' + ((gg.s0 - gg.lo) * gg.ppm) + 'px;height:' + ((gg.e0 - gg.s0) * gg.ppm) + 'px';
    gg.el.parentNode.insertBefore(ghost, gg.el);
    gg.ghost = ghost;
  }

  function makeLabel() {
    label = document.createElement('div');
    label.className = 'cz-g-label';
    label.setAttribute('aria-hidden', 'true');
    label.appendChild(document.createElement('span'));
    label.appendChild(document.createElement('small'));
    (document.getElementById('main') || document.body).appendChild(label);
    gg.lw = 0;
  }
  function dropLabel() { if (label && label.parentNode) label.parentNode.removeChild(label); label = null; }

  // ---- the zoom -----------------------------------------------------------------------------------------------------------
  function setK(k) {
    Z.k = k;
    Z.zoom.style.transform = k === 1 ? '' : 'scaleY(' + k + ')';
    Z.grid.style.setProperty('--zk', k);
  }
  function ease(p) { return 1 - Math.pow(1 - p, 3); }
  function tween(to, ms, done) {
    cancelAnimationFrame(Z.raf);
    var from = Z.k, t0 = performance.now();
    (function step(now) {
      var p = Math.min(1, (now - t0) / ms);
      setK(from + (to - from) * ease(p));
      if (p < 1) Z.raf = requestAnimationFrame(step); else if (done) done();
    })(t0);
  }
  function startZoom() {
    Z.grid = gg.g;
    Z.zoom = gg.zoom;
    gg.oy = (gg.e0 - gg.lo) * gg.ppm;                                    // the edge being dragged, in the layer: the zoom's origin, so it stays under the finger
    gg.bottomPage = gg.top0 + gg.oy;
    Z.zoom.style.transformOrigin = '0 ' + gg.oy + 'px';
    Z.zoom.classList.add('is-zooming');
    gg.zoomed = !CZ.reduced.matches;
    if (gg.zoomed) tween(ZOOM, 260);
  }
  function endZoom(done) {
    if (!Z.zoom) { if (done) done(); return; }
    var finish = function () {
      Z.zoom.style.transform = '';
      Z.zoom.style.transformOrigin = '';
      Z.zoom.classList.remove('is-zooming');
      Z.grid.style.removeProperty('--zk');
      Z.k = 1;
      Z.zoom = Z.grid = null;
      if (done) done();
    };
    if (Z.k === 1 || CZ.reduced.matches) finish(); else tween(1, 240, finish);
  }

  // ---- each frame: the edge scroll, then the block ------------------------------------------------------------------------
  function frame() {
    if (!gg || gg.mode !== 'held') return;
    var zoomed = gg.resize && Z.k > 1.01;
    var top = 88, bottom = gg.bottom;
    var dy = 0, speed = zoomed ? 7 : 11;
    if (gg.y < top) dy = -Math.ceil(Math.min(1, (top - gg.y) / top) * speed) - 1;
    else if (gg.y > bottom) dy = Math.ceil(Math.min(1, (gg.y - bottom) / 72) * speed) + 1;
    if (dy) { window.scrollBy(0, dy); gg.dirty = true; }
    if (gg.dirty) { gg.dirty = false; paint(gg); }
    gg.raf = requestAnimationFrame(frame);
  }

  function paint(gg) {
    var sy = window.scrollY, fy = gg.y + sy;
    var snapped, text, small;
    if (gg.resize) {
      var k = Z.k, grain = gg.zoomed && k > 1.5 ? FINE : GRAIN;
      var eu = gg.oy + (fy - gg.off - gg.bottomPage) / k;                  // the edge, in the layer's own pixels
      var e = clamp(Math.round((gg.lo + eu / gg.ppm) / grain) * grain, gg.s0 + MIN_LEN, Math.min(gg.hi, DAY_END));
      if (e !== gg.cur) { buzz(4); gg.cur = e; setWhen(gg.el, gg.s0, e); }
      gg.el.style.height = ((e - gg.s0) * gg.ppm) + 'px';
      snapped = e;
      text = span(gg.s0, e);
      small = lenText(e - gg.s0);
    } else {
      var dur = gg.e0 - gg.s0, maxStart = Math.max(gg.lo, Math.min(gg.hi, DAY_END) - dur);
      var topPage = fy - gg.grab, base = gg.top0 + (gg.s0 - gg.lo) * gg.ppm;
      var s = clamp(Math.round((gg.lo + (topPage - gg.top0) / gg.ppm) / GRAIN) * GRAIN, gg.lo, maxStart);
      if (s !== gg.cur) { buzz(4); gg.cur = s; setWhen(gg.el, s, s + dur); }
      var follow = clamp(topPage, gg.top0, gg.top0 + (maxStart - gg.lo) * gg.ppm);
      gg.el.style.transform = 'translate3d(' + clamp((gg.x - gg.x0) * 0.2, -12, 12) + 'px,' + (follow - base) + 'px,0)';
      gg.ghost.style.transform = 'translate3d(0,' + ((s - gg.s0) * gg.ppm) + 'px,0)';
      snapped = s;
      text = span(s, s + dur);
      small = s === gg.s0 ? 'same time' : 'was ' + clock12(gg.s0);
    }
    gg.snapped = snapped;
    var w = label.firstChild, sm = label.lastChild;
    if (w.textContent !== text) w.textContent = text;
    if (sm.textContent !== small) sm.textContent = small;
    if (!gg.lw) { gg.lw = label.offsetWidth; gg.lh = label.offsetHeight; }       // measured once: the label's width is fixed (min-width), its height never changes
    var x = clamp(gg.x - gg.lw / 2, 8, window.innerWidth - gg.lw - 8), y = gg.y - gg.lh - 64;
    if (y < 8) y = gg.y + 56;
    label.style.transform = 'translate3d(' + x + 'px,' + y + 'px,0)';
  }

  // ---- let go ------------------------------------------------------------------------------------------------------------
  document.addEventListener('pointerup', function (e) {
    if (!gg || e.pointerId !== gg.id) return;
    clearTimeout(gg.timer);
    cancelAnimationFrame(gg.raf || 0);
    var g = gg;
    gg = null;
    if (g.mode === 'wait') { if (CZ.tap) CZ.tap(g.el, e); return; }        // a tap: the click that follows opens the block (two taps on a title edit it: day_menu.js)
    CZ.guard(300, g.el);
    if (!g.moved && CZ.hold) {                                              // held (by the edge too) and let go without moving: nothing changes, it gets its menu (day_menu.js)
      g.el.style.transform = '';
      if (g.resize) { g.el.style.height = ''; endZoom(); }
      unhold(g);
      CZ.hold(g.el);
      return;
    }
    g.y = e.clientY;
    g.x = e.clientX;
    paint(g);
    release(g);
  });

  function unhold(g) {
    CZ.held = false;
    g.el.classList.remove('is-held', 'is-resizing', 'is-moving');
    g.g.classList.remove('is-editing-time');
    if (g.ghost && g.ghost.parentNode) g.ghost.parentNode.removeChild(g.ghost);
    dropLabel();
  }
  function restore(g) {                       // a gesture that did not finish: the block as it was
    g.el.style.transform = '';
    g.el.style.height = '';
    endZoom();
  }

  function release(g) {
    var changed = g.resize ? g.cur !== g.e0 : g.cur !== g.s0;
    if (g.resize) releaseResize(g, changed); else releaseMove(g, changed);
  }

  // Move: the block lands in its slot (a FLIP: its place is changed at once, and it travels the last bit), then the change is saved.
  function releaseMove(g, changed) {
    var el = g.el, dur = g.e0 - g.s0;
    var from = el.getBoundingClientRect();
    unholdSoon(g);
    el.style.transform = '';
    if (!changed) { land(el, from, g, function () { busy = false; }); return; }
    var s = g.cur;
    el.style.setProperty('--s', s - g.lo);
    el.dataset.s = s;
    el.dataset.e = s + dur;
    setWhen(el, s, s + dur);
    land(el, from, g, function () { save(g, { start: s, end: s + dur }, { s: g.s0, e: g.e0 }); });
  }

  // Resize: the grid eases back to normal while the block keeps the length it was given.
  function releaseResize(g, changed) {
    var el = g.el, e = g.cur;
    if (changed) {
      el.dataset.e = e;
      el.style.setProperty('--l', e - g.s0);
      setWhen(el, g.s0, e);
    }
    unholdSoon(g);
    dropLabel();
    endZoom(function () {
      el.style.height = '';
      if (changed) save(g, { start: g.s0, end: e }, { s: g.s0, e: g.e0 }); else busy = false;
    });
  }

  function unholdSoon(g) {                    // the lifted look goes at once; the label and the ghost stay until the block has landed
    CZ.held = false;
    g.el.classList.remove('is-held', 'is-resizing');
    g.g.classList.remove('is-editing-time');
    busy = true;
  }
  function setWhen(el, s, e) {
    var w = el.querySelector('.cz-gb-when');
    if (w) w.textContent = span(s, e);
  }
  // FLIP: the block's real place has changed; draw it where it was, then let it travel.
  function land(el, from, g, then) {
    var to = el.getBoundingClientRect();
    var dy = from.top - to.top;
    if (CZ.reduced.matches || (Math.abs(dy) < 1 && Math.abs(from.height - to.height) < 1)) { finishLand(g, then); return; }
    el.style.transform = 'translate3d(0,' + dy + 'px,0)';
    void el.offsetHeight;                      // one deliberate read, after all the writes: the starting place is now the one the transition leaves from
    el.classList.add('is-landing');
    el.style.transform = '';
    var ended = false, end = function () { if (ended) return; ended = true; el.classList.remove('is-landing'); finishLand(g, then); };
    el.addEventListener('transitionend', end, { once: true });
    setTimeout(end, (window.GA && GA.motion ? GA.motion.t('settle') : 280) + 60);
  }
  function finishLand(g, then) {
    if (g.ghost && g.ghost.parentNode) g.ghost.parentNode.removeChild(g.ghost);
    dropLabel();
    if (then) then();
  }
  // ---- saving, the toast and Undo -----------------------------------------------------------------------------------------
  function save(g, fields, old) {
    var el = g.el;
    var body = CZ.tripBody(Object.assign({ op: 'edit', act: el.dataset.act, next: CZ.here() }, fields));
    return CZ.post('/trip/canvas/plan', body).then(function (res) {
      busy = false;
      if (res.toast) CZ.showToast(res.toast, res.undo ? function () { undo(res.undo); } : null);
      return CZ.quiet();
    }, function (err) {
      busy = false;
      if (old && el.isConnected) {            // refused or never answered: the block goes back where it was, even if the refresh below cannot be fetched
        var lo = +el.closest('#cz-grid').dataset.lo;
        el.style.setProperty('--s', old.s - lo);
        el.style.setProperty('--l', old.e - old.s);
        el.dataset.s = old.s;
        el.dataset.e = old.e;
        setWhen(el, old.s, old.e);
      }
      CZ.showToast(err && err.soft ? err.soft : 'Could not save that. Check your connection.');
      return CZ.quiet();                      // the page shows what is really saved
    });
  }

  function undo(snap) {
    var before = rects();
    CZ.post('/trip/canvas/plan', CZ.tripBody({ op: 'undo', undo: JSON.stringify(snap), next: CZ.here() })).then(function (res) {
      flipOnSwap = before;
      return CZ.quiet().then(function () { CZ.showToast(res.toast || 'Put back'); });
    }, function (err) { CZ.showToast(err && err.soft ? err.soft : 'Could not undo that.'); });
  }

  // A change that did not come from a drag (the menu's Earlier, Later, Shorter, Longer): the same landing, the same save.
  CZ.setTimes = function (el, s, e) {
    var g = el.closest('#cz-grid');
    if (!g || busy) return false;
    var from = el.getBoundingClientRect(), old = { s: +el.dataset.s, e: +el.dataset.e };
    busy = true;
    el.style.setProperty('--s', s - +g.dataset.lo);
    el.style.setProperty('--l', e - s);
    el.dataset.s = s;
    el.dataset.e = e;
    setWhen(el, s, e);
    land(el, from, {}, function () { save({ el: el }, { start: s, end: e }, old); });
    return true;
  };
  CZ.undo = undo;
  CZ.span = span;      // "12:30 – 1:30 PM", for the block a new plan starts as (day_new.js)

  // A refresh after a write replaces the page: the block that had the keyboard's focus gets it back.
  CZ.beforeQuiet = function () {
    var f = document.activeElement, b = f && f.closest && stage.contains(f) ? f.closest('.cz-gb') : null;
    if (!b) return null;
    var act = b.dataset.act, button = f.classList.contains('cz-gb-menubtn');
    return function () {
      var n = stage.querySelector('.cz-gb[data-act="' + act + '"]');
      n = n && (button ? n.querySelector('.cz-gb-menubtn') : n);
      if (n) { try { n.focus({ preventScroll: true }); } catch (e) { n.focus(); } }
    };
  };

  // After an Undo the blocks travel from where they were to where they are, so the change reads as a move and not as a flicker.
  var flipOnSwap = null;
  function rects() {
    var out = {};
    stage.querySelectorAll('.cz-gb[data-act]').forEach(function (b) { var r = b.getBoundingClientRect(); out[b.dataset.act] = { top: r.top, height: r.height }; });
    return out;
  }
  function flipAll(before) {
    if (CZ.reduced.matches) return;
    stage.querySelectorAll('.cz-gb[data-act]').forEach(function (b) {
      var o = before[b.dataset.act];
      if (!o) return;
      var r = b.getBoundingClientRect();
      if (Math.abs(o.top - r.top) < 1 && Math.abs(o.height - r.height) < 1) return;
      b.style.transform = 'translate3d(0,' + (o.top - r.top) + 'px,0)';
      b.style.height = o.height + 'px';
    });
    void stage.offsetHeight;
    stage.querySelectorAll('.cz-gb[data-act]').forEach(function (b) {
      if (!b.style.transform && !b.style.height) return;
      b.classList.add('is-landing');
      var h = b.style.height;
      b.style.transform = '';
      b.style.height = '';
      setTimeout(function () { b.classList.remove('is-landing'); }, (window.GA && GA.motion ? GA.motion.t('settle') : 280) + 60);
    });
  }

  // ---- scroll to the day's first plan (or now), and keep the now line moving ---------------------------------------------------
  function scrollToPlans() {
    var g = grid();
    if (!g) return;
    var target = g.querySelector('#cz-nowline') || g.querySelector('.cz-gb');
    if (!target) return;
    var r = target.getBoundingClientRect();
    if (r.top > window.innerHeight * 0.6 || r.bottom < 0) window.scrollTo(0, Math.max(0, window.scrollY + r.top - window.innerHeight * 0.32));
  }
  function startNow() {
    clearInterval(tick);
    var line = stage.querySelector('#cz-nowline'), g = grid();
    if (!line || !g) return;
    var base = +line.dataset.m, lo = +g.dataset.lo, t0 = Date.now();
    tick = setInterval(function () {
      var m = base + Math.floor((Date.now() - t0) / 60000);
      line.style.setProperty('--s', m - lo);
    }, 20000);
  }

  stage.addEventListener('cz:swap', function (e) {
    startNow();
    if (flipOnSwap && e.detail && e.detail.quiet) { var b = flipOnSwap; flipOnSwap = null; flipAll(b); }
  });
  CZ.afterScroll = scrollToPlans;      // trip_canvas.js calls it right after a level it pushed or replaced is scrolled to the top
  startNow();
  if (window.scrollY < 4) scrollToPlans();
})();
