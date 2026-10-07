// The one Ask box (F-072, F-087). The server draws everything; this script only
//  - lets the box grow with what is said, typed or pasted, and counts characters as the 20,000 limit gets near;
//  - gives the Paste button its job: read the clipboard where the browser allows it, else take the person to the box with a hint;
//  - shows a Tap-to-talk microphone when the browser has speech recognition (SpeechRecognition / webkitSpeechRecognition): it keeps listening, fills the box
//    live (what it is still unsure of included) and restarts itself after a pause, until the person taps Stop. Where there is none the button stays hidden and
//    typing or the keyboard's own dictation does the job. Where recognition is missing, errors or hears nothing for 5 s (an iPhone Home Screen app, which goes
//    straight to it), the mic records (MediaRecorder, up to 3 minutes) and /trip/ask/transcribe turns it into words, added to the box (F-102);
//  - ?mode=paste puts the Paste button first and focuses it; ?mode=talk starts listening where it can, else focuses the box;
//  - shows that the model is working (with the seconds so far) and stops a second tap of Ask, Continue or Apply.
// F-104: the same box also lives in the Ask sheet (assets/js/ask_sheet.js), which draws the fragments and calls AskBox.init(root) on each; init returns { destroy } (stops the
// recorder and drops the page-wide listeners). Where the browser can record, the voice is always recorded and transcribed on the server (Sarvam: Tamil, Hindi and the other
// Indian languages); the browser's own speech recognition is only the fallback where recording is impossible (or the server has no voice service).
(function () {
  function init(root) {
  function $(id) { return root.querySelector('#' + id); }
  var offs = [];
  function on(target, type, fn, opt) { target.addEventListener(type, fn, opt); offs.push(function () { target.removeEventListener(type, fn, opt); }); }
  var form = $('ak-form');
  var box = $('ak-text');
  var mic = $('ak-mic');
  var micLabel = $('ak-mic-label');
  var paste = $('ak-paste');
  var say = $('ak-mic-status');
  var count = $('ak-count');
  var go = $('ak-go');
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
          if (clock) { clearInterval(f._clock); f._clock = setInterval(function () { clock.textContent = Math.round((Date.now() - started) / 1000) + ' s'; }, 1000); offs.push(function () { clearInterval(f._clock); }); }
        }
      }, 0);
    });
  }
  if (form && go) busy(form, go, 'Reading…', $('ak-progress'));
  var questions = $('ak-questions-form');
  if (questions) busy(questions, $('ak-continue'), 'Working…', $('ak-q-progress'));
  var applyForm = $('ak-apply-form');
  if (applyForm) busy(applyForm, $('ak-apply'), 'Applying…', null);
  // In the sheet a single question is one tap: choosing an answer sends it.
  // With several, each question is its own row of chips: a tap answers that question, and when every one has been answered the proposal comes (Done accepts the suggestions as they are).
  if (questions && questions.dataset.tap) questions.addEventListener('change', function (e) {
    if (!(e.target && e.target.type === 'radio') || questions.dataset.sent) return;
    var q = e.target.closest('.ak-q');
    if (q) q.dataset.answered = '1';
    var all = questions.querySelectorAll('.ak-q');
    if (questions.querySelectorAll('.ak-q[data-answered]').length === all.length) questions.requestSubmit($('ak-continue'));
  });

  if (!form || !box) return { destroy: function () {} };

  function note(text) { if (say) say.textContent = text; }

  // ---- the box grows, and counts near the limit ----
  var limit = parseInt(box.dataset.limit, 10) || 20000;
  // On the trip the day picker opens on today. A long paste is a plan for GitAway to place, so until the person picks a day themselves it follows the length.
  var dayPick = $('ak-day');
  var longAt = parseInt(box.dataset.long, 10) || 0;
  var picked = false;
  if (dayPick) dayPick.addEventListener('change', function () { picked = true; });
  function placeByLength() {
    if (!dayPick || picked || !dayPick.dataset.auto || !longAt) return;
    var words = box.value.split(/\s+/).join(' ').trim();
    dayPick.value = words.length > longAt ? '' : dayPick.dataset.auto;
    dayPick.dispatchEvent(new CustomEvent('ak:day'));
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
  on(window, 'resize', refresh);
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
  // Wherever the browser can record and the server has a voice service (data-server), the voice is recorded and transcribed there: the browser's own recognition (an iPhone's
  // dictation) does not understand Tamil, Hindi and the rest, which Sarvam does. Recognition is only the fallback.
  function preferRecord() { return canRecord && !!mic && mic.dataset.server === '1'; }
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var timeEl = $('ak-mic-time');
  var cancelBtn = $('ak-rec-cancel');
  var working = $('ak-transcribing');
  var workingClock = $('ak-tr-elapsed');
  var MAX = parseInt(mic && mic.dataset.maxSecs, 10) || 180;
  var NO_VOICE = "Voice typing isn't set up yet — tap the microphone on your keyboard to dictate.";

  // Diagnostics (F-104): where the microphone path stops, one tiny line per step to POST /trip/ask/mic-event, which the server writes to its log. Never audio, never words.
  var sent = 0;
  function diag(stage, name, detail) {
    if (sent >= 40 || !window.fetch) return;
    sent += 1;
    try {
      fetch('/trip/ask/mic-event', { method: 'POST', credentials: 'same-origin', keepalive: true, headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
        body: JSON.stringify({ stage: stage, name: String(name || '').slice(0, 40), detail: String(detail || '').slice(0, 120) }) }).catch(function () {});
    } catch (e) { /* diagnostics must never get in the way */ }
  }
  function why() {
    return 'canRecord=' + (canRecord ? 1 : 0) + ' recognition=' + (Recognition ? 1 : 0) + ' ios=' + (ios ? 1 : 0) + ' installed=' + (installed ? 1 : 0) + ' server=' + (mic && mic.dataset.server === '1' ? 1 : 0) + ' sheet=' + (form.dataset.sheet ? 1 : 0) + ' type=' + (recType || '');
  }
  function blocked(err) {
    var n = err && err.name;
    return n === 'NotFoundError' ? 'No microphone was found on this phone.'
      : n === 'NotAllowedError' || n === 'SecurityError' ? 'The microphone is blocked for GitAway. Allow it in Settings > GitAway (or Safari > Microphone), then tap the mic again.'
      : n === 'NotReadableError' ? 'The microphone is being used by another app. Close it and tap the mic again.'
      : 'The microphone could not start' + (n ? ' (' + n + ')' : '') + '. You can type instead.';
  }

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
      diag('speech', 'error', e.error);
      giveUp(e.error === 'not-allowed' || e.error === 'service-not-allowed' ? 'The microphone is off for this site. You can type instead.' : 'Could not hear you. You can type instead.');
    };
    rec.onend = function () {
      if (recording) return;
      if (wanted) { setTimeout(function () { if (wanted) { try { begin(); } catch (err) { wanted = false; ui(false); } } }, 150); return; }
      words('final');
      ui(false);
      if (say && say.textContent.indexOf('Listening') === 0) note('');
      sendWhenDone();
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
    if (paste && !sheet) paste.hidden = on;
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
  var heardField = form.elements.heard, understood = $('ak-understood');
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
    diag('piece', 'upload', 'bytes=' + blob.size + ' secs=' + Math.round(secs) + ' type=' + (blob.type || ''));
    return fetch('/trip/ask/transcribe', { method: 'POST', credentials: 'same-origin', body: body }).then(function (r) {
      if (mine !== gen) return;
      if (r.ok) return r.json().then(function (j) { gotWords = true; diag('result', j.text ? 'ok' : 'empty', 'status=' + r.status + ' lang=' + String(j.language || '').slice(0, 8)); return addWords(j.text || '', j.english || ''); });
      return r.text().then(function (t) {
        diag('result', 'error', 'status=' + r.status);
        if (/^The assistant is busy/.test(t) && (tries || 0) < 3) {      // the line was taken (the server already waited a few seconds): try this piece again, keeping order
          return new Promise(function (go) { setTimeout(go, 2500); }).then(function () { return mine === gen ? send(blob, secs, mine, (tries || 0) + 1) : null; });
        }
        if (/^Nothing could be heard/.test(t) && (pieces > 1 || recording)) return;       // a quiet stretch in a long recording is not a failure
        failed = r.status === 503 && t === NO_VOICE ? NO_VOICE : (t && t.length < 200 ? t : 'That did not work.');
      });
    }, function (err) { diag('result', 'network', err && err.name); if (mine === gen) failed = 'That did not upload. Try again, or type it.'; });
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
    if (failed) note(failed + kept()); else if (gotWords) note(sheet ? 'Added what you said.' : 'Added what you said. Check it, then tap Ask GitAway.');
    if (mic) mic.focus();
    sendWhenDone();
  }
  function startPiece() {     // a new recorder on the stream that is already open
    var r, cs = [], t0 = Date.now(), n = 0;
    try { r = recType ? new MediaRecorder(stream, { mimeType: recType }) : new MediaRecorder(stream); } catch (e) { diag('recorder', 'error', (e && e.name) + ' type=' + recType); return false; }
    r.onerror = function (e) { diag('recorder', 'error', (e && e.error && e.error.name) || 'error'); };
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
    try { r.start(1000); } catch (e) { diag('recorder', 'error', (e && e.name) + ' on start'); return false; }
    recorder = r;
    diag('recorder', 'start', 'type=' + (r.mimeType || recType));
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
      diag('gum', 'granted', '');
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
      diag('gum', 'refused', err && err.name);
      note(blocked(err) + kept());
      if (form.dataset.mode === 'talk') box.focus();
    });
  }
  if (cancelBtn) cancelBtn.addEventListener('click', function () {
    gen += 1;       // pieces still out are dropped; words already added stay
    if (recorder && recorder.state === 'recording') { action = 'cancel'; recorder.stop(); } else reset();
  });
  on(document, 'visibilitychange', function () { if (document.hidden) rotate(); });      // the screen locked or the app was left: finish this piece now, timers may stop
  on(window, 'pagehide', function () { if (recorder && recorder.state === 'recording') { action = 'cancel'; recorder.stop(); } release(); });

  var sheet = !!form.dataset.sheet, sendAfter = false;
  function sendWhenDone() {
    if (!sendAfter || recording || inflight > 0 || listening) return;
    sendAfter = false;
    if (box.value.trim() && !form.dataset.sent) form.requestSubmit(go);
  }
  if (sheet) {
    // Done pressed while still talking: finish the recording (or the listening), wait for the words, then send.
    go.addEventListener('click', function (e) {      // a click, not the submit: an empty required box would stop the submit before it fires
      if (!(recording || inflight > 0 || listening || wanted)) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      sendAfter = true;
      if (recording) { if (recorder && recorder.state === 'recording') { action = 'stop'; recorder.stop(); } }
      else if (wanted || listening) { wanted = false; clearHeard(); try { rec.stop(); } catch (err) { ui(false); sendWhenDone(); } }
    }, true);
    // the keyboard-mic hint only where this phone can neither record nor recognise speech
    var hint = $('ak-hint');
    if (hint) hint.hidden = !!(Recognition || canRecord);
  }

  function toggle() {
    if (busyUp) return;
    if (recording) { if (recorder && recorder.state === 'recording') { action = 'stop'; recorder.stop(); } return; }
    diag('tap', 'mic', why());
    if (preferRecord()) { diag('mode', 'record', why()); startRecording(); return; }
    if (!(wanted || listening)) diag('mode', Recognition ? 'web-speech' : 'none', why());
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
  } else if (mic) diag('mode', 'none', why());       // neither recording nor recognition here: the mic stays hidden, typing and the keyboard's dictation are all there is

  // ---- the Ask sheet's date chip: it opens a row of days; a pick moves the hidden day field and the chip's words ----
  var chip = $('ak-chip'), picks = $('ak-days-pick');
  if (chip && picks && dayPick) {
    var label = $('ak-chip-label');
    var sync = function () {
      Array.prototype.forEach.call(picks.querySelectorAll('.ak-dpick'), function (b) {
        var on = b.dataset.d === dayPick.value;
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
        if (on && label) label.textContent = b.textContent;
      });
    };
    var MO = window.GA.motion, shut = 0;
    var show = function (on) {           // F-109: the row of days grows out of the chip and folds back into it
      var was = !picks.hidden;
      chip.setAttribute('aria-expanded', on ? 'true' : 'false');
      if (on === was) return;
      shut += 1;
      var mine = shut;
      var sheet = chip.closest('.ak-sheet');      // the sheet is anchored at the bottom: the row makes it taller or shorter, and the sheet moves from its old size to the new one with the spring instead of jumping
      if (on) {
        var reveal = function () { picks.hidden = false; };
        if (sheet) MO.reflow(sheet, reveal, { during: function () { MO.open(picks, chip); } });
        else { reveal(); MO.open(picks, chip); }
        return;
      }
      MO.close(picks, chip).then(function () {
        if (mine !== shut) return;
        var hide = function () { picks.hidden = true; };
        if (sheet && sheet.isConnected) MO.reflow(sheet, hide); else hide();
      });
    };
    chip.addEventListener('click', function () { show(picks.hidden); });
    picks.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('.ak-dpick');
      if (!b) return;
      dayPick.value = b.dataset.d;
      dayPick.dispatchEvent(new Event('change', { bubbles: true }));
      sync();
      show(false);
    });
    dayPick.addEventListener('ak:day', sync);
  }

  var mode = form.dataset.mode;
  if (mode === 'paste' && paste) paste.focus();
  if (mode === 'talk') {
    if (mic && (Recognition || canRecord)) toggle(); else box.focus();
  }
  return {
    destroy: function () {
      wanted = false; sendAfter = false; gen += 1;
      clearHeard();
      if (rec) { try { rec.abort(); } catch (e) { /* already stopped */ } }
      if (recorder && recorder.state === 'recording') { action = 'cancel'; try { recorder.stop(); } catch (e) { /* stopped */ } }
      release();
      clearInterval(ticker); if (working) clearInterval(working.timer);
      offs.forEach(function (off) { off(); });
    }
  };
  }
  window.AskBox = { init: init };
  if (document.getElementById('ak-form')) init(document);
})();
