/* Around you (F-073). A tap on a chip (or on "Use my location") asks the phone where it is, posts that with the chip to /trip/map/around and shows the cards
   that come back. The position lives in this page's variables for as long as the page is open: it is never written to storage, a link or a cookie. If the phone
   says no (or cannot), the request goes without it and the server answers for the day's hotel, and says so. */
(function () {
  var root = document.getElementById('ar');
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var ctx = $('ar-ctx'), results = $('ar-results'), loc = $('ar-loc');
  var cat = root.dataset.picked || '', mode = 'walk', pos = null, denied = false, asked = false, seq = 0;
  var PLACEHOLDER = loc.lastChild ? loc.lastChild.textContent : 'Tap a button to look nearby';

  function say(text) {
    // the pin icon stays; only the words change
    var node = loc.lastChild;
    if (node && node.nodeType === 3) node.textContent = text; else loc.appendChild(document.createTextNode(text));
  }
  function press(list, attr, value) {
    Array.prototype.forEach.call(list, function (b) { b.setAttribute('aria-pressed', b.dataset[attr] === value ? 'true' : 'false'); });
  }

  function locate(done) {
    if (!navigator.geolocation) { pos = null; denied = true; done(); return; }
    say('Asking your phone where you are…');
    navigator.geolocation.getCurrentPosition(function (p) {
      pos = { lat: p.coords.latitude, lon: p.coords.longitude }; denied = false; done();
    }, function () {
      pos = null; denied = true; done();
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
  }

  function search() {
    if (!cat) { say('Pick what you are looking for'); return; }
    var mine = ++seq;
    results.setAttribute('aria-busy', 'true');
    results.innerHTML = '';
    var busy = document.createElement('p');
    busy.className = 'ar-busy'; busy.id = 'ar-busy'; busy.setAttribute('role', 'status'); busy.textContent = 'Looking for places…';
    results.appendChild(busy);
    var fd = new FormData(ctx);
    fd.append('cat', cat); fd.append('mode', mode);
    if (pos) { fd.append('lat', String(pos.lat)); fd.append('lon', String(pos.lon)); } else if (denied) { fd.append('denied', '1'); }
    fetch(ctx.dataset.url, { method: 'POST', body: fd, credentials: 'same-origin' }).then(function (r) { return r.text(); }).then(function (html) {
      if (mine !== seq) return;
      results.innerHTML = html;
      results.setAttribute('aria-busy', 'false');
      var near = $('ar-near');
      say(near ? near.textContent.charAt(0).toUpperCase() + near.textContent.slice(1) : PLACEHOLDER);
    }).catch(function () {
      if (mine !== seq) return;
      results.innerHTML = '<p class="ar-empty" id="ar-error" role="alert">Couldn’t look up places just now. Check your connection and try again.</p>';
      results.setAttribute('aria-busy', 'false');
    });
  }

  function go() {
    if (!cat) { say('Pick what you are looking for'); return; }
    if (asked) { search(); return; }
    asked = true;
    locate(search);
  }

  Array.prototype.forEach.call(root.querySelectorAll('.ar-chip'), function (b) {
    b.addEventListener('click', function () {
      cat = b.dataset.cat;
      press(root.querySelectorAll('.ar-chip'), 'cat', cat);
      go();
    });
  });
  Array.prototype.forEach.call(root.querySelectorAll('.ar-mode'), function (b) {
    b.addEventListener('click', function () {
      mode = b.dataset.mode;
      press(root.querySelectorAll('.ar-mode'), 'mode', mode);
      if (cat && asked) search();
    });
  });
  $('ar-locate').addEventListener('click', function () {
    asked = true;
    locate(function () { if (cat) search(); else say(denied ? 'We could not use your location. Pick what you need and we will look near your hotel.' : 'Got it. Now pick what you need.'); });
  });
})();
