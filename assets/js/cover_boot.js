// The cover's first paint (F-206, cover v3): day or night, and calm under reduced motion, decided before anything is drawn.
// gitaway/pages/cover.py inlines this file in <head>; assets/js/cover.js does the rest and reuses cvMode().
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
  var calm = q.has('still') || matchMedia('(prefers-reduced-motion: reduce)').matches;
  // cv-run: the reveals start hidden and the booking tour pins, from the first paint (no flash of the story fading out); should cover.js not
  // have run by the time the page has loaded, everything simply shows
  d.classList.add(window.cvMode() === 'dark' ? 'cv-dark' : 'cv-light', 'cv-run');
  if (calm) d.classList.add('cv-calm');
  addEventListener('load', function () { if (!window.GA_COVER) d.classList.remove('cv-run'); });
})();
