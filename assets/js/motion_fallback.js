// The one stand-in for GA.motion (F-110), defined once. It loads right after motion.js on every page: when motion.js is there it does nothing; when motion.js did not load (or
// failed) every script that moves something (the Ask sheet, the hold menu, the plan card, pickers, the toast, the workspace) still works, with instant changes and no error.
// The scripts take `GA.motion` as given and no longer carry a copy of this.
(function () {
  var GA = window.GA = window.GA || {};
  if (GA.motion) return;
  var done = function () { return Promise.resolve(); };
  GA.motion = {
    fallback: true, log: [],
    open: done, close: done, stop: function () {}, spring: done, flip: done, run: done, settle: done,
    reflow: function (el, change, o) { change(); if (o && o.during) o.during(); return done(); },
    origin: function () { return null; },
    box: function (el) { return el.getBoundingClientRect(); },
    reduced: function () { return true; },
    ease: function () { return 'ease-out'; },
    t: function () { return 240; }
  };
})();
