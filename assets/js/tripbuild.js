// The guided trip builder (F-055): shows only the rows that apply (adults, kids' ages, flights / hotel / car yes-or-no).
// The page works without this script: the server reads every field and validates it. Nothing here decides what a trip is.
(function () {
  var form = document.getElementById("tb-form");
  if (!form) return;

  function rows(prefix, n) {
    form.querySelectorAll("[data-row]").forEach(function (row) {
      var m = /^([a-z]+)(\d+)$/.exec(row.getAttribute("data-row"));
      if (m && m[1] === prefix) row.hidden = Number(m[2]) > n;
    });
  }
  var adults = form.elements.adults, kids = form.elements.nkids;
  function people() {
    if (adults) rows("a", Number(adults.value) || 0);
    if (kids) {
      var n = Number(kids.value) || 0;
      rows("k", n);
      var box = document.getElementById("tb-ages");
      if (box) box.hidden = n === 0;
    }
  }
  if (adults) adults.addEventListener("change", people);
  if (kids) kids.addEventListener("change", people);

  function toggles() {
    form.querySelectorAll("[data-when]").forEach(function (box) {
      var name = box.getAttribute("data-when"), picked = form.querySelector('input[name="' + name + '"]:checked');
      var on = !picked || picked.value === "yes";
      box.hidden = !on;
    });
  }
  form.querySelectorAll("[data-toggle]").forEach(function (r) { r.addEventListener("change", toggles); });
  toggles();
  people();
})();
