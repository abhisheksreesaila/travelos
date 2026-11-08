"""The cover's product screenshots (the agreed story, docs/decisions.md D-354..D-363): real pages of this branch showing the cover's made-up family's
Tahoe trip, at 390 and 1440, light and dark, saved as WebP in assets/cover/shots/.

    TMPDIR=$HOME/.cache/gitaway-testtmp pixi run python scripts/cover_shots.py [--serve] [--only plan,cockpit,...] [--port 6031]

It runs the app in this process on 127.0.0.1 (default port 6031) with a copy of the local dev data (GITAWAY_DEV_DATA, default
~/.cache/gitaway-dev-data/db) and the showcase on, signs in as the story's family (a made-up address), imports the founder's Tahoe trip from
tests/tahoe.py with the family's made-up names (Lena, Sam, Noa and Theo: D-270), writes a made-up family chat, publishes the trip as a trail,
and answers every map, AI and weather call from that file's real data, a canned reply or a refusal, so nothing leaves the machine and no real
person's data is on any page it shoots. `--serve` seeds and keeps the server up for a look in a browser.
"""
import argparse
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
OUT = REPO / "assets" / "cover" / "shots"
EMAIL = "lena@example.com"                 # made up: the cover's family (D-270)
SIZES = {"phone": {"width": 390, "height": 844}, "wide": {"width": 1440, "height": 900}}
DPR = {"phone": 2, "wide": 1}
# encoded widths: a phone shot is shown about 300 css px wide (about 2x), a laptop shot up to about 900 css px wide (1x and 1.6x)
WIDTHS = {"phone": (600,), "wide": (960, 1440)}
QUALITY = {"phone": 72, "wide": 70}
# the booking scene (cover v3, D-380..): only the booking lanes and the side panel beside them (weather, cost, the airport drive), cut out of /plan at
# 1440 wide and 2x, down to the bottom of the panel, so the cover can ring each part (and a phone zoom into it); one picture for phone and laptop
CROP = {"book": "#pw"}
CROP_W = {"wide": (960, 1600)}
CROP_DPR = 2
# the drive from Reno to South Lake Tahoe as OSRM's public router answered it on 2026-11-08 (gitaway/airportdrive.py, 83 min): the shots ask no service
DRIVE = ("RNO", "South Lake Tahoe, California", 83)

TEMPLATE_NAMES = (("- name: Abhi", "- name: Lena"), ("- name: Maya", "- name: Sam"), ("- name: Kid 1", "- name: Noa"), ("- name: Kid 2", "- name: Theo"))
CHAT = (   # (who, text, when in UTC on Mon Dec 21): the family's chat on the trip, made up
    ("Sam", "Chains are in the SUV. Leaving the cabin at 9:30 for snowshoeing?", "15:02"),
    ("me", "Yes! Noa wants hot chocolate at Taylor Creek after.", "15:04"),
    ("Sam", "Booked the sled hill for Christmas Day, 1 pm.", "15:21"),
    ("me", "Perfect. Theo is asking if it snows tonight.", "15:40"),
    ("Sam", "After 6, they say. Pizza night at the cabin then.", "15:43"),
)
MORE_PLANS = ((2, "08:00", "08:45", "Pancakes at the cabin", "food"), (2, "16:30", "17:30", "Hot tub at the cabin", "fun"),
              (2, "18:30", "19:30", "Pizza night", "food"))
TRAIL = {"title": "Five snowy days at Lake Tahoe", "name": "Lena & Sam"}
ASK = "Move snowshoeing after lunch and add hot chocolate at Taylor Creek"
PLAN = "/plan?place=Lake%20Tahoe&home=SFO&d=2027-02-05&r=2027-02-09&a=2&n=2&k1=11&k2=8"


def _env(data):
    os.environ.update({"GITAWAY_DATA_DIR": str(data), "GITAWAY_DEV_LOGIN": "1", "GITAWAY_SHOWCASE": "1", "DB_TYPE": "SQLITE", "DB_NAME": "app_host",
                       "PLAN_FOR_ME_PAID": "0", "PLAN_FOR_ME_REVIEW": "0", "MET_NORWAY_TERMS_ACCEPTED": ""})
    for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "ANTHROPIC_API_KEY", "SARVAM_API_KEY", "TRAVELPAYOUTS_DRIVE_ID", "TRAVELPAYOUTS_MARKER", "TRAVELPAYOUTS_TOKEN",
              "GITAWAY_VAPID_PUBLIC", "GITAWAY_VAPID_PRIVATE", "GITAWAY_VAPID_SUBJECT", "GITAWAY_ENV", "RAILWAY_ENVIRONMENT"):
        os.environ[k] = ""
    # Ask's model is the canned reply below: a stand-in Azure deployment, so the box offers itself
    os.environ.update({"AZURE_OPENAI_API_KEY": "k", "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com", "AZURE_OPENAI_DEPLOYMENT": "gpt-story"})
    for k in [k for k in os.environ if k.startswith("GITAWAY_AI_")]:
        os.environ[k] = ""


