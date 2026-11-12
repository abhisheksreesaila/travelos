// The trip grid (F-217). The page works as plain links; this adds three things on top.
//   1. Looking: a square under the pointer or the focus fills the panel beside the grid, so both lists are weighed without leaving the page.
//   2. Budget, Price or Ease, and whose day, changed on the page: the squares are re-marked here with the same rules as gitaway/tripgrid.py `Grid.tone` and
//      pages/tripgrid.py `sub`, and every link on the page is rewritten to carry the change.
//   3. From 1020px the search on top and the panel on the side follow the scroll into small islands (--tg-p and --tg-q on the stage, 0 open to 1 folded), written
//      straight to the style with no re-render so they track the hand; a tap on an island opens it again until the grid is scrolled on.
(function () {
  var stage = document.getElementById('tg-stage'), raw = document.getElementById('tg-data');
  if (!stage || !raw) return;
  var data = JSON.parse(raw.textContent);
  var scroll = document.getElementById('tg-scroll'), grid = document.getElementById('tg-grid');
  var cells = Array.prototype.slice.call(grid.querySelectorAll('[data-cell]'));
  var wide = window.matchMedia('(min-width: 1020px)');
  var looking = '';

  function money(cents) {
    return '$' + (cents / 100).toLocaleString('en-US', cents % 100 ? { minimumFractionDigits: 2, maximumFractionDigits: 2 } : {});
  }
  function set(name, text) {
    stage.querySelectorAll('[data-slot="' + name + '"]').forEach(function (el) { el.textContent = text; });
  }
  function easing() { return data.lens === 'ease' && data.who && data.whos.indexOf(data.who) >= 0; }

  // ---- the same rules as the server's ----
  function tone(key) {
    var c = data.cells[key];
    if (key === data.pick) return 'mine';
    if (easing()) return key === data.easy[data.who] ? 'best' : (c.d[data.who].s >= data.hard ? 'bad' : 'plain');
    if (key === data.low) return 'best';
    return data.budget && c.c > data.budget ? 'bad' : 'plain';
  }
  function sub(key, t) {
    var c = data.cells[key];
    if (easing()) {
      var word = c.d[data.who].w;
      return t === 'mine' ? 'your pick · ' + word : (t === 'best' ? 'easiest · ' + word : word);
    }
    if (t === 'mine') return 'your pick';
    if (t === 'best') return 'lowest';
    if (data.budget && c.c > data.budget) return 'over by ' + money(c.c - data.budget);
    return '+' + money(c.c - data.cells[data.low].c);
  }
  function focusKey() {
    if (data.pick) return data.pick;
    var best = '';
    Object.keys(data.cells).forEach(function (key) {
      var ids = key.split('|'), c = data.cells[key];
      if ((data.f && ids[0] !== data.f) || (data.h && ids[1] !== data.h)) return;
      var b = best && data.cells[best];
      var was = best.split('|');
      var less = !b || (easing() && c.d[data.who].s !== b.d[data.who].s ? c.d[data.who].s < b.d[data.who].s
        : (c.c !== b.c ? c.c < b.c : (ids[0] !== was[0] ? ids[0] < was[0] : ids[1] < was[1])));
      if (less) best = key;
    });
    return best;
  }
  function title() {
    if (data.pick) return 'Your pick · all in';
    return (easing() ? 'Easiest' : 'Lowest') + (data.f ? ' for this flight' : (data.h ? ' for this stay' : '')) + ' · all in';
  }
  function leftText(cents) {
    if (!data.budget) return 'No budget set';
    var over = cents - data.budget;
    return over > 0 ? money(over) + ' over your ' + money(data.budget) : money(-over) + ' under your ' + money(data.budget);
  }

  // ---- 1. looking ----
  function show(key) {
    var c = data.cells[key];
    if (!c) return;
    var ids = key.split('|'), focus = focusKey();
    set('title', key !== focus ? 'Looking at · all in' : title());
    set('total', money(c.c));
    set('left', leftText(c.c));
    set('flight', data.flights[ids[0]].line);
    set('stay', data.stays[ids[1]].line);
    set('room', data.stays[ids[1]].room);
    set('rail-total', money(c.c));
    set('rail-flight', data.flights[ids[0]].at);
    set('rail-stay', data.stays[ids[1]].name);
    var d = c.d[data.who];
    if (d) {
      d.f.forEach(function (fact, i) { set('k' + i, fact[0]); set('v' + i, fact[1]); });
      set('verdict', d.v);
      set('note', d.n);
      set('rail-day', d.w.replace(' day', ''));
    }
    cells.forEach(function (el) { el.classList.toggle('is-look', el.dataset.cell === key && key !== focus); });
    grid.querySelectorAll('[data-f]').forEach(function (el) { el.classList.toggle('is-look', el.dataset.f === ids[0] && key !== focus); });
    grid.querySelectorAll('[data-h]').forEach(function (el) { el.classList.toggle('is-look', el.dataset.h === ids[1] && key !== focus); });
  }
  function look(e) {
    var el = e.target.closest && e.target.closest('[data-cell]');
    if (!el || el.dataset.cell === looking) return;
    looking = el.dataset.cell;
    show(looking);
  }
  function rest() {
    looking = '';
    show(focusKey());
  }
  grid.addEventListener('pointerover', look);
  grid.addEventListener('focusin', look);
  scroll.addEventListener('pointerleave', rest);
  grid.addEventListener('focusout', function (e) { if (!grid.contains(e.relatedTarget)) rest(); });

  // ---- 2. budget, lens and whose day, on the page ----
  function carry() {
    var changes = { b: data.budget ? String(data.budget / 100) : '', lens: data.lens === 'ease' ? 'ease' : '', who: data.who && data.who !== data.whos[0] ? data.who : '' };
    function rewrite(url) {
      Object.keys(changes).forEach(function (name) {
        if (changes[name]) url.searchParams.set(name, changes[name]); else url.searchParams.delete(name);
      });
      return url;
    }
    document.querySelectorAll('a[href^="/plan/grid"]').forEach(function (a) {
      if (a.dataset.lens || a.dataset.who || a.id === 'tg-budget-none') return;      // these links are the change itself
      a.setAttribute('href', (function (u) { return u.pathname + u.search; })(rewrite(new URL(a.href))));
    });
    document.querySelectorAll('#tg-budget-form input[type="hidden"]').forEach(function (input) {
      if (input.name in changes) input.value = changes[input.name];
    });
    var here = rewrite(new URL(location.href));
    history.replaceState(null, '', here.pathname + here.search);
  }
  function paint() {
    grid.dataset.lens = data.lens;
    cells.forEach(function (el) {
      var key = el.dataset.cell, t = tone(key), words = sub(key, t);
      ['mine', 'best', 'bad', 'plain'].forEach(function (name) { el.classList.toggle('is-' + name, name === t); });
      el.querySelector('.tg-sub').textContent = words;
      el.setAttribute('aria-label', el.dataset.say + ', ' + words);
    });
    document.querySelectorAll('[data-lens]').forEach(function (a) {
      if (a === grid) return;
      a.classList.toggle('is-on', a.dataset.lens === data.lens);
      if (a.dataset.lens === data.lens) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
    });
    document.querySelectorAll('[data-who]').forEach(function (a) {
      a.classList.toggle('is-on', a.dataset.who === data.who);
      if (a.dataset.who === data.who) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
    });
    var word = document.querySelector('.tg-tk-budget > summary');
    if (word) word.textContent = data.budget ? 'under ' + money(data.budget) : 'any budget';
    var focus = focusKey(), cell = grid.querySelector('[data-cell="' + focus + '"]');
    carry();
    if (cell) document.querySelectorAll('#tg-go, [data-go]').forEach(function (a) { a.setAttribute('href', cell.getAttribute('href')); });
    show(looking || focus);
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[data-lens], a[data-who], #tg-budget-none');
    if (!a) return;
    e.preventDefault();
    if (a.dataset.lens) data.lens = a.dataset.lens;
    else if (a.dataset.who) {
      data.who = a.dataset.who;
      if (a.closest('.tg-pop')) data.lens = 'ease';
    } else data.budget = null;
    paint();
  });
  var slider = document.getElementById('tg-budget'), form = document.getElementById('tg-budget-form');
  if (slider) {
    slider.addEventListener('input', function () {
      data.budget = Number(slider.value) * 100;
      document.getElementById('tg-budget-val').textContent = money(data.budget);
      paint();
    });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      data.budget = Number(slider.value) * 100;
      paint();
      form.closest('details').open = false;
    });
  }

  // one popover at a time; a click elsewhere or Escape closes it
  var pops = Array.prototype.slice.call(document.querySelectorAll('.tg-tk'));
  pops.forEach(function (d) {
    d.addEventListener('toggle', function () {
      if (d.open) pops.forEach(function (other) { if (other !== d) other.open = false; });
    });
  });
  document.addEventListener('click', function (e) {
    pops.forEach(function (d) { if (d.open && !d.contains(e.target)) d.open = false; });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') pops.forEach(function (d) { if (d.open) { d.open = false; d.querySelector('summary').focus(); } });
  });

  // ---- 3. the top and the side follow the scroll ----
  var holdTop = null, holdSide = null, settle = 0;
  function px(name) {
    return parseFloat(getComputedStyle(stage).getPropertyValue(name)) * (parseFloat(getComputedStyle(document.documentElement).fontSize) || 12);
  }
  function mode(v) { return v === 0 ? 'open' : (v > 0.6 ? 'mini' : 'mid'); }
  function glide() {
    // a tap opens an island with a glide; scrolling itself is never eased, it tracks the hand
    stage.dataset.glide = '1';
    cancelAnimationFrame(settle);
    var frames = 0;
    (function wait() {
      var style = getComputedStyle(stage);
      var there = Math.abs(parseFloat(style.getPropertyValue('--tg-p')) - parseFloat(stage.style.getPropertyValue('--tg-p') || 0)) < 0.001 &&
        Math.abs(parseFloat(style.getPropertyValue('--tg-q')) - parseFloat(stage.style.getPropertyValue('--tg-q') || 0)) < 0.001;
      if ((there && frames > 1) || frames > 90) delete stage.dataset.glide; else settle = requestAnimationFrame(wait);
      frames += 1;
    })();
  }
  function follow() {
    if (!wide.matches) {
      stage.style.removeProperty('--tg-p');
      stage.style.removeProperty('--tg-q');
      stage.dataset.top = stage.dataset.side = 'open';
      return;
    }
    var x = scroll.scrollLeft, y = scroll.scrollTop;
    if (holdTop !== null && Math.abs(y - holdTop) > 24) { holdTop = null; glide(); }
    if (holdSide && (Math.abs(x - holdSide.x) > 24 || Math.abs(y - holdSide.y) > 96)) { holdSide = null; glide(); }
    var p = holdTop !== null ? 0 : Math.min(1, y / Math.max(1, px('--tg-open') - px('--tg-mini')));
    var q = holdSide ? 0 : Math.min(1, x / Math.max(1, px('--tg-fold')));
    stage.style.setProperty('--tg-p', p);
    stage.style.setProperty('--tg-q', q);
    stage.dataset.top = mode(p);
    stage.dataset.side = mode(q);
    if (p > 0) pops.forEach(function (d) { d.open = false; });
  }
  // a phone's strip of days starts on the trip's first day
  var first = document.querySelector('.tg-day[aria-current]');
  if (first && !wide.matches) first.parentNode.scrollLeft = first.offsetLeft - first.parentNode.offsetLeft - 8;
  stage.classList.add('is-live');
  scroll.addEventListener('scroll', follow, { passive: true });
  wide.addEventListener('change', follow);
  document.getElementById('tg-open-top').addEventListener('click', function () {
    holdTop = scroll.scrollTop;
    glide();
    follow();
  });
  document.getElementById('tg-open-side').addEventListener('click', function () {
    holdSide = { x: scroll.scrollLeft, y: scroll.scrollTop };
    glide();
    follow();
  });
  follow();
})();
