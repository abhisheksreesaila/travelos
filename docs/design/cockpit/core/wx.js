/* The living weather widget: one small canvas engine (about 4 KB) behind the widget's text, on the weather kind's solid fill.
   Snow actually falls and settles into a bank, the sun turns slowly, wind drives streaks and bends the pines, clouds drift.
   Adapted from Meng To's threejs-weather skill (MIT): density is a draw range over one preallocated pool (never reallocate
   when the weather changes), falling snow and settled snow are two separate variables (the bank grows while it snows and
   stays on the next sunny day), and a windy day runs on a slow gust envelope instead of a constant. Every flake has its own
   size, speed and sway (falling-leaves skill: share nothing, or the eye finds the rhythm).
   Text stays readable: flakes fade to 18% inside the widget's [data-calm] text boxes. Reduced motion draws one still frame.
   Pauses when off screen or when the tab is hidden. */
(function () {
  const POOL = 260;
  const live = new Set();
  let raf = 0, last = 0;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const TYPES = {
    sun: { snow: 0, wind: .08, sun: 1, cloud: .05 },
    cloud: { snow: .04, wind: .22, sun: .22, cloud: .9 },
    snow: { snow: 1, wind: .42, sun: 0, cloud: 1 },
    flurry: { snow: .34, wind: .22, sun: .35, cloud: .6 },
    wind: { snow: 0, wind: 1, sun: .6, cloud: .35 },
  };
  function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

  function mount(cv, opts = {}) {
    const ctx = cv.getContext('2d');
    const r = rng(opts.seed || 7);
    const flakes = Array.from({ length: POOL }, () => ({ x: r(), y: r(), z: .35 + r() * .65, ph: r() * 6.28, sw: .4 + r() * 1.2, sp: .6 + r() * .8, a: .55 + r() * .4 }));
    const streaks = Array.from({ length: 14 }, () => ({ x: r(), y: r(), l: .5 + r() * .7, sp: .7 + r() * .6, ph: r() * 6.28 }));
    const clouds = Array.from({ length: 4 }, (_, i) => ({ x: r(), y: .08 + r() * .3, s: .7 + r() * .6, sp: .5 + r(), i }));
    const pines = (opts.pines ?? true) ? [{ x: .70, h: 30 }, { x: .76, h: 40 }, { x: .83, h: 26 }, { x: .89, h: 36 }, { x: .95, h: 28 }] : [];
    const st = { snow: 0, wind: 0, sun: 0, cloud: 0, ground: 0, t: r() * 100 };
    let tgt = { ...st };
    let W = 0, H = 0, dpr = 1, calm = [], visible = true;
    const scale = opts.scale || 1;

    function size() {
      const b = cv.getBoundingClientRect();
      dpr = Math.min(devicePixelRatio || 1, 2);
      W = b.width; H = b.height;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      readCalm();
      if (reduced) draw(0);
    }
    function readCalm() {
      const host = opts.host || cv.parentElement;
      const b = cv.getBoundingClientRect();
      calm = [...host.querySelectorAll('[data-calm]')].map((el) => { const e = el.getBoundingClientRect(); return [e.left - b.left - 6, e.top - b.top - 4, e.width + 12, e.height + 8]; });
    }
    function set(w, o = {}) {
      const base = TYPES[w.type] || TYPES.sun;
      const amt = w.type === 'snow' && /6|9/.test(w.snow) ? 1 : w.type === 'snow' ? .62 : 1;
      tgt = { snow: base.snow * amt, wind: Math.min(1, base.wind + (w.gust || 0) / 120), sun: base.sun, cloud: base.cloud, ground: w.ground ?? st.ground };
      if (o.instant || reduced) Object.assign(st, tgt);
      readCalm();
      if (reduced) draw(0); else kick();
    }
    function inCalm(x, y) { for (const c of calm) if (x > c[0] && x < c[0] + c[2] && y > c[1] && y < c[1] + c[3]) return true; return false; }

    function draw(dt) {
      // ease every dial toward its target (critically damped feel, no overshoot); the bank is slower than the sky
      const k = 1 - Math.exp(-dt * 3.2), kg = 1 - Math.exp(-dt * .9);
      st.snow += (tgt.snow - st.snow) * k; st.wind += (tgt.wind - st.wind) * k; st.sun += (tgt.sun - st.sun) * k; st.cloud += (tgt.cloud - st.cloud) * k;
      st.ground += (tgt.ground - st.ground) * kg;
      st.t += dt;
      const gust = st.wind * (.65 + .35 * Math.sin(st.t * .35) * Math.sin(st.t * .13 + 1)); // slow envelope
      ctx.clearRect(0, 0, W, H);
      ctx.lineCap = 'round';
      // sun: a disc, twelve slow rays, a breathing ring
      if (st.sun > .02) {
        const sx = W - (opts.sunX ?? 54) * scale, sy = (opts.sunY ?? 46) * scale, R = 15 * scale;
        ctx.save(); ctx.globalAlpha = st.sun; ctx.translate(sx, sy);
        ctx.strokeStyle = 'rgba(255,255,255,.95)'; ctx.lineWidth = 2.2 * scale;
        ctx.rotate(st.t * .12);
        for (let i = 0; i < 12; i++) { ctx.rotate(Math.PI / 6); ctx.beginPath(); ctx.moveTo(R + 5 * scale, 0); ctx.lineTo(R + (i % 2 ? 9 : 12) * scale, 0); ctx.stroke(); }
        ctx.rotate(-st.t * .12);
        ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(0, 0, R, 0, 6.283); ctx.fill();
        ctx.globalAlpha = st.sun * (.22 + .1 * Math.sin(st.t * 1.4)); ctx.lineWidth = 1.5 * scale;
        ctx.beginPath(); ctx.arc(0, 0, R + 20 * scale, 0, 6.283); ctx.stroke();
        ctx.restore();
      }
      // clouds: opaque-looking soft white puffs at low alpha, drifting
      if (st.cloud > .02) {
        for (const c of clouds) {
          c.x += dt * (.006 + st.wind * .02) * c.sp; if (c.x > 1.25) c.x = -.25;
          const cx = c.x * W, cy = c.y * H, s = 22 * c.s * scale;
          ctx.fillStyle = `rgba(255,255,255,${(.13 + c.i * .03) * st.cloud})`;
          ctx.beginPath(); ctx.arc(cx, cy, s, 0, 6.283); ctx.arc(cx + s * .9, cy - s * .35, s * .8, 0, 6.283); ctx.arc(cx + s * 1.8, cy, s * .9, 0, 6.283); ctx.arc(cx + s * .9, cy + s * .3, s * .9, 0, 6.283); ctx.fill();
        }
      }
      // wind streaks
      if (st.wind > .3) {
        ctx.lineWidth = 1.6 * scale;
        for (const s of streaks) {
          s.x += dt * (.5 + gust * .9) * s.sp; if (s.x > 1.3) { s.x = -.3; s.y = Math.random(); }
          const x = s.x * W, y = s.y * H * .8 + Math.sin(st.t * 2 + s.ph) * 4, L = 60 * s.l * scale;
          ctx.strokeStyle = `rgba(255,255,255,${Math.min(.5, (st.wind - .3) * .7) * (inCalm(x, y) ? .3 : 1)})`;
          ctx.beginPath(); ctx.moveTo(x - L, y); ctx.quadraticCurveTo(x - L / 2, y - 3, x, y); ctx.stroke();
        }
      }
      // snow: draw only as many flakes as the density asks for
      const n = Math.round(POOL * Math.min(1, st.snow + (st.wind > .7 ? .12 : 0)) * Math.min(1.4, (W * H) / 70000 + .25));
      const blow = gust * 1.1 + .05;
      ctx.fillStyle = '#fff';
      for (let i = 0; i < Math.min(n, POOL); i++) {
        const f = flakes[i];
        f.y += dt * (.06 + .1 * f.sp) * f.z * (H > 120 ? 1 : 1.6);
        f.x += dt * (blow * .16 * f.z + Math.sin(st.t * f.sw + f.ph) * .012);
        if (f.y > 1.04) { f.y = -.04; f.x = Math.random(); }
        if (f.x > 1.04) f.x = -.04; else if (f.x < -.04) f.x = 1.04;
        const x = f.x * W, y = f.y * H;
        ctx.globalAlpha = f.a * (inCalm(x, y) ? .18 : 1) * Math.min(1, st.snow * 3 + .3);
        ctx.beginPath(); ctx.arc(x, y, (.9 + f.z * 1.9) * scale, 0, 6.283); ctx.fill();
      }
      ctx.globalAlpha = 1;
      // pines bend with the gusts, wearing the settled snow
      for (const p of pines) {
        const bx = p.x * W, by = H, h = p.h * scale, lean = (gust * .14 + Math.sin(st.t * 1.7 + p.x * 9) * .02 * (gust + .2));
        ctx.save(); ctx.translate(bx, by - st.ground * 7 * scale); ctx.rotate(lean);
        ctx.fillStyle = 'rgba(255,255,255,.2)';
        ctx.beginPath(); ctx.moveTo(0, -h); ctx.lineTo(h * .32, -h * .35); ctx.lineTo(h * .18, -h * .35); ctx.lineTo(h * .4, 0); ctx.lineTo(-h * .4, 0); ctx.lineTo(-h * .18, -h * .35); ctx.lineTo(-h * .32, -h * .35); ctx.closePath(); ctx.fill();
        if (st.ground > .2) { ctx.fillStyle = `rgba(255,255,255,${.75 * st.ground})`; ctx.beginPath(); ctx.moveTo(0, -h); ctx.lineTo(h * .14, -h * .7); ctx.lineTo(-h * .14, -h * .7); ctx.closePath(); ctx.fill(); }
        ctx.restore();
      }
      // the bank of settled snow along the bottom edge
      if (st.ground > .02) {
        const gh = st.ground * 10 * scale;
        ctx.fillStyle = 'rgba(255,255,255,.92)';
        ctx.beginPath(); ctx.moveTo(0, H);
        for (let x = 0; x <= W; x += 8) ctx.lineTo(x, H - gh - Math.sin(x * .045 + 1.3) * gh * .2 - Math.sin(x * .013) * gh * .25);
        ctx.lineTo(W, H); ctx.closePath(); ctx.fill();
      }
    }
    function kick() { if (!raf) { last = performance.now(); raf = requestAnimationFrame(loop); } }
    const api = { set, size, draw, get visible() { return visible && !document.hidden; }, destroy() { live.delete(api); io.disconnect(); ro.disconnect(); } };
    const io = new IntersectionObserver((e) => { visible = e[0].isIntersecting; if (visible) kick(); });
    io.observe(cv);
    const ro = new ResizeObserver(size); ro.observe(cv);
    size();
    live.add(api);
    if (opts.wx) set(opts.wx, { instant: true });
    return api;
  }
  function loop(now) {
    const dt = Math.min(.05, (now - last) / 1000); last = now;
    let any = false;
    for (const a of live) if (a.visible) { a.draw(dt); any = true; }
    raf = any && !reduced ? requestAnimationFrame(loop) : 0;
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden && live.size) { last = performance.now(); if (!raf) raf = requestAnimationFrame(loop); } });
  window.WXE = { mount, TYPES };
})();
