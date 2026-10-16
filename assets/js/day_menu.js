// The hold menu, rename in place and delete on the day grid (F-098). Needs canvas_core.js and day_grid.js, which load first and hand over two moments:
//   CZ.hold(block)      a block was held and let go without moving: it wiggles and a small menu pops beside it: Chat, Rename, Delete, and Earlier, Later, Shorter and
//                       Longer by 15 minutes (the same moves as dragging, for a keyboard or a screen reader; they are a real menu, role="menu").
//   CZ.tap(block, e)    a tap: two quick taps on a title edit it in place. A park block's single tap on its title waits a moment for a second tap before it opens.
// Rename in place: the title becomes a field right there; Enter or tapping away saves, Escape cancels; an empty or too-long title is refused in plain words (the
// calendar's own rule: 1 to 40 characters). Delete asks once, in the menu, and has Undo after. The blocks are editors' only: a viewer's page has no menu button.
(function () {
  var CZ = window.CZ;
  if (!CZ || !CZ.setTimes) return;
  var MO = window.GA.motion;      // the one liquid motion (motion.js, F-109)
  var stage = CZ.stage;
  var MAX_TITLE = 40, STEP = 15, FINE = 5, MIN_LEN = 15, DAY_END = 22 * 60;
  var fineOn = false;       // the menu's own 5-minute switch: precision for a person who has no zoom (reduced motion) or would rather press than drag
  function nstep() { return fineOn ? FINE : STEP; }
  var menu = null;          // the open menu: { el, block, act, node, return: the thing to focus when it closes }
  var lastTap = null, opening = 0;

  function editing() { return stage.dataset.edit === '1'; }
  function clamp(v, lo, hi) { return Math.min(Math.max(v, lo), hi); }
  function clock12(m) { var h = Math.floor(m / 60) % 24, mm = m % 60; return ((h % 12) || 12) + ':' + (mm < 10 ? '0' : '') + mm + ' ' + (h < 12 ? 'AM' : 'PM'); }
  function titleOf(el) { return el.dataset.title || 'This plan'; }
  function mk(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; }
  function icon(name) {
    var paths = {
      chat: 'M21 12a8 8 0 0 1-11.5 7.2L4 20.5l1.4-4.6A8 8 0 1 1 21 12Z', pencil: 'M4 20h4L19 9l-4-4L4 16v4ZM13 7l4 4', trash: 'M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13M10 11v6M14 11v6',
      tag: 'M3 12V4h8l10 10-8 8L3 12ZM7.5 7.5h.01', cal: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4', back: 'M19 12H5M12 5l-7 7 7 7',
      up: 'M12 19V5M5 12l7-7 7 7', down: 'M12 5v14M19 12l-7 7-7-7', shorter: 'M5 9h14M5 15h14M9 4l3 3 3-3M9 20l3-3 3 3', longer: 'M5 12h14M9 8l3-4 3 4M9 16l3 4 3-4'
    };
    var s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor'); s.setAttribute('stroke-width', '2.4');
    s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round'); s.setAttribute('aria-hidden', 'true'); s.setAttribute('class', 'cz-mi-ico');
    var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', paths[name]);
    s.appendChild(p);
    return s;
  }
  function item(kind, label, ico, extra) {
    var b = mk(kind === 'chat' ? 'a' : 'button', 'cz-mi cz-mi-' + (extra && extra.id || ''));
    if (kind !== 'chat') b.type = 'button';
    b.setAttribute('role', 'menuitem');
    b.appendChild(icon(ico));
    b.appendChild(mk('span', 'cz-mi-t', label));
    if (extra && extra.id) b.dataset.do = extra.id;
    return b;
  }

  // ---- the menu ---------------------------------------------------------------------------------------------------------------
  function close(returnFocus) {
    if (!menu) return;
    var m = menu;
    menu = null;
    document.removeEventListener('pointerdown', outside, true);
    var gone = function () { if (m.node.parentNode) m.node.parentNode.removeChild(m.node); };
    if (MO && !MO.reduced() && m.node.parentNode) {      // F-109: it folds back into the block it grew out of
      m.node.setAttribute('inert', ''); m.node.setAttribute('aria-hidden', 'true'); m.node.style.pointerEvents = 'none';
      MO.close(m.node, m.block && m.block.isConnected ? m.block : null).then(gone);
    } else gone();
    if (m.block && m.block.isConnected) { m.block.classList.remove('is-wiggle', 'is-menu'); if (returnFocus) focusBlock(m.block); }
    CZ.menuOpen = false;
  }
  function focusBlock(b) {
    var f = b.querySelector('.cz-gb-menubtn') || b;
    try { f.focus({ preventScroll: true }); } catch (e) { f.focus(); }
  }
  function outside(e) {
    if (!menu || menu.node.contains(e.target)) return;
    var onBlock = e.target.closest && (e.target.closest('.cz-gb') === menu.block || e.target.closest('.cz-g-knobs'));      // (F-110: the block's knobs are the block)
    close(false);
    if (!onBlock) CZ.guard(450, stage);      // the tap that put the menu away is only that: it opens nothing
  }

  function bounds(b) {
    var g = b.closest('#cz-grid');
    return { lo: g ? +g.dataset.lo : 420, hi: Math.min(g ? +g.dataset.hi : DAY_END, DAY_END), s: +b.dataset.s, e: +b.dataset.e };
  }

  // The menu's first step: what can be done to the plan. (F-152: Change type and Move to day open a second step in this same menu, below.)
  function render(node, b) {
    node.appendChild(mk('p', 'cz-menu-t', titleOf(b)));
    var main = mk('div', 'cz-menu-main');
    var chat = item('chat', 'Chat', 'chat', { id: 'chat' });
    chat.href = b.dataset.talk || '#';
    main.appendChild(chat);
    main.appendChild(item('rename', 'Rename', 'pencil', { id: 'rename' }));
    main.appendChild(item('delete', 'Delete', 'trash', { id: 'delete' }));
    node.appendChild(main);
    if (/^a\d/.test(b.dataset.act || '')) {      // a plan, not a booking
      var more = mk('div', 'cz-menu-more');
      more.appendChild(item('button', 'Change type', 'tag', { id: 'type' }));
      more.appendChild(item('button', 'Move to day…', 'cal', { id: 'moveday' }));
      node.appendChild(more);
    }
    var nudge = mk('div', 'cz-menu-nudge');
    nudge.setAttribute('role', 'group');
    nudge.setAttribute('aria-label', 'By 15 minutes');
    [['earlier', 'Earlier', 'up'], ['later', 'Later', 'down'], ['shorter', 'Shorter', 'shorter'], ['longer', 'Longer', 'longer']].forEach(function (n) {
      var it = item('button', n[1], n[2], { id: n[0] });
      it.setAttribute('aria-label', n[1] + ' by ' + nstep() + ' minutes');
      nudge.appendChild(it);
    });
    node.appendChild(nudge);
    var fine = item('button', 'Fine: 5 min', 'shorter', { id: 'fine' });
    fine.setAttribute('role', 'menuitemcheckbox');
    fine.classList.add('cz-mi-fine');
    node.appendChild(fine);
    syncNudges(node, bounds(b));
  }

  function open(b, focusItem, kbd) {
    if (!editing() || !b || !b.isConnected) return;
    close(false);
    var k = bounds(b);
    var node = mk('div', 'cz-menu');
    node.setAttribute('role', 'menu');
    node.tabIndex = -1;
    node.setAttribute('aria-label', titleOf(b) + ': what to do');
    render(node, b);
    node.addEventListener('focusin', function (e) { if (menu && e.target.dataset && e.target.dataset.do) menu.focusId = e.target.dataset.do; });
    stage.appendChild(node);
    menu = { block: b, act: b.dataset.act, node: node, focusId: focusItem || '' };
    CZ.menuOpen = true;
    b.classList.add('is-menu');
    if (!CZ.reduced.matches) b.classList.add('is-wiggle');
    place(node, b);
    if (MO) {                       // F-109: it grows out of the block that was held; while it grows it is not a target, so the block's knobs (F-110) can be grabbed through it
      node.style.pointerEvents = 'none';
      MO.open(node, b).then(function () { if (node.isConnected && !node.hasAttribute('inert')) node.style.pointerEvents = ''; });
    }
    document.addEventListener('pointerdown', outside, true);
    // A keyboard or a screen reader lands on the first choice; a finger that held the block lands on the menu itself (no focus ring on a button nobody asked for), and Escape and the arrow keys work from there.
    var first = kbd ? ((focusItem && node.querySelector('[data-do="' + focusItem + '"]:not(:disabled)')) || node.querySelector('.cz-mi:not(:disabled)')) : node;
    if (first) { try { first.focus({ preventScroll: true }); } catch (e) { first.focus(); } }
  }

  // What the four nudges may still do: not before the grid starts, not past its end, not under 15 minutes.
  function syncNudges(node, k) {
    var d = nstep(), ok = { earlier: k.s - d >= k.lo, later: k.e + d <= k.hi, shorter: k.e - k.s - d >= MIN_LEN, longer: k.e + d <= k.hi };
    var f = node.querySelector('[data-do="fine"]');
    if (f) { f.setAttribute('aria-checked', fineOn ? 'true' : 'false'); f.classList.toggle('is-on', fineOn); }
    ['earlier', 'later', 'shorter', 'longer'].forEach(function (id) {
      var it = node.querySelector('[data-do="' + id + '"]');
      if (it) it.setAttribute('aria-label', it.textContent.trim() + ' by ' + d + ' minutes');
    });
    Object.keys(ok).forEach(function (id) {
      var it = node.querySelector('[data-do="' + id + '"]');
      if (!it) return;
      it.disabled = !ok[id];
      if (ok[id]) it.removeAttribute('aria-disabled'); else it.setAttribute('aria-disabled', 'true');
    });
  }

  // Beside the block: under it when there is room above the tab bar, else over it, else over the middle of what can be seen of it.
  function place(node, b) {
    var sr = stage.getBoundingClientRect(), br = b.getBoundingClientRect();
    var tabs = document.querySelector('.ph-tabs'), floor = (tabs && getComputedStyle(tabs).display !== 'none' ? tabs.getBoundingClientRect().top : window.innerHeight) - 8;
    var w = Math.min(node.offsetWidth, window.innerWidth - 16), h = node.offsetHeight;
    var x = clamp(br.left, 8, window.innerWidth - w - 8);
    var gap = 8 + (parseFloat(getComputedStyle(document.documentElement).fontSize) || 16) * 1.375;      // clear of the knobs' touch areas (F-110: 2.75rem across, centred on the block's edges)
    var y = br.bottom + gap;
    if (y + h > floor) y = br.top - h - gap;
    if (y < 8 && br.bottom + gap + h <= window.innerHeight - 8) y = br.bottom + gap;      // no room either side above the tab bar: under the block, over the tab bar, rather than over the block's knobs
    if (y < 8) y = clamp(Math.max(br.top, 8) + (Math.min(br.bottom, floor) - Math.max(br.top, 8)) / 2 - h / 2, 8, Math.max(8, floor - h));
    node.style.left = (x - sr.left) + 'px';
    node.style.top = (y - sr.top) + 'px';
  }

  stage.addEventListener('click', function (e) {
    var it = e.target.closest && e.target.closest('.cz-mi');
    if (it && menu && menu.node.contains(it)) { choose(it, e); return; }
    var btn = e.target.closest && e.target.closest('.cz-gb-menubtn');      // the keyboard's and the screen reader's way in
    if (btn && editing()) { e.preventDefault(); open(btn.closest('.cz-gb'), null, true); }
  });
  stage.addEventListener('keydown', function (e) {
    var b = e.target.classList && e.target.classList.contains('cz-gb') && editing() ? e.target : null;
    if (b && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); open(b, null, true); }
  });
  // Escape and the arrow keys belong to the menu (and to a title being edited) while they are open; the canvas's own Escape would zoom out a level.
  document.addEventListener('keydown', function (e) {
    if (menu) {
      if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); close(true); return; }
      var items = Array.prototype.filter.call(menu.node.querySelectorAll('.cz-mi'), function (n) { return !n.disabled; });
      var at = items.indexOf(document.activeElement), next = null;
      if (e.key === 'ArrowDown' || e.key === 'ArrowRight') next = items[(at + 1) % items.length];
      else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') next = items[at < 0 ? items.length - 1 : (at - 1 + items.length) % items.length];
      else if (e.key === 'Home') next = items[0];
      else if (e.key === 'End') next = items[items.length - 1];
      if (next) { e.preventDefault(); next.focus(); }
    }
  }, true);

  function choose(it, e) {
    var what = it.dataset.do, b = menu.block, act = menu.act;
    if (what === 'chat') return;                                  // a real link: it goes to the plan's chat
    e.preventDefault();
    if (what === 'rename') { close(false); rename(b); return; }
    if (what === 'delete') { confirmDelete(); return; }
    if (what === 'type') { pickType(); return; }
    if (what === 'moveday') { pickDay(); return; }
    if (what === 'back') { toFirstStep(); return; }
    if (what === 'pick-kind') { saveEdit(b, { kind: it.dataset.kind }); return; }
    if (what === 'pick-day') { saveEdit(b, { day: it.dataset.day }); return; }
    var k = bounds(b), s = k.s, en = k.e, d = nstep();
    if (what === 'fine') { fineOn = !fineOn; syncNudges(menu.node, k); return; }
    if (what === 'earlier') { s -= d; en -= d; }
    else if (what === 'later') { s += d; en += d; }
    else if (what === 'shorter') en -= d;
    else if (what === 'longer') en += d;
    if (s < k.lo || en > k.hi || en - s < MIN_LEN) return;
    CZ.setTimes(b, s, en);              // the menu stays for the next nudge: the page behind it is brought up to date, and the menu goes back on the same block (cz:swap, below)
  }

  // ---- Change type and Move to day (F-152): a second step inside the same menu, large choices, no dropdown --------------------------------------------
  // The step's words and choices replace the menu's content and rise in with the shared settle; Back (or Escape, which closes the whole menu) goes the other way.
  function toStep(title, sub, cls, build) {
    var node = menu.node, b = menu.block;
    node.textContent = '';
    node.setAttribute('aria-label', title);
    var step = mk('div', 'cz-menu-step');
    step.appendChild(mk('p', 'cz-menu-t', title));
    if (sub) step.appendChild(mk('p', 'cz-menu-sub', sub));
    var grid = mk('div', cls);
    grid.setAttribute('role', 'group');
    grid.setAttribute('aria-label', title);
    build(grid);
    step.appendChild(grid);
    var back = item('button', 'Back', 'back', { id: 'back' });
    back.classList.add('cz-mi-back');
    step.appendChild(back);
    node.appendChild(step);
    place(node, b);
    if (MO) MO.settle(step, { y: 0.375 });
    var first = step.querySelector('.cz-mi[aria-checked="false"], .cz-mi:not([aria-checked])') || back;
    try { first.focus({ preventScroll: true }); } catch (e) { first.focus(); }
  }
  function toFirstStep() {
    var node = menu.node, b = menu.block;
    node.textContent = '';
    node.setAttribute('aria-label', titleOf(b) + ': what to do');
    render(node, b);
    place(node, b);
    if (MO) MO.settle(node.querySelector('.cz-menu-main'), { y: 0.25 });
    var again = node.querySelector('[data-do="' + (menu.focusId || 'type') + '"]:not(:disabled)') || node.querySelector('.cz-mi:not(:disabled)');
    if (again) { try { again.focus({ preventScroll: true }); } catch (e) { again.focus(); } }
  }
  function pickType() {
    var b = menu.block, now = b.dataset.type || 'fun';
    var tpl = stage.querySelectorAll('#cz-kinds-tpl [data-pick-kind]');
    toStep('Change type', titleOf(b), 'cz-menu-kinds', function (grid) {
      Array.prototype.forEach.call(tpl, function (src) {
        var k = src.dataset.pickKind, c = src.cloneNode(true), here = k === now;
        c.dataset.do = 'pick-kind';
        c.dataset.kind = k;
        c.setAttribute('aria-checked', here ? 'true' : 'false');
        if (here) c.classList.add('is-here');
        c.querySelector('svg').classList.add('cz-mi-ico');
        grid.appendChild(c);
      });
    });
  }
  function pickDay() {
    var b = menu.block, now = b.dataset.day;
    var pills = stage.querySelectorAll('.cz-hchips [data-move-day]');
    toStep('Move to day', titleOf(b), 'cz-menu-days', function (grid) {
      Array.prototype.forEach.call(pills, function (src) {
        var d = src.dataset.moveDay, w = (src.dataset.moveLabel || '').split(' ');
        var label = mk('span', 'cz-dc-dow', w[0] || ''), num = mk('span', 'cz-dc-num', w[1] || '');
        if (d === now) {      // the day it is on: marked, and not something to pick
          var here = mk('span', 'cz-dc is-here');
          here.setAttribute('aria-label', (src.dataset.moveLabel || '') + ', where it is now');
          here.appendChild(label); here.appendChild(num);
          grid.appendChild(here);
          return;
        }
        var c = mk('button', 'cz-mi cz-dc');
        c.type = 'button';
        c.setAttribute('role', 'menuitem');
        c.setAttribute('aria-label', 'Move to ' + src.dataset.moveLabel);
        c.dataset.do = 'pick-day';
        c.dataset.day = d;
        c.appendChild(label); c.appendChild(num);
        grid.appendChild(c);
      });
    });
  }
  // The write is the canvas's own edit with a kind or a day (F-151, F-152); the toast has its Undo. A plan moved away leaves the laptop's panel for Up next (it would show a plan that is not on
  // this day); a plan that only changed type stays open in the panel, which is brought up to date with the day.
  function saveEdit(b, fields) {
    var act = b.dataset.act, pane = document.querySelector('#cz-dock .cz-pp:not(.is-leaving)');
    close(false);
    var body = CZ.tripBody(Object.assign({ op: 'edit', act: act, next: CZ.here() }, fields));
    CZ.post('/trip/canvas/plan', body).then(function (res) {
      if (fields.day != null && pane && pane.dataset.act === act && window.Dock) Dock.close();
      if (res.toast) CZ.showToast(res.toast, res.undo ? function () { CZ.undo(res.undo); } : null);
      return CZ.quiet();
    }, function (err) {
      CZ.showToast(err && err.soft ? err.soft : 'Could not save that. Check your connection.');
    });
  }

  // ---- delete: asked once, in the menu, then Undo ------------------------------------------------------------------------------
  function confirmDelete() {
    var b = menu.block, steps = +b.dataset.steps || 0;
    var node = menu.node;
    node.textContent = '';
    node.appendChild(mk('p', 'cz-menu-t', 'Delete ' + titleOf(b) + '?'));
    if (steps) node.appendChild(mk('p', 'cz-menu-sub', 'Its ' + steps + (steps === 1 ? ' step goes' : ' steps go') + ' with it. You can undo this.'));
    var row = mk('div', 'cz-menu-ask');
    var keep = item('button', 'Keep it', 'chat', { id: 'keep' }), del = item('button', 'Delete', 'trash', { id: 'really' });
    keep.querySelector('svg').replaceWith(icon('up'));
    row.appendChild(keep);
    row.appendChild(del);
    node.appendChild(row);
    del.classList.add('is-danger');
    keep.addEventListener('click', function (e) { e.preventDefault(); e.stopPropagation(); var b2 = menu.block; close(false); open(b2, 'delete', true); });
    del.addEventListener('click', function (e) { e.preventDefault(); e.stopPropagation(); remove(menu.block); });
    place(node, b);
    keep.focus();
  }
  function remove(b) {
    var act = b.dataset.act;
    close(false);
    b.classList.add('is-leaving');
    CZ.post('/trip/canvas/plan', CZ.tripBody({ op: 'delete', act: act, next: CZ.here() })).then(function (res) {
      if (res.toast) CZ.showToast(res.toast, res.undo ? function () { CZ.undo(res.undo); } : null);
      return CZ.quiet();
    }, function (err) {
      b.classList.remove('is-leaving');
      CZ.showToast(err && err.soft ? err.soft : 'Could not delete that.');
    });
  }

  // ---- rename in place --------------------------------------------------------------------------------------------------------
  var REFUSALS = { empty: 'Give it a title.', long: 'Keep the title to ' + MAX_TITLE + ' characters.' };
  function check(v) {
    var t = v.replace(/\s+/g, ' ').trim();
    return !t ? { err: REFUSALS.empty } : t.length > MAX_TITLE ? { err: REFUSALS.long } : { title: t };
  }
  function rename(b) {
    if (!b) return;
    titleField(b, {
      value: titleOf(b),
      label: 'Name of this plan',
      same: titleOf(b),
      save: function (title) { return CZ.post('/trip/canvas/plan', CZ.tripBody({ op: 'edit', act: b.dataset.act, title: title, next: CZ.here() })); },
      saved: function (res, title) { b.querySelector('.cz-gb-t').textContent = title; b.dataset.title = title; }
    });
  }

  // The title field in a block, shared by Rename (above) and a new plan (day_new.js, F-101: `discard` removes the block when the title is left empty).
  //   o.value, o.label   what the field holds and is called      o.same    the title it already has (saving that changes nothing, posts nothing)
  //   o.save(title)      -> the write's promise                  o.saved(res, title)   after it landed (the toast and Undo are shown here)
  //   o.settle           ms after opening in which losing the focus is the touch's own mouse events, not a tap away: the field takes it back
  //   o.inside           a selector for controls that belong to the field: using one is not tapping away (F-161)
