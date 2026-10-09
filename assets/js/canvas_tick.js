// F-125: tap a step's circle to tick it, as in Reminders. The circle fills and the title strikes at once; the save runs behind, and its reply brings the
// counts up to date in place (F-124). A refused or lost save puts the step back and says so. The rest of the row still opens the step's sheet.
// Editors only (the stage's data-edit). Loaded after trip_canvas.js (CZ.post, CZ.quiet).
(function () {
  'use strict';
  var stage = document.getElementById('cz');
  if (!stage || !window.CZ) return;
  var CZ = window.CZ;

  function ring(e) {
    if (stage.dataset.edit !== '1' || e.button) return null;
    var r = e.target.closest ? e.target.closest('.cz-ring') : null;
    return r && stage.contains(r) ? r.closest('.cz-step[data-step]') : null;
  }

  function set(step, done) {
    step.classList.toggle('is-done', done);
  }

  function tick(step) {
    if (step.dataset.ticking) return;
    var done = !step.classList.contains('is-done');
    step.dataset.ticking = '1';
    set(step, done);
    if (navigator.vibrate) { try { navigator.vibrate(8); } catch (e) { /* no buzz */ } }
    CZ.post('/trip/canvas/step', CZ.tripBody({ step: step.dataset.step, do: done ? 'done' : 'undone', next: CZ.here() })).then(function () {
      delete step.dataset.ticking;
      return CZ.quiet();
    }, function (err) {
      delete step.dataset.ticking;
      set(step, !done);
      CZ.showToast(err && err.soft ? err.soft : 'Could not save that. Check your connection.');
    });
  }

  stage.addEventListener('click', function (e) {
    var step = ring(e);
    if (!step) return;
    e.preventDefault();
    e.stopPropagation();
    tick(step);
  });
})();
