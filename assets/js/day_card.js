// Tap a plan: its note, right there (F-106, F-107). A tap (not a hold) on a block of the day grid expands the block, in place, into a card over the grid: the plan's name and time, the
// links "Open chat" (with how much was said) and, on a park block, "Rides" to its block level, then the whole note as the sticky (an editor taps one of their own notes to edit it right
// there, or "Add a note"). No messages and no box in it: the chat is its own page. Tap outside, Escape or a swipe down on the card's top folds it back into the block.
//
// How it fits. The card's body is a fragment the server draws (GET /trip/canvas/card, gitaway/pages/daycard.py), fetched as soon as a finger goes down on a block, so the tap that
// follows has nothing to wait for; the card opens at once with the title and time and fills in when the fragment arrives, then is as tall as its words (up to what the screen leaves).
// It always sits inside what can be seen: above the tab bar and, with the keyboard up (editing a note), above the keyboard. The card lives beside the stage (not in it), so a
// refresh of the day behind it (after a note is saved) never takes it away; CZ.editing keeps the quiet revalidation off while it is open.
//
// Motion. The card grows from the block's own rectangle with the one liquid spring (GA.motion.open, motion.js: a transform on one layer; its words fade in a moment later, so nothing is seen squashed), the rest of the
// day dims, and a fold (GA.motion.close) runs it backwards into the block. Reduced motion: no spring, an instant change. Holds, drags, resizes, the hold menu and hold-on-empty-time are not touched: the
// card only answers the click that a tap makes (the click a held block makes is already guarded by trip_canvas.js, CZ.guard).
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var stage = CZ.stage;
  var main = document.getElementById('main') || document.body;
  var MO = (window.GA && GA.motion) || (function () { var r = function () { return Promise.resolve(); }; return { open: r, close: r, spring: r, flip: r, run: r, settle: r, reflow: function (e, c, o) { c(); if (o && o.during) o.during(); return r(); }, origin: function () { return null; }, box: function (e) { return e.getBoundingClientRect(); }, reduced: function () { return true; }, t: function () { return 240; } }; })();      // (a page without motion.js still works: everything is instant) the one liquid motion (motion.js, F-109): the spring, the fold and their timings are its tokens
  var open = null;                 // the card on screen: { wrap, card, scrim, block, act, folding, note }
  var fetched = {};                // act -> { at, promise }: the fragment fetched ahead of the tap

  function rem() { return parseFloat(getComputedStyle(document.documentElement).fontSize) || 16; }
  function clamp(v, lo, hi) { return Math.min(Math.max(v, lo), hi); }
  function mk(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; }
  function svg(path) {
    var s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor'); s.setAttribute('stroke-width', '2.4');
    s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round'); s.setAttribute('aria-hidden', 'true');
    var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', path);
    s.appendChild(p);
    return s;
  }
  function trip() { return stage.dataset.trip || ''; }
  function blockOf(act) { return stage.querySelector('.cz-gb[data-act="' + act + '"]'); }

  // ---- the fragment -------------------------------------------------------------------------------------------------------
  function cardUrl(act) { return '/trip/canvas/card?act=' + encodeURIComponent(act) + (trip() ? '&trip=' + encodeURIComponent(trip()) : ''); }
  function fetchCard(act) {
    var hit = fetched[act];
    if (hit && Date.now() - hit.at < 8000) return hit.promise;
    var p = fetch(cardUrl(act), { credentials: 'same-origin', headers: { 'X-Canvas': '1' } }).then(function (r) {
      if (!r.ok) throw new Error('card ' + r.status);
      return r.text();
    });
    fetched[act] = { at: Date.now(), promise: p };
    p.catch(function () { delete fetched[act]; });
    return p;
  }
  document.addEventListener('pointerdown', function (e) {
    if (open || !e.target.closest) return;
    var a = e.target.closest('.cz-gb-open[data-card]');
    if (a && stage.contains(a)) { var b = a.closest('.cz-gb'); if (b && b.dataset.act) fetchCard(b.dataset.act).catch(function () {}); }
  }, { passive: true });

  // ---- where the card goes ------------------------------------------------------------------------------------------------------
  // Over the block, as wide as the screen allows (a laptop: a column), as tall as the screen allows up to about 34 rem, and always inside what can be seen: above the tab bar and,
  // with the keyboard up, above the keyboard. `r` is the block's rectangle.
  // The card is as tall as its words (up to `max`) and never lower than the tab bar's top or the keyboard's: `max` is what is left between the strip above and the floor.
  function geometry(wrap, r) {
    var vv = window.visualViewport, u = rem();
    var kb = !!vv && vv.height < window.innerHeight - 80;          // the keyboard is up: every bit of height is needed; otherwise a strip of the day stays above the card to tap
    var tabs = document.querySelector('.ph-tabs'), reserve = !kb && tabs && getComputedStyle(tabs).display !== 'none' ? tabs.offsetHeight : 0;      // the tab bar steps aside for the keyboard
    var vw = wrap.clientWidth, floor = wrap.clientHeight - reserve, top0 = parseFloat(getComputedStyle(wrap).paddingTop) || 0;
    var topMin = top0 + u * (kb ? 0.5 : 4);
    if (vv) { topMin = Math.max(topMin, vv.offsetTop + u * 0.5); floor = Math.min(floor, vv.offsetTop + vv.height); }
    floor -= u * 0.5;
    var w = Math.min(u * 30, vw - u);
    var left = clamp(r ? r.left : (vw - w) / 2, u * 0.5, Math.max(u * 0.5, vw - w - u * 0.5));
    return { left: left, width: w, topMin: topMin, floor: floor, max: Math.min(u * 34, Math.max(u * 6, floor - topMin)), r: r };
  }
  function place(o, g, glide) {
    var c = o.card, u = rem(), was = o.g;
    c.style.left = g.left + 'px'; c.style.width = g.width + 'px'; c.style.maxHeight = g.max + 'px'; c.style.height = 'auto';
    var h = Math.min(c.offsetHeight, g.max);                       // as tall as what is in it
    var top = clamp(g.r ? g.r.top - u * 0.25 : g.topMin, g.topMin, Math.max(g.topMin, g.floor - h));
    c.style.top = top + 'px'; c.style.height = h + 'px';
    o.g = { left: g.left, top: top, width: g.width, height: h };
    if (glide && was && !CZ.reduced.matches && c.animate && !c.getAnimations().length && (Math.abs(was.top - top) > 1 || Math.abs(was.height - h) > 1)) {      // the words arrived or grew: the card follows them, gently
      MO.flip(c, was, o.g);
    }
  }
  // ---- open ---------------------------------------------------------------------------------------------------------------------
  function show(block) {
    if (open || !block || !block.dataset.act) return;
    var act = block.dataset.act, r = block.getBoundingClientRect();
    var wrap = mk('div', 'cz-card-wrap'), scrim = mk('div', 'cz-card-scrim'), card = mk('div', 'cz-card');
    scrim.setAttribute('aria-hidden', 'true');
    card.setAttribute('role', 'dialog'); card.setAttribute('aria-modal', 'true'); card.setAttribute('aria-labelledby', 'cz-card-title'); card.tabIndex = -1;
    var kind = getComputedStyle(block);
    card.style.setProperty('--accent', kind.getPropertyValue('--accent') || ''); card.style.setProperty('--tint', kind.getPropertyValue('--tint') || '');
    var content = mk('div', 'cz-card-content');
    var grab = mk('div', 'cz-card-grab'); grab.setAttribute('aria-hidden', 'true'); grab.appendChild(mk('span'));
    var head = mk('header', 'cz-card-head');
    var ti = mk('div', 'cz-card-ti');
    var t = mk('h2', 'cz-card-t', block.dataset.title || 'This plan'); t.id = 'cz-card-title';
    var when = block.querySelector('.cz-gb-when');
    ti.appendChild(t);
    if (when) ti.appendChild(mk('p', 'cz-card-when', when.textContent));
    var x = mk('button', 'cz-card-x'); x.type = 'button'; x.setAttribute('aria-label', 'Close');
    x.appendChild(svg('M18 6 6 18M6 6l12 12'));
    head.appendChild(ti); head.appendChild(x);
    var body = mk('div', 'cz-card-body'); body.setAttribute('aria-busy', 'true');
    body.appendChild(mk('p', 'cz-card-loading', 'Opening the note'));
    content.appendChild(grab); content.appendChild(head); content.appendChild(body);
    card.appendChild(content);
    wrap.appendChild(scrim); wrap.appendChild(card);
    main.appendChild(wrap);
    open = { wrap: wrap, card: card, scrim: scrim, content: content, body: body, block: block, act: act, folding: false };
    block.classList.add('is-card');
    lock(open);
    place(open, geometry(wrap, r));
    CZ.cardOpen = true;
    if (!CZ.reduced.matches) MO.open(card, r, { scrim: scrim, content: content, radius: ['0.875rem', '1.75rem'] });
    try { card.focus({ preventScroll: true }); } catch (e) { /* no focus */ }
    scrim.addEventListener('click', function () { fold(); });
    x.addEventListener('click', function () { fold(); });
    swipe(open, [grab, head]);
    fetchCard(act).then(function (html) { if (open && open.card === card) fill(open, html); }, function () {
      if (!open || open.card !== card) return;
      body.removeAttribute('aria-busy');
      body.textContent = '';
      var p = mk('p', 'cz-card-loading', 'The note could not load. ');
      var a = mk('a', 'cz-card-link', 'Open chat'); a.href = block.dataset.talk || ('/trip/talk?act=' + encodeURIComponent(act));
      p.appendChild(a); body.appendChild(p);
    });
  }

  function fill(o, html) {
    o.body.removeAttribute('aria-busy');
    o.body.innerHTML = html;
    var inner = o.body.firstElementChild;
    if (!inner) return;
    bindNotes(o, inner);
    var rides = inner.querySelector('#cz-card-rides');
    if (rides) rides.addEventListener('click', function (e) {          // the old tap on a park block: zoom to its block level
      if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      var hero = blockOf(o.act), href = rides.getAttribute('href');
      closeNow();
      CZ.goto(CZ.path(href), { dir: 'in', key: hero ? 'blk-' + o.act : null, mode: 'push' });
    });
    refit(true);                                                       // the card is as tall as its note now
    o.card.dispatchEvent(new CustomEvent('cz:cardready', { bubbles: true }));
  }

  // ---- the note, in place ----------------------------------------------------------------------------------------------------
  // An editor's own note (data-mine) and "Add a note" turn into a field on the spot: Enter or tapping away saves, Escape puts it back. An empty note is not saved (nothing changes).
  function bindNotes(o, inner) {
    var area = inner.querySelector('.cz-card-notes');
    if (!area) return;
    function start(n) {
      if (!n || n.classList.contains('is-editing') || o.folding) return;
      if (n.hasAttribute('data-add') || n.dataset.mine === '1') edit(o, area, n);
    }
    area.addEventListener('click', function (e) { start(e.target.closest ? e.target.closest('.cz-card-note') : null); });
    area.addEventListener('keydown', function (e) {
      if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('cz-card-note') && e.target.dataset.mine === '1') { e.preventDefault(); start(e.target); }
    });
  }

  function edit(o, area, n) {
    var add = n.hasAttribute('data-add'), id = add ? '' : n.dataset.note;
    var was = add ? '' : n.querySelector('.cz-card-text').textContent;
    var keep = Array.prototype.slice.call(n.childNodes);
    var ta = mk('textarea', 'cz-card-edit');
    ta.rows = 2; ta.maxLength = 140; ta.value = was; ta.setAttribute('aria-label', add ? 'Write a note' : 'Edit this note');
    ta.setAttribute('enterkeyhint', 'done'); ta.setAttribute('autocapitalize', 'sentences');
    var err = mk('span', 'cz-card-err'); err.setAttribute('role', 'alert');
    n.classList.add('is-editing');
    n.removeAttribute('role'); n.removeAttribute('tabindex');
    keep.forEach(function (c) { n.removeChild(c); });
    n.appendChild(ta); n.appendChild(err);
    o.note = ta;
    var over = false, sending = false;
    o.cancelNote = null;
    function size() { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight + 2, rem() * 9) + 'px'; refit(); }
    function finish(restore) {
      over = true; o.note = null;
      n.classList.remove('is-editing');
      n.textContent = '';
      restore.forEach(function (c) { n.appendChild(c); });
      if (n.dataset.mine === '1') { n.setAttribute('role', 'button'); n.tabIndex = 0; }
    }
    function cancel() { if (over || sending) return; o.commitNote = null; finish(keep); }
    o.cancelNote = cancel;
    o.commitNote = function () { commit(); };
    function commit() {
      if (over) return;
      if (sending) return;
      var v = ta.value.replace(/\s+/g, ' ').trim();
      if (!v || v === was) { cancel(); return; }
      sending = true; o.saving = true;
      ta.disabled = true;
      CZ.post('/trip/canvas/actnote', CZ.tripBody({ act: o.act, text: v, note: id, id: add && area.dataset.next ? 'n' + area.dataset.next : undefined })).then(function (res) {
        var saved = res.note || { id: id, text: v };
        if (!over) over = true;
        o.note = null; o.saving = false; o.commitNote = null;
        if (add) area.dataset.next = String((parseInt(String(saved.id).slice(1), 10) || 0) + 1);
        n.classList.remove('is-editing');
        n.textContent = '';
        if (add) {                     // the empty sticky becomes the note, and a quiet "Add a note" follows it
          n.dataset.note = saved.id; n.dataset.mine = '1'; n.removeAttribute('data-add'); n.classList.remove('cz-card-add', 'is-empty'); n.classList.add('is-mine'); n.setAttribute('role', 'button'); n.tabIndex = 0;
          n.setAttribute('aria-label', 'Edit this note: ' + saved.text);
          n.appendChild(mk('span', 'cz-card-text', saved.text));
          var quiet = mk('button', 'cz-card-note cz-card-add'); quiet.type = 'button'; quiet.setAttribute('data-add', '1');
          quiet.appendChild(svg('M12 5v14M5 12h14')); quiet.appendChild(mk('span', '', 'Add a note'));
          n.after(quiet);
        } else {
          n.setAttribute('aria-label', 'Edit this note: ' + saved.text);
          n.appendChild(mk('span', 'cz-card-text', saved.text));
        }
        delete fetched[o.act];
        if (CZ.forget) CZ.forget();
        CZ.quiet();                    // the block behind the card shows the new words
      }, function (e) {
        sending = false; o.saving = false;
        ta.disabled = false;
        err.textContent = e && e.soft ? e.soft : 'Could not save that. Try again.';
        ta.focus();
      });
    }
    ta.addEventListener('input', function () { err.textContent = ''; size(); });
    ta.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.stopPropagation(); commit(); }
      else if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); cancel(); }
      else e.stopPropagation();
    }, true);
    ta.addEventListener('blur', function () { setTimeout(commit, 0); });
    size();
    try { ta.focus({ preventScroll: true }); } catch (e) { ta.focus(); }
    ta.setSelectionRange(ta.value.length, ta.value.length);
  }

  // ---- fold ---------------------------------------------------------------------------------------------------------------------
  // While the card is open it is the whole page: every other part of the page (the day, the heading, the tab bar) is inert, so a keyboard or a screen reader stays in the card.
  function lock(o) {
    o.locked = [];
    for (var n = o.wrap; n && n.parentElement && n !== document.documentElement; n = n.parentElement) {
      Array.prototype.forEach.call(n.parentElement.children, function (c) {
        if (c !== n && c.id !== 'ga-toast' && !c.hasAttribute('inert') && !/^(SCRIPT|STYLE|LINK|TEMPLATE)$/.test(c.tagName)) { c.setAttribute('inert', ''); o.locked.push(c); }
      });
    }
  }
  function unlock(o) { (o.locked || []).forEach(function (c) { c.removeAttribute('inert'); }); o.locked = []; }
  var TABBABLE = 'a[href], button:not([disabled]), input:not([type="hidden"]):not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Tab' || !open) return;
    var items = Array.prototype.filter.call(open.card.querySelectorAll(TABBABLE), function (n) { return !n.hidden && n.getClientRects().length > 0; });
    if (!items.length) { e.preventDefault(); return; }
    var a = document.activeElement, first = items[0], last = items[items.length - 1];
    if (!open.card.contains(a) || a === open.card) { e.preventDefault(); (e.shiftKey ? last : first).focus(); }
    else if (e.shiftKey && a === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && a === last) { e.preventDefault(); first.focus(); }
  }, true);

  function cleanup() {
    var o = open;
    if (!o) return;
    o.wrap.remove();
    unlock(o);
    o.block.classList.remove('is-card');
    open = null;
    CZ.cardOpen = false;
  }
  function closeNow() { cleanup(); }

  function focusBlock(act) {
    var b = blockOf(act), f = b && (b.querySelector('.cz-gb-open') || b);
    if (f) { try { f.focus({ preventScroll: true }); } catch (e) { f.focus(); } }
  }

  function fold(from) {
    var o = open;
    if (!o || o.folding) return;
    if (o.saving) return;                                          // a note is on its way: the card stays until it has landed (or failed, and says so)
    if (o.note && o.commitNote) { o.commitNote(); if (o.saving || o.note) return; }      // a note being edited is saved first; if that cannot be done, the card stays and shows why
    o.folding = true;
    var act = o.act, card = o.card;
    var done = function () { cleanup(); focusBlock(act); };
    var b = blockOf(act);
    if (CZ.reduced.matches || !card.animate) { done(); return; }
    MO.close(card, b, { scrim: o.scrim, content: o.content, from: from || card.style.transform || undefined, radius: ['0.875rem', '1.75rem'] }).then(done);
    setTimeout(function () { if (open === o) done(); }, MO.t('dur') + 160);
  }

  // Swipe down on the card's top (its handle and heading) folds it; a short pull springs back.
  function swipe(o, handles) {
    var s = null;
    handles.forEach(function (h) {
      h.addEventListener('pointerdown', function (e) {
        if (e.button > 0 || o.folding || e.target.closest('button, a')) return;
        s = { id: e.pointerId, y0: e.clientY, t0: Date.now(), dy: 0, el: h };
        try { h.setPointerCapture(e.pointerId); } catch (err) { /* not capturable */ }
      });
      h.addEventListener('pointermove', function (e) {
        if (!s || e.pointerId !== s.id) return;
        s.dy = Math.max(0, e.clientY - s.y0);
        o.card.style.transform = s.dy ? 'translateY(' + s.dy + 'px)' : '';
        o.scrim.style.opacity = String(Math.max(0.3, 1 - s.dy / 400));
      });
      function end(e) {
        if (!s || e.pointerId !== s.id) return;
        var dy = s.dy, quick = dy > 30 && dy / Math.max(1, Date.now() - s.t0) > 0.5;
        s = null;
        if (e.type === 'pointerup' && (dy > 90 || quick)) { fold('translateY(' + dy + 'px)'); return; }
        o.scrim.style.opacity = '';
        if (!dy) return;
        if (CZ.reduced.matches || !o.card.animate) { o.card.style.transform = ''; return; }
        o.card.style.transform = '';
        MO.spring(o.card, 'translateY(' + dy + 'px)');
      }
      h.addEventListener('pointerup', end);
      h.addEventListener('pointercancel', end);
    });
  }

  // ---- keys, taps and the keyboard ------------------------------------------------------------------------------------------------
  document.addEventListener('click', function (e) {          // a tap on a block (the click it makes), before the day's own link handling sees it
    if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || !e.target.closest) return;
    var a = e.target.closest('.cz-gb-open[data-card]');
    if (!a || !stage.contains(a) || open) return;
    var b = a.closest('.cz-gb');
    if (!b || b.classList.contains('is-editing')) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    show(b);
  }, true);

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || !open) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (open.note && open.cancelNote) { open.cancelNote(); return; }      // Escape ends a note being edited first, then the card
    fold();
  }, true);

  // The iPhone keyboard shrinks the visual viewport, not the page: the card stays inside what is left (above the keyboard, never under the tab bar), and the note being written stays in view.
  var vv = window.visualViewport;
  function refit(glide) {
    if (!open || open.folding) return;
    var r = open.block && open.block.isConnected ? open.block.getBoundingClientRect() : null;
    place(open, geometry(open.wrap, r), glide === true);
    if (open.note) open.note.scrollIntoView({ block: 'nearest' });
  }
  if (vv) { vv.addEventListener('resize', function () { refit(); }); vv.addEventListener('scroll', function () { refit(); }); }
  window.addEventListener('resize', function () { refit(); });

  // Anything that leaves the day (Rides, Back, a date) takes the card with it; a refresh of the same day (after a write) does not.
  stage.addEventListener('cz:swap', function (e) { if (open && !(e.detail && e.detail.quiet)) closeNow(); });
  window.addEventListener('pagehide', function () { if (open) closeNow(); });

  var before = CZ.editing;
  CZ.editing = function () { return !!open || (before ? before() : false); };      // trip_canvas.js never swaps the day under an open card (typing, a message being sent)
  CZ.openCard = show;
  CZ.foldCard = fold;
})();
