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
//
// AT ONCE (F-177): the pane is fetched ahead, when the page has been idle a moment (after it loads, after another day is shown, after Family is left) and on pointerover / pointerdown / focus of
// the Family tab or the top bar's Family, together with the text of thread.js and voicenote.js. A click then draws the pane in the same frame, from that copy (no request is waited for); the
// chat polls once straight away for what is new, and the rows follow after /seen. The panel draws the newest 30 messages; "Earlier messages" asks for the 30 before the first one shown.
// On the week, the top bar's Family opens the day (today, else the first) with the Family panel, as Ask does.
(function () {
  var stage = document.getElementById('cz');
  if (!stage || !window.Dock) return;
  var CZ = window.CZ, MO = window.GA && window.GA.motion;
  var desk = window.matchMedia('(min-width: 1020px) and (not (display-mode: standalone))');
  var POLL = 5000, TRIP = 'trip';
  var key = TRIP, token = 0, open = false, timer = 0, busy = false, planBusy = false, voiceLoaded = false, going = false;
  var AHEAD = 60000, KEEP = 4;       // a copy fetched ahead is used for this long (ms); at most this many are kept

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

  // ---- fetched ahead ----------------------------------------------------------------------------------------------------------------
  var ahead = {}, code = {};
  function panelUrl(want, day) { return '/trip/family/panel?thread=' + encodeURIComponent(want) + '&day=' + encodeURIComponent(day); }
  function warm(want, day) {              // the pane for this chat and day: the copy fetched ahead (or on its way), else a new request
    var u = panelUrl(want, day), e = ahead[u];
    if (e && Date.now() - e.at < AHEAD) return e;
    e = ahead[u] = { at: Date.now(), html: null, total: null, p: null };
    e.p = fetch(u, { credentials: 'same-origin', headers: { Accept: 'text/html' } }).then(function (r) {
      if (!r.ok) throw new Error('no panel');
      return r.text().then(function (t) { e.html = t; e.total = r.headers.get('X-Family-Unread'); return e; });
    }, function (err) { throw err; });
    e.p.catch(function () { if (ahead[u] === e) delete ahead[u]; });
    Object.keys(ahead).sort(function (a, b) { return ahead[b].at - ahead[a].at; }).slice(KEEP).forEach(function (k) { delete ahead[k]; });
    ['thread', 'voicenote'].forEach(function (n) {      // the phone's script and the notes' player, as text: starting the pane runs them in the same frame
      if (code[n]) return;
      code[n] = { text: null };
      fetch('/assets/js/' + n + '.js', { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.text() : null; }).then(function (t) { code[n].text = t; }, function () { delete code[n]; });
    });
    return e;
  }
  function soon() {                       // when the page is idle a moment: the pane of the chat last open, for the day on the screen
    var d = dock(), v = CZ.view(), day = d ? d.dataset.day || '0' : v && v.dataset.level === 'week' ? v.dataset.famDay : '';      // (on the week: the day its Family opens)
    if (!desk.matches || !day || !Dock.has('family') || !visible() || Dock.mode() === 'family') return;
    warm(key, day);
  }
  function later() {
    if (window.requestIdleCallback) window.requestIdleCallback(function () { setTimeout(soon, 300); }, { timeout: 2000 });
    else setTimeout(soon, 600);
  }
  function near(e) {                      // the pointer or the keyboard is on a way in
    if (!desk.matches || !e.target.closest) return;
    var a = e.target.closest('.cz-dock-tab[data-tab="family"], .ga-tb-family');
    if (!a) return;
    var d = dock(), v = CZ.view();
    if (d && Dock.has('family')) warm(key, d.dataset.day || '0');
    else if (v && v.dataset.level === 'week' && v.dataset.famDay) warm(key, v.dataset.famDay);
  }
  document.addEventListener('pointerover', near, { passive: true });
  document.addEventListener('pointerdown', near, { passive: true });
  document.addEventListener('focusin', near);

  function run(name) {                    // a script of the pane, from the text fetched ahead (no wait), else as a script tag
    var c = code[name], s = document.createElement('script');
    // (inline code: a future script-src CSP without 'unsafe-inline' would block this silently, and the pane would not start; the sourceURL keeps the file's name in the devtools)
    if (c && c.text) { s.text = c.text + '\n//# sourceURL=/assets/js/' + name + '.js'; document.body.appendChild(s); s.remove(); return; }
    s.src = '/assets/js/' + name + '.js'; s.async = false;
    s.addEventListener('load', function () { s.remove(); });
    document.body.appendChild(s);
  }
  function boot(stale) {                  // the phone's own script on the new pane, and the notes' player once
    var p = pane();
    if (!p || !desk.matches) return;
    key = p.dataset.key || TRIP;
    var t = p.querySelector('#ft-thread'), last = t ? t.dataset.last : '0';      // what the pane shows is now seen (the server only marks what it draws on a laptop's request)
    fetch('/trip/family/seen', { method: 'POST', credentials: 'same-origin', body: new URLSearchParams({ key: key, upto: last || '0' }) }).then(function () { refreshList(); }, function () { /* the next poll marks it */ });
    run('thread');
    if (!voiceLoaded) { voiceLoaded = true; run('voicenote'); }
    if (stale && t) t.dispatchEvent(new CustomEvent('ft-refresh'));      // the copy is a moment old: what is new comes now, not at the next poll
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
    var d = dock(), mine = ++token, day = d.dataset.day || '0', u = panelUrl(want, day), e = warm(want, day), ahead_ = e.html !== null;      // (fetched ahead: it may be a moment old, so what is new is asked for at once)
    function show() {                     // the copy is here: the pane is drawn now (the same frame as the click when it was fetched ahead)
      if (ahead[u] === e) delete ahead[u];      // (it is used once: the next open gets a fresh one, fetched when Family is left)
      if (mine !== token || !dock() || Dock.mode() !== 'family') return;
      var frag = parse(e.html), np = frag.querySelector('.cz-fam'), nf = frag.querySelector('.cz-fam-foot'), compose = dock().querySelector('.cz-compose');
      if (!np || !nf) throw new Error('no pane');
      drop();
      dock().insertBefore(np, compose || null);
      dock().insertBefore(nf, compose || null);
      badge(e.total);
      boot(ahead_);
      if (animate && MO) MO.settle(np);
    }
    function failed() {
      if (mine !== token || !dock()) return;
      var p = pane();
      if (p) { var er = foot() && foot().querySelector('.cz-error'); if (er) { er.textContent = 'The chats could not load. Try again.'; er.hidden = false; } }
    }
    if (e.html !== null) { try { show(); } catch (x) { failed(); } return Promise.resolve(); }
    return e.p.then(show).catch(failed);
  }

  stage.addEventListener('click', function (e) {          // "Earlier messages": the 30 before the first one shown, put above it without moving what is read
    var b = e.target.closest ? e.target.closest('#ft-older') : null, t = document.getElementById('ft-thread'), first = t && t.querySelector('[data-n]');
    if (!b || !t || !first || b.disabled) return;
    e.preventDefault();
    b.disabled = true;
    var rel = function () { return first.getBoundingClientRect().top - t.getBoundingClientRect().top; }, seen = rel();      // where the oldest message shown now sits: it stays there (a name or a time line it loses to the regrouping is above or inside it)
    fetch(b.dataset.older + '&before=' + encodeURIComponent(first.dataset.n), { credentials: 'same-origin', headers: { Accept: 'text/html' } }).then(function (r) {
      if (!r.ok) throw new Error('no earlier');
      return r.text().then(function (h) { return { h: h, more: r.headers.get('X-Thread-More') === '1' }; });
    }).then(function (got) {
      if (!t.isConnected) return;
      t.insertBefore(parse(got.h), t.firstChild);
      if (window.GA && GA.runs) GA.runs.fix(t);      // (F-178: the older page may end with the person who wrote the first message shown: regroup before the scroll is put back)
      t.scrollTop += rel() - seen;
      if (got.more) b.disabled = false; else { b.remove(); }
    }, function () { b.disabled = false; });
  });

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
  document.addEventListener('click', function (e) {         // the top bar's Family, on the day: the same switch; on the week, the day (today, else the first) with the chats in its panel
    var a = e.target.closest ? e.target.closest('.ga-tb-family') : null;
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button || !desk.matches) return;
    if (Dock.show('family', {})) { e.preventDefault(); return; }
    var v = CZ.view(), day = v && v.dataset.level === 'week' ? v.dataset.famDay : '';
    if (!day || !/^\d+$/.test(day)) return;
    e.preventDefault();
    if (going) return;
    going = true;
    warm(key, day);
    Promise.resolve(CZ.goto('/trip/canvas?day=' + day, { mode: 'push' })).then(function () {
      going = false;
      var nv = CZ.view();
      if (nv && nv.dataset.level === 'day') Dock.show('family', {});
    }, function () { going = false; });
  });
  stage.addEventListener('click', function (e) {            // "Open in Family" in a plan's pane: that plan's chat, in place
    var a = e.target.closest ? e.target.closest('#cz-pp-family') : null, p = a && a.closest('.cz-pp');
    if (!a || !p || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
    if (Dock.show('family', { key: p.dataset.act })) e.preventDefault();
  });

  // Esc (F-144 keeps the keys, each thing closes in its own file): in the chats it puts the panel back to Up next, like the plan's pane; a message being written is not thrown away, the
  // first Esc only leaves the box. Before the canvas's own Escape, which would zoom the day out to the week.
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || e.defaultPrevented || !desk.matches || Dock.mode() !== 'family' || CZ.menuOpen || e.isComposing) return;
    if (stage.querySelector('.cz-sheet-wrap, .cz-card-wrap, .cz-menu')) return;
    var t = e.target;
    e.preventDefault(); e.stopImmediatePropagation();
    if (t && t.id === 'ft-text' && t.value) { t.blur(); return; }
    Dock.close();
  }, true);

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
      if (window.GA && GA.runs) GA.runs.watch(msgs);      // (F-178)
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
    if (d.from === 'family' && d.mode !== 'family') later();      // (the next open is then at once too)
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
    later();
    if (open && desk.matches && Dock.mode() !== 'family') {      // another day: the panel keeps the chats open (the new day's panel came up idle)
      setTimeout(function () { if (open && Dock.mode() !== 'family') Dock.show('family', { key: key }); }, 0);      // (after the canvas has written the new day's address, which the panel then adds to)
    }
  });
  if (pane() && !desk.matches) drop();     // below 1020px nobody sees the panel: its chat is not started, not marked read and not left in the page for another chat script to find
  else if (pane()) { open = true; boot(); }     // the address had the chats open: the server drew them, so only start them
  else { sync(); later(); }
  desk.addEventListener('change', function () {      // a window made wide (or narrow) after the page loaded
    if (!desk.matches) { open = false; drop(); sync(); }
    else if (Dock.mode() === 'family' && !pane()) { open = true; load(key, false); }
  });
})();
