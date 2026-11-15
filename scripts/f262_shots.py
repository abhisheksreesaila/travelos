"""The guides next to the approved prototype (F-262): walks hub -> search -> menu -> a guide -> a stop -> make -> edit -> published on a running `scripts/f253_dev.py` (the recorded Lisbon post, the
dev sign-in, the showcase on) and saves, for each state, docs/report/f262-<width>-<mode>-<state>.png with the prototype's screenshot (docs/design/guides-v2/shots) on the left and the build's on the right.
    F253_PORT=5262 pixi run python scripts/f253_dev.py        (in another shell)
    pixi run python scripts/f262_shots.py [1440|390] [light|dark]          (base address: F262_BASE, default http://127.0.0.1:5262)
The prototype's guide is a made-up San Diego one with a stop for every kind of detail; the build's real-data guide is the recorded Lisbon post, whose stops carry the post's own sentences and tips and
no price or travel time (the post gives none, and nothing is invented), so the two differ in what a stop shows, not in how it is laid out."""
import json
import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE = os.getenv("F262_BASE", "http://127.0.0.1:5262")
WIDTH = int(sys.argv[1]) if len(sys.argv) > 1 else 1440
MODE = sys.argv[2] if len(sys.argv) > 2 else "light"
PHONE = WIDTH < 720
SHOTS = ROOT / "docs" / "design" / "guides-v2" / "shots"
OUT = ROOT / "docs" / "report"
LEAD = ROOT / "tests" / "fixtures" / "creator_import" / "lisbon-48-hours" / "lead.jpg"
POST = "https://theplanetd.com/48-hours-in-lisbon-itinerary/"
SAMPLE = "sun-tacos-and-tide-pools"
# build state -> the prototype's screenshot for it
PROTO = {"hub": "01-hub", "hub-search": "02-hub-search", "menu": "03-menu", "guide": "04-guide", "guide-stop": "05-guide-stop", "make": "12-make", "make-blog": "13-make-blog", "make-trip": "14-make-trip",
         "edit": "15-edit", "published": "16-published"}
shots = {}


def snap(page, name, full=False):
    path = OUT / f".f262-build-{name}.png"
    page.screenshot(path=str(path), full_page=full)
    shots[name] = path


def compare(name):
    dark = MODE == "dark"
    left = SHOTS / f"{WIDTH}-{PROTO[name]}{'-dark' if dark else ''}.png"
    if not left.exists():
        left = SHOTS / f"{WIDTH}-{PROTO[name]}.png"
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
    sheet.quantize(256).save(OUT / f"f262-{WIDTH}-{MODE}-{name}.png", optimize=True)      # a palette keeps a side-by-side small
    shots[name].unlink()


def context(browser, email):
    ctx = browser.new_context(viewport={"width": WIDTH, "height": 844 if PHONE else 900}, has_touch=PHONE, is_mobile=PHONE, reduced_motion="reduce")
    ctx.set_default_timeout(40000)
    ctx.add_init_script(f"localStorage.setItem('ga-mode', '{MODE}')")
    ctx.request.post(f"{BASE}/signin", form={"email": email, "next": "/", "intent": "save"}, max_redirects=0)
    return ctx


with sync_playwright() as p:
    browser = p.chromium.launch()
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = context(browser, f"maya{time.time_ns()}@example.com")
    ctx.route("https://theplanetd.com/images/**", lambda r: r.fulfill(status=200, content_type="image/jpeg", body=LEAD.read_bytes()))
    r = ctx.request.post(f"{BASE}/creators/import", form={"do": "draft", "link": POST}, headers={"X-Magic": "1"})
    draft = [json.loads(line) for line in r.text().splitlines() if line.strip()][-1]
    did = draft["id"]
    page = ctx.new_page()
    page.route("https://theplanetd.com/images/**", lambda r: r.fulfill(status=200, content_type="image/jpeg", body=LEAD.read_bytes()))

    page.goto(f"{BASE}/guides")
    page.wait_for_timeout(600)
    snap(page, "hub")
    page.fill("#gh-q", "San D")
    page.wait_for_timeout(500)
    snap(page, "hub-search")
    page.fill("#gh-q", "")
    page.click("#v2-me")
    page.wait_for_timeout(400)
    snap(page, "menu")
    page.keyboard.press("Escape")
    page.evaluate("document.getElementById('make').scrollIntoView({block: 'center'})")
    page.wait_for_timeout(300)
    snap(page, "make")
    page.goto(f"{BASE}/guides/make")
    page.wait_for_timeout(600)
    snap(page, "make-blog")
    page.goto(f"{BASE}/trips/{SAMPLE}")
    page.wait_for_timeout(600)
    snap(page, "guide")

    # the owner's guide: edit a word, publish, share
    page.goto(f"{BASE}/creators/import/{did}/guide")
    page.wait_for_timeout(500)
    page.locator(".g-chev.g-open").nth(0).click()
    page.wait_for_timeout(700)
    snap(page, "guide-stop")
    page.click("#g-close")
    word = page.locator('[data-k="d0.head"]')
    word.click()
    page.keyboard.press("Control+A")
    page.keyboard.type("Belém and the river")
    page.wait_for_timeout(200)
    snap(page, "edit")
    page.keyboard.press("Enter")
    page.click("#pubBtn")
    page.click("#mine")
    page.click("#pubGo")
    page.wait_for_selector("#sharep:not([hidden])")
    page.wait_for_timeout(900)
    snap(page, "published")

    # from my trip: a family with a booked trip and a few plans
    fam = context(browser, f"ari{time.time_ns()}@example.com")
    fam.request.post(f"{BASE}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
    for i, (title, start, end, kind) in enumerate((("Breakfast tacos", "09:00", "10:00", "food"), ("Sea lions at the cove", "11:00", "12:30", "outdoors"), ("Dinner on the pier", "18:30", "20:00", "food"))):
        fam.request.post(f"{BASE}/trip/plans", form={"id": f"a{i + 1}", "day": "1", "start": start, "end": end, "title": title, "kind": kind}, max_redirects=0)
    fp = fam.new_page()
    fp.goto(f"{BASE}/guides")
    fp.click("#mk-trip button")
    fp.wait_for_url("**/guide")
    fp.wait_for_timeout(700)
    snap(fp, "make-trip")
    for name in shots.copy():
        compare(name)
    browser.close()
print("saved", sorted(f.name for f in OUT.glob(f"f262-{WIDTH}-{MODE}-*.png")))
