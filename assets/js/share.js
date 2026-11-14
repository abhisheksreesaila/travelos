// Share to Instagram (F-234). The cockpit's "Share to Instagram" is a link to /trip/share (a page that works with no script); with this script a tap fetches the
// sheet as a fragment (X-Share: 1) and grows it out of the button (GA.motion.open: a laptop gets the calm fade, reduced motion nothing), then the card tilts into place and
// its confetti bursts out (phone only: GA.motion.run keeps just the fades on a laptop).
//
// In the sheet: the two switches (first names, exact dates) post themselves and the preview picture swaps to the new card; Share hands the PNG to the phone's share sheet
// (navigator.share with files, so Instagram's Stories and Feed are in it); Download saves it (a plain link: laptops, and the fallback everywhere); Copy link copies the page
// the card points at. The picture is fetched ahead of the tap (a share must start inside the tap's user activation). Escape, the scrim and the close button fold it back.
(function () {
  var btn = document.getElementById('sh-open');
  if (!btn || !window.GA || !GA.motion) return;
  var MO = GA.motion, root = document.documentElement, reducedQ = window.matchMedia('(prefers-reduced-motion: reduce)');
  var wrap = null, box = null, blob = null, blobFor = '', frag = null, state = null;

  function get() {
    if (!frag) frag = fetch('/trip/share', { headers: { 'X-Share': '1' }, credentials: 'same-origin' }).then(function (r) { if (!r.ok) throw new Error('share'); return r.text(); });
    return frag;
  }
  btn.addEventListener('pointerdown', function () { get().catch(function () { frag = null; }); }, { passive: true });

  btn.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || wrap) return;
    e.preventDefault();
    btn.setAttribute('aria-expanded', 'true');
    get().then(open, function () { btn.setAttribute('aria-expanded', 'false'); window.location.href = btn.href; });
  });

  function open(html) {
    frag = null;      // the next open asks again: always the freshest choices and link
    wrap = document.createElement('div');
    wrap.className = 'sh-sheet sh-live-script';
    wrap.innerHTML = '<div class="sh-scrim" data-close="1"></div><div class="sh-box" role="dialog" aria-modal="true" aria-labelledby="sh-title" tabindex="-1">' + html + '</div>';
    box = wrap.querySelector('.sh-box');
    document.body.appendChild(wrap);
    root.classList.add('sh-open');
    state = { link: wrap.querySelector('.sh-body').dataset.link };
    wire();
    var scrim = wrap.querySelector('.sh-scrim');
    var grown = reducedQ.matches ? Promise.resolve() : MO.open(box, btn, { scrim: scrim });
    grown.then(settle);
    box.focus({ preventScroll: true });
    prefetch();
  }

  function settle() {      // the card lands a hair crooked, like a print, and the confetti bursts (a laptop: only the fades are kept)
    if (reducedQ.matches || !wrap) return;
    var img = wrap.querySelector('.sh-img');
    MO.run(img, [{ transform: 'rotate(-3deg) scale(.94)', opacity: .4 }, { transform: 'rotate(0) scale(1)', opacity: 1 }], { t: 'spring', ease: 'spring' });
    Array.prototype.forEach.call(wrap.querySelectorAll('.sh-dot'), function (d, i) {
      var a = (i / 12) * Math.PI * 2, r = 70 + (i % 3) * 22;
      MO.run(d, [{ transform: 'translate(' + (-Math.cos(a) * r) + 'px,' + (-Math.sin(a) * r) + 'px) scale(.2)', opacity: 0 }, { transform: 'none', opacity: 1 }], { t: 'spring', ease: 'spring' });
    });
  }

  function wire() {
    if (!wrap.dataset.wired) {      // (wire runs again when "Create link" swaps the sheet's contents: the sheet's own listeners are added once)
      wrap.dataset.wired = '1';
      wrap.addEventListener('click', function (e) {
        if (e.target.closest('[data-close]')) close();
      });
      wrap.addEventListener('change', function (e) { if (e.target.classList.contains('sh-cb')) update(); });
    }
    var make = wrap.querySelector('#sh-make');
    if (make) { make.addEventListener('submit', create); return; }      // a trip that is not shared: one button
    wrap.querySelector('#sh-form').addEventListener('submit', function (e) { e.preventDefault(); update(); });
    wrap.querySelector('#sh-copy').addEventListener('click', copy);
    wrap.querySelector('#sh-off').addEventListener('submit', stop);
    var share = wrap.querySelector('#sh-share');
    share.addEventListener('click', send);
    if (navigator.share && navigator.canShare) share.hidden = false;      // (hidden again if this device cannot share a file: see prefetch)
  }

  function create(e) {      // "Create link": make the share, then show the sheet it makes
    e.preventDefault();
    fetch('/trip/share', { method: 'POST', headers: { 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' }, body: '', credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error('save'); return fetch('/trip/share', { headers: { 'X-Share': '1' }, credentials: 'same-origin' }); })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        if (!wrap) return;
        box.innerHTML = html;
        state = { link: box.querySelector('.sh-body').dataset.link };
        wire();
        settle();
        prefetch();
      }, function () { say('Could not create the link. Try again.'); });
  }

  function say(text) { var n = wrap && wrap.querySelector('#sh-live'); if (n) n.textContent = text; }

  function prefetch() {      // the PNG in hand before the tap, so navigator.share runs inside the tap
    var img = wrap && wrap.querySelector('#sh-img');
    if (!img) return;
    var src = img.getAttribute('src');
    blob = null; blobFor = src;
    fetch(src).then(function (r) { return r.blob(); }).then(function (b) {
      if (blobFor !== src) return;
      blob = new File([b], 'trip-card.png', { type: 'image/png' });
      var share = wrap && wrap.querySelector('#sh-share');
      if (share && navigator.canShare && !navigator.canShare({ files: [blob] })) share.hidden = true;
    }).catch(function () {});
  }

  function update() {
    var form = wrap.querySelector('#sh-form'), card = wrap.querySelector('.sh-card');
    var body = new URLSearchParams();
    ['names', 'exact'].forEach(function (n) { if (form.elements[n] && form.elements[n].checked) body.set(n, '1'); });
    card.setAttribute('data-busy', '1');
    fetch('/trip/share', { method: 'POST', headers: { 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' }, body: body.toString(), credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error('save'); return r.json(); })
      .then(function (j) {
        var img = wrap.querySelector('#sh-img'), done = function () { card.removeAttribute('data-busy'); };
        img.onload = done; img.onerror = done;
        img.src = j.card;
        wrap.querySelector('#sh-dl').href = j.card;
        wrap.querySelector('#sh-link').value = j.link;
        state.link = j.link;
        prefetch();
      }, function () { card.removeAttribute('data-busy'); say('Could not update the card. Try again.'); });
  }

  function send() {
    var text = wrap.querySelector('.sh-card img').alt.replace(/^Your trip card: /, '') + '\n' + state.link;
    if (!blob) { say('One moment, the card is still loading.'); return; }
    navigator.share({ files: [blob], title: 'Our trip', text: text }).catch(function (err) {
      if (err && err.name !== 'AbortError') say('Sharing did not work here. Download the card instead.');
    });
  }

  function copy() {
    var done = function () { say('Link copied.'); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(state.link).then(done, fallback); else fallback();
    function fallback() { var f = wrap.querySelector('#sh-link'); f.focus(); f.select(); try { document.execCommand('copy'); done(); } catch (e) { say('Press and hold the link to copy it.'); } }
  }

  function stop(e) {
    e.preventDefault();
    fetch('/trip/share/off', { method: 'POST', headers: { 'Accept': 'application/json' }, credentials: 'same-origin' }).then(function () { close(); }, function () { say('Could not turn it off. Try again.'); });
  }

  function close() {
    if (!wrap) return;
    var w = wrap, b = box;
    wrap = null; box = null; blob = null;
    var done = function () { w.remove(); root.classList.remove('sh-open'); btn.setAttribute('aria-expanded', 'false'); btn.focus({ preventScroll: true }); };
    if (reducedQ.matches) done(); else MO.close(b, btn, { scrim: w.querySelector('.sh-scrim') }).then(done);
  }

  document.addEventListener('keydown', function (e) {
    if (!wrap) return;
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key !== 'Tab') return;
    var stops = Array.prototype.filter.call(wrap.querySelectorAll('button, a[href], input, [tabindex]:not([tabindex="-1"])'), function (n) { return !n.hidden && n.getClientRects().length && !n.classList.contains('sr-only'); });
    if (!stops.length) return;
    var first = stops[0], last = stops[stops.length - 1], at = document.activeElement;
    if (e.shiftKey && (at === first || !wrap.contains(at) || at === box)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (at === last || !wrap.contains(at))) { e.preventDefault(); first.focus(); }
  });
})();
