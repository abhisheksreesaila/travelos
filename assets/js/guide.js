// The guide page (F-262, docs/design/guides-v2): the run sheet the server drew becomes master-detail. A stop's card opens its details in a panel beside the sheet on a laptop and in a sheet over it
// on a phone; ↑ and ↓ step through the stops, Esc closes. The sticky day strip scrolls to its day and follows the reading. "Add to my plan" drops stops into the family's free hours (POST /guides/add)
// with an Undo; the heart is the existing Save. A creator's own guide can fix a word in place and publish. Every time here is a token of v2-tokens.css read with getComputedStyle: no script writes one.
// Without script every card shows its details under it (the panel and its buttons are drawn only here).
(function () {
  'use strict';
  var root = document.getElementById('gpage');
  if (!root) return;
  var cv = root.closest('.cv') || document.body;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var RM = matchMedia('(prefers-reduced-motion: reduce)');
  var PHONE = matchMedia('(max-width: 719px)');
  var cs = getComputedStyle(document.documentElement);
  function tok(n) { var v = cs.getPropertyValue(n).trim(); return v.slice(-2) === 'ms' ? parseFloat(v) : parseFloat(v) * 1000; }
  function wait(token) { return new Promise(function (r) { setTimeout(r, RM.matches ? 0 : tok(token)); }); }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  var D = root.dataset, owner = D.mode === 'owner';
  var ICON = {
    x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12l5 5 9-10"/></svg>',
    plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
    target: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/></svg>'
  };
  function toast(msg, undo) {
    var t = $('#toast'); t.textContent = msg;
    if (undo) { var b = el('button', 'tonal', 'Undo'); b.type = 'button'; b.addEventListener('click', function () { t.classList.remove('on'); undo(); }); t.appendChild(b); }
    t.classList.add('on'); clearTimeout(toast.t); toast.t = setTimeout(function () { t.classList.remove('on'); }, undo ? 7000 : 3200);
  }

  // ---- the stops, in reading order ----
  var cards = $$('.g-card'), panel = $('#g-panel'), cur = -1;
  function post(url, fields, extra) {
    var body = new FormData();
    Object.keys(fields).forEach(function (k) { [].concat(fields[k]).forEach(function (v) { body.append(k, v); }); });
    return fetch(url, { method: 'POST', body: body, headers: extra || {}, credentials: 'same-origin' }).then(function (r) { return r.json(); });
  }

  // ---- the panel ----
  function actions(c) {
    var out = '';
    if (D.can === 'yes') out += '<button class="go" type="button" data-add="' + esc(c.dataset.k) + '">' + ICON.plus + 'Add to my plan</button>';
    out += '<a class="tonal" href="' + esc(D.plan) + '">' + ICON.target + 'Plan this trip</a>';
    return out;
  }
  function fill(i, dir) {
    var c = cards[i]; if (!c) return;
    var more = $('.g-more', c);
    $('.g-pk', panel).textContent = c.dataset.label;
    $('.g-pk', panel).style.color = 'var(--bk-' + c.dataset.kind + ')';
    $('.g-po', panel).textContent = 'Day ' + c.dataset.day + ' · stop ' + c.dataset.n + ' of ' + c.dataset.of;
    var day = $('#g-day' + c.dataset.day + ' h2'), body = $('#g-pbody');
    body.innerHTML = '<h2>' + esc(c.dataset.name) + '</h2><p class="g-sub">' + esc(c.dataset.label) + ' · ' + esc(day ? day.textContent : '') + '</p>' + (more ? more.outerHTML : '');
    $('#g-pact').innerHTML = actions(c);
    body.classList.remove('swap-dn', 'swap-up'); void body.offsetWidth;
    if (dir && !RM.matches) body.classList.add(dir > 0 ? 'swap-dn' : 'swap-up');
    $('#g-prev').disabled = i === 0; $('#g-next').disabled = i === cards.length - 1;
  }
  function open(i, opts) {
    opts = opts || {};
    var dir = cur < 0 ? 0 : (i > cur ? 1 : -1);
    cards.forEach(function (c, j) { c.classList.toggle('sel', j === i); $$('.g-open', c).forEach(function (b) { b.setAttribute('aria-expanded', j === i ? 'true' : 'false'); }); });
    cur = i; panel.hidden = false; fill(i, dir);
    void panel.offsetWidth; root.classList.add('has-detail');
    if (PHONE.matches) { $('#scrim').classList.add('on'); panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true'); if (!opts.keep) $('#g-close').focus({ preventScroll: true }); }
    else { panel.removeAttribute('aria-modal'); panel.setAttribute('role', 'complementary'); }
    if (opts.scroll) cards[i].scrollIntoView({ block: 'center', behavior: RM.matches ? 'auto' : 'smooth' });
  }
  function close() {
    if (cur < 0) return;
    var c = cards[cur]; cur = -1;
    cards.forEach(function (x) { x.classList.remove('sel'); $$('.g-open', x).forEach(function (b) { b.setAttribute('aria-expanded', 'false'); }); });
    root.classList.remove('has-detail'); $('#scrim').classList.remove('on');
    setTimeout(function () { if (cur < 0) panel.hidden = true; }, RM.matches ? 0 : tok('--cv-d600'));
    var b = $('.g-open', c); if (b && PHONE.matches) b.focus({ preventScroll: true });
  }
  cards.forEach(function (c, i) {
    $$('.g-open', c).forEach(function (b) { b.addEventListener('click', function () { if (cur === i) close(); else open(i); }); });
  });
  if (cards.length) {
    $('#g-close').addEventListener('click', close);
    $('#g-prev').addEventListener('click', function () { if (cur > 0) open(cur - 1, { scroll: true, keep: true }); });
    $('#g-next').addEventListener('click', function () { if (cur < cards.length - 1) open(cur + 1, { scroll: true, keep: true }); });
    $('#scrim').addEventListener('click', function () { if (!$('#sheet').hidden) closeSheet(); else close(); });
  }
  addEventListener('keydown', function (e) {
    var typing = document.activeElement && (document.activeElement.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName));
    if (e.key === 'Escape') { if (!$('#sheet').hidden) closeSheet(); else if (cur >= 0 && !typing) close(); return; }
    if (typing || cur < 0 || !$('#sheet').hidden || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      var n = cur + (e.key === 'ArrowDown' ? 1 : -1);
      if (n >= 0 && n < cards.length) open(n, { scroll: true, keep: true });
    }
  });

  // ---- the day strip: scroll to a day, follow the reading ----
  var strip = $$('.dbtn'), days = $$('.g-day');
  function press(n) { strip.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.day === String(n) ? 'true' : 'false'); }); }
  strip.forEach(function (b) {
    b.addEventListener('click', function () {
      var d = $('#g-day' + b.dataset.day); press(b.dataset.day);
      if (d) d.scrollIntoView({ block: 'start', behavior: RM.matches ? 'auto' : 'smooth' });
    });
  });
  if ('IntersectionObserver' in window && days.length > 1) {
    var io = new IntersectionObserver(function (es) {
      var seen = es.filter(function (e) { return e.isIntersecting; }).sort(function (a, b) { return a.boundingClientRect.top - b.boundingClientRect.top; })[0];
      if (seen) press(seen.target.dataset.day);
    }, { rootMargin: '-25% 0px -60% 0px' });
    days.forEach(function (d) { io.observe(d); });
  }
  function openDay() { var p = strip.filter(function (b) { return b.getAttribute('aria-pressed') === 'true'; })[0]; return p ? p.dataset.day : '1'; }

  // ---- Add to my plan ----
  function undoAll(list) {
    return function () {
      list.reduce(function (p, u) { return p.then(function () { return post('/trip/plan/write', { op: 'undo', undo: JSON.stringify(u) }); }); }, Promise.resolve())
        .then(function () { toast('Taken out of your plan'); $$('.g-plus.done').forEach(function (b) { b.classList.remove('done'); b.innerHTML = ICON.plus; }); });
    };
  }
  function addStops(keys, btn) {
    if (btn) btn.disabled = true;
    return post('/guides/add', { slug: D.slug, k: keys }).then(function (j) {
      if (btn) btn.disabled = false;
      if (j.error) { toast(j.error); return; }
      (j.added || []).forEach(function (a, i) { var k = keys[i]; $$('.g-plus[data-add="' + k + '"]').forEach(function (b) { b.classList.add('done'); b.innerHTML = ICON.check; b.setAttribute('aria-label', 'Added to your plan'); }); });
      toast(j.toast, (j.added || []).length ? undoAll((j.added || []).map(function (a) { return a.undo; }).reverse()) : null);
    }).catch(function () { if (btn) btn.disabled = false; toast('Could not reach the server. Check your connection and try again.'); });
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-add]'); if (!b || b.tagName === 'A') return;
    if (b.dataset.add === 'day') addStops($$('#g-day' + openDay() + ' .g-card').map(function (c) { return c.dataset.k; }), b);
    else addStops([b.dataset.add], b);
  });

  // ---- a reader: Save (the existing /save) and Copy link ----
  var heart = $('#heartBtn');
  if (heart) heart.addEventListener('click', function () {
    var on = heart.getAttribute('aria-pressed') === 'true', next = '/trips/' + heart.dataset.slug;
    if (heart.dataset.signed !== '1') { var f = el('form'); f.method = 'post'; f.action = '/save'; f.innerHTML = '<input type="hidden" name="next" value="' + esc(next) + '">'; document.body.appendChild(f); f.submit(); return; }
    heart.setAttribute('aria-pressed', !on); $('.t', heart).textContent = on ? 'Save' : 'Saved';
    heart.classList.remove('pop'); void heart.offsetWidth; heart.classList.add('pop');
    fetch(on ? '/unsave' : '/save', { method: 'POST', body: new URLSearchParams({ next: next }), credentials: 'same-origin', redirect: 'manual' })
      .catch(function () { heart.setAttribute('aria-pressed', on); $('.t', heart).textContent = on ? 'Saved' : 'Save'; toast('Could not save that. Try again.'); });
  });
  var share = $('#g-share');
  if (share) share.addEventListener('click', function () {
    var link = location.origin + location.pathname;
    if (navigator.share) { navigator.share({ title: D.title, url: link }).catch(function () {}); return; }
    try { navigator.clipboard.writeText(link); } catch (err) { /* the toast still says it */ }
    toast('Link copied');
  });

  // ---- a creator's own guide: fix a word in place, publish, share ----
  if (!owner) return;
  var postUrl = location.pathname.replace(/\/guide$/, '');
  function own(fields) {
    return post(postUrl, fields, { 'X-Book': '1' }).catch(function () { return { ok: false, error: 'Could not reach the server. Check your connection and try again.' }; });
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
      own({ do: 'word', key: ed.dataset.k, value: v }).then(function (j) {
        if (!j.ok) { ed.textContent = before; toast(j.error); return; }
        $$('[data-k="' + ed.dataset.k + '"]').forEach(function (n) { n.textContent = j.value; });
        ed.classList.remove('saved'); void ed.offsetWidth; ed.classList.add('saved'); toast('Fixed in the guide. Your post stays as it is.');
      });
    }, { once: true });
  }
  root.addEventListener('click', function (e) { var ed = e.target.closest('.ed'); if (ed) editWord(ed, e); });

  function openSheet(html) {
    var sh = $('#sheet'); sh.innerHTML = html; sh.hidden = false; sh.classList.remove('in'); void sh.offsetWidth; sh.classList.add('in');
    $('#scrim').classList.add('on');
    var x = sh.querySelector('.x'); if (x) x.addEventListener('click', closeSheet);
    var f = sh.querySelector('[data-first]'); if (f) f.focus({ preventScroll: true });
  }
  function closeSheet() { $('#sheet').hidden = true; $('#scrim').classList.remove('on'); }
  function publishSheet() {
    openSheet('<button class="v2-round x" type="button" aria-label="Close">' + ICON.x + '</button><h2>Publish your guide</h2>' +
      '<div class="sh-book"><div><b>' + esc(D.title) + '</b><span>' + D.days + ' days · ' + D.stops + ' stops · by ' + esc(D.by) + '</span></div></div>' +
      '<p>People can read it, save it, add its stops to their plan and plan the trip from it. Your flights and stays are never published.</p>' +
      '<button class="check" type="button" role="checkbox" aria-checked="false" id="mine" data-first><span class="bx">' + ICON.check + '</span><span><b>This is my post</b><span>I wrote it' + (D.host ? ' at ' + esc(D.host) : '') + ' and I am happy for GitAway to show it as a guide.</span></span></button>' +
      '<p class="v2-error" id="pubError" role="alert" hidden></p><div class="sh-foot"><button class="tonal" type="button" id="pubCancel">Not yet</button><button class="go" type="button" id="pubGo" disabled>Publish</button></div>');
    $('#mine').addEventListener('click', function (e) { var c = e.currentTarget, on = c.getAttribute('aria-checked') !== 'true'; c.setAttribute('aria-checked', on); $('#pubGo').disabled = !on; });
    $('#pubCancel').addEventListener('click', closeSheet);
    $('#pubGo').addEventListener('click', function () {
      var go = $('#pubGo'); go.disabled = true;
      own({ do: 'publish', own: '1' }).then(function (j) {
        if (!j.ok) { var p = $('#pubError'); p.innerHTML = esc(j.error) + (j.editor ? ' <a href="' + esc(j.editor) + '">Fix it in the details</a>' : ''); p.hidden = false; go.disabled = false; return; }
        published(j);
      });
    });
  }
  var last = null;
  function published(j) {
    last = j; closeSheet();
    var tag = $('.g-own .tag'); if (tag) tag.outerHTML = '<span class="tag live"><i></i>Published<span class="long">&nbsp;· ' + esc(j.link.replace(/^https?:\/\//, '')) + '</span></span>';
    var pb = $('#pubBtn');
    if (pb) { var sb = el('button', 'go', '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>Share'); sb.type = 'button'; sb.id = 'shareBtn'; sb.setAttribute('aria-label', 'Share'); pb.replaceWith(sb); }
    window.scrollTo({ top: 0, behavior: RM.matches ? 'auto' : 'smooth' });
    wait('--cv-d400').then(function () { confetti(); return wait('--cv-d600'); }).then(function () { showShare(j); });
  }
  function confetti() {
    if (RM.matches) return;
    var c = el('div', 'confetti'), cols = ['var(--ride)', 'var(--food)', 'var(--flight)', 'var(--see)', 'var(--tix)', 'var(--stay)'], out = '';
    c.style.left = innerWidth / 2 + 'px'; c.style.top = innerHeight * 0.35 + 'px';
    for (var i = 0; i < 64; i++) { var a = Math.random() * Math.PI * 2, d = 140 + Math.random() * 260; out += '<i style="--c:' + cols[i % cols.length] + ';--x:' + Math.cos(a) * d + 'px;--y:' + (Math.sin(a) * d * 0.8 + 180) + 'px;--r:' + (Math.random() * 720 - 360) + 'deg;--d:' + Math.round(Math.random() * 120) + 'ms;width:' + (6 + Math.random() * 7) + 'px;height:' + (8 + Math.random() * 8) + 'px"></i>'; }
    c.innerHTML = out; document.body.appendChild(c); setTimeout(function () { c.remove(); }, tok('--cv-d2400'));
  }
  function showShare(j) {
    j = j || last; if (!j) return;
    var p = $('#sharep'), t = $('#t-share');
    p.textContent = ''; p.appendChild(t.content.cloneNode(true));
    var x = el('button', 'v2-round x', ICON.x); x.type = 'button'; x.setAttribute('aria-label', 'Close'); x.addEventListener('click', hideShare); p.prepend(x);
    $('#shLink', p).textContent = j.link.replace(/^https?:\/\//, ''); $('#shCode', p).textContent = j.code;
    var card = j.card || ('/trips/' + (j.slug || D.slug) + '/card.png');
    $('#shCard', p).src = card; $('#shDown', p).href = card;
    var nat = $('#shNative', p);
    if (navigator.canShare && navigator.share) {
      nat.hidden = false;
      nat.addEventListener('click', function () {
        fetch(card).then(function (r) { return r.blob(); }).then(function (b) {
          var f = new File([b], 'guide-card.png', { type: 'image/png' });
          if (navigator.canShare({ files: [f] })) return navigator.share({ files: [f], title: D.title, url: j.link });
          return navigator.share({ title: D.title, url: j.link });
        }).catch(function () {});
      });
    }
    $('#shFine', p).textContent = j.listed ? 'It is in Guides.' : 'It joins Guides once the captain has checked the post is yours' + (j.host ? ': we look for your email at ' + j.host : '') + '. Until then only people with its link can open it.';
    $$('[data-copy]', p).forEach(function (b) {
      b.addEventListener('click', function () { try { navigator.clipboard.writeText(b.dataset.copy === 'code' ? j.code : j.link); } catch (err) { /* the toast still says it */ } b.innerHTML = ICON.check + 'Copied'; toast('Copied'); });
    });
    p.hidden = false; cv.classList.add('share-open');
  }
  function hideShare() { $('#sharep').hidden = true; cv.classList.remove('share-open'); }
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (t.closest('#pubBtn')) publishSheet();
    else if (t.closest('#shareBtn')) showShare(last || { link: location.origin + postUrl.replace('/creators/import/', '/trips/'), code: '', listed: true, host: D.host, slug: D.slug });
  });
})();
