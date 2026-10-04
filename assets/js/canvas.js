// Add to the trip (F-080). Convert can take up to 45 seconds: show that it is working and stop a second tap; the same for Add to trip.
(function () {
  function busy(form, button, label, progress) {
    form.addEventListener('submit', function (e) {
      if (form.dataset.sent) { e.preventDefault(); return; }
      var submitter = e.submitter;
      if (submitter && submitter !== button) return;        // "Edit text" and "Back" leave the page without waiting
      form.dataset.sent = '1';
      form.setAttribute('aria-busy', 'true');
      // disabling the button inside its own submit event would drop its value on some browsers: do it a tick later
      setTimeout(function () {
        button.disabled = true;
        button.textContent = label;
        if (progress) progress.hidden = false;
      }, 0);
    });
  }
  var paste = document.getElementById('cv-form');
  if (paste) busy(paste, document.getElementById('cv-convert'), 'Reading…', document.getElementById('cv-progress'));
  var ask = document.getElementById('cv-questions-form');
  if (ask) busy(ask, document.getElementById('cv-add'), 'Adding…', null);
  // coming back with the browser's Back button must not leave the page stuck in its waiting state
  window.addEventListener('pageshow', function (e) {
    if (!e.persisted) return;
    [paste, ask].forEach(function (f) {
      if (!f) return;
      delete f.dataset.sent;
      f.removeAttribute('aria-busy');
    });
    var c = document.getElementById('cv-convert'), a = document.getElementById('cv-add'), p = document.getElementById('cv-progress');
    if (c) { c.disabled = false; c.textContent = 'Convert'; }
    if (a) { a.disabled = false; a.textContent = 'Add to trip'; }
    if (p) p.hidden = true;
  });
})();
