// The hotel as a decision dashboard (F-282, D-895..D-899): what the page's script adds to the server's dashboard, fine print and review drawer (gitaway/pages/hotelview.py, fineprint.py,
// reviewdrawer.py). Nothing here is a fact of its own: every number and word comes from the offers and answers the server drew (data attributes on the chosen room and flight, the hotel's
// check-in, the pins route), and anything missing says "not listed".
//   - the rows that depend on the choice (fees paid at the hotel, breakfast, refundability, the flight's landing against check-in, the drive from the airport and "what the stay really
//     costs", shown only when the chosen room has a real amount paid at the hotel) are rewritten each time assets/js/v2drawer.js says the choice changed (`dr:changed`) or a hotel's page
//     arrived (`dr:rich`);
//   - "Getting there and around" asks the pins route once, when it scrolls into view (the server reads OpenStreetMap, F-284), and draws the heads-ups and the top pins from its answer;
//   - the review drawer: opened from the score, the last-100 strip or a complaint, filtered by traveller type (and by a complaint's reviews), Escape and the close button fold it back into
//     what was tapped and give that its focus back. Motion is GA.motion's (reduced motion: it simply appears); durations and easings are the page's tokens.
(function () {
  'use strict';
  var PINS = '/plan/matrix/aerial/pins', HEADS_UP = 'Heads up', EARLY_MIN = 180;      // a flight landing this long before check-in is worth a flag
  var ICON = {
    check: '<path d="M5 12l5 5L20 7"/>', flag: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.01"/>', arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>'
  };
  var KINDS = ['flight', 'road', 'water', 'shop', 'park'];      // the pins worth a line (restaurants are the card's)

  function q(el, sel) { return el.querySelector(sel); }
  function qa(el, sel) { return Array.prototype.slice.call(el.querySelectorAll(sel)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function svg(n) { return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICON[n] + '</svg>'; }
  function money(c) { var r = c % 100; return '$' + (r === 0 ? Math.round(c / 100).toLocaleString('en-US') : (c / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })); }
  function motion() { return window.GA && window.GA.motion; }

  // ---- one row of the fine print, drawn the way the server draws it ----
  function rowHtml(cls, title, note, flag) {
    var mark = flag ? 'flag' : cls.indexOf('is-ok') >= 0 ? 'check' : 'info';
    return '<span class="fp-m" aria-hidden="true">' + svg(mark) + '</span><div><span class="fp-t">' + esc(title) + (flag ? '<span class="fp-flag">' + HEADS_UP + '</span>' : '') + '</span>' +
      (note ? '<p class="fp-n">' + esc(note) + '</p>' : '') + '</div>';
  }
  function setRow(fp, key, cls, title, note, flag) {
    var el = q(fp, '[data-live="' + key + '"]');
    if (!el) return;
    el.className = 'fp-i ' + cls;
    el.innerHTML = rowHtml(cls, title, note, flag);
  }
  function count(fp) {
    var n = qa(fp, '.fp-i.is-hu').length, c = q(fp, '[data-count]');
    if (c) c.textContent = n ? n + (n === 1 ? ' thing to know' : ' things to know') : '';
  }

  // ---- what the chosen room and flight say ----
  function minutes(clock) {
    var m = /^\s*(\d{1,2}):(\d{2})\s*([AP]M)\s*$/i.exec(clock || '');
    return m ? (parseInt(m[1], 10) % 12 + (m[3].toUpperCase() === 'PM' ? 12 : 0)) * 60 + parseInt(m[2], 10) : null;
  }
  function span(min) { var h = Math.floor(min / 60), m = min % 60; return ((h ? h + ' h ' : '') + (m ? m + ' min' : '')).trim(); }
  function clockWords(min) { var h = Math.floor(min / 60), m = min % 60, ap = h >= 12 ? 'PM' : 'AM'; return (h % 12 || 12) + ':' + (m < 10 ? '0' : '') + m + ' ' + ap; }

  function update(slot) {
    var fp = q(slot, '.fp');
    if (!fp) return;
    var pane = slot.closest('.dr-sp'), dr = slot.closest('.dr');
    if (!pane || !dr) return;
    var rooms = slot.dataset['for'] != null ? '.dr-rooms[data-for="' + slot.dataset['for'] + '"]' : '.dr-rooms:not([hidden])';
    var room = q(pane, rooms + ' .dr-opt[aria-checked="true"]'), fl = q(dr, '.dr-fly .dr-opt[aria-checked="true"]');
    var due = room ? parseInt(room.dataset.due, 10) || 0 : 0, price = room ? parseInt(room.dataset.c, 10) || 0 : 0;
    if (!room) setRow(fp, 'due', 'is-no', 'Paid at the hotel: not listed');
    else if (due > 0) setRow(fp, 'due', 'is-hu', 'Paid at the hotel: ' + money(due), 'Fees the price leaves out, listed by LiteAPI for this room', true);
    else setRow(fp, 'due', 'is-no', 'Fees paid at the hotel: none listed', 'For this room');
    var board = room ? room.dataset.board : '';
    if (!board) setRow(fp, 'board', 'is-no', 'Breakfast: not listed');
    else if (board === 'breakfast') setRow(fp, 'board', 'is-ok', 'Breakfast is included in this room’s price');
    else if (board === 'room only') setRow(fp, 'board', 'is-plain', 'Breakfast is not in this room’s price');
    else setRow(fp, 'board', 'is-plain', 'Meals: ' + board, 'The offer’s own words');
    var real = q(fp, '[data-live="real"]');
    if (real) {
      real.hidden = !(room && due > 0);
      if (!real.hidden) { q(real, '[data-real="total"]').textContent = 'about ' + money(price + due); q(real, '[data-real="words"]').textContent = money(price) + ' for the room, plus ' + money(due) + ' paid at the hotel.'; }
    }
    if (!room) setRow(fp, 'refund', 'is-no', 'Refundability: not listed');
    else if (room.dataset.refund) setRow(fp, 'refund', 'is-ok', 'Refundable', 'LiteAPI marks this room’s rate refundable');
    else setRow(fp, 'refund', 'is-hu', 'Non-refundable', 'LiteAPI marks this room’s rate non-refundable', true);
    var inn = fp.dataset.checkin === '' ? null : parseInt(fp.dataset.checkin, 10), land = fl ? minutes(fl.dataset.land) : null, first = pane.dataset.stayI === '0';
    if (!first || inn == null || isNaN(inn) || land == null) setRow(fp, 'landing', 'is-no', 'Check-in against your flight: not listed');
    else if (fl.dataset.landNext) setRow(fp, 'landing', 'is-plain', 'Your flight lands at ' + clockWords(land) + ' the next day', 'Check-in is from ' + clockWords(inn));
    else if (inn - land >= EARLY_MIN) setRow(fp, 'landing', 'is-hu', 'Your flight lands ' + clockWords(land) + ', ' + span(inn - land) + ' before check-in', 'Rooms are ready from ' + clockWords(inn), true);
    else if (inn > land) setRow(fp, 'landing', 'is-ok', 'Your flight lands ' + clockWords(land) + ', ' + span(inn - land) + ' before check-in', 'Rooms are ready from ' + clockWords(inn));
    else setRow(fp, 'landing', 'is-ok', 'Your flight lands ' + clockWords(land) + ', after check-in opens at ' + clockWords(inn));
    var drive = parseInt(slot.dataset.drive, 10);
    if (drive > 0) setRow(fp, 'drive', 'is-ok', drive + ' min from the airport', 'By car, to this town');
    else setRow(fp, 'drive', 'is-no', 'Drive from the airport: not listed');
    count(fp);
  }
  function updateAll(root) { qa(root, '.dr-rich[data-state="done"], .dr-sampleslot').forEach(update); }
  document.addEventListener('dr:changed', function (e) { updateAll(e.target); });
  document.addEventListener('dr:rich', function (e) { update(e.target); watchPins(e.target); });

  // ---- getting there and around: the pins, asked once when the card scrolls into view ----
  var io = null;
  function watchPins(slot) {
    var box = q(slot, '[data-pins]');
    if (!box || box.dataset.watching) return;
    box.dataset.watching = '1';
    if (!('IntersectionObserver' in window)) { askPins(slot, box); return; }
    io = io || new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { io.unobserve(e.target); askPins(e.target.closest('.dr-rich, .dr-sampleslot'), e.target); } });
    }, { rootMargin: '200px' });
    io.observe(box);
  }
  function askPins(slot, box) {
    var card = q(slot, '.av-card');
    if (!card || !card.dataset.aerial) { box.innerHTML = '<div class="fp-i is-no">' + rowHtml('is-no', 'Pins around the hotel: not listed', 'LiteAPI gave no place for this hotel') + '</div>'; return; }
    fetch(PINS + '?id=' + encodeURIComponent(card.dataset.aerial), { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (j) { paintPins(slot, box, j); })
      .catch(function () { paintPins(slot, box, { ok: false, message: 'The pins could not be loaded just now.' }); });
  }
  function paintPins(slot, box, j) {
    if (!j.ok) { box.innerHTML = '<p class="fp-n">' + esc(j.message || 'Nothing is known about the surroundings just now.') + '</p>'; return; }
    var out = (j.heads || []).map(function (h) {
      return '<div class="fp-i ' + (h.good ? 'is-ok' : 'is-hu') + '">' + rowHtml(h.good ? 'is-ok' : 'is-hu', h.text, h.more, !h.good) + '</div>';
    });
    (j.pins || []).filter(function (p) { return KINDS.indexOf(p.kind) >= 0; }).forEach(function (p) {
      if (p.m == null) { out.push('<div class="fp-i is-no">' + rowHtml('is-no', p.title, p.sub) + '</div>'); return; }
      out.push('<div class="fp-i is-plain fp-pin"><span class="fp-m" aria-hidden="true">' + svg('info') + '</span><div><span class="fp-t">' + esc(p.title) + '</span><p class="fp-n">' + esc(p.sub) +
        '</p></div><span class="fp-d num">' + esc(p.far) + ' ' + esc(p.by) + '<small>' + esc(p.dist) + '</small></span></div>');
    });
    out.push('<p class="fp-n">' + esc(j.source_text || '') + '</p>');
    box.innerHTML = out.join('');
    var fp = slot.closest('.fp') || q(slot, '.fp');
    if (fp) count(fp);
  }

  // ---- the review drawer ----
  var cur = null;      // { aside, scrim, from, slot }
  function host() { return document.querySelector('.ga-page') || document.body; }
  function filter(aside, type, ids, why, words) {
    var want = ids ? ids.split(',').filter(Boolean) : null, shown = 0;
    qa(aside, '.rv-item').forEach(function (it) {
      var ok = (!want || want.indexOf(it.dataset.i) >= 0) && (!type || it.dataset.type === type);
      it.hidden = !ok;
      if (ok) shown++;
    });
    qa(aside, '.rv-chip').forEach(function (c) { c.setAttribute('aria-pressed', c.dataset.rvType === type ? 'true' : 'false'); });
    var bar = q(aside, '.rv-filter');
    bar.hidden = !want;
    if (want) q(bar, '.rv-why').textContent = want.length + (want.length === 1 ? ' review mentions ' : ' reviews mention ') + (words || 'it') + ' · about “' + why + '”' + (type ? ' · ' + shown + ' shown' : '');      // what they share, never more
    aside._ids = ids; aside._why = why; aside._words = words;
    q(aside, '.rv-body').scrollTop = 0;
  }
  function openDrawer(slot, from, ids, why, words) {
    var aside = slot._rv || q(slot, '.rv');
    if (!aside) return;
    if (cur) return;
    slot._rv = aside;
    if (aside.parentNode !== host()) host().appendChild(aside);      // out of the page's flow, still inside the .v2 page (its buttons press)
    var scrim = document.createElement('div');
    scrim.className = 'rv-scrim';
    scrim.addEventListener('click', closeDrawer);
    host().appendChild(scrim);
    filter(aside, '', ids, why, words);
    aside.hidden = false;
    document.body.classList.add('rv-open');
    cur = { aside: aside, scrim: scrim, from: from, slot: slot };
    var m = motion();
    if (m) m.open(aside, from, { scrim: scrim, content: q(aside, '.rv-body'), radius: [20, window.matchMedia('(max-width: 47.9375rem)').matches ? 0 : 28] });
    q(aside, '.rv-x').focus({ preventScroll: true });
  }
  function closeDrawer() {
    if (!cur) return;
    var c = cur;
    cur = null;
    var done = function () { c.aside.hidden = true; c.scrim.remove(); document.body.classList.remove('rv-open'); };
    var from = c.from && c.from.isConnected ? c.from : null, m = motion();
    if (m) m.close(c.aside, from, { scrim: c.scrim }).then(done); else done();
    if (from) from.focus({ preventScroll: true });
  }
  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('[data-rv-open], [data-rv-type], [data-rv-close]');
    if (!t) return;
    if (t.hasAttribute('data-rv-close')) { closeDrawer(); return; }
    if (t.hasAttribute('data-rv-type')) {
      var aside = t.closest('.rv');
      if (aside) filter(aside, t.dataset.rvType, t.classList.contains('rv-all') ? '' : aside._ids, aside._why, aside._words);
      return;
    }
    var slot = t.closest('.dr-rich, .dr-sampleslot');
    if (slot) openDrawer(slot, t, t.dataset.rvOpen === 'some' ? t.dataset.rvIds : '', t.dataset.rvWhy || '', t.dataset.rvWords || '');
  });
  document.addEventListener('keydown', function (e) {
    if (!cur) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeDrawer(); return; }
    if (e.key !== 'Tab') return;
    var f = qa(cur.aside, 'button').filter(function (b) { return b.offsetParent !== null; });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && (document.activeElement === first || !cur.aside.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }, true);

  // the showcase's hotel dashboard arrives with the drawer (no fetch): paint what it depends on once the drawer has painted its state
  qa(document, '.dr-sampleslot').forEach(function (s) { watchPins(s); });
  document.addEventListener('mx:drawer', function (e) { qa(e.detail.box, '.dr-sampleslot').forEach(function (s) { watchPins(s); }); });
})();
