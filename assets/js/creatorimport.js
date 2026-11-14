// Turn a post into a trip (F-183, F-235): "Draft my trip" asks the server to tell the page as it works (X-Magic: one JSON line per step). The post's title and lead picture appear as
// soon as it is read, its own sentences keep the waiting company, then the days and stops land one by one (the stagger is CSS: --i), then Publish. Every word shown is the post's own or the
// draft's. All motion is CSS on the --motion-* tokens; reduced motion shows everything at once. Without fetch streaming, or without JavaScript, the form just submits and the browser waits.
(function () {
  var form = document.getElementById('ci-form');
  var stage = document.getElementById('ci-magic');
  if (!form || !stage || !window.fetch || !window.TextDecoder || !window.ReadableStream) return;
  var root = form.closest('.ci');
  var $ = function (id) { return document.getElementById(id); };
  var KINDS = 6;
  var calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function step(n, state) {
    var li = $('cm-steps').children[n];
    if (li) { li.classList.toggle('is-on', state === 'on'); li.classList.toggle('is-done', state === 'done'); }
  }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  function waitWords(words) {              // the post's own sentences, one after the other, while the draft is made
    var box = $('cm-word'), say = $('cm-say'), i = 0, running = true;
    if (!words || !words.length) { say.hidden = true; return function () {}; }
    say.hidden = false;
    function show() { box.textContent = '“' + words[i % words.length] + '”'; box.classList.remove('go'); void box.offsetWidth; if (!calm) box.classList.add('go'); }
    box.addEventListener('animationend', function () { if (running) { i += 1; show(); } });
    show();
    return function () { running = false; say.hidden = true; };
  }

  function log(text) { var l = $('cm-log'); if (l) l.textContent = text; }

  function read(e, st) {
    stage.dataset.kind = e.kind || '';
    $('cm-site').textContent = e.site || '';
    var t = $('cm-title');
    t.textContent = e.title || 'Your post';
    t.classList.add('in');
    $('cm-by').textContent = e.by ? 'by ' + e.by : '';
    if (e.image && /^https?:\/\//i.test(e.image)) {
      var img = stage.querySelector('.cm-img');
      img.addEventListener('load', function () { img.hidden = false; img.classList.add('in'); stage.querySelector('.cm-ph').hidden = true; });
      img.src = e.image;
    }
    log('Read ' + (e.site || 'your post') + (e.chars ? ': ' + e.chars.toLocaleString() + ' characters. Finding the days and stops' : '. Finding the days and stops'));
    step(0, 'done'); step(1, 'on');
    st.stopWords = waitWords(e.words);
  }

  function land(d, st) {
    if (st.stopWords) st.stopWords();
    step(0, 'done'); step(1, 'done'); step(2, 'on');
    var list = $('cm-days'), i = 0, stops = 0, unsure = 0;
    if (!stage.querySelector('.cm-title.in')) $('cm-title').textContent = d.title;
    d.days.forEach(function (day, di) {
      var li = el('li', 'cm-day'), h = el('h3', 'cm-day-h');
      li.style.setProperty('--i', calm ? 0 : i++);
      h.appendChild(el('span', 'cm-day-n', 'Day ' + (di + 1)));
      h.appendChild(el('span', '', day.title));
      li.appendChild(h);
      var ul = el('ul', 'cm-stops');
      day.stops.forEach(function (s, si) {
        var k = el('li', 'cm-stop cm-c' + ((stops + di) % KINDS));
        k.style.setProperty('--i', calm ? 0 : i++);
        var dot = el('span', 'cm-dot', String(si + 1)); dot.setAttribute('aria-hidden', 'true');
        k.appendChild(dot);
        k.appendChild(el('span', 'cm-stop-t', s.name));
        if (s.time) k.appendChild(el('span', 'cm-stop-m', s.time));
        if (s.name === d.unsure) { k.classList.add('is-unsure'); unsure += 1; }
        ul.appendChild(k); stops += 1;
      });
      li.appendChild(ul);
      list.appendChild(li);
    });
    var done = $('cm-done');
    list.addEventListener('animationstart', function (ev) {      // the agent narrates each day as it lands (no timer: the CSS animation says when)
      var d = ev.target.classList && ev.target.classList.contains('cm-day') ? ev.target : null;
      if (d) log('Placing day ' + (Array.prototype.indexOf.call(list.children, d) + 1) + ' of ' + list.children.length + ': ' + d.querySelector('.cm-day-h span:last-child').textContent);
    });
    var finish = function () { log('Laid out ' + d.days.length + (d.days.length === 1 ? ' day' : ' days') + ': ' + stops + (stops === 1 ? ' stop' : ' stops') + ' placed'); stage.classList.add('is-done'); step(2, 'done'); };
    if (calm) finish(); else done.addEventListener('animationstart', finish);
    done.style.setProperty('--n', calm ? 0 : i + 1);
    var named = unsure ? ' ' + unsure + (unsure === 1 ? ' stop needs a name: you can fix it in the editor.' : ' stops need a name: you can fix them in the editor.') : '';
    $('cm-count').textContent = d.days.length + (d.days.length === 1 ? ' day, ' : ' days, ') + stops + (stops === 1 ? ' stop' : ' stops') + (d.place ? ' in ' + d.place : '') + '.' + named;
    $('cm-form').action = d.editor;
    $('cm-preview').href = d.preview;
    $('cm-edit').href = d.editor;
    done.hidden = false;
    $('cm-live').textContent = 'Your trip is ready: ' + $('cm-count').textContent;
  }

  function fail(message) {
    stage.hidden = true; root.classList.remove('is-drafting');
    var old = $('ci-error'); if (old) old.remove();
    var p = el('p', 'ci-error', message); p.id = 'ci-error'; p.setAttribute('role', 'alert');
    form.insertBefore(p, form.querySelector('.ci-actions'));
    p.scrollIntoView({ block: 'nearest' });
  }

  form.addEventListener('submit', function (e) {
    var by = e.submitter;
    if (!by || by.value !== 'draft') return;
    var link = (form.elements.link || {}).value || '';
    var text = (form.elements.text || {}).value || '';
    if (!link.trim() && !text.trim()) return;           // nothing to read: the server answers with its message
    e.preventDefault();
    var body = new FormData(form); body.set('do', 'draft');
    var st = {};
    root.classList.add('is-drafting'); stage.hidden = false;
    step(0, 'on');
    stage.scrollIntoView({ block: 'nearest' });
    fetch(form.action, { method: 'POST', body: body, headers: { 'X-Magic': '1' }, credentials: 'same-origin' }).then(function (r) {
      if (r.redirected || !r.body || (r.headers.get('content-type') || '').indexOf('ndjson') < 0) { window.location.href = r.redirected ? r.url : form.action; return; }       // signed out: the sign-in page, not a stream
      var reader = r.body.getReader(), dec = new TextDecoder(), buf = '', ended = false;
      function line(l) {
        if (!l.trim()) return;
        var ev = JSON.parse(l);
        if (ev.event === 'read') read(ev, st);
        else if (ev.event === 'draft') { ended = true; land(ev, st); }
        else if (ev.event === 'error') { ended = true; if (st.stopWords) st.stopWords(); fail(ev.message); }
      }
      return (function pump() {
        return reader.read().then(function (x) {
          if (x.done) { if (buf) line(buf); if (!ended) fail('The draft was cut short. Try again, or paste the text of your post.'); return; }
          buf += dec.decode(x.value, { stream: true });
          var parts = buf.split('\n'); buf = parts.pop();
          parts.forEach(line);
          return pump();
        });
      })();
    }).catch(function () { if (st.stopWords) st.stopWords(); fail('Could not reach the server. Check your connection and try again.'); });
  });
})();

// F-186: text pasted on the For creators page before signing in comes back here, once, if it is less than an hour old.
(function () {
  var box = document.getElementById('ci-text');
  var link = document.getElementById('ci-link');
  var saved;
  try { saved = JSON.parse(localStorage.getItem('ga-paste') || 'null'); localStorage.removeItem('ga-paste'); } catch (err) { return; }
  if (!saved || !saved.text || Date.now() - saved.at > 3600000 || !box || box.value || (link && link.value)) return;
  if (/^https?:\/\/\S+$/i.test(saved.text.trim()) && link) link.value = saved.text.trim(); else box.value = saved.text;
})();
