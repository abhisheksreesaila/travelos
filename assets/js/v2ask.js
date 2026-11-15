// The landing's search box (F-257, D-660..): one soft box, an autocomplete under it, Search. The page works without this script as a plain form (the box posts `q`, the server reads it with
// gitaway/asksuggest.py); the script adds the suggestions (GET /plan/ask/suggest: only places we know, and the who and when that complete the sentence), the combobox keys, and the glide
// of the box up into the results' skeleton before the matrix opens. Choosing a suggestion only sets the box (and asks again for what comes next); Search is always the button or Enter.
// Motion: only the --v2-* tokens in v2-tokens.css, read here with getComputedStyle; nothing in this file is a time.
(function () {
  var form = document.getElementById('v2-form'), q = document.getElementById('v2-q'), list = document.getElementById('v2-list'), say = document.getElementById('v2-say');
  var root = document.querySelector('.v2'), stage = document.querySelector('[data-v2="landing"]');
  if (!form || !q || !list || !stage) return;
  var cs = getComputedStyle(document.documentElement);
  var RM = window.matchMedia('(prefers-reduced-motion: reduce)');
  var items = [], active = -1, seq = 0, shown = false;

  function tok(n) { var v = cs.getPropertyValue(n).trim(); return v.slice(-2) === 'ms' ? parseFloat(v) : (v.slice(-1) === 's' ? parseFloat(v) * 1000 : parseFloat(v)); }
  function ease(n) { return cs.getPropertyValue(n).trim(); }
  function esc(t) { return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function home() { return form.elements.home ? form.elements.home.value : ''; }

  function setActive(n) {
    active = n;
    list.querySelectorAll('[role=option]').forEach(function (o, i) { o.setAttribute('aria-selected', String(i === n)); });
    if (n >= 0) { q.setAttribute('aria-activedescendant', 'ak-o' + n); var o = document.getElementById('ak-o' + n); if (o && o.scrollIntoView) o.scrollIntoView({ block: 'nearest' }); }
    else q.removeAttribute('aria-activedescendant');
  }
  function hide() {
    if (!shown) return;
    shown = false; list.hidden = true; q.setAttribute('aria-expanded', 'false'); setActive(-1);
  }
  function draw(r) {
    items = r.items || [];
    say.hidden = !r.say; say.textContent = r.say || '';
    if (r.say) q.setAttribute('aria-describedby', 'v2-say'); else q.removeAttribute('aria-describedby');
    if (!items.length) { hide(); return; }
    list.innerHTML = items.map(function (it, i) {
      return '<li role="option" id="ak-o' + i + '" class="ak-o ak-' + esc(it.kind) + '" aria-selected="false" data-i="' + i + '"><span class="ak-l">' + esc(it.label) + '</span>' + (it.hint ? '<span class="ak-hint">' + esc(it.hint) + '</span>' : '') + '</li>';
    }).join('');
    var was = shown;
    shown = true; list.hidden = false; q.setAttribute('aria-expanded', 'true'); setActive(-1);
    if (!was && !RM.matches) list.animate([{ opacity: 0, transform: 'translateY(-0.375rem) scale(.98)' }, { opacity: 1, transform: 'none' }], { duration: tok('--v2-pop'), easing: ease('--v2-ease') });
  }
  function ask() {
    var n = ++seq;      // a late answer to an older word is dropped
    fetch(form.dataset.suggest + '?' + new URLSearchParams({ q: q.value, home: home() }), { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { return r.json(); }).then(function (r) { if (n === seq) draw(r); }).catch(function () { if (n === seq) hide(); });
  }
  function take(i) {
    var it = items[i]; if (!it) return;
    q.value = it.text; q.focus({ preventScroll: true }); ask();
  }

  q.addEventListener('input', function () { var e = document.getElementById('v2-error'); if (e) e.hidden = true; ask(); });
  q.addEventListener('focus', ask);
  q.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!shown) { ask(); return; }
      e.preventDefault();
      var d = e.key === 'ArrowDown' ? 1 : -1, n = active + d;
      setActive(n >= items.length ? 0 : (n < -1 ? items.length - 1 : n));
    } else if (e.key === 'Enter' && shown && active >= 0) { e.preventDefault(); take(active); }
    else if (e.key === 'Escape' && shown) { e.preventDefault(); hide(); }
    else if (e.key === 'Tab') hide();
  });
  list.addEventListener('mousedown', function (e) { e.preventDefault(); });      // a tap on a suggestion must not take the focus from the box
  list.addEventListener('click', function (e) { var o = e.target.closest('[role=option]'); if (o) take(+o.dataset.i); });
  list.addEventListener('mousemove', function (e) { var o = e.target.closest('[role=option]'); if (o && +o.dataset.i !== active) setActive(+o.dataset.i); });
  document.addEventListener('pointerdown', function (e) { if (shown && !e.target.closest('.ak-box')) hide(); });
  form.querySelectorAll('.ak-ex').forEach(function (a) {
    a.addEventListener('click', function (e) { e.preventDefault(); q.value = a.textContent; q.focus({ preventScroll: true }); ask(); });
  });

  // ---- Search: the box glides up, the results' skeleton plays, then the matrix opens ----
  function glide() {
    var f = form.querySelector('.ak-field'), a = f.getBoundingClientRect();
    root.classList.add('is-results');
    var b = f.getBoundingClientRect();
    if (RM.matches) return Promise.resolve();
    return f.animate([{ transform: 'translate(' + (a.left - b.left) + 'px, ' + (a.top - b.top) + 'px)' }, { transform: 'none' }], { duration: tok('--v2-glide'), easing: ease('--spring-soft') }).finished.catch(function () {});
  }
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    hide(); seq++;
    var skel = document.getElementById('v2-skel'), err = document.getElementById('v2-error');
    var moved = glide();
    if (skel) { skel.hidden = false; skel.classList.add('is-in'); }
    fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'X-V2': '1', Accept: 'application/json' }, credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (j) {
      if (j.error) { root.classList.remove('is-results'); if (skel) skel.hidden = true; err.textContent = j.error; err.hidden = false; q.focus({ preventScroll: true }); return; }
      err.hidden = true;
      moved.then(function () { document.documentElement.classList.add('v2-leaving'); location.assign(j.to); });
    }).catch(function () { form.submit(); });
  });
  window.addEventListener('pageshow', function (e) { if (e.persisted) { root.classList.remove('is-results'); document.documentElement.classList.remove('v2-leaving'); } });      // back from the matrix: the landing, not a skeleton
})();
