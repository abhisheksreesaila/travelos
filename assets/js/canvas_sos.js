// The trip canvas, SOS (F-093, F-109; a module since F-128). Loaded after canvas_core.js.
// SOS opens from the page itself, with no network: the emergency sheet sits inert in a <template> in every week and day page. It grows out of the SOS button and folds
// back into it (GA.motion); it adds no history entry; close, the scrim and Escape take it away again. (With no template, the sheet is already the level and the link is a plain zoom.)
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var stage = CZ.stage;

  function focus(n) { if (n) { try { n.focus({ preventScroll: true }); } catch (err) { n.focus(); } } }

  function open(e, button) {
    var v = CZ.view(), tpl = v && v.querySelector('#cz-sos-tpl');
    if (!tpl) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    var old = v.querySelector('.cz-sheet-wrap[data-local]');
    if (old && !old.dataset.closing) return;
    if (old) old.remove();      // one still folding back into the button: this tap opens a fresh one
    var frag = tpl.content.cloneNode(true);
    frag.querySelector('.cz-sheet-wrap').setAttribute('data-local', '1');
    v.appendChild(frag);
    var lw = v.querySelector('.cz-sheet-wrap[data-local]');
    lw._from = button;
    if (window.GA && GA.motion) GA.motion.open(lw.querySelector('.cz-sheet'), button, { scrim: lw.querySelector('.cz-scrim') });
    focus(v.querySelector('.cz-sheet-wrap[data-local] #cz-sheet-title'));
  }

  function close(e) {
    e.preventDefault();
    e.stopImmediatePropagation();
    var w = stage.querySelector('.cz-sheet-wrap[data-local]');
    var b = stage.querySelector('.cz-fold.is-on .cz-sos') || stage.querySelector('#cz-sos');      // F-103: the folded bar's own SOS when that is the one on screen
    if (w && window.GA && GA.motion && !CZ.reduced.matches && w.querySelector('.cz-sheet')) {
      if (w.dataset.closing) return;
      w.dataset.closing = '1'; w.setAttribute('inert', '');
      GA.motion.close(w.querySelector('.cz-sheet'), b || w._from, { scrim: w.querySelector('.cz-scrim') }).then(function () { w.remove(); });
    } else if (w) w.remove();
    focus(b);
  }

  document.addEventListener('click', function (e) {
    if (e.button || !e.target.closest || !stage.contains(e.target)) return;
    var button = e.target.closest('a.cz-sos');
    if (button) open(e, button);
    else if (e.target.closest('.cz-sheet-wrap[data-local] .cz-close, .cz-sheet-wrap[data-local] .cz-scrim')) close(e);
  }, true);
})();
