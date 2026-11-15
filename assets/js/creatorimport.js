// The magic import (F-183, F-235, F-253): "Make my book" asks the server to tell the page as it works (X-Magic: one JSON line per step). The post's card grows with its title and picture as soon as
// they are read, its own sentences arrive highlighted while the draft is made, then the days and stops land under the story line, tagged with the sentence that names them, and "Your book is ready".
// Every word shown is the post's or the draft's. All time is a --cv-d* token (v2-tokens.css) read with getComputedStyle; reduced motion shows everything at once. Without fetch streaming, or without
// script, the form just submits and the browser waits (the server answers with the editor).
(function () {
  var form = document.getElementById('fc-paste') || document.getElementById('ci-form');
  var stage = document.getElementById('imp');
  if (!stage) return;
  var cv = stage.closest('.cv');
  var $ = function (id) { return document.getElementById(id); };
  var RM = matchMedia('(prefers-reduced-motion: reduce)');
  var PHONE = matchMedia('(max-width: 719px)');
  var cs = getComputedStyle(document.documentElement);
  function tok(n) { var v = cs.getPropertyValue(n).trim(); return v.slice(-2) === 'ms' ? parseFloat(v) : parseFloat(v) * 1000; }
  function wait(token) { return new Promise(function (r) { setTimeout(r, RM.matches ? 0 : tok(token)); }); }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  var KINDS = { see: ['Sight', 'M3 21h18M5 21V10M19 21V10M9 21v-7M15 21v-7M3 10l9-6 9 6z'], food: ['Food', 'M7 3v8a2 2 0 0 0 2 2v8M11 3v8a2 2 0 0 1-2 2M7 3h4M17 21V3c-2 1-3 4-3 8h3'],
                tix: ['Tickets', 'M3 8a2 2 0 0 0 2-2h14a2 2 0 0 0 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 0-2 2H5a2 2 0 0 0-2-2v-2a2 2 0 0 0 0-4zM14 6v12'], ride: ['Ride', 'M4 16V9a3 3 0 0 1 3-3h7l4 5h1a2 2 0 0 1 2 2v3M4 11h14'],
                show: ['Show', 'M9 18V5l11-2v13'], walk: ['Walk', 'M13 4m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M9 21l3-7 3 3v5M12 14l-1-5 4 2 3 1M11 9l-4 2v3'] };
  function kt(k, extra) { var d = (KINDS[k] || KINDS.see)[1]; return '<span class="kt' + (k === 'ride' ? ' dark' : '') + ' ' + (extra || '') + '" style="--k:var(--bk-' + (KINDS[k] ? k : 'see') + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="' + d + '"/></svg></span>'; }
  function kindName(k) { return (KINDS[k] || KINDS.see)[0]; }

  var run = 0;
  function story(t, done) { var s = $('story'); s.textContent = t; s.classList.remove('swap'); void s.offsetWidth; s.classList.add('swap'); $('storyRow').classList.toggle('done', !!done); }
  function step(i) { Array.prototype.forEach.call($('steps').children, function (li, j) { li.classList.toggle('on', j === i); li.classList.toggle('done', j < i); }); }
  function prog(p) { $('progBar').style.width = p + '%'; }
  function reset() {
    var old = $('ci-error'); if (old) old.remove();
    $('postCard').className = 'post';
    $('postT').innerHTML = '<span class="sk"></span>'; $('postBy').innerHTML = '<span class="sk" style="width:40%"></span>';
    $('postSite').textContent = ''; $('postFav').textContent = ''; $('postFav').style.background = '';
    var img = $('postImg'); img.removeAttribute('src');
    $('river').textContent = ''; $('days').textContent = ''; $('ready').hidden = true; $('itinCount').textContent = '0 stops'; $('cm-live').textContent = '';
    var n = $('impNote'); n.hidden = true; n.textContent = '';
  }
  function show(on) { cv.classList.toggle('is-results', on); cv.dataset.view = on ? 'import' : 'landing'; stage.hidden = !on; var l = $('landing'); if (l) l.hidden = on; if (on) scrollTo(0, 0); }

  // the card grows out of the box that was submitted
  function morphFrom(from, to) {
    if (RM.matches || !from || !to || !from.width) return;
    var b = to.getBoundingClientRect(); if (!b.width) return;
    to.animate([{ transform: 'translate(' + (from.left - b.left) + 'px,' + (from.top - b.top) + 'px) scale(' + (from.width / b.width) + ',' + (from.height / b.height) + ')', transformOrigin: '0 0', opacity: 0.4 }, { transform: 'none', transformOrigin: '0 0', opacity: 1 }],
               { duration: tok('--cv-d600'), easing: cs.getPropertyValue('--v2-ease').trim() });
  }

  function addSentence(text, tag) {
    var river = $('river'), old = river.querySelectorAll('.snt');
    Array.prototype.forEach.call(old, function (p) { p.classList.add('old'); });
    var p = el('p', 'snt'); p.innerHTML = '<q>' + esc(text) + '</q>' + (tag ? tagHtml(tag) : ''); p.dataset.said = text;
    river.appendChild(p);
    while (river.children.length > 6) river.firstElementChild.remove();
    setTimeout(function () { p.classList.add('marked'); }, RM.matches ? 0 : tok('--cv-d250'));
    return p;
  }
  function tagHtml(tag) { return '<span class="to"><i style="--k:var(--bk-' + tag.kind + ')"></i>' + esc(tag.text) + '</span>'; }
  function tagSentence(text, tag) {
    var found = Array.prototype.filter.call($('river').children, function (p) { return p.dataset.said === text; })[0];
    if (!found) { addSentence(text, tag); return; }
    if (!found.querySelector('.to')) found.insertAdjacentHTML('beforeend', tagHtml(tag));
    found.classList.remove('old');
  }

  function compactDay(d) {
    var blk = document.querySelector('#days .dayb[data-d="' + d + '"]'); if (!blk) return;
    var rows = blk.querySelector('.rows'), chips = el('div', 'chips2'), i = 0;
    Array.prototype.forEach.call(rows.children, function (r) { chips.insertAdjacentHTML('beforeend', '<span class="pc" style="--i:' + (i++) + '">' + r.dataset.kt + (r.dataset.t ? '<em>' + esc(r.dataset.t) + '</em> ' : '') + esc(r.dataset.name) + '</span>'); });
    rows.replaceWith(chips);
  }

  function fail(message) {
    run += 1; show(false);
    var old = $('ci-error'); if (old) old.remove();
    var p = el('p', 'v2-error', message); p.id = 'ci-error'; p.setAttribute('role', 'alert');
    var bar = form.querySelector('.ci-actions'); if (bar) form.insertBefore(p, bar); else form.parentNode.insertBefore(p, form.nextSibling);
    p.scrollIntoView({ block: 'nearest' });
  }

  var waiting = null;                          // the post's own sentences, one after another, while the draft is made
  function wait8(words, mine) {
    var i = 0, go = true;
    (function next() {
      if (!go || mine !== run || i >= words.length) return;
      addSentence(words[i++]);
      setTimeout(next, RM.matches ? 0 : tok('--cv-d700'));
    })();
    return function () { go = false; };
  }

  function read(e, mine) {
    if (mine !== run) return;
    $('postCard').classList.add('read');
    var site = e.site || '', fav = $('postFav');
    $('postSite').textContent = site; fav.textContent = (site.replace(/^www\./, '')[0] || '').toUpperCase(); fav.style.background = 'var(--k-wx)';
    $('postOk').hidden = !e.robots; $('postT').innerHTML = '<span class="in">' + esc(e.title || 'Your post') + '</span>';
    $('postBy').innerHTML = e.by ? '<span class="in">by ' + esc(e.by) + '</span>' : '';
    story(site ? 'Read ' + site + (e.chars ? ': ' + e.chars.toLocaleString() + ' characters' : '') : 'Read your post'); prog(14); step(0);
    if (e.image && /^https?:\/\//i.test(e.image)) { var img = $('postImg'); img.addEventListener('load', function () { $('postCard').classList.add('pic'); }, { once: true }); img.src = e.image; }
    wait(RM.matches ? '--cv-d0' : '--cv-d450').then(function () { if (mine === run) { step(1); prog(20); } });
    waiting = wait8(e.words || [], mine);
  }

  async function land(d, mine) {
    var ok = function () { return mine === run; };
    if (waiting) waiting();
    step(1); prog(20);
    var count = 0, total = d.days.reduce(function (n, x) { return n + x.stops.length; }, 0), unsure = 0;
    if ($('postT').querySelector('.sk')) $('postT').innerHTML = '<span class="in">' + esc(d.title) + '</span>';
    for (var di = 0; di < d.days.length; di++) {
      if (di) compactDay(di - 1);
      var day = d.days[di];
      story(di === 0 ? 'Found ' + d.days.length + (d.days.length === 1 ? ' day' : ' days') + '. Placing day 1: ' + day.title : 'Placing day ' + (di + 1) + ' of ' + d.days.length + ': ' + day.title);
      var blk = el('div', 'dayb'); blk.dataset.d = di; blk.innerHTML = '<h4><span class="dn">Day ' + (di + 1) + '</span>' + esc(day.title) + '</h4><div class="rows"></div>';
      $('days').appendChild(blk);
      var rows = blk.querySelector('.rows');
      for (var si = 0; si < day.stops.length; si++) {
        var s = day.stops[si], named = s.name !== d.unsure;
        if (!named) unsure += 1;
        var r = el('div', 'srow', '<span class="tm">' + (s.time ? esc(s.time) : '') + '</span>' + kt(s.kind) + '<span><b>' + esc(s.name) + '</b><small>' + kindName(s.kind) + '</small></span>');
        r.dataset.kt = kt(s.kind); r.dataset.t = s.time || ''; r.dataset.name = s.name;
        rows.appendChild(r);
        if (s.said) tagSentence(s.said, { kind: s.kind || 'see', text: 'Day ' + (di + 1) + ' · ' + s.name });
        if (PHONE.matches) r.scrollIntoView({ block: 'nearest', behavior: RM.matches ? 'auto' : 'smooth' });
        count++; $('itinCount').textContent = count + (count === 1 ? ' stop' : ' stops'); prog(20 + count / Math.max(total, 1) * 64);
        await wait('--cv-d250'); if (!ok()) return;
      }
      await wait('--cv-d250'); if (!ok()) return;
    }
    compactDay(d.days.length - 1);
    step(2); story('Binding your book: cover, ' + d.days.length + (d.days.length === 1 ? ' day, ' : ' days, ') + (d.tips.length === 1 ? 'one tip' : d.tips.length + ' tips')); prog(94);
    await wait('--cv-d800'); if (!ok()) return;
    step(3); prog(100); story('Done. Every word is from your post.', true);
    $('readyLine').textContent = d.days.length + (d.days.length === 1 ? ' day · ' : ' days · ') + total + (total === 1 ? ' stop · ' : ' stops · ') + d.tips.length + (d.tips.length === 1 ? ' tip' : ' tips') + ', from your post' +
      (unsure ? '. ' + unsure + (unsure === 1 ? ' stop needs a name: fix it in the book.' : ' stops need a name: fix them in the book.') : '');
    $('openBook').href = d.book; $('readyEdit').href = d.editor;
    $('ready').hidden = false; $('cm-live').textContent = 'Your book is ready: ' + $('readyLine').textContent;
    if (PHONE.matches) $('ready').scrollIntoView({ block: 'nearest', behavior: RM.matches ? 'auto' : 'smooth' });
  }

  if (form && window.fetch && window.TextDecoder && window.ReadableStream) form.addEventListener('submit', function (e) {
    var by = e.submitter;
    if (!by || by.value !== 'draft') return;
    var link = (form.elements.link || {}).value || '', text = (form.elements.text || {}).value || '';
    if (!link.trim() && !text.trim()) return;           // nothing to read: the server answers with its message
    if (form.dataset.signedIn === '0') { try { localStorage.setItem('ga-paste', JSON.stringify({ text: link.trim() || text, at: Date.now() })); } catch (err) { /* private mode: they paste again */ } return; }
    e.preventDefault();
    var mine = ++run, from = form.getBoundingClientRect(), body = new FormData(form); body.set('do', 'draft');
    reset(); show(true); morphFrom(from, $('postCard')); story('Opening your post'); step(0); prog(4);
    fetch(form.action, { method: 'POST', body: body, headers: { 'X-Magic': '1' }, credentials: 'same-origin' }).then(function (r) {
      if (r.redirected || !r.body || (r.headers.get('content-type') || '').indexOf('ndjson') < 0) { location.href = r.redirected ? r.url : form.action; return; }       // signed out: the sign-in page, not a stream
      var reader = r.body.getReader(), dec = new TextDecoder(), buf = '', ended = false;
      function line(l) {
        if (!l.trim() || mine !== run) return;
        var ev = JSON.parse(l);
        if (ev.event === 'read') read(ev, mine);
        else if (ev.event === 'draft') { ended = true; land(ev, mine); }
        else if (ev.event === 'error') { ended = true; if (waiting) waiting(); fail(ev.message); }
      }
      return (function pump() {
        return reader.read().then(function (x) {
          if (x.done) { if (buf) line(buf); if (!ended && mine === run) { if (waiting) waiting(); fail('The draft was cut short. Try again, or paste the text of your post.'); } return; }
          buf += dec.decode(x.value, { stream: true });
          var parts = buf.split('\n'); buf = parts.pop();
          parts.forEach(line);
          return pump();
        });
      })();
    }).catch(function () { if (waiting) waiting(); fail('Could not reach the server. Check your connection and try again.'); });
  });

  // an example chip fills the box with the real post it names
  var chip = $('fc-example-chip');
  if (chip && form) chip.addEventListener('click', function () {
    var box = form.elements.text; if (!box) return; box.value = chip.dataset.fill; box.focus();
    form.classList.remove('flash'); void form.offsetWidth; form.classList.add('flash');
  });

  // F-186: text pasted before signing in comes back here, once, if it is less than an hour old.
  (function () {
    var box = $('ci-text') || (form && form.elements.text), link = $('ci-link'), saved;
    try { saved = JSON.parse(localStorage.getItem('ga-paste') || 'null'); localStorage.removeItem('ga-paste'); } catch (err) { return; }
    if (!saved || !saved.text || Date.now() - saved.at > 3600000 || !box || box.value || (link && link.value)) return;
    if (/^https?:\/\/\S+$/i.test(saved.text.trim()) && link) link.value = saved.text.trim(); else box.value = saved.text;
  })();
})();
