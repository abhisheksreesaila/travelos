// The sample trip every prototype tells (the same LA trip the reskin uses). Sample data only.
// Kinds: flight stay car tix see food. `place` keys are what each scene maps to its own coordinates.
export const TRIP = {
  title: 'Five sunny days in LA', titleEm: 'with two kids.',
  who: 'Priya & Dev', handle: '@twokidsonemap', initial: 'P',
  story: 'We came for the beach and stayed for the stars. Every stop, nap and taco is here.',
  meta: ['5 days', 'Los Angeles', 'October', '2 adults, 2 kids (4 and 7)'],
  thanks: 1284, forks: 214,
};

export const DAYS = [
  { d: 'Fri 16', tag: 'Pier', title: 'Santa Monica, slowly', wx: ['sun', 75, 77, 61, 'Clear all day'],
    note: 'We dropped bags and went straight to the sand. The kids still talk about the Ferris wheel at dusk.',
    stops: [
      ['8:05', 'AM', 'flight', 'Land at LAX, pick up the car', 'SK 214 · the rental desk is in the garage', 'lax'],
      ['12:30', 'PM', 'food', 'Tacos at Leo’s', 'Al pastor for everyone; go before noon', 'tacos'],
      ['3:00', 'PM', 'stay', 'Check in · The Tidewater', 'Santa Monica · 2 rooms, 4 nights', 'tidewater'],
      ['4:30', 'PM', 'see', 'Santa Monica Pier', 'The Ferris wheel at dusk, then the aquarium', 'pier'],
    ] },
  { d: 'Sat 17', tag: 'Stars', title: 'Griffith and the stars', wx: ['sun', 73, 75, 60, 'Sunny, breezy up top'],
    note: 'Go to the Observatory at 4, so you get daylight and the planetarium show.',
    stops: [
      ['9:30', 'AM', 'see', 'Griffith Park pony rides', 'Ages 1 and up · bring cash', 'pony'],
      ['1:00', 'PM', 'food', 'Picnic at Fern Dell', 'Shade and a creek for little feet', 'ferndell'],
      ['4:00', 'PM', 'see', 'Griffith Observatory', 'Free; the planetarium show is $10', 'observatory'],
    ] },
  { d: 'Sun 18', tag: 'Venice', title: 'Venice, wheels and murals', wx: ['cloudsun', 70, 71, 60, 'Morning cloud, sun by 11'],
    note: 'No car today. Rent bikes with a kid seat and ride the beach path south.',
    stops: [
      ['10:00', 'AM', 'see', 'Bikes on the beach path', 'Kid seats at the rental by the pier', 'bikes'],
      ['12:30', 'PM', 'food', 'Lunch on Abbot Kinney', 'Split plates, no wait before 12:30', 'abbot'],
      ['3:00', 'PM', 'see', 'Venice canals walk', 'Ducks, little bridges, painted doors', 'canals'],
    ] },
  { d: 'Mon 19', tag: 'Tide pools', title: 'Tide pools at Point Dume', wx: ['sun', 72, 74, 59, 'Clear, cool morning'],
    note: 'Low tide was 9:10. Get there by 8:30; the pools close up by 11.',
    stops: [
      ['8:30', 'AM', 'see', 'Point Dume tide pools', 'Water shoes; look under the ledges', 'dume'],
      ['12:00', 'PM', 'food', 'Lunch at Malibu Farm', 'On the pier, with a kids menu', 'malibufarm'],
      ['3:00', 'PM', 'see', 'Zuma Beach', 'Lifeguard tower 8, gentle waves', 'zuma'],
    ] },
  { d: 'Tue 20', tag: 'Getty', title: 'The Getty, then home', wx: ['sun', 77, 79, 62, 'Warm and clear'],
    note: 'The Getty is free, and the tram up the hill was the kids’ favourite ride of the week.',
    stops: [
      ['10:00', 'AM', 'see', 'The Getty Center', 'Free; the tram up is the fun part', 'getty'],
      ['1:30', 'PM', 'food', 'Lunch at the Getty', 'The café terrace has the view', 'gettylunch'],
      ['3:30', 'PM', 'car', 'Return the car at LAX', 'Fill up on Sepulveda first', 'laxcar'],
      ['5:15', 'PM', 'flight', 'Fly home', 'SK 213 · leaves from gate 4', 'laxfly'],
    ] },
];

