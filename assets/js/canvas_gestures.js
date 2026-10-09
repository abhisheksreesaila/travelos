// The trip canvas, fingers (F-082, F-090; a module since F-128). Loaded after canvas_core.js and canvas_writes.js.
//   A flick left on a day is the next day, right the previous one (the day follows the finger a little).
//   Hold a step (about 350 ms) to lift it; a chip follows the finger, and the parts, the days across the top and the Set aside tray light up as drop targets; letting go
//   posts a move and brings the level up to date in place, with a toast that has Undo. A list chip held the same way is added to a part.
//   Swipe a step left for Done and Set aside; swipe right (or tap elsewhere) to put them away.
// Fingers are counted, so two fingers never start a flick or a drag, and the page's own pinch zoom is left alone (F-092: the canvas's own pinch is gone).
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var stage = CZ.stage, path = CZ.path, reduced = CZ.reduced;

  var pts = {};
  function count() { return Object.keys(pts).length; }
  stage.addEventListener('pointerdown', function (e) { pts[e.pointerId] = { x: e.clientX, y: e.clientY }; });
  function lift(e) { delete pts[e.pointerId]; }
  stage.addEventListener('pointerup', lift);
  stage.addEventListener('pointercancel', lift);

  var clickGuard = 0, guardItem = null;     // the click that follows a flick, a drag or a swipe, on what was held, is not a tap
  function guard(ms, el) { clickGuard = Date.now() + ms; guardItem = el; }

  // ---- a flick between days -----------------------------------------------------------------------------------------------------
  var flick = null;
  var FLICK = 60;
  stage.addEventListener('pointerdown', function (e) {
    flick = null;
    var v = CZ.view();
    if (!v || v.dataset.level !== 'day' || e.pointerType === 'mouse' || count() > 1) return;
    if (e.target.closest && e.target.closest('.cz-dpills, .cz-strip, .cz-filters, .cz-kinds, .cz-fold, .cz-sheet, input, textarea, select')) return;
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
    if (e.type !== 'pointerup' || CZ.busy() || (g && g.mode === 'drag') || CZ.held) return;
    var dx = e.clientX - f.x, dy = e.clientY - f.y;
    if (Math.abs(dx) < FLICK || Math.abs(dx) < Math.abs(dy) * 1.5 || Date.now() - f.at > 900) return;
    var u = dx < 0 ? f.v.dataset.next : f.v.dataset.prev;
    if (!u) return;
    guard(250, f.v);
    CZ.goto(path(u), { dir: dx < 0 ? 'next' : 'prev', key: null, mode: 'replace' });
  }
  stage.addEventListener('pointerup', endFlick);
  stage.addEventListener('pointercancel', endFlick);

  // ---- hold to move, swipe for Done and Set aside (editors only) ------------------------------------------------------------------
  // One gesture at a time, from pointerdown on a step (data-drag) or on a list chip (data-add-title):
  //   wait   the finger is down and still. After HOLD ms the step is lifted (drag). Moving more than SLOP first is a scroll (or, sideways on a row, a swipe).
  //   drag   a chip follows the finger; the part under it, a day in the bar at the top, or the Set aside tray is the target. Letting go posts the move.
  //   swipe  the row slides left over its Done and Set aside buttons, and settles open or shut.
  var edit = stage.dataset.edit === '1';
  var HOLD = 350, SLOP = 10;
  var g = null;                 // the gesture in progress

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
  function clearMarks() {
    stage.querySelectorAll('.is-target, .is-before, .is-end').forEach(function (n) { n.classList.remove('is-target', 'is-before', 'is-end'); });
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
    var chip = document.createElement('div');
    chip.className = 'cz-lift';
    chip.setAttribute('aria-hidden', 'true');
    chip.textContent = dragLabel(g.item);
    var hint = document.createElement('span');
    hint.className = 'cz-lift-when';
    chip.appendChild(hint);
    (document.getElementById('main') || document.body).appendChild(chip);
    g.lift = chip;
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

  function failed(word) { return function (err) { CZ.showToast(err && err.soft ? err.soft : word); }; }
  function dropOn() {
    var t = g.target, item = g.item;
    if (!t) return;
    if (g.adding) {
      if (t.kind !== 'part') return;
      CZ.post('/trip/canvas/add', CZ.tripBody({ act: t.act, part: t.part, title: item.dataset.addTitle, note: item.dataset.addNote || '', next: CZ.here() })).then(function (res) {
        return CZ.refresh().then(function () { CZ.showToast(res.toast || 'Added'); });
      }).catch(failed('Could not add that.'));
      return;
    }
    var fields = t.kind === 'part' ? { step: item.dataset.drag, part: t.part, before: t.before } : t.kind === 'day' ? { step: item.dataset.drag, act: t.act } : { step: item.dataset.drag, aside: '1' };
    fields.next = CZ.here();
    CZ.post('/trip/canvas/move', CZ.tripBody(fields)).then(function (res) {
      return CZ.refresh().then(function () { if (res.toast) CZ.showToast(res.toast, res.undo); });
    }).catch(failed('Could not move that.'));
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
    if (mode === 'drag') { guard(200, g.item); if (e.type === 'pointerup') dropOn(); }
    else if (mode === 'swipe') { guard(200, g.item); settle(); }
    endGesture();
  }
  document.addEventListener('pointerup', finish);
  document.addEventListener('pointercancel', finish);

  // The click that ends a drag or a swipe is not a tap; a tap on an open row puts its buttons away instead of opening the step.
  document.addEventListener('click', function (e) {
    if (!stage.contains(e.target)) return;
    if (Date.now() < clickGuard && guardItem && guardItem.contains(e.target) && !e.target.closest('.cz-swipe-acts')) { e.preventDefault(); e.stopImmediatePropagation(); return; }
    var open = e.target.closest ? e.target.closest('.cz-swipe.is-open') : null;
    if (open && !e.target.closest('.cz-swipe-acts')) { e.preventDefault(); e.stopImmediatePropagation(); closeSwipes(); }
  }, true);

  CZ.guard = guard;            // the day grid: the click a lifting finger makes is not a tap on what it lifted from
  CZ.closeSwipes = closeSwipes;
  CZ.gesturing = function () { return !!g || !!flick || count() > 0; };      // canvas_core.js: no refresh lands under a finger
})();
