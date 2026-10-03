/* The Morning plan card on the phone Today view (F-066). The server draws the card in its "add to the Home Screen" state; this decides
   which part shows, because only the browser knows whether it can push:
     install   no push here (an iPhone's browser tab, an old browser): explain how to add GitAway to the Home Screen
     off / on  the switch, and when on the time picker
     blocked   the person said no to notifications: say where to turn them on
   Turning it on is always the person's own tap (that tap is what makes iPhone ask for permission, once). The keys are the page's
   data-key (the server's public key); the push service's address and keys go to /trip/morning in the body, never the URL. */
(function () {
  "use strict";
  var card = document.getElementById("tp-morning");
  if (!card) return;
  var $ = function (id) { return document.getElementById(id); };
  var sw = $("tp-morning-switch"), timeRow = $("tp-morning-timerow"), time = $("tp-morning-time"), install = $("tp-morning-install");
  var blocked = $("tp-morning-blocked"), error = $("tp-morning-error"), sub = $("tp-morning-sub");
  var reg = null, subscription = null, busy = false, quiet = false;

  function show(el, on) { if (el) el.hidden = !on; }
  function clock(v) {
    var m = /^(\d\d):(\d\d)/.exec(v || ""); if (!m) return "";
    var h = +m[1];
    return (h % 12 || 12) + ":" + m[2] + " " + (h < 12 ? "AM" : "PM");
  }
  function set(state, t) {
    card.setAttribute("data-state", state);
    var on = state === "on";
    show(install, state === "install");
    show(sw, state === "on" || state === "off" || state === "blocked");
    show(blocked, state === "blocked");
    show(timeRow, on);
    sw.setAttribute("aria-checked", on ? "true" : "false");
    sw.classList.toggle("is-on", on);
    if (t && time && time.value !== t) { quiet = true; time.value = t; time.dispatchEvent(new Event("change", { bubbles: true })); quiet = false; }
    if (sub) sub.textContent = on ? "On: you will get today's plan at " + clock(time.value) : "Today's plan on your phone each trip morning";
  }
  function fail(message) { error.textContent = message; show(error, !!message); }

  function post(path, data) {
    return fetch(path, { method: "POST", body: new URLSearchParams(data), credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j && j.error || "Something went wrong."); return j; }); });
  }
  function keyBytes(b64) {
    var s = (b64 + "====".slice(b64.length % 4)).replace(/-/g, "+").replace(/_/g, "/"), raw = atob(s), out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  function keyChanged(s) {
    var have = s.options && s.options.applicationServerKey;
    if (!have) return false;
    var a = new Uint8Array(have), b = keyBytes(card.getAttribute("data-key"));
    if (a.length !== b.length) return true;
    for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return true;
    return false;
  }

  // An iPhone only pushes from a web app on the Home Screen; elsewhere the browser either has no PushManager or cannot be relied on.
  var apple = /iPhone|iPad|iPod/.test(navigator.userAgent);
  var possible = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window && !(apple && navigator.standalone !== true);
  if (!possible) { set("install"); return; }

  var ready = Promise.race([navigator.serviceWorker.ready, new Promise(function (_, no) { setTimeout(no, 5000); })]);
  ready.then(function (r) {
    reg = r;
    return r.pushManager.getSubscription();
  }).then(function (s) {
    subscription = s;
    if (!s) return set(window.Notification.permission === "denied" ? "blocked" : "off");
    if (keyChanged(s)) return turnOff();  // subscribed under other server keys (they were replaced): it can never be pushed to, so drop it; the next tap makes a fresh one
    return post("/trip/morning/status", { endpoint: s.endpoint }).then(function (j) { set(j.on ? "on" : "off", j.time); });
  }).catch(function () { if (!reg) set("install"); else set("off"); });

  function turnOn() {
    var permission = window.Notification.permission === "granted" ? Promise.resolve("granted") : window.Notification.requestPermission();
    return Promise.resolve(permission).then(function (p) {
      if (p !== "granted") { set("blocked"); return; }
      return (subscription ? Promise.resolve(subscription) : reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(card.getAttribute("data-key")) })).then(function (s) {
        subscription = s;
        var k = s.toJSON().keys || {};
        return post("/trip/morning", { endpoint: s.endpoint, p256dh: k.p256dh || "", authkey: k.auth || "", time: time.value || "07:30" }).then(function (j) { set("on", j.time); });
      });
    });
  }
  function turnOff() {
    var s = subscription;
    subscription = null;
    return (s ? post("/trip/morning/off", { endpoint: s.endpoint }).catch(function () {}).then(function () { return s.unsubscribe().catch(function () {}); }) : Promise.resolve()).then(function () { set("off"); });
  }

  sw.addEventListener("click", function () {
    if (busy || !reg) return;
    busy = true; fail("");
    (card.getAttribute("data-state") === "on" ? turnOff() : turnOn())
      .catch(function (e) { fail(e && e.message || "Could not change the morning plan."); if (card.getAttribute("data-state") !== "on") set("off"); })
      .then(function () { busy = false; });
  });
  time.addEventListener("change", function () {
    if (quiet || !subscription || card.getAttribute("data-state") !== "on" || !time.value) return;
    fail("");
    post("/trip/morning/time", { endpoint: subscription.endpoint, time: time.value }).then(function (j) { set("on", j.time); }).catch(function (e) { fail(e.message); });
  });
})();
