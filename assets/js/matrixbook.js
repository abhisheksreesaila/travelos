// Book my trip (F-233, D-480 to D-489; the prototype's flow in F-251, D-620: docs/design/booking-v2/index.html `startBooking`, `openSheet`, `drawSheet`). The drawer's Book button is a plain form
// (POST /plan/matrix/book): without this script it is a page of the same words, the four questions all open and one button that books. With it:
//   1. The button spins while the room is really held (LiteAPI's sandbox prebook, or a stand-in for a sample square), then the answer (the questions) opens as a sheet that GROWS OUT OF THE
//      BUTTON (GA.motion.open: the liquid spring on a phone, and on the matrix a laptop too, D-439) and folds back into it. Reduced motion: it fades. Escape, the scrim and a pull down close it.
//   2. The questions come one at a time under a progress bar: lead guest, contact, requests, then the review with Edit links, a sum and a required tick. Continue checks the question in place
//      (the browser's own words); Enter does the same; Back and every Edit go back with the page sliding the other way. Nothing is sent until Book. The phone number, the requests and the
//      arrival never leave the page (only the lead guest's name and email go to the server, and on to LiteAPI).
//   3. Booking plays out step by step (holding the room, paying with the test card, booking, putting the trip together) while the real POST to /plan/matrix/book/confirm runs: each step takes a
//      few frames of a spinner at the pace of the --v2-step token, the booking step waits for the real answer, and a mistake or a refusal opens the question it is in with the typed words kept.
//      Then the stamped pass settles in (its confetti is CSS, none under reduced motion) and "Plan this trip" is a plain link to the trip.
// A viewer is told in a word (the server answers 403 before anything is asked of LiteAPI); a signed-out person is sent to sign in (the redirect is followed).
(function () {
  var sheet = null, scrim = null, origin = null;
  var M = function () { return window.GA && GA.motion; };
  var X = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  var TICK = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';

  function reduced() { return M() ? M().reduced() : window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
  function tok(n) { return parseFloat(getComputedStyle(document.documentElement).getPropertyValue(n)) || 0; }
  function pace() { return reduced() ? tok('--motion-fade') || 120 : tok('--v2-step') || 850; }      // a step of the progress; under reduced motion, a fade
  function wait(ms) { return new Promise(function (done) { setTimeout(done, ms); }); }

  function post(form) {
    return fetch(form.action, { method: 'POST', body: new URLSearchParams(new FormData(form)), headers: { 'X-Matrix': '1' }, credentials: 'same-origin' })
      .then(function (r) {
        if (r.status === 403) return { refused: true };
        if (r.redirected && r.url.indexOf('/signin') >= 0) { location.href = r.url; return { gone: true }; }
        if ((!r.ok && r.status !== 429) || (r.headers.get('content-type') || '').indexOf('html') < 0) throw new Error(r.status);
        return r.text().then(function (html) { return { html: html }; });
      })
      .catch(function () { return { failed: true }; });
  }

  function say(form, words) {
    var old = form.parentNode.querySelector('.mx-book-said');
    if (old) old.remove();
    var p = document.createElement('p');
    p.className = 'mx-saved mx-book-said';
    p.setAttribute('role', 'status');
    p.textContent = words;
    form.parentNode.insertBefore(p, form.nextSibling);
    if (M()) (M().reduced() ? M().fade(p) : M().settle(p, { y: 4 }));
  }

  function begin(form) {
    var button = form.querySelector('button[type=submit]'), started = Date.now(), minimum = reduced() ? 0 : tok('--v2-book-spin');
    button.classList.add('is-busy');
    button.setAttribute('aria-busy', 'true');
    button.disabled = true;
    var settle = function () { button.disabled = false; button.classList.remove('is-busy'); button.removeAttribute('aria-busy'); };
    post(form).then(function (got) {
      return wait(Math.max(0, minimum - (Date.now() - started))).then(function () { return got; });      // the spin is seen: a room check is not a blink
    }).then(function (got) {
      if (got.gone) return;
      if (got.refused) { settle(); return say(form, 'Only an editor in your family can book.'); }
      if (got.failed) { settle(); return say(form, 'Could not hold the room just now. Try again.'); }
      var old = document.querySelector('.mx-book-said');
      if (old) old.remove();
      show(got.html, button, settle);
    });
  }

  function show(html, from, settle) {
    if (sheet) close(true);
    origin = from;
    scrim = document.createElement('div');
    scrim.className = 'mxb-scrim';
    sheet = document.createElement('div');
    sheet.className = 'mxb-sheet';
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-modal', 'true');
    sheet.setAttribute('aria-label', 'Book my trip');
    sheet.innerHTML = '<div class="mxb-bar"><span class="mx-grab" aria-hidden="true"></span><button type="button" class="mx-x" aria-label="Close">' + X + '</button></div><div class="mxb-in"></div>';
    sheet.querySelector('.mxb-in').innerHTML = html;
    document.body.appendChild(scrim);
    document.body.appendChild(sheet);
    document.body.classList.add('sheet-open');
    scrim.addEventListener('click', function () { close(); });
    sheet.querySelector('.mx-x').addEventListener('click', function () { close(); });
    sheet.addEventListener('click', function (e) { if (e.target.closest('[data-close]')) { e.preventDefault(); close(); } });
    drag(sheet);
    fold(sheet.querySelector('.mxb-f'));
    if (M()) M().open(sheet, from, { scrim: scrim, content: sheet.querySelector('.mxb-in'), radius: [14, 26] });
    if (settle) settle();
    var first = sheet.querySelector('.mxb-pane.is-on input:not([type=hidden])') || sheet.querySelector('input:not([type=hidden])') || sheet.querySelector('.mx-x');
    first.focus({ preventScroll: true });
  }

  function close(now) {
    if (!sheet) return;
    var s = sheet, sc = scrim, from = origin && document.body.contains(origin) ? origin : null;
    sheet = scrim = origin = null;
    document.body.classList.remove('sheet-open');
    var done = function () { s.remove(); sc.remove(); };
    if (!now && M()) M().close(s, from, { scrim: sc }).then(done); else done();
    if (from) from.focus({ preventScroll: true });
  }

  function drag(s) {
    var bar = s.querySelector('.mxb-bar'), y0 = null, dy = 0;
    bar.addEventListener('pointerdown', function (e) { if (e.target.closest('.mx-x')) return; y0 = e.clientY; dy = 0; bar.setPointerCapture(e.pointerId); });
    bar.addEventListener('pointermove', function (e) { if (y0 == null) return; dy = Math.max(0, e.clientY - y0); s.style.transform = 'translateY(' + dy + 'px)'; });
    bar.addEventListener('pointerup', function () {
      if (y0 == null) return;
      y0 = null;
      if (dy > 80) { s.style.transform = ''; close(); } else if (M()) { M().spring(s, s.style.transform); s.style.transform = ''; } else s.style.transform = '';
    });
  }

  // ---- the four questions ----
  var LAST = 3;
  function panes(form) { return Array.prototype.slice.call(form.querySelectorAll('.mxb-pane')); }
  function field(form, name) { return form.querySelector('[name="' + name + '"]'); }
  function val(form, name) { var f = field(form, name); return f ? f.value.trim() : ''; }
  function review(form) {      // the review says what was typed; the phone, the requests and the arrival are only read here, never posted by name
    var set = function (k, text) { var el = form.querySelector('[data-rv="' + k + '"]'); if (el) el.textContent = text; };
    set('guest', [val(form, 'first'), val(form, 'last')].filter(Boolean).join(' ') + ' + ' + (form.dataset.travel || '0'));
    set('contact', val(form, 'email'));
    set('contact-s', val(form, 'phone'));
    var picked = Array.prototype.map.call(form.querySelectorAll('[data-req][aria-pressed="true"]'), function (c) { return c.dataset.req; });
    var arrive = form.querySelector('[data-arr][aria-pressed="true"]');
    set('requests', picked.join(', ') || 'None');
    set('requests-s', arrive ? 'Arriving in the ' + arrive.dataset.arr.toLowerCase() : '');
  }
  function ready(form) { var go = form.querySelector('.mxb-go'), tick = form.querySelector('.mxb-tick'); if (go && tick) go.disabled = !tick.checked; }
  function go(form, i, dir, quiet) {
    var ps = panes(form);
    i = Math.max(0, Math.min(LAST, i));
    ps.forEach(function (p, k) { p.classList.toggle('is-on', k === i); p.classList.toggle('is-back', dir < 0 && k === i); });
    form.dataset.step = String(i);
    Array.prototype.forEach.call(form.querySelectorAll('.mxb-prog span'), function (b, k) { b.classList.toggle('on', k <= i); });
    var n = form.querySelector('.mxb-stepn');
    if (n) n.textContent = 'Step ' + (i + 1) + ' of ' + (LAST + 1);
    var k0 = sheet && sheet.querySelector('.mxb-k0');
    if (k0 && ps[i]) k0.textContent = ps[i].dataset.small;
    if (i === LAST) review(form);
    ready(form);
    var box = form.querySelector('.mxb-panes');
    if (box) box.scrollTop = 0;
    if (!quiet) { var f = ps[i].querySelector('input:not([type=hidden])') || form.querySelector(i === LAST ? '.mxb-tick' : '[data-cont]'); if (f) f.focus({ preventScroll: true }); }
  }
  function fold(form) {
    if (!form) return;
    form.classList.add('is-fold');
    go(form, parseInt(form.dataset.step, 10) || 0, 1, true);
  }
  function next(form) {      // Continue: say what is wrong in place, with the browser's own words, before going on
    var at = parseInt(form.dataset.step, 10) || 0, bad = Array.prototype.filter.call(panes(form)[at].querySelectorAll('input[required], input[type=email], input[type=tel]'), function (el) { return !el.checkValidity(); })[0];
    if (bad) { bad.reportValidity(); bad.focus({ preventScroll: true }); return; }
    go(form, at + 1, 1);
  }

  // ---- the booking plays out ----
  function stagesEl(names) {
    var run = document.createElement('div');
    run.className = 'mxb-run';
    run.setAttribute('role', 'status');
    run.setAttribute('aria-live', 'polite');
    run.innerHTML = '<div class="mxb-run-top"><span class="mxb-spin" aria-hidden="true"></span><h3 class="mxb-q">Booking your trip…</h3></div><ol class="mxb-stages"></ol>';
    var ol = run.querySelector('ol');
    names.forEach(function (n) {
      var li = document.createElement('li');
      li.dataset.state = 'todo';
      li.innerHTML = '<span class="mxb-st-i" aria-hidden="true">' + TICK + '</span><span class="mxb-st-t"></span>';
      li.querySelector('.mxb-st-t').textContent = n;
      ol.appendChild(li);
    });
    return run;
  }
  function mark(run, i, state) { var li = run.querySelectorAll('li')[i]; if (li) li.dataset.state = state; }

  function step(form) {
    var names = (form.dataset.stages || '').split('|').filter(Boolean), run = stagesEl(names), button = form.querySelector('button[type=submit]');
    var p = pace(), asked = post(form);      // the real call starts now; the steps below take their time beside it
    button.disabled = true;
    form.hidden = true;
    form.parentNode.insertBefore(run, form.nextSibling);
    sheet.scrollTop = 0;
    if (M()) (M().reduced() ? M().fade(run) : M().settle(run, { y: 10 }));
    var back = function (fn) { run.remove(); form.hidden = false; button.disabled = false; ready(form); fn && fn(); };
    mark(run, 0, 'active');
    wait(p * 0.6).then(function () { mark(run, 0, 'done'); mark(run, 1, 'active'); return wait(p); })      // the room was held when the sheet opened; the test card pays (no money moves)
      .then(function () { mark(run, 1, 'done'); mark(run, 2, 'active'); return Promise.all([asked, wait(p)]); })
      .then(function (both) {
        var got = both[0];
        if (!sheet) return;
        if (got.gone) return;
        if (got.refused) return back(function () { swap('<div class="mxb" data-at="room"><div class="mxb-problem"><p class="mxb-note is-warn" role="alert">Only an editor in your family can book.</p></div></div>'); });
        if (got.failed) {
          return back(function () {
            var n = form.parentNode.querySelector('.mxb-fail') || document.createElement('p');
            n.className = 'mxb-note is-warn mxb-fail';
            n.setAttribute('role', 'alert');
            n.textContent = 'We could not confirm the booking just now. Check your trip before you try again.';
            form.parentNode.insertBefore(n, form);
          });
        }
        var booked = /data-at="booked"/.test(got.html.slice(0, 300));
        if (!booked) return back(function () { swap(got.html); });      // a mistake in a field, a room taken, a failed booking: the question again, the words kept
        mark(run, 2, 'done');
        mark(run, 3, 'active');
        return wait(p * 0.6).then(function () { mark(run, 3, 'done'); return wait(p * 0.4); }).then(function () { if (sheet) swap(got.html); });
      });
  }

  // the answer replaces the body (the head's pill changes in place)
  function swap(html) {
    var inner = sheet.querySelector('.mxb-in'), cur = inner.querySelector('.mxb');
    var next = new DOMParser().parseFromString(html, 'text/html').querySelector('.mxb');
    if (!cur || !next) { inner.innerHTML = html; return; }
    var pill = cur.querySelector('.mxb-head .mxb-sandbox'), pillNext = next.querySelector('.mxb-head .mxb-sandbox');
    if (pill && pillNext) { pill.className = pillNext.className; pill.innerHTML = pillNext.innerHTML; }
    var k0 = cur.querySelector('.mxb-k0'), k0Next = next.querySelector('.mxb-k0');
    if (k0 && k0Next) k0.textContent = k0Next.textContent;
    var body = cur.lastElementChild, fresh = next.lastElementChild;
    cur.dataset.at = next.dataset.at;
    body.replaceWith(fresh);
    sheet.scrollTop = 0;
    fold(fresh.querySelector('.mxb-f'));
    if (M()) (M().reduced() ? M().fade(fresh) : M().settle(fresh, { y: 12 }));
    var focus = fresh.querySelector('[aria-invalid="true"]') || fresh.querySelector('.mxb-pane.is-on input:not([type=hidden])') || fresh.querySelector('a.mxb-plan');
    if (focus) focus.focus({ preventScroll: true });
  }

  document.addEventListener('click', function (e) {
    if (!sheet || !e.target.closest) return;
    var f = e.target.closest('.mxb-f');
    if (!f || !sheet.contains(f)) return;
    var t = e.target.closest('[data-cont], [data-back], [data-go], [data-req], [data-arr]');
    if (!t) return;
    var at = parseInt(f.dataset.step, 10) || 0;
    if (t.matches('[data-cont]')) { e.preventDefault(); next(f); }
    else if (t.matches('[data-back]')) { e.preventDefault(); go(f, at - 1, -1); }
    else if (t.matches('[data-go]')) { e.preventDefault(); go(f, parseInt(t.dataset.go, 10), -1); }
    else if (t.matches('[data-req]')) {
      t.setAttribute('aria-pressed', t.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
      field(f, 'req').value = Array.prototype.map.call(f.querySelectorAll('[data-req][aria-pressed="true"]'), function (c) { return c.dataset.req; }).join('|');
    } else if (t.matches('[data-arr]')) {
      Array.prototype.forEach.call(f.querySelectorAll('[data-arr]'), function (c) { c.setAttribute('aria-pressed', c === t ? 'true' : 'false'); });
      field(f, 'arrive').value = t.dataset.arr;
    }
  });
  document.addEventListener('change', function (e) { var f = e.target.closest && e.target.closest('.mxb-f'); if (f && e.target.matches('.mxb-tick')) ready(f); });
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f.classList) return;
    if (f.classList.contains('mx-book-f')) { e.preventDefault(); begin(f); }
    else if (f.classList.contains('mxb-f') && sheet && sheet.contains(f)) {
      e.preventDefault();
      var at = parseInt(f.dataset.step, 10) || 0;
      if (f.classList.contains('is-fold') && at < LAST) next(f);      // Enter in a field goes on to the next question
      else step(f);
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && sheet) { e.stopImmediatePropagation(); close(); }
  }, true);
})();