// Booking is links only: a partner link where one is connected (Aviasales, Klook), else a plain link that earns nothing.
export const LANE = [
  ['flight', 'Flights', 'Real prices from $312', 'Aviasales · checked 12 min ago. They confirm the final price.', 'Partner link · we may earn a commission'],
  ['stay', 'Stay', 'The Tidewater, Santa Monica', 'Search stays on Klook. No price here; Klook has the live one.', 'Partner link · we may earn a commission'],
  ['car', 'Car', 'LAX · Oct 16 → 20 · 2 car seats', 'Search cars on Expedia', 'Plain link · we earn nothing'],
  ['tix', 'Tickets', 'Aquarium, planetarium show', 'Find tickets on Klook', 'Partner link · we may earn a commission'],
];

// Where the forks went: a git graph, newest first. A fork branches from the row named in `from`.
export const FORKS = [
  { id: 'u2', lane: 0, from: 'p1', who: 'Priya & Dev', commit: true, text: 'added the low-tide tip to day 4', meta: '2 days ago' },
  { id: 'f1', lane: 1, from: 'p1', who: 'Ana & Luis', ini: 'A', av: '#0F766E', home: 'Toronto', text: 'forked it · seven days, with two in San Diego', meta: 'September · 18 forks of their own' },
  { id: 'f2', lane: 2, from: 'f1', who: 'The Okafors', ini: 'O', av: '#4338CA', home: 'London', text: 'forked Ana & Luis · swapped the Getty for Universal', meta: 'October · 4 forks' },
  { id: 'p1', lane: 0, from: 'p0', who: 'Priya & Dev', commit: true, text: 'added the Griffith pony rides', meta: 'August' },
  { id: 'f4', lane: 2, from: 'f3', who: 'Mei & Jun', ini: 'M', av: '#C92A5E', home: 'Sydney', text: 'forked Marisol · added a Disneyland day', meta: 'July · 9 forks' },
  { id: 'f3', lane: 1, from: 'p0', who: 'Marisol', ini: 'M', av: '#C2410C', home: 'Mexico City', text: 'forked it · three days: Griffith, tacos and the Getty', meta: 'June · 61 forks' },
  { id: 'p0', lane: 0, who: 'Priya & Dev', ini: 'P', av: '#C2410C', home: 'Chicago', text: 'shared the trip', meta: 'May 2026' },
];

// Lucide-style icon paths (ISC), shared by the page and the scenes that draw icons onto textures.
export const ICON = {
  flight: 'M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z',
  stay: 'M2 20v-8a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v8M4 10V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v4M12 4v6M2 18h20',
  car: 'M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2M9 17h6M5 17a2 2 0 1 0 4 0 2 2 0 1 0-4 0M15 17a2 2 0 1 0 4 0 2 2 0 1 0-4 0',
  tix: 'M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2ZM13 5v2M13 17v2M13 11v2',
  sun: 'M8 12a4 4 0 1 0 8 0 4 4 0 1 0-8 0M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41',
  cloudsun: 'M12 2v2M4.93 4.93l1.41 1.41M20 12h2M19.07 4.93l-1.41 1.41M15.947 12.65a4 4 0 0 0-5.925-4.128M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z',
  food: 'M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2M7 2v20M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7',
  see: 'M2 12a10 10 0 1 0 20 0 10 10 0 1 0-20 0M16.24 7.76l-1.804 5.411a2 2 0 0 1-1.265 1.265L7.76 16.24l1.804-5.411a2 2 0 0 1 1.265-1.265z',
  fork: 'M9 18a3 3 0 1 0 6 0 3 3 0 1 0-6 0M3 6a3 3 0 1 0 6 0 3 3 0 1 0-6 0M15 6a3 3 0 1 0 6 0 3 3 0 1 0-6 0M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9M12 12v3',
  star: 'M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z',
  play: 'M7 4v16l13-8z', pause: 'M7 4h4v16H7zM13 4h4v16h-4z',
  moon: 'M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z',
  ext: 'M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6',
  swipe: 'M18 8l4 4-4 4M6 8l-4 4 4 4M2 12h20',
  globe: 'M2 12a10 10 0 1 0 20 0 10 10 0 1 0-20 0M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z',
  pin: 'M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0M9 10a3 3 0 1 0 6 0 3 3 0 1 0-6 0',
};

export const KIND_COLOR = { flight: '#4338CA', stay: '#8B2FC9', car: '#15803D', tix: '#C2410C', weather: '#0369A1', food: '#C92A5E', see: '#0F766E', ride: '#FFD43B' };
