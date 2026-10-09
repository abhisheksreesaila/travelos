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
  var CAP = 3;            // with no filter a week row shows its first three entries and "and N more"
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
    v.querySelectorAll('.cz-row').forEach(function (row) {      // the week: a row with nothing to show is a thin line
      var shown = 0;
      row.querySelectorAll('[data-kind]').forEach(function (n) {
        var ok = on ? hit(n) : parseInt(n.dataset.n || '0', 10) < CAP;
        n.classList.toggle('is-off', !ok);
        if (ok) shown++;
      });
      var more = row.querySelector('.cz-more');
      if (more) more.hidden = on;
      var link = row.querySelector('.cz-row-link');
      if (!link) return;
      var thin = on && shown === 0;
      link.classList.toggle('is-bare', link.querySelectorAll('[data-kind]:not(.is-off)').length === 0);
      link.classList.toggle('is-thin', thin);
      row.classList.toggle('is-thin', thin);
      var t = link.querySelector('.cz-thin-t');
      if (t) t.textContent = thin ? 'Nothing for ' + (KIND_WORD[k] || k) : '';
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
    }
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
})();
