// Your family (F-043): share or copy an invite link, and ask before removing someone. Plain JavaScript; the page works without it.
(() => {
  async function copy(btn, link) {
    const field = btn.parentElement.querySelector("[data-link]");
    try {
      await navigator.clipboard.writeText(link);
    } catch (err) {
      if (field) { field.focus(); field.select(); try { document.execCommand("copy"); } catch (x) { /* the link is selected: copy it by hand */ } }
    }
    const was = btn.textContent;
    btn.textContent = "Copied";
    setTimeout(() => { btn.textContent = was; }, 1800);
  }
  document.addEventListener("click", async (e) => {
    const share = e.target.closest("button[data-share]");
    if (share) {
      const data = { title: share.dataset.shareTitle, text: share.dataset.shareText, url: share.dataset.share };
      if (typeof navigator.share === "function") {
        try { await navigator.share(data); } catch (err) {
          if (!err || err.name !== "AbortError") await copy(share, data.url); // closing the share sheet is fine; any other failure falls back to copying
        }
      } else {
        await copy(share, data.url);
      }
      return;
    }
    const btn = e.target.closest("button[data-copy]");
    if (btn) await copy(btn, btn.dataset.copy);
  });
  document.addEventListener("submit", (e) => {
    const ask = e.submitter && e.submitter.dataset ? e.submitter.dataset.confirm : "";
    if (ask && !window.confirm(ask)) e.preventDefault();
  });
  document.addEventListener("focusin", (e) => { if (e.target.matches && e.target.matches("[data-link]")) e.target.select(); });
})();
