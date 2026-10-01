// Booking workspace behaviour. The page never does arithmetic on money: every figure in the ledger, the stay prices and the
// choose bar comes from GET /plan/quote (computed by gitaway.catalog) and is only swapped in here.
(function () {
  var dataEl = document.getElementById('ws-data');
  var grid = document.getElementById('ws-grid');
  if (!dataEl || !grid) return;
  var data = JSON.parse(dataEl.textContent);
  var PANES = { 1: 'flights', 2: 'stays', 3: 'cars', 4: 'weather', 5: 'map', 6: 'news', 7: 'community' };
  var still = window.matchMedia('(prefers-reduced-motion: reduce)');
  var phone = window.matchMedia('(max-width: 720px)');
  // The lane picks, plus the stay's rooms and add-ons as compact codes ("cq1", "bf"). null means "the default".
  var pick = { flight: data.pick.f, stay: data.pick.h, car: data.pick.c, rooms: data.pick.rooms, add: data.pick.add };
  var base = data.base; // the address-bar URL for the pick, from the server
  var tripq = data.tripq || ''; // the trip's URL params ("d=..&r=..&a=..&k=.."), empty for the sample trip; just passed along

  // ---- asking the server for figures ------------------------------------------------------------------------------
  function enc(s) { return encodeURIComponent(s); }
  function getQuote(qs) {
    return fetch('/plan/quote?' + qs, { headers: { Accept: 'application/json' } }).then(function (r) {
      if (!r.ok) throw new Error('quote ' + r.status);
      return r.json();
    });
  }
  function pickQuery() {
    return 'f=' + enc(pick.flight) + '&h=' + enc(pick.stay) + '&c=' + enc(pick.car) +
      (pick.rooms == null ? '' : '&rooms=' + enc(pick.rooms)) + (pick.add == null ? '' : '&add=' + enc(pick.add)) + (tripq ? '&' + tripq : '');
  }

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

  // The address bar keeps the pick (the server's URL for it) plus which pane is split open and which offer is being viewed.
  function syncUrl() {
    var url = base, name = grid.dataset.expanded;
    if (SPLIT[name]) {
      url += '&x=' + name;
      var pane = paneEl(name);
      if (pane.dataset.screen === 'detail') url += '&v=' + viewing[name];
    }
    history.replaceState(null, '', url);
  }

  function panelOf(id) { return document.querySelector('.ws-detail-panel[data-detail="' + id + '"]'); }

  // "Choose" buttons say "Chosen" on the lane's pick; for a stay that means these very rooms and add-ons.
  function paintChoose() {
    document.querySelectorAll('.ws-choose').forEach(function (b) {
      var on = pick[b.dataset.chooseLane] === b.dataset.choose;
      if (on && b.dataset.chooseLane === 'stay') {
        var p = panelOf(b.dataset.choose);
        on = !!p && p.dataset.rooms === pick.rooms && p.dataset.add === pick.add;
      }
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.textContent = on ? 'Chosen' : b.dataset.label;
    });
  }

  // Show one stay's editor state (rooms, add-ons, fit badge, choose bar) exactly as the server described it.
  function applyStay(panel, s) {
    if (!panel || !s) return;
    panel.dataset.rooms = s.rooms_code;
    panel.dataset.add = s.add_code;
    panel.querySelectorAll('.ws-room').forEach(function (card) {
      var n = s.rooms[card.dataset.room] || 0;
      card.dataset.count = String(n);
      card.classList.toggle('is-on', n > 0);
      card.querySelector('.ws-count').textContent = String(n);
      card.querySelector('[data-step="-1"]').disabled = n <= 0;
      card.querySelector('[data-step="1"]').disabled = n >= Number(card.dataset.max);
    });
    panel.querySelectorAll('.ws-addon').forEach(function (b) {
      b.setAttribute('aria-pressed', s.add.indexOf(b.dataset.addon) >= 0 ? 'true' : 'false');
    });
    var fit = panel.querySelector('.ws-fit');
    fit.textContent = s.fit_text;
    fit.dataset.fit = s.fit;
    panel.querySelector('[data-cb-sum]').textContent = s.summary;
    panel.querySelector('[data-cb-price]').textContent = s.price;
    panel.querySelector('.ws-choose').disabled = !s.fits;
    panel.dataset.fits = s.fits ? '1' : '0'; // the last answer the server gave
    panel.querySelector('[data-cb-err]').hidden = true;
  }

  // The ledger, the stay cards and the map follow a quote from the server.
  function applyLedger(j) {
    var L = j.ledger;
    pick.flight = L.pick.f; pick.stay = L.pick.h; pick.car = L.pick.c; pick.rooms = L.pick.rooms; pick.add = L.pick.add;
    base = L.url;
    ['flight', 'stay', 'car'].forEach(function (lane) {
      var s = L.slots[lane];
      document.querySelector('[data-slot="' + lane + '"]').textContent = s.name;
      document.querySelector('[data-slot-sub="' + lane + '"]').textContent = s.sub;
      document.querySelector('[data-slot-price="' + lane + '"]').textContent = s.price;
      var lineEl = document.querySelector('[data-line-price="' + lane + '"]');
      lineEl.textContent = s.price;
      lineEl.parentNode.title = s.name;
    });
    document.getElementById('ws-total').textContent = L.total;
    document.getElementById('ws-total-live').textContent = 'Total ' + L.total;
    var chip = document.getElementById('ws-delta');
    chip.textContent = L.delta;
    chip.classList.toggle('fill-mint', L.cheapest);
    chip.classList.toggle('fill-sun-tint', !L.cheapest);
    document.getElementById('ws-book').setAttribute('href', L.book);
    // The picked stay's card shows the price of its rooms and add-ons; the others show their list price.
    document.querySelectorAll('[data-stay-price]').forEach(function (el) {
      el.textContent = el.dataset.stayPrice === pick.stay ? L.slots.stay.price : data.offers[el.dataset.stayPrice].price;
    });
    applyStay(panelOf(pick.stay), j.stay);
    syncUrl();
    paintChoose();
    paintMap(data.map && data.map[pick.stay]);
  }

  var quoteSeq = 0;
  function refresh() {
    var n = ++quoteSeq;
    return getQuote(pickQuery()).then(function (j) { if (n === quoteSeq) applyLedger(j); }).catch(function () {});
  }

  // Pick an offer in a lane. A stay's rooms and add-ons come along only when they are the ones being chosen
  // (cfg); picking another stay starts from its default room.
  function selectPick(lane, id, cfg) {
    if (lane === 'stay') {
      // The stay being left goes back to its default room, like a reload; the new pick's own panel is set by the server's answer.
      if (id !== pick.stay) resetPanel(pick.stay);
      if (cfg) { pick.rooms = cfg.rooms; pick.add = cfg.add; }
      else if (id !== pick.stay) { pick.rooms = null; pick.add = null; }
    }
    pick[lane] = id;
    // A pick made while the lane is tiled is what the split view opens on next.
    Object.keys(SPLIT).forEach(function (n) { if (SPLIT[n] === lane && grid.dataset.expanded !== n) viewing[n] = id; });
    document.querySelectorAll('.ws-offer[data-lane="' + lane + '"]').forEach(function (o) {
      o.setAttribute('aria-pressed', o.dataset.pick === id ? 'true' : 'false');
    });
    paintChoose();
    refresh();
  }

  // ---- split view (F-025) -----------------------------------------------------------------------------------------
  // Flights and Stays expand into a list sidebar and a detail panel; the detail is server-rendered, so this only shows
  // one panel at a time. On a phone the list and the detail are two screens.
  var SPLIT = { flights: 'flight', stays: 'stay' };
  var viewing = {};
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
    setPill(false);
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
    b.addEventListener('click', function () {
      if (b.disabled) return;
      var lane = b.dataset.chooseLane;
      if (lane === 'stay') {
        var p = b.closest('.ws-detail-panel');
        selectPick(lane, b.dataset.choose, { rooms: p.dataset.rooms, add: p.dataset.add });
      } else selectPick(lane, b.dataset.choose);
    });
  });

  // ---- stay editor: rooms, add-ons (each change asks the server for the figures) -------------------------------------
  var panelSeq = {};
  document.querySelectorAll('.ws-detail-panel[data-rooms]').forEach(function (p) {
    p.dataset.fits = p.querySelector('.ws-choose').disabled ? '0' : '1';
  });
  var dirty = {}; // stays whose rooms or add-ons were edited but not chosen
  function editStay(panel) {
    var id = panel.dataset.detail, rooms = '', add = '';
    dirty[id] = true;
    panel.querySelectorAll('.ws-room').forEach(function (c) { if (Number(c.dataset.count) > 0) rooms += c.dataset.room + c.dataset.count; });
    panel.querySelectorAll('.ws-addon[aria-pressed="true"]').forEach(function (b) { add += b.dataset.addon; });
    var n = panelSeq[id] = (panelSeq[id] || 0) + 1;
    // Choose waits for the server's answer, so it can never pick the setup from before this edit.
    panel.querySelector('.ws-choose').disabled = true;
    getQuote('h=' + enc(id) + '&rooms=' + enc(rooms) + '&add=' + enc(add)).then(function (j) {
      if (n !== panelSeq[id]) return;
      applyStay(panel, j.stay);
      paintChoose();
    }).catch(function () { if (n === panelSeq[id]) quoteFailed(panel); });
  }

  // The price did not load: the editor and Choose go back to what the last answer allowed, and a polite line says so until the next success.
  function quoteFailed(panel) {
    if (!panel) return;
    // Show the setup the server last answered for (panel.dataset.rooms / .add), so what is shown is what Choose picks.
    var have = {};
    for (var k = 0; k < panel.dataset.rooms.length; k += 3) have[panel.dataset.rooms.substr(k, 2)] = Number(panel.dataset.rooms.charAt(k + 2));
    panel.querySelectorAll('.ws-room').forEach(function (card) {
      var n = have[card.dataset.room] || 0;
      card.dataset.count = String(n);
      card.classList.toggle('is-on', n > 0);
      card.querySelector('.ws-count').textContent = String(n);
      card.querySelector('[data-step="-1"]').disabled = n <= 0;
      card.querySelector('[data-step="1"]').disabled = n >= Number(card.dataset.max);
    });
    panel.querySelectorAll('.ws-addon').forEach(function (b) {
      b.setAttribute('aria-pressed', panel.dataset.add.indexOf(b.dataset.addon) >= 0 ? 'true' : 'false');
    });
    panel.querySelector('.ws-choose').disabled = panel.dataset.fits !== '1';
    panel.querySelector('[data-cb-err]').hidden = false;
  }

  // Put a stay's editor back to its default room (what a reload shows for a stay that is not picked).
  function resetPanel(id) {
    delete dirty[id];
    var n = panelSeq[id] = (panelSeq[id] || 0) + 1; // ignore answers still on their way
    var panel = panelOf(id);
    if (panel) panel.querySelector('.ws-choose').disabled = true;
    getQuote('h=' + enc(id)).then(function (j) {
      if (n === panelSeq[id]) { applyStay(panel, j.stay); paintChoose(); }
    }).catch(function () { if (n === panelSeq[id]) quoteFailed(panel); });
  }

  // Leaving the split view drops edits that were not chosen, so opening it again (like a reload) shows the picks.
  function discardDrafts() {
    Object.keys(dirty).forEach(function (id) {
      if (id === pick.stay) {
        delete dirty[id];
        panelSeq[id] = (panelSeq[id] || 0) + 1;
        refresh();
      } else resetPanel(id);
    });
  }

  document.querySelectorAll('.ws-detail-panel[data-rooms]').forEach(function (panel) {
    panel.addEventListener('click', function (e) {
      var step = e.target.closest('[data-step]');
      var addon = e.target.closest('.ws-addon');
      if (step && !step.disabled) {
        var card = step.closest('.ws-room');
        var n = Math.max(0, Math.min(Number(card.dataset.max), Number(card.dataset.count) + Number(step.dataset.step)));
        if (n === Number(card.dataset.count)) return;
        card.dataset.count = String(n); // shown at once; the server's answer then confirms it
        card.querySelector('.ws-count').textContent = String(n);
        editStay(panel);
      } else if (addon) {
        addon.setAttribute('aria-pressed', addon.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
        editStay(panel);
      }
    });
  });

  // ---- look around: Photos / Explore the area in 3D ---------------------------------------------------------------------
  function selectTab(look, name, focus) {
    look.querySelectorAll('[role="tab"]').forEach(function (t) {
      var on = t.dataset.tab === name;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
      if (on && focus) t.focus();
    });
    look.querySelectorAll('[role="tabpanel"]').forEach(function (p) { p.hidden = p.dataset.panel !== name; });
    if (name === 'explore') loadExplore(look.querySelector('.ws-explore-slot'));
  }

  // The explorer loads the first time its tab opens (a skeleton, then the map); a failed load tries again on the next open.
  function loadExplore(slot) {
    if (slot.dataset.state === 'loading' || slot.dataset.state === 'ready') return;
    slot.dataset.state = 'loading';
    slot.innerHTML = '<div class="ws-skel skeleton" role="status">Loading the aerial view…</div>';
    var t0 = Date.now(), wait = still.matches ? 0 : 400;
    fetch(slot.dataset.mapSrc).then(function (r) {
      if (!r.ok) throw new Error('explore ' + r.status);
      return r.text();
    }).then(function (html) {
      setTimeout(function () { slot.innerHTML = html; slot.dataset.state = 'ready'; bindExplore(slot); }, Math.max(0, wait - (Date.now() - t0)));
    }).catch(function () {
      slot.dataset.state = 'error';
      slot.innerHTML = '<div class="ws-skel ws-skel-error" role="status">The aerial view did not load. Open the tab again to retry.</div>';
    });
  }

  function bindExplore(slot) {
    var aerial = slot.querySelector('.ws-aerial');
    var spin = 0;
    function select(i, from) {
      slot.querySelectorAll('[data-poi]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.poi === i ? 'true' : 'false'); });
      slot.querySelectorAll('[data-poi-card]').forEach(function (c) { c.hidden = c.dataset.poiCard !== i; });
      aerial.style.setProperty('--tx', from.dataset.tx + '%');
      aerial.style.setProperty('--ty', from.dataset.ty + '%');
    }
    slot.addEventListener('click', function (e) {
      var poi = e.target.closest('[data-poi]');
      if (poi) { select(poi.dataset.poi, poi); return; }
      if (e.target.closest('[data-recenter]')) { select('0', aerial); return; }
      if (e.target.closest('[data-spin]')) { spin = (spin + 30) % 360; aerial.style.setProperty('--spin', spin + 'deg'); }
    });
  }

  document.querySelectorAll('.ws-look').forEach(function (look) {
    var tabs = look.querySelector('[role="tablist"]');
    tabs.addEventListener('click', function (e) {
      var t = e.target.closest('[role="tab"]');
      if (t) selectTab(look, t.dataset.tab, false);
    });
    tabs.addEventListener('keydown', function (e) {
      var keys = { ArrowLeft: -1, ArrowRight: 1, Home: 'first', End: 'last' };
      if (!(e.key in keys)) return;
      var list = [].slice.call(tabs.querySelectorAll('[role="tab"]'));
      var at = list.indexOf(document.activeElement);
      var next = keys[e.key] === 'first' ? 0 : keys[e.key] === 'last' ? list.length - 1 : (at + keys[e.key] + list.length) % list.length;
      e.preventDefault();
      selectTab(look, list[next].dataset.tab, true);
    });
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
    if (grid.dataset.expanded === 'stays' && name !== 'stays') discardDrafts();
    setPill(false);
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
    if (e.key === 'Escape' && popOpen()) { e.preventDefault(); setPop(false, true); return; }
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

  // ---- the ledger line (F-031): total opens a breakdown popover; scrolling a detail down shrinks the line to a pill -------
  var ledger = document.querySelector('.ws-ledger');
  var totalBtn = document.getElementById('ws-total');
  var pop = document.getElementById('ws-pop');
  function popOpen() { return !!pop && !pop.hidden; }
  function setPop(open, moveFocus) {
    if (!pop || popOpen() === open) return;
    pop.hidden = !open;
    totalBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) { setPill(false); if (moveFocus) pop.focus(); }
    else if (moveFocus) totalBtn.focus();
  }
  function setPill(on) {
    if (!ledger || ledger.classList.contains('is-pill') === on) return;
    if (on && popOpen()) setPop(false, false);
    ledger.classList.toggle('is-pill', on);
    // As a pill the first tap only restores the line, so the button says that instead of promising a popover.
    if (on) { totalBtn.setAttribute('aria-label', 'Show cost line'); totalBtn.removeAttribute('aria-haspopup'); }
    else { totalBtn.removeAttribute('aria-label'); totalBtn.setAttribute('aria-haspopup', 'dialog'); }
  }
  if (ledger && pop) {
    totalBtn.addEventListener('click', function () {
      if (ledger.classList.contains('is-pill')) { setPill(false); return; } // tapping the pill restores the line
      setPop(!popOpen(), true);
    });
    // Tapping outside closes it (focus stays where the tap put it); so does moving focus out with Tab.
    document.addEventListener('pointerdown', function (e) { if (popOpen() && !ledger.contains(e.target)) setPop(false, false); });
    ledger.addEventListener('focusout', function (e) {
      if (popOpen() && e.relatedTarget && !ledger.contains(e.relatedTarget)) setPop(false, false);
    });
    // Scrolling the open detail down shrinks the line; scrolling up (or back to the top) restores it.
    // A run in one direction counts once it is a few pixels long, so a smooth scroll's tiny steps still add up.
    var runs = new WeakMap();
    grid.addEventListener('scroll', function (e) {
      var el = e.target;
      if (!el.classList || !el.classList.contains('ws-dscroll') || phone.matches) return;
      var r = runs.get(el) || { last: 0, dir: 0, from: 0 }, now = el.scrollTop;
      runs.set(el, r);
      if (now === r.last) return;
      var dir = now > r.last ? 1 : -1;
      if (dir !== r.dir) { r.dir = dir; r.from = r.last; }
      r.last = now;
      if (now <= 4 || (dir < 0 && r.from - now > 6)) setPill(false);
      else if (dir > 0 && now > 16 && now - r.from > 6) setPill(true);
    }, true);
  }

  var start = grid.dataset.expanded;
  focusPane(start || 'flights', false);
  paintChoose();
})();
