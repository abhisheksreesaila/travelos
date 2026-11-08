"""How smoothly the cover's film plays (cover v4, D-400..; docs/lessons.md 2026-10-09): headless Chromium with the CPU slowed 4x (CDP), a long-task
observer and a requestAnimationFrame log, while the whole page is scrolled top to bottom: by a finger on a phone (390), by the wheel on a laptop
(1440). Prints the frames, the mean frame rate, the share of frames over 1.5 vsyncs and the long tasks, per stage.

    pixi run python scripts/cover_fps.py [--base http://127.0.0.1:6034] [--throttle 4]
"""
import argparse
import json

from playwright.sync_api import sync_playwright

STEP = 40
PROBE = """() => {
  window.__f = []; window.__lt = [];
  new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__lt.push([e.startTime, e.duration, scrollY]))).observe({ entryTypes: ['longtask'] });
  const tick = (t) => { window.__f.push([t, scrollY]); requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}"""


def run(browser, base, size, throttle, css=""):
    phone = size == 390
    vp = {"width": 390, "height": 844} if phone else {"width": 1440, "height": 900}
    ctx = browser.new_context(viewport=vp, is_mobile=phone, has_touch=phone, device_scale_factor=3 if phone else 2)
    page = ctx.new_page()
    page.goto(f"{base}/")
    page.wait_for_function("!!window.GA_COVER")
    if css:                                                     # an experiment: extra CSS (--css)
        page.add_style_tag(content=css)
    page.wait_for_timeout(1000)
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": throttle})
    page.evaluate(PROBE)
    end = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    stages = page.evaluate("[...document.querySelectorAll('.cv-stage')].map((s) => [s.dataset.stage, s.getBoundingClientRect().top + scrollY])")
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
    f = page.evaluate("window.__f")
    lt = page.evaluate("window.__lt")
    ctx.close()
    f = [x for x in f if x[0] >= t0]
    def stage_of(y):
        name = "top"
        for n, top in stages:
            if y + vp["height"] / 2 >= top:
                name = n
        return name
    rows = {}
    for (a, ya), (b, yb) in zip(f, f[1:]):
        if ya == yb:
            continue                                            # idle frames between gestures are not the film
        r = rows.setdefault(stage_of(yb), [])
        r.append(b - a)
    out = {"size": size, "throttle": throttle, "stages": {}}
    alld = [d for r in rows.values() for d in r]
    for n, ds in rows.items():
        out["stages"][n] = {"frames": len(ds), "fps": round(1000 * len(ds) / sum(ds), 1), "slow": round(sum(d > 25 for d in ds) / len(ds), 3), "worst_ms": round(max(ds), 1)}
    out["all"] = {"frames": len(alld), "fps": round(1000 * len(alld) / sum(alld), 1), "slow": round(sum(d > 25 for d in alld) / len(alld), 3), "worst_ms": round(max(alld), 1)}
    out["longtasks"] = [[round(s), round(d), round(y)] for s, d, y in lt if s >= t0]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:6034")
    ap.add_argument("--throttle", type=float, default=4)
    ap.add_argument("--css", default="", help="extra CSS for an experiment")
    ap.add_argument("--sizes", default="390,1440")
    a = ap.parse_args()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for size in map(int, a.sizes.split(",")):
            print(json.dumps(run(browser, a.base, size, a.throttle, a.css)))
        browser.close()


if __name__ == "__main__":
    main()
