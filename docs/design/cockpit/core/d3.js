/* Direction 3 · Ticket line. The trip is one line of ticket stubs, one per day, each with its own living weather;
   the open stub is today (Up next and the next leg, the focal card), and tapping another day opens its stub while the
   paper pop-up map flies there. Bookings are passes in a wallet. Map: no library, about 3 KB gzip of script plus about 115 KB
   of per-trip data (relief image + OpenStreetMap shapes). */
(function () {
  const { UI } = window; const { I } = UI;
  const { TRIP, DAYS, LANES, LANE_ORDER, NEXT, money, short } = window.TRIP;
  const S = UI.S;
  const avs = `<span class="avs"><span class="avatar">A</span><span class="avatar">${I('user')}</span><span class="avatar">11</span><span class="avatar">8</span></span>`;

  /* ---------- day stubs ---------- */
  const shortT = (t) => t.replace(':00', '').replace(' AM', 'a').replace(' PM', 'p');
  function stubBody(i, open) {
    const d = DAYS[i];
    const items = d.plans.filter((p) => !p.drive);
    if (open && i === TRIP.nowDay) {
      return `<div class="ds-open"><div class="eyebrow">Today · up next · leave in <span class="tnum">${NEXT.inMin} min</span></div>
        <div class="up-t">Snowshoe at Taylor Creek</div>
        <div class="kv"><div><small>Leave</small><b>9:35</b></div><div><small>Drive</small><b>${NEXT.min} min</b></div><div><small>Starts</small><b>10:00</b></div><div><small>Distance</small><b>${NEXT.mi} mi</b></div></div>
        <div class="perf"></div>
        <div class="legs">${NEXT.steps.map((s) => `<div class="lg"><span class="lg-i">${I(s.icon)}</span><span class="lg-t">${s.verb} <b>${s.road}</b></span><span class="lg-d tnum">${s.mi} mi</span></div>`).join('')}</div>
        <div class="ds-acts"><button class="btn fill">${I('nav')}Start directions</button><span class="bdg warn">${I('chain')}R2 chains on CA 89</span></div></div>`;
    }
    if (open) {
      return `<div class="ds-open"><div class="eyebrow">${d.dow} ${d.date} · ${d.name}</div>
        <div class="ds-plan">${d.plans.map((p) => p.drive ? `<div class="dp drv"><span class="tnum">${shortT(p.t)}</span><span>${I('car')} ${short(p.drive.min)} · ${p.drive.via}</span></div>`
          : `<div class="dp"><span class="tnum">${shortT(p.t)}</span><span class="dp-b k-${p.kind}"><i class="ktile sm">${I(p.icon)}</i><b>${p.title}</b>${p.lane ? `<em>${LANES[p.lane].booked.direct ? 'Direct' : LANES[p.lane].booked.on}</em>` : ''}</span></div>`).join('')}</div></div>`;
    }
    const on = [...new Set(items.filter((p) => p.lane).map((p) => LANES[p.lane].booked.direct ? 'Direct' : LANES[p.lane].booked.on))];
    return `<div class="ds-closed"><div class="ds-d"><b>${d.dow} ${d.d}</b><span>${d.name}</span></div>
      <ul class="ds-items">${items.slice(0, 3).map((p) => `<li><i class="dot k-${p.kind}"></i><span class="tnum">${p.t}</span><b>${p.st || p.title}</b></li>`).join('')}</ul>
      <div class="ds-foot">${on.length ? on.map((o) => `<span class="ds-on">${I('check')}${o}</span>`).join('') : '<span class="ds-free">Nothing to book</span>'}</div></div>`;
  }
  const stub = (i, open) => `<div class="dstub ${open ? 'open on' : ''} ${i === TRIP.nowDay ? 'today' : ''}" data-stub="${i}">
    <button class="ds-hit" data-day="${i}" aria-label="${DAYS[i].dow} ${DAYS[i].date}: ${DAYS[i].name}"></button>
    <div class="ds-wx" data-wxd="${i}"><canvas aria-hidden="true"></canvas><b class="ds-temp tnum" data-calm>${DAYS[i].wx.hi}°</b><span class="ds-w" data-calm>${DAYS[i].wx.word}</span></div>
    <div class="ds-body">${stubBody(i, open)}</div></div>`;

  function mountStubs(root) {
    root.querySelectorAll('[data-wxd]').forEach((el) => {
      const i = +el.dataset.wxd;
      window.WXE.mount(el.querySelector('canvas'), { host: el, wx: DAYS[i].wx, seed: 30 + i, scale: .72, pines: true, sunX: 30, sunY: 30 });
    });
  }
  function openStub(root, i) {
    const calm = UI.M.calm(root);
    root.querySelectorAll('[data-stub]').forEach((el) => {
      const k = +el.dataset.stub, open = k === i, was = el.classList.contains('open');
      if (open === was) return;
      const body = el.querySelector('.ds-body');
      const first = el.getBoundingClientRect();
      el.classList.toggle('open', open); el.classList.toggle('on', open);
      body.innerHTML = stubBody(k, open);
      if (calm) body.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180, easing: 'cubic-bezier(.2,0,0,1)' });
      else body.animate([{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'none' }], { duration: 360, easing: 'cubic-bezier(.2,0,0,1)' });
    });
  }

  /* ---------- wallet passes ---------- */
  const PASS = { flight: ['plane', 'Flight home · Sat 26', 'RNO → SFO · 1:30 PM', 'United · nonstop · 4 seats', 'United'],
    stay: ['cabin', 'Stay · 5 nights left', 'Cabin near Heavenly', 'Check out Sat · 10:00 AM', 'Vrbo'],
    car: ['car', 'Car · chains in the back', 'Mid-size SUV, AWD', 'Hertz · return Sat 11:45 AM', 'Expedia'],
    tix: ['ticket', 'Tickets · 3 booked', 'Snowshoe · today 10:00', 'Snowmobile Tue · ski school Wed', 'Klook'] };
  const pass = (k) => { const [ic, eb, t, s, on] = PASS[k]; return `<section class="pass on-k k-${k}" data-pass="${k}"><div class="whead"><span class="eyebrow">${eb}</span><span class="sp"></span>${I(ic, 'ico')}</div>
    <div class="ps-t">${t}</div><div class="ps-s">${s}</div><div class="perf"></div>
    <div class="booked-on"><span class="bo"><span class="ck">${I('check')}</span>Booked on ${on}</span><a class="cxl" href="#">Change or cancel ${I('ext')}</a></div></section>`; };

  /* ---------- map card ---------- */
  const mapCard = (o = {}) => `<section class="d3-map card w"><div class="d3-paper" data-paper></div>
    <div class="d3-maptools"><span class="d3-tag">${I('layers')}Paper map · real relief</span>${o.hint === false ? '' : `<span class="d3-tag soft">Tap a day: the map flies there</span>`}</div>
    <div class="d3-cap">© OpenStreetMap · relief: AWS Terrain Tiles</div></section>`;
  function mountPaper(root, o = {}) {
    const el = root.querySelector('[data-paper]'); if (!el) return null;
    const map = window.Paper.mount(el, o);
    requestAnimationFrame(() => { map.setDay(S.day, { instant: true }); setTimeout(() => window.VIEW.ready(), 900); });
    S.on('day', (i) => map.setDay(i));
    return map;
  }

  /* ---------- 1 · cockpit ---------- */
  function cockpit(size) {
    if (size === 'dk') return `${UI.top('trip')}<main class="d3c">
      <div class="d3-head"><div><div class="eyebrow">${TRIP.who} · day 3 of 8 · Mon Dec 21, 9:12 AM</div><h1 class="h1">Tahoe at Christmas</h1></div>
        <div class="d3-meta"><span class="d3-chip">${I('cal')}${TRIP.dates}</span><span class="d3-chip">${I('users')}${TRIP.party}</span>${avs}</div></div>
      <div class="d3-row">${mapCard()}<section class="wallet" aria-label="Wallet: the trip’s bookings">${['flight', 'stay', 'car', 'tix'].map(pass).join('')}</section></div>
      <section class="stubs" aria-label="The week">${DAYS.map((d) => stub(d.i, d.i === S.day)).join('')}</section></main>`;
    return `${UI.sbar()}<main class="d3p">
      <div class="p-head"><div class="eyebrow">${TRIP.name} · day 3 of 8</div><div class="h1">Monday</div><div class="sub">Dec 21 · snow day · 9:12 AM</div></div>
      <section class="stubs one">${stub(S.day, true)}</section>
      ${mapCard({ hint: false })}
      <div class="p-sec"><b>The week</b><span>Swipe · tap a day to open its ticket</span></div>
      <section class="stubs scroll">${DAYS.filter((d) => d.i !== S.day).map((d) => stub(d.i, false)).join('')}</section>
      <div class="p-sec"><b>Wallet</b><span>6 bookings, each on its partner</span></div>
      <section class="wallet col">${['tix', 'stay', 'car', 'flight'].map(pass).join('')}</section>
    </main>${UI.tabbar('trip')}`;
  }
  function mountCockpit(root, size) {
    mountStubs(root);
    mountPaper(root, size === 'dk' ? { tilt: 44, fitW: .62, fitH: .5, cy: .6 } : { tilt: 42, fitW: .48, fitH: .46, cy: .6, maxZoom: 1.7, badges: false, minor: true, pillAt: .64 });
    UI.bindDays(root, (i) => { if (size === 'dk') openStub(root, i); });
  }

  /* ---------- 2 · Book this trip: each lane is a ticket; booked ones get stamped ---------- */
  function tlane(id) {
    const L = LANES[id], booked = S.booked.has(id), B = L.booked;
    const info = `<div class="tl-info"><div class="ln-h"><span class="ktile">${I(L.icon)}</span><div class="ln-n"><b>${L.name}</b><span>${L.what}</span></div></div><div class="ln-q">${I('search')}<span>${L.search}</span></div></div>`;
    if (booked) return `<section class="tlane booked k-${L.kind}" data-lane="${id}">${info}
      <div class="tl-body"><div class="ln-booked"><div class="ln-bt">${B.line}</div><div class="ln-bm"><span>${B.when}</span><b class="tnum">${money(B.total)}</b></div></div></div>
      <div class="tl-stub"><span class="bdg ok">${I('check')}${B.direct ? 'Bought direct' : 'Booked on ' + B.on}</span><a class="cxl" href="#">Change or cancel ${I('ext')}</a><span class="ln-fine">${I('mail')}From your confirmation</span></div></section>`;
    let body = '', stubA = '';
    if (L.state === 'real') {
      const max = Math.max(...L.cal.map((c) => c.p));
      body = `<div class="tl-top">${UI.laneState(L)}</div>
        <div class="tl-real"><div class="ln-price"><span class="big">$${L.price}</span><span>per person<br>round trip</span></div>
        <div class="ln-cal" aria-label="Cheapest fares by departure day">${L.cal.map((c) => `<div class="${c.sel ? 'sel' : ''}"><i style="height:${Math.round(8 + 22 * c.p / max)}px"></i><b>$${c.p}</b><span>${c.d}</span></div>`).join('')}</div></div>`;
      stubA = `<a class="btn fill" href="#">Search on Aviasales ${I('ext')}</a><span class="ln-fine">${I('link')}Partner link · we may earn a commission. Aviasales confirms the final price.</span>`;
    } else if (L.state === 'partner') {
      body = `${UI.laneState(L)}<div class="ln-note">No price here: ${L.partner} has the live price. We won’t guess one.</div>`;
      stubA = `<a class="btn fill" href="#">Search on ${L.partner} ${I('ext')}</a><span class="ln-fine">${I('link')}Partner link · we may earn a commission</span>`;
    } else if (L.state === 'direct') {
      body = `${UI.laneState(L)}<div class="ln-note">${L.note}</div>`;
      stubA = `<a class="btn fill" href="#">Buy direct at ${L.direct} ${I('ext')}</a><span class="ln-fine">${I('shield')}The resort’s own site</span>`;
    } else {
      body = `${UI.laneState(L)}<div class="ln-note">${L.note}</div>`;
      stubA = `<div class="tl-links">${L.links.map((p, k) => `<a class="btn ${k ? 'tonal' : 'fill'} sm lk" href="#">${p} ${I('ext')}</a>`).join('')}</div><span class="ln-fine">${I('link')}Plain link${L.links.length > 1 ? 's' : ''} · we earn nothing</span>`;
    }
    return `<section class="tlane k-${L.kind}" data-lane="${id}">${info}<div class="tl-body">${body}</div>
      <div class="tl-stub">${stubA}<button class="btn text sm tl-back" data-paste="${id}">${I('clip')}Booked it? Paste it</button></div></section>`;
  }
  function book(size, q) {
    if (!q || q.get('state') !== 'all') S.booked = new Set(['lessons']);
    const head = (ph) => `<div class="${ph ? 'p-head' : 'd3-head'}"><div><div class="eyebrow">${TRIP.name}</div><h1 class="h1">Book this trip</h1>${ph ? `<div class="sub">${TRIP.dates} · ${TRIP.partyShort}</div>` : ''}</div>
      ${ph ? '' : `<div class="d3-meta"><span class="d3-chip">${I('plane')}SFO → Reno</span><span class="d3-chip">${I('cal')}${TRIP.dates}</span><span class="d3-chip">${I('users')}${TRIP.party}</span><button class="btn text">Change</button></div>`}</div>`;
    if (size === 'dk') return `${UI.top('book', { icon: 'ticket', text: 'Book this trip ·', val: `${S.booked.size} of 6` })}<main class="d3b">${head(false)}
      <div class="d3b-grid"><div class="tlanes">${LANE_ORDER.map(tlane).join('')}</div><div class="d3b-side">${UI.checklist({ cls: 'd3-ticket' })}${UI.wxPre({ cls: 'compact' })}</div></div></main>${UI.pasteSheet()}`;
    return `${UI.sbar('10:24')}<main class="d3p">${head(true)}
      <div class="p-prog"><span class="tk-n">${UI.ring(S.booked.size, 6)}</span><div><b>${S.booked.size} of 6 booked</b><span>${money(UI.bookedTotal())} so far, from your confirmations</span></div><button class="btn tonal sm" data-paste="stay">${I('clip')}Paste</button></div>
      <div class="tlanes">${LANE_ORDER.map(tlane).join('')}</div>
      <p class="p-honest">${I('spark')}Every link opens the partner’s own site. GitAway never takes payment, so changes and refunds stay with the partner.</p>
    </main>${UI.tabbar('book')}${UI.pasteSheet()}`;
  }
  function mountBook(root, size, q) {
    UI.mountWxPre(root);
    const paste = UI.bindPaste(root, {
      target: () => root.querySelector('[data-lane="stay"]'),
      done: () => landStay(root),
    });
    window.VIEW.ready();
    return paste;
  }
  function landStay(root) {
    S.booked.add('stay');
    const el = root.querySelector('[data-lane="stay"]');
    const tmp = document.createElement('div'); tmp.innerHTML = tlane('stay'); const nu = tmp.firstElementChild; el.replaceWith(nu);
    UI.M.calm(root) ? nu.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180 }) : nu.animate([{ transform: 'scale(.97)' }, { transform: 'none' }], { duration: 420, easing: 'cubic-bezier(.2,0,0,1)' });
    UI.M.stamp(nu, 'stay', { big: true, pos: UI.M.calm(root) ? 'right: 318px; top: 8px;' : 'right: 16px; top: 16px;' });
    const row = root.querySelector('[data-crow="stay"]');
    if (row) { const t2 = document.createElement('div'); t2.innerHTML = UI.checkRow('stay'); const r2 = t2.firstElementChild; row.replaceWith(r2); r2.animate([{ opacity: 0, transform: 'translateY(-4px)' }, { opacity: 1, transform: 'none' }], { duration: UI.M.calm(root) ? 180 : 420, easing: 'cubic-bezier(.2,0,0,1)' }); }
    root.querySelectorAll('[data-ticket]').forEach((t) => { UI.M.swap(t.querySelector('[data-f="ring"]'), `${UI.ring(S.booked.size, 6)}<b class="tnum">${S.booked.size} of 6</b>`); UI.M.swap(t.querySelector('[data-f="total"]'), money(UI.bookedTotal())); });
    const pr = root.querySelector('.p-prog'); if (pr) { UI.M.swap(pr.querySelector('.tk-n'), UI.ring(S.booked.size, 6)); UI.M.swap(pr.querySelector('div'), `<b>${S.booked.size} of 6 booked</b><span>${money(UI.bookedTotal())} so far, from your confirmations</span>`); }
    const bc = root.querySelector('.beacon b'); if (bc) UI.M.swap(bc, `${S.booked.size} of 6`);
  }

  /* ---------- 3 · one day on the phone: the day's ticket ---------- */
  function day(size) {
    const d = DAYS[S.day];
    return `${UI.sbar()}<main class="d3p d3day">
      <div class="p-top"><button class="xbtn" aria-label="Back">${I('back')}</button><div><div class="eyebrow">${TRIP.name} · day ${S.day + 1} of 8</div><div class="h2">${d.dow} ${d.date} · ${d.name}</div></div></div>
      <section class="daypass">
        <div class="ds-wx wide" data-wxd="${S.day}"><canvas aria-hidden="true"></canvas><div class="dpw" data-calm><span class="big tnum">${d.wx.hi}°</span><div><b>${d.wx.word}</b><span>H ${d.wx.hi}° · L ${d.wx.lo}° · gusts ${d.wx.gust} mph</span></div></div><span class="dpw-src" data-calm>Forecast · MET Norway · 6:10 AM</span></div>
        <div class="dp-map"><div class="d3-paper" data-paper></div></div>
        <div class="perf"></div>
        ${UI.rail(S.day)}
      </section>
      <div class="days-mini">${UI.dayChips()}</div>
    </main>${UI.tabbar('plan')}`;
  }
  function mountDay(root) {
    mountPaper(root, { tilt: 40, fitW: .5, fitH: .5, cy: .6, maxZoom: 2.2, badges: false, minor: true, pillAt: .64 });
    UI.bindDays(root, (i) => {
      const d = DAYS[i];
      root.querySelector('.h2').textContent = `${d.dow} ${d.date} · ${d.name}`;
      root.querySelector('[data-rail]').outerHTML = UI.rail(i);
      const w = root.querySelector('[data-wxd]');
      w.querySelector('.big').textContent = `${d.wx.hi}°`; w.querySelector('.dpw b').textContent = d.wx.word;
      w.querySelector('.dpw span').textContent = `H ${d.wx.hi}° · L ${d.wx.lo}° · gusts ${d.wx.gust} mph`;
      w.querySelector('canvas').__eng?.set(d.wx);
    });
    const c = root.querySelector('[data-wxd] canvas');
    c.__eng = window.WXE.mount(c, { host: c.parentElement, wx: DAYS[S.day].wx, seed: 77, scale: 1 });
  }

  /* ---------- 4 · paste: the book screen with the sheet up ---------- */
  function mountPaste(root, size, q) {
    const p = mountBook(root, size, q);
    const phase = q.get('phase') || 'open';
    if (phase === 'landed') { landStay(root); if (size === 'ph') root.querySelector('[data-lane="stay"]').scrollIntoView({ block: 'center' }); return; }
    p.open(root.querySelector('[data-paste="stay"]'));
    if (phase === 'read') { p.scrim.dataset.phase = 'read'; }
    if (phase === 'play') setTimeout(() => p.read(), 900);
  }

  window.DIR = {
    id: 3, name: 'Ticket line',
    notes: `<h1>Direction 3 · Ticket line <em>the trip as one line of tickets.</em></h1>
      <p><b>The week is a row of ticket stubs.</b> Each stub carries its own living weather (snow falls on Monday and Christmas Day, Thursday’s pines bend in the gusts, Wednesday’s sun turns over fresh powder). The open stub is today, inverse ink: Up next, the next leg turn by turn, Start directions. Tap another day and its ticket opens while the paper map flies there.</p>
      <ul><li><b>Map:</b> a paper pop-up map. A relief image drawn from free elevation tiles, OpenStreetMap lakes and roads, the OSRM route, tilted with CSS 3D; the labels stand up like a pop-up book. No map library, no tiles at run time.</li>
      <li><b>Bookings</b> are passes in a wallet; each shows “Booked on” and its partner’s Change or cancel.</li>
      <li><b>Book this trip</b> is a book of tickets: one per lane, stub on the right with the honest action. Pasting a confirmation stamps the ticket and tears a stub into the checklist.</li>
      <li><b>Motion:</b> phone, the stub and the sheet grow from what you tapped on a spring; desktop, a calm 180 ms fade and a 620 ms ease for the map.</li></ul>`,
    screens: {
      cockpit: { sizes: ['dk', 'ph'], render: cockpit, mount: mountCockpit, note: 'Tap a day stub: its ticket opens and the map flies to that day’s route. The phone shows today’s ticket first; the week scrolls sideways.' },
      book: { sizes: ['dk', 'ph'], render: book, mount: mountBook, note: 'Flights show a real cached price; Klook is a partner search; the cabin, the car and the snowmobile are plain links with no commission; ski school is Buy direct. Tap “Booked it? Paste it” to try the paste moment.' },
      day: { sizes: ['ph'], render: day, mount: mountDay, fixed: [], note: 'One day as its own ticket: living weather, the day’s route on the paper map, then the day on a time rail. The chips at the bottom switch days.' },
      paste: { sizes: ['dk', 'ph'], render: book, mount: (r, s, q) => mountPaste(r, s, new URLSearchParams(q.toString() + '&phase=' + (q.get('phase') || 'open'))), note: 'Press “Read it”: the email is read, its fields pop out, then (phone) the card flies into the Stay ticket and the stamp lands; on a desktop the sheet fades and the ticket fades to booked.' },
    },
  };
})();
