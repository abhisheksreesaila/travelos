// The widget rail beside the matrix (F-251, D-620). It follows the place you look at: assets/js/tripmatrix.js says so with the event `mx:follow` ({lane, w, n, fresh}) when the page loads,
// a square is opened or a place's name is tapped, and with `mx:settled` once every square in view has its answer (a cheaper airport needs two answers, so the rail asks again).
// The widgets themselves are the server's (GET /plan/matrix/rail, gitaway/pages/v2rail.py): each has a real source or is not drawn. This script only asks, keeps what it was told for
// the place (so going back is instant), and swaps it in on the page's springs (the widgets arrive one after another; reduced motion: no movement). The latest ask wins: an answer for a place
// you have already left is kept but not shown. "Show all" opens the rest of a list; "Look at <place>" (the cheaper airport) tells the matrix to follow that place (`mx:look`).
(function () {
  var rail = document.getElementById('mx-rail'), raw = document.getElementById('mx-data');
  if (!rail || !raw) return;
  var data = JSON.parse(raw.textContent), kept = {}, want = '', last = null, shown = '';      // shown: the server's own words for what is on the rail now

  function address(d, wg) {
    var u = new URL(data.rail, location.href);
    u.searchParams.set('lane', d.lane);
    u.searchParams.set('w', d.w);
    if (data.returns && d.n && data.returns[d.n]) u.searchParams.set('r', data.returns[d.n]);      // the nights on the slider
    if (wg) u.searchParams.set('wg', wg);
    return u.pathname + u.search;
  }

  // The extra-info row (F-277, D-870): the server sends chips only. A chip fetches its card when it is tapped, never before, so an untapped chip costs nothing; what was fetched is kept for the
  // place (tapping again is instant) and what you opened follows the rail to another place of the same kind. The first tap ends the nudge for good (localStorage, if the browser lets us).
  var USED = 'ga-rail-used', cards = {}, asking = {};
  function used() { try { return !!localStorage.getItem(USED); } catch (e) { return false; } }
  function nudge() { rail.classList.toggle('is-nudge', !used()); }
  function spent() { try { localStorage.setItem(USED, '1'); } catch (e) { /* private window: the nudge comes back next visit, harmless */ } rail.classList.remove('is-nudge'); }
  function chipOf(name) { return rail.querySelector('.wchip[data-wg="' + name + '"]'); }
  function tray() { return rail.querySelector('.rl-cards'); }
  function openNames() { return Array.prototype.map.call(rail.querySelectorAll('.wchip[aria-expanded="true"]'), function (c) { return c.dataset.wg; }); }

  function put(name, html) {      // the card is in the tray (replacing an older one of the same widget), shown while its chip is open
    var old = document.getElementById('wg-' + name), chip = chipOf(name);
    if (old) old.remove();
    tray().insertAdjacentHTML('beforeend', html);
    var card = document.getElementById('wg-' + name);
    card.hidden = !(chip && chip.getAttribute('aria-expanded') === 'true');
    if (chip) chip.removeAttribute('aria-busy');
  }

  function load(name, d, fresh) {
    var id = address(d, name), chip = chipOf(name);
    if (!chip) return;
    if (cards[id] && !fresh) { put(name, cards[id]); return; }
    if (asking[id] && !fresh) return;      // F-277 review: a second tap while the first answer is on its way asks nothing
    asking[id] = true;
    chip.setAttribute('aria-busy', 'true');
    fetch(id, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) {
        delete asking[id];
        cards[id] = j.card;
        if (last && address(last, name) === id) put(name, j.card);      // an answer for a place you have left is kept, not shown
      })
      .catch(function () { delete asking[id]; chip.removeAttribute('aria-busy'); chip.setAttribute('aria-expanded', 'false'); });
  }

  function toggle(name, on) {
    var chip = chipOf(name), card = document.getElementById('wg-' + name);
    if (!chip) return;
    if (on === undefined) on = chip.getAttribute('aria-expanded') !== 'true';
    chip.setAttribute('aria-expanded', on ? 'true' : 'false');
    if (card) card.hidden = !on;
    else if (on && last) load(name, last);
  }

  function show(html, id) {
    var was = openNames();      // what you opened stays open when the rail follows another place of the same kind
    shown = html;
    rail.innerHTML = html;
    nudge();
    was.forEach(function (n) { var c = chipOf(n); if (c && last) { c.setAttribute('aria-expanded', 'true'); load(n, last); } });
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
          if (rail.dataset.id === id && shown === j.html) {      // the same chips again: leave them be, but what is open may have changed (a cheaper airport needs two answers): ask it again
            openNames().forEach(function (n) { load(n, d, true); });
            return;
          }
          show(j.html, id);
        }
      })
      .catch(function () { if (!rail.dataset.id) rail.hidden = true; });      // nothing came: no rail at all rather than a skeleton that never fills
  }

  document.addEventListener('mx:follow', function (e) { ask(e.detail); });
  document.addEventListener('mx:settled', function () { if (last) { kept = {}; cards = {}; ask({ lane: last.lane, w: last.w, n: last.n, fresh: true }); } });
  rail.addEventListener('click', function (e) {
    var chip = e.target.closest('.wchip[data-wg]'), shut = e.target.closest('[data-wg-close]');
    if (chip) { spent(); toggle(chip.dataset.wg); return; }
    if (shut) { toggle(shut.dataset.wgClose, false); var c = chipOf(shut.dataset.wgClose); if (c) c.focus(); return; }
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
