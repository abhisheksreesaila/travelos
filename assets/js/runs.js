/* Runs in a chat (F-178): which messages are the first and last of a run from one person (data-by: who, plan and part; a plan change or anyone else ends it). The server draws the same
   classes (tab_family.fragment); this keeps them right wherever a script adds or moves messages: thread.js (the Family tab, a plan's chat, the panel's Family), and the plan pane's own
   chat (day_dock.js, day_family.js). GA.runs.fix(list) regroups now; GA.runs.watch(list) does it after every change to the list's children (once per list; it ends with the list). */
(function () {
  "use strict";
  var GA = window.GA = window.GA || {};
  if (GA.runs) return;
  function fix(list) {
    var prev = null;
    Array.prototype.forEach.call(list.children, function (el) {
      if (!el.classList.contains("ft-msg")) { prev = null; return; }
      var same = prev && prev.getAttribute("data-by") === el.getAttribute("data-by");
      if (prev) prev.classList.toggle("ft-last", !same);
      el.classList.toggle("ft-first", !same);
      el.classList.add("ft-last");
      prev = el;
    });
  }
  function watch(list) {
    if (!list || list._runs) return;
    list._runs = new MutationObserver(function () { fix(list); });
    list._runs.observe(list, { childList: true });
    fix(list);
  }
  GA.runs = { fix: fix, watch: watch };
})();
