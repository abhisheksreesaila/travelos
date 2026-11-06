/* Plan it for me (F-193): three small things on /plan-for-me, no framework.
   1. one age picker per kid: the Kids number shows that many of the pickers the server drew (all are there without JavaScript).
   2. a signed-out visitor's answers are kept in this browser (sessionStorage: this tab only, gone when it closes, an hour at most) while they sign in, and put back once on the form when they come back.
   3. an order that is still being paid or built polls its own status and reloads the page when it changes. */
(function () {
  var KEY = "ga-plan-for-me";
  var form = document.getElementById("pf-form");

  if (form) {
    var kids = document.getElementById("pf-nkids");
    var show = function () {
      var n = parseInt(kids.value, 10) || 0;
      document.querySelectorAll("#pf-kids .pf-kid").forEach(function (box, i) { box.hidden = i >= n; });
    };
    kids.addEventListener("change", show);
    show();

    var out = form.getAttribute("data-signed-out") === "1";
    var read = function () {
      var data = {};
      new FormData(form).forEach(function (v, k) { if (typeof v === "string") data[k] = v; });
      return data;
    };
    if (out) {
      form.addEventListener("input", function () {
        try { sessionStorage.setItem(KEY, JSON.stringify({ at: Date.now(), data: read() })); } catch (e) { /* private mode: the answers are simply not kept */ }
      });
    } else {
      try {
        var saved = JSON.parse(sessionStorage.getItem(KEY) || "null");
        sessionStorage.removeItem(KEY);
        if (saved && Date.now() - saved.at < 3600 * 1000 && !form.elements.where.value) {
          Object.keys(saved.data).forEach(function (k) {
            var el = form.elements[k];
            if (el && el.type !== "hidden" && el.type !== "submit") {
              if (el.length && el[0] && el[0].type === "radio") { for (var i = 0; i < el.length; i++) el[i].checked = el[i].value === saved.data[k]; }
              else el.value = saved.data[k];
            }
          });
          show();
        }
      } catch (e) { /* nothing kept, nothing to put back */ }
    }
    form.addEventListener("submit", function () {
      var go = document.getElementById("pf-go");
      window.setTimeout(function () { if (go) go.disabled = true; }, 0);      // one tap makes one order
    });
  }

  var poll = document.querySelector("[data-pf-poll]");
  if (poll) {
    var url = poll.getAttribute("data-pf-poll");
    var now = poll.getAttribute("data-status");
    var tick = function () {
      fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin", cache: "no-store" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) { if (j && j.status !== now) { window.location.reload(); } else { window.setTimeout(tick, 3000); } })
        .catch(function () { window.setTimeout(tick, 6000); });
    };
    window.setTimeout(tick, 3000);
  }
})();
