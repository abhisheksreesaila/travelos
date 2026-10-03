/* The Map tab (F-068): Leaflet draws the day's stops from the JSON in #mp-data; tapping a pin or a row opens the bottom sheet.
   Without Leaflet or tiles the list under the map still opens the same sheet's facts in the page (the pins are progressive enhancement). */
(function () {
  var dataEl = document.getElementById('mp-data');
  if (!dataEl) return;
  var data = {};
  try { data = JSON.parse(dataEl.textContent); } catch (e) { return; }
  var stops = data.stops || [];
  var $ = function (id) { return document.getElementById(id); };
  var sheet = $('mp-sheet'), mapEl = $('mp-map');
  var map = null, markers = {}, current = null;

  // Places still being found in the background: look again a few times, then stop.
  if (data.pending > 0) {
    var tries = 0;
    try { tries = parseInt(sessionStorage.getItem('mp-tries') || '0', 10); } catch (e) {}
    if (tries < 4) {
      try { sessionStorage.setItem('mp-tries', String(tries + 1)); } catch (e) {}
      setTimeout(function () { location.reload(); }, 5000);
    }
  } else {
    try { sessionStorage.removeItem('mp-tries'); } catch (e) {}
  }

  function byNumber(n) { return stops.filter(function (s) { return s.n === n; })[0]; }

  function show(n) {
    var s = byNumber(n);
    if (!s || !sheet) return;
    current = n;
    $('mp-s-n').textContent = String(s.n);
    $('mp-s-name').textContent = s.title;
    $('mp-s-addr').textContent = s.addr;
    $('mp-s-when').textContent = s.when;
    var drive = $('mp-s-drive');
    drive.hidden = !s.drive;
    drive.textContent = s.drive ? s.drive + ' min from ' + (s.frm || 'the stop before') : '';
    $('mp-s-dir').href = s.dir;
    $('mp-s-uber').href = s.uber;
    var tel = $('mp-s-tel');
    tel.hidden = !s.tel;
    if (s.tel) { tel.href = 'tel:' + s.tel.replace(/[^+\d]/g, ''); tel.setAttribute('aria-label', 'Call ' + s.title); }
    sheet.hidden = false;
    Object.keys(markers).forEach(function (k) { markers[k].getElement().classList.toggle('is-sel', Number(k) === n); });
    document.querySelectorAll('.mp-li[data-stop]').forEach(function (b) { b.classList.toggle('is-sel', Number(b.dataset.stop) === n); });
    if (map) {
      var ll = [s.lat, s.lon];
      var h = sheet.offsetHeight;
      map.panTo(ll, { animate: false });
      map.panBy([0, h / 2], { animate: false }); // the pin sits in the part of the map the sheet leaves free
    }
  }

  function hide() {
    if (!sheet) return;
    sheet.hidden = true;
    current = null;
    Object.keys(markers).forEach(function (k) { markers[k].getElement().classList.remove('is-sel'); });
    document.querySelectorAll('.mp-li.is-sel').forEach(function (b) { b.classList.remove('is-sel'); });
  }

  document.querySelectorAll('.mp-li[data-stop]').forEach(function (b) {
    b.addEventListener('click', function () {
      show(Number(b.dataset.stop));
      if (mapEl) mapEl.scrollIntoView({ block: 'nearest' });
    });
  });
  if ($('mp-close')) $('mp-close').addEventListener('click', hide);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && current !== null) hide(); });

  if (!mapEl || !window.L || !stops.length) return;
  var root = document.documentElement;
  var rem = parseFloat(getComputedStyle(root).fontSize) || 16;
  var css = function (name) { return getComputedStyle(root).getPropertyValue(name).trim() || '#FF7352'; };
  var size = Math.round(2.75 * rem);

  map = L.map(mapEl, { zoomControl: true, attributionControl: true, scrollWheelZoom: false, tap: true });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(map);

  var bounds = [];
  stops.forEach(function (s) {
    var ll = [s.lat, s.lon];
    bounds.push(ll);
    var m = L.marker(ll, {
      icon: L.divIcon({ className: 'mp-pin-wrap', html: '<span class="mp-pin">' + s.n + '</span>', iconSize: [size, size], iconAnchor: [size / 2, size / 2] }),
      keyboard: true, title: 'Stop ' + s.n + ', ' + s.title, alt: 'Stop ' + s.n + ', ' + s.title, riseOnHover: true
    }).addTo(map);
    m.on('click', function () { show(s.n); });
    m.getElement().setAttribute('data-stop', String(s.n));
    markers[s.n] = m;
  });

  var line = null;
  if (data.route && data.route.coordinates && data.route.coordinates.length > 1) {
    line = data.route.coordinates.map(function (c) { return [c[1], c[0]]; });
    L.polyline(line, { color: css('--card'), weight: 9, opacity: 0.9, lineCap: 'round', lineJoin: 'round', interactive: false }).addTo(map);
    L.polyline(line, { color: css('--coral'), weight: 5, lineCap: 'round', lineJoin: 'round', interactive: false, className: 'mp-route' }).addTo(map);
    bounds = bounds.concat(line);
  } else if (stops.length > 1) { // no road route known: a dashed straight line says "in this order"
    L.polyline(stops.map(function (s) { return [s.lat, s.lon]; }), { color: css('--coral'), weight: 4, dashArray: '8 8', interactive: false, className: 'mp-route mp-route-straight' }).addTo(map);
  }
  if (bounds.length > 1) map.fitBounds(bounds, { padding: [size, size], maxZoom: 16 });
  else map.setView(bounds[0], 15);

  mapEl.dataset.ready = '1';
})();
