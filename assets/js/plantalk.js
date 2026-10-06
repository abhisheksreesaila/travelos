/* A plan's chat (F-091): the photo button and the tap-to-record mic. thread.js polls and sends text (the form carries act and part); voicenote.js plays notes.
     - Photo: choosing a file posts it to /trip/talk/photo (multipart) and shows what is new.
     - Mic: a tap asks for the microphone, starts a MediaRecorder (audio/mp4 on iPhone, audio/webm elsewhere) and swaps the composer for a bar with a red dot,
       the time, Cancel and Send. It stops by itself at the limit (3:00) and waits for Send or Cancel. Send posts the recording to /trip/talk/voice with the
       length the page timed; Cancel throws it away. The microphone is released as soon as recording stops or the page is left.
   Where there is no MediaRecorder or getUserMedia the mic stays hidden; the photo button needs only fetch. */
(function () {
  "use strict";
  var root = document.getElementById("ft");
  var thread = document.getElementById("ft-thread");
  if (!root || !thread || !root.getAttribute("data-act")) return;
  var $ = function (id) { return document.getElementById(id); };
  var form = $("ft-compose"), error = $("ft-error"), mic = $("pt-mic"), rec = $("pt-rec"), timer = $("pt-timer"), state = $("pt-state");
  var photoBtn = $("pt-photo-btn"), photoIn = $("pt-photo"), cancel = $("pt-cancel"), sendBtn = $("pt-rec-send");
  var counts = window.__ftBound = window.__ftBound || { thread: 0, plantalk: 0 };      // F-106: the chats bound now, for the tests
  counts.plantalk++;
  root.addEventListener("ft-close", function () { counts.plantalk--; }, { once: true });
  var MAX = parseInt(root.getAttribute("data-max-secs"), 10) || 180;
  var TYPES = ["audio/mp4", "audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];

  function field(name) { var el = form.elements[name]; return el ? el.value : ""; }
  function fail(message) { error.textContent = message || ""; error.hidden = !message; }
  function clock(s) { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60); }

  function upload(path, name, blob, filename, extra) {
    var body = new FormData();
    body.append("act", field("act")); body.append("part", field("part")); body.append("trip", field("trip"));
    Object.keys(extra || {}).forEach(function (k) { body.append(k, extra[k]); });
    body.append(name, blob, filename);
    return fetch(path, { method: "POST", credentials: "same-origin", headers: { "X-Fragment": "1" }, body: body }).then(function (r) {
      if (r.ok) { thread.dispatchEvent(new Event("ft-refresh")); return; }
      return r.text().then(function (t) { throw new Error(t && t.length < 200 ? t : "That did not send. Try again."); });
    }, function () { throw new Error("That did not send. Try again."); });
  }

  // ---- photo ------------------------------------------------------------------------------------------------------------------
  if (photoBtn && photoIn) {
    photoBtn.hidden = false;
    photoIn.addEventListener("change", function () {
      var file = photoIn.files && photoIn.files[0];
      if (!file) return;
      var max = parseInt(photoIn.getAttribute("data-max"), 10) || 0;
      if (max && file.size > max) { fail("That photo is too large (at most " + Math.floor(max / 1048576) + " MB)."); photoIn.value = ""; return; }
      fail("");
      photoBtn.classList.add("is-busy");
      upload("/trip/talk/photo", "photo", file, file.name || "photo.jpg", {})
        .catch(function (err) { fail(err.message); })
        .then(function () { photoBtn.classList.remove("is-busy"); photoIn.value = ""; });
    });
  }

  // ---- voice ------------------------------------------------------------------------------------------------------------------
  if (!(mic && navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder)) return;
  mic.hidden = false;
  var stream = null, recorder = null, chunks = [], started = 0, secs = 0, ticker = null, action = "", blob = null, busy = false;

  function pickType() {
    for (var i = 0; i < TYPES.length; i++) { try { if (MediaRecorder.isTypeSupported(TYPES[i])) return TYPES[i]; } catch (e) { /* try the next */ } }
    return "";
  }
  function release() { if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; } }
  function elapsed() { return Math.min(MAX, (Date.now() - started) / 1000); }
  function show(on) { form.hidden = on; rec.hidden = !on; }
  function reset() {
    clearInterval(ticker); ticker = null; release();
    recorder = null; chunks = []; blob = null; action = ""; busy = false;
    sendBtn.disabled = false; cancel.disabled = false;
    rec.classList.remove("is-full");
    show(false);
    mic.focus();
  }
  function extension(type) { return /mp4/.test(type) ? "m4a" : /ogg/.test(type) ? "ogg" : "webm"; }

  function post() {
    if (busy || !blob) return;
    busy = true; sendBtn.disabled = true; cancel.disabled = true; state.textContent = "Sending";
    fail("");
    upload("/trip/talk/voice", "voice", blob, "voice." + extension(blob.type), { secs: String(Math.max(1, Math.round(secs))) })
      .then(function () { reset(); })
      .catch(function (err) { busy = false; sendBtn.disabled = false; cancel.disabled = false; state.textContent = "Not sent"; fail(err.message); });
  }

  function stopped() {
    clearInterval(ticker); ticker = null; release();
    blob = new Blob(chunks, { type: (recorder && recorder.mimeType) || "audio/webm" });
    if (action === "cancel") { reset(); return; }
    if (action === "send") { post(); return; }
    rec.classList.add("is-full");   // reached the limit by itself: keep the recording for Send or Cancel
    state.textContent = "Time limit reached";
    sendBtn.focus();
  }

  function begin() {
    if (recorder) return;
    fail("");
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (s) {
      stream = s; chunks = []; action = ""; blob = null;
      var type = pickType();
      try { recorder = type ? new MediaRecorder(stream, { mimeType: type }) : new MediaRecorder(stream); }
      catch (e) { release(); recorder = null; fail("This phone cannot record voice notes here."); return; }
      recorder.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      recorder.onstop = stopped;
      recorder.start();
      started = Date.now(); secs = 0;
      timer.textContent = "0:00"; state.textContent = "Recording";
      show(true);
      sendBtn.focus();
      ticker = setInterval(function () {
        var e = elapsed();
        timer.textContent = clock(e);
        if (e >= MAX && recorder && recorder.state === "recording") { secs = MAX; recorder.stop(); }
      }, 200);
    }).catch(function (err) {
      release();
      fail(err && err.name === "NotFoundError" ? "No microphone was found." : "The microphone is blocked. Allow it in the browser's settings, then try again.");
    });
  }

  mic.addEventListener("click", begin);
  cancel.addEventListener("click", function () {
    if (busy) return;
    if (recorder && recorder.state === "recording") { action = "cancel"; recorder.stop(); } else reset();
  });
  sendBtn.addEventListener("click", function () {
    if (busy) return;
    if (recorder && recorder.state === "recording") {
      secs = elapsed();
      if (secs < 1) { fail("Record a little longer first."); return; }
      action = "send"; recorder.stop();
    } else post();
  });
  function leave() { if (recorder && recorder.state === "recording") { action = "cancel"; recorder.stop(); } release(); }
  window.addEventListener("pagehide", leave);
  root.addEventListener("ft-close", function () { leave(); window.removeEventListener("pagehide", leave); });   // F-106: the plan card this was in is folding away
})();
