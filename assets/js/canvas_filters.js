// The trip canvas, filters (F-082, F-093; a module since F-128). Loaded after canvas_core.js.
//   The people / list chips (.cz-fchip) highlight what matches and dim the rest.
//   The All | Plans | Hotels | Flights | Car | Chats row (.cz-kchip) shows only what matches on the week and the day.
// Each is one choice, remembered per person and trip in localStorage (and for the page when storage is missing), applied on every swap (CZ.onSwap).
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var stage = CZ.stage, view = CZ.view;

  function store(key) {
    var chosen = null;      // the choice made on this page; storage may be missing (a private window), and then it still lasts until the page is left
    return {
      get: function () {
        if (chosen !== null) return chosen;
        try { return localStorage.getItem(key()) || 'all'; } catch (e) { return 'all'; }
      },
      set: function (v) {
        chosen = v;
        try { if (v === 'all') localStorage.removeItem(key()); else localStorage.setItem(key(), v); } catch (e) { /* not stored */ }
      }
    };
  }
  function keyFor(name) { return function () { return name + ':' + (stage.dataset.trip || '') + ':' + (stage.dataset.me || ''); }; }

  // ---- people and lists: highlight what matches, dim the rest ----------------------------------------------------------------
  var filter = store(keyFor('cz-filter'));
  function matches(n, f) {
    if (f.indexOf('list:') === 0) return (n.dataset.lists || '').split(' ').indexOf(f.slice(5)) >= 0;
    var who = [];
    try { who = JSON.parse(n.dataset.who || '[]'); } catch (e) { who = []; }
    return who.length === 0 || who.indexOf(f.slice(4)) >= 0;      // a step for everyone is for each person
  }
  function applyFilter() {
    var v = view();
    var bar = v && v.querySelector('.cz-filters');
    if (!bar) return;
    var chips = Array.prototype.slice.call(bar.querySelectorAll('[data-f]'));
    var f = filter.get();
    if (!chips.some(function (c) { return c.dataset.f === f; })) f = 'all';
    chips.forEach(function (c) { c.setAttribute('aria-pressed', c.dataset.f === f ? 'true' : 'false'); });
    var on = f !== 'all';
    v.classList.toggle('cz-flt-on', on);
    v.querySelectorAll('[data-who][data-lists]').forEach(function (n) {
      var hit = on && matches(n, f);
      n.classList.toggle('is-hit', hit);
      n.classList.toggle('is-dim', on && !hit);
    });
    v.querySelectorAll('.cz-listmore').forEach(function (n) { n.hidden = f !== 'list:' + n.dataset.list; });
  }
  document.addEventListener('click', function (e) {
    var chip = e.target.closest ? e.target.closest('.cz-fchip') : null;
    if (!chip || !stage.contains(chip)) return;
    filter.set(chip.getAttribute('aria-pressed') === 'true' ? 'all' : chip.dataset.f);
    applyFilter();
  });

  // ---- kinds: the week and the day show only what matches ----------------------------------------------------------------------
  var KIND_WORD = { plan: 'plans', hotel: 'hotels', flight: 'flights', car: 'the car', chat: 'chats' };
  var kind = store(keyFor('cz-kind'));
  function applyKinds() {
    var v = view();
    var bar = v && v.querySelector('.cz-kinds');
    if (!bar) return;
    bar.hidden = false;                   // drawn hidden: without script the buttons would do nothing
    var k = kind.get();
    if (!bar.querySelector('[data-k="' + k + '"]')) k = 'all';
    bar.querySelectorAll('[data-k]').forEach(function (c) { c.setAttribute('aria-pressed', c.dataset.k === k ? 'true' : 'false'); });
    v.dataset.k = k;
    var on = k !== 'all';
    var hit = function (n) { return k === 'chat' ? n.dataset.chat === '1' : n.dataset.kind === k; };
    v.querySelectorAll('.cz-row').forEach(function (row) {      // the week's day cards: an item that does not match goes (its bar segment too); a card with nothing to show is a thin line
      var shown = 0;
      row.querySelectorAll('.cz-wcard[data-kind]').forEach(function (n) {
        var ok = !on || hit(n);
        n.classList.toggle('is-off', !ok);
        row.querySelectorAll('.cz-mb-seg[data-n="' + n.dataset.n + '"]').forEach(function (seg) { seg.classList.toggle('is-off', !ok); });
        if (ok) shown++;
      });
      var thin = on && shown === 0;
      row.classList.toggle('is-thin', thin);
      var t = row.querySelector('.cz-thin-t');
      if (t) t.textContent = thin ? 'Nothing for ' + (KIND_WORD[k] || k) : '';
    });
    v.querySelectorAll('.cz-wcol').forEach(function (col) {      // F-145: the desktop week's columns: a row that does not match is hidden, a column with none says so
      var shown = 0, rows = col.querySelectorAll('[data-kind]');
      rows.forEach(function (n) { var ok = !on || hit(n); n.classList.toggle('is-off', !ok); if (ok) shown++; });
      var none = col.querySelector('.cz-wnone');
      if (none) none.textContent = on && rows.length && shown === 0 ? 'Nothing for ' + (KIND_WORD[k] || k) : '';
      col.classList.toggle('is-none', on && rows.length > 0 && shown === 0);
    });
    var main = v.querySelector('.cz-day-main');                  // the day
    if (main) {
      var seen = 0;
      v.querySelectorAll('.cz-day-body [data-kind], .cz-now[data-kind]').forEach(function (n) {
        var ok = !on || (n.dataset.kind !== 'now' && n.dataset.kind !== 'empty' && hit(n));
        n.classList.toggle('is-off', !ok);
        if (ok && on) seen++;
      });
      v.querySelectorAll('.cz-part').forEach(function (p) { p.classList.toggle('is-off', k === 'chat' && p.dataset.chat !== '1'); });
      var none = main.querySelector('.cz-kind-none');
      if (none) none.hidden = !(on && seen === 0);
      tidyRail(v);
    }
  }
  // F-160: what a filter hides leaves nothing behind on the rail or in the "+N more" cards. A start label whose plans are all hidden goes (the laptop's too); a "+N more" card counts only the plans
  // behind it that still show, and goes at none; an hour label that a printed start no longer covers comes back.
  function planOf(id) { return stage.querySelector('.cz-gb[data-act="' + id + '"], .cz-gbk[data-zk="bkg-' + id + '"]'); }
  function tidyRail(v) {
    v.querySelectorAll('.cz-g-start[data-for]').forEach(function (s) {
      var live = s.dataset['for'].split(' ').some(function (id) { var b = planOf(id); return b && !b.classList.contains('is-off'); });
      s.classList.toggle('is-off', !live);
    });
    v.querySelectorAll('.cz-lanemore').forEach(function (c) {
      var n = c.dataset.more.split(' ').filter(function (id) { var b = planOf(id); return b && !b.classList.contains('is-off'); }).length;
      c.classList.toggle('is-off', n === 0);
      var t = c.querySelector('.cz-lanemore-t');
      if (t && n) t.textContent = '+' + n + ' more';
    });
    var grid = v.querySelector('#cz-grid'), room = grid ? parseFloat(grid.style.getPropertyValue('--rail')) || 35 : 35;
    var starts = Array.prototype.filter.call(v.querySelectorAll('.cz-g-start'), function (s) { return !s.classList.contains('is-off') && getComputedStyle(s).display !== 'none'; })
      .map(function (s) { return parseFloat(s.style.getPropertyValue('--s')); });
    v.querySelectorAll('.cz-g-hour.is-near').forEach(function (h) {
      var at = parseFloat(h.style.getPropertyValue('--s'));
      h.classList.toggle('is-clear', !starts.some(function (y) { return at - y >= -30 && at - y <= room + 8; }));
    });
  }
  document.addEventListener('click', function (e) {
    var chip = e.target.closest ? e.target.closest('.cz-kchip') : null;
    if (!chip || !stage.contains(chip)) return;
    kind.set(chip.dataset.k);
    applyKinds();
  });

  // F-115: a plan just made is never hidden by the filter (Chats, Hotels ...): the day goes back to All.
  CZ.showPlans = function () { var k = kind.get(); if (k !== 'all' && k !== 'plan') { kind.set('all'); applyKinds(); } };
  CZ.onSwap.push(applyFilter, applyKinds);
  applyFilter();
  applyKinds();

  // F-162: a week card's title that does not fit its card is faded at the edge (week_desk.css .is-cut), so a cut is never silent. One ResizeObserver on the titles covers a card shown again by the
  // filter (it measured 0 while hidden), a resize and a new swap (the titles are observed anew); the fonts arriving change the text, not the box, so they re-measure too.
  var ro = window.ResizeObserver ? new ResizeObserver(function (list) { markCuts(list.map(function (e) { return e.target; })); }) : null;
  function markCuts(ts) {      // F-173: every title is measured, then every mark is written (a read after a write makes the browser lay the page out again, once per title)
    var cut = Array.prototype.map.call(ts, function (t) { return t.clientWidth ? t.scrollHeight > t.clientHeight + 1 || t.scrollWidth > t.clientWidth + 1 : null; });
    Array.prototype.forEach.call(ts, function (t, i) { if (cut[i] !== null) t.classList.toggle('is-cut', cut[i]); });
  }
  function watchCuts() {
    var titles = document.querySelectorAll('.cz-wk .cz-wi-t, .cz-week .cz-wr-t');
    if (ro) { ro.disconnect(); titles.forEach(function (t) { ro.observe(t); }); }
    markCuts(titles);
  }
  CZ.onSwap.push(watchCuts);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(watchCuts);
  watchCuts();
})();
