// Ask in the panel (F-142, frame A2 of docs/design/canvas/Web-Trip-v1.html; docs/trip-canvas.md "Ask lives in the panel"). On a laptop (the same media query as day_dock.css) the Ask box is a MODE of the
// docked panel, registered with the one `Dock.register('ask', ...)` of day_dock.js. It is the phone's Ask box, not a second one: the server's own fragments (`GET /trip/ask?day=N&mode=` with
// `X-Ask: 1`, the box, the follow-up questions, the preview) are drawn into the panel and ask.js (`AskBox.init`) drives them, exactly as ask_sheet.js does in the phone's sheet.
//
// What opens it (any link to /trip/ask on the trip canvas's day or week): the top bar's Ask and the `/` key (topbar.js clicks that link), the panel's Ask tab, the compose bar and the mic of
// Up next, Say the plan (the microphone starts, as on the phone) and Paste a plan (the note is focused, ready for a long paste). On the week there is no panel: the link opens the day
// (the link's own day, else today, else the first, `data-ask-day`) with the Ask mode in it. Every other page, the tablet and the phone keep the link (the page, or the phone's sheet).
//
// Apply (a JSON reply, as on the phone): the panel goes back to Up next, the grid is brought up to date in place (CZ.quiet, or the day that was chosen), what changed glows for a moment and
// the one toast says what was done and that the family has been told. The panel is left alone by the day's own refreshes while Ask is open (CZ.dockBusy), so a half-said request is never lost.
(function () {
  var stage = document.getElementById('cz'), CZ = window.CZ, Dock = window.Dock, MO = window.GA && window.GA.motion;
  if (!stage || !CZ || !Dock || !MO) return;
  var desk = window.matchMedia('(min-width: 1020px) and (not (display-mode: standalone))');
  var fr = null;      // (ask_flow.js and ask.js come with the page shell, after this file: used when asked)
  function frags() { return fr || (fr = window.AskFlow.fragments(30000)); }
  var ctl = null, body = null, leaving = Promise.resolve(), going = false;

  function dock() { return document.getElementById('cz-dock'); }
  function pane() { var d = dock(); return d && d.querySelector('.cz-ak:not(.is-leaving)'); }
  function tabOf() { var d = dock(); return d && d.querySelector('.cz-dock-tab[data-tab="ask"]'); }
  function mk(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; }
  function svgX() {
    var s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'), p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    s.setAttribute('width', '18'); s.setAttribute('height', '18'); s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor');
    s.setAttribute('stroke-width', '2.6'); s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round'); s.setAttribute('aria-hidden', 'true');
    p.setAttribute('d', 'M18 6 6 18M6 6l12 12'); s.appendChild(p);
    return s;
  }

  // ---- the fragment, fetched ahead (the microphone starts inside the click, so the box must be there already) ------------------------
  function url(day, mode) { return '/trip/ask?day=' + day + '&mode=' + mode; }
  function get(u) { return frags().get(u); }
  function target(a) {                                       // a link to the Ask page on this canvas -> { day, mode } or null
    var u;
    try { u = new URL(a.getAttribute('href'), location.href); } catch (e) { return null; }
    if (u.origin !== location.origin || u.pathname.replace(/\/$/, '') !== '/trip/ask') return null;
    var v = CZ.view(), lv = v && v.dataset.level;
    if (lv !== 'day' && lv !== 'week') return null;
    var q = u.searchParams.get('day'), day = q !== null && /^\d+$/.test(q) ? +q : lv === 'day' ? +v.dataset.day : +v.dataset.askDay;
    if (isNaN(day)) return null;
    var m = u.searchParams.get('mode');
    return { day: day, mode: m === 'talk' || m === 'paste' ? m : 'type' };
  }
  function ahead(e) {
    if (!desk.matches) return;
    var a = e.target.closest && e.target.closest('a[href*="/trip/ask"]'), t = a && target(a);
    if (t) get(url(t.day, t.mode)).p.catch(function () {});
  }
  document.addEventListener('pointerover', ahead, { passive: true });
  document.addEventListener('pointerdown', ahead, { passive: true });
  document.addEventListener('focusin', ahead);

  // ---- the mode ---------------------------------------------------------------------------------------------------------------------
  function fill(html, late) {
    if (ctl) { ctl.destroy(); ctl = null; }
    body.innerHTML = html;
    body.scrollTop = 0;
    var f = body.querySelector('#ak-form');
    if (f && late && f.dataset.mode === 'talk') f.removeAttribute('data-mode');      // the box came after the click: the user activation may be gone, so the big mic waits to be tapped
    ctl = window.AskBox.init(body);
    var box = body.querySelector('#ak-text'), mode = f && f.dataset.mode;
    if (box && mode !== 'talk') { try { box.focus({ preventScroll: true }); } catch (e) { /* no focus */ } }       // typing, or a long paste, goes straight in
    else if (!box) { var p = pane(); try { (body.querySelector('#ak-apply') || p).focus({ preventScroll: true }); } catch (e) { /* no focus */ } }
  }
  function build(day) {
    var p = mk('section', 'cz-dock-body cz-ak'), hd = mk('header', 'cz-ak-hd'), x = mk('span', 'cz-pp-x'), close = mk('button', 'cz-pp-close');
    p.dataset.pane = 'ask'; p.dataset.day = String(day); p.setAttribute('aria-labelledby', 'cz-ak-title'); p.tabIndex = -1;
    close.type = 'button'; close.setAttribute('aria-label', 'Close Ask'); close.setAttribute('data-dock-close', ''); close.appendChild(svgX());
    x.appendChild(mk('span', 'cz-pp-kbd', 'esc')); x.appendChild(close);
    var h = mk('h2', 'cz-ak-t', 'Ask GitAway'); h.id = 'cz-ak-title';
    hd.appendChild(h); hd.appendChild(x);
    body = mk('div', 'cz-ak-body');
    body.appendChild(mk('p', 'ak-fine', 'Getting ready'));
    body.firstChild.setAttribute('role', 'status');
    p.appendChild(hd); p.appendChild(body);
    p.addEventListener('submit', onSubmit);
    return p;
  }

  Dock.register('ask', {
    tab: 'ask',
    same: function (o) { var p = pane(); return !!p && !o.mode && (o.day === undefined || String(o.day) === p.dataset.day); },
    enter: function (o, from) {
      var d = dock(), day = o.day !== undefined ? o.day : +d.dataset.day, mode = o.mode || 'type', old = pane();
      if (old) { if (ctl) { ctl.destroy(); ctl = null; } old.remove(); }
      var p = build(day), entry = get(url(day, mode)), html = entry.html;
      d.insertBefore(p, d.querySelector('.cz-compose') || null);
      var landed = from === 'ask' ? MO.settle(p) : MO.open(p, o.origin || tabOf(), { radius: ['0.875rem', '1.75rem'] });
      if (html !== null) fill(html, false);
      else entry.p.then(function (h) { if (p.isConnected && !p.classList.contains('is-leaving')) fill(h, true); }, function () {
        if (!p.isConnected) return;
        body.textContent = '';
        var m = mk('p', 'ak-fine', 'Ask could not load. '), a = mk('a', 'cz-pp-open', 'Open the Ask page');
        a.setAttribute('data-ask-page', ''); a.href = url(day, mode).replace('&mode=' + mode, ''); m.appendChild(a); body.appendChild(m);
      });
      if (!p.contains(document.activeElement)) { try { p.focus({ preventScroll: true }); } catch (e) { /* no focus */ } }
      return landed;
    },
    leave: function () {
      var d = dock(), p = pane();
      if (ctl) { ctl.destroy(); ctl = null; }
      if (!p) return null;
      var tab = tabOf(), pr = p.getBoundingClientRect(), dr = d.getBoundingClientRect(), had = p.contains(document.activeElement);
      p.classList.add('is-leaving');
      p.style.cssText = 'position:absolute;left:' + (pr.left - dr.left) + 'px;top:' + (pr.top - dr.top) + 'px;width:' + pr.width + 'px;height:' + pr.height + 'px;z-index:3';
      if (had && tab) { try { tab.focus({ preventScroll: true }); } catch (e) { /* no focus */ } }
      var gone = function () { p.remove(); };
      leaving = MO.close(p, tab, { radius: ['0.875rem', '1.75rem'] }).then(gone, gone);
      return leaving;
    }
  });

  // Whether Ask is the panel's to show is decided when it is asked (the level on the screen now, not the page that was loaded): an editor's day carries `data-ask` on its panel, an editor's week
  // `data-ask-day`; a viewer's carry neither, and block and step levels have no panel. `Dock.has('ask')` and `Dock.show('ask')` follow it: **`Dock.show('ask')` is false where there is no panel
  // to show it in (the week, a block, a viewer), so a caller (F-144's `/`) can fall back to the link**; the links themselves (target() below) open the day first on the week.
  function can() { return !!stage.querySelector('#cz-dock[data-ask], [data-ask-day]'); }
  var has = Dock.has, show = Dock.show;
  Dock.has = function (m) { return m === 'ask' ? has.call(Dock, m) && can() : has.call(Dock, m); };
  Dock.show = function (m, o) { return m === 'ask' && !can() ? false : show.call(Dock, m, o); };

  // the day's own refreshes leave the panel alone while Ask is open: what is being said is not thrown away
  var busy = CZ.dockBusy;
  CZ.dockBusy = function () { return (busy && busy()) || (Dock.mode() === 'ask' && !!pane()); };

  // ---- what opens it -----------------------------------------------------------------------------------------------------------------
  function openAsk(t, origin) {
    var v = CZ.view();
    if (v && v.dataset.level === 'day' && +v.dataset.day === t.day) {
      var was = Dock.mode() === 'ask', ok = Dock.show('ask', { day: t.day, mode: t.mode === 'type' ? '' : t.mode, origin: origin });
      var box = ok && was && t.mode === 'type' && pane() && pane().querySelector('#ak-text');
      if (box) box.focus();
      return;
    }
    if (going) return;                                        // the week: the day first, then the panel with the Ask mode in it
    going = true;
    get(url(t.day, t.mode)).p.catch(function () {});         // the box comes while the day does, so the microphone can start inside the same click
    Promise.resolve(CZ.goto('/trip/canvas?day=' + t.day, { mode: 'push' })).then(function () {
      going = false;
      var nv = CZ.view();
      if (nv && nv.dataset.level === 'day' && +nv.dataset.day === t.day) Dock.show('ask', { day: t.day, mode: t.mode === 'type' ? '' : t.mode });
    }, function () { going = false; });
  }
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || !desk.matches || !e.target.closest) return;
    var a = e.target.closest('a[href]');
    if (!a || a.hasAttribute('data-ask-page') || a.closest('.cz-dock-tabs') || !Dock.has('ask')) return;      // (the tab is the dock's own: day_dock.js shows the mode)
    var t = target(a);
    if (!t) return;
    e.preventDefault();
    openAsk(t, a);
  }, true);

  // ---- the forms in the panel post with X-Ask and get the next step back (ask_flow.js) ---------------------------------------------------
  function onSubmit(e) {
    var p = e.currentTarget;
    window.AskFlow.submit(e, {
      alive: function () { return p.isConnected && !p.classList.contains('is-leaving'); },
      root: function () { return body; },
      fill: function (html) { fill(html, false); },
      applied: function (j, before) {      // Apply worked: back to Up next, then the grid up to date in place, what changed glows, the toast says so
        frags().clear();
        Dock.close();
        window.AskFlow.applied(j, before, leaving, true);
      }
    });
  }

  // ---- Esc, and a day shown anew -------------------------------------------------------------------------------------------------------
  document.addEventListener('keydown', function (e) {        // Esc in the Ask panel: what was typed is kept (the field lets go first), then the panel goes back to Up next
    if (e.key !== 'Escape' || e.defaultPrevented || !desk.matches || Dock.mode() !== 'ask' || CZ.menuOpen) return;
    var p = pane(), t = e.target;
    if (!p || (t !== document.body && !p.contains(t))) return;
    if (stage.querySelector('.cz-sheet-wrap, .cz-card-wrap')) return;
    e.preventDefault(); e.stopImmediatePropagation();
    if (t.matches && t.matches('textarea') && t.value) { t.blur(); return; }
    Dock.close();
  }, true);
  stage.addEventListener('cz:swap', function (e) {
    if (!(e.detail && e.detail.quiet) && ctl && !pane()) { ctl.destroy(); ctl = null; }        // another day: its panel starts at Up next, so the box in the old one is let go
  });
})();
