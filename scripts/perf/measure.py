"""F-168: measure how each common tap feels on the trip canvas, phone and laptop, with a 4x slower CPU and 180 ms added to every request.

Needs the measuring server (scripts/perf/serve.py) and a seeded, signed-in state (scripts/perf/seed.py). Writes one JSON line per run to OUT.

    python scripts/perf/measure.py http://127.0.0.1:5020 /tmp/x/state.json /tmp/x/runs.jsonl [phone|laptop|both|stale] [reps] [cpu-slowdown] [latency-ms]

What is measured, per interaction:
  - input:   the input event's own timestamp (pointerdown / touchstart / keydown, or a mark just before a script-made Back)
  - frames:  what the screen showed, from a CDP screencast (a frame arrives only when the picture changed; identical pictures are dropped).
             first = first changed picture after the input, bursts = runs of changed pictures (a gap of 120 ms or more splits them), settled = the end of the last burst
  - net:     every request after the input (Resource Timing: start, first byte, end, bytes on the wire, the server's own time from Server-Timing)
  - steps:   view transition called / ready / finished, Web Animations and CSS animations started, DOM mutation bursts
  - jank:    long tasks, long animation frames (with the script and its forced layout time), dropped frames from a rAF log, CDP layout and style counts
"""
import asyncio
import base64
import hashlib
import json
import sys
import time

from playwright.async_api import async_playwright

PHONE = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
LAPTOP = dict(viewport={"width": 1440, "height": 900}, device_scale_factor=1, is_mobile=False, has_touch=False)
LATENCY = 180
CPU = 4

RECORDER = """(() => {
  const P = window.__p = { ev: [], frames: [], lt: [], loaf: [], armed: false, input: null };
  const T = () => performance.now();
  (function loop(t) { P.frames.push(t); requestAnimationFrame(loop); })(T());
  try { new PerformanceObserver(l => l.getEntries().forEach(e => P.lt.push([e.startTime, e.duration]))).observe({ type: 'longtask', buffered: true }); } catch (e) {}
  try { new PerformanceObserver(l => l.getEntries().forEach(e => P.loaf.push({ start: e.startTime, dur: e.duration, block: e.blockingDuration,
      scripts: e.scripts.map(s => ({ src: (s.sourceURL || '').split('/').pop().split('?')[0], fn: s.sourceFunctionName, inv: s.invoker, dur: Math.round(s.duration), forced: Math.round(s.forcedStyleAndLayoutDuration) })) })))
      .observe({ type: 'long-animation-frame', buffered: true }); } catch (e) {}
  ['pointerdown', 'touchstart', 'keydown', 'mousedown'].forEach(t => addEventListener(t, e => { if (P.armed && P.input === null) P.input = { t: e.timeStamp, type: t }; }, true));
  ['click', 'pointerup', 'touchend', 'keyup'].forEach(t => addEventListener(t, e => { if (P.armed) P.ev.push([t, e.timeStamp]); }, true));
  ['animationstart', 'animationend', 'transitionstart', 'transitionend'].forEach(t => addEventListener(t, e => { if (P.armed) P.ev.push([t, T(), (e.animationName || e.propertyName || ''), (e.target.className && e.target.className.baseVal === undefined ? String(e.target.className).slice(0, 40) : e.target.tagName)]); }, true));
  const mo = new MutationObserver(ms => { if (P.armed) P.ev.push(['mut', T(), ms.length]); });
  const start = () => mo.observe(document.documentElement, { subtree: true, childList: true, attributes: true, characterData: true });
  if (document.documentElement) start(); else addEventListener('DOMContentLoaded', start);
  const anim = Element.prototype.animate;
  Element.prototype.animate = function (k, o) { const a = anim.apply(this, arguments); if (P.armed) { const t0 = T(), c = String(this.className || this.tagName).slice(0, 40), d = typeof o === 'number' ? o : (o && o.duration);
    P.ev.push(['waapi', t0, c, d]); a.finished.then(() => P.ev.push(['waapi-end', T(), c]), () => {}); } return a; };
  const svt = document.startViewTransition && document.startViewTransition.bind(document);
  if (svt) document.startViewTransition = function (cb) { const t0 = T(); if (P.armed) P.ev.push(['vt-call', t0, document.documentElement.dataset.czDir || '']);
    const t = svt(async () => { if (P.armed) P.ev.push(['vt-cb', T()]); await (typeof cb === 'function' ? cb() : cb && cb.update && cb.update()); if (P.armed) P.ev.push(['vt-cb-done', T()]); });
    t.ready.then(() => P.armed && P.ev.push(['vt-ready', T()]), () => P.armed && P.ev.push(['vt-skip', T()]));
    t.finished.then(() => P.armed && P.ev.push(['vt-done', T()]), () => {}); return t; };
  const of = window.fetch;
  window.fetch = function (u, o) { const t0 = T(), url = String(u && u.url || u); const p = of.apply(this, arguments); if (P.armed) { P.ev.push(['fetch', t0, url, (o && o.method) || 'GET']); p.then(() => P.ev.push(['fetch-headers', T(), url]), () => {}); } return p; };
  addEventListener('popstate', () => P.armed && P.ev.push(['popstate', T()]));
  P.arm = () => { P.ev = []; P.input = null; P.armed = true; P.t0 = T(); P.res0 = performance.getEntriesByType('resource').length; P.lt0 = P.lt.length; P.loaf0 = P.loaf.length; };
  P.mark = () => { P.input = { t: T(), type: 'script' }; };
  P.dump = () => { P.armed = false; const tf = (x) => Math.round(x);
    const res = performance.getEntriesByType('resource').slice(P.res0).map(e => ({ url: e.name.replace(location.origin, ''), start: tf(e.startTime), ttfb: tf(e.responseStart), end: tf(e.responseEnd),
      wire: e.transferSize, body: e.decodedBodySize, server: (e.serverTiming.find(s => s.name === 'app') || {}).duration, type: e.initiatorType }));
    return { origin: performance.timeOrigin, input: P.input, ev: P.ev, frames: P.frames.filter(f => f >= P.t0 - 50), lt: P.lt.slice(P.lt0), loaf: P.loaf.slice(P.loaf0), res }; };
})();"""

