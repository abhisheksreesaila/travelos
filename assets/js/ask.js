// The one Ask box (F-072, F-087). The server draws everything; this script only
//  - lets the box grow with what is said, typed or pasted, and counts characters as the 20,000 limit gets near;
//  - gives the Paste button its job: read the clipboard where the browser allows it, else take the person to the box with a hint;
//  - shows a Tap-to-talk microphone when the browser has speech recognition (SpeechRecognition / webkitSpeechRecognition): it keeps listening, fills the box
//    live (what it is still unsure of included) and restarts itself after a pause, until the person taps Stop. Where there is none the button stays hidden and
//    typing or the keyboard's own dictation does the job;
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

  // ---- Tap to talk ----
  var rec = null, listening = false, wanted = false, base = '';
  function ui(on) {
    listening = on;
    if (mic) mic.setAttribute('aria-pressed', on ? 'true' : 'false');
    if (micLabel) micLabel.textContent = on ? 'Stop' : 'Tap to talk';
  }
  function begin() {
    rec = new Recognition();
    rec.lang = document.documentElement.lang || 'en-US';
    rec.interimResults = true;
    rec.continuous = true;
    base = box.value ? box.value.replace(/\s+$/, '') + ' ' : '';
    rec.onresult = function (e) {
      var heard = '';
      for (var i = 0; i < e.results.length; i++) heard += e.results[i][0].transcript;
      box.value = base + heard;
      refresh();
    };
    rec.onerror = function (e) {
      if (e.error === 'no-speech' || e.error === 'aborted') return;
      wanted = false;
      note(e.error === 'not-allowed' || e.error === 'service-not-allowed' ? 'The microphone is off for this site. You can type instead.' : 'Could not hear you. You can type instead.');
    };
    rec.onend = function () {
      if (wanted) { setTimeout(function () { if (wanted) { try { begin(); } catch (err) { wanted = false; ui(false); } } }, 150); return; }
      ui(false);
      if (say && say.textContent.indexOf('Listening') === 0) note('');
    };
    rec.start();
    ui(true);
    note('Listening. Tap Stop when you are done.');
  }
  function toggle() {
    if (wanted || listening) {
      wanted = false;
      try { rec.stop(); } catch (e) { ui(false); }
      return;
    }
    wanted = true;
    try { begin(); } catch (e) { wanted = false; note('Could not start the microphone. You can type instead.'); }
  }
  if (mic && Recognition) {
    mic.hidden = false;
    mic.addEventListener('click', toggle);
  }

  var mode = form.dataset.mode;
  if (mode === 'paste' && paste) paste.focus();
  if (mode === 'talk') {
    if (mic && Recognition) toggle(); else box.focus();
  }
})();
