// Pay sheet: the page behind it goes inert, focus starts inside and stays inside, Esc closes (back to the picks).
(() => {
  const dialog = document.getElementById("pay-dialog");
  const cancel = document.getElementById("pay-cancel");
  if (!dialog) return;
  document.querySelectorAll("#main, .ga-skip").forEach((el) => el.setAttribute("inert", ""));
  const focusable = () => [...dialog.querySelectorAll("a[href], button:not([disabled])")];
  const go = document.getElementById("pay-go");
  (go || focusable()[0]).focus();
  // Capture phase, so the workspace's own number-key shortcuts never fire behind the sheet.
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && cancel) {
      e.preventDefault();
      e.stopImmediatePropagation();
      location.href = cancel.getAttribute("href");
    } else if (e.key === "Tab") {
      const items = focusable();
      const a = items[0], z = items[items.length - 1];
      if (!dialog.contains(document.activeElement)) { e.preventDefault(); a.focus(); }
      else if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    } else {
      e.stopImmediatePropagation();
    }
  }, true);
  // A second tap while the request is in flight must not send a second POST (the server is idempotent anyway).
  dialog.querySelector("form").addEventListener("submit", (e) => {
    if (dialog.dataset.paying) e.preventDefault();
    dialog.dataset.paying = "1";
  });
  // Back from the next page can restore this one from the bfcache: make the button live again.
  window.addEventListener("pageshow", () => { delete dialog.dataset.paying; });
})();
