// What are you after? (F-241): the page is a plain form that works without this script. The script adds three small things: a chip pops when tapped (the CSS animation, replayed),
// an idea fills the box (and focuses it), and Search shows the matrix's skeleton at once while the browser opens the matrix (the form then posts as it always does).
(function () {
  var form = document.getElementById('ak');
  if (!form) return;
  var wrap = form.closest('.ak-wrap'), q = document.getElementById('ak-q'), go = document.getElementById('ak-go');
  form.addEventListener('change', function (e) {
    var chip = e.target.closest && e.target.closest('.ak-chip');
    if (!chip) return;
    chip.classList.remove('is-pop'); void chip.offsetWidth; chip.classList.add('is-pop');
  });
  form.addEventListener('click', function (e) {
    var ex = e.target.closest && e.target.closest('.ak-ex');
    if (!ex) return;
    q.value = ex.dataset.say; q.removeAttribute('aria-invalid');
    var err = document.getElementById('ak-error'); if (err) err.remove();
    q.focus();
  });
  form.addEventListener('submit', function () {
    wrap.classList.add('is-going');
    go.setAttribute('aria-busy', 'true');
  });
  window.addEventListener('pageshow', function (e) { if (e.persisted) wrap.classList.remove('is-going'); });      // back from the matrix: the ask, not a skeleton
})();
