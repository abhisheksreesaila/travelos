// The trip matrix (F-222). The page works as plain links (every square is a link to its own page); this adds four things on top.
//   1. Loading like map tiles: only the squares in view (and a margin) are asked for, at most MAX_AT_ONCE at a time (3: the server's gate keeps LiteAPI to 3 calls at once, F-229),
//      after one POST to data.warm that starts the first squares' searches on the server (never from drawing the page, so a crawler starts none); a square
//      the server was too busy for ("busy") is asked again after BUSY_MS; the asked square first, then the nearest days and
//      the likeliest places (gitaway/tripmatrix.py `order`); a square scrolled past before its turn is never asked for. A waiting square is a skeleton, never a number.
//   2. The marks, with the same rules as gitaway/tripmatrix.py `marks` and `find` (change one, change the other: tests_browser/test_tripmatrix.py compares them):
//      the cheapest start in a lane, over the budget, and the find, said in words with real totals only.
//   3. While the first squares are searched, a small floating island says a fact about the place (F-230): it settles in on the spring and leaves calmly once the
//      asked square has landed (or nothing in view is waiting); a search that takes a while says so in a word beside the count.
//   4. Opening a square: its trip bar (laptop, the design's bar under the calendar, D-520) or sheet (phone) grows out of the square tapped and folds back into it.
//      The ringed band of each lane (its nights, labelled "4 nights · $2,080", the find's lane "Found · +$50 vs San Diego alone") sits on the find's start in the find's lane,
//      else the lane's cheapest start, else the opened square, and moves with the same rules as pages/tripmatrix.py `band_window` and `band_words`. Liquid at every width (D-439): the page sets
//      data-liquid on <html>, so GA.motion keeps its spring on a laptop too. Reduced motion: fades.
(function () {
  var root = document.getElementById('mx'), raw = document.getElementById('mx-data');
  if (!root || !raw) return;
  document.documentElement.setAttribute('data-liquid', '');
  var data = JSON.parse(raw.textContent);
  var MAX_AT_ONCE = 3, SLOW_MS = 4000, BUSY_MS = 3000, BUSY_TRIES = 3, MARGIN = '240px 120px', again = 0, tries = {};
  var known = {}, panels = {}, bars = {}, asked = {}, seen = {}, active = 0, timers = {}, curFind = null;
  Object.keys(data.known).forEach(function (k) { known[k] = data.known[k]; });
  var wide = window.matchMedia('(min-width: 1020px)');
  var M = function () { return window.GA && GA.motion; };
  var lanes = data.lanes, windows = data.windows;
  var side = document.getElementById('mx-side'), isle = document.getElementById('mx-fact'), isleUp = false, looked = false;
  var chosen = {}, opened = '', sheet = null, scrim = null;

  function money(c) { return '$' + Math.floor((c + 50) / 100).toLocaleString('en-US'); }
  function key(l, w) { return l + '|' + w; }
  function els(k) { return root.querySelectorAll('[data-sq="' + k + '"]'); }
  function totals() {
    var t = {};
    Object.keys(known).forEach(function (k) { if (known[k].s === 'ok' && known[k].c != null) t[k] = known[k].c; });
    return t;
  }

  // ---- the same rules as gitaway/tripmatrix.py ----
  function find(t) {
    var a = lanes.filter(function (x) { return x.a; })[0], best = null;
    if (!a) return null;
    windows.forEach(function (w, j) {
      var base = t[key(a.k, w.k)];
      if (base == null) return;
      lanes.forEach(function (x, i) {
        var got = t[key(x.k, w.k)];
        if (x.a || got == null || got - base > data.nearly) return;
        var rank = [got - base, x.c ? 0 : 1, i, j];
        if (!best || less(rank, best.rank)) best = { rank: rank, lane: x, w: w, diff: got - base };
      });
    });
    if (!best) return null;
    var x = best.lane, d = best.diff;
    var said = d < 0 ? money(-d) + ' less than ' + a.n : d === 0 ? 'the same as ' + a.n : money(d) + ' more than ' + a.n + (x.c ? ' alone' : '');
    return { key: key(x.k, best.w.k), lane: x.k, w: best.w.k, words: x.n + ', ' + said, when: best.w.when };
  }
  function less(a, b) { for (var i = 0; i < a.length; i++) { if (a[i] !== b[i]) return a[i] < b[i]; } return false; }
  function marks(t) {
    var f = find(t), out = {};
    lanes.forEach(function (x) {
      var got = [];
      windows.forEach(function (w, j) { var k = key(x.k, w.k); if (t[k] != null) got.push([t[k], j, w.k]); });
      var low = null;
      if (got.length >= 2) low = got.reduce(function (m, g) { return (g[0] < m[0] || (g[0] === m[0] && g[1] < m[1])) ? g : m; })[2];
      got.forEach(function (g) {
        var k = key(x.k, g[2]), m = [];
        if (f && f.key === k) m.push('find');
        if (g[2] === low) m.push('low');
        if (data.budget && g[0] > data.budget) m.push('over');
        out[k] = m;
      });
    });
    return { marks: out, find: f };
  }
  function vs(k) {
    var p = k.split('|'), x = lanes.filter(function (l) { return l.k === p[0]; })[0], a = lanes.filter(function (l) { return l.a; })[0];
    var mine = known[k], base = known[key(a.k, p[1])];
    if (!x || x.a || !mine || !base || mine.s !== 'ok' || base.s !== 'ok') return '';
    var d = mine.c - base.c;      // pages/tripmatrix.py `vs_words`
    return d < 0 ? money(-d) + ' less than ' + a.n : d === 0 ? 'the same as ' + a.n : '+' + money(d) + ' vs ' + a.n + (x.c ? ' alone' : '');
  }

  // ---- drawing what is known ----
  function remark() {
    var t = totals(), r = marks(t);
    curFind = r.find;
    root.querySelectorAll('[data-sq]').forEach(function (el) {
      var m = r.marks[el.dataset.sq] || [];
      ['find', 'low', 'over'].forEach(function (n) { el.classList.toggle('is-' + n, m.indexOf(n) >= 0); });
    });
    lanes.forEach(function (x) {
      var got = windows.map(function (w, j) { return [t[key(x.k, w.k)], j, w]; }).filter(function (g) { return g[0] != null; });
      var best = got.length ? got.reduce(function (m, g) { return (g[0] < m[0] || (g[0] === m[0] && g[1] < m[1])) ? g : m; }) : null;
      root.querySelectorAll('[data-lane-best="' + x.k + '"]').forEach(function (el) {
        el.textContent = best ? (el.classList.contains('mx-l-best') ? 'from ' + money(best[0]) : money(best[0])) : '';
      });
      root.querySelectorAll('[data-lane-when="' + x.k + '"]').forEach(function (el) { el.textContent = best ? best[2].when + ' · its cheapest' : ''; });
      var at = chosen[x.k] || (r.find && r.find.lane === x.k ? r.find.w : (best ? best[2].k : ''));      // pages/tripmatrix.py `band_window`
      if (at) band(x.k, at);
    });
    drawFind(r.find);
    var n = Object.keys(known).length, count = document.getElementById('mx-count-n');
    if (count) count.textContent = String(n);
    return r;
  }
  function drawFind(f) {
    var box = document.getElementById('mx-find');
    if (!box) return;
    var w = box.querySelector('#mx-find-w');
    if (!f) { box.classList.add('is-empty'); box.innerHTML = ''; box.dataset.key = ''; return; }
    if (box.dataset.key === f.key && w && w.textContent === f.words) return;
    var link = root.querySelector('.mx-sq[data-sq="' + f.key + '"]');
    box.innerHTML = '<span class="mx-found">Found</span><a class="mx-find-a" id="mx-find-a" data-open="' + f.key + '" href="' + (link ? link.getAttribute('href') : '#') + '">' +
      '<span class="mx-find-w" id="mx-find-w"></span><span class="mx-find-d" id="mx-find-d"></span></a>';
    box.querySelector('#mx-find-w').textContent = f.words;
    box.querySelector('#mx-find-d').textContent = ' · ' + f.when;
    box.dataset.key = f.key;
    var fresh = box.classList.contains('is-empty');
    box.classList.remove('is-empty');
    if (fresh && M()) (M().reduced() ? M().fade(box) : M().settle(box, { y: 6 }));
  }
  function bandWords(x, w) {      // pages/tripmatrix.py `band_words`
    var got = known[key(x.k, w.k)];
    if (!got || got.s !== 'ok') return w.n + ' nights';
    if (curFind && curFind.key === key(x.k, w.k)) return 'Found · ' + vs(curFind.key);
    return w.n + ' nights · ' + money(got.c);
  }
  function band(laneKey, wKey) {
    var el = root.querySelector('[data-band="' + laneKey + '"]'), w = windows.filter(function (x) { return x.k === wKey; })[0];
    var x = lanes.filter(function (l) { return l.k === laneKey; })[0];
    if (!el || !w || !x) return;
    var at = data.days.indexOf(w.k), col = at + 2, from = el.getBoundingClientRect(), want = col + ' / span ' + (w.n + 1);
    if (el.style.gridColumn.replace(/\s/g, '') !== want.replace(/\s/g, '')) {
      el.style.gridColumn = want;
      if (M() && from.width) M().land(el, from);
    }
    var last = data.days[at + w.n], got = known[key(laneKey, wKey)];
    el.dataset.l = bandWords(x, w);
    var lane = root.querySelector('.mx-lane[data-lane="' + laneKey + '"]');
    if (lane) {
      lane.classList.toggle('is-lit', !!(curFind && curFind.lane === laneKey && curFind.w === wKey));
      lane.querySelectorAll('.mx-day[data-day]').forEach(function (d) { d.classList.toggle('is-in', d.dataset.day >= w.k && d.dataset.day <= last); });
    }
    root.querySelectorAll('[data-lane-total="' + laneKey + '"]').forEach(function (t) { t.textContent = got && got.s === 'ok' ? money(got.c) : ''; });
    root.querySelectorAll('.mx-sq[data-sq^="' + laneKey + '|"]').forEach(function (sq) { sq.classList.toggle('is-on', sq.dataset.sq === key(laneKey, wKey)); });
  }
  function waiting() {
    var count = 0;
    root.querySelectorAll('.mx-sq.is-wait').forEach(function (el) { if (seen[el.dataset.sq]) count++; });
    return count;
  }
  function firstIn() {      // the first squares have landed: the asked square (the first the server started), else everything in view
    var a = lanes.filter(function (x) { return x.a; })[0], w = windows.filter(function (x) { return x.a; })[0] || windows[0];
    return !!(a && known[key(a.k, w.k)]) || (looked && waiting() === 0);
  }
  function isleIn() {
    if (!isle || isleUp) return;
    isleUp = true;
    isle.classList.remove('is-gone', 'is-leaving');
    isle.setAttribute('aria-hidden', 'false');
    if (M()) (M().reduced() ? M().fade(isle) : M().settle(isle, { y: 1 }));
  }
  function isleOut() {
    if (!isle || !isleUp || isle.classList.contains('is-leaving')) return;
    isle.classList.add('is-leaving');      // a calm fade and a small drop (CSS, the --motion tokens); then it is gone
    isle.setAttribute('aria-hidden', 'true');
    var gone = function () { if (isle.classList.contains('is-leaving')) isle.classList.add('is-gone'); };
    isle.addEventListener('transitionend', gone, { once: true });
    setTimeout(gone, (M() ? M().t('dur') : 240) + 100);
  }
  function news_() {
    var still = waiting() > 0;
    root.dataset.waiting = still ? '1' : '0';
    if (firstIn()) isleOut();
    if (!still) root.removeAttribute('data-slow');
  }

  // ---- loading like map tiles ----
  function land(k, j) {
    if (j.s === 'busy') {      // no turn at the server's gate in time: asked again after 3, 6, 12 s, then the square says so and settles
      tries[k] = (tries[k] || 0) + 1;
      if (tries[k] > BUSY_TRIES) { said(k, 'Lots of searches right now. Try again in a minute.'); return; }
      again++;
      setTimeout(function () { again--; delete asked[k]; pump(); }, BUSY_MS * Math.pow(2, tries[k] - 1));
      return;
    }
    known[k] = { c: j.c, s: j.s };
    panels[k] = j.panel;
    bars[k] = j.bar;
    els(k).forEach(function (el) {
      io.unobserve(el);
      el.querySelector('.mx-in').innerHTML = j.inner;
      el.classList.remove('is-wait', 'skeleton');
      el.classList.add(j.s === 'ok' ? 'is-ok' : 'is-said');
      el.setAttribute('aria-label', j.label);
      if (el.offsetParent && M()) {      // the copy on screen settles into its answer: a short liquid morph (scale and opacity, the settle spring), a fade under reduced motion
        if (M().reduced()) M().fade(el);
        else M().run(el, [{ opacity: 0.2, transform: 'scale(0.9)' }, { opacity: 1, transform: 'none' }], { t: 'settle', ease: 'spring' });
      }
    });
    var age = document.getElementById('mx-age');
    if (age && j.age && age.textContent === 'Preview') age.textContent = 'Preview · ' + j.age;
    var r = remark();
    news_();
    if (opened === k) show(k, null, true);
    else if (!opened && side) {      // nothing opened yet: the side follows the find, else the asked square (pages/tripmatrix.py `default_open`)
      var a = lanes.filter(function (x) { return x.a; })[0], w = windows.filter(function (x) { return x.a; })[0] || windows[0];
      var first = r.find ? r.find.key : (a && known[key(a.k, w.k)] ? key(a.k, w.k) : '');
      var now = side.querySelector('[data-open]');
      if (first && bars[first] && (!now || now.dataset.open !== first)) {
        var inner = fill(side, first, bars);
        if (inner && M() && wide.matches) M().fade(inner);
      }
    }
  }
  function said(k, words) {
    known[k] = { c: null, s: 'failed' };
    els(k).forEach(function (el) {
      io.unobserve(el);
      el.querySelector('.mx-in').innerHTML = '<span class="mx-w"></span>';
      el.querySelector('.mx-w').textContent = words;
      el.classList.remove('is-wait', 'skeleton');
      el.classList.add('is-said');
    });
    news_();
  }
  function next() {
    for (var i = 0; i < data.order.length; i++) {
      var k = data.order[i];
      if (seen[k] && !known[k] && !asked[k]) return k;
    }
    return null;
  }
  function pump() {
    while (active < MAX_AT_ONCE) {
      var k = next();
      if (!k) break;
      ask(k);
    }
    root.dataset.busy = active > 0 || again > 0 ? '1' : '0';      // 0: every square in view has its answer (the tests wait on it)
  }
  function ask(k) {
    asked[k] = 1;
    active++;
    var p = k.split('|');
    timers[k] = setTimeout(function () { root.setAttribute('data-slow', '1'); }, SLOW_MS);
    fetch(data.tile + '&lane=' + encodeURIComponent(p[0]) + '&w=' + encodeURIComponent(p[1]), { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) { land(k, j); })
      .catch(function () { said(k, 'Couldn’t search'); })
      .then(function () { clearTimeout(timers[k]); active--; pump(); });
  }
  var showing = new Set();      // the square elements in view now (a key has two: the laptop's lane and the phone's card, one of them hidden)
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) showing.add(e.target); else showing.delete(e.target);
      var k = e.target.dataset.sq;
      seen[k] = Array.prototype.some.call(els(k), function (el) { return showing.has(el); });
    });
    looked = true;
    news_();
    pump();
  }, { rootMargin: MARGIN });
  var watched = 0;
  root.dataset.busy = '1';
  root.querySelectorAll('.mx-sq[data-sq]').forEach(function (el) { if (!known[el.dataset.sq]) { io.observe(el); watched++; } });
  if (!watched) root.dataset.busy = '0';
  else {
    if (data.warm) fetch(data.warm, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' } }).catch(function () {});      // the head start, once
    if (!firstIn()) isleIn();
  }

  // ---- opening a square ----
  function placeholder(k, cls) {
    return '<div class="' + cls + '" data-open="' + k + '"><p class="mx-p-note" role="status">Searching this square. It fills in as soon as its answer lands.</p></div>';
  }
  function fill(box, k, from) {      // `from`: the bars (the laptop) or the panels (the sheet)
    var src = from || panels;
    box.innerHTML = src[k] || placeholder(k, src === bars ? 'mx-b' : 'mx-p');
    var chip = box.querySelector('[data-vs]');
    if (chip && !chip.textContent) { var v = vs(k); chip.textContent = v; chip.classList.toggle('is-empty', !v); }
    bindSave(box);
    return box.firstElementChild;
  }
  function show(k, from, refill) {
    opened = k;
    root.querySelectorAll('.mx-sq.is-open').forEach(function (el) { el.classList.remove('is-open'); });
    els(k).forEach(function (el) { el.classList.add('is-open'); });
    var p = k.split('|');
    chosen[p[0]] = p[1];
    band(p[0], p[1]);
    if (wide.matches && side) {
      var inner = fill(side, k, bars);
      if (!refill && M() && inner) (M().reduced() ? M().fade(inner) : M().open(inner, from || side));
      return;
    }
    if (sheet) { fill(sheet.querySelector('.mx-sheet-in'), k); return; }
    scrim = document.createElement('div');
    scrim.className = 'mx-scrim';
    sheet = document.createElement('div');
    sheet.className = 'mx-sheet';
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-modal', 'true');
    sheet.setAttribute('aria-label', 'The square you opened');
    sheet.innerHTML = '<div class="mx-sheet-bar"><span class="mx-grab" aria-hidden="true"></span><button type="button" class="mx-x" aria-label="Close">' +
      '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div><div class="mx-sheet-in"></div>';
    fill(sheet.querySelector('.mx-sheet-in'), k);
    document.body.appendChild(scrim);
    document.body.appendChild(sheet);
    sheet.origin = from;
    scrim.addEventListener('click', close);
    sheet.querySelector('.mx-x').addEventListener('click', close);
    drag(sheet);
    if (M()) M().open(sheet, from, { scrim: scrim, content: sheet.querySelector('.mx-sheet-in'), radius: [14, 26] });
    sheet.querySelector('.mx-x').focus({ preventScroll: true });
  }
  function close() {
    if (!sheet) return;
    var s = sheet, sc = scrim, from = s.origin && document.body.contains(s.origin) ? s.origin : null;
    sheet = scrim = null;
    var done = function () { s.remove(); sc.remove(); };
    if (M()) M().close(s, from, { scrim: sc }).then(done); else done();
    if (from) from.focus({ preventScroll: true });
  }
  function drag(s) {
    var bar = s.querySelector('.mx-sheet-bar'), y0 = null, dy = 0;
    bar.addEventListener('pointerdown', function (e) { if (e.target.closest('.mx-x')) return; y0 = e.clientY; dy = 0; bar.setPointerCapture(e.pointerId); });
    bar.addEventListener('pointermove', function (e) { if (y0 == null) return; dy = Math.max(0, e.clientY - y0); s.style.transform = 'translateY(' + dy + 'px)'; });
    bar.addEventListener('pointerup', function () {
      if (y0 == null) return;
      y0 = null;
      if (dy > 80) { s.style.transform = ''; close(); } else if (M()) { M().spring(s, s.style.transform); s.style.transform = ''; } else s.style.transform = '';
    });
  }
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  root.addEventListener('click', function (e) {
    var a = e.target.closest('.mx-sq[data-sq], .mx-find-a[data-open]');
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
    e.preventDefault();
    var k = a.dataset.sq || a.dataset.open, from = a.classList.contains('mx-sq') ? a : (Array.prototype.filter.call(els(k), function (el) { return el.offsetParent; })[0] || a);
    if (!known[k] && !asked[k]) { seen[k] = true; ask(k); }
    show(k, from);
  });

  // ---- Save to trip, without leaving the page ----
  function bindSave(box) {
    var form = box.querySelector('.mx-save-f');
    if (!form) return;
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = form.querySelector('button');
      btn.disabled = true;
      fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'X-Matrix': '1' }, credentials: 'same-origin' })
        .then(function (r) {
          if (r.status === 403) { return { saved: 'Only an editor in your family can save to the trip.', refused: true }; }   // a viewer: say so here, never a GET of the POST route
          if (r.redirected || (r.headers.get('content-type') || '').indexOf('json') < 0) { location.href = r.url; return null; }
          return r.json();
        })
        .then(function (j) {
          if (!j) return;
          var p = document.createElement('p');
          p.className = 'mx-saved';
          p.setAttribute('role', 'status');
          p.textContent = j.saved + ' ';
          if (j.refused) { btn.disabled = false; form.parentNode.insertBefore(p, form.nextSibling); return; }
          var link = document.createElement('a');
          link.href = j.trip;
          link.textContent = 'Open the trip';
          p.appendChild(link);
          form.replaceWith(p);
          if (M()) (M().reduced() ? M().fade(p) : M().settle(p, { y: 4 }));
        })
        .catch(function () { btn.disabled = false; });
    });
  }
  if (side) bindSave(side);
  remark();
  news_();
  root.classList.add('is-live');
})();
