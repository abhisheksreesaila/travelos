// Family chat in the panel (F-143, frame A3 of docs/design/canvas/Web-Trip-v1.html). One `Dock.register('family', ...)` (day_dock.js): the Family tab, the top bar's Family and "Open in Family" in a
// plan's pane switch the panel to the trip's chats without a page load. The pane is drawn by the server (gitaway/pages/familydock.py: the chats as rows, People and invites, the open chat and its
// message bar) and fetched from `/trip/family/panel?thread=KEY&day=N`; it is the Family tab's own markup, and the phone's own `thread.js` is run on it, so sending (the bubble at once, Retry),
// the order of messages and the live poll are the phone's. Nothing here forks a chat.
//
// LIVE: while the Family or the Plan pane is open and the tab is visible, every POLL ms (the phone's 5 s):
//   - the open Family chat is polled by thread.js (`data-poll-url`, with `read=1`: what it shows is marked read);
//   - the rows (who said what last, the counts) are asked again from `/trip/family/list`, and the Family tab's count follows (`X-Family-Unread`);
//   - a plan's chat in the Plan pane (F-141) asks `/trip/talk/items?act=&since=&read=1` and appends what others said.
// A hidden tab asks for nothing and asks once as soon as it is shown again. A new message is simply there (no motion, F-118).
(function () {
  var stage = document.getElementById('cz');
  if (!stage || !window.Dock) return;
  var CZ = window.CZ, MO = window.GA && window.GA.motion;
  var desk = window.matchMedia('(min-width: 1020px) and (not (display-mode: standalone))');
  var POLL = 5000, TRIP = 'trip';
  var key = TRIP, token = 0, open = false, timer = 0, busy = false, planBusy = false, voiceLoaded = false;

  function dock() { return document.getElementById('cz-dock'); }
  function pane() { var d = dock(); return d && d.querySelector('.cz-fam'); }
  function foot() { var d = dock(); return d && d.querySelector('.cz-fam-foot'); }
  function parse(html) { var t = document.createElement('template'); t.innerHTML = html; return t.content; }
  function visible() { return document.visibilityState !== 'hidden'; }

  function badge(total) {                // the Family tab's count (the chats you have not read)
    var tab = dock() && dock().querySelector('.cz-dock-tab[data-tab="family"]'), b = tab && tab.querySelector('.cz-dock-un');
    total = parseInt(total, 10) || 0;
    if (!tab) return;
    if (!total) { if (b) b.remove(); return; }
    if (!b) {
      b = document.createElement('span'); b.className = 'cz-dock-un'; b.id = 'cz-dock-un';
      var s = document.createElement('span'); s.className = 'sr-only'; s.textContent = ' unread';
      b.appendChild(document.createTextNode(String(total))); b.appendChild(s); tab.appendChild(b);
    } else if (b.firstChild) b.firstChild.nodeValue = String(total);
  }

  function script(src) { var s = document.createElement('script'); s.src = src; s.async = false; document.body.appendChild(s); return s; }
  function boot() {                       // the phone's own script on the new pane, and the notes' player once
    var p = pane();
    if (!p || !desk.matches) return;
    key = p.dataset.key || TRIP;
    var last = p.querySelector('#ft-thread') ? p.querySelector('#ft-thread').dataset.last : '0';      // what the pane shows is now seen (the server only marks what it draws on a laptop's request)
    fetch('/trip/family/seen', { method: 'POST', credentials: 'same-origin', body: new URLSearchParams({ key: key, upto: last || '0' }) }).then(function () { refreshList(); }, function () { /* the next poll marks it */ });
    var s = script('/assets/js/thread.js');
    s.addEventListener('load', function () { s.remove(); });
    if (!voiceLoaded) { voiceLoaded = true; script('/assets/js/voicenote.js'); }
    sync();
  }
  function unbind() {                     // thread.js takes its listeners and timer off when its root says so
    var p = pane();
    if (p) p.dispatchEvent(new CustomEvent('ft-close'));
  }
  function drop() {
    unbind();
    var p = pane(), f = foot();
    if (p) p.remove();
    if (f) f.remove();
  }

  function load(want, animate) {
    var d = dock(), mine = ++token, day = d.dataset.day || '0';
    return fetch('/trip/family/panel?thread=' + encodeURIComponent(want) + '&day=' + encodeURIComponent(day), { credentials: 'same-origin', headers: { Accept: 'text/html' } }).then(function (r) {
      if (!r.ok) throw new Error('no panel');
      return r.text().then(function (t) { return { t: t, total: r.headers.get('X-Family-Unread') }; });
    }).then(function (got) {
      if (mine !== token || !dock() || Dock.mode() !== 'family') return;
      var frag = parse(got.t), np = frag.querySelector('.cz-fam'), nf = frag.querySelector('.cz-fam-foot'), compose = dock().querySelector('.cz-compose');
      if (!np || !nf) throw new Error('no pane');
      drop();
      dock().insertBefore(np, compose || null);
      dock().insertBefore(nf, compose || null);
      badge(got.total);
      boot();
      if (animate && MO) MO.settle(np);
    }).catch(function () {
      if (mine !== token || !dock()) return;
      var p = pane();
      if (p) { var e = foot() && foot().querySelector('.cz-error'); if (e) { e.textContent = 'The chats could not load. Try again.'; e.hidden = false; } }
    });
  }

  Dock.register('family', {
    tab: 'family',
    same: function (o, d) { var p = d.querySelector('.cz-fam'); return !!p && (!o.key || o.key === p.dataset.key); },
    url: function (o, d) {
      var k = o.key || key, u = d.dataset.familyUrl || d.dataset.base;
      return k === TRIP ? u.replace('&thread=THREAD', '').replace('thread=THREAD&', '') : u.replace('THREAD', encodeURIComponent(k));
    },
    enter: function (o, from) {
      open = true;
      var p = pane(), want = o.key || (p && p.dataset.key) || key || TRIP;
      if (p && p.dataset.key === want && from !== 'family') { boot(); return null; }      // the server drew it (the address had it): only start it
      return load(want, from !== 'family');
    },
    leave: function () {
      open = false; token++;
      drop();
      sync();
      return null;
    }
  });

  // ---- the rows ---------------------------------------------------------------------------------------------------------------------
  stage.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('.cz-fam-th') : null;
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
    e.preventDefault();
    if (Dock.mode() === 'family') Dock.show('family', { key: a.dataset.thread });
  });
  document.addEventListener('click', function (e) {         // the top bar's Family, on the day: the same switch
    var a = e.target.closest ? e.target.closest('.ga-tb-family') : null;
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button || !desk.matches) return;
    if (Dock.show('family', {})) e.preventDefault();
  });
  stage.addEventListener('click', function (e) {            // "Open in Family" in a plan's pane: that plan's chat, in place
    var a = e.target.closest ? e.target.closest('#cz-pp-family') : null, p = a && a.closest('.cz-pp');
    if (!a || !p || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
    if (Dock.show('family', { key: p.dataset.act })) e.preventDefault();
  });

  // ---- live -------------------------------------------------------------------------------------------------------------------------
  function refreshList() {
    var d = dock(), p = pane();
    if (busy || !d || !p || Dock.mode() !== 'family' || Dock.busy()) return;
    busy = true;
    var want = p.dataset.key;
    fetch('/trip/family/list?open=' + encodeURIComponent(want) + '&day=' + encodeURIComponent(d.dataset.day || '0'), { credentials: 'same-origin', headers: { Accept: 'text/html' } }).then(function (r) {
      if (!r.ok) return null;
      return r.text().then(function (t) { return { t: t, total: r.headers.get('X-Family-Unread') }; });
    }).then(function (got) {
      busy = false;
      var now = pane(), list = now && now.querySelector('#cz-fam-list');
      if (!got || !list || now.dataset.key !== want) return;
      var fresh = parse(got.t).querySelector('#cz-fam-list'), on = list.contains(document.activeElement) ? document.activeElement.dataset.thread : '';
      if (fresh && fresh.innerHTML !== list.innerHTML) {
        list.innerHTML = fresh.innerHTML;
        if (on) { var back = list.querySelector('[data-thread="' + on.replace(/"/g, '') + '"]'); if (back) back.focus({ preventScroll: true }); }
      }
      badge(got.total);
    }, function () { busy = false; });
  }

  function planChat() {                    // others' new messages in the plan's pane (F-141)
    var d = dock(), msgs = document.getElementById('cz-pp-msgs'), pp = msgs && msgs.closest('.cz-pp');
    if (planBusy || !d || !msgs || !pp || pp.classList.contains('is-loading') || pp.classList.contains('is-leaving') || Dock.mode() !== 'plan') return;
    var f = d.querySelector('form.cz-pp-foot'), trip = f && f.elements.trip ? f.elements.trip.value : '', last = parseInt(msgs.dataset.last, 10) || 0;
    planBusy = true;
    fetch('/trip/talk/items?act=' + encodeURIComponent(pp.dataset.act) + '&since=' + last + '&trip=' + encodeURIComponent(trip) + '&read=1', { credentials: 'same-origin', headers: { Accept: 'text/html' } }).then(function (r) {
      if (!r.ok) return null;
      return r.text().then(function (t) { return { t: t, last: parseInt(r.headers.get('X-Thread-Last'), 10) || 0 }; });
    }).then(function (got) {
      planBusy = false;
      if (!got || !msgs.isConnected || !got.t.trim()) return;
      var near = pp.scrollHeight - pp.scrollTop - pp.clientHeight < 160, added = 0, nodes = parse(got.t);
      Array.prototype.slice.call(nodes.children).forEach(function (n) {
        var id = n.getAttribute('data-n');
        if (id && msgs.querySelector('[data-n="' + id + '"]')) return;      // already here (mine, just sent)
        msgs.appendChild(n); added++;
      });
      if (got.last > last) { msgs.dataset.last = String(got.last); if (f && f.elements.since) f.elements.since.value = String(got.last); }
      var none = document.getElementById('cz-pp-quiet');
      if (none) none.hidden = true;
      if (added) {
        if (near) pp.scrollTop = pp.scrollHeight;
        if (CZ.forget) CZ.forget();
        CZ.quiet();                        // the block behind shows its new chat count
      }
    }, function () { planBusy = false; });
  }

  function tick() {
    if (!visible()) return;
    if (Dock.mode() === 'family') refreshList();
    else if (Dock.mode() === 'plan') planChat();
  }
  function sync() {                        // the timer runs only while the Family or Plan pane is open and the tab is seen
    var m = Dock.mode(), want = visible() && (m === 'family' || m === 'plan');
    if (want && !timer) timer = setInterval(tick, POLL);
    if (!want && timer) { clearInterval(timer); timer = 0; }
  }
  stage.addEventListener('dock:mode', function (e) {      // the top bar marks the section the panel is in: Family while the chats are open, Trip otherwise
    var fam = document.querySelector('.ga-tb-family'), trip = document.querySelector('.ga-tb-trip'), d = e.detail || {};
    if (fam && trip && d.mode !== d.from) {
      if (d.mode === 'family') { fam.setAttribute('aria-current', 'page'); trip.removeAttribute('aria-current'); }
      else if (d.from === 'family') { trip.setAttribute('aria-current', 'page'); fam.removeAttribute('aria-current'); }
    }
    sync();
  });
  document.addEventListener('visibilitychange', function () { sync(); if (visible()) tick(); });

  // ---- the day --------------------------------------------------------------------------------------------------------------------------
  stage.addEventListener('cz:swap', function (e) {
    sync();
    if (e.detail && e.detail.quiet) return;
    if (open && desk.matches && Dock.mode() !== 'family') {      // another day: the panel keeps the chats open (the new day's panel came up idle)
      setTimeout(function () { if (open && Dock.mode() !== 'family') Dock.show('family', { key: key }); }, 0);      // (after the canvas has written the new day's address, which the panel then adds to)
    }
  });
  if (pane() && !desk.matches) drop();     // below 1020px nobody sees the panel: its chat is not started, not marked read and not left in the page for another chat script to find
  else if (pane()) { open = true; boot(); }     // the address had the chats open: the server drew them, so only start them
  else sync();
  desk.addEventListener('change', function () {      // a window made wide (or narrow) after the page loaded
    if (!desk.matches) { open = false; drop(); sync(); }
    else if (Dock.mode() === 'family' && !pane()) { open = true; load(key, false); }
  });
})();
