// My trip as a journey (F-300, docs/briefs/journey.md, docs/design/journey/index.html). The page sends the trip as JSON (#pj-data, gitaway/journey.py) and this script draws the road: a line you
// scroll along with the booked things locked on it, your plans as cards you drag to retime (15 minutes at a time, a bubble says the time), the line you hover or tap to add, the stay as a band,
// flights as arcs, the weather where weather.py has it (ticks, curtains over the road, the scene itself) and the plans that sit too close folded into one ghost card. Every write is the grid's own
// POST /trip/plan/write, so the roles, the calendar's rules and the family's thread are the same; the script only says what happened and draws the answer.
// Time on the road is minutes from midnight of the trip's first day, in the place's own time. Motion is CSS (the --v2-* tokens and --spring); the only times here are the hold of a finger,
// and the snow and rain are drawn still when reduced motion is asked for.
(function () {
  var root = document.querySelector('[data-pl]'), pj = document.getElementById('pj'), raw = document.getElementById('pj-data');
  if (!root || !pj || !raw) return;
  var D = JSON.parse(raw.textContent);
  var road = pj.querySelector('.pj-road'), track = pj.querySelector('.pj-track'), hit = pj.querySelector('.pj-hit'), ghost = pj.querySelector('.pj-ghost'), bar = pj.querySelector('.pj-bar');
  var orb = pj.querySelector('.pj-orb'), clouds = pj.querySelector('.pj-clouds'), canvas = pj.querySelector('.pj-fall'), cx = canvas.getContext('2d');
  var RM = window.matchMedia('(prefers-reduced-motion: reduce)'), HOVER = window.matchMedia('(hover: hover) and (pointer: fine)');
  var PXH = [22, 64, 150], STEP_H = [6, 3, 1], PAD = 40, SNAP = 15, HOLD = 450, SLOP = 5, MAXROWS = 3;
  var z = 1, LY = 0, W = 0, ROW = 0, REM = 12, barB = 0, drag = null, pan = null, panMoved = false, loaded = false;
  var PTS = [], WINDOWS = [];

  function $(s, r) { return (r || document).querySelector(s); }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function icon(name) { var t = document.getElementById('pj-ico-' + name); return t ? t.innerHTML : ''; }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function active() { return root.dataset.mode !== 'grid'; }
  function toast(text, opts) { if (window.GA && GA.toast && text) GA.toast(text, opts || {}); }
  function px(m) { return (m - D.range[0]) / 60 * PXH[z] + PAD; }
  function at(x) { return D.range[0] + (x - PAD) / PXH[z] * 60; }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function tod(m) { m = ((Math.round(m) % 1440) + 1440) % 1440; var h = Math.floor(m / 60); return (h % 12 || 12) + ':' + pad(m % 60) + ' ' + (h < 12 ? 'AM' : 'PM'); }
  function hour(m) { return tod(m).replace(':00', ''); }
  function span(a, b) { var x = tod(a), y = tod(b); if (x.slice(-2) === y.slice(-2)) x = x.slice(0, -3); return x + '–' + y; }
  function dayOf(m) { return clamp(Math.floor(m / 1440), 0, D.days.length - 1); }
  function dayLabel(m) { return D.days[dayOf(m)].label; }
  function pxOf(prop) { var p = el('div'); p.style.cssText = 'position:absolute;visibility:hidden;width:var(' + prop + ')'; pj.appendChild(p); var w = p.offsetWidth; p.remove(); return w; }

  var KIND = { flight: 'Flight', stay: 'Stay', car: 'Car', tix: 'Ticket', food: 'Food', fun: 'Fun', outdoors: 'Outdoors', culture: 'Culture', travel: 'Travel' };
  var KICON = { flight: 'plane', stay: 'bed', car: 'car', tix: 'ticket', food: 'food', fun: 'star', outdoors: 'leaf', culture: 'sight', travel: 'road' };

  // ---- the weather: only what the server sent (weather.py) ----
  function prep() {
    PTS = D.points.slice().sort(function (a, b) { return a.t - b.t; });
    WINDOWS = [];
    PTS.forEach(function (p) {
      if (!p.s) return;
      var w = WINDOWS[WINDOWS.length - 1], end = p.t + p.h * 60;
      if (w && w.s === p.s && w.to === p.t) { w.to = end; w.p = Math.max(w.p, p.p); } else WINDOWS.push({ s: p.s, from: p.t, to: end, p: p.p });
    });
  }
  function pointAt(m) { for (var i = 0; i < PTS.length; i++) if (m >= PTS[i].t && m < PTS[i].t + PTS[i].h * 60) return PTS[i]; return null; }
  function words(w) {
    var snow = w.s === 'snow';
    return w.p < .5 ? (snow ? 'Light snow' : 'Light rain') : w.p < 2 ? (snow ? 'Snow' : 'Rain') : (snow ? 'Heavy snow' : 'Heavy rain');
  }
  function sunOf(day) { var s = D.days[day].sun; return s || [6.5 * 60, 18.5 * 60]; }
  function night(m) { var d = dayOf(m), s = sunOf(d), md = m - d * 1440; return md < s[0] || md > s[1]; }

  // ---- drawing ----
  function sizes() {
    REM = parseFloat(getComputedStyle(document.documentElement).fontSize) || 12;
    pj.style.height = Math.max(window.innerHeight - (pj.getBoundingClientRect().top + window.pageYOffset), 34 * REM) + 'px';      // the rest of the screen under the top bar
    var dock = pxOf('--pj-dock'), H = pj.clientHeight;
    LY = Math.round((H - dock) * .734);
    pj.style.setProperty('--ly', LY + 'px'); pj.style.setProperty('--sh', Math.round(LY / .734) + 'px');
    W = pxOf('--pj-w'); ROW = pxOf('--pj-row');
    barB = bar.getBoundingClientRect().bottom - pj.getBoundingClientRect().top;
  }
  function laneTop(lane) { return LY - 3.2 * REM - (ROW - .9 * REM) - lane * ROW; }

  function card(e, left, top) {
    var locked = e.locked, n = locked ? el('a', 'pj-ev locked k-' + e.kind) : el('div', 'pj-ev k-' + e.kind);
    n.setAttribute('data-j', ''); n.dataset.id = e.id; n.style.left = left + 'px'; n.style.top = top + 'px';
    var kd = el('span', 'kd'), i = el('i'); i.innerHTML = icon(KICON[e.kind] || 'pin'); kd.appendChild(i); kd.appendChild(document.createTextNode(KIND[e.kind] || 'Plan'));
    if (locked) { var lk = el('span', 'lk'); lk.innerHTML = icon('lock'); kd.appendChild(lk); }
    n.appendChild(kd); n.appendChild(el('b', null, e.title));
    var a = e.day * 1440 + e.start, b = e.day * 1440 + e.end;
    n.appendChild(el('span', 'tm', span(a, b) + (e.by && !locked ? ' · ' + e.by : '')));
    var hot = locked ? null : WINDOWS.filter(function (w) { return w.from < b && a < w.to; })[0];      // a real forecast of snow or rain over the plan: the Heads up
    if (hot) n.appendChild(el('span', 'nudge', words(hot) + ', ' + hour(hot.from) + ' to ' + hour(hot.to)));
    if (locked) { n.href = e.href; n.setAttribute('aria-label', e.title + ', ' + span(a, b) + '. Booked: opens the booking'); }
    else {
      n.setAttribute('role', 'button'); n.tabIndex = 0; n.setAttribute('aria-label', e.title + ', ' + span(a, b) + (D.edit ? '. Tap for 15 minute steps, or drag to move' : ''));
      if (D.edit) {
        var st = el('div', 'pj-step'), back = el('button', null, '−15 min'), fwd = el('button', null, '+15 min');
        back.type = fwd.type = 'button'; back.setAttribute('aria-label', e.title + ' 15 minutes earlier'); fwd.setAttribute('aria-label', e.title + ' 15 minutes later');
        back.addEventListener('click', function (ev) { ev.stopPropagation(); retime(e, a - SNAP); }); fwd.addEventListener('click', function (ev) { ev.stopPropagation(); retime(e, a + SNAP); });
        st.appendChild(back); st.appendChild(fwd); n.appendChild(st);
      }
    }
    track.appendChild(n);
    n.style.setProperty('--stem', Math.max(0, LY - top - n.offsetHeight) + 'px');
    n._e = e; bindCard(n);
    return n;
  }

  function crowd(c) {
    c.list.sort(function (a, b) { return a.day * 1440 + a.start - (b.day * 1440 + b.start); });
    var f = c.list[0], l = c.list[c.list.length - 1], fa = f.day * 1440 + f.start, la = l.day * 1440 + l.start;
    c.list.forEach(function (e) { var d = el('div', 'pj-gdot'); d.setAttribute('data-j', ''); d.style.left = px(e.day * 1440 + e.start) + 'px'; track.appendChild(d); });
    var n = el('div', 'pj-crowd'), btn = el('button'), dots = el('span', 'dots'), peek = el('div', 'pj-peek'), ul = el('ul');
    n.setAttribute('data-j', ''); n.style.left = c.x + 'px'; n.style.top = laneTop(c.lane) + 'px';
    btn.type = 'button'; btn.setAttribute('aria-expanded', 'false'); btn.setAttribute('aria-haspopup', 'true');
    c.list.forEach(function (e) { dots.appendChild(el('i', 'k-' + e.kind)); });
    btn.appendChild(dots); btn.appendChild(el('b', null, c.list.length + ' plans, close together'));
    btn.appendChild(el('span', 'tm', dayLabel(fa) + ' ' + tod(fa) + ' to ' + tod(la) + ' · ' + (HOVER.matches ? 'hover' : 'tap') + ' to see'));
    c.list.forEach(function (e) {
      var li = el('li', 'k-' + e.kind), t = el('span', null, tod(e.day * 1440 + e.start)); li.appendChild(el('i')); li.appendChild(t); li.appendChild(document.createTextNode(e.title));
      var end = el('em'); if (e.locked) end.innerHTML = icon('lock'); li.appendChild(end); ul.appendChild(li);
    });
    peek.appendChild(ul); peek.hidden = true;
    if (z < 2) { var sp = el('button', 'spread', 'Spread them out'); sp.type = 'button'; sp.addEventListener('click', function () { setZoom(2, (fa + la) / 2); }); peek.appendChild(sp); }
    n.appendChild(btn); n.appendChild(peek); track.appendChild(n);
    n.style.setProperty('--stem', Math.max(0, LY - laneTop(c.lane) - btn.offsetHeight) + 'px');
    var timer = 0;
    function show(on) { clearTimeout(timer); peek.hidden = !on; n.classList.toggle('open', on); btn.setAttribute('aria-expanded', String(on)); }
    n.addEventListener('pointerdown', function (e) { e.stopPropagation(); });
    btn.addEventListener('click', function () { show(peek.hidden); });
    if (HOVER.matches) { n.addEventListener('pointerenter', function () { show(true); }); n.addEventListener('pointerleave', function () { timer = setTimeout(function () { show(false); }, 220); }); }
    n.addEventListener('keydown', function (e) { if (e.key === 'Escape') { show(false); btn.focus(); } });
  }

  function layout() {
    var evs = D.events.slice().sort(function (a, b) { return a.day * 1440 + a.start - (b.day * 1440 + b.start) || (b.locked - a.locked); });
    var maxl = Math.max(1, Math.min(MAXROWS, Math.floor((laneTop(0) - (barB + 14)) / ROW) + 1)), GAP = .8 * REM, GW = W - 1.5 * REM, lanes = [], items = [], cur = null;
    evs.forEach(function (e) {
      var x = px(e.day * 1440 + e.start) - 14, lane = -1;
      for (var i = 0; i < maxl; i++) if (lanes[i] === undefined || lanes[i] <= x - GAP) { lane = i; break; }
      if (lane >= 0) { lanes[lane] = x + W; items.push({ e: e, x: x, lane: lane }); return; }
      if (cur && x <= cur.last + W) { cur.list.push(e); cur.last = x; return; }
      var v = -1;      // no row is free: the latest plan that is not booked folds in with this one (booked things fold last)
      for (var j = items.length - 1; j >= 0; j--) if (items[j].e && !items[j].e.locked && lanes[items[j].lane] === items[j].x + W) { v = j; break; }
      if (v < 0) { cur = { list: [e], x: x, lane: maxl - 1, last: x }; items.push(cur); return; }
      var vic = items.splice(v, 1)[0];
      cur = { list: [vic.e, e], x: vic.x, lane: vic.lane, last: x }; items.push(cur); lanes[vic.lane] = vic.x + GW;
    });
    return items;
  }

  function draw() {
    if (!active() || !pj.offsetParent) return;
    sizes();
    $$('[data-j]', track).forEach(function (n) { n.remove(); });
    var lo = D.range[0], hi = D.range[1];
    track.style.width = px(hi) + PAD * 2 + 'px';
    // ticks, each with the hour's sky and temperature where MET gave one
    var step = STEP_H[z] * 60;
    for (var m = Math.ceil(lo / step) * step; m <= hi; m += step) {
      if (m % 1440 === 0) continue;
      var t = el('div', 'pj-tick', hour(m)), p = pointAt(m);
      t.setAttribute('data-j', ''); t.style.left = px(m) + 'px';
      if (p && p.f != null) {
        var w = el('em', p.s ? 'wet' : ''), name = p.s || ((p.c || 0) >= 60 ? 'cloud' : night(m) ? 'moon' : 'sun');
        w.innerHTML = icon(name); w.appendChild(document.createTextNode(p.f + '°')); t.appendChild(w);
      }
      track.appendChild(t);
    }
    // a snow or rain window: a soft curtain over the road, with its words
    WINDOWS.forEach(function (w) {
      var c = el('div', 'pj-curtain'), s = el('span');
      c.setAttribute('data-j', ''); c.style.left = px(w.from) + 'px'; c.style.width = px(w.to) - px(w.from) + 'px'; c.style.top = barB + 14 + 'px'; c.style.height = Math.max(0, LY - barB - 14) + 'px';
      s.innerHTML = icon(w.s); s.appendChild(document.createTextNode(words(w) + ' · ' + hour(w.from) + ' to ' + hour(w.to))); c.appendChild(s); track.appendChild(c);
    });
    // each day: its name, its sky in weather.py's words, the sun
    D.days.forEach(function (d, i) {
      var n = el('div', 'pj-day', d.label), x = el('small'), wx = d.wx;
      n.setAttribute('data-j', ''); n.style.left = px(Math.max(lo, i * 1440)) + 'px';
      if (wx) {
        var wet = (wx.cond === 'rain' || wx.cond === 'snow') && !wx.typical && !wx.sample;
        n.appendChild(el('small', wet ? 'wet' : '', (wx.typical ? 'Typical' : wx.word) + (wx.hi != null ? ' · ' + wx.hi + '°/' + wx.lo + '°' : '')));
        if (wx.typical) n.appendChild(el('small', null, 'Not a forecast yet'));      // a forecast and the sample are named once, in the notes at the foot
      }
      if (d.sun) n.appendChild(el('small', null, 'Sun ' + tod(d.sun[0]) + ' to ' + tod(d.sun[1])));
      track.appendChild(n);
    });
    if (D.stay) {
      var s = el('a', 'pj-stay'); s.setAttribute('data-j', ''); s.href = D.stay.href; s.style.left = px(D.stay.from) + 'px'; s.style.width = px(D.stay.to) - px(D.stay.from) + 'px';
      s.innerHTML = icon('bed'); s.appendChild(document.createTextNode(D.stay.name + ' · ' + D.stay.nights + ' night' + (D.stay.nights === 1 ? '' : 's') + ' · booked')); track.appendChild(s);
    }
    if (D.now != null) {
      var nw = el('div', 'pj-now'); nw.setAttribute('data-j', ''); nw.style.left = px(D.now) + 'px'; nw.style.top = barB + 26 + 'px'; nw.style.height = LY - barB - 6 + 'px'; nw.appendChild(el('span', null, 'NOW')); track.appendChild(nw);
    }
    layout().forEach(function (it) {
      if (it.list) return crowd(it);
      var e = it.e;
      if (e.kind === 'flight') {      // a flight is a dashed arc over the road from take-off to landing
        var x1 = px(e.day * 1440 + e.start), x2 = px(e.day * 1440 + e.end), w = Math.max(x2 - x1, 30), h = Math.min(90, 30 + w / 3);
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('class', 'pj-arc'); svg.setAttribute('data-j', ''); svg.setAttribute('width', w); svg.setAttribute('height', h);
        svg.style.left = x1 + 'px'; svg.style.top = LY - h + 'px'; svg.innerHTML = '<path d="M0 ' + h + ' Q ' + w / 2 + ' ' + (-h * .6) + ' ' + w + ' ' + h + '"/>'; track.appendChild(svg);
      }
      card(e, it.x, laneTop(it.lane));
    });
    sizeFall(); scene();
  }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }

  // ---- the scene: the sky follows the hour at the centre of the view ----
  function lerp(a, b, f) { var pa = a.match(/\w\w/g).map(function (x) { return parseInt(x, 16); }), pb = b.match(/\w\w/g).map(function (x) { return parseInt(x, 16); }); return pa.map(function (v, i) { return Math.round(v + (pb[i] - v) * f).toString(16); }).map(function (h) { return h.length < 2 ? '0' + h : h; }).join(''); }
  //                    sky top   sky bottom far ridge  mid ridge  near ridge ground     sun or moon
  var NIGHT = ['0B1A2E', '17304A', '1D3550', '152A40', '0F2133', '0A1824', 'F2F1EA'], DAWN = ['F2A66B', 'FBD9A6', '6E7FA0', '4A6382', '2F4A60', '13303C', 'FFE7B8'], DAY = ['8EC9F5', 'D9EEFB', '5E9BC8', '3B7AA3', '24566F', '123A44', 'FFF6D8'];
  var DUSK = ['F07F4E', 'FBC08A', '5D6E92', '3E5677', '29405A', '12303B', 'FFD39A'], LATE = ['12223A', '274466', '22395A', '182C45', '102237', '0A1824', 'F2F1EA'];
  function keys(R, S) { return [[0, NIGHT], [Math.max(.1, R - .5), NIGHT], [R + .5, DAWN], [R + 1.9, DAY], [Math.max(R + 2, S - 1.9), DAY], [Math.max(R + 2.1, S - .6), DUSK], [Math.min(23.8, S + .4), LATE], [24, NIGHT]]; }
  function pcMix(c, f) { return lerp(c, (D.pc || '#6E6E73').replace('#', ''), f); }
  function scene() {
    if (!active() || !pj.offsetParent) return;
    var vw = road.clientWidth, centre = clamp(at(road.scrollLeft + vw / 2), 0, D.days.length * 1440 - 1), d = dayOf(centre), hr = (centre - d * 1440) / 60, s = sunOf(d), R = s[0] / 60, S = s[1] / 60;
    var K = keys(R, S), i = 0; while (i < K.length - 2 && K[i + 1][0] < hr) i++;
    var a = K[i], b = K[i + 1], f = clamp((hr - a[0]) / ((b[0] - a[0]) || 1), 0, 1), c = function (k) { return lerp(a[1][k], b[1][k], f); };
    var p = pointAt(centre), cloud = p && p.c != null ? p.c / 100 : 0, fall = p && p.s ? Math.min(1, .35 + p.p * .5) : 0, dark = night(centre), grey = Math.min(1, cloud * .7 + (p && p.s === 'snow' ? fall * .3 : 0));
    var light = clamp((parseInt(c(1).slice(0, 2), 16) / 255 - .1) / .7, 0, 1), mix = function (hex, m) { return pcMix(hex, m * (.35 + .65 * light)); };      // the place's colour shows more by day than by night
    var st = pj.style;
    st.setProperty('--jv-sky-top', '#' + lerp(c(0), dark ? '1E2733' : 'A3AFBA', grey)); st.setProperty('--jv-sky-bot', '#' + lerp(c(1), dark ? '2C3746' : 'D3D9DF', grey)); st.setProperty('--jv-sun', '#' + c(6));
    st.setProperty('--jv-r1', '#' + mix(lerp(c(2), dark ? '252F3D' : '7F8FA0', grey * .5), .26)); st.setProperty('--jv-r2', '#' + mix(c(3), .2)); st.setProperty('--jv-r3', '#' + mix(c(4), .14)); st.setProperty('--jv-ground', '#' + c(5));
    pj.classList.toggle('night', dark);
    var span = dark ? ((hr + 24 - S) % 24) / (24 - S + R) : (hr - R) / (S - R), phone = vw < 640;
    orb.style.left = vw * .1 + span * vw * .8 + 'px'; orb.style.top = LY * (phone ? .64 : .53) - Math.sin(Math.PI * clamp(span, 0, 1)) * LY * (phone ? .23 : .36) + 'px'; orb.style.opacity = 1 - grey * .75;
    clouds.style.opacity = Math.min(1, cloud * 1.1);
    setFall(p && p.s ? p.s : '', fall);
    var sx = road.scrollLeft;      // parallax: the far hills drift slower than the road, the clouds slower still
    [1, 2, 3].forEach(function (k) { var v = $('.pj-ridge.r' + k + ' svg', pj); v.style.transform = 'translateX(' + -(sx * [.04, .1, .2][k - 1]) % vw + 'px)'; });
    $('div', clouds).style.transform = 'translateX(' + -(sx * .02) % vw + 'px)';
  }

  // snow and rain: a canvas of flakes or streaks, moving only while the hour at the centre says so (drawn still with reduced motion)
  var flakes = [], fallKind = '', fallK = 0, falling = false;
  function sizeFall() {
    var r = window.devicePixelRatio || 1, w = pj.clientWidth, h = pj.clientHeight; canvas.width = w * r; canvas.height = h * r; canvas.style.width = w + 'px'; canvas.style.height = h + 'px'; cx.setTransform(r, 0, 0, r, 0, 0);
    flakes = []; for (var i = 0; i < 180; i++) flakes.push({ x: Math.random() * w, y: Math.random() * h, r: .8 + Math.random() * 2.2, v: .5 + Math.random() * 1.2, p: Math.random() * 6 });
  }
  function paintFall(move) {
    var w = pj.clientWidth, h = pj.clientHeight, n = Math.round(flakes.length * fallK), rain = fallKind === 'rain'; cx.clearRect(0, 0, w, h);
    cx.fillStyle = 'rgba(255,255,255,' + .9 * fallK + ')'; cx.strokeStyle = 'rgba(200,225,255,' + .7 * fallK + ')'; cx.lineWidth = 1.2;
    for (var i = 0; i < n; i++) {
      var f = flakes[i];
      if (move) { f.y += rain ? f.v * 7 : f.v; f.x += rain ? -1.2 : Math.sin(f.y / 40 + f.p) * .5; if (f.y > h) { f.y = -8; f.x = Math.random() * w; } }
      cx.beginPath();
      if (rain) { cx.moveTo(f.x, f.y); cx.lineTo(f.x - 3, f.y + 11 * f.r / 2); cx.stroke(); } else { cx.arc(f.x, f.y, f.r, 0, 7); cx.fill(); }
    }
  }
  function loop() { if (!falling || fallK < .02 || !active()) { falling = false; cx.clearRect(0, 0, canvas.width, canvas.height); return; } paintFall(true); requestAnimationFrame(loop); }
  function setFall(kind, k) {
    var was = fallKind + fallK; fallKind = kind; fallK = k;
    if (RM.matches) { if (was !== kind + k) paintFall(false); return; }      // reduced motion: the flakes stand still
    if (k >= .02 && !falling) { falling = true; requestAnimationFrame(loop); }
  }

  // ---- zoom, Now ----
  function setZoom(nz, centre) {
    var vw = road.clientWidth, c = centre != null ? centre : at(road.scrollLeft + vw / 2);
    z = clamp(nz, 0, 2); draw(); road.scrollLeft = px(c) - vw / 2;
    $$('.pj-seg button', pj).forEach(function (b) { b.setAttribute('aria-pressed', String(+b.dataset.z === z)); });
    pj.style.setProperty('--z', z); scene();
  }
  $$('.pj-seg button', pj).forEach(function (b) { b.addEventListener('click', function () { setZoom(+b.dataset.z); }); });
  $('#pj-now').addEventListener('click', function () { if (D.now != null) road.scrollTo({ left: px(D.now) - road.clientWidth / 2, behavior: RM.matches ? 'auto' : 'smooth' }); });
  road.addEventListener('scroll', function () { requestAnimationFrame(scene); }, { passive: true });
  road.addEventListener('wheel', function (e) {
    if (e.ctrlKey) { e.preventDefault(); setZoom(z + (e.deltaY < 0 ? 1 : -1)); }
    else if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) road.scrollLeft += e.deltaY;
  }, { passive: false });
  // grab the road with a mouse to travel along it
  road.addEventListener('pointerdown', function (e) {
    if (e.pointerType !== 'mouse' || e.button) return;
    var t = e.target; if (t !== road && t !== track && !t.classList.contains('pj-line') && !t.classList.contains('pj-hit')) return;
    pan = { x: e.clientX, s: road.scrollLeft }; panMoved = false;
  });

  // ---- a plan: drag to retime; booked things shake ----
  function bindCard(n) {
    var e = n._e;
    n.addEventListener('pointerdown', function (ev) {
      if (ev.button) return; ev.stopPropagation(); n._blocked = false;
      if (e.locked) { drag = { n: n, e: e, locked: true, pid: ev.pointerId, x0: ev.clientX, y0: ev.clientY, moved: false }; return; }
      if (!D.edit) return;
      var mouse = ev.pointerType === 'mouse';
      drag = { n: n, e: e, pid: ev.pointerId, x0: ev.clientX, y0: ev.clientY, s0: road.scrollLeft, left0: parseFloat(n.style.left), a0: e.day * 1440 + e.start, len: e.end - e.start, armed: false, moved: false, mouse: mouse, ms: e.day * 1440 + e.start, last: ev };
      if (!mouse) drag.hold = setTimeout(function () { if (drag && drag.n === n) { drag.armed = true; n.classList.add('drag'); if (navigator.vibrate) navigator.vibrate(8); } }, HOLD);      // a finger holds first; a plain swipe scrolls the road
    });
    n.addEventListener('click', function (ev) {
      if (e.locked) { if (n._blocked) { ev.preventDefault(); n._blocked = false; } return; }
      if (!D.edit) return;
      var was = n.classList.contains('sel'); $$('.pj-ev.sel', track).forEach(function (x) { x.classList.remove('sel'); }); n.classList.toggle('sel', !was); relabel();
    });
    n.addEventListener('keydown', function (ev) { if (!e.locked && D.edit && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); n.click(); } });
  }
  function relabel() { $$('.pj-ev', track).forEach(function (n) { n.style.setProperty('--stem', Math.max(0, LY - parseFloat(n.style.top) - n.offsetHeight) + 'px'); }); }
  function moveTo(d, ev) {
    var left = d.left0 + ev.clientX - d.x0 + (road.scrollLeft - d.s0), last = D.days.length * 1440 - d.len - 1;
    d.ms = clamp(Math.round(at(left + 14) / SNAP) * SNAP, 0, last); d.n.style.left = px(d.ms) - 14 + 'px';
    if (!d.bub) { d.bub = el('div', 'pj-bubble'); d.n.appendChild(d.bub); }
    d.bub.textContent = dayLabel(d.ms) + ' · ' + tod(d.ms);
  }
  var edge = 0, rafEdge = 0;
  function autoscroll() { if (!drag || !drag.armed || !edge) { rafEdge = 0; return; } road.scrollLeft += edge; moveTo(drag, drag.last); rafEdge = requestAnimationFrame(autoscroll); }
  window.addEventListener('pointermove', function (ev) {
    if (pan) { var dx = ev.clientX - pan.x; if (Math.abs(dx) > SLOP) { panMoved = true; road.classList.add('is-panning'); } road.scrollLeft = pan.s - dx; return; }
    if (!drag || ev.pointerId !== drag.pid) return;
    var dx2 = ev.clientX - drag.x0, dy = ev.clientY - drag.y0, far = Math.abs(dx2) > SLOP || Math.abs(dy) > SLOP;
    if (drag.locked) { if (far && !drag.moved) { drag.moved = true; drag.n._blocked = true; drag.n.classList.remove('shake'); void drag.n.offsetWidth; drag.n.classList.add('shake'); } return; }
    if (!drag.armed) {
      if (drag.mouse && far) { drag.armed = true; drag.n.classList.add('drag'); }
      else { if (!drag.mouse && (Math.abs(dx2) > 8 || Math.abs(dy) > 8)) { clearTimeout(drag.hold); drag = null; } if (!drag || !drag.armed) return; }
    }
    drag.moved = true; drag.last = ev; moveTo(drag, ev);
    var r = road.getBoundingClientRect(); edge = ev.clientX < r.left + 48 ? -14 : ev.clientX > r.right - 48 ? 14 : 0;
    if (edge && !rafEdge) rafEdge = requestAnimationFrame(autoscroll);
  });
  window.addEventListener('pointerup', function (ev) {
    if (pan) { pan = null; road.classList.remove('is-panning'); return; }
    if (!drag || ev.pointerId !== drag.pid) return;
    var d = drag; drag = null; edge = 0; clearTimeout(d.hold);
    if (d.locked) return;
    d.n.classList.remove('drag'); if (d.bub) d.bub.remove();
    if (d.armed && d.moved) { d.n._blocked = true; setTimeout(function () { d.n._blocked = false; }, 0); if (d.ms !== d.a0) retime(d.e, d.ms); else draw(); }
  });
  window.addEventListener('pointercancel', function (ev) { if (drag && ev.pointerId === drag.pid) { clearTimeout(drag.hold); drag.n.classList.remove('drag'); if (drag.bub) drag.bub.remove(); if (drag.armed) draw(); drag = null; edge = 0; } if (pan) { pan = null; road.classList.remove('is-panning'); } });
  window.addEventListener('touchmove', function (ev) { if (drag && drag.armed && !drag.mouse) ev.preventDefault(); }, { passive: false });

  // ---- writes: the grid's own route ----
  function post(data) {
    var body = new URLSearchParams(); for (var k in data) body.set(k, data[k]);
    return fetch('/trip/plan/write', { method: 'POST', body: body, credentials: 'same-origin' }).then(function (r) {
      return r.json().catch(function () { return { error: 'That did not work.' }; }).then(function (j) { j.ok = r.ok; return j; });
    });
  }
  function changed() { document.dispatchEvent(new CustomEvent('pl:changed', { detail: { plans: [], from: 'journey' } })); }      // the grid reads the trip again
  function undoer(res) { return res.undo ? { undo: function () { post({ op: 'undo', undo: JSON.stringify(res.undo) }).then(function (r) { if (!r.ok) toast(r.error || 'That did not work.', { error: true }); toast(r.toast); load(); changed(); }); } } : {}; }
  function retime(e, ms) {
    var day = Math.floor(ms / 1440), start = ms - day * 1440, len = e.end - e.start;
    return post({ op: 'edit', act: e.id, day: day, start: start, end: start + len }).then(function (res) {
      if (!res.ok) { toast(res.error || 'That did not work.', { error: true }); draw(); return; }
      var p = res.plan; if (p) { e.day = p.day; e.start = p.start; e.end = p.end; }
      draw(); toast(res.toast, undoer(res)); changed();
    });
  }

  // ---- hover the line to add; tap it on a phone ----
  function snapAt(ev) { return clamp(Math.round(at(ev.clientX - track.getBoundingClientRect().left) / SNAP) * SNAP, 0, D.days.length * 1440 - 61); }
  hit.addEventListener('pointermove', function (ev) {
    if (!D.edit || ev.pointerType !== 'mouse' || pan) return;
    var m = snapAt(ev); ghost.style.left = px(m) + 'px'; ghost.classList.add('on'); ghost.querySelector('span').textContent = '+ Add at ' + dayLabel(m) + ' ' + tod(m); ghost._m = m;
  });
  hit.addEventListener('pointerleave', function () { ghost.classList.remove('on'); });
  hit.addEventListener('click', function (ev) { if (D.edit && !panMoved) openAdd(snapAt(ev)); panMoved = false; });
  function openAdd(m) {
    closeAdd();
    var box = el('div', 'pj-add'), lab = el('label', null, dayLabel(m) + ' · ' + tod(m)), inp = el('input'), kinds = el('div', 'kinds'), row = el('div', 'row'), no = el('button', 'no', 'Cancel'), go = el('button', 'go', 'Add'), kind = 'fun';
    box.setAttribute('data-j', ''); box.setAttribute('role', 'dialog'); box.setAttribute('aria-label', 'Add a plan');
    inp.type = 'text'; inp.placeholder = "What's the plan?"; inp.maxLength = 40; inp.setAttribute('aria-label', "What's the plan?");
    D.kinds.forEach(function (k) {
      var b = el('button', null, k[1]); b.type = 'button'; b.setAttribute('aria-pressed', String(k[0] === kind));
      b.addEventListener('click', function () { kind = k[0]; $$('button', kinds).forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); }); }); kinds.appendChild(b);
    });
    no.type = go.type = 'button'; row.appendChild(no); row.appendChild(go); [lab, inp, kinds, row].forEach(function (n) { box.appendChild(n); });
    track.appendChild(box);
    var w = box.offsetWidth, left = clamp(px(m) - 20, road.scrollLeft + 8, road.scrollLeft + road.clientWidth - w - 8);
    box.style.left = left + 'px'; box.style.top = Math.max(barB + 8, LY - box.offsetHeight - 16) + 'px'; box.style.transformOrigin = Math.max(8, px(m) - left) + 'px 100%'; inp.focus({ preventScroll: true });
    function add() {
      var title = inp.value.trim(); if (!title) { inp.focus(); return; }
      go.disabled = true;
      post({ op: 'add', day: Math.floor(m / 1440), start: m % 1440, end: m % 1440 + 60, title: title, kind: kind }).then(function (res) {
        if (!res.ok) { go.disabled = false; toast(res.error || 'That did not work.', { error: true }); inp.focus(); return; }
        closeAdd(); toast(res.toast, undoer(res)); changed();
        load().then(draw);      // the plan as the server has it, with whose it is
      });
    }
    go.addEventListener('click', add); no.addEventListener('click', closeAdd);
    box.addEventListener('keydown', function (e) { if (e.key === 'Enter' && e.target === inp) add(); if (e.key === 'Escape') { closeAdd(); road.focus({ preventScroll: true }); } });
  }
  function closeAdd() { var b = $('.pj-add', track); if (b) b.remove(); }
  document.addEventListener('pointerdown', function (e) { if (!e.target.closest('.pj-add, .pj-hit')) closeAdd(); $$('.pj-ev.sel', track).forEach(function (n) { if (!n.contains(e.target)) { n.classList.remove('sel'); relabel(); } }); });
  if (!D.edit) hit.style.pointerEvents = 'none';

  // ---- Journey or Grid, kept on the device; the trip's More menu lives in whichever bar shows ----
  var more = $('.pl-trip [data-more]'), home = more ? more.parentNode : null, slot = $('#pj-more-slot');
  function setMode(mode) {
    root.dataset.mode = mode;
    try { localStorage.setItem('ga-plan-view', mode); } catch (e) { /* the choice is only for this visit */ }
    if (more && slot) (mode === 'journey' ? slot : home).appendChild(more);
    if (mode === 'journey') load().then(show); else { closeAdd(); window.scrollTo(0, 0); }
  }
  document.addEventListener('click', function (e) { var b = e.target.closest('[data-mode-set]'); if (b && root.contains(b)) setMode(b.dataset.modeSet); });
  function load() {
    return fetch('/trip/plan/journey', { credentials: 'same-origin' }).then(function (r) { if (!r.ok) throw new Error('journey'); return r.json(); }).then(function (j) { D = j; prep(); }).catch(function () { /* offline: what is drawn stays */ });
  }
  function show() {
    var vw = road.clientWidth, c = loaded ? at(road.scrollLeft + vw / 2) : null; loaded = true;
    $('#pj-now').hidden = D.now == null;
    setZoom(z, c);      // draws, keeping the centre
    if (c === null) {
      var first = D.events.length ? Math.min.apply(null, D.events.map(function (e) { return e.day * 1440 + e.start; })) : D.range[0];
      road.scrollLeft = D.now != null ? px(D.now) - vw / 2 : px(first) - vw * .3; scene();
    }
  }
  function size() { var vw = road.clientWidth, c = at(road.scrollLeft + vw / 2); sizeFall(); draw(); road.scrollLeft = px(c) - vw / 2; scene(); }
  var rs = 0; window.addEventListener('resize', function () { cancelAnimationFrame(rs); rs = requestAnimationFrame(function () { if (active() && pj.offsetParent) size(); }); });
  document.addEventListener('pl:changed', function (e) { if (!(e.detail && e.detail.from === 'journey') && active()) load().then(function () { draw(); }); });
  document.addEventListener('visibilitychange', function () { if (!document.hidden && active() && !drag) load().then(function () { draw(); }); });

  prep();
  if (active()) { if (more && slot) slot.appendChild(more); show(); }
})();
