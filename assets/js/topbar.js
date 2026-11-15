// The top bar's avatar menu (F-139; F-254 took out the trip picker and the "/" key with the Ask page). The menu is a <details>: it grows out of its button and folds back into it
// with the one liquid motion (GA.motion, motion.js); it closes on Esc, on a press outside it, and when another opens.
(function () {
  var MO = window.GA && window.GA.motion;
  var bar = document.querySelector('.ga-topbar');
  if (!bar) return;

  function menus() { return Array.prototype.slice.call(document.querySelectorAll('.ga-tb-menu')); }
  function popOf(d) { return d.querySelector('.ga-tb-pop'); }
  function sumOf(d) { return d.querySelector('summary'); }

  function fold(d, focusBack) {
    if (!d.open) return;
    var pop = popOf(d), done = function () { d.open = false; d.removeAttribute('data-closing'); };
    if (focusBack) sumOf(d).focus();
    if (MO && pop && !MO.reduced()) {
      d.setAttribute('data-closing', '1');
      MO.close(pop, sumOf(d)).then(done);
    } else done();
  }

  document.addEventListener('toggle', function (e) {
    var d = e.target;
    if (!d.classList || !d.classList.contains('ga-tb-menu') || !d.open) return;
    menus().forEach(function (o) { if (o !== d) fold(o, false); });         // one menu open at a time
    var pop = popOf(d);
    // F-154: the bar's menu is opened all the time, so it grows with the calm --motion-dur (240ms, no overshoot) and is still within a quarter second
    if (MO && pop) MO.open(pop, sumOf(d), { t: 'dur', ease: 'calm' });
  }, true);

  document.addEventListener('pointerdown', function (e) {
    menus().forEach(function (d) { if (d.open && (!d.contains(e.target) || e.target === d)) fold(d, false); });
  }, true);

  document.addEventListener('keydown', function (e) {      // (capture: before a page's own Esc)
    if (e.key !== 'Escape') return;
    var shut = false;
    menus().forEach(function (d) { if (d.open && !d.hasAttribute('data-closing')) { fold(d, true); shut = true; } });      // (a menu already folding is not closed again: a second Esc reaches the page)
    if (shut) { e.preventDefault(); e.stopImmediatePropagation(); }      // F-156: Esc closed the menu and nothing else
  }, true);
})();
