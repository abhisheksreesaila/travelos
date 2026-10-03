/* Photos on the Family tab (F-071). The server draws both views; this
     - switches Chat / Photos without a reload (the links work without script too: /trip/family?view=photos);
     - opens the camera or the library from the buttons marked data-pick, and uploads the chosen photos one at a time to POST /trip/photos
       (the server checks type, size and content again), then reloads the same view so the strip, the polaroid and the thread card show it. */
(function () {
  "use strict";
  var root = document.getElementById("ft");
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var chat = $("ft-chat"), photos = $("fp"), status = $("ph-status");
  var inputs = { camera: $("ph-camera"), library: $("ph-library") };
  var holder = document.querySelector(".fp-inputs");
  var maxBytes = parseInt(holder && holder.getAttribute("data-max"), 10) || 15 * 1024 * 1024;
  var maxFiles = parseInt(holder && holder.getAttribute("data-files"), 10) || 6;
  var view = root.getAttribute("data-view") === "photos" ? "photos" : "chat";
  var busy = false;

  function say(text, bad) {
    status.textContent = text || "";
    status.hidden = !text;
    status.classList.toggle("is-error", !!bad);
  }

  function show(next, push) {
    view = next;
    root.setAttribute("data-view", next);
    chat.hidden = next !== "chat";
    photos.hidden = next !== "photos";
    ["chat", "photos"].forEach(function (v) {
      var a = $("fam-" + v);
      if (a) a.setAttribute("aria-current", v === next ? "true" : "false");
    });
    if (push) { try { history.replaceState(null, "", next === "photos" ? "/trip/family?view=photos" : "/trip/family"); } catch (e) {} }
    window.scrollTo(0, next === "chat" ? document.documentElement.scrollHeight : 0);
  }

  ["chat", "photos"].forEach(function (v) {
    var a = $("fam-" + v);
    if (a) a.addEventListener("click", function (e) { e.preventDefault(); show(v, true); });
  });
  if (view === "photos") window.scrollTo(0, 0);   // thread.js scrolls the chat to its end when the page loads

  function setBusy(on) {
    busy = on;
    Array.prototype.forEach.call(document.querySelectorAll("[data-pick]"), function (b) { b.disabled = on; });
  }

  function uploadOne(file) {
    var body = new FormData();
    body.append("photo", file, file.name);
    return fetch("/trip/photos", { method: "POST", credentials: "same-origin", headers: { "X-Fragment": "1" }, body: body })
      .then(function (r) {
        if (r.ok) return r.json();
        return r.text().then(function (t) { throw new Error(t || "That photo did not upload. Try again."); });
      });
  }

  function upload(list) {
    var files = Array.prototype.slice.call(list || []);
    if (!files.length || busy) return;
    if (files.length > maxFiles) { say("Add at most " + maxFiles + " photos at a time.", true); return; }
    var big = files.filter(function (f) { return f.size > maxBytes; });
    if (big.length) { say("A photo is too large (at most " + Math.round(maxBytes / 1048576) + " MB each).", true); files = files.filter(function (f) { return f.size <= maxBytes; }); if (!files.length) return; }
    setBusy(true);
    var done = 0, failed = big.length ? "A photo is too large (at most " + Math.round(maxBytes / 1048576) + " MB each)." : "";
    var chain = Promise.resolve();
    files.forEach(function (file, i) {
      chain = chain.then(function () {
        say("Adding photo " + (i + 1) + " of " + files.length + "…");
        return uploadOne(file).then(function () { done += 1; }).catch(function (err) { failed = err.message || "That photo did not upload."; });
      });
    });
    chain.then(function () {
      setBusy(false);
      if (done) {
        say(done + (done === 1 ? " photo added." : " photos added."));
        var q = failed ? "&error=" + encodeURIComponent(failed) : "";
        window.location.href = (view === "photos" ? "/trip/family?view=photos" + q : "/trip/family" + (q ? "?view=photos" + q : ""));
      } else {
        say(failed || "That photo did not upload. Try again.", true);
      }
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-pick]"), function (b) {
    b.addEventListener("click", function () { var input = inputs[b.getAttribute("data-pick")]; if (input) input.click(); });
  });
  Object.keys(inputs).forEach(function (k) {
    var input = inputs[k];
    if (input) input.addEventListener("change", function () { var files = input.files; upload(files); input.value = ""; });
  });
})();
