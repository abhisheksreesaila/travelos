// Demo sign-in dialog: focus starts inside, Tab stays inside, Esc goes back (same as Cancel).
(() => {
  const dialog = document.getElementById("si-dialog");
  const cancel = document.getElementById("si-cancel");
  if (!dialog) return;
  const focusable = () => [...dialog.querySelectorAll("a[href], button:not([disabled]), input:not([type=hidden])")];
  const first = focusable()[0];
  if (first) first.focus();
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && cancel) {
      e.preventDefault();
      location.href = cancel.getAttribute("href");
    } else if (e.key === "Tab") {
      const items = focusable();
      const a = items[0], z = items[items.length - 1];
      if (!dialog.contains(document.activeElement)) { e.preventDefault(); a.focus(); }
      else if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    }
  });
})();
