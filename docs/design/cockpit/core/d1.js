/* Direction 1 · Diorama. The trip lives on a little 3D toy of the real Tahoe basin: the day's route draws itself, the
   family's SUV drives it, snow falls in the scene on snow days, and dark mode turns it to night with the towns lit.
   Widgets dock around the stage on the grey canvas. Map: three.js r187 tree-shaken (about 147 KB gzip) plus the
   region's elevation (about 77 KB gzip, 32 KB if stored as 8-bit) and OpenStreetMap shapes (13 KB gzip). */
(function () {
  const { UI } = window; const { I } = UI;
  const { TRIP, DAYS, LANES, LANE_ORDER, NEXT, money, short } = window.TRIP;
  const G = window.GEO, S = UI.S;
  const KINDS = { rno: 'flight', cabin: 'stay', grocery: 'food', heavenly: 'tix', gondola: 'tix', taylor: 'tix', zephyr: 'tix', emerald: 'see' };
  const ICO = { rno: 'plane', cabin: 'cabin', grocery: 'cart', heavenly: 'ski', gondola: 'ticket', taylor: 'snowshoe', zephyr: 'snowmobile', emerald: 'see' };
  const NAME = { rno: 'Reno airport', cabin: 'Cabin', grocery: 'Groceries', heavenly: 'Heavenly', gondola: 'Gondola', taylor: 'Taylor Creek', zephyr: 'Zephyr Cove', emerald: 'Emerald Bay' };
  const TIMES = { 0: { rno: '1:47 PM', grocery: '4:05 PM', cabin: '4:30 PM' }, 1: { heavenly: '8:45 AM' }, 2: { taylor: '10:00 AM' }, 3: { zephyr: '11:00 AM' }, 4: { heavenly: '8:45 AM', emerald: '4:00 PM' }, 5: { gondola: '11:00 AM' }, 6: { cabin: 'all day' }, 7: { cabin: '10:00 AM', rno: '1:30 PM' } };
  const avs = `<span class="avs"><span class="avatar">A</span><span class="avatar">${I('user')}</span><span class="avatar">11</span><span class="avatar">8</span></span>`;
  const mode = () => document.documentElement.className.includes('dark') ? 'dark' : 'light';
  const lbl = (k, html, minor) => ({ key: k, html: `<span class="mlabel ${minor ? 'minor dim' : ''}"><span class="ktile k-${KINDS[k]}">${I(ICO[k])}</span>${html}</span>` });

  function dayLabels(i, o = {}) {
    const d = DAYS[i], r = d.route ? G.routes[d.route].alts[0] : null;
    const keys = new Set(d.stops);
    const out = [];
    const near = (k) => d.stops.some((s) => Math.hypot((G.places[s].lon - G.places[k].lon) * 86, (G.places[s].lat - G.places[k].lat) * 111) < 5.2);
    for (const k of Object.keys(KINDS)) {
      const on = keys.has(k), t = (TIMES[i] || {})[k];
      if (!on && (o.phone || ['grocery', 'gondola'].includes(k) || near(k) || (r && r.km > 60))) continue;
      out.push(lbl(k, `${NAME[k]}${on && t ? ` <em>${t}</em>` : ''}`, !on));
    }
    if (r) {
      const m = r.pts[Math.floor(r.pts.length * (d.route === 'd1' || d.route === 'd8' ? .5 : o.phone ? .66 : .32))];
      out.push({ at: m, lift: .9, html: `<span class="mtime">${I('car')}${short(r.min)}</span>` });
      if (d.route === 'd3' && !o.phone) { const c = r.pts[Math.floor(r.pts.length * .8)]; out.push({ at: c, lift: 1.2, html: `<span class="mwarn"><span class="bdg warn">${I('chain')}R2 chains</span></span>` }); }
      if ((d.route === 'd1' || d.route === 'd8') && !o.phone) { const sp = G.places.spooner; out.push({ at: [sp.lon, sp.lat], lift: 1, html: `<span class="mwarn"><span class="bdg warn">${I('mountain')}Spooner Summit 7,146 ft</span></span>` }); }
    }
    if (!o.phone) for (const t of G.towns.filter((t) => ['Reno', 'Carson City', 'Incline Village', 'Tahoe City', 'Truckee', 'Minden'].includes(t.name))) out.push({ at: [t.lon, t.lat], lift: .4, html: `<span class="mtown">${t.name}</span>` });
    return out;
  }
  function dayArgs(i, o = {}) {
    const d = DAYS[i], r = d.route ? G.routes[d.route].alts[0] : null;
    const stops = d.stops.map((k) => [G.places[k].lon, G.places[k].lat]);
    const fpts = r ? r.pts.concat(stops) : [[G.places.cabin.lon - .05, G.places.cabin.lat - .03], [G.places.cabin.lon + .05, G.places.cabin.lat + .04]];
    return { pts: r ? r.pts : null, frame: fpts, weather: d.wx, labels: dayLabels(i, o), pad: o.pad || (r && r.km > 60 ? 1 : 1.75), instant: o.instant };
  }
  function mountStage(root, o = {}) {
    const el = root.querySelector('[data-stage]'); if (!el) return null;
    const api = window.Diorama.mount(el, {
      mode: mode(), calm: UI.M.calm(root), kinds: KINDS, fogColor: getComputedStyle(root).getPropertyValue('--stage').trim() || undefined, az: o.az, el: o.el,
      onReady: (a) => {
        if (o.book) a.setDay({ pts: null, frame: o.phone ? [[-120.0, 38.9], [-119.7, 39.52]] : [[-120.1, 38.9], [-119.72, 39.52]], weather: { type: 'sun' }, labels: bookLabels(), pad: o.phone ? .8 : .9, az: -.25, el: 1.05, instant: true });
        else a.setDay(dayArgs(S.day, { ...o, instant: true }));
        setTimeout(() => window.VIEW.ready(), 1600);
      },
    });
    if (!o.book) S.on('day', (i) => api.setDay(dayArgs(i, o)));
    root.querySelector('[data-overview]')?.addEventListener('click', () => { api.resetUser(); api.overview({ pad: 1.05 }); });
    return api;
  }

  /* ---------- stage chrome ---------- */
  const stage = (o = {}) => `<section class="d1-stage ${o.cls || ''}"><div class="d1-dio" data-stage></div>
    <div class="d1-tools"><span class="d3-tag">${I('cube')}Toy map · real elevation</span>${o.hint === false ? '' : `<span class="d3-tag soft">Drag to turn · scroll to zoom</span>`}</div>
    ${o.over === false ? '' : `<button class="d1-over btn tonal sm" data-overview>${I('mountain')}Whole trip</button>`}
    <div class="d3-cap">© OpenStreetMap · elevation: AWS Terrain Tiles</div></section>`;

  /* ---------- 1 · cockpit ---------- */
  function cockpit(size) {
    if (size === 'dk') return `${UI.top('trip')}<main class="d1c">
      <div class="d1-head"><div><div class="eyebrow">${TRIP.who} · day 3 of 8 · Mon Dec 21, 9:12 AM</div><h1 class="h1">Tahoe at Christmas</h1></div>${UI.dayChips()}</div>
      ${stage()}
      <div class="d1-bw">${['flight', 'stay', 'car', 'tix'].map((k) => UI.bookingWidget(k)).join('')}</div>
      <aside class="d1-rail">${UI.upNext({ cls: 'd1-up', inline: true })}${UI.wxWidget(S.day, { cls: 'd1-wx' })}${UI.family({ cls: 'd1-fam', short: true })}</aside>
    </main>`;
    return `${UI.sbar()}<main class="d1p">
      <div class="p-top d1-ptop"><div><div class="eyebrow">Tahoe · day 3 of 8 · 9:12 AM</div><div class="h1">Monday</div></div><span class="sp"></span>${avs}</div>
      ${stage({ cls: 'ph-stage', hint: false, over: false })}
      <div class="d1-pdays">${UI.dayChips()}</div>
      <section class="d1-sheet" data-sheet><div class="grab" data-grab></div>
        ${UI.upNext({ cls: 'd1-up', steps: 2 })}
        ${UI.wxWidget(S.day, { cls: 'd1-wx' })}
        <div class="p-sec"><b>Bookings</b><span>Each one on its partner</span></div>
        <div class="d1-pbw">${['tix', 'stay', 'car', 'flight'].map((k) => UI.bookingWidget(k)).join('')}</div>
        ${UI.family()}
      </section></main>${UI.tabbar('trip')}`;
  }
  function bindSheet(root) {
    const sh = root.querySelector('[data-sheet]'); if (!sh) return;
    const rest = sh.offsetTop, up = 112; let y0 = 0, start = 0, dragging = false, pos = rest;
    const set = (v, anim) => { sh.style.transition = anim ? 'transform 520ms var(--spring)' : 'none'; sh.style.transform = `translateY(${v - rest}px)`; pos = v; };
    root.querySelector('[data-grab]').addEventListener('pointerdown', (e) => { dragging = true; y0 = e.clientY; start = pos; sh.setPointerCapture(e.pointerId); });
    sh.addEventListener('pointermove', (e) => { if (dragging) set(Math.max(up, Math.min(rest + 40, start + e.clientY - y0))); });
    sh.addEventListener('pointerup', () => { if (!dragging) return; dragging = false; set(pos < (rest + up) / 2 ? up : rest, true); });
    root.querySelector('[data-grab]').addEventListener('click', () => set(pos === rest ? up : rest, true));
  }
  function mountCockpit(root, size) {
    UI.mountWx(root);
    mountStage(root, size === 'ph' ? { phone: true, az: -.5, el: .9 } : { az: -.55, el: .8 });
    UI.bindDays(root);
    if (size === 'ph') bindSheet(root);
  }

  /* ---------- 2 · Book this trip: lanes beside the toy, each with its pin ---------- */
  let phone = false;
  function bookLabels() {
    const L = LANES, b = (id) => S.booked.has(id);
    const st = (id) => b(id) ? `<em class="ok">${I('check')}${L[id].booked.direct ? 'direct' : L[id].booked.on}</em>` : `<em>${L[id].state === 'real' ? `from $${L[id].price}` : L[id].state === 'partner' ? L[id].partner : L[id].state === 'direct' ? 'buy direct' : 'plain link'}</em>`;
    const c = (k, kind, ic, name, id, x, y, minor) => ({ key: k, fixed: { x, y }, html: `<span class="mlabel call ${x < 0 ? 'r' : ''} ${minor ? 'minor' : ''}"><span class="ktile k-${kind}">${I(ic)}</span>${name} ${st(id)}</span>` });
    if (phone) return [['rno', 'flight', 'plane', 'Flights', 'flight'], ['rno', 'car', 'car', 'SUV', 'car'], ['heavenly', 'tix', 'ski', 'Ski school', 'lessons'], ['cabin', 'stay', 'cabin', 'Cabin', 'stay'], ['zephyr', 'tix', 'snowmobile', 'Snowmobile', 'snowmobile'], ['taylor', 'tix', 'snowshoe', 'Snowshoe', 'snowshoe']]
      .map(([k, kind, ic, n, id], i) => c(k, kind, ic, n, id, 10, 54 + i * 31, true));
    return [c('rno', 'flight', 'plane', 'Flights', 'flight', -14, 64), c('rno', 'car', 'car', 'SUV', 'car', -14, 108),
      c('heavenly', 'tix', 'ski', 'Ski school', 'lessons', 14, 64), c('cabin', 'stay', 'cabin', 'Cabin', 'stay', 14, 108), c('zephyr', 'tix', 'snowmobile', 'Snowmobile', 'snowmobile', 14, 152), c('taylor', 'tix', 'snowshoe', 'Snowshoe', 'snowshoe', 14, 196)];
  }
  function book(size, q) {
    if (!q || q.get('state') !== 'all') S.booked = new Set(['lessons']);
    const facts = `<div class="d3-meta"><span class="d3-chip">${I('plane')}SFO → Reno</span><span class="d3-chip">${I('cal')}${TRIP.dates}</span><span class="d3-chip">${I('users')}${TRIP.party}</span><button class="btn text">Change</button></div>`;
    if (size === 'dk') return `${UI.top('book', { icon: 'ticket', text: 'Book this trip ·', val: `${S.booked.size} of 6` })}<main class="d1b">
      <div class="d1-head"><div><div class="eyebrow">${TRIP.name}</div><h1 class="h1">Book this trip</h1></div>${facts}</div>
      <div class="d1b-left">${stage({ hint: false, over: false, cls: 'book-stage' })}${UI.checklist({ cls: 'd1-ticket' })}</div>
      <div class="d1b-lanes">${LANE_ORDER.map((id) => UI.lane(id, undefined, { cls: 'compact', back: false, note: false })).join('')}</div></main>${UI.pasteSheet()}`;
    return `${UI.sbar('10:24')}<main class="d1p d1pb"><div class="p-head"><div class="eyebrow">${TRIP.name}</div><div class="h1">Book this trip</div><div class="sub">${TRIP.dates} · ${TRIP.partyShort}</div></div>
      ${stage({ cls: 'ph-stage sm', hint: false, over: false })}
      ${UI.checklist({ cls: 'd1-pticket' })}
      <div class="d1-plane">${LANE_ORDER.map((id) => UI.lane(id)).join('')}</div>
      <p class="p-honest">${I('spark')}Every link opens the partner’s own site. GitAway never takes payment, so changes and refunds stay with the partner.</p>
    </main>${UI.tabbar('book')}${UI.pasteSheet()}`;
  }
  let dio = null;
  function mountBook(root, size, q) {
    phone = size === 'ph';
    dio = mountStage(root, { book: true, phone, az: -.35, el: .98 });
    return UI.bindPaste(root, {
      target: () => { const st = root.querySelector('[data-stage]'); const p = dio.screenPos('cabin'); const t = document.createElement('div'); t.style.cssText = `position:absolute;left:${p.x - 20}px;top:${p.y - 20}px;width:40px;height:40px;pointer-events:none`; st.appendChild(t); setTimeout(() => t.remove(), 900); return t; },
      done: () => { dio.pulse('cabin'); UI.land(root, 'stay', { laneOpts: size === 'dk' ? { cls: 'compact', back: false, note: false } : {} }); dio.setLabels(bookLabels()); const bc = root.querySelector('.beacon b'); if (bc) UI.M.swap(bc, `${S.booked.size} of 6`); },
    });
  }

  /* ---------- 3 · one day on the phone ---------- */
  function day() {
    const d = DAYS[S.day];
    return `${UI.sbar()}<main class="d1p d1day">
      <div class="p-top"><button class="xbtn" aria-label="Back">${I('back')}</button><div><div class="eyebrow">${TRIP.name} · day ${S.day + 1} of 8</div><div class="h2" data-f="title">${d.dow} ${d.date} · ${d.name}</div></div></div>
      ${stage({ cls: 'ph-stage day', hint: false, over: false })}
      <div class="d1-pdays">${UI.dayChips()}</div>
      ${UI.wxWidget(S.day, { cls: 'd1-wx' })}
      <div class="p-sec"><b>The day</b><span>Start times on the left</span></div>
      ${UI.rail(S.day)}
    </main>${UI.tabbar('plan')}`;
  }
  function mountDay(root) {
    UI.mountWx(root);
    mountStage(root, { phone: true, az: -.45, el: .92 });
    UI.bindDays(root, (i) => { const d = DAYS[i]; UI.M.swap(root.querySelector('[data-f="title"]'), `${d.dow} ${d.date} · ${d.name}`); const r = root.querySelector('[data-rail]'); const t = document.createElement('div'); t.innerHTML = UI.rail(i); r.replaceWith(t.firstElementChild); });
  }

  /* ---------- 4 · paste ---------- */
  function mountPaste(root, size, q) {
    const p = mountBook(root, size, q);
    const phase = q.get('phase') || 'open';
    const go = () => {
      if (phase === 'landed') { dio.pulse('cabin'); UI.land(root, 'stay', { laneOpts: size === 'dk' ? { cls: 'compact', back: false, note: false } : {} }); dio.setLabels(bookLabels()); const bc = root.querySelector('.beacon b'); if (bc) bc.textContent = `${S.booked.size} of 6`; if (size === 'ph') root.querySelector('[data-lane="stay"]').scrollIntoView({ block: 'center' }); return; }
      p.open(root.querySelector('[data-paste="stay"]'));
      if (phase === 'read') p.scrim.dataset.phase = 'read';
      if (phase === 'play') setTimeout(() => p.read(), 900);
    };
    setTimeout(go, 1700);
  }

  window.DIR = {
    id: 1, name: 'Diorama',
    notes: `<h1>Direction 1 · Diorama <em>the trip on a toy of the real place.</em></h1>
      <p><b>The trip lives on a little 3D model of the Tahoe basin</b>, built from real elevation: the Sierra crest, the lake, the Carson Range and the valley down to Reno. Tap a day: the camera flies to that day, the route draws itself and the family’s green SUV drives it. On snow days it snows on the model; in dark mode the diorama turns to night and the towns light up.</p>
      <ul><li><b>Around it,</b> on the grey canvas: Up next with the next leg turn by turn (the focal ink card), the living weather, the family chat, and the four bookings as solid kind widgets with “Booked on” and Change or cancel.</li>
      <li><b>Map:</b> three.js r187, tree-shaken to about 147 KB gzip, plus the region’s elevation (AWS Terrain Tiles, free) and OpenStreetMap shapes. No tile server, works offline once loaded, falls back to a still on weak phones. It doesn’t do street level: directions hand off to Google or Apple Maps.</li>
      <li><b>Book this trip</b> puts each lane on its pin: the airport has flights and the SUV, the cabin has the stay, Taylor Creek the snowshoes. A pasted confirmation flies to its pin, the pin pops, the lane gets stamped.</li>
      <li><b>Motion:</b> phone, springs and morphs from what you tapped, the sheet drags up from the stage; desktop, a calm 180 ms fade and a slower camera.</li></ul>`,
    screens: {
      cockpit: { sizes: ['dk', 'ph'], render: cockpit, mount: mountCockpit, fixed: ['ph'], note: 'Tap a day chip: the camera flies, the route draws, the SUV drives, the weather widget and the in-scene weather change together (Monday and Friday snow, Thursday wind). Drag the model to turn it. On the phone, drag the sheet up from its handle.' },
      book: { sizes: ['dk', 'ph'], render: book, mount: mountBook, note: 'Each lane sits beside its pin on the model. Flights show a real cached price; Klook is a partner search; the cabin, SUV and snowmobile are plain links with no commission; ski school is Buy direct.' },
      day: { sizes: ['ph'], render: day, mount: mountDay, note: 'One day: the model flies to that day’s route, then the living weather and the day on a time rail. The chips switch days.' },
      paste: { sizes: ['dk', 'ph'], render: book, mount: mountPaste, note: 'Press “Read it”. On the phone the read card flies into the cabin’s pin, the pin pops and the Stay lane is stamped; on a desktop the panel fades and the lane fades to booked.' },
    },
  };
})();
