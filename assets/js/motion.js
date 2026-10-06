// The one liquid motion (F-109), taken from the F-106 plan card: a thing that opens GROWS out of what was tapped (its own rectangle, a short soft spring, one layer moved by a transform) and,
// when it closes, FOLDS BACK into it. The same spring settles a new chat bubble or plan block into place. Every sheet, menu, popover and toast, and every screen move, uses this module and
// the tokens in tokens.css (--motion-spring-dur / --motion-spring for what grows, --motion-dur / --motion-out for what folds, --motion-quick, --motion-settle-dur, --motion-fade); no
// component writes a duration or an easing of its own (tests_browser/test_motion.py scans for that).
//
//   GA.motion.open(el, origin, { scrim, content, radius: [from, to] })   grow `el` (already in the page, at its final place) out of `origin`; resolves when it has landed
//   GA.motion.close(el, origin, { scrim, content, from, radius })        fold `el` into `origin` (or, with no origin on screen, down and away); resolves when it is gone (the caller removes it)
//   GA.motion.settle(el, { y })                                         a new bubble or block: it rises a few pixels, from a little smaller, with the same spring
//   GA.motion.spring(el, fromTransform)                                  let go of a drag: back to rest with the spring
//   GA.motion.run(el, frames, { t: 'quick', ease: 'calm' })              any other small move, with a token's duration and easing
//   GA.motion.origin()                                                   the thing tapped a moment ago (a toast, which nobody tapped, grows from it); null if nothing was
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
  function squash(to, from) {              // the transform that makes `el` (at `to`) look like the thing it grows from
    var sx = Math.max(from.width / Math.max(to.width, 1), 0.04), sy = Math.max(from.height / Math.max(to.height, 1), 0.04);
    return 'translate(' + (from.left - to.left) + 'px,' + (from.top - to.top) + 'px) scale(' + sx + ',' + sy + ')';
  }
  function note(kind, from, to, dur, easing) {
    var l = M.log; l.push({ kind: kind, from: from, to: to, dur: dur, easing: easing });
    if (l.length > 24) l.shift();
  }
  function go(el, frames, dur, easing, extra) {
    if (!el || !el.animate) return Promise.resolve();
    var a = el.animate(frames, Object.assign({ duration: dur, easing: easing }, extra || {}));
    return a.finished.catch(function () {});
  }

  var M = GA.motion = { log: [], t: t, ease: ease, reduced: reduced, box: box };

  // Grow `el` out of `origin`.
  M.open = function (el, origin, o) {
    o = o || {};
    var from = rectOf(origin);
    if (reduced() || !el.animate || !from) return Promise.resolve();
    var to = box(el), dur = t('spring'), e = ease('spring'), done = [];
    el.style.transformOrigin = '0 0';
    var sq = squash(to, from);
    var frames = [{ transform: sq, opacity: 0.35 }, { transform: 'none', opacity: 1 }];
    if (o.radius) { frames[0].borderRadius = o.radius[0]; frames[1].borderRadius = o.radius[1]; }
    done.push(go(el, frames, dur, e, { fill: 'backwards' }));
    if (o.scrim) done.push(go(o.scrim, [{ opacity: 0 }, { opacity: 1 }], t('calm'), ease('calm'), { fill: 'backwards' }));
    if (o.content) done.push(go(o.content, [{ opacity: 0 }, { opacity: 1 }], t('quick'), ease('calm'), { delay: Math.round(dur * 0.3), fill: 'backwards' }));
    note('open', from, to, dur, e);
    return Promise.all(done);
  };

  // Fold `el` into `origin`. `from` is the transform to leave from (a drag in progress); by default where the element is now.
  M.close = function (el, origin, o) {
    o = o || {};
    if (reduced() || !el.animate) return Promise.resolve();
    var start = o.from || getComputedStyle(el).transform;
    var to = box(el), target = rectOf(origin), dur = t('dur'), e = ease('out'), done = [];
    el.style.transformOrigin = '0 0';
    var end = onScreen(target) ? squash(to, target) : 'translateY(' + Math.round(window.innerHeight * 0.1) + 'px) scale(.9)';
    var frames = [{ transform: !start || start === 'matrix(1, 0, 0, 1, 0, 0)' ? 'none' : start, opacity: 1 }, { transform: end, opacity: 0.2 }];
    if (o.radius) { frames[0].borderRadius = o.radius[1]; frames[1].borderRadius = o.radius[0]; }
    done.push(go(el, frames, dur, e, { fill: 'forwards' }));
    if (o.scrim) done.push(go(o.scrim, [{ opacity: parseFloat(getComputedStyle(o.scrim).opacity) || 1 }, { opacity: 0 }], dur, ease('calm'), { fill: 'forwards' }));
    if (o.content) done.push(go(o.content, [{ opacity: 1 }, { opacity: 0 }], t('fade'), ease('calm'), { fill: 'forwards' }));
    note('close', to, target, dur, e);
    return Promise.all(done);
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
