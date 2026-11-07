// Writes a.html, b.html and c.html from one template, so the three concepts share the header, the footer, the
// plan widgets and the page plumbing, and differ only in their story. Run: node tools/pages.mjs
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = join(dirname(fileURLToPath(import.meta.url)), '..');

const I = {
  snow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 2v20M4.9 7l14.2 10M4.9 17 19.1 7M9 4l3 3 3-3M9 20l3-3 3 3"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2"/></svg>',
  plane: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/></svg>',
  bed: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4v16M2 8h18a2 2 0 0 1 2 2v10M2 17h20M6 8v9"/></svg>',
  car: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/></svg>',
  ticket: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M13 5v2M13 17v2M13 11v2"/></svg>',
  route: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/></svg>',
  out: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M7 7h10v10"/></svg>',
  down: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/></svg>',
};
const MARK = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 16V10.5M10 10.5 5.4 5.6M10 10.5l4.6-4.9" stroke="var(--mark-line)" stroke-width="1.8" stroke-linecap="round" fill="none"/><circle cx="10" cy="16" r="2.3" fill="var(--mark-c)"/><circle cx="5" cy="5.2" r="2.3" fill="var(--mark-a)"/><circle cx="15" cy="5.2" r="2.3" fill="var(--mark-b)"/></svg>';

// the trip's widgets: Direction A solid kind fills; bookings are tickets with "Booked on <partner>" (links out only)
export const widgets = (o = {}) => `
      <div class="wds" aria-label="The trip, planned">
        <div class="wd wx wide" style="--kf:var(--k-wx)"><span class="k">${o.wxPlace || 'South Lake Tahoe'} ${o.wxIcon || I.snow}</span><div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap"><span class="big">${o.temp || '28°'}</span><span>${o.wx || 'Snow · 6 in tonight'}</span></div></div>
        <div class="wd up wide"><span class="k">${o.driveK || 'Drive · 32 min'} ${I.route}</span><b>${o.drive || 'Cabin → Hope Valley sled hill'}</b><span>${o.driveSub || '14 mi · chains advised'}</span></div>
        <div class="wd flight stub" style="--kf:var(--k-flight)"><span class="k">Flight ${I.plane}</span><b>${o.flight || 'SFO → RNO'}</b><span>${o.flightSub || 'Fri 8:05 · nonstop'}</span><span class="by">Booked on Aviasales ${I.out}</span><i class="stamp">BOOKED</i></div>
        <div class="wd stay stub" style="--kf:var(--k-stay)"><span class="k">Stay ${I.bed}</span><b>${o.stay || 'Cabin on Pioneer Trail'}</b><span>${o.staySub || '4 nights · Fri to Tue'}</span><span class="by">Booked on ${o.stayBy || 'Vrbo'} ${I.out}</span><i class="stamp">BOOKED</i></div>
        <div class="wd car stub" style="--kf:var(--k-car)"><span class="k">Car ${I.car}</span><b>${o.car || 'AWD SUV, chains'}</b><span>${o.carSub || 'Reno airport'}</span><span class="by">Booked on Expedia ${I.out}</span><i class="stamp">BOOKED</i></div>
        <div class="wd tix stub" style="--kf:var(--k-tix)"><span class="k">Tickets ${I.ticket}</span><b>${o.tix || 'Hope Valley sled hill'}</b><span>${o.tixSub || '4 passes · Sat'}</span><span class="by">Booked on Klook ${I.out}</span><i class="stamp">BOOKED</i></div>
      </div>`;

const chip = (i, name, color) => `<button class="chip" type="button" data-day="${i}"><i style="background:var(--k-${color})"></i>${name}</button>`;

