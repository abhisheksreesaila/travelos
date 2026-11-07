/* F-200: the "Early preview" label (layout.preview()), on every page, signed in or not. It is a <details>: its one line grows out of the pill and folds back into it
   with the one motion (GA.motion, motion.js; a calm fade on a laptop), closes on Esc and on a press outside it, and one is open at a time. The top bar's own menus are topbar.js's. */
(function () {
  var MO = window.GA && window.GA.motion;
  function all() { return Array.prototype.slice.call(document.querySelectorAll('details.ga-preview')); }
  function fold(d, focusBack) {
    if (!d.open) return;
    var pop = d.querySelector('.ga-preview-pop'), sum = d.querySelector('summary'), done = function () { d.open = false; d.removeAttribute('data-closing'); };
    if (focusBack) sum.focus();
    if (MO && pop && !MO.reduced()) { d.setAttribute('data-closing', '1'); MO.close(pop, sum).then(done); } else done();
  }
  document.addEventListener('toggle', function (e) {
    var d = e.target;
    if (!d.classList || !d.classList.contains('ga-preview') || !d.open) return;
    all().forEach(function (o) { if (o !== d) fold(o, false); });
    var pop = d.querySelector('.ga-preview-pop');
    if (MO && pop) MO.open(pop, d.querySelector('summary'), { t: 'dur', ease: 'calm' });
  }, true);
  document.addEventListener('pointerdown', function (e) {
    all().forEach(function (d) { if (d.open && !d.contains(e.target)) fold(d, false); });
  }, true);
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var shut = false;
    all().forEach(function (d) { if (d.open && !d.hasAttribute('data-closing')) { fold(d, true); shut = true; } });
    if (shut) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, true);
})();
