// The drawer (F-251, D-620): an opened square, the prototype's drawer (docs/design/booking-v2/index.html). assets/js/tripmatrix.js puts the server's drawer (gitaway/pages/v2drawer.py) in
// #mx-drawer and asks `V2D.grow` to make it flow down out of the square's column on the page's springs; this script then does what a drawer does:
//   - choose in place: a hotel (the alternatives strip), a room of that hotel, a flight; the total counts to its new value and every other number follows (the Book button's, the mini summaries,
//     the budget words). Every option was drawn by the server with its own price; nothing is priced here. The forms' three fields carry only indexes: fl, st (the hotel of each stay) and rm
//     (its room), which the server reads again and prices itself (gitaway/tripmatrix.py `pick`); a held room is bound to its choice (pages/matrixbook.py).
//   - one thing at a time (F-258, D-670): the stay is open, the flights a summary card; tapping a summary opens that side in place and folds the other to its summary. Nothing else changes
//     it: choosing, the gallery and the tabs never move a side, at any width, and nothing here moves keyboard focus or the scroll.
//   - the hotel gallery: scroll or the arrows; two stays (a two-place trip) are two tabs.
// Durations and easings are the page's tokens (--v2-*), read here with getComputedStyle; reduced motion: nothing moves.
(function () {
  var RM = window.matchMedia('(prefers-reduced-motion: reduce)'), phone = window.matchMedia('(max-width: 719px)');
  function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  function ms(n) { return parseFloat(tok(n)) || 0; }
  function q(el, sel) { return el.querySelector(sel); }
  function qa(el, sel) { return Array.prototype.slice.call(el.querySelectorAll(sel)); }
  function dollars(c) { return '$' + Math.floor((c + 50) / 100).toLocaleString('en-US'); }
  function signed(c) { return c === 0 ? 'same' : (c > 0 ? '+' : '−') + dollars(Math.abs(c)); }

  function state(dr) {
    if (!dr._s) {
      var n = qa(dr, '.dr-sp').length;
      dr._s = { fl: 0, hotel: [], room: [], tab: 0, open: 'stay' };
      for (var i = 0; i < n; i++) { dr._s.hotel.push(0); dr._s.room.push(0); }
    }
    return dr._s;
  }
  function cents(el) { return parseInt(el && el.dataset.c, 10) || 0; }
  function pane(dr, i) { return q(dr, '.dr-sp[data-stay-i="' + i + '"]'); }
  function roomOf(dr, i) { var s = state(dr), r = q(pane(dr, i), '.dr-rooms[data-for="' + s.hotel[i] + '"] .dr-opt[data-room="' + s.room[i] + '"]'); return r; }
  function flightOf(dr) { return q(dr, '.dr-fly .dr-opt[data-fl="' + state(dr).fl + '"]'); }
  function total(dr) { var t = cents(flightOf(dr)); qa(dr, '.dr-sp').forEach(function (p, i) { t += cents(roomOf(dr, i)); }); return t; }

  function countTo(el, from, to) {
    if (!el) return;
    if (RM.matches || from === to) { el.textContent = dollars(to); return; }
    var t0 = performance.now(), dur = ms('--v2-count');
    (function step(now) {
      var p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      el.textContent = dollars(from + (to - from) * e);
      if (p < 1) requestAnimationFrame(step);
    })(t0);
  }
  function fade(el) {
    if (RM.matches || !el) return;
    var kf = [{ opacity: 0, transform: 'translateY(0.5rem)' }, { opacity: 1, transform: 'none' }];
    el.animate(kf, { duration: ms('--v2-swap'), easing: tok('--v2-ease') });
  }

  // paint the state: which hotel, room and flight show, every delta, the total and what depends on it, the forms' fields
  function apply(dr, what) {
    var s = state(dr), before = parseInt(dr.dataset.total, 10);
    qa(dr, '.dr-sp').forEach(function (p, i) {
      p.hidden = i !== s.tab;
      qa(p, '.dr-hotel').forEach(function (h) { h.hidden = parseInt(h.dataset.hotelI, 10) !== s.hotel[i]; });
      qa(p, '.dr-rooms, .dr-rich').forEach(function (l) { l.hidden = parseInt(l.dataset.for, 10) !== s.hotel[i]; });
      var now = cents(roomOf(dr, i));
      qa(p, '.dr-rooms:not([hidden]) .dr-opt').forEach(function (b) { mark(b, parseInt(b.dataset.room, 10) === s.room[i], cents(b) - now); });
      qa(p, '.dr-alt').forEach(function (b) { mark(b, parseInt(b.dataset.hotel, 10) === s.hotel[i], cents(b) - now); });
    });
    var fl = cents(flightOf(dr));
    qa(dr, '.dr-fly .dr-opt').forEach(function (b) { mark(b, parseInt(b.dataset.fl, 10) === s.fl, cents(b) - fl); });
    qa(dr, '.dr-flt').forEach(function (f) { f.hidden = parseInt(f.dataset.fltI, 10) !== s.fl; });
    qa(dr, '.dr-seg button').forEach(function (b) { b.setAttribute('aria-pressed', parseInt(b.dataset.tab, 10) === s.tab ? 'true' : 'false'); });
    var t = total(dr), names = [], rooms = [], price = 0;
    qa(dr, '.dr-sp').forEach(function (p, i) { names.push(q(p, '.dr-hotel:not([hidden])').dataset.name); rooms.push(roomOf(dr, i).dataset.roomname); price += cents(roomOf(dr, i)); });
    set(dr, 'stay-name', names.join(' + '));
    set(dr, 'stay-room', rooms[0]);
    set(dr, 'stay-price', moneyOf(price));
    var f = flightOf(dr);
    set(dr, 'fly-times', f.dataset.times);
    set(dr, 'fly-al', f.dataset.al + ' · ' + f.dataset.stops);
    set(dr, 'fly-price', moneyOf(fl));
    qa(dr, '[data-pick="fl"]').forEach(function (e) { e.value = String(s.fl); });
    qa(dr, '[data-pick="st"]').forEach(function (e) { e.value = s.hotel.join(','); });
    qa(dr, '[data-pick="rm"]').forEach(function (e) { e.value = s.room.join(','); });
    var changed = s.fl || s.hotel.some(Boolean) || s.room.some(Boolean);
    dr.dataset.changed = changed ? '1' : '';
    var vs = q(dr, '[data-vs]');
    if (vs) vs.hidden = !!changed;      // "+$145 vs San Diego alone" was for the trip shown first
    var bud = q(dr, '[data-budget]');
    if (bud) { var gap = parseInt(bud.dataset.budget, 10) * 100 - t; bud.textContent = dollars(Math.abs(gap)) + (gap >= 0 ? ' under' : ' over') + ' your ' + dollars(parseInt(bud.dataset.budget, 10) * 100); }
    if (!isNaN(before) && before !== t) { qa(dr, '[data-slot="total"], [data-mirror="total"]').forEach(function (e) { countTo(e, before, t); }); }
    else qa(dr, '[data-slot="total"], [data-mirror="total"]').forEach(function (e) { e.textContent = dollars(t); });
    dr.dataset.total = String(t);
    (what || []).forEach(function (sel) { qa(dr, sel).forEach(fade); });
    loadRich(dr);
    dr.dispatchEvent(new CustomEvent('dr:changed', { bubbles: true }));      // F-282: the fine print follows the room and flight now chosen (assets/js/hotelfine.js)
  }

  // ---- the hotel's own photos, words and reviews (F-275, D-860): asked when the hotel is shown, never for a square nobody opened; kept for the next time ----
  var richKept = {};
  function loadRich(dr) {
    qa(dr, '.dr-sp:not([hidden]) .dr-rich:not([hidden])[data-state="idle"]').forEach(function (slot) {
      var id = slot.dataset.hid;
      if (!id) return;
      slot.dataset.state = 'loading';
      (richKept[id] = richKept[id] || fetch('/plan/matrix/hotel?id=' + encodeURIComponent(id) + (slot.dataset.pt ? '&pt=' + encodeURIComponent(slot.dataset.pt) : ''), { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (j) { return j.html || ''; }))
        .then(function (html) {
          if (!html) { slot.dataset.state = 'none'; slot.hidden = true; return; }
          slot.innerHTML = html;
          slot.dataset.state = 'done';
          var hotel = q(slot.closest('.dr-sp'), '.dr-hotel[data-hotel-i="' + slot.dataset.for + '"]');
          if (hotel) hotel.classList.add('has-rich');      // its mosaic replaces the one-photo gallery
          roomThumbs(slot);
          fade(slot);
          slot.dispatchEvent(new CustomEvent('dr:rich', { bubbles: true }));      // F-282: the hotel's page is in: its fine print reads the chosen room and flight
        })
        .catch(function () { delete richKept[id]; slot.dataset.state = 'none'; slot.hidden = true; });      // nothing came: the hotel is what the search gave, as before
    });
  }
  function roomThumbs(slot) {      // a room you can choose wears the hotel's photo of it when the offer and the hotel call it the same
    var holder = q(slot, '.dr-roomphotos'), map = {};
    try { map = holder ? JSON.parse(holder.textContent) : {}; } catch (e) { map = {}; }
    qa(slot.closest('.dr-sp'), '.dr-rooms[data-for="' + slot.dataset.for + '"] .dr-opt').forEach(function (b) {
      var url = map[(b.dataset.roomname || '').toLowerCase()];
      if (!url || q(b, '.dr-rthumb')) return;
      var img = document.createElement('img');
      img.className = 'dr-rthumb'; img.alt = ''; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer'; img.src = url;
      b.insertBefore(img, q(b, '.dr-tx'));
    });
  }

  // ---- the lightbox: every photo of the hotel, one at a time (arrows, a swipe, Esc) ----
  var lb = null, lbPhotos = [], lbAt = 0, lbFrom = null;
  function lbShow(i) {
    lbAt = (i + lbPhotos.length) % lbPhotos.length;
    var p = lbPhotos[lbAt];
    q(lb, 'img').src = p.src; q(lb, 'img').alt = p.cap || 'Hotel photo';
    q(lb, 'figcaption').textContent = p.cap || '';
    q(lb, '.dr-lb-c').textContent = (lbAt + 1) + ' of ' + lbPhotos.length;
  }
  function lbMake() {
    lb = document.createElement('dialog');
    lb.className = 'dr-lb';
    lb.setAttribute('aria-label', 'Photos of the hotel');
    lb.innerHTML = '<button type="button" class="dr-lb-x" aria-label="Close photos">✕</button><button type="button" class="dr-lb-n l" data-go="-1" aria-label="Previous photo">‹</button>' +
      '<figure><img alt=""><figcaption></figcaption></figure><button type="button" class="dr-lb-n r" data-go="1" aria-label="Next photo">›</button><p class="dr-lb-c" aria-live="polite"></p>';
    document.body.appendChild(lb);
    lb.addEventListener('click', function (e) {
      if (e.target === lb || e.target.closest('.dr-lb-x')) { lb.close(); return; }
      var go = e.target.closest('[data-go]');
      if (go) lbShow(lbAt + parseInt(go.dataset.go, 10));
    });
    lb.addEventListener('close', function () { if (lbFrom && lbFrom.isConnected) lbFrom.focus({ preventScroll: true }); });
    lb.addEventListener('keydown', function (e) { if (e.key === 'ArrowLeft') lbShow(lbAt - 1); else if (e.key === 'ArrowRight') lbShow(lbAt + 1); });
    var x0 = null;
    lb.addEventListener('pointerdown', function (e) { x0 = e.clientX; });
    lb.addEventListener('pointerup', function (e) { if (x0 !== null && Math.abs(e.clientX - x0) > 48) lbShow(lbAt + (e.clientX < x0 ? 1 : -1)); x0 = null; });
  }
  document.addEventListener('click', function (e) {
    var ph = e.target.closest && e.target.closest('.dr-photos [data-lb]');
    if (!ph) return;
    var all = qa(ph.closest('.dr-photos'), '[data-lb]');
    lbPhotos = all.map(function (b) { return { src: b.dataset.src, cap: b.dataset.cap }; });
    if (!lb) lbMake();
    lbFrom = ph;
    lbShow(all.indexOf(ph));
    if (!lb.open) lb.showModal();
  });
  function moneyOf(c) { var d = Math.floor(c / 100), r = c % 100; return '$' + (r === 0 ? d.toLocaleString('en-US') : (c / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })); }
  function set(dr, k, text) { qa(dr, '[data-m="' + k + '"]').forEach(function (e) { e.textContent = text; }); }
  function mark(b, on, diff) {
    b.setAttribute('aria-checked', on ? 'true' : 'false');
    var d = b.querySelector('[data-d]');
    if (!d) return;
    d.textContent = on ? 'Chosen' : signed(diff);
    d.classList.toggle('is-minus', !on && diff < 0);
  }

  // one side open, the other its summary: the open one's content fades in, the panels' height follows (calm: fade and height only)
  function setOpen(dr) {
    var o = state(dr).open, panels = q(dr, '.dr-panels');
    panels.dataset.open = o;
    qa(panels, '.dr-pn').forEach(function (p) { p.classList.toggle('is-mini', p.dataset.pane !== o); });
  }
  function open(dr, who) {
    var s = state(dr);
    if (s.open === who) return;
    var panels = q(dr, '.dr-panels'), h0 = panels.offsetHeight;
    s.open = who;
    setOpen(dr);
    if (RM.matches) return;
    var h1 = panels.offsetHeight, d = ms('--v2-fold'), e = tok('--v2-ease');
    panels.classList.add('is-folding');
    var a = panels.animate([{ height: h0 + 'px' }, { height: h1 + 'px' }], { duration: d, easing: e });
    a.onfinish = a.oncancel = function () { panels.classList.remove('is-folding'); };
    qa(dr, '.dr-pn:not(.is-mini) .dr-full, .dr-pn.is-mini .dr-mini').forEach(function (x) { x.animate([{ opacity: 0 }, { opacity: 1 }], { duration: d, easing: e }); });
  }

  document.addEventListener('click', function (e) {
    var dr = e.target.closest && e.target.closest('#mx-drawer .dr, .dr-alone .dr');
    if (!dr) return;
    var s = state(dr), t = e.target.closest('button, .dr-mini');
    if (!t) { var pn = e.target.closest('.dr-pn.is-mini'); if (pn) open(dr, pn.dataset.pane); return; }
    if (t.dataset.act === 'close') { document.dispatchEvent(new CustomEvent('mx:close')); return; }
    if (t.dataset.galGo) { var tr = q(t.closest('.dr-gal'), '.dr-track'); tr.scrollBy({ left: parseInt(t.dataset.galGo, 10) * tr.clientWidth, behavior: RM.matches ? 'auto' : 'smooth' }); return; }
    if (t.dataset.tab) { s.tab = parseInt(t.dataset.tab, 10); apply(dr, ['.dr-sp:not([hidden])']); return; }
    if (t.dataset.room) { var i = s.tab; s.room[i] = parseInt(t.dataset.room, 10); apply(dr); return; }
    if (t.dataset.hotel) { var h = s.tab; s.hotel[h] = parseInt(t.dataset.hotel, 10); s.room[h] = 0; apply(dr, ['.dr-hotel:not([hidden])', '.dr-rooms:not([hidden])']); return; }
    if (t.dataset.fl) { s.fl = parseInt(t.dataset.fl, 10); apply(dr, ['.dr-flt:not([hidden])']); return; }
    if (t.classList.contains('dr-mini')) open(dr, t.dataset.show);
  });
  document.addEventListener('keydown', function (e) {
    var m = e.target.closest && e.target.closest('.dr-mini');
    if (m && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); open(m.closest('.dr'), m.dataset.show); }
  });
  document.addEventListener('scroll', function (e) {      // the gallery's dots follow its scroll
    var g = e.target;
    if (!g || !g.classList || !g.classList.contains('dr-track')) return;
    var i = Math.round(g.scrollLeft / g.clientWidth);
    qa(g.parentNode, '.dr-dots span').forEach(function (d, j) { d.classList.toggle('on', j === i); });
  }, true);

  // a drawer was put in the page (tripmatrix.js): paint its state
  function ready(dr) {
    if (!dr || !dr.classList.contains('dr') || dr.classList.contains('is-quiet')) return;
    dr.dataset.total = '';
    var why = q(dr, '.dr-why');
    if (why) why.hidden = !why.textContent.replace(/Our pick:/, '').trim();      // nothing known to say: no empty pill
    setOpen(dr);
    apply(dr);
  }
  document.addEventListener('mx:drawer', function (e) { ready(e.detail.box.firstElementChild); });
  qa(document, '.dr-alone .dr').forEach(ready);      // the square's own page

  // ---- the drawer flows down out of the square's column on the spring ----
  window.V2D = {
    grow: function (box, from, o) {
      var dr = box.firstElementChild;
      if (!dr) return;
      box.dataset.from = from && from.dataset ? (from.dataset.sq || '') : box.dataset.from || '';
      if (RM.matches) { if (!o.refill) dr.scrollIntoView({ block: 'nearest' }); return; }
      if (!o.refill) {
        var r = dr.getBoundingClientRect(), c = (from || dr).getBoundingClientRect();
        var left = Math.max(0, c.left - r.left), right = Math.max(0, r.right - c.right), drop = Math.min(90, r.height);
        var kf = [{ clipPath: 'inset(0 ' + right + 'px calc(100% - ' + drop + 'px) ' + left + 'px round 1.125rem)', transform: 'translateY(-1.625rem)' }, { clipPath: 'inset(0 0 0 0 round 2rem)', transform: 'none' }];
        dr.animate(kf, { duration: ms(o.again ? '--v2-drawer-again' : '--v2-drawer'), easing: tok('--spring-soft') });
        qa(dr, '.dr-head, .dr-panels, .dr-foot').forEach(function (x, i) {
          var part = [{ opacity: 0, transform: 'translateY(0.875rem)' }, { opacity: 1, transform: 'none' }];
          x.animate(part, { duration: ms('--v2-drawer-in'), delay: ms('--v2-drawer-stagger') * (i + 2), easing: tok('--v2-ease'), fill: 'backwards' });
        });
        requestAnimationFrame(function () {
          var top = dr.getBoundingClientRect().top + window.scrollY - (phone.matches ? 12 : 20);
          window.scrollTo({ top: top, behavior: 'smooth' });
        });
      }
    },
    away: function (box, done) {
      var dr = box.firstElementChild;
      if (!dr || RM.matches) return done();
      var kf = [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-1rem) scale(.985)' }];
      var a = dr.animate(kf, { duration: ms('--v2-drawer-out'), easing: tok('--v2-ease') });
      a.onfinish = done;
    },
  };
})();
