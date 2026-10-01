// Your family (F-043): copy an invite link, and ask before removing someone. Plain JavaScript; the page works without it.
(() => {
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-copy]");
    if (!btn) return;
    const link = btn.dataset.copy;
    const field = btn.parentElement.querySelector("[data-link]");
    try {
      await navigator.clipboard.writeText(link);
    } catch (err) {
      if (field) { field.focus(); field.select(); try { document.execCommand("copy"); } catch (x) { /* the link is selected: copy it by hand */ } }
    }
    const was = btn.textContent;
    btn.textContent = "Copied";
    setTimeout(() => { btn.textContent = was; }, 1800);
  });
  document.addEventListener("submit", (e) => {
    const ask = e.submitter && e.submitter.dataset ? e.submitter.dataset.confirm : "";
    if (ask && !window.confirm(ask)) e.preventDefault();
  });
  document.addEventListener("focusin", (e) => { if (e.target.matches && e.target.matches("[data-link]")) e.target.select(); });
})();
