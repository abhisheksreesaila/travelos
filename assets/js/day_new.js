// Make a plan by touching empty time on the day grid (F-101). Needs trip_canvas.js, day_grid.js and day_menu.js, which load first.
//
//   Hold empty time about 350 ms (a finger that stays still; a scroll or the flick between days starts earlier and is left alone): a one-hour block appears there, snapped to
//   15 minutes, and follows the finger until it lets go. On release its title field opens in place (the same field as Rename, day_menu.js `CZ.titleField`) with the keyboard up.
//   Enter, or tapping away, saves it (the calendar's own add rules, POST /trip/canvas/plan op=add; the toast has Undo; the family gets one card). Escape or an empty title removes it.
//   Once saved it is a plan like any other: hold it to move it, hold its bottom edge to change its length (day_grid.js).
//   Or tap empty time: a "+" appears in the slot; tapping the "+" does the same. Keyboard and screen reader: the visually hidden "Add a plan" button at the top of the grid.
//
// The iOS rule. Safari opens the keyboard only for focus() called inside a user activation: a touchend, pointerup or click handler, not a timer (the hold's 350 ms timer is a
// timer, so the field is NOT opened from it). The timer only shows the block; the field is opened by `openField` from the same pointerup that ends the hold, or from the click on
// the "+" chip. If focus() was still refused (some WebKit builds count only touchend), the touchend and click that follow try once more.
//
// While a title is typed the rest of the grid is calm: other blocks and bookings are dimmed and take no touches, a sideways flick does not change the day, no gesture starts, and
// a tap anywhere else (even on something that is not a control, where iOS would not blur the field) saves the title (day_menu.js `away`).
// Viewers: no data-edit, so none of this runs. Reduced motion: the block appears without its pop.
(function () {
  var CZ = window.CZ;
  if (!CZ || !CZ.titleField) return;
  var stage = CZ.stage;
  var HOLD = 350, SLOP = 10, GRAIN = 15, LEN = 60, DAY_END = 22 * 60, CHIP_MS = 6000;
  var h = null;           // the finger on empty time: { id, x0, y0, y, at, timer, mode: 'wait' | 'held', draft, s }
  var fingers = {};
  var chip = null;        // the "+" waiting for a tap: { ghost, btn, s, timer }
  var making = null;      // the new plan whose title is being typed: { draft, grid, field }

  function editing() { return stage.dataset.edit === '1'; }
  function grid() { return stage.querySelector('#cz-grid'); }
  function clamp(v, lo, hi) { return Math.min(Math.max(v, lo), hi); }
  function buzz(ms) { try { if (navigator.vibrate) navigator.vibrate(ms); } catch (e) { /* no buzz */ } }
  function count() { return Object.keys(fingers).length; }

  document.addEventListener('pointerdown', function (e) { fingers[e.pointerId] = 1; if (count() > 1) cancelHold(); }, true);
  function lifted(e) { delete fingers[e.pointerId]; }
  document.addEventListener('pointerup', lifted);
  document.addEventListener('pointercancel', lifted);

  // ---- where the finger is, in minutes ----------------------------------------------------------------------------------------
  function slotAt(g, y) {
    var zoom = g.querySelector('.cz-g-zoom'), lo = +g.dataset.lo, hi = +g.dataset.hi;
    var m = lo + (y - zoom.getBoundingClientRect().top) / (zoom.offsetHeight / (hi - lo));
    return clamp(Math.floor(m / GRAIN) * GRAIN, lo, Math.max(lo, Math.min(hi, DAY_END) - LEN));
  }
  function emptyTime(e) {
    var g = grid();
    if (!g || !editing() || e.button > 0) return null;
    var t = e.target;
    if (!t.closest || !t.closest('.cz-g-plane') || t.closest('.cz-gb, .cz-gbk, .cz-gnew, input, textarea, .cz-menu')) return null;
    return g;
  }

  // ---- the block ---------------------------------------------------------------------------------------------------------------
  function mk(tag, cls) { var n = document.createElement(tag); if (cls) n.className = cls; return n; }
  function put(draft, g, s) {
    draft.style.setProperty('--s', s - +g.dataset.lo);
    draft.dataset.s = s;
    draft.dataset.e = s + LEN;
    var w = draft.querySelector('.cz-gb-when');
    if (w) w.textContent = CZ.span(s, s + LEN);
  }
  function newBlock(g, s) {
    var d = mk('div', 'cz-gb cz-k-fun is-new');
    d.style.cssText = '--l:' + LEN + ';--lane:0;--lanes:1';
    d.setAttribute('role', 'group');
    d.setAttribute('aria-label', 'New plan');
    var inner = mk('div', 'cz-gb-in cz-cs');
    inner.appendChild(mk('span', 'cz-gb-t'));
    inner.appendChild(mk('span', 'cz-gb-when'));
    d.appendChild(inner);
    put(d, g, s);
    g.querySelector('.cz-g-plane').appendChild(d);
    return d;
  }

  // ---- hold ---------------------------------------------------------------------------------------------------------------------
  stage.addEventListener('pointerdown', function (e) {
    dropChip(e);
    if (h || making || CZ.held || count() !== 1) return;
    var g = emptyTime(e);
    if (!g) return;
    h = { id: e.pointerId, x0: e.clientX, y0: e.clientY, y: e.clientY, at: Date.now(), mode: 'wait', g: g, type: e.pointerType };
    h.timer = setTimeout(lift, HOLD);
  });
  function lift() {
    if (!h || h.mode !== 'wait' || !h.g.isConnected) { h = null; return; }
    h.mode = 'held';
    h.s = slotAt(h.g, h.y);
    h.draft = newBlock(h.g, h.s);
    CZ.held = true;                          // the flick between days and the other gestures leave this finger alone
    buzz(14);
    // No focus here: this is a timer, and iOS would refuse the keyboard. See the note at the top; `openField` runs from the pointerup.
  }
  document.addEventListener('pointermove', function (e) {
    if (!h || e.pointerId !== h.id) return;
    h.y = e.clientY;
    if (h.mode === 'wait') {
      if (Math.hypot(e.clientX - h.x0, e.clientY - h.y0) > SLOP) { clearTimeout(h.timer); h = null; }       // a scroll, or the flick between days
      return;
    }
    var s = slotAt(h.g, h.y);
    if (s !== h.s) { h.s = s; put(h.draft, h.g, s); buzz(4); }
  });
  document.addEventListener('touchmove', function (e) { if (h && h.mode === 'held' && e.cancelable) e.preventDefault(); }, { passive: false });
  document.addEventListener('contextmenu', function (e) { if (h && h.mode === 'held') e.preventDefault(); });

  function cancelHold() {
    if (!h) return;
    clearTimeout(h.timer);
    if (h.draft && h.draft.parentNode) h.draft.parentNode.removeChild(h.draft);
    if (h.mode === 'held') CZ.held = false;
    h = null;
  }
  document.addEventListener('pointercancel', function (e) { if (h && e.pointerId === h.id) cancelHold(); });
  document.addEventListener('pointerup', function (e) {
    if (!h || e.pointerId !== h.id) return;
    clearTimeout(h.timer);
    var f = h;
    h = null;
    if (f.mode === 'wait') {                                           // a tap on empty time: the "+" for that slot
      if (Math.hypot(e.clientX - f.x0, e.clientY - f.y0) <= SLOP && Date.now() - f.at < HOLD) showChip(f.g, e.clientX, e.clientY);
      return;
    }
    CZ.guard(300, f.draft);        // the click a lifting finger makes lands on the new block, and is not a tap on anything else
    openField(f.g, f.draft);                                           // inside the pointerup: a user activation, so the keyboard really opens on iOS
    CZ.held = !!making;                                                // (the flick's own pointerup, on the stage, has already looked at it)
  });

  // ---- the field -----------------------------------------------------------------------------------------------------------------
  function openField(g, draft) {
    var s = +draft.dataset.s, e = +draft.dataset.e;
    var f = CZ.titleField(draft, {
      value: '', label: 'Name of the new plan', same: null, discard: true, settle: 350,
      save: function (title) { return CZ.post('/trip/canvas/plan', CZ.tripBody({ op: 'add', day: g.dataset.day, start: s, end: e, title: title, next: CZ.here() })); },
      saved: function (res, title) { draft.querySelector('.cz-gb-t').textContent = title; calm(false); },      // the refresh that follows makes it a real block
      cancel: function () { if (draft.parentNode) draft.parentNode.removeChild(draft); calm(false); }
    });
    if (!f) { if (draft.parentNode) draft.parentNode.removeChild(draft); calm(false); return; }
    making = { draft: draft, grid: g, field: f };
    CZ.held = true;
    g.classList.add('is-making');
    if (document.activeElement !== f.input) {                          // some WebKit builds count touchend, not pointerup: try once more, then the click
      var again = function () { if (making && making.field === f && document.activeElement !== f.input && f.input.isConnected) { try { f.input.focus({ preventScroll: true }); } catch (x) { f.input.focus(); } } };
      document.addEventListener('touchend', again, { once: true, capture: true });
      document.addEventListener('click', again, { once: true, capture: true });
    }
  }
  function calm(on) {
    if (!on) {
      if (making && making.grid) making.grid.classList.remove('is-making');
      making = null;
      if (!count()) { CZ.held = false; return; }
      // The tap that put the field away is still down: it must not turn into the flick between days (the grid was calm while the title was typed). Held until it lifts.
      var rel = function () { document.removeEventListener('pointerup', rel); document.removeEventListener('pointercancel', rel); clearTimeout(t); if (!making && !h) CZ.held = false; };
      var t = setTimeout(rel, 2000);
      document.addEventListener('pointerup', rel);
      document.addEventListener('pointercancel', rel);
    }
  }

  var before = CZ.editing;
  CZ.editing = function () { return !!making || !!h || !!chip || (before ? before() : false); };      // trip_canvas.js never re-swaps the page (F-099 revalidation) under a title being typed, a hold or the "+"

  // ---- the "+" ---------------------------------------------------------------------------------------------------------------------
  function showChip(g, x, y) {
    dropChip();
    var s = slotAt(g, y), plane = g.querySelector('.cz-g-plane'), pr = plane.getBoundingClientRect();
    var ghost = mk('div', 'cz-gnew-ghost');
    ghost.setAttribute('aria-hidden', 'true');
    ghost.style.cssText = '--s:' + (s - +g.dataset.lo) + ';--l:' + LEN;
    var btn = mk('button', 'cz-gnew');
    btn.type = 'button';
    btn.setAttribute('aria-label', 'Add a plan at ' + CZ.span(s, s + LEN));
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>';
    btn.style.cssText = '--s:' + (s - +g.dataset.lo) + ';left:' + clamp(x - pr.left - 22, 4, pr.width - 48) + 'px';
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      dropChip();
      if (making) return;
      openField(g, newBlock(g, s));                                    // a click: a user activation
    });
    plane.appendChild(ghost);
    plane.appendChild(btn);
    chip = { ghost: ghost, btn: btn, timer: setTimeout(function () { dropChip(); }, CHIP_MS) };
  }
  function dropChip(e) {
    if (!chip) return;
    if (e && e.target && e.target.closest && e.target.closest('.cz-gnew')) return;      // the tap that presses it
    clearTimeout(chip.timer);
    [chip.ghost, chip.btn].forEach(function (n) { if (n.parentNode) n.parentNode.removeChild(n); });
    chip = null;
  }

  // ---- a keyboard or a screen reader ---------------------------------------------------------------------------------------------
  function offerButton() {
    var g = grid();
    if (!g || !editing() || g.querySelector('.cz-gadd')) return;
    var b = mk('button', 'cz-gadd sr-only');
    b.type = 'button';
    b.textContent = 'Add a plan';
    b.addEventListener('click', function () {
      if (making) return;
      var line = g.querySelector('#cz-nowline'), lo = +g.dataset.lo;
      var s = line ? clamp(Math.ceil((+line.dataset.m + 1) / GRAIN) * GRAIN, lo, Math.min(+g.dataset.hi, DAY_END) - LEN) : clamp(9 * 60, lo, Math.min(+g.dataset.hi, DAY_END) - LEN);
      openField(g, newBlock(g, s));
    });
    g.insertBefore(b, g.firstChild);
  }
  stage.addEventListener('cz:swap', function () {
    dropChip();
    if (h) cancelHold();
    if (making && !making.draft.isConnected) calm(false);           // the page was replaced under the field (a day was opened): nothing to finish
    offerButton();
  });
  offerButton();
})();
