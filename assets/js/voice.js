// Talk to plan (F-024). The server renders everything (the sentence, the question, the plans, where they land); this script only
//  - plays the scripted sentence word by word with a listening animation when the mic was just tapped (data-hear),
//  - announces the heard sentence and the question to screen readers when hearing ends (the typed bubble itself is aria-hidden),
//  - keeps the ticked plans and the draft blocks in the calendar in step, and the Apply button's count,
//  - lets Apply animate the drafts settling into the calendar before the form posts (instantly with reduced motion).
// No audio is captured and the page never asks for the microphone: the "voice" is a fixed sentence already in the page.
(() => {
  "use strict";
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;  // prefers-reduced-motion: no typing, no pulse, no pop
  const WORD_MS = 170, COMMA_MS = 320;
  let timer = 0;

  function dropHear() {
    // The listening belongs to the moment of the tap: a reload or a later swap must not replay it.
    const url = new URL(location.href);
    if (!url.searchParams.has("hear")) return;
    url.searchParams.delete("hear");
    history.replaceState(null, "", url.pathname + (url.search || ""));
  }

  // The end of hearing, the same on every path (typed, or all at once with reduced motion): the panel stops listening, the hint
  // and the mic label go back to normal, the sentence and the question are announced, and focus lands on the first answer.
  function finish(root, panel) {
    panel.classList.remove("is-typing", "is-listening");
    root.removeAttribute("data-hearing");
    panel.removeAttribute("data-hear");
    const after = $(".vo-after", panel);
    if (after && !reduced()) after.classList.add("vo-pop");
    const hint = $("#vo-hintline", panel);
    if (hint) hint.textContent = "Got it. One quick question";
    const mic = $("#vo-mic", panel);
    if (mic) mic.setAttribute("aria-label", "Play the demo sentence again");
    const live = $("#vo-live", panel), full = $(".vo-full", panel), ask = $("#vo-q", panel);
    if (live) setTimeout(() => { live.textContent = `You said: ${full ? full.textContent : ""} Got it. One quick question. ${ask ? ask.textContent : ""}`; }, 150);
    // After a beat: calendar.js hands focus back to the control it swapped out (the mic) just after this runs on the reduced-motion path.
    const first = $(".vo-chip", panel);
    if (first) setTimeout(() => first.isConnected && first.focus({ preventScroll: true }), 80);
  }

  function play(root, panel) {
    const words = $$(".vo-w", panel);
    clearTimeout(timer);
    dropHear();
    if (reduced() || !words.length) { finish(root, panel); return; }
    panel.classList.add("is-typing", "is-listening");
    root.setAttribute("data-hearing", "");
    const cursor = $(".vo-cursor", panel);
    let i = 0;
    const step = () => {
      if (!panel.isConnected) return;
      if (i < words.length) {
        const w = words[i++];
        w.classList.add("is-on");
        if (cursor) w.after(cursor);  // the "|" follows the last word heard
        timer = setTimeout(step, /[,.]\s*$/.test(w.textContent) ? WORD_MS + COMMA_MS : WORD_MS);
        return;
      }
      timer = setTimeout(() => { if (panel.isConnected) finish(root, panel); }, 450);
    };
    step();
  }

  function wire(root, panel) {
    const form = $("#vo-form", panel);
    if (!form) return;
    const btn = $("#vo-apply", form);
    const boxes = $$(".vo-check", form);
    const locked = btn && btn.hasAttribute("data-locked");
    const draft = (box) => $(`.cal-draft[data-key="${CSS.escape(box.getAttribute("data-plan"))}"]`, root);
    // Seeded from the boxes as the page loads (a browser may restore ticks on Back) and kept in step on every change.
    const sync = () => {
      let n = 0;
      boxes.forEach((box) => {
        const d = draft(box);
        if (d) d.hidden = !box.checked;
        if (box.checked && !box.disabled) n++;
      });
      if (btn && !locked) {
        btn.textContent = `Add ${n} plan${n === 1 ? "" : "s"}`;
        btn.disabled = n === 0;
      }
    };
    boxes.forEach((box) => box.addEventListener("change", sync));
    sync();
    form.addEventListener("submit", (e) => {
      // One post only: a second click or Enter while the first is under way must not post again (it would lose the undo toast).
      if (form.getAttribute("data-go")) { e.preventDefault(); return; }
      form.setAttribute("data-go", "1");
      const drafts = $$(".cal-draft:not([hidden])", root);
      if (reduced() || !drafts.length) { if (btn) setTimeout(() => { btn.disabled = true; }, 0); return; }
      e.preventDefault();
      if (btn) btn.disabled = true;
      drafts.forEach((d, i) => { d.style.setProperty("--i", i); d.classList.add("is-applying"); });
      setTimeout(() => form.submit(), 650 + drafts.length * 70);
    });
  }

  // The mic is a real button in a GET form (Space and Enter work, and it works without this script): swap the calendar in place.
  document.addEventListener("submit", (e) => {
    const f = e.target.closest && e.target.closest(".vo-micform");
    if (!f || e.defaultPrevented || !window.calSwap) return;
    e.preventDefault();
    window.calSwap(f.action + "?" + new URLSearchParams(new FormData(f)).toString());
  });

  window.calVoice = (root) => {
    const panel = $("#cal-voice", root);
    if (!panel) { clearTimeout(timer); return; }
    wire(root, panel);
    if (panel.hasAttribute("data-hear")) play(root, panel);
  };
  const app = document.getElementById("cal-app");
  if (app) window.calVoice(app);
  addEventListener("pageshow", (e) => { if (e.persisted) $$(".cal-draft.is-applying").forEach((d) => d.classList.remove("is-applying")); });
})();
