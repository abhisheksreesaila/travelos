// The publish editor (F-181): two small helps on top of a plain form.
//   1. Choosing a photo as the cover also includes it (the cover must be one of the picked photos).
//   2. "Add photos" sends the pictures through the existing upload (POST /trip/photos, the same route and checks the Family tab uses), after quietly saving what was typed, then comes back to
//      this page with the new photos already ticked (?added=id,id), so a note written a moment ago is never lost.
// Everything else (picking, notes, tips, preview, publish) is the form itself and works without this script.
(function () {
  var form = document.getElementById('pb-form');
  if (!form) return;

  form.addEventListener('change', function (e) {
    var t = e.target;
    if (!t.classList || !t.classList.contains('pb-cover')) return;
    var tile = t.closest('.pb-tile');
    var pick = tile && tile.querySelector('.pb-pick');
    if (pick) pick.checked = true;
  });

  var add = document.getElementById('pb-add');
  var say = document.getElementById('pb-add-say');
  if (!add) return;

  function tell(text) { if (say) say.textContent = text; }

  add.addEventListener('change', function () {
    var files = Array.prototype.slice.call(add.files || []);
    if (!files.length) return;
    tell(files.length === 1 ? 'Adding your photo…' : 'Adding ' + files.length + ' photos…');
    var trip = (form.querySelector('input[name="trip"]') || {}).value || '';
    fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'X-Fragment': '1' }, credentials: 'same-origin' })
      .then(function () {
        var body = new FormData();
        files.slice(0, 6).forEach(function (f) { body.append('photo', f); });
        if (trip) body.append('trip', trip);
        return fetch('/trip/photos', { method: 'POST', body: body, headers: { 'X-Fragment': '1' }, credentials: 'same-origin' });
      })
      .then(function (r) {
        return r.text().then(function (text) {
          if (!r.ok) throw new Error(text || 'Could not add that photo.');
          return JSON.parse(text);
        });
      })
      .then(function (res) {
        location.href = '/trip/publish?added=' + encodeURIComponent((res.ids || []).join(','));
      })
      .catch(function (err) {
        tell(err && err.message ? err.message : 'Could not add that photo. Try again.');
        add.value = '';
      });
  });
})();
