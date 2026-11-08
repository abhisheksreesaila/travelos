"""The cover's film as frame strips for review (cover v4, D-400..): the page scrolled to set points of each stage, at 390 and 1440, light and dark,
one contact sheet each in docs/report/cover-v4-<width>-<mode>.png, and with --video a short scroll-through recording of each size.

    pixi run python scripts/cover_film_report.py [--base http://127.0.0.1:6034] [--video] [--only 390-light]

Frames scroll the real page (no ?p= hold), wait for the moments that play on their own to settle, and label each frame with its stage and point.
"""
import argparse
import io
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "report"
SIZES = {"390": {"width": 390, "height": 844}, "1440": {"width": 1440, "height": 900}}
POINTS = (("hero", 0), ("hero", 0.5), ("hero", 1), ("book", 0.06), ("book", 0.28), ("book", 0.49), ("book", 0.63), ("book", 0.74), ("book", 0.86), ("book", 0.97),
          ("head", 0.2), ("head", 0.5), ("head", 0.9), ("with", 0.1), ("with", 0.26), ("with", 0.4), ("with", 0.62), ("with", 0.92),
          ("tips", 0.35), ("tips", 0.95), ("trail", 0.7), ("creators", 0.2), ("creators", 0.9), ("end", 0.9))
SETTLED = """() => [...document.images].filter((im) => { const r = im.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight && r.width > 2; })
  .every((im) => im.complete && im.naturalWidth > 0)"""


def frames(browser, base, size, scheme, points=POINTS):
    vp = SIZES[size]
    phone = vp["width"] < 760
    ctx = browser.new_context(viewport=vp, color_scheme=scheme, is_mobile=phone, has_touch=phone, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(f"{base}/")
    page.wait_for_function("!!window.GA_COVER")
    page.wait_for_timeout(600)
    out = []
    for key, p in points:
        page.evaluate("([k, p]) => window.scrollTo(0, GA_COVER.yAt(k, p))", [key, p])
        page.wait_for_timeout(300)
        page.wait_for_function(SETTLED, timeout=15000)
        page.wait_for_timeout(900)
        im = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        out.append((f"{key} {p:g}", im))
    ctx.close()
    return out


def sheet(images, cols):
    w, h = images[0][1].size
    scale = 0.36 if w > 800 else 0.5
    tw, th, gap, lab = int(w * scale), int(h * scale), 16, 28
    rows = (len(images) + cols - 1) // cols
    board = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * (th + lab) + (rows + 1) * gap), (60, 60, 68))
    d = ImageDraw.Draw(board)
    for k, (name, im) in enumerate(images):
        x, y = gap + (k % cols) * (tw + gap), gap + (k // cols) * (th + lab + gap)
        d.text((x + 4, y + 6), f"{k + 1}. {name}", fill=(240, 240, 245))
        board.paste(im.resize((tw, th)), (x, y + lab))
    return board


def video(browser, base, size, scheme):
    vp = SIZES[size]
    phone = vp["width"] < 760
    ctx = browser.new_context(viewport=vp, color_scheme=scheme, is_mobile=phone, has_touch=phone, record_video_dir=str(OUT / "_video"), record_video_size=vp)
    page = ctx.new_page()
    page.goto(f"{base}/")
    page.wait_for_function("!!window.GA_COVER")
    page.wait_for_timeout(800)
    end = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    y = 0
    while y < end:
        y = min(end, y + vp["height"] * 0.04)
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(33)
    page.wait_for_timeout(600)
    path = page.video.path()
    ctx.close()
    dest = OUT / f"cover-v4-{size}-{scheme}.webm"
    Path(path).replace(dest)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:6034")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for size in SIZES:
            for scheme in ("light", "dark"):
                if a.only and a.only != f"{size}-{scheme}":
                    continue
                ims = frames(browser, a.base, size, scheme)
                path = OUT / f"cover-v4-{size}-{scheme}.png"
                sheet(ims, 8 if size == "390" else 4).save(path, optimize=True)
                print(path)
                if a.video and scheme == "light":
                    print(video(browser, a.base, size, scheme))
        browser.close()


if __name__ == "__main__":
    main()
