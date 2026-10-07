// The hold menu, rename in place and delete on the day grid (F-098). Needs trip_canvas.js and day_grid.js, which load first and hand over two moments:
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

  function open(b, focusItem, kbd) {
    if (!editing() || !b || !b.isConnected) return;
    close(false);
    var steps = +b.dataset.steps || 0, k = bounds(b);
    var node = mk('div', 'cz-menu');
    node.setAttribute('role', 'menu');
    node.tabIndex = -1;
    node.setAttribute('aria-label', titleOf(b) + ': what to do');
    node.appendChild(mk('p', 'cz-menu-t', titleOf(b)));
    var main = mk('div', 'cz-menu-main');
    var chat = item('chat', 'Chat', 'chat', { id: 'chat' });
    chat.href = b.dataset.talk || '#';
    main.appendChild(chat);
    main.appendChild(item('rename', 'Rename', 'pencil', { id: 'rename' }));
    main.appendChild(item('delete', 'Delete', 'trash', { id: 'delete' }));
    node.appendChild(main);
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
    syncNudges(node, k);
    node.addEventListener('focusin', function (e) { if (menu && e.target.dataset && e.target.dataset.do) menu.focusId = e.target.dataset.do; });
    stage.appendChild(node);
    menu = { block: b, act: b.dataset.act, node: node, focusId: focusItem || '' };
    CZ.menuOpen = true;
    b.classList.add('is-menu');
    if (!CZ.reduced.matches) b.classList.add('is-wiggle');
    place(node, b);
    if (MO) MO.open(node, b);       // F-109: it grows out of the block that was held
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
    var y = br.bottom + 8;
    if (y + h > floor) y = br.top - h - 8;
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
    var k = bounds(b), s = k.s, en = k.e, d = nstep();
    if (what === 'fine') { fineOn = !fineOn; syncNudges(menu.node, k); return; }
    if (what === 'earlier') { s -= d; en -= d; }
    else if (what === 'later') { s += d; en += d; }
    else if (what === 'shorter') en -= d;
    else if (what === 'longer') en += d;
    if (s < k.lo || en > k.hi || en - s < MIN_LEN) return;
    CZ.setTimes(b, s, en);              // the menu stays for the next nudge: the page behind it is brought up to date, and the menu goes back on the same block (cz:swap, below)
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
  //   o.discard          an empty title (Enter, tapping away) or Escape gives the block up: o.cancel() runs, and nothing is saved or refused
  // Returns { input }. Call it from inside the gesture's own pointerup or click when the keyboard has to open (the iOS rule, day_new.js).
  function titleField(b, o) {
    if (!editing() || !b || !b.isConnected || b.classList.contains('is-editing')) return null;
    var t = b.querySelector('.cz-gb-t');
    if (!t) return null;
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
    function away(e) { if (e.target !== input && !(e.target.closest && e.target.closest('.cz-gb-edit'))) { left = true; input.blur(); } }
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
    input.addEventListener('blur', function () {
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
