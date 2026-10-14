// The desktop day (F-140): the grid is the one thing on the left that scrolls, so this puts it where the day starts (7 AM, or now with its coral line during the trip),
// every time a day is shown, and makes "Open the plan" in the panel's Up next open the plan's card on the grid. A phone and the tablet layout scroll the page as before and
// are left alone (the same media query as day_dock.css). Hooks into canvas_core.js through the `cz:swap` event.
(function () {
  var stage = document.getElementById('cz');
  if (!stage) return;
  var desk = window.matchMedia('(min-width: 1020px) and (not (display-mode: standalone))');
  var START = 7 * 60;       // the grid opens at 7 AM
  var NOW_AT = 0.3;         // and with a now line, that line sits this far down the grid

  function rem() { return parseFloat(getComputedStyle(document.documentElement).fontSize) || 12; }

  function showChip() {          // a trip of many days: the chips scroll inside the header, and the open day is kept in view
    var n = stage.querySelector('.cz-hchips'), c = n && n.querySelector('.is-open');
    if (c && n.scrollWidth > n.clientWidth) n.scrollLeft = c.offsetLeft - (n.clientWidth - c.offsetWidth) / 2 - n.offsetLeft;
  }

  function place() {
    if (!desk.matches) return;
    showChip();
    var scroller = stage.querySelector('.cz-view[data-day] .cz-day-body'), grid = stage.querySelector('#cz-grid');
    var zoom = grid && grid.querySelector('.cz-g-zoom');
    if (!scroller || !zoom) return;
    var lo = +grid.dataset.lo, hi = +grid.dataset.hi, mm = zoom.offsetHeight / (hi - lo);
    var line = grid.querySelector('#cz-nowline');
    var m = line ? +line.dataset.m : Math.max(lo, START);
    var top = zoom.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop + (m - lo) * mm;
    scroller.scrollTop = Math.max(0, top - (line ? scroller.clientHeight * NOW_AT : 0) - 1.25 * rem());      // a little air above the first hour
  }

  stage.addEventListener('cz:swap', function (e) { if (!(e.detail && e.detail.quiet)) place(); });
  place();

  stage.addEventListener('click', function (e) {          // "Open the plan" on a plan with no steps: the same card a tap on its block opens
    var a = e.target.closest ? e.target.closest('[data-dock-open]') : null;
    if (!a || !desk.matches) return;
    var block = stage.querySelector('.cz-gb[data-act="' + a.dataset.dockOpen + '"]'), open = block && block.querySelector('.cz-gb-open');
    if (!open) return;
    e.preventDefault();
    block.scrollIntoView({ block: 'center' });
    open.click();
  });
})();
