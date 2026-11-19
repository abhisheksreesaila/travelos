// The cover's first paint (F-266): html.cv-film, before anything is drawn, when the postcard will pin and travel (always, unless ?still, reduced motion or a screen under
// 35rem tall: then every beat is a card with its words under it, cover.css), so the page never jumps from the still to the film. gitaway/pages/cover.py inlines this
// file ahead of the markup; should assets/js/cover.js not have run by the time the page has loaded, the still stays.
(function () {
  var d = document.documentElement;
  if (!/[?&]still\b/.test(location.search) && !matchMedia('(prefers-reduced-motion: reduce)').matches && innerHeight >= 560) d.classList.add('cv-film');
  addEventListener('load', function () { if (!window.GA_COVER) d.classList.remove('cv-film'); });
})();