//   o.discard          an empty title (Enter, tapping away) or Escape gives the block up: o.cancel() runs, and nothing is saved or refused
  // Returns { input }. Call it from inside the gesture's own pointerup or click when the keyboard has to open (the iOS rule, day_new.js).
  function titleField(b, o) {
    if (!editing() || !b || !b.isConnected || b.classList.contains('is-editing')) return null;
    var t = b.querySelector('.cz-gb-t');
    if (!t) return null;
    if (CZ.deselect) CZ.deselect();      // F-110: the knobs go while the title is typed, so the top one never sits on the field
    var input = mk('input', 'cz-gb-edit');
    input.type = 'text';
    input.value = o.value || '';
    input.setAttribute('aria-label', o.label || 'Name of this plan');
    input.setAttribute('enterkeyhint', 'done');
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('autocapitalize', 'sentences');
    input.setAttribute('spellcheck', 'false');
    var err = mk('span', 'cz-gb-err');
    err.setAttribute('role', 'alert');
    t.hidden = true;
    t.parentNode.insertBefore(input, t.nextSibling);
    input.parentNode.insertBefore(err, input.nextSibling);
    b.classList.add('is-editing');
    var over = false;
    function stop(keep) {
      over = true;
      document.removeEventListener('pointerdown', away, true);
      input.remove(); err.remove();
      t.hidden = false;
      b.classList.remove('is-editing');
      if (keep && !o.discard) focusBlock(b);
    }
    function giveUp() { stop(false); if (o.cancel) o.cancel(); }
    // iOS does not blur a field when the finger lands on something that is not a control, so a tap anywhere else puts the field away itself (it saves, as tapping away does).
    var left = false;      // a real tap away (the next pointerdown), as against the touch's own mouse events right after the field opened (o.settle)
    function inside(n) { return !!(o.inside && n && n.closest && n.closest(o.inside)); }      // o.inside: a control that belongs to the field (a new plan's kind chips, F-161): using it is not a tap away
    function away(e) { if (e.target !== input && !(e.target.closest && e.target.closest('.cz-gb-edit')) && !inside(e.target)) { left = true; input.blur(); } }
    document.addEventListener('pointerdown', away, true);
    function commit(fromBlur) {
      if (over) return;
      var got = check(input.value);
      if (got.err) {
        if (o.discard && !input.value.trim()) { giveUp(); return; }        // a new plan with no title is no plan
        if (fromBlur) { stop(false); if (o.cancel) o.cancel(); CZ.showToast(got.err); return; }       // tapped away from a title that cannot be saved: it goes back as it was, with the reason
        err.textContent = got.err;
        input.setAttribute('aria-invalid', 'true');
        input.focus();
        return;
      }
      if (got.title === o.same) { stop(!fromBlur); return; }
      input.disabled = true;
      o.save(got.title).then(function (res) {
        stop(!fromBlur);
        if (o.saved) o.saved(res, got.title);
        if (res.toast) CZ.showToast(res.toast, res.undo ? function () { CZ.undo(res.undo); } : null);
        return CZ.quiet();
      }, function (e) {
        input.disabled = false;
        if (fromBlur) { stop(false); if (o.cancel) o.cancel(); CZ.showToast(e && e.soft ? e.soft : 'Could not save that.'); return; }
        err.textContent = e && e.soft ? e.soft : 'Could not save that.';
        input.setAttribute('aria-invalid', 'true');
        input.focus();
      });
    }
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); commit(false); }
      else if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); if (o.discard) giveUp(); else stop(true); }
      else e.stopPropagation();
    }, true);
    input.addEventListener('input', function () { err.textContent = ''; input.removeAttribute('aria-invalid'); });
    var born = Date.now();
    input.addEventListener('blur', function (e) {
      if (inside(e.relatedTarget)) return;      // the focus went to one of its own chips (the keyboard, or a click that took it): the field is still open
      // The mouse events a touch ends with can take the focus back right after it opened: that is not a tap away, so the field stays open. It is not refocused from here (iOS refuses
      // a focus() outside a user activation): if the keyboard went down, the field is still there and a tap on it brings the keyboard back.
      if (o.settle && !left && Date.now() - born < o.settle && !over) return;
      setTimeout(function () { commit(true); }, 0);
    });
    try { input.focus({ preventScroll: true }); } catch (e) { input.focus(); }
    input.select();
    setTimeout(function () { if (!over && input.isConnected) input.scrollIntoView({ block: 'center', behavior: 'auto' }); }, 320);      // above the phone's keyboard
    return { input: input };
  }

  // ---- taps: a double tap on a title edits it ---------------------------------------------------------------------------------------
  function inRect(n, x, y, pad) { var r = n.getBoundingClientRect(); return x >= r.left - pad && x <= r.right + pad && y >= r.top - pad && y <= r.bottom + pad; }
  CZ.tap = function (b, e) {
    if (!editing() || b.classList.contains('is-editing')) return;
    var t = b.querySelector('.cz-gb-t');
    if (!t || !inRect(t, e.clientX, e.clientY, 10)) { lastTap = null; return; }
    var now = Date.now();
    if (lastTap && lastTap.b === b && now - lastTap.at < 330) {
      lastTap = null;
      clearTimeout(opening);
      CZ.guard(500, b);                                            // neither tap opens the block
      setTimeout(function () { rename(b); }, 80);                   // after the mouse events a tap ends with, which would take the focus straight back
      return;
    }
    lastTap = { b: b, at: now };
  };
  // A park block's single tap on its title waits a moment for a second tap; every other tap opens at once.
  document.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('.cz-gb-open') : null;
    if (!a || !editing() || !lastTap || a.dataset.go) return;
    var b = a.closest('.cz-gb');
    if (lastTap.b !== b || Date.now() - lastTap.at > 120) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    opening = setTimeout(function () { lastTap = null; a.dataset.go = '1'; a.click(); delete a.dataset.go; }, 330);
  }, true);

  // ---- from the grid ------------------------------------------------------------------------------------------------------------
  CZ.hold = function (b) { open(b, null); };
  CZ.rename = rename;
  CZ.titleField = titleField;      // day_new.js (F-101) types a new plan's title into the same field
  stage.addEventListener('cz:swap', function (e) {
    if (!menu) return;
    var b = e.detail && e.detail.quiet ? stage.querySelector('.cz-gb[data-act="' + menu.act + '"]') : null;
    if (!b) { close(false); return; }                               // somewhere else, or the plan is gone
    var node = menu.node, id = menu.focusId;                        // a nudge replaced the page behind the menu: put the same menu back on the same block, on the same item
    stage.appendChild(node);
    menu.block = b;
    b.classList.add('is-menu');
    if (!CZ.reduced.matches) b.classList.add('is-wiggle');
    syncNudges(node, bounds(b));
    place(node, b);
    var again = (id && node.querySelector('[data-do="' + id + '"]:not(:disabled)')) || node.querySelector('.cz-mi:not(:disabled)');
    if (again) { try { again.focus({ preventScroll: true }); } catch (err) { again.focus(); } }
  });
})();
