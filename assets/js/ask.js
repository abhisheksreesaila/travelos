// Ask GitAway (F-072). The server draws everything; this script only
//  - shows a hold-to-talk microphone when the browser has speech recognition (SpeechRecognition / webkitSpeechRecognition), and fills the box live while it listens.
//    Where there is none the button stays hidden and typing or the keyboard's own dictation does the job.
//  - shows that the model is working and stops a second tap of Ask or Apply.
(function () {
  var form = document.getElementById('ak-form');
  var box = document.getElementById('ak-text');
  var mic = document.getElementById('ak-mic');
  var say = document.getElementById('ak-mic-status');
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  function busy(f, button, label, progress) {
    f.addEventListener('submit', function (e) {
      if (f.dataset.sent) { e.preventDefault(); return; }
      f.dataset.sent = '1';
      f.setAttribute('aria-busy', 'true');
      setTimeout(function () {       // a disabled button inside its own submit event would drop its value on some browsers
        button.disabled = true;
        button.textContent = label;
        if (progress) progress.hidden = false;
      }, 0);
    });
  }
  if (form) busy(form, document.getElementById('ak-go'), 'Reading…', document.getElementById('ak-progress'));
  var applyForm = document.getElementById('ak-apply-form');
  if (applyForm) busy(applyForm, document.getElementById('ak-apply'), 'Applying…', null);

  if (!form || !box || !mic || !Recognition) return;
  mic.hidden = false;
  var rec = null, base = '', listening = false;

  function note(text) { if (say) say.textContent = text; }

  function stop() {
    if (rec && listening) { try { rec.stop(); } catch (e) { /* already stopped */ } }
  }

  function start() {
    if (listening) return;
    rec = new Recognition();
    rec.lang = document.documentElement.lang || 'en-US';
    rec.interimResults = true;
    rec.continuous = true;
    base = box.value ? box.value.replace(/\s+$/, '') + ' ' : '';
    rec.onresult = function (e) {
      var heard = '';
      for (var i = 0; i < e.results.length; i++) heard += e.results[i][0].transcript;
      box.value = (base + heard).slice(0, box.maxLength > 0 ? box.maxLength : 600);
    };
    rec.onerror = function (e) {
      note(e.error === 'not-allowed' || e.error === 'service-not-allowed' ? 'The microphone is off for this site. You can type instead.' : 'Could not hear you. You can type instead.');
    };
    rec.onend = function () { listening = false; mic.setAttribute('aria-pressed', 'false'); if (say && say.textContent === 'Listening…') note(''); };
    try {
      rec.start();
      listening = true;
      mic.setAttribute('aria-pressed', 'true');
      note('Listening…');
    } catch (e) { note('Could not start the microphone. You can type instead.'); }
  }

  mic.addEventListener('pointerdown', function (e) { e.preventDefault(); start(); });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (name) { mic.addEventListener(name, stop); });
  mic.addEventListener('keydown', function (e) { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.preventDefault(); start(); } });
  mic.addEventListener('keyup', function (e) { if (e.key === ' ' || e.key === 'Enter') stop(); });
  mic.addEventListener('contextmenu', function (e) { e.preventDefault(); });
})();
