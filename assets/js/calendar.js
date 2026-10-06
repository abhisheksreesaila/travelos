// Trip calendar (F-019). The server renders everything and stays the source of truth: this script only
//  - swaps the server-rendered #cal-app in place after a link or form (progressive: without it, they are normal pages),
//  - drives the day window (prev/next, strip chips, the "Days a-b of n" label),
//  - shows the "+ Add something fun" ghost on an empty hour,
//  - moves and resizes activities by pointer (15-minute snap) and by keyboard (Enter edits, arrows move, Shift+arrows resize),
//  - opens the notes drawer on phones and keeps focus inside the dialog,
//  - copies the fake invite link, and (F-020) a few seconds after load asks the server to play Mom's scripted add.
// Data only ever reaches the page as text or attributes from the server's HTML; nothing here builds markup from data.
(() => {
  "use strict";
  document.documentElement.classList.add("cal-js");

  // One hour is 3rem tall (calendar.py HH). Sizes are rem so the page scale in tokens.css rules; pointer maths needs px.
  const HOUR_REM = 3, SNAP = 15;
  const remPx = () => parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
  const hourPx = () => HOUR_REM * remPx();
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const app = () => document.getElementById("cal-app");
  const pad = (n) => String(n).padStart(2, "0");
  const hhmm = (m) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
  const clock = (m) => { const h = Math.floor(m / 60); return `${h % 12 || 12}:${pad(m % 60)} ${h < 12 ? "AM" : "PM"}`; };
  const minPerPx = () => 60 / hourPx();  // minutes per screen pixel
  const remPerMin = HOUR_REM / 60;

  // Blocks keep their true height. Mark the ones whose text does not fit (is-cut: CSS fades the edge) and the narrow
  // side-by-side lanes that cannot fit even one word (is-timeonly: the time shows, hover or focus opens the title).
  function markCut(root) {
    $$(".cal-act, a.cal-booked:not(.cal-ride)", root).forEach((b) => {  // the second kind: a block booked elsewhere (F-042)
      b.classList.add("is-measuring");
      b.classList.remove("is-cut", "is-timeonly");
      const title = $(".cal-title", b);
      if (b.classList.contains("cal-booked")) {  // a booked block only fades and opens on hover: no lanes, no time-only
        if (b.scrollHeight > b.clientHeight + 1 || b.scrollWidth > b.clientWidth + 1) b.classList.add("is-cut");
        b.classList.remove("is-measuring");
        return;
      }
      if (b.classList.contains("cal-lane") && !b.classList.contains("cal-short") && title.scrollWidth > title.clientWidth + 1) b.classList.add("is-timeonly");
      if (b.scrollHeight > b.clientHeight + 1 || b.scrollWidth > b.clientWidth + 1) b.classList.add("is-cut");
      b.classList.remove("is-measuring");
    });
  }

  // ---- soft navigation: fetch the page, swap #cal-app, keep scroll and focus --------------------------------------
  // Requests run one after another, so a click that arrives mid-flight is queued, never dropped.
  let queue = Promise.resolve();
  let opener = "";  // the block whose edit form is open, so closing the form can hand focus back to it
  const swap = (url, options, closing) => { queue = queue.then(() => doSwap(url, options, closing)).catch(() => {}); return queue; };
  async function doSwap(url, options, closing) {
    const cur = app();
    const scroller = $("#cal-scroll", cur), feed = $("#cal-feed", cur);
    const keep = {
      x: scroller ? scroller.scrollLeft : 0, y: scroller ? scroller.scrollTop : 0, feed: feed ? feed.scrollTop : 0,
      id: document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.id : "",
      drawer: !!$("#cal-notes.open", cur), sel: focusKey(document.activeElement),
    };
    try {
      const res = await fetch(url, { credentials: "same-origin", ...options });
      const doc = new DOMParser().parseFromString(await res.text(), "text/html");
      const next = doc.getElementById("cal-app");
      if (!next) { location.href = cur.dataset.base || "/calendar"; return; }
      const fresh = document.importNode(next, true);
      cur.replaceWith(fresh);
      const path = new URL(res.url, location.href);
      const p = path.pathname === "/calendar" ? path.searchParams : new URLSearchParams();
      const isLive = !!p.get("live");
      if (res.ok && path.pathname === "/calendar") {
        // The "just now" ring belongs to the moment: a reload must show a normal item, so the URL drops new and live.
        const keepQuery = new URLSearchParams(path.search);
        if (isLive) { keepQuery.delete("live"); keepQuery.delete("new"); }
        const qs = keepQuery.toString();
        history.replaceState(null, "", path.pathname + (qs ? `?${qs}` : ""));
      }
      // A friend's live add never steals focus from what the traveler is doing.
      keep.focus = isLive ? "" : p.get("undo") ? "undo" : p.get("new") ? p.get("new") : closing ? opener : "";
      setup(fresh, keep);
    } catch (err) {
      // A network error: never navigate to the POST url. Reload the calendar page we were on instead.
      location.href = cur.dataset.base || "/calendar";
    }
  }
  // A stable selector for the focused control, so a swap (a friend's live add, say) can hand focus back to it.
  function focusKey(el) {
    if (!el || el === document.body || !el.closest || !el.closest("#cal-app") || el.closest(".cal-act")) return "";
    const d = el.dataset || {};
    if (el.id) return `#${CSS.escape(el.id)}`;
    if (d.chip != null) return `[data-chip="${d.chip}"]`;
    if (d.dir != null) return `[data-dir="${d.dir}"]`;
    if (el.tagName === "A" && el.getAttribute("href")) return `a[href="${CSS.escape(el.getAttribute("href"))}"]`;
    if (el.name) return `${el.tagName.toLowerCase()}[name="${CSS.escape(el.name)}"]`;
    return "";
  }
  window.calSwap = (url) => swap(url);  // voice.js: swap the calendar in place for a GET
  const post = (url, data) => swap(url, { method: "POST", body: new URLSearchParams(data) });

  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-soft]");
    if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
    if (suppressClick) { e.preventDefault(); return; }
    if (a.id === "cal-ghost" && a.getAttribute("href") === "#") { e.preventDefault(); return; }
    e.preventDefault();
    const block = a.closest(".cal-act");
    if (!a.hasAttribute("data-close")) opener = block ? block.dataset.id : a.dataset.id || "";
    swap(a.href, undefined, a.hasAttribute("data-close"));
  });
  document.addEventListener("submit", (e) => {
    const f = e.target.closest("form[data-soft]");
    if (!f || e.defaultPrevented) return;
    e.preventDefault();
    // The submitter carries a quick-pick chip's name and value. Older browsers ignore the second argument: add it by hand.
    const fd = new FormData(f, e.submitter), who = e.submitter;
    if (who && who.name && !fd.getAll(who.name).includes(who.value)) fd.append(who.name, who.value);
    swap(f.action, { method: "POST", body: new URLSearchParams(fd) }, !!f.closest(".cal-modal"));
  });

  // ---- setup after every render ------------------------------------------------------------------------------------
  // Open the hour grid at the first booked item, or 8 AM when that is earlier in the day.
  function firstScroll(root, scroller) {
    const gs = +root.dataset.gridStart || 0;
    const booked = $$(".cal-booked", scroller).map((b) => +b.dataset.start).filter((m) => m >= 0);
    const target = Math.min(8 * 60, ...booked);
    return Math.max(0, Math.round((target - gs) / 60 * hourPx()) - 8);
  }
  function setup(root, keep) {
    markCut(root);
    const scroller = $("#cal-scroll", root);
    if (scroller) {
      const day = +scroller.dataset.w || 0;
      if (keep) { scroller.scrollLeft = keep.x; scroller.scrollTop = keep.y; }
      else { jump(scroller, day, false); scroller.scrollTop = firstScroll(root, scroller); }
      updateWindow(scroller);
    }
    const feed = $("#cal-feed", root);
    if (feed) feed.scrollTop = keep ? keep.feed : feed.scrollHeight;
    if (keep && keep.drawer && $("#cal-notes", root)) $("#cal-notes", root).classList.add("open");
    if (window.calVoice) window.calVoice(root);  // Talk to plan (voice.js) re-wires its panel after every swap
    const modal = $(".cal-modal", root);
    if (modal) {
      $$(".cal-bar, .cal-layout", root).forEach((el) => el.setAttribute("inert", ""));
      const first = $("[data-autofocus]", modal) || $("button, a[href], input", modal);
      if (first) first.focus();
    } else if (keep && keep.focus === "undo") {
      const undo = $(".cal-undo", root);
      if (undo) undo.focus();
    } else if (keep && (keep.focus || keep.id)) {
      const back = $(`[data-id="${CSS.escape(keep.focus || keep.id)}"]`, root);
      if (back) back.focus({ preventScroll: !keep.focus });
    } else if (keep && keep.sel) {
      const back = $(keep.sel, root);
      if (back) back.focus({ preventScroll: true });
    }
    if (feed && $(".cal-note-live", feed)) feed.scrollTop = feed.scrollHeight;
    armLive(root);
    const liveToast = $(".cal-toast-live", root);
    if (liveToast) setTimeout(() => { if (liveToast.isConnected) liveToast.remove(); }, 9000);
    const toggle = $("#cal-notes-toggle", root);
    if (toggle) toggle.setAttribute("aria-expanded", $("#cal-notes", root).classList.contains("open") ? "true" : "false");
  }

  // ---- scripted liveness (F-020): with Mom invited, the server adds her activity once, a few seconds after load -------
  // The page says data-live="1" only while it is still pending, so a reload after it happened asks for nothing.
  let liveTimer = 0;
  function armLive(root) {
    clearTimeout(liveTimer);
    if (root.dataset.live !== "1") return;
    liveTimer = setTimeout(function fire() {
      if (!app() || app().dataset.live !== "1") return;
      // Queued behind any swap in flight, then checked again at the moment it would run: a dialog opened, a drag started
      // or some typing begun in the meantime all make it wait, because the swap would drop them.
      queue = queue.then(async () => {
        const r = app(), a = document.activeElement;
        if (!r || r.dataset.live !== "1") return;
        if ($(".cal-modal", r) || drag || (a && r.contains(a) && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName))) { liveTimer = setTimeout(fire, 2000); return; }
        const data = { view: r.dataset.view };
        if (r.dataset.demo) data.demo = r.dataset.demo;
        if (r.dataset.trip) data.trip = r.dataset.trip;
        await doSwap("/calendar/live", { method: "POST", body: new URLSearchParams(data) });
      }).catch(() => {});
    }, 4000);
  }
  // "Show me" on the live toast jumps the day window to the day she added to (on a phone that day may be off screen).
  document.addEventListener("click", (e) => {
    const j = e.target.closest("[data-jump]");
    const scroller = $("#cal-scroll");
    if (!j || !scroller) return;
    e.preventDefault();
    jump(scroller, +j.dataset.jump);
  });

  // ---- copy the fake invite link ---------------------------------------------------------------------------------
  function flash(text) {
    if (window.GA && GA.toast) GA.toast(text);
  }
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-copy]");
    if (!b) return;
    let ok = false;
    try { await navigator.clipboard.writeText(b.dataset.copy); ok = true; } catch (err) {
      const f = $(".cal-linkfield");
      if (f) { f.select(); try { ok = document.execCommand("copy"); } catch (err2) { ok = false; } }
    }
    flash(ok ? "Invite link copied" : "Could not copy. Select the link and copy it by hand.");
  });

  // ---- the day window ----------------------------------------------------------------------------------------------
  const cols = (scroller) => $$(".cal-day", scroller);
  const winSize = (scroller) => Math.max(1, parseInt(getComputedStyle(scroller).getPropertyValue("--n") || getComputedStyle(app()).getPropertyValue("--n"), 10) || 1);
  const gutter = (scroller) => $(".cal-gutter", scroller).offsetWidth;
  function jump(scroller, day, smooth = false) {
    const col = cols(scroller)[Math.max(0, Math.min(day, cols(scroller).length - 1))];
    if (!col) return;
    // Instant: a smooth scroll fights scroll-snap and an in-flight re-render. The snap itself eases the landing.
    scroller.scrollTo({ left: col.offsetLeft - gutter(scroller), behavior: smooth && !reduced() ? "smooth" : "auto" });
    updateWindow(scroller);
  }
  function firstVisible(scroller) {
    const left = scroller.scrollLeft + gutter(scroller);
    const list = cols(scroller);
    const i = list.findIndex((c) => c.offsetLeft + c.offsetWidth / 2 > left);
    return i < 0 ? 0 : i;
  }
  function updateWindow(scroller) {
    const root = app(), list = cols(scroller), n = winSize(scroller), first = firstVisible(scroller);
    const last = Math.min(first + n, list.length);
    const label = $("#cal-range", root);
    if (label) label.textContent = n === 1 ? `Day ${first + 1} of ${list.length}` : `Days ${first + 1}–${last} of ${list.length}`;
    const strip = $(".cal-strip", root), lead = $$(".cal-chip", root)[first];
    if (strip && lead && (lead.offsetLeft < strip.scrollLeft || lead.offsetLeft + lead.offsetWidth > strip.scrollLeft + strip.clientWidth)) {
      strip.scrollLeft = Math.max(0, lead.offsetLeft - 8);
    }
    $$(".cal-chip", root).forEach((chip, i) => chip.classList.toggle("in-view", i >= first && i < last));
    const prev = $('[data-dir="-1"]', root), next = $('[data-dir="1"]', root);
    if (prev) prev.disabled = first <= 0;
    if (next) next.disabled = last >= list.length;
  }
  document.addEventListener("click", (e) => {
    const chip = e.target.closest(".cal-chip");
    const btn = e.target.closest("[data-dir]");
    const scroller = $("#cal-scroll");
    if (!scroller) return;
    if (chip) { e.preventDefault(); jump(scroller, +chip.dataset.chip); }
    else if (btn) { jump(scroller, firstVisible(scroller) + +btn.dataset.dir * winSize(scroller)); }
  });
  document.addEventListener("scroll", (e) => { if (e.target && e.target.id === "cal-scroll") updateWindow(e.target); }, true);
  addEventListener("resize", () => { const s = $("#cal-scroll"); if (s) updateWindow(s); if (app()) markCut(app()); });

  // ---- the ghost on an empty hour ----------------------------------------------------------------------------------
  function bodyGeometry(body) {
    const blocks = $$(".cal-block", body).filter((b) => !b.classList.contains("is-drag") && !b.classList.contains("cal-draft"));
    return blocks.map((b) => [+b.dataset.start, +b.dataset.end]);
  }
  function placeGhost(e) {
    const ghost = $("#cal-ghost");
    if (!ghost || e.pointerType === "touch" && e.type === "pointermove") return;
    const body = e.target.closest && e.target.closest(".cal-body");
    if (!body || e.target.closest(".cal-block, .cal-empty, .cal-ghost")) { if (!e.target.closest(".cal-ghost")) ghost.hidden = true; return; }
    const gs = +app().dataset.gridStart, ge = +app().dataset.gridEnd;
    const y = e.clientY - body.getBoundingClientRect().top;
    const start = gs + Math.floor(y / hourPx()) * 60;
    if (start + 30 > ge) { ghost.hidden = true; return; }
    let end = Math.min(start + 60, ge);
    for (const [s, en] of bodyGeometry(body)) {
      if (start < en && s < end) {
        if (s <= start) { ghost.hidden = true; return; }
        end = Math.min(end, s);
      }
    }
    if (end - start < 30) { ghost.hidden = true; return; }
    if (ghost.parentElement !== body) body.appendChild(ghost);
    ghost.hidden = false;
    ghost.style.top = `${(start - gs) * remPerMin}rem`;
    ghost.style.height = `calc(${(end - start) * remPerMin}rem - 0.25rem)`;
    ghost.style.left = "0";
    ghost.style.right = "0.25rem";
    const url = new URL(app().dataset.base, location.href);
    url.searchParams.set("add", body.dataset.day);
    url.searchParams.set("at", hhmm(start));
    ghost.setAttribute("href", url.pathname + url.search);
    ghost.setAttribute("aria-label", `Add something on day ${+body.dataset.day + 1} from ${clock(start)}`);
  }
  document.addEventListener("pointermove", placeGhost);
  document.addEventListener("pointerdown", (e) => { if (e.pointerType === "touch") placeGhost(e); });

  // ---- moving and resizing by pointer ------------------------------------------------------------------------------
  let drag = null, suppressClick = false;
  const dur = (b) => +b.dataset.end - +b.dataset.start;
  function paint(b, day, start, end) {
    const gs = +app().dataset.gridStart;
    b.dataset.day = day; b.dataset.start = start; b.dataset.end = end;
    b.style.setProperty("--top", `${(start - gs) * remPerMin}rem`);
    b.style.setProperty("--h", `${(end - start) * remPerMin}rem`);
    const time = $(".cal-time", b);
    if (time) time.textContent = clock(start);
  }
  function clashes(day, start, end) {
    const body = $(`.cal-body[data-day="${day}"]`);
    return !!body && $$(".cal-booked", body).some((b) => start < +b.dataset.end && +b.dataset.start < end);
  }
  document.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "touch" || e.button !== 0 || $(".cal-modal") || app().classList.contains("cal-readonly")) return;  // a viewer cannot move or resize
    const b = e.target.closest(".cal-act");
    if (!b) return;
    drag = { b, mode: e.target.closest(".cal-resize") ? "resize" : "move", x: e.clientX, y: e.clientY,
             day: +b.dataset.day, start: +b.dataset.start, end: +b.dataset.end, moved: false, id: e.pointerId };
  });
  document.addEventListener("pointermove", (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.moved) {
      if (Math.hypot(dx, dy) < 5) return;
      drag.moved = true;
      drag.b.classList.add("is-drag");
      drag.b.setPointerCapture(e.pointerId);
      const g = $("#cal-ghost"); if (g) g.hidden = true;
    }
    const gs = +app().dataset.gridStart, ge = +app().dataset.gridEnd;
    const delta = Math.round((dy * minPerPx()) / SNAP) * SNAP;
    let { day, start, end } = drag;
    if (drag.mode === "resize") {
      end = Math.max(start + 30, Math.min(ge, drag.end + delta));
    } else {
      const len = drag.end - drag.start;
      start = Math.max(gs, Math.min(ge - len, drag.start + delta));
      end = start + len;
      drag.b.style.pointerEvents = "none";
      const under = document.elementFromPoint(e.clientX, e.clientY);
      drag.b.style.pointerEvents = "";
      const body = under && under.closest(".cal-body");
      if (body) {
        day = +body.dataset.day;
        if (drag.b.parentElement !== body) body.appendChild(drag.b);
      }
    }
    paint(drag.b, day, start, end);
    drag.b.classList.toggle("is-clash", clashes(day, start, end));
  });
  function finishDrag(e) {
    if (!drag || e.pointerId !== drag.id) return;
    const { b, moved, day, start, end } = drag;
    drag = null;
    if (!moved) return;
    b.classList.remove("is-drag");
    suppressClick = true;
    setTimeout(() => { suppressClick = false; }, 0);
    const now = { day: +b.dataset.day, start: +b.dataset.start, end: +b.dataset.end };
    if (now.day === day && now.start === start && now.end === end) return;
    sendMove(b);
  }
  document.addEventListener("pointerup", finishDrag);
  document.addEventListener("pointercancel", finishDrag);
  function sendMove(b) {
    const root = app();
    const data = { day: b.dataset.day, start: hhmm(+b.dataset.start), end: hhmm(+b.dataset.end), view: root.dataset.view };
    if (root.dataset.demo) data.demo = root.dataset.demo;
    if (root.dataset.trip) data.trip = root.dataset.trip;
    return post(`/calendar/activities/${encodeURIComponent(b.dataset.id)}/move`, data);
  }

  // ---- keyboard: Enter edits (the link's own action), arrows move by 15 minutes, Shift+arrows resize, Delete removes --
  let keyTimer = 0;
  document.addEventListener("keydown", (e) => {
    const modal = $(".cal-modal");
    if (modal) {
      if (e.key === "Escape") { const c = $("[data-close]", modal); if (c) { e.preventDefault(); c.click(); } }
      else if (e.key === "Tab") {
        const items = $$("a[href], button:not([disabled]), input:not([type=hidden]), select", $(".cal-dialog", modal)).filter((x) => x.offsetParent);
        const a = items[0], z = items[items.length - 1];
        if (!modal.contains(document.activeElement)) { e.preventDefault(); a.focus(); }
        else if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
        else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
      }
      return;
    }
    const b = e.target.closest && e.target.closest(".cal-act");
    if (!b || e.target !== b) return;
    const gs = +app().dataset.gridStart, ge = +app().dataset.gridEnd;
    let day = +b.dataset.day, start = +b.dataset.start, end = +b.dataset.end;
    const days = $$(".cal-day").length;
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      const root = app(), data = { view: root.dataset.view };
      if (root.dataset.demo) data.demo = root.dataset.demo;
      if (root.dataset.trip) data.trip = root.dataset.trip;
      post(`/calendar/activities/${encodeURIComponent(b.dataset.id)}/delete`, data);
      return;
    }
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      const d = e.key === "ArrowUp" ? -SNAP : SNAP;
      if (e.shiftKey) end = Math.max(start + 30, Math.min(ge, end + d));
      else if (start + d >= gs && end + d <= ge) { start += d; end += d; }
    } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      day = Math.max(0, Math.min(days - 1, day + (e.key === "ArrowLeft" ? -1 : 1)));
    } else return;
    e.preventDefault();
    const body = $(`.cal-body[data-day="${day}"]`);
    if (body && b.parentElement !== body) { body.appendChild(b); b.focus({ preventScroll: true }); }
    const sc = $("#cal-scroll");
    if (sc && body) {
      const first = firstVisible(sc), n = winSize(sc);
      if (day < first) jump(sc, day); else if (day >= first + n) jump(sc, day - n + 1);
    }
    paint(b, day, start, end);
    b.classList.toggle("is-clash", clashes(day, start, end));
    b.setAttribute("aria-label", `${$(".cal-title", b).textContent}, ${clock(start)} to ${clock(end)}, moving`);
    clearTimeout(keyTimer);
    keyTimer = setTimeout(() => sendMove(b), 450);
  });

  // ---- notes drawer on phones --------------------------------------------------------------------------------------
  document.addEventListener("click", (e) => {
    const t = e.target.closest("#cal-notes-toggle");
    if (!t) return;
    const drawer = $("#cal-notes");
    const open = drawer.classList.toggle("open");
    t.setAttribute("aria-expanded", open ? "true" : "false");
    const feed = $("#cal-feed");
    if (open && feed) feed.scrollTop = feed.scrollHeight;
  });

  if (app()) setup(app(), null);
  // Back or forward from the bfcache: the server copy is the truth, so re-fetch the current page.
  addEventListener("pageshow", (e) => { if (e.persisted && app()) swap(location.pathname + location.search); });
})();
