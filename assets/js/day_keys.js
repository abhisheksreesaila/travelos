// The keys of the desktop day (F-144), in one small place. From 1020px, when nothing is being typed and no modifier is held:
//   T today · the left and right arrows the day before and after · W the week · D the day · / Ask
// (Esc is not here: the innermost thing closes first, each in its own file: a plan in the air and a new plan being drawn or named, the plan menu, a note, then the panel, day_dock.js.)
// `CZ.keys` maps a key (a letter in lower case, or `ArrowLeft`...) to the function that runs; it is the one place to add or replace a key. F-142 (Ask in the panel) needs nothing here: `/`
// opens the panel's Ask mode as soon as `Dock.register('ask', ...)` has been called, and otherwise follows the Ask tab's link (/trip/ask?day=N). A key never fires while a field is
// being typed in, a menu, a sheet or a card is open, or a plan is being held, drawn or named. Viewers have the keys too: none of them writes.
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var stage = CZ.stage;
  var desk = window.matchMedia('(min-width: 1020px) and (not (display-mode: standalone))');
  var keys = CZ.keys = CZ.keys || {};

  function level() { var v = CZ.view && CZ.view(); return v ? v.dataset.level : ''; }
  function press(sel) { var n = document.querySelector(sel); if (n) { n.click(); return true; } return false; }
  function step(dir) {
    var v = CZ.view && CZ.view(), u = v && v.dataset.level === 'day' ? v.dataset[dir] : '';
    if (u) CZ.goto(CZ.path(u), { dir: dir, key: null, mode: 'replace' });
  }
  keys.ArrowLeft = function () { step('prev'); };
  keys.ArrowRight = function () { step('next'); };
  keys.t = function () {
    var chip = stage.querySelector('.cz-hchip.is-today');
    if (chip) { if (!chip.classList.contains('is-open')) chip.click(); return; }
    if (level() === 'week' && press('#cz-z-day')) return;
    if (CZ.showToast) CZ.showToast('Today is not on this trip');
  };
  keys.w = function () { press('#cz-z-week[data-zoom]'); };
  keys.d = function () { press('#cz-z-day[data-zoom]'); };
  keys['/'] = function () {
    if (window.Dock && Dock.has('ask')) { Dock.show('ask', {}); return; }
    if (press('.cz-dock-tab[data-tab="ask"]')) return;          // (its link: /trip/ask?day=N)
    location.assign('/trip/ask');
  };

  function typing(t) { return !!t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)); }
  document.addEventListener('keydown', function (e) {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.isComposing || !desk.matches || typing(e.target)) return;
    var k = e.key && e.key.length === 1 ? e.key.toLowerCase() : e.key, fn = keys[k];
    if (!fn || !CZ.view || !CZ.view()) return;
    if (CZ.held || CZ.menuOpen || stage.querySelector('.cz-sheet-wrap, .cz-card-wrap, .cz-menu')) return;
    e.preventDefault();
    fn(e);
  });
})();
