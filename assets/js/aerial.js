/* See it from above (F-284, D-905..D-909; docs/design/flyaround is the prototype). The card in the opened square's hotel (gitaway/pages/aerialview.py) opens a full-screen sheet on a phone and a
   panel on a laptop: a 3D-buildings map (MapLibre over OpenFreeMap, no key), and with a key Google's satellite tiles and photoreal 3D (CesiumJS over Google Photorealistic 3D Tiles), with the
   truth pins the server read from OpenStreetMap (gitaway/aerial.py) drawn on the map and listed beside it.
   Nothing is loaded before the tap: the libraries load on it, from exact versions, and closing the sheet destroys the map and gives its WebGL context back. Satellite and photoreal ask the
   server for the Google key each time a sheet first uses one (POST /plan/matrix/aerial/open), which counts the open per day and says "Back tomorrow" past its cap; the key lives in this
   page's memory only, never in storage. Distances and words come from the server; this file only draws them. Everything the server sends is escaped. */
(function () {
  'use strict';
  var VERSIONS = { maplibre: '4.7.1', cesium: '1.123.0' };
  var HOSTS = { maplibre: 'https://unpkg.com/maplibre-gl@' + VERSIONS.maplibre + '/dist/', cesium: 'https://cdn.jsdelivr.net/npm/cesium@' + VERSIONS.cesium + '/Build/Cesium/' };
  var SRI = { 'maplibre-gl.js': 'sha384-SYKAG6cglRMN0RVvhNeBY0r3FYKNOJtznwA0v7B5Vp9tr31xAHsZC0DqkQ/pZDmj', 'Cesium.js': 'sha384-xAdxnnaIzRit+cIXQWeImuZHfoK0MA0EaxSb8rlO3RaT9NWVqgvICnDMtPUI/aar' };      // the exact files of the pinned versions (checked 16 Nov 2026): a changed file does not run
  var PINS = '/plan/matrix/aerial/pins', OPEN = '/plan/matrix/aerial/open';
  var TILES = { sat: 'https://tile.googleapis.com/v1/2dtiles/{z}/{x}/{y}', session: 'https://tile.googleapis.com/v1/createSession' };
  var TURN_MS = 30000, RESUME_MS = 900, FIT_MS = 1200, FLY_S = 1.5;      // camera moves of the map itself (not the page's motion tokens)
  var DESK = window.matchMedia('(min-width: 64rem)'), REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)');
  var ICONS = {
    flight: '<path d="M10.5 21l1.5-1v-5.5l8 2.5v-2l-8-5V4.5a1.5 1.5 0 0 0-3 0V10l-8 5v2l8-2.5V20l1.5 1z"/>',
    road: '<path d="M5 21L9 3M19 21L15 3M12 5v2M12 11v2M12 17v2"/>',
    water: '<path d="M2 9c2 0 2-1.5 4-1.5S8 9 10 9s2-1.5 4-1.5S16 9 18 9s2-1.5 4-1.5M2 15c2 0 2-1.5 4-1.5s2 1.5 4 1.5 2-1.5 4-1.5 2 1.5 4 1.5 2-1.5 4-1.5"/>',
    shop: '<path d="M3 4h2l2.4 11h10.2L20 8H6.3"/><circle cx="9" cy="19.5" r="1.3"/><circle cx="17" cy="19.5" r="1.3"/>',
    food: '<path d="M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10M17 3c-2 1-3 3.5-3 7h3v11"/>',
    park: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M10 16V8h3a2.5 2.5 0 0 1 0 5h-3"/>',
    bed: '<path d="M3 18V7M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5"/><circle cx="7" cy="11" r="1.6"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>', orbit: '<path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4"/>',
    alert: '<path d="M12 3l9.5 17h-19L12 3zM12 10v4.5M12 17.5v.01"/>'
  };
  var COLOUR = { flight: '#4338CA', road: '#C2410C', water: '#0369A1', shop: '#0F766E', food: '#C92A5E', park: '#8B2FC9' };      // the kinds' colours on the 3D labels (Cesium draws its own text, outside the page's CSS)
  var S = null;      // the open sheet's state; null when closed

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function svg(name) { return '<svg class="av-i" viewBox="0 0 24 24" aria-hidden="true">' + ICONS[name] + '</svg>'; }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function motion() { return window.GA && window.GA.motion; }
  function dark() { return document.documentElement.getAttribute('data-mode') === 'dark'; }

  // ---- lazy libraries: nothing here runs before a tap ----
  var loaded = {};
  function loadScript(src, file) {
    return loaded[src] || (loaded[src] = new Promise(function (ok, no) {
      var s = document.createElement('script');
      s.src = src; s.async = true;
      if (SRI[file]) { s.integrity = SRI[file]; s.crossOrigin = 'anonymous'; }
      s.onload = ok; s.onerror = function () { delete loaded[src]; no(new Error('load ' + file)); };
      document.head.appendChild(s);
    }));
  }
  function loadCss(href) {
    if (loaded[href]) return; loaded[href] = 1;
    var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = href; document.head.appendChild(l);
  }

  // ---- the sheet ----
  function build(card) {
    var keyed = !!card.dataset.keyed;
    var scrim = document.createElement('div'); scrim.className = 'av-scrim';
    var sheet = document.createElement('div'); sheet.className = 'av-sheet'; sheet.setAttribute('role', 'dialog'); sheet.setAttribute('aria-modal', 'true');
    sheet.setAttribute('aria-label', 'See it from above: ' + (card.dataset.hotel || 'the hotel'));
    sheet.innerHTML =
      '<div class="av-stage"><div class="av-map"></div><div class="av-loading"><span class="v2-glass">Loading the view…</span></div>' +
      '<div class="av-msg" hidden></div>' +
      '<div class="av-bar"><button type="button" class="av-round v2-glass av-close" aria-label="Close">' + svg('x') + '</button>' +
      '<div class="av-seg v2-glass" role="group" aria-label="View"><button type="button" data-v="map" aria-pressed="true">Map</button>' +
      (keyed ? '<button type="button" data-v="sat" aria-pressed="false">Satellite</button><button type="button" data-v="photo" aria-pressed="false">Photoreal</button>' : '') + '</div></div>' +
      '<button type="button" class="av-resume v2-glass" hidden>' + svg('orbit') + '<span>Resume orbit</span></button><div class="av-attr"></div></div>' +
      '<section class="av-truth" aria-labelledby="av-title"><div class="av-kk">What the photos don’t show</div><h2 id="av-title"></h2><div class="av-heads"></div>' +
      '<p class="av-src">Looking around the hotel in OpenStreetMap…</p><ul class="av-pins"></ul>' +
      '<p class="av-note">Distances are straight-line from the hotel; walking adds a quarter for real streets at 80 m a minute, driving assumes city speeds plus two minutes to park.</p></section>';
    q('#av-title', sheet).textContent = card.dataset.hotel || '';
    document.body.appendChild(scrim); document.body.appendChild(sheet);
    return { scrim: scrim, sheet: sheet };
  }

  function openFrom(card) {
    if (S) return;
    var parts = build(card);
    S = { card: card, tok: card.dataset.aerial, keyed: !!card.dataset.keyed, view: 'map', engine: null, map: null, viewer: null, truth: null, orbit: false, raf: 0, last: 0, markers: [], ro: null,
          heading: 0, bearing: -20, groundH: 0, pinH: null, gkey: {}, satSession: '', scrim: parts.scrim, sheet: parts.sheet, closing: false, up: true };
    document.body.classList.add('av-open');
    var landed = motion() ? motion().open(S.sheet, card, { scrim: S.scrim, content: q('.av-stage', S.sheet), radius: [20, DESK.matches ? 24 : 0] }) : Promise.resolve();
    q('.av-close', S.sheet).focus({ preventScroll: true });
    truth();
    Promise.resolve(landed).then(function () { if (S && S.up) setView('map'); });
  }

  function close() {
    if (!S || S.closing) return;
    var s = S; s.closing = true; s.up = false;
    var from = document.body.contains(s.card) ? s.card : null;
    var done = function () {
      teardown(s);
      s.sheet.remove(); s.scrim.remove();
      document.body.classList.remove('av-open');
      if (S === s) S = null;
    };
    if (motion()) motion().close(s.sheet, from, { scrim: s.scrim }).then(done); else done();
    if (from) from.focus({ preventScroll: true });
  }

  // ---- the truth pins: drawn from what the server read ----
  function truth() {
    var s = S;
    fetch(PINS + '?id=' + encodeURIComponent(s.tok), { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (j) { if (S === s) paintTruth(j); })
      .catch(function () { if (S === s) paintTruth({ ok: false, message: 'The pins could not be loaded just now. The map is still here.' }); });
  }
  function paintTruth(j) {
    var el = S.sheet;
    if (j.lat != null) S.hotel = { lat: j.lat, lon: j.lon, name: j.name };      // the place is known even when OpenStreetMap did not answer: the map still shows
    if (!j.ok) { q('.av-src', el).textContent = j.message || ''; q('.av-src', el).classList.add('warn'); S.truth = { pins: [] }; return; }
    S.truth = j;
    q('#av-title', el).textContent = j.name;
    var head = j.heads && j.heads[0];
    q('.av-heads', el).innerHTML = '<div class="av-hd' + (head && head.good ? ' good' : '') + '">' + svg(head && head.good ? 'water' : 'alert') + '<div><b>' + (head && head.good ? '' : 'Heads up: ') + esc(j.headline) + '</b>' +
      (head ? '<span>' + esc(head.more) + '</span>' : '') + '</div></div>';
    var src = q('.av-src', el); src.textContent = j.source_text || ''; src.classList.toggle('warn', j.source === 'saved' || !!j.sample);
    q('.av-pins', el).innerHTML = j.pins.map(function (p, i) {
      var has = p.lat != null;
      return '<li><button type="button" class="av-pin' + (has ? '' : ' none') + '" data-i="' + i + '"' + (has ? '' : ' disabled') + '><span class="av-ic av-c-' + esc(p.kind) + '">' + svg(p.kind) + '</span>' +
        '<span><span class="av-nm">' + esc(p.title) + '</span><span class="av-sub">' + esc(p.sub) + '</span></span>' +
        '<span class="av-d num">' + (p.m != null ? esc(p.far) + '<small>' + esc(p.by) + ' · ' + esc(p.dist) + '</small>' : '<small>none</small>') + '</span></button></li>';
    }).join('');
    var line = q('.av-l', S.card); if (line && j.headline) line.textContent = j.headline;      // the card says the heads-up once it is known
    if (S.engine === 'maplibre') drawMarkers();
    if (S.engine === 'cesium') { cesiumPins(); sampleGround(S.viewer); }
  }

  // ---- views ----
  function setView(v) {
    if (!S) return;
    var s = S; s.view = v;
    [].forEach.call(s.sheet.querySelectorAll('.av-seg button'), function (b) { b.setAttribute('aria-pressed', String(b.dataset.v === v)); });
    message('');
    if (v === 'photo') return key('photo').then(function (k) { if (S === s && s.view === 'photo') { teardown(s); return startCesium(k); } }, function () { back(s); });
    if (v === 'sat') return key('sat').then(function (k) { return mapView(s, k); }, function () { back(s); });
    return mapView(s, null);
  }
  function back(s) { if (S === s) { s.view = s.engine === 'cesium' ? 'photo' : 'map'; [].forEach.call(s.sheet.querySelectorAll('.av-seg button'), function (b) { b.setAttribute('aria-pressed', String(b.dataset.v === (s.engine === 'cesium' ? 'photo' : 'map'))); }); } }
  function mapView(s, gkey) {
    if (S !== s) return;
    if (s.engine === 'cesium') teardown(s);
    if (s.engine === 'maplibre' && s.map) { satellite(s, gkey); attribution(); return Promise.resolve(); }
    return startMapLibre(s, gkey);
  }
  function message(html, title) {
    var m = q('.av-msg', S.sheet);
    m.hidden = !html;
    m.innerHTML = html ? '<div class="av-card2"><b>' + esc(title || '') + '</b><p>' + html + '</p></div>' : '';
  }
  // the Google key, asked for once per view per sheet: the server counts the open and may say "Back tomorrow"
  function key(view) {
    var s = S;
    if (s.gkey[view]) return Promise.resolve(s.gkey[view]);
    return fetch(OPEN, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json' }, credentials: 'same-origin',
      body: 'id=' + encodeURIComponent(s.tok) + '&view=' + view })
      .then(function (r) { return r.json().then(function (j) { return { status: r.status, j: j }; }); })
      .then(function (x) {
        if (S !== s) return Promise.reject(new Error('closed'));
        if (x.j && x.j.ok && x.j.key) { s.gkey[view] = x.j.key; return x.j.key; }
        message(esc((x.j && x.j.more) || (x.j && x.j.message) || 'That view is not available right now.'), (x.j && x.j.full) ? x.j.message : 'Not available');
        return Promise.reject(new Error('refused'));
      }, function (e) { if (S === s) message('That view could not be reached. The map is still here.', 'No connection'); return Promise.reject(e); });
  }
  function attribution() {
    var osm = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';
    var ofm = '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> · <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">© OpenMapTiles</a>';
    var g = '<a href="https://www.google.com/intl/en_us/help/terms_maps/" target="_blank" rel="noopener">Imagery © Google</a>';
    var a = S.view === 'photo' ? 'Pins ' + osm : S.view === 'sat' ? g + ' · ' + ofm + ' · ' + osm : ofm + ' · ' + osm;
    q('.av-attr', S.sheet).innerHTML = a;
  }
  function styleUrl() { return 'https://tiles.openfreemap.org/styles/' + (dark() ? 'dark' : 'liberty'); }
  function camera() { var h = S.hotel || { lat: 0, lon: 0 }; return { center: [h.lon, h.lat], zoom: DESK.matches ? 16.4 : 15.9, pitch: 55, bearing: S.bearing }; }

  // ---- the 3D-buildings map ----
  function startMapLibre(s, gkey) {
    q('.av-loading', s.sheet).hidden = false;
    loadCss(HOSTS.maplibre + 'maplibre-gl.css');
    return Promise.all([loadScript(HOSTS.maplibre + 'maplibre-gl.js', 'maplibre-gl.js'), hotelReady(s)]).then(function () {
      if (S !== s || s.engine) return;
      if (!s.hotel) { q('.av-loading', s.sheet).hidden = true; message('This hotel’s place is not known, so there is no map to show.', 'No map'); return; }
      var phone = !DESK.matches, el = document.createElement('div');
      el.className = 'av-canvas'; q('.av-map', s.sheet).appendChild(el);
      var map = new window.maplibregl.Map({ container: el, style: styleUrl(), center: camera().center, zoom: camera().zoom, pitch: 55, bearing: s.bearing, maxPitch: 65, attributionControl: false,
        pixelRatio: Math.min(window.devicePixelRatio || 1, phone ? 1.5 : 2), maxTileCacheSize: phone ? 60 : 120, fadeDuration: 0, antialias: false });
      s.map = map; s.engine = 'maplibre'; s.gSat = gkey; attribution();
      s.ro = new ResizeObserver(function () { map.resize(); }); s.ro.observe(el);
      map.on('style.load', function () { decorate(); satellite(s, s.gSat); });
      map.once('load', function () {
        map.once('render', function () { q('.av-loading', s.sheet).hidden = true; });
        if (!REDUCED.matches) startOrbit(); else q('.av-resume', s.sheet).hidden = false;
      });
      ['dragstart', 'rotatestart', 'pitchstart', 'zoomstart'].forEach(function (t) { map.on(t, function (e) { if (e.originalEvent) stopOrbit(); }); });
      el.addEventListener('pointerdown', function () { stopOrbit(); }, { passive: true });
      el.addEventListener('wheel', function () { stopOrbit(); }, { passive: true });
    }, function () { if (S === s) { q('.av-loading', s.sheet).hidden = true; message('The map could not be loaded. Check your connection and try again.', 'No map'); } });
  }
  // the pins' place comes from the server (the hotel's coordinates are never in the page): wait for them before the first frame
  function hotelReady(s) {
    return new Promise(function (ok) { var n = 0; (function wait() { if (s.hotel || n++ > 100 || S !== s) ok(); else setTimeout(wait, 50); })(); });
  }
  function decorate() {
    var m = S.map, isDark = dark();
    if (m.getLayer('building-3d')) m.removeLayer('building-3d');
    var ls = m.getStyle().layers.filter(function (l) { return l.id.indexOf('av-') !== 0 && l.id !== 'google-sat'; }), last = -1;
    ls.forEach(function (l, i) { if (l.type !== 'symbol') last = i; });
    var firstSymbol = ls[last + 1] && ls[last + 1].id;      // labels stay on top
    if (!m.getLayer('av-3d')) m.addLayer({ id: 'av-3d', type: 'fill-extrusion', source: 'openmaptiles', 'source-layer': 'building', minzoom: 13,
      paint: { 'fill-extrusion-color': isDark ? '#3A3F6B' : '#D9D6F0', 'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 6], 'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0], 'fill-extrusion-opacity': 0.9 } }, firstSymbol);
    if (!m.getSource('av-lines')) m.addSource('av-lines', { type: 'geojson', data: lines() });
    if (!m.getLayer('av-lines')) m.addLayer({ id: 'av-lines', type: 'line', source: 'av-lines', paint: { 'line-color': isDark ? '#9A94FF' : '#372DB0', 'line-width': 2, 'line-dasharray': [2, 2], 'line-opacity': 0.8 } }, firstSymbol);
    drawMarkers();
  }
  function satellite(s, gkey) {
    var m = s.map; if (!m || !m.isStyleLoaded()) { s.gSat = gkey; return; }
    var on = s.view === 'sat' && !!gkey;
    var apply = function (session) {
      if (S !== s || !s.map) return;
      if (on && session && !m.getSource('google-sat')) {
        m.addSource('google-sat', { type: 'raster', tileSize: 256, maxzoom: 21, tiles: [TILES.sat + '?session=' + encodeURIComponent(session) + '&key=' + encodeURIComponent(gkey)] });
        m.addLayer({ id: 'google-sat', type: 'raster', source: 'google-sat' }, m.getLayer('av-3d') ? 'av-3d' : undefined);
      }
      if (m.getLayer('google-sat')) m.setLayoutProperty('google-sat', 'visibility', on ? 'visible' : 'none');
      if (m.getLayer('av-3d')) m.setLayoutProperty('av-3d', 'visibility', on ? 'none' : 'visible');      // the photo already shows the roofs; extruded blocks over it hid the truth
      attribution();
    };
    if (!on || s.satSession || m.getSource('google-sat')) return apply(s.satSession);
    fetch(TILES.session + '?key=' + encodeURIComponent(gkey), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mapType: 'satellite', language: 'en-US', region: 'US' }) })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) { s.satSession = j.session; apply(j.session); })
      .catch(function () { if (S === s) { message('Google’s satellite view did not open with this key. The map is still here.', 'No satellite'); s.view = 'map'; back(s); } });
  }
  function lines() {
    var h = S.hotel, pins = (S.truth && S.truth.pins) || [];
    return { type: 'FeatureCollection', features: h ? pins.filter(function (p) { return p.lat != null; }).map(function (p) { return { type: 'Feature', properties: { kind: p.kind }, geometry: { type: 'LineString', coordinates: [[h.lon, h.lat], [p.lon, p.lat]] } }; }) : [] };
  }
  function drawMarkers() {
    var m = S.map; if (!m || !window.maplibregl || !S.hotel) return;
    S.markers.forEach(function (x) { x.remove(); }); S.markers = [];
    var hk = document.createElement('div'); hk.className = 'av-mk hotel'; hk.innerHTML = svg('bed'); hk.title = S.hotel.name;
    S.markers.push(new window.maplibregl.Marker({ element: hk }).setLngLat([S.hotel.lon, S.hotel.lat]).addTo(m));
    ((S.truth && S.truth.pins) || []).forEach(function (p) {
      if (p.lat == null) return;
      var el = document.createElement('div'); el.className = 'av-mk av-c-' + p.kind; el.dataset.kind = p.kind; el.innerHTML = svg(p.kind); el.title = p.title;
      S.markers.push(new window.maplibregl.Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(m));
    });
    var src = m.getSource('av-lines'); if (src) src.setData(lines());
  }

  // ---- the orbit: one turn in 30 s, a touch takes over ----
  function startOrbit() {
    var s = S; if (!s || s.orbit) return;
    s.orbit = true; s.last = 0; q('.av-resume', s.sheet).hidden = true;
    var step = function (t) {
      if (!s.orbit || S !== s) return;
      if (s.last) {
        var d = (t - s.last) / TURN_MS * 360;
        if (s.engine === 'maplibre' && s.map) s.map.setBearing((s.map.getBearing() + d) % 360);
        if (s.engine === 'cesium' && s.viewer) { s.heading += window.Cesium.Math.toRadians(d); cesiumHome(); }
      }
      s.last = t; s.raf = requestAnimationFrame(step);
    };
    s.raf = requestAnimationFrame(step);
  }
  function stopOrbit(silent) {
    var s = S; if (!s) return;
    if (!s.orbit && !silent) return;
    s.orbit = false; cancelAnimationFrame(s.raf);
    if (!silent && s.engine) q('.av-resume', s.sheet).hidden = false;
  }
  function resume() {
    var s = S; if (!s) return;
    if (s.engine === 'maplibre' && s.map) {
      var c = camera(); c.bearing = s.map.getBearing();
      if (REDUCED.matches) { s.map.jumpTo(c); s.map.setBearing((c.bearing + 45) % 360); return; }      // reduced motion: a step, never a spin
      s.map.easeTo({ center: c.center, zoom: c.zoom, pitch: c.pitch, bearing: c.bearing, duration: RESUME_MS }); s.map.once('moveend', startOrbit);
    } else if (s.engine === 'cesium') { cesiumHome(); if (!REDUCED.matches) startOrbit(); }
  }
  function showPin(i) {
    var s = S, p = s && s.truth && s.truth.pins[i], h = s && s.hotel; if (!p || p.lat == null || !h) return;
    stopOrbit();
    if (s.engine === 'maplibre' && s.map) {
      var b = new window.maplibregl.LngLatBounds([h.lon, h.lat], [h.lon, h.lat]).extend([p.lon, p.lat]);
      s.map.fitBounds(b, { padding: DESK.matches ? 120 : 60, pitch: 50, bearing: s.map.getBearing(), duration: REDUCED.matches ? 0 : FIT_MS, maxZoom: 17 });
      var mk = q('.av-mk[data-kind="' + p.kind + '"]', s.sheet); if (mk) { mk.classList.remove('flash'); void mk.offsetWidth; mk.classList.add('flash'); }
    } else if (s.engine === 'cesium') {
      var C = window.Cesium;
      s.viewer.camera.flyToBoundingSphere(new C.BoundingSphere(C.Cartesian3.fromDegrees((h.lon + p.lon) / 2, (h.lat + p.lat) / 2, s.groundH), p.m * 0.7 + 150),
        { offset: new C.HeadingPitchRange(s.heading, C.Math.toRadians(-45), 0), duration: REDUCED.matches ? 0 : FLY_S });
    }
    if (!DESK.matches) q('.av-stage', s.sheet).scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  // ---- photoreal: CesiumJS over Google Photorealistic 3D Tiles ----
  function startCesium(gkey) {
    var s = S;
    q('.av-loading', s.sheet).hidden = false;
    window.CESIUM_BASE_URL = HOSTS.cesium;
    loadCss(HOSTS.cesium + 'Widgets/widgets.css');
    return Promise.all([loadScript(HOSTS.cesium + 'Cesium.js', 'Cesium.js'), hotelReady(s)]).then(function () {
      if (S !== s || s.view !== 'photo') return;
      if (!s.hotel) { q('.av-loading', s.sheet).hidden = true; message('This hotel’s place is not known, so there is no map to show.', 'No map'); return; }
      var C = window.Cesium, phone = !DESK.matches, el = document.createElement('div');
      el.className = 'av-canvas'; q('.av-map', s.sheet).appendChild(el);
      // no globe under Google's tiles (a low-resolution globe z-fights with the mesh), no imagery layer, no widgets
      var viewer = new C.Viewer(el, { baseLayer: false, baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false, navigationHelpButton: false, animation: false, timeline: false,
        fullscreenButton: false, infoBox: false, selectionIndicator: false, globe: false, useBrowserRecommendedResolution: true, msaaSamples: phone ? 1 : 4 });
      viewer.scene.skyAtmosphere.show = true;
      if (viewer.scene.globe) viewer.scene.globe.show = false;
      s.viewer = viewer; s.engine = 'cesium'; attribution(); s.sheet.classList.add('cesium-on');
      C.GoogleMaps.defaultApiKey = gkey;
      // Cesium's Google defaults (screen-space error 16, a large cache) on a laptop; a phone gets coarser tiles and a smaller cache that still holds the view.
      // Requests are not culled or deferred while the camera moves: the orbit never stops, so with those on, detail never arrived.
      var opts = { cullRequestsWhileMoving: false, foveatedScreenSpaceError: false, showCreditsOnScreen: true };
      if (phone) { opts.maximumScreenSpaceError = 24; opts.cacheBytes = 512 * 1048576; opts.maximumCacheOverflowBytes = 256 * 1048576; }
      return C.createGooglePhotorealistic3DTileset(undefined, opts).then(function (ts) {
        if (S !== s || s.viewer !== viewer) return;
        viewer.scene.primitives.add(ts);
        cesiumPins();
        viewer.scene.postRender.addEventListener(function first() { viewer.scene.postRender.removeEventListener(first); q('.av-loading', s.sheet).hidden = true; });
        var hnd = new C.ScreenSpaceEventHandler(viewer.scene.canvas);
        [C.ScreenSpaceEventType.LEFT_DOWN, C.ScreenSpaceEventType.RIGHT_DOWN, C.ScreenSpaceEventType.WHEEL, C.ScreenSpaceEventType.PINCH_START].forEach(function (t) { hnd.setInputAction(function () { stopOrbit(); }, t); });
        // the ground under the hotel and each pin, read from Google's mesh itself (not the ellipsoid): the camera and the pins move onto it before the orbit starts
        return sampleGround(viewer, true).then(function () { if (S !== s) return; cesiumHome(); if (!REDUCED.matches) startOrbit(); else q('.av-resume', s.sheet).hidden = false; });
      }, function () {
        if (S !== s) return;
        q('.av-loading', s.sheet).hidden = true; teardown(s); s.view = 'map'; back(s);
        message('Google’s 3D tiles did not open with this key. The map is still here.', 'No photoreal');
      });
    }, function () { if (S === s) { q('.av-loading', s.sheet).hidden = true; message('The 3D viewer could not be loaded. Check your connection and try again.', 'No photoreal'); back(s); } });
  }
  function sampleGround(viewer, first) {
    var s = S, C = window.Cesium; if (!s || !viewer || !C || !s.hotel) return Promise.resolve();
    var spots = [[s.hotel.lon, s.hotel.lat]].concat(((s.truth && s.truth.pins) || []).filter(function (p) { return p.lat != null; }).map(function (p) { return [p.lon, p.lat]; }));
    return viewer.scene.sampleHeightMostDetailed(spots.map(function (p) { return C.Cartographic.fromDegrees(p[0], p[1]); })).then(function (got) {
      if (S !== s || s.viewer !== viewer) return;
      var hs = got.map(function (c) { return c && c.height; }).filter(function (x) { return isFinite(x); });
      if (got[0] && isFinite(got[0].height)) s.groundH = Math.min(got[0].height, Math.min.apply(null, hs) + 120);      // a rooftop sample stays near the ground
      s.pinH = got.map(function (c) { return c && isFinite(c.height) ? c.height : null; });
      if (!first && !s.orbit) cesiumHome();
      cesiumPins();
    }, function () { /* the camera keeps the last height; the pins keep theirs */ });
  }
  function cesiumHome() {
    var s = S, C = window.Cesium; if (!s || !s.viewer || !s.hotel) return;
    s.viewer.camera.lookAt(C.Cartesian3.fromDegrees(s.hotel.lon, s.hotel.lat, s.groundH + 25), new C.HeadingPitchRange(s.heading, C.Math.toRadians(-35), DESK.matches ? 620 : 682));
  }
  function cesiumPins() {
    var s = S, C = window.Cesium, v = s && s.viewer; if (!v || !C || !s.hotel) return;
    v.entities.removeAll();
    var ground = function (i) { return s.pinH && s.pinH[i] != null ? s.pinH[i] : s.groundH; };
    // points and labels only, lifted a little over the sampled mesh and never hidden behind it: no polygons, walls or corridors
    var mark = function (lon, lat, z, label, css, size, font) {
      v.entities.add({ position: C.Cartesian3.fromDegrees(lon, lat, z),
        point: { pixelSize: size, color: C.Color.fromCssColorString(css), outlineColor: C.Color.WHITE, outlineWidth: 2, disableDepthTestDistance: Number.POSITIVE_INFINITY },
        label: { text: label, font: font, pixelOffset: new C.Cartesian2(0, -(size + 6)), fillColor: C.Color.WHITE, outlineColor: C.Color.fromCssColorString('#0F1124'), outlineWidth: 4,
          style: C.LabelStyle.FILL_AND_OUTLINE, showBackground: false, disableDepthTestDistance: Number.POSITIVE_INFINITY } });
    };
    mark(s.hotel.lon, s.hotel.lat, ground(0) + 45, s.hotel.name, '#0F1124', 16, '600 15px Inter, sans-serif');
    var i = 1;
    ((s.truth && s.truth.pins) || []).forEach(function (p) {
      if (p.lat == null) return;
      mark(p.lon, p.lat, ground(i++) + 20, p.title + ' · ' + p.dist, COLOUR[p.kind], 12, '500 13px Inter, sans-serif');
    });
  }

  // ---- closing gives everything back: the map, the viewer, their WebGL contexts and every listener ----
  function teardown(s) {
    if (s.orbit || s.raf) { s.orbit = false; cancelAnimationFrame(s.raf); }
    if (s.ro) { s.ro.disconnect(); s.ro = null; }
    s.markers.forEach(function (m) { m.remove(); }); s.markers = [];
    if (s.map) {
      var canvas = s.map.getCanvas(), gl = canvas && (canvas.getContext('webgl2') || canvas.getContext('webgl'));
      s.map.remove(); if (gl) { var x = gl.getExtension('WEBGL_lose_context'); if (x) x.loseContext(); }
      s.map = null;
    }
    if (s.viewer) {
      var g = s.viewer.scene.context._gl;
      s.viewer.destroy(); if (g) { var y = g.getExtension('WEBGL_lose_context'); if (y) y.loseContext(); }
      s.viewer = null;
    }
    s.engine = null; s.sheet.classList.remove('cesium-on');
    var box = q('.av-map', s.sheet); if (box) box.textContent = '';
    var r = q('.av-resume', s.sheet); if (r) r.hidden = true;
  }

  // ---- wiring: one delegated listener for the card (it arrives inside the hotel's fragment, after the page loaded) and for the open sheet ----
  document.addEventListener('click', function (e) {
    var card = e.target.closest && e.target.closest('[data-aerial]');
    if (card && !S) { openFrom(card); return; }
    if (!S) return;
    if (e.target.closest('.av-close') || e.target === S.scrim) { close(); return; }
    var v = e.target.closest('.av-seg button'); if (v) { setView(v.dataset.v); return; }
    var pin = e.target.closest('.av-pin'); if (pin) { showPin(+pin.dataset.i); return; }
    if (e.target.closest('.av-resume')) resume();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && S) { e.stopImmediatePropagation(); close(); } }, true);
})();
