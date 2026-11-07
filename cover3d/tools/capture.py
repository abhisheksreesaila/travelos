"""Renders the cover's images from the live world on a running app (F-206): the calm stills (what reduced motion, no WebGL and weak phones see, and
chapter 0's is the poster), the share image, the report's screenshots and close-ups, and a scroll-through video.

    pixi run python -I cover3d/tools/capture.py stills|og|report|closeups|video [--base http://127.0.0.1:6206]

Uses Playwright's full Chromium on this machine's GPU (Vulkan) and the page's capture mode (?capture: fixed time steps, no render loop), so every
image is the same frame each time. Overlays (cards, header, labels) are hidden for the stills and the share image, kept for the report.
"""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
STILLS = REPO / "assets" / "cover" / "stills"
REPORT = REPO / "docs" / "report"
# Playwright's own full Chromium (channel "chromium": its headless shell has no GPU path), or COVER3D_CHROME=<path to a chrome binary>
CHROME = os.environ.get("COVER3D_CHROME")
GPU = ["--use-angle=vulkan", "--enable-features=Vulkan", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]
# each chapter at its most telling moment: chapter 0 at rest is the poster, the first frame the live world draws
MOMENTS = {0: 0.0, 1: 0.95, 2: 0.95, 3: 0.92, 4: 0.72, 5: 0.42, 6: 0.97}
HIDE = ".cv-top, .cv-rail, main, .cv-close, .ga-skip { visibility: hidden !important; } .cv-anchors { display: none !important; }"
WIDE, PHONE = {"width": 1440, "height": 900}, {"width": 390, "height": 844}


def launch(p, args):
    return p.chromium.launch(executable_path=CHROME, args=args) if CHROME else p.chromium.launch(channel="chromium", args=args)


def open_page(browser, base, viewport, scheme, query, dpr=1, hide=True):
    phone = viewport["width"] < 760
    ctx = browser.new_context(viewport=viewport, device_scale_factor=dpr, color_scheme=scheme, reduced_motion="no-preference", has_touch=phone, is_mobile=phone)
    page = ctx.new_page()
    logs = []
    page.on("console", lambda m: logs.append(f"{m.type}: {m.text[:300]}"))
    page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
    page.goto(f"{base}/?{query}&capture&q=high")
    try:
        page.wait_for_function("!!(window.__cover && window.__cover.step)", timeout=90000)
    except Exception:
        print("\n".join(logs[-12:]), page.evaluate("document.documentElement.className"))
        raise
    page.wait_for_timeout(300)
    if hide:
        page.add_style_tag(content=HIDE)
    return ctx, page


def settle(page, frames=75):
    page.evaluate(f"() => {{ for (let i = 0; i < {frames}; i++) window.__cover.step(1 / 30); }}")
    page.wait_for_timeout(150)


def webp(png: Path, out: Path, quality: int):
    Image.open(png).convert("RGB").save(out, "WEBP", quality=quality, method=6)


