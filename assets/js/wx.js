// F-201 · the living sky of a day: one small canvas engine behind a sky's words, on the weather blue (ported from docs/design/cockpit/core/wx.js).
// Snow falls and settles into a bank, the sun turns slowly, wind drives streaks and bends the pines, clouds drift. Adapted from Meng To's threejs-weather skill
// (MIT): density is a draw range over one preallocated pool (nothing is allocated when the weather changes), falling snow and settled snow are two separate
// values (the bank grows while it snows and stays on the next sunny day), and a windy day runs on a slow gust envelope. Every flake has its own size, speed
// and sway (falling-leaves skill: share nothing, or the eye finds the rhythm). The words stay readable: flakes fade to 18% inside the sky's [data-calm] boxes.
// Reduced motion draws one still frame. It pauses when off screen or when the tab is hidden. Nothing here is timed in milliseconds: it moves by the frame's dt.
//
//   GA.wx.mount(canvas, { host, wx: { kind, gust, ground }, seed, scale, pines })   -> { set(wx, { instant }), destroy() }
(function () {
  var GA = window.GA = window.GA || {};
  if (GA.wx) return;
  var POOL = 260;
  var live = new Set();
  var raf = 0, last = 0;
  var reducedQ = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
  var TYPES = {
    sun: { snow: 0, wind: 0.08, sun: 1, cloud: 0.05 },
    cloud: { snow: 0.04, wind: 0.22, sun: 0.22, cloud: 0.9 },
    snow: { snow: 1, wind: 0.42, sun: 0, cloud: 1 },
    flurry: { snow: 0.34, wind: 0.22, sun: 0.35, cloud: 0.6 },
    wind: { snow: 0, wind: 1, sun: 0.6, cloud: 0.35 },
    plain: { snow: 0, wind: 0, sun: 0, cloud: 0 }       // no weather known: a plain sky that claims nothing
  };
  function rng(seed) { var s = seed >>> 0; return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
  function reduced() { return reducedQ.matches; }

  function mount(cv, opts) {
    opts = opts || {};
    var ctx = cv.getContext && cv.getContext('2d');
    if (!ctx) return { set: function () {}, destroy: function () {} };
    var r = rng(opts.seed || 7), i;
    var flakes = [], streaks = [], clouds = [];
    for (i = 0; i < POOL; i++) flakes.push({ x: r(), y: r(), z: 0.35 + r() * 0.65, ph: r() * 6.28, sw: 0.4 + r() * 1.2, sp: 0.6 + r() * 0.8, a: 0.55 + r() * 0.4 });
    for (i = 0; i < 14; i++) streaks.push({ x: r(), y: r(), l: 0.5 + r() * 0.7, sp: 0.7 + r() * 0.6, ph: r() * 6.28 });
    for (i = 0; i < 4; i++) clouds.push({ x: r(), y: 0.08 + r() * 0.3, s: 0.7 + r() * 0.6, sp: 0.5 + r(), i: i });
    var pines = opts.pines === false ? [] : [{ x: 0.70, h: 30 }, { x: 0.76, h: 40 }, { x: 0.83, h: 26 }, { x: 0.89, h: 36 }, { x: 0.95, h: 28 }];
    var st = { snow: 0, wind: 0, sun: 0, cloud: 0, ground: 0, t: r() * 100 };
    var tgt = { snow: 0, wind: 0, sun: 0, cloud: 0, ground: 0 };
    var W = 0, H = 0, calm = [], visible = true;
    var scale = opts.scale || 1;

    function size() {
      var b = cv.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = b.width; H = b.height;
      cv.width = Math.max(1, Math.round(W * dpr)); cv.height = Math.max(1, Math.round(H * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      readCalm();
      if (reduced()) draw(0);
    }
    function readCalm() {
      var host = opts.host || cv.parentElement, b = cv.getBoundingClientRect();
      calm = Array.prototype.map.call(host.querySelectorAll('[data-calm]'), function (el) {
        var e = el.getBoundingClientRect();
        return [e.left - b.left - 6, e.top - b.top - 4, e.width + 12, e.height + 8];
      });
    }
    function set(w, o) {
      w = w || {}; o = o || {};
      var base = TYPES[w.kind] || TYPES.sun;
      tgt = { snow: base.snow * (w.kind === 'snow' ? (w.amount || 0.8) : 1), wind: Math.min(1, base.wind + (w.gust || 0) / 120), sun: base.sun, cloud: base.cloud,
              ground: w.ground != null ? w.ground : st.ground };
      if (o.instant || reduced()) { st.snow = tgt.snow; st.wind = tgt.wind; st.sun = tgt.sun; st.cloud = tgt.cloud; st.ground = tgt.ground; }
      readCalm();
      if (reduced()) draw(0); else kick();
    }
    function inCalm(x, y) { for (var k = 0; k < calm.length; k++) { var c = calm[k]; if (x > c[0] && x < c[0] + c[2] && y > c[1] && y < c[1] + c[3]) return true; } return false; }

    function draw(dt) {
      // every dial eases toward its target (critically damped, no overshoot); the bank is slower than the sky
      var k = 1 - Math.exp(-dt * 3.2), kg = 1 - Math.exp(-dt * 0.9);
      st.snow += (tgt.snow - st.snow) * k; st.wind += (tgt.wind - st.wind) * k; st.sun += (tgt.sun - st.sun) * k; st.cloud += (tgt.cloud - st.cloud) * k;
      st.ground += (tgt.ground - st.ground) * kg;
      st.t += dt;
      var gust = st.wind * (0.65 + 0.35 * Math.sin(st.t * 0.35) * Math.sin(st.t * 0.13 + 1));
      ctx.clearRect(0, 0, W, H);
      ctx.lineCap = 'round';
      if (st.sun > 0.02) {      // the sun: a disc, twelve slow rays, a breathing ring
        var sx = W - (opts.sunX != null ? opts.sunX : 54) * scale, sy = (opts.sunY != null ? opts.sunY : 46) * scale, R = 15 * scale;
        ctx.save(); ctx.globalAlpha = st.sun; ctx.translate(sx, sy);
        ctx.strokeStyle = 'rgba(255,255,255,.95)'; ctx.lineWidth = 2.2 * scale;
        ctx.rotate(st.t * 0.12);
        for (var a = 0; a < 12; a++) { ctx.rotate(Math.PI / 6); ctx.beginPath(); ctx.moveTo(R + 5 * scale, 0); ctx.lineTo(R + (a % 2 ? 9 : 12) * scale, 0); ctx.stroke(); }
        ctx.rotate(-st.t * 0.12);
        ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(0, 0, R, 0, 6.283); ctx.fill();
        ctx.globalAlpha = st.sun * (0.22 + 0.1 * Math.sin(st.t * 1.4)); ctx.lineWidth = 1.5 * scale;
        ctx.beginPath(); ctx.arc(0, 0, R + 20 * scale, 0, 6.283); ctx.stroke();
        ctx.restore();
      }
      if (st.cloud > 0.02) {    // clouds: soft white puffs at low alpha, drifting
        clouds.forEach(function (c) {
          c.x += dt * (0.006 + st.wind * 0.02) * c.sp; if (c.x > 1.25) c.x = -0.25;
          var cx = c.x * W, cy = c.y * H, s = 22 * c.s * scale;
          ctx.fillStyle = 'rgba(255,255,255,' + ((0.13 + c.i * 0.03) * st.cloud) + ')';
          ctx.beginPath(); ctx.arc(cx, cy, s, 0, 6.283); ctx.arc(cx + s * 0.9, cy - s * 0.35, s * 0.8, 0, 6.283); ctx.arc(cx + s * 1.8, cy, s * 0.9, 0, 6.283); ctx.arc(cx + s * 0.9, cy + s * 0.3, s * 0.9, 0, 6.283); ctx.fill();
        });
      }
      if (st.wind > 0.3) {      // wind streaks
        ctx.lineWidth = 1.6 * scale;
        streaks.forEach(function (s) {
          s.x += dt * (0.5 + gust * 0.9) * s.sp; if (s.x > 1.3) { s.x = -0.3; s.y = Math.random(); }
          var x = s.x * W, y = s.y * H * 0.8 + Math.sin(st.t * 2 + s.ph) * 4, L = 60 * s.l * scale;
          ctx.strokeStyle = 'rgba(255,255,255,' + (Math.min(0.5, (st.wind - 0.3) * 0.7) * (inCalm(x, y) ? 0.3 : 1)) + ')';
          ctx.beginPath(); ctx.moveTo(x - L, y); ctx.quadraticCurveTo(x - L / 2, y - 3, x, y); ctx.stroke();
        });
      }
      // snow: draw only as many flakes as the density asks for
      var n = Math.round(POOL * Math.min(1, st.snow + (st.wind > 0.7 ? 0.12 : 0)) * Math.min(1.4, (W * H) / 70000 + 0.25)), blow = gust * 1.1 + 0.05;
      ctx.fillStyle = '#fff';
      for (var f = 0; f < Math.min(n, POOL); f++) {
        var p = flakes[f];
        p.y += dt * (0.06 + 0.1 * p.sp) * p.z * (H > 120 ? 1 : 1.6);
        p.x += dt * (blow * 0.16 * p.z + Math.sin(st.t * p.sw + p.ph) * 0.012);
        if (p.y > 1.04) { p.y = -0.04; p.x = Math.random(); }
        if (p.x > 1.04) p.x = -0.04; else if (p.x < -0.04) p.x = 1.04;
        var fx = p.x * W, fy = p.y * H;
        ctx.globalAlpha = p.a * (inCalm(fx, fy) ? 0.18 : 1) * Math.min(1, st.snow * 3 + 0.3);
        ctx.beginPath(); ctx.arc(fx, fy, (0.9 + p.z * 1.9) * scale, 0, 6.283); ctx.fill();
      }
      ctx.globalAlpha = 1;
      pines.forEach(function (pn) {      // pines bend with the gusts, wearing the settled snow
        var bx = pn.x * W, h = pn.h * scale, lean = gust * 0.14 + Math.sin(st.t * 1.7 + pn.x * 9) * 0.02 * (gust + 0.2);
        ctx.save(); ctx.translate(bx, H - st.ground * 7 * scale); ctx.rotate(lean);
        ctx.fillStyle = 'rgba(255,255,255,.2)';
        ctx.beginPath(); ctx.moveTo(0, -h); ctx.lineTo(h * 0.32, -h * 0.35); ctx.lineTo(h * 0.18, -h * 0.35); ctx.lineTo(h * 0.4, 0); ctx.lineTo(-h * 0.4, 0); ctx.lineTo(-h * 0.18, -h * 0.35); ctx.lineTo(-h * 0.32, -h * 0.35); ctx.closePath(); ctx.fill();
        if (st.ground > 0.2) { ctx.fillStyle = 'rgba(255,255,255,' + (0.75 * st.ground) + ')'; ctx.beginPath(); ctx.moveTo(0, -h); ctx.lineTo(h * 0.14, -h * 0.7); ctx.lineTo(-h * 0.14, -h * 0.7); ctx.closePath(); ctx.fill(); }
        ctx.restore();
      });
      if (st.ground > 0.02) {   // the bank of settled snow along the bottom edge
        var gh = st.ground * 10 * scale;
        ctx.fillStyle = 'rgba(255,255,255,.92)';
        ctx.beginPath(); ctx.moveTo(0, H);
        for (var x = 0; x <= W; x += 8) ctx.lineTo(x, H - gh - Math.sin(x * 0.045 + 1.3) * gh * 0.2 - Math.sin(x * 0.013) * gh * 0.25);
        ctx.lineTo(W, H); ctx.closePath(); ctx.fill();
      }
    }
    function kick() { if (!raf && !reduced()) { last = performance.now(); raf = requestAnimationFrame(loop); } }
    var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (e) { visible = e[0].isIntersecting; if (visible) kick(); }) : null;
    var ro = 'ResizeObserver' in window ? new ResizeObserver(size) : null;
    var api = { set: set, size: size, draw: draw, frames: 0,
      get visible() { return visible && !document.hidden; },
      destroy: function () { live.delete(api); if (io) io.disconnect(); if (ro) ro.disconnect(); } };
    if (io) io.observe(cv);
    if (ro) ro.observe(cv);
    size();
    live.add(api);
    set(opts.wx || { kind: 'sun' }, { instant: true });
    cv.__wx = api;
    return api;
  }
  function loop(now) {
    var dt = Math.min(0.05, (now - last) / 1000), any = false;
    last = now;
    live.forEach(function (a) { if (a.visible) { a.draw(dt); a.frames++; any = true; } });
    raf = any && !reduced() ? requestAnimationFrame(loop) : 0;
  }
  document.addEventListener('visibilitychange', function () { if (!document.hidden && live.size && !raf && !reduced()) { last = performance.now(); raf = requestAnimationFrame(loop); } });
  GA.wx = { mount: mount, TYPES: TYPES };
})();
