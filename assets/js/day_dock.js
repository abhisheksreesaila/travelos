// The desktop day (F-140, F-141): the grid is the one thing on the left that scrolls, so this puts it where the day starts (7 AM, or now with its coral line during the trip),
// every time a day is shown, and makes "Open the plan" in the panel's Up next open the plan's card. A phone and the tablet layout scroll the page as before and are left alone (the same
// media query as day_dock.css). Hooks into canvas_core.js through the `cz:swap` event.
//
// The panel's MODES (F-141). `#cz-dock[data-mode]` is idle | plan | family | ask. `Dock` is the small API the modes plug into, so the tabs, the clicks and the keys switch the panel without a page load:
//   Dock.register(mode, { tab, same(opts, dock), url(opts, dock), enter(opts, from), leave(to) })   a mode: `tab` the tab it belongs to, `same` true when `opts` is already what is shown, `url` the address
//                                                                                                    that keeps it (none: the day's own), `enter` fills the panel (may return a promise), `leave` puts it away (a promise)
//   Dock.show(mode, opts)   switch to a mode: true when it was handled; false for a mode nobody registered (the tab's own link is then followed, so F-142 Ask and F-143 Family are one register() each)
//   Dock.close()            back to Up next (idle); Dock.mode() the mode now; Dock.busy() true while something moves (a refresh does not touch the panel then)
//   `dock:mode` bubbles from the panel on every switch with detail { mode, from, opts }.
// This file registers idle and plan. The plan mode grows the plan's pane out of its block (GA.motion.open), fills it from the card route (`/trip/canvas/card?act=&panel=1`, fetched ahead by
// day_card.js), rings the block in coral and keeps the plan in the address (`?day=N&plan=<id>`); Esc or the close button folds it back into the block.
(function () {
  var stage = document.getElementById('cz');
  if (!stage) return;
  var CZ = window.CZ, MO = window.GA && window.GA.motion;
  var desk = window.matchMedia('(min-width: 1020px) and (not (display-mode: standalone))');
  var START = 7 * 60;       // the grid opens at 7 AM
  var NOW_AT = 0.3;         // and with a now line, that line sits this far down the grid

  function rem() { return parseFloat(getComputedStyle(document.documentElement).fontSize) || 12; }

  function showChip() {          // a trip of many days: the chips scroll inside the header, and the open day is kept in view
    var n = stage.querySelector('.cz-hchips'), c = n && n.querySelector('.is-open');
    if (c && n.scrollWidth > n.clientWidth) n.scrollLeft = c.offsetLeft - (n.clientWidth - c.offsetWidth) / 2 - n.offsetLeft;
  }

  function place() {
    if (!desk.matches) return;
    showChip();
    var scroller = stage.querySelector('.cz-view[data-day] .cz-day-body'), grid = stage.querySelector('#cz-grid');
    var zoom = grid && grid.querySelector('.cz-g-zoom');
    if (!scroller || !zoom) return;
    var lo = +grid.dataset.lo, hi = +grid.dataset.hi, mm = zoom.offsetHeight / (hi - lo);
    var line = grid.querySelector('#cz-nowline');
    var m = line ? +line.dataset.m : Math.max(lo, START);
    var top = zoom.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop + (m - lo) * mm;
    scroller.scrollTop = Math.max(0, top - (line ? scroller.clientHeight * NOW_AT : 0) - 1.25 * rem());      // a little air above the first hour
  }

  // ---- the modes ----------------------------------------------------------------------------------------------------------------
  var modes = {}, moving = 0, lastAct = '';
  function dock() { return document.getElementById('cz-dock'); }
  function blockOf(act) { return stage.querySelector('.cz-gb[data-act="' + act + '"]'); }
  function hold(p) {                       // something moves: a refresh of the day leaves the panel alone until it has landed
    var d = dock(), over = false;
    moving++;
    if (d) d.classList.add('is-moving');
    function done() {
      if (over) return;
      over = true; moving = Math.max(0, moving - 1);
      if (!moving && dock()) dock().classList.remove('is-moving');
    }
    var timer = setTimeout(done, 2000);    // (no frames come in a hidden tab)
    Promise.resolve(p).then(function () { clearTimeout(timer); done(); }, function () { clearTimeout(timer); done(); });
  }
  function setTabs(mode) {
    var d = dock(), want = (modes[mode] && modes[mode].tab) || mode;
    d.querySelectorAll('.cz-dock-tab').forEach(function (t) {
      var on = t.dataset.tab === want;
      t.classList.toggle('is-on', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
    });
  }
  function address(u) {                    // the panel's state in the address bar, in place: no history entry, nothing fetched
    if (!u || CZ.path(u) === CZ.here()) return;
    try { history.replaceState(Object.assign({}, history.state), '', u); } catch (e) { /* not allowed */ }
  }
  var Dock = window.Dock = {
    register: function (mode, impl) { modes[mode] = impl; },
    has: function (mode) { return !!modes[mode]; },
    mode: function () { var d = dock(); return d ? d.dataset.mode : ''; },
    busy: function () { return moving > 0; },
    close: function () { return Dock.show('idle'); },
    show: function (mode, opts) {
      var impl = modes[mode], d = dock();
      if (!impl || !d) return false;
      opts = opts || {};
      var from = d.dataset.mode || 'idle';
      if (from === mode && impl.same && impl.same(opts, d)) return true;
      var out = from !== mode && modes[from] && modes[from].leave ? modes[from].leave(mode, opts) : null;
      if (out) hold(out);
      d.dataset.mode = mode;
      setTabs(mode);
      address(impl.url ? impl.url(opts, d) : d.dataset.base);      // (a mode with no address of its own leaves the plan out of it)
      var inn = impl.enter ? impl.enter(opts, from) : null;
      if (inn) hold(inn);
      d.dispatchEvent(new CustomEvent('dock:mode', { bubbles: true, detail: { mode: mode, from: from, opts: opts } }));
      return true;
    }
  };

  Dock.register('idle', {
    tab: 'plan',
    same: function () { return true; },
    url: function (o, d) { return d.dataset.base; }
  });

  // ---- the plan mode ----------------------------------------------------------------------------------------------------------------
  function mk(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; }
  function svgX() {
    var s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'), p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    s.setAttribute('width', '18'); s.setAttribute('height', '18'); s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor');
    s.setAttribute('stroke-width', '2.6'); s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round'); s.setAttribute('aria-hidden', 'true');
    p.setAttribute('d', 'M18 6 6 18M6 6l12 12'); s.appendChild(p);
    return s;
  }
  function ringBlock(act) {
    stage.querySelectorAll('.cz-gb.is-ringed').forEach(function (b) { if (b.dataset.act !== act) b.classList.remove('is-ringed'); });
    var b = act && blockOf(act);
    if (b) b.classList.add('is-ringed');
  }
  function outline(block, act) {         // the pane at once, before the words come: the title and time from the block that was clicked, soft rows where the rest will be
    var d = dock(), pane = mk('section', 'cz-dock-body cz-pp is-loading');
    pane.dataset.pane = 'plan'; pane.dataset.act = act; pane.setAttribute('aria-busy', 'true'); pane.setAttribute('aria-labelledby', 'cz-pp-title'); pane.tabIndex = -1;
    var kind = /\bcz-k-\w+/.exec(block ? block.className : ''), when = block && block.querySelector('.cz-gb-when');
    var hd = mk('header', 'cz-pp-hd'), ti = mk('div', 'cz-pp-ti'), x = mk('span', 'cz-pp-x'), close = mk('button', 'cz-pp-close');
    close.type = 'button'; close.setAttribute('aria-label', 'Close the plan'); close.setAttribute('data-dock-close', ''); close.appendChild(svgX());
    x.appendChild(mk('span', 'cz-pp-kbd', 'esc')); x.appendChild(close);
    ti.appendChild(mk('div', 'cz-pp-eb', 'Plan · ' + (d.dataset.dow ? d.dataset.dow + ' ' : '') + (when ? when.textContent : '')));
    var h = mk('h2', 'cz-pp-t', (block && block.dataset.title) || 'This plan'); h.id = 'cz-pp-title'; ti.appendChild(h);
    hd.appendChild(mk('span', 'cz-pp-ic' + (kind ? ' ' + kind[0] : '')));
    hd.appendChild(ti); hd.appendChild(x);
    pane.appendChild(hd);
    for (var i = 0; i < 3; i++) pane.appendChild(mk('div', 'cz-pp-skel'));
    return pane;
  }
  function parse(html) { var t = document.createElement('template'); t.innerHTML = html; return t.content; }
  function bindNotes(pane) {             // the phone card's own in-place note editing (day_card.js), on the pane
    var area = pane.querySelector('.cz-card-notes');
    if (!area || area._czBound || !CZ.cardNotes) return;
    area._czBound = true;
    pane._o = pane._o || { act: pane.dataset.act, folding: false };
    CZ.cardNotes(pane._o, pane);
  }
  function fill(pane, html) {            // the words arrived: they replace the outline inside the same pane (the panel does not move)
    var frag = parse(html), np = frag.querySelector('.cz-pp'), nf = frag.querySelector('.cz-pp-foot'), d = dock();
    if (!np || !d || !pane.isConnected) return;
    pane.textContent = '';
    while (np.firstChild) pane.appendChild(np.firstChild);
    pane.classList.remove('is-loading'); pane.removeAttribute('aria-busy');
    if (nf) { var old = d.querySelector('.cz-pp-foot'); if (old) old.remove(); pane.after(nf); }
    bindNotes(pane);
    pane.dispatchEvent(new CustomEvent('cz:cardready', { bubbles: true }));
  }
  function failed(pane) {
    if (!pane.isConnected) return;
    pane.removeAttribute('aria-busy');
    pane.querySelectorAll('.cz-pp-skel').forEach(function (n) { n.remove(); });
    var p = mk('p', 'cz-pp-none', 'The plan could not load. '), a = mk('a', 'cz-pp-open', 'Open chat');
    a.href = '/trip/talk?act=' + encodeURIComponent(pane.dataset.act);
    p.appendChild(a); pane.appendChild(p);
  }

  Dock.register('plan', {
    tab: 'plan',
    same: function (o, d) { var p = d.querySelector('.cz-pp:not(.is-leaving)'); return !!p && p.dataset.act === o.act; },
    url: function (o, d) { return d.dataset.base + (d.dataset.base.indexOf('?') < 0 ? '?' : '&') + 'plan=' + encodeURIComponent(o.act); },
    enter: function (o, from) {
      var d = dock(), act = o.act, block = o.block || blockOf(act), old = d.querySelector('.cz-pp:not(.is-leaving)');
      lastAct = act;
      ringBlock(act);
      if (old) { old.remove(); var of = d.querySelector('.cz-pp-foot'); if (of) of.remove(); }
      var pane = outline(block, act), compose = d.querySelector('.cz-compose');
      d.insertBefore(pane, compose || null);
      var landed = !MO ? Promise.resolve() : from === 'plan' ? MO.settle(pane) : MO.open(pane, block || null, { radius: ['0.875rem', '1.75rem'] });
      var words = CZ.fetchCard ? CZ.fetchCard(act, true) : Promise.reject(new Error('no cards'));
      Promise.all([words, landed]).then(function (got) {      // (the words wait for the pane to land: nothing is squashed while it grows)
        if (dock() && pane.isConnected && !pane.classList.contains('is-leaving')) fill(pane, got[0]);
      }, function () { failed(pane); });
      try { pane.focus({ preventScroll: true }); } catch (e) { /* no focus */ }
      return landed;
    },
    leave: function (to) {
      var d = dock(), pane = d.querySelector('.cz-pp:not(.is-leaving)'), foot = d.querySelector('.cz-pp-foot');
      ringBlock('');
      if (foot) foot.remove();
      if (!pane) return null;
      var act = pane.dataset.act, block = blockOf(act), had = pane.contains(document.activeElement);
      var pr = pane.getBoundingClientRect(), dr = d.getBoundingClientRect();
      pane.classList.add('is-leaving');
      pane.style.cssText = 'position:absolute;left:' + (pr.left - dr.left) + 'px;top:' + (pr.top - dr.top) + 'px;width:' + pr.width + 'px;height:' + pr.height + 'px;z-index:3';
      if (had && block) { var f = block.querySelector('.cz-gb-open') || block; try { f.focus({ preventScroll: true }); } catch (e) { /* no focus */ } }
      var gone = function () { pane.remove(); };
      if (!MO) { gone(); return null; }
      return MO.close(pane, block || null, { radius: ['0.875rem', '1.75rem'] }).then(gone, gone);
    }
  });

  CZ.dockOpen = function (block) {       // day_card.js: a click on a plan's block, on a laptop
    if (!desk.matches || !Dock.has('plan') || !block || !block.dataset.act) return false;
    return Dock.show('plan', { act: block.dataset.act, block: block });
  };
  CZ.dockBusy = function () { return moving > 0; };

  // ---- clicks, keys and the forms in the pane --------------------------------------------------------------------------------------
  stage.addEventListener('click', function (e) {
    if (!e.target.closest) return;
    var close = e.target.closest('[data-dock-close]');
    if (close) { e.preventDefault(); Dock.close(); return; }
    var tab = e.target.closest('.cz-dock-tab');
    if (tab) {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
      var key = tab.dataset.tab;
      if (key === 'plan') {
        e.preventDefault();
        var m = Dock.mode();
        if (m !== 'idle' && m !== 'plan') Dock.show(lastAct && blockOf(lastAct) ? 'plan' : 'idle', { act: lastAct, block: blockOf(lastAct) });
      } else if (Dock.has(key)) { e.preventDefault(); Dock.show(key, {}); }      // a mode nobody registered yet keeps its link (Family: /trip/family, Ask: /trip/ask)
      return;
    }
    var add = e.target.closest('[data-add-step]');
    if (add) {
      var form = add.parentNode.querySelector('.cz-pp-addf'), open = form.hidden;
      form.hidden = !open; add.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) { var i = form.querySelector('input[name="title"]'); if (i) i.focus(); }
      return;
    }
    var aside = e.target.closest('[data-aside-toggle]');
    if (aside) {
      var tray = document.getElementById('cz-pp-aside'), shown = tray.hidden;
      tray.hidden = !shown; aside.setAttribute('aria-expanded', shown ? 'true' : 'false');
    }
  });

  document.addEventListener('keydown', function (e) {      // Esc: the panel goes back to Up next (before the canvas's own Escape, which would zoom out a level)
    if (e.key !== 'Escape' || e.defaultPrevented || !desk.matches || Dock.mode() !== 'plan' || CZ.menuOpen) return;
    var t = e.target;
    if (t.classList && t.classList.contains('cz-card-edit')) return;      // a note being written: its own Escape puts the words back
    if (t.closest && t.closest('.cz-pp-addf')) {                              // the Add a step field: Escape puts it away
      e.preventDefault(); e.stopImmediatePropagation();
      var f = t.closest('.cz-pp-addf'), b = f.parentNode.querySelector('[data-add-step]');
      f.hidden = true; b.setAttribute('aria-expanded', 'false'); b.focus();
      return;
    }
    if (t.classList && t.classList.contains('cz-pp-text') && t.value) { e.preventDefault(); e.stopImmediatePropagation(); t.blur(); return; }      // a message being written is not thrown away
    if (stage.querySelector('.cz-sheet-wrap, .cz-card-wrap')) return;
    e.preventDefault(); e.stopImmediatePropagation();
    Dock.close();
  }, true);

  document.addEventListener('submit', function (e) {      // the plan's chat: a message goes to the plan's chat and appears at the foot of the pane at once
    var f = e.target;
    if (f.matches && f.matches('form[data-cz-form]') && f.classList.contains('cz-pp-addf') && f.elements.title) {      // Add a step (canvas_writes.js sends it): the field is emptied once the day is up to date
      var field = f.elements.title, sent = field.value;
      stage.addEventListener('cz:swap', function () { if (field.isConnected && field.value === sent) field.value = ''; }, { once: true });
      return;
    }
    if (!f.matches || !f.matches('form.cz-pp-foot')) return;
    e.preventDefault();
    var input = f.elements.text, text = input.value.trim(), err = f.querySelector('.cz-error');
    if (!text || f.dataset.sent) return;
    f.dataset.sent = '1'; err.textContent = '';
    var body = new URLSearchParams(new FormData(f));
    body.set('text', text);
    fetch(f.action, { method: 'POST', body: body, credentials: 'same-origin', headers: { 'X-Fragment': '1' } }).then(function (r) {
      return r.text().then(function (t) { return { ok: r.ok, t: t, last: r.headers.get('X-Thread-Last') }; });
    }).then(function (got) {
      delete f.dataset.sent;
      if (!got.ok) { err.textContent = got.t || 'Could not send that.'; return; }
      var msgs = document.getElementById('cz-pp-msgs'), quiet = document.getElementById('cz-pp-quiet'), pane = f.previousElementSibling;
      if (msgs) {
        var nodes = parse(got.t);
        while (nodes.firstChild) msgs.appendChild(nodes.firstChild);
        if (got.last) { msgs.dataset.last = got.last; f.elements.since.value = got.last; }
      }
      if (quiet) quiet.hidden = true;
      input.value = '';
      if (pane && pane.classList.contains('cz-pp')) pane.scrollTop = pane.scrollHeight;
      input.focus();
      if (CZ.forget) CZ.forget();
      CZ.quiet();                      // the block behind shows its new chat count
    }, function () {
      delete f.dataset.sent;
      err.textContent = 'Could not send that. Check your connection.';
    });
  });

  // ---- the day ---------------------------------------------------------------------------------------------------------------------
  stage.addEventListener('cz:swap', function (e) {
    var quiet = e.detail && e.detail.quiet, d = dock(), pane = d && d.querySelector('.cz-pp:not(.is-leaving)');
    if (!quiet) { place(); lastAct = pane ? pane.dataset.act : ''; }
    if (pane) bindNotes(pane);
  });
  place();
  (function () {                // a plan in the address: the panel came with it from the server; the grid shows its block
    var d = dock(), pane = d && d.querySelector('.cz-pp');
    if (!pane) return;
    lastAct = pane.dataset.act;
    bindNotes(pane);
    var b = blockOf(lastAct);
    if (b && desk.matches) b.scrollIntoView({ block: 'center' });
  })();

  stage.addEventListener('click', function (e) {          // "Open the plan" on a plan with no steps: the same click a block makes opens it in the panel
    var a = e.target.closest ? e.target.closest('[data-dock-open]') : null;
    if (!a || !desk.matches) return;
    var block = stage.querySelector('.cz-gb[data-act="' + a.dataset.dockOpen + '"]'), open = block && block.querySelector('.cz-gb-open');
    if (!open) return;
    e.preventDefault();
    block.scrollIntoView({ block: 'center' });
    open.click();
  });
})();