def stills(browser, base):
    STILLS.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="cover-stills-", dir=os.environ.get("TMPDIR")))
    for scheme in ("light", "dark"):
        for layout, vp, dpr, quality in (("wide", WIDE, 1, 72), ("phone", PHONE, 2, 68)):
            for i, local in MOMENTS.items():
                ctx, page = open_page(browser, base, vp, scheme, f"shot={i}&local={local}", dpr)
                settle(page)
                png = tmp / f"a-{i}-{layout}-{scheme}.png"
                page.screenshot(path=str(png))
                webp(png, STILLS / png.with_suffix(".webp").name, quality)
                ctx.close()
                print("still", png.stem, (STILLS / png.with_suffix(".webp").name).stat().st_size // 1024, "KB")


def og(browser, base):
    ctx, page = open_page(browser, base, {"width": 1200, "height": 630}, "light", "shot=1&local=0.95")
    settle(page)
    png = Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR"))) / "og.png"
    page.screenshot(path=str(png))
    Image.open(png).convert("RGB").save(REPO / "assets" / "cover" / "og.jpg", quality=85, optimize=True, progressive=True)
    ctx.close()
    print("og", (REPO / "assets/cover/og.jpg").stat().st_size // 1024, "KB")


def report(browser, base):
    REPORT.mkdir(parents=True, exist_ok=True)
    sets = [("1440", WIDE, 1, "light", range(7)), ("1440", WIDE, 1, "dark", (1, 2, 4, 6)), ("390", PHONE, 2, "light", (0, 1, 2, 3, 4, 6)), ("390", PHONE, 2, "dark", (2, 4))]
    for name, vp, dpr, scheme, chapters in sets:
        for i in chapters:
            ctx, page = open_page(browser, base, vp, scheme, f"shot={i}&local={MOMENTS[i] if i else 0.3}", dpr, hide=False)
            settle(page)
            out = REPORT / f"f206-{name}-{scheme}-{i}.jpg"
            page.screenshot(path=str(out), type="jpeg", quality=86)
            ctx.close()
            print("report", out.name)


# close-ups for judging the detail: (name, chapter, local, scheme, camera x,y,z, target x,y,z, fov)
CLOSE = [
    ("cabin", 2, 0.02, "light", None),
    ("cabin-night", 2, 0.02, "dark", None),
    ("pier-sunset", 4, 0.72, "light", None),
    ("pier-night", 4, 0.72, "dark", None),
    ("family-and-deck", 4, 0.7, "light", "cam=-84.5,2.4,-55.5,-91,1.9,-59.5,46"),
    ("trees-snow", 2, 0.02, "light", "cam={tx},{ty},{tz},{cx},{cy},{cz},38"),
    ("water", 4, 0.4, "light", "cam=-60,9,-120,-700,0,-900,50"),
    ("emerald-bay", 1, 0.95, "light", "cam=-9800,1400,3600,-12900,0,600,40"),
]


def closeups(browser, base):
    REPORT.mkdir(parents=True, exist_ok=True)
    for name, ch, local, scheme, cam in CLOSE:
        query = f"shot={ch}&local={local}"
        if cam and "{" in cam:
            # from the cabin close-up's own viewpoint (its corridor is kept clear of trees), look up over the roof at the snowy firs uphill
            ctx, page = open_page(browser, base, WIDE, scheme, query)
            c = page.evaluate("""() => { const { T } = window.__cover, P = T.places.cabin, h = (x, z) => T.landH(x, z);
              const gx = h(P[0] + 6, P[1]) - h(P[0] - 6, P[1]), gz = h(P[0], P[1] + 6) - h(P[0], P[1] - 6), n = Math.hypot(gx, gz) || 1, dx = -gx / n, dz = -gz / n;
              const cx = P[0] + dx * 30, cz = P[1] + dz * 30, tx = P[0] - dx * 40, tz = P[1] - dz * 40;
              return [cx, h(cx, cz) + 3.5, cz, tx, h(tx, tz) + 16, tz]; }""")
            cam = cam.format(tx=c[0], ty=c[1], tz=c[2], cx=c[3], cy=c[4], cz=c[5])
            ctx.close()
        ctx, page = open_page(browser, base, WIDE, scheme, query + (f"&{cam}" if cam else ""))
        settle(page)
        out = REPORT / f"f206-closeup-{name}.jpg"
        page.screenshot(path=str(out), type="jpeg", quality=90)
        ctx.close()
        print("closeup", out.name)


def video(browser, base, seconds=22, fps=30):
    tmp = Path(tempfile.mkdtemp(prefix="cover-video-", dir=os.environ.get("TMPDIR")))
    ctx = browser.new_context(viewport={"width": 1280, "height": 720}, color_scheme="light", reduced_motion="no-preference")
    page = ctx.new_page()
    page.goto(f"{base}/?capture&q=high")
    page.wait_for_function("!!(window.__cover && window.__cover.step)", timeout=90000)
    n = seconds * fps
    for k in range(n):
        t = k / (n - 1)
        T = 13.0 * t                                                                  # an even scroll from the book to the line
        page.evaluate(f"() => {{ const G = window.__cover.G; G.measure(); window.scrollTo(0, G.yFor({T:.4f})); G.read(); window.__cover.step(1 / {fps}); }}")
        page.screenshot(path=str(tmp / f"{k:05d}.jpg"), type="jpeg", quality=90)
    ctx.close()
    out = REPORT / "f206-scroll-1280.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmp / "%05d.jpg"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "29", "-preset", "slow", "-movflags", "+faststart", str(out)], check=True)
    print("video", out.name, out.stat().st_size // 1024, "KB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="+", choices=["stills", "og", "report", "closeups", "video"])
    ap.add_argument("--base", default="http://127.0.0.1:6206")
    a = ap.parse_args()
    with sync_playwright() as p:
        browser = launch(p, GPU)
        for w in a.what:
            {"stills": stills, "og": og, "report": report, "closeups": closeups, "video": video}[w](browser, a.base)
        browser.close()


if __name__ == "__main__":
    main()
