"""Frame rate of the cover's live world on a running app (F-206), on one repeatable path: a scripted scroll from the book to the line in 24 s.

    pixi run python -I cover3d/tools/measure.py [--base http://127.0.0.1:6206]

Four runs: a 1440 laptop on this machine's GPU; a 390 phone (DPR 3, touch, the strong-phone tier) with the CPU throttled 4x on the GPU; the same
phone on SwiftShader (Chromium's software renderer, standing in for a weak phone GPU) with the governor off, for raw numbers; and that weak phone
with the governor on, as a visitor would get it. Results go to cover3d/fps.json. This machine's GPU flatters the phone numbers: a real phone is
the next check (cover3d/README.md says so).
"""
import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
# Playwright's own full Chromium (channel "chromium": its headless shell has no GPU path), or COVER3D_CHROME=<path to a chrome binary>
CHROME = os.environ.get("COVER3D_CHROME")
GPU = ["--use-angle=vulkan", "--enable-features=Vulkan", "--ignore-gpu-blocklist"]
SOFT = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
RUN = """async (dur) => {
  const G = window.GA_COVER, S = window.__cover.S, calls = [], tris = [];
  await new Promise((done) => { const t0 = performance.now();
    const tick = () => { const t = (performance.now() - t0) / dur; G.measure(); window.scrollTo(0, G.yFor(Math.min(1, t) * 12.9)); if (t < 1 && !G.still) requestAnimationFrame(tick); else done(); };
    const iv = setInterval(() => { calls.push(S.renderer.info.render.calls); tris.push(S.renderer.info.render.triangles); if (performance.now() - t0 > dur) clearInterval(iv); }, 400);
    tick(); });
  const f = window.__frames.slice(-Math.min(window.__frames.length, 1200)).sort((a, b) => a - b);
  const mean = f.reduce((a, b) => a + b, 0) / f.length;
  return { fps: +(1000 / mean).toFixed(1), p95_ms: +f[Math.floor(f.length * 0.95)].toFixed(1), over_33ms: +(100 * f.filter((x) => x > 33.4).length / f.length).toFixed(1),
           frames: f.length, calls_max: Math.max(...calls), triangles_max: Math.max(...tris), scale: window.__cover.loop.scale, tier: G.tier, still: G.still };
}"""


def launch(p, args):
    return p.chromium.launch(executable_path=CHROME, args=args) if CHROME else p.chromium.launch(channel="chromium", args=args)


def run(p, name, args, viewport, dpr, phone, cpu, governor, base):
    b = launch(p, args)
    ctx = b.new_context(viewport=viewport, device_scale_factor=dpr, has_touch=phone, is_mobile=phone, reduced_motion="no-preference")
    page = ctx.new_page()
    if cpu > 1:
        ctx.new_cdp_session(page).send("Emulation.setCPUThrottlingRate", {"rate": cpu})
    page.goto(f"{base}/" + ("" if governor else "?measure"))
    page.wait_for_function("document.documentElement.classList.contains('cv-ready') || document.documentElement.classList.contains('cv-still')", timeout=120000)
    if page.evaluate("window.GA_COVER.still"):
        out = {"still": True, "note": "went straight to the stills"}
    else:
        page.wait_for_timeout(2500)
        out = page.evaluate(RUN, 24000)
        if governor:
            page.wait_for_timeout(1500)
            out["still_after"] = page.evaluate("window.GA_COVER.still")
    b.close()
    print(name, json.dumps(out))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--base", default="http://127.0.0.1:6206"); a = ap.parse_args()
    phone = {"width": 390, "height": 844}
    res = {}
    with sync_playwright() as p:
        res["laptop-1440-gpu"] = run(p, "laptop-1440-gpu", GPU, {"width": 1440, "height": 900}, 1, False, 1, False, a.base)
        res["phone-390-cpu4x-gpu"] = run(p, "phone-390-cpu4x-gpu", GPU, phone, 3, True, 4, False, a.base)
        res["phone-390-cpu4x-software-gl"] = run(p, "phone-390-cpu4x-software-gl", SOFT, phone, 3, True, 4, False, a.base)
        res["phone-390-cpu4x-software-gl-governor"] = run(p, "phone-390-cpu4x-software-gl-governor", SOFT, phone, 3, True, 4, True, a.base)
    (REPO / "cover3d" / "fps.json").write_text(json.dumps(res, indent=2) + "\n")


if __name__ == "__main__":
    main()
