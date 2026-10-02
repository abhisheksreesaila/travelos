// The import page (F-058): shows the chosen PDF's name beside the styled "Choose the PDF" button.
// Without this script the page still works: the hidden input is a real file input inside the form.
(function () {
  var input = document.getElementById("ti-file");
  var name = document.getElementById("ti-file-name");
  if (!input || !name) return;
  function show() {
    var file = input.files && input.files[0];
    name.textContent = file ? file.name : "No file chosen";
    name.classList.toggle("has-file", !!file);
  }
  input.addEventListener("change", show);
  show();
})();
