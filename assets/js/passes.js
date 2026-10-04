/* The gate view (F-083): the slides are a CSS scroll-snap strip, so swiping works with no script at all, and `#gp-<pass id>` starts on one person.
   This adds what a finger cannot do alone: the arrows and dots move one person, the dots and "2 of 4" follow the swipe, the arrow keys work, and the screen is
   kept awake (Screen Wake Lock, where the browser has it) so it does not dim in the agent's hand. The browser cannot turn the brightness up; the page says so. */
(function () {
  "use strict";
  var track = document.getElementById("gp-track");
  if (!track) return;
  var slides = Array.prototype.slice.call(track.querySelectorAll(".gp-slide"));
  var dots = Array.prototype.slice.call(document.querySelectorAll(".gp-dot"));
  var count = document.getElementById("gp-count");
  var prev = document.getElementById("gp-prev"), next = document.getElementById("gp-next");
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var current = 0;

  function indexNow() {
    var w = track.clientWidth || 1;
    return Math.max(0, Math.min(slides.length - 1, Math.round(track.scrollLeft / w)));
  }

  function show(i) {
    current = i;
    dots.forEach(function (d, n) { d.setAttribute("aria-current", n === i ? "true" : "false"); });
    if (count && slides.length > 1) count.textContent = (i + 1) + " of " + slides.length + " · swipe for the next person";
    if (prev) prev.disabled = i === 0;
    if (next) next.disabled = i === slides.length - 1;
  }

  function go(i) {
    i = Math.max(0, Math.min(slides.length - 1, i));
    track.scrollTo({ left: i * track.clientWidth, behavior: reduce ? "auto" : "smooth" });
    show(i);
  }

  var timer = null;
  track.addEventListener("scroll", function () {
    clearTimeout(timer);
    timer = setTimeout(function () { show(indexNow()); }, 60);
  }, { passive: true });
  if (prev) prev.addEventListener("click", function () { go(current - 1); });
  if (next) next.addEventListener("click", function () { go(current + 1); });
  dots.forEach(function (d, n) { d.addEventListener("click", function () { go(n); }); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "ArrowRight") { e.preventDefault(); go(current + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(current - 1); }
  });

  var hash = (location.hash || "").slice(1);
  var start = slides.findIndex(function (s) { return s.id === hash; });
  if (start > 0) track.scrollTo({ left: start * track.clientWidth, behavior: "auto" });
  show(start > 0 ? start : indexNow());

  function keepAwake() {
    try {
      if (navigator.wakeLock && navigator.wakeLock.request) navigator.wakeLock.request("screen").catch(function () {});
    } catch (e) {}
  }
  keepAwake();
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") keepAwake(); });
  window.addEventListener("resize", function () { go(current); });
})();
