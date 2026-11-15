// Planning v2 (F-252, D-630..): the trip calendar's behaviour. The page and every redraw of the calendar are the server's (gitaway/pages/planv2.py draws it, gitaway/planv2.py knows it); this
// script only reads where a finger or the pointer is and says what happened: a tap on empty time opens quick add, a tap on a plan opens its editor, a drag moves it, the bottom edge
// resizes it, the rail's "+" drops a suggestion into a free slot. Every change is one POST /trip/plan/write (or /suggest) that answers the calendar again, so what is drawn is
// always what is stored; a refusal arrives in the calendar's own words as a toast. Every gesture has a visible way: the editor's time stepper and duration chips move and resize a plan
// with taps, the Add button adds without a tap on the grid, "Show me" opens a day, and Undo is in the toast. Touch drags start with a half-second hold (a vertical swipe scrolls the day).
// Motion: only CSS (the --v2-* tokens); nothing here is a time but the hold and the polling interval of the open chat.
(function () {
  var root = document.querySelector('[data-pl]');
  var raw = document.getElementById('pl-data');
  if (!root || !raw) return;
  var D = JSON.parse(raw.textContent);
  var cal = document.getElementById('pl-cal');
  var pop = document.getElementById('pl-pop');
  var scrim = document.getElementById('pl-scrim');
  var side = document.getElementById('pl-side');
  var sheet = document.getElementById('pl-sheet');
  var RM = window.matchMedia('(prefers-reduced-motion: reduce)');
  var HOLD = 450, POLL = 8000, SLOP = 5;
  var state = { view: 'week', frm: 0, cols: 7, day: D.open || 0 };
  var KIND = {}; D.kinds.forEach(function (k) { KIND[k[0]] = k[1]; });
  var drag = null, hold = 0, poller = 0, key = 'trip', saved = null;

  function phone() { return window.innerWidth < 720; }
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function icon(name) { var t = document.getElementById('pl-ico-' + name); return t ? t.innerHTML : ''; }
  function time(m) { var h = Math.floor(m / 60), mm = m % 60; return (h % 12 || 12) + ':' + (mm < 10 ? '0' : '') + mm + ' ' + (h < 12 ? 'AM' : 'PM'); }
  function dur(m) { var h = Math.floor(m / 60), mm = m % 60; return h ? (mm ? h + 'h ' + mm + 'm' : h + 'h') : mm + ' min'; }
  function toast(text, opts) { if (window.GA && GA.toast && text) GA.toast(text, opts || {}); }
  function dayOf(i) { return D.days[i] || D.days[0]; }

  // ---- the calendar: always the server's drawing ----
  function qs(extra) {
    var o = { view: state.view, frm: state.frm, cols: state.cols, day: state.day };
    for (var k in extra) o[k] = extra[k];
    return Object.keys(o).map(function (k) { return k + '=' + encodeURIComponent(o[k]); }).join('&');
  }
  function wantCols() { return phone() ? 5 : 7; }
  function render(html) {
    var body = $('.g-body', cal), top = body ? body.scrollTop : 0;
    cal.innerHTML = html;
    var g = $('.grid', cal);
    if (g) {
      var s = g.dataset.state.split('|');
      state = { view: s[0], frm: +s[1], cols: +s[2], day: +s[3] };
      cal.dataset.view = state.view;
    }
    body = $('.g-body', cal);
    if (body) body.scrollTop = top;
    var sum = $('.pl-sum', cal);
    if (sum) { try { saved = JSON.parse(sum.textContent); D.inPlan = saved.titles; } catch (e) { saved = null; } }
    marks();
  }
  function marks() {      // the rail's "+" shows done for what is already in the plan
    $$('#pl-rail [data-sug]').forEach(function (b) {
      var s = D.sugg.filter(function (x) { return x.id === b.dataset.sug; })[0];
      var on = s && D.inPlan.indexOf(s.title) >= 0;
      b.classList.toggle('done', !!on);
      b.innerHTML = on ? icon('check') : icon('plus');
    });
  }
  function refresh() {
    return fetch('/trip/plan/cal?' + qs({}), { credentials: 'same-origin', headers: { 'X-Requested-With': 'plan' } }).then(function (r) { if (!r.ok) throw new Error('cal'); return r.text(); }).then(render);
  }
  function go(change) { for (var k in change) state[k] = change[k]; closePop(); return refresh(); }
  function post(path, data) {
    var body = new URLSearchParams(); for (var k in data) body.set(k, data[k]);
    body.set('view', state.view); body.set('frm', state.frm); body.set('cols', state.cols); body.set('vday', state.day);      // what the calendar shows, so the answer redraws it (a plan's own day is the body's `day`)
    return fetch(path, { method: 'POST', body: body, credentials: 'same-origin' }).then(function (r) {
      return r.json().catch(function () { return { error: 'That did not work.' }; }).then(function (j) { j.ok = r.ok; return j; });
    });
  }
  function done(res, opts) {      // an answer: draw it, say it, offer the undo
    if (!res.ok) { toast(res.error || 'That did not work.', { error: true }); return refresh().then(function () { return res; }); }
    render(res.grid);
    if (res.toast) toast(res.toast, res.undo ? { undo: function () { post('/trip/plan/write', { op: 'undo', undo: JSON.stringify(res.undo) }).then(function (r) { done(r); }); } } : {});
    if (res.plan) land(res.plan);
    return Promise.resolve(res);
  }
  function land(p) {      // bring the plan's day into view and let it settle in
    var inView = state.view === 'day' ? state.day === p.day : (p.day >= state.frm && p.day < state.frm + state.cols);
    var again = inView ? Promise.resolve() : go(state.view === 'day' ? { day: p.day } : { frm: Math.max(0, Math.min(p.day, D.days.length - state.cols)) });
    again.then(function () {
      var n = $('.ev[data-id="' + p.act + '"]', cal);
      if (!n) return;
      n.classList.add('land');
      var body = $('.g-body', cal), y = (p.start - gs()) / 60 * hh();
      if (body && (y < body.scrollTop || y > body.scrollTop + body.clientHeight - hh())) body.scrollTop = Math.max(0, y - hh());
    });
  }

  // ---- popovers (a card under the tap; a sheet from the bottom on a phone) ----
  function closePop() {
    pop.hidden = true; pop.innerHTML = ''; scrim.classList.remove('on'); root.classList.remove('pop-open'); pop.classList.remove('as-sheet');
    $$('.ev.sel', cal).forEach(function (n) { n.classList.remove('sel'); });
  }
  function place(anchor, x, y) {
    scrim.classList.add('on'); root.classList.add('pop-open');
    pop.hidden = false;
    if (phone()) { pop.classList.add('as-sheet'); pop.style.left = ''; pop.style.top = ''; return; }
    var w = pop.offsetWidth, h = pop.offsetHeight, r = anchor ? anchor.getBoundingClientRect() : { left: x, right: x, top: y, bottom: y };
    var left = r.right + 12; if (left + w > window.innerWidth - 12) left = r.left - w - 12; if (left < 12) left = Math.max(12, Math.min(window.innerWidth - w - 12, (x || r.left)));
    var top = Math.max(12, Math.min(window.innerHeight - h - 12, (y || r.top) - 40));
    pop.style.left = left + 'px'; pop.style.top = top + 'px';
  }
  function head(kicker, title, onx) {
    var ph = el('div', 'ph'), t = el('div', 't'), h = el('h4', null, kicker), b = el('b', null, title);
    t.appendChild(h); t.appendChild(b); ph.appendChild(t);
    var x = el('button', 'x'); x.type = 'button'; x.setAttribute('aria-label', 'Close'); x.innerHTML = icon('x'); x.addEventListener('click', onx || closePop); ph.appendChild(x);
    return { box: ph, title: b };
  }
  function stepper(get, set, lo, hi) {
    var box = el('div', 'timeline'), st = el('div', 'step'), minus = el('button'), out = el('output'), plus = el('button');
    minus.type = plus.type = 'button'; minus.setAttribute('aria-label', 'Earlier'); plus.setAttribute('aria-label', 'Later');
    minus.innerHTML = icon('minus'); plus.innerHTML = icon('plus');
    function paint() { out.textContent = time(get()); minus.disabled = get() - D.step < lo(); plus.disabled = get() + D.step > hi(); }
    minus.addEventListener('click', function () { set(get() - D.step); paint(); });
    plus.addEventListener('click', function () { set(get() + D.step); paint(); });
    st.appendChild(minus); st.appendChild(out); st.appendChild(plus); box.appendChild(st); paint();
    return { box: box, paint: paint };
  }
  function chips(items, current, onpick, kind) {
    var box = el('div', 'chips'), btns = [];
    items.forEach(function (it) {
      var b = el('button', 'chip' + (kind ? ' kind k-' + it[0] : '')); b.type = 'button';
      if (kind) { var i = el('i'); b.appendChild(i); b.appendChild(document.createTextNode(it[1])); } else b.textContent = it[1];
      b.setAttribute('aria-pressed', String(it[0] === current));
      b.addEventListener('click', function () { btns.forEach(function (x, n) { x.setAttribute('aria-pressed', String(items[n][0] === it[0])); }); onpick(it[0]); });
      btns.push(b); box.appendChild(b);
    });
    return { box: box, set: function (v) { btns.forEach(function (x, n) { x.setAttribute('aria-pressed', String(items[n][0] === v)); }); } };
  }
  function label(text) { return el('div', 'lab', text); }
  var DURS = function () { return D.durs.map(function (m) { return [m, dur(m)]; }); };
  var KINDS = function () { return D.kinds.map(function (k) { return [k[0], k[1]]; }); };

  function plan(opts) {      // one editor for adding and for changing: a name, a time, how long, what kind
    var add = !opts.id, w = dayOf(opts.day), lo = w.lo, hi = w.hi;
    var s = { title: opts.title || '', start: opts.start, len: opts.len, kind: opts.kind || 'fun', sug: '' };
    function clampStart() { s.start = Math.max(lo, Math.min(hi - s.len, Math.round(s.start / D.step) * D.step)); }
    clampStart();
    pop.innerHTML = '';
    var h = head(add ? 'Add to ' + w.label : 'Change on ' + w.label, add ? 'New plan' : s.title);
    pop.appendChild(h.box);
    var name = el('label', 'namefield'), input = el('input'); input.type = 'text'; input.placeholder = add ? 'Name it' : 'Name'; input.value = s.title; input.maxLength = 40; input.setAttribute('aria-label', 'Name');
    name.appendChild(input); pop.appendChild(name);
    function btnText() { return add ? 'Add at ' + time(s.start) + ', ' + dur(s.len) : 'Save ' + time(s.start) + ', ' + dur(s.len); }
    var go1 = el('button', 'go1'); go1.type = 'button';
    function paint() { go1.innerHTML = icon(add ? 'plus' : 'check'); go1.appendChild(document.createTextNode(btnText())); }
    input.addEventListener('input', function () { s.title = input.value; });
    var sugList = null;
    if (add && D.sugg.length) {
      var lb = label('Suggestions'); lb.appendChild(el('span', 'smp', 'Sample')); pop.appendChild(lb);
      sugList = el('div', 'sugs');
      sugList.setAttribute('role', 'radiogroup');
      D.sugg.slice(0, 4).forEach(function (x) {
        var b = el('button', 'sug k-' + x.kind), r = el('span', 'rad'), t = el('span', 't'), n = el('b', null, x.title), sub = el('small', null, x.sub);
        b.type = 'button'; b.setAttribute('role', 'radio'); b.setAttribute('aria-checked', 'false'); t.appendChild(n); t.appendChild(sub); b.appendChild(r); b.appendChild(t);
        b.addEventListener('click', function () {
          $$('.sug', sugList).forEach(function (o) { o.setAttribute('aria-checked', 'false'); }); b.setAttribute('aria-checked', 'true');
          s.title = x.title; input.value = x.title; s.kind = x.kind; s.len = x.minutes; kinds.set(x.kind); lens.set(x.minutes); clampStart(); st.paint(); paint();
        });
        sugList.appendChild(b);
      });
      pop.appendChild(sugList);
    }
    pop.appendChild(label('Starts'));
    var st = stepper(function () { return s.start; }, function (v) { s.start = v; clampStart(); st.paint(); paint(); }, function () { return lo; }, function () { return hi - s.len; });
    pop.appendChild(st.box);
    pop.appendChild(label('How long'));
    var lens = chips(DURS(), s.len, function (v) { s.len = v; clampStart(); st.paint(); paint(); });
    pop.appendChild(lens.box);
    pop.appendChild(label('Kind'));
    var kinds = chips(KINDS(), s.kind, function (v) { s.kind = v; }, true);
    pop.appendChild(kinds.box);
    paint(); pop.appendChild(go1);
    go1.addEventListener('click', function () {
      var t = input.value.trim();
      if (!t) { input.focus(); input.setAttribute('aria-invalid', 'true'); return; }
      go1.disabled = true;
      var body = { day: opts.day, start: s.start, end: s.start + s.len, title: t, kind: s.kind };
      if (add) body.op = 'add'; else { body.op = 'edit'; body.act = opts.id; }
      post('/trip/plan/write', body).then(function (res) { closePop(); done(res); });
    });
    if (!add) {
      var row = el('div', 'row2'), del = el('button', 'btn2 danger', 'Delete'), talk = el('button', 'btn2', 'Talk about this');
      del.type = talk.type = 'button';
      del.addEventListener('click', function () { post('/trip/plan/write', { op: 'delete', act: opts.id }).then(function (res) { closePop(); done(res); }); });
      talk.addEventListener('click', function () { closePop(); openSide(opts.id); });
      row.appendChild(del); row.appendChild(talk); pop.appendChild(row);
    }
    return input;
  }
  function viewer(n) {      // a viewer reads: what it is, when, and a way to talk about it
    var w = dayOf(+n.dataset.day);
    pop.innerHTML = '';
    pop.appendChild(head(w.label, n.dataset.title).box);
    pop.appendChild(el('p', null, time(+n.dataset.start) + ' to ' + time(+n.dataset.end)));
    var talk = el('button', 'btn2', 'Talk about this'); talk.type = 'button';
    talk.addEventListener('click', function () { closePop(); openSide(n.dataset.id); });
    pop.appendChild(talk);
  }
  function openAdd(day, start, anchor, x, y) {
    if (!D.edit) return;
    var w = dayOf(day);
    start = Math.max(w.lo, Math.min(w.hi - 60, Math.round(start / D.step) * D.step));
    var input = plan({ day: day, start: start, len: 60 });
    place(anchor, x, y); input.focus({ preventScroll: true });
  }
  function openEdit(n) {
    closePop(); n.classList.add('sel');
    if (!D.edit) { viewer(n); place(n); return; }
    var input = plan({ id: n.dataset.id, day: +n.closest('.col').dataset.day, start: +n.dataset.start, len: +n.dataset.end - +n.dataset.start, title: n.dataset.title, kind: n.dataset.kind });
    place(n); input.focus({ preventScroll: true });
  }
  function openMore(btn) {
    closePop();
    var col = btn.closest('.col'), day = +col.dataset.day, ids = btn.dataset.more.split(',');
    pop.innerHTML = '';
    pop.appendChild(head(dayOf(day).label, ids.length + ' more at the same time').box);
    var ul = el('ul', 'evlist');
    fetch('/trip/plan/cal?' + qs({ view: 'day', day: day }), { credentials: 'same-origin' }).then(function (r) { return r.text(); }).then(function (html) {
      var tmp = el('div'); tmp.innerHTML = html;
      $$('.ev', tmp).filter(function (n) { return ids.indexOf(n.dataset.id) >= 0; }).forEach(function (n) {
        var li = el('li'), item = n.tagName === 'A' ? el('a') : el('button'), tm = $('.tm', n);
        item.className = 'k-' + (n.className.match(/k-(\w+)/) || [0, 'fun'])[1];
        if (n.tagName === 'A') item.href = n.getAttribute('href'); else item.type = 'button';
        item.appendChild(el('span', null, $('b', n).textContent)); item.appendChild(el('span', 'tm', tm ? tm.textContent : ''));
        if (n.tagName !== 'A') item.addEventListener('click', function () { closePop(); fromData(n.dataset, day); });
        li.appendChild(item); ul.appendChild(li);
      });
    });
    pop.appendChild(ul); place(btn);
  }
  function fromData(d, day) {      // a plan listed in "+N" opens its editor
    if (!D.edit) return;
    var input = plan({ id: d.id, day: day, start: +d.start, len: +d.end - +d.start, title: d.title, kind: d.kind });
    place(null, window.innerWidth / 2 - 200, 120); input.focus({ preventScroll: true });
  }

  // ---- gestures on the grid ----
  function hh() { var g = $('.g-inner', cal); return g.offsetHeight / (parseFloat(g.style.getPropertyValue('--hours')) || 1); }
  function gs() { return +$('.g-inner', cal).dataset.gs; }
  function snap(m) { return Math.round(m / D.step) * D.step; }
  function colAt(x) { var found = null; $$('.col', cal).forEach(function (c) { var r = c.getBoundingClientRect(); if (x >= r.left && x < r.right) found = c; }); return found; }
  function minuteAt(c, y) { var r = c.getBoundingClientRect(); return gs() + (y - r.top) / hh() * 60; }
  function tip(c, text, y) {
    var t = $('.tip', cal) || el('div', 'tip'); t.textContent = text; c.appendChild(t); t.style.left = '50%'; t.style.top = y + 'px';
  }

  cal.addEventListener('pointerdown', function (e) {
    var n = e.target.closest('.ev'), rz = e.target.closest('.rz');
    if (!D.edit || !n || n.hasAttribute('data-locked') || e.button) return;
    if (e.target.closest('.more')) return;
    var c = n.closest('.col'), r = n.getBoundingClientRect();
    drag = { n: n, mode: rz ? 'resize' : 'move', x0: e.clientX, y0: e.clientY, id: n.dataset.id, start: +n.dataset.start, end: +n.dataset.end, day: +c.dataset.day, col: c, left0: r.left, moved: false,
             armed: e.pointerType === 'mouse', pid: e.pointerId, ns: 0, nd: +c.dataset.day, ne: +n.dataset.end, type: e.pointerType };
    if (!drag.armed) hold = setTimeout(function () { if (drag) { drag.armed = true; n.classList.add('armed'); if (navigator.vibrate) navigator.vibrate(8); } }, HOLD);
  });
  window.addEventListener('pointermove', function (e) {
    if (!drag || e.pointerId !== drag.pid) return;
    var dx = e.clientX - drag.x0, dy = e.clientY - drag.y0, d = drag;
    if (!d.armed) { if (Math.abs(dx) > 8 || Math.abs(dy) > 8) { clearTimeout(hold); drag = null; } return; }      // a touch that moved before the hold is a scroll
    if (!d.moved && Math.abs(dx) < SLOP && Math.abs(dy) < SLOP) return;
    if (!d.moved) { d.moved = true; d.n.classList.add('dragging'); try { d.n.setPointerCapture(e.pointerId); } catch (x) { /* no capture: the window still hears it */ } }
    var perMin = hh() / 60;
    if (d.mode === 'resize') {
      var lenMin = Math.max(D.step, snap(d.end - d.start + dy / perMin)), win = dayOf(d.day);
      lenMin = Math.min(lenMin, win.hi - d.start); d.ne = d.start + lenMin;
      d.n.style.height = Math.max(lenMin * perMin, 28) + 'px';
      tip(d.col, time(d.start) + ' to ' + time(d.ne), (d.start - gs()) * perMin + lenMin * perMin);
      return;
    }
    var shift = snap(dy / perMin), c = state.view === 'week' ? colAt(e.clientX) : d.col;
    d.nd = c ? +c.dataset.day : d.day;
    var w = dayOf(d.nd), len = d.end - d.start;
    d.ns = Math.max(w.lo, Math.min(w.hi - len, d.start + shift));
    d.n.style.transform = 'translate(' + ((c ? c.getBoundingClientRect().left - d.col.getBoundingClientRect().left : 0)) + 'px,' + ((d.ns - d.start) * perMin) + 'px) scale(1.03)';
    tip(c || d.col, time(d.ns) + ' to ' + time(d.ns + len), (d.ns - gs()) * perMin);
  });
  function finish(e) {
    if (!drag || (e && e.pointerId !== drag.pid)) return;
    clearTimeout(hold);
    var d = drag; drag = null;
    d.n.classList.remove('dragging', 'armed'); d.n.style.transform = ''; var t = $('.tip', cal); if (t) t.remove();
    if (!d.moved) return;
    d.n.dataset.dragged = '1'; setTimeout(function () { delete d.n.dataset.dragged; }, 0);
    var body = { op: 'edit', act: d.id };
    if (d.mode === 'resize') { if (d.ne === d.end) { d.n.style.height = ''; return; } body.end = d.ne; }
    else { if (d.ns === d.start && d.nd === d.day) return; body.start = d.ns; body.end = d.ns + (d.end - d.start); if (d.nd !== d.day) body.day = d.nd; }
    post('/trip/plan/write', body).then(function (res) { done(res); });
  }
  window.addEventListener('pointerup', finish);
  window.addEventListener('pointercancel', function (e) { if (drag && e.pointerId === drag.pid) { clearTimeout(hold); drag.n.classList.remove('dragging', 'armed'); drag.n.style.transform = ''; var t = $('.tip', cal); if (t) t.remove(); drag = null; } });
  window.addEventListener('touchmove', function (e) { if (drag && drag.armed && drag.type !== 'mouse') e.preventDefault(); }, { passive: false });

  cal.addEventListener('click', function (e) {
    var t = e.target;
    var v = t.closest('[data-view]'); if (v && cal.contains(v) && v.tagName === 'BUTTON') { go({ view: v.dataset.view, cols: wantCols() }); return; }
    var nav = t.closest('[data-nav]');
    if (nav) { var dir = +nav.dataset.nav; if (state.view === 'day') go({ day: state.day + dir }); else go({ frm: state.frm + dir * Math.max(1, state.cols - 1) }); return; }
    var dh = t.closest('.dh'); if (dh && state.view === 'week') { go({ view: 'day', day: +dh.dataset.day }); return; }
    var chip = t.closest('.dchip'); if (chip) { go({ day: +chip.dataset.day }); return; }
    if (t.closest('[data-add]')) { var d = state.view === 'day' ? state.day : Math.min(Math.max(state.frm, D.open), state.frm + state.cols - 1); openAdd(d, 10 * 60, t.closest('[data-add]')); return; }
    var more = t.closest('.more'); if (more) { openMore(more); return; }
    var ev = t.closest('.ev'); if (ev) { if (ev.hasAttribute('data-locked') || ev.dataset.dragged) return; openEdit(ev); return; }
    var col = t.closest('.col');
    if (col) { openAdd(+col.dataset.day, minuteAt(col, e.clientY), null, e.clientX, e.clientY); }
  });
  cal.addEventListener('keydown', function (e) {
    var ev = e.target.closest && e.target.closest('.ev[role="button"]');
    if (ev && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openEdit(ev); }
  });
  cal.addEventListener('pointermove', function (e) {      // a soft hint of the half hour a tap would add (a mouse only)
    if (e.pointerType !== 'mouse' || !D.edit || drag) return;
    var c = e.target.closest && e.target.closest('.col'), h = $('.hov', cal);
    if (!c || e.target.closest('.ev, .more')) { if (h) h.classList.remove('on'); return; }
    if (!h) { h = el('div', 'hov'); }
    c.appendChild(h); h.style.top = (snap(minuteAt(c, e.clientY) - D.step / 2) - gs()) / 60 * hh() + 'px'; h.classList.add('on');
  });
  scrim.addEventListener('click', function () { closePop(); if (!side.hidden) closeSide(); closeSheet(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { if (!pop.hidden) closePop(); else if (!side.hidden) closeSide(); else if (!sheet.hidden) closeSheet(); } });
  document.addEventListener('pointerdown', function (e) { if (!pop.hidden && !pop.contains(e.target) && !e.target.closest('.ev, .col, .addbtn, .more')) closePop(); });

  // ---- the rail ----
  var rail = document.getElementById('pl-rail');
  if (rail) rail.addEventListener('click', function (e) {
    var b = e.target.closest('[data-sug]');
    if (b && D.edit) {
      if (b.classList.contains('done')) return;
      b.disabled = true;
      post('/trip/plan/suggest', { id: b.dataset.sug }).then(function (res) { b.disabled = false; return done(res); });
      return;
    }
    var day = e.target.closest('[data-day], [data-show]');
    if (day) go({ view: 'day', day: +(day.dataset.day || day.dataset.show), cols: wantCols() }).then(function () { cal.scrollIntoView({ block: 'start', behavior: RM.matches ? 'auto' : 'smooth' }); });      // on a phone the rail is under the calendar: bring the day up
  });

  // ---- planning together ----
  function openSide(k) {
    closePop(); side.hidden = false; side.classList.add('in'); root.classList.add('side-open');
    if (phone()) scrim.classList.add('on');
    fetch('/trip/plan/together', { credentials: 'same-origin' }).then(function (r) { return r.text(); }).then(function (h) { var top = document.getElementById('pl-top'); if (top) top.innerHTML = h; });
    loadThread(k || key); clearInterval(poller); poller = setInterval(function () { if (!document.hidden) loadThread(key); }, POLL);
    var f = $('#pl-say'); if (f && !phone()) f.focus({ preventScroll: true });
  }
  function closeSide() { side.hidden = true; side.classList.remove('in'); root.classList.remove('side-open'); scrim.classList.remove('on'); clearInterval(poller); }
  function loadThread(k) {
    key = k || 'trip';
    return fetch('/trip/plan/thread?key=' + encodeURIComponent(key), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (j) {
      var tb = document.getElementById('pl-threads'); tb.innerHTML = '';
      j.threads.forEach(function (t) {
        var b = el('button', 'chip'); b.type = 'button'; b.appendChild(document.createTextNode(t.title));
        var n = t.unread || 0; if (n) b.appendChild(el('span', 'cnt', ' ' + n));
        b.setAttribute('aria-pressed', String(t.key === key)); b.addEventListener('click', function () { loadThread(t.key); }); tb.appendChild(b);
      });
      var bx = document.getElementById('pl-bubbles'), atEnd = bx.scrollTop + bx.clientHeight >= bx.scrollHeight - 8; bx.innerHTML = '';
      if (!j.items.length) bx.appendChild(el('p', 'none', 'Nothing said here yet.'));
      j.items.forEach(function (i) {
        var b = el('div', 'bub ' + (i.mine ? 'me' : 'them')); if (!i.mine && i.name) b.appendChild(el('span', 'nm', i.name)); b.appendChild(document.createTextNode(i.text)); bx.appendChild(b);
      });
      if (atEnd || !bx.dataset.seen) bx.scrollTop = bx.scrollHeight; bx.dataset.seen = '1';
      badge(0);
    });
  }
  function badge(n) { var b = document.getElementById('pl-badge'); if (!b) return; b.textContent = n; b.hidden = !n; }
  function send() {
    var f = $('#pl-say'), text = f.value.trim(); if (!text) return;
    var parts = key.split(':'), body = new URLSearchParams(), url = '/trip/family/message';
    body.set('text', text);
    if (key !== 'trip') { url = '/trip/talk/message'; body.set('act', parts[0]); if (parts[1]) body.set('part', parts[1]); }
    f.value = '';
    fetch(url, { method: 'POST', body: body, credentials: 'same-origin', headers: { 'X-Fragment': '1' } }).then(function (r) { if (!r.ok) throw new Error(); return loadThread(key); }).catch(function () { toast('That did not send.', { error: true }); f.value = text; });
  }
  $('#pl-send').addEventListener('click', send);
  $('#pl-say').addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); send(); } });
  $$('#pl-together, [data-together]').forEach(function (b) { b.addEventListener('click', function () { openSide('trip'); }); });
  $$('[data-close]', side).forEach(function (b) { b.addEventListener('click', closeSide); });
  side.addEventListener('click', function (e) {
    var c = e.target.closest('[data-copy]');
    if (c) { (navigator.clipboard ? navigator.clipboard.writeText(c.dataset.copy) : Promise.reject()).then(function () { c.textContent = 'Copied'; }, function () { c.textContent = 'Copy it from the address'; }); }
  });

  // ---- save: the plan is already stored; this reads it back and shows what is there ----
  function closeSheet() { sheet.hidden = true; sheet.classList.remove('in'); root.classList.remove('sheet-open'); if (side.hidden) scrim.classList.remove('on'); }
  function saveNow(btn) {
    btn.classList.add('busy'); var s0 = btn.innerHTML; btn.innerHTML = '<span class="v2-spin"></span>';
    refresh().then(function () { openSheet(); }, function () { toast('Could not reach the trip to check it.', { error: true }); }).then(function () { btn.classList.remove('busy'); btn.innerHTML = s0; });
  }
  function openSheet() {
    var sum = saved || { plans: [], booked: D.summary.booked, titles: [], days: D.days.length, people: D.summary.people };
    sheet.innerHTML = '';
    var body = el('div', 'sh-body'), h = el('div', 'done-h'); h.appendChild(el('b', null, 'Plan saved')); h.appendChild(el('p', null, 'Every change is stored in your family’s trip as you make it.'));
    var pass = el('div', 'pass'), k = el('div'), st = el('div', 'stamp thump'); st.appendChild(document.createTextNode('Saved'));
    k.appendChild(el('small', null, D.summary.dates)); k.appendChild(el('h3', 'disp', D.summary.title)); pass.appendChild(k);
    var cols = el('div', 'cols');
    [['Days', sum.days], ['Plans', sum.plans.length], ['Booked', sum.booked]].forEach(function (c) { var d = el('div'); d.appendChild(el('small', null, c[0])); d.appendChild(el('b', 'num', String(c[1]))); cols.appendChild(d); });
    pass.appendChild(cols);
    var strip = el('div', 'wkstrip');
    D.days.forEach(function (d) {
      var c = el('div'); c.appendChild(el('span', null, d.label.split(',')[0]));
      sum.plans.filter(function (p) { return p.day === d.i; }).forEach(function (p) { var i = el('i'); i.className = 'k-' + p.kind; c.appendChild(i); });
      strip.appendChild(c);
    });
    pass.appendChild(strip); pass.appendChild(st); body.appendChild(h); body.appendChild(pass); sheet.appendChild(body);
    var foot = el('div', 'sh-foot'), back = el('button', 'btn2', 'Back to planning'), share = $('#sh-open');
    back.type = 'button'; back.addEventListener('click', closeSheet); foot.appendChild(back); foot.appendChild(el('span', 'sp'));
    if (share) { var s = el('button', 'btn1 sun'); s.type = 'button'; s.innerHTML = icon('share'); s.appendChild(document.createTextNode('Share the trip')); s.addEventListener('click', function () { closeSheet(); share.click(); }); foot.appendChild(s); }
    sheet.appendChild(foot);
    if (window.GA && GA.hideToast) GA.hideToast(true);
    sheet.hidden = false; sheet.classList.add('in'); root.classList.add('sheet-open'); scrim.classList.add('on'); back.focus({ preventScroll: true });
  }
  $$('#pl-save, [data-save]').forEach(function (b) { b.addEventListener('click', function () { saveNow(b); }); });

  // ---- coming back to the tab: read the trip again (no live channel: a change someone else made shows on return) ----
  function again() { if (document.hidden || drag || !pop.hidden) return; refresh().catch(function () { /* offline: what is drawn stays */ }); if (!side.hidden) loadThread(key); }
  document.addEventListener('visibilitychange', again);
  window.addEventListener('focus', again);
  if (wantCols() !== state.cols) go({ cols: wantCols(), view: state.view });
  marks();
})();