const page = ({ id, title, name, desc, chapters, scene }) => `<!doctype html>
<html lang="en" class="light" data-concept="${id}" data-scene="dist/${id}.js">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>${title}</title>
<meta name="description" content="${desc}">
<link rel="stylesheet" href="fonts.css">
<link rel="stylesheet" href="cover.css">
<!-- prototype ${id.toUpperCase()} · ${name} · design only, not app code -->
</head>
<body>
<div class="stage" aria-hidden="true">
  <picture class="poster">
    <source media="(prefers-color-scheme: dark) and (max-width: 759px)" srcset="stills/${id}-0-phone-dark.webp">
    <source media="(prefers-color-scheme: dark)" srcset="stills/${id}-0-wide-dark.webp">
    <source media="(max-width: 759px)" srcset="stills/${id}-0-phone-light.webp">
    <img src="stills/${id}-0-wide-light.webp" alt="" fetchpriority="high" decoding="async">
  </picture>
  <div class="stills"></div>
  <canvas></canvas>
</div>

<header class="top">
  <a class="brand" href="#top" aria-label="GitAway, home"><span class="mark">${MARK}</span>GitAway</a>
  <span class="pill-tag">Early preview</span>
  <span class="sp"></span>
  <div class="acts">
    <button class="btn tonal icon js-mode" type="button" aria-label="Switch to the night scene"></button>
    <a class="btn tonal" href="#start">Sign in</a>
  </div>
</header>
<nav class="rail" aria-label="Chapters"></nav>

<main id="top">
${chapters}
</main>

<footer class="foot">
  <a class="brand" href="#top"><span class="mark">${MARK}</span>GitAway</a>
  <p>GitAway is free. Plan a trip together, share it, and fork trips other families shared. Booking always happens on the partner’s site, under their terms, never here.</p>
  <nav aria-label="Footer"><a href="#top">Trips people shared</a><a href="#top">For creators</a><a href="#top">About</a><a href="#top">Privacy</a></nav>
  <p>Early preview · sample trip, people and prices</p>
</footer>

<div class="anchors" aria-hidden="true"></div>
<nav class="proto" aria-label="Prototype switcher"><a href="#" data-go="-1" aria-label="Previous concept">‹</a><a href="index.html">${id.toUpperCase()} · ${name}</a><a href="#" data-go="1" aria-label="Next concept">›</a></nav>
<script src="dist/page.js"></script>
</body>
</html>
`;

const hero = (h1, lede) => `  <section class="ch hero" data-chapter="0" data-name="The book" style="--h:1.5">
    <div class="pin"><div class="hero-copy">
      <h1>${h1}</h1>
      <p class="lede">${lede}</p>
    </div><p class="hint">Scroll${I.down}</p></div>
  </section>
  <div class="gap" style="--h:0.8" aria-hidden="true"></div>`;
const card = (i, name, h, cls, body) => `  <section class="ch ${cls}" data-chapter="${i}" data-name="${name}" style="--h:${h}">
    <div class="pin"><article class="card">
${body}
    </article></div>
  </section>`;
const cta = (i, h2, p) => `  <section class="ch cta" data-chapter="${i}" data-name="Start" style="--h:1.6" id="start">
    <div class="pin"><article class="card">
      <h2>${h2}</h2>
      <p>${p}</p>
      <div class="row"><a class="btn fill" href="#start">Start a trip</a><a class="btn tonal" href="#start">Share a trip</a><a class="btn text" href="#start">See trips people shared ${I.arrow}</a></div>
    </article></div>
  </section>`;

