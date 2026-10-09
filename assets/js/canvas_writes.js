// The trip canvas, writes (F-081 onwards; a module since F-128). Loaded after canvas_core.js.
//   Forms marked data-cz-form (Mark done, Put back, a note, the swipe's Done and Set aside, Add a step) post through CZ.post instead of leaving the page.
//   Done and Not done never wait for the server (F-126); every write that stays on its level is brought up to date in place (F-122, F-124).
//   The toast (GA.toast, toast.js) with Undo.
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var stage = CZ.stage, path = CZ.path, here = CZ.here;

  // ---- the toast, and Undo ------------------------------------------------------------------------------------------------------
  // F-108: a function is the day grid's own Undo, anything else the snapshot the server's undo route takes.
  function hideToast(instant) { if (window.GA && GA.hideToast) GA.hideToast(instant); }
  function showToast(text, undo) {
    if (!window.GA || !GA.toast) return;
    GA.toast(text, undo ? { undo: function () { if (typeof undo === 'function') undo(); else doUndo(undo); } } : null);
  }
  function doUndo(undo) {
    hideToast();
    CZ.post('/trip/canvas/undo', CZ.tripBody({ undo: JSON.stringify(undo), next: here() })).then(function (res) {
      return CZ.refresh().then(function () { showToast(res.toast || 'Moved back'); });
    }).catch(function (err) { showToast(err && err.soft ? err.soft : 'Could not undo that.'); });
  }

  // ---- F-126: Done and Not done never wait --------------------------------------------------------------------------------------
  // The swipe's Done ticks the row where it is (and the row slides shut); the sheet's Mark done goes back to the plan at once with the row already ticked. The save runs
  // behind, and its reply brings the counts up to date. True when it was shown early.
  function tickNow(f, body) {
    var d = body.get('do'), sid = body.get('step'), next = body.get('next');
    if (f.getAttribute('action') !== '/trip/canvas/step' || (d !== 'done' && d !== 'undone') || !sid || !next) return false;
    var mark = function () {
      var row = stage.querySelector('.cz-step[data-step="' + sid + '"]');
      if (row) row.classList.toggle('is-done', d === 'done');
    };
    if (path(next) === here()) { mark(); if (CZ.closeSwipes) CZ.closeSwipes(); return true; }
    if (CZ.busy()) return false;
    stage.addEventListener('cz:swap', mark, { once: true });
    CZ.zoomOutTo(next);
    return true;
  }

  // ---- forms ----------------------------------------------------------------------------------------------------------------------
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f.matches || !f.matches('form[data-cz-form]') || e.defaultPrevented) return;
    e.preventDefault();
    if (f.dataset.sent) return;
    f.dataset.sent = '1';
    var body = new URLSearchParams(new FormData(f));
    var buttons = f.querySelectorAll('button');
    buttons.forEach(function (b) { b.disabled = true; });
    var early = tickNow(f, body);
    CZ.post(f.action, body).then(function (res) {
      CZ.forget();
      if (res.toast) showToast(res.toast, res.undo);
      if (early || path(res.url) === here()) CZ.quiet();      // on this level (a tick, a note): brought up to date where it is, no fade
      else if (f.hasAttribute('data-cz-stay')) CZ.goto(res.url, { dir: 'side', mode: 'stay', key: null });
      else CZ.zoomOutTo(res.url);
    }).catch(function (err) {
      if (err && err.soft) {            // refused with a reason: say it where the person is looking, and let them try again
        var box = f.querySelector('.cz-error');
        if (box) box.textContent = err.soft; else showToast(err.soft);
        buttons.forEach(function (b) { b.disabled = false; });
        delete f.dataset.sent;
        if (early) CZ.quiet();
        return;
      }
      if (early) { showToast('Could not save that. Check your connection.'); CZ.quiet(); return; }      // the screen goes back to what is saved
      f.submit();     // the plain form post does the same write and redirects to the level
    });
  });

  // F-121: the step sheet's note is written on the sticky itself and saved when the keyboard goes (no Save button to find).
  document.addEventListener('change', function (e) {
    var i = e.target;
    if (!i.matches || !i.matches('.cz-note-sticky') || i.value === i.defaultValue || !i.form) return;
    if (i.form.requestSubmit) i.form.requestSubmit(); else i.form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
  });

  // The add-a-step sheet: Everyone and the people are one choice.
  document.addEventListener('change', function (e) {
    var input = e.target;
    if (!input.matches || !input.matches('input[name="who"]') || !input.form) return;
    var all = input.form.querySelector('input[name="who"][value="all"]');
    if (!all) return;
    var others = Array.prototype.filter.call(input.form.querySelectorAll('input[name="who"]'), function (x) { return x !== all; });
    if (input === all) { if (all.checked) others.forEach(function (x) { x.checked = false; }); else all.checked = true; }
    else if (input.checked) all.checked = false;
    else if (!others.some(function (x) { return x.checked; })) all.checked = true;
  });

  CZ.showToast = showToast;
  CZ.hideToast = hideToast;
})();
