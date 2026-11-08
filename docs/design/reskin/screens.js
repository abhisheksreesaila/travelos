/* GitAway reskin artboards: one markup for both directions; a.css and b.css skin it.
   GA.render(screen, size, theme) returns the HTML of one screen at phone (390) or desk (1440) size.
   Sample data only (the LA trip the app already uses). Icons are drawn in Lucide's style (ISC). */
(function () {
  const P = {
    plane: '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
    bed: '<path d="M2 20v-8a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v8"/><path d="M4 10V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v4"/><path d="M12 4v6"/><path d="M2 18h20"/>',
    car: '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
    ticket: '<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M13 5v2"/><path d="M13 17v2"/><path d="M13 11v2"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    cloudsun: '<path d="M12 2v2M4.93 4.93l1.41 1.41M20 12h2M19.07 4.93l-1.41 1.41M15.947 12.65a4 4 0 0 0-5.925-4.128"/><path d="M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z"/>',
    pin: '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
    food: '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2M7 2v20M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
    see: '<circle cx="12" cy="12" r="10"/><path d="m16.24 7.76-1.804 5.411a2 2 0 0 1-1.265 1.265L7.76 16.24l1.804-5.411a2 2 0 0 1 1.265-1.265z"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    arrow: '<path d="M5 12h14M12 5l7 7-7 7"/>',
    chev: '<path d="m9 18 6-6-6-6"/>',
    back: '<path d="m15 18-6-6 6-6"/>',
    plus: '<path d="M5 12h14M12 5v14"/>',
    fork: '<circle cx="12" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9M12 12v3"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    spark: '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>',
    ext: '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    cal: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    home: '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    chat: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    key: '<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r="1.2" fill="currentColor"/>',
    wind: '<path d="M12.8 19.6A2 2 0 1 0 14 16H2M17.5 8a2.5 2.5 0 1 1 2 4H2M9.8 4.4A2 2 0 1 1 11 8H2"/>',
    camera: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
    play: '<polygon points="7 4 20 12 7 20 7 4" fill="currentColor" stroke="none"/>',
    smile: '<circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01"/>',
    nav: '<polygon points="3 11 22 2 13 21 11 13 3 11"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    wallet: '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/>',
    heart: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    umbrella: '<path d="M22 12a10.06 10.06 1 0 0-20 0Z"/><path d="M12 12v8a2 2 0 0 0 4 0M12 2v1"/>',
    mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
  };
  const I = (n, cls = '') => `<svg class="i ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n]}</svg>`;
  const KIND_ICON = { flight: 'plane', stay: 'bed', car: 'car', tix: 'ticket', weather: 'sun', food: 'food', see: 'see', ride: 'nav' };
  const G = '<svg class="i g" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.6 12.23c0-.68-.06-1.36-.18-2.02H12v3.83h5.4a4.6 4.6 0 0 1-2 3.02v2.5h3.24c1.9-1.75 2.96-4.33 2.96-7.33z"/><path fill="#34A853" d="M12 22c2.7 0 4.97-.9 6.63-2.43l-3.24-2.5c-.9.6-2.04.96-3.39.96-2.6 0-4.81-1.76-5.6-4.12H3.06v2.58A10 10 0 0 0 12 22z"/><path fill="#FBBC05" d="M6.4 13.9a6 6 0 0 1 0-3.8V7.52H3.06a10 10 0 0 0 0 8.96z"/><path fill="#EA4335" d="M12 5.98c1.47 0 2.79.5 3.83 1.5l2.87-2.87A9.6 9.6 0 0 0 12 2a10 10 0 0 0-8.94 5.52L6.4 10.1C7.19 7.74 9.4 5.98 12 5.98z"/></svg>';

  const mark = () => `<span class="mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round"><path class="mk-l" d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9M12 12v3"/><circle class="mk-a" cx="6" cy="6" r="2.6"/><circle class="mk-b" cx="18" cy="6" r="2.6"/><circle class="mk-c" cx="12" cy="18" r="2.6"/></svg></span>`;
  const brand = (cls = '') => `<a class="brand ${cls}" href="#">${mark()}<span class="wm">GitAway</span></a>`;
  const status = () => `<div class="sbar"><b>6:20</b><span class="sb-r"><i></i><i></i><i></i><em></em></span></div>`;
  const btn = (label, cls = 'fill', icon = '', after = '') => `<button class="btn ${cls}">${icon ? I(icon) : ''}<span>${label}</span>${after ? I(after) : ''}</button>`;
  const chip = (t, cls = '') => `<span class="chip ${cls}">${t}</span>`;
  const tag = (t, cls = '') => `<span class="tag ${cls}">${t}</span>`;
  const kt = (k, cls = '') => `<span class="kt k-${k} ${cls}">${I(KIND_ICON[k])}</span>`;

  /* ---------- shells ---------- */
  const tabs = (on) => {
    const t = [['home', 'Today'], ['cal', 'Plan'], ['spark', 'Ask'], ['wallet', 'Book'], ['users', 'Family']];
    return `<nav class="tabbar" aria-label="Trip">${t.map(([i, l]) => `<a class="tab ${l === on ? 'on' : ''} ${l === 'Ask' ? 'ask' : ''}" href="#">${I(i)}<span>${l}</span></a>`).join('')}</nav>`;
  };
  const topbar = (on, beacon = true) => `<header class="topbar">${brand()}
    <nav class="navpill" aria-label="Trip">${['Today', 'Plan', 'Book', 'Family'].map(l => `<a class="${l === on ? 'on' : ''}" href="#">${l}</a>`).join('')}<a class="askbtn" href="#">${I('spark')}Ask</a></nav>
    <div class="tb-r">${beacon ? `<button class="beacon">${I('plane')}<span>SK 214 boards in</span><b class="num">1:15</b></button>` : ''}<span class="avatar">AR</span></div></header>`;
  const sitebar = (on = '', cta = 'Sign in') => `<header class="sitebar">${brand()}<nav class="sitenav">${['Trips to fork', 'Plan a trip', 'For creators'].map(l => `<a class="${l === on ? 'on' : ''}" href="#">${l}</a>`).join('')}</nav><div class="tb-r">${btn(cta, 'tonal sm')}</div></header>`;

  /* ---------- widgets ---------- */
  const W = {
    upnext: (sz = 'wide') => `<article class="w w-up ${sz}"><div class="w-head"><span class="eyebrow">Up next · in 1 h 15 m</span>${kt('flight', 'on-ink')}</div>
      <h3 class="w-title">Board SK 214 to Los Angeles</h3>
      <div class="ticket-row"><div><span class="lbl">Boards</span><b class="num">7:35</b></div><div><span class="lbl">Gate</span><b class="num">B12</b></div><div><span class="lbl">Seats</span><b class="num">14A–D</b></div></div>
      <div class="w-foot"><span class="dot ok"></span>On time · leave home by 6:30</div></article>`,
    weather: (sz = 'sq') => `<article class="w w-k k-weather ${sz}"><div class="w-head"><span class="eyebrow">Santa Monica</span>${I('sun', 'wi')}</div>
      <b class="big num">75°</b><div class="w-sub">Clear all day</div><div class="w-meta num">H 77° · L 61° · UV 6</div>
      ${sz === 'wide' || sz === 'tall' ? `<div class="wx-row">${[['Fri', 'sun', 75], ['Sat', 'sun', 73], ['Sun', 'cloudsun', 70], ['Mon', 'sun', 72], ['Tue', 'sun', 77]].map(([d, i, t]) => `<span><em>${d}</em>${I(i)}<b class="num">${t}°</b></span>`).join('')}</div>` : ''}</article>`,
    flight: (sz = 'sq') => `<article class="w w-k k-flight ${sz}"><div class="w-head"><span class="eyebrow">Flight · booked</span>${I('plane', 'wi')}</div>
      <div class="route num"><b>SFO</b>${I('arrow')}<b>LAX</b></div><div class="w-sub num">8:05 → 9:32 · nonstop</div><div class="w-meta">Skylark Air 214 · on time</div></article>`,
    stay: (sz = 'sq') => `<article class="w w-k k-stay ${sz}"><div class="w-head"><span class="eyebrow">Stay · booked</span>${I('bed', 'wi')}</div>
      <h4 class="w-name">The Tidewater</h4><div class="w-sub">Check in 3:00 PM</div><div class="w-meta">Santa Monica · 4 nights · 2 rooms</div></article>`,
    car: (sz = 'wide') => `<article class="w w-k k-car ${sz}"><div class="w-head"><span class="eyebrow">Car · booked</span>${I('car', 'wi')}</div>
      <h4 class="w-name">Pick up 10:15</h4><div class="w-sub">Breeze Rentals · LAX lot C</div><div class="w-meta">Compact SUV · 2 car seats</div></article>`,
    tix: (sz = 'sq') => `<article class="w w-k k-tix ${sz}"><div class="w-head"><span class="eyebrow">Tonight · tickets</span>${I('ticket', 'wi')}</div>
      <h4 class="w-name">Pacific Park rides</h4><div class="w-sub">On the pier, 4:30 PM</div><div class="w-meta">Wristbands on Klook · not booked yet</div></article>`,
    ride: (sz = 'sq') => `<article class="w w-k k-ride ${sz}"><div class="w-head"><span class="eyebrow">Ride</span>${I('nav', 'wi')}</div>
      <b class="big num">$45–60</b><div class="w-sub">LAX → Santa Monica</div><div class="w-meta">Uber or Lyft · an estimate, not a quote</div></article>`,
  };

  /* ---------- the day ---------- */
  const DAY = [
    ['flight', '8:05', 'AM', 'Fly to Los Angeles', 'SFO 8:05 → LAX 9:32 · Gate B12', 'Booked', 8.08, 9.53],
    ['car', '10:15', 'AM', 'Pick up the car', 'Breeze Rentals · LAX lot C', 'Booked', 10.25, 10.9],
    ['food', '12:30', 'PM', 'Tacos at Leo’s', 'Venice · 20 min drive', 'Plan', 12.5, 13.5],
    ['stay', '3:00', 'PM', 'Check in · The Tidewater', 'Santa Monica · 2 rooms', 'Booked', 15, 15.6],
    ['see', '4:30', 'PM', 'Santa Monica Pier', 'Ferris wheel, then the aquarium', 'Plan', 16.5, 18.4],
    ['food', '7:00', 'PM', 'Dinner on Main St', 'Walk from the hotel', 'Plan', 19, 20.2],
  ];
  const dayChips = () => `<div class="daychips">${[['Fri', 16, 'Arrive'], ['Sat', 17, 'Beach'], ['Sun', 18, 'Griffith'], ['Mon', 19, 'Tide pools'], ['Tue', 20, 'Home']].map(([d, n, t], i) => `<button class="dchip ${i === 0 ? 'on' : ''}"><b>${d} ${n}</b><span>${t}</span></button>`).join('')}</div>`;
  const railList = () => `<ol class="rail">${DAY.map(([k, t, ap, ti, sub, st]) => `<li><time class="num"><b>${t}</b><em>${ap}</em></time><span class="rdot k-${k}"></span><div class="blk k-${k}">${kt(k, 'sm')}<div><b>${ti}</b><span>${sub}</span></div>${tag(st)}</div></li>`).join('')}<li class="now-li"><time class="num"><b>Now</b><em>6:20</em></time><span class="now-line"></span></li></ol>`;
  const gridDay = () => {
    const top = 7, h = 42;
    const hours = []; for (let x = top; x <= 21; x++) hours.push(x);
    return `<div class="dgrid" style="--hh:${h}px">${hours.map(x => `<div class="hr" style="top:${(x - top) * h}px"><span class="num">${x > 12 ? x - 12 : x} ${x >= 12 ? 'PM' : 'AM'}</span></div>`).join('')}
      ${DAY.map(([k, t, ap, ti, sub, st, s, e]) => `<div class="gb k-${k} ${e - s < 0.9 ? 'short' : ''}" style="top:${(s - top) * h + 1}px;height:${Math.max((e - s) * h - 3, 34)}px">${kt(k, 'sm')}<div><b>${ti}</b><span class="num">${t} ${ap} · ${sub}</span></div>${tag(st)}</div>`).join('')}
      <div class="nowbar" style="top:${(6.33 - top + 0.9) * h}px"></div></div>`;
  };

  /* ---------- 1. landing ---------- */
  const doorForm = () => `<div class="door-form">${[['From', 'San Francisco'], ['To', 'Los Angeles'], ['When', 'Oct 16 – 20'], ['Who', '2 adults, 2 kids']].map(([l, v]) => `<label class="fld"><span>${l}</span><b>${v}</b></label>`).join('')}${btn('Plan this trip', 'fill lg', '', 'arrow')}</div>`;
  const tripCards = () => [['santa-monica', 'Five sunny days in LA with two kids', '@twokidsonemap', '5 days · 214 forks'], ['venice', 'Venice to Malibu, slow and salty', '@saltandsoles', '4 days · 98 forks'], ['', 'Griffith, tacos and the Getty', '@marisolmaps', '3 days · 61 forks']].map(([ph, t, h, m], i) => `<a class="tcard" href="#"><div class="tc-ph ${ph ? '' : 'drawn'}" ${ph ? `style="background-image:url(assets/${ph}.jpg)"` : ''}>${ph ? '' : I('see')}<span class="tc-tag">${['Scrapbook', 'Magazine', 'Structured'][i]}</span></div><div class="tc-b"><b>${t}</b><span>${h} · ${m}</span></div></a>`).join('');
  const themeMini = (t) => `<div class="tmini tm-${t}"><div class="tm-in">${t === 'scrapbook' ? `<span class="tm-hand">Day 1 · beach!</span><span class="tm-pol" style="background-image:url(assets/santa-monica.jpg)"></span><span class="tm-pol b" style="background-image:url(assets/venice.jpg)"></span><span class="tm-stk">kid friendly</span>` : t === 'structured' ? `<span class="tm-row"><i class="k-flight"></i><i class="k-flight"></i></span><span class="tm-row"><i class="k-food"></i><i class="k-see"></i></span><span class="tm-row"><i class="k-stay"></i><i class="k-see"></i></span><span class="tm-row"><i class="k-food"></i><i class="k-car"></i></span>` : `<span class="tm-cover" style="background-image:url(assets/venice.jpg)"></span><span class="tm-mast">LOS ANGELES</span><span class="tm-hl">Five sunny days</span>`}</div></div>`;
  const landing = (s) => `<div class="page landing ${s}">${s === 'ph' ? `<header class="sitebar">${brand()}${btn('Sign in', 'tonal sm')}</header>` : sitebar()}
    <section class="hero"><span class="kicker">${I('fork')}Trips families actually took, ready to copy</span>
      <h1 class="h-hero">Fork a <em>getaway.</em></h1>
      <p class="lede">Book it, plan it with your people, and share a trip anyone can copy. <span class="ink2">All on one screen, not twelve tabs.</span></p></section>
    <section class="doors">
      <div class="door d-go"><h2 class="h-door">We’re going.</h2><p>Flights, stays, the car and the weather side by side, with one honest total.</p>${doorForm()}</div>
      <div class="door d-insp"><h2 class="h-door">Show me a trip.</h2><p>Fork a trip a real family took, then make it yours.</p><div class="tcards">${tripCards()}</div><a class="tlink" href="#">See all trips ${I('chev')}</a></div>
    </section>
    <section class="sec showcase"><h2 class="h-sec">Everything about the trip. <span class="ink2">One glance.</span></h2>
      <div class="bento">${W.upnext('wide')}${W.weather('sq')}${W.flight('sq')}${W.stay('sq')}${W.car('sq')}${W.tix('sq')}${W.ride('sq')}</div></section>
    <section class="sec themes"><h2 class="h-sec">Your plan, your way.</h2><p class="lede-s">Some people want a clean grid. Some want a scrapbook. Creators pick a look, readers can switch it.</p>
      <div class="trio">${[['scrapbook', 'Scrapbook', 'Photos, tape and handwriting.'], ['structured', 'Structured', 'A clean day grid, every time on its rail.'], ['magazine', 'Magazine', 'A cover, a story, a day per spread.']].map(([k, n, d]) => `<div class="tpick">${themeMini(k)}<b>${n}</b><span>${d}</span></div>`).join('')}</div></section>
    <section class="sec promise"><h2 class="h-sec">Not another travel site.</h2>
      <div class="three">${[['shield', 'We don’t sell trips', 'Partners keep your booking. We say on every link that we may earn a commission.'], ['search', 'No made-up prices', 'Where we have a real price, we show it with its age. Where we don’t, we say so.'], ['fork', 'Real trips, forkable', 'Copy the days a family loved into your own calendar, then change anything.']].map(([i, t, d]) => `<div class="pt">${I(i)}<b>${t}</b><span>${d}</span></div>`).join('')}</div></section>
    <footer class="foot">${brand()}<span>Terms · Privacy · For creators</span></footer></div>`;

  /* ---------- 2. sign-in ---------- */
  const tripStack = () => `<div class="savecard"><div class="sc-head">${kt('flight')}<div><b>LA with the kids</b><span class="num">SFO → LAX · Fri Oct 16 – Tue Oct 20</span></div></div><div class="sc-rows"><span>${I('users')}2 adults, 2 kids</span><span>${I('plane')}Skylark Air 214 · $1,236</span><span>${I('bed')}The Tidewater · 4 nights</span></div></div>`;
  const signin = (s) => `<div class="page signin ${s}">${s === 'ph' ? status() : ''}
    ${s === 'dk' ? `<div class="si-art"><div class="si-art-in">${brand('lg')}<h2 class="h-art">Your trip, <span class="ink2">kept in your pocket.</span></h2><div class="si-widgets">${W.flight('sq')}${W.weather('sq')}${W.stay('wide')}</div></div></div>` : ''}
    <main class="si-main"><div class="si-col">${s === 'ph' ? `<div class="si-top"><button class="xbtn" aria-label="Close">${I('x')}</button>${brand()}</div>` : ''}
      <h1 class="h-si">Sign in to save this trip</h1>
      <p class="si-lede">Plan it with your family, keep every booking in one calendar, and pick up on your phone where you left off.</p>
      ${tripStack()}
      <div class="si-btns">${btn('Continue with Google', 'tonal xl google').replace('<span>', G + '<span>')}${btn('Sign in with a passkey', 'fill xl', 'key')}</div>
      <p class="si-new">New here? The same buttons make your account. No password to remember.</p>
      <p class="si-fine">By continuing you agree to the <a href="#">Terms</a> and the <a href="#">Privacy policy</a>.</p></div></main></div>`;

  /* ---------- 3. the day ---------- */
  const day = (s) => s === 'ph' ? `<div class="page app day ph">${status()}
    <header class="apphead"><button class="iconbtn" aria-label="Trips">${I('back')}</button><div class="ah-t"><span class="eyebrow">LA with the kids</span><b>Friday</b></div><button class="avatar">AR</button></header>
    ${dayChips()}
    <div class="wgrid">${W.upnext('wide')}${W.weather('sq')}${W.flight('sq')}${W.stay('sq')}${W.car('sq')}</div>
    <section class="dayplan"><div class="dp-head"><h2>The day</h2>${btn('Add', 'tonal sm', 'plus')}</div>${railList()}</section>
    ${tabs('Today')}</div>`
    : `<div class="page app day dk">${topbar('Today')}
    <main class="daydesk"><section class="dd-main"><div class="dd-head"><div><span class="eyebrow">LA with the kids · Day 1 of 5</span><h1 class="h-day">Friday, Oct 16 <span class="ink2">· Arrive</span></h1></div><div class="dd-acts">${btn('Week', 'tonal sm', 'cal')}${btn('Add a plan', 'fill sm', 'plus')}</div></div>${dayChips()}<div class="dd-panel">${gridDay()}</div></section>
    <aside class="dd-side">${W.upnext('wide')}<div class="sidegrid">${W.weather('sq')}${W.flight('sq')}${W.stay('sq')}${W.car('sq')}</div>${W.tix('wide')}</aside></main></div>`;

  /* ---------- 4. booking ---------- */
  const fares = [['Skylark Air 214', '8:05 → 9:32', 'Nonstop · 1 h 27 m', '$1,236', 'Best for kids', 1], ['Pacific Hop 88', '6:40 → 8:02', 'Nonstop · very early', '$1,104', '', 0], ['Skylark Air 902', '9:20 → 12:05', '1 stop in SJC · 2 h 45 m', '$968', 'Cheapest', 0]];
  const bFlights = () => `<article class="bw bw-flight k-flight"><div class="bw-head">${kt('flight')}<div><h3>Flights</h3><span class="num">SFO ⇄ LAX · Oct 16 – 20 · 4 travellers</span></div><span class="live"><span class="dot ok"></span>Real prices</span></div>
    <ol class="fares">${fares.map(([n, t, d, p, b, on]) => `<li class="${on ? 'on' : ''}"><div class="f-l"><b class="num">${t}</b><span>${n} · ${d}</span>${b ? tag(b, 'soft') : ''}</div><div class="f-r"><b class="num">${p}</b><span>round trip, all 4</span></div></li>`).join('')}</ol>
    <div class="bw-foot"><span class="fine">${I('clock')}Aviasales price, checked 12 min ago. They confirm the final price.</span>${btn('Book on Aviasales', 'fill', '', 'ext')}</div></article>`;
  const honest = (k, title, what, chips, cta, extra = '') => `<article class="bw bw-honest k-${k}"><div class="bw-head">${kt(k)}<div><h3>${title}</h3><span class="num">${what}</span></div><span class="live muted">Search on partner</span></div>
    <p class="hon">No price here yet: Klook has the live ${title.toLowerCase()} and prices. We won’t guess one.</p>
    <div class="chips">${chips.map((c, i) => chip(c, i === 0 ? 'on' : '')).join('')}</div>${extra}
    <div class="bw-foot"><span class="fine">${I('link')}Partner link · we may earn a commission</span>${btn(cta, 'tonal', '', 'ext')}</div></article>`;
  const bStay = () => honest('stay', 'Stays', 'Oct 16 – 20 · 2 rooms · 2 adults, 2 kids', ['Santa Monica · beach', 'Venice', 'Downtown'], 'Search stays on Klook');
  const bStayBooked = () => `<article class="bw bw-booked k-stay"><div class="bw-head">${kt('stay')}<div><h3>Stay</h3><span class="num">Oct 16 – 20 · 2 rooms</span></div><span class="live okk">${I('check')}Booked elsewhere</span></div>
    <div class="bk-row"><b>The Tidewater, Santa Monica</b><span>Booked on Klook · on your trip as “Booked elsewhere · Klook”</span></div>
    <div class="bw-foot"><span class="fine">Wrong? You can undo it.</span>${btn('Undo', 'text sm')}</div></article>`;
  const bCar = () => honest('car', 'Cars', 'LAX · Oct 16, 10:15 → Oct 20', ['2 car seats', 'Minivan', 'Compact SUV'], 'Search cars on Klook', `<p class="tip">${I('spark')}312 families on this route skipped the car in Santa Monica and rented one for the Griffith day only.</p>`);
  const bTix = () => honest('tix', 'Tickets', 'Things to do in Los Angeles', ['Universal Studios', 'Aquarium of the Pacific', 'Getty Center (free)'], 'Find tickets on Klook');
  const checklist = () => `<aside class="bw bw-check"><span class="eyebrow">Book this trip</span><div class="ck-total"><b class="num">$1,236</b><span>known so far · flights</span></div><p class="ck-sub">Stays, the car and tickets are priced on Klook.</p>
    <ol class="ck">${[['flight', 'Flights', 'Aviasales · $1,236', 'Book', 'go'], ['stay', 'Stay', 'Booked elsewhere · Klook', '', 'done'], ['car', 'Car', 'Search on Klook', 'Search', 'todo'], ['tix', 'Tickets', 'Optional', 'Search', 'todo']].map(([k, n, s, a, st]) => `<li class="ck-${st}">${kt(k, 'sm')}<div><b>${n}</b><span>${s}</span></div>${st === 'done' ? `<span class="ck-ok">${I('check')}</span>` : btn(a, st === 'go' ? 'fill sm' : 'tonal sm', '', 'ext')}</li>`).join('')}</ol>
    <p class="ck-back">${I('spark')}Back from a partner? We’ll ask “Did you book it?” and put it on the trip.</p></aside>`;
  const book = (s) => s === 'ph' ? `<div class="page app book ph">${status()}
    <div class="totalbar"><div><span class="eyebrow">Known so far</span><b class="num">$1,236</b></div>${btn('Book this trip', 'fill', '', 'chev')}</div>
    <header class="bk-h"><h1 class="h-app">Book the trip</h1><div class="trip-pills">${chip('SFO → LAX', 'on')}${chip('Oct 16 – 20')}${chip('2 + 2 kids')}</div></header>
    <div class="bstack">${W.weather('wide')}${bFlights()}${bStayBooked()}${bCar()}${bTix()}${W.ride('wide')}</div>
    ${tabs('Book')}</div>`
    : `<div class="page app book dk">${topbar('Book')}
    <main class="bookdesk"><div class="bd-head"><div><span class="eyebrow">LA with the kids</span><h1 class="h-day">Book the trip</h1></div><div class="trip-pills">${chip('SFO → LAX', 'on')}${chip('Fri Oct 16 – Tue Oct 20')}${chip('2 adults, 2 kids')}${btn('Change', 'text sm')}</div></div>
    <div class="bd-grid"><div class="bd-a">${bFlights()}<div class="bd-wx">${W.weather('tall')}${W.ride('sq')}</div></div><div class="bd-b">${bStay()}${bCar()}</div><div class="bd-c">${checklist()}${bTix()}</div></div></main></div>`;

  /* ---------- 5. a creator's public trip, three themes ---------- */
  const TD = [
    ['Santa Monica, slowly', 'santa-monica', 'We dropped bags and went straight to the sand. The kids still talk about the Ferris wheel at dusk.', [['8:05', 'flight', 'Fly in, rent the car'], ['12:30', 'food', 'Tacos at Leo’s'], ['4:30', 'see', 'Santa Monica Pier']]],
    ['Griffith and the stars', '', 'Go to the Observatory at 4 so you get both daylight and the planetarium show.', [['9:30', 'see', 'Griffith Park pony rides'], ['1:00', 'food', 'Picnic at Fern Dell'], ['4:00', 'see', 'Griffith Observatory']]],
    ['Venice, wheels and murals', 'venice', 'Rent bikes at the north end; the path is flat and the murals keep everyone pedalling.', [['10:00', 'see', 'Bikes on the Strand'], ['12:30', 'food', 'Abbot Kinney lunch'], ['5:30', 'see', 'Venice canals walk']]],
  ];
  const creator = () => `<div class="creator"><span class="cav">P</span><div><b>Priya &amp; Dev</b><span>@twokidsonemap · family travel</span></div></div>`;
  const tpicker = (t) => `<div class="tpicker" role="tablist" aria-label="Plan look">${[['scrapbook', 'Scrapbook'], ['structured', 'Structured'], ['magazine', 'Magazine']].map(([k, n]) => `<button role="tab" class="${k === t ? 'on' : ''}" aria-selected="${k === t}">${n}${k === 'scrapbook' ? '<i class="pick" title="Creator’s pick"></i>' : ''}</button>`).join('')}</div>`;
  const tripTop = (s, t) => `<header class="sitebar pub">${brand()}${s === 'dk' ? tpicker(t) : ''}<div class="tb-r">${btn('Sign in', 'text sm')}${s === 'dk' ? btn('Fork this trip', 'fill sm', 'fork') : ''}</div></header>${s === 'ph' ? `<div class="tp-wrap">${tpicker(t)}</div>` : ''}`;
  const source = () => `<a class="source" href="#"><span class="src-play">${I('play')}</span><div><b>From our video: LA with kids, 5 days</b><span>YouTube · 12:41 · watch it on their channel</span></div>${I('ext')}</a>`;
  const scrap = (s) => `<main class="th th-scrap"><div class="sc-hero"><span class="hand h1">Five sunny days in LA with two kids</span>${creator()}<div class="stickers"><span class="stk s1">kid friendly</span><span class="stk s2">beach days</span><span class="stk s3">no car day 3</span></div></div>
    <svg class="squiggle" viewBox="0 0 600 80" preserveAspectRatio="none"><path d="M4 60 C 90 10, 160 75, 250 38 S 420 8, 500 46 S 580 70, 596 30" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="2 9" stroke-linecap="round"/></svg>
    <div class="sc-days">${TD.map(([t, ph, note, items], i) => `<section class="sc-day"><div class="pol ${i % 2 ? 'r' : 'l'}"><span class="tape"></span>${ph ? `<span class="pic" style="background-image:url(assets/${ph}.jpg)"></span>` : `<span class="pic drawn"><svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect width="400" height="300" fill="#1d2a4d"/><rect y="150" width="400" height="150" fill="#f2a65a"/><rect y="190" width="400" height="110" fill="#e07a4f"/><circle cx="320" cy="70" r="26" fill="#ffd43b"/><g fill="#fff" opacity=".8"><circle cx="60" cy="50" r="2"/><circle cx="120" cy="90" r="1.6"/><circle cx="210" cy="40" r="2"/><circle cx="250" cy="110" r="1.4"/><circle cx="30" cy="120" r="1.5"/></g><path d="M0 230 C 80 170, 150 180, 210 200 S 330 160, 400 190 V300 H0Z" fill="#3c5a3a"/><path d="M140 196 h120 v-14 h-120z" fill="#efe6d6"/><path d="M160 182 a40 40 0 0 1 80 0z" fill="#9aa7b5"/><path d="M188 150 h24 v-8 h-24z" fill="#efe6d6"/><rect x="196" y="128" width="8" height="16" fill="#9aa7b5"/><path d="M0 260 C 100 225, 200 245, 400 230 V300 H0Z" fill="#2c4430"/></svg></span>`}<span class="cap hand">Day ${i + 1} · ${t}</span></div>
      <div class="page-note"><span class="hand dnum">Day ${i + 1}</span><p class="hand note">${note}</p><ul class="sc-list">${items.map(([tm, k, n]) => `<li><span class="num">${tm}</span>${kt(k, 'sm')}<b>${n}</b></li>`).join('')}</ul></div></section>`).join('')}</div>
    ${source()}</main>`;
  const structured = (s) => `<main class="th th-struct"><div class="st-hero"><div><span class="eyebrow">Los Angeles · 5 days · Oct, any year</span><h1 class="h-trip">Five sunny days in LA with two kids</h1>${creator()}</div>
    <div class="stats">${[['5', 'days'], ['14', 'stops'], ['3', 'kid picks'], ['214', 'forks']].map(([n, l]) => `<div><b class="num">${n}</b><span>${l}</span></div>`).join('')}</div></div>
    <div class="st-grid">${TD.concat([['Tide pools at Point Dume', '', '', [['8:30', 'see', 'Point Dume tide pools'], ['12:00', 'food', 'Malibu Farm lunch'], ['3:00', 'see', 'Zuma Beach']]], ['Getty, then home', '', '', [['10:00', 'see', 'Getty Center'], ['1:30', 'food', 'Lunch at the Getty'], ['5:15', 'flight', 'Fly home']]]]).map(([t, ph, note, items], i) => `<section class="st-day"><header><span class="st-n">Day ${i + 1}</span><b>${t}</b></header><ol>${items.map(([tm, k, n]) => `<li><time class="num">${tm}</time><div class="blk k-${k}">${kt(k, 'sm')}<b>${n}</b></div></li>`).join('')}</ol></section>`).join('')}</div>
    ${source()}</main>`;
  const magazine = (s) => `<main class="th th-mag"><div class="mg-cover"><span class="mg-photo" style="background-image:url(assets/venice.jpg)"></span><div class="mg-cov-t"><span class="mg-mast">GitAway · Los Angeles</span><h1 class="mg-hl">Five sunny days, <em>two small explorers.</em></h1><p class="mg-dek">A family’s week between the pier, the stars and the canals, told day by day. Fork it and make it yours.</p>${creator()}</div></div>
    <div class="mg-body"><nav class="mg-toc"><span class="eyebrow">In this trip</span>${['Santa Monica, slowly', 'Griffith and the stars', 'Venice, wheels and murals', 'Tide pools at Point Dume', 'Getty, then home'].map((t, i) => `<a href="#"><b class="num">0${i + 1}</b><span>${t}</span></a>`).join('')}</nav>
    <article class="mg-story">${TD.slice(0, 2).map(([t, ph, note, items], i) => `<section class="mg-day"><span class="mg-num num">0${i + 1}</span><h2>${t}</h2><p class="${i === 0 ? 'dropcap' : ''}">${note} ${i === 0 ? 'Park once at the pier lot, walk everywhere after, and let the afternoon go long.' : 'Pack a sweater: the hill gets cold once the sun drops.'}</p><ul class="mg-list">${items.map(([tm, k, n]) => `<li>${kt(k, 'sm')}<span class="num">${tm}</span><b>${n}</b></li>`).join('')}</ul>${i === 0 ? `<blockquote class="pull">“The Ferris wheel at dusk was the whole trip for our six-year-old.”</blockquote>` : ''}</section>`).join('')}${source()}</article></div></main>`;
  const trip = (s, t = 'scrapbook') => `<div class="page pub ${s} theme-${t}">${tripTop(s, t)}${t === 'scrapbook' ? scrap(s) : t === 'structured' ? structured(s) : magazine(s)}
    ${s === 'ph' ? `<div class="forkbar"><div><b>Fork this trip</b><span>Copy the days into your calendar</span></div>${btn('Fork', 'fill', 'fork')}</div>` : ''}</div>`;

  /* ---------- 6. for creators ---------- */
  const creators = (s) => `<div class="page creators ${s}">${s === 'ph' ? `<header class="sitebar">${brand()}${btn('Sign in', 'tonal sm')}</header>` : sitebar('For creators')}
    <section class="cr-hero"><div class="cr-copy"><span class="kicker">${I('spark')}For travel creators</span><h1 class="h-hero cr">Your post, <em>forkable.</em></h1>
      <p class="lede">Paste your blog, YouTube video or Instagram caption. GitAway drafts the days, you fix what’s off, and families copy your trip into their own plans.</p>
      <div class="paste"><label class="fld big"><span>Link to your post, or its text</span><b class="ph">youtube.com/watch?v=…</b></label>${btn('Draft my trip', 'fill lg', 'spark')}</div>
      <p class="fine">Free. You tick “This is my post” before anything goes public. Take it down any time.</p></div>
      <div class="cr-demo"><div class="cr-draft"><span class="eyebrow">Drafted from your video · 38 s</span><h3>A family week in Los Angeles</h3>${[['flight', '8:05', 'Fly in, rent the car'], ['see', '4:30', 'Santa Monica Pier'], ['food', '7:00', 'Dinner on Main St'], ['see', 'Day 2', 'Griffith Observatory']].map(([k, t, n]) => `<div class="cd-row k-${k}">${kt(k, 'sm')}<span class="num">${t}</span><b>${n}</b></div>`).join('')}<div class="cd-foot">${chip('Fix 2 times', 'on')}${chip('Add photos')}</div></div></div></section>
    <section class="sec cr-three"><div class="three">${[['spark', 'Under a minute', 'Paste, glance at the draft, publish. You only fix what’s off.'], ['wallet', 'Flights from your trips pay you', 'Add your Travelpayouts marker and Aviasales pays you for flights booked from your trips.'], ['link', 'It links back to you', 'Every trip opens with a source card that sends readers to your post, with your name on it.']].map(([i, t, d]) => `<div class="pt">${I(i)}<b>${t}</b><span>${d}</span></div>`).join('')}</div></section>
    <section class="sec themes"><h2 class="h-sec">Pick the look. <span class="ink2">Readers can switch it.</span></h2>
      <div class="trio">${[['scrapbook', 'Scrapbook', 'Your photos, taped in.'], ['structured', 'Structured', 'Every stop on a time rail.'], ['magazine', 'Magazine', 'A cover and a story.']].map(([k, n, d]) => `<div class="tpick">${themeMini(k)}<b>${n}</b><span>${d}</span></div>`).join('')}</div></section>
    <section class="sec terms"><h2 class="h-sec">The terms, in plain words.</h2><div class="three">${[['What we show', 'Your name, the days, stops and tips you approve, and a link to your post.'], ['What we never show', 'Confirmation numbers, your family’s names, exact addresses, photo locations.'], ['What you earn', 'Flight commissions through your own marker. Stays and tickets support GitAway for now; we say so on every trip.']].map(([t, d]) => `<div class="pt plain"><b>${t}</b><span>${d}</span></div>`).join('')}</div></section>
    <footer class="foot">${brand()}<span>Terms · Privacy · Creator terms</span></footer></div>`;

  window.GA = {
    I, screens: ['landing', 'signin', 'day', 'book', 'trip', 'creators'],
    render(screen, size, theme) {
      return ({ landing, signin, day, book, trip, creators })[screen](size, theme);
    },
  };
})();
