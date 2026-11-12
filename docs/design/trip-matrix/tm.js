/* F-221 artboards: sample data (labelled sample wherever shown) and the shell pieces every screen shares.
   Every price is a plausible sample for a family of 4 from SFO in December: flight + 4-night stay + airport drive. */
(function () {
  const q = new URLSearchParams(location.search);
  if (q.get('mode')) document.documentElement.dataset.mode = q.get('mode');

  const money = n => '$' + n.toLocaleString('en-US');
  const WINDOWS = [
    { id: 'd10', label: 'Dec 10–14', dow: 'Thu–Mon', start: 10 },
    { id: 'd11', label: 'Dec 11–15', dow: 'Fri–Tue', start: 11 },
    { id: 'd12', label: 'Dec 12–16', dow: 'Sat–Wed', start: 12, asked: true },
    { id: 'd13', label: 'Dec 13–17', dow: 'Sun–Thu', start: 13 },
    { id: 'd14', label: 'Dec 14–18', dow: 'Mon–Fri', start: 14 },
  ];
  // per place: the art, airports, door-to-door time, typical December weather, and the five window totals (null = still searching)
  const PLACES = [
    { id: 'sd', art: 'san-diego', name: 'San Diego', via: 'SFO → SAN', door: '2h 50m', hi: 66, lo: 49, wx: 'sun', rain: '1 day in 6', fr: .265, drive: 80,
      t: [2310, 2260, 2140, 2080, 2390], marks: { d13: ['Easiest for kids'] } },
    { id: 'la', art: 'los-angeles', name: 'Los Angeles', via: 'SFO → LAX', door: '3h 20m', hi: 68, lo: 48, wx: 'sun', rain: '1 day in 7', fr: .27, drive: 80,
      t: [1980, 1910, 1840, 1870, 2050] },
    { id: 'lasd', art: 'los-angeles', art2: 'san-diego', name: 'LA + San Diego', sub: '2 nights each', via: 'LAX in, SAN out', door: '3h 20m', hi: 67, lo: 49, wx: 'sun', rain: '1 day in 6', fr: .28, drive: 150,
      t: [2350, 2280, 2190, 2150, 2420], discovery: 'd12' },
    { id: 'oc', art: 'orange-county', name: 'Orange County', via: 'SFO → SNA', door: '3h 05m', hi: 68, lo: 47, wx: 'sun', rain: '1 day in 7', fr: .26, drive: 90,
      t: [2420, 2380, 2290, 2240, 2610] },
    { id: 'ps', art: 'palm-springs', name: 'Palm Springs', via: 'SFO → PSP', door: '3h 10m', hi: 71, lo: 46, wx: 'sun', rain: '1 day in 20', fr: .41, drive: 70,
      t: [1760, 1720, 1690, 1740, 1880], marks: { d12: ['Cheapest'] }, rowMark: 'Best weather' },
    { id: 'sb', art: 'santa-barbara', name: 'Santa Barbara', via: 'SFO → SBA', door: '2h 40m', hi: 66, lo: 43, wx: 'cloud', rain: '1 day in 6', fr: .36, drive: 60,
      t: [2560, 2510, 2470, null, null] },
  ];
  const EXACT = { 'sd-d12': [568, 1492, 80], 'la-d12': [496, 1264, 80], 'lasd-d12': [612, 1428, 150], 'ps-d12': [704, 916, 70], 'sd-d13': [552, 1448, 80] };
  function split(p, w) {
    const total = p.t[WINDOWS.findIndex(x => x.id === w)]; if (total == null) return null;
    const k = p.id + '-' + w; if (EXACT[k]) return EXACT[k];
    const f = Math.round(total * p.fr / 10) * 10; return [f, total - f - p.drive, p.drive];
  }

  // the family (drawn faces, not colour codes) and a guest who joined through the owner's link
  const PEOPLE = {
    ana:   { name: 'Ana', skin: '#C68B65', hair: '#2B1B14', style: 'long', role: 'Owner' },
    dev:   { name: 'Dev', skin: '#A9714B', hair: '#1A1210', style: 'short' },
    leela: { name: 'Leela', skin: '#C68B65', hair: '#3A2418', style: 'bun', age: 10 },
    arjun: { name: 'Arjun', skin: '#B57A55', hair: '#20150F', style: 'messy', age: 7 },
    sam:   { name: 'Sam', guest: true },
    maya:  { name: 'Maya', skin: '#E0AC86', hair: '#6B3F22', style: 'curly', creator: true },
  };
  const HEARTS = { 'lasd-d12': ['ana', 'leela', 'dev', 'sam'], 'sd-d13': ['arjun'], 'ps-d12': ['dev'], 'la-d12': ['leela'] };

  function face(id, size = 22) {
    const p = PEOPLE[id];
    if (p.guest) return `<span class="face guest" style="width:${size}px;height:${size}px;font-size:${size * .45}px" title="${p.name} (guest)">${p.name[0]}</span>`;
    const hair = {
      long: '<path d="M7 18c0-7 4-10.5 9-10.5S25 11 25 18v8H7z"/>',
      short: '<path d="M8 15c0-5 3.5-7.5 8-7.5s8 2.5 8 7.5c-2-2.6-5-3.4-8-3.4s-6 .8-8 3.4z"/>',
      bun: '<circle cx="16" cy="6.5" r="3.4"/><path d="M7.6 16c0-5.4 3.6-8 8.4-8s8.4 2.6 8.4 8c-2.4-3-5.6-3.8-8.4-3.8S10 13 7.6 16z"/>',
      messy: '<path d="M8 15.5c-.5-5 3-8.5 8-8.5 4.5 0 8.2 2.8 8 8-1-1.6-2-2-3-2.2l-1 1.6-1.5-2-1.8 1.6-1.4-1.8-1.8 1.8-1.2-1.6c-1.6.4-3 1.2-4.3 3.1z"/>',
      curly: '<circle cx="9.5" cy="13" r="3.4"/><circle cx="13" cy="9.6" r="3.6"/><circle cx="18" cy="9.4" r="3.6"/><circle cx="22.3" cy="12.6" r="3.4"/><circle cx="8.6" cy="17.6" r="3"/><circle cx="23.4" cy="17.6" r="3"/>',
    }[p.style];
    return `<span class="face" style="width:${size}px;height:${size}px;background:var(--paper-2)" title="${p.name}"><svg viewBox="0 0 32 32" width="${size}" height="${size}" style="border-radius:50%">` +
      `<path d="M5 32c1.5-6 6-8.6 11-8.6S25.5 26 27 32z" fill="#8E8E98"/>` +
      (p.style === 'long' ? `<g fill="${p.hair}">${hair}</g>` : '') +
      `<circle cx="16" cy="17" r="8" fill="${p.skin}"/>` + (p.style !== 'long' ? `<g fill="${p.hair}">${hair}</g>` : `<path d="M8.4 15.6C9 11 12 9 16 9s7 2 7.6 6.6c-2.6-2.4-5-3-7.6-3s-5 .6-7.6 3z" fill="${p.hair}"/>`) +
      `<circle cx="13.2" cy="17.6" r="1" fill="#1A1210"/><circle cx="18.8" cy="17.6" r="1" fill="#1A1210"/><path d="M13.6 20.6q2.4 1.8 4.8 0" stroke="#1A1210" stroke-width="1.1" fill="none" stroke-linecap="round"/></svg></span>`;
  }
  const faces = (ids, size) => `<span class="faces">${ids.map(i => face(i, size)).join('')}</span>`;

  // typical December days (NOAA normals in the build; here sample) for the date strip, Dec 8 to 20, San Diego
  const DAYS = Array.from({ length: 13 }, (_, i) => {
    const d = 8 + i, dow = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d % 7];
    const hi = [66, 65, 66, 67, 66, 64, 65, 66, 66, 65, 64, 65, 66][i], lo = [49, 48, 49, 50, 49, 48, 48, 49, 50, 49, 47, 48, 49][i];
    const chance = [8, 10, 12, 9, 10, 22, 26, 14, 9, 8, 18, 12, 10][i];
    return { d, dow, hi, lo, chance, wx: chance >= 20 ? 'cloud' : 'sun', weekend: dow === 'Sat' || dow === 'Sun' };
  });

  const markSvg = `<i><svg viewBox="0 0 28 28" width="20" height="20"><path d="M9 7v14M9 14c0-4 10-3 10-7" stroke="var(--mark-line)" stroke-width="2" fill="none" stroke-linecap="round"/><circle cx="9" cy="7" r="2.6" fill="var(--mark-a)"/><circle cx="9" cy="21" r="2.6" fill="var(--mark-b)"/><circle cx="19" cy="7" r="2.6" fill="var(--mark-c)"/></svg></i>`;
  const brand = () => `<span class="mark">${markSvg}GitAway</span>`;
  function topbar(active = 'Book') {
    return `<header class="top only-laptop"><div class="l">${brand()}<span class="preview-pill">Early preview</span></div>` +
      `<nav class="navpill">${['Trip', 'Book', 'Family', 'Ask'].map(t => `<a class="${t === active ? 'on' : ''}" href="#">${t === 'Ask' ? ic('mic', 15) : ''}${t}</a>`).join('')}</nav>` +
      `<div class="r"><span class="beacon">${ic('plane', 15)}Dec trip <b>30 days</b></span>${face('ana', 36)}</div></header>`;
  }
  function tabbar(active = 'Book') {
    const t = [['Trip', 'home'], ['Plan', 'calendar'], ['Ask', 'mic'], ['Book', 'ticket'], ['Family', 'users']];
    return `<nav class="tabbar only-phone">${t.map(([n, i]) => n === 'Ask' ? `<a href="#"><span class="ask">${ic('mic', 22)}</span></a>` : `<a class="${n === active ? 'on' : ''}" href="#">${ic(i, 22)}${n}</a>`).join('')}</nav>`;
  }
  const status = () => `<div class="phone-status only-phone"><span>9:41</span><span style="display:flex;gap:6px;align-items:center"><svg width="18" height="11" viewBox="0 0 18 11"><rect x="0" y="7" width="3" height="4" rx="1" fill="currentColor"/><rect x="5" y="5" width="3" height="6" rx="1" fill="currentColor"/><rect x="10" y="2.5" width="3" height="8.5" rx="1" fill="currentColor"/><rect x="15" y="0" width="3" height="11" rx="1" fill="currentColor"/></svg><svg width="26" height="12" viewBox="0 0 26 12"><rect x=".5" y=".5" width="22" height="11" rx="3" fill="none" stroke="currentColor" opacity=".4"/><rect x="2" y="2" width="17" height="8" rx="2" fill="currentColor"/><rect x="24" y="4" width="1.5" height="4" rx=".75" fill="currentColor" opacity=".4"/></svg></span></div>`;
  const wxIcon = (w, s = 18) => ic(w === 'cloud' ? 'cloud' : w === 'rain' ? 'rain' : w === 'snow' ? 'snow' : 'sun', s);
  const SENTENCE = `A family of <span class="k">4</span>, from <span class="k">SFO</span>, <span class="k">San Diego or nearby</span>, <span class="k">Dec 12 to 16</span> <span class="soft">give or take</span> <span class="k">2 days</span>, under <span class="k">$3,000</span>.`;

  window.TM = { money, WINDOWS, PLACES, split, PEOPLE, HEARTS, face, faces, DAYS, brand, topbar, tabbar, status, wxIcon, SENTENCE, q };
})();
