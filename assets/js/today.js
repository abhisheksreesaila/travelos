// Today (F-287). Two small things, both on the page's own side.
// 1. "Use my location": only on a tap, the browser's position becomes a straight-line distance and a rough time to the hotel's coordinates (data-lat, data-lon). Nothing is sent
//    to the server, kept or logged: the position lives in this function and the sentence it writes.
// 2. On the planner, the Today card asks the service worker to keep the day's page ahead of time, so its codes and addresses show without signal (assets/sw.js "prefetch").
(function () {
  var EARTH_KM = 6371.0088, CITY_KMH = 30;

  function km(a, b) {      // haversine, in km
    var rad = Math.PI / 180, dLat = (b[0] - a[0]) * rad, dLon = (b[1] - a[1]) * rad;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * EARTH_KM * Math.asin(Math.min(1, Math.sqrt(h)));
  }
  function words(distKm) {
    var miles = /^en-(US|GB)$/.test(navigator.language || "") || !navigator.language;
    var d = miles ? distKm * 0.621371 : distKm, unit = miles ? "mi" : "km";
    var near = d < 0.1 ? "less than 0.1 " + unit : (d < 10 ? d.toFixed(1) : String(Math.round(d))) + " " + unit;
    var min = Math.max(1, Math.round(distKm / CITY_KMH * 60));
    return near + " away, as the crow flies. Roughly " + min + " min at city speed, and more by road.";
  }

  var btn = document.getElementById("td-locate"), out = document.getElementById("td-near");
  if (btn && out) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      if (!navigator.geolocation) { out.textContent = "This browser cannot tell us where you are."; return; }
      out.textContent = "Finding you…";
      navigator.geolocation.getCurrentPosition(function (p) {
        out.textContent = words(km([p.coords.latitude, p.coords.longitude], [parseFloat(btn.dataset.lat), parseFloat(btn.dataset.lon)]));
      }, function () {
        out.textContent = "Your location is off for this page, so there is nothing to measure. Nothing was sent.";
      }, { enableHighAccuracy: false, maximumAge: 60000, timeout: 10000 });
    });
  }

  var card = document.getElementById("td-card");
  if (card && card.dataset.today && "serviceWorker" in navigator) {
    navigator.serviceWorker.ready.then(function (reg) {
      if (reg.active) reg.active.postMessage({ type: "prefetch", url: card.dataset.today });
    }).catch(function () {});
  }
})();
