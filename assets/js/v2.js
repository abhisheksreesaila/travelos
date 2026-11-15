// The v2 sentence (F-250, D-611): the search as one sentence whose every word opens its own picker, never a box you type in. Used by the landing (/plan/ask) and the
// results (/plan/matrix). Reference: docs/design/booking-v2/index.html. The page works without this script as a plain form (its hidden fields hold the sentence's state;
// Search posts them); the script adds the pickers (a popover under the word on a laptop, a bottom sheet on a phone), the glide of the sentence up into the results, and
// the re-search when a word changes on the results. `text` says the same words as gitaway/v2sentence.py `words`: change one, change the other
// (tests_browser/test_v2_sentence.py compares them). Motion: only the --v2-* tokens in v2-tokens.css, read here with getComputedStyle; nothing in this file is a time.
(function () {
  var raw = document.getElementById('v2-data');
  var sent = document.getElementById('v2-sent');
  var pop = document.getElementById('v2-pop');
  var scrim = document.getElementById('v2-scrim');
  var form = document.getElementById('v2-form');
  if (!raw || !sent || !pop) return;
  var S = JSON.parse(raw.textContent);
  var root = document.querySelector('.v2'), stage = document.querySelector('[data-v2]');
  var cs = getComputedStyle(document.documentElement);
  var RM = window.matchMedia('(prefers-reduced-motion: reduce)');
  var DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var MONTH = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  var open = null, snapshot = '', calMonth = null;

  function tok(n) { var v = cs.getPropertyValue(n).trim(); return v.slice(-2) === 'ms' ? parseFloat(v) : (v.slice(-1) === 's' ? parseFloat(v) * 1000 : parseFloat(v)); }
  function ease(n) { return cs.getPropertyValue(n).trim(); }
  function money(n) { return '$' + Math.round(n).toLocaleString('en-US'); }
  function iso(d) { return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
  function parse(s) { var p = s.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function esc(t) { return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

  // ---- the words (gitaway/v2sentence.py `words`) ----
  function whoText() {
    var n = S.adults + S.kids.length;
    if (S.kids.length) return 'A family of ' + n;
    return S.adults === 1 ? 'Just me' : (S.adults === 2 ? 'The two of us' : S.adults + ' adults');
  }
  function intoText() {
    var label = {};
    S.interests.forEach(function (i) { label[i[0]] = i[1].toLowerCase(); });
    var names = S.into.filter(function (k) { return label[k]; }).map(function (k) { return label[k]; });
    if (!names.length) return 'anything';
    return names.length === 1 ? names[0] : names.slice(0, -1).join(', ') + ' & ' + names[names.length - 1];
  }
  function text(k) {
    switch (k) {
      case 'who': return whoText();
      case 'from': return S.home || 'anywhere';
      case 'where': return S.to + (S.nearby ? ', or nearby' : '');
      case 'start': var d = parse(S.depart); return DOW[d.getDay()] + ', ' + MON[d.getMonth()] + ' ' + d.getDate();
      case 'flex': return S.flex === 0 ? 'on the dot' : 'give or take ' + S.flex + ' day' + (S.flex === 1 ? '' : 's');
      case 'nights': return S.nights + ' night' + (S.nights === 1 ? '' : 's');
      case 'budget': return S.budget ? money(S.budget) : 'any budget';
      case 'into': return intoText();
    }
    return '';
  }
  function word(k) {
    return '<span role="button" tabindex="0" class="v2-w" data-k="' + k + '" aria-haspopup="dialog" aria-expanded="false" aria-label="' + esc(S.labels[k] + ': ' + text(k)) + '">' + esc(text(k)) + '</span>';
  }
  function drawSentence() {
    var fill = function (t) { return '<span class="fill">' + t + '</span>'; };
    sent.innerHTML = word('who') + ' ' + fill('from') + ' ' + word('from') + ' ' + fill('to') + ' ' + word('where') + fill(', around') + ' ' + word('start') + fill(',') + ' ' + word('flex') +
      fill(', for') + ' ' + word('nights') + fill(S.budget ? ', under' : ', with') + ' ' + word('budget') + fill(', into') + ' ' + word('into') + fill('.');
    syncForm();
  }
  function syncForm() {      // the hidden fields the plain form posts: what the words say, in the matrix's own parameters (gitaway/v2sentence.py `address`)
    if (!form) return;
    var set = function (n, v) { var f = form.elements[n]; if (f) f.value = v; };
    set('to', S.to); set('home', S.home); set('d', S.depart); set('n', S.nights); set('a', S.adults); set('k', S.kids.join(',')); set('x', S.flex); set('nb', S.nearby ? '' : '0'); set('b', S.budget || '');
    form.querySelectorAll('input[name="i"]').forEach(function (i) { i.remove(); });
    S.into.forEach(function (k) { var i = document.createElement('input'); i.type = 'hidden'; i.name = 'i'; i.value = k; form.appendChild(i); });
  }

  // ---- the pickers ----
  function stepper(id, v, min, max) {
    return '<div class="v2-step"><button type="button" data-st="' + id + '" data-dv="-1"' + (v <= min ? ' disabled' : '') + ' aria-label="Fewer">−</button><output class="num">' + v +
      '</output><button type="button" data-st="' + id + '" data-dv="1"' + (v >= max ? ' disabled' : '') + ' aria-label="More">+</button></div>';
  }
  function whoBody() {
    var L = S.limits, full = S.adults + S.kids.length >= L.travelers;
    var h = '<div class="big">' + whoText() + '</div><div class="row"><div><b>Adults</b><small>18 and over</small></div>' + stepper('adults', S.adults, L.adults[0], full ? S.adults : L.adults[1]) +
      '</div><div class="row"><div><b>Kids</b><small>17 and under</small></div>' + stepper('kids', S.kids.length, L.kids[0], full ? S.kids.length : L.kids[1]) + '</div>';
    S.kids.forEach(function (a, i) {
      h += '<div class="row"><div><b>Kid ' + (i + 1) + '</b><small>Age</small></div>' + stepper('age' + i, a, 0, L.kidAge) + '</div>';
    });
    if (full) h += '<p class="note">GitAway plans for up to ' + L.travelers + ' travelers.</p>';
    return h;
  }
  function chips(items, current, attr) {
    return '<div class="v2-chips">' + items.map(function (it) {
      return '<button type="button" class="v2-chip" ' + attr + '="' + esc(it[0]) + '" aria-pressed="' + (current === it[0]) + '">' + it[1] + '</button>';
    }).join('') + '</div>';
  }
  function calBody() {
    var today = parse(S.today), last = parse(S.last), cur = parse(S.depart);
    if (!calMonth) calMonth = new Date(cur.getFullYear(), cur.getMonth(), 1);
    var first = new Date(calMonth.getFullYear(), calMonth.getMonth(), 1), days = new Date(calMonth.getFullYear(), calMonth.getMonth() + 1, 0).getDate();
    var prev = new Date(first.getFullYear(), first.getMonth() - 1, 1), next = new Date(first.getFullYear(), first.getMonth() + 1, 1);
    var canPrev = new Date(first.getFullYear(), first.getMonth(), 0) >= today, canNext = next <= last;
    var h = '<div class="v2-cal-h"><div class="big">' + MONTH[first.getMonth()] + ' ' + first.getFullYear() + '</div><div class="v2-step">' +
      '<button type="button" data-month="' + iso(prev) + '"' + (canPrev ? '' : ' disabled') + ' aria-label="Earlier month">‹</button>' +
      '<button type="button" data-month="' + iso(next) + '"' + (canNext ? '' : ' disabled') + ' aria-label="Later month">›</button></div></div>';
    h += '<div class="v2-cal">' + ['M', 'T', 'W', 'T', 'F', 'S', 'S'].map(function (x) { return '<span>' + x + '</span>'; }).join('');
    for (var b = (first.getDay() + 6) % 7; b > 0; b--) h += '<i></i>';
    for (var d = 1; d <= days; d++) {
      var day = new Date(first.getFullYear(), first.getMonth(), d), w = day.getDay();
      h += '<button type="button" data-set="start" data-v="' + iso(day) + '"' + (day < today || day > last ? ' disabled' : '') + ' class="num' + (w === 0 || w === 6 ? ' wk' : '') + '" aria-pressed="' + (iso(day) === S.depart) +
        '" aria-label="' + DOW[w] + ', ' + MON[day.getMonth()] + ' ' + d + '">' + d + '</button>';
    }
    return h + '</div>';
  }
  function body(k) {
    var h = '<h4>' + S.labels[k] + '</h4>', L = S.limits;
    switch (k) {
      case 'who': return h + whoBody();
      case 'from': return h + chips(S.airports.map(function (a) { return [a[0], '<b>' + a[0] + '</b> ' + a[1]]; }), S.home, 'data-home');
      case 'where':
        var cur = S.places.filter(function (p) { return p.n === S.to; })[0];
        return h + chips(S.places.map(function (p) { return [p.n, esc(p.n)]; }), S.to, 'data-to') +
          (cur && cur.near ? '<div class="row"><div><b>Or nearby</b><small>Places close by, and two-place trips</small></div><button type="button" class="v2-switch" role="switch" data-tog="nearby" aria-checked="' + S.nearby + '" aria-label="Or nearby"></button></div>' : '');
      case 'start': return h + calBody();
      case 'flex':
        var opts = [];
        for (var i = L.flex[0]; i <= L.flex[1]; i++) opts.push([String(i), i ? '± ' + i + ' day' + (i === 1 ? '' : 's') : 'Exact day']);
        return h + chips(opts, String(S.flex), 'data-flex') + '<p class="note">More days give you more columns to compare.</p>';
      case 'nights':
        var pct = Math.round((S.nights - L.nights[0]) * 100 / (L.nights[1] - L.nights[0])), ticks = '';
        for (var n = L.nights[0]; n <= L.nights[1]; n++) ticks += '<span>' + n + '</span>';
        return h + '<div class="big num" id="v2-pv">' + text('nights') + '</div><input class="v2-range" type="range" min="' + L.nights[0] + '" max="' + L.nights[1] + '" step="1" value="' + S.nights +
          '" data-rng="nights" data-nights="1" aria-label="Nights" aria-valuetext="' + text('nights') + '" style="--fill: ' + pct + '%"><div class="v2-ticks">' + ticks + '</div>';
      case 'budget':
        var any = !S.budget, B = L.budget;
        return h + '<div class="big num" id="v2-pv">' + (any ? 'Any budget' : money(S.budget) + ' <span style="font-size:18px;color:var(--ink-2);letter-spacing:0">all in, for ' + (S.adults + S.kids.length) + '</span>') + '</div>' +
          (any ? '' : '<input class="v2-range" type="range" min="' + B[0] + '" max="' + B[1] + '" step="' + B[2] + '" value="' + Math.min(B[1], Math.max(B[0], S.budget)) + '" data-rng="budget" aria-label="Budget"><div class="v2-ticks"><span>' + money(B[0]) + '</span><span>' + money((B[0] + B[1]) / 2) + '</span><span>' + money(B[1]) + '</span></div>') +
          '<div class="row"><div><b>Any budget</b><small>Mark nothing as over</small></div><button type="button" class="v2-switch" role="switch" data-tog="anybudget" aria-checked="' + any + '" aria-label="Any budget"></button></div>';
      case 'into':
        return h + '<div class="v2-chips">' + S.interests.map(function (i) {
          return '<button type="button" class="v2-chip" data-multi="' + i[0] + '" aria-pressed="' + (S.into.indexOf(i[0]) >= 0) + '">' + i[1] + '</button>';
        }).join('') + '</div>';
    }
    return h;
  }
  function snap() { return JSON.stringify([S.adults, S.kids, S.home, S.to, S.nearby, S.depart, S.flex, S.nights, S.budget, S.into]); }
  function fillPop() { pop.innerHTML = body(open) + '<button type="button" class="v2-done">Done</button>'; }
  function run(el, kf, ms, easing) { if (!RM.matches) el.animate(kf, { duration: ms, easing: easing }); }

  function openPop(btn) {
    if (!pop.hidden) { var same = open === btn.dataset.k; closePop(); if (same) return; }
    open = btn.dataset.k; snapshot = snap(); calMonth = null;
    fillPop();
    pop.hidden = false; btn.setAttribute('aria-expanded', 'true'); document.body.classList.add('pop-open');
    pop.setAttribute('aria-label', S.labels[open]);
    var phone = window.innerWidth < 720;
    pop.classList.toggle('as-sheet', phone);
    scrim.classList.add('on');
    var kf;
    if (!phone) {
      var r = btn.getBoundingClientRect(), pw = pop.offsetWidth, ph = pop.offsetHeight;
      var left = Math.min(Math.max(12, r.left + r.width / 2 - pw / 2), window.innerWidth - pw - 12);
      var top = r.bottom + 10; if (top + ph > window.innerHeight - 12) top = Math.max(12, r.top - ph - 10);
      pop.style.left = left + 'px'; pop.style.top = top + 'px';
      pop.style.transformOrigin = (r.left + r.width / 2 - left) + 'px ' + (top > r.top ? 0 : ph) + 'px';
      kf = [{ transform: 'scale(.94) translateY(-6px)', opacity: 0 }, { transform: 'none', opacity: 1 }];
      run(pop, kf, tok('--v2-pop'), ease('--v2-ease'));
    } else {
      pop.style.left = ''; pop.style.top = ''; pop.style.transformOrigin = '50% 100%';
      kf = [{ transform: 'translateY(40px)', opacity: 0 }, { transform: 'none', opacity: 1 }];
      run(pop, kf, tok('--v2-sheet'), ease('--spring-soft'));
    }
    var first = pop.querySelector('[aria-pressed="true"], input, button');
    if (first) first.focus({ preventScroll: true });
  }
  function closePop(silent) {
    if (pop.hidden) return;
    var k = open; open = null;
    sent.querySelectorAll('.v2-w[aria-expanded="true"]').forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
    scrim.classList.remove('on'); document.body.classList.remove('pop-open');
    var end = function () { pop.hidden = true; };
    if (RM.matches || silent) end(); else { var kf = [{ opacity: 1 }, { opacity: 0 }]; pop.animate(kf, { duration: tok('--v2-out') }).onfinish = end; }
    if (silent) return;
    if (snapshot !== snap()) changed(k);
    else { var w = sent.querySelector('.v2-w[data-k="' + k + '"]'); if (w) w.focus({ preventScroll: true }); }
  }
  function refresh(k) {
    drawSentence();
    var b = sent.querySelector('.v2-w[data-k="' + k + '"]');
    if (b) { b.setAttribute('aria-expanded', 'true'); b.classList.add('flash'); }
    if (k === 'who') sent.querySelectorAll('.v2-w[data-k="budget"]').forEach(function (x) { x.classList.add('flash'); });
  }

  pop.addEventListener('click', function (e) {
    var t = e.target.closest('button'); if (!t) return;
    if (t.classList.contains('v2-done')) return closePop();
    if (t.dataset.st) {
      var id = t.dataset.st, dv = +t.dataset.dv;
      if (id === 'adults') S.adults = Math.max(S.limits.adults[0], S.adults + dv);
      else if (id === 'kids') { if (dv > 0) S.kids.push(S.limits.defaultAge); else S.kids.pop(); }
      else { var i = +id.slice(3); S.kids[i] = Math.max(0, Math.min(S.limits.kidAge, S.kids[i] + dv)); }
    } else if (t.dataset.home) S.home = t.dataset.home;
    else if (t.dataset.to) { S.to = t.dataset.to; var p = S.places.filter(function (x) { return x.n === S.to; })[0]; if (!p || !p.near) S.nearby = false; else if (!S.nearby) S.nearby = true; }
    else if (t.dataset.flex !== undefined) S.flex = +t.dataset.flex;
    else if (t.dataset.set === 'start') S.depart = t.dataset.v;
    else if (t.dataset.month) { calMonth = parse(t.dataset.month); }
    else if (t.dataset.tog === 'nearby') S.nearby = !S.nearby;
    else if (t.dataset.tog === 'anybudget') S.budget = S.budget ? 0 : 2500;
    else if (t.dataset.multi) { var m = t.dataset.multi; S.into = S.into.indexOf(m) >= 0 ? S.into.filter(function (x) { return x !== m; }) : S.into.concat(m); S.into = S.interests.map(function (i) { return i[0]; }).filter(function (x) { return S.into.indexOf(x) >= 0; }); }
    else return;
    var scrollT = pop.scrollTop;
    fillPop(); pop.scrollTop = scrollT;
    refresh(open);
    var same = pop.querySelector('[data-st="' + t.dataset.st + '"][data-dv="' + t.dataset.dv + '"], [data-home="' + t.dataset.home + '"], [data-to="' + t.dataset.to + '"], [data-flex="' + t.dataset.flex + '"], [data-set="start"][data-v="' + t.dataset.v + '"], [data-month="' + t.dataset.month + '"], [data-tog="' + t.dataset.tog + '"], [data-multi="' + t.dataset.multi + '"]');
    if (same) same.focus({ preventScroll: true });
  });
  pop.addEventListener('input', function (e) {
    var r = e.target.closest('[data-rng]'); if (!r) return;
    S[r.dataset.rng] = +r.value;
    var pv = document.getElementById('v2-pv');
    if (pv) pv.innerHTML = r.dataset.rng === 'nights' ? text('nights') : money(S.budget) + ' <span style="font-size:18px;color:var(--ink-2);letter-spacing:0">all in, for ' + (S.adults + S.kids.length) + '</span>';
    if (r.dataset.rng === 'nights') { r.setAttribute('aria-valuetext', text('nights')); r.style.setProperty('--fill', Math.round((S.nights - S.limits.nights[0]) * 100 / (S.limits.nights[1] - S.limits.nights[0])) + '%'); }
    drawSentence(); var w = sent.querySelector('.v2-w[data-k="' + open + '"]'); if (w) w.setAttribute('aria-expanded', 'true');
  });
  sent.addEventListener('click', function (e) { var b = e.target.closest('.v2-w'); if (b) { e.stopPropagation(); openPop(b); } });
  sent.addEventListener('keydown', function (e) { var b = e.target.closest('.v2-w'); if (b && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openPop(b); } });
  scrim.addEventListener('click', function () { closePop(); });
  document.addEventListener('pointerdown', function (e) { if (!pop.hidden && !pop.contains(e.target) && !e.target.closest('.v2-w') && window.innerWidth >= 720) closePop(); });
  addEventListener('keydown', function (e) { if (e.key === 'Escape' && !pop.hidden) closePop(); });

  // ---- what a change does: on the landing nothing until Search; on the results it searches again (or, for the interests alone, keeps them) ----
  function post() {
    syncForm();
    return fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'X-V2': '1', Accept: 'application/json' }, credentials: 'same-origin' }).then(function (r) { return r.json(); });
  }
  function changed(k) {
    if (!form || stage.dataset.v2 !== 'results') return;
    if (k === 'nights') return;      // the matrix's own slider handles the nights in place (assets/js/tripmatrix.js)
    var was = JSON.parse(snapshot);
    var onlyInto = JSON.stringify(was.slice(0, 9)) === JSON.stringify([S.adults, S.kids, S.home, S.to, S.nearby, S.depart, S.flex, S.nights, S.budget]);
    post().then(function (j) { if (!onlyInto && j.to) { go(j.to); } });
  }
  function go(to) { document.documentElement.classList.add('v2-leaving'); location.assign(to); }

  // ---- Search on the landing: the sentence glides to the top and the results' skeleton plays, then the matrix opens ----
  function glide() {
    var a = sent.getBoundingClientRect(), fa = parseFloat(getComputedStyle(sent).fontSize);
    root.classList.add('is-results');
    var b = sent.getBoundingClientRect(), fb = parseFloat(getComputedStyle(sent).fontSize);
    if (RM.matches) return Promise.resolve();
    var s = fa / fb, kf = [{ transform: 'translate(' + (a.left - b.left) + 'px, ' + (a.top - b.top) + 'px) scale(' + s + ')', opacity: 0.85 }, { transform: 'none', opacity: 1 }];
    return sent.animate(kf, { duration: tok('--v2-glide'), easing: ease('--spring-soft') }).finished.catch(function () {});
  }
  if (form && stage.dataset.v2 === 'landing') {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var skel = document.getElementById('v2-skel');
      var moved = glide();
      if (skel) { skel.hidden = false; skel.classList.add('is-in'); }
      post().then(function (j) {
        if (j.error) { root.classList.remove('is-results'); if (skel) skel.hidden = true; showError(j.error); return; }
        moved.then(function () { go(j.to); });
      }).catch(function () { form.submit(); });
    });
  }
  function showError(msg) {
    var p = document.getElementById('v2-error');
    if (!p) return;
    p.textContent = msg; p.hidden = false;
  }
  window.addEventListener('pageshow', function (e) { if (e.persisted) { root.classList.remove('is-results'); document.documentElement.classList.remove('v2-leaving'); } });      // back from the matrix: the landing, not a skeleton
  window.V2 = { spec: S, text: text, drawSentence: drawSentence };
  syncForm();
})();