def _patch():
    """Everything that would reach the network answers from tests/tahoe.py's real data, a canned reply or not at all."""
    from gitaway import ai, catalog, geo, geopack, safefetch, weather
    from tests import tahoe
    geo.fetch, geo.ASYNC = tahoe.geo_fetch, False
    geopack.TRANSPORT, geopack.ASYNC, geopack.LONG_SIDE = tahoe.pack_transport, False, 1600

    def refuse(*a, **k):
        raise OSError("the network is off for the cover's screenshots")
    weather.TRANSPORT = safefetch.TRANSPORT = ai.ANTHROPIC_TRANSPORT = refuse
    from gitaway import airportdrive
    iata, town, minutes = DRIVE
    airportdrive._keep((iata, town.lower()), airportdrive.Drive(iata, town, minutes))
    catalog.now_utc = lambda: tahoe.NOW
    catalog.today = lambda: tahoe.NOW.astimezone(catalog.TZ).date()
    ai.TRANSPORT = _ask_reply


def _ask_reply(url, headers, body, timeout):
    """Ask's model, canned for ASK on Monday: snowshoeing after lunch, lunch a little earlier, hot chocolate to finish."""
    from tests.canvas_samples import azure_reply
    ctx = json.loads(json.loads(body)["messages"][1]["content"])
    plans = (ctx.get("day") or {}).get("plans") or []
    find = lambda word: next((p for p in plans if word in (p.get("title") or "")), None)      # noqa: E731
    base = {"id": None, "title": None, "start": None, "end": None, "note": None, "block_id": None, "part_id": None, "time": None, "who": []}
    ops = []
    if (snow := find("Snowshoe")):
        ops.append({**base, "op": "move_plan", "id": snow["id"], "start": "13:30", "end": "15:30"})
    ops.append({**base, "op": "add_plan", "title": "Hot chocolate at Taylor Creek", "start": "15:30", "end": "16:15"})
    if (lunch := find("Lunch")):
        ops.append({**base, "op": "move_plan", "id": lunch["id"], "start": "12:00", "end": "13:00"})
    return azure_reply({"summary": "Snowshoeing moves after lunch, with hot chocolate at Taylor Creek to finish.", "ops": ops})


def serve(port):
    import uvicorn
    from main import app
    _patch()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(200):
        if server.started:
            return server, t
        time.sleep(0.05)
    raise RuntimeError("the server did not start")


def sign_in(base, ctx):
    r = ctx.request.post(f"{base}/signin", form={"email": EMAIL, "next": "/", "intent": "save"}, max_redirects=0)
    assert r.status in (302, 303), r.status


def seed(base, ctx):
    """Sign in as the story's family, import the trip, add its plans, fill the map cache, build the paper map, write the chat, publish the trail.
    Returns the trail's public path."""
    from gitaway import auth, familydb, familythread, geo, geopack, publish, session as ses, tripcal as cal, tripgeo
    from tests import tahoe
    sign_in(base, ctx)
    text = tahoe.TEMPLATE
    for a, b in TEMPLATE_NAMES:
        text = text.replace(a, b)
    r = ctx.request.post(f"{base}/trips/import/save", form={"text": text}, max_redirects=0)
    assert r.status in (302, 303), r.status
    me = {}
    auth.sign_in_dev(me, EMAIL)
    for day, s, e, title, kind in (*tahoe.PLANS, *MORE_PLANS):
        h1, m1 = map(int, s.split(":"))
        h2, m2 = map(int, e.split(":"))
        cal.add_activity(me, day=day, start=h1 * 60 + m1, end=h2 * 60 + m2, title=title, kind=kind)
    with familydb.using(me) as db:
        for group in tripgeo.day_places(me):
            geo.warm(db, group, budget=30)
    assert geopack.ensure(me) == "ready"
    with ses.family(me) as fam:
        mine = fam.traveler.id
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "DELETE FROM thread WHERE trip_id = :t", t=fam.trip_id)       # the plan-change cards the seeding wrote: only the chat stays
            for who, msg, at in CHAT:
                familythread._insert(fam.db, fam.trip_id, "message", mine if who == "me" else "story-sam", "Lena" if who == "me" else who, msg)
                familydb.run(fam.db, "UPDATE thread SET created_at = :c WHERE text = :x", c=f"2026-12-21T{at}:00+00:00", x=msg)
    # home again: the trip published as a trail, through the editor's own routes
    ctx.request.post(f"{base}/trip/publish/save", form={**TRAIL, "do": "preview"}, max_redirects=0)
    r = ctx.request.post(f"{base}/trip/publish", form={"names_ok": "1"}, max_redirects=0)
    assert r.status in (302, 303), r.status
    me = {}
    auth.sign_in_dev(me, EMAIL)
    return f"/trips/{publish.live(me)['slug']}"


