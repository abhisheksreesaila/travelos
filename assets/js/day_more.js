// The "+N more" card of a crowded phone or tablet day (F-160). Where more than three plans would stand side by side, the server keeps two lanes and puts the rest behind one kind-neutral card
// in the third (`.cz-lanemore`, data-more = the ids behind it; those plans are `.is-more`: in place but not drawn). Tapping the card opens a short list of them, each row its start time and its title,
// in the hold menu's own look (`.cz-menu`, grown out of the card with the shared motion). A row opens the plan's hold menu for an editor (so re-timing, moving to another day, renaming and
// deleting stay one tap away, as for any plan) and its card for a viewer. The list counts only the plans a filter still shows. Also here: a title cut at its second line is marked `.is-cut`, which
// day_phone.css fades. Needs canvas_core.js (window.CZ), which loads first.
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var MO = window.GA && window.GA.motion;
  var stage = CZ.stage;
  var list = null;      // the open list: { node, card }

  function mk(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; }
  function clamp(v, lo, hi) { return Math.min(Math.max(v, lo), hi); }
  function clock12(m) { var h = Math.floor(m / 60) % 24, mm = m % 60; return ((h % 12) || 12) + ':' + (mm < 10 ? '0' : '') + mm + ' ' + (h < 12 ? 'AM' : 'PM'); }

  function close(returnFocus) {
    if (!list) return;
    var l = list;
    list = null;
    document.removeEventListener('pointerdown', outside, true);
    CZ.menuOpen = false;
    var gone = function () { if (l.node.parentNode) l.node.parentNode.removeChild(l.node); };
    if (MO && !MO.reduced() && l.node.parentNode) {
      l.node.setAttribute('inert', ''); l.node.style.pointerEvents = 'none';
      MO.close(l.node, l.card.isConnected ? l.card : null).then(gone);
    } else gone();
    if (returnFocus && l.card.isConnected) { try { l.card.focus({ preventScroll: true }); } catch (e) { l.card.focus(); } }
  }
  function outside(e) { if (list && !list.node.contains(e.target) && !(e.target.closest && e.target.closest('.cz-lanemore') === list.card)) close(false); }

  function place(node, card) {
    var sr = stage.getBoundingClientRect(), cr = card.getBoundingClientRect();
    var tabs = document.querySelector('.ph-tabs'), floor = (tabs && getComputedStyle(tabs).display !== 'none' ? tabs.getBoundingClientRect().top : window.innerHeight) - 8;
    var w = Math.min(node.offsetWidth, window.innerWidth - 16), h = node.offsetHeight;
    var x = clamp(cr.right - w, 8, window.innerWidth - w - 8);
    var y = cr.bottom + 8;
    if (y + h > floor) y = Math.max(8, cr.top - h - 8);
    node.style.left = (x - sr.left) + 'px';
    node.style.top = (y - sr.top) + 'px';
  }

  function open(card) {
    close(false);
    var ids = (card.dataset.more || '').split(' ').filter(Boolean);
    var blocks = ids.map(function (id) { return stage.querySelector('.cz-gb[data-act="' + id + '"]'); }).filter(function (b) { return b && !b.classList.contains('is-off'); });
    if (!blocks.length) return;
    var node = mk('div', 'cz-menu cz-more-list');
    node.setAttribute('role', 'menu');
    node.tabIndex = -1;
    node.setAttribute('aria-label', blocks.length + ' more plans');
    node.appendChild(mk('p', 'cz-menu-t', blocks.length + (blocks.length === 1 ? ' more plan' : ' more plans')));
    var rows = mk('div', 'cz-more-rows');
    blocks.forEach(function (b) {
      var row = mk('button', 'cz-mi cz-more-row');
      row.type = 'button';
      row.setAttribute('role', 'menuitem');
      row.appendChild(mk('span', 'cz-more-when', clock12(+b.dataset.s)));
      row.appendChild(mk('span', 'cz-mi-t', b.dataset.title || 'A plan'));
      row.addEventListener('click', function () {
        var link = b.querySelector('.cz-gb-open');
        close(false);
        if (stage.dataset.edit === '1' && CZ.hold) CZ.hold(b);      // an editor: the hold menu, with every move a held plan has (it cannot be held where it waits)
        else if (link) link.click();      // a viewer: the plan's own card, as a tap on it would open it
      });
      rows.appendChild(row);
    });
    node.appendChild(rows);
    stage.appendChild(node);
    list = { node: node, card: card };
    CZ.menuOpen = true;
    place(node, card);
    if (MO) {
      node.style.pointerEvents = 'none';
      MO.open(node, card).then(function () { if (node.isConnected && !node.hasAttribute('inert')) node.style.pointerEvents = ''; });
    }
    document.addEventListener('pointerdown', outside, true);
    try { node.focus({ preventScroll: true }); } catch (e) { node.focus(); }
  }

  stage.addEventListener('click', function (e) {
    var card = e.target.closest && e.target.closest('.cz-lanemore');
    if (!card) return;
    e.preventDefault();
    if (list && list.card === card) close(true); else open(card);
  });
  document.addEventListener('keydown', function (e) {
    if (!list) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); close(true); return; }
    var rows = Array.prototype.slice.call(list.node.querySelectorAll('.cz-more-row')), at = rows.indexOf(document.activeElement), next = null;
    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') next = rows[(at + 1) % rows.length];
    else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') next = rows[(at < 0 ? 0 : at - 1 + rows.length) % rows.length];
    else if (e.key === 'Home') next = rows[0];
    else if (e.key === 'End') next = rows[rows.length - 1];
    if (next) { e.preventDefault(); e.stopImmediatePropagation(); next.focus(); }
  }, true);
  stage.addEventListener('cz:swap', function () { if (list && !list.card.isConnected) close(false); });

  // A plan's title that needs more than two lines is cut at the second (day_phone.css), and the end of that line fades. One observer re-measures when the box changes size; the fonts arriving
  // change the text, not the box, so they re-measure too.
  var ro = window.ResizeObserver ? new ResizeObserver(function (l) { markCuts(l.map(function (e) { return e.target; })); }) : null;
  function markCuts(ts) {      // F-173: every title is measured, then every mark is written (a read after a write makes the browser lay the page out again, once per title)
    var cut = Array.prototype.map.call(ts, function (t) { return t.clientWidth ? t.scrollHeight > t.clientHeight + 1 : null; });
    Array.prototype.forEach.call(ts, function (t, i) { if (cut[i] !== null) t.classList.toggle('is-cut', cut[i]); });
  }
  function watchCuts() {
    var titles = stage.querySelectorAll('.cz-gb-t');
    if (ro) { ro.disconnect(); titles.forEach(function (t) { ro.observe(t); }); }
    markCuts(titles);
  }
  if (CZ.onSwap) CZ.onSwap.push(watchCuts);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(watchCuts);
  watchCuts();
})();
