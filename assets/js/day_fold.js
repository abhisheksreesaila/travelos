// The top of the day folds away (F-103). Needs trip_canvas.js, which loads first (window.CZ).
//
// The captain, on the trip: the heading, the filters and the dates "occupy a lot of real estate... it's almost like it should fade away, and the only thing I should see is a compact
// version". The day's heading, kinds row, date strip and filters scroll away as they always did; once the last of them has left the top of the screen, a compact bar (the day's name,
// the small Day | Week switch, map, SOS: `.cz-fold`, drawn by the server) slides in at the top. Scrolling back up brings the top back and the bar goes; a tap on the bar (its name, or
// any bare part of it) scrolls back up at once. The switch, map and SOS in the bar work as they do in the heading.
//
// Nothing here changes the layout: the bar sits in a zero-height sticky box and only its transform and opacity move, so the grid's coordinates under a finger never shift. The state is
// still left alone while a block is held, dragged or resized, a hold menu or a title field is open, or a zoom is running, and brought up to date when that is over.
// Reduced motion: the bar appears and goes with no movement, and the tap scrolls at once. Without script the bar stays hidden and inert.
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var stage = CZ.stage;
  var TOP = '.cz-head, .cz-bar, .cz-dpills, .cz-strip, .cz-filters';      // what the bar replaces
  var queued = false;

  function calm() { return !(CZ.held || CZ.menuOpen || (CZ.editing && CZ.editing())); }

  // How far down the screen the lowest of the top parts reaches (a hidden part has no box and counts for nothing).
  function reach(v) {
    var lowest = -1e6;
    v.querySelectorAll(TOP).forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (r.width && r.height && r.bottom > lowest) lowest = r.bottom;
    });
    return lowest;
  }

  function show(f, on) {
    if (f.classList.contains('is-on') === on) return;
    f.classList.toggle('is-on', on);
    f.inert = !on;
    if (on) f.removeAttribute('aria-hidden'); else f.setAttribute('aria-hidden', 'true');
    document.dispatchEvent(new CustomEvent('cz:fold'));      // F-121: a notice on the screen moves once, to stay clear of the bar
  }

  function update(force) {
    queued = false;
    var v = CZ.view && CZ.view(), f = v && v.querySelector('.cz-fold');
    if (!f || (force !== true && !calm())) return;
    var bar = f.firstElementChild, edge = bar.offsetHeight + bar.offsetTop;      // the bar's lower edge, in the layout it has once shown
    var on = f.classList.contains('is-on');
    show(f, reach(v) < edge + (on ? 8 : 0));      // a little slack on the way back, so the edge does not flicker
  }

  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(update);
  }

  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  stage.addEventListener('cz:swap', function () { update(true); setTimeout(schedule, 450); });      // a new level (or a quiet refresh of this one) has its own bar: bring it up to date before anything is painted
  ['pointerup', 'pointercancel', 'keyup'].forEach(function (t) { document.addEventListener(t, function () { setTimeout(schedule, 450); }, true); });      // the gesture that held it still is over

  stage.addEventListener('click', function (e) {
    var bar = e.target.closest && e.target.closest('.cz-fold-bar');
    if (!bar || e.target.closest('a')) return;
    window.scrollTo({ top: 0, behavior: CZ.reduced && CZ.reduced.matches ? 'auto' : 'smooth' });
    var title = stage.querySelector('#cz-title');
    if (title) { try { title.focus({ preventScroll: true }); } catch (err) { /* no focus */ } }
  });

  update();
})();
