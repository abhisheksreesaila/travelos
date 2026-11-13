"""The cover as frame strips for review (F-227, one stage): the real page scrolled to each part at 390 and 1440, light and dark, with frames taken
during the swap (the incoming screen settling on the spring) and once it has settled; one contact sheet each in docs/report/cover-<tag>-<width>-<mode>.png,
and with --video a short scroll-through recording of each size (light).

    pixi run python scripts/cover_film_report.py [--base http://127.0.0.1:5013] [--tag f227] [--video] [--only 390-light]

Each frame is labelled with what it shows; the sheet also prints, for each swap, the incoming screen's opacity and scale at the moment it was taken.
"""
import argparse
import io
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "report"
SIZES = {"390": {"width": 390, "height": 844}, "1440": {"width": 1440, "height": 900}}
# (part, how long after the part shows the frame is taken, in ms): during the settle (380 ms) and settled, its moments played
POINTS = ((1, 120), (1, 3000), (2, 90), (2, 200), (2, 2400), (3, 90), (3, 200), (3, 1600))
SHOW = """n => { const c = document.querySelector(`.cv-ch[data-n="${n}"]`), top = c.getBoundingClientRect().top + scrollY;
  window.scrollTo(0, innerWidth >= 1100 ? top : top - innerHeight * 0.6); }"""
STATE = """n => { const s = getComputedStyle(document.querySelector(`.cv-L${n}`)); return [s.opacity, new DOMMatrix(s.transform).a]; }"""


def frames(browser, base, size, scheme):
    vp = SIZES[size]
    phone = vp["width"] < 760
    ctx = browser.new_context(viewport=vp, color_scheme=scheme, is_mobile=phone, has_touch=phone, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(f"{base}/")
    page.wait_for_function("!!window.GA_COVER")
    page.wait_for_timeout(600)
    out = [("opening", Image.open(io.BytesIO(page.screenshot())).convert("RGB"))]
    for n, after in POINTS:
        if after < 1000:                                     # come from the part before, so the swap plays
            page.evaluate(SHOW, str(n - 1 if n > 1 else 1))
            page.wait_for_function(f"document.querySelector('.cv-stage').dataset.part === '{n - 1 if n > 1 else 1}'")
            page.wait_for_timeout(700)
        page.evaluate(SHOW, str(n))
        page.wait_for_function(f"document.querySelector('.cv-stage').dataset.part === '{n}'")
        page.wait_for_timeout(after)
        op, k = page.evaluate(STATE, str(n))
        im = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        out.append((f"part {n} +{after}ms · opacity {float(op):.2f} scale {k:.3f}", im))
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(400)
    out.append(("the close", Image.open(io.BytesIO(page.screenshot())).convert("RGB")))
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


def video(browser, base, size, tag):
    vp = SIZES[size]
    phone = vp["width"] < 760
    ctx = browser.new_context(viewport=vp, is_mobile=phone, has_touch=phone, record_video_dir=str(OUT / "_video"), record_video_size=vp)
    page = ctx.new_page()
    page.goto(f"{base}/")
    page.wait_for_function("!!window.GA_COVER")
    page.wait_for_timeout(800)
    end = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    y = 0
    while y < end:
        y = min(end, y + vp["height"] * 0.03)
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(33)
    page.wait_for_timeout(600)
    path = page.video.path()
    ctx.close()
    dest = OUT / f"cover-{tag}-{size}.webm"
    Path(path).replace(dest)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5013")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--tag", default="f227")
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
                for name, _ in ims:
                    print(f"{size} {scheme} {name}")
                path = OUT / f"cover-{a.tag}-{size}-{scheme}.png"
                sheet(ims, 5 if size == "390" else 4).save(path, optimize=True)
                print(path)
            if a.video and not a.only:
                print(video(browser, a.base, size, a.tag))
        browser.close()


if __name__ == "__main__":
    main()