/* ---------------------------------------------------------------- A · one continuous fly-through */
const A = [
  hero('Don’t read about it. <em>Go.</em>', 'Forget the guidebook. Start from a trip a real family took, <b>make it yours</b>, and go.'),
  card(1, 'Arrive', 2.2, 'arrive', `      <p class="eyebrow"><i></i>Lake Tahoe · December</p>
      <h2>A family shared their five days here.</h2>
      <p>Lena and Sam posted the whole trip: the cabin, the drives, where they ate, the ski day. Every pin is somewhere they really went.</p>
      <div class="row">${chip(0, 'Cabin', 'stay')}${chip(1, 'Emerald Bay', 'see')}${chip(2, 'Tahoe City', 'food')}${chip(3, 'Sand Harbor', 'see')}${chip(4, 'Heavenly', 'tix')}</div>`),
  card(2, 'Fork', 2.0, 'fork', `      <p class="eyebrow"><i></i>Fork</p>
      <h2>Make it yours.</h2>
      <p>Fork their trip and it’s yours to change. Keep the cabin, swap the ski day for a sled hill. <b>Lena and Sam get the thanks;</b> you get a head start.</p>`),
  card(3, 'Plan together', 2.6, 'plan', `      <p class="eyebrow"><i></i>Plan together</p>
      <h2>The whole trip on one screen.</h2>
      <p>The weather, your route, the drive time and every booking, wherever you made it. Your family plans it together.</p>${widgets()}
      <p class="note">Every booking opens on the partner’s site. GitAway never takes payment.</p>`),
  card(4, 'Go', 2.0, 'go', `      <p class="eyebrow"><i></i>Go</p>
      <h2>Then go. <em>Be there.</em></h2>
      <p>Five days, the four of you, and the lake doing that impossible blue. The plan keeps itself; you keep the moment.</p>`),
  card(5, 'Share it back', 2.2, 'share', `      <p class="eyebrow"><i></i>Share it back</p>
      <h2>Someone’s next trip starts with yours.</h2>
      <p>Post your photos and your plan when you’re home. The next family forks it, and their thank-you finds its way back to you.</p>
      <div class="row"><span class="chip on">${I.star.replace('<svg', '<svg width="16" height="16"')} Thanks from Ana &amp; Luis</span></div>`),
  cta(6, 'Your trip is <em>out there.</em>', 'Start from a trip someone shared, or from a blank page. Plan it with your people, then share it back.'),
].join('\n');

/* ---------------------------------------------------------------- B · one place, four seasons */
const B = [
  hero('Don’t read about it. <em>Go.</em>', 'One place, four seasons, and a trip for each one, <b>shared by the families who went</b>. Start from theirs.'),
  card(1, 'Winter', 2.1, 'winter', `      <p class="eyebrow"><i></i>Emerald Bay · Winter</p>
      <h2>A family shared their five days here.</h2>
      <p>Lena and Sam’s December: snowshoes from Inspiration Point down to the castle, cocoa at the overlook, and nobody else around.</p>`),
  card(2, 'Spring', 2.1, 'spring', `      <p class="eyebrow"><i></i>Spring · a fork</p>
      <h2>Make it yours.</h2>
      <p>In April, Priya forked their trip. Same overlook, same castle, then up to Eagle Falls while the snow melts. <b>Lena and Sam got the thanks.</b></p>`),
  card(3, 'Summer', 2.6, 'plan', `      <p class="eyebrow"><i></i>Summer · plan together</p>
      <h2>The whole trip on one screen.</h2>
      <p>The Okafors planned July together: kayaks to Fannette Island, the beach at D.L. Bliss, and every booking in one place.</p>${widgets({ wxPlace: 'Emerald Bay', wxIcon: I.sun, temp: '78°', wx: 'Sunny · light wind', driveK: 'Drive · 35 min', drive: 'Tahoe City → Emerald Bay', driveSub: 'CA-89 · lot fills by 10', flightSub: 'Fri 7:40 · nonstop', stay: 'Lakeside cabin, Tahoma', staySub: '5 nights · July 11 to 16', stayBy: 'Airbnb', car: 'Compact SUV', tix: 'Kayaks to Fannette Island', tixSub: '2 doubles · Sat 9:00' })}
      <p class="note">Every booking opens on the partner’s site. GitAway never takes payment.</p>`),
  card(4, 'Fall', 2.0, 'go', `      <p class="eyebrow"><i></i>Fall · go</p>
      <h2>Then go. <em>Be there.</em></h2>
      <p>October gold. The aspens turn, the light goes long, and the plan keeps itself while you sit and watch.</p>`),
  card(5, 'A year later', 2.2, 'share', `      <p class="eyebrow"><i></i>A year later · share it back</p>
      <h2>Someone’s next trip starts with yours.</h2>
      <p>Four seasons, four families who shared what they did. This winter a new family starts from all of them, and the thanks go back.</p>
      <div class="row"><span class="chip on">${I.star.replace('<svg', '<svg width="16" height="16"')} 4 thank-yous sent</span></div>`),
  cta(6, 'Every trip here <em>grew from another.</em>', 'On GitAway every trip can be forked. Start from one someone shared, or start your own and share it back.'),
].join('\n');