# ---- the shots: (path on a phone, path on a laptop, signed in, what to do once the page is up) ---------------------------------------------

def _ready(page):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(900)


def _cockpit(page, layout):
    page.wait_for_selector("#ck-paper[data-ready='1']", timeout=30000)
    page.wait_for_timeout(1500)


def _ask(page, layout):
    if layout == "wide":
        page.locator("[data-tab=ask]").click()
        page.wait_for_selector("#ak-text")
    page.locator("#ak-text").fill(ASK)
    page.locator("button", has_text="Done" if layout == "wide" else "Ask GitAway").first.click()
    page.wait_for_selector("text=Here's the change", timeout=15000)
    page.wait_for_timeout(900)


def _top(page, layout):
    """The day view scrolls its timeline to now: start the shot at the top of the page, with the day's heading."""
    page.evaluate("scrollTo(0, 0)")
    page.wait_for_timeout(600)


SHOTS = {
    "plan": (PLAN, PLAN, True, None),
    "book": (None, PLAN, True, None),            # laptop only, cut to CROP
    "cockpit": ("/trip/cockpit", "/trip/cockpit", True, _cockpit),
    "day": ("/trip/today", "/trip/canvas?day=2", True, _top),
    "ask": ("/trip/ask?day=2", "/trip/canvas?day=2", True, _ask),
    "family": ("/trip/family", "/trip/canvas?day=2&panel=family", True, None),
    "trail": ("{trail}", "{trail}", False, _top),
    "creators": ("/for-creators", "/for-creators", False, None),
}


def shoot(browser, base, name, layout, scheme, trail):
    phone_path, wide_path, signed, act = SHOTS[name]
    vp, phone = SIZES[layout], layout == "phone"
    ctx = browser.new_context(viewport=vp, device_scale_factor=CROP_DPR if name in CROP else DPR[layout], color_scheme=scheme, reduced_motion="reduce", is_mobile=phone, has_touch=phone,
                              service_workers="block")
    ctx.route("**/*", lambda r: r.abort() if not r.request.url.startswith((base, "https://fonts.googleapis.com", "https://fonts.gstatic.com")) else r.continue_())
    if signed:
        sign_in(base, ctx)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base + (phone_path if phone else wide_path).format(trail=trail))
    _ready(page)
    if act:
        act(page, layout)
    page.evaluate("document.fonts.ready")
    if name in CROP:      # the lanes and the panel beside them, a little margin round them
        box = page.evaluate("""sel => { const p = document.querySelector(sel), r = p.parentElement.getBoundingClientRect(), x = r.left - 16, y = r.top + scrollY - 8;
          return { x, y, width: r.width + 32, height: p.getBoundingClientRect().bottom + scrollY + 12 - y }; }""", CROP[name])
        png = page.screenshot(full_page=True, clip=box)
    else:
        png = page.screenshot()
    ctx.close()
    if errors:
        print(f"  {name} {layout} {scheme}: page errors {errors}", flush=True)
    return png


def save(png, name, layout, scheme):
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    for w in (CROP_W[layout] if name in CROP else WIDTHS[layout]):
        out = im if im.width == w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
        path = OUT / f"{name}-{layout}-{scheme}-{w}.webp"
        out.save(path, "WEBP", quality=QUALITY[layout], method=6)
        print(f"{path.relative_to(REPO)} {path.stat().st_size / 1024:.0f} KB", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--port", type=int, default=6031)
    args = ap.parse_args()
    src = Path(os.environ.get("GITAWAY_DEV_DATA", Path.home() / ".cache" / "gitaway-dev-data" / "db"))
    data = Path(tempfile.mkdtemp(prefix="gitaway-cover-shots-"))
    if src.is_dir():
        shutil.copytree(src, data, dirs_exist_ok=True)
    _env(data)
    os.chdir(data)
    with socket.socket() as s:
        assert s.connect_ex(("127.0.0.1", args.port)) != 0, f"port {args.port} is taken"
    server, thread = serve(args.port)
    base = f"http://127.0.0.1:{args.port}"
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context()
            trail = seed(base, ctx)
            ctx.close()
            if args.serve:
                print(f"serving {base} (sign in as {EMAIL}); the trail is {trail}; data {data}; Ctrl-C to stop", flush=True)
                while True:
                    time.sleep(1)
            only = set(filter(None, args.only.split(",")))
            OUT.mkdir(parents=True, exist_ok=True)
            for name in SHOTS:
                if only and name not in only:
                    continue
                for layout in [x for x in SIZES if SHOTS[name][0 if x == "phone" else 1]]:
                    for scheme in ("light", "dark"):
                        save(shoot(browser, base, name, layout, scheme, trail), name, layout, scheme)
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    main()
