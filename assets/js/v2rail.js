// The widget rail beside the matrix (F-251, D-620). It follows the place you look at: assets/js/tripmatrix.js says so with the event `mx:follow` ({lane, w, n, fresh}) when the page loads,
// a square is opened or a place's name is tapped, and with `mx:settled` once every square in view has its answer (a cheaper airport needs two answers, so the rail asks again).
// The widgets themselves are the server's (GET /plan/matrix/rail, gitaway/pages/v2rail.py): each has a real source or is not drawn. This script only asks, keeps what it was told for
// the place (so going back is instant), and swaps it in on the page's springs (the widgets arrive one after another; reduced motion: no movement). The latest ask wins: an answer for a place
// you have already left is kept but not shown. "Show all" opens the rest of a list; "Look at <place>" (the cheaper airport) tells the matrix to follow that place (`mx:look`).
(function () {
  var rail = document.getElementById('mx-rail'), raw = document.getElementById('mx-data');
  if (!rail || !raw) return;
  var data = JSON.parse(raw.textContent), kept = {}, want = '', last = null, shown = '';      // shown: the server's own words for what is on the rail now

  function address(d) {
    var u = new URL(data.rail, location.href);
    u.searchParams.set('lane', d.lane);
    u.searchParams.set('w', d.w);
    if (data.returns && d.n && data.returns[d.n]) u.searchParams.set('r', data.returns[d.n]);      // the nights on the slider
    return u.pathname + u.search;
  }

  function show(html, id) {
    shown = html;
    rail.innerHTML = html;
    rail.dataset.id = id;
    rail.classList.remove('is-swap');
    void rail.offsetWidth;      // restart the arrival
    rail.classList.add('is-swap');
  }

  function ask(d) {
    var id = address(d);
    want = id;
    last = d;
    if (kept[id] && !d.fresh) { if (rail.dataset.id !== id) show(kept[id], id); return; }
    fetch(id, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) {
        kept[id] = j.html;
        if (want === id && (rail.dataset.id !== id || d.fresh)) {
          if (rail.dataset.id === id && shown === j.html) return;      // the same widgets again: leave them be (compared with what the server sent last, not the page's rewritten markup, which never matched)
          show(j.html, id);
        }
      })
      .catch(function () { if (!rail.dataset.id) rail.hidden = true; });      // nothing came: no rail at all rather than a skeleton that never fills
  }

  document.addEventListener('mx:follow', function (e) { ask(e.detail); });
  document.addEventListener('mx:settled', function () { if (last) { kept = {}; ask({ lane: last.lane, w: last.w, n: last.n, fresh: true }); } });
  rail.addEventListener('click', function (e) {
    var more = e.target.closest('[data-more]');
    if (more) {
      var list = more.previousElementSibling, open = more.dataset.open !== '1';
      list.querySelectorAll('li').forEach(function (li, i) { if (i > 2) li.hidden = !open; });
      more.dataset.open = open ? '1' : '';
      more.textContent = open ? 'Show fewer' : 'Show all ' + list.querySelectorAll('li').length;
      return;
    }
    var look = e.target.closest('[data-lane]');
    if (look && look.tagName === 'BUTTON') document.dispatchEvent(new CustomEvent('mx:look', { detail: { lane: look.dataset.lane } }));
  });
})();
