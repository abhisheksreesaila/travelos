/* Registers the service worker (F-044) and forgets the saved pages when a traveler signs out. */
(function () {
  /* F-116: the Today tab goes straight back to the day (or week) last shown in this visit, not through /trip's redirect: one trip to the server less, and the
     service worker can open it at once from its saved copy. A new visit (the app started again) still asks /trip for today. */
  try {
    var today = sessionStorage.getItem("ga-today");
    if (today && /^\/trip\/canvas(\?[^#]*)?$/.test(today)) document.querySelectorAll('#ph-tab-today, a.ph-back[href="/trip"]').forEach(function (a) { a.setAttribute("href", today); });
  } catch (e) { /* no storage: the tab keeps /trip */ }
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
  /* F-099: a finger touching a link starts loading its page; the service worker keeps the copy for a few seconds and answers the tap with it.
     Plain same-site page links only: not the trip canvas's zoom links (it loads those itself), new tabs, downloads, sign-in or sign-out routes. */
  var AUTH = /^\/(login|logout|signin|signout|auth)(\/|$)/;
  var touched = {};
  function prefetchable(a) {
    if (!a || !a.href || a.target || a.hasAttribute("download") || a.hasAttribute("data-zoom") || a.getAttribute("href").charAt(0) === "#") return null;
    var rel = a.getAttribute("rel") || "";
    if (/\bexternal\b/.test(rel)) return null;
    var u;
    try { u = new URL(a.href, location.href); } catch (x) { return null; }
    if (u.origin !== location.origin || AUTH.test(u.pathname) || u.pathname.indexOf("/assets/") === 0) return null;
    if (u.pathname === location.pathname && u.search === location.search) return null;
    return u.pathname + u.search;
  }
  document.addEventListener("pointerdown", function (e) {
    var ctl = navigator.serviceWorker.controller;
    var c = navigator.connection;
    if (!ctl || (c && c.saveData) || (e.pointerType === "mouse" && e.button !== 0)) return;
    var url = prefetchable(e.target && e.target.closest ? e.target.closest("a") : null);
    var now = Date.now();
    if (!url || (touched[url] && now - touched[url] < 2000)) return;
    touched[url] = now;
    ctl.postMessage({ type: "prefetch", url: url });
  }, { passive: true });
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form && form.getAttribute && form.getAttribute("action") === "/signout" && window.caches) {
      forgetPages();
    }
  });
})();
