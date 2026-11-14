/* D-460 (F-200 before it): light by default, dark when the person picks it, remembered on this device. Loaded without defer in the head (layout.HEAD) so a
   remembered dark is on <html> before the first paint: no flash. The server draws html[data-mode="light"] (main.py), which tokens.css's system-dark block
   steps aside for, so the site is light whatever the system says. The switch is any [data-mode-toggle] button (layout.mode_switch()): pressed when dark.
   The browser bar's colour (theme-color) follows. */
(function () {
  var KEY = 'ga-mode', root = document.documentElement;
  function stored() { try { return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light'; } catch (e) { return 'light'; } }
  function apply(m) {
    root.setAttribute('data-mode', m);
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    for (var i = 0; i < metas.length; i++) metas[i].setAttribute('content', m === 'dark' ? '#000000' : '#F2F2F5');
    var t = document.querySelectorAll('[data-mode-toggle]');
    for (var j = 0; j < t.length; j++) t[j].setAttribute('aria-pressed', m === 'dark' ? 'true' : 'false');
  }
  apply(stored());
  document.addEventListener('DOMContentLoaded', function () { apply(stored()); });
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-mode-toggle]');
    if (!b) return;
    var m = root.getAttribute('data-mode') === 'dark' ? 'light' : 'dark';
    try { if (m === 'dark') localStorage.setItem(KEY, m); else localStorage.removeItem(KEY); } catch (err) { /* not stored: it still applies to this page */ }
    apply(m);
  });
  window.addEventListener('storage', function (e) { if (e.key === KEY) apply(stored()); });   // another tab changed it
  window.addEventListener('pageshow', function () { apply(stored()); });                     // a page restored from the back-forward cache
})();
