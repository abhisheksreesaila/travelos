/* The phone trip home (F-054). The server draws everything; this only enhances it without a reload:
   tab switching, the add sheet, and centring the selected day in the strip. Without it every tab and the + are plain links. */
(function () {
  "use strict";
  var app = document.getElementById("tp-app");
  if (!app) return;
  var tabs = ["today", "days", "notes"];
  var heading = document.getElementById("tp-title-h");
  var kicker = document.getElementById("tp-head-k");
  var sheet = document.getElementById("tp-sheet");
  var opener = null;

  function showTab(name) {
    tabs.forEach(function (t) {
      var panel = document.getElementById("tp-panel-" + t);
      var tab = document.getElementById("tp-tab-" + t);
      if (panel) panel.hidden = t !== name;
      if (tab) { if (t === name) tab.setAttribute("aria-current", "page"); else tab.removeAttribute("aria-current"); }
    });
    var panel = document.getElementById("tp-panel-" + name);
    if (heading && panel) heading.textContent = panel.getAttribute("data-title") || heading.textContent;
    if (kicker) kicker.textContent = name === "today" ? kicker.getAttribute("data-today") : kicker.getAttribute("data-other");
    app.setAttribute("data-tab", name);
    var url = new URL(location.href);
    if (name === "today") url.searchParams.delete("tab"); else url.searchParams.set("tab", name);
    url.searchParams.delete("add"); url.searchParams.delete("new");
    history.replaceState(null, "", url.pathname + url.search);
    window.scrollTo(0, 0);
    if (name === "today") centreDay();
  }

  function centreDay() {
    var strip = document.getElementById("tp-strip");
    var cur = strip && strip.querySelector('[aria-current="date"]');
    if (cur) strip.scrollLeft = cur.offsetLeft - (strip.clientWidth - cur.offsetWidth) / 2;
  }

  function openSheet(from) {
    if (!sheet) return;
    opener = from || document.activeElement;
    sheet.setAttribute("data-open", "");
    var title = document.getElementById("tp-title");
    if (title) title.focus();
  }

  function closeSheet() {
    if (!sheet) return;
    sheet.removeAttribute("data-open");
    if (opener && opener.focus) opener.focus();
  }

  document.addEventListener("click", function (e) {
    var tab = e.target.closest("[data-tab-link]");
    if (tab && tab.closest(".tp-tabs, .tp-up")) { e.preventDefault(); showTab(tab.getAttribute("data-tab-link")); return; }
    var open = e.target.closest("[data-open-sheet]");
    if (open && sheet) { e.preventDefault(); openSheet(open); return; }
    if (e.target.closest("[data-close-sheet]")) { e.preventDefault(); closeSheet(); }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && sheet && sheet.hasAttribute("data-open")) closeSheet();
  });

  centreDay();
  if (sheet && sheet.hasAttribute("data-open")) { var t = document.getElementById("tp-title"); if (t) t.focus(); }
})();
