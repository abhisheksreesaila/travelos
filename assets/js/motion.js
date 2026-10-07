// The one liquid motion (F-109), taken from the F-106 plan card: a thing that opens GROWS out of what was tapped (its own rectangle, a short soft spring, one layer moved by a transform) and,
// when it closes, FOLDS BACK into it. The same spring settles a new chat bubble or plan block into place. Every sheet, menu, popover and toast, and every screen move, uses this module and
// the tokens in tokens.css (--motion-spring-dur / --motion-spring for what grows, --motion-dur / --motion-out for what folds, --motion-quick, --motion-settle-dur, --motion-fade); no
// component writes a duration or an easing of its own (tests_browser/test_motion.py scans for that).
//
//   GA.motion.open(el, origin, { scrim, content, radius: [from, to] })   grow `el` (already in the page, at its final place) out of `origin`; resolves when it has landed
//   GA.motion.close(el, origin, { scrim, content, from, radius })        fold `el` into `origin` (or, with no origin on screen, down and away); resolves when it is gone (the caller removes it)
//   GA.motion.settle(el, { y })                                         a new bubble or block: it rises a few pixels, from a little smaller, with the same spring
//   GA.motion.land(el, from)                                            (F-112) `el` is at its real place but is drawn where `from` (a rect) was: it travels there with the spring (a block dropped or nudged, a
//                                                                        block or bubble the day or the list moved under; resolves when it has landed)
//   GA.motion.fade(el)                                                   reduced motion's version of a new bubble: a short fade, the one fade that is kept
//   GA.motion.spring(el, fromTransform)                                let go of a drag: back to rest with the spring
//   GA.motion.run(el, frames, { t: 'quick', ease: 'calm' })              any other small move, with a token's duration and easing
//   GA.motion.stop(el)                                                   cancel whatever is moving `el` (and its words' counter-scale); use it instead of cancelling by hand
//   GA.motion.origin()                                                   the thing tapped a moment ago (a toast, which nobody tapped, grows from it); null if nothing was
// While the box is scaled, its children are counter-scaled (and the box clips), so words never stretch (F-111).
// With no origin (or one scrolled off the screen) a thing rises from a small place just above where it rests.
// `origin` is an element, a DOMRect-like { left, top, width, height } or a point { x, y }. Only transform and opacity are animated (the radius at most), so it stays on the compositor.
// Reduced motion: nothing moves and nothing fades: it simply appears and goes (the promise resolves at once). GA.motion.log keeps the last few moves { kind, from, to, dur, easing } for the tests.
(function () {
  var GA = window.GA = window.GA || {};
  if (GA.motion) return;
  var root = document.documentElement;
  var reducedQ = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
  var NAMES = { spring: '--motion-spring-dur', calm: '--motion-dur', dur: '--motion-dur', settle: '--motion-settle-dur', quick: '--motion-quick', fade: '--motion-fade' };
  var EASES = { spring: '--motion-spring', calm: '--motion-ease', out: '--motion-out' };
  var FALLBACK = { spring: 380, calm: 240, dur: 240, settle: 280, quick: 160, fade: 120 };

  function css(n) { return getComputedStyle(root).getPropertyValue(n).trim(); }
  function t(name) {                       // a duration token, in milliseconds
    var v = css(NAMES[name] || name), x = parseFloat(v);
    if (!(x >= 0)) return FALLBACK[name] || 240;
    return /ms$/.test(v) ? x : /s$/.test(v) ? x * 1000 : x;
  }
  function ease(name) { return css(EASES[name] || name) || 'ease-out'; }
  function rem() { return parseFloat(getComputedStyle(root).fontSize) || 16; }
  function reduced() { return reducedQ.matches; }

  function rectOf(o) {
    if (!o) return null;
    if (o.getBoundingClientRect) { var r = o.getBoundingClientRect(); return { left: r.left, top: r.top, width: r.width, height: r.height }; }
    if (o.width !== undefined) return { left: o.left, top: o.top, width: o.width, height: o.height };
    if (o.x !== undefined) return { left: o.x, top: o.y, width: 0, height: 0 };
    return null;
  }
  function onScreen(r) { return !!r && r.top + r.height > 0 && r.top < window.innerHeight && r.left + r.width > 0 && r.left < window.innerWidth; }
  // where `el` sits when nothing is moving it: its layout box, ignoring a transform that is running or set
  function box(el) {
    el.getAnimations().forEach(function (a) { a.cancel(); });
    var own = el.style.transform;
    if (own) el.style.transform = '';
    var r = rectOf(el);
    if (own) el.style.transform = own;
    return r;
  }
  function natural(el) {                  // the layout box of an element that is being moved by a scale and a translate (transform-origin 0 0): the box we see, less the transform
    var r = rectOf(el), m = /^matrix\(([^)]+)\)$/.exec(getComputedStyle(el).transform || '');
    if (!m) return r;
    var v = m[1].split(',').map(parseFloat), a = v[0] || 1, d = v[3] || 1;
    return { left: r.left - v[4], top: r.top - v[5], width: r.width / a, height: r.height / d };
  }
  function squash(to, from) {              // the transform that makes `el` (at `to`) look like the thing it grows from
    var sx = Math.max(from.width / Math.max(to.width, 1), 0.04), sy = Math.max(from.height / Math.max(to.height, 1), 0.04);
    return 'translate(' + (from.left - to.left) + 'px,' + (from.top - to.top) + 'px) scale(' + sx + ',' + sy + ')';
  }
  // A sheet may still change size in the moment around its move (a status line comes or goes, a field): while it runs, its end is aimed at where the element really rests (its box with the running
  // transform taken out; never seeking). `aim(now)` gives the new transform for frame `key`.
  function follow(anim, el, to, frames, key, aim) {
    (function look() {
      if (!el.isConnected || anim.playState !== 'running') return;
      var now = natural(el);
      if (Math.abs(now.left - to.left) >= 1 || Math.abs(now.top - to.top) >= 1 || Math.abs(now.width - to.width) >= 1 || Math.abs(now.height - to.height) >= 1) {
        to = now;
        frames[key].transform = aim(now);
        anim.effect.setKeyframes(frames);
      }
      requestAnimationFrame(look);
    })();
  }
  function note(kind, from, to, dur, easing) {
    var l = M.log; l.push({ kind: kind, from: from, to: to, dur: dur, easing: easing });
    if (l.length > 24) l.shift();
    return l[l.length - 1];
  }
  function go(el, frames, dur, easing, extra) {
    if (!el || !el.animate) return Promise.resolve();
    var a = el.animate(frames, Object.assign({ duration: dur, easing: easing }, extra || {}));
    return a.finished.catch(function () {});
  }

  // The words of a thing that grows or folds keep their shape: while `el` is scaled (a grow out of what was tapped, a fold into it) each child of `el` is scaled by the exact inverse, frame by frame,
  // about the box's own corner (sampled from the same easing: 1/scale is not a straight line), and the box clips what it has not grown to yet. Frames for the child: scale `s0` (a vector)
  // to `s1`, in the box's own scale at the start and end of the move. The children are measured before anything is animated, with their own counter-scale taken out.
  var KEEP = 'ga-keep', N = 48;
  function keepWords(el, to, s0, s1, easing, dur, o) {
    var kids = Array.prototype.slice.call(el.children || []).filter(function (k) { return k.animate && getComputedStyle(k).display !== 'contents'; }), curve = bezier(easing), made = [];
    kids.forEach(function (k) { dropKeep(k, true); });
    function frames(a0, a1) {
      var out = [], i, p, sx, sy;
      for (i = 0; i <= N; i++) {
        p = curve(i / N);
        sx = a0[0] + (a1[0] - a0[0]) * p;
        sy = a0[1] + (a1[1] - a0[1]) * p;
        out.push({ offset: i / N, transform: 'scale(' + (1 / Math.max(sx, 0.01)) + ',' + (1 / Math.max(sy, 0.01)) + ')' });
      }
      return out;
    }
    kids.forEach(function (k) {
      var r = rectOf(k), a;
      if (k._gaPrev === undefined) k._gaPrev = k.style.transformOrigin;      // the corner is a style for the move's duration (not part of the keyframes: they stay on the compositor)
      k.style.transformOrigin = (to.left - r.left) + 'px ' + (to.top - r.top) + 'px';
      a = k.animate(frames(s0, s1), Object.assign({ duration: dur, easing: 'linear' }, o || {}));
      a.id = KEEP;
      made.push({ k: k, a: a });
    });
    var out = made.map(function (m) {
      return m.a.finished.then(function () { if (!(o && o.fill === 'forwards')) dropKeep(m.k, false); }, function () {});      // a fold stays as it ends until the thing is removed
    });
    // The box was aimed at a new rest (it changed size around its move): the words follow, with the box's new scales. Where the box's corner is in a word's own space is the same in the picture as at
    // rest (the counter-scale cancels the box's), so it is read from the boxes as they are now; call this before the box's own frames change.
    out.refit = function (a0, a1) {
      var er = rectOf(el);
      made.forEach(function (m) {
        if (m.a.playState !== 'running') return;
        var r = rectOf(m.k);
        m.k.style.transformOrigin = (er.left - r.left) + 'px ' + (er.top - r.top) + 'px';
        m.a.effect.setKeyframes(frames(a0, a1));
      });
    };
    // the box clips its words until it has landed (then lets its shadow and anything that pokes out show again); a fold eases the clip in over its first frames, from wherever it is (a fold that
    // interrupts a grow does not snap it); started after the box's own move, with `clip()`
    out.clip = function () {
      var free = 'inset(-4rem)', from = o && o.clipFrom && o.clipFrom !== 'none' ? o.clipFrom : free;
      var fr = o && o.fill === 'forwards' ? [{ clipPath: from, offset: 0 }, { clipPath: 'inset(0)', offset: 0.15 }, { clipPath: 'inset(0)', offset: 1 }]
        : [{ clipPath: 'inset(0)', offset: 0 }, { clipPath: 'inset(0)', offset: 0.85 }, { clipPath: free, offset: 1 }];
      var c = el.animate(fr, { duration: dur, easing: 'linear', fill: o && o.fill });
      return c.finished.catch(function () {});
    };
    return out;
  }
  function dropKeep(k, keepStyle) {              // the counter-scale of a word box goes (and the corner it was scaled about is put back)
    k.getAnimations().forEach(function (a) { if (a.id === KEEP) a.cancel(); });
    if (!keepStyle && k._gaPrev !== undefined) { k.style.transformOrigin = k._gaPrev; delete k._gaPrev; }
  }
  // Stop whatever moved `el` (a toast called back while it folds): its own animations and its words' counter-scale go, and every word box is at its own size again.
  M_stop = function (el) {
    if (!el) return;
    el.getAnimations().forEach(function (a) { a.cancel(); });
    Array.prototype.forEach.call(el.children || [], function (k) { dropKeep(k, false); });
  };
  var M_stop;
  function scaleOf(tf) {
    if (!tf || tf === 'none') return [1, 1];
    var m = new DOMMatrix(tf);
    return [m.a || 1, m.d || 1];
  }

  var M = GA.motion = { log: [], t: t, ease: ease, reduced: reduced, box: box, stop: function (el) { M_stop(el); } };

  // Grow `el` out of `origin`.
  M.open = function (el, origin, o) {
    o = o || {};
    var from = rectOf(origin);
    if (reduced() || !el.animate) return Promise.resolve();
    var to = box(el), dur = t('spring'), e = ease('spring'), done = [];
    if (!onScreen(from)) from = { left: to.left + to.width * 0.15, top: to.top - rem() * 0.75, width: to.width * 0.7, height: to.height * 0.6 };      // nothing (on screen) was tapped: it rises from a small place just above where it rests
    el.style.transformOrigin = '0 0';
    var sq = squash(to, from);
    var frames = [{ transform: sq, opacity: 0.35 }, { transform: 'none', opacity: 1 }];
    if (o.radius) { frames[0].borderRadius = o.radius[0]; frames[1].borderRadius = o.radius[1]; }
    var kept = keepWords(el, to, scaleOf(sq), [1, 1], e, dur, { fill: 'backwards' });      // (measured before the box is moved)
    done.push.apply(done, kept);
    var main = el.animate(frames, { duration: dur, easing: e, fill: 'backwards' });
    done.push(main.finished.catch(function () {}), kept.clip());
    var rec = note('open', from, to, dur, e);
    follow(main, el, to, frames, 0, function (now) { var q = squash(now, from); kept.refit(scaleOf(q), [1, 1]); to = rec.to = now; return q; });
    if (o.scrim) done.push(go(o.scrim, [{ opacity: 0 }, { opacity: 1 }], t('calm'), ease('calm'), { fill: 'backwards' }));
    if (o.content) done.push(go(o.content, [{ opacity: 0 }, { opacity: 1 }], t('quick'), ease('calm'), { delay: Math.round(dur * 0.3), fill: 'backwards' }));
    return Promise.all(done);
  };

  // Fold `el` into `origin`. `from` is the transform to leave from (a drag in progress); by default where the element is now.
  M.close = function (el, origin, o) {
    o = o || {};
    if (reduced() || !el.animate) return Promise.resolve();
    var cs = getComputedStyle(el);      // where it is right now: closing in the middle of opening starts from there (no flash back to full)
    var start = o.from || cs.transform, op = parseFloat(cs.opacity), rad = cs.borderRadius, clip0 = cs.clipPath;
    var cop = o.content ? parseFloat(getComputedStyle(o.content).opacity) : 1;
    var to = box(el), target = rectOf(origin), dur = t('dur'), e = ease('out'), done = [];
    el.style.transformOrigin = '0 0';
    var end = onScreen(target) ? squash(to, target) : 'translateY(' + Math.round(window.innerHeight * 0.1) + 'px) scale(.9)';
    var frames = [{ transform: !start || start === 'matrix(1, 0, 0, 1, 0, 0)' ? 'none' : start, opacity: op >= 0 ? op : 1 }, { transform: end, opacity: Math.min(0.2, op >= 0 ? op : 1) }];
    if (o.radius) { frames[0].borderRadius = rad || o.radius[1]; frames[1].borderRadius = o.radius[0]; }
    var kept = keepWords(el, to, scaleOf(frames[0].transform), scaleOf(end), e, dur, { fill: 'forwards', clipFrom: clip0 });
    done.push.apply(done, kept);
    var fold = el.animate(frames, { duration: dur, easing: e, fill: 'forwards' });
    done.push(fold.finished.catch(function () {}), kept.clip());
    if (onScreen(target)) follow(fold, el, to, frames, 1, function (now) { var q = squash(now, target); kept.refit(scaleOf(frames[0].transform), scaleOf(q)); return q; });
    if (o.scrim) done.push(go(o.scrim, [{ opacity: parseFloat(getComputedStyle(o.scrim).opacity) || 1 }, { opacity: 0 }], dur, ease('calm'), { fill: 'forwards' }));
    if (o.content) done.push(go(o.content, [{ opacity: cop >= 0 ? cop : 1 }, { opacity: 0 }], t('fade'), ease('calm'), { fill: 'forwards' }));
    note('close', to, target, dur, e);
    return Promise.all(done);
  };

  // The progress of a CSS cubic-bezier easing (the spring token: it overshoots) at time x in 0..1, for the words that are held still while their box scales (see flip).
  function bezier(str) {
    var m = /cubic-bezier\(([^)]+)\)/.exec(str || ''), v = m ? m[1].split(',').map(parseFloat) : [0.25, 0.1, 0.25, 1];
    var ax = 3 * v[0] - 3 * v[2] + 1, bx = 3 * v[2] - 6 * v[0], cx = 3 * v[0], ay = 3 * v[1] - 3 * v[3] + 1, by = 3 * v[3] - 6 * v[1], cy = 3 * v[1];
    return function (x) {
      var s = x, i;
      for (i = 0; i < 8; i++) {                                                       // Newton, then bisection when it cannot get there
        var f = ((ax * s + bx) * s + cx) * s - x, d = (3 * ax * s + 2 * bx) * s + cx;
        if (Math.abs(f) < 1e-5) break;
        if (Math.abs(d) < 1e-6) { i = 8; break; }
        s -= f / d;
      }
      if (i === 8 || !(s >= 0 && s <= 1)) { var lo = 0, hi = 1; s = x; for (i = 0; i < 30; i++) { var g = ((ax * s + bx) * s + cx) * s; if (g < x) lo = s; else hi = s; s = (lo + hi) / 2; } }
      return ((ay * s + by) * s + cy) * s;
    };
  }

  // Something that is already open changes size or place (the card follows its words, a pane expands): it goes from where it was to where it is with a transform (never top, height or width).
  // The box is scaled, its words are not: each child of `el` is scaled by the inverse, frame by frame, about the box's own corner, so text never stretches (the box clips what it has not
  // grown to yet). The children's frames are sampled from the same spring, 1/scale is not a straight line, so a plain pair of keyframes would be wrong in the middle.
  M.flip = function (el, from, to) {
    if (reduced() || !el || !el.animate || !from || !to) return Promise.resolve();
    if (Math.abs(from.left - to.left) < 1 && Math.abs(from.top - to.top) < 1 && Math.abs(from.width - to.width) < 1 && Math.abs(from.height - to.height) < 1) return Promise.resolve();
    el.style.transformOrigin = '0 0';
    var dur = t('spring'), e = ease('spring');
    note('flip', from, to, dur, e);
    var kids = Array.prototype.slice.call(el.children || []), out = [go(el, [{ transform: squash(to, from) }, { transform: 'none' }], dur, e)];
    if (kids.length) {
      var er = rectOf(el), sx0 = Math.max(from.width / Math.max(to.width, 1), 0.04), sy0 = Math.max(from.height / Math.max(to.height, 1), 0.04), curve = bezier(e), N = 24;
      kids.forEach(function (k) {
        var r = rectOf(k), frames = [], i, p, sx, sy, origin = (er.left - r.left) + 'px ' + (er.top - r.top) + 'px';
        for (i = 0; i <= N; i++) {
          p = curve(i / N);
          sx = sx0 + (1 - sx0) * p;
          sy = sy0 + (1 - sy0) * p;
          frames.push({ offset: i / N, transform: i === N ? 'none' : 'scale(' + (1 / sx) + ',' + (1 / sy) + ')', transformOrigin: origin });
        }
        out.push(go(k, frames, dur, 'linear'));
      });
    }
    return Promise.all(out);
  };

  // `change()` alters the layout around `el` (a row opens inside a bottom sheet, so the sheet gets taller): `el` moves from its old box to its new one with the spring. `o.during` runs after the change and
  // before the move starts (so others can measure the new layout untransformed).
  M.reflow = function (el, change, o) {
    o = o || {};
    if (reduced() || !el || !el.animate) { change(); if (o.during) o.during(); return Promise.resolve(); }
    var before = box(el);
    change();
    var after = box(el);
    if (o.during) o.during();
    return M.flip(el, before, after);
  };

  // A new bubble or block: it rises a few pixels from a little smaller and settles with the spring (no movement under reduced motion).
  M.settle = function (el, o) {
    o = o || {};
    if (reduced() || !el || !el.animate) return Promise.resolve();
    var y = (o.y !== undefined ? o.y : 0.5) * rem();
    var dur = t('settle'), e = ease('spring');
    note('settle', null, null, dur, e);
    return go(el, [{ transform: 'translateY(' + y + 'px) scale(.96)', opacity: 0 }, { transform: 'none', opacity: 1 }], dur, e, { fill: 'backwards' });
  };

  // A block (or a bubble) that is already at its real place, but is still drawn where it was (`from`: a DOMRect-like of what the eye saw a moment ago, a lifted and dragged block, or the
  // same block just before the day was re-drawn): it travels from there to its place with the spring, one animation of transform alone, a gentle overshoot at the end. Whatever was moving
  // it is taken over (its running land stops where it is: `from` is read by the caller, from the screen, so the new move starts exactly there). The resolved promise means "it has landed".
  // Words are only held still when the size really changes (a resize undone); a small difference (the lifted block's 3% scale) just folds out with the box.
  M.land = function (el, from, o) {
    o = o || {};
    if (reduced() || !el || !el.animate || !from) return Promise.resolve();
    el.getAnimations().forEach(function (a) { if (a.id === 'ga-land') a.cancel(); });      // (not box(): a block's wiggle is a CSS animation that must go on)
    var to = rectOf(el);
    if (Math.abs(from.left - to.left) < 0.5 && Math.abs(from.top - to.top) < 0.5 && Math.abs(from.width - to.width) < 0.5 && Math.abs(from.height - to.height) < 0.5) return Promise.resolve();
    var was = el.style.transformOrigin, big = Math.abs(from.height / Math.max(to.height, 1) - 1) > 0.05 || Math.abs(from.width / Math.max(to.width, 1) - 1) > 0.05;
    if (big) return M.flip(el, from, to).then(function () { el.style.transformOrigin = was; });
    var dur = t('spring'), e = ease('spring'), a;
    note('land', from, to, dur, e);
    if (Math.abs(from.width - to.width) < 0.5 && Math.abs(from.height - to.height) < 0.5) {      // only a move: the `translate` property, so a wiggle (a transform of the block's own) goes on under it, with no jump when it ends
      a = el.animate([{ translate: (from.left - to.left) + 'px ' + (from.top - to.top) + 'px' }, { translate: '0px 0px' }], { duration: dur, easing: e });
    } else {
      el.style.transformOrigin = '0 0';
      a = el.animate([{ transform: squash(to, from) }, { transform: 'none' }], { duration: dur, easing: e });
    }
    a.id = 'ga-land';
    var back = function () { if (el.isConnected && !el.getAnimations().some(function (x) { return x.id === 'ga-land'; })) el.style.transformOrigin = was; };
    return Promise.race([a.finished.then(back, back), new Promise(function (r) { setTimeout(r, dur + 150); })]);      // (a block taken out of the page by a refresh still lets the caller go on)
  };

  // Reduced motion's version of a new bubble: it only fades in, quickly (the one place a fade is kept).
  M.fade = function (el) {
    if (!el || !el.animate) return Promise.resolve();
    note('fade', null, null, t('fade'), ease('calm'));
    return go(el, [{ opacity: 0 }, { opacity: 1 }], t('fade'), ease('calm'), { fill: 'backwards' });
  };

  // Let go of a drag: back to rest with the spring.
  M.spring = function (el, fromTransform) {
    if (reduced() || !el.animate) return Promise.resolve();
    return go(el, [{ transform: fromTransform }, { transform: 'none' }], t('spring'), ease('spring'));
  };

  // Any other small move, with a token's duration and easing.
  M.run = function (el, frames, o) {
    o = o || {};
    if (reduced() || !el || !el.animate) return Promise.resolve();
    return go(el, frames, t(o.t || 'quick'), ease(o.ease || 'calm'), o.fill ? { fill: o.fill } : null);
  };

  // What was tapped a moment ago, for a toast (nobody taps a toast to open it, but the thing that made it can be where it grows from).
  var lastTap = null;
  document.addEventListener('pointerdown', function (e) {
    var n = e.target && e.target.closest ? e.target.closest('a, button, [role=button], [role=menuitem], .cz-gb, [data-zk]') : null;
    lastTap = n ? { n: n, at: Date.now() } : null;
  }, { capture: true, passive: true });
  M.origin = function () { return lastTap && Date.now() - lastTap.at < 2500 && lastTap.n.isConnected ? lastTap.n : null; };
})();
