/* Registers the service worker (F-044) and forgets the saved pages when a traveler signs out. */
(function () {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
  });
  /* Safari ignores Clear-Site-Data, so a signed-out page (no ga-user key) also forgets any saved pages left on this device. */
  function forgetPages() {
    if (!window.caches) return;
    caches.keys().then(function (names) {
      names.filter(function (n) { return n.indexOf("ga-pages-") === 0; }).forEach(function (n) { caches.delete(n); });
    });
  }
  if (!document.querySelector('meta[name="ga-user"]')) forgetPages();
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form && form.getAttribute && form.getAttribute("action") === "/signout" && window.caches) {
      forgetPages();
    }
  });
})();