NO_CARET = "*, *::before, *::after { caret-color: transparent !important; }"      # a blinking caret would read as the screen changing


class Shots:
    """The CDP screencast: (epoch ms, hash) of every picture that differs from the one before."""
    def __init__(self, cdp):
        self.cdp, self.frames, self.last = cdp, [], None
        cdp.on("Page.screencastFrame", self.on)

    def on(self, f):
        h = hashlib.md5(base64.b64decode(f["data"])).hexdigest()
        ts = f["metadata"].get("timestamp", time.time()) * 1000
        if h != self.last:
            self.frames.append((ts, h))
            self.last = h
        asyncio.ensure_future(self.cdp.send("Page.screencastFrameAck", {"sessionId": f["sessionId"]}))

    async def start(self, w, h):
        await self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 40, "maxWidth": w, "maxHeight": h, "everyNthFrame": 1})

    def since(self, t):
        return [x for x in self.frames if x[0] > t]


async def metrics(cdp):
    m = {x["name"]: x["value"] for x in (await cdp.send("Performance.getMetrics"))["metrics"]}
    return {k: m.get(k, 0) for k in ("LayoutCount", "RecalcStyleCount", "LayoutDuration", "RecalcStyleDuration", "ScriptDuration", "TaskDuration")}


def bursts(times, gap=120):
    out = []
    for t in times:
        if out and t - out[-1][1] < gap:
            out[-1][1] = t
        else:
            out.append([t, t])
    return out


