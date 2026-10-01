/* Registers the service worker (F-044) and forgets the saved pages when a traveler signs out. */
(function () {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
  });
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form && form.getAttribute && form.getAttribute("action") === "/signout" && window.caches) {
      caches.keys().then(function (names) {
        names.filter(function (n) { return n.indexOf("ga-pages-") === 0; }).forEach(function (n) { caches.delete(n); });
      });
    }
  });
})();
