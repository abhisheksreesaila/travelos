// The opened square's view (F-242, D-570 to D-579): switch the hotel or the flight in place. Each tile (.mx-tile) holds the options the source gave (.mx-opt, one visible);
// the two arrows step through them, and what depends on the choice follows at once: the total (data-slot="total" and the sticky bar's data-mirror="total"), the cost rows
// (data-cost), the timeline's blocks (data-mirror), and the forms' `fl` and `st` fields (the chosen indexes, which the server reads again and prices itself: a price is never
// sent). Without this script the first option of each tile is shown and Book and Save use it. The new option settles in from the side it came from (a short fade under reduced
// motion). Plain DOM, no state outside the page: the server draws the options, this only shows one.
(function () {
  function money(c) { var d = Math.floor(c / 100), r = c % 100; return '$' + (r === 0 ? d.toLocaleString('en-US') : (c / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })); }
  function dollars(c) { return '$' + Math.floor((c + 50) / 100).toLocaleString('en-US'); }
  function tiles(view) { return Array.prototype.slice.call(view.querySelectorAll('.mx-tile')); }
  function current(tile) { return tile.querySelectorAll('.mx-opt')[parseInt(tile.dataset.i, 10) || 0]; }

  function sync(view) {
    var total = 0, flight = 0, stays = [], at = [];
    tiles(view).forEach(function (t) {
      var opt = current(t), c = parseInt(opt.dataset.c, 10) || 0, i = parseInt(t.dataset.i, 10) || 0;
      total += c;
      if (t.dataset.slotKind === 'flight') {
        flight = i;
        view.querySelectorAll('[data-mirror="flight"]').forEach(function (el) { el.textContent = opt.dataset.short; });
        view.querySelectorAll('[data-cost="flight"]').forEach(function (el) { el.textContent = money(c); });
      } else {
        var n = stays.length;
        stays.push(i);
        view.querySelectorAll('[data-mirror="stay' + n + '"]').forEach(function (el) { el.textContent = opt.dataset.short; });
        view.querySelectorAll('[data-cost="stay' + n + '"]').forEach(function (el) { el.textContent = money(c); });
      }
    });
    view.querySelectorAll('[data-slot="total"]').forEach(function (el) { el.textContent = dollars(total); });
    view.querySelectorAll('[data-mirror="total"]').forEach(function (el) { el.textContent = dollars(total); });
    view.querySelectorAll('[data-pick="fl"]').forEach(function (el) { el.value = String(flight); });
    view.querySelectorAll('[data-pick="st"]').forEach(function (el) { el.value = stays.join(','); });
    view.dataset.changed = (flight || stays.some(Boolean)) ? '1' : '';
    var vs = view.querySelector('[data-vs]');      // the "vs San Diego" chip was for the shown trip
    if (vs && view.dataset.changed) vs.classList.add('is-empty');
  }

  function flip(button) {
    var tile = button.closest('.mx-tile'), view = button.closest('.mx-tv');
    if (!tile || !view) return;
    var opts = tile.querySelectorAll('.mx-opt'), dir = parseInt(button.dataset.flip, 10), i = ((parseInt(tile.dataset.i, 10) || 0) + dir + opts.length) % opts.length;
    opts[parseInt(tile.dataset.i, 10) || 0].hidden = true;
    tile.dataset.i = String(i);
    opts[i].hidden = false;
    var count = tile.querySelector('[data-count]');
    if (count) count.textContent = (i + 1) + ' of ' + opts.length;
    var calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!calm) {
      var wide = window.matchMedia('(min-width: 1020px)').matches;      // the laptop is calm: a fade, no travel
      opts[i].style.setProperty('--mx-from', wide ? '0px' : (dir > 0 ? '1rem' : '-1rem'));
      opts[i].classList.remove('is-in');
      void opts[i].offsetWidth;
      opts[i].classList.add('is-in');
    }
    sync(view);
  }

  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('.mx-flip');
    if (b) { e.preventDefault(); flip(b); }
  });
})();
