"""The creator pages next to the approved prototype (F-253): walks landing -> import -> book -> edit -> publish -> shelf on a running `scripts/f253_dev.py` and saves, for each state,
docs/report/f253-<width>-<mode>-<state>.png with the prototype's screenshot (docs/design/creators-v2/shots) on the left and the build's on the right.
    pixi run python scripts/f253_shots.py [1440|390] [light|dark]          (base address: F253_BASE, default http://127.0.0.1:5253)"""
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE = os.getenv("F253_BASE", "http://127.0.0.1:5253")
WIDTH = int(sys.argv[1]) if len(sys.argv) > 1 else 1440
MODE = sys.argv[2] if len(sys.argv) > 2 else "light"
PHONE = WIDTH < 720
SHOTS = ROOT / "docs" / "design" / "creators-v2" / "shots"
OUT = ROOT / "docs" / "report"
LEAD = ROOT / "tests" / "fixtures" / "creator_import" / "lisbon-48-hours" / "lead.jpg"
# build state -> the prototype's screenshot for it (its numbering differs at 390: it has one more book page)
PROTO = {1440: {"landing": "01-landing", "import-opening": "03-import-opening", "import-sentences": "05-import-sentences", "import-ready": "08-import-ready", "book-cover": "09-book-cover",
                "book-intro": "11-book-intro", "book-day": "13-book-day2", "edit-mode": "14-edit-mode", "edit-fixed": "16-edit-fixed", "book-end": "17-book-end", "publish-sheet": "19-publish-sheet",
                "published-share": "22-published-share", "community": "23-community"},
         390: {"landing": "01-landing", "import-opening": "03-import-opening", "import-sentences": "05-import-sentences", "import-ready": "08-import-ready", "book-cover": "09-book-cover",
               "book-intro": "11-book-intro", "book-day": "13-book-day1-stops", "edit-mode": "15-edit-mode", "edit-fixed": "17-edit-fixed", "book-end": "18-book-end", "publish-sheet": "20-publish-sheet",
               "published-share": "23-published-share", "community": "24-community"}}[WIDTH]
shots = {}


def snap(page, name):
    path = OUT / f".f253-build-{name}.png"
    page.screenshot(path=str(path))
    shots[name] = path


def compare(name):
    left = SHOTS / f"{WIDTH}{'-dark' if MODE == 'dark' else ''}-{PROTO[name]}.png"
    a, b = Image.open(left).convert("RGB"), Image.open(shots[name]).convert("RGB")
    scale = 0.5 if not PHONE else 0.8
    a, b = [i.resize((int(i.width * scale), int(i.height * scale))) for i in (a, b)]
    h = max(a.height, b.height) + 30
    sheet = Image.new("RGB", (a.width + b.width + 30, h), "#888888")
    sheet.paste(a, (0, 30))
    sheet.paste(b, (a.width + 30, 30))
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), f"prototype: {left.name}", fill="white")
    d.text((a.width + 38, 8), f"build: {name}", fill="white")
    sheet.quantize(256).save(OUT / f"f253-{WIDTH}-{MODE}-{name}.png", optimize=True)      # a palette keeps a side-by-side to about 150 KB
    shots[name].unlink()


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": WIDTH, "height": 844 if PHONE else 900}, has_touch=PHONE, is_mobile=PHONE)
    ctx.set_default_timeout(40000)
    ctx.request.post(f"{BASE}/signin", form={"email": "maya.chen@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page = ctx.new_page()
    page.route("https://theplanetd.com/images/**", lambda r: r.fulfill(status=200, content_type="image/jpeg", body=LEAD.read_bytes()))
    OUT.mkdir(parents=True, exist_ok=True)

    def dark():
        if MODE == "dark":
            page.evaluate("document.documentElement.dataset.mode='dark'")
    page.goto(BASE + "/for-creators")
    dark()
    page.wait_for_timeout(900)
    snap(page, "landing")
    page.click("#fc-example-chip")
    page.click("#fc-draft")
    page.wait_for_selector("#postCard.pic")
    page.wait_for_timeout(1000)
    snap(page, "import-opening")
    page.wait_for_selector("#river .snt.marked")
    page.wait_for_timeout(1800)
    snap(page, "import-sentences")
    page.wait_for_selector("#ready:not([hidden])")
    page.wait_for_timeout(700)
    snap(page, "import-ready")
    page.click("#openBook")
    page.wait_for_selector("#bookv")
    dark()
    page.wait_for_timeout(1300)
    snap(page, "book-cover")
    for _ in range(2):
        page.click("#next")
        page.wait_for_timeout(1500)
    snap(page, "book-intro")
    page.click("#next")
    page.wait_for_timeout(1500)
    snap(page, "book-day")
    page.click("#editBtn")
    page.wait_for_timeout(1500)
    snap(page, "edit-mode")
    page.locator('h2[data-k="d0.head"]' if PHONE else 'h2[data-k="d1.head"]').click()
    page.keyboard.type("Alfama and the tram")
    page.keyboard.press("Enter")
    page.wait_for_timeout(900)
    snap(page, "edit-fixed")
    page.click("#editDone")
    while not page.locator("#next").is_disabled():
        page.click("#next")
        page.wait_for_timeout(500)
    page.wait_for_timeout(900)
    snap(page, "book-end")
    page.click("#pubBtn")
    page.wait_for_timeout(500)
    snap(page, "publish-sheet")
    page.click("#mine")
    page.click("#pubGo")
    page.wait_for_selector("#sharep:not([hidden])")
    page.wait_for_timeout(900)
    snap(page, "published-share")
    page.goto(BASE + "/community")
    dark()
    page.wait_for_timeout(1300)
    snap(page, "community")
    browser.close()
for name in PROTO:
    compare(name)
print(f"saved {len(PROTO)} comparisons to {OUT}/f253-{WIDTH}-{MODE}-*.png")
