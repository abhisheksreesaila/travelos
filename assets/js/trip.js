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
    if (tab && tab.closest(".tp-tabs, .tp-up, .tp-notestrip")) { e.preventDefault(); showTab(tab.getAttribute("data-tab-link")); return; }
    var open = e.target.closest("[data-open-sheet]");
    if (open && sheet) { e.preventDefault(); openSheet(open); return; }
    if (e.target.closest("[data-close-sheet]")) { e.preventDefault(); closeSheet(); }
  });

  var FOCUSABLE = 'a[href]:not([tabindex="-1"]), button:not([disabled]), input:not([type=hidden]):not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

  document.addEventListener("keydown", function (e) {
    if (!sheet || !sheet.hasAttribute("data-open")) return;
    if (e.key === "Escape") { closeSheet(); return; }
    if (e.key !== "Tab") return;
    // keep focus inside the open sheet: wrap at both ends
    var items = Array.prototype.filter.call(sheet.querySelectorAll(FOCUSABLE), function (el) { return el.offsetParent !== null; });
    if (!items.length) return;
    var first = items[0], last = items[items.length - 1];
    if (!sheet.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  centreDay();
  if (sheet && sheet.hasAttribute("data-open")) { var t = document.getElementById("tp-title"); if (t) t.focus(); }
})();