def summarise(name, kind, d, shots, m0, m1):
    o = d["origin"]
    inp = d["input"]["t"] if d["input"] else None
    if inp is None:
        return {"name": name, "kind": kind, "error": "no input seen"}
    rel = lambda t: round(t - inp)
    pics = [round(ts - o - inp) for ts, _ in shots]
    pics = [p for p in pics if p > -5]
    b = bursts(pics)
    fr = [f for f in d["frames"] if f >= inp]
    gaps = [fr[i + 1] - fr[i] for i in range(len(fr) - 1)]
    settle = b[-1][1] if b else None
    in_win = [g for g, f in zip(gaps, fr) if settle is not None and f - inp <= settle]
    dropped = sum(max(0, round(g / 16.67) - 1) for g in in_win)
    ev = [[e[0], rel(e[1])] + e[2:] for e in d["ev"]]
    muts = bursts([e[1] for e in ev if e[0] == "mut"], 30)
    moves = [e[1] for e in ev if e[0] in ("vt-ready", "waapi") or (e[0] == "animationstart" and not str(e[2]).startswith("-ua-"))]
    content = min(moves) if moves else (muts[0][0] if muts else None)      # the new thing starts to show (a transition or animation begins; else the first DOM change)
    return {
        "name": name, "kind": kind, "input": d["input"]["type"], "cpu": CPU, "latency": LATENCY,
        "first_pic": b[0][0] if b else None, "content": content, "settled": settle, "bursts": b,
        "net": [dict(r, start=rel(r["start"]), ttfb=rel(r["ttfb"]), end=rel(r["end"])) for r in d["res"] if r["type"] in ("fetch", "xmlhttprequest", "navigation", "other") or "frag" in r["url"]],
        "steps": [e for e in ev if e[0] not in ("mut", "transitionstart", "transitionend")],
        "transitions": [e for e in ev if e[0] in ("transitionstart",)][:12],
        "mut_bursts": muts,
        "longtasks": [[rel(s), round(du)] for s, du in d["lt"] if s + du >= inp],
        "loaf": [dict(l, start=rel(l["start"]), dur=round(l["dur"]), block=round(l["block"])) for l in d["loaf"] if l["start"] + l["dur"] >= inp],
        "frames_dropped": dropped, "worst_frame": round(max(in_win)) if in_win else None,
        "layouts": m1["LayoutCount"] - m0["LayoutCount"], "styles": m1["RecalcStyleCount"] - m0["RecalcStyleCount"],
        "layout_ms": round((m1["LayoutDuration"] - m0["LayoutDuration"]) * 1000), "style_ms": round((m1["RecalcStyleDuration"] - m0["RecalcStyleDuration"]) * 1000),
        "script_ms": round((m1["ScriptDuration"] - m0["ScriptDuration"]) * 1000),
    }


class Rig:
    def __init__(self, browser, base, state, form, kind):
        self.browser, self.base, self.state, self.form, self.kind = browser, base, state, form, kind

    async def open(self, url, throttle=True):
        self.ctx = await self.browser.new_context(storage_state=self.state, service_workers="block", reduced_motion="no-preference", **self.form)
        await self.ctx.add_init_script(RECORDER)
        self.page = await self.ctx.new_page()
        self.cdp = await self.ctx.new_cdp_session(self.page)
        await self.cdp.send("Performance.enable")
        await self.cdp.send("Network.enable")
        if throttle:
            await self.cdp.send("Emulation.setCPUThrottlingRate", {"rate": CPU})
            await self.cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": LATENCY, "downloadThroughput": 1.5e6, "uploadThroughput": 0.75e6})
        await self.page.goto(self.base + url)
        await self.page.add_style_tag(content=NO_CARET)
        await self.page.wait_for_selector(".cz-view")
        self.shots = Shots(self.cdp)
        vp = self.form["viewport"]
        await self.shots.start(vp["width"], vp["height"])
        await self.quiet()

    async def quiet(self, ms=1500, cap=15000):
        """Wait until no request has started for `ms` (the idle prefetch is done)."""
        t_end = time.time() + cap / 1000
        last, stable = -1, 0
        while time.time() < t_end:
            n = await self.page.evaluate("performance.getEntriesByType('resource').length")
            stable = stable + 250 if n == last else 0
            last = n
            if stable >= ms:
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.3)

    async def measure(self, name, act, window=2200):
        await self.page.evaluate("__p.arm()")
        m0 = await metrics(self.cdp)
        n0 = len(self.shots.frames)
        await act()
        await asyncio.sleep(window / 1000)
        m1 = await metrics(self.cdp)
        d = await self.page.evaluate("__p.dump()")
        s = summarise(name, self.kind, d, self.shots.frames[n0:], m0, m1)
        return s

    async def close(self):
        await self.ctx.close()

    # ---- inputs ----
    async def touch(self, pts, hold_ms=0, step_ms=16):
        """One finger: down at pts[0], held hold_ms, moved through pts[1:], lifted."""
        x, y = pts[0]
        await self.cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        if hold_ms:
            await asyncio.sleep(hold_ms / 1000)
        for x, y in pts[1:]:
            await self.cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y}]})
            await asyncio.sleep(step_ms / 1000)
        await self.cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})

    async def grid_y(self, minute):
        return await self.page.evaluate("""(m) => { const e = document.querySelector('#cz-grid'), z = e.querySelector('.cz-g-zoom');
          return z.getBoundingClientRect().top + (m - +e.dataset.lo) * z.offsetHeight / (+e.dataset.hi - +e.dataset.lo); }""", minute)

    async def centre(self, sel):
        loc = self.page.locator(sel + " >> visible=true").first
        await loc.scroll_into_view_if_needed()
        b = await loc.bounding_box()
        return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


