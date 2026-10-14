// A mouse on the desktop day (F-144): hover a plan and its two tools appear, a knob at its foot (pull it to change the length) and a menu button (rename and delete); a right-click on a plan
// opens the same menu. The menu is the phone's hold menu (day_menu.js, `CZ.hold`), not a second one; the knob starts the resize day_grid.js already does (it reads `.cz-g-tknob`).
// The tools are a layer next to the block, the size of the block (the block clips its words, so a knob that straddles its foot cannot live inside it). They are for a mouse only: a touch,
// a viewer and a phone never get them, and a keyboard keeps the block's own hidden menu button. Needs canvas_core.js, day_grid.js and day_menu.js, which load first.
(function () {
  var CZ = window.CZ;
  if (!CZ || !CZ.mouseOn || !CZ.hold) return;
  var stage = CZ.stage;
  var tools = null;      // { layer, block, engaged }
  var leave = 0;

  function editing() { return stage.dataset.edit === '1'; }
  function mk(tag, cls) { var n = document.createElement(tag); if (cls) n.className = cls; return n; }
  function drop() {
    clearTimeout(leave);
    if (!tools) return;
    if (tools.layer.parentNode) tools.layer.parentNode.removeChild(tools.layer);
    tools = null;
  }
  function leaveSoon() { clearTimeout(leave); leave = setTimeout(drop, 120); }
  function dots() {
    var s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('fill', 'currentColor'); s.setAttribute('aria-hidden', 'true');
    [5, 12, 19].forEach(function (x) { var c = document.createElementNS('http://www.w3.org/2000/svg', 'circle'); c.setAttribute('cx', x); c.setAttribute('cy', 12); c.setAttribute('r', 2.1); s.appendChild(c); });
    return s;
  }
  function placeLayer(layer, b) {
    var s = layer.style;
    s.left = b.offsetLeft + 'px'; s.top = b.offsetTop + 'px'; s.width = b.offsetWidth + 'px'; s.height = b.offsetHeight + 'px';
  }

  function showFor(b) {
    if (tools && tools.block === b && tools.layer.isConnected) { clearTimeout(leave); return; }
    drop();
    if (!editing() || CZ.held || CZ.menuOpen || b.classList.contains('is-new') || b.classList.contains('is-editing') || (CZ.landing && CZ.landing())) return;
    var layer = mk('div', 'cz-g-tools'), more = mk('button', 'cz-g-tmenu'), knob = mk('i', 'cz-g-tknob');
    layer.setAttribute('aria-hidden', 'true');                       // the keyboard and the screen reader have the block's own hidden menu button
    layer.style.setProperty('--accent', getComputedStyle(b).getPropertyValue('--accent'));
    more.type = 'button';
    more.tabIndex = -1;
    more.title = 'Rename or delete';
    more.appendChild(dots());
    layer.appendChild(more);
    layer.appendChild(knob);
    layer.block = b;
    b.parentNode.insertBefore(layer, b.nextSibling);
    placeLayer(layer, b);
    tools = { layer: layer, block: b };
    more.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      var blk = layer.block;
      drop();
      if (blk && blk.isConnected) CZ.hold(blk);
    });
  }

  stage.addEventListener('pointermove', function (e) {
    if (!CZ.mouseOn(e) || e.buttons) return;
    var t = e.target;
    if (!t.closest) return;
    if (t.closest('.cz-g-tools')) { clearTimeout(leave); return; }
    var b = t.closest('.cz-gb[data-act]');
    if (b && stage.contains(b)) showFor(b); else if (tools) leaveSoon();
  });
  stage.addEventListener('pointerleave', function (e) { if (CZ.mouseOn(e) && tools) leaveSoon(); });
  document.addEventListener('pointerdown', function (e) {          // a press on a block or its tools is a gesture (day_grid.js); a press elsewhere puts the tools away
    if (!tools || !CZ.mouseOn(e)) return;
    if (e.target.closest && e.target.closest('.cz-g-tools, .cz-gb')) { tools.engaged = true; return; }
    drop();
  }, true);
  document.addEventListener('pointerup', function () {             // a drag changed the block: its tools are drawn again when the pointer moves
    if (tools && tools.engaged) { var t = tools; setTimeout(function () { if (tools === t) drop(); }, 0); }
  });
  stage.addEventListener('cz:swap', drop);

  // right-click: the same menu as the button
  stage.addEventListener('contextmenu', function (e) {
    if (!editing() || e.pointerType === 'touch' || !CZ.dayBox || !CZ.dayBox()) return;
    var b = e.target.closest ? e.target.closest('.cz-gb[data-act]') : null;
    if (!b || !stage.contains(b) || b.classList.contains('is-new') || b.classList.contains('is-editing')) return;
    e.preventDefault();
    drop();
    CZ.hold(b);
  });
})();
