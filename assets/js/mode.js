/* F-200: light, dark or the system's (auto), remembered on this device. Loaded without defer in the head (layout.HEAD) so the remembered choice is on <html> before the
   first paint: no flash of the other mode. tokens.css holds both palettes: dark follows prefers-color-scheme unless html[data-mode] says light or dark.
   The switch is any [data-mode-pick] button (layout.mode_switch(): Auto, Light, Dark); its state is aria-pressed. The browser bar's colour (theme-color) follows the choice. */
(function () {
  var KEY = 'ga-mode', root = document.documentElement;
  function stored() { try { var m = localStorage.getItem(KEY); return m === 'light' || m === 'dark' ? m : ''; } catch (e) { return ''; } }
  function apply(m) {
    if (m) root.setAttribute('data-mode', m); else root.removeAttribute('data-mode');
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    for (var i = 0; i < metas.length; i++) {
      var meta = metas[i];
      if (!meta.hasAttribute('data-c')) meta.setAttribute('data-c', meta.getAttribute('content'));
      meta.setAttribute('content', m ? (m === 'dark' ? '#000000' : '#F2F2F5') : meta.getAttribute('data-c'));
    }
    var picks = document.querySelectorAll('[data-mode-pick]');
    for (var j = 0; j < picks.length; j++) picks[j].setAttribute('aria-pressed', picks[j].getAttribute('data-mode-pick') === (m || 'auto') ? 'true' : 'false');
  }
  apply(stored());
  document.addEventListener('DOMContentLoaded', function () { apply(stored()); });
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-mode-pick]');
    if (!b) return;
    var m = b.getAttribute('data-mode-pick');
    m = m === 'light' || m === 'dark' ? m : '';
    try { if (m) localStorage.setItem(KEY, m); else localStorage.removeItem(KEY); } catch (err) { /* not stored: it still applies to this page */ }
    apply(m);
  });
  window.addEventListener('storage', function (e) { if (e.key === KEY) apply(stored()); });   // another tab changed it
  window.addEventListener('pageshow', function () { apply(stored()); });                     // a page restored from the back-forward cache
})();
