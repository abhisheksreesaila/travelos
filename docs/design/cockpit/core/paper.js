/* Direction 3's map: a paper pop-up map. No map library and no tiles at run time (about 3 KB of script, gzip):
   the relief is one image per trip region drawn from free elevation tiles, the lakes and roads are OpenStreetMap shapes
   (simplified to about 50 KB), the route is OSRM's line. The sheet is tilted with a CSS 3D transform and the place labels
   stand up from it like a pop-up book. Tapping a day re-flies the sheet: phone on a spring, desktop on a calm ease. */
(function () {
  const G = window.GEO, D = window.DEM;
  const [W0, S0, E0, N0] = G.bbox;
  const PW = 1000, PH = Math.round(1000 * D.km[1] / D.km[0]);
  const X = (lon) => (lon - W0) / (E0 - W0) * PW, Y = (lat) => (N0 - lat) / (N0 - S0) * PH;
  const pd = (pts, close) => pts.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join('') + (close ? 'Z' : '');
  const { I } = window.ICON;
  const { DAYS, LANES } = window.TRIP;
  const STOPI = { rno: ['plane', 'flight'], cabin: ['cabin', 'stay'], grocery: ['cart', 'food'], heavenly: ['ski', 'tix'], taylor: ['snowshoe', 'tix'], zephyr: ['snowmobile', 'tix'], emerald: ['see', 'see'], gondola: ['ticket', 'tix'] };
  const TIMES = { 0: { rno: '1:47 PM', grocery: '4:05', cabin: '4:30' }, 1: { heavenly: '8:45' }, 2: { taylor: '10:00' }, 3: { zephyr: '11:00' }, 4: { heavenly: '8:45', emerald: '4:00' }, 5: { gondola: '11:00' }, 6: { cabin: 'all day' }, 7: { cabin: '10:00', rno: '1:30 PM' } };
  const SHORT = { rno: 'Reno airport', cabin: 'Cabin', grocery: 'Groceries', heavenly: 'Heavenly', taylor: 'Taylor Creek', zephyr: 'Zephyr Cove', emerald: 'Emerald Bay', gondola: 'Gondola' };
  const TOWNS = ['Reno', 'Carson City', 'Minden', 'Tahoe City', 'Incline Village', 'Kings Beach', 'Truckee', 'Glenbrook'];

  function svg(mode) {
    const lakes = Object.entries(G.lakes).map(([k, rings]) => rings.map((r) => `<path class="pp-lake" d="${pd(r, true)}"/>`).join('')).join('');
    const roads = G.roads.map((r) => pd(r.pts)).join('');
    const towns = G.towns.filter((t) => TOWNS.includes(t.name)).map((t) => `<text class="pp-town" x="${X(t.lon).toFixed(1)}" y="${Y(t.lat).toFixed(1)}">${t.name}</text>`).join('');
    const folds = [PW / 3, PW * 2 / 3].map((x) => `<line x1="${x}" y1="0" x2="${x}" y2="${PH}"/>`).join('') + `<line x1="0" y1="${PH / 2}" x2="${PW}" y2="${PH / 2}"/>`;
    const st = G.stateline;
    return `<svg class="pp-svg" viewBox="0 0 ${PW} ${PH}" width="${PW}" height="${PH}" aria-hidden="true">
      <image href="img/relief-${mode}.webp" x="0" y="0" width="${PW}" height="${PH}" preserveAspectRatio="none"/>
      ${lakes}
      <path class="pp-state" d="${pd(st)}"/>
      <path class="pp-road-c" d="${roads}"/><path class="pp-road" d="${roads}"/>
      <text class="pp-lakename" x="${X(-120.035)}" y="${Y(39.1)}">Lake Tahoe</text><text class="pp-lakename sm" x="${X(-120.02)}" y="${Y(38.982)}">Lake Tahoe</text>
      ${towns}
      <text class="pp-st" x="${X(-120.0) + 6}" y="${Y(39.36)}">CA · NV</text>
      <path class="pp-route-all" d="${Object.entries(G.routes).filter(([k]) => k !== 'alt').map(([, r]) => pd(r.alts[0].pts)).join('')}"/>
      <path class="pp-route-c" data-rc d=""/><path class="pp-route" data-route d="" pathLength="1"/>
      <g class="pp-folds">${folds}</g>
    </svg>`;
  }
  function mount(el, opts = {}) {
    const mode = el.closest('.ab').classList.contains('dark') ? 'dark' : 'light';
    const calm = !!el.closest('.ab.dk');
    el.classList.add('pp', calm ? 'pp-calm' : 'pp-liquid');
    el.innerHTML = `<div class="pp-plane" style="width:${PW}px;height:${PH}px">${svg(mode)}<div class="pp-bb" data-bb></div></div>`;
    const plane = el.querySelector('.pp-plane'), bb = el.querySelector('[data-bb]');
    const route = el.querySelector('[data-route]'), rc = el.querySelector('[data-rc]');
    const tilt = opts.tilt ?? 46;
    plane.style.setProperty('--tilt', tilt + 'deg');
    let day = -1;
    function frame(pts, instant) {
      const b = el.getBoundingClientRect();
      const xs = pts.map((p) => X(p[0])), ys = pts.map((p) => Y(p[1]));
      const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
      const bw = Math.max(maxx - minx, 60), bh = Math.max(maxy - miny, 60);
      const c = Math.cos(tilt * Math.PI / 180);
      const s = Math.max(.12, Math.min(opts.maxZoom || 2.1, (b.width * (opts.fitW || .6)) / bw, (b.height * (opts.fitH || .5)) / (bh * c)));
      const cx = (minx + maxx) / 2, cy = (miny + maxy) / 2;
      if (instant) { plane.style.transition = 'none'; requestAnimationFrame(() => (plane.style.transition = '')); }
      // scale3d, not scale: a 2D scale doesn't commute with the tilt, so the labels' counter-scale would stretch them
      plane.style.transform = `translate3d(${b.width / 2}px, ${b.height * (opts.cy || .58)}px, 0) rotateX(${tilt}deg) scale3d(${s}, ${s}, ${s}) translate(${-cx}px, ${-cy}px)`;
      plane.style.setProperty('--inv', (1 / s).toFixed(4));
    }
    function label(key, i, minor) {
      const P = G.places[key], [ic, kind] = STOPI[key];
      const t = (TIMES[i] || {})[key];
      return `<div class="pp-a" style="left:${X(P.lon).toFixed(1)}px;top:${Y(P.lat).toFixed(1)}px"><span class="pp-dot k-${kind}"></span><div class="pp-pop"><span class="mlabel ${minor ? 'minor' : ''}"><span class="ktile k-${kind}">${I(ic)}</span>${SHORT[key]}${t ? ` <em>${t}</em>` : ''}</span></div></div>`;
    }
    function setDay(i, o = {}) {
      if (i === day && !o.force) return;
      day = i;
      const d = DAYS[i];
      const r = d.route ? G.routes[d.route].alts[0] : null;
      const stops = d.stops;
      const pts = r ? r.pts.slice() : stops.map((k) => [G.places[k].lon, G.places[k].lat]);
      if (!r) pts.push([G.places.cabin.lon + .03, G.places.cabin.lat + .02], [G.places.cabin.lon - .03, G.places.cabin.lat - .02]);
      const p = r ? pd(r.pts) : '';
      route.setAttribute('d', p); rc.setAttribute('d', p);
      route.classList.remove('draw'); void route.getBoundingClientRect(); route.classList.add('draw');
      // labels: today's stops stand up; the cabin stays as a small marker
      const long = d.route === 'd1' || d.route === 'd8';
      const keys = [...new Set(stops)].filter((k) => !(long && k === 'grocery'));
      let html = keys.map((k) => label(k, i, !!opts.minor)).join('');
      if (!keys.includes('cabin')) html += label('cabin', i, true);
      if (r) {
        const mid = r.pts[Math.floor(r.pts.length * (long ? .3 : (opts.pillAt ?? .3)))];
        html += `<div class="pp-a" style="left:${X(mid[0]).toFixed(1)}px;top:${Y(mid[1]).toFixed(1)}px"><div class="pp-pop flat"><span class="mtime">${I('car')}${window.TRIP.short(r.min)}</span></div></div>`;
        if (d.route === 'd3' && opts.badges !== false) { const q = r.pts[Math.floor(r.pts.length * .82)]; html += `<div class="pp-a" style="left:${X(q[0]).toFixed(1)}px;top:${Y(q[1]).toFixed(1)}px"><div class="pp-pop flat low"><span class="bdg warn">${I('chain')}R2 chains</span></div></div>`; }
        if ((d.route === 'd1' || d.route === 'd8') && opts.badges !== false) { const sp = G.places.spooner; html += `<div class="pp-a" style="left:${X(sp.lon).toFixed(1)}px;top:${Y(sp.lat).toFixed(1)}px"><div class="pp-pop flat low"><span class="bdg warn">${I('mountain')}Spooner Summit 7,146 ft</span></div></div>`; }
      }
      bb.innerHTML = html;
      frame(pts.concat(stops.map((k) => [G.places[k].lon, G.places[k].lat])), o.instant);
    }
    const ro = new ResizeObserver(() => day >= 0 && setDay(day, { force: true, instant: true })); ro.observe(el);
    return { setDay, el, overview() { frame([[W0 + .05, S0 + .05], [E0 - .05, N0 - .05]]); } };
  }
  window.Paper = { mount, X, Y, PW, PH };
})();
