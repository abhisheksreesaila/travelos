/* Voice notes that play in place (F-091), in the Family tab's thread and in a plan's chat. Each note is
     <div class="vn" data-secs="42"> <button data-vn="btn"> <span data-vn="fill"> <span data-vn="len"> <audio data-vn="audio" preload="none"> </div>
   and is handled by one click listener on the document, so notes added by the poll work too. The length shown is the one the server stored (a recorder's
   file often does not know its own length). Only one note plays at a time; a finished note rewinds. The audio is fetched only when played. */
(function () {
  "use strict";
  var current = null;

  function clock(s) { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60); }
  function part(vn, name) { return vn.querySelector('[data-vn="' + name + '"]'); }
  function paint(vn, playing) {
    var btn = part(vn, "btn"), audio = part(vn, "audio"), total = parseFloat(vn.getAttribute("data-secs")) || 0;
    var at = audio.currentTime || 0;
    vn.classList.toggle("is-playing", playing);
    btn.querySelector(".sr-only").textContent = playing ? "Pause voice note" : "Play voice note";
    btn.setAttribute("aria-pressed", playing ? "true" : "false");
    part(vn, "fill").style.width = (total ? Math.min(100, (at / total) * 100) : 0) + "%";
    part(vn, "len").textContent = playing || at > 0 ? clock(at) + " / " + clock(total) : part(vn, "len").getAttribute("data-total");
  }

  function wire(vn) {
    if (vn.__vn) return;
    vn.__vn = true;
    var audio = part(vn, "audio");
    audio.addEventListener("timeupdate", function () { paint(vn, !audio.paused); });
    audio.addEventListener("pause", function () { paint(vn, false); });
    audio.addEventListener("play", function () { paint(vn, true); });
    audio.addEventListener("ended", function () { audio.currentTime = 0; paint(vn, false); });
    audio.addEventListener("error", function () { paint(vn, false); part(vn, "len").textContent = "Could not play"; });
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest('[data-vn="btn"]') : null;
    if (!btn) return;
    var vn = btn.closest(".vn");
    wire(vn);
    var audio = part(vn, "audio");
    if (!audio.paused) { audio.pause(); return; }
    if (current && current !== audio) current.pause();
    current = audio;
    var p = audio.play();
    if (p && p.catch) p.catch(function () { paint(vn, false); part(vn, "len").textContent = "Could not play"; });
  });
})();
