/* The Family tab's thread (F-070). The server draws the page with what exists; this keeps it live and sends from the compose bar:
     - every data-poll milliseconds (5 s) while the page is visible it asks /trip/family/thread?since=<last> for new items and appends them;
       a hidden page does not ask, and asks once as soon as it is shown again;
     - Send shows the bubble at once and posts the message with fetch (X-Fragment: 1); without script the form posts and reloads;
     - the Quiet switch posts its own state and changes in place.
   Items are only ever added (the server never edits or removes one), so a response is appended after the last item already here. */
(function () {
  "use strict";
  var thread = document.getElementById("ft-thread");
  if (!thread) return;
  var root = document.getElementById("ft");
  var $ = function (id) { return document.getElementById(id); };
  // F-106: in a plan's card this script is bound again for each card; the listeners on the window, the visual viewport and the document, and the timer, are taken off when the card closes
  // (its #ft gets "ft-close") or the chat is found gone. window.__ftBound counts the chats bound now, for the tests.
  var counts = window.__ftBound = window.__ftBound || { thread: 0, plantalk: 0 };
  counts.thread++;
  var undo = [];
  function listen(target, type, fn, opt) { target.addEventListener(type, fn, opt); undo.push(function () { target.removeEventListener(type, fn, opt); }); }
  var unbound = false;
  function teardown() {
    if (unbound) return;
    unbound = true;
    counts.thread--;
    undo.forEach(function (f) { f(); });
    undo = [];
    stop();
  }
  var empty = $("ft-empty"), form = $("ft-compose"), text = $("ft-text"), error = $("ft-error");
  function tripId() { return thread.getAttribute("data-trip") || ""; }
  var interval = parseInt(thread.getAttribute("data-poll"), 10) || 5000;
  var last = parseInt(thread.getAttribute("data-last"), 10) || 0;
  var timer = null, inflight = false;
  var pollUrl = thread.getAttribute("data-poll-url") || "/trip/family/thread";   // a plan's chat (F-091) polls its own address
  function sendTimeout() { return parseInt(thread.getAttribute("data-send-timeout"), 10) || 15000; }   // a request that never answers ends as a failed send
  function join(url) { return url + (url.indexOf("?") < 0 ? "?" : "&"); }

  // F-100: on the phone the message list scrolls on its own (the box is docked under it); elsewhere the page scrolls.
  function docked() { return window.getComputedStyle(thread).overflowY === "auto"; }
  function scroller() { return thread; }
  function nearBottom() {
    if (docked()) { var sc = scroller(); return sc.scrollHeight - sc.scrollTop - sc.clientHeight < 160; }
    return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 160;
  }
  function toBottom() {
    if (docked()) { var sc = scroller(); sc.scrollTop = sc.scrollHeight; return; }
    window.scrollTo(0, document.documentElement.scrollHeight);
  }
  // A photo that finishes loading under the newest message must not push it out of view.
  var stuck = true;
  scroller().addEventListener("scroll", function () { stuck = nearBottom(); }, { passive: true });
  thread.addEventListener("load", function () { if (stuck) toBottom(); }, true);
  window.addEventListener("load", function () { toBottom(); });

  // F-100: the iPhone keyboard shrinks the visual viewport, not the page. The docked column follows it (--vvh, --vvtop), the tab bar steps aside
  // (.kb-open) and the newest message stays in view above the box. `reference` is the tallest the viewport has been.
  // The reference is kept per width: a rotation or a resized window starts it again, and a shrink counts as the keyboard only while a field has focus
  // and the page is not pinch-zoomed.
  var vv = window.visualViewport, app = document.querySelector(".tp"), reference = window.innerHeight, refWidth = window.innerWidth;
  function typing() { var a = document.activeElement; return !!a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA" || a.isContentEditable); }
  function fit() {
    if (!vv || !app) return;
    var root = document.documentElement.style;
    if (!docked()) { app.classList.remove("kb-open"); root.removeProperty("--vvh"); root.removeProperty("--vvtop"); return; }
    var was = nearBottom();
    if (window.innerWidth !== refWidth) { refWidth = window.innerWidth; reference = window.innerHeight; }
    if (!typing() && window.innerHeight > reference) reference = window.innerHeight;
    reference = Math.max(reference, vv.height + vv.offsetTop);
    var covered = typing() && vv.scale <= 1.01 && reference - (vv.height + vv.offsetTop) > 80;     // 80px: ignore the browser's own bar growing and shrinking
    app.classList.toggle("kb-open", covered);
    if (covered) { root.setProperty("--vvh", vv.height + "px"); root.setProperty("--vvtop", vv.offsetTop + "px"); }
    else { root.removeProperty("--vvh"); root.removeProperty("--vvtop"); }
    if (was || covered) toBottom();
  }
  if (vv) { listen(vv, "resize", fit); listen(vv, "scroll", fit); }
  listen(window, "resize", fit);
  if (text) {
    text.addEventListener("focus", function () { setTimeout(function () { fit(); toBottom(); }, 250); });
    text.addEventListener("blur", function () { setTimeout(fit, 150); });
  }
  function fail(message) { error.textContent = message || ""; error.hidden = !message; }

  function timed(url, options, ms) {
    var ctl = new AbortController(), t = setTimeout(function () { ctl.abort(); }, ms);
    options.signal = ctl.signal;
    return fetch(url, options).then(function (r) { clearTimeout(t); return r; }, function (e) { clearTimeout(t); throw e; });
  }

  // Put what the server sent into the thread. An item of mine that carries the client id (cid) of a pending or failed bubble replaces that bubble in
  // place (no second fade, order kept); anything else new is appended and fades in.
  // F-112: before the list changes the bubbles in view are measured; afterwards each one that moved (the list scrolled up to make room) glides from where it was to where it is, and a
  // new bubble settles into place (one that I sent rises out of the box, see the send below). Reduced motion: a short fade.
  // F-113: every move here is one plain animation of `translate` (and `scale`) that the phone runs off the main thread, all with the same smooth ease-out, no overshoot: no per-frame
  // counter-scaling of the words (it stuttered on the iPhone) and no second move when the server confirms (the pending bubble already has the time line's height).
  function motion() { return window.GA && window.GA.motion; }      // (read when needed: motion.js is deferred)
  function snapshot() {
    var out = [], MO = motion();
    if (!MO || MO.reduced()) return out;
    var view = docked() ? thread.getBoundingClientRect() : { top: 0, bottom: window.innerHeight };
    Array.prototype.forEach.call(thread.children, function (c) {
      var r = c.getBoundingClientRect();
      if (r.bottom > view.top && r.top < view.bottom) out.push({ el: c, r: { left: r.left, top: r.top, width: r.width, height: r.height } });
    });
    return out;
  }
  var SMOOTH = { t: "spring", ease: "calm" };
  function glide(snap) {
    var MO = motion();
    snap.forEach(function (s) {
      if (!s.el.isConnected) return;
      s.el.getAnimations().forEach(function (a) { a.cancel(); });      // a rise or glide still running (a quick second Send): the new glide starts from where the eye saw it (`s.r`), not with a jump
      var dy = s.r.top - s.el.getBoundingClientRect().top;
      if (Math.abs(dy) >= 0.5) MO.run(s.el, [{ transform: "translateY(" + dy + "px)" }, { transform: "none" }], SMOOTH);
    });
  }
  // A bubble I sent rises from the box into its place, a touch smaller at first (about its bottom corner, like a message leaving the field), in the same ease-out as the list's glide.
  function rise(el, from) {
    var MO = motion(), dy = Math.max(0, from.top - el.getBoundingClientRect().top);
    MO.log.push({ kind: "rise" });
    el.style.transformOrigin = "100% 100%";
    MO.run(el, [{ transform: "translateY(" + dy + "px) scale(.92)", opacity: 0.5 }, { transform: "none", opacity: 1 }], SMOOTH);      // (one transform: the iPhone runs it off the main thread)
  }
  // The server's copy of a bubble I sent takes the pending one's place without a new element: the same box keeps its place, takes the server's words, time and classes
  // (its "Sending" look fades to the full look). Nothing moves: the "Sending" line and the time line are the same height.
  function adopt(old, fresh) {
    var a, i, kids = old.children, news = fresh.children;
    for (i = old.attributes.length - 1; i >= 0; i--) { a = old.attributes[i].name; if (a !== "class" && a !== "style" && !fresh.hasAttribute(a)) old.removeAttribute(a); }
    for (i = 0; i < fresh.attributes.length; i++) { a = fresh.attributes[i]; if (a.name === "class") old.className = a.value + (old.classList.contains("is-new") ? " is-new" : ""); else old.setAttribute(a.name, a.value); }
    if (kids.length === news.length) {
      for (i = 0; i < kids.length; i++) {
        if (kids[i].tagName !== news[i].tagName) { kids[i].replaceWith(news[i].cloneNode(true)); continue; }
        kids[i].className = news[i].className;
        kids[i].innerHTML = news[i].innerHTML;
      }
    } else { old.innerHTML = fresh.innerHTML; }
  }
  // The bubble may still be rising out of the box: its content is only swapped once that has finished, never under the motion.
  function handOver(old, fresh) {
    old._adopt = true;                                    // delivered from now on, whatever the reply does
    var running = old.getAnimations ? old.getAnimations({ subtree: true }) : [];
    if (!running.length) { adopt(old, fresh); return; }
    Promise.all(running.map(function (a) { return a.finished.catch(function () {}); })).then(function () { adopt(old, fresh); });
  }
  function merge(html, n, mine) {
    if (!html.trim() || n <= last) return;
    var stick = mine || nearBottom(), snap = snapshot(), fresh = [], MO = motion();
    var holder = document.createElement("div");
    holder.innerHTML = html;
    Array.prototype.slice.call(holder.children).forEach(function (el) {   // a copy: appending moves each child out of the live list
      var id = parseInt(el.getAttribute("data-n"), 10) || 0;
      if (id <= last) return;
      var cid = el.getAttribute("data-cid"), waiting = cid ? thread.querySelector('.is-pending[data-cid="' + cid + '"]') : null;
      if (waiting) { handOver(waiting, el); return; }
      if (!MO) el.classList.add("is-new");
      thread.appendChild(el);
      fresh.push(el);
    });
    last = n;
    thread.setAttribute("data-last", String(last));
    if (empty) empty.hidden = true;
    if (stick) toBottom();
    glide(snap);
    fresh.forEach(function (el) { if (MO) (MO.reduced() ? MO.fade : MO.settle)(el); });
  }
  function append(response, mine) {
    var n = parseInt(response.headers.get("X-Thread-Last"), 10) || 0;
    return response.text().then(function (html) { merge(html, n, mine); });
  }

  function poll(mine) {
    if (!thread.isConnected) { teardown(); return Promise.resolve(); }      // F-106: the card this chat was in has been folded away
    if (inflight || document.visibilityState === "hidden") return Promise.resolve();
    inflight = true;
    return timed(join(pollUrl) + "since=" + last + "&trip=" + encodeURIComponent(tripId()), { credentials: "same-origin", headers: { Accept: "text/html" } }, sendTimeout())
      .then(function (r) { if (r.status === 409) { stop(); fail("This trip changed. Reload the page."); return; } if (r.ok) return append(r, mine === true); })
      .catch(function () {})
      .then(function () { inflight = false; });
  }

  function start() { if (!timer) timer = setInterval(poll, interval); }
  function stop() { if (timer) { clearInterval(timer); timer = null; } }
  function shown() {
    if (!thread.isConnected) { teardown(); return; }
    if (document.visibilityState === "hidden") { stop(); return; }
    poll(); start();
  }
  listen(document, "visibilitychange", shown);
  if (root) root.addEventListener("ft-close", teardown);
  if (document.visibilityState !== "hidden") start();
  toBottom();
  // The chat's own script (plantalk.js) fires this after it sent a photo or a voice note: show what is new now, and scroll to it.
  thread.addEventListener("ft-refresh", function () { inflight = false; poll(true); });

  // F-094: Send shows the bubble at once, from the text typed (quiet "Sending" state). Each send carries a client id (cid): the server keeps a repeat of
  // it once, and the server's item (from the answer or from a poll) takes the pending bubble's place by that id. A failed send keeps the bubble, says so
  // (spoken too) and offers Retry with the same text and id. Sends go one after another so they keep their order; polls are not held up by them.
  var chain = Promise.resolve();
  var live = document.createElement("p");
  live.className = "sr-only"; live.setAttribute("role", "status"); live.setAttribute("aria-live", "assertive");
  thread.parentNode.insertBefore(live, thread.nextSibling);
  function newId() {
    var a = new Uint8Array(10);
    window.crypto.getRandomValues(a);
    return Array.prototype.map.call(a, function (b) { return (b % 36).toString(36); }).join("") + Date.now().toString(36);
  }
  function pendingBubble(value) {
    var el = document.createElement("div");
    el.className = "ft-msg ft-me is-pending is-sending";
    var bub = document.createElement("div"); bub.className = "ft-bub";
    var body = document.createElement("span"); body.className = "ft-body"; body.textContent = value;
    var state = document.createElement("span"); state.className = "ft-time ft-state"; state.textContent = "Sending";
    bub.appendChild(body); bub.appendChild(state); el.appendChild(bub);
    el.setAttribute("data-text", value);
    el.setAttribute("data-cid", newId());
    return el;
  }
  function pending(el) { return !!el.parentNode && el.classList.contains("is-pending") && !el._adopt; }      // F-112: a poll may have handed the bubble over to the server's copy: it is delivered, whatever the reply does
  function settle(el, ok, message) {
    if (!pending(el)) return;
    var state = el.querySelector(".ft-state"), old = el.querySelector(".ft-retry");
    if (!state) return;
    if (old) old.remove();
    el.classList.toggle("is-sending", ok === null);
    el.classList.toggle("is-failed", ok === false);
    if (ok === null) { state.textContent = "Sending"; return; }
    state.textContent = message || "Not sent";
    live.textContent = "Message not sent" + (message ? ": " + message : ". Check your connection") + ". Retry is next to it.";
    var retry = document.createElement("button");
    retry.type = "button"; retry.className = "ft-retry"; retry.textContent = "Retry";
    retry.addEventListener("click", function () { deliver(el); text.focus(); });
    state.after(retry);
  }
  function deliver(el) {
    settle(el, null);
    chain = chain.then(function () {
      if (!pending(el)) return;                        // a poll already brought the real one
      var fields = new URLSearchParams(new FormData(form));   // trip and (a plan's chat) act and part
      fields.set("text", el.getAttribute("data-text"));
      fields.set("cid", el.getAttribute("data-cid"));
      fields.set("since", String(last));
      return timed(form.getAttribute("action") || "/trip/family/message", { method: "POST", credentials: "same-origin", headers: { "X-Fragment": "1" }, body: fields }, sendTimeout())
        .then(function (r) {
          return r.text().then(function (html) {
            if (r.status === 400) {                    // refused for what it says (too long ...): the words go back to the box, nothing to retry
              el.remove();
              if (!text.value) text.value = el.getAttribute("data-text");
              fail(html); text.focus();
              return;
            }
            if (!r.ok) throw new Error(r.status === 409 ? html : "");
            merge(html, parseInt(r.headers.get("X-Thread-Last"), 10) || 0, true);   // replaces this bubble in place, by its id
            if (pending(el)) el.remove();           // the answer did not carry it (a poll got there first); a bubble the answer took over stays (F-112)
          });
        })
        .catch(function (err) {
          if (!pending(el)) return;                    // delivered already (a poll got there first): a lost reply is nothing to report
          settle(el, false, err instanceof TypeError || err.name === "AbortError" || !err.message || err.message.length > 120 ? "" : err.message); text.focus();
        });
    }).catch(function () {});                          // the chain never rejects: the next Send always goes
  }
  if (form) form.addEventListener("submit", function (e) {
    e.preventDefault();
    var value = text.value.trim();
    if (!value) { fail("Write something first."); return; }
    fail("");
    var el = pendingBubble(value);
    var MO = motion(), snap = snapshot(), box = text.getBoundingClientRect(), from = { left: box.left, top: box.top, width: box.width, height: box.height };
    if (!MO) el.classList.add("is-new");
    thread.appendChild(el);
    if (empty) empty.hidden = true;
    text.value = "";
    text.focus();
    toBottom();
    if (MO) {
      if (MO.reduced()) MO.fade(el);
      else { rise(el, from); glide(snap); }      // the bubble rises out of the box, the ones above glide up
    }
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
