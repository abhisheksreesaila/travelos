/* Shared parts for the three directions: chrome, day chips, the living weather widget, Up next with the next leg,
   booking widgets ("Booked on" + "Change or cancel", always together), the Book lanes in their honest states, the checklist
   ticket, the time rail, the stamp, and the paste-a-confirmation moment. Each direction composes these; motion follows
   one rule: phone = Liquid (morph from what you tapped, springs), desktop (.dk) = a calm fade. */
(function () {
  const { I, mark } = window.ICON;
  const { TRIP, DAYS, LANES, LANE_ORDER, NEXT, AROUND, PASTE, money } = window.TRIP;
  const WXI = { sun: 'sun', cloud: 'cloud', snow: 'cloudsnow', flurry: 'cloudsnow', wind: 'wind' };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  /* ---------- a tiny shared state: the selected day and what is booked ---------- */
  const S = { day: TRIP.nowDay, booked: new Set(LANE_ORDER), fns: {} };
  S.on = (k, f) => (S.fns[k] = S.fns[k] || []).push(f);
  S.emit = (k, v) => (S.fns[k] || []).forEach((f) => f(v));

  /* ---------- motion ---------- */
  const SPRING = 'linear(0, 0.023, 0.079, 0.154, 0.237, 0.322, 0.405, 0.482, 0.553, 0.617, 0.674, 0.723, 0.766, 0.803, 0.835, 0.862, 0.885, 0.905, 0.921, 0.935, 0.946, 0.955, 0.963, 0.97, 0.975, 0.98, 0.983, 0.986, 0.989, 0.991, 0.993, 0.994, 0.995, 0.996, 0.997, 0.997, 0.998, 0.998, 0.999, 0.999, 1)';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const M = {
    calm: (el) => !!(el.closest && el.closest('.ab.dk')),
    // a sheet or card grows out of the thing that was tapped (phone) or simply fades in where it lands (desktop)
    open(el, src) {
      if (reduced) return el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 150 });
      if (M.calm(el) || !src) return el.animate([{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'none' }], { duration: 180, easing: 'cubic-bezier(.2,0,0,1)' });
      const a = src.getBoundingClientRect(), b = el.getBoundingClientRect();
      const sx = a.width / b.width, sy = a.height / b.height;
      return el.animate([{ transformOrigin: '0 0', transform: `translate(${a.left - b.left}px, ${a.top - b.top}px) scale(${sx}, ${sy})`, opacity: .4, borderRadius: '24px' },
        { transformOrigin: '0 0', transform: 'none', opacity: 1 }], { duration: 520, easing: SPRING });
    },
    // an element flies into a target's place (phone); desktop never flies: the source fades out
    fly(el, target) {
      if (reduced || M.calm(el)) return el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 180, easing: 'cubic-bezier(.3,0,1,1)', fill: 'forwards' });
      const a = el.getBoundingClientRect(), b = target.getBoundingClientRect();
      const dx = b.left + b.width / 2 - (a.left + a.width / 2), dy = b.top + b.height / 2 - (a.top + a.height / 2);
      const s = Math.min(b.width / a.width, b.height / a.height, 1);
      return el.animate([{ transform: 'none', opacity: 1 }, { transform: `translate(${dx}px, ${dy}px) scale(${s})`, opacity: .2 }], { duration: 560, easing: SPRING, fill: 'forwards' });
    },
    // live values change in place: a short cross-fade, never a bounce
    swap(el, html) {
      if (!el || el.innerHTML === String(html)) return;
      if (reduced) { el.innerHTML = html; return; }
      el.classList.add('swap', 'out');
      setTimeout(() => { el.innerHTML = html; el.classList.remove('out'); }, 140);
    },
    stamp(host, laneId, opts = {}) {
      const L = LANES[laneId];
      const st = document.createElement('span');
      st.className = `stamp k-${L.kind} ${opts.big ? 'big' : ''}`;
      st.innerHTML = `<small>${L.booked.direct ? 'Bought direct' : 'Booked on'}</small>${esc(L.booked.on)}`;
      st.style.cssText = opts.pos || 'right: 14px; top: 12px;';
      host.appendChild(st);
      requestAnimationFrame(() => st.classList.add('go'));
      if (!M.calm(host)) { host.classList.remove('thud'); void host.offsetWidth; host.classList.add('thud'); }
      return st;
    },
  };

  /* ---------- press: one feedback for everything tappable (omxqua: press is JS, never :active) ---------- */
  function bindPress(root) {
    const sel = '.btn, .dchip, .cxl, .navpill button, .tabbar button, [data-press], .xbtn, .lchip';
    root.addEventListener('pointerdown', (e) => {
      const t = e.target.closest(sel); if (!t || reduced) return;
      t.classList.add('press', 'pressed'); if (t.offsetWidth <= 48) t.classList.add('sm-press');
      const up = () => { t.classList.remove('pressed', 'sm-press'); removeEventListener('pointerup', up); removeEventListener('pointercancel', up); };
      addEventListener('pointerup', up); addEventListener('pointercancel', up);
    });
  }

  /* ---------- chrome ---------- */
  const brand = () => `<a class="brand" href="#" aria-label="GitAway home">${mark()}<span>GitAway</span></a>`;
  function top(active = 'trip', beacon) {
    const b = beacon || { icon: 'snowshoe', text: 'Snowshoe · leave in', val: '23 min' };
    const nav = [['trip', 'Trip', 'home'], ['book', 'Book', 'ticket'], ['family', 'Family', 'users'], ['ask', 'Ask', 'mic']];
    return `<header class="top">${brand()}<nav class="navpill" aria-label="Sections">${nav.map(([k, n, ic]) => `<button class="${k === active ? 'on' : ''}" data-nav="${k}">${k === 'ask' ? I('mic') : ''}${n}</button>`).join('')}</nav>
      <div class="topr"><div class="beacon" data-press><span class="ring">${I(b.icon)}</span>${b.text} <b>${b.val}</b></div><span class="avatar" aria-label="Abhi">A</span></div></header>`;
  }
  const sbar = (t = '9:12') => `<div class="sbar"><span>${t}</span><span class="sg"><svg width="18" height="12" viewBox="0 0 18 12"><rect x="0" y="8" width="3" height="4" rx="1" fill="currentColor"/><rect x="5" y="5" width="3" height="7" rx="1" fill="currentColor"/><rect x="10" y="2.5" width="3" height="9.5" rx="1" fill="currentColor"/><rect x="15" y="0" width="3" height="12" rx="1" fill="currentColor"/></svg><svg width="16" height="12" viewBox="0 0 16 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1.5 4.5a9.5 9.5 0 0 1 13 0M4 7.3a6 6 0 0 1 8 0"/><circle cx="8" cy="10" r="1.2" fill="currentColor" stroke="none"/></svg><span class="bat"></span></span></div>`;
  function tabbar(active = 'trip') {
    const t = [['trip', 'Trip', 'home'], ['plan', 'Plan', 'cal'], ['ask', 'Ask', 'mic'], ['book', 'Book', 'ticket'], ['family', 'Family', 'users']];
    return `<nav class="tabbar" aria-label="Trip">${t.map(([k, n, ic]) => k === 'ask' ? `<button class="ask" aria-label="Ask">${I('mic')}</button>` : `<button class="${k === active ? 'on' : ''}" aria-label="${n}">${I(ic)}<span>${n}</span></button>`).join('')}</nav>`;
  }

  /* ---------- day chips: neutral, the selected one ink; a monochrome weather glyph, never a colour ---------- */
  const dayChips = (sel = S.day) => `<div class="days" role="tablist" aria-label="Days">${DAYS.map((d) => `<button role="tab" aria-selected="${d.i === sel}" class="dchip ${d.i === sel ? 'on' : ''} ${d.i === TRIP.nowDay ? 'today' : ''}" data-day="${d.i}"><b>${d.dow} ${d.d}</b><span>${I(WXI[d.wx.type])}${d.wx.hi}°</span></button>`).join('')}</div>`;
  function bindDays(root, fn) {
    root.addEventListener('click', (e) => {
      const b = e.target.closest('[data-day]'); if (!b) return;
      const i = +b.dataset.day; if (i === S.day) return;
      S.day = i;
      root.querySelectorAll('[data-day]').forEach((x) => { const on = +x.dataset.day === i; x.classList.toggle('on', on); x.setAttribute('aria-selected', on); });
      fn && fn(i, b);
      S.emit('day', i);
    });
  }

  /* ---------- the living weather widget ---------- */
  const wxMeta = (w) => `H ${w.hi}° · L ${w.lo}° · ${w.gust ? `gusts ${w.gust} mph` : `wind ${w.wind} mph`}`;
  function wxWidget(i = S.day, o = {}) {
    const d = DAYS[i], w = d.wx;
    return `<section class="w on-k k-wx wx ${o.cls || ''}" data-wx aria-live="polite">
      <canvas class="wx-cv" aria-hidden="true"></canvas>
      <div class="wx-in">
        <div class="eyebrow" data-calm>${o.place || 'South Lake Tahoe'} · <span data-f="date">${d.dow} ${d.date}</span></div>
        <div class="wx-now" data-calm><span class="big" data-f="hi">${w.hi}°</span><span class="wx-word" data-f="word">${w.word}</span></div>
        ${o.mini ? '' : `<div class="wx-meta" data-calm data-f="meta">${wxMeta(w)}</div><div class="wx-line" data-calm data-f="line">${w.line}</div>`}
        ${o.src === false ? '' : `<div class="wx-src" data-calm>${o.pre ? 'Typical late December · not a forecast yet' : 'Forecast · MET Norway · 6:10 AM'}</div>`}
      </div></section>`;
  }
  function mountWx(root, o = {}) {
    const out = [];
    root.querySelectorAll('[data-wx]').forEach((el, k) => {
      const eng = window.WXE.mount(el.querySelector('canvas'), { host: el, wx: DAYS[S.day].wx, seed: 11 + k, scale: o.scale || 1, pines: o.pines });
      el._eng = eng; out.push(el);
    });
    S.on('day', (i) => out.forEach((el) => updateWx(el, i)));
    return out;
  }
  function updateWx(el, i) {
    const d = DAYS[i], w = d.wx;
    const f = (k) => el.querySelector(`[data-f="${k}"]`);
    M.swap(f('date'), `${d.dow} ${d.date}`); M.swap(f('hi'), `${w.hi}°`); M.swap(f('word'), w.word);
    M.swap(f('meta'), wxMeta(w)); M.swap(f('line'), w.line);
    setTimeout(() => el._eng && el._eng.set(w), 20);
  }

  // before the trip there is no forecast yet: say so, and show what late December is usually like
  const PRE = { type: 'flurry', ground: .45, gust: 10, snow: '1–3 in' };
  const wxPre = (o = {}) => `<section class="w on-k k-wx wx ${o.cls || ''}" data-wxpre>
    <canvas class="wx-cv" aria-hidden="true"></canvas><div class="wx-in">
      <div class="eyebrow" data-calm>South Lake Tahoe · Dec 19–26</div>
      <div class="wx-now" data-calm><span class="big">40°</span><span class="wx-word">by day, typically</span></div>
      <div class="wx-meta" data-calm>Nights near 18° · snowy spells are common</div>
      <div class="wx-line" data-calm>The real forecast opens Dec 9, ten days out.</div>
      <div class="wx-src" data-calm>Climate normals · not a forecast yet</div></div></section>`;
  function mountWxPre(root) { root.querySelectorAll('[data-wxpre]').forEach((el, k) => window.WXE.mount(el.querySelector('canvas'), { host: el, wx: PRE, seed: 50 + k })); }

  /* ---------- Up next, with the next leg as its ticket stub ---------- */
  function upNext(o = {}) {
    const steps = NEXT.steps.slice(0, o.steps ?? 3);
    return `<section class="w w-up upnext ${o.cls || ''}" data-upnext>
      <div class="whead"><span class="eyebrow">Up next · leave in <span class="tnum" data-f="in">${NEXT.inMin} min</span></span><span class="sp"></span><span class="ktile sm k-tix">${I('snowshoe')}</span></div>
      <div class="up-t">Snowshoe at Taylor Creek</div>
      <div class="kv"><div><small>Leave</small><b>9:35</b></div><div><small>Drive</small><b>${NEXT.min} min</b></div><div><small>Starts</small><b>10:00</b></div>${o.wide ? `<div><small>Distance</small><b>${NEXT.mi} mi</b></div>` : ''}</div>
      <div class="perf"></div>
      ${o.legs === false ? '' : `<div class="legs" aria-label="Next leg, turn by turn">${steps.map((s) => `<div class="lg"><span class="lg-i">${I(s.icon)}</span><span class="lg-t">${s.verb} <b>${s.road}</b></span><span class="lg-d tnum">${s.mi} mi</span></div>`).join('')}</div>
      ${o.inline ? '' : `<div class="up-row"><span class="bdg warn">${I('chain')}R2 chains on CA 89</span></div>`}`}
      <div class="up-acts"><button class="btn fill">${I('nav')}Start directions</button>${o.inline ? `<span class="bdg warn">${I('chain')}R2 chains on CA 89</span>` : ''}</div>
      <div class="booked-on"><span class="bo"><span class="ck">${I('check')}</span>Booked on Klook</span><a class="cxl" href="#" title="Opens Klook’s own booking page">Change or cancel ${I('ext')}</a></div>
      ${o.rest ? `<div class="up-rest"><div class="eyebrow">Then today</div>${DAYS[TRIP.nowDay].plans.filter((p) => !p.drive && p.lane !== 'snowshoe').map((p) => `<div><span class="tnum">${p.t}</span><b>${p.title}</b></div>`).join('')}</div>` : ''}
    </section>`;
  }

  /* ---------- booking widgets (the trip's bookings, solid kind fills) ---------- */
  const BW = {
    flight: { eb: 'Flight home · Sat 26', t: 'RNO → SFO · 1:30 PM', s: 'United · nonstop · 4 seats', on: 'United' },
    stay: { eb: 'Stay · 5 nights left', t: 'Cabin near Heavenly', s: 'Check out Sat · 10:00 AM', on: 'Vrbo' },
    car: { eb: 'Car · chains packed', t: 'Mid-size SUV, AWD', s: 'Hertz · return Sat 11:45 AM', on: 'Expedia' },
    tix: { eb: 'Tickets · 3 booked', t: 'Snowshoe, 10:00', s: 'Snowmobile Tue · ski school Wed', on: 'Klook' },
  };
  const bkIcon = { flight: 'plane', stay: 'cabin', car: 'car', tix: 'ticket' };
  function bookingWidget(k, o = {}) {
    const b = BW[k];
    return `<section class="w on-k k-${k} bw ${o.cls || ''}" data-bw="${k}" data-press>
      <div class="whead"><span class="eyebrow">${b.eb}</span><span class="sp"></span>${I(bkIcon[k], 'ico')}</div>
      <div class="bw-t">${b.t}</div><div class="bw-s">${b.s}</div>
      <div class="bw-sp"></div>
      <div class="booked-on"><span class="bo"><span class="ck">${I('check')}</span>Booked on ${b.on}</span><a class="cxl" href="#">Change or cancel ${I('ext')}</a></div>
    </section>`;
  }

  /* ---------- Book lanes, in their honest states ---------- */
  const ext = I('ext');
  function laneState(L) {
    if (L.state === 'real') return `<span class="bdg real"><i></i>Real price · ${L.priceSeen}</span>`;
    if (L.state === 'partner') return `<span class="bdg partner">Search on ${L.partner}</span>`;
    if (L.state === 'direct') return `<span class="bdg direct">Buy direct</span>`;
    return `<span class="bdg plain">No commission</span>`;
  }
  function laneBody(L, o) {
    const foot = (acts, fine) => `<div class="ln-foot"><div class="ln-acts">${acts}</div><div class="ln-fine">${fine}</div></div>`;
    if (L.state === 'real') {
      const max = Math.max(...L.cal.map((c) => c.p));
      return `<div class="ln-pr"><div class="ln-price"><span class="big">$${L.price}</span><span>per person<br>round trip</span></div>
        ${o.bars === false ? '' : `<div class="ln-cal" aria-label="Cheapest fares by departure day">${L.cal.map((c) => `<div class="${c.sel ? 'sel' : ''}"><i style="height:${Math.round(10 + 26 * c.p / max)}px"></i><b>$${c.p}</b><span>${c.d}</span></div>`).join('')}</div>`}</div>
        ${foot(`<a class="btn fill" href="#">Search on Aviasales ${ext}</a>`, `${I('link')}<span>Partner link · we may earn a commission. Aviasales confirms the final price.</span>`)}`;
    }
    if (L.state === 'partner') return `<div class="ln-note">No price here: ${L.partner} has the live price. We won’t guess one.</div>
        ${foot(`<a class="btn fill" href="#">Search on ${L.partner} ${ext}</a>`, `${I('link')}<span>Partner link · we may earn a commission</span>`)}`;
    if (L.state === 'direct') return `<div class="ln-note">${L.note}</div>
        ${foot(`<a class="btn fill" href="#">Buy direct at ${L.direct} ${ext}</a>`, `${I('shield')}<span>The resort’s own site · no commission</span>`)}`;
    return `${o.note === false || !L.note ? '' : `<div class="ln-note">${L.note}</div>`}
        ${foot(L.links.map((p, k) => `<a class="btn ${k === 0 ? 'fill' : 'tonal'} lchip" href="#">${p} ${ext}</a>`).join(''), `${I('link')}<span>Plain link${L.links.length > 1 ? 's' : ''}, search filled in · we earn nothing</span>`)}`;
  }
  function lane(id, booked = S.booked.has(id), o = {}) {
    const L = LANES[id];
    if (booked) {
      const B = L.booked;
      return `<section class="lane card w booked k-${L.kind} ${o.cls || ''}" data-lane="${id}">
        <div class="ln-h"><span class="ktile">${I(L.icon)}</span><div class="ln-n"><b>${L.name}</b><span>${L.what}</span></div>
          <span class="bdg ok">${I('check')}${B.direct ? 'Bought direct' : 'Booked on ' + B.on}</span></div>
        <div class="ln-booked"><div class="ln-bt">${B.line}</div><div class="ln-bm"><span>${B.when}</span><b class="tnum">${money(B.total)}</b></div></div>
        <div class="ln-acts"><a class="cxl" href="#">Change or cancel on ${B.on} ${ext}</a></div>
        <div class="ln-fine">${I('mail')} From your confirmation · ref ••${B.conf.slice(-3)}</div>
      </section>`;
    }
    return `<section class="lane card w k-${L.kind} ${o.cls || ''}" data-lane="${id}">
      <div class="ln-h"><span class="ktile">${I(L.icon)}</span><div class="ln-n"><b>${L.name}</b><span>${L.what}</span></div>${laneState(L)}</div>
      <div class="ln-q">${I('search')}<span>${L.search}</span></div>
      ${laneBody(L, o)}
      ${o.back === false ? '' : `<div class="ln-back"><button class="btn text sm" data-paste="${id}">${I('clip')}Booked it? Paste the confirmation</button></div>`}
    </section>`;
  }

  /* ---------- the checklist ticket (Book this trip): booked rows turn into stubs ---------- */
  function checkRow(id) {
    const L = LANES[id], booked = S.booked.has(id);
    if (booked) return `<div class="crow stubrow k-${L.kind}" data-crow="${id}"><span class="ktile sm">${I(L.icon)}</span>
      <div class="cr-n"><b>${L.name}</b><span>${L.booked.direct ? 'Bought direct at' : 'Booked on'} ${L.booked.on}</span></div><b class="cr-v tnum">${money(L.booked.total)}</b></div>`;
    const v = L.state === 'real' ? `from $${L.price}` : L.state === 'direct' ? 'Buy direct' : L.state === 'partner' ? `Search ${L.partner}` : (L.links.length > 1 ? `${L.links.length} plain links` : 'Plain link');
    return `<div class="crow k-${L.kind}" data-crow="${id}"><span class="ktile sm">${I(L.icon)}</span>
      <div class="cr-n"><b>${L.name}</b><span>${v}</span></div><a class="btn tonal sm cr-go" href="#" aria-label="Open ${L.name}">${I('ext')}</a></div>`;
  }
  const bookedTotal = () => [...S.booked].reduce((n, id) => n + LANES[id].booked.total, 0);
  function ring(n, of) {
    const c = 2 * Math.PI * 15, p = n / of;
    return `<svg class="ring6" viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="15" fill="none" stroke="var(--up-line)" stroke-width="4"/><circle cx="18" cy="18" r="15" fill="none" stroke="var(--ok)" stroke-width="4" stroke-linecap="round" stroke-dasharray="${(c * p).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 18 18)"/></svg>`;
  }
  function checklist(o = {}) {
    const n = S.booked.size;
    return `<section class="w w-up ticket ${o.cls || ''}" data-ticket>
      <div class="whead"><span class="eyebrow">Book this trip</span><span class="sp"></span><span class="tk-n" data-f="ring">${ring(n, 6)}<b class="tnum">${n} of 6</b></span></div>
      <div class="tk-total"><span class="big tnum" data-f="total">${money(bookedTotal())}</span><span>booked so far<br>from your confirmations</span></div>
      <div class="perf"></div>
      <div class="crows">${LANE_ORDER.map(checkRow).join('')}</div>
      <div class="tk-foot"><p>${I('spark')}Back from a partner? We’ll ask “Did you book it?” and put it on the trip.</p>
      <button class="btn fill" data-paste="stay">${I('clip')}Paste a confirmation</button></div>
    </section>`;
  }

  /* ---------- the day on a time rail: start times beside kind-filled blocks, drives in between ---------- */
  function rail(i = S.day, o = {}) {
    const d = DAYS[i];
    return `<div class="rail" data-rail>${d.plans.map((p) => p.drive ? `<div class="rr leg"><span class="t tnum">${p.t.replace(' AM', '').replace(' PM', '')}</span><div class="lgx"><span class="lgx-i">${I('car')}</span><span><b>${window.TRIP.short(p.drive.min)} drive</b> · ${window.TRIP.mi(p.drive.km)} mi · ${p.drive.via}</span>${p.drive.chains ? `<span class="bdg warn">${I('chain')}${p.drive.chains.replace(' (sample)', '')}</span>` : ''}</div></div>`
      : `<div class="rr"><span class="t tnum">${p.t}</span><div class="blk on-k k-${p.kind}" data-press><span class="ktile sm">${I(p.icon)}</span><div class="bk-n"><b>${p.title}</b><span>${p.sub}</span>${p.lane && o.booked !== false ? `<span class="bk-on">${I('check')}${LANES[p.lane].booked.direct ? 'Bought direct' : 'Booked on ' + LANES[p.lane].booked.on}</span>` : ''}</div></div></div>`).join('')}</div>`;
  }

  /* ---------- family chat (iMessage-style: mine ink on the right, others grey on the left) ---------- */
  const family = (o = {}) => `<section class="w card fam ${o.cls || ''}"><div class="whead"><span class="ktile sm k-see">${I('chat')}</span><b class="fam-t">Family</b><span class="sp"></span><span class="avs"><span class="avatar">A</span><span class="avatar">${I('user')}</span><span class="avatar">11</span><span class="avatar">8</span></span></div>
    <div class="msgs">${o.short ? '' : `<div class="msg them"><span>Can we get hot chocolate after?</span><em>Kid, 11 · 8:58</em></div>`}<div class="msg me"><span>Yes. Boots on by 9:30, chains are in the back.</span></div></div></section>`;

  /* ---------- the paste moment ---------- */
  function pasteSheet() {
    return `<div class="ps-scrim" data-ps hidden><section class="paste" role="dialog" aria-label="Paste a confirmation">
      <div class="grab" aria-hidden="true"></div>
      <div class="ps-h"><div><div class="eyebrow">Bring a booking home</div><div class="h2">Paste the confirmation</div></div><button class="xbtn" data-ps-x aria-label="Close">${I('x')}</button></div>
      <div class="ps-box" data-ps-box><div class="ps-mail"><div class="ps-from"><span class="ktile sm k-stay">${I('mail')}</span><div><b>${PASTE.subject}</b><span>${PASTE.from}</span></div></div><pre>${esc(PASTE.body)}</pre></div><div class="ps-scan" aria-hidden="true"></div></div>
      <div class="ps-fields" data-ps-fields>${PASTE.fields.map((f, k) => `<div class="pf" style="--k:${k}"><span>${f.k}</span><b>${f.v}</b></div>`).join('')}</div>
      <div class="ps-acts"><button class="btn tonal" data-ps-x>Not now</button><button class="btn fill" data-ps-go>${I('spark')}Read it</button></div>
      <p class="ps-fine">We keep the place, dates, total and partner. The reservation number stays masked, and the email itself isn’t stored.</p>
    </section></div>`;
  }
  // phases: open → reading (scan + fields pop in) → land (fly/fade into target, stamp)
  function bindPaste(root, land) {
    const scrim = root.querySelector('[data-ps]'); if (!scrim) return;
    const sheet = scrim.querySelector('.paste');
    let src = null;
    const open = (from) => { src = from; scrim.hidden = false; scrim.dataset.phase = 'open'; M.open(sheet, from); };
    const close = () => { scrim.hidden = true; delete scrim.dataset.phase; };
    root.addEventListener('click', (e) => {
      const p = e.target.closest('[data-paste]'); if (p) { e.preventDefault(); open(p); return; }
      if (e.target.closest('[data-ps-x]')) { close(); return; }
      if (e.target.closest('[data-ps-go]')) read();
    });
    function read() {
      scrim.dataset.phase = 'reading';
      setTimeout(() => { scrim.dataset.phase = 'read'; }, M.calm(root) ? 900 : 1300);
      setTimeout(() => go(), M.calm(root) ? 1900 : 2500);
    }
    function go() {
      const target = land.target();
      const card = scrim.querySelector('[data-ps-fields]');
      scrim.dataset.phase = 'landing';
      const done = () => { close(); land.done(); };
      if (M.calm(root) || reduced) { sheet.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 180, fill: 'forwards' }).onfinish = () => { sheet.getAnimations().forEach((a) => a.cancel()); done(); }; return; }
      scrim.classList.add('fading');
      M.fly(card, target).onfinish = () => { card.getAnimations().forEach((a) => a.cancel()); scrim.classList.remove('fading'); done(); };
    }
    return { open, read, go, close, scrim };
  }
  // after a paste or "mark booked": re-render the lane, its checklist row and the totals in place, then stamp
  function land(root, id, o = {}) {
    S.booked.add(id);
    const laneEl = root.querySelector(`[data-lane="${id}"]`);
    if (laneEl) {
      const tmp = document.createElement('div'); tmp.innerHTML = lane(id, true, o.laneOpts || {});
      const nu = tmp.firstElementChild; laneEl.replaceWith(nu);
      M.calm(root) ? nu.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180 }) : nu.animate([{ transform: 'scale(.97)' }, { transform: 'none' }], { duration: 420, easing: SPRING });
      M.stamp(nu, id, { pos: 'right: 18px; top: 58px;' });
    }
    const row = root.querySelector(`[data-crow="${id}"]`);
    if (row) {
      const tmp = document.createElement('div'); tmp.innerHTML = checkRow(id);
      const nu = tmp.firstElementChild; row.replaceWith(nu);
      M.calm(root) ? nu.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180 }) : nu.animate([{ transform: 'translateY(-6px) scale(1.02)', opacity: .3 }, { transform: 'none', opacity: 1 }], { duration: 520, easing: SPRING });
    }
    root.querySelectorAll('[data-ticket]').forEach((t) => {
      M.swap(t.querySelector('[data-f="ring"]'), `${ring(S.booked.size, 6)}<b class="tnum">${S.booked.size} of 6</b>`);
      M.swap(t.querySelector('[data-f="total"]'), money(bookedTotal()));
    });
    S.emit('booked', id);
  }

  window.UI = { S, M, I, esc, wxPre, mountWxPre, top, sbar, tabbar, brand, dayChips, bindDays, wxWidget, mountWx, updateWx, upNext, bookingWidget, BW, lane, laneState, checklist, checkRow, rail, family, pasteSheet, bindPaste, land, bindPress, ring, bookedTotal, WXI };
})();
