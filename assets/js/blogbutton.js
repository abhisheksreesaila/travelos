// F-191: the Copy buttons of "Put this on your blog". A button names its text box in data-copy; a tap copies the box's text and says "Copied" with the one toast (GA.toast, toast.js,
// which grows out of the tap with GA.motion). The clipboard API needs https or localhost; otherwise the text is selected and copied the old way, and if that fails too it is left selected.
(function () {
  function say(text, error) { if (window.GA && GA.toast) GA.toast(text, error ? { error: true } : null); }
  function legacy(box) {
    box.focus(); box.select();
    try { return document.execCommand('copy'); } catch (e) { return false; }
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-copy]');
    var box = btn && document.getElementById(btn.getAttribute('data-copy'));
    if (!box) return;
    var done = function () { say('Copied'); }, fail = function () { box.focus(); box.select(); say('Press and hold to copy it', true); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(box.value).then(done, function () { legacy(box) ? done() : fail(); });
    else legacy(box) ? done() : fail();
  });
})();
