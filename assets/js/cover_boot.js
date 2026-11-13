// The cover's first paint (F-227): html.cv-film, before anything is drawn, when the frame will pin and swap its screens (always, unless ?still;
// under reduced motion the swap is a plain fade, cover.css), so the page never jumps from the still to the film. gitaway/pages/cover.py inlines
// this file in <head>; should assets/js/cover.js not have run by the time the page has loaded, the still stays.
(function () {
  var d = document.documentElement;
  if (!/[?&]still\b/.test(location.search)) d.classList.add('cv-film');
  addEventListener('load', function () { if (!window.GA_COVER) d.classList.remove('cv-film'); });
})();
