"""A scroll-through of the cover's story for review (cover v3, D-380..D-392): the page as a visitor scrolls it, at 390 and 1440, light and dark, one
contact sheet each in docs/report/cover-v3-<width>-<mode>.png.

    pixi run python scripts/cover_story_report.py [--base http://127.0.0.1:6033] [--calm]

Each frame is one screen, taken every 0.8 of a screen down the page, after the reveals and the screenshots on it have settled (the booking tour's
three beats come up as you pass them). --calm shoots with reduced motion.
"""
import argparse
import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "report"
SIZES = {"390": {"width": 390, "height": 844}, "1440": {"width": 1440, "height": 900}}
SETTLED = """() => [...document.images].filter((im) => { const r = im.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; })
  .every((im) => im.complete && im.naturalWidth > 0)"""


def frames(browser, base, size, scheme, calm):
    vp = SIZES[size]
    phone = vp["width"] < 760
    ctx = browser.new_context(viewport=vp, color_scheme=scheme, reduced_motion="reduce" if calm else "no-preference", is_mobile=phone, has_touch=phone)
    page = ctx.new_page()
    page.goto(f"{base}/")
    page.wait_for_function("!!window.GA_COVER")
    out, y = [], 0
    while True:
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(250)
        page.wait_for_function(SETTLED, timeout=15000)
        page.wait_for_timeout(500)
        out.append(Image.open(io.BytesIO(page.screenshot())).convert("RGB"))
        if y + vp["height"] >= page.evaluate("document.documentElement.scrollHeight"):
            break
        y += int(vp["height"] * 0.8)
    ctx.close()
    return out


def sheet(images, cols):
    w, h = images[0].size
    scale = 0.4 if w > 800 else 0.5
    tw, th, gap = int(w * scale), int(h * scale), 16
    rows = (len(images) + cols - 1) // cols
    board = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * th + (rows + 1) * gap), (128, 128, 136))
    for k, im in enumerate(images):
        r, c = divmod(k, cols)
        board.paste(im.resize((tw, th), Image.LANCZOS), (gap + c * (tw + gap), gap + r * (th + gap)))
    return board


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:6033")
    ap.add_argument("--calm", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for size in SIZES:
            for scheme in ("light", "dark"):
                imgs = frames(browser, args.base, size, scheme, args.calm)
                path = OUT / f"cover-v3-{size}-{scheme}.png"
                sheet(imgs, 8 if size == "390" else 4).save(path, optimize=True)
                print(path.relative_to(REPO), len(imgs), "frames", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
