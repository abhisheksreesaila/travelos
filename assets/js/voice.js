// Talk to plan (F-024). The server renders everything (the sentence, the question, the plans, where they land); this script only
//  - plays the scripted sentence word by word with a listening animation when the mic was just tapped (data-hear),
//  - keeps the ticked plans and the draft blocks in the calendar in step, and the Apply button's count,
//  - lets Apply animate the drafts settling into the calendar before the form posts (instantly with reduced motion).
// No audio is captured and the page never asks for the microphone: the "voice" is a fixed sentence already in the page.
(() => {
  "use strict";
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const WORD_MS = 170, COMMA_MS = 320;
  let timer = 0;

  function dropHear() {
    // The listening belongs to the moment of the tap: a reload or a later swap must not replay it.
    const url = new URL(location.href);
    if (!url.searchParams.has("hear")) return;
    url.searchParams.delete("hear");
    history.replaceState(null, "", url.pathname + (url.search || ""));
  }

  function play(root, panel) {
    const words = $$(".vo-w", panel);
    const app = root;
    clearTimeout(timer);
    dropHear();
    if (reduced() || !words.length) { panel.removeAttribute("data-hear"); return; }  // prefers-reduced-motion: everything shows at once
    panel.classList.add("is-typing", "is-listening");
    app.setAttribute("data-hearing", "");
    const hint = $("#vo-hintline", panel);
    let i = 0;
    const step = () => {
      if (!panel.isConnected) return;
      if (i < words.length) {
        const w = words[i++];
        w.classList.add("is-on");
        timer = setTimeout(step, /[,.]\s*$/.test(w.textContent) ? WORD_MS + COMMA_MS : WORD_MS);
        return;
      }
      timer = setTimeout(() => {
        if (!panel.isConnected) return;
        panel.classList.remove("is-typing", "is-listening");
        app.removeAttribute("data-hearing");
        panel.removeAttribute("data-hear");
        const after = $(".vo-after", panel);
        if (after) after.classList.add("vo-pop");
        if (hint) hint.textContent = "Got it. One quick question";
        const first = $(".vo-chip", panel);
        if (first && !first.matches("[aria-current]")) first.focus({ preventScroll: true });
      }, 450);
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
      if (form.getAttribute("data-go")) return;
      const drafts = $$(".cal-draft:not([hidden])", root);
      if (reduced() || !drafts.length) return;
      e.preventDefault();
      form.setAttribute("data-go", "1");
      drafts.forEach((d, i) => { d.style.setProperty("--i", i); d.classList.add("is-applying"); });
      setTimeout(() => form.submit(), 650 + drafts.length * 70);
    });
  }

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
