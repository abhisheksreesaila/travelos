// The booking lanes' trip form (F-198): one age picker per kid, as the old Where to? form had. The page works without it: the server reads the kid count and the first that many ages.
(function () {
  var form = document.getElementById('ps-trip');
  if (!form || !form.elements.n) return;
  var kids = form.elements.n;
  function show() {
    var n = Number(kids.value) || 0;
    form.querySelectorAll('[data-age]').forEach(function (field) {
      var on = Number(field.dataset.age) <= n;
      field.hidden = !on;
      field.querySelector('select').disabled = !on;
    });
  }
  kids.addEventListener('change', show);
  show();
})();
