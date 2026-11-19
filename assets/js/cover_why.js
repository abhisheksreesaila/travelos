// "Why another travel site?" (F-299): each card opens on its grey Elsewhere face and flips to GitAway by itself, about a second after it is well in view (cards that arrive together go one after
// another). One IntersectionObserver, no scroll handler, no frame loop, no layout read: the script only sets classes (.on on a card, data-d for its place in the batch); the hinge is CSS
// (assets/css/cover_why.css, only transform and opacity, times are the --cvt-* tokens). "Watch again" folds them all back and lets the observer run again. Without this script, with reduced
// motion, ?still or on a short screen (cover_boot.js adds html.cv-flip only when the flip should play) every card just shows its GitAway face.
(function () {
  var cards = [].slice.call(document.querySelectorAll('.wy-card'));
  if (!cards.length || !('IntersectionObserver' in window)) return;
  var batch = [], timer = 0;
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting || e.target.classList.contains('on')) return;
      io.unobserve(e.target);
      batch.push(e.target);
      clearTimeout(timer);
      timer = setTimeout(function () {      // a beat on Elsewhere, then the batch flips in order
        batch.forEach(function (c, k) { c.dataset.d = Math.min(k, 5); c.classList.add('on'); });
        batch = [];
      }, 900);
    });
  }, { threshold: .6 });
  function watch() { cards.forEach(function (c) { io.observe(c); }); }
  watch();
  var again = document.getElementById('why-again');
  if (again) again.addEventListener('click', function () {
    clearTimeout(timer); batch = [];
    cards.forEach(function (c) { io.unobserve(c); c.dataset.d = 0; c.classList.remove('on'); });
    setTimeout(watch, 500);
  });
  window.GA_WHY = { cards: function () { return cards.length; } };
})();
