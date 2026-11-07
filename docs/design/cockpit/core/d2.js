/* Direction 2 · Widget board. The trip as a home screen of widgets on the grey canvas: a big map widget (a real map,
   tilted, with terrain), Up next with the next leg, the living weather, the family, and one widget per booking.
   Map: MapLibre GL JS 5.24 (about 275 KB gzip) + OpenFreeMap vector tiles + AWS terrain, all free. */
(function () {
  const { UI } = window; const { I } = UI;
  const { TRIP, DAYS, LANES, LANE_ORDER, NEXT, AROUND, money, short } = window.TRIP;
  const G = window.GEO, S = UI.S;
  const KINDS = { rno: 'flight', cabin: 'stay', grocery: 'food', heavenly: 'tix', gondola: 'tix', taylor: 'tix', zephyr: 'tix', emerald: 'see' };
  const ICO = { rno: 'plane', cabin: 'cabin', grocery: 'cart', heavenly: 'ski', gondola: 'ticket', taylor: 'snowshoe', zephyr: 'snowmobile', emerald: 'see' };
  const NAME = { rno: 'Reno airport', cabin: 'Cabin', grocery: 'Groceries', heavenly: 'Heavenly', gondola: 'Gondola', taylor: 'Taylor Creek', zephyr: 'Zephyr Cove', emerald: 'Emerald Bay' };
  const TIMES = { 0: { rno: '1:47 PM', grocery: '4:05 PM', cabin: '4:30 PM' }, 1: { heavenly: '8:45 AM' }, 2: { taylor: '10:00 AM' }, 3: { zephyr: '11:00 AM' }, 4: { heavenly: '8:45 AM', emerald: '4:00 PM' }, 5: { gondola: '11:00 AM' }, 6: { cabin: 'all day' }, 7: { cabin: '10:00 AM', rno: '1:30 PM' } };
  const avs = `<span class="avs"><span class="avatar">A</span><span class="avatar">${I('user')}</span><span class="avatar">11</span><span class="avatar">8</span></span>`;
  const mode = () => document.documentElement.className.includes('dark') ? 'dark' : 'light';
  const pt = (k) => [G.places[k].lon, G.places[k].lat];

  function dayArgs(i, o = {}) {
    const d = DAYS[i], r = d.route ? G.routes[d.route].alts[0] : null;
    const labels = [...new Set(d.stops)].map((k) => ({ at: pt(k), html: `<span class="mlabel"><span class="ktile k-${KINDS[k]}">${I(ICO[k])}</span>${NAME[k]}${(TIMES[i] || {})[k] ? ` <em>${TIMES[i][k]}</em>` : ''}</span>` }));
    if (r) {
      labels.push({ at: r.pts[Math.floor(r.pts.length * (r.km > 60 ? .5 : .38))], anchor: 'center', html: `<span class="mtime">${I('car')}${short(r.min)}</span>` });
      if (d.route === 'd3' && !o.phone) labels.push({ at: r.pts[Math.floor(r.pts.length * .82)], anchor: 'top', html: `<span class="bdg warn">${I('chain')}R2 chains</span>` });
      if (r.km > 60 && !o.phone) labels.push({ at: pt('spooner'), anchor: 'left', html: `<span class="bdg warn">${I('mountain')}Spooner Summit 7,146 ft</span>` });
    }
    const frame = r ? r.pts.concat(d.stops.map(pt)) : [[-120.0, 38.91], [-119.9, 38.96]];
    return { pts: r ? r.pts : null, frame, labels, maxZoom: r && r.km > 60 ? 10.2 : 12.3, pitch: r && r.km > 60 ? 45 : 55, bearing: r && r.km > 60 ? -8 : -22 };
  }
  function mountMap(root, o = {}) {
    const el = root.querySelector('[data-mapl]'); if (!el) return null;
    const api = window.MapL.mount(el, { mode: mode(), calm: UI.M.calm(root), padding: o.padding, onReady: () => setTimeout(() => window.VIEW.ready(), 600) });
    api.setDay(o.book ? bookArgs() : dayArgs(S.day, o));
    if (!o.book) S.on('day', (i) => api.setDay(dayArgs(i, o)));
    return api;
  }
  const mapWidget = (o = {}) => `<section class="w card d2-map ${o.cls || ''}"><div class="d2-ml" data-mapl></div>
    <div class="d2-mtools"><span class="d3-tag">${I('layers')}Real map · tilted, hillshade</span>${o.around === false ? '' : `<span class="d3-tag soft">${I('pin')}Around the cabin: ${AROUND.map((a) => `${a.name} ${a.min} min`).join(' · ')}</span>`}</div></section>`;

  /* ---------- 1 · cockpit ---------- */
  function cockpit(size) {
    if (size === 'dk') return `${UI.top('trip')}<main class="d2c">
      <div class="d2-head"><div><div class="eyebrow">${TRIP.who} · day 3 of 8 · Mon Dec 21, 9:12 AM</div><h1 class="h1">Tahoe at Christmas</h1></div>${UI.dayChips()}</div>
      ${mapWidget({ cls: 'g-map' })}
      ${UI.upNext({ cls: 'g-up', wide: true })}
      ${UI.wxWidget(S.day, { cls: 'g-wx' })}
      ${UI.family({ cls: 'g-fam' })}
      ${['flight', 'stay', 'car', 'tix'].map((k) => UI.bookingWidget(k, { cls: 'g-b' })).join('')}
    </main>`;
    return `${UI.sbar()}<main class="d2p">
      <div class="p-head d2-ph"><div><div class="eyebrow">Tahoe · day 3 of 8 · 9:12 AM</div><div class="h1">Monday</div></div>${avs}</div>
      <div class="d2-pdays">${UI.dayChips()}</div>
      ${UI.upNext({ steps: 2 })}
      <div class="d2-two">${UI.wxWidget(S.day, { cls: 'sq', mini: true, src: false, place: 'Tahoe' })}${around()}</div>
      ${mapWidget({ cls: 'ph-map', around: false })}
      <div class="p-sec"><b>Bookings</b><span>Each one on its partner</span></div>
      <div class="d2-grid2">${['tix', 'stay', 'car', 'flight'].map((k) => UI.bookingWidget(k, { cls: 'sq' })).join('')}</div>
      ${UI.family()}
    </main>${UI.tabbar('trip')}`;
  }
  const around = () => `<section class="w card d2-around sq"><div class="whead"><span class="ktile sm k-see">${I('pin')}</span><b>Around you</b></div>
    ${AROUND.map((a) => `<div class="ar"><span>${a.name}</span><b class="tnum">${a.min} min</b></div>`).join('')}<span class="fine">From the cabin, by car</span></section>`;
  const ride = (o = {}) => `<section class="w on-k k-ride ride ${o.cls || ''}"><div class="whead"><span class="eyebrow">Ride to SFO · Sat 10:30 AM</span><span class="sp"></span>${I('car', 'ico')}</div>
    <span class="big tnum">$45–60</span><span class="ri-s">Uber or Lyft from home · an estimate, not a quote</span>
    <div class="ri-f"><a class="btn tonal sm" href="#">Open Uber ${I('ext')}</a><span>Plain link · we earn nothing</span></div></section>`;
  function mountCockpit(root, size) {
    UI.mountWx(root);
    mountMap(root, size === 'ph' ? { phone: true, padding: { top: 70, bottom: 40, left: 70, right: 50 } } : { padding: { top: 90, bottom: 50, left: 60, right: 60 } });
    UI.bindDays(root);
  }

  /* ---------- 2 · Book this trip: lanes as widgets ---------- */
  function bookArgs() {
    const st = (id) => S.booked.has(id) ? `<em class="ok">${I('check')}${LANES[id].booked.direct ? 'direct' : LANES[id].booked.on}</em>` : '';
    return { pts: G.routes.d1.alts[0].pts, frame: G.routes.d1.alts[0].pts.concat([pt('taylor'), pt('zephyr')]), maxZoom: 9.6, pitch: 40, bearing: -10,
      labels: [['rno', 'Flights + SUV', 'flight'], ['cabin', 'Cabin', 'stay'], ['taylor', 'Snowshoe', 'snowshoe'], ['zephyr', 'Snowmobile', 'snowmobile'], ['heavenly', 'Ski school', 'lessons']].map(([k, n, id]) => ({ at: pt(k), html: `<span class="mlabel minor"><span class="ktile k-${KINDS[k]}">${I(ICO[k])}</span>${n} ${st(id)}</span>` })) };
  }
  const pasteW = (o = {}) => `<section class="w card d2-pastew ${o.cls || ''}"><div class="whead"><span class="ktile sm k-stay">${I('mail')}</span><b>Bring a booking home</b></div>
    <button class="d2-drop" data-paste="stay">${I('clip')}<span><b>Paste the confirmation email</b>From Vrbo, United, Klook, anywhere. We read the place, dates and total.</span></button>
    <p class="fine">Or forward it later. The reservation number stays masked.</p></section>`;
  function book(size, q) {
    if (!q || q.get('state') !== 'all') S.booked = new Set(['lessons']);
    const lane = (id, cls) => UI.lane(id, undefined, { cls: `compact ${cls}`, back: false, note: id === 'flight' });
    if (size === 'dk') return `${UI.top('book', { icon: 'ticket', text: 'Book this trip ·', val: `${S.booked.size} of 6` })}<main class="d2b">
      <div class="d2-head"><div><div class="eyebrow">${TRIP.name}</div><h1 class="h1">Book this trip</h1></div><div class="d3-meta"><span class="d3-chip">${I('plane')}SFO → Reno</span><span class="d3-chip">${I('cal')}${TRIP.dates}</span><span class="d3-chip">${I('users')}${TRIP.party}</span><button class="btn text">Change</button></div></div>
      ${lane('flight', 'b-fl')}${lane('stay', 'b-st')}${UI.checklist({ cls: 'b-ck' })}
      ${lane('car', 'b-ca')}${lane('snowshoe', 'b-ss')}${lane('snowmobile', 'b-sm')}
      ${lane('lessons', 'b-le')}${pasteW({ cls: 'b-pa' })}${ride({ cls: 'b-ri' })}${UI.wxPre({ cls: 'b-wx compact' })}
    </main>${UI.pasteSheet()}`;
    return `${UI.sbar('10:24')}<main class="d2p"><div class="p-head"><div class="eyebrow">${TRIP.name}</div><div class="h1">Book this trip</div><div class="sub">${TRIP.dates} · ${TRIP.partyShort}</div></div>
      ${UI.checklist()}
      ${pasteW()}
      ${LANE_ORDER.map((id) => UI.lane(id)).join('')}
      ${ride()}
      ${UI.wxPre()}
      <p class="p-honest">${I('spark')}Every link opens the partner’s own site. GitAway never takes payment, so changes and refunds stay with the partner.</p>
    </main>${UI.tabbar('book')}${UI.pasteSheet()}`;
  }
  function mountBook(root, size, q) {
    UI.mountWxPre(root);
    setTimeout(() => window.VIEW.ready(), 600);
    return UI.bindPaste(root, {
      target: () => root.querySelector('[data-lane="stay"]'),
      done: () => { UI.land(root, 'stay', { laneOpts: size === 'dk' ? { cls: 'compact b-st', back: false, note: false } : {} }); const bc = root.querySelector('.beacon b'); if (bc) UI.M.swap(bc, `${S.booked.size} of 6`); },
    });
  }

  /* ---------- 3 · one day on the phone ---------- */
  function hourly(i) {
    const w = DAYS[i].wx, n = 12, base = { snow: [.2, .4, .7, .9, 1, .9, .8, .7, .6, .5, .5, .4], flurry: [.5, .4, .3, .2, .1, 0, 0, 0, 0, 0, 0, 0], cloud: [0, 0, 0, 0, 0, 0, 0, 0, 0, .1, .3, .5] }[w.type] || Array(n).fill(0);
    const hrs = ['7a', '8a', '9a', '10a', '11a', '12p', '1p', '2p', '3p', '4p', '5p', '6p'];
    return `<div class="hrly" aria-label="Snow by the hour">${base.map((v, k) => `<div><i style="height:${Math.round(4 + v * 30)}px"></i><span>${hrs[k]}</span></div>`).join('')}</div>`;
  }
  function day() {
    const d = DAYS[S.day];
    return `${UI.sbar()}<main class="d2p">
      <div class="p-top"><button class="xbtn" aria-label="Back">${I('back')}</button><div><div class="eyebrow">${TRIP.name} · day ${S.day + 1} of 8</div><div class="h2" data-f="title">${d.dow} ${d.date} · ${d.name}</div></div></div>
      <div class="d2-pdays">${UI.dayChips()}</div>
      <section class="w on-k k-wx wx d2-wxbig" data-wx aria-live="polite"><canvas class="wx-cv" aria-hidden="true"></canvas><div class="wx-in">
        <div class="eyebrow" data-calm>South Lake Tahoe · <span data-f="date">${d.dow} ${d.date}</span></div>
        <div class="wx-now" data-calm><span class="big" data-f="hi">${d.wx.hi}°</span><span class="wx-word" data-f="word">${d.wx.word}</span></div>
        <div class="wx-meta" data-calm data-f="meta">H ${d.wx.hi}° · L ${d.wx.lo}° · gusts ${d.wx.gust} mph</div>
        <div data-calm data-f="hrly">${hourly(S.day)}</div>
        <div class="wx-src" data-calm>Forecast · MET Norway · 6:10 AM</div></div></section>
      ${mapWidget({ cls: 'ph-map day', around: false })}
      <div class="p-sec"><b>The day</b><span>Start times on the left</span></div>
      ${UI.rail(S.day)}
    </main>${UI.tabbar('plan')}`;
  }
  function mountDay(root) {
    UI.mountWx(root);
    mountMap(root, { phone: true, padding: { top: 60, bottom: 30, left: 30, right: 30 } });
    UI.bindDays(root, (i) => { const d = DAYS[i]; UI.M.swap(root.querySelector('[data-f="title"]'), `${d.dow} ${d.date} · ${d.name}`); UI.M.swap(root.querySelector('[data-f="hrly"]'), hourly(i)); const r = root.querySelector('[data-rail]'); const t = document.createElement('div'); t.innerHTML = UI.rail(i); r.replaceWith(t.firstElementChild); });
  }

  /* ---------- 4 · paste ---------- */
  function mountPaste(root, size, q) {
    const p = mountBook(root, size, q);
    const phase = q.get('phase') || 'open';
    if (phase === 'landed') { UI.land(root, 'stay', { laneOpts: size === 'dk' ? { cls: 'compact b-st', back: false, note: false } : {} }); const bc = root.querySelector('.beacon b'); if (bc) bc.textContent = `${S.booked.size} of 6`; if (size === 'ph') root.querySelector('[data-lane="stay"]').scrollIntoView({ block: 'center' }); return; }
    p.open(root.querySelector('[data-paste="stay"]'));
    if (phase === 'read') p.scrim.dataset.phase = 'read';
    if (phase === 'play') setTimeout(() => p.read(), 900);
  }

  window.DIR = {
    id: 2, name: 'Widget board',
    notes: `<h1>Direction 2 · Widget board <em>the trip as a home screen.</em></h1>
      <p><b>Every part of the trip is a widget on the grey canvas</b>, the way a phone’s home screen works: one big map widget, Up next with the next leg (the focal ink card), the living weather, the family, and one solid widget per booking with “Booked on” and Change or cancel. Tap a day and the map flies there; the weather widget changes with it.</p>
      <ul><li><b>Map:</b> a real map, tilted, with 3D terrain: MapLibre GL JS 5.24 (about 275 KB gzip, loaded only where the map is) drawing OpenFreeMap’s free vector tiles, restyled to the grey canvas, with free AWS terrain. Streets and zoom are real, so it works at street level and for any destination.</li>
      <li><b>Book this trip</b> is the same board: a wide flights widget with real fares by day, one widget per lane in its honest state, the checklist ticket down the right, and a “Bring a booking home” widget to paste a confirmation.</li>
      <li><b>Motion:</b> phone, a tapped widget grows into its sheet and the paste card flies into its widget; desktop, a calm 180 ms fade; the map flies calmly on both.</li></ul>`,
    screens: {
      cockpit: { sizes: ['dk', 'ph'], render: cockpit, mount: mountCockpit, note: 'Tap a day chip: the map flies to that day’s route and redraws it, and the weather widget changes in place. Drag the map to pan; right-drag or two fingers to tilt and turn. Needs a connection for the tiles; offline it shows a still.' },
      book: { sizes: ['dk', 'ph'], render: book, mount: mountBook, note: 'Flights get a wide widget with real fares by day; Klook is a partner search; the cabin, SUV and snowmobile are plain links with no commission; ski school is Buy direct. “Bring a booking home” opens the paste sheet.' },
      day: { sizes: ['ph'], render: day, mount: mountDay, note: 'One day: the weather widget grows to show snow by the hour, the map widget shows the day’s route, then the time rail. The chips switch days.' },
      paste: { sizes: ['dk', 'ph'], render: book, mount: mountPaste, note: 'Press “Read it”: on the phone the read card flies into the Stay widget and the stamp lands; on a desktop the panel fades and the widget fades to booked.' },
    },
  };
})();
