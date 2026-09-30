const body = document.body;

function isEditing(target) {
  return target instanceof Element && Boolean(
    target.closest("input, textarea, select, [contenteditable=''], [contenteditable='true'], [role='textbox']")
  );
}

function creatorVariant() {
  const value = (new URL(window.location.href).searchParams.get("variant") || "A").toUpperCase();
  return ["A", "B", "C"].includes(value) ? value : "A";
}

function setVariant(variant, { writeHistory = true } = {}) {
  if (!["A", "B", "C"].includes(variant)) return;
  body.dataset.creatorVariant = variant;

  document.querySelectorAll("a[data-creator-variant]").forEach((link) => {
    const selected = link.dataset.creatorVariant === variant;
    link.classList.toggle("is-selected", selected);
    if (selected) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
    link.href = `/creators?variant=${link.dataset.creatorVariant}`;
  });
  document.querySelectorAll("[data-variant-live]").forEach((node) => {
    node.textContent = `Variant ${variant}`;
  });

  if (writeHistory && body.dataset.prototypePage === "creators") {
    const url = new URL(window.location.href);
    url.searchParams.set("variant", variant);
    window.history.pushState({ variant }, "", url);
  }
  document.dispatchEvent(new CustomEvent("travelos:variantchange", { detail: { variant } }));
}

function updateVariantRoutes() {
  const variant = body.dataset.creatorVariant || "A";
  document.querySelectorAll("[data-variant-route]").forEach((link) => {
    const url = new URL(link.dataset.variantRoute, window.location.origin);
    url.searchParams.set("variant", variant);
    link.href = `${url.pathname}${url.search}${url.hash}`;
  });
}

if (body.dataset.prototypePage === "creators") {
  const initial = creatorVariant();
  setVariant(initial, { writeHistory: false });

  document.querySelectorAll("a[data-creator-variant]").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (event.button !== 0 || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      event.preventDefault();
      setVariant(link.dataset.creatorVariant);
      updateVariantRoutes();
    });
  });

  document.querySelectorAll("[data-variant-step]").forEach((button) => {
    button.addEventListener("click", () => {
      const variants = ["A", "B", "C"];
      const index = variants.indexOf(body.dataset.creatorVariant || "A");
      const step = Number(button.dataset.variantStep) < 0 ? -1 : 1;
      const next = variants[(index + step + variants.length) % variants.length];
      setVariant(next);
      updateVariantRoutes();
    });
  });

  window.addEventListener("popstate", () => {
    setVariant(creatorVariant(), { writeHistory: false });
    updateVariantRoutes();
  });

  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || isEditing(event.target)) return;
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    const current = body.dataset.creatorVariant || "A";
    const index = ["A", "B", "C"].indexOf(current);
    const next = ["A", "B", "C"][(index + (event.key === "ArrowRight" ? 1 : 2)) % 3];
    event.preventDefault();
    setVariant(next);
    updateVariantRoutes();
    document.querySelector(`a[data-creator-variant="${next}"]`)?.focus({ preventScroll: true });
  });

  updateVariantRoutes();
}
