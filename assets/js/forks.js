/* Your forks (F-021): enhances the server-rendered preview. Without this script everything still works as plain forms. */
(function () {
  var form = document.getElementById('fk-form');
  if (!form) return;
  var btn = document.getElementById('fk-apply');
  var boxes = Array.prototype.slice.call(form.querySelectorAll('.fk-check'));
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');

  function draft(box) {
    return document.querySelector('.fk-draft[data-key="' + box.getAttribute('data-plan') + '"]');
  }

  // Seeded from the boxes as the page loads (a browser may restore ticks on Back), and kept in step on every change.
  function sync() {
    var n = 0;
    boxes.forEach(function (box) {
      var d = draft(box);
      if (d) d.hidden = !box.checked;
      if (box.checked && !box.disabled) n++;
    });
    if (btn) {
      btn.textContent = 'Apply ' + n + ' plan' + (n === 1 ? '' : 's');
      btn.disabled = n === 0;
    }
  }

  boxes.forEach(function (box) { box.addEventListener('change', sync); });
  window.addEventListener('pageshow', sync);
  sync();

  // Apply: the drafts settle into the calendar, then the form posts. Reduced motion posts straight away.
  form.addEventListener('submit', function (e) {
    if (form.getAttribute('data-go')) return;
    var drafts = document.querySelectorAll('.fk-draft:not([hidden])');
    if (reduce.matches || !drafts.length) return;
    e.preventDefault();
    form.setAttribute('data-go', '1');
    Array.prototype.forEach.call(drafts, function (d, i) {
      d.style.setProperty('--i', i);
      d.classList.add('is-applying');
    });
    setTimeout(function () { form.submit(); }, 650 + drafts.length * 70);
  });
})();