async def phone_runs(rig, out, reps):
    P = rig
    res = []

    async def tap(sel):
        x, y = await P.centre(sel)
        await P.page.touchscreen.tap(x, y)

    for r in range(reps):
        day = 1 + r % 3
        await P.open(f"/trip/canvas?day={day}")
        nxt = day + 1
        res.append(await P.measure("day chip tap (prefetched)", lambda: tap(f".cz-hchip[data-move-day='{nxt}']")))
        await P.quiet()
        await P.page.evaluate("CZ.forget()")
        res.append(await P.measure("day chip tap (not prefetched)", lambda: tap(f".cz-hchip[data-move-day='{day}']")))
        await P.quiet()
        res.append(await P.measure("swipe to next day", lambda: P.touch([(300, 600)] + [(300 - 30 * i, 600) for i in range(1, 7)])))
        await P.quiet()
        res.append(await P.measure("Back (browser)", lambda: P.page.evaluate("__p.mark(); history.back()")))
        await P.quiet()
        res.append(await P.measure("Day -> Week (Trip back button)", lambda: tap(".cz-view .cz-back")))
        await P.quiet()
        res.append(await P.measure("Week -> Day (day row)", lambda: tap(f"a.cz-row-link[href*='day={day}']")))
        await P.quiet()
        await P.close()

        await P.open(f"/trip/canvas?day={day}")
        res.append(await P.measure("filter tap (Plans)", lambda: tap(".cz-kchip[data-k='plan']"), 1200))
        await P.page.locator(".cz-kchip[data-k='all']").first.click()
        await P.quiet(600)
        res.append(await P.measure("open a plan (card)", lambda: tap(".cz-gb-open[href*='talk']")))
        await P.page.keyboard.press("Escape")
        await P.quiet(800)
        res.append(await P.measure("Ask open (sheet)", lambda: tap("#ph-tab-ask")))
        await P.page.keyboard.press("Escape")
        await P.quiet(800)
        await P.close()

        # add a plan: hold empty time, release (title field opens), type, Enter. Measured: the hold to the draft, and Enter to settled.
        await P.open(f"/trip/canvas?day={day}")
        y = await P.grid_y(7 * 60 + 15)

        async def hold_add():
            await P.touch([(230, y)], hold_ms=450)
        res.append(await P.measure("add: hold empty time -> draft", hold_add, 1000))
        await P.page.locator(".cz-gb.is-new .cz-gb-edit").focus()      # (iOS focuses it inside the pointerup; a CDP touch is not a user activation for focus)
        await P.page.keyboard.type("Snack stop", delay=20)
        res.append(await P.measure("add: Enter -> saved", lambda: P.page.keyboard.press("Enter"), 2500))
        await P.quiet()
        # move: hold Breakfast, drag it down an hour, let go. Measured from the touchstart (the hold is ~350 ms by design) and the drop is marked in the steps.
        x0, y0 = await P.centre(".cz-gb:has-text('Breakfast')")
        res.append(await P.measure("move: hold, drag, drop", lambda: P.touch([(x0, y0)] + [(x0, y0 + 6 * i) for i in range(1, 11)], hold_ms=450), 2800))
        await P.quiet()
        await P.close()
    for x in res:
        out.write(json.dumps(x) + "\n")
    return res


