// Tap a plan: its note and its chat, right there (F-106). A tap (not a hold) on a block of the day grid expands the block, in place, into a card over the grid: the whole note on top
// as the sticky (an editor taps one of their own notes to edit it right there, or "Add a note"), then the plan's chat (the latest few messages, "Earlier" for more, the box with text,
// photo and mic), and for a park block a "Rides" link to its block level. Tap outside, Escape or a swipe down on the card's top folds it back into the block.
//
// How it fits. The card's body is a fragment the server draws (GET /trip/canvas/card, gitaway/pages/daycard.py), fetched as soon as a finger goes down on a block, so the tap that
// follows has nothing to wait for; the card opens at once with the title and time and fills in when the fragment arrives. The chat is the chat page's own markup and scripts
// (thread.js, plantalk.js, voicenote.js), loaded the first time a card opens and bound again for each card; a folded card's chat stops polling by itself. The card lives beside the
// stage (not in it), so a refresh of the day behind it (after a note is saved) never takes it away; CZ.editing keeps the quiet revalidation off while it is open.
//
// Motion. The card grows from the block's own rectangle with a short spring (a transform on one layer; its words fade in a moment later, so nothing is seen squashed), the rest of the
// day dims, and a fold runs it backwards into the block. Reduced motion: no spring, an instant change. Holds, drags, resizes, the hold menu and hold-on-empty-time are not touched: the
// card only answers the click that a tap makes (the click a held block makes is already guarded by trip_canvas.js, CZ.guard).
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var stage = CZ.stage;
  var main = document.getElementById('main') || document.body;
  var SPRING = 'cubic-bezier(.3, 1.35, .5, 1)', OUT = 'cubic-bezier(.4, 0, .8, .4)';
  var open = null;                 // the card on screen: { wrap, card, scrim, block, act, folding, note }
  var fetched = {};                // act -> { at, promise }: the fragment fetched ahead of the tap
  var voiceLoaded = false;

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
  function geometry(wrap, r) {
    var vv = window.visualViewport, u = rem();
    var vw = wrap.clientWidth, floor = wrap.clientHeight, top0 = parseFloat(getComputedStyle(wrap).paddingTop) || 0;
    var topMin = top0 + u * 0.5;
    if (vv) { topMin = Math.max(topMin, vv.offsetTop + u * 0.5); floor = Math.min(floor, vv.offsetTop + vv.height); }
    floor -= u * 0.5;
    var h = Math.min(u * 34, Math.max(u * 12, floor - topMin));
    var w = Math.min(u * 30, vw - u);
    var top = clamp(r ? r.top - u * 0.25 : topMin, topMin, Math.max(topMin, floor - h));
    var left = clamp(r ? r.left : (vw - w) / 2, u * 0.5, Math.max(u * 0.5, vw - w - u * 0.5));
    return { left: left, top: top, width: w, height: h };
  }
  function place(o, g) {
    o.card.style.left = g.left + 'px'; o.card.style.top = g.top + 'px'; o.card.style.width = g.width + 'px'; o.card.style.height = g.height + 'px';
    o.g = g;
  }
  function squash(g, r) {          // the transform that makes the card look like the block it grows from
    return 'translate(' + (r.left - g.left) + 'px,' + (r.top - g.top) + 'px) scale(' + (r.width / g.width) + ',' + (r.height / g.height) + ')';
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
    body.appendChild(mk('p', 'cz-card-loading', 'Opening the note and chat'));
    content.appendChild(grab); content.appendChild(head); content.appendChild(body);
    card.appendChild(content);
    wrap.appendChild(scrim); wrap.appendChild(card);
    main.appendChild(wrap);
    stage.setAttribute('inert', '');
    open = { wrap: wrap, card: card, scrim: scrim, content: content, body: body, block: block, act: act, folding: false };
    block.classList.add('is-card');
    place(open, geometry(wrap, r));
    CZ.cardOpen = true;
    if (!CZ.reduced.matches && card.animate) {
      card.style.transformOrigin = '0 0';
      card.animate([{ transform: squash(open.g, r), borderRadius: '0.875rem' }, { transform: 'none', borderRadius: '1.75rem' }], { duration: 380, easing: SPRING });
      scrim.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 220, easing: 'ease-out' });
      content.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 160, delay: 110, easing: 'ease-out', fill: 'backwards' });
    }
    try { card.focus({ preventScroll: true }); } catch (e) { /* no focus */ }
    scrim.addEventListener('click', function () { fold(); });
    x.addEventListener('click', function () { fold(); });
    swipe(open, [grab, head]);
    fetchCard(act).then(function (html) { if (open && open.card === card) fill(open, html); }, function () {
      if (!open || open.card !== card) return;
      body.removeAttribute('aria-busy');
      body.textContent = '';
      var p = mk('p', 'cz-card-loading', 'The note and chat could not load. ');
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
    var chat = inner.querySelector('#ft');
    if (chat) { bindEarlier(o, chat); chatScripts(); }
    o.card.dispatchEvent(new CustomEvent('cz:cardready', { bubbles: true }));
  }

  // The chat's own scripts bind to the ids in the fragment: thread.js polls and sends, plantalk.js has the photo button and the mic. They run again for each card (the old card's chat
  // sees it is gone and stops); voicenote.js is one listener on the document, so it loads once.
  function chatScripts() {
    function add(src, then) {
      var s = document.createElement('script');
      s.src = src; s.async = false;
      s.onload = s.onerror = function () { s.remove(); if (then) then(); };
      document.body.appendChild(s);
    }
    if (!voiceLoaded) { voiceLoaded = true; add('/assets/js/voicenote.js'); }
    add('/assets/js/thread.js');
    add('/assets/js/plantalk.js');
  }

  // "Earlier": the messages before the oldest one shown, put above it without moving what is being read.
  function bindEarlier(o, chat) {
    var more = chat.querySelector('#cz-card-earlier'), thread = chat.querySelector('#ft-thread'), box = chat.querySelector('.cz-card-scroll');
    if (!more || !thread || !box) return;
    var busy = false;
    more.addEventListener('click', function () {
      if (busy) return;
      busy = true; more.disabled = true;
      var url = '/trip/talk/items?act=' + encodeURIComponent(o.act) + '&before=' + encodeURIComponent(thread.getAttribute('data-first') || '0') + '&limit=8' + (trip() ? '&trip=' + encodeURIComponent(trip()) : '');
      fetch(url, { credentials: 'same-origin', headers: { Accept: 'text/html' } }).then(function (r) {
        if (!r.ok) throw new Error('earlier');
        var first = r.headers.get('X-Thread-First'), left = r.headers.get('X-Thread-More') === '1';
        return r.text().then(function (html) {
          var holder = document.createElement('div');
          holder.innerHTML = html;
          var before = box.scrollHeight, top = box.scrollTop;
          Array.prototype.slice.call(holder.children).reverse().forEach(function (el) { thread.insertBefore(el, thread.firstChild); });
          box.scrollTop = top + (box.scrollHeight - before);
          if (first) thread.setAttribute('data-first', first);
          thread.setAttribute('data-more', left ? '1' : '0');
          if (!left) more.remove(); else { more.disabled = false; busy = false; }
        });
      }).catch(function () { more.disabled = false; busy = false; });
    });
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
    function size() { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight + 2, rem() * 9) + 'px'; }
    function finish(restore) {
      over = true; o.note = null;
      n.classList.remove('is-editing');
      n.textContent = '';
      restore.forEach(function (c) { n.appendChild(c); });
      if (n.dataset.mine === '1') { n.setAttribute('role', 'button'); n.tabIndex = 0; }
    }
    function cancel() { if (over) return; finish(keep); }
    o.cancelNote = cancel;
    function commit() {
      if (over) return;
      if (sending) return;
      var v = ta.value.replace(/\s+/g, ' ').trim();
      if (!v || v === was) { cancel(); return; }
      sending = true;
      ta.disabled = true;
      CZ.post('/trip/canvas/actnote', CZ.tripBody({ act: o.act, text: v, note: id })).then(function (res) {
        var saved = res.note || { id: id, text: v };
        if (!over) over = true;
        o.note = null;
        n.classList.remove('is-editing');
        n.textContent = '';
        if (add) {                     // the empty sticky becomes the note, and a quiet "Add a note" follows it
          var again = n.cloneNode(false);
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
        sending = false;
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
  function recording() { return !!(open && open.card.querySelector('#pt-rec:not([hidden])')); }      // a voice note being recorded is not thrown away by a stray tap

  function cleanup() {
    var o = open;
    if (!o) return;
    var chat = o.card.querySelector('#ft');
    if (chat) chat.dispatchEvent(new Event('ft-close'));
    o.wrap.remove();
    stage.removeAttribute('inert');
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
    if (!o || o.folding || recording()) return;
    if (o.note) { try { o.note.blur(); } catch (e) { /* the note saves as it loses the focus */ } }
    o.folding = true;
    var act = o.act, card = o.card;
    var done = function () { cleanup(); focusBlock(act); };
    var b = blockOf(act), r = b ? b.getBoundingClientRect() : null;
    if (CZ.reduced.matches || !card.animate) { done(); return; }
    var to = r && r.bottom > 0 && r.top < window.innerHeight ? squash(o.g, r) : 'translateY(' + (window.innerHeight * 0.1) + 'px) scale(.9)';
    var a = card.animate([{ transform: from || card.style.transform || 'none', opacity: 1 }, { transform: to, opacity: 0.2 }], { duration: 240, easing: OUT, fill: 'forwards' });
    o.content.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 110, easing: 'ease-in', fill: 'forwards' });
    o.scrim.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 240, easing: 'ease-in', fill: 'forwards' });
    a.onfinish = done;
    setTimeout(function () { if (open === o) done(); }, 400);
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
        var back = o.card.animate([{ transform: 'translateY(' + dy + 'px)' }, { transform: 'none' }], { duration: 260, easing: SPRING });
        o.card.style.transform = '';
        back.onfinish = function () { o.card.style.transform = ''; };
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

  // The iPhone keyboard shrinks the visual viewport, not the page: the card stays inside what is left, the newest message stays in view above the box.
  var vv = window.visualViewport;
  function refit() {
    if (!open || open.folding) return;
    var g = geometry(open.wrap, null);
    var r = open.block && open.block.isConnected ? open.block.getBoundingClientRect() : null;
    place(open, geometry(open.wrap, r));
    var box = open.card.querySelector('.cz-card-scroll');
    if (box && document.activeElement && document.activeElement.id === 'ft-text') box.scrollTop = box.scrollHeight;
  }
  if (vv) { vv.addEventListener('resize', refit); vv.addEventListener('scroll', refit); }
  window.addEventListener('resize', refit);

  // Anything that leaves the day (Rides, Back, a date) takes the card with it; a refresh of the same day (after a write) does not.
  stage.addEventListener('cz:swap', function (e) { if (open && !(e.detail && e.detail.quiet)) closeNow(); });
  window.addEventListener('pagehide', function () { if (open) closeNow(); });

  var before = CZ.editing;
  CZ.editing = function () { return !!open || (before ? before() : false); };      // trip_canvas.js never swaps the day under an open card (typing, a message being sent)
  CZ.openCard = show;
  CZ.foldCard = fold;
})();
