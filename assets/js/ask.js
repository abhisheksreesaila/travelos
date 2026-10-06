// The one Ask box (F-072, F-087). The server draws everything; this script only
//  - lets the box grow with what is said, typed or pasted, and counts characters as the 20,000 limit gets near;
//  - gives the Paste button its job: read the clipboard where the browser allows it, else take the person to the box with a hint;
//  - shows a Tap-to-talk microphone when the browser has speech recognition (SpeechRecognition / webkitSpeechRecognition): it keeps listening, fills the box
//    live (what it is still unsure of included) and restarts itself after a pause, until the person taps Stop. Where there is none the button stays hidden and
//    typing or the keyboard's own dictation does the job. Where recognition is missing, errors or hears nothing for 5 s (an iPhone Home Screen app, which goes
//    straight to it), the mic records (MediaRecorder, up to 3 minutes) and /trip/ask/transcribe turns it into words, added to the box (F-102);
//  - ?mode=paste puts the Paste button first and focuses it; ?mode=talk starts listening where it can, else focuses the box;
//  - shows that the model is working (with the seconds so far) and stops a second tap of Ask, Continue or Apply.
(function () {
  var form = document.getElementById('ak-form');
  var box = document.getElementById('ak-text');
  var mic = document.getElementById('ak-mic');
  var micLabel = document.getElementById('ak-mic-label');
  var paste = document.getElementById('ak-paste');
  var say = document.getElementById('ak-mic-status');
  var count = document.getElementById('ak-count');
  var go = document.getElementById('ak-go');
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  function busy(f, button, label, progress) {
    f.addEventListener('submit', function (e) {
      if (f.dataset.sent) { e.preventDefault(); return; }
      f.dataset.sent = '1';
      f.setAttribute('aria-busy', 'true');
      var started = Date.now();
      setTimeout(function () {       // a disabled button inside its own submit event would drop its value on some browsers
        button.disabled = true;
        button.textContent = label;
        if (progress) {
          progress.hidden = false;
          var clock = progress.querySelector('.ak-elapsed');
          if (clock) setInterval(function () { clock.textContent = Math.round((Date.now() - started) / 1000) + ' s'; }, 1000);
        }
      }, 0);
    });
  }
  if (form && go) busy(form, go, 'Reading…', document.getElementById('ak-progress'));
  var questions = document.getElementById('ak-questions-form');
  if (questions) busy(questions, document.getElementById('ak-continue'), 'Working…', document.getElementById('ak-q-progress'));
  var applyForm = document.getElementById('ak-apply-form');
  if (applyForm) busy(applyForm, document.getElementById('ak-apply'), 'Applying…', null);

  if (!form || !box) return;

  function note(text) { if (say) say.textContent = text; }

  // ---- the box grows, and counts near the limit ----
  var limit = parseInt(box.dataset.limit, 10) || 20000;
  // On the trip the day picker opens on today. A long paste is a plan for GitAway to place, so until the person picks a day themselves it follows the length.
  var dayPick = document.getElementById('ak-day');
  var longAt = parseInt(box.dataset.long, 10) || 0;
  var picked = false;
  if (dayPick) dayPick.addEventListener('change', function () { picked = true; });
  function placeByLength() {
    if (!dayPick || picked || !dayPick.dataset.auto || !longAt) return;
    var words = box.value.split(/\s+/).join(' ').trim();
    dayPick.value = words.length > longAt ? '' : dayPick.dataset.auto;
  }
  function refresh() {
    box.style.height = 'auto';
    var rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 12;
    box.style.height = Math.min(box.scrollHeight, Math.max(window.innerHeight * 0.6, 13 * rem)) + 'px';
    placeByLength();
    var n = box.value.length;
    if (!count) return;
    if (n > limit) {
      count.hidden = false;
      count.classList.add('is-over');
      count.textContent = (n - limit).toLocaleString('en-US') + ' characters over the ' + limit.toLocaleString('en-US') + ' limit. Paste it in two parts.';
      if (go && !form.dataset.sent) go.disabled = true;
    } else {
      count.classList.remove('is-over');
      count.hidden = n < limit * 0.8;
      count.textContent = n.toLocaleString('en-US') + ' of ' + limit.toLocaleString('en-US') + ' characters';
      if (go && !form.dataset.sent) go.disabled = false;
    }
  }
  box.addEventListener('input', refresh);
  window.addEventListener('resize', refresh);
  refresh();

  // ---- Paste ----
  function insert(text) {
    if (!text) { note('The clipboard is empty.'); return; }
    var s = box.selectionStart, e = box.selectionEnd;
    if (document.activeElement === box && typeof s === 'number') {
      box.value = box.value.slice(0, s) + text + box.value.slice(e);
      box.selectionStart = box.selectionEnd = s + text.length;
    } else {
      box.value = box.value ? box.value.replace(/\s+$/, '') + '\n' + text : text;
    }
    box.dispatchEvent(new Event('input', { bubbles: true }));
    note('Pasted ' + text.length.toLocaleString('en-US') + ' characters.');
  }
  function pasteByHand() {
    box.focus();
    note('Touch and hold in the box, then tap Paste.');
  }
  if (paste) {
    paste.addEventListener('click', function () {
      if (navigator.clipboard && navigator.clipboard.readText) {
        navigator.clipboard.readText().then(insert, pasteByHand);
      } else {
        pasteByHand();
      }
    });
  }

  // ---- The microphone ----
  // Two ways to turn a voice into words. Where the browser has speech recognition it is used (live, in the box). Where it is missing, errors out or says nothing
  // for a few seconds (an iPhone Home Screen app), the mic records instead (MediaRecorder, as the plan chat does) and the recording is sent to /trip/ask/transcribe;
  // the words are added to what is already in the box. In an installed iPhone app it records straight away.
  var rec = null, listening = false, wanted = false, base = '', heardTimer = null;
  var canRecord = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  var ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  var installed = !!(navigator.standalone || (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches));
  var preferRecord = canRecord && (!Recognition || (ios && installed));
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var timeEl = document.getElementById('ak-mic-time');
  var cancelBtn = document.getElementById('ak-rec-cancel');
  var working = document.getElementById('ak-transcribing');
  var workingClock = document.getElementById('ak-tr-elapsed');
  var MAX = parseInt(mic && mic.dataset.maxSecs, 10) || 180;
  var NO_VOICE = "Voice typing isn't set up yet — tap the microphone on your keyboard to dictate.";

  function words(state) { box.setAttribute('data-words', state); }
  function kept() { return box.value.trim() ? ' What you typed is still in the box.' : ''; }
  function ui(on) {
    listening = on;
    if (mic) mic.setAttribute('aria-pressed', on ? 'true' : 'false');
    if (micLabel) micLabel.textContent = on ? 'Stop' : 'Tap to talk';
  }

  // ---- speech recognition ----
  function clearHeard() { if (heardTimer) { clearTimeout(heardTimer); heardTimer = null; } }
  function giveUp(why) {      // recognition failed or heard nothing: record instead where the browser can, else say so
    clearHeard();
    wanted = false;
    if (rec) { try { rec.abort(); } catch (e) { /* already stopped */ } }
    words('final');
    if (canRecord) { ui(false); startRecording(); return true; }
    note(why);
    return false;
  }
  function begin() {
    rec = new Recognition();
    rec.lang = document.documentElement.lang || 'en-US';
    rec.interimResults = true;
    rec.continuous = true;
    base = box.value ? box.value.replace(/\s+$/, '') + ' ' : '';
    rec.onaudiostart = rec.onspeechstart = clearHeard;
    rec.onresult = function (e) {
      clearHeard();
      var heard = '';
      for (var i = 0; i < e.results.length; i++) heard += e.results[i][0].transcript;
      box.value = base + heard;
      words(e.results.length && e.results[e.results.length - 1].isFinal ? 'final' : 'interim');
      refresh();
    };
    rec.onerror = function (e) {
      if (e.error === 'no-speech' || e.error === 'aborted') return;
      giveUp(e.error === 'not-allowed' || e.error === 'service-not-allowed' ? 'The microphone is off for this site. You can type instead.' : 'Could not hear you. You can type instead.');
    };
    rec.onend = function () {
      if (recording) return;
      if (wanted) { setTimeout(function () { if (wanted) { try { begin(); } catch (err) { wanted = false; ui(false); } } }, 150); return; }
      words('final');
      ui(false);
      if (say && say.textContent.indexOf('Listening') === 0) note('');
    };
    rec.start();
    ui(true);
    note('Listening. Tap Stop when you are done.');
    clearHeard();
    if (canRecord) heardTimer = setTimeout(function () { giveUp(''); }, 5000);      // nothing heard and no word that it started: this browser cannot do it here
  }

  // ---- recording ----
  // The recorder is rotated every PIECE seconds (25): the current MediaRecorder stops and a new one starts on the SAME stream at once (no new permission prompt), so every
  // piece is a standalone file with its own header. Each finished piece is uploaded one at a time while the person keeps talking, and its words are appended to the
  // box in order. The speech service takes about 30 seconds per piece. The whole recording stops at MAX (3 minutes).
  var recording = false, recorder = null, stream = null, started = 0, ticker = null, action = '', inflight = 0, busyUp = false;
  var gen = 0, queue = Promise.resolve(), pieces = 0, gotWords = false, failed = '', piece = 25, recType = '';
  var TYPES = ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus'];
  function pickType() {
    for (var i = 0; i < TYPES.length; i++) { try { if (MediaRecorder.isTypeSupported(TYPES[i])) return TYPES[i]; } catch (e) { /* next */ } }
    return '';
  }
  function release() { if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; } }
  function clock(s) { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + ':' + (s % 60 < 10 ? '0' : '') + (s % 60); }
  function recUi(on) {
    recording = on;
    if (mic) mic.classList.toggle('is-recording', on);
    if (timeEl) { timeEl.hidden = !on; if (on) timeEl.textContent = '0:00'; }
    if (cancelBtn) cancelBtn.hidden = !on;
    if (paste) paste.hidden = on;
    ui(on);
    if (on) note('Recording. Tap Stop when you are done.');
    busyState();
  }
  function reset() {
    clearInterval(ticker); ticker = null; release();
    recorder = null; action = '';
    recUi(false);
  }
  function busyState() {      // "Transcribing…" shows while any piece is out; the mic stays a Stop button while recording and waits otherwise
    busyUp = inflight > 0 && !recording;
    if (mic) mic.disabled = busyUp;
    if (!working) return;
    var on = inflight > 0;
    if (on && working.hidden) {
      var t0 = Date.now();
      clearInterval(working.timer);
      working.timer = setInterval(function () { if (workingClock) workingClock.textContent = Math.round((Date.now() - t0) / 1000) + ' s'; }, 500);
      if (workingClock) workingClock.textContent = '0 s';
    }
    if (!on) clearInterval(working.timer);
    working.hidden = !on;
  }
  // What was said in another language: the box keeps it as said; the English the service gave for it travels in the hidden `heard` field, so the planner reads English.
  var heardField = form.elements.heard, understood = document.getElementById('ak-understood');
  function heardList() { try { var v = JSON.parse(heardField && heardField.value || '[]'); return Array.isArray(v) ? v : []; } catch (e) { return []; } }
  function showUnderstood() {
    if (!understood) return;
    var now = heardList().filter(function (p) { return box.value.indexOf(p[0]) >= 0; });
    if (heardField) heardField.value = now.length ? JSON.stringify(now) : '';
    understood.hidden = !now.length;
    understood.textContent = now.length ? 'Understood as: ' + now.map(function (p) { return p[1]; }).join(' ') : '';
  }
  function rememberHeard(spoken, english) {
    if (!heardField || !english || english === spoken) return;
    var list = heardList(); list.push([spoken, english]);
    heardField.value = JSON.stringify(list);
    showUnderstood();
  }
  box.addEventListener('input', showUnderstood);
  showUnderstood();
  function addWords(text, english) {     // the piece's words join what is there, in order; they write themselves in word by word (not under reduced motion). Returns a promise.
    return new Promise(function (resolve) {
      var start = box.value ? box.value.replace(/\s+$/, '') + ' ' : '';
      var list = text.split(/\s+/).filter(Boolean);
      text = list.join(' ');
      var done = function () { rememberHeard(text, english); resolve(); };
      if (reduced || list.length < 2) { box.value = start + text; words('final'); refresh(); done(); return; }
      var i = 0;
      words('interim');
      box.classList.add('is-typing-in');
      var timer = setInterval(function () {
        i += 1;
        box.value = start + list.slice(0, i).join(' ');
        refresh();
        if (i >= list.length) { clearInterval(timer); words('final'); box.classList.remove('is-typing-in'); done(); }
      }, 70);
    });
  }
  function send(blob, secs, mine, tries) {       // one piece to the server; resolves when its words are in the box (or it failed)
    var body = new FormData();
    body.append('audio', blob, 'voice.' + (/mp4/.test(blob.type) ? 'm4a' : /ogg/.test(blob.type) ? 'ogg' : 'webm'));
    body.append('secs', String(Math.max(1, Math.round(secs))));
    var lang = (box.dataset.lang || '').trim();
    if (lang) body.append('lang', lang);
    return fetch('/trip/ask/transcribe', { method: 'POST', credentials: 'same-origin', body: body }).then(function (r) {
      if (mine !== gen) return;
      if (r.ok) return r.json().then(function (j) { gotWords = true; return addWords(j.text || '', j.english || ''); });
      return r.text().then(function (t) {
        if (/^The assistant is busy/.test(t) && (tries || 0) < 3) {      // the line was taken (the server already waited a few seconds): try this piece again, keeping order
          return new Promise(function (go) { setTimeout(go, 2500); }).then(function () { return mine === gen ? send(blob, secs, mine, (tries || 0) + 1) : null; });
        }
        if (/^Nothing could be heard/.test(t) && (pieces > 1 || recording)) return;       // a quiet stretch in a long recording is not a failure
        failed = r.status === 503 && t === NO_VOICE ? NO_VOICE : (t && t.length < 200 ? t : 'That did not work.');
      });
    }, function () { if (mine === gen) failed = 'That did not upload. Try again, or type it.'; });
  }
  function enqueue(blob, secs) {
    var mine = gen;
    pieces += 1;
    inflight += 1;
    busyState();
    queue = queue.then(function () { return mine === gen ? send(blob, secs, mine) : null; }).then(function () {
      inflight -= 1;
      busyState();
      if (mine === gen) finished();
    });
  }
  function finished() {       // nothing more is coming: say how it went
    if (inflight > 0 || recording) return;
    if (failed) note(failed + kept()); else if (gotWords) note('Added what you said. Check it, then tap Ask GitAway.');
    if (mic) mic.focus();
  }
  function startPiece() {     // a new recorder on the stream that is already open
    var r, cs = [], t0 = Date.now(), n = 0;
    try { r = recType ? new MediaRecorder(stream, { mimeType: recType }) : new MediaRecorder(stream); } catch (e) { return false; }
    // One chunk a second (the recorder's own clock, which does not stop when the screen locks): a piece is closed by the page's timer, by the screen going away,
    // or by the recorder having produced `piece` chunks, whichever comes first.
    r.ondataavailable = function (e) {
      if (e.data && e.data.size) cs.push(e.data);
      n += 1;
      if (recorder === r && n >= piece && r.state === 'recording') rotate();
    };
    r.onstop = function () {
      var secs = Math.min(n || (Date.now() - t0) / 1000, 30, (Date.now() - t0) / 1000 + 1);
      var blob = new Blob(cs, { type: r.mimeType || recType || 'audio/webm' });
      var last = action === 'stop' || action === 'limit' || action === 'cancel';
      if (action === 'cancel') { reset(); note('Recording thrown away.'); if (mic) mic.focus(); return; }
      if (blob.size && secs >= 0.5) enqueue(blob, secs);
      if (!last) return;
      var empty = pieces === 0;
      reset();
      if (empty) note('Record a little longer, then tap Stop.'); else finished();
    };
    try { r.start(1000); } catch (e) { return false; }
    recorder = r;
    return true;
  }
  var lastCut = 0;
  function rotate() {     // close this piece and open the next on the same stream; if the next cannot start the recording ends here, with what was said so far
    if (!recorder || recorder.state !== 'recording') return;
    var old = recorder;
    lastCut = Date.now();
    if (!startPiece()) action = 'limit';
    old.stop();
  }
  function startRecording() {
    if (recording || busyUp) return;
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (s) {
      stream = s; action = ''; pieces = 0; gotWords = false; failed = ''; gen += 1;
      recType = pickType();
      piece = parseFloat(mic && mic.dataset.pieceSecs) || 25;
      if (!startPiece()) { release(); recorder = null; note('This phone cannot record here. Tap the microphone on your keyboard to dictate.'); return; }
      started = Date.now();
      lastCut = started;
      recUi(true);
      ticker = setInterval(function () {
        var now = Date.now(), e = Math.min(MAX, (now - started) / 1000);
        if (timeEl) timeEl.textContent = clock(e);
        if (!recorder || recorder.state !== 'recording') return;
        if (e >= MAX) { action = 'limit'; recorder.stop(); return; }       // the limit: the last piece is transcribed
        if ((now - lastCut) / 1000 >= piece) rotate();
      }, 250);
    }).catch(function (err) {
      release();
      note((err && err.name === 'NotFoundError' ? 'No microphone was found.' : 'The microphone is blocked. Allow it in the settings, or tap the microphone on your keyboard.') + kept());
      if (form.dataset.mode === 'talk') box.focus();
    });
  }
  if (cancelBtn) cancelBtn.addEventListener('click', function () {
    gen += 1;       // pieces still out are dropped; words already added stay
    if (recorder && recorder.state === 'recording') { action = 'cancel'; recorder.stop(); } else reset();
  });
  document.addEventListener('visibilitychange', function () { if (document.hidden) rotate(); });      // the screen locked or the app was left: finish this piece now, timers may stop
  window.addEventListener('pagehide', function () { if (recorder && recorder.state === 'recording') { action = 'cancel'; recorder.stop(); } release(); });

  function toggle() {
    if (busyUp) return;
    if (recording) { if (recorder && recorder.state === 'recording') { action = 'stop'; recorder.stop(); } return; }
    if (preferRecord) { startRecording(); return; }
    if (wanted || listening) {
      wanted = false;
      clearHeard();
      try { rec.stop(); } catch (e) { ui(false); }
      return;
    }
    wanted = true;
    try { begin(); } catch (e) { wanted = false; if (!giveUp('Could not start the microphone. You can type instead.')) { /* said */ } }
  }
  if (mic && (Recognition || canRecord)) {
    mic.hidden = false;
    mic.addEventListener('click', toggle);
  }

  var mode = form.dataset.mode;
  if (mode === 'paste' && paste) paste.focus();
  if (mode === 'talk') {
    if (mic && (Recognition || canRecord)) toggle(); else box.focus();
  }
})();
