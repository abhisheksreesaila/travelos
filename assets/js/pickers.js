// GitAway pickers (F-051). Dresses the page's real <select>, <input type="date"> and <input type="time"> with themed ones.
// The native control stays in the page (clipped, not removed), so the form submits and the server validates exactly as before;
// without this script the page is a plain form. Markers (see gitaway/pickers.py): data-ga="chips|stepper", data-ga-range, data-ga-end,
// data-ga-label, data-ga-hint. Everything is sized in rem by pickers.css; no prices or trip rules live here.
(function () {
  "use strict";
  var uid = 0;
  var phone = window.matchMedia("(max-width: 720px)");
  var widgets = [];   // {refresh()} for every dressed control
  var open = null;    // the one open popover: {trigger, close(refocus)}
  var MO = (window.GA && GA.motion) || (function () { var r = function () { return Promise.resolve(); }; return { open: r, close: r, spring: r, flip: r, run: r, settle: r, reflow: function (e, c, o) { c(); if (o && o.during) o.during(); return r(); }, origin: function () { return null; }, box: function (e) { return e.getBoundingClientRect(); }, reduced: function () { return true; }, t: function () { return 240; } }; })();      // the one liquid motion (motion.js, F-109): a popover or sheet grows out of the field that opened it and folds back into it

  // ---- tiny helpers ---------------------------------------------------------------------------------------------------
  function el(tag, props, kids) {
    var n = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) {
      var v = props[k];
      if (v === false || v == null) return;
      if (k === "text") n.textContent = v; else if (k === "class") n.className = v; else n.setAttribute(k, v === true ? "" : v);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  var CHEVRON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" style="--ico:1.125rem"><path d="m6 9 6 6 6-6"/></svg>';
  function chevron() { var s = el("span", { class: "ga-chev", "aria-hidden": "true" }); s.innerHTML = CHEVRON; return s; }
  function fire(node) {
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
  }
  function labelOf(native) {
    if (native.dataset.gaLabel) return native.dataset.gaLabel;
    if (native.getAttribute("aria-label")) return native.getAttribute("aria-label");
    var lab = native.labels && native.labels[0];
    if (lab) {
      var c = lab.cloneNode(true);
      c.querySelectorAll("select,input,button,.ga-pick-btn,.ga-step,.ga-st-error,[class*=error]").forEach(function (x) { x.remove(); });
      var t = c.textContent.replace(/\s+/g, " ").trim();
      if (t) return t;
    }
    return native.name || "Choose";
  }
  function dress(native) {
    native.classList.add("ga-native");
    native.tabIndex = -1;
    native.setAttribute("aria-hidden", "true");
  }
  function place(native, node, before) { native.parentNode.insertBefore(node, before ? native : native.nextSibling); }
  function watchDisabled(native, refresh) {
    new MutationObserver(refresh).observe(native, { attributes: true, attributeFilter: ["disabled"] });
  }
  // Every dressed control registers here; a swapped-out form's controls are dropped (prune) so nothing keeps them in memory.
  function register(native, refresh, voice) {
    widgets.push({ native: native, refresh: refresh });
    native.addEventListener("change", refresh);
    native.addEventListener("input", refresh);
    if (voice) mirrorErrors(native, voice.invalid, voice.described, voice.focus);
  }
  function refreshAll() { widgets.forEach(function (w) { w.refresh(); }); }
  function prune() { widgets = widgets.filter(function (w) { return w.native.isConnected; }); }
  // A server error is on the native field: say it on the control the visitor sees, and send the error-summary link there too.
  function mirrorErrors(native, invalid, described, focus) {
    if (native.getAttribute("aria-invalid") === "true" && invalid) invalid.setAttribute("aria-invalid", "true");
    if (native.getAttribute("aria-describedby") && described) described.setAttribute("aria-describedby", native.getAttribute("aria-describedby"));
    if (native.id && focus) {
      focus.id = native.id + "-ga";
      document.querySelectorAll('a[href="#' + native.id + '"]').forEach(function (a) { a.setAttribute("href", "#" + focus.id); });
    }
  }

  // ---- popover shell (desktop: under the field; phone: a bottom sheet) --------------------------------------------------
  function closeOpen(refocus) { if (open) open.close(refocus); }

  function openPopover(trigger, box, onKey, focusEl) {
    closeOpen(false);
    var scrim = el("div", { class: "ga-scrim" });
    box.classList.add("ga-pop");
    document.body.appendChild(scrim);
    document.body.appendChild(box);
    trigger.setAttribute("aria-expanded", "true");

    function position() {
      if (phone.matches) { box.style.left = box.style.top = box.style.minWidth = ""; return; }
      var r = trigger.getBoundingClientRect(), vw = document.documentElement.clientWidth, vh = window.innerHeight, gap = 8;
      box.style.minWidth = r.width + "px";
      var w = box.offsetWidth, h = box.offsetHeight;
      var left = Math.max(gap, Math.min(r.left, vw - w - gap));
      var top = r.bottom + gap;
      if (top + h > vh - gap && r.top - h - gap > gap) top = r.top - h - gap;
      box.style.left = left + "px"; box.style.top = Math.max(gap, top) + "px";
    }
    function outside(e) { if (!box.contains(e.target) && !trigger.contains(e.target)) close(false); }
    function close(refocus) {
      document.removeEventListener("pointerdown", outside, true);
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
      trigger.setAttribute("aria-expanded", "false");
      if (open && open.box === box) open = null;
      if (refocus) trigger.focus();
      if (MO.reduced()) { box.remove(); scrim.remove(); return; }
      box.setAttribute("inert", ""); box.style.pointerEvents = "none"; scrim.style.pointerEvents = "none";
      MO.close(box, trigger.isConnected ? trigger : null, { scrim: scrim }).then(function () { box.remove(); scrim.remove(); });
    }
    box.addEventListener("keydown", function (e) {
      e.stopPropagation(); // the calendar modal also listens for Escape and Tab on the document
      if (e.key === "Escape") { e.preventDefault(); close(true); return; }
      if (e.key === "Tab") {
        var items = Array.prototype.filter.call(box.querySelectorAll("button:not([disabled]):not([tabindex='-1']), [role=listbox], [role=gridcell] button[tabindex='0']"), function (x) { return x.offsetParent; });
        if (!items.length) return;
        var a = items[0], z = items[items.length - 1];
        if (box.getAttribute("role") !== "dialog") { close(true); return; } // a list: Tab leaves it, from the field
        if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
        else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
        return;
      }
      onKey(e, close);
    });
    scrim.addEventListener("pointerdown", function () { close(false); });
    document.addEventListener("pointerdown", outside, true);
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    position();
    MO.open(box, trigger, { scrim: scrim });
    open = { trigger: trigger, box: box, close: close };
    if (focusEl) focusEl.focus({ preventScroll: true });
    return { close: close, position: position };
  }

  function bindTrigger(trigger, opener) {
    trigger.addEventListener("click", function (e) {
      e.preventDefault();
      if (open && open.trigger === trigger) open.close(true); else opener();
    });
    trigger.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); if (!(open && open.trigger === trigger)) opener(); }
    });
  }

  // ---- listbox: selects and times --------------------------------------------------------------------------------------
  function listbox(native, config) {
    // config: {options:[{value,label}], kind:"list"|"chips", text(), label, empty}
    var label = labelOf(native);
    var trigger = el("button", { type: "button", class: "ga-pick-btn", "aria-haspopup": "listbox", "aria-expanded": "false" });
    var val = el("span", { class: "ga-pick-val" });
    trigger.appendChild(val); trigger.appendChild(chevron());
    place(native, trigger, true);
    dress(native);

    function refresh() {
      var t = config.text();
      val.textContent = t;
      trigger.setAttribute("aria-label", label + ": " + t);
      trigger.disabled = native.disabled;
    }
    watchDisabled(native, refresh);
    register(native, refresh, { invalid: trigger, described: trigger, focus: trigger });
    refresh();

    function opener() {
      var opts = config.options(), chips = config.kind === "chips";
      var list = el("div", { class: "ga-listbox" + (chips ? " is-chips" : ""), role: "listbox", tabindex: "0", "aria-label": label });
      var nodes = opts.map(function (o) {
        var n = el("div", { class: "ga-opt", role: "option", id: "ga-o" + (++uid), "aria-selected": String(o.value === native.value), text: o.label });
        if (o.disabled) n.setAttribute("aria-disabled", "true");
        n.addEventListener("click", function () { if (!o.disabled) choose(o); });
        list.appendChild(n);
        return n;
      });
      var cur = Math.max(0, opts.findIndex(function (o) { return o.value === native.value; }));
      var typed = "", typedAt = 0;
      var box = el("div", { class: "ga-pop-list" }, [el("div", { class: "ga-pop-title", "aria-hidden": "true", text: label }), list]);
      var pop;
      function setActive(i, scroll) {
        cur = Math.max(0, Math.min(nodes.length - 1, i));
        nodes.forEach(function (n, k) { n.classList.toggle("is-active", k === cur); });
        list.setAttribute("aria-activedescendant", nodes[cur].id);
        if (scroll !== false) nodes[cur].scrollIntoView({ block: "nearest" });
      }
      function choose(o) {
        native.value = o.value;
        pop.close(true);
        fire(native);
      }
      function cols() {
        var top = nodes[0].offsetTop, c = 0;
        while (c < nodes.length && nodes[c].offsetTop === top) c++;
        return Math.max(1, c);
      }
      function onKey(e) {
        var k = e.key, step = chips ? cols() : 1;
        if (k === "ArrowDown") { e.preventDefault(); setActive(cur + step); }
        else if (k === "ArrowUp") { e.preventDefault(); setActive(cur - step); }
        else if (chips && k === "ArrowRight") { e.preventDefault(); setActive(cur + 1); }
        else if (chips && k === "ArrowLeft") { e.preventDefault(); setActive(cur - 1); }
        else if (k === "Home") { e.preventDefault(); setActive(0); }
        else if (k === "End") { e.preventDefault(); setActive(nodes.length - 1); }
        else if (k === "PageDown") { e.preventDefault(); setActive(cur + 8); }
        else if (k === "PageUp") { e.preventDefault(); setActive(cur - 8); }
        else if (k === "Enter" || (k === " " && !(typed && Date.now() - typedAt <= 700))) { e.preventDefault(); if (!opts[cur].disabled) choose(opts[cur]); }
        else if (k.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
          var now = Date.now();
          typed = (now - typedAt > 700 ? "" : typed) + k.toLowerCase(); typedAt = now;
          var from = typed.length === 1 ? cur + 1 : cur, hit = -1;
          for (var n = 0; n < opts.length && hit < 0; n++) {
            var i = (from + n) % opts.length;
            if (opts[i].label.toLowerCase().indexOf(typed) === 0) hit = i;
          }
          if (hit >= 0) setActive(hit);
        }
      }
      pop = openPopover(trigger, box, onKey, list);
      if (chips) box.classList.add("is-chips-box");
      pop.position();
      setActive(cur);
    }
    bindTrigger(trigger, opener);
    return trigger;
  }

  function dressSelect(native) {
    var mode = native.dataset.ga;
    if (mode === "stepper") return stepper(native);
    var chips = mode === "chips";
    listbox(native, {
      kind: chips ? "chips" : "list",
      options: function () {
        return Array.prototype.filter.call(native.options, function (o) { return !(chips && o.value === ""); })
          .map(function (o) { return { value: o.value, label: o.textContent.trim(), disabled: o.disabled }; });
      },
      text: function () { var o = native.options[native.selectedIndex]; return o ? o.textContent.trim() : "Choose"; },
    });
  }

  // ---- stepper: adults, kids --------------------------------------------------------------------------------------------
  function stepper(native) {
    var label = labelOf(native), hint = native.dataset.gaHint || "";
    var nums = Array.prototype.map.call(native.options, function (o) { return Number(o.value); }).filter(function (n) { return !isNaN(n); });
    var lo = Math.min.apply(null, nums), hi = Math.max.apply(null, nums);
    var low = label.toLowerCase();
    var less = el("button", { type: "button", class: "ga-step-btn", "aria-label": "Fewer " + low, text: "−" });
    var more = el("button", { type: "button", class: "ga-step-btn is-more", "aria-label": "More " + low, text: "+" });
    var num = el("span", { class: "ga-step-n", role: "status", "aria-live": "polite" });
    var box = el("span", { class: "ga-step", role: "group", "aria-label": label + (hint ? ", " + hint : "") }, [less, num, more]);
    dress(native);
    place(native, box, false);
    function refresh() {
      var n = Number(native.value);
      num.textContent = String(n);
      less.setAttribute("aria-disabled", String(n <= lo));
      more.setAttribute("aria-disabled", String(n >= hi));
    }
    function move(d) {
      var n = Number(native.value) + d;
      if (n < lo || n > hi) return;
      native.value = String(n);
      fire(native);
    }
    less.addEventListener("click", function (e) { e.preventDefault(); move(-1); });
    more.addEventListener("click", function (e) { e.preventDefault(); move(1); });
    register(native, refresh, { described: box, focus: less });
    // A click on the label text must not reach the hidden select: it goes to the stepper.
    var lab = native.labels && native.labels[0];
    if (lab) lab.addEventListener("click", function (e) { if (!box.contains(e.target)) { e.preventDefault(); less.focus(); } });
    refresh();
  }

  // ---- time -------------------------------------------------------------------------------------------------------------
  function clock(hhmm) {
    var p = /^(\d{1,2}):(\d{2})/.exec(hhmm || "");
    if (!p) return "";
    var h = +p[1];
    return (h % 12 || 12) + ":" + p[2] + " " + (h < 12 ? "AM" : "PM");
  }
  function dressTime(native) {
    listbox(native, {
      kind: "list",
      options: function () {
        var step = Number(native.step) >= 300 ? Number(native.step) / 60 : 15, out = [], seen = {};
        for (var m = 0; m < 1440; m += step) {
          var v = ("0" + Math.floor(m / 60)).slice(-2) + ":" + ("0" + (m % 60)).slice(-2);
          out.push({ value: v, label: clock(v) }); seen[v] = 1;
        }
        var cur = native.value.slice(0, 5);
        if (cur && !seen[cur]) { out.push({ value: cur, label: clock(cur) }); out.sort(function (a, b) { return a.value < b.value ? -1 : 1; }); }
        return out;
      },
      text: function () { return clock(native.value) || "Pick a time"; },
    });
  }

  // ---- dates: one calendar for a single date or a "Leave / Come home" range ------------------------------------------------
  function parse(iso) { var p = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || ""); return p ? new Date(Date.UTC(+p[1], +p[2] - 1, +p[3])) : null; }
  function iso(d) { return d.toISOString().slice(0, 10); }
  function plus(isoStr, n) { var d = parse(isoStr); d.setUTCDate(d.getUTCDate() + n); return iso(d); }
  function monthStart(isoStr) { return isoStr.slice(0, 8) + "01"; }
  function addMonths(isoStr, n) { var d = parse(monthStart(isoStr)); d.setUTCMonth(d.getUTCMonth() + n); return iso(d); }
  function fmt(isoStr, opts) { var d = parse(isoStr); return d ? d.toLocaleDateString("en-US", Object.assign({ timeZone: "UTC" }, opts)) : ""; }
  function short(isoStr) { return fmt(isoStr, { weekday: "short", month: "short", day: "numeric" }); }
  function nightsBetween(a, b) { return Math.round((parse(b) - parse(a)) / 86400000); }
  function nightsText(n) { return n + (n === 1 ? " night" : " nights"); }

  var DOW = [["S", "Sunday"], ["M", "Monday"], ["T", "Tuesday"], ["W", "Wednesday"], ["T", "Thursday"], ["F", "Friday"], ["S", "Saturday"]];

  function dressDates(start, end) {
    var range = !!end, pair = range ? [start, end] : [start];
    var triggers = pair.map(function (native) {
      var label = labelOf(native);
      var t = el("button", { type: "button", class: "ga-pick-btn ga-date-btn", "aria-haspopup": "dialog", "aria-expanded": "false" });
      var val = el("span", { class: "ga-pick-val" });
      t.appendChild(val); t.appendChild(el("span", { class: "ga-chev ga-cal-ico", "aria-hidden": "true" }));
      t.lastChild.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" style="--ico:1.25rem"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M8 3v4M16 3v4M3 10h18"/></svg>';
      place(native, t, true);
      dress(native);
      function refresh() {
        var txt = short(native.value) || "Pick a day";
        val.textContent = txt;
        t.setAttribute("aria-label", label + ": " + txt);
        t.disabled = native.disabled;
      }
      watchDisabled(native, refresh);
      register(native, refresh, { invalid: t, described: t, focus: t });
      refresh();
      return t;
    });
    var labels = pair.map(function (n, i) { return labelOf(n); });

    function opener(side) {
      var a = start.value, b = range ? end.value : "", phase = side === 1 && a ? "end" : "start";
      var min = start.min || "";
      var focus = (phase === "end" && b) || a || min || iso(new Date());
      if (min && focus < min) focus = min;
      var month = monthStart(focus);
      var trigger = triggers[side];

      var live = el("div", { class: "sr-only", "aria-live": "polite", "aria-atomic": "true" });
      var tiles = range ? el("div", { class: "ga-tiles" }, pair.map(function (n, i) {
        var tile = el("button", { type: "button", class: "ga-tile", "data-i": String(i) }, [el("span", { class: "ga-tile-k", text: labels[i] }), el("span", { class: "ga-tile-v" })]);
        tile.addEventListener("click", function () { phase = i ? "end" : "start"; render(true); });
        return tile;
      })) : "";
      var prev = el("button", { type: "button", class: "ga-cal-nav", "aria-label": "Previous month", text: "‹" });
      var next = el("button", { type: "button", class: "ga-cal-nav", "aria-label": "Next month", text: "›" });
      var title = el("span", { class: "ga-month", "aria-live": "polite" });
      var grid = el("div", { class: "ga-grid", role: "grid" });
      var chip = el("span", { class: "ga-nights", "aria-hidden": "true" });
      var tip = el("span", { class: "ga-tip", "aria-hidden": "true" });
      var done = el("button", { type: "button", class: "btn btn-primary ga-done", text: "Done" });
      var box = el("div", { class: "ga-pop-cal", role: "dialog", "aria-modal": "true", "aria-label": range ? "Choose your dates" : "Choose a date" }, [
        tiles, el("div", { class: "ga-cal-head" }, [prev, title, next]), grid, el("div", { class: "ga-cal-foot" }, [chip, tip, done]), live]);
      var pop;

      function commit() {
        var changed = [];
        if (start.value !== a) { start.value = a; changed.push(start); }
        if (range && b && end.value !== b) { end.value = b; changed.push(end); }
        changed.forEach(fire);
        if (range) b = end.value && end.value > a ? end.value : ""; // the form may have moved the return day (start.js keeps it after the leave day)
        refreshAll();
      }
      function announce(msg) { live.textContent = ""; setTimeout(function () { live.textContent = msg; }, 30); }
      function describe() {
        if (!range) return a ? short(a) : "No date picked";
        if (a && b) return "Leaving " + short(a) + ", back " + short(b) + ", " + nightsText(nightsBetween(a, b));
        if (a) return "Leaving " + short(a) + ". Now choose the day you come back";
        return "Choose the day you leave";
      }
      function pick(d) {
        if (min && d < min) return;
        if (!range) { a = d; commit(); pop.close(true); return; }
        if (phase === "start" || !a || d <= a) { a = d; if (b && b <= a) b = ""; phase = "end"; commit(); announce(describe()); } // a new leave day is kept at once, with the old return day if still later
        else { b = d; commit(); phase = "start"; announce(describe()); }
        focus = d; render(true);
      }
      function render(keepFocus) {
        month = monthStart(focus);
        title.textContent = fmt(month, { month: "long", year: "numeric" });
        prev.disabled = !!min && monthStart(min) >= month;
        prev.setAttribute("aria-disabled", String(prev.disabled));
        grid.setAttribute("aria-label", title.textContent);
        grid.textContent = "";
        var head = el("div", { class: "ga-row", role: "row" }, DOW.map(function (d) { return el("span", { class: "ga-dow", role: "columnheader", "aria-label": d[1], text: d[0] }); }));
        grid.appendChild(head);
        var first = parse(month), lead = first.getUTCDay(), cur = plus(month, -lead), row;
        for (var i = 0; i < 42; i++, cur = plus(cur, 1)) {
          if (i % 7 === 0) { if (i >= 35 && cur.slice(0, 7) !== month.slice(0, 7)) break; row = el("div", { class: "ga-row", role: "row" }); grid.appendChild(row); }
          if (cur.slice(0, 7) !== month.slice(0, 7)) { row.appendChild(el("span", { role: "gridcell", class: "ga-blank", "aria-hidden": "true" })); continue; }
          row.appendChild(dayCell(cur));
        }
        function dayCell(d) {
          var past = !!min && d < min, endpoint = d === a || (range && d === b), within = range && a && b && d > a && d < b;
          var label = fmt(d, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
          if (d === a) label += range ? ", leaving day" : ", selected"; else if (range && d === b) label += ", back day"; else if (within) label += ", in your trip";
          if (past) label += ", not available";
          var btn = el("button", { type: "button", class: "ga-day" + (endpoint ? " is-end" : "") + (within ? " is-in" : "") + (d === a && range && b ? " is-from" : "") + (range && d === b ? " is-to" : ""),
            "aria-label": label, tabindex: d === focus ? "0" : "-1", "data-d": d, disabled: past, text: String(+d.slice(8)) });
          btn.addEventListener("click", function () { pick(d); });
          return el("div", { role: "gridcell", "aria-selected": String(endpoint || !!within) }, [btn]);
        }
        if (tiles) {
          Array.prototype.forEach.call(tiles.children, function (t, i) {
            var v = i ? b : a;
            t.querySelector(".ga-tile-v").textContent = short(v) || "Pick a day";
            t.classList.toggle("is-on", (i ? "end" : "start") === phase);
            t.setAttribute("aria-pressed", String((i ? "end" : "start") === phase));
          });
        }
        chip.textContent = range ? (a && b ? nightsText(nightsBetween(a, b)) : "Choose dates") : (a ? short(a) : "Pick a day");
        tip.textContent = range ? (phase === "start" ? "Tap a start, then an end" : "Now tap the day you come back") : "Tap a day";
        if (keepFocus) { var f = grid.querySelector('[data-d="' + focus + '"]'); if (f) f.focus({ preventScroll: true }); }
      }
      function go(d, e) {
        if (e) e.preventDefault();
        if (min && d < min) d = min;
        focus = d; render(true);
      }
      function onKey(e) {
        var t = e.target;
        if (!(t && t.classList && t.classList.contains("ga-day"))) return;
        var k = e.key;
        if (k === "ArrowLeft") go(plus(focus, -1), e);
        else if (k === "ArrowRight") go(plus(focus, 1), e);
        else if (k === "ArrowUp") go(plus(focus, -7), e);
        else if (k === "ArrowDown") go(plus(focus, 7), e);
        else if (k === "Home") go(plus(focus, -parse(focus).getUTCDay()), e);
        else if (k === "End") go(plus(focus, 6 - parse(focus).getUTCDay()), e);
        else if (k === "PageUp") go(shiftMonth(focus, e.shiftKey ? -12 : -1), e);
        else if (k === "PageDown") go(shiftMonth(focus, e.shiftKey ? 12 : 1), e);
      }
      function shiftMonth(d, n) {
        var m = addMonths(d, n), last = plus(addMonths(m, 1), -1);
        var day = Math.min(+d.slice(8), +last.slice(8));
        return m.slice(0, 8) + ("0" + day).slice(-2);
      }
      prev.addEventListener("click", function () { if (!prev.disabled) { focus = shiftMonth(focus, -1); if (min && focus < min) focus = min; render(false); } });
      next.addEventListener("click", function () { focus = shiftMonth(focus, 1); render(false); });
      done.addEventListener("click", function () { pop.close(true); });

      pop = openPopover(trigger, box, onKey, null);
      render(false);
      pop.position();
      var f = grid.querySelector('[data-d="' + focus + '"]'); if (f) f.focus({ preventScroll: true });
      announce(range ? describe() : "");
    }
    triggers.forEach(function (t, i) { bindTrigger(t, function () { opener(i); }); });
  }

  // ---- finding the fields ---------------------------------------------------------------------------------------------------
  function enhance(root) {
    if (!root.querySelectorAll) return;
    var found = Array.prototype.slice.call(root.querySelectorAll("select:not([multiple]), input[type=date], input[type=time]"));
    if (root.matches && root.matches("select:not([multiple]), input[type=date], input[type=time]")) found.unshift(root);
    var ranges = {};
    found.forEach(function (n) {
      if (n.__ga) return;
      n.__ga = true;
      if (n.tagName === "SELECT") dressSelect(n);
      else if (n.type === "time") dressTime(n);
      else if (n.dataset.gaRange) {
        var key = (n.form ? Array.prototype.indexOf.call(document.forms, n.form) : -1) + ":" + n.dataset.gaRange;
        (ranges[key] = ranges[key] || {})[n.hasAttribute("data-ga-end") ? "end" : "start"] = n;
      } else dressDates(n, null);
    });
    Object.keys(ranges).forEach(function (k) {
      var g = ranges[k];
      if (g.start && g.end) dressDates(g.start, g.end);
      else dressDates(g.start || g.end, null);
    });
  }

  var queued = false, pending = [];
  new MutationObserver(function (muts) {
    var removed = false;
    muts.forEach(function (m) {
      if (m.removedNodes.length) removed = true;
      Array.prototype.forEach.call(m.addedNodes, function (n) { if (n.nodeType === 1 && !(n.classList.contains("ga-pop") || n.classList.contains("ga-scrim"))) pending.push(n); });
    });
    if (queued || !(pending.length || removed)) return;
    queued = true;
    requestAnimationFrame(function () { queued = false; var list = pending; pending = []; prune(); list.forEach(function (n) { if (document.body.contains(n)) enhance(n); }); });
  }).observe(document.body, { childList: true, subtree: true });

  document.addEventListener("reset", function () { setTimeout(refreshAll, 0); });
  window.addEventListener("pageshow", refreshAll);
  window.GAPickers = { count: function () { return widgets.length; } };
  enhance(document.body);
  document.documentElement.setAttribute("data-ga-ready", "");
})();
