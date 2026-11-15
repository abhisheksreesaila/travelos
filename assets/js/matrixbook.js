// Booking a trip matrix square (F-233, D-480 to D-489; the checkout redone in F-242, D-570 to D-579). The "Book this trip" button of an opened square is a plain form
// (POST /plan/matrix/book): without this script it is a page of the same words. With it:
//   1. The answer (the stays' rooms held by LiteAPI's sandbox, and the checkout) opens as a sheet that GROWS OUT OF THE SQUARE you opened (GA.motion.open: the liquid spring on
//      a phone, and on the matrix a laptop too, D-439) and folds back into it. Reduced motion: it fades. Escape, the scrim and a pull down close it.
//   2. The checkout is three folding cards (guest, payment, confirm): Continue folds one into a one-line answer with an Edit and opens the next; Enter does the same. Nothing is
//      sent until the last card's Book this trip.
//   3. Booking plays out step by step (holding the room, paying with the test card, booking, putting the trip together) while the real POST to /plan/matrix/book/confirm runs:
//      each step takes a few frames of a spinner at the pace of the screen tokens, the booking step waits for the real answer, and a mistake or a refusal folds the cards back
//      with the typed words kept. Then the stamped pass settles in (its confetti is CSS, none under reduced motion) and "Plan this trip" is a plain link to the trip.
// A viewer is told in a word (the server answers 403 before anything is asked of LiteAPI); a signed-out person is sent to sign in (the redirect is followed).
(function () {
  var sheet = null, scrim = null, origin = null;
  var M = function () { return window.GA && GA.motion; };
  var X = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  var TICK = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';

  function reduced() { return M() ? M().reduced() : window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
  function pace() {      // a step of the progress lasts as long as a screen moving, three times over; under reduced motion, a fade
    var root = getComputedStyle(document.documentElement), ms = parseFloat(root.getPropertyValue(reduced() ? '--motion-fade' : '--motion-screen-dur')) || 300;
    return reduced() ? ms : ms * 3;
  }
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

  function send(form, button, busy) {
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    var label = button.lastChild, was = label && label.textContent;
    if (busy && label) label.textContent = busy;
    return post(form).then(function (got) {
      button.disabled = false;
      button.removeAttribute('aria-busy');
      if (label && was) label.textContent = was;
      return got;
    });
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
    var button = form.querySelector('button');
    send(form, button, 'Holding your room…').then(function (got) {
      if (got.gone) return;
      if (got.refused) return say(form, 'Only an editor in your family can book.');
      if (got.failed) return say(form, 'Could not hold the room just now. Try again.');
      var old = document.querySelector('.mx-book-said');
      if (old) old.remove();
      var open = Array.prototype.filter.call(document.querySelectorAll('.mx-sq.is-open'), function (el) { return el.offsetParent; })[0];
      show(got.html, open || button);
    });
  }

  function show(html, from) {
    if (sheet) close(true);
    origin = from;
    scrim = document.createElement('div');
    scrim.className = 'mxb-scrim';
    sheet = document.createElement('div');
    sheet.className = 'mxb-sheet';
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-modal', 'true');
    sheet.setAttribute('aria-label', 'Book this trip');
    sheet.innerHTML = '<div class="mxb-bar"><span class="mx-grab" aria-hidden="true"></span><button type="button" class="mx-x" aria-label="Close">' + X + '</button></div><div class="mxb-in"></div>';
    sheet.querySelector('.mxb-in').innerHTML = html;
    document.body.appendChild(scrim);
    document.body.appendChild(sheet);
    scrim.addEventListener('click', function () { close(); });
    sheet.querySelector('.mx-x').addEventListener('click', function () { close(); });
    sheet.addEventListener('click', function (e) { if (e.target.closest('[data-close]')) { e.preventDefault(); close(); } });
    drag(sheet);
    fold(sheet.querySelector('.mxb-f'));
    if (M()) M().open(sheet, from, { scrim: scrim, content: sheet.querySelector('.mxb-in'), radius: [14, 26] });
    var first = sheet.querySelector('input:not([type=hidden])') || sheet.querySelector('.mx-x');
    first.focus({ preventScroll: true });
  }

  function close(now) {
    if (!sheet) return;
    var s = sheet, sc = scrim, from = origin && document.body.contains(origin) ? origin : null;
    sheet = scrim = origin = null;
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

  // ---- the folding cards ----
  var ORDER = ['guest', 'pay', 'review'];
  function cards(form) { return ORDER.map(function (k) { return form.querySelector('[data-card="' + k + '"]'); }); }
  function guestWords(form) {
    var f = form.querySelector('[name=first]'), l = form.querySelector('[name=last]');
    return [f && f.value.trim(), l && l.value.trim()].filter(Boolean).join(' ');
  }
  function show_card(form, key, quiet) {
    var at = ORDER.indexOf(key);
    cards(form).forEach(function (c, i) {
      var state = i < at ? 'done' : i === at ? 'active' : 'todo', n = c.querySelector('.mxb-n');
      c.dataset.state = state;
      n.innerHTML = state === 'done' ? TICK : c.querySelector('.mxb-n').dataset.n;
    });
    var gs = form.querySelector('[data-sum="guest"]');
    if (gs) gs.textContent = guestWords(form) + (form.querySelector('[name=email]') ? ' · ' + form.querySelector('[name=email]').value.trim() : '');
    form.dataset.step = key;
    var c = cards(form)[at];
    if (!quiet && M()) (M().reduced() ? M().fade(c.querySelector('.mxb-card-b')) : M().settle(c.querySelector('.mxb-card-b'), { y: 10 }));
  }
  function fold(form) {
    if (!form) return;
    form.classList.add('is-fold');
    show_card(form, form.dataset.step || 'guest', true);
  }
  function next(form, key) {
    if (key === 'pay') {      // the guest card: say what is wrong in place, with the browser's own words, before folding
      var bad = Array.prototype.filter.call(form.querySelectorAll('[data-card="guest"] input[required]'), function (el) { return !el.checkValidity(); })[0];
      if (bad) { bad.reportValidity(); bad.focus({ preventScroll: true }); return; }
    }
    show_card(form, key);
    var f = form.querySelector('[data-card="' + key + '"] input:not([type=hidden])') || form.querySelector('[data-card="' + key + '"] .mxb-next, [data-card="' + key + '"] .mxb-go');
    if (f) f.focus({ preventScroll: true });
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
    var back = function (fn) { run.remove(); form.hidden = false; button.disabled = false; fn && fn(); };
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
            var n = form.querySelector('.mxb-fail') || document.createElement('p');
            n.className = 'mxb-note is-warn mxb-fail';
            n.setAttribute('role', 'alert');
            n.textContent = 'We could not confirm the booking just now. Check your trip before you try again.';
            form.insertBefore(n, form.firstChild);
          });
        }
        var booked = /data-at="booked"/.test(got.html.slice(0, 300));
        if (!booked) return back(function () { swap(got.html); });      // a mistake in a field, a room taken, a failed booking: the cards again, the words kept
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
    var body = cur.lastElementChild, fresh = next.lastElementChild;
    cur.dataset.at = next.dataset.at;
    body.replaceWith(fresh);
    sheet.scrollTop = 0;
    fold(fresh.querySelector('.mxb-f'));
    if (M()) (M().reduced() ? M().fade(fresh) : M().settle(fresh, { y: 12 }));
    var focus = fresh.querySelector('[aria-invalid="true"]') || fresh.querySelector('input:not([type=hidden])') || fresh.querySelector('a.mxb-plan');
    if (focus) focus.focus({ preventScroll: true });
  }

  document.addEventListener('click', function (e) {
    var n = e.target.closest && e.target.closest('[data-next]'), ed = e.target.closest && e.target.closest('[data-edit]');
    if (n && sheet && sheet.contains(n)) { e.preventDefault(); next(n.closest('form'), n.dataset.next); }
    else if (ed && sheet && sheet.contains(ed)) { e.preventDefault(); show_card(ed.closest('form'), ed.dataset.edit); }
  });
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f.classList) return;
    if (f.classList.contains('mx-book-f')) { e.preventDefault(); begin(f); }
    else if (f.classList.contains('mxb-f') && sheet && sheet.contains(f)) {
      e.preventDefault();
      var at = f.dataset.step || 'guest';
      if (f.classList.contains('is-fold') && at !== 'review') next(f, ORDER[ORDER.indexOf(at) + 1]);      // Enter in a field goes on to the next card
      else step(f);
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && sheet) { e.stopImmediatePropagation(); close(); }
  }, true);
})();
