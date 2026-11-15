// The v2 top bar's account menu (F-255, D-650): the avatar opens a small frosted menu that grows out of it on the springs (GA.motion.open / close; on a laptop the same calls are a short
// fade). It closes on Escape (focus back on the avatar), on a tap outside, and when focus leaves it with Tab; the arrow keys, Home and End move through its items. Without this script the
// menu stays closed; the pill of sections beside it is plain links. Nothing here is a time: durations come from GA.motion's tokens.
(function () {
  var btn = document.getElementById('v2-me'), menu = document.getElementById('v2-menu');
  if (!btn || !menu) return;
  var motion = function () { return window.GA && window.GA.motion; };
  var busy = null;

  function items() { return Array.prototype.slice.call(menu.querySelectorAll('[role=menuitem]')); }
  function isOpen() { return !menu.hidden; }

  function open() {
    if (isOpen()) return;
    menu.hidden = false;
    busy = null;      // a fold still running must not hide it again
    btn.setAttribute('aria-expanded', 'true');
    if (motion()) motion().open(menu, btn);
    var first = items()[0];
    if (first) first.focus();
  }

  function close(refocus) {
    if (!isOpen()) return;
    btn.setAttribute('aria-expanded', 'false');
    var done = function () { menu.hidden = true; busy = null; };
    if (motion()) { var p = busy = motion().close(menu, btn); p.then(function () { if (busy === p) done(); }); } else done();
    if (refocus) btn.focus();
  }

  btn.addEventListener('click', function () { if (isOpen()) close(true); else open(); });
  btn.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); open(); }
  });
  menu.addEventListener('keydown', function (e) {
    var list = items(), i = list.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); list[(i + 1) % list.length].focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); list[(i - 1 + list.length) % list.length].focus(); }
    else if (e.key === 'Home') { e.preventDefault(); list[0].focus(); }
    else if (e.key === 'End') { e.preventDefault(); list[list.length - 1].focus(); }
    else if (e.key === 'Tab') close(false);
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && isOpen()) { e.preventDefault(); close(true); } });
  document.addEventListener('pointerdown', function (e) { if (isOpen() && !menu.contains(e.target) && !btn.contains(e.target)) close(false); });
})();
