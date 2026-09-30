// Booking workspace behaviour. The server embeds every combination's figures (from gitaway.catalog)
// in #ws-data; this file only switches between them, so displayed totals always equal catalog.quote.
(function () {
  var dataEl = document.getElementById('ws-data');
  var grid = document.getElementById('ws-grid');
  if (!dataEl || !grid) return;
  var data = JSON.parse(dataEl.textContent);
  var LANE_KEY = { flight: 'f', stay: 'h', car: 'c' };
  var PANES = { 1: 'flights', 2: 'stays', 3: 'cars', 4: 'weather', 5: 'map', 6: 'news', 7: 'community' };
  var pick = {};
  document.querySelectorAll('.ws-offer').forEach(function (b) {
    if (b.getAttribute('aria-pressed') === 'true') pick[b.dataset.lane] = b.dataset.pick;
  });

  // Move the schematic map's stay pin and hotel-to-beach line to the picked stay (figures embedded by the server).
  var MAP_W = 320, MAP_H = 150;
  function paintMap(m) {
    if (!m) return;
    var pin = document.getElementById('ws-map-pin');
    if (!pin) return;
    pin.textContent = m.label;
    pin.dataset.mapPin = pick.stay;
    pin.style.left = (m.x / MAP_W * 100) + '%';
    pin.style.top = (m.y / MAP_H * 100) + '%';
    var dot = document.getElementById('ws-beach-dot');
    dot.style.left = (m.bx / MAP_W * 100) + '%';
    dot.style.top = (m.by / MAP_H * 100) + '%';
    var line = document.getElementById('ws-beach-line');
    line.setAttribute('x1', m.x); line.setAttribute('y1', m.y);
    line.setAttribute('x2', m.bx); line.setAttribute('y2', m.by);
    document.getElementById('ws-map-caption').textContent = m.caption;
  }

  function paint() {
    var key = [pick.flight, pick.stay, pick.car].join('|');
    var q = data.quotes[key];
    if (!q) return;
    ['flight', 'stay', 'car'].forEach(function (lane) {
      var o = data.offers[pick[lane]];
      document.querySelector('[data-slot="' + lane + '"]').textContent = o.name;
      document.querySelector('[data-slot-price="' + lane + '"]').textContent = o.price;
    });
    document.getElementById('ws-total').textContent = q.total;
    var chip = document.getElementById('ws-delta');
    chip.textContent = q.delta;
    chip.classList.toggle('fill-mint', q.cheapest);
    chip.classList.toggle('fill-sun-tint', !q.cheapest);
    document.getElementById('ws-book').setAttribute('href', q.book);
    history.replaceState(null, '', q.url);
    paintMap(data.map && data.map[pick.stay]);
  }

  document.querySelectorAll('.ws-offer').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var lane = btn.dataset.lane;
      pick[lane] = btn.dataset.pick;
      document.querySelectorAll('.ws-offer[data-lane="' + lane + '"]').forEach(function (o) {
        o.setAttribute('aria-pressed', o === btn ? 'true' : 'false');
      });
      paint();
    });
  });

  function focusPane(name, moveFocus) {
    grid.dataset.focus = name;
    document.querySelectorAll('.ws-pane[data-pane]').forEach(function (p) {
      var on = p.dataset.pane === name;
      p.classList.toggle('is-focused', on);
      var t = p.querySelector('.ws-focus');
      if (t) t.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    if (moveFocus) {
      var pane = document.querySelector('.ws-pane[data-pane="' + name + '"]');
      var first = pane && (pane.querySelector('.ws-offer[aria-pressed="true"]') || pane.querySelector('.ws-offer') || pane.querySelector('.ws-focus'));
      if (first) first.focus({ preventScroll: false });
    }
  }

  function setExpanded(name) {
    if (name) grid.dataset.expanded = name; else delete grid.dataset.expanded;
    document.querySelectorAll('.ws-expand').forEach(function (b) {
      b.setAttribute('aria-expanded', b.dataset.expand === name ? 'true' : 'false');
    });
    if (name) focusPane(name, false);
  }

  document.querySelectorAll('.ws-focus').forEach(function (b) {
    b.addEventListener('click', function () { focusPane(b.dataset.focus, false); });
  });
  document.querySelectorAll('.ws-expand').forEach(function (b) {
    b.addEventListener('click', function () {
      setExpanded(grid.dataset.expanded === b.dataset.expand ? '' : b.dataset.expand);
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (e.key === 'Escape' && grid.dataset.expanded) {
      var was = grid.dataset.expanded;
      setExpanded('');
      var btn = document.querySelector('.ws-expand[data-expand="' + was + '"]');
      if (btn) btn.focus();
    } else if (PANES[e.key]) {
      e.preventDefault();
      if (grid.dataset.expanded) setExpanded(PANES[e.key]);
      focusPane(PANES[e.key], true);
    }
  });

  var toggle = document.getElementById('ws-details');
  if (toggle) toggle.addEventListener('click', function () {
    var open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    toggle.textContent = open ? 'Hide' : 'Details';
    toggle.closest('.ws-ledger').classList.toggle('is-open', open);
  });

  // Keep page padding in step with the pinned ledger's real height (phone layout).
  var ledger = document.querySelector('.ws-ledger');
  function sizeLedger() {
    document.documentElement.style.setProperty('--ws-ledger-h', ledger.offsetHeight + 'px');
  }
  if (ledger) {
    sizeLedger();
    if (window.ResizeObserver) new ResizeObserver(sizeLedger).observe(ledger);
    else window.addEventListener('resize', sizeLedger);
  }

  focusPane('flights', false);
})();
