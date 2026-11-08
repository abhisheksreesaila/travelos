"""A scroll-through of the cover's story for review (D-354): every scene at 390 and 1440, light and dark, one contact sheet each in docs/report/.

    pixi run python scripts/cover_story_report.py [--base http://127.0.0.1:6031] [--live]

Each scene is shot where its card is pinned (?scene=N), after its screenshot has loaded. Without --live it uses reduced motion, so the world is
the calm stills (the same renders) and every run gives the same pictures.
"""
import argparse
import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "report"
SIZES = {"390": {"width": 390, "height": 844}, "1440": {"width": 1440, "height": 900}}


def frames(browser, base, size, scheme, live):
    vp = SIZES[size]
    phone = vp["width"] < 760
    ctx = browser.new_context(viewport=vp, color_scheme=scheme, reduced_motion="no-preference" if live else "reduce", is_mobile=phone, has_touch=phone)
    page = ctx.new_page()
    page.goto(f"{base}/")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.scenes().length > 0")
    n = page.evaluate("GA_COVER.scenes().length")
    out = []
    for i in range(n):
        page.evaluate("i => { const t = GA_COVER.scenes()[i]; window.scrollTo(0, t.s + (t.e - t.s) * 0.6); }", i)
        page.wait_for_function(f"document.documentElement.dataset.cvScene === '{i}'")
        page.wait_for_function(f"""(() => {{ const s = document.querySelector('[data-scene="{i}"] .cv-shot img'); return !s || (s.complete && s.naturalWidth > 0); }})()""", timeout=15000)
        page.wait_for_timeout(1800 if live else 450)
        out.append(Image.open(io.BytesIO(page.screenshot())).convert("RGB"))
    page.evaluate("document.querySelector('.cv-close').scrollIntoView({ block: 'start' })")
    page.wait_for_timeout(300)
    out.append(Image.open(io.BytesIO(page.screenshot())).convert("RGB"))
    ctx.close()
    return out


def sheet(images, cols):
    w, h = images[0].size
    scale = 0.5 if w > 800 else 0.6
    tw, th, gap = int(w * scale), int(h * scale), 16
    rows = (len(images) + cols - 1) // cols
    board = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * th + (rows + 1) * gap), (128, 128, 136))
    for k, im in enumerate(images):
        r, c = divmod(k, cols)
        board.paste(im.resize((tw, th), Image.LANCZOS), (gap + c * (tw + gap), gap + r * (th + gap)))
    return board


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:6031")
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for size in SIZES:
            for scheme in ("light", "dark"):
                imgs = frames(browser, args.base, size, scheme, args.live)
                path = OUT / f"cover-story-{size}-{scheme}.png"
                sheet(imgs, 6 if size == "390" else 3).save(path, optimize=True)
                print(path.relative_to(REPO), len(imgs), "frames", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
