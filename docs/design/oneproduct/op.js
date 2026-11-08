/* GitAway · one product: the creator and booking screens, drawn from the cockpit's parts.
   screen.html?s=<id>&size=dk|ph&mode=light|dark[&theme=structured|scrapbook|magazine|minimal]
   Data is sample: Juno Park is a made-up creator; the Tahoe trip is the founder's (Dec 19-26 2026). */
(function () {
  const { I, mark } = window.ICON;
  const q = new URLSearchParams(location.search);
  const S = q.get('s') || 'creators', size = q.get('size') || 'dk', mode = q.get('mode') || 'light';
  const ph = size === 'ph', dk = !ph;
  const ext = I('ext');

  /* ---------- the sample creator and her trail ---------- */
  const J = { name: 'Juno Park', ini: 'JP', handle: '@junoparkoutside', site: 'junoparkoutside.com', trails: 7, thanks: 214, follows: 38, readers: '3,906' };
  const TR = { title: 'Snow week at Tahoe', tail: 'kids in tow', place: 'Lake Tahoe', when: 'December 2025', days: 5 };
  const DAYS = [
    { n: 1, dow: 'Sat', name: 'Over the pass', ph: 'c-1', stops: [['car', '1:00 PM', 'Drive in over Echo Summit', 'car'], ['stay', '4:00 PM', 'Cabin near Heavenly', 'cabin'], ['food', '6:30 PM', 'Chili at the cabin', 'food']],
      tip: 'Chains on <b>before</b> Echo Summit, not at it. The chain-up line was 40 minutes.' },
    { n: 2, dow: 'Sun', name: 'Snowshoe Taylor Creek', ph: 'b-1', stops: [['tix', '9:30 AM', 'Snowshoes, Camp Richardson', 'snowshoe'], ['see', '10:30 AM', 'Taylor Creek loop · 2.2 mi', 'mountain'], ['food', '1:00 PM', 'Cocoa at Kiva Beach', 'food']],
      tip: 'The loop is flat: our 6-year-old did all of it.' },
    { n: 3, dow: 'Mon', name: 'Emerald Bay', ph: 'a-1', stops: [['car', '10:00 AM', 'CA 89 to the overlook', 'car'], ['see', '10:40 AM', 'Inspiration Point', 'see'], ['food', '12:30 PM', 'Lunch in Tahoe City', 'food']],
      tip: '89 closes on storm days. Check Caltrans before you leave.' },
    { n: 4, dow: 'Tue', name: 'Sleds at Spooner', ph: 'c-4', stops: [['tix', '9:00 AM', 'Kids’ ski school, Heavenly', 'ski'], ['see', '2:00 PM', 'Sledding, Spooner Summit', 'sled'], ['food', '6:00 PM', 'Pizza in Stateline', 'food']],
      tip: 'Book ski school three weeks out. It sold out by the 20th.' },
    { n: 5, dow: 'Wed', name: 'The pier, then home', ph: 'a-4', stops: [['see', '8:00 AM', 'Sunrise on the pier', 'see'], ['stay', '10:00 AM', 'Check out', 'cabin'], ['car', '11:00 AM', 'Drive to Reno', 'car']],
      tip: 'Go to the pier at sunrise. Nobody else was there.' },
  ];
  const still = (id, kind = 'wide') => `../cover3d/stills/${id}-${kind}-${mode}.webp`;
  const photo = (id, h, cap = '', cls = '', st = '') => `<figure class="photo ${cls}" style="height:${h}px;background-image:url(${still(id)});${st}">${cap ? `<figcaption class="cap">${cap}</figcaption>` : ''}</figure>`;
  const sample = (t = 'Sample creator') => `<span class="sample">${t}</span>`;

  /* ---------- chrome: the cockpit's top islands and floating tab bar; the pill names the space ---------- */
  const SPACES = {
    pub: [['trails', 'Trails'], ['creators', 'For creators'], ['plan', 'Plan a trip']],
    creator: [['trails', 'Trails'], ['yours', 'Your trails'], ['stats', 'Stats']],
    trip: [['trip', 'Trip'], ['book', 'Book'], ['family', 'Family'], ['ask', 'Ask']],
    admin: [['creators', 'Creators'], ['trails', 'Trails'], ['reports', 'Reports']],
  };
  const brand = (extra = '') => `<span class="brand">${mark()}GitAway${extra}</span>`;
  function top(space, active, right = '') {
    return `<header class="top">${brand(space === 'admin' ? ' <span class="bdg" style="margin-left:4px">Admin</span>' : '')}<nav class="navpill">${SPACES[space].map(([k, n]) => `<button class="${k === active ? 'on' : ''}" data-press>${k === 'ask' ? I('mic') : ''}${n}</button>`).join('')}</nav><div class="topr">${right}</div></header>`;
  }
  const beacon = (icon, text, val) => `<div class="beacon" data-press><span class="ring">${I(icon)}</span>${text} <b>${val}</b></div>`;
  const avatar = (t = 'A') => `<span class="avatar">${t}</span>`;
  const sbar = (t = '9:41') => `<div class="sbar"><span>${t}</span><span class="sg"><svg width="18" height="12" viewBox="0 0 18 12"><rect x="0" y="8" width="3" height="4" rx="1" fill="currentColor"/><rect x="5" y="5" width="3" height="7" rx="1" fill="currentColor"/><rect x="10" y="2.5" width="3" height="9.5" rx="1" fill="currentColor"/><rect x="15" y="0" width="3" height="12" rx="1" fill="currentColor"/></svg><span class="bat"></span></span></div>`;
  const TABS = {
    trip: [['trip', 'Trip', 'home'], ['plan', 'Plan', 'cal'], ['ask', 'Ask', 'mic'], ['book', 'Book', 'ticket'], ['family', 'Family', 'users']],
    trail: [['trails', 'Trails', 'pin'], ['yours', 'Yours', 'layers'], ['ask', 'Leave a trail', 'plus'], ['stats', 'Stats', 'tag'], ['you', 'You', 'user']],
    pub: [['trails', 'Trails', 'pin'], ['creators', 'Creators', 'spark'], ['ask', 'Leave a trail', 'plus'], ['plan', 'Plan', 'cal'], ['you', 'Sign in', 'user']],
  };
  const tabbar = (set, active) => `<nav class="tabbar">${TABS[set].map(([k, n, ic]) => k === 'ask' ? `<button class="ask" aria-label="${n}" data-press>${I(ic)}</button>` : `<button class="${k === active ? 'on' : ''}" data-press>${I(ic)}<span>${n}</span></button>`).join('')}</nav>`;
  const ptop = (right = '') => `<div class="ptop">${brand()}<span class="sp"></span>${right}</div>`;

  /* ---------- shared parts ---------- */
  const kt = (kind, icon, cls = '') => `<span class="ktile k-${kind} ${cls}">${I(icon)}</span>`;
  const trow = ([kind, t, what]) => `<div class="trow k-${kind}"><time><i></i>${t}</time><b>${what}</b></div>`;
  const rblk = ([kind, t, what, icon], sub = '') => `<div class="rblk k-${kind}"><time>${t}</time><div class="blk"><span class="ktile">${I(icon)}</span><div><b>${what}</b>${sub ? `<span>${sub}</span>` : ''}</div></div></div>`;
  const creatorCard = (o = {}) => `<div class="cc"><span class="av ${o.lg ? 'lg' : ''}">${J.ini}</span><div><b>${J.name}</b><span>${J.handle} · ${J.trails} trails</span></div></div>`;
  const thank = (n = J.thanks, label = 'Thank them') => `<button class="thank" data-thank data-press>${I('spark')}${label}<span class="n swap">${n}</span></button>`;
  const follow = (cls = '') => `<button class="btn fill follow ${cls}" data-press>${I('fork')}Follow this trail</button>`;
  const dayStub = (d, o = {}) => `<article class="stub ${o.on ? 'on' : ''} rise" style="animation-delay:${(o.i || 0) * 60}ms">${photo(d.ph, o.h || 120)}<div class="sb"><span class="tno">Day ${d.n} · ${d.dow}</span><b class="d">${d.name}</b><div class="stack" style="gap:6px">${d.stops.map(trow).join('')}</div></div></article>`;

  /* fork tree (git graph): lanes at x 14 / 38 / 62 */
  const X = [14, 38, 62];
  function frow(parts, node, H = ph ? 60 : 56) {
    const c = H / 2; let s = '';
    for (const p of parts) {
      if (p[0] === 'v') s += `<path d="M${X[p[1]]} ${p[2] === 'top' ? 0 : c} V${p[3] === 'bot' ? H : c}" class="${p[4] || ''}"/>`;
      if (p[0] === 'b') s += `<path d="M${X[p[1]]} 0 C${X[p[1]]} ${c * .8}, ${X[p[2]]} ${c * .3}, ${X[p[2]]} ${c}" class="${p[3] || ''}"/>`;
      if (p[0] === 'o') s += `<circle cx="${X[p[1]]}" cy="${c}" r="${p[2] === 'root' ? 7 : 6}" class="${p[2] || ''}"/>`;
      if (p[0] === 'd') s += `<path d="M${X[p[1]]} 0 V${c - 4}" stroke-dasharray="2 5"/>`;
    }
    return `<div class="frow" style="min-height:${H}px"><div class="fg"><svg viewBox="0 0 76 ${H}" preserveAspectRatio="xMinYMid meet">${s}</svg></div><div class="fnode">${node}</div></div>`;
  }
  function forkTree(o = {}) {
    return `<div class="ftree">
      ${frow([['v', 0, 'mid', 'bot'], ['o', 0, 'root']], `<span class="av sm">${J.ini}</span><div><b>Juno’s trail</b> <span>· Dec 2025</span></div>${o.compact ? '' : '<span class="bdg">Original</span>'}`)}
      ${frow([['v', 0, 'top', 'bot'], ['b', 0, 1], ['v', 1, 'mid', 'bot'], ['o', 1]], `<span class="av sm c3">O</span><div><b>The Okafors</b> <span>· the same week in July</span></div>${o.compact ? '' : '<span class="bdg">12 follows</span>'}`)}
      ${o.compact ? '' : frow([['v', 0, 'top', 'bot'], ['v', 1, 'top', 'mid'], ['b', 1, 2], ['o', 2]], `<span class="av sm c5">L</span><div><b>Lena &amp; Sam</b> <span>· kayaks, not sleds</span></div>`)}
      ${frow([['v', 0, 'top', 'bot'], ['b', 0, 1], ['o', 1]], `<span class="av sm c2">P</span><div><b>Priya R.</b> <span>· Eagle Falls instead of Emerald Bay</span></div>`)}
      ${frow([['v', 0, 'top', 'bot'], ['b', 0, 1, 'me'], ['o', 1, 'me']], `<span class="av sm c5">A</span><div><b>Abhi’s family</b> <span>· Tahoe at Christmas, Dec 2026</span></div>${o.compact ? '' : '<span class="bdg ok">You</span>'}`)}
      ${frow([['d', 0]], `<span class="ink2">+ ${J.follows - 4} more families followed it</span>`)}
    </div>`;
  }

  /* the book-this-trail lanes: honest states, links only */
  const TLANES = [
    { k: 'flight', ic: 'plane', n: 'Flights', s: 'Into Reno (RNO)', who: 'Juno’s link', why: 'Partner link. If you book, Aviasales pays Juno, not us.', btn: 'Search on Aviasales', bdg: '<span class="bdg partner">Juno’s link</span>' },
    { k: 'stay', ic: 'cabin', n: 'Stay', s: 'Juno’s cabin', why: 'Plain link to the cabin she stayed in. Nobody earns.', btn: 'See it on Vrbo', bdg: '<span class="bdg plain">No commission</span>' },
    { k: 'car', ic: 'car', n: 'Car', s: 'SUV with chains', why: 'Search filled in: an SUV with the chain option.', btn: 'Expedia', bdg: '<span class="bdg plain">No commission</span>' },
    { k: 'tix', ic: 'snowshoe', n: 'Snowshoes', s: 'Camp Richardson', why: 'Klook has the live price. We won’t guess one.', btn: 'Search on Klook', bdg: '<span class="bdg partner">Partner link</span>' },
    { k: 'tix', ic: 'ski', n: 'Ski school', s: 'Heavenly, kids', why: 'Ski schools sell only on their own site.', btn: 'Buy direct', bdg: '<span class="bdg direct k-tix">Buy direct</span>' },
  ];
  const tlane = (L) => `<section class="ln k-${L.k}"><div class="h"><span class="ktile">${I(L.ic)}</span><div><b>${L.n}</b><span>${L.s}</span></div></div>${L.bdg}<div class="perf"></div><a class="lnk" data-press>${L.btn} ${ext}</a><p class="why">${I('link')}${L.why}</p></section>`;

  /* ---------- themes for the shared trail ---------- */
  function themeBody(t) {
    if (t === 'scrapbook') {
      const rot = [-2.2, 1.6, -1, 2.1, -1.6];
      return `<div class="th-scrap"><div class="sbook">${DAYS.map((d, i) => `<div class="polaroid rise" style="transform:rotate(${rot[i]}deg);animation-delay:${i * 60}ms"><span class="tape"></span>${photo(d.ph, ph ? 120 : 150)}<p class="note">Day ${d.n} · ${d.name}<small>${d.stops.map((s) => s[2]).join(' · ')}</small></p></div>`).join('')}</div>
        <div class="tip mt24" style="max-width:640px">${I('spark')}<span><b>Juno’s tip.</b> ${DAYS[0].tip}</span></div></div>`;
    }
    if (t === 'magazine') {
      const d = DAYS[1];
      return `<div class="mag"><div>${photo(d.ph, ph ? 220 : 340, 'Sample render')}</div><div class="stack" style="gap:14px"><span class="num">02</span><span class="eyebrow">Day 2 · Sunday</span><h3 class="h1" style="font-size:${ph ? 30 : 44}px">Snowshoe Taylor Creek</h3>
        <p class="lead">We rented snowshoes at Camp Richardson at half past nine and walked the creek loop while it was still snowing. It’s flat, so the kids set the pace, and the trail ends at Kiva Beach, where the cocoa stand had a line of exactly one family: ours.</p>
        <div class="stack" style="gap:6px">${d.stops.map(trow).join('')}</div><div class="tip">${I('spark')}<span><b>Juno’s tip.</b> ${d.tip}</span></div></div></div>`;
    }
    if (t === 'minimal') {
      return `<div class="card pad"><div class="ml">${DAYS.map((d) => d.stops.map((s, j) => ph
        ? `<div class="r"><span class="t">${j ? '' : 'Day ' + d.n}</span><span><b>${s[2]}</b><br><span class="t">${s[1]}</span></span></div>`
        : `<div class="r"><span class="t">${j ? '' : 'Day ' + d.n + ' · ' + d.dow}</span><span class="t">${s[1]}</span><b>${s[2]}</b>${kt(s[0], s[3], 'sm')}</div>`).join('')).join('')}</div></div>`;
    }
    // structured: the ticket line
    return ph
      ? `<div class="stack">${DAYS.map((d, i) => `${dayStub(d, { i, on: i === 0, h: 150 })}${d.tip && i < 2 ? `<div class="tip">${I('spark')}<span><b>Juno’s tip.</b> ${d.tip}</span></div>` : ''}`).join('')}</div>`
      : `<div class="line">${DAYS.map((d, i) => dayStub(d, { i, on: i === 1 })).join('')}</div><div class="line mt12">${DAYS.map((d) => `<div class="tip" style="font-size:13px">${I('spark')}<span>${d.tip}</span></div>`).join('')}</div>`;
  }
  const THEMES = [['structured', 'Structured', 'ticket'], ['scrapbook', 'Scrapbook', 'clip'], ['magazine', 'Magazine', 'layers'], ['minimal', 'Minimal list', 'grip']];
  const themeSeg = (on) => `<div class="seg" data-themes>${THEMES.map(([k, n, ic]) => `<button class="${k === on ? 'on' : ''}" data-theme="${k}" data-press>${dk ? I(ic) : ''}${n}</button>`).join('')}</div>`;

  /* ======================================================================
     1 · For creators
     ====================================================================== */
  function creators() {
    const comp = `<div class="composer"><div class="field">Paste a link to your trip post, a YouTube video, or your whole blog<span class="caret"></span></div>
      <div class="kinds">${[['link', 'A blog post'], ['layers', 'A whole blog'], ['see', 'YouTube'], ['clip', 'Instagram caption']].map(([ic, n]) => `<span class="chip">${I(ic)}${n}</span>`).join('')}</div>
      <div class="row wrapr">${dk ? '<span class="fine">Free. Nothing goes public until you tick “This is my post”.</span><span class="sp"></span>' : ''}<button class="btn fill ${ph ? 'lg' : ''}" style="${ph ? 'width:100%' : 'height:48px;padding:0 22px;font-size:16px'}" data-press>${I('plus')}Leave a trail</button></div>${ph ? '<span class="fine">Free. Nothing goes public until you tick “This is my post”.</span>' : ''}</div>`;
    const preview = `<div class="stack" style="gap:10px"><div class="row"><span class="eyebrow">What your post becomes</span><span class="sp"></span>${sample()}</div>
      <div class="story" style="height:${ph ? 190 : 250}px;background-image:url(${still('a-6')})"><span class="play"><span class="pb">${I('arrow')}</span>${TR.title}</span></div>
      <div class="line" style="${ph ? 'grid-auto-flow:column;grid-auto-columns:120px;overflow:hidden' : ''}">${DAYS.map((d, i) => `<article class="stub ${i === 1 ? 'on' : ''}">${photo(d.ph, 64)}<div class="sb" style="padding:8px 10px 10px;gap:2px"><span class="tno">Day ${d.n}</span><b class="d" style="font-size:13px">${d.name}</b></div></article>`).join('')}</div>
      <div class="row">${creatorCard()}<span class="sp"></span>${dk ? `<span class="bdg">${I('fork')}${J.follows} follows</span><span class="bdg" style="background:var(--k-food-t);color:var(--k-food-i)">${I('spark')}${J.thanks} thanks</span>` : ''}</div></div>`;
    const why = [
      `<section class="tk ink" style="display:grid;gap:8px"><span class="eyebrow">People say thanks</span><span class="big tnum" style="font-size:${ph ? 52 : 64}px">${J.thanks}</span><p class="sub">families thanked Juno for one trail. Every thank-you is a real person, counted like a star on a repo.</p><div class="perf"></div><div class="row"><div class="avs">${['O', 'P', 'A', 'L', 'M'].map((x, i) => `<span class="av sm c${i + 2}" style="box-shadow:0 0 0 2px var(--up-bg);margin-left:${i ? -8 : 0}px">${x}</span>`).join('')}</div><span class="fine">The Okafors, Priya and 212 more</span></div></section>`,
      `<section class="tk" style="display:grid;gap:8px"><span class="eyebrow">Your trip keeps going</span><h3 class="h2">${J.follows} families followed it</h3><p class="sub">Following copies your trail into their trip. You see every branch, and where it went next.</p><div class="perf"></div>${forkTree({ compact: true })}</section>`,
      `<section class="tk kf k-flight" style="display:grid;gap:8px"><span class="eyebrow">Your links keep paying you</span><h3 class="h2">Your marker rides along</h3><p class="sub">Add your Travelpayouts marker once. Flights booked from your trails carry it, so Aviasales pays you. Every trail says who earns, in plain words.</p><div class="perf"></div><div class="row wrapr"><span class="bdg">${I('plane')}Aviasales · your marker</span><span class="bdg">${I('cabin')}Your own stay links</span></div></section>`,
    ];
    const steps = [
      ['01', 'Paste', 'A post, a video, or the whole blog.', `<div class="composer" style="padding:10px;box-shadow:var(--sh1)"><div class="field filled" style="min-height:0;font-size:14px">${J.site}/snow-week-tahoe</div></div>`],
      ['02', 'We draft', 'Days, stops, times and your tips, in about a minute.', `<div class="stack" style="gap:7px"><div class="sk" style="width:80%"></div><div class="sk" style="width:62%"></div><div class="sk" style="width:70%"></div><div class="prog" style="background:var(--s3)"><i style="width:40%"></i></div><span class="fine">Day 2 of 5</span></div>`],
      ['03', 'You glance and fix', 'Tap anything that’s off. Add your own links.', `<div class="rail">${rblk(DAYS[1].stops[0])}<span class="from">${I('clip')}“we rented snowshoes at Camp Rich…”</span></div>`],
      ['04', 'Leave a trail', 'It goes live under your name, linked to your post.', `<div style="position:relative;height:74px"><span class="stamp big go" style="left:10px;top:10px;--sc:var(--ok)">Live<small>Juno’s trail</small></span></div>`],
    ];
    const how = dk
      ? `<div class="tk" style="padding:0;display:grid;grid-template-columns:repeat(4,1fr)">${steps.map(([n, t, s, art], i) => `<div style="position:relative;padding:20px 22px 22px;display:grid;gap:8px;align-content:start">${i ? '<span class="vperf" style="left:0"></span>' : ''}<span class="tno">${n} · Admit one</span><h3 class="h2">${t}</h3><p class="sub">${s}</p><div class="mt8">${art}</div></div>`).join('')}</div>`
      : `<div class="stack">${steps.map(([n, t, s, art]) => `<div class="tk" style="display:grid;gap:8px"><span class="tno">${n} · Admit one</span><h3 class="h2">${t}</h3><p class="sub">${s}</p><div class="perf"></div>${art}</div>`).join('')}</div>`;
    const terms = [['What we show', 'Your name, the days, stops and tips you approve, up to two photos a day, and a link to your post.'], ['Take it down any time', 'Unpublish in one tap: the page and its photos go. Anyone can report a trail.'], ['Your marker', 'Paste your Travelpayouts marker once. Klook uses GitAway’s account for now, and the trail says so.'], ['Later, a share', 'When a creator’s trails bring a lot of bookings, we want to share what partners pay us. A plan, not a promise.']];
    const termsHtml = `<section class="tk"><div class="row"><span class="tno">The back of the ticket</span><span class="sp"></span><span class="fine">Free · terms shown on day one</span></div><div class="perf"></div><div style="display:grid;grid-template-columns:${dk ? 'repeat(4,1fr)' : '1fr'};gap:${dk ? 24 : 14}px">${terms.map(([t, s]) => `<div><b class="h3" style="font-size:16px">${t}</b><p class="fine mt8" style="font-size:${ph ? 15 : 14}px">${s}</p></div>`).join('')}</div></section>`;
    if (dk) return `<div class="ab dk page ${mode}">${top('pub', 'creators', `<button class="btn text" data-press>Sign in</button><button class="btn fill" data-press>${I('plus')}Leave a trail</button>`)}
      <main class="wrap" style="padding-top:112px">
        <div style="display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:start"><div class="stack" style="gap:22px"><span class="eyebrow">For creators · free</span><h1 class="hero">Take a trip.<br><em>Leave a trail.</em></h1><p class="lede">Paste your trip post. We draft the days, the stops and your tips. You glance, fix, and publish a trail the next family can follow, and thank you for.</p>${comp}</div>${preview}</div>
        <h2 class="h1 mt48 two-tone" style="font-size:44px">Why leave a trail. <em>Three things a blog post can’t do.</em></h2>
        <div class="mt24" style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;align-items:stretch">${why.join('')}</div>
        <h2 class="h1 mt48 two-tone" style="font-size:44px">How it works. <em>About a minute.</em></h2><div class="mt24">${how}</div>
        <div class="mt32">${termsHtml}</div>
        <section class="tk ink mt32" style="display:flex;align-items:center;gap:24px;padding:28px 32px"><h2 class="h1" style="font-size:40px">Your next trip post is a trail someone can follow.</h2><span class="sp"></span><button class="btn fill" style="height:52px;padding:0 24px;font-size:17px" data-press>${I('plus')}Leave a trail</button></section>
      </main></div>`;
    return `<div class="ab ph page ${mode}">${sbar()}<main class="wrap">${ptop(`<button class="btn tonal sm" data-press>Sign in</button>`)}
      <div class="stack" style="gap:16px;margin-top:14px"><span class="eyebrow">For creators · free</span><h1 class="hero">Take a trip.<br><em>Leave a trail.</em></h1><p class="lede">Paste your trip post. We draft the days, stops and tips; you fix what’s off and publish a trail families can follow, and thank you for.</p>${comp}</div>
      <div class="mt32">${preview}</div>
      <h2 class="h1 mt48 two-tone" style="font-size:30px">Why leave a trail. <em>Three things a post can’t do.</em></h2><div class="stack mt16">${why.join('')}</div>
      <h2 class="h1 mt48 two-tone" style="font-size:30px">How it works. <em>About a minute.</em></h2><div class="mt16">${how}</div>
      <div class="mt32">${termsHtml}</div>
    </main>${tabbar('pub', 'creators')}</div>`;
  }

  /* ======================================================================
     2 · Paste a link / pick posts from a whole blog
     ====================================================================== */
  const POSTS = [
    ['b-1', 'Snow week at Tahoe, kids in tow', 'Jan 2025 · Lake Tahoe', '5 days', 1, 1],
    ['c-1', 'Highway 50 in a snowstorm', 'Feb 2025 · Sierra', '2 days', 1, 1],
    ['a-4', 'Sunrise piers of the West', 'Mar 2025 · California', '7 days', 1, 1],
    ['c-4', 'Our sled, ranked', 'Dec 2024 · Gear', 'Gear list', 0, 0],
    ['a-1', 'Emerald Bay in one day', 'Oct 2024 · Lake Tahoe', '1 day', 1, 0],
    ['b-3', 'Kayaks for small kids', 'Aug 2024 · Gear', 'Gear list', 0, 0],
  ];
  function pick() {
    const comp = `<div class="composer" style="padding:12px 14px;gap:10px"><div class="row"><span class="field filled" style="min-height:0;font-size:${ph ? 17 : 18}px;flex:1">${J.site}</span>${dk ? `<button class="btn tonal" data-press>${I('search')}Read again</button>` : ''}</div><div class="row wrapr"><span class="bdg ok">${I('check')}Whole blog · 23 posts</span><span class="bdg">9 look like trips</span></div></div>`;
    const seg = `<div class="seg"><button class="on" data-press>Trips · 9</button><button data-press>All · 23</button><button data-press>Picked · 3</button></div>`;
    const card = ([p, t, m, d, trip, on]) => `<article class="card pick" style="overflow:hidden;opacity:${trip ? 1 : .55}">${photo(p, 116)}<span class="tick ${on ? 'on' : ''}">${on ? I('check') : ''}</span><div class="pad" style="display:grid;gap:6px;padding:12px 14px 14px"><b class="h3" style="font-size:16px">${t}</b><span class="fine">${m}</span>${trip ? `<span class="bdg ok">${I('cal')}${d} · looks like a trip</span>` : `<span class="bdg plain">${d} · not a trip</span>`}</div></article>`;
    const rowp = ([p, t, m, d, trip, on]) => `<article class="card row" style="padding:10px;gap:12px;opacity:${trip ? 1 : .55}">${photo(p, 72, '', '', 'width:72px;flex:none;border-radius:14px')}<div style="flex:1;display:grid;gap:4px;min-width:0"><b style="font-size:17px;line-height:1.2">${t}</b><span class="fine">${m}</span>${trip ? `<span class="bdg ok" style="justify-self:start">${d} · a trip</span>` : `<span class="bdg plain" style="justify-self:start">${d}</span>`}</div><span class="tick ${on ? 'on' : ''}" style="margin-right:6px">${on ? I('check') : ''}</span></article>`;
    const picked = POSTS.filter((p) => p[5]);
    const ticket = `<section class="tk ink" style="display:grid;gap:10px"><span class="eyebrow">Your picks</span><div class="row" style="align-items:baseline;gap:12px"><span class="big">3</span><span class="sub">posts, so 3 trails</span></div><div class="perf"></div>${picked.map((p) => `<div class="row" style="gap:10px"><span class="ktile k-see sm">${I('pin')}</span><div style="flex:1"><b style="font-size:15px">${p[1]}</b><div class="fine">${p[3]}</div></div></div>`).join('')}<div class="perf"></div><p class="fine">About a minute each. Nothing is public until you publish.</p><button class="btn fill" style="height:48px" data-press>${I('spark')}Draft 3 trails</button></section>`;
    if (dk) return `<div class="ab dk ${mode}">${top('creator', 'yours', `${beacon('spark', 'Thanks this week', '+18')}${avatar('J')}`)}
      <main class="wrap"><div class="row"><div class="stack" style="gap:6px"><span class="eyebrow">Leave a trail · step 1 of 3</span><h1 class="h1">Pick the posts that are trips</h1></div><span class="sp"></span>${seg}</div>
      <div class="mt16" style="display:grid;grid-template-columns:1fr 340px;gap:20px;align-items:start"><div class="stack" style="gap:14px">${comp}<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">${POSTS.map(card).join('')}</div></div>
      <div class="stack">${ticket}<div class="card pad fine row" style="gap:10px">${I('link')}<span>Only one post? Paste its link instead of the blog.</span></div></div></div></main></div>`;
    return `<div class="ab ph ${mode}">${sbar()}<main class="wrap"><div class="ptop"><button class="iconbtn" data-press>${I('back')}</button><span class="sp"></span><span class="fine">Step 1 of 3</span></div>
      <h1 class="h1" style="margin:6px 0 14px">Pick the posts that are trips</h1>${comp}<div class="mt12" style="overflow:hidden">${seg}</div><div class="stack mt12" style="gap:10px">${POSTS.slice(0, 5).map(rowp).join('')}</div></main>
      <div class="dock solo"><button class="btn fill lg" data-press>${I('spark')}Draft 3 trails</button></div></div>`;
  }

  /* ======================================================================
     3 · Drafting in progress
     ====================================================================== */
  function drafting() {
    const post = `<section class="card pad" style="display:grid;gap:12px;position:relative;overflow:hidden"><div class="row"><span class="eyebrow">From your post</span><span class="sp"></span><a class="cxl">${J.site} ${ext}</a></div><h3 class="h2">${TR.title}, ${TR.tail}</h3>
      <div style="position:relative;display:grid;gap:10px;font-size:${ph ? 16 : 15}px;line-height:1.55;color:var(--ink2)"><span class="scan"></span>
      <p><span class="hl done">We drove up over Echo Summit on Saturday</span> and learned the hard way to put chains on before the top. <span class="hl done">The cabin near Heavenly</span> had a wood stove and a sled in the shed.</p>
      <p><span class="hl">Sunday we rented snowshoes at Camp Richardson around half nine</span> and <span class="hl">walked the Taylor Creek loop</span> while it snowed. The kids set the pace.</p>
      <p>Monday, if 89 is open, Emerald Bay. We stopped at Inspiration Point and ate lunch in Tahoe City…</p></div>
      <p class="fine">Reading paragraph 6 of 14</p></section>`;
    const prog = `<section class="tk ink" style="display:grid;gap:10px"><div class="row"><span class="eyebrow">Drafting your trail</span><span class="sp"></span><b class="mono tnum">0:24</b></div><div class="prog"><i style="width:38%"></i></div>
      <div style="display:grid;grid-template-columns:${dk ? 'repeat(5,auto)' : '1fr 1fr'};gap:8px 18px;justify-content:start;font-size:${ph ? 15 : 14}px">${[['Read the post', 1], ['Found 5 days', 1], ['Days and stops · 2 of 5', 2], ['Your tips', 0], ['Photos', 0]].map(([t, s]) => `<span class="row" style="gap:6px;color:${s ? 'var(--up-fg)' : 'var(--up-fg2)'}">${s === 1 ? `<span class="ktile sm" style="background:var(--ok);color:#fff;width:20px;height:20px;border-radius:50%;font-size:12px">${I('check')}</span>` : s === 2 ? `<span style="width:20px;height:20px;border-radius:50%;box-shadow:inset 0 0 0 3px var(--ok)"></span>` : `<span style="width:20px;height:20px;border-radius:50%;box-shadow:inset 0 0 0 2px var(--up-line)"></span>`}${t}</span>`).join('')}</div></section>`;
    const st = (i) => {
      const d = DAYS[i];
      if (i === 0) return dayStub(d, { h: dk ? 110 : 120 });
      if (i === 1) return `<article class="stub" style="box-shadow:var(--sh2),inset 0 0 0 2px var(--k-wx)"><div class="photo" style="border-radius:0;height:${dk ? 110 : 120}px"><div class="sk" style="position:absolute;inset:0;height:auto;border-radius:0"></div></div><div class="sb"><span class="tno">Day 2 · drafting</span><b class="d">Snowshoe Taylor Creek</b><div class="trow k-tix"><time><i></i>9:30 AM</time><b>Snowshoes, Camp Richardson</b></div><div class="sk" style="width:86%"></div><div class="sk" style="width:64%"></div><span class="from">${I('clip')}“around half nine”</span></div></article>`;
      return `<article class="stub waiting" style="box-shadow:inset 0 0 0 2px var(--line2);background:transparent;min-height:${dk ? 200 : 90}px;display:grid;place-items:center;align-self:start;color:var(--ink3)"><span class="tno">Day ${d.n}</span></article>`;
    };
    if (dk) return `<div class="ab dk ${mode}">${top('creator', 'yours', `${beacon('spark', 'Drafting · day', '2 of 5')}${avatar('J')}`)}
      <main class="wrap" style="display:grid;grid-template-columns:420px 1fr;gap:24px;align-items:start">${post}
      <div class="stack" style="gap:16px"><div><span class="eyebrow">Leave a trail · step 2 of 3</span><h1 class="h1 mt8">Drafting your trail</h1><p class="sub mt8" style="font-size:16px">${TR.title} · 5 days found · you can leave, we’ll email you when it’s ready</p></div>${prog}<div class="line">${[0, 1, 2, 3, 4].map(st).join('')}</div></div></main></div>`;
    return `<div class="ab ph fixed ${mode}">${sbar()}<main class="wrap"><div class="ptop"><button class="iconbtn" data-press>${I('x')}</button><span class="sp"></span><span class="fine">Step 2 of 3</span></div>
      <h1 class="h1" style="margin:6px 0 14px">Drafting your trail</h1>${prog}<div class="stack mt12" style="gap:10px">${st(1)}${st(2)}${st(3)}</div><p class="fine mt12">You can close this. We’ll send a note when it’s ready.</p></main></div>`;
  }

  /* ======================================================================
     4 · The draft editor
     ====================================================================== */
  function editor() {
    const d = DAYS[1];
    const days = DAYS.map((x, i) => `<button class="row card" style="padding:8px;gap:10px;${i === 1 ? 'background:var(--up-bg);color:var(--up-fg);box-shadow:var(--sh2)' : ''}" data-press>${photo(x.ph, 44, '', '', 'width:44px;flex:none;border-radius:10px')}<div style="flex:1;text-align:left"><span class="tno" style="${i === 1 ? 'color:var(--up-fg2)' : ''}">Day ${x.n}</span><b style="display:block;font-size:14px;line-height:1.2">${x.name}</b></div>${i === 2 ? '<span class="bdg warn">1</span>' : ''}</button>`).join('');
    const stops = `<div class="rail">${rblk(d.stops[0])}<div style="margin-left:76px;display:flex;gap:8px;flex-wrap:wrap"><span class="from">${I('clip')}“we rented snowshoes at Camp Richardson around half nine”</span></div>
      <div class="tk" style="margin-left:76px;padding:12px 14px;background:var(--warn-t);color:var(--warn-ink);box-shadow:inset 0 0 0 1px var(--warn-line);display:flex;gap:10px;align-items:center;flex-wrap:wrap">${I('clock')}<span style="flex:1;min-width:180px;font-size:${ph ? 16 : 14}px">We guessed <b>10:30</b>. Your post says “while it snowed”. Right time?</span><button class="btn sm tonal" data-press>Keep 10:30</button><button class="btn sm fill" data-press>Change</button></div>
      ${rblk(d.stops[1], '2.2 mi loop · flat')}${rblk(d.stops[2])}<button class="btn line sm" style="margin-left:76px;justify-self:start" data-press>${I('plus')}Add a stop</button></div>`;
    const photos = `<div class="row" style="gap:8px">${['b-1', 'a-1'].map((p, i) => `<div class="pick" style="width:${ph ? 130 : 150}px">${photo(p, ph ? 96 : 100, i ? '' : 'Sample render')}<span class="tick on">${I('check')}</span></div>`).join('')}<div style="width:${ph ? 80 : 100}px;height:${ph ? 96 : 100}px;border-radius:var(--rc);box-shadow:inset 0 0 0 2px var(--line2);display:grid;place-items:center;color:var(--ink2);font-size:13px;text-align:center">${I('plus')}<span>From your post</span></div></div><p class="fine">Up to two photos a day, only ones you took. We drop where they were taken.</p>`;
    const editorCard = `<section class="card pad" style="display:grid;gap:14px"><div class="row"><span class="tno">Day 2 · Sunday</span><span class="sp"></span><span class="bdg ok">${I('check')}Looks right</span></div><h2 class="h1" style="font-size:${ph ? 30 : 34}px"><span class="edit focus">Snowshoe Taylor Creek</span></h2>${photos}<div class="hair"></div>${stops}<div class="hair"></div><div class="tip">${I('spark')}<span><b>Your tip.</b> <span class="edit">${d.tip}</span></span></div></section>`;
    const links = `<section class="card pad" style="display:grid;gap:12px"><div class="row"><span class="eyebrow">Your booking links</span><span class="sp"></span><span class="fine">readers see them</span></div>
      ${[['flight', 'plane', 'Flights', 'Aviasales · your marker 48213', '<span class="bdg ok">' + I('check') + 'Pays you</span>'], ['stay', 'cabin', 'Stay', 'vrbo.com/2193…  your cabin', '<span class="bdg plain">No commission</span>'], ['tix', 'ski', 'Ski school', 'heavenly.com · kids’ school', '<span class="bdg direct k-tix">Buy direct</span>']].map(([k, ic, n, s, b]) => `<div class="row" style="gap:10px">${kt(k, ic, 'sm')}<div style="flex:1;min-width:0"><b style="font-size:15px">${n}</b><div class="fine" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${s}</div></div>${b}</div>`).join('')}
      <button class="btn line sm" style="justify-self:start" data-press>${I('plus')}Add a link</button></section>`;
    const publish = `<section class="tk ink" style="display:grid;gap:10px"><span class="eyebrow">Ready to leave a trail</span>${[['Days', '5 of 5', 1], ['Stops', '15 · 1 to check', 2], ['Photos', '8', 1], ['Your links', '3', 1]].map(([a, b, s]) => `<div class="row" style="font-size:15px">${s === 1 ? I('check') : I('clock')}<span>${a}</span><span class="sp"></span><b>${b}</b></div>`).join('')}<div class="perf"></div><label class="row" style="gap:10px;font-size:15px"><span class="tick" style="box-shadow:inset 0 0 0 2px var(--up-fg2)"></span>This is my post, and these are my photos</label><button class="btn fill" style="height:48px;opacity:.5" data-press>${I('plus')}Leave a trail</button><p class="fine">Readers first see it as</p>${themeSeg('structured').replace('class="seg"', 'class="seg" style="background:var(--up-tile);box-shadow:none;flex-wrap:wrap"')}</section>`;
    if (dk) return `<div class="ab dk ${mode}">${top('creator', 'yours', `<span class="toolpill"><span class="ktile k-car">${I('check')}</span>Draft · saved</span><button class="btn tonal" data-press>Preview</button>`)}
      <main class="wrap" style="display:grid;grid-template-columns:230px 1fr 350px;gap:18px;align-items:start;padding-top:88px"><div class="stack" style="gap:8px"><span class="eyebrow">Step 3 of 3 · ${TR.title}</span>${days}<button class="btn line sm" data-press>${I('plus')}Add a day</button></div>
      <div style="height:796px;overflow:hidden;border-radius:var(--rw)">${editorCard}</div><div class="stack">${links}${publish}</div></main></div>`;
    return `<div class="ab ph page ${mode}">${sbar()}<main class="wrap"><div class="ptop"><button class="iconbtn" data-press>${I('back')}</button><span class="sp"></span><span class="toolpill" style="height:40px;font-size:14px"><span class="ktile k-car" style="width:28px;height:28px">${I('check')}</span>Saved</span></div>
      <div class="days" style="overflow:hidden;margin:6px -16px 14px;padding:4px 16px">${DAYS.map((x, i) => `<button class="dchip ${i === 1 ? 'on' : ''}"><b>Day ${x.n}</b><span>${i === 2 ? '1 to check' : x.stops.length + ' stops'}</span></button>`).join('')}</div>
      ${editorCard}<div class="mt12">${links}</div></main>
      <div class="dock solo"><button class="btn tonal lg" data-press>Preview</button><button class="btn fill lg" data-press>${I('plus')}Leave a trail</button></div></div>`;
  }

  /* ======================================================================
     5 · The published trail (the shared trip as a story)
     ====================================================================== */
  function trail() {
    const theme = q.get('theme') || 'structured';
    const head = `<div class="row wrapr"><span class="chip">${I('pin')}${TR.place}</span><span class="chip">${I('cal')}5 days · ${TR.when}</span>${sample()}</div>
      <h1 class="hero" style="font-size:${ph ? 42 : 64}px">${TR.title}, <em>${TR.tail}</em></h1>
      <div class="row">${creatorCard()}<span class="sp"></span>${dk ? `<a class="cxl" data-press>Read Juno’s post ${ext}</a>` : ''}</div>
      <div class="row" style="gap:${ph ? 18 : 28}px"><div class="stat"><b data-thanks>${J.thanks}</b><span>thanks</span></div><div class="stat"><b>${J.follows}</b><span>follows</span></div><div class="stat"><b>${J.readers}</b><span>readers</span></div></div>
      ${dk ? `<div class="row">${follow()}${thank()}</div><p class="fine">Following copies it into your trips with your own dates. Juno’s trail stays as it is.</p>` : ''}`;
    const story = `<div class="story" style="height:${ph ? 230 : 440}px;background-image:url(${still('a-6')})"><span class="slot sample">3D story slot</span><span class="play" data-press><span class="pb">${I('arrow')}</span>Play the story · 1:10</span></div>`;
    const lanes = `<div class="lanes ${dk ? 'row5' : ''}">${TLANES.map(tlane).join('')}</div>`;
    const tips = `<section class="card pad" style="display:grid;gap:12px">${creatorCard({ lg: false })}<p class="sub" style="font-size:${ph ? 16 : 15}px">Snow, short trails, two kids under ten. I write it all up at ${J.site}.</p><div class="row">${thank(J.thanks, 'Thank Juno')}<a class="lnk tonal" data-press>Profile</a></div></section>`;
    if (dk) return `<div class="ab dk page ${mode} th-${theme}">${top('pub', 'trails', `<button class="btn fill" data-press>${I('plus')}Leave a trail</button>${avatar('A')}`)}
      <main class="wrap" style="padding-top:104px"><div style="display:grid;grid-template-columns:1fr 1.2fr;gap:40px;align-items:center"><div class="stack" style="gap:18px">${head}</div>${story}</div>
      <div class="row mt48"><h2 class="h1" style="font-size:36px">The trail</h2><span class="sp"></span><span class="fine" style="margin-right:6px">Show it as</span>${themeSeg(theme)}</div>
      <div class="mt16" data-themebody>${themeBody(theme)}</div>
      <div class="mt48" style="display:grid;grid-template-columns:1.3fr 1fr;gap:16px;align-items:start"><section class="card pad"><div class="row"><h2 class="h2">Where this trail went</h2><span class="sp"></span><span class="bdg">${I('fork')}${J.follows} follows</span></div><p class="fine mt8">Every family that followed it, and where they took it next.</p><div class="mt12">${forkTree()}</div></section>${tips}</div>
      <div class="row mt48"><div><h2 class="h1" style="font-size:36px">Book this trail</h2><p class="sub mt8" style="font-size:16px">Links only. You book on the partner’s own site; it says who earns on each one.</p></div><span class="sp"></span>${follow()}</div><div class="mt16">${lanes}</div>
      <section class="tk ink mt48" style="display:flex;align-items:center;gap:24px;padding:28px 32px"><div><h2 class="h1" style="font-size:40px">Take a trip. Leave a trail.</h2><p class="sub mt8">Been somewhere? Share the whole trip, not just the photos.</p></div><span class="sp"></span><button class="btn tonal" style="height:52px;padding:0 22px;font-size:17px" data-press>${I('plus')}Leave a trail</button></section></main></div>`;
    return `<div class="ab ph page ${mode} th-${theme}">${sbar()}<main class="wrap" style="padding-bottom:200px">${ptop(`<button class="iconbtn" data-press>${I('ext')}</button>`)}${story}<div class="stack mt16" style="gap:14px">${head}</div>
      <div class="mt32 stack" style="gap:12px"><h2 class="h1" style="font-size:30px">The trail</h2><div style="overflow-x:auto;margin:0 -16px;padding:2px 16px">${themeSeg(theme)}</div></div><div class="mt12" data-themebody>${themeBody(theme)}</div>
      <section class="card pad mt32"><h2 class="h2">Where this trail went</h2><div class="mt12">${forkTree()}</div></section>
      <h2 class="h1 mt32" style="font-size:30px">Book this trail</h2><p class="sub mt8">Links only. Each one says who earns.</p><div class="mt12">${lanes}</div><div class="mt16">${tips}</div></main>
      <div class="dock">${follow('lg')}${thank()}</div>${tabbar('pub', 'trails')}</div>`;
  }

  /* ======================================================================
     6 · Creator profile
     ====================================================================== */
  const MORE = [['a-6', TR.title + ', ' + TR.tail, '5 days · Dec 2025', 214, 38], ['c-1', 'Highway 50 in a snowstorm', '2 days · Feb 2025', 61, 9], ['a-4', 'Sunrise piers of the West', '7 days · Mar 2025', 132, 21], ['a-1', 'Emerald Bay in one day', '1 day · Oct 2024', 88, 14], ['b-3', 'Lake days with a toddler', '4 days · Jul 2024', 340, 51], ['c-4', 'Spooner to Tahoe City', '3 days · Jan 2024', 211, 19]];
  const trailCard = ([p, t, m, th, fo]) => `<article class="stub" style="overflow:visible">${photo(p, ph ? 150 : 170, '', '', 'border-radius:var(--rw) var(--rw) 0 0')}<div class="sb" style="gap:8px"><b class="d" style="font-size:17px">${t}</b><span class="t">${m}</span><div class="perf" style="margin:6px -14px;--perf:var(--line2)"></div><div class="row" style="gap:14px;font-size:14px;color:var(--ink2)"><span class="row" style="gap:5px">${I('spark')}<b style="color:var(--ink)">${th}</b> thanks</span><span class="row" style="gap:5px">${I('fork')}<b style="color:var(--ink)">${fo}</b> follows</span></div></div></article>`;
  function profile() {
    const head = `<section class="card" style="overflow:hidden">${photo('a-6', ph ? 140 : 210, '', '', 'border-radius:0')}<div class="pad" style="display:grid;gap:12px;padding-top:0"><div class="row" style="align-items:flex-end;margin-top:-48px"><span class="av lg">${J.ini}</span><span class="sp"></span>${dk ? `<a class="cxl" data-press>${J.site} ${ext}</a>` : ''}</div>
      <div class="row wrapr"><h1 class="h1">${J.name}</h1>${sample()}</div><p class="sub" style="font-size:${ph ? 17 : 16}px;max-width:620px">Snow, short trails, two kids under ten. Every trip here started as a post on my blog.</p>
      <div class="row" style="gap:${ph ? 18 : 32}px"><div class="stat"><b>7</b><span>trails</span></div><div class="stat"><b>1,046</b><span>thanks</span></div><div class="stat"><b>152</b><span>follows</span></div><div class="stat"><b>2024</b><span>sharing since</span></div></div>
      <div class="row">${thank('1,046', 'Thank Juno')}</div></div></section>`;
    if (dk) return `<div class="ab dk page ${mode}">${top('pub', 'trails', `<button class="btn fill" data-press>${I('plus')}Leave a trail</button>${avatar('A')}`)}
      <main class="wrap" style="padding-top:96px">${head}<div class="row mt32"><h2 class="h1" style="font-size:32px">Trails</h2><span class="sp"></span><div class="seg"><button class="on">Most thanked</button><button>Newest</button></div></div>
      <div class="mt16" style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px">${MORE.map(trailCard).join('')}</div></main></div>`;
    return `<div class="ab ph page ${mode}">${sbar()}<main class="wrap">${ptop(`<button class="iconbtn" data-press>${I('ext')}</button>`)}${head}<h2 class="h1 mt32" style="font-size:28px">Trails</h2><div class="stack mt12">${MORE.slice(0, 3).map(trailCard).join('')}</div></main>${tabbar('pub', 'trails')}</div>`;
  }

  /* ======================================================================
     7 · Creator stats
     ====================================================================== */
  function stats() {
    const readers = [22, 30, 26, 41, 38, 52, 47, 61, 58, 72, 66, 80, 75, 92, 88, 101, 97, 120, 110, 131, 128, 140, 136, 151, 162, 158, 171, 180, 176, 198];
    const mx = Math.max(...readers);
    const bars = `<div class="bars">${readers.map((v, i) => `<i class="${i > 26 ? 'hi' : ''}" style="height:${Math.round(v / mx * 100)}%"></i>`).join('')}</div>`;
    const focal = `<section class="tk ink" style="display:grid;gap:10px;align-content:start"><span class="eyebrow">Families who thanked you</span><div class="row" style="align-items:baseline;gap:12px"><span class="big" style="font-size:${ph ? 56 : 72}px">${J.thanks}</span><span class="bdg ok">+18 this week</span></div><p class="sub">on ${TR.title}. 1,046 across your 7 trails.</p><div class="perf"></div>
      ${[['O', 'The Okafors', 'thanked you', '2 h', 3], ['A', 'Abhi’s family', 'followed it for Dec 19', '1 d', 5], ['P', 'Priya R.', 'thanked you', '1 d', 2], ['M', 'Marcus T.', 'thanked you', '3 d', 6]].map(([a, n, w, t, c]) => `<div class="row" style="gap:10px;font-size:${ph ? 16 : 15}px"><span class="av sm c${c}" style="box-shadow:none">${a}</span><span style="flex:1"><b>${n}</b> <span style="color:var(--up-fg2)">${w}</span></span><span class="fine">${t}</span></div>`).join('')}<div class="perf"></div><div class="quote">“We followed your trail for Christmas. The chain tip alone saved us an hour.”<small>Abhi’s family, with their thank-you</small></div><div class="row" style="gap:8px"><button class="btn tonal" data-press>${I('chat')}Say thanks back</button><button class="btn text" data-press>All 214</button></div></section>`;
    const rd = `<section class="card pad" style="display:grid;gap:10px"><div class="row"><span class="eyebrow">Readers</span><span class="sp"></span><span class="fine">30 days</span></div><div class="stat"><b>${J.readers}</b><span>people read ${TR.title}</span></div>${bars}</section>`;
    const fo = `<section class="card pad" style="display:grid;gap:8px"><div class="row"><span class="eyebrow">Follows</span><span class="sp"></span><span class="bdg ok">+4</span></div><div class="stat"><b>${J.follows}</b><span>families made it their trip</span></div>${forkTree({ compact: true })}</section>`;
    const clicks = `<section class="card pad" style="display:grid;gap:10px"><div class="row"><span class="eyebrow">Clicks to partners</span><span class="sp"></span><span class="fine">30 days</span></div>${[['flight', 'Flights · yours', 63, 63], ['tix', 'Snowshoes · Klook', 41, 41], ['stay', 'Your cabin · Vrbo', 28, 28], ['tix', 'Ski school · direct', 19, 19]].map(([k, n, v]) => `<div class="hbar k-${k}"><span>${n}</span><span class="tr"><i style="width:${v / 63 * 100}%"></i></span><b>${v}</b></div>`).join('')}<p class="fine">Clicks we sent. What you earned shows in your Travelpayouts account, not here; we won’t guess it.</p></section>`;
    const lk = `<section class="card pad" style="display:grid;gap:10px"><span class="eyebrow">Your links</span><div class="row" style="gap:10px">${kt('flight', 'plane', 'sm')}<span style="flex:1">Aviasales marker 48213</span><span class="bdg ok">${I('check')}On</span></div><div class="row" style="gap:10px">${kt('tix', 'ticket', 'sm')}<span style="flex:1">Klook</span><span class="bdg">GitAway’s for now</span></div><div class="row" style="gap:10px">${kt('stay', 'cabin', 'sm')}<span style="flex:1">Your Vrbo cabin</span><span class="bdg plain">No commission</span></div></section>`;
    const seg = `<div class="seg"><button data-press>7 days</button><button class="on" data-press>30 days</button><button data-press>All</button></div>`;
    if (dk) return `<div class="ab dk ${mode}">${top('creator', 'stats', `${beacon('spark', 'Thanks this week', '+18')}${avatar('J')}`)}
      <main class="wrap"><div class="row"><div><span class="eyebrow">Stats · ${sample().replace('Sample creator', 'Sample numbers')}</span><h1 class="h1 mt8">Your trails, this month</h1></div><span class="sp"></span>${seg}</div>
      <div class="mt16" style="display:grid;grid-template-columns:1.1fr 1fr 1fr;grid-template-rows:auto auto;gap:14px">${focal.replace('style="', 'style="grid-row:span 2;')}${rd}${fo}${clicks}${lk}</div></main></div>`;
    return `<div class="ab ph page ${mode}">${sbar()}<main class="wrap">${ptop(avatar('J'))}<h1 class="h1" style="margin:6px 0 12px">Your trails</h1>${seg}<div class="stack mt12">${focal}${rd}${clicks}${fo}</div></main>${tabbar('trail', 'stats')}</div>`;
  }

  /* ======================================================================
     8 · The claim link
     ====================================================================== */
  function claim() {
    const prev = `<section class="tk" style="display:grid;gap:12px;padding:0;overflow:hidden">${photo('a-6', ph ? 150 : 220, '', '', 'border-radius:0')}<div style="padding:0 18px 18px;display:grid;gap:10px"><span class="tno">Draft · not public</span><h2 class="h2">${TR.title}, ${TR.tail}</h2><p class="fine">Drafted by GitAway on Nov 2 from ${J.site}/snow-week-tahoe</p><div class="perf"></div>${DAYS.map((d) => `<div class="trow k-see"><time><i></i>Day ${d.n}</time><b>${d.name}</b></div>`).join('')}</div></section>`;
    const form = `<div class="stack" style="gap:16px"><span class="eyebrow">For ${J.name} · ${sample()}</span><h1 class="hero" style="font-size:${ph ? 40 : 60}px">Is this yours, <em>Juno?</em></h1><p class="lede">We drafted this trail from your post so families can follow it. It isn’t public. Claim it to fix it, publish it under your name, and get the thanks.</p>
      <div class="fld"><label>Your email</label><div class="inbox focus">${I('mail')}juno@${J.site}</div></div>
      <label class="row" style="gap:12px;font-size:${ph ? 17 : 16}px"><span class="tick on">${I('check')}</span>This is my post</label>
      <div class="row wrapr"><button class="btn fill" style="height:52px;padding:0 24px;font-size:17px;${ph ? 'width:100%' : ''}" data-press>${I('check')}Claim this trail</button><button class="btn text" style="${ph ? 'height:48px;width:100%' : ''}" data-press>Not mine, take it down</button></div>
      <p class="fine">We send a sign-in link; no password. Unclaimed drafts are deleted after 30 days.</p></div>`;
    if (dk) return `<div class="ab dk ${mode}">${top('pub', 'creators', `<button class="btn text" data-press>Sign in</button>`)}<main class="wrap" style="display:grid;grid-template-columns:1fr 440px;gap:64px;align-items:center;padding:120px 120px 40px">${form}${prev}</main></div>`;
    return `<div class="ab ph page ${mode}">${sbar()}<main class="wrap" style="padding-bottom:40px">${ptop()}${form}<div class="mt24">${prev}</div></main></div>`;
  }

  /* ======================================================================
     9 · The founder's /admin creator list
     ====================================================================== */
  const CREATORS = [
    ['JP', 'Juno Park', J.site, '7 · 7', ['ok', 'Live'], '1,046', 152, 151, '2 h', 1],
    ['MA', 'Mateo Alves', 'mateoontrains.com', '3 · 0', ['warn', 'Invited'], '—', '—', '—', '1 d', 2],
    ['RK', 'Rina Kato', 'youtube.com/@rinagoes', '5 · 4', ['ok', 'Live'], 380, 41, 66, '3 h', 3],
    ['DO', 'Dee Okoro', 'instagram.com/deeroams', '2 · 0', ['', 'Claimed'], '—', '—', '—', '5 h', 4],
    ['TS', 'Tom & Sal', 'twosmallsuitcases.blog', '4 · 2', ['ok', 'Live'], 122, 18, 30, '1 d', 5],
    ['LH', 'Lia Hart', 'liahart.com', '1 · 0', ['warn', 'Invited'], '—', '—', '—', '2 d', 6],
    ['BN', 'Ben Nash', 'bennash.co', '2 · 0', ['plain', 'Taken down'], '—', '—', '—', '6 d', 2],
  ];
  function admin() {
    const comp = `<div class="composer" style="padding:12px 14px;flex-direction:row;display:flex;align-items:center;gap:12px"><span class="field" style="min-height:0;font-size:17px;flex:1">Paste a creator’s post to draft a trail and get a claim link</span><button class="btn fill" style="height:44px" data-press>${I('spark')}Draft for them</button></div>`;
    const tiles = [['Creators', 24], ['Live trails', 21], ['Thanks this week', 96], ['Partner clicks · 7 d', 412]];
    const chips = `<div class="row wrapr">${[['All', 24, 1], ['Invited', 9], ['Claimed', 6], ['Live', 7], ['Taken down', 2]].map(([n, c, on]) => `<span class="chip ${on ? 'on' : ''}">${n} · ${c}</span>`).join('')}</div>`;
    const bdg = ([c, t]) => `<span class="bdg ${c}">${c === 'ok' ? '<i></i>' : ''}${t}</span>`;
    if (dk) return `<div class="ab dk ${mode}">${top('admin', 'creators', avatar('A'))}<main class="wrap">
      <div class="row"><h1 class="h1">Creators</h1>${sample('Sample data')}<span class="sp"></span></div>
      <div class="mt16" style="display:grid;grid-template-columns:1.6fr repeat(4,1fr);gap:12px;align-items:stretch">${comp}${tiles.map(([n, v]) => `<div class="card pad stat"><b>${v}</b><span>${n}</span></div>`).join('')}</div>
      <div class="mt16 row">${chips}<span class="sp"></span><div class="inbox" style="height:40px;font-size:15px;width:260px">${I('search')}<span class="ink2" style="font-weight:500">Find a creator</span></div></div>
      <section class="card mt12" style="padding:14px 8px 4px"><table class="tbl"><thead><tr><th>Creator</th><th>Trails · live</th><th>Status</th><th class="num">Thanks</th><th class="num">Follows</th><th class="num">Clicks 30 d</th><th>Last</th><th></th></tr></thead><tbody>
      ${CREATORS.map(([a, n, s, tr, st, th, fo, cl, la, c], i) => `<tr class="${i === 1 ? 'sel' : ''}"><td><div class="row" style="gap:10px"><span class="av sm c${c}" style="${c === 1 ? 'background:var(--k-see)' : ''}">${a}</span><div><b>${n}</b><div class="fine">${s}</div></div></div></td><td>${tr}</td><td>${bdg(st)}</td><td class="num">${th}</td><td class="num">${fo}</td><td class="num">${cl}</td><td class="fine">${la}</td><td style="text-align:right">${st[1] === 'Invited' ? `<button class="btn sm fill" data-press>${I('link')}Copy claim link</button>` : `<button class="btn sm tonal" data-press>Open</button>`}</td></tr>`).join('')}
      </tbody></table></section></main></div>`;
    return `<div class="ab ph page ${mode}">${sbar()}<main class="wrap">${ptop(avatar('A'))}<div class="row"><h1 class="h1">Creators</h1><span class="sp"></span>${sample('Sample')}</div>
      <div class="composer mt12"><div class="field" style="min-height:60px">Paste a creator’s post to draft a trail for them</div><button class="btn fill lg" data-press>${I('spark')}Draft for them</button></div>
      <div class="mt12" style="overflow:hidden;white-space:nowrap">${chips.replace('wrapr', '')}</div>
      <div class="stack mt12" style="gap:10px">${CREATORS.slice(0, 5).map(([a, n, s, tr, st, th, fo, cl, la, c]) => `<article class="card pad" style="display:grid;gap:10px"><div class="row" style="gap:10px"><span class="av sm c${c}" style="${c === 1 ? 'background:var(--k-see)' : ''}">${a}</span><div style="flex:1"><b style="font-size:17px">${n}</b><div class="fine">${s}</div></div>${bdg(st)}</div><div class="row fine" style="gap:16px"><span>Trails ${tr}</span><span>${I('spark')} ${th}</span><span>${I('fork')} ${fo}</span></div>${st[1] === 'Invited' ? `<button class="btn fill sm" data-press>${I('link')}Copy claim link</button>` : ''}</article>`).join('')}</div></main></div>`;
  }

  /* ======================================================================
     10 · Where to? (any destination)
     ====================================================================== */
  function calendar() {
    const dows = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
    let c = dows.map((d) => `<span class="dow">${d}</span>`).join('');
    for (let i = 29; i <= 30; i++) c += `<span class="mute">${i}</span>`;  // Dec 1 2026 is a Tuesday
    for (let d = 1; d <= 31; d++) c += `<span class="${d === 19 ? 'a' : d === 26 ? 'b' : d > 19 && d < 26 ? 'in' : ''}">${d}</span>`;
    for (let d = 1; d <= 2; d++) c += `<span class="mute">${d}</span>`;
    return `<div class="row"><b class="h3">December 2026</b><span class="sp"></span><button class="xbtn" data-press>${I('back')}</button><button class="xbtn" style="transform:scaleX(-1)" data-press>${I('back')}</button></div><div class="cal mt8">${c}</div>`;
  }
  function where() {
    const ages = (sel) => `<div class="ages">${[5, 6, 7, 8, 9, 10, 11, 12, 13].map((a) => `<button class="${a === sel ? 'on' : ''}" data-press>${a}</button>`).join('')}</div>`;
    const dest = `<div style="position:relative"><div class="inbox big focus">${I('search')}Lake Tahoe<span class="caret" style="display:inline-block;width:2px;height:1em;background:var(--ink);margin-left:-6px"></span></div>
      </div><div class="row wrapr mt12"><span class="chip on">${I('check')}Lake Tahoe · CA and NV</span><span class="chip">South Lake Tahoe</span><span class="chip">Tahoe City</span><span class="chip">Truckee</span></div>`;
    const dates = `<section class="card pad">${calendar()}<p class="fine mt8">Sat Dec 19 – Sat Dec 26 · 7 nights</p></section>`;
    const who = `<section class="card pad" style="display:grid;gap:14px"><span class="eyebrow">Who’s coming</span>
      <div class="row"><b style="flex:1;font-size:17px">Adults</b><div class="step"><button data-press>−</button><b>2</b><button data-press>+</button></div></div>
      <div class="row"><b style="flex:1;font-size:17px">Kids</b><div class="step"><button data-press>−</button><b>2</b><button data-press>+</button></div></div>
      <div class="fld"><label>Kid 1 · age</label>${ages(8)}</div><div class="fld"><label>Kid 2 · age</label>${ages(11)}</div><p class="fine">Ages pick the right lift tickets, ski school and car seats.</p></section>`;
    const air = `<section class="card pad" style="display:grid;gap:12px"><span class="eyebrow">Home airport</span><div class="inbox">${I('plane')}SFO <span class="ink2" style="font-weight:500;font-size:15px">San Francisco</span></div><div class="row wrapr"><span class="chip">Also OAK</span><span class="chip">Also SJC</span></div><div class="tip" style="background:var(--k-flight-t);color:var(--k-flight-i)">${I('spark')}<span>Fly into <b>Reno (RNO)</b>: it’s 1 h 20 to the lake, Sacramento is 2 h.</span></div></section>`;
    const ticket = `<section class="tk ink" style="display:grid;gap:12px"><span class="eyebrow">Your trip</span><h2 class="h1" style="font-size:34px">Tahoe at Christmas</h2>
      <div class="kv" style="grid-auto-flow:row;grid-template-columns:1fr 1fr;gap:14px"><div><small>Dates</small><b>Dec 19–26</b></div><div><small>Nights</small><b>7</b></div><div><small>Who</small><b>2 + 8, 11</b></div><div><small>Fly</small><b>SFO → RNO</b></div></div>
      <div class="perf"></div><p class="sub">Next: a book of tickets, one per lane.</p><div class="row" style="gap:8px">${[['flight', 'plane'], ['stay', 'cabin'], ['car', 'car'], ['tix', 'ticket']].map(([k, ic]) => kt(k, ic)).join('')}</div>
      <button class="btn fill" style="height:52px;font-size:17px" data-press>${I('arrow')}Plan it</button></section>
      <section class="card pad row" style="gap:12px">${photo('a-6', 56, '', '', 'width:72px;flex:none')}<div style="flex:1"><span class="eyebrow">Or follow a trail</span><b style="display:block;font-size:15px;margin-top:4px">${TR.title} · Juno Park</b><span class="fine">${J.follows} families followed it</span></div></section>`;
    if (dk) return `<div class="ab dk ${mode}">${top('trip', 'book', avatar('A'))}<main class="wrap" style="display:grid;grid-template-columns:1fr 380px;gap:24px;align-items:start">
      <div class="stack" style="gap:16px"><div><span class="eyebrow">New trip</span><h1 class="hero two-tone mt8" style="font-size:60px">Where to? <em>Anywhere.</em></h1></div>${dest}<div style="display:grid;grid-template-columns:1fr 1.1fr 1fr;gap:14px;align-items:start">${dates}${who}${air}</div></div>
      <div class="stack">${ticket}</div></main></div>`;
    return `<div class="ab ph page ${mode}">${sbar()}<main class="wrap" style="padding-bottom:110px"><div class="ptop"><button class="iconbtn" data-press>${I('x')}</button><span class="sp"></span><span class="fine">New trip</span></div>
      <h1 class="hero two-tone" style="font-size:44px;margin:4px 0 16px">Where to? <em>Anywhere.</em></h1>${dest}<div class="mt16">${dates}</div><div class="mt12">${who}</div><div class="mt12">${air}</div></main>
      <div class="dock solo"><button class="btn fill lg" data-press>${I('arrow')}Plan it · Dec 19–26 · 4 people</button></div></div>`;
  }

  /* ======================================================================
     13 · A booking's detail: Booked on X · Change or cancel
     ====================================================================== */
  function detail() {
    const pass = `<section class="tk kf k-stay on-k" style="padding:20px 22px;display:grid;gap:12px;position:relative;overflow:visible"><div class="row"><span class="eyebrow">Stay · 7 nights</span><span class="sp"></span>${I('cabin')}</div>
      <h1 class="h1" style="font-size:${ph ? 32 : 44}px">Cabin near Heavenly</h1><p class="sub" style="font-size:${ph ? 16 : 15}px">South Lake Tahoe · 3 bedrooms · wood stove</p>
      <div class="kv" style="${ph ? 'grid-auto-flow:row;grid-template-columns:1fr 1fr;' : ''}gap:${ph ? 14 : 28}px"><div><small>Check in</small><b>Sat Dec 19</b><span class="fine">4:00 PM</span></div><div><small>Check out</small><b>Sat Dec 26</b><span class="fine">10:00 AM</span></div><div><small>Guests</small><b>2 + 2 kids</b></div><div><small>Ref</small><b class="mono">••821</b></div></div>
      <span class="stamp big go" style="right:${ph ? 18 : 28}px;${ph ? 'bottom:178px' : 'top:30px'};--sc:var(--k-stay)">Booked<small>Dec 19–26</small></span>
      <div class="perf" style="--notch:var(--bg)"></div>
      <div class="row wrapr" style="gap:12px"><div class="booked-on"><span class="bo" style="font-size:${ph ? 17 : 16}px"><span class="ck">${I('check')}</span>Booked on Vrbo</span></div><span class="sp"></span><div style="text-align:${ph ? 'left' : 'right'}"><b class="big" style="font-size:${ph ? 34 : 40}px">$1,940</b><div class="fine">from your confirmation, Nov 3</div></div></div>
      <a class="btn fill" style="height:52px;font-size:17px;${ph ? '' : 'justify-self:start'}" data-press>Change or cancel on Vrbo ${ext}</a>
      <p class="fine">Vrbo handles changes, refunds and support. GitAway only keeps it on your trip.</p></section>`;
    const days = ['Sat 19', 'Sun 20', 'Mon 21', 'Tue 22', 'Wed 23', 'Thu 24', 'Fri 25', 'Sat 26'];
    const onTrip = `<section class="card pad" style="display:grid;gap:12px"><span class="eyebrow">On the trip</span><div style="display:grid;grid-template-columns:repeat(${ph ? 4 : 8},1fr);gap:6px">${days.slice(0, ph ? 4 : 8).map((d, i) => `<div class="dchip ${i === 0 ? 'on' : ''}" style="min-width:0;box-shadow:var(--sh1)"><b>${d.split(' ')[0]}</b><span>${d.split(' ')[1]}</span></div>`).join('')}</div>
      <div class="k-stay" style="height:12px;border-radius:6px;background:var(--kf);margin:0 ${ph ? 0 : 'calc(100% / 16)'}"></div>
</section>`;
    const there = `<section class="card pad" style="display:grid;gap:12px"><span class="eyebrow">Getting there</span><div class="rail">${rblk(['car', '2:20 PM', 'Pick up the SUV · RNO', 'car'])}<div class="drive">${I('road')}1 h 20 · US 50 · chains possible at Spooner</div>${rblk(['stay', '4:00 PM', 'Check in · Cabin near Heavenly', 'cabin'], 'Vrbo sends the door code 48 h before')}</div></section>`;
    const conf = `<section class="card pad" style="display:grid;gap:10px"><div class="row"><span class="eyebrow">From your confirmation</span><span class="sp"></span><span class="fine">pasted Nov 3</span></div>
      <div style="border-radius:14px;background:var(--s3);padding:14px;font:500 14px/1.55 var(--mono);color:var(--ink2)">Your booking is confirmed.<br>Reservation <span style="color:var(--ink)">••••821</span><br>Dec 19 – Dec 26, 2026 · 4 guests<br>Total <span style="color:var(--ink)">$1,940.00</span></div>
      <div class="row"><button class="btn tonal sm" data-press>${I('clip')}Fix a detail</button><button class="btn text sm" data-press>Remove from trip</button></div></section>`;
    if (dk) return `<div class="ab dk ${mode}">${top('trip', 'book', `${beacon('ticket', 'Book this trip ·', '2 of 6')}${avatar('A')}`)}<main class="wrap">
      <div class="row"><button class="btn tonal" data-press>${I('back')}Book this trip</button><span class="fine" style="margin-left:6px">Tahoe at Christmas · Stay</span></div>
      <div class="mt16" style="display:grid;grid-template-columns:1.25fr 1fr;gap:16px;align-items:start"><div class="stack" style="gap:14px">${pass}${onTrip}</div><div class="stack" style="gap:14px">${there}${conf}</div></div></main></div>`;
    return `<div class="ab ph page ${mode}">${sbar()}<main class="wrap"><div class="ptop"><button class="iconbtn" data-press>${I('back')}</button><span class="sp"></span><span class="fine">Book this trip</span></div><div class="mt8">${pass}</div><div class="mt12">${onTrip}</div><div class="mt12">${there}</div><div class="mt12">${conf}</div></main>${tabbar('trip', 'book')}</div>`;
  }

  /* ---------- mount ---------- */
  const SCREENS = { creators, pick, drafting, editor, trail, profile, stats, claim, admin, where, detail };
  document.documentElement.className = mode;
  document.body.style.margin = 0;
  document.body.style.background = mode === 'dark' ? '#000' : '#F2F2F5';
  document.body.innerHTML = SCREENS[S]();
  const root = document.body.firstElementChild;

  // press: everything tappable squashes on the spring (phone and desktop), never :active
  root.addEventListener('pointerdown', (e) => { const el = e.target.closest('[data-press],.btn,.chip,.seg button,.dchip'); if (!el) return; el.classList.add('press', 'pressed'); const up = () => { el.classList.remove('pressed'); removeEventListener('pointerup', up); }; addEventListener('pointerup', up); });
  // Thank them: the real count ticks up once, in place (cross-fade, no bounce)
  root.addEventListener('click', (e) => {
    const t = e.target.closest('[data-thank]');
    if (t && !t.classList.contains('done')) {
      root.querySelectorAll('[data-thank]').forEach((b) => { const n = b.querySelector('.n'); n.classList.add('out'); setTimeout(() => { n.textContent = (parseInt(n.textContent.replace(',', ''), 10) + 1).toLocaleString('en-US'); n.classList.remove('out'); b.classList.add('done'); }, 140); });
    }
    const th = e.target.closest('[data-theme]');
    if (th) {
      const body = root.querySelector('[data-themebody]'); if (!body) return;
      root.querySelectorAll('[data-theme]').forEach((b) => b.classList.toggle('on', b === th));
      body.innerHTML = themeBody(th.dataset.theme);
    }
  });
  document.documentElement.dataset.ready = '1';
})();
