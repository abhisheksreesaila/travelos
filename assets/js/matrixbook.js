// Booking a trip matrix square (F-233, D-480 to D-489). The Book button of an opened square is a plain form (POST /plan/matrix/book): without this script it is a page.
// With it:
//   1. The answer (the stays' rooms checked by LiteAPI's sandbox, and the guest form) opens as a sheet that GROWS OUT OF THE SQUARE you opened (GA.motion.open: the liquid
//      spring on a phone, and on the matrix a laptop too, D-439) and folds back into it. Reduced motion: it fades. Escape, the scrim and a pull down close it.
//   2. The guest form posts to /plan/matrix/book/confirm without leaving the sheet: the three step chips (Room, Guest, Booked) change state in place and spring, and the
//      new step settles in (GA.motion.settle). A mistake comes back in the same sheet with the typed words kept.
//   3. The confirmation shows LiteAPI's booking id; "Open your trip" is a plain link to the trip's cockpit.
// A viewer is told in a word (the server answers 403 before anything is asked of LiteAPI); a signed-out person is sent to sign in (the redirect is followed).
(function () {
  var sheet = null, scrim = null, origin = null;
  var M = function () { return window.GA && GA.motion; };
  var X = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';

  function send(form, button, busy) {
    var label = button.textContent;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    if (busy) button.dataset.was = label, button.lastChild.textContent = busy;
    return fetch(form.action, { method: 'POST', body: new URLSearchParams(new FormData(form)), headers: { 'X-Matrix': '1' }, credentials: 'same-origin' })
      .then(function (r) {
        if (r.status === 403) return { refused: true };
        if (r.redirected && r.url.indexOf('/signin') >= 0) { location.href = r.url; return { gone: true }; }
        if (!r.ok || (r.headers.get('content-type') || '').indexOf('html') < 0) throw new Error(r.status);
        return r.text().then(function (html) { return { html: html }; });
      })
      .catch(function () { return { failed: true }; })
      .then(function (got) {
        button.disabled = false;
        button.removeAttribute('aria-busy');
        if (button.dataset.was && button.lastChild) button.lastChild.textContent = button.dataset.was.trim();
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
    send(form, button, 'Checking the room…').then(function (got) {
      if (got.gone) return;
      if (got.refused) return say(form, 'Only an editor in your family can book.');
      if (got.failed) return say(form, 'Could not check the room just now. Try again.');
      var old = form.parentNode.querySelector('.mx-book-said');
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

  // the next step: the chips change state in place (CSS springs them), the pill is replaced, the body settles in
  function swap(html) {
    var inner = sheet.querySelector('.mxb-in'), cur = inner.querySelector('.mxb');
    var next = new DOMParser().parseFromString(html, 'text/html').querySelector('.mxb');
    if (!cur || !next) { inner.innerHTML = html; return; }
    var a = cur.querySelectorAll('.mxb-step'), b = next.querySelectorAll('.mxb-step');
    Array.prototype.forEach.call(a, function (el, i) { if (b[i]) el.dataset.state = b[i].dataset.state; });
    var pill = cur.querySelector('.mxb-head .mxb-sandbox'), pillNext = next.querySelector('.mxb-head .mxb-sandbox');
    if (pill && pillNext) { pill.className = pillNext.className; pill.innerHTML = pillNext.innerHTML; }
    var body = cur.lastElementChild, fresh = next.lastElementChild;
    cur.dataset.at = next.dataset.at;
    body.replaceWith(fresh);
    sheet.scrollTop = 0;
    if (M()) (M().reduced() ? M().fade(fresh) : M().settle(fresh, { y: 12 }));
    var focus = fresh.querySelector('[aria-invalid="true"]') || fresh.querySelector('input:not([type=hidden])') || fresh.querySelector('a.btn');
    if (focus) focus.focus({ preventScroll: true });
  }

  function step(form) {
    var button = form.querySelector('button[type=submit]');
    send(form, button, 'Booking…').then(function (got) {
      if (got.gone || !sheet) return;
      if (got.refused) return swap('<div class="mxb" data-at="room"><div class="mxb-problem"><p class="mxb-note is-warn" role="alert">Only an editor in your family can book.</p></div></div>');
      if (got.failed) {
        var p = form.querySelector('.mxb-fail') || document.createElement('p');
        p.className = 'mxb-note is-warn mxb-fail';
        p.setAttribute('role', 'alert');
        p.textContent = 'Could not reach the booking just now. Nothing was booked. Try again.';
        form.insertBefore(p, form.querySelector('button[type=submit]'));
        return;
      }
      swap(got.html);
    });
  }

  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f.classList) return;
    if (f.classList.contains('mx-book-f')) { e.preventDefault(); begin(f); }
    else if (f.classList.contains('mxb-f') && sheet && sheet.contains(f)) { e.preventDefault(); step(f); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && sheet) { e.stopImmediatePropagation(); close(); }
  }, true);
})();
