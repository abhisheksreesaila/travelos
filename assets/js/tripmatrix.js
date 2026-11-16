// The trip matrix (F-222). The page works as plain links (every square is a link to its own page); this adds four things on top.
//   1. Loading like map tiles: only the squares in view (and a margin) are asked for, at most MAX_AT_ONCE at a time (32, F-273: a live key's gate takes a whole matrix at once; a sandbox key's gate keeps LiteAPI to 3 calls at once and the rest wait there, F-229),
//      after one POST to data.warm that starts the first squares' searches on the server (never from drawing the page, so a crawler starts none); a square
//      the server was too busy for ("busy") is asked again after BUSY_MS; the asked square first, then the nearest days and
//      the likeliest places (gitaway/tripmatrix.py `order`); a square scrolled past before its turn is never asked for. A waiting square is a skeleton, never a number.
//   2. The marks, with the same rules as gitaway/tripmatrix.py `marks` and `find` (change one, change the other: tests_browser/test_tripmatrix.py compares them):
//      the cheapest start in a lane, over the budget, and the find, said in words with real totals only.
//   3. While the first squares are searched, a small floating island says a fact about the place (F-230): it settles in on the spring and leaves calmly once the
//      asked square has landed (or nothing in view is waiting); a search that takes a while says so in a word beside the count.
//   4. Opening a square (F-251, D-620): the prototype's drawer grows down out of the square's column under the matrix, on a laptop and on a phone (assets/js/v2drawer.js); the widget rail
//      beside it follows the place of the square (or the lane) you look at (assets/js/v2rail.js, through the events mx:follow, mx:look, mx:close and mx:settled).
//      The ringed band of each lane (its nights, labelled "4 nights · $2,080", the find's lane "Found · +$50 vs San Diego alone") sits on the find's start in the find's lane,
//      else the lane's cheapest start, else the opened square, and moves with the same rules as pages/tripmatrix.py `band_window` and `band_words`. Liquid at every width (D-439): the page sets
//      data-liquid on <html>, so GA.motion keeps its spring on a laptop too. Reduced motion: fades.
//   5. The nights slider (F-237, D-530 to D-535; F-238, D-542): one range input, in the popover of the sentence's "4 nights" word (the same word on a phone and a laptop). While it moves every square shows
//      "about $X" at once (`estimate`: the flight and the nightly stay rate already read for that square's start day, else the lane's cheapest; never a search, never a
//      mark, never a price). Let go (after COMMIT_MS), the address keeps the nights, one GET of data.peek fills what is already known for them (the showcase's samples, LiteAPI's
//      cache) and only then the squares in view are asked for, as tiles, through the same gate and budgets. Every nights has its own store (`stores`), so going back is
//      instant. The opened square's drawer, Save and Book are always the tile's real answer for those exact nights; while sliding they say so instead of a price.
(function () {
  var root = document.getElementById('mx'), raw = document.getElementById('mx-data');
  if (!root || !raw) return;
  document.documentElement.setAttribute('data-liquid', '');
  var data = JSON.parse(raw.textContent);
  MAX_AT_ONCE = data.at_once || MAX_AT_ONCE;      // F-273 review: the server's gate size for the key the site runs with (32 live, 3 sandbox), so a sandbox page doesn't flood its gate into BUSY retries
  var MAX_AT_ONCE = 32, SLOW_MS = 4000, BUSY_MS = 3000, BUSY_TRIES = 3, MARGIN = '240px 120px', COMMIT_MS = 220, again = 0, committing = 0, looking = false, settling = false;
  var N = data.nights, stores = {}, known, drawers, asked, tries, seen = {}, active = 0, timers = {}, curFind = null;
  var sliding = false, touched = false, commitTimer = 0, bandAt = {};
  function store(n) { return stores[n] || (stores[n] = { known: {}, drawers: {}, asked: {}, tries: {} }); }
  function use(n) { var s = store(n); N = n; known = s.known; drawers = s.drawers; asked = s.asked; tries = s.tries; }
  use(N);
  Object.keys(data.known).forEach(function (k) { known[k] = data.known[k]; });
  var M = function () { return window.GA && GA.motion; };
  var lanes = data.lanes, windows = data.windows;
  var dbox = document.getElementById('mx-drawer'), isle = document.getElementById('mx-fact'), isleUp = false, looked = false;
  var chosen = {}, opened = '', followed = '';

  function money(c) { return '$' + Math.floor((c + 50) / 100).toLocaleString('en-US'); }
  function key(l, w) { return l + '|' + w; }
  function els(k) { return root.querySelectorAll('[data-sq="' + k + '"]'); }
  function totals() {
    var t = {};
    Object.keys(known).forEach(function (k) { if (known[k].s === 'ok' && known[k].c != null) t[k] = known[k].c; });
    return t;
  }

  function nightsWords(n) { return n + ' night' + (n === 1 ? '' : 's'); }
  function withNights(u, n) {      // the same address for another trip length: only `r`, the last day, moves
    var url = new URL(u, location.href);
    url.searchParams.set('r', data.returns[n]);
    return url.pathname + url.search;
  }
  function laneOf(k) { return lanes.filter(function (l) { return l.k === k.split('|')[0]; })[0]; }
  function windowOf(k) { return windows.filter(function (w) { return w.k === k.split('|')[1]; })[0]; }

  // ---- estimates while the slider moves: a guess from what is already read, never a price, never marked ----
  function estimate(k, n) {      // cents for the whole trip of n nights, or null when nothing is known to guess from
    var p = k.split('|'), e = null, order = Object.keys(stores).map(Number).sort(function (a, b) { return Math.abs(a - n) - Math.abs(b - n) || a - b; });
    order.some(function (m) { var r = stores[m].known[k]; if (r && r.s === 'ok' && r.e) { e = r.e; return true; } return false; });      // this start day's own flight and nightly rates
    if (!e) {      // none yet: the lane's cheapest flight and cheapest nightly rates read on any start day
      var f = null, rates = [];
      order.forEach(function (m) {
        windows.forEach(function (w) {
          var r = stores[m].known[key(p[0], w.k)];
          if (!r || r.s !== 'ok' || !r.e) return;
          f = f == null ? r.e[0] : Math.min(f, r.e[0]);
          r.e.slice(1).forEach(function (v, i) { rates[i] = rates[i] == null ? v : Math.min(rates[i], v); });
        });
      });
      if (f != null) e = [f].concat(rates);
    }
    if (!e) return null;
    var first = Math.floor(n / 2), parts = e.length > 2 ? [first, n - first] : [n], cents = e[0];      // two places split the nights, the shorter half first (gitaway/tripmatrix.py `stays_for`)
    for (var i = 1; i < e.length; i++) cents += e[i] * parts[i - 1];
    return cents;
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
    var said = (d < 0 ? money(-d) + ' less than ' : 'the same as ') + a.n + (x.c ? ' alone' : '');      // never a dearer one (D-860)
    return { key: key(x.k, best.w.k), lane: x.k, w: best.w.k, name: x.n, said: said, words: x.n + ', ' + said, when: best.w.when };
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
    return (d < 0 ? money(-d) + ' less than ' : d === 0 ? 'the same as ' : money(d) + ' more than ') + a.n + (x.c ? ' alone' : '');
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
      root.querySelectorAll('[data-lane-best="' + x.k + '"]').forEach(function (el) { el.textContent = best ? 'from ' + money(best[0]) : 'Pricing…'; });
      var at = chosen[x.k] || (r.find && r.find.lane === x.k ? r.find.w : (best ? best[2].k : '')) || bandAt[x.k];      // pages/tripmatrix.py `band_window`; none known yet: where it was
      if (at) band(x.k, at);
    });
    drawFind(r.find);
    var n = Object.keys(known).length, count = document.getElementById('mx-count-n'), of = document.getElementById('mx-done-of'), doneN = document.getElementById('mx-done-n');
    if (count) count.textContent = String(n);
    if (doneN) doneN.textContent = String(n);
    if (of) of.textContent = n < lanes.length * windows.length ? ' of ' + lanes.length * windows.length : '';
    return r;
  }
  function drawFind(f) {      // the pick bar: the find (the prototype's "Our pick"), drawn from what is known: its art, its place and days, what it beats, its total
    var box = document.getElementById('mx-find');
    if (!box) return;
    if (!f) { box.classList.add('is-empty'); box.dataset.open = ''; box.dataset.key = ''; return; }
    if (box.dataset.key === f.key) { box.querySelector('.mx-pk-p').textContent = money(known[f.key].c); return; }
    var link = root.querySelector('.mx-sq[data-sq="' + f.key + '"]'), art = root.querySelector('.mx-lane[data-lane="' + f.lane + '"] .mx-thumb');
    box.querySelector('.mx-pk-art').innerHTML = art ? art.outerHTML : '';
    box.querySelector('.mx-pk-h').textContent = f.name + ', ' + f.when;
    box.querySelector('.mx-pk-s').textContent = f.said.charAt(0).toUpperCase() + f.said.slice(1);
    box.querySelector('.mx-pk-p').textContent = money(known[f.key].c);
    box.setAttribute('href', link ? link.getAttribute('href') : '#');
    box.dataset.open = f.key;
    box.dataset.key = f.key;
    var fresh = box.classList.contains('is-empty');
    box.classList.remove('is-empty');
    if (fresh && M()) (M().reduced() ? M().fade(box) : M().settle(box, { y: 6 }));
  }
  function bandWords(x, w) {      // pages/tripmatrix.py `band_words`
    var got = known[key(x.k, w.k)];
    if (!got || got.s !== 'ok') {
      var g = touched ? estimate(key(x.k, w.k), N) : null;      // sliding: the band says an estimate as one
      return w.n + ' nights' + (g != null ? ' · about ' + money(g) : '');
    }
    if (curFind && curFind.key === key(x.k, w.k)) return 'Found · ' + vs(curFind.key);
    return w.n + ' nights · ' + money(got.c);
  }
  function band(laneKey, wKey) {      // the ringed nights on a lane's start: its columns are the lane's squares', so it spans as many start days as the trip has nights, as far as there are any
    var el = root.querySelector('[data-band="' + laneKey + '"]'), at = windows.map(function (x) { return x.k; }).indexOf(wKey);
    var w = windows[at], x = lanes.filter(function (l) { return l.k === laneKey; })[0];
    if (!el || !w || !x) return;
    var from = el.getBoundingClientRect(), want = (at + 2) + ' / span ' + Math.max(1, Math.min(w.n, windows.length - at));
    if (el.style.gridColumn.replace(/\s/g, '') !== want.replace(/\s/g, '')) {
      el.style.gridColumn = want;
      if (M() && from.width) M().land(el, from);
    }
    bandAt[laneKey] = wKey;
    var got = known[key(laneKey, wKey)];
    el.dataset.l = bandWords(x, w);
    var lane = root.querySelector('.mx-lane[data-lane="' + laneKey + '"]');
    if (lane) lane.classList.toggle('is-lit', !!(curFind && curFind.lane === laneKey && curFind.w === wKey));
    root.querySelectorAll('.mx-sq[data-sq^="' + laneKey + '|"]').forEach(function (sq) { sq.classList.toggle('is-on', sq.dataset.sq === key(laneKey, wKey)); });
  }
  function waiting() {
    var count = 0;
    root.querySelectorAll('.mx-sq[data-sq]').forEach(function (el) { if (!known[el.dataset.sq] && seen[el.dataset.sq]) count++; });      // skeletons and estimates alike
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
    var gone = function () { if (isle.classList.contains('is-leaving')) { isle.classList.add('is-gone'); isleUp = false; } };
    isle.addEventListener('transitionend', gone, { once: true });
    setTimeout(gone, (M() ? M().t('dur') : 240) + 100);
  }
  var wasWaiting = true;
  function news_() {
    var still = waiting() > 0;
    root.dataset.waiting = still ? '1' : '0';
    if (wasWaiting && !still) { wasWaiting = false; document.dispatchEvent(new CustomEvent('mx:settled')); }      // every square in view has its answer: the rail may know more (a cheaper airport needs two)
    if (still) wasWaiting = true;
    if (firstIn()) isleOut();
    if (!still) root.removeAttribute('data-slow');
  }

  // ---- loading like map tiles ----
  function settleIn(el) {      // the copy on screen settles into its answer: a short liquid morph (scale and opacity, the settle spring), a fade under reduced motion
    if (!el.offsetParent || !M()) return;
    if (M().reduced()) M().fade(el);
    else M().run(el, [{ opacity: 0.2, transform: 'scale(0.9)' }, { opacity: 1, transform: 'none' }], { t: 'settle', ease: 'spring' });
  }
  function paint(el, k) {      // what a square shows now: its answer, else (once the slider has been touched) an estimate said as one, else a skeleton, never a bare number
    var r = known[k], box = el.querySelector('.mx-in'), head = laneOf(k).n + ', ' + windowOf(k).when;
    el.classList.remove('is-wait', 'skeleton', 'is-ok', 'is-said', 'is-est');
    if (r) {
      box.innerHTML = r.i;
      el.classList.add(r.s === 'ok' ? 'is-ok' : 'is-said');
      el.setAttribute('aria-label', r.l);
      return;
    }
    var g = touched ? estimate(k, N) : null;
    if (g != null) {
      box.innerHTML = '<span class="mx-v mx-est"><span class="mx-about-w">about</span> <span class="mx-est-n"></span></span>';
      box.querySelector('.mx-est-n').textContent = money(g);
      el.classList.add('is-est');
      el.setAttribute('aria-label', head + ': about ' + money(g) + ' for the whole trip, an estimate');
    } else {
      box.innerHTML = '<span class="mx-sr">Searching</span>';
      el.classList.add('is-wait', 'skeleton');
      el.setAttribute('aria-label', head + ': searching');
    }
  }
  function land(k, j, n) {
    var st = store(n);
    if (j.s === 'busy') {      // no turn at the server's gate in time: asked again after 3, 6, 12 s, then the square says so and settles
      st.tries[k] = (st.tries[k] || 0) + 1;
      if (st.tries[k] > BUSY_TRIES) { said(k, 'Lots of searches right now. Try again in a minute.', n); return; }
      again++;
      setTimeout(function () { again--; delete st.asked[k]; pump(); }, BUSY_MS * Math.pow(2, st.tries[k] - 1));
      return;
    }
    st.known[k] = { c: j.c, s: j.s, e: j.e, i: j.inner, l: j.label };
    st.drawers[k] = j.drawer;
    if (n !== N) return;      // asked for other nights and answered after the slider moved on: kept for when it comes back
    els(k).forEach(function (el) { io.unobserve(el); paint(el, k); settleIn(el); });
    var age = document.getElementById('mx-age');
    if (age && j.age) age.textContent = j.age;      // F-267: with a live key the about card says when the prices were checked
    remark();
    news_();
    if (opened === k) show(k, null, true);
    else followDefault();
    estFlag();
  }
  function said(k, words, n) {
    var st = store(n);
    st.known[k] = { c: null, s: 'failed', e: null, i: '<span class="mx-w">' + words + '</span>', l: laneOf(k).n + ', ' + windowOf(k).when + ': ' + words };
    if (n !== N) return;
    els(k).forEach(function (el) { io.unobserve(el); paint(el, k); });
    news_();
    estFlag();
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
    root.dataset.busy = active > 0 || again > 0 || committing > 0 || looking || settling ? '1' : '0';      // 0: every square in view has its answer (the tests wait on it)
  }
  function ask(k) {
    asked[k] = 1;
    active++;
    var p = k.split('|');
    timers[k] = setTimeout(function () { root.setAttribute('data-slow', '1'); }, SLOW_MS);
    var n = N;      // the answer belongs to these nights, whatever the slider has moved on to
    fetch(withNights(data.tile, n) + '&lane=' + encodeURIComponent(p[0]) + '&w=' + encodeURIComponent(p[1]), { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) { land(k, j, n); })
      .catch(function () { said(k, 'Couldn’t search', n); })
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
    looking = false;
    news_();
    pump();
  }, { rootMargin: MARGIN });
  var watched = 0;
  root.dataset.busy = '1';
  root.querySelectorAll('.mx-sq[data-sq]').forEach(function (el) { if (!known[el.dataset.sq]) { io.observe(el); watched++; } });
  if (!watched) root.dataset.busy = '0';
  else {
    if (data.warm) fetch(data.warm, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' } }).then(function (r) { return r.text(); }).catch(function () {});      // the head start, once (its answer read, so the request ends)
    if (!firstIn()) isleIn();
  }

  // ---- the rail follows the place you look at (F-251, D-620): before anything is opened, the find's place, else the asked one; then the square or the lane you tap ----
  function follow(laneKey, wKey, fresh) {      // assets/js/v2rail.js asks the server for that place's widgets and swaps them in
    var l = laneKey || '', w = wKey || '';
    if (!l) return;
    if (!w) w = (windows.filter(function (x) { return x.a; })[0] || windows[0]).k;      // no square opened: the asked start day (the rail's sky begins there)
    var id = l + '|' + w + '|' + N;
    if (id === followed && !fresh) return;
    followed = id;
    document.dispatchEvent(new CustomEvent('mx:follow', { detail: { lane: l, w: w, n: N, fresh: !!fresh } }));
  }
  function followDefault() {
    if (opened || touchedLane) return;
    if (curFind) return follow(curFind.lane, curFind.w);
    var a = lanes.filter(function (x) { return x.a; })[0];
    if (a) follow(a.k, '');
  }
  var touchedLane = false;

  // ---- opening a square: the prototype's drawer grows down out of the square's column (assets/js/v2drawer.js) ----
  function placeholder(k) {      // an estimate is never the opened square's price: while sliding it says so, and Save and Book wait for the real answer
    var words = sliding ? 'Let go for the exact price of ' + nightsWords(N) + '.' : 'Searching this square. It fills in as soon as its answer lands.';
    return '<div class="dr is-quiet is-ph" data-open="' + k + '"><div class="dr-head"><div class="dr-ti"><h2 class="dr-h">' + laneOf(k).n + '</h2><p>' + windowOf(k).when + '</p></div>' +
      '<button type="button" class="dr-x" data-act="close" aria-label="Close"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>' +
      '<div class="dr-quiet"><p class="dr-note" role="status">' + words + '</p></div></div>';
  }
  function ensure(k) {      // the opened square's drawer is the tile's real answer for these exact nights: ask for it if it is not here yet
    if (!drawers[k] && !asked[k]) { seen[k] = true; ask(k); }
  }
  function fill(k) {
    var cur = dbox.firstElementChild, fresh = dbox.dataset.n !== String(N);
    if (!fresh && cur && cur.dataset.open === k && (dbox.dataset.ph ? !drawers[k] : true)) return null;      // already showing it (a placeholder waits for its answer): the family's choices stay
    dbox.innerHTML = drawers[k] || placeholder(k);
    dbox.dataset.n = String(N);
    dbox.dataset.ph = drawers[k] ? '' : '1';
    var chip = dbox.querySelector('[data-pickword]');
    if (chip) chip.hidden = !(curFind && curFind.key === k);      // "Our pick:" only where the matrix itself says it is the find
    var vsEl = dbox.querySelector('[data-vs]');
    if (vsEl && !vsEl.textContent) { var v = vs(k); if (v) vsEl.textContent = (vsEl.dataset.sep ? ' \u00b7 ' : '') + v; }
    bindSave(dbox);
    document.dispatchEvent(new CustomEvent('mx:drawer', { detail: { key: k, box: dbox } }));
    return dbox.firstElementChild;
  }
  function show(k, from, refill) {
    var p = k.split('|'), was = opened;
    opened = k;
    root.querySelectorAll('.mx-sq.is-open').forEach(function (el) { el.classList.remove('is-open'); });
    els(k).forEach(function (el) { el.classList.add('is-open'); });
    chosen[p[0]] = p[1];
    band(p[0], p[1]);
    if (!sliding) ensure(k);
    var wasHidden = dbox.hidden;
    dbox.hidden = false;
    var inner = fill(k);
    document.body.classList.add('drawer-open');
    if (inner && window.V2D) V2D.grow(dbox, from, { again: !wasHidden && was !== k, refill: !!refill });
    if (!refill) { touchedLane = true; follow(p[0], p[1]); }
  }
  function close() {
    if (!opened) return;
    opened = '';      // nothing is open now: a later answer or a new length of trip must not open the drawer again
    root.querySelectorAll('.mx-sq.is-open').forEach(function (el) { el.classList.remove('is-open'); });
    document.body.classList.remove('drawer-open');
    var from = dbox.dataset.from && root.querySelector('.mx-sq[data-sq="' + dbox.dataset.from + '"]');
    var done = function () { if (!opened) { dbox.hidden = true; dbox.innerHTML = ''; dbox.dataset.n = ''; } };
    if (window.V2D) V2D.away(dbox, done); else done();
    remark();
    if (from) from.focus({ preventScroll: true });
  }
  document.addEventListener('mx:close', close);
  document.addEventListener('mx:look', function (e) { touchedLane = true; follow(e.detail.lane, ''); });

  // ---- the sentence's words and ⓘ About these prices: popovers that grow from their word (F-238, D-542) ----
  var pops = root.querySelectorAll('details.mx-tk');
  function shutPops(except) { pops.forEach(function (d) { if (d !== except && d.open) d.open = false; }); }
  pops.forEach(function (d) {
    d.addEventListener('toggle', function () {
      if (!d.open) return;
      shutPops(d);
      var pop = d.querySelector('.mx-pop'), word = d.querySelector('summary');
      if (pop && M()) (M().reduced() ? M().fade(pop) : M().open(pop, word));      // grows out of the word tapped; reduced motion: a fade
      var first = pop && pop.querySelector('input, a[href], button, summary');      // keyboard: focus moves into the popover (to the slider for the nights) so a key can use it at once
      if (first) first.focus({ preventScroll: true });
    });
    d.addEventListener('focusout', function (e) { if (d.open && e.relatedTarget && !d.contains(e.relatedTarget)) d.open = false; });      // Tab on past the popover puts it away
  });
  document.addEventListener('pointerdown', function (e) { if (!e.target.closest('details.mx-tk')) shutPops(null); });      // a tap anywhere else puts the popover away
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var open = Array.prototype.filter.call(pops, function (d) { return d.open; });
    open.forEach(function (d) { d.open = false; var w = d.querySelector('summary'); if (w) w.focus({ preventScroll: true }); });
    if (!open.length) close();
  });
  root.addEventListener('click', function (e) {
    var lead = e.target.closest('.mx-lane .mx-lead');      // a place's name: the rail follows it (the prototype's "follows the place you look at")
    if (lead) { touchedLane = true; follow(lead.parentNode.dataset.lane, ''); return; }
    var a = e.target.closest('.mx-sq[data-sq], .mx-find[data-open]');
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
    e.preventDefault();
    var k = a.dataset.sq || a.dataset.open, from = a.classList.contains('mx-sq') ? a : (Array.prototype.filter.call(els(k), function (el) { return el.offsetParent; })[0] || a);
    show(k, from);
  });

  // ---- the nights slider (F-237) ----
  function estFlag() { root.dataset.est = root.querySelector('.mx-sq.is-est') ? '1' : '0'; }      // the page says "about" prices are estimates while any shows
  function observeAll() {      // after a change of nights: every square still without an answer is looked at again, so only those in view are asked for
    var n = 0;
    root.querySelectorAll('.mx-sq[data-sq]').forEach(function (el) {
      io.unobserve(el);
      showing.delete(el);
      if (known[el.dataset.sq]) return;
      seen[el.dataset.sq] = false;
      io.observe(el);
      n++;
    });
    looking = n > 0;      // the observer reports on its next frame: until it has, the page is not idle (the tests wait on it)
  }
  function setNights(n) {      // at once, on every move: the words, the days, the squares as estimates or what is kept, the band; nothing is searched
    touched = true;
    use(n);
    windows.forEach(function (w, i) { w.n = n; w.when = data.whens[n][i]; });
    document.querySelectorAll('[data-nights-out]').forEach(function (el) { el.textContent = nightsWords(n); });
    var pct = Math.round((n - data.lo) * 100 / (data.hi - data.lo)) + '%';
    document.querySelectorAll('input[data-nights]').forEach(function (r) { r.value = n; r.setAttribute('aria-valuetext', nightsWords(n)); r.style.setProperty('--fill', pct); });
    root.querySelectorAll('a[href^="/plan/matrix"]').forEach(function (a) { var h = a.getAttribute('href'); if (/[?&]r=/.test(h)) a.setAttribute('href', withNights(h, n)); });
    root.querySelectorAll('.mx-sq[data-sq]').forEach(function (el) { paint(el, el.dataset.sq); });
    remark();
    if (opened) show(opened, null, true); else followDefault();
    estFlag();
  }
  function commit(n) {      // let go: the address keeps the nights, what is already known fills in at once, then the squares in view are asked for like any tile
    sliding = false;
    try { history.replaceState(null, '', withNights(location.pathname + location.search, n)); } catch (e) { /* a preview without history: the page still works */ }
    committing++;
    root.dataset.busy = '1';
    var st = store(n);
    fetch(withNights(data.peek, n), { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) {
        Object.keys(j.known).forEach(function (k) { var v = j.known[k]; if (!st.known[k]) st.known[k] = { c: v.c, s: v.s, e: v.e, i: v.inner, l: v.label }; });
      })
      .catch(function () { /* nothing known: the tiles ask */ })
      .then(function () {
        committing--;
        if (n === N) {
          root.querySelectorAll('.mx-sq[data-sq]').forEach(function (el) {
            var k = el.dataset.sq, was = el.classList.contains('is-est') || el.classList.contains('is-wait');
            paint(el, k);
            if (was && known[k]) settleIn(el);
          });
          remark();
          observeAll();
          if (opened) show(opened, null, true); else followDefault();
          estFlag();
          if (!firstIn()) isleIn();
          news_();
        }
        pump();
      });
  }
  root.addEventListener('input', function (e) {
    var t = e.target;
    if (!t.matches || !t.matches('input[data-nights]')) return;
    clearTimeout(commitTimer);
    settling = false;
    sliding = true;
    if (+t.value !== N) setNights(+t.value);
  });
  root.addEventListener('change', function (e) {
    var t = e.target, n = +(t && t.value);
    if (!t.matches || !t.matches('input[data-nights]')) return;
    clearTimeout(commitTimer);
    if (n !== N) setNights(n);
    settling = true;
    root.dataset.busy = '1';      // not idle while the release waits out its short settle
    commitTimer = setTimeout(function () { settling = false; commit(n); }, COMMIT_MS);      // a key pressed three times asks once, for where it stopped
  });
  root.querySelectorAll('.mx-lane .mx-sq.is-on').forEach(function (el) { var p = el.dataset.sq.split('|'); bandAt[p[0]] = p[1]; });
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
          link.textContent = j.next || 'Open the trip';
          p.appendChild(link);
          form.replaceWith(p);
          if (M()) (M().reduced() ? M().fade(p) : M().settle(p, { y: 4 }));
        })
        .catch(function () { btn.disabled = false; });
    });
  }
  remark();
  news_();
  followDefault();
  root.classList.add('is-live');
})();
