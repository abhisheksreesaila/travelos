// Turn a post into a trip (F-183): one small help on the paste page. When "Draft my trip" is pressed, the form gives way to a calm skeleton while the server reads the post and
// drafts it (the page then loads the editor). Without JavaScript the form just submits and the browser waits. "Write it myself" is instant, so it shows no skeleton. Motion is CSS
// (--motion-* tokens only), and reduced motion keeps the bands still.
(function () {
  var form = document.getElementById('ci-form');
  var skel = document.getElementById('ci-skel');
  if (!form || !skel) return;
  form.addEventListener('submit', function (e) {
    var by = e.submitter;
    if (!by || by.value !== 'draft') return;
    var link = (form.elements.link || {}).value || '';
    var text = (form.elements.text || {}).value || '';
    if (!link.trim() && !text.trim()) return;           // nothing to read: the server answers with its message, no skeleton
    skel.hidden = false;
    var root = form.closest('.ci');
    if (root) root.classList.add('is-drafting');
    skel.scrollIntoView({ block: 'nearest' });
  });
})();
