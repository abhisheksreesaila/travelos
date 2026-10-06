// The one toast (F-108). GA.toast(text, opts) shows a short message as a light frosted pill at the top of the screen, just under the heading (assets/css/toast.css has the look).
//
//   GA.toast('Lunch moved to 12:30 PM', { undo: function () { ... } })      a clear Undo button inside it (the toast then stays 9 s instead of 4.5 s)
//   GA.toast('Added 1 plan', { href: '/trip/canvas?day=1', label: 'See the day' })      a link inside it
//   GA.toast('Could not save that', { error: true })
//   GA.hideToast(instant)                                                    fade it away (or remove it at once)
//
// One toast at a time: a new one takes the old one's place without the pill moving (only its words crossfade), so a burst of messages never stacks or slides again. It grows out of what was
// tapped (GA.motion, the one liquid spring: motion.js) and folds back into it after 4.5 s (9 s with Undo), and waits while a finger (or the pointer, or the keyboard) is on it. It is placed under the lowest visible part of the
// heading (the day's heading, the compact bar that replaces it, or the phone header on Family and Ask) so it never covers the Day | Week switch, the map or SOS, and it keeps up while the
// page scrolls. role=status with aria-live polite: a screen reader says it once. Reduced motion: no movement and no fade (the removal is not delayed).
// A toast the server drew with the page (.ga-toast-static: the calendar's, the old Today page's) is only placed here.
(function () {
  var GA = window.GA = window.GA || {};
  if (GA.toast) return;
  var MO = (window.GA && GA.motion) || (function () { var r = function () { return Promise.resolve(); }; return { open: r, close: r, spring: r, flip: r, run: r, settle: r, reflow: function (e, c, o) { c(); if (o && o.during) o.during(); return r(); }, origin: function () { return null; }, box: function (e) { return e.getBoundingClientRect(); }, reduced: function () { return true; }, t: function () { return 240; } }; })();
  var el = null, body = null, hideT = 0, swapT = 0, removeT = 0, latest = null, pressed = false, queued = false, curMs = 4500;
  // the heading and every row of controls under it: the day's kinds and step filters, Family's Chat / Photos / Invite and Quiet rows, the calendar's top bar
  var HEADS = ['.cz-fold.is-on .cz-fold-bar', '.cz-head', '.cz-bar', '.cz-filters', '.tp-head', '.fam-bar', '.ft-notify', '.ga-header', '.cal-bar'];
  var reduced = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };

  function rem() { return parseFloat(getComputedStyle(document.documentElement).fontSize) || 16; }

  // How far down the screen the pill's top must be (0 when nothing is in the way: it then sits just under the top of the screen). Under the lowest visible part of the heading and the
  // rows of controls beneath it (HEADS), then lower still while any other control (a date, a chip, a button) would be under the pill: it never covers something to tap. The day's grid and
  // the family thread are content, not controls, so the pill may float over them.
  var CONTROLS = 'a, button, input, textarea, select, [role=button], [tabindex]:not([tabindex="-1"])';
  function visible(n) {
    var s = getComputedStyle(n);
    return s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) >= 0.1;
  }
  function anchor(pill) {
    var y = 0, gap = rem() * 0.5, limit = window.innerHeight * 0.75;
    HEADS.forEach(function (sel) {
      var n = document.querySelector(sel);
      if (!n || !visible(n)) return;
      var r = n.getBoundingClientRect();
      if (r.width && r.height && r.bottom > 0 && r.top < window.innerHeight * 0.4 && r.bottom > y) y = r.bottom;
    });
    var h = pill.offsetHeight, pr = pill.getBoundingClientRect(), list = Array.prototype.slice.call(document.querySelectorAll(CONTROLS));
    list = list.filter(function (n) { return !n.closest('.ga-live, #cz-grid, #cz-week, .ft-thread, .ph-tabs, [inert], [hidden], .cz-fold:not(.is-on), .cz-card-wrap, .ak-sheet-wrap') && visible(n); });
    for (var i = 0; i < 24; i++) {
      var top = Math.max(y, 0) + gap, moved = false;
      for (var k = 0; k < list.length; k++) {
        var r2 = list[k].getBoundingClientRect();        if (!r2.width || !r2.height || r2.bottom <= top || r2.top >= top + h || r2.right <= pr.left || r2.left >= pr.right) continue;
        if (r2.bottom + gap > limit) continue;      // far down the screen: leave it
        y = Math.max(y, r2.bottom); moved = true;
      }
      if (!moved) break;
    }
    return y;
  }
  function place(n) {
    var y = anchor(n);
    if (y) n.style.setProperty('--ga-toast-y', y + 'px'); else n.style.removeProperty('--ga-toast-y');
  }
  function follow() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(function () {
      queued = false;
      if (el) place(el);
      document.querySelectorAll('.ga-toast-static').forEach(place);
    });
  }
  window.addEventListener('scroll', follow, { passive: true, capture: true });
  window.addEventListener('resize', follow);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', follow); else follow();

  function clearTimers() { clearTimeout(hideT); hideT = 0; }
  function arm(ms) {
    if (typeof ms === 'number') curMs = ms;
    clearTimers();
    if (pressed) return;
    hideT = setTimeout(function () { GA.hideToast(); }, curMs);
  }

  // One live region that is always on the page, empty, from the start: a screen reader announces what is put into it (a region made together with its words is often missed).
  // The pill is inside it.
  function live() {
    var l = document.getElementById('ga-toast');
    if (l) return l;
    l = document.createElement('div');
    l.id = 'ga-toast'; l.className = 'ga-live';
    l.setAttribute('role', 'status'); l.setAttribute('aria-live', 'polite'); l.setAttribute('aria-atomic', 'true');
    document.body.appendChild(l);
    return l;
  }
  if (document.body) live(); else document.addEventListener('DOMContentLoaded', live);

  function fill(into, o) {
    var t = document.createElement('span');
    t.className = 'ga-toast-t';
    t.textContent = o.text;
    into.appendChild(t);
    if (typeof o.undo === 'function') {
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'ga-toast-act ga-toast-undo'; b.textContent = 'Undo';
      b.addEventListener('click', function () { var f = o.undo; GA.hideToast(true); f(); });
      into.appendChild(b);
    } else if (o.href) {
      var a = document.createElement('a');
      a.className = 'ga-toast-act'; a.href = o.href; a.textContent = o.label || 'Open';
      into.appendChild(a);
    }
  }

  GA.toast = function (text, opts) {
    var o = { text: String(text || 'Done'), undo: opts && opts.undo, href: opts && opts.href, label: opts && opts.label, error: !!(opts && opts.error) };
    var ms = (opts && opts.ms) || (o.undo ? 9000 : 4500);
    clearTimeout(removeT); removeT = 0;
    pressed = false;                                              // a new toast starts free: a finger that was on the last one does not hold this one
    if (el && el.isConnected) {                                   // in place: the pill stays, its words crossfade
      latest = o;
      clearTimeout(swapT);
      body.classList.add('is-swap');
      swapT = setTimeout(function () {
        body.textContent = '';
        fill(body, latest);
        el.classList.toggle('is-error', latest.error);
        body.classList.remove('is-swap');
        place(el);
      }, reduced.matches ? 0 : MO.t('fade'));
      el.classList.add('is-in');                                  // (a toast on its way out is called back)
      el.getAnimations().forEach(function (a) { a.cancel(); });
      arm(ms);
      return el;
    }
    el = document.createElement('div');
    el.className = 'ga-toast' + (o.error ? ' is-error' : '');
    body = document.createElement('div');
    body.className = 'ga-toast-body';
    el.appendChild(body);
    live().appendChild(el);
    fill(body, o);
    place(el);
    var mine = el;
    mine.addEventListener('pointerdown', function () { if (!mine.classList.contains('is-in')) return; pressed = true; clearTimers(); });      // a finger on a fading toast holds nothing
    function release() { if (!pressed) return; pressed = false; if (el === mine) arm(); }
    window.addEventListener('pointerup', release, true);           // kept until the toast is dropped, so a toast called back from its fade is released too
    window.addEventListener('pointercancel', release, true);
    mine.addEventListener('mouseenter', function () { if (mine.classList.contains('is-in')) clearTimers(); });
    mine.addEventListener('mouseleave', function () { if (!pressed && el === mine) arm(); });
    mine.addEventListener('focusin', function () { clearTimers(); });
    mine.addEventListener('focusout', function () { if (el === mine && !pressed) arm(); });
    mine._release = release;
    mine.classList.add('is-in');
    mine._from = MO.origin();                              // what was tapped a moment ago: the toast grows out of it and folds back into it
    MO.open(mine, mine._from);
    arm(ms);
    return el;
  };

  GA.hideToast = function (instant) {
    clearTimers(); clearTimeout(swapT);
    var gone = el;
    if (!gone) return;
    pressed = false;
    function drop() {
      window.removeEventListener('pointerup', gone._release, true);
      window.removeEventListener('pointercancel', gone._release, true);
      if (gone.parentNode) gone.parentNode.removeChild(gone);
      if (el === gone) { el = null; body = null; }
    }
    if (instant === true || reduced.matches) { drop(); return; }
    gone.classList.remove('is-in');
    el = gone;
    MO.close(gone, gone._from && gone._from.isConnected ? gone._from : null);
    removeT = setTimeout(drop, MO.t('dur') + 80);          // after its fold
  };
})();
