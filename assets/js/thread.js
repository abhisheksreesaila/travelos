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
      Array.prototype.slice.call(holder.children).forEach(function (el) {   // a copy: appending moves each child out of the live list
        var id = parseInt(el.getAttribute("data-n"), 10) || 0;
        if (id <= last) return;
        if (!(mine && el.classList.contains("ft-me"))) el.classList.add("is-new");
        thread.appendChild(el);
      });
      last = n;
      thread.setAttribute("data-last", String(last));
      if (empty) empty.hidden = true;
      if (stick) toBottom();
    });
  }

  function poll(mine) {
    if (inflight || sending > 0 || document.visibilityState === "hidden") return Promise.resolve();
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

  // F-094: Send shows the bubble at once, from the text typed (quiet "Sending" state), and the server's answer replaces it in place. A failed
  // send keeps the bubble, says so and offers Retry with the same text. Sends go one after another so they keep their order; polls wait while one is out.
  var sending = 0, chain = Promise.resolve();
  function pendingBubble(value) {
    var el = document.createElement("div");
    el.className = "ft-msg ft-me is-pending is-sending";
    var bub = document.createElement("div"); bub.className = "ft-bub";
    var body = document.createElement("span"); body.className = "ft-body"; body.textContent = value;
    var state = document.createElement("span"); state.className = "ft-time ft-state"; state.textContent = "Sending";
    bub.appendChild(body); bub.appendChild(state); el.appendChild(bub);
    el.setAttribute("data-text", value);
    return el;
  }
  function settle(el, ok, message) {
    var state = el.querySelector(".ft-state"), old = el.querySelector(".ft-retry");
    if (old) old.remove();
    el.classList.toggle("is-sending", ok === null);
    el.classList.toggle("is-failed", ok === false);
    if (ok === null) { state.textContent = "Sending"; return; }
    state.textContent = message || "Not sent";
    var retry = document.createElement("button");
    retry.type = "button"; retry.className = "ft-retry"; retry.textContent = "Retry";
    retry.addEventListener("click", function () { deliver(el); });
    state.after(retry);
  }
  function deliver(el) {
    settle(el, null);
    sending += 1;
    chain = chain.then(function () {
      var fields = new URLSearchParams(new FormData(form));   // trip and (a plan's chat) act and part
      fields.set("text", el.getAttribute("data-text"));
      fields.set("since", String(last));
      return fetch(form.getAttribute("action") || "/trip/family/message", { method: "POST", credentials: "same-origin", headers: { "X-Fragment": "1" }, body: fields })
        .then(function (r) {
          if (!r.ok) return r.text().then(function (t) { throw new Error(r.status === 400 || r.status === 409 ? t : ""); });
          el.remove();                                   // the server's own bubble takes its place (no second fade)
          return append(r, true);
        })
        .catch(function (err) { settle(el, false, err instanceof TypeError || !err.message || err.message.length > 120 ? "" : err.message); if (!el.parentNode) thread.appendChild(el); })
        .then(function () { sending -= 1; });
    });
  }
  if (form) form.addEventListener("submit", function (e) {
    e.preventDefault();
    var value = text.value.trim();
    if (!value) { fail("Write something first."); return; }
    fail("");
    var el = pendingBubble(value);
    el.classList.add("is-new");
    thread.appendChild(el);
    if (empty) empty.hidden = true;
    text.value = "";
    text.focus();
    toBottom();
    deliver(el);
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
