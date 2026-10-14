// The day as a time grid (F-097): hold a block about 350 ms to lift it and drag it to a new time (15-minute snap, the time shown under the finger, the page scrolls at the
// top and bottom edge); hold its bottom edge to change its length, while the grid zooms in around the finger (about 2.5x, 5-minute snap) and eases back on release. Each
// change saves through the calendar's own rules (POST /trip/canvas/plan) and shows a toast with Undo. Editors only: a viewer's page has no data-edit and no gestures.
// Needs canvas_core.js, which loads first and shares its toast, writes, quiet refresh and the flick (a held block never flicks, CZ.held).
//
// Smoothness: nothing here reads layout inside a frame. The geometry is read once when a block is lifted; after that each frame writes a `transform` (a move), one height
// on one absolutely positioned block (a resize) and the zoom's scale, all from the latest pointer position, one rAF at a time. The zoom is a scaleY on one layer
// (.cz-g-zoom) with its origin on the edge being dragged; --zk carries the same number to what has words in it, which scales back by 1/--zk, so text keeps its size.
// Reduced motion: no zoom, no easing; moves and resizes keep the 15-minute snap.
//
// F-110: no handle at rest. A block that was held and let go stays SELECTED (it keeps its lift, its hold menu opens as before) and shows two small round knobs, as Apple Calendar does
// while an event is being edited: the top one changes the start, the bottom one the end, each with the same zoom (the start edge is a resize of its own: same route, same rules).
// While a block is selected a touch on a knob drags that edge at once, a touch on its body (past a few pixels) moves it at once, and a touch anywhere else puts the knobs away and
// scrolls as usual (a selected block itself does not scroll under a finger: touch-action none, so a drag on it is never taken for a scroll). It stays selected through the save.
//
// F-098 adds the hold menu, the wiggle, rename in place and delete (further down).
//
// F-144: a mouse on the desktop day (from 1020px) needs no hold. Press a plan and drag past a few pixels to move it (a click still opens it in the panel); the knob at its foot (day_mouse.js
// shows it on hover) resizes at once. Both snap like the phone, with no zoom (a mouse is exact), and save through the same path with the same Undo. The grid there scrolls inside its own
// card, so the edge scroll, the geometry and the label read the card's scroll (`scrollY()`), not the window's; a wheel turned during a hold repaints, so the plan stays under the pointer.
// Escape drops a plan in the air back where it was.
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var stage = CZ.stage;
  var root = document.documentElement;
  var HOLD = 350, SLOP = 10, TURN = 4, DRAG = 6;
  var GRAIN = 15, FINE = 5, ZOOM = 2.5, MIN_LEN = 15, DAY_END = 22 * 60;
  var ptrs = {};          // fingers down: two fingers are never a gesture of ours
  var gg = null;          // the gesture in progress
  var Z = { k: 1, raf: 0, grid: null, zoom: null };      // the zoom, which outlives the gesture while it eases back
  var label = null;
  var busy = false;       // a block is landing: no new gesture until it has
  var tick = 0;
  var DESK = window.matchMedia('(min-width: 1020px) and (not (display-mode: standalone))');      // the same query as day_dock.css

  // F-144: a mouse on the desktop day, and the card that scrolls there. A touch screen of any size keeps the phone's gestures.
  function mouseOn(e) { return !!e && e.pointerType === 'mouse' && DESK.matches; }
  function box() { return DESK.matches ? stage.querySelector('.cz-view[data-day] .cz-day-body') : null; }
  function scrollY() { var b = box(); return b ? b.scrollTop : window.scrollY; }
  CZ.mouseOn = mouseOn;
  CZ.dayBox = box;
  CZ.DRAG = DRAG;      // the distance a mouse travels before a press is a drag (day_new.js draws with it too)

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
    var knob = sel && e.target.closest ? e.target.closest('.cz-g-knob') : null;
    if (knob && sel.layer.contains(knob)) {                                                  // F-110: a knob of the selected block: that edge is dragged at once, with the zoom
      gg = { id: e.pointerId, el: sel.el, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, mode: 'wait', resize: true, edge: knob.classList.contains('is-top') ? 'start' : 'end', knob: knob, moved: false, dirty: false };
      lift();
      return;
    }
    var mouse = mouseOn(e), tk = mouse && e.target.closest ? e.target.closest('.cz-g-tknob') : null;
    if (tk && tk.closest('.cz-g-tools') && tk.closest('.cz-g-tools').block) {                  // F-144: the hover knob at a plan's foot: its end is dragged at once, with the mouse
      gg = { id: e.pointerId, el: tk.closest('.cz-g-tools').block, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, mode: 'wait', resize: true, edge: 'end', knob: tk, mouse: true, moved: false, dirty: false };
      e.preventDefault();
      lift();
      return;
    }
    var el = e.target.closest ? e.target.closest('.cz-gb') : null;
    if (!el || !stage.contains(el) || e.target.closest('input, textarea, .cz-g-tools')) return;
    if (mouse) {                                                                              // F-144: press and drag moves it; a click opens it (the panel), as before
      gg = { id: e.pointerId, el: el, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, mode: 'wait', resize: false, edge: 'end', mouse: true, moved: false, dirty: false };
      return;
    }
    var r = el.getBoundingClientRect();
    var edge = Math.min(clamp(r.height * 0.4, rem() * 0.75, rem() * 1.75), r.height * 0.45);        // the bottom edge: a hand's width of the block's last stretch (never more than its lower half)
    var own = !!sel && sel.el === el && !el.classList.contains('is-tall');                                                       // F-110: a touch on the selected block's body moves it as soon as it travels (no second hold)
    gg = { id: e.pointerId, el: el, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, mode: 'wait', resize: !own && e.clientY > r.bottom - edge, edge: 'end', own: own, moved: false, dirty: false };
    if (own) CZ.held = true;                                                                  // so a sideways drag is never taken for the flick between days
    gg.timer = setTimeout(lift, HOLD);
  });

  document.addEventListener('pointermove', function (e) {
    if (!gg || e.pointerId !== gg.id) return;
    gg.x = e.clientX;
    gg.y = e.clientY;
    if (gg.mode === 'wait') {
      var far = Math.hypot(gg.x - gg.x0, gg.y - gg.y0);
      if (gg.mouse) { if (far > DRAG) lift(); return; }                                       // F-144: no hold with a mouse; a small wobble is still a click
      if (gg.own && far > DRAG) { clearTimeout(gg.timer); lift(); return; }
      if (far > SLOP) { clearTimeout(gg.timer); if (gg.own) CZ.held = false; gg = null; }       // it is a scroll, or the flick between days: not ours
      return;
    }
    if (gg.mouse && !e.buttons) { cancel(); return; }                                       // the button was let go out of sight (no pointerup came): the drag is over
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
    if (g.mode !== 'wait') { restore(g); unhold(g); wake(); } else if (g.own) CZ.held = false;
  }
  document.addEventListener('pointercancel', function (e) { if (gg && e.pointerId === gg.id) cancel(); });
  window.addEventListener('blur', function () { if (gg && gg.mouse) cancel(); });                // the window lost focus mid-drag: put the block back

  // ---- selected: two knobs beside the block (F-110) -----------------------------------------------------------------------------
  // The knobs live in a layer next to the block, the size of the block (the block itself clips its words), so they straddle its edges. The layer follows the block's size (a
  // ResizeObserver: a short block opens out while its menu is open) and is told where the block is while an edge is dragged.
  var sel = null;       // { el, act, layer, ro }
  function ms(name) { return window.GA && GA.motion ? GA.motion.t(name) : 160; }
  function place() {
    if (!sel || !sel.el.isConnected || !sel.layer.isConnected) return;
    var s = sel.layer.style, el = sel.el;
    s.left = el.offsetLeft + 'px';
    s.top = el.offsetTop + 'px';
    s.width = el.offsetWidth + 'px';
    s.height = el.offsetHeight + 'px';
    el.classList.toggle('is-tall', el.offsetHeight > window.innerHeight * 0.6);      // resized past (or back under) 60% of the screen while selected: touch-action follows
  }
  function wake() {                                  // a gesture is over: the knobs are back on the block's real edges
    if (!sel || !sel.layer.isConnected) return;
    place();
    sel.layer.classList.remove('is-away');
  }
  function select(el, quiet) {
    if (!el || !el.isConnected) return;
    if (sel && sel.el === el && sel.layer.isConnected) return;
    clearSel(true);
    var layer = document.createElement('div');
    layer.className = 'cz-g-knobs';
    layer.setAttribute('aria-hidden', 'true');
    layer.style.setProperty('--accent', getComputedStyle(el).getPropertyValue('--accent'));
    ['top', 'bottom'].forEach(function (w) {
      var k = document.createElement('div');
      k.className = 'cz-g-knob cz-cs is-' + w;
      k.appendChild(document.createElement('i'));
      layer.appendChild(k);
    });
    el.parentNode.insertBefore(layer, el.nextSibling);
    el.classList.add('is-selected');
    el.classList.toggle('is-tall', el.offsetHeight > window.innerHeight * 0.6);      // a block that fills the screen must still let a flick scroll the day
    sel = { el: el, act: el.dataset.act, layer: layer, ro: null };
    place();
    if (window.ResizeObserver) { sel.ro = new ResizeObserver(place); sel.ro.observe(el); }
    if (!quiet && window.GA && GA.motion) layer.querySelectorAll('i').forEach(function (i) { GA.motion.run(i, [{ transform: 'scale(0.4)', opacity: 0 }, { transform: 'none', opacity: 1 }], { t: 'settle', ease: 'spring' }); });
  }
  function clearSel(now) {
    if (!sel) return;
    var s = sel;
    sel = null;
    if (s.ro) s.ro.disconnect();
    if (s.el.isConnected) s.el.classList.remove('is-selected', 'is-tall');
    var gone = function () { if (s.layer.parentNode) s.layer.parentNode.removeChild(s.layer); };
    if (now || CZ.reduced.matches || !s.layer.isConnected) gone();
    else { s.layer.classList.add('is-away'); s.layer.style.pointerEvents = 'none'; setTimeout(gone, ms('quick')); }
  }
  function deselect() { clearSel(false); }
  var swallow = null;      // the click that ends a tap which only deselected: it is registered here, before the card's own click handler (day_card.js loads after this file)
  document.addEventListener('click', function (e) {
    if (swallow && Date.now() < swallow.until && swallow.el.contains(e.target)) { e.preventDefault(); e.stopImmediatePropagation(); }
    swallow = null;
  }, true);
  CZ.deselect = deselect;
  document.addEventListener('pointerdown', function (e) {        // a touch anywhere else puts the knobs away (and does what it would have done: scrolls, taps, holds)
    swallow = null;                                              // (a new touch is a new tap: the last one's click, if it never came, is not waited for)
    if (!sel) return;
    var t = e.target;
    if (t.closest && (t.closest('.cz-g-knobs, .cz-menu, .ga-toast') || sel.el.contains(t))) return;
    deselect();
  }, true);
  document.addEventListener('keydown', function (e) {            // Escape puts the knobs away (the menu's own Escape comes first when it is open)
    if (!sel || e.key !== 'Escape' || CZ.menuOpen || (e.target.closest && e.target.closest('input, textarea'))) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    deselect();
  }, true);

  document.addEventListener('keydown', function (e) {            // F-144: Escape drops a plan held in the air (before the panel's and the canvas's Escape)
    if (!gg || gg.mode !== 'held' || e.key !== 'Escape') return;
    e.preventDefault();
    e.stopImmediatePropagation();
    cancel();
  }, true);
  document.addEventListener('scroll', function () { if (gg && gg.mode === 'held') gg.dirty = true; }, true);      // F-144: a wheel turned during a hold: the plan is painted again under the pointer

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
    var sy = scrollY(), zr = zoom.getBoundingClientRect(), br = el.getBoundingClientRect();
    gg.ppm = zoom.offsetHeight / (gg.hi - gg.lo);                        // pixels per minute
    gg.top0 = zr.top + sy;                                                // the layer's top, in page coordinates
    gg.left = el.offsetLeft;
    gg.width = el.offsetWidth;
    gg.grab = gg.y0 + sy - (gg.top0 + (gg.s0 - gg.lo) * gg.ppm);        // where on the block the finger took it (move)
    var edgeAt = gg.edge === 'start' ? gg.s0 : gg.e0;                    // the edge a resize drags: the end (the bottom edge), or the start (the top knob, F-110)
    gg.off = gg.y0 + sy - (gg.top0 + (edgeAt - gg.lo) * gg.ppm);        // and how far from it the finger took hold (resize)
    gg.cur = gg.resize ? edgeAt : gg.s0;
    gg.h0 = br.height;
    gg.minh = rem() * 2.75;                                              // a block is never drawn shorter than a finger
    if (sel && sel.el === el) { if (gg.knob) gg.knob.classList.add('is-on'); else sel.layer.classList.add('is-away'); }
    var tabs = document.querySelector('.ph-tabs');
    gg.bottom = (tabs && getComputedStyle(tabs).display !== 'none' ? tabs.getBoundingClientRect().top : window.innerHeight) - 72;      // the tab bar is not part of the page to scroll under
    gg.edgeTop = 88; gg.zoneTop = 88; gg.edgeBot = gg.bottom; gg.zoneBot = 72; gg.box = null;
    var card = gg.mouse ? box() : null;                                  // F-144: on the desktop the grid card scrolls, and its edges are where the scroll starts
    if (card) { var cr = card.getBoundingClientRect(), zone = rem() * 3; gg.box = card; gg.edgeTop = cr.top + zone; gg.zoneTop = zone; gg.edgeBot = cr.bottom - zone; gg.zoneBot = zone; }
    if (gg.mouse && !gg.knob) gg.moved = true;                           // (it was lifted by travelling: letting go is a drop, never a hold menu)
    if (gg.knob) gg.knob.classList.add('is-on');
    el.classList.add(gg.resize ? 'is-resizing' : 'is-held');
    g.classList.add('is-editing-time');
    buzz(14);
    makeLabel();
    gg.chips = !!(gg.mouse && !gg.resize && CZ.chipDrop && /^a\d/.test(el.dataset.act || '') && CZ.chipDrop.begin());      // F-151: a plan (not a booking) held with the mouse can be dropped on a day chip
    if (gg.resize) { gg.oy = ((gg.edge === 'start' ? gg.s0 : gg.e0) - gg.lo) * gg.ppm; gg.bottomPage = gg.top0 + gg.oy; if (!gg.mouse) startZoom(); } else makeGhost();      // (a mouse is exact: no zoom)
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
    var top = gg.edgeTop, bottom = gg.edgeBot;
    var dy = 0, speed = zoomed ? 7 : 11;
    if (gg.y < top) dy = -Math.ceil(Math.min(1, (top - gg.y) / gg.zoneTop) * speed) - 1;
    else if (gg.y > bottom) dy = Math.ceil(Math.min(1, (gg.y - bottom) / gg.zoneBot) * speed) + 1;
    if (gg.chips && CZ.chipDrop.tick(gg.x, gg.y)) gg.dirty = true;       // F-151: held near an end of the day chips, they scroll
    if (dy && gg.chips && CZ.chipDrop.inBand(gg.y)) dy = 0;               // (over the chips the grid card below stays still)
    if (dy) { if (gg.box) gg.box.scrollBy(0, dy); else window.scrollBy(0, dy); gg.dirty = true; }
    if (gg.dirty) { gg.dirty = false; paint(gg); }
    gg.raf = requestAnimationFrame(frame);
  }

  function paint(gg) {
    var sy = scrollY(), fy = gg.y + sy;
    var snapped, text, small;
    if (gg.resize) {
      var k = Z.k, grain = gg.zoomed && k > 1.5 ? FINE : GRAIN;
      var eu = gg.oy + (fy - gg.off - gg.bottomPage) / k;                  // the edge, in the layer's own pixels
      var at = gg.lo + eu / gg.ppm;
      if (gg.edge === 'start') {                                           // the top knob: the start moves, the end stays (never within 15 minutes of it)
        var s0 = clamp(Math.round(at / grain) * grain, gg.lo, gg.e0 - MIN_LEN);
        if (s0 !== gg.cur) { buzz(4); gg.cur = s0; setWhen(gg.el, s0, gg.e0); }
        gg.el.style.top = ((s0 - gg.lo) * gg.ppm) + 'px';
        gg.el.style.height = ((gg.e0 - s0) * gg.ppm) + 'px';
        snapped = s0;
        text = span(s0, gg.e0);
        small = lenText(gg.e0 - s0);
      } else {
        var e = clamp(Math.round(at / grain) * grain, gg.s0 + MIN_LEN, Math.min(gg.hi, DAY_END));
        if (e !== gg.cur) { buzz(4); gg.cur = e; setWhen(gg.el, gg.s0, e); }
        gg.el.style.height = ((e - gg.s0) * gg.ppm) + 'px';
        snapped = e;
        text = span(gg.s0, e);
        small = lenText(e - gg.s0);
      }
      if (sel && sel.el === gg.el) {                                       // the knobs follow the block's edges (their layer is the block's own box)
        var top = (((gg.edge === 'start' ? gg.cur : gg.s0) - gg.lo) * gg.ppm), h = ((gg.edge === 'start' ? gg.e0 - gg.cur : gg.cur - gg.s0) * gg.ppm);
        sel.layer.style.top = top + 'px';
        sel.layer.style.height = Math.max(h, gg.minh) + 'px';
      }
    } else {
      var dur = gg.e0 - gg.s0, maxStart = Math.max(gg.lo, Math.min(gg.hi, DAY_END) - dur);
      var topPage = fy - gg.grab, base = gg.top0 + (gg.s0 - gg.lo) * gg.ppm;
      var s = gg.chips && CZ.chipDrop.inBand(gg.y) ? gg.s0 : clamp(Math.round((gg.lo + (topPage - gg.top0) / gg.ppm) / GRAIN) * GRAIN, gg.lo, maxStart);      // (F-151: over the day chips a plan is not being moved in time: dropped on no chip it stays)
      if (s !== gg.cur) { buzz(4); gg.cur = s; setWhen(gg.el, s, s + dur); }
      var follow = clamp(topPage, gg.top0, gg.top0 + (maxStart - gg.lo) * gg.ppm);
      gg.el.style.transform = 'translate3d(' + clamp((gg.x - gg.x0) * 0.2, -12, 12) + 'px,' + (follow - base) + 'px,0)';
      gg.ghost.style.transform = 'translate3d(0,' + ((s - gg.s0) * gg.ppm) + 'px,0)';
      snapped = s;
      text = span(s, s + dur);
      small = s === gg.s0 ? 'same time' : 'was ' + clock12(gg.s0);
    }
    gg.snapped = snapped;
    gg.chip = gg.chips ? CZ.chipDrop.over(gg.x, gg.y) : null;           // F-151: the day chip under the pointer that will take the plan
    if (gg.chip) { text = 'Move to ' + gg.chip.dataset.moveLabel; small = 'same time'; }
    label.style.visibility = gg.chip ? 'hidden' : '';                  // (the coral ring says it; the label must not sit over the header)
    var w = label.firstChild, sm = label.lastChild;
    if (w.textContent !== text) w.textContent = text;
    if (sm.textContent !== small) sm.textContent = small;
    if (!gg.lw) { gg.lw = label.offsetWidth; gg.lh = label.offsetHeight; }       // measured once: the label's width is fixed (min-width), its height never changes
    var x = clamp(gg.x - gg.lw / 2, 8, window.innerWidth - gg.lw - 8), y = gg.y - gg.lh - (gg.mouse ? rem() * 1.8 : 64);      // (a pointer is small: the label sits close above it)
    if (y < 8) y = gg.y + (gg.mouse ? rem() * 2.3 : 56);
    label.style.transform = 'translate3d(' + x + 'px,' + y + 'px,0)';
  }

  // ---- let go ------------------------------------------------------------------------------------------------------------
  document.addEventListener('pointerup', function (e) {
    if (!gg || e.pointerId !== gg.id) return;
    clearTimeout(gg.timer);
    cancelAnimationFrame(gg.raf || 0);
    var g = gg;
    gg = null;
    if (g.mode === 'wait') {                                               // a tap: the click that follows opens the block (two taps on a title edit it: day_menu.js)
      if (g.own) CZ.held = false;
      if (sel && sel.el === g.el) {                                        // a tap on the selected block only puts the knobs away: the click it makes opens nothing
        deselect();
        swallow = { el: g.el, until: Date.now() + 600 };
        return;
      }
      if (CZ.tap) CZ.tap(g.el, e);
      return;
    }
    CZ.guard(300, g.el);
    if (!g.moved && g.knob) {                                              // a knob touched and let go without moving: nothing changes, and it is no hold
      g.el.style.height = ''; g.el.style.top = '';
      unhold(g);
      endZoom(wake);
      return;
    }
    if (!g.moved && CZ.hold) {                                              // held (by the edge too) and let go without moving: nothing changes, it gets its menu (day_menu.js), and stays selected with its knobs
      g.el.style.transform = '';
      if (g.resize) { g.el.style.height = ''; endZoom(); }
      unhold(g);
      select(g.el);
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
    if (g.knob) g.knob.classList.remove('is-on');
    g.el.classList.remove('is-held', 'is-resizing', 'is-moving');
    g.g.classList.remove('is-editing-time');
    if (g.chips && CZ.chipDrop) CZ.chipDrop.end();
    if (g.ghost && g.ghost.parentNode) g.ghost.parentNode.removeChild(g.ghost);
    dropLabel();
  }
  function restore(g) {                       // a gesture that did not finish: the block as it was
    g.el.style.transform = '';
    g.el.style.height = '';
    g.el.style.top = '';
    endZoom();
  }

  function release(g) {
    var changed = g.resize ? g.cur !== (g.edge === 'start' ? g.s0 : g.e0) : g.cur !== g.s0;
    if (g.chip) releaseToDay(g);
    else if (g.resize) releaseResize(g, changed); else releaseMove(g, changed);
  }

  // Move: the block lands in its slot (a FLIP: its place is changed at once, and it travels the last bit), then the change is saved.
  function releaseMove(g, changed) {
    var el = g.el, dur = g.e0 - g.s0;
    var from = el.getBoundingClientRect();      // where the finger left it (lifted: a little bigger)
    unholdSoon(g);
    el.style.transform = '';
    var s = g.cur;
    if (changed) {
      el.style.setProperty('--s', s - g.lo);
      el.dataset.s = s;
      el.dataset.e = s + dur;
      setWhen(el, s, s + dur);
    }
    var landed = land(el, from, g);
    if (!changed) { landed.then(function () { busy = false; }); return; }
    save(g, { start: s, end: s + dur }, { s: g.s0, e: g.e0 }, landed);      // saved while it travels; the toast and the refresh wait until it has landed
  }

  // F-151: dropped on a day chip. The plan keeps its times and goes to that day: it shrinks into the chip while the write (the canvas's own, with a `day`) is made, then the toast has its
  // Undo and the day is brought up to date in place, the plan gone from it. A plan open in the panel would be left showing a plan that is not on this day: the panel goes back to Up next.
  function releaseToDay(g) {
    var el = g.el, chip = g.chip, to = chip.dataset.moveDay, act = el.dataset.act;
    var from = el.getBoundingClientRect(), cr = chip.getBoundingClientRect();
    var dx = cr.left + cr.width / 2 - (from.left + from.width / 2), dy = cr.top + cr.height / 2 - (from.top + from.height / 2);
    var cur = el.style.transform || 'none', pane = document.querySelector('#cz-dock .cz-pp:not(.is-leaving)');
    unholdSoon(g);
    dropLabel();
    if (g.ghost && g.ghost.parentNode) g.ghost.parentNode.removeChild(g.ghost);
    var gone = window.GA && GA.motion ? GA.motion.run(el, [{ transform: cur, opacity: 1 }, { transform: 'translate(' + dx + 'px,' + dy + 'px) ' + (cur === 'none' ? '' : cur) + ' scale(0.2)', opacity: 0 }], { t: 'settle', ease: 'calm', fill: 'forwards' }) : Promise.resolve();
    var body = CZ.tripBody({ op: 'edit', act: act, day: to, next: CZ.here() });
    CZ.post('/trip/canvas/plan', body).then(function (res) {
      return gone.then(function () {
        busy = false;
        el.style.opacity = '0';
        if (pane && pane.dataset.act === act && window.Dock) Dock.close();
        if (res.toast) CZ.showToast(res.toast, res.undo ? function () { undo(res.undo); } : null);
        return CZ.quiet();
      });
    }, function (err) {
      return gone.then(function () {                    // refused or never answered: the plan comes back where it was
        busy = false;
        el.getAnimations().forEach(function (a) { a.cancel(); });
        el.style.transform = '';
        CZ.showToast(err && err.soft ? err.soft : 'Could not save that. Check your connection.');
        return CZ.quiet();
      });
    });
  }

  // Resize: the grid eases back to normal while the block keeps the length it was given.
  function releaseResize(g, changed) {
    var el = g.el, start = g.edge === 'start', s = start ? g.cur : g.s0, e = start ? g.e0 : g.cur;
    if (changed) {
      el.dataset.s = s;
      el.dataset.e = e;
      el.style.setProperty('--s', s - g.lo);
      el.style.setProperty('--l', e - s);
      setWhen(el, s, e);
    }
    unholdSoon(g);
    dropLabel();
    endZoom(function () {
      el.style.height = '';
      el.style.top = '';
      wake();
      if (changed) save(g, { start: s, end: e }, { s: g.s0, e: g.e0 }); else busy = false;
    });
  }

  function unholdSoon(g) {                    // the lifted look goes at once; the label and the ghost stay until the block has landed
    CZ.held = false;
    if (g.knob) g.knob.classList.remove('is-on');
    g.el.classList.remove('is-held', 'is-resizing');
    g.g.classList.remove('is-editing-time');
    if (g.chips && CZ.chipDrop) CZ.chipDrop.end();
    busy = true;
  }
  function setWhen(el, s, e) {
    var w = el.querySelector('.cz-gb-when');
    if (w) w.textContent = span(s, e);
  }
  // FLIP, one move (GA.motion.land): the block's real place has changed; it is drawn where the eye saw it (`from`) and travels to its place with the spring and a gentle overshoot. The
  // promise resolves when it has landed; the ghost, the label and the knobs wait for that. Nothing re-draws it after: the refreshed day takes over the same spot (see CZ.snap).
  var landing = 0;
  function land(el, from, g) {
    var done = function () { landing--; el.classList.remove('is-landing'); if (g.ghost && g.ghost.parentNode) g.ghost.parentNode.removeChild(g.ghost); dropLabel(); wake(); };
    landing++;
    el.classList.add('is-landing');      // (its lift folds out with the move: no second ease on `scale`)
    var p = window.GA && GA.motion ? GA.motion.land(el, from) : Promise.resolve();
    return p.then(done, done);
  }
  CZ.landing = function () { return landing > 0; };
  // ---- saving, the toast and Undo -----------------------------------------------------------------------------------------
  // `landed` is the block's own move (it is saved while it travels): the toast glides in and the day is refreshed only once the block is at rest, so nothing is drawn over a move in progress.
  function save(g, fields, old, landed) {
    var el = g.el, wait = landed || Promise.resolve();
    var body = CZ.tripBody(Object.assign({ op: 'edit', act: el.dataset.act, next: CZ.here() }, fields));
    return CZ.post('/trip/canvas/plan', body).then(function (res) {
      return wait.then(function () {
        busy = false;
        if (res.toast) CZ.showToast(res.toast, res.undo ? function () { undo(res.undo); } : null);
        return CZ.quiet();
      });
    }, function (err) {
      return wait.then(function () {
        var back = Promise.resolve();
        if (old && el.isConnected) {            // refused or never answered: the block goes back where it was (it travels there), even if the refresh below cannot be fetched
          var lo = +el.closest('#cz-grid').dataset.lo, from = el.getBoundingClientRect();
          el.style.setProperty('--s', old.s - lo);
          el.style.setProperty('--l', old.e - old.s);
          el.dataset.s = old.s;
          el.dataset.e = old.e;
          setWhen(el, old.s, old.e);
          back = land(el, from, {});
        }
        return back.then(function () {
          busy = false;
          CZ.showToast(err && err.soft ? err.soft : 'Could not save that. Check your connection.');
          return CZ.quiet();                      // the page shows what is really saved
        });
      });
    });
  }

  function undo(snap) {
    CZ.post('/trip/canvas/plan', CZ.tripBody({ op: 'undo', undo: JSON.stringify(snap), next: CZ.here() })).then(function (res) {
      return CZ.quiet().then(function () { CZ.showToast(res.toast || 'Put back'); });      // (the blocks glide from where they were: CZ.snap)
    }, function (err) { CZ.showToast(err && err.soft ? err.soft : 'Could not undo that.'); });
  }

  // A change that did not come from a drag (the menu's Earlier, Later, Shorter, Longer): the same landing, the same save.
  CZ.setTimes = function (el, s, e) {
    var g = el.closest('#cz-grid');
    if (!g || busy) return false;
    var from = el.getBoundingClientRect(), old = { s: +el.dataset.s, e: +el.dataset.e };
    busy = true;
    if (sel && sel.el === el) sel.layer.classList.add('is-away');          // the knobs wait while the block travels
    el.style.setProperty('--s', s - +g.dataset.lo);
    el.style.setProperty('--l', e - s);
    el.dataset.s = s;
    el.dataset.e = e;
    setWhen(el, s, e);
    save({ el: el }, { start: s, end: e }, old, land(el, from, {}));
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

  // A refresh that follows a write (a drop, a nudge, an Undo, or someone else's change) re-draws the day, but the eye must not see it: every block is measured before the swap by its plan
  // (data-act) and, after it (and the scroll put back), drawn where it was and sent to where it is, with the same spring (GA.motion.land). A block that did not move does not move now; one that
  // did (an overlap changed, an Undo) glides. canvas_core.js calls this before a quiet swap and runs what it returns after.
  function wiggleOf(n) { var a = n && n.getAnimations ? n.getAnimations().filter(function (x) { return x.animationName === 'cz-wiggle'; })[0] : null; return a ? a.currentTime : null; }
  function arrived(n) {      // a re-drawn block (or its knobs) is born in the state the old one was in (lifted by its selection or its menu): the eases that would play from "plain" to that are over at once, nothing pops
    if (n && n.getAnimations) n.getAnimations().forEach(function (a) { if (a.transitionProperty !== undefined) a.finish(); });
  }
  function wiggleTo(n, at) {
    var a = at !== null && n && n.getAnimations ? n.getAnimations().filter(function (x) { return x.animationName === 'cz-wiggle'; })[0] : null;
    if (a) a.currentTime = at;
  }
  CZ.snap = function () {
    if (CZ.reduced.matches || !(window.GA && GA.motion)) return null;
    var before = {};
    stage.querySelectorAll('.cz-gb[data-act]').forEach(function (b) {
      var r = b.getBoundingClientRect();      // what the eye sees (a transform, the menu's wiggle, included), and where the block really is
      before[b.dataset.act] = { eye: { left: r.left, top: r.top, width: r.width, height: r.height }, top: b.offsetTop, left: b.offsetLeft, width: b.offsetWidth, height: b.offsetHeight, wiggle: [wiggleOf(b), wiggleOf(b.nextElementSibling)] };
    });
    return function () {
      stage.querySelectorAll('.cz-gb[data-act]').forEach(function (b) {
        var o = before[b.dataset.act];
        if (o) { arrived(b); arrived(b.nextElementSibling); wiggleTo(b, o.wiggle[0]); wiggleTo(b.nextElementSibling, o.wiggle[1]); }      // the wiggle of a block whose menu is open goes on from where it was, not from its start
        if (!o || (Math.abs(o.top - b.offsetTop) < 2 && Math.abs(o.left - b.offsetLeft) < 2 && Math.abs(o.width - b.offsetWidth) < 2 && Math.abs(o.height - b.offsetHeight) < 2)) return;      // it did not move (the wiggle only tilts it)
        landing++;      // (a refresh must not swap the day under a neighbour's glide either: CZ.landing)
        var over = function () { landing--; };
        GA.motion.land(b, o.eye).then(over, over);
      });
    };
  };

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
      var t = line.querySelector('.cz-now-t');      // F-140: the desktop's time pill follows the line
      if (t) t.textContent = ((Math.floor(m / 60) % 12) || 12) + ':' + ('0' + (m % 60)).slice(-2);
    }, 20000);
  }

  stage.addEventListener('cz:swap', function (e) {
    startNow();
    if (sel) {                                           // the page behind the knobs was replaced: after a save the same plan is still selected; going somewhere else puts the knobs away
      var act = sel.act, again = e.detail && e.detail.quiet ? stage.querySelector('.cz-gb[data-act="' + act + '"]') : null;
      clearSel(true);
      if (again && editing()) select(again, true);
    }
  });
  CZ.afterScroll = scrollToPlans;      // canvas_core.js calls it right after a level it pushed or replaced is scrolled to the top
  startNow();
  if (window.scrollY < 4) scrollToPlans();
})();
