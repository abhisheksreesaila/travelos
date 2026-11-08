// /plan on a phone (autopilot M5): the lanes (flights, stays, cars, around) are one sideways swipe with scroll-snap, and a segmented switcher above them follows the finger.
// The CSS (plan_coast.css) makes .ws-grid the scroller below 721px; this file only (1) moves the switcher's thumb with the scroll position (--p, 0 to 3), (2) lights the segment of the
// lane in view, (3) scrolls to a lane when its segment is tapped, (4) keeps the scroller as tall as the lane in view, so a short lane has no empty page under it.
// No durations here: the swipe is the browser's, a tap uses the browser's smooth scroll (instant under reduced motion), the thumb is positioned by the scroll itself.
(function () {
  var grid = document.getElementById('ws-grid');
  var seg = document.querySelector('.ws-seg');
  if (!grid || !seg) return;
  var thumb = seg.querySelector('.ws-seg-thumb');
  var buttons = [].slice.call(seg.querySelectorAll('.ws-seg-b'));
  var phone = window.matchMedia('(max-width: 720px)');
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var slides = [].slice.call(grid.children);
  var current = -1, ticking = false;

  function carousel() { return phone.matches && !grid.hasAttribute('data-expanded'); }
  function step() { return slides.length > 1 ? slides[1].offsetLeft - slides[0].offsetLeft : grid.clientWidth; }

  function size() {                               // the scroller is as tall as the lane in view (its own padding included)
    if (!carousel()) { grid.style.height = ''; return; }
    var s = slides[Math.max(current, 0)];
    var cs = getComputedStyle(grid);
    grid.style.height = (s.offsetHeight + parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom)) + 'px';
  }

  function sync() {
    ticking = false;
    if (!carousel()) { seg.style.removeProperty('--p'); return; }
    var p = step() ? grid.scrollLeft / step() : 0;
    p = Math.min(Math.max(p, 0), slides.length - 1);
    seg.style.setProperty('--p', p.toFixed(3));
    var i = Math.round(p);
    if (i !== current) {
      current = i;
      buttons.forEach(function (b, n) { b.setAttribute('aria-pressed', n === i ? 'true' : 'false'); });
      size();
    }
  }

  grid.addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(sync); } }, { passive: true });
  buttons.forEach(function (b, n) {
    b.addEventListener('click', function () {
      if (!carousel()) return;
      grid.scrollTo({ left: slides[n].offsetLeft - slides[0].offsetLeft, behavior: reduced.matches ? 'auto' : 'smooth' });
    });
  });
  if (window.ResizeObserver) {                    // cards change height (a skipped lane, a price loading): follow it
    var ro = new ResizeObserver(function () { if (carousel()) size(); });
    slides.forEach(function (s) { ro.observe(s); });
  }
  [phone, reduced].forEach(function (q) { if (q.addEventListener) q.addEventListener('change', function () { current = -1; sync(); }); });
  new MutationObserver(function () { current = -1; sync(); }).observe(grid, { attributes: true, attributeFilter: ['data-expanded'] });
  sync();
})();
