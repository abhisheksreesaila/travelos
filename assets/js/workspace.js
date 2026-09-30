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

  // The address bar keeps the pick (from the server's quote) plus which pane is split open and which offer is being viewed.
  function syncUrl() {
    var q = data.quotes[[pick.flight, pick.stay, pick.car].join('|')];
    if (!q) return;
    var url = q.url, name = grid.dataset.expanded;
    if (SPLIT[name]) {
      url += '&x=' + name;
      var pane = paneEl(name);
      if (pane.dataset.screen === 'detail') url += '&v=' + viewing[name];
    }
    history.replaceState(null, '', url);
  }

  // "Choose" buttons say "Chosen" on the lane's pick; the labels live in the markup.
  function paintChoose() {
    document.querySelectorAll('.ws-choose').forEach(function (b) {
      var on = pick[b.dataset.chooseLane] === b.dataset.choose;
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.textContent = on ? 'Chosen' : b.dataset.label;
    });
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
    syncUrl();
    paintChoose();
    paintMap(data.map && data.map[pick.stay]);
  }

  function selectPick(lane, id) {
    pick[lane] = id;
    // A pick made while the lane is tiled is what the split view opens on next.
    Object.keys(SPLIT).forEach(function (n) { if (SPLIT[n] === lane && grid.dataset.expanded !== n) viewing[n] = id; });
    document.querySelectorAll('.ws-offer[data-lane="' + lane + '"]').forEach(function (o) {
      o.setAttribute('aria-pressed', o.dataset.pick === id ? 'true' : 'false');
    });
    paint();
  }

  // Split view (F-025). Flights and Stays expand into a list sidebar and a detail panel; the detail is server-rendered,
  // so this only shows one panel at a time. On a phone the list and the detail are two screens.
  var SPLIT = { flights: 'flight', stays: 'stay' };
  var viewing = {};
  var phone = window.matchMedia('(max-width: 720px)');
  var still = window.matchMedia('(prefers-reduced-motion: reduce)');
  function paneEl(name) { return document.querySelector('.ws-pane[data-pane="' + name + '"]'); }
  Object.keys(SPLIT).forEach(function (name) {
    var cur = paneEl(name).querySelector('.ws-detail-panel:not([hidden])');
    viewing[name] = cur ? cur.dataset.detail : pick[SPLIT[name]];
  });

  function view(name, id, focusCard) {
    var pane = paneEl(name);
    viewing[name] = id;
    pane.querySelectorAll('.ws-offer').forEach(function (b) {
      if (b.dataset.pick === id) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current');
    });
    pane.querySelectorAll('.ws-detail-panel').forEach(function (a) { a.hidden = a.dataset.detail !== id; });
    var sc = pane.querySelector('.ws-detail-panel:not([hidden]) .ws-dscroll');
    if (sc) sc.scrollTop = 0;
    if (focusCard) {
      var card = pane.querySelector('.ws-offer[data-pick="' + id + '"]');
      if (card) card.focus();
    }
    syncUrl();
  }

  function screen(name, which) {
    paneEl(name).dataset.screen = which;
    syncUrl();
  }

  document.querySelectorAll('.ws-offer').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var name = btn.closest('.ws-pane').dataset.pane;
      if (SPLIT[name] && grid.dataset.expanded === name) {
        // Expanded: a card opens its detail (Choose picks). On a phone that moves to the detail screen.
        view(name, btn.dataset.pick, false);
        if (phone.matches) {
          screen(name, 'detail');
          var back = paneEl(name).querySelector('.ws-detail-panel:not([hidden]) .ws-back');
          if (back) back.focus();
        }
        return;
      }
      selectPick(btn.dataset.lane, btn.dataset.pick);
    });
  });

  document.querySelectorAll('.ws-choose').forEach(function (b) {
    b.addEventListener('click', function () { selectPick(b.dataset.chooseLane, b.dataset.choose); });
  });

  document.querySelectorAll('[data-back="list"]').forEach(function (b) {
    b.addEventListener('click', function () { backToList(b.closest('.ws-pane').dataset.pane); });
  });
  function backToList(name) {
    screen(name, 'list');
    var card = paneEl(name).querySelector('.ws-offer[data-pick="' + viewing[name] + '"]');
    if (card) card.focus();
  }

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

  function applyExpanded(name) {
    if (name) grid.dataset.expanded = name; else delete grid.dataset.expanded;
    document.querySelectorAll('.ws-expand').forEach(function (b) {
      var on = b.dataset.expand === name;
      b.setAttribute('aria-expanded', on ? 'true' : 'false');
      b.setAttribute('aria-label', (on ? 'Collapse ' : 'Expand ') + b.dataset.title + ' pane');
    });
    if (name) focusPane(name, false);
  }

  // Morph the pane between its tile and the expanded view (first/last rectangles, transform only).
  // Reduced motion, or no Web Animations, swaps instantly.
  function setExpanded(name) {
    var target = paneEl(name || grid.dataset.expanded || '');
    var before = target && target.getBoundingClientRect();
    applyExpanded(name);
    if (!target || still.matches || !target.animate || !before.width) return;
    var after = target.getBoundingClientRect();
    if (!after.width) return;
    target.animate([
      { transformOrigin: 'top left', transform: 'translate(' + (before.left - after.left) + 'px,' + (before.top - after.top) + 'px) scale(' + (before.width / after.width) + ',' + (before.height / after.height) + ')' },
      { transformOrigin: 'top left', transform: 'none' }
    ], { duration: 320, easing: 'cubic-bezier(.2,.8,.2,1)' });
  }

  // Open a split pane: the current pick (or the offer in the URL) is shown, and focus lands on its card.
  function openSplit(name) {
    setExpanded(name);
    if (phone.matches) screen(name, 'list'); else screen(name, 'detail');
    view(name, viewing[name] || pick[SPLIT[name]], false);
    var card = paneEl(name).querySelector('.ws-offer[data-pick="' + viewing[name] + '"]');
    if (card) card.focus();
  }

  function collapse() {
    var was = grid.dataset.expanded;
    if (!was) return;
    setExpanded('');
    if (SPLIT[was]) viewing[was] = pick[SPLIT[was]];
    syncUrl();
    var btn = document.querySelector('.ws-expand[data-expand="' + was + '"]');
    if (btn) btn.focus();
  }

  document.querySelectorAll('.ws-focus').forEach(function (b) {
    b.addEventListener('click', function () { focusPane(b.dataset.focus, false); });
  });
  document.querySelectorAll('.ws-expand').forEach(function (b) {
    b.addEventListener('click', function () {
      var name = b.dataset.expand;
      if (grid.dataset.expanded === name) { collapse(); return; }
      if (SPLIT[name]) openSplit(name); else setExpanded(name);
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    var open = grid.dataset.expanded;
    if (e.key === 'Escape' && open) {
      // On a phone's detail screen, Esc goes back to the list first.
      if (SPLIT[open] && phone.matches && paneEl(open).dataset.screen === 'detail') backToList(open); else collapse();
    } else if (e.key === 'Enter' && !open && t && t.closest) {
      // A pane's key then Enter opens the split view: Enter on the picked card (or the pane title) of Flights or Stays.
      var host = t.closest('.ws-pane[data-pane]');
      var name = host && host.dataset.pane;
      var onPicked = t.classList.contains('ws-offer') && t.getAttribute('aria-pressed') === 'true';
      if (SPLIT[name] && (onPicked || t.classList.contains('ws-focus'))) { e.preventDefault(); openSplit(name); }
    } else if (PANES[e.key]) {
      e.preventDefault();
      var next = PANES[e.key];
      if (open) { if (SPLIT[next]) openSplit(next); else setExpanded(next); }
      focusPane(next, !open || !SPLIT[next]);
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

  var start = grid.dataset.expanded;
  focusPane(start || 'flights', false);
  paintChoose();
})();
