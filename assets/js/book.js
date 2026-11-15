// The book (F-253, docs/design/creators-v2): the pages the server drew (#pgs) become leaves you turn in CSS 3D (a fade under reduced motion), by arrows, keys or a swipe. A creator's own book can
// fix a word in place and publish; a reader's can be saved and planned from. Every time here is a --cv-d* token of v2-tokens.css read with getComputedStyle: no script writes one.
(function () {
  'use strict';
  var root = document.getElementById('bookv');
  if (!root) return;
  var cv = root.closest('.cv') || document.body;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var RM = matchMedia('(prefers-reduced-motion: reduce)');
  var PHONE = matchMedia('(max-width: 719px)');
  var cs = getComputedStyle(document.documentElement);
  function tok(n) { var v = cs.getPropertyValue(n).trim(); return v.slice(-2) === 'ms' ? parseFloat(v) : parseFloat(v) * 1000; }
  function wait(token) { return new Promise(function (r) { setTimeout(r, RM.matches ? 0 : tok(token)); }); }
  var creator = root.dataset.mode === 'creator';
  var postUrl = location.pathname.replace(/\/book$/, '');
  var S = { spread: 0, faces: [], editing: false, live: root.dataset.live === '1' };
  var book = $('#book'), wrap = $('#bookWrap'), stage = $('#stage3d');
  var ICON = { x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
               check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12l5 5 9-10"/></svg>',
               share: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>',
               copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="3"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>',
               arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>' };
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function toast(msg) { var t = $('#toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(toast.t); toast.t = setTimeout(function () { t.classList.remove('on'); }, 3200); }

  // ---- the pages: moved (never copied, so no id is ever twice) out of #pgs into leaves ----
  $$('#pgs .pf').forEach(function (sec) { S.faces.push({ lbl: sec.dataset.lbl, nodes: Array.prototype.slice.call(sec.childNodes) }); });
  function face(f, cls) { var d = el('div', 'face ' + cls); f.nodes.forEach(function (n) { d.appendChild(n); }); return d; }
  function maxSpread() { return PHONE.matches ? S.faces.length - 1 : S.faces.length / 2; }
  function bookSize() {
    var vw = innerWidth, vh = innerHeight, pw, ph;
    if (PHONE.matches) { pw = Math.min(vw - 28, 420); ph = Math.min(vh - 226, Math.round(pw * 1.72)); }
    else { ph = Math.min(vh - 250, 720); pw = Math.round(ph * 0.72); var max = (vw - 120) / 2; if (pw > max) { pw = Math.round(max); ph = Math.round(pw / 0.72); } }
    wrap.style.setProperty('--pw', pw + 'px'); wrap.style.setProperty('--ph', ph + 'px');
  }
  function drawBook() {
    bookSize(); book.textContent = '';
    var F = S.faces, n;
    if (PHONE.matches) {
      F.forEach(function (f, i) { var lf = el('div', 'leaf'); lf.dataset.i = i; lf.appendChild(face(f, 'front')); book.appendChild(lf); });
    } else {
      n = F.length / 2;
      for (var i = 0; i < n; i++) { var lf = el('div', 'leaf'); lf.dataset.i = i; lf.appendChild(face(F[i * 2], 'front')); lf.appendChild(face(F[i * 2 + 1], 'back')); book.appendChild(lf); }
    }
    layout(true);
  }
  function layout(instant) {
    var leaves = $$('.leaf', book), n = leaves.length, s = S.spread;
    leaves.forEach(function (lf, i) {
      if (instant) lf.style.transition = 'none';
      lf.classList.toggle('turned', i < s);
      lf.style.zIndex = i < s ? i + 1 : n - i;
      if (instant) { void lf.offsetWidth; lf.style.transition = ''; }
    });
    var M = maxSpread();
    wrap.classList.toggle('at-start', s === 0); wrap.classList.toggle('at-end', s === M);
    var shift = '0px';
    if (!PHONE.matches) { if (s === 0) shift = 'calc(var(--pw) * -.5)'; else if (s === M) shift = 'calc(var(--pw) * .5)'; }
    if (instant) wrap.style.transition = 'none';
    wrap.style.setProperty('--shift', shift);
    if (instant) { void wrap.offsetWidth; wrap.style.transition = ''; }
    pager();
  }
  function pager() {
    var s = S.spread, M = maxSpread(), F = S.faces, lbl, sub;
    if (PHONE.matches) { lbl = F[s].lbl; sub = (s + 1) + ' of ' + F.length; }
    else { lbl = s === 0 ? 'Cover' : s === M ? 'Back cover' : (F[s * 2 - 1].lbl === F[s * 2].lbl ? F[s * 2].lbl : F[s * 2 - 1].lbl); sub = (s + 1) + ' of ' + (M + 1); }
    $('#pageLbl').innerHTML = esc(lbl) + '<small>' + sub + '</small>';
    $('#prev').disabled = s === 0; $('#next').disabled = s === M;
  }
  function flipTo(s) {
    var M = maxSpread(); s = Math.max(0, Math.min(M, s)); if (s === S.spread) return;
    var leaves = $$('.leaf', book), dir = s > S.spread ? 1 : -1;
    var moving = dir > 0 ? leaves.slice(S.spread, s) : leaves.slice(s, S.spread);
    if (document.activeElement && document.activeElement.isContentEditable) document.activeElement.blur();
    S.spread = s;
    if (RM.matches) { wrap.classList.remove('fade'); void wrap.offsetWidth; wrap.classList.add('fade'); layout(true); return; }
    moving.forEach(function (lf) { lf.style.zIndex = 200; lf.classList.add('turning'); setTimeout(function () { lf.classList.remove('turning'); }, tok('--cv-d1000')); });
    layout(false);
    moving.forEach(function (lf) { lf.style.zIndex = 200; });
    setTimeout(function () { if (!PHONE.matches) layout(false); }, tok('--cv-d500'));
  }
  $('#prev').addEventListener('click', function () { flipTo(S.spread - 1); });
  $('#next').addEventListener('click', function () { flipTo(S.spread + 1); });
  addEventListener('keydown', function (e) {
    if (!$('#sheet').hidden || (document.activeElement && (document.activeElement.isContentEditable || /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)))) return;
    if (e.key === 'ArrowRight') { flipTo(S.spread + 1); e.preventDefault(); }
    if (e.key === 'ArrowLeft') { flipTo(S.spread - 1); e.preventDefault(); }
    if (e.key === 'Escape' && S.editing) setEditing(false);
  });
  (function swipe() {
    var x0 = null, y0 = 0, t0 = 0;
    stage.addEventListener('pointerdown', function (e) { if (S.editing) return; x0 = e.clientX; y0 = e.clientY; t0 = Date.now(); });
    stage.addEventListener('pointerup', function (e) {
      if (x0 === null) return;
      var dx = e.clientX - x0, dy = e.clientY - y0; x0 = null;
      if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) { flipTo(S.spread + (dx < 0 ? 1 : -1)); return; }
      if (Math.abs(dx) < 6 && Date.now() - t0 < 400 && !e.target.closest('button, a, .ed')) {       // a tap on a page edge turns it
        var r = wrap.getBoundingClientRect(), fx = (e.clientX - r.left) / r.width;
        if (fx > 0.82) flipTo(S.spread + 1); else if (fx < 0.18) flipTo(S.spread - 1);
      }
    });
  })();
  var lastPhone = PHONE.matches;
  addEventListener('resize', function () {
    if (PHONE.matches !== lastPhone) {          // spread index <-> page index
      S.spread = PHONE.matches ? Math.max(0, S.spread * 2 - 1) : Math.ceil(S.spread / 2); lastPhone = PHONE.matches;
      drawBook();
    } else { bookSize(); layout(true); }
  });

  // ---- sheets ----
  function openSheet(html) {
    var sh = $('#sheet'); sh.innerHTML = html; sh.hidden = false; sh.classList.remove('in'); void sh.offsetWidth; sh.classList.add('in');
    $('#scrim').classList.add('on');
    var x = sh.querySelector('.x'); if (x) x.addEventListener('click', closeSheet);
    var f = sh.querySelector('[data-first]') || sh.querySelector('button'); setTimeout(function () { if (f) f.focus({ preventScroll: true }); }, 50);
  }
  function closeSheet() { $('#sheet').hidden = true; $('#scrim').classList.remove('on'); }
  $('#scrim').addEventListener('click', closeSheet);
  addEventListener('keydown', function (e) { if (e.key === 'Escape' && !$('#sheet').hidden) closeSheet(); });

  // ---- a creator's own book: fix a word, publish ----
  function setEditing(on) {
    S.editing = on; cv.classList.toggle('editing', on);
    var b = $('#editBtn'); if (b) { b.setAttribute('aria-pressed', on); $('.t', b).textContent = on ? 'Editing' : 'Edit'; }
    if (on && S.spread === 0) flipTo(PHONE.matches ? 3 : 2);
    if (!on && document.activeElement && document.activeElement.isContentEditable) document.activeElement.blur();
  }
  function post(fields) {
    var body = new FormData(); Object.keys(fields).forEach(function (k) { body.set(k, fields[k]); });
    return fetch(postUrl, { method: 'POST', body: body, headers: { 'X-Book': '1' }, credentials: 'same-origin' }).then(function (r) {
      if (r.redirected || (r.headers.get('content-type') || '').indexOf('json') < 0) { location.href = r.redirected ? r.url : postUrl; return new Promise(function () {}); }
      return r.json();
    });
  }
  function editWord(ed, e) {
    if (ed.isContentEditable) return;
    ed.contentEditable = 'true'; ed.spellcheck = true; ed.focus();
    var r = document.caretRangeFromPoint ? document.caretRangeFromPoint(e.clientX, e.clientY) : null;       // select the word that was tapped
    if (r && r.startContainer.nodeType === 3) {
      var txt = r.startContainer.textContent, a = r.startOffset, z = r.startOffset;
      while (a > 0 && /[\p{L}\p{N}’'-]/u.test(txt[a - 1])) a--;
      while (z < txt.length && /[\p{L}\p{N}’'-]/u.test(txt[z])) z++;
      var sel = getSelection(), rg = document.createRange(); rg.setStart(r.startContainer, a); rg.setEnd(r.startContainer, z); sel.removeAllRanges(); sel.addRange(rg);
    }
    var before = ed.textContent;
    function key(ev) { if (ev.key === 'Enter') { ev.preventDefault(); ed.blur(); } if (ev.key === 'Escape') { ed.textContent = before; ed.blur(); } }
    ed.addEventListener('keydown', key);
    ed.addEventListener('blur', function () {
      ed.contentEditable = 'false'; ed.removeEventListener('keydown', key);
      var v = ed.textContent.replace(/\s+/g, ' ').trim() || before; ed.textContent = v;
      if (v === before) return;
      post({ do: 'word', key: ed.dataset.k, value: v }).then(function (j) {
        if (!j.ok) { ed.textContent = before; toast(j.error); return; }
        $$('[data-k="' + ed.dataset.k + '"]').forEach(function (n) { n.textContent = j.value; });
        ed.classList.remove('saved'); void ed.offsetWidth; ed.classList.add('saved'); toast('Fixed in the book. Your post stays as it is.');
      }).catch(function () { ed.textContent = before; toast('Could not reach the server. Check your connection and try again.'); });
    }, { once: true });
  }
  book.addEventListener('click', function (e) {
    var lead = e.target.closest('#useLead');
    if (lead) { lead.disabled = true; post({ do: 'lead' }).then(function (j) { if (j.ok) location.reload(); else { lead.disabled = false; toast(j.error); } }); return; }
    if (S.editing) { var ed = e.target.closest('.ed'); if (ed) editWord(ed, e); }
  });
  function publishSheet() {
    var host = root.dataset.host, n = root.dataset;
    openSheet('<button class="v2-round x" type="button" aria-label="Close">' + ICON.x + '</button><h2>Publish your book</h2>' +
      '<div class="sh-book"><div><b>' + esc(n.title) + '</b><span>' + n.days + ' days · ' + n.stops + ' stops · by ' + esc(n.by) + '</span></div></div>' +
      '<p>Families can flip through it, save it and plan the trip from any page. It links back to your post.</p>' +
      '<button class="check" type="button" role="checkbox" aria-checked="false" id="mine" data-first><span class="bx">' + ICON.check + '</span><span><b>This is my post</b><span>I wrote it' + (host ? ' at ' + esc(host) : '') + ' and I am happy for GitAway to show it as a book.</span></span></button>' +
      '<p class="v2-error" id="pubError" role="alert" hidden></p><div class="sh-foot"><button class="tonal" type="button" id="pubCancel">Not yet</button><button class="go" type="button" id="pubGo" disabled>Publish</button></div>');
    $('#mine').addEventListener('click', function (e) { var c = e.currentTarget, on = c.getAttribute('aria-checked') !== 'true'; c.setAttribute('aria-checked', on); $('#pubGo').disabled = !on; });
    $('#pubCancel').addEventListener('click', closeSheet);
    $('#pubGo').addEventListener('click', function () {
      var go = $('#pubGo'); go.disabled = true;
      post({ do: 'publish', own: '1' }).then(function (j) {
        if (!j.ok) { var p = $('#pubError'); p.textContent = j.error; p.hidden = false; go.disabled = false; return; }
        published(j);
      }).catch(function () { var p = $('#pubError'); p.textContent = 'Could not reach the server. Check your connection and try again.'; p.hidden = false; go.disabled = false; });
    });
  }
  function published(j) {
    closeSheet(); setEditing(false); flipTo(0);
    wait(PHONE.matches ? '--cv-d300' : '--cv-d1000').then(function () {
      S.live = true; root.dataset.live = '1';
      var cover = $('.leaf .face.front .cover'), st = el('div', 'stamp', 'Published<small>' + esc(j.stamp) + '</small>'); if (cover) cover.appendChild(st);
      $('#bookTop').firstElementChild.outerHTML = '<span class="tag live"><i></i>Published<span class="long">&nbsp;· ' + esc(j.link.replace(/^https?:\/\//, '')) + '</span></span>';
      var pb = $('#pubBtn'); if (pb) { var sb = el('button', 'go', ICON.share + '<span class="t">Share</span>'); sb.type = 'button'; sb.id = 'shareBtn'; sb.setAttribute('aria-label', 'Share'); pb.replaceWith(sb); }
      layout(false);
      return wait('--cv-d400').then(function () { confetti(cover); return wait(PHONE.matches ? '--cv-d900' : '--cv-d600'); });
    }).then(function () { showShare(j); });
    S.last = j;
  }
  function confetti(cover) {
    if (RM.matches || !cover) return;
    var r = cover.getBoundingClientRect(), c = el('div', 'confetti');
    c.style.left = (r.left + r.width / 2) + 'px'; c.style.top = (r.top + r.height * 0.42) + 'px';
    var cols = ['var(--ride)', 'var(--food)', 'var(--flight)', 'var(--see)', 'var(--tix)', 'var(--stay)', 'var(--bk-foil)'], out = '';
    for (var i = 0; i < 64; i++) { var a = Math.random() * Math.PI * 2, d = 140 + Math.random() * 260; out += '<i style="--c:' + cols[i % cols.length] + ';--x:' + Math.cos(a) * d + 'px;--y:' + (Math.sin(a) * d * 0.8 + 180) + 'px;--r:' + (Math.random() * 720 - 360) + 'deg;--d:' + Math.round(Math.random() * 120) + 'ms;width:' + (6 + Math.random() * 7) + 'px;height:' + (8 + Math.random() * 8) + 'px"></i>'; }
    c.innerHTML = out; document.body.appendChild(c); setTimeout(function () { c.remove(); }, tok('--cv-d2400'));
  }
  function showShare(j) {
    j = j || S.last; if (!j) return;
    var p = $('#sharep'), t = $('#t-share');
    p.textContent = ''; p.appendChild(t.content.cloneNode(true));
    if (PHONE.matches) { var x = el('button', 'v2-round x', ICON.x); x.type = 'button'; x.setAttribute('aria-label', 'Close'); x.addEventListener('click', hideShare); p.prepend(x); }
    $('#shLink', p).textContent = j.link.replace(/^https?:\/\//, ''); $('#shCode', p).textContent = j.code;
    $('#shFine', p).textContent = j.listed ? 'It is on the shelf.' : 'It joins the shelf once the captain has checked the post is yours' + (j.host ? ': we look for your email at ' + j.host : '') + '. Until then only people with its link can open it.';
    $$('[data-copy]', p).forEach(function (b) {
      b.addEventListener('click', function () { try { navigator.clipboard.writeText(b.dataset.copy === 'code' ? j.code : j.link); } catch (err) { /* the toast still says it */ } b.innerHTML = ICON.check + 'Copied'; toast('Copied'); });
    });
    p.hidden = false; cv.classList.add('share-open');
  }
  function hideShare() { $('#sharep').hidden = true; cv.classList.remove('share-open'); }
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (t.closest('#editBtn')) setEditing(!S.editing);
    else if (t.closest('#editDone')) setEditing(false);
    else if (t.closest('#pubBtn')) publishSheet();
    else if (t.closest('#shareBtn')) showShare(S.last || { link: location.origin + postUrl.replace('/creators/import/', '/trips/') + '/book', code: '', listed: true, host: root.dataset.host });
  });

  // ---- a reader's book: the heart is the existing Save ----
  var heart = $('#heartBtn');
  if (heart) heart.addEventListener('click', function () {
    var on = heart.getAttribute('aria-pressed') === 'true', next = '/trips/' + heart.dataset.slug + '/book';
    if (heart.dataset.signed !== '1') { var f = el('form'); f.method = 'post'; f.action = '/save'; f.innerHTML = '<input type="hidden" name="next" value="' + esc(next) + '">'; document.body.appendChild(f); f.submit(); return; }
    heart.setAttribute('aria-pressed', !on); $('.t', heart).textContent = on ? 'Save' : 'Saved';
    heart.classList.remove('pop'); void heart.offsetWidth; heart.classList.add('pop');
    var body = new URLSearchParams({ next: next });
    fetch(on ? '/unsave' : '/save', { method: 'POST', body: body, credentials: 'same-origin', redirect: 'manual' }).catch(function () { heart.setAttribute('aria-pressed', on); $('.t', heart).textContent = on ? 'Saved' : 'Save'; toast('Could not save that. Try again.'); });
  });

  // ---- start ----
  var bar = $('#bbar');                          // the bar is frosted glass only where it floats over the page (the phone)
  function glass() { bar.classList.toggle('v2-glass', PHONE.matches); }
  glass(); PHONE.addEventListener('change', glass);
  drawBook();
  var auto = root.dataset.auto === '1' && !creator;
  if (auto) setTimeout(function () { flipTo(1); }, RM.matches ? 0 : tok('--cv-d450'));
})();
