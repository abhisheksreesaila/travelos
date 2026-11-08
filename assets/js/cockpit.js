// F-201 · the trip cockpit's page script (gitaway/pages/cockpit.py draws everything; this only makes it live).
// - Every day's sky is a living canvas (wx.js). The paper map (paper.js) is drawn from the page's own data (#ck-data) and the trip's geo pack, so it works offline
//   once loaded; while the pack is still being built it asks /trip/cockpit/map again and fills in the relief when it is ready.
// - A day stub is a link to ?day=N. A tap opens that day's ticket in place and re-flies the map: on the desktop the open stub moves along the line, on a phone the
//   ticket at the top shows that day. It grows out of the stub that was tapped on a phone (GA.motion.open) and is the calm fade on a desktop (GA.motion.calm());
//   under reduced motion it is a short fade. The address follows (?day=N), without a new history entry.
// - "Open map" loads MapLibre and OpenFreeMap's street map only when tapped, in a sheet over the page (it needs a connection; the paper map does not).
// - The map's water and relief follow the page: dark when the page's own card is dark (F-200's dark mode, or the system's).
(function () {
  var root = document.getElementById('main');
  var dataEl = document.getElementById('ck-data');
  if (!root || !root.classList.contains('ck') || !dataEl || !window.GA) return;
  var GA = window.GA, MO = GA.motion;
  var data = JSON.parse(dataEl.textContent);
  var deskQ = window.matchMedia('(min-width: 1020px) and (not (display-mode: standalone))');
  var reducedQ = window.matchMedia('(prefers-reduced-motion: reduce)');
  var open = +root.dataset.open || 0;
  var state = { day: open };
  // MapLibre GL JS 5.24.0 (BSD-3), this site's own copy (no CDN sees anyone), pinned by the hash of those exact files: a changed copy is refused by the browser
  var libre = { base: '/assets/vendor/maplibre-gl-5.24.0/', js: 'sha384-5+cfbwT0iiub6VsQAdn6yz16nr6sDiQoHx6tm4O8OVYXHYOxcffFmCJBL0dgdvGp',
    css: 'sha384-uTttxo/aOKbdE5RlD/SPzSDoDmNvGlUYPjONi2MN/b7c9HPSvW07OIuyP7uL6jxK' };
  var ck = window.GA.cockpit = { state: state, libre: libre };

  // ---- the skies ----
  Array.prototype.forEach.call(document.querySelectorAll('.ck-sky[data-wx]'), function (el, k) {
    var cv = el.querySelector('canvas');
    if (!cv || !GA.wx) return;
    var wide = el.classList.contains('ck-sky-wide');
    GA.wx.mount(cv, { host: el, wx: JSON.parse(el.dataset.wx), seed: 30 + k, scale: wide ? 1 : 0.72, sunX: wide ? 54 : 30, sunY: wide ? 46 : 30 });
  });

  // ---- the paper map ----
  var paperEl = document.getElementById('ck-paper');
  function mapOpts() {
    return deskQ.matches ? { tilt: 44, fitW: 0.62, fitH: 0.5, cy: 0.6 } : { tilt: 42, fitW: 0.5, fitH: 0.46, cy: 0.6, maxZoom: 1.7, minor: true, pillAt: 0.64 };
  }
  var map = null;
  function isDark() {
    var probe = document.createElement('span');
    probe.style.cssText = 'position:absolute;visibility:hidden;background:var(--card)';
    root.appendChild(probe);
    var m = /rgba?\(([\d.]+)[, ]+([\d.]+)[, ]+([\d.]+)/.exec(getComputedStyle(probe).backgroundColor || '');
    probe.remove();
    if (!m) return false;
    var lum = (0.2126 * m[1] + 0.7152 * m[2] + 0.0722 * m[3]) / 255;
    return lum < 0.4;
  }
  function startMap(shapes) {
    if (!paperEl || !GA.paper || !data.box) return;
    var o = mapOpts();
    o.shapes = shapes || null;
    map = GA.paper.mount(paperEl, data, o);
    map.setDark(isDark());
    map.setDay(state.day, { instant: true });
    ck.map = map;
    paperEl.dataset.ready = '1';
  }
  function loadShapes() {
    if (!data.pack) return Promise.resolve(null);
    return fetch(data.pack.shapes, { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  loadShapes().then(startMap);
  function followTheme() { if (map) map.setDark(isDark()); }
  if (window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', followTheme);
  new MutationObserver(followTheme).observe(document.documentElement, { attributes: true });

  // while the map waits for a pack or for its first place, ask again now and then: the relief, the shapes and each day's stops and drive come in without a reload
  var asked = 0, every = window.__ckPollMs || 5000;      // (a test asks quicker)
  function showOpenMap() { var b = document.getElementById('ck-open-map'); if (b && data.box) b.hidden = false; }
  function poll() {
    if ((data.state !== 'building' && data.state !== 'none') || asked > 36) return;
    asked++;
    setTimeout(function () {
      fetch('/trip/cockpit/map', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (m) {
        if (!m || !m.state) return poll();
        var placed = !data.box && m.box, packed = m.state === 'ready' && m.pack && (!data.pack || data.pack.key !== m.pack.key);
        if (m.days) data.days = m.days;
        if (m.box) { data.box = m.box; data.km = m.km; }
        data.state = m.state;
        if (m.pack) data.pack = m.pack;
        if (packed || placed) {
          var note = document.getElementById('ck-map-note');
          if (note && packed) note.remove();
          loadShapes().then(function (shapes) { data.shapes = shapes; if (map) { map.setPack(data); map.setDark(isDark()); } else startMap(shapes); });
          if (paperEl) paperEl.dataset.state = m.state;
        } else if (map && m.days) map.setPack(data);
        showOpenMap();
        if (m.state === 'building' || m.state === 'none') poll();
      }).catch(poll);
    }, every);
  }
  poll();

  // ---- a tap on a day ----
  function stubs() { return Array.prototype.slice.call(root.querySelectorAll('.ck-stub')); }
  function select(i, from) {
    if (i === state.day) return;
    state.day = i;
    stubs().forEach(function (s) {
      var on = +s.dataset.day === i, hit = s.querySelector('.ck-hit');
      s.classList.toggle('is-open', on);
      if (hit) { if (on) hit.setAttribute('aria-current', 'true'); else hit.removeAttribute('aria-current'); }
    });
    var stub = document.getElementById('ck-stub-' + i);
    if (deskQ.matches) {
      var body = stub && stub.querySelector('.ck-open');
      if (body) { if (reducedQ.matches) MO.fade(body); else MO.open(body, from); }      // the calm fade (GA.motion.calm() on a desktop)
      if (stub && stub.scrollIntoView && root.querySelector('.ck-week.is-long')) stub.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    } else {
      showTicket(i, from);
    }
    if (map) map.setDay(i);
    var hitLink = stub && stub.querySelector('.ck-hit');
    if (hitLink && window.history && history.replaceState) history.replaceState(history.state, '', hitLink.getAttribute('href'));
    root.dataset.open = String(i);
  }
  function showTicket(i, from) {
    var tk = document.getElementById('ck-ticket');
    if (!tk) return;
    var panel = null;
    Array.prototype.forEach.call(tk.querySelectorAll('.ck-tk'), function (p) { var on = +p.dataset.day === i; p.hidden = !on; if (on) panel = p; });
    if (!panel) return;
    tk.dataset.day = String(i);
    tk.classList.toggle('is-today', root.dataset.today === String(i));
    var sky = tk.querySelector('.ck-sky');
    if (sky) {
      ['.ck-temp', '.ck-word'].forEach(function (sel, k) {      // the numbers cross-fade in place (a short fade on the --motion-desk token); they never bounce
        var el = sky.querySelector(sel);
        el.textContent = k ? panel.dataset.word : panel.dataset.temp;
        if (!reducedQ.matches) MO.run(el, [{ opacity: 0 }, { opacity: 1 }], { t: 'desk' });
      });
      var src = sky.querySelector('.ck-src');
      if (src) src.textContent = panel.dataset.src;
      sky.dataset.wx = panel.dataset.wx;
      sky.setAttribute('aria-label', panel.dataset.word + ', high ' + panel.dataset.temp);
      var cv = sky.querySelector('canvas');
      if (cv && cv.__wx) cv.__wx.set(JSON.parse(panel.dataset.wx));
    }
    var top = tk.getBoundingClientRect().top;
    if (top < 0) tk.scrollIntoView({ block: 'start', behavior: reducedQ.matches ? 'auto' : 'smooth' });
    if (reducedQ.matches) MO.fade(panel); else MO.open(panel, top < 0 ? null : from);       // it grows out of the stub that was tapped (or rises in place when the page scrolls up to it)
  }
  root.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('.ck-hit[data-day]');
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
    e.preventDefault();
    select(+a.dataset.day, a.closest('.ck-stub'));
  });

  // ---- Open map: the street map, only when asked ----
  var sheet = null, street = null, loading = null;
  function loadLibre() {
    if (window.maplibregl) return Promise.resolve();
    if (loading) return loading;
    loading = new Promise(function (ok, no) {
      var css = document.createElement('link');
      css.rel = 'stylesheet'; css.href = libre.base + 'maplibre-gl.css';
      if (libre.css) css.integrity = libre.css;
      document.head.appendChild(css);
      var s = document.createElement('script');
      s.src = libre.base + 'maplibre-gl.js'; s.id = 'ck-libre';
      if (libre.js) s.integrity = libre.js;
      s.onload = ok; s.onerror = function () { loading = null; s.remove(); no(new Error('offline')); };
      document.head.appendChild(s);
    });
    return loading;
  }
  function buildSheet() {
    var el = document.createElement('div');
    el.className = 'ck-sheet'; el.id = 'ck-sheet'; el.hidden = true;
    el.innerHTML = '<div class="ck-scrim" data-close></div><div class="ck-sheet-box" role="dialog" aria-modal="true" aria-labelledby="ck-sheet-t">' +
      '<div class="ck-sheet-h"><b id="ck-sheet-t">Street map</b><button type="button" class="ck-x" data-close aria-label="Close the street map">' + ((data.icons || {}).x || '×') + '</button></div>' +
      '<div class="ck-street" id="ck-street"><p class="ck-street-msg" id="ck-street-msg">Loading the street map…</p></div></div>';
    el.addEventListener('click', function (e) { if (e.target.closest('[data-close]')) closeSheet(); });
    document.body.appendChild(el);
    return el;
  }
  var opener = null;
  function openSheet(btn) {
    if (!sheet) sheet = buildSheet();
    opener = btn;
    sheet.hidden = false;
    document.documentElement.classList.add('ck-sheet-open');
    var box = sheet.querySelector('.ck-sheet-box');
    if (!reducedQ.matches) MO.open(box, btn, { scrim: sheet.querySelector('.ck-scrim') });
    sheet.querySelector('.ck-x').focus();
    var msg = document.getElementById('ck-street-msg');
    loadLibre().then(function () { drawStreet(); }).catch(function () {
      if (msg) { msg.hidden = false; msg.textContent = 'The street map needs a connection. The paper map works offline.'; }
    });
  }
  function closeSheet() {
    if (!sheet || sheet.hidden) return;
    var box = sheet.querySelector('.ck-sheet-box');
    var done = function () { sheet.hidden = true; document.documentElement.classList.remove('ck-sheet-open'); if (street) { street.remove(); street = null; } if (opener) opener.focus(); };
    if (reducedQ.matches) done(); else MO.close(box, opener, { scrim: sheet.querySelector('.ck-scrim') }).then(done);
  }
  function drawStreet() {
    var msg = document.getElementById('ck-street-msg');
    var d = data.days[state.day] || { stops: [], route: null };
    var pts = (d.route || []).slice();
    d.stops.forEach(function (s) { pts.push([s.lon, s.lat]); });
    if (!pts.length && data.box) pts = [[data.box[0], data.box[1]], [data.box[2], data.box[3]]];
    var lons = pts.map(function (p) { return p[0]; }), lats = pts.map(function (p) { return p[1]; });
    var bounds = [[Math.min.apply(null, lons), Math.min.apply(null, lats)], [Math.max.apply(null, lons), Math.max.apply(null, lats)]];
    try {
      street = new window.maplibregl.Map({ container: 'ck-street', style: 'https://tiles.openfreemap.org/styles/' + (isDark() ? 'dark' : 'positron'), bounds: bounds,
        fitBoundsOptions: { padding: 56, maxZoom: 15 }, attributionControl: { compact: true }, dragRotate: false });
    } catch (err) {
      if (msg) msg.textContent = 'The street map could not start on this device. The paper map is above.';
      return;
    }
    if (window.maplibregl.NavigationControl) street.addControl(new window.maplibregl.NavigationControl({ showCompass: false }), 'top-right');      // + and - for a finger or a mouse
    street.on('load', function () {
      if (msg) msg.hidden = true;
      if (d.route) {
        street.addSource('ck-route', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: d.route } } });
        street.addLayer({ id: 'ck-route-c', type: 'line', source: 'ck-route', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': isDark() ? '#000000' : '#FFFFFF', 'line-width': 9 } });
        street.addLayer({ id: 'ck-route', type: 'line', source: 'ck-route', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': isDark() ? '#F5F5F7' : '#0B0B0D', 'line-width': 5 } });
      }
      d.stops.forEach(function (s) {
        var pin = document.createElement('span');
        pin.className = 'pp-lbl ck-k-' + s.kind;
        pin.style.position = 'relative';
        pin.style.transform = 'none';
        pin.textContent = s.label + (s.time ? ' · ' + s.time : '');
        new window.maplibregl.Marker({ element: pin, anchor: 'bottom' }).setLngLat([s.lon, s.lat]).addTo(street);
      });
    });
    street.on('error', function () { if (msg && !street.loaded()) { msg.hidden = false; msg.textContent = 'The street map needs a connection. The paper map works offline.'; } });
  }
  var openBtn = document.getElementById('ck-open-map');
  if (openBtn) openBtn.addEventListener('click', function () { openSheet(openBtn); });
  document.addEventListener('keydown', function (e) {
    if (!sheet || sheet.hidden) return;
    if (e.key === 'Escape') { e.preventDefault(); closeSheet(); return; }
    if (e.key !== 'Tab') return;      // the focus stays inside the dialog (aria-modal): Tab and Shift+Tab go round it
    var stops = Array.prototype.filter.call(sheet.querySelectorAll('button, a[href], [tabindex]:not([tabindex="-1"])'), function (n) { return n.getClientRects().length; });
    if (!stops.length) return;
    var first = stops[0], last = stops[stops.length - 1], at = document.activeElement;
    if (e.shiftKey && (at === first || !sheet.contains(at))) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (at === last || !sheet.contains(at))) { e.preventDefault(); first.focus(); }
  });
  ck.select = select;
})();
