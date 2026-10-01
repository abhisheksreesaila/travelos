// "Where to?" (F-035): shows one age picker per kid, and keeps the return date after the leaving date.
// The page works without this script: the server reads the form and validates it. No prices are computed here.
(function () {
  var form = document.getElementById('st-form');
  if (!form) return;
  var kids = form.elements.n, ages = form.querySelector('#st-ages');
  var depart = form.elements.d, back = form.elements.r;

  function showAges() {
    var n = Number(kids.value) || 0;
    ages.hidden = n === 0;
    ages.querySelectorAll('[data-age]').forEach(function (field) {
      var show = Number(field.dataset.age) <= n;
      field.hidden = !show;
      field.querySelector('select').disabled = !show;
    });
  }

  function dayAfter(iso) {
    var t = new Date(iso + 'T00:00:00Z');
    t.setUTCDate(t.getUTCDate() + 1);
    return t.toISOString().slice(0, 10);
  }

  function keepOrder() {
    if (!depart.value) return;
    var min = dayAfter(depart.value);
    back.min = min;
    if (!back.value || back.value < min) back.value = min;
  }

  kids.addEventListener('change', showAges);
  depart.addEventListener('change', keepOrder);
  showAges();
  if (depart.value) back.min = dayAfter(depart.value);
})();