/* ---------------------------------------------------------------- C · the road trip (wildcard) */
const C = [
  hero('Don’t read about it. <em>Go.</em>', 'Forget the guidebook. Get in the car with a trip a real family shared, <b>take your own turn</b>, and go.'),
  card(1, 'Arrive', 2.2, 'arrive', `      <p class="eyebrow"><i></i>Kingsbury Grade · December</p>
      <h2>A family shared their five days here.</h2>
      <p>Lena and Sam’s trip glows on the road ahead: the cabin, Emerald Bay, dinner in Tahoe City. Follow it, or don’t.</p>`),
  card(2, 'Fork', 2.1, 'fork', `      <p class="eyebrow"><i></i>Fork</p>
      <h2>Make it yours.</h2>
      <p>At the fork they went straight on. You turn for the sled hill. Fork any trip and it’s yours to change; <b>they get the thanks.</b></p>`),
  card(3, 'Plan together', 2.6, 'plan', `      <p class="eyebrow"><i></i>Plan together</p>
      <h2>The whole trip on one screen.</h2>
      <p>The weather, the drive and every booking ride along with you, wherever you made them. Your family plans it together.</p>${widgets()}
      <p class="note">Every booking opens on the partner’s site. GitAway never takes payment.</p>`),
  card(4, 'Go', 2.0, 'go', `      <p class="eyebrow"><i></i>Go</p>
      <h2>Then go. <em>Be there.</em></h2>
      <p>Golden hour at the sled hill, the lake far below, four of you on one sled. The plan keeps itself.</p>`),
  card(5, 'Share it back', 2.2, 'share', `      <p class="eyebrow"><i></i>Share it back</p>
      <h2>Someone’s next trip starts with yours.</h2>
      <p>Your photos fly down the valley to the next car coming up. Ana and Luis forked your trip, and their thanks finds its way back.</p>
      <div class="row"><span class="chip on">${I.star.replace('<svg', '<svg width="16" height="16"')} Thanks from Ana &amp; Luis</span></div>`),
  cta(6, 'Your road is <em>out there.</em>', 'Start from a trip someone shared, or from a blank page. Plan it with your people, then share it back.'),
].join('\n');

const pages = {
  a: { id: 'a', name: 'Fly-through', title: 'GitAway · Don’t read about it. Go.', desc: 'Start from a trip a real family took: fork it, make it yours, plan it together, and share it back. GitAway is the GitHub of travel.', chapters: A },
  c: { id: 'c', name: 'Road trip', title: 'GitAway · Take your own turn', desc: 'Get in the car with a trip a real family shared, take your own turn, plan it together and share it back. GitAway is the GitHub of travel.', chapters: C },
  b: { id: 'b', name: 'Four seasons', title: 'GitAway · One place, four seasons', desc: 'One place, four seasons, and a trip for each, shared by the families who went. Fork one and make it yours. GitAway is the GitHub of travel.', chapters: B },
};
export { page, hero, card, cta, chip, I };
const only = process.argv[2];
for (const k of Object.keys(pages)) { if (only && only !== k) continue; writeFileSync(join(root, k + '.html'), page(pages[k])); console.log('wrote', k + '.html'); }
