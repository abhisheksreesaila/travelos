/* The Family tab's thread (F-070). The server draws the page with what exists; this keeps it live and sends from the compose bar:
     - every data-poll milliseconds (5 s) while the page is visible it asks /trip/family/thread?since=<last> for new items and appends them;
       a hidden page does not ask, and asks once as soon as it is shown again;
     - Send posts the message with fetch (X-Fragment: 1) and appends what is new, so a message shows at once; without script the form posts and reloads;
     - the Quiet switch posts its own state and changes in place.
   Items are only ever added (the server never edits or removes one), so a response is appended after the last item already here. */
(function () {
  "use strict";
  var thread = document.getElementById("ft-thread");
  if (!thread) return;
  var $ = function (id) { return document.getElementById(id); };
  var empty = $("ft-empty"), form = $("ft-compose"), text = $("ft-text"), error = $("ft-error"), send = $("ft-send");
  function tripId() { return thread.getAttribute("data-trip") || ""; }
  var interval = parseInt(thread.getAttribute("data-poll"), 10) || 5000;
  var last = parseInt(thread.getAttribute("data-last"), 10) || 0;
  var timer = null, inflight = false;
  var pollUrl = thread.getAttribute("data-poll-url") || "/trip/family/thread";   // a plan's chat (F-091) polls its own address
  function join(url) { return url + (url.indexOf("?") < 0 ? "?" : "&"); }

  function nearBottom() { return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 160; }
  function toBottom() { window.scrollTo(0, document.documentElement.scrollHeight); }
  function fail(message) { error.textContent = message || ""; error.hidden = !message; }

  function append(response, mine) {
    var n = parseInt(response.headers.get("X-Thread-Last"), 10) || 0;
    return response.text().then(function (html) {
      if (!html.trim() || n <= last) return;
      var stick = mine || nearBottom();
      var holder = document.createElement("div");
      holder.innerHTML = html;
      Array.prototype.forEach.call(holder.children, function (el) {
        var id = parseInt(el.getAttribute("data-n"), 10) || 0;
        if (id <= last) return;
        el.classList.add("is-new");
        thread.appendChild(el);
      });
      last = n;
      thread.setAttribute("data-last", String(last));
      if (empty) empty.hidden = true;
      if (stick) toBottom();
    });
  }

  function poll(mine) {
    if (inflight || document.visibilityState === "hidden") return Promise.resolve();
    inflight = true;
    return fetch(join(pollUrl) + "since=" + last + "&trip=" + encodeURIComponent(tripId()), { credentials: "same-origin", headers: { Accept: "text/html" } })
      .then(function (r) { if (r.status === 409) { stop(); fail("This trip changed. Reload the page."); return; } if (r.ok) return append(r, mine === true); })
      .catch(function () {})
      .then(function () { inflight = false; });
  }

  function start() { if (!timer) timer = setInterval(poll, interval); }
  function stop() { if (timer) { clearInterval(timer); timer = null; } }
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") { stop(); return; }
    poll(); start();
  });
  if (document.visibilityState !== "hidden") start();
  toBottom();
  // The chat's own script (plantalk.js) fires this after it sent a photo or a voice note: show what is new now, and scroll to it.
  thread.addEventListener("ft-refresh", function () { inflight = false; poll(true); });

  if (form) form.addEventListener("submit", function (e) {
    e.preventDefault();
    var value = text.value.trim();
    if (!value) { fail("Write something first."); return; }
    fail("");
    send.disabled = true;
    var fields = new URLSearchParams(new FormData(form));   // text, trip and (a plan's chat) act and part
    fields.set("since", String(last));
    fetch(form.getAttribute("action") || "/trip/family/message", { method: "POST", credentials: "same-origin", headers: { "X-Fragment": "1" }, body: fields })
      .then(function (r) {
        if (!r.ok) return r.text().then(function (t) { throw new Error(r.status === 400 || r.status === 409 ? t : "That did not send. Try again."); });
        text.value = "";
        return append(r, true);
      })
      .catch(function (err) { fail(err instanceof TypeError || !err.message || err.message.length > 120 ? "That did not send. Try again." : err.message); })
      .then(function () { send.disabled = false; text.focus(); });
  });

  var quiet = $("ft-quiet"), quietValue = $("ft-quiet-value"), quietText = $("ft-quiet-text");
  if (quiet) quiet.closest("form").addEventListener("submit", function (e) {
    e.preventDefault();
    var wanted = quietValue.value;
    quiet.disabled = true;
    fetch("/trip/family/quiet", { method: "POST", credentials: "same-origin", headers: { "X-Fragment": "1" }, body: new URLSearchParams({ quiet: wanted }) })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (j) {
        quiet.setAttribute("aria-checked", j.quiet ? "true" : "false");
        quiet.classList.toggle("is-on", j.quiet);
        quietValue.value = j.quiet ? "0" : "1";
        quietText.textContent = j.quiet ? quietText.getAttribute("data-on") : quietText.getAttribute("data-off");
        fail("");
      })
      .catch(function () { fail("That did not save. Try again."); })
      .then(function () { quiet.disabled = false; });
  });
})();
