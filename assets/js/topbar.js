// The top bar's two menus (the trip picker and the avatar) and the "/" key (F-139, gitaway/topbar.py). The menus are <details>: a menu grows out of its button and folds back into it
// with the one liquid motion (GA.motion, motion.js); it closes on Esc, on a press outside it, and when another opens. "/" goes to Ask (the link beside it), unless a field has focus.
// The key clicks the Ask link beside it. The link is the Ask page; on the trip canvas's day and week (a laptop) day_ask.js (F-142) catches that click and opens Ask in the panel instead.
(function () {
  var MO = window.GA && window.GA.motion;
  var bar = document.querySelector('.ga-topbar');
  if (!bar) return;

  function menus() { return Array.prototype.slice.call(bar.querySelectorAll('.ga-tb-menu')); }
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

  bar.addEventListener('toggle', function (e) {
    var d = e.target;
    if (!d.classList || !d.classList.contains('ga-tb-menu') || !d.open) return;
    menus().forEach(function (o) { if (o !== d) fold(o, false); });         // one menu open at a time
    var pop = popOf(d);
    if (MO && pop) MO.open(pop, sumOf(d));
  }, true);

  document.addEventListener('pointerdown', function (e) {
    menus().forEach(function (d) { if (d.open && !d.contains(e.target)) fold(d, false); });
  }, true);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      menus().forEach(function (d) { if (d.open) fold(d, true); });
      return;
    }
    if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return;
    var t = e.target, tag = t && t.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (t && t.isContentEditable)) return;
    var ask = document.getElementById('ga-tb-ask');
    if (!ask || getComputedStyle(bar).display === 'none') return;           // no bar at this width (the phone and the tablet): "/" does nothing
    e.preventDefault();
    ask.click();
  });
})();
