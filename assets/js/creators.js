/* Creator link import (F-023). Plain JS, progressive: every control is a real form field and the page works without this file.
   1. After a new link, the draft waits behind its skeleton, then fades in (the inline script in the page sets data-wait first).
   2. Tapping an answer chip saves the form and swaps in the redrawn scrapbook, so the draft updates live.
   3. Editing a spot or ticking a box saves quietly and refreshes the time-left line only.
   4. Submit without both boxes ticked is stopped here with the same message the server gives. */
(function () {
  var NEED = 'Tick both boxes first: that it is accurate, and that you give GitAway permission to publish it.';
  var stage = document.getElementById('cr-stage');
  var form = document.getElementById('cr-form');

  if (stage) {
    var wait = stage.hasAttribute('data-wait');
    setTimeout(function () {
      stage.removeAttribute('data-wait');
      try { history.replaceState(null, '', location.pathname); } catch (e) { /* the address stays; harmless */ }
    }, wait ? 1600 : 0);
    // the fade-in is for the first view only; later swaps must not replay it
    setTimeout(function () { stage.removeAttribute('data-new'); }, wait ? 2800 : 1200);
  }
  if (!form || !window.fetch || !window.DOMParser) return;

  var queue = Promise.resolve();

  function redraw(html, ids) {
    var doc = new DOMParser().parseFromString(html, 'text/html');
    ids.forEach(function (id) {
      var fresh = doc.getElementById(id), old = document.getElementById(id);
      if (fresh && old) old.replaceWith(fresh);
    });
  }

  function save(ids) {
    queue = queue.then(function () {
      var data = new URLSearchParams(new FormData(form));
      data.set('do', 'save');
      return fetch(form.action, { method: 'POST', body: data, credentials: 'same-origin' })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          var book = document.getElementById('cr-book');
          var typing = book && book.contains(document.activeElement) && /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
          redraw(html, typing ? ids.filter(function (id) { return id !== 'cr-book'; }) : ids);
        })
        .catch(function () { form.submit(); });
    });
  }

  form.addEventListener('change', function (e) {
    var t = e.target;
    if (!t || !t.name) return;
    if (t.closest('.cr-questions')) save(['cr-book', 'cr-progress']);    // an answer: redraw the scrapbook
    else if (t.name === 'ok1' || t.name === 'ok2') save(['cr-progress']);
    else save(['cr-progress']);                                          // an edit: keep what they typed, refresh the time line
  });

  form.addEventListener('submit', function (e) {
    var by = e.submitter;
    if (!by || by.value !== 'submit') return;
    var ok1 = form.elements.ok1, ok2 = form.elements.ok2;
    if (ok1.checked && ok2.checked) return;
    e.preventDefault();
    var note = document.getElementById('cr-alert');
    if (!note) {
      note = document.createElement('p');
      note.id = 'cr-alert';
      note.className = 'cr-alert';
      note.setAttribute('role', 'alert');
      form.querySelector('.cr-confirm').before(note);
    }
    note.textContent = NEED;
    (ok1.checked ? ok2 : ok1).focus();
  });
})();
