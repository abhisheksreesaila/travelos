/* The template trip: the founder's family to Lake Tahoe, Sat Dec 19 to Sat Dec 26 2026, SFO to Reno, 2 adults and kids 8 and 11.
   Places and drive times are real (data/geo.js: OpenStreetMap, OSRM). Weather, prices, confirmation numbers and the
   carriers' times are sample data, labelled as such in the README. */
(function () {
  const G = window.GEO;
  const R = G.routes;
  const mi = (km) => Math.round(km * 0.621371 * 10) / 10;
  const hm = (m) => (m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')} min` : `${m} min`);
  const short = (m) => (m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} m` : `${m} min`);
  const leg = (r, i = 0) => R[r].alts[0].legs[i];

  const TRIP = {
    name: 'Tahoe at Christmas', who: 'Abhi’s family', party: '2 adults · kids 8 and 11', partyShort: '2 adults, 2 kids',
    dates: 'Sat Dec 19 – Sat Dec 26', nights: 7, from: 'SFO', to: 'RNO', town: 'South Lake Tahoe',
    nowDay: 2, nowTime: '9:12 AM', countdown: 43, today: 'Fri Nov 6',
  };

  // Weather per day (sample forecast). type drives the living widget: sun | cloud | snow | flurry | wind
  const WX = [
    { ground: 0.3, type: 'sun', hi: 41, lo: 22, wind: 6, gust: 0, snow: '', word: 'Clear', line: 'Clear and calm. An easy drive over Spooner Summit.' },
    { ground: 0.35, type: 'cloud', hi: 38, lo: 25, wind: 10, gust: 18, snow: '1 in tonight', word: 'Clouds, snow late', line: 'Grey afternoon. Snow starts around 8 PM.' },
    { ground: 0.9, type: 'snow', hi: 31, lo: 21, wind: 15, gust: 30, snow: '6–9 in', word: 'Snow, 6–9 in', line: 'Chains likely on US 50 and CA 89.' },
    { ground: 0.95, type: 'flurry', hi: 33, lo: 17, wind: 8, gust: 14, snow: '1–2 in', word: 'Flurries ending', line: 'Light flurries until noon, then breaks of sun.' },
    { ground: 0.9, type: 'sun', hi: 36, lo: 15, wind: 3, gust: 0, snow: '', word: 'Sunny, fresh powder', line: 'Bluebird powder day. Cold start: 15° at 8 AM.' },
    { ground: 0.75, type: 'wind', hi: 39, lo: 24, wind: 22, gust: 40, snow: '', word: 'Windy', line: 'Gusts to 40 mph on the ridges. The gondola may pause.' },
    { ground: 0.95, type: 'snow', hi: 34, lo: 22, wind: 9, gust: 16, snow: '1–3 in', word: 'Light snow', line: 'A white Christmas: light snow most of the day.' },
    { ground: 0.7, type: 'sun', hi: 40, lo: 19, wind: 7, gust: 0, snow: '', word: 'Clear', line: 'Dry roads back to Reno.' },
  ];

  // Lanes: what can be booked, its honest state before booking, and its "Booked on" state after.
  const LANES = {
    flight: { id: 'flight', kind: 'flight', icon: 'plane', name: 'Flights', what: 'SFO ⇄ Reno', search: 'Sat Dec 19 – Sat Dec 26 · 2 adults, 2 kids',
      state: 'real', partner: 'Aviasales', price: 148, priceSeen: '3 h ago',
      cal: [{ d: 'Thu 17', p: 156 }, { d: 'Fri 18', p: 171 }, { d: 'Sat 19', p: 148, sel: true }, { d: 'Sun 20', p: 139 }, { d: 'Mon 21', p: 132 }],
      booked: { on: 'United', via: 'Aviasales', total: 612, conf: '7KQ', line: 'Nonstop both ways · 4 seats', when: 'Sat Dec 19 · 12:40 PM' }, place: 'rno' },
    stay: { id: 'stay', kind: 'stay', icon: 'cabin', name: 'Stay', what: 'A cabin near Heavenly', search: 'South Lake Tahoe · Dec 19–26 · 7 nights · 2 adults, kids 8 and 11',
      state: 'plain', links: ['Vrbo', 'Airbnb', 'Expedia'], note: 'Klook has 6 hotels here and no cabins, so these are plain links.',
      booked: { on: 'Vrbo', total: 2846, conf: '4821', line: '3 bedrooms · hot tub · 7 nights', when: 'Check in Sat 4:00 PM' }, place: 'cabin' },
    car: { id: 'car', kind: 'car', icon: 'car', name: 'Car', what: 'An SUV with snow chains', search: 'Reno airport · Dec 19, 2:20 PM – Dec 26, 11:45 AM · SUV · snow chains',
      state: 'plain', links: ['Expedia'], note: 'The search asks for an SUV with chains (Expedia’s snow-chain option).',
      booked: { on: 'Expedia', op: 'Hertz', total: 512, conf: '0193', line: 'Mid-size SUV, AWD · chains requested', when: 'Pick up Sat 2:20 PM' }, place: 'rno' },
    snowshoe: { id: 'snowshoe', kind: 'tix', icon: 'snowshoe', name: 'Snowshoeing', what: 'Rentals and a self-guided trail', search: 'Lake Tahoe · Mon Dec 21 · 4 people',
      state: 'partner', partner: 'Klook',
      booked: { on: 'Klook', total: 156, conf: '55K2', line: 'Snowshoe rental + self-guided tour · 4', when: 'Mon Dec 21 · 10:00 AM' }, place: 'taylor' },
    snowmobile: { id: 'snowmobile', kind: 'tix', icon: 'snowmobile', name: 'Snowmobile tour', what: 'Two hours above the lake', search: 'Lake Tahoe · Tue Dec 22 · 4 people',
      state: 'plain', links: ['GetYourGuide'], note: 'GetYourGuide has these tours. No partner deal yet, so it’s a plain link.',
      booked: { on: 'GetYourGuide', total: 530, conf: '8XW1', line: '2-hour tour · 2 sleds, kids ride along', when: 'Tue Dec 22 · 11:00 AM' }, place: 'zephyr' },
    lessons: { id: 'lessons', kind: 'tix', icon: 'ski', name: 'Ski lessons', what: 'Kids’ ski school, 2 days', search: 'Heavenly · kids 8 and 11 · Sun Dec 20 and Wed Dec 23',
      state: 'direct', direct: 'Heavenly', note: 'Ski schools sell only on their own site. No middle-man, nothing for us.',
      booked: { on: 'Heavenly', direct: true, total: 1156, conf: 'H-209', line: 'Group lessons · 9:00–3:00 · 2 kids', when: 'Sun Dec 20 · 8:45 AM' }, place: 'heavenly' },
  };
  const LANE_ORDER = ['flight', 'stay', 'car', 'snowshoe', 'snowmobile', 'lessons'];

  const d1 = leg('d1', 0), d1b = leg('d1', 1), d3 = leg('d3'), d4 = leg('d4'), d5a = leg('d5', 1), d5b = leg('d5', 2), d6 = leg('d6'), d8 = leg('d8'), d2 = leg('d2');
  // a plan: t (time), kind, icon, title, sub, place, lane (its booking), drive (a leg before it)
  const DAYS = [
    { dow: 'Sat', d: 19, name: 'Arrive', route: 'd1', stops: ['rno', 'grocery', 'cabin'], plans: [
      { t: '10:30 AM', kind: 'ride', icon: 'car', st: 'Leave for SFO', title: 'Leave home for SFO', sub: 'Long-term parking, Lot D' },
      { t: '12:40 PM', kind: 'flight', icon: 'plane', st: 'Fly to Reno', title: 'Fly SFO → Reno', sub: 'United · nonstop · lands 1:47 PM', lane: 'flight', place: 'rno', dur: 67 },
      { t: '2:20 PM', kind: 'car', icon: 'car', st: 'Pick up SUV', title: 'Pick up the SUV', sub: 'Hertz at the airport · chains requested', lane: 'car', place: 'rno' },
      { t: '2:45 PM', drive: { min: d1.min, km: d1.km, via: 'I-580 S, US 50 W over Spooner Summit', to: 'grocery' } },
      { t: '4:05 PM', kind: 'food', icon: 'cart', st: 'Groceries', title: 'Groceries', sub: 'On US 50, 3 min from the cabin', place: 'grocery' },
      { t: '4:30 PM', kind: 'stay', icon: 'cabin', st: 'Check in', title: 'Check in at the cabin', sub: 'Door code arrives at 3 PM', lane: 'stay', place: 'cabin' },
    ] },
    { dow: 'Sun', d: 20, name: 'Ski school', route: 'd2', stops: ['cabin', 'heavenly'], plans: [
      { t: '8:40 AM', drive: { min: Math.max(d2.min, 3), km: d2.km, via: 'Ski Run Blvd', to: 'heavenly' } },
      { t: '8:45 AM', kind: 'tix', icon: 'ski', st: 'Ski school', title: 'Kids’ ski school, day 1', sub: 'Heavenly · California Lodge · until 3:00', lane: 'lessons', place: 'heavenly' },
      { t: '12:30 PM', kind: 'food', icon: 'food', st: 'Lunch', title: 'Lunch at the lodge', sub: 'Adults’ break' },
      { t: '6:00 PM', kind: 'food', icon: 'food', st: 'Chili night', title: 'Dinner at the cabin', sub: 'Chili night' },
    ] },
    { dow: 'Mon', d: 21, name: 'Snow day', route: 'd3', stops: ['cabin', 'taylor'], plans: [
      { t: '9:35 AM', drive: { min: d3.min, km: d3.km, via: 'US 50, then CA 89 at the Y', to: 'taylor', chains: 'R2 chain control on CA 89' } },
      { t: '10:00 AM', kind: 'tix', icon: 'snowshoe', st: 'Snowshoe', title: 'Snowshoe at Taylor Creek', sub: 'Rentals + a self-guided trail', lane: 'snowshoe', place: 'taylor' },
      { t: '1:00 PM', kind: 'food', icon: 'food', st: 'Hot chocolate', title: 'Hot chocolate and lunch', sub: 'Back at the cabin' },
      { t: '3:00 PM', kind: 'stay', icon: 'cabin', st: 'Hot tub', title: 'Board games, hot tub', sub: 'Snow all afternoon', place: 'cabin' },
    ] },
    { dow: 'Tue', d: 22, name: 'Snowmobile', route: 'd4', stops: ['cabin', 'zephyr'], plans: [
      { t: '10:40 AM', drive: { min: d4.min, km: d4.km, via: 'Pioneer Trail, US 50', to: 'zephyr' } },
      { t: '11:00 AM', kind: 'tix', icon: 'snowmobile', st: 'Snowmobile', title: 'Snowmobile tour', sub: 'Zephyr Cove · 2 h · kids ride along', lane: 'snowmobile', place: 'zephyr' },
      { t: '1:30 PM', kind: 'food', icon: 'food', st: 'Lake lunch', title: 'Lunch by the lake', sub: 'Zephyr Cove' },
    ] },
    { dow: 'Wed', d: 23, name: 'Powder day', route: 'd5', stops: ['cabin', 'heavenly', 'emerald'], plans: [
      { t: '8:45 AM', kind: 'tix', icon: 'ski', st: 'Ski school', title: 'Kids’ ski school, day 2', sub: 'Heavenly · until 3:00', lane: 'lessons', place: 'heavenly' },
      { t: '3:30 PM', drive: { min: d5a.min, km: d5a.km, via: 'US 50, CA 89', to: 'emerald' } },
      { t: '4:00 PM', kind: 'see', icon: 'see', st: 'Emerald Bay', title: 'Emerald Bay at sunset', sub: 'Inspiration Point · CA 89 can close for snow', place: 'emerald' },
    ] },
    { dow: 'Thu', d: 24, name: 'Christmas Eve', route: 'd6', stops: ['cabin', 'gondola'], plans: [
      { t: '10:50 AM', drive: { min: d6.min, km: d6.km, via: 'Ski Run Blvd, Pioneer Trail', to: 'gondola' } },
      { t: '11:00 AM', kind: 'tix', icon: 'ticket', st: 'Gondola', title: 'Gondola ride', sub: 'Heavenly Village · pauses in strong gusts', place: 'gondola' },
      { t: '6:00 PM', kind: 'food', icon: 'food', st: 'Dinner', title: 'Christmas Eve dinner', sub: 'At the cabin' },
    ] },
    { dow: 'Fri', d: 25, name: 'Christmas', route: null, stops: ['cabin'], plans: [
      { t: '9:00 AM', kind: 'stay', icon: 'gift', st: 'Presents', title: 'Presents at the cabin', sub: 'Slow morning', place: 'cabin' },
      { t: '1:00 PM', kind: 'see', icon: 'sled', st: 'Sledding', title: 'Sledding out back', sub: 'Snow boots by the door', place: 'cabin' },
    ] },
    { dow: 'Sat', d: 26, name: 'Home', route: 'd8', stops: ['cabin', 'rno'], plans: [
      { t: '10:00 AM', kind: 'stay', icon: 'cabin', st: 'Check out', title: 'Check out', sub: 'Keys in the lockbox', lane: 'stay', place: 'cabin' },
      { t: '10:15 AM', drive: { min: d8.min, km: d8.km, via: 'US 50 E, I-580 N', to: 'rno' } },
      { t: '11:45 AM', kind: 'car', icon: 'car', st: 'Return SUV', title: 'Return the SUV', sub: 'Hertz at the airport', lane: 'car', place: 'rno' },
      { t: '1:30 PM', kind: 'flight', icon: 'plane', st: 'Fly home', title: 'Fly Reno → SFO', sub: 'United · lands 2:42 PM', lane: 'flight', place: 'rno' },
    ] },
  ].map((d, i) => Object.assign(d, { i, wx: WX[i], date: `Dec ${d.d}` }));

  // The next leg (cockpit "now": Mon Dec 21, 9:12 AM): cabin to Taylor Creek, turn by turn from OSRM's steps.
  const stepIcon = (s) => (s.type === 'depart' ? 'straight' : s.mod.includes('left') ? 'turnl' : s.mod.includes('right') ? 'turnr' : 'straight');
  const legSteps = (l) => l.steps.map((s) => ({ icon: stepIcon(s), road: s.road.replace('CA 89', 'Emerald Bay Rd (CA 89)').replace('US 50', 'Lake Tahoe Blvd (US 50)'), mi: mi(s.km), min: s.min,
    verb: s.type === 'depart' ? 'Head down' : s.mod.includes('left') ? 'Turn left on' : s.mod.includes('right') ? 'Turn right on' : 'Continue on' }));
  const NEXT = { from: 'Cabin', to: 'Taylor Creek', min: d3.min, mi: mi(d3.km), leave: '9:35 AM', arrive: '9:53 AM', inMin: 23,
    steps: legSteps(d3), chains: 'R2 chain control on CA 89 (sample)', alt: 'If CA 89 closes: Fallen Leaf Lake Rd trail, 11 min' };
  // Day 1's long leg, for the Reno arrival
  const ARRIVE = { from: 'Reno airport', to: 'Cabin', min: d1.min + d1b.min, mi: mi(d1.km + d1b.km),
    steps: [
      { icon: 'straight', verb: 'Take', road: 'I-580 S / US 395 S to Carson City', mi: 31.4, min: 35 },
      { icon: 'turnr', verb: 'Turn right on', road: 'US 50 W over Spooner Summit (7,146 ft)', mi: 22.2, min: 36 },
      { icon: 'straight', verb: 'Continue on', road: 'Lake Tahoe Blvd through Stateline', mi: 1.3, min: 3 },
      { icon: 'turnl', verb: 'Turn left on', road: 'Ski Run Blvd to the cabin', mi: 1.0, min: 2 },
    ] };

  const AROUND = [{ icon: 'cart', name: 'Groceries', min: 4 }, { icon: 'gas', name: 'Gas', min: 3 }, { icon: 'cross', name: 'Urgent care', min: 6 }];

  // The confirmation the paste moment reads (a sample Vrbo email; numbers masked as the app does)
  const PASTE = {
    from: 'Vrbo <noreply@vrbo.com>', subject: 'Your booking is confirmed: Cabin near Heavenly',
    body: 'Hi Abhi, your stay is confirmed!\nCabin near Heavenly · South Lake Tahoe, CA\nCheck-in: Sat, Dec 19, 2026 after 4:00 PM\nCheck-out: Sat, Dec 26, 2026 by 10:00 AM\nGuests: 2 adults, 2 children\nTotal paid: $2,846.00\nReservation ID: HA-7Q4821\nManage your trip at vrbo.com/trips',
    fields: [{ k: 'Stay', v: 'Cabin near Heavenly' }, { k: 'Dates', v: 'Dec 19 – 26 · 7 nights' }, { k: 'Guests', v: '2 adults, 2 kids' }, { k: 'Total', v: '$2,846' }, { k: 'Booked on', v: 'Vrbo' }],
  };

  const money = (n) => '$' + n.toLocaleString('en-US');
  window.TRIP = { TRIP, WX, DAYS, LANES, LANE_ORDER, NEXT, ARRIVE, AROUND, PASTE, mi, hm, short, money };
})();
