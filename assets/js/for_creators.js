// The For creators page (F-186): one small help. A visitor who is not signed in pastes first and signs in after, and the sign-in takes them away from the page,
// so the box's text is kept in this browser (localStorage, never sent anywhere until the person submits it on the paste page) and the paste page puts it back.
// Without JavaScript the form still posts: signed in it drafts at once, signed out the person signs in and pastes again.
(function () {
  var form = document.getElementById('fc-paste');
  if (!form) return;
  form.addEventListener('submit', function (e) {
    if (form.dataset.signedIn === '1') return;
    var by = e.submitter, box = form.elements.text;
    if (!by || by.value !== 'draft' || !box || !box.value.trim()) return;
    try { localStorage.setItem('ga-paste', JSON.stringify({ text: box.value, at: Date.now() })); } catch (err) { /* private mode: they paste again */ }
  });
})();
