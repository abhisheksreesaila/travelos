// The cover's first paint (F-206): day or night, and the calm stills under reduced motion, decided before anything is drawn.
// gitaway/pages/cover.py inlines this file at the top of <body>; assets/js/cover.js does the rest and reuses cvMode().
(function () {
  var d = document.documentElement, q = new URLSearchParams(location.search);
  // Day or night follows the site's own switch when it sets one (dark or light on <html> or <body>), else the system setting.
  window.cvMode = function () {
    var m = q.get('mode');
    if (m === 'dark' || m === 'light') return m;
    for (var n = [d, document.body], i = 0; i < 2; i++) {
      var e = n[i];
      if (!e) continue;
      var v = (e.getAttribute('data-theme') || e.getAttribute('data-mode') || e.getAttribute('data-color-scheme') || '').toLowerCase();
      if (v === 'dark' || v === 'light') return v;
      if (/(^|\s)(dark|theme-dark|oq-night)(\s|$)/.test(e.className)) return 'dark';
      if (/(^|\s)(light|theme-light|oq-light)(\s|$)/.test(e.className)) return 'light';
    }
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  };
  var still = q.has('still') || matchMedia('(prefers-reduced-motion: reduce)').matches;
  d.classList.add(window.cvMode() === 'dark' ? 'cv-dark' : 'cv-light', still ? 'cv-still' : 'cv-live');
})();