async def laptop_runs(rig, out, reps):
    L = rig
    res = []
    for r in range(reps):
        day = 1 + r % 3
        await L.open(f"/trip/canvas?day={day}")
        nxt = day + 1
        res.append(await L.measure("day tab click (prefetched)", lambda: L.page.locator(f".cz-hchip[data-move-day='{nxt}']").first.click()))
        await L.quiet()
        await L.page.evaluate("CZ.forget()")
        res.append(await L.measure("day tab click (not prefetched)", lambda: L.page.locator(f".cz-hchip[data-move-day='{day}']").first.click()))
        await L.quiet()
        await L.page.mouse.click(700, 60)      # focus off the chip, onto the page
        res.append(await L.measure("arrow key next day", lambda: L.page.keyboard.press("ArrowRight")))
        await L.quiet()
        res.append(await L.measure("Back (browser)", lambda: L.page.evaluate("__p.mark(); history.back()")))
        await L.quiet()
        res.append(await L.measure("Day -> Week", lambda: L.page.locator("#cz-z-week").first.click()))
        await L.quiet()
        res.append(await L.measure("Week -> Day", lambda: L.page.locator("#cz-z-day").first.click()))
        await L.quiet()
        await L.close()

        await L.open(f"/trip/canvas?day={day}")
        res.append(await L.measure("filter click (Plans)", lambda: L.page.locator(".cz-kchip[data-k='plan']").first.click(), 1200))
        await L.page.locator(".cz-kchip[data-k='all']").first.click()
        await L.quiet(600)
        res.append(await L.measure("open a plan (panel)", lambda: L.page.locator(".cz-gb-open[href*='talk']").first.click()))
        await L.quiet(800)
        res.append(await L.measure("Ask (panel tab)", lambda: L.page.locator(".cz-dock-tab[data-tab='ask']").first.click()))
        await L.quiet(800)
        await L.close()

        await L.open(f"/trip/canvas?day={day}")
        y1, y2 = await L.grid_y(7 * 60 + 5), await L.grid_y(7 * 60 + 50)

        async def draw():
            await L.page.mouse.move(500, y1)
            await L.page.mouse.down()
            for i in range(1, 9):
                await L.page.mouse.move(500, y1 + (y2 - y1) * i / 8)
            await L.page.mouse.up()
        res.append(await L.measure("add: draw empty time -> field", draw, 1000))
        await L.page.keyboard.type("Snack stop", delay=20)
        res.append(await L.measure("add: Enter -> saved", lambda: L.page.keyboard.press("Enter"), 2500))
        await L.quiet()
        x0, y0 = await L.centre(".cz-gb:has-text('Breakfast')")

        async def drag():
            await L.page.mouse.move(x0, y0)
            await L.page.mouse.down()
            for i in range(1, 11):
                await L.page.mouse.move(x0, y0 + 5 * i)
                await asyncio.sleep(0.016)
            await L.page.mouse.up()
        res.append(await L.measure("move: drag, drop", drag, 2800))
        await L.quiet()
        await L.close()
    for x in res:
        out.write(json.dumps(x) + "\n")
    return res


async def stale_runs(rig, out, reps):
    """The day left on the screen for over a minute (FRESH = 60 s in canvas_core.js), then the next day's chip: is the prefetched copy still used?"""
    res = []
    for r in range(reps):
        await rig.open("/trip/canvas?day=1")
        await asyncio.sleep(62)
        sel = ".cz-hchip[data-move-day='2']"
        if rig.kind == "phone":
            x, y = await rig.centre(sel)
            res.append(await rig.measure("day chip tap after 62 s on the day", lambda: rig.page.touchscreen.tap(x, y)))
        else:
            res.append(await rig.measure("day tab click after 62 s on the day", lambda: rig.page.locator(sel).first.click()))
        await rig.close()
    for x in res:
        out.write(json.dumps(x) + "\n")
    return res


async def main(base, state, path, which="both", reps=3):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        with open(path, "a") as out:
            if which in ("phone", "both"):
                await phone_runs(Rig(b, base, state, PHONE, "phone"), out, reps)
            if which in ("laptop", "both"):
                await laptop_runs(Rig(b, base, state, LAPTOP, "laptop"), out, reps)
            if which == "stale":
                await stale_runs(Rig(b, base, state, PHONE, "phone"), out, reps)
                await stale_runs(Rig(b, base, state, LAPTOP, "laptop"), out, reps)
        await b.close()


if __name__ == "__main__":
    a = sys.argv[1:]
    CPU = int(a[5]) if len(a) > 5 else CPU
    LATENCY = int(a[6]) if len(a) > 6 else LATENCY
    asyncio.run(main(a[0], a[1], a[2], a[3] if len(a) > 3 else "both", int(a[4]) if len(a) > 4 else 3))
