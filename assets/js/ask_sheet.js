// The Ask sheet (F-104): on a phone the centre Ask tab opens a glass bottom sheet over the screen that is open (the day, Family, Map ...) instead of a page of its own.
//
// Progressive enhancement: the tab is still a link to /trip/ask?day=N (the page works with no script, on a laptop, from an old link). With this script, and for editors only
// (phone.py marks the tab data-ask="sheet"), a tap on the tab fetches the box as a fragment (GET /trip/ask?day=N with X-Ask: 1; the canvas points the tab's href at the day it shows) and
// grows it out of the Ask button: transform-origin at the button, scale and fade with --motion-dur / --motion-ease (Web Animations; none under reduced motion). The forms inside
// (box, follow-up questions, preview, Apply) post with X-Ask and get fragments back, so the whole conversation stays in the sheet; ask.js (AskBox.init) drives the box in it.
//
// The iOS rule. Safari starts the microphone only from a user activation, so the tap on the tab must reach getUserMedia in the same task: the fragment and ask.js are therefore
// fetched ahead of time (on load, when the shown day changes, and as the finger goes down on the tab), and the click handler puts the box in and starts it synchronously (data-mode="talk").
// Only if the fragment has not arrived yet does the sheet open empty and fill when it does; then recording may need one more tap on the big mic.
//
// Closing: swipe the grabber down (a flick or a third of the height), the scrim, or Escape; the sheet shrinks back into the button. Apply: the sheet closes, the day behind it is brought
// up to date (CZ.quiet, or the day that was chosen), what changed glows for a moment and a toast says what was done and that the family was told. There is no Undo: a removed plan cannot come back.
(function () {
  var tab = document.getElementById('ph-tab-ask');
  if (!tab || tab.dataset.ask !== 'sheet') return;
  var root = document.documentElement;
  var app = document.getElementById('ph-app') || document.body;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var phone = window.matchMedia('(max-width: 720px), (display-mode: standalone)');
  var FRESH = 300000;
  var cache = {};
  var wrap = null, sheet = null, scroll = null, ctl = null, closing = false, back = [];
  var toast = null, toastTimer = 0;

  function url() { return tab.getAttribute('href') || '/trip/ask'; }
  function ms() { var v = parseFloat(getComputedStyle(root).getPropertyValue('--motion-dur')); return v > 0 ? v : 240; }
  function ease() { return getComputedStyle(root).getPropertyValue('--motion-ease').trim() || 'ease-out'; }
  function animate(el, frames, opts) {
    if (reduced.matches || !el.animate) return Promise.resolve();
    return el.animate(frames, Object.assign({ duration: ms(), easing: ease(), fill: 'both' }, opts || {})).finished.catch(function () {});
  }

  // ---- the fragment, fetched ahead -------------------------------------------------------------------------------------------
  function get(u) {
    var hit = cache[u];
    if (hit && Date.now() - hit.at < FRESH) return hit;
    var entry = { at: Date.now(), html: null, p: null };
    entry.p = fetch(u, { credentials: 'same-origin', headers: { 'X-Ask': '1' } }).then(function (r) {
      if (!r.ok) throw new Error('ask ' + r.status);
      return r.text();
    }).then(function (h) { entry.html = h; return h; });
    entry.p.catch(function () { if (cache[u] === entry) delete cache[u]; });
    cache[u] = entry;
    return entry;
  }
  var idle = window.requestIdleCallback ? function (fn) { window.requestIdleCallback(fn, { timeout: 2000 }); } : function (fn) { setTimeout(fn, 300); };
  function ahead() {
    var c = navigator.connection;
    if (document.hidden || (c && c.saveData)) return;
    idle(function () { get(url()).p.catch(function () {}); });
  }
  ahead();
  if (window.MutationObserver) new MutationObserver(ahead).observe(tab, { attributes: true, attributeFilter: ['href'] });
  tab.addEventListener('pointerdown', function () { get(url()).p.catch(function () {}); }, { passive: true });
  window.addEventListener('pageshow', function (e) { if (e.persisted) { cache = {}; ahead(); } });

  // ---- open -------------------------------------------------------------------------------------------------------------------
  tab.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || !phone.matches || !window.AskBox) return;
    e.preventDefault();
    if (wrap) return;
    open();
  });

  function make() {
    wrap = document.createElement('div');
    wrap.className = 'ak-sheet-wrap';
    var scrim = document.createElement('div');
    scrim.className = 'ak-scrim';
    sheet = document.createElement('div');
    sheet.className = 'ak-sheet';
    sheet.id = 'ak-sheet';
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-modal', 'true');
    sheet.setAttribute('aria-label', 'Ask GitAway');
    sheet.tabIndex = -1;
    var grab = document.createElement('div');
    grab.className = 'ak-grab';
    grab.id = 'ak-grab';
    scroll = document.createElement('div');
    scroll.className = 'ak-sheet-scroll';
    sheet.appendChild(grab);
    sheet.appendChild(scroll);
    wrap.appendChild(scrim);
    wrap.appendChild(sheet);
    scrim.addEventListener('click', function () { close(); });
    grabbing(grab);
    wrap.addEventListener('submit', onSubmit);
    return { scrim: scrim };
  }

  function origin() {
    var b = tab.querySelector('.ph-ti') || tab, r = b.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }
  function pointOrigin() {       // the point of the sheet that sits on the Ask button (offsets, so a transform in progress does not matter; the wrap fills the viewport)
    var o = origin();
    sheet.style.transformOrigin = (o.x - sheet.offsetLeft) + 'px calc(100% + ' + (o.y - sheet.offsetTop - sheet.offsetHeight) + 'px)';       // from the bottom edge: the sheet grows upward when the mic starts
  }

  function open() {
    closing = false;
    var entry = get(url());
    var parts = make();
    var html = entry.html;
    app.appendChild(wrap);
    wrap.classList.add('is-open');
    behind(true);
    if (html !== null) fill(html, true);        // the box is in (and the microphone started) inside this tap, before anything animates
    else scroll.innerHTML = '<div id="ak-sheet-body"><p class="ak-fine" role="status">Getting ready…</p></div>';
    pointOrigin();                              // after the content: the sheet's height decides where its top is
    animate(parts.scrim, [{ opacity: 0 }, { opacity: 1 }]);
    animate(sheet, [{ transform: 'scale(0.08)', opacity: 0 }, { transform: 'none', opacity: 1 }]);
    if (html === null) entry.p.then(function (h) { if (wrap && !closing) { fill(h, true); pointOrigin(); } }, function () { if (wrap) { wrap.remove(); wrap = null; behind(false); location.href = tab.href; } });
    document.addEventListener('keydown', onKey, true);
    if (window.visualViewport) { window.visualViewport.addEventListener('resize', kb); window.visualViewport.addEventListener('scroll', kb); }
    back.push(function () {
      document.removeEventListener('keydown', onKey, true);
      if (window.visualViewport) { window.visualViewport.removeEventListener('resize', kb); window.visualViewport.removeEventListener('scroll', kb); }
    });
    if (!sheet.contains(document.activeElement)) { try { sheet.focus({ preventScroll: true }); } catch (err) { /* old browser */ } }       // unless the box already took it (no microphone: the note)
  }

  // the page behind is for looking only while the sheet is open
  function behind(on) {
    ['main', 'ph-tabs'].forEach(function (k) {
      var n = k === 'main' ? document.getElementById('main') : document.querySelector('.' + k);
      if (n) { if (on) n.setAttribute('inert', ''); else n.removeAttribute('inert'); }
    });
  }

  // a fragment becomes the sheet's content and the box in it is started
  function fill(html, first) {
    if (ctl) { ctl.destroy(); ctl = null; }
    scroll.innerHTML = html;
    scroll.scrollTop = 0;
    ctl = window.AskBox.init(scroll);
    if (!first) { try { sheet.focus({ preventScroll: true }); } catch (e) { /* old browser */ } }
  }

  function kb() {
    var vv = window.visualViewport;
    if (!vv || !wrap) return;
    wrap.style.setProperty('--ak-kb', Math.max(0, window.innerHeight - vv.height - vv.offsetTop) + 'px');
  }
  function onKey(e) {
    if (e.key !== 'Escape' || !wrap) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    close();
  }

  // ---- close: shrink back into the button --------------------------------------------------------------------------------------
  function close() {
    if (!wrap || closing) return Promise.resolve();
    closing = true;
    if (ctl) { ctl.destroy(); ctl = null; }
    var w = wrap, s = sheet, from = getComputedStyle(s).transform;
    pointOrigin();
    var scrim = w.querySelector('.ak-scrim');
    w.classList.remove('is-open');
    return Promise.all([
      animate(scrim, [{ opacity: parseFloat(getComputedStyle(scrim).opacity) || 1 }, { opacity: 0 }]),
      animate(s, [{ transform: from === 'none' ? 'none' : from, opacity: 1 }, { transform: 'scale(0.08)', opacity: 0 }]),
    ]).then(function () {
      if (w.parentNode) w.parentNode.removeChild(w);
      back.forEach(function (f) { f(); });
      back = [];
      wrap = sheet = scroll = null;
      closing = false;
      behind(false);
      try { tab.focus({ preventScroll: true }); } catch (e) { /* old browser */ }
    });
  }

  // ---- swipe down on the grabber (and on the sheet when its content is at the top) ---------------------------------------------
  function grabbing(grab) {
    var d = null;
    function move(y, t) {
      var dy = Math.max(0, y - d.y0);
      d.dy = dy;
      d.samples.push([t, dy]);
      if (d.samples.length > 6) d.samples.shift();
      sheet.style.transform = 'translateY(' + dy + 'px)';
      var s = wrap && wrap.querySelector('.ak-scrim');
      if (s) s.style.opacity = String(Math.max(0, 1 - dy / (sheet.offsetHeight * 1.2)));
    }
    function end(cancel) {
      if (!d) return;
      var dd = d, h = sheet.offsetHeight, a = dd.samples[0], b = dd.samples[dd.samples.length - 1];
      d = null;
      var v = a && b && b[0] > a[0] ? (b[1] - a[1]) / (b[0] - a[0]) : 0;       // px per ms over the last few moves
      var scrim = wrap && wrap.querySelector('.ak-scrim');
      if (!cancel && (dd.dy > h * 0.3 || (v > 0.5 && dd.dy > 24))) {        // a third of the way, or a quick flick (more than half a pixel a millisecond)
        sheet.style.transform = '';
        if (scrim) scrim.style.opacity = '';
        // the sheet is already part way down: shrink from where it is
        sheet.style.transform = 'translateY(' + dd.dy + 'px)';
        close();
        return;
      }
      sheet.style.transition = reduced.matches ? 'none' : 'transform ' + ms() + 'ms ' + ease();
      sheet.style.transform = '';
      if (scrim) scrim.style.opacity = '';
      setTimeout(function () { if (sheet) sheet.style.transition = ''; }, ms() + 20);
    }
    grab.addEventListener('pointerdown', function (e) {
      if (closing || e.button > 0) return;
      d = { id: e.pointerId, y0: e.clientY, dy: 0, samples: [[e.timeStamp, 0]] };
      try { grab.setPointerCapture(e.pointerId); } catch (err) { /* synthetic pointers */ }
    });
    grab.addEventListener('pointermove', function (e) { if (d && e.pointerId === d.id) move(e.clientY, e.timeStamp); });
    grab.addEventListener('pointerup', function (e) { if (d && e.pointerId === d.id) { move(e.clientY, e.timeStamp); end(false); } });
    grab.addEventListener('pointercancel', function () { end(true); });
    // a finger pulling the sheet's own content down while that content is at the top takes the sheet with it
    var t = null;
    sheet.addEventListener('touchstart', function (e) {
      if (closing || e.touches.length !== 1 || !scroll || scroll.scrollTop > 0 || e.target.closest('textarea, input, .ak-dpicks')) { t = null; return; }
      t = { y0: e.touches[0].clientY, on: false };
    }, { passive: true });
    sheet.addEventListener('touchmove', function (e) {
      if (!t || e.touches.length !== 1) return;
      var dy = e.touches[0].clientY - t.y0;
      if (!t.on && dy > 12 && scroll.scrollTop <= 0) { t.on = true; d = { id: -1, y0: t.y0, dy: 0, samples: [[e.timeStamp, 0]] }; }
      if (t.on && d) { if (e.cancelable) e.preventDefault(); move(e.touches[0].clientY, e.timeStamp); }
    }, { passive: false });
    sheet.addEventListener('touchend', function () { if (t && t.on) end(false); t = null; });
    sheet.addEventListener('touchcancel', function () { if (t && t.on) end(true); t = null; });
  }

  // ---- the forms inside post with X-Ask ---------------------------------------------------------------------------------------
  function ids() {
    var out = {};
    document.querySelectorAll('.cz-gb[data-act]').forEach(function (n) { out[n.dataset.act] = 1; });
    return out;
  }
  function oops(f, labels, text) {
    delete f.dataset.sent;
    f.removeAttribute('aria-busy');
    var bs = f.querySelectorAll('button');
    bs.forEach(function (b, i) { b.disabled = false; if (labels[i] !== undefined) b.textContent = labels[i]; });
    var slot = scroll && scroll.querySelector('#ak-error');
    if (!slot) {
      slot = document.createElement('div');
      slot.id = 'ak-error';
      slot.className = 'tp-error ak-error';
      slot.setAttribute('role', 'alert');
      f.insertBefore(slot, f.firstChild);
    }
    slot.textContent = text;
  }
  function onSubmit(e) {
    var f = e.target;
    if (e.defaultPrevented || !f.matches || !f.closest('#ak-sheet-body')) return;
    e.preventDefault();
    var action = (e.submitter && e.submitter.getAttribute('formaction')) || f.getAttribute('action');
    var labels = Array.prototype.map.call(f.querySelectorAll('button'), function (b) { return b.textContent; });
    var applying = f.id === 'ak-apply-form', before = applying ? ids() : null;
    fetch(action, { method: 'POST', body: new URLSearchParams(new FormData(f)), credentials: 'same-origin', headers: { 'X-Ask': '1' } }).then(function (r) {
      var json = /json/.test(r.headers.get('content-type') || '');
      return r.text().then(function (text) { return { ok: r.ok, status: r.status, json: json, text: text }; });
    }).then(function (r) {
      if (!wrap || closing) return;
      if (r.json && r.ok) { applied(JSON.parse(r.text), before); return; }
      if (/id="ak-sheet-body"/.test(r.text)) { fill(r.text, false); return; }
      oops(f, labels, r.status === 403 ? 'Only editors can change the plan.' : 'That did not go through. Try again.');
    }, function () { if (wrap && !closing) oops(f, labels, 'That did not go through. Check the connection and try again. What you said is still here.'); });
  }

  // ---- Apply worked: close, bring the day up to date, glow what changed, say so ---------------------------------------------------
  function applied(j, before) {
    cache = {};
    var CZ = window.CZ, v = CZ && CZ.view ? CZ.view() : null;
    var shown = v && v.dataset.level === 'day' ? v.dataset.day : null;
    var other = j.day !== null && j.day !== undefined && shown !== null && String(j.day) !== shown;      // another day was chosen: show that one
    var closed = close();
    var refreshed;
    if (!v) refreshed = Promise.resolve();
    else if (other && CZ.forget) { CZ.forget(); refreshed = CZ.goto('/trip/canvas?day=' + j.day, { dir: 'side', mode: 'replace', key: null }); }
    else refreshed = CZ.quiet();
    Promise.all([closed, refreshed]).then(function () {
      glow(j.ids || [], before || {});
      say(j.toast, !v && j.day !== null && j.day !== undefined ? '/trip/canvas?day=' + j.day : '');
      ahead();
    });
  }
  function glow(wanted, before) {
    var hit = [];
    wanted.forEach(function (id) {
      document.querySelectorAll('.cz-gb[data-act="' + id + '"], [data-drag="' + id + '"]').forEach(function (n) { hit.push(n); });
    });
    document.querySelectorAll('.cz-gb[data-act]').forEach(function (n) { if (!before[n.dataset.act] && hit.indexOf(n) < 0) hit.push(n); });
    hit.forEach(function (n) { n.classList.add('ak-fresh'); });
    var first = hit[0];
    if (first) {
      var r = first.getBoundingClientRect();
      if (r.top < 0 || r.bottom > window.innerHeight - 96) first.scrollIntoView({ block: 'center', behavior: reduced.matches ? 'auto' : 'smooth' });
    }
    setTimeout(function () { hit.forEach(function (n) { n.classList.remove('ak-fresh'); }); }, 2200);
  }
  function say(text, href) {
    if (toast && toast.parentNode) toast.parentNode.removeChild(toast);
    clearTimeout(toastTimer);
    toast = document.createElement('div');
    toast.className = 'ak-toast';
    toast.id = 'ak-toast';
    toast.setAttribute('role', 'status');
    var t = document.createElement('span');
    t.className = 'ak-toast-t';
    t.textContent = text || 'Done';
    toast.appendChild(t);
    if (href) {
      var a = document.createElement('a');
      a.href = href;
      a.textContent = 'See the day';
      toast.appendChild(a);
    }
    app.appendChild(toast);
    toastTimer = setTimeout(function () { if (toast && toast.parentNode) toast.parentNode.removeChild(toast); toast = null; }, 7000);
  }
})();
