// What the phone's Ask sheet (ask_sheet.js, F-104) and the laptop's Ask panel (day_ask.js, F-142) do the same way, once: fetching the box ahead, posting a form with X-Ask and handing back the next
// fragment, saying what went wrong, and what follows an Apply (the day brought up to date, what changed glows, the one toast). Loaded after ask.js and before either of them.
//   AskFlow.fragments()            -> { get(url) -> { html, p }, clear() }  the box, the questions or the preview as fragments, kept 5 minutes
//   AskFlow.submit(e, o)           a submit event inside `#ak-sheet-body`: posts it with X-Ask; o = { root, alive(), fill(html), applied(json, before) }
//   AskFlow.applied(j, before, closed, wait)  after an Apply: `closed` (a promise) is the sheet or panel going away; then the day is made current (CZ.quiet, or the day that was chosen), what is new
//                                  glows and the toast says so. Returns a promise.
(function () {
  if (window.AskFlow) return;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

  function fragments(fresh) {
    var cache = {}, FRESH = fresh || 300000;
    function get(u) {
      var hit = cache[u];
      if (hit && Date.now() - hit.at < FRESH) return hit;
      var entry = { at: Date.now(), html: null, p: null };
      entry.p = fetch(u, { credentials: 'same-origin', headers: { 'X-Ask': '1' } }).then(function (r) {
        if (!r.ok) throw new Error('ask ' + r.status);
        return r.text();
      }).then(function (h) { entry.html = h; return h; });
      entry.p.catch(function () { if (cache[u] === entry) delete cache[u]; });
      cache[u] = entry;
      return entry;
    }
    return { get: get, clear: function () { cache = {}; } };
  }

  function ids() {
    var out = {};
    document.querySelectorAll('.cz-gb[data-act]').forEach(function (n) { out[n.dataset.act] = 1; });
    return out;
  }

  function oops(f, labels, text, root) {
    delete f.dataset.sent;
    clearInterval(f._clock);
    f.removeAttribute('aria-busy');
    f.querySelectorAll('button').forEach(function (b, i) { b.disabled = false; if (labels[i] !== undefined) b.textContent = labels[i]; });
    var slot = root && root.querySelector('#ak-error');
    if (!slot) {
      slot = document.createElement('div');
      slot.id = 'ak-error';
      slot.className = 'tp-error ak-error';
      slot.setAttribute('role', 'alert');
      f.insertBefore(slot, f.firstChild);
    }
    slot.textContent = text;
  }

  function submit(e, o) {
    var f = e.target;
    if (e.defaultPrevented || !f.matches || !f.closest('#ak-sheet-body')) return;
    e.preventDefault();
    var action = (e.submitter && e.submitter.getAttribute('formaction')) || f.getAttribute('action');
    var labels = Array.prototype.map.call(f.querySelectorAll('button'), function (b) { return b.textContent; });
    var before = f.id === 'ak-apply-form' ? ids() : null;
    fetch(action, { method: 'POST', body: new URLSearchParams(new FormData(f)), credentials: 'same-origin', headers: { 'X-Ask': '1' } }).then(function (r) {
      var json = /json/.test(r.headers.get('content-type') || '');
      return r.text().then(function (text) { return { ok: r.ok, status: r.status, json: json, text: text }; });
    }).then(function (r) {
      if (!o.alive()) return;
      if (r.json && r.ok) { o.applied(JSON.parse(r.text), before); return; }
      if (/id="ak-sheet-body"/.test(r.text)) { o.fill(r.text); return; }
      oops(f, labels, r.status === 403 ? 'Only editors can change the plan.' : 'That did not go through. Try again.', o.root());
    }, function () { if (o.alive()) oops(f, labels, 'That did not go through. Check the connection and try again. What you said is still here.', o.root()); });
  }

  function glow(wanted, before) {
    var hit = [];
    wanted.forEach(function (id) {
      document.querySelectorAll('.cz-gb[data-act="' + id + '"], [data-drag="' + id + '"]').forEach(function (n) { hit.push(n); });
    });
    document.querySelectorAll('.cz-gb[data-act]').forEach(function (n) { if (!before[n.dataset.act] && hit.indexOf(n) < 0) hit.push(n); });
    hit.forEach(function (n) { n.classList.add('ak-fresh'); });
    var first = hit[0];
    if (first) {
      var r = first.getBoundingClientRect();
      if (r.top < 0 || r.bottom > window.innerHeight - 96) first.scrollIntoView({ block: 'center', behavior: reduced.matches ? 'auto' : 'smooth' });
    }
    setTimeout(function () { hit.forEach(function (n) { n.classList.remove('ak-fresh'); }); }, 2200);
  }

  function applied(j, before, closed, wait) {
    var CZ = window.CZ, v = CZ && CZ.view ? CZ.view() : null;
    var shown = v && v.dataset.level === 'day' ? v.dataset.day : null;
    var other = j.day !== null && j.day !== undefined && shown !== null && String(j.day) !== shown;      // another day was chosen: show that one
    function refresh() {
      if (!v) return Promise.resolve();
      if (other && CZ.forget) { CZ.forget(true); return CZ.goto('/trip/canvas?day=' + j.day, { dir: 'side', mode: 'replace', key: null }); }
      if (CZ.forget) CZ.forget();      // (F-170: the other days fetched ahead are checked when next shown)
      return CZ.quiet();
    }
    var done = wait ? Promise.resolve(closed).then(refresh) : Promise.all([closed, refresh()]);      // the panel must be gone first (the day leaves it alone while it is open); the sheet closes as the day updates
    return done.then(function () {
      glow(j.ids || [], before || {});
      var href = !v && j.day !== null && j.day !== undefined ? '/trip/canvas?day=' + j.day : '';      // on a screen with no day grid the toast has a "See the day" link
      if (window.GA && GA.toast) GA.toast(j.toast || 'Done', href ? { href: href, label: 'See the day', ms: 7000 } : null);
    });
  }

  window.AskFlow = { fragments: fragments, submit: submit, applied: applied };
})();
