/* Direction 2's map: a real, tilted map. MapLibre GL JS 5.24 (BSD-3, about 275 KB gzip, loaded only where the map is)
   drawing OpenFreeMap's free vector tiles (no key, no limits; © OpenMapTiles © OpenStreetMap) restyled to the grey canvas,
   with 3D terrain and hillshade from AWS Terrain Tiles (free). The route is OSRM's line; pins and drive times are DOM
   markers in the shared label style. Offline or without WebGL it shows a still of the live map, labelled as such. */
(function () {
  const G = window.GEO;
  const { I } = window.ICON;
  const CDN = 'https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/dist/';
  // 3D terrain is one line (?terrain=1.3 turns it on), but with it on, DOM markers drift above the draped route in 5.24;
  // the shipping build would draw pins as a symbol layer (which drapes correctly). Off by default: tilt + hillshade.
  const TERRAIN = +(new URLSearchParams(location.search).get('terrain') ?? 0);
  let loading = null;
  function load() {
    if (window.maplibregl) return Promise.resolve();
    if (loading) return loading;
    loading = new Promise((ok, no) => {
      const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = CDN + 'maplibre-gl.css'; document.head.appendChild(css);
      const s = document.createElement('script'); s.src = CDN + 'maplibre-gl.js'; s.onload = ok; s.onerror = no; document.head.appendChild(s);
      setTimeout(() => no(new Error('timeout')), 9000);
    });
    return loading;
  }
  // the hillshade reads elevation only up to zoom 10 and stretches it: soft relief for about a tenth of the bytes
  const DEM = { type: 'raster-dem', tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'], encoding: 'terrarium', tileSize: 256, maxzoom: 10, attribution: 'Elevation: AWS Terrain Tiles' };
  const PAL = {
    light: { bg: '#EDEDF0', water: '#9CC3EA', land: '#F3F3F5', park: '#E3EBE2', road: '#FFFFFF', roadCase: '#D0D0D8', label: '#4A4A52', route: '#0B0B0D', routeCase: '#FFFFFF', shade: '#5C6070', hl: '#FFFFFF' },
    dark: { bg: '#121214', water: '#173A60', land: '#18181B', park: '#17201A', road: '#3A3A42', roadCase: '#0B0B0D', label: '#C9C9D1', route: '#F5F5F7', routeCase: '#000000', shade: '#000000', hl: '#6E7590' },
  };
  async function style(mode) {
    const p = PAL[mode];
    const st = await (await fetch(`https://tiles.openfreemap.org/styles/${mode === 'dark' ? 'dark' : 'positron'}`)).json();
    st.layers = st.layers.filter((l) => !/poi|housenumber|aerialway|transit|aeroway_runway|building/i.test(l.id));
    for (const l of st.layers) {
      const pt = l.paint = l.paint || {};
      delete pt['fill-pattern'];
      if (l.type === 'background') pt['background-color'] = p.bg;
      else if (l.type === 'fill' && /water/.test(l.id)) pt['fill-color'] = p.water;
      else if (l.type === 'fill' && /park|wood|forest|landcover|grass/.test(l.id)) { pt['fill-color'] = p.park; pt['fill-opacity'] = .6; }
      else if (l.type === 'line' && /waterway/.test(l.id)) pt['line-color'] = p.water;
      else if (l.type === 'symbol') { pt['text-color'] = p.label; pt['text-halo-color'] = p.bg; }
    }
    st.sources.dem2 = DEM;
    if (TERRAIN) st.sources.dem = { ...DEM, maxzoom: 12 };
    const firstSym = st.layers.findIndex((l) => l.type === 'symbol');
    st.layers.splice(firstSym, 0, { id: 'hills', type: 'hillshade', source: 'dem2', paint: { 'hillshade-shadow-color': p.shade, 'hillshade-highlight-color': p.hl, 'hillshade-exaggeration': .45, 'hillshade-accent-color': p.shade } });
    if (TERRAIN) st.terrain = { source: 'dem', exaggeration: TERRAIN };
    return st;
  }
  const geo = (pts) => ({ type: 'Feature', geometry: { type: 'LineString', coordinates: pts }, properties: {} });

  function mount(el, opts = {}) {
    const mode = opts.mode || 'light', p = PAL[mode], calm = !!opts.calm;
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    let map = null, markers = [], drawRaf = 0, pending = null, dead = false;
    const api = { setDay(a) { pending = a; if (map && map.loaded()) apply(a, true); }, map: () => map, fallback: false };
    function fallback(why) {
      if (dead) return; dead = true; api.fallback = true;
      el.innerHTML = `<img class="ml-still" src="img/map-still-${mode}.webp" alt="A still of the live map: the day’s route from the cabin"><span class="ml-off">${I('layers')}Offline: a still of the live map</span>`;
      opts.onReady && opts.onReady(api);
    }
    function marker(html, lngLat, anchor = 'bottom') {
      const d = document.createElement('div'); d.className = 'mlm'; d.innerHTML = html;
      const m = new maplibregl.Marker({ element: d, anchor }).setLngLat(lngLat).addTo(map); markers.push(m); return m;
    }
    function apply(a, animate) {
      markers.forEach((m) => m.remove()); markers = [];
      cancelAnimationFrame(drawRaf);
      const src = map.getSource('route');
      const pts = a.pts || [];
      if (pts.length && animate && !reduced) {
        let t0 = performance.now(); const dur = calm ? 700 : 1100;
        const step = (now) => { const t = Math.min(1, (now - t0) / dur), n = Math.max(2, Math.round(pts.length * t)); src.setData(geo(pts.slice(0, n))); if (t < 1) drawRaf = requestAnimationFrame(step); };
        drawRaf = requestAnimationFrame(step);
      } else src.setData(pts.length ? geo(pts) : geo([[0, 0], [0, 0]]));
      for (const l of a.labels || []) marker(l.html, l.at, l.anchor);
      const b = new maplibregl.LngLatBounds(); (a.frame || pts).forEach((q) => b.extend(q));
      const pad = opts.padding || { top: 80, bottom: 40, left: 50, right: 50 };
      const cam = map.cameraForBounds(b, { padding: pad, bearing: a.bearing ?? -18, pitch: a.pitch ?? 52 });
      const target = { center: cam.center, zoom: Math.min(cam.zoom, a.maxZoom || 12.6), bearing: a.bearing ?? -18, pitch: a.pitch ?? 52 };
      if (!animate || reduced) map.jumpTo(target); else map.flyTo({ ...target, duration: calm ? 1000 : 1700, curve: 1.25, essential: true });
    }
    load().then(async () => {
      if (dead) return;
      let st;
      try { st = await style(mode); } catch (e) { return fallback(e); }
      map = new maplibregl.Map({ container: el, style: st, center: [-119.98, 38.94], zoom: 10.5, pitch: 52, bearing: -18, attributionControl: { compact: true }, maxPitch: 75, fadeDuration: 0, canvasContextAttributes: { preserveDrawingBuffer: true } });
      map.on('error', (e) => { if (!map.loaded()) console.warn('map', e.error && e.error.message); });
      map.on('load', () => {
        map.addSource('route', { type: 'geojson', data: geo([[0, 0], [0, 0]]), lineMetrics: true });
        map.addLayer({ id: 'route-case', type: 'line', source: 'route', paint: { 'line-color': p.routeCase, 'line-width': 10 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
        map.addLayer({ id: 'route', type: 'line', source: 'route', paint: { 'line-color': p.route, 'line-width': 5.5 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
        if (pending) apply(pending, false);
        map.once('idle', () => opts.onReady && opts.onReady(api));
      });
    }).catch(fallback);
    api.setDay = (a) => { pending = a; if (map && map.loaded() && map.getSource('route')) apply(a, true); };
    return api;
  }
  window.MapL = { mount };
})();
