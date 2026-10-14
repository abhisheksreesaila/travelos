// Drop a plan on a day chip (F-151), on a laptop. While a plan is held with the mouse (day_grid.js), the day chips in the ink header become drop targets: the chip under the pointer
// shows it will take the plan (a coral ring, the rest of the row a quiet dashed one); the chip of the day the plan is already on does not accept. A trip with more days than the header
// shows has chips that scroll sideways: holding the plan near either end of the row scrolls it. This file only finds the chip and draws the targets; day_grid.js owns the gesture
// (the lift, Esc, the label) and the save, and calls these four: begin() when a plan is lifted, over(x, y) for the chip under the pointer, tick(x, y) every frame (the edge scroll),
// end() when the plan is let go of or put back. Needs canvas_core.js (`CZ`); the chips are `.cz-hchip[data-move-day]` (tripcanvas.head_chips).
(function () {
  var CZ = window.CZ;
  if (!CZ) return;
  var stage = CZ.stage;
  var ZONE = 3;          // rem: the stretch at each end of the row that scrolls it
  var SPEED = 9;         // px a frame at the very end
  var nav = null, hot = null;

  function rem() { return parseFloat(getComputedStyle(document.documentElement).fontSize) || 12; }
  function row() { return stage.querySelector('.cz-view[data-day] .cz-hchips'); }
  function inside(r, x, y) { return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom; }

  function clearHot() { if (hot) { hot.classList.remove('is-drop-target'); hot = null; } }

  CZ.chipDrop = {
    // A plan was lifted: the row says where it can go.
    begin: function () {
      nav = row();
      if (!nav) return false;
      nav.classList.add('is-dropping');
      return true;
    },
    // The chip under the pointer that takes a drop (null: none, or the day the plan is already on).
    over: function (x, y) {
      if (!nav || !nav.isConnected) return null;
      var found = null;
      if (inside(nav.getBoundingClientRect(), x, y)) {
        var chips = nav.querySelectorAll('.cz-hchip[data-move-day]');
        for (var i = 0; i < chips.length; i++) {
          if (inside(chips[i].getBoundingClientRect(), x, y)) { found = chips[i]; break; }
        }
      }
      if (found && found.classList.contains('is-open')) found = null;
      if (found !== hot) { clearHot(); if (found) { hot = found; hot.classList.add('is-drop-target'); } }
      return found;
    },
    // Is the pointer over the header row (so the grid card below must not start to scroll)?
    inBand: function (y) { return !!nav && nav.isConnected && y <= nav.getBoundingClientRect().bottom + rem() * 0.5; },
    // Every frame: the row scrolls when the plan is held near its ends. True when it moved (the hovered chip is looked up again).
    tick: function (x, y) {
      if (!nav || !nav.isConnected || nav.scrollWidth <= nav.clientWidth) return false;
      var r = nav.getBoundingClientRect(), zone = rem() * ZONE;
      if (y < r.top - rem() || y > r.bottom + rem()) return false;
      var dx = 0;
      if (x < r.left + zone) dx = -Math.ceil(Math.min(1, (r.left + zone - x) / zone) * SPEED);
      else if (x > r.right - zone) dx = Math.ceil(Math.min(1, (x - (r.right - zone)) / zone) * SPEED);
      if (!dx) return false;
      var before = nav.scrollLeft;
      nav.scrollLeft = before + dx;
      return nav.scrollLeft !== before;
    },
    end: function () {
      clearHot();
      if (nav) nav.classList.remove('is-dropping');
      nav = null;
    }
  };
})();
