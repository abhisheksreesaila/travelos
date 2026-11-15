// Guides in context (F-263, D-730..): a guide opened beside the decision, in a sheet over booking's matrix or planning's calendar, without losing your place.
// A "Guides for <place>" row in the rail (`data-sheet`, the address of its sheet, /guides/sheet, gitaway/pages/guidesheet.py) opens the sheet: on a phone it grows out of the row and folds back
// into it (GA.motion.open/close, the v2 springs, with a dimmed page); on a laptop (the calm rule: from 1020px up, not the installed app) it is a short fade, a panel beside the page that
// does not dim it. The page behind is never touched, so closing returns you where you were: the same scroll, the same opened square, the drawer as it was, and the focus on the row.
// In the sheet a stop opens in place (never a sheet on a sheet). Over planning, "+" and "Add this morning to Sat" post to /guides/add (editors only) and the calendar redraws itself
// (the event pl:changed, assets/js/v2plan.js); the toast has the Undo, and on a phone the sheet shrinks to a bar so you can watch the stops land. Every time is a token (--motion-desk,
// --v2-fold, --v2-sheet) read with getComputedStyle: no script writes one.
(function () {
  'use strict';
  var page = document.querySelector('.ga-page') || document.body;
  var cur = null, loaded = {};
  var PHONE = matchMedia('(max-width: 719px)');
  var CALM = matchMedia('(min-width: 1020px) and (not (display-mode: standalone))');
  var RM = matchMedia('(prefers-reduced-motion: reduce)');
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function el(tag, cls) { var e = document.createElement(tag); if (cls) e.className = cls; return e; }
  function ms(token) { var v = getComputedStyle(document.documentElement).getPropertyValue(token).trim(); return RM.matches ? 0 : (v.slice(-2) === 'ms' ? parseFloat(v) : parseFloat(v) * 1000) || 0; }
  function motion() { return window.GA && window.GA.motion; }
  function toast(text, opts) { if (window.GA && GA.toast && text) GA.toast(text, opts || {}); }
  var CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12l5 5 9-10"/></svg>';
  var PLUS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>';

  // the sheet's own styles (the guide page's run sheet) load once, when the first sheet opens
  function styles(list) {
    return Promise.all((list || []).map(function (href) {
      if (!loaded[href]) {
        loaded[href] = new Promise(function (done) {
          if ($('link[href="' + href + '"]')) return done();
          var l = el('link'); l.rel = 'stylesheet'; l.href = href; l.onload = l.onerror = function () { done(); }; document.head.appendChild(l);
        });
      }
      return loaded[href];
    }));
  }

  function post(url, fields) {
    var body = new FormData();
    Object.keys(fields).forEach(function (k) { [].concat(fields[k]).forEach(function (v) { body.append(k, v); }); });
    return fetch(url, { method: 'POST', body: body, credentials: 'same-origin' }).then(function (r) {
      return r.json().catch(function () { return { error: 'That did not work.' }; }).then(function (j) { j.status = r.status; return j; });
    }).catch(function () { return { error: 'Could not reach the server. Check your connection and try again.' }; });
  }

  // ---- opening and closing ----
  function open(from) {
    if (cur || from.getAttribute('aria-busy') === 'true') return;
    // The row can be reached under another dialog by keyboard (a modal sheet or popover only has a scrim) and beside the planning drawer on a laptop: never a sheet on a sheet.
    var other = $$('[role=dialog]').some(function (d) { if (d.classList.contains('gsheet')) return false; var st = getComputedStyle(d); return !d.hidden && st.display !== 'none' && st.visibility !== 'hidden'; });
    if (other) return toast('Close this first, then open the guide.', { error: true });
    from.setAttribute('aria-busy', 'true');
    fetch(from.dataset.sheet, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || 'That guide did not open.'); return j; }); })
      .then(function (j) { return styles(j.css).then(function () { return j; }); })
      .then(function (j) { from.removeAttribute('aria-busy'); show(j, from); })
      .catch(function (e) { from.removeAttribute('aria-busy'); toast(e.message || 'That guide did not open. Try again.', { error: true }); });
  }

  function show(j, from) {
    var scrim = el('div', 'gs-scrim'), sheet = el('aside', 'gsheet cv g');
    var modal = PHONE.matches, calm = CALM.matches || !motion();
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-label', 'Guide: ' + j.title);
    sheet.setAttribute('aria-modal', modal ? 'true' : 'false');
    sheet.innerHTML = j.html;
    scrim.classList.toggle('dim', modal);
    page.appendChild(scrim);
    page.appendChild(sheet);
    var inner = $('.gs-in', sheet);
    cur = { el: sheet, scrim: scrim, from: from, slug: inner.dataset.slug, ctx: inner.dataset.ctx, calm: calm, undo: [] };
    if (calm) { sheet.classList.add('is-calm'); void sheet.offsetWidth; sheet.classList.add('on'); }
    else motion().open(sheet, from, { scrim: scrim, content: inner, radius: [16, 28] });
    scrim.addEventListener('click', function () { if (PHONE.matches) close(); });
    sheet.addEventListener('click', onClick);
    $('.gs-body', sheet).addEventListener('scroll', follow, { passive: true });
    var first = $('[data-close]', sheet);
    if (first) first.focus({ preventScroll: true });
  }

  function close() {
    if (!cur) return;
    var c = cur, from = c.from && document.body.contains(c.from) ? c.from : null;
    cur = null;
    var gone = function () { c.el.remove(); c.scrim.remove(); };
    c.scrim.classList.remove('dim');
    if (c.calm) { c.el.classList.remove('on'); setTimeout(gone, ms('--motion-desk')); }
    else motion().close(c.el, from, { scrim: c.scrim }).then(gone);
    if (from) from.focus({ preventScroll: true });      // exactly where you were: the page was never scrolled, so the focus returns without moving it
  }

  // ---- a stop opens in place ----
  function setStop(card, on) {
    card.classList.toggle('is-open', on);
    var more = $('.g-inplace', card);
    if (more) { if (on) more.removeAttribute('inert'); else more.setAttribute('inert', ''); }
    $$('.g-open', card).forEach(function (b) { b.setAttribute('aria-expanded', on ? 'true' : 'false'); });
  }
  function toggleStop(card) {
    var on = !card.classList.contains('is-open');
    $$('.g-card.is-open', cur.el).forEach(function (c) { if (c !== card) setStop(c, false); });
    setStop(card, on);
    if (on) setTimeout(function () { reveal(card); }, ms('--v2-fold'));
  }
  function reveal(card) {      // bring the opened stop into view inside the sheet only (scrollIntoView could move the page behind it)
    if (!cur) return;
    var body = $('.gs-body', cur.el), b = body.getBoundingClientRect(), r = card.getBoundingClientRect(), strip = $('.g-strip', cur.el), top = b.top + (strip ? strip.offsetHeight : 0) + 8;
    if (r.bottom > b.bottom - 8) body.scrollBy({ top: Math.min(r.bottom - b.bottom + 16, r.top - top), behavior: RM.matches ? 'auto' : 'smooth' });
    else if (r.top < top) body.scrollBy({ top: r.top - top, behavior: RM.matches ? 'auto' : 'smooth' });
  }

  // ---- the day strip ----
  function press(n) { $$('.dbtn', cur.el).forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.day === String(n) ? 'true' : 'false'); }); }
  function toDay(n) {
    var d = $('#g-day' + n, cur.el), body = $('.gs-body', cur.el), strip = $('.g-strip', cur.el);
    if (!d) return;
    press(n);
    body.scrollTo({ top: d.offsetTop - (strip ? strip.offsetHeight : 0) - 12, behavior: RM.matches ? 'auto' : 'smooth' });
  }
  var ticking = false;
  function follow() {
    if (ticking || !cur) return;
    ticking = true;
    requestAnimationFrame(function () {
      ticking = false;
      if (!cur) return;
      var body = $('.gs-body', cur.el), strip = $('.g-strip', cur.el), edge = body.scrollTop + (strip ? strip.offsetHeight : 0) + 40, on = null;
      $$('.g-day', cur.el).forEach(function (d) { if (d.offsetTop <= edge) on = d.dataset.day; });
      if (on) press(on);
    });
  }

  // ---- Add to my plan ----
  function mark(keys, on) {
    keys.forEach(function (k) {
      $$('.g-plus[data-add="' + k + '"], .g-inplace .go[data-add="' + k + '"]', cur ? cur.el : document).forEach(function (b) {
        if (b.classList.contains('g-plus')) { b.classList.toggle('done', on); b.innerHTML = on ? CHECK : PLUS; b.setAttribute('aria-label', on ? 'Added to your plan' : 'Add to my plan'); }
        else if (on) { b.dataset.was = b.innerHTML; b.innerHTML = CHECK + 'Added to your plan'; b.disabled = true; }
        else if (b.dataset.was) { b.innerHTML = b.dataset.was; b.disabled = false; }
      });
    });
  }
  function ran(btn, on) {      // the free time's button says it is done, and what it was again after an Undo
    if (on) { btn.dataset.was = btn.innerHTML; btn.innerHTML = CHECK + 'Added to ' + btn.dataset.when; btn.disabled = true; }
    else if (btn.dataset.was) { btn.innerHTML = btn.dataset.was; btn.disabled = false; }
  }
  function undo(added) {
    return function () {
      var c = cur, gone = [], failed = null;      // the server judges each undo (someone may have changed the plan since): stop at the first refusal and say its words
      added.slice().reverse().reduce(function (p, a) {
        return p.then(function () {
          if (failed) return;
          return post('/trip/plan/write', { op: 'undo', undo: JSON.stringify(a.undo) }).then(function (j) { if (j.error || j.status >= 400) failed = j.error || 'That did not work.'; else gone.push(a); });
        });
      }, Promise.resolve()).then(function () {
        if (gone.length) document.dispatchEvent(new CustomEvent('pl:changed'));
        if (gone.length && c && c === cur) { mark(gone.map(function (a) { return a.key; }), false); if (!failed) $$('[data-add-day]', cur.el).forEach(function (b) { ran(b, false); }); }
        if (failed) toast(failed, { error: true }); else toast('Taken out of your plan');
      });
    };
  }
  function add(keys, extra, btn) {
    var c = cur, fields = { slug: c.slug, k: keys };
    Object.keys(extra || {}).forEach(function (k) { fields[k] = extra[k]; });
    btn.disabled = true;
    post('/guides/add', fields).then(function (j) {
      if (j.error) { btn.disabled = false; toast(j.error, { error: true }); return; }
      var added = j.added || [];
      if (!added.length) btn.disabled = false;
      if (c === cur) { mark(added.map(function (a) { return a.key; }), true); if (added.length && btn.hasAttribute('data-add-day')) ran(btn, true); }
      if (added.length) document.dispatchEvent(new CustomEvent('pl:changed', { detail: { plans: added } }));
      toast(j.toast, added.length ? { undo: undo(added) } : {});
      if (added.length && c === cur && PHONE.matches) peek(true);      // watch them land
    });
  }
  function peek(on) {
    var s = cur.el;
    s.classList.toggle('peek', on);
    s.setAttribute('aria-modal', on ? 'false' : String(PHONE.matches));
    cur.scrim.classList.toggle('dim', !on && PHONE.matches);
    if (!on) { var b = $('[data-close]', s); if (b) b.focus({ preventScroll: true }); }
  }

  function onClick(e) {
    var t = e.target;
    if (t.closest('[data-close]')) return close();
    if (t.closest('[data-unpeek]')) return peek(false);
    var open_ = t.closest('.g-open');
    if (open_) return toggleStop(open_.closest('.g-card'));
    var day = t.closest('.dbtn');
    if (day) return toDay(day.dataset.day);
    var one = t.closest('[data-add]');
    if (one) return add([one.dataset.add], {}, one);
    var run = t.closest('[data-add-day]');
    if (run) return add(run.dataset.addDay.split(' '), { to: run.dataset.to, after: run.dataset.after }, run);
  }

  document.addEventListener('click', function (e) {
    var row = e.target.closest('[data-sheet]');
    if (!row) return;
    e.preventDefault();
    open(row);
  });
  document.addEventListener('keydown', function (e) {      // in the capture phase: Escape closes only the sheet, never the opened square or the drawer behind it (their own handlers never see it)
    if (!cur) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); return close(); }
    if (e.key !== 'Tab' || cur.el.getAttribute('aria-modal') !== 'true') return;
    var f = $$('button:not(:disabled), a[href], [tabindex="0"]', cur.el).filter(function (n) { return n.offsetParent && !n.closest('[inert]'); });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (!cur.el.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }, true);
})();
