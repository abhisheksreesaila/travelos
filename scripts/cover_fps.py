"""How smoothly the cover scrolls (F-227, one stage; docs/lessons.md 2026-10-09): headless Chromium with the CPU slowed 4x (CDP), a long-task
observer and a requestAnimationFrame log, while the whole page is scrolled top to bottom: by a finger on a phone (390), by the wheel on a laptop
(1440). Prints, per part of the page (the opening, parts 1 to 3 by the stage's data-part, the close), the frames, the mean frame rate, the share of
frames over 1.5 vsyncs (25 ms), the worst frame, and the bursts: runs of three or more slow frames in a row (what reads as a stutter).

    pixi run python scripts/cover_fps.py [--base http://127.0.0.1:5013] [--throttle 4] [--sizes 390,1440]
"""
import argparse
import json

from playwright.sync_api import sync_playwright

STEP = 40
SLOW = 25                    # ms: over 1.5 vsyncs at 60 Hz
PROBE = """() => {
  window.__f = []; window.__lt = [];
  new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__lt.push([e.startTime, e.duration, scrollY]))).observe({ entryTypes: ['longtask'] });
  const stage = document.querySelector('.cv-stage'), close = document.querySelector('.cv-close');
  const where = () => close.getBoundingClientRect().top < innerHeight / 2 ? 'close'
    : stage.getBoundingClientRect().top < innerHeight / 2 ? 'part ' + stage.dataset.part : 'opening';
  const tick = (t) => { window.__f.push([t, scrollY, where()]); requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}"""


def bursts(ds):
    out, run = 0, 0
    for d in ds:
        run = run + 1 if d > SLOW else 0
        out += run == 3
    return out


def summary(ds):
    return {"frames": len(ds), "fps": round(1000 * len(ds) / sum(ds), 1), "slow": round(sum(d > SLOW for d in ds) / len(ds), 3),
            "worst_ms": round(max(ds), 1), "bursts": bursts(ds)}


def run(browser, base, size, throttle):
    phone = size == 390
    vp = {"width": 390, "height": 844} if phone else {"width": 1440, "height": 900}
    ctx = browser.new_context(viewport=vp, is_mobile=phone, has_touch=phone, device_scale_factor=3 if phone else 2)
    page = ctx.new_page()
    page.goto(f"{base}/")
    page.wait_for_function("!!window.GA_COVER")
    page.wait_for_timeout(1000)
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": throttle})
    page.evaluate(PROBE)
    end = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    t0 = page.evaluate("performance.now()")
    if phone:
        while page.evaluate("scrollY") < end - 5:
            cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 195, "y": 700}]})
            for k in range(1, 13):
                cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": 195, "y": 700 - 40 * k}]})
                page.wait_for_timeout(16)
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            page.wait_for_timeout(120)
    else:
        page.mouse.move(700, 450)
        while page.evaluate("scrollY") < end - 5:
            page.mouse.wheel(0, STEP)
            page.wait_for_timeout(16)
    page.wait_for_timeout(500)
    f = [x for x in page.evaluate("window.__f") if x[0] >= t0]
    lt = page.evaluate("window.__lt")
    ctx.close()
    rows = {}
    for (a, ya, _), (b, yb, where) in zip(f, f[1:]):
        if ya == yb:
            continue                                            # idle frames between gestures are not the scroll
        rows.setdefault(where, []).append(b - a)
    out = {"size": size, "throttle": throttle, "parts": {n: summary(ds) for n, ds in rows.items()}}
    out["all"] = summary([d for ds in rows.values() for d in ds])
    out["longtasks"] = [[round(s), round(d), round(y)] for s, d, y in lt if s >= t0]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5013")
    ap.add_argument("--throttle", type=float, default=4)
    ap.add_argument("--sizes", default="390,1440")
    a = ap.parse_args()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for size in map(int, a.sizes.split(",")):
            print(json.dumps(run(browser, a.base, size, a.throttle)))
        browser.close()


if __name__ == "__main__":
    main()
