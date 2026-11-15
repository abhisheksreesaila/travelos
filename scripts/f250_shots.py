"""F-250: side-by-side screenshots of the prototype (docs/design/booking-v2/index.html, type C) and the built pages, for landing, picker, skeleton and matrix at 1440 and 390.

    pixi run python scripts/f250_shots.py [--port 6350] [--mode light|dark] [--only landing,picker,...]

Needs the app running with GITAWAY_DEV_LOGIN=1 (the showcase on) on --port. Writes docs/report/f250-<width>-<state>[-dark].png: the prototype on the left, the build on the right."""
import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PROTO = (ROOT / "docs/design/booking-v2/index.html").as_uri()
OUT = ROOT / "docs/report"
SIZES = {"1440": (1440, 900), "390": (390, 844)}


def side(a, b, path, label_a="prototype", label_b="build"):
    ia, ib = Image.open(BytesIO(a)).convert("RGB"), Image.open(BytesIO(b)).convert("RGB")
    h = max(ia.height, ib.height)
    out = Image.new("RGB", (ia.width + ib.width + 24, h + 28), (30, 30, 40))
    out.paste(ia, (0, 28))
    out.paste(ib, (ia.width + 24, 28))
    d = ImageDraw.Draw(out)
    d.text((8, 8), label_a, fill=(255, 255, 255))
    d.text((ia.width + 32, 8), label_b, fill=(255, 255, 255))
    out.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="6350")
    ap.add_argument("--mode", default="light")
    ap.add_argument("--only", default="landing,picker,skeleton,matrix")
    a = ap.parse_args()
    only = a.only.split(",")
    base = f"http://localhost:{a.port}"
    suffix = "" if a.mode == "light" else "-dark"
    with sync_playwright() as p:
        br = p.chromium.launch()
        for wname, (w, h) in SIZES.items():
            ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
            ctx.add_init_script(f"try {{ localStorage.setItem('ga-mode', '{a.mode}'); localStorage.setItem('bv2-theme', '{a.mode}'); }} catch (e) {{}}")
            ref = ctx.new_page()
            ref.goto(PROTO + "?type=c&theme=" + a.mode)
            ref.wait_for_selector("#sent .w")
            built = ctx.new_page()
            built.request.post(base + "/signin", data={"email": "ari@example.com", "next": "/plan/ask"})
            built.goto(base + "/plan/ask")
            built.wait_for_selector("#v2-sent .v2-w")
            built.wait_for_timeout(700)
            ref.wait_for_timeout(700)
            if "landing" in only:
                side(ref.screenshot(), built.screenshot(), OUT / f"f250-{wname}-landing{suffix}.png")
            if "picker" in only:
                ref.click("#sent .w[data-k=nights]")
                built.click("#v2-sent .v2-w[data-k=nights]")
                ref.wait_for_timeout(600)
                built.wait_for_timeout(600)
                side(ref.screenshot(), built.screenshot(), OUT / f"f250-{wname}-picker{suffix}.png")
                ref.keyboard.press("Escape")
                built.keyboard.press("Escape")
                ref.wait_for_timeout(300)
                built.wait_for_timeout(300)
            if "skeleton" in only or "matrix" in only:
                ref.click("#goBtn")
                built.click("#v2-go")
                ref.wait_for_timeout(1000)
                built.wait_for_timeout(500)
                if "skeleton" in only:
                    side(ref.screenshot(), built.screenshot(), OUT / f"f250-{wname}-skeleton{suffix}.png")
                ref.wait_for_timeout(3000)
                built.wait_for_url("**/plan/matrix**")
                built.wait_for_selector("#mx.is-live")
                built.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
                built.wait_for_timeout(1500)
                if "matrix" in only:
                    side(ref.screenshot(), built.screenshot(), OUT / f"f250-{wname}-matrix{suffix}.png")
            ctx.close()
        br.close()


if __name__ == "__main__":
    main()
