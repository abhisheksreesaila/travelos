// Move a plan on the desktop week (F-157). The week shows every day at once, so with a mouse a plan row (`.cz-wi[data-wk-act]`, plans only) can be pressed, pulled past the shared drag
// distance (CZ.DRAG) and dropped on another day's column: the plan keeps its time and goes to that day, written through the canvas's own path (POST /trip/canvas/plan, op=edit, `day`; the
// same write, toast "Moved to Sat 17" and Undo as dropping on a day chip, F-151). A press that does not travel is still a click and opens the day with the plan in the panel (F-145).
// The column under the pointer shows it takes the drop (a coral ring and tint); the plan's own column does not. Esc, or letting go on the plan's own column or anywhere else, leaves it.
// A trip longer than five days scrolls sideways inside the week: held within a few rem of its left or right edge it scrolls. Laptop only, a mouse only, editors only (the server refuses
// a viewer too). No motion of its own: the lifted copy follows the pointer, and the refreshed week simply has the row in its new column in time order. Needs canvas_core.js and day_grid.js.
(function () {
  var CZ = window.CZ;
  if (!CZ || !CZ.mouseOn) return;
  var stage = CZ.stage;
  var ZONE = 3, SPEED = 14;      // rem: the stretch at each side of the week that scrolls it; px a frame at the very edge
  var g = null;                  // { row, act, from, x0, y0, x, y, lifted, copy, hot, raf, id }
  var stop = 0;                  // until when the click a drop makes on its row is not a tap
  var busy = false;              // the write of a drop is on its way

  function rem() { return parseFloat(getComputedStyle(document.documentElement).fontSize) || 12; }
  function wk() { return stage.querySelector('#cz-wk'); }
  function cols() { var w = wk(); return w ? Array.prototype.slice.call(w.querySelectorAll('.cz-wcol')) : []; }
  function editing() { return stage.dataset.edit === '1'; }

  function colAt(x, y) {
    var w = wk();
    if (!w) return null;
    var wr = w.getBoundingClientRect();
    if (y < wr.top || y > wr.bottom || x < wr.left || x > wr.right) return null;
    var c = cols();
    for (var i = 0; i < c.length; i++) { var r = c[i].getBoundingClientRect(); if (x >= r.left && x <= r.right) return c[i]; }
    return null;
  }
  function target() {
    var c = g.lifted ? colAt(g.x, g.y) : null;
    if (c && c.dataset.day === g.from) c = null;
    if (c !== g.hot) { if (g.hot) g.hot.classList.remove('is-drop-target'); g.hot = c; if (c) c.classList.add('is-drop-target'); }
    return c;
  }
  function place() { if (g && g.copy) g.copy.style.transform = 'translate(' + (g.x - g.dx) + 'px,' + (g.y - g.dy) + 'px)'; }

  function lift() {
    var row = g.row, r = row.getBoundingClientRect(), w = wk();
    g.lifted = true; CZ.held = true;
    g.dx = g.x0 - r.left; g.dy = g.y0 - r.top;
    var copy = row.cloneNode(true);
    copy.removeAttribute('href'); copy.removeAttribute('data-zoom'); copy.removeAttribute('data-wk-act'); copy.setAttribute('aria-hidden', 'true');
    copy.className += ' cz-wi-copy';
    copy.style.cssText = 'position:fixed;left:0;top:0;width:' + r.width + 'px;pointer-events:none;z-index:60;';
    (stage.closest('.cz') || stage).appendChild(copy);      // (inside .cz: the row's rules are scoped to it)
    g.copy = copy;
    row.classList.add('is-lifted');
    if (w) w.classList.add('is-dragging');
    document.documentElement.classList.add('cz-wk-moving');
    place();
    (function frame() {                                      // the sideways scroll of a long trip, every frame while held
      if (!g) return;
      var w2 = wk();
      if (w2 && w2.scrollWidth > w2.clientWidth) {
        var wr = w2.getBoundingClientRect(), z = rem() * ZONE, dx = 0;
        if (g.y >= wr.top - rem() && g.y <= wr.bottom + rem()) {
          if (g.x < wr.left + z) dx = -Math.ceil(Math.min(1, (wr.left + z - g.x) / z) * SPEED);
          else if (g.x > wr.right - z) dx = Math.ceil(Math.min(1, (g.x - (wr.right - z)) / z) * SPEED);
        }
        if (dx) { var b = w2.scrollLeft; w2.scrollLeft = b + dx; if (w2.scrollLeft !== b) target(); }
      }
      g.raf = requestAnimationFrame(frame);
    })();
  }

  function end() {
    if (!g) return;
    cancelAnimationFrame(g.raf);
    if (g.copy && g.copy.parentNode) g.copy.parentNode.removeChild(g.copy);
    if (g.hot) g.hot.classList.remove('is-drop-target');
    g.row.classList.remove('is-lifted');
    var w = wk(); if (w) w.classList.remove('is-dragging');
    document.documentElement.classList.remove('cz-wk-moving');
    if (g.lifted) { CZ.held = false; stop = Date.now() + 400; }
    g = null;
  }

  function drop(col) {
    var act = g.act, to = col.dataset.day, row = g.row;
    end();
    busy = true;
    row.classList.add('is-saving');
    CZ.post('/trip/canvas/plan', CZ.tripBody({ op: 'edit', act: act, day: to, next: CZ.here() })).then(function (res) {
      busy = false;
      if (res.toast) CZ.showToast(res.toast, res.undo ? function () { CZ.undo(res.undo); } : null);
      return CZ.quiet();
    }, function (err) {
      busy = false;
      row.classList.remove('is-saving');
      CZ.showToast(err && err.soft ? err.soft : 'Could not save that. Check your connection.');
      return CZ.quiet();
    });
  }

  document.addEventListener('pointerdown', function (e) {
    if (g || busy || e.button || !CZ.mouseOn(e) || !editing()) return;
    var row = e.target.closest ? e.target.closest('.cz-wk .cz-wi[data-wk-act]') : null;
    if (!row || !stage.contains(row)) return;
    g = { row: row, act: row.dataset.wkAct, from: row.closest('.cz-wcol').dataset.day, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, lifted: false, hot: null, id: e.pointerId };
  }, true);
  document.addEventListener('pointermove', function (e) {
    if (!g || e.pointerId !== g.id) return;
    g.x = e.clientX; g.y = e.clientY;
    if (!g.lifted) {
      if (!e.buttons) { g = null; return; }
      if (Math.hypot(g.x - g.x0, g.y - g.y0) <= CZ.DRAG) return;
      lift();
    }
    place(); target();
  }, true);
  function up(e) {
    if (!g || e.pointerId !== g.id) return;
    if (!g.lifted) { g = null; return; }
    var col = e.type === 'pointerup' ? target() : null;
    if (col) drop(col); else end();
  }
  document.addEventListener('pointerup', up, true);
  document.addEventListener('pointercancel', up, true);
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || !g || !g.lifted) return;
    e.preventDefault(); e.stopImmediatePropagation(); end();
  }, true);
  document.addEventListener('dragstart', function (e) { if (g && e.target.closest && e.target.closest('.cz-wi')) e.preventDefault(); }, true);
  document.addEventListener('click', function (e) {      // the click a drop makes on the row it was lifted from is not a tap
    if (Date.now() < stop && e.target.closest && e.target.closest('.cz-wk .cz-wi')) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, true);
  CZ.onSwap.push(function () { if (g) end(); });      // a swap to another level drops the gesture (a refresh in place waits: CZ.held keeps it off)
})();
