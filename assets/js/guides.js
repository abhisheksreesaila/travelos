// The guide hub's search (F-262): the box asks /plan/ask/suggest (the places GitAway knows, F-257) as you type and lists them; choosing one fills the box and searches the guides for that place.
// Without script the box is a plain GET form that matches a place or a word of a title.
(function () {
  'use strict';
  var form = document.getElementById('gh-form'), q = document.getElementById('gh-q'), list = document.getElementById('gh-list');
  if (!form || !q || !list) return;
  var RM = matchMedia('(prefers-reduced-motion: reduce)');
  var cs = getComputedStyle(document.documentElement);
  function tok(n) { var v = cs.getPropertyValue(n).trim(); return v.slice(-2) === 'ms' ? parseFloat(v) : parseFloat(v) * 1000; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  var items = [], active = -1, shown = false, seq = 0;
  function setActive(i) {
    active = i;
    Array.prototype.forEach.call(list.children, function (li, j) { li.setAttribute('aria-selected', j === i ? 'true' : 'false'); });
    if (i >= 0) q.setAttribute('aria-activedescendant', 'gh-o' + i); else q.removeAttribute('aria-activedescendant');
  }
  function hide() { if (!shown) return; shown = false; list.hidden = true; q.setAttribute('aria-expanded', 'false'); setActive(-1); }
  function draw(r) {
    items = (r.items || []).filter(function (it) { return it.kind === 'place'; });
    if (!items.length) { hide(); return; }
    list.innerHTML = items.map(function (it, i) { return '<li role="option" id="gh-o' + i + '" aria-selected="false" data-i="' + i + '"><span>' + esc(it.label) + '</span>' + (it.hint ? '<span class="ak-hint">' + esc(it.hint) + '</span>' : '') + '</li>'; }).join('');
    var was = shown; shown = true; list.hidden = false; q.setAttribute('aria-expanded', 'true'); setActive(-1);
    if (!was && !RM.matches) list.animate([{ opacity: 0, transform: 'translateY(-0.375rem) scale(.98)' }, { opacity: 1, transform: 'none' }], { duration: tok('--v2-pop'), easing: cs.getPropertyValue('--v2-ease').trim() });
  }
  function ask() {
    var n = ++seq;      // a late answer to an older word is dropped
    fetch(form.dataset.suggest + '?' + new URLSearchParams({ q: q.value }), { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { return r.json(); }).then(function (r) { if (n === seq) draw(r); }).catch(function () { if (n === seq) hide(); });
  }
  function take(i) { var it = items[i]; if (!it) return; q.value = it.label; hide(); form.requestSubmit ? form.requestSubmit() : form.submit(); }
  q.addEventListener('input', ask);
  q.addEventListener('focus', function () { if (q.value) ask(); });
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
  list.addEventListener('mousedown', function (e) { e.preventDefault(); });      // a tap on a place must not take the focus from the box
  list.addEventListener('click', function (e) { var o = e.target.closest('[role=option]'); if (o) take(+o.dataset.i); });
  document.addEventListener('pointerdown', function (e) { if (shown && !e.target.closest('#gh-form')) hide(); });
})();
