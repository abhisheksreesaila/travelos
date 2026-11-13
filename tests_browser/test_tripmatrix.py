"""F-222 in a real browser: the trip matrix at laptop (1440, calendar lanes and the side panel) and phone (390, place cards and a sheet). A stand-in source answers every
square from a fixed table (gridsource.SQUARE), so the find and the marks are known; by default it answers nothing to a peek, so every square loads like a map tile.
Set F222_SHOTS=1 for docs/design/trip-matrix/built/*.png."""
import os
import re
import threading
from datetime import date
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import gridsource, tripmatrix as tm
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "design" / "trip-matrix" / "built"
URL = "/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16&a=2&k=7,10&x=2&b=2300"
# dollars by lane, Dec 10 to 14: LA + San Diego is $50 more than San Diego on the 12th, the find
TABLE = {"sandiego": (2310, 2260, 2140, 2080, 2390), "losangeles": (2480, 2410, 2350, 2400, 2550), "orangecounty": (2420, 2380, 2290, 2240, 2610),
         "losangeles+sandiego": (2400, 2330, 2190, 2160, 2470), "orangecounty+sandiego": (2500, 2450, 2380, None, 2600)}
STARTS = ("2026-12-10", "2026-12-11", "2026-12-12", "2026-12-13", "2026-12-14")


class Stand:
    """A source with a fixed table. `peek_all`: the page's server knows every square (no script needed); else it knows none. Records what was asked for."""

    def __init__(self):
        self.peek_all, self.asked, self.lock = False, [], threading.Lock()

    def __call__(self, lane, w, adults=2, kid_ages=(), home="", family="", peek=False, rank=0):
        if peek and not self.peek_all:
            return None
        if not peek:
            with self.lock:
                self.asked.append(tm.key(lane.key, w.key))
        dollars = TABLE[lane.key][STARTS.index(w.key)]
        if dollars is None:
            return tm.Square(lane.key, w.key, tm.NONE)
        flight = tm.FlightPart("Test Air", "Sat, Dec 12 · SFO 8:05 AM → SAN 9:32 AM · Nonstop", "Wed, Dec 16 · SAN 6:40 PM → SFO 8:10 PM · Nonstop", 0, 60_000)
        stays = tuple(tm.StayPart(p.name, w.nights // len(lane.places), f"Test Stay {p.name}", "Two queens", "breakfast", True, 16_000 if i == 0 else 0, "", "9.1 of 10",
                                  (dollars * 100 - 60_000) // len(lane.places) + (dollars * 100 - 60_000) % len(lane.places) * (i == 0)) for i, p in enumerate(lane.places))
        return tm.Square(lane.key, w.key, tm.OK, flight, stays, 25, None, False)


@pytest.fixture
def stand(monkeypatch):
    s = Stand()
    monkeypatch.setattr(gridsource, "SQUARE", s)
    return s


@pytest.fixture
def matrix(browser, base_url, stand):
    contexts = []

    def matrix(viewport=DESKTOP, js=True, scheme="light", motion=False, url=URL, wait=True, signed_in=False):
        phone = viewport is PHONE
        ctx = browser.new_context(viewport=viewport, reduced_motion="no-preference" if motion else "reduce", java_script_enabled=js, color_scheme=scheme,
                                  has_touch=phone, is_mobile=phone)
        ctx.set_default_timeout(8000)
        contexts.append(ctx)
        if signed_in:
            ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.goto(base_url + url)
        if js:
            page.wait_for_selector("#mx.is-live")
            if wait:
                page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
        return page

    yield matrix
    for c in contexts:
        c.close()


def drawn(page):
    """{key: (marks, words)} of the squares on screen (the laptop's lanes or the phone's cards)."""
    got = page.evaluate("""() => [...document.querySelectorAll('.mx-sq[data-sq]')].filter(e => e.offsetParent).map(e =>
        [e.dataset.sq, ['find', 'low', 'over'].filter(m => e.classList.contains('is-' + m)), e.querySelector('.mx-in').textContent.trim()])""")
    return {k: (tuple(m), w) for k, m, w in got}


def totals():
    return {tm.key(lane, w): d * 100 for lane, row in TABLE.items() for w, d in zip(STARTS, row) if d is not None}


def test_server_and_script_mark_the_same(matrix, stand):
    live = drawn(matrix())                                   # every square answered by a tile, marked by assets/js/tripmatrix.js
    stand.peek_all = True
    still = drawn(matrix(js=False))                          # every square known to the server, marked by gitaway/tripmatrix.py
    assert len(live) == len(still) == 25 and live == still
    from gitaway.partners import places
    found = tm.find(tm.lanes(places.resolve("San Diego")), tm.windows(date(2026, 12, 12), date(2026, 12, 16), 2, date(2026, 9, 30)), totals())
    assert live[found.key][0] == ("find",) and live["sandiego|2026-12-13"][0] == ("low",) and "over" in live["sandiego|2026-12-10"][0]
    assert live["orangecounty+sandiego|2026-12-13"] == ((), "None found")


def test_the_find_is_said_with_real_totals(matrix):
    page = matrix()
    expect(page.locator("#mx-find-w")).to_have_text("Los Angeles + San Diego, $50 more than San Diego alone")
    expect(page.locator("#mx-find-d")).to_have_text(" · Dec 12 to 16")
    page.click("#mx-find-a")
    expect(page.locator("#mx-side .mx-p-h")).to_have_text("Los Angeles + San Diego · Dec 12 to 16")
    expect(page.locator("#mx-side [data-slot='total']")).to_have_text("$2,190")
    expect(page.locator("#mx-side .mx-vs")).to_have_text("+$50 vs San Diego alone")
    expect(page.locator("#mx-side")).to_contain_text("$160 of it paid at the hotel")


def test_only_squares_in_view_are_asked_for_and_the_rest_wait_as_skeletons(matrix, stand):
    page = matrix(PHONE, wait=False)
    page.wait_for_function("() => document.querySelectorAll('.mx-card[data-lane=\"sandiego\"] .mx-sq.is-ok').length === 5")
    page.wait_for_timeout(400)
    asked = set(stand.asked)
    assert {f"sandiego|{w}" for w in STARTS} <= asked
    assert not any(k.startswith("orangecounty+sandiego|") for k in asked)                    # the last card is far below the screen: not asked for
    last = page.locator(".mx-card[data-lane='orangecounty+sandiego'] .mx-sq").first
    assert "is-wait" in last.get_attribute("class")
    last.scroll_into_view_if_needed()
    expect(last).not_to_have_class(re.compile("is-wait"))
    assert any(k.startswith("orangecounty+sandiego|") for k in stand.asked)


def test_a_square_scrolled_past_before_its_turn_is_never_asked_for(matrix, stand, slow_server):
    slow_server(r"/plan/matrix/tile", 0.6)
    page = matrix(PHONE, wait=False)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_function("() => document.querySelectorAll('.mx-card[data-lane=\"orangecounty+sandiego\"] .mx-sq.is-wait').length === 0", timeout=15000)
    middle = [k for k in stand.asked if k.startswith("orangecounty|")]
    assert middle == [], middle                                                               # passed by before its turn: never searched


def test_a_waiting_square_is_a_skeleton_never_a_number_and_the_fact_or_the_wait_is_said(matrix, slow_server):
    slow_server(r"/plan/matrix/tile", 5)
    page = matrix(DESKTOP, wait=False, motion=True)
    waits = page.locator(".mx-lane .mx-sq.is-wait")
    expect(waits.first).to_be_visible()
    for text, label in page.eval_on_selector_all(".mx-lane .mx-sq.is-wait", "els => els.map(e => [e.innerText, e.getAttribute('aria-label')])"):
        assert not re.search(r"\d", text) and label.endswith("searching")
    shimmer = page.eval_on_selector(".mx-lane .mx-sq.is-wait", "e => getComputedStyle(e).animationName")
    assert shimmer == "ga-shimmer"
    expect(page.locator(".mx-slow")).to_be_visible(timeout=8000)                            # a search that takes a while says so, never a frozen page
    expect(page.locator("#mx-count")).to_contain_text("of 25 in")


def test_reduced_motion_keeps_the_skeleton_still(matrix, slow_server):
    slow_server(r"/plan/matrix/tile", 3)
    page = matrix(DESKTOP, wait=False)
    assert page.eval_on_selector(".mx-lane .mx-sq.is-wait", "e => getComputedStyle(e).animationName") == "none"


def test_phone_cards_open_a_sheet_that_grows_from_the_square_and_folds_back(matrix):
    page = matrix(PHONE, motion=True)
    expect(page.locator(".mx-stage")).to_be_hidden()
    expect(page.locator(".mx-card")).to_have_count(5)
    sq = page.locator(".mx-card[data-lane='losangeles'] .mx-sq").nth(2)
    box = sq.bounding_box()
    assert box["height"] >= 47.5 and box["width"] >= 47.5
    sq.click()
    sheet = page.locator(".mx-sheet")
    expect(sheet).to_be_visible()
    expect(sheet.locator(".mx-p-h")).to_have_text("Los Angeles · Dec 12 to 16")
    expect(sheet).to_contain_text("Booking opens soon.")
    expect(sheet.locator(".mx-save")).to_be_visible()
    opened = page.evaluate("() => GA.motion.log.filter(m => m.kind === 'open').slice(-1)[0]")
    assert opened and not opened.get("calm") and opened["from"]                               # grew out of the square
    page.click(".mx-x")
    expect(sheet).to_have_count(0)
    page.keyboard.press("Escape")
    assert page.errors == []


def test_the_laptop_is_liquid_here_the_one_named_exception(matrix):
    page = matrix(DESKTOP, motion=True)
    assert page.evaluate("document.documentElement.hasAttribute('data-liquid') && GA.motion.calm() === false")
    page.click(".mx-lane[data-lane='sandiego'] .mx-sq >> nth=3")
    expect(page.locator("#mx-side .mx-p-h")).to_have_text("San Diego · Dec 13 to 17")
    opened = page.evaluate("() => GA.motion.log.filter(m => m.kind === 'open').slice(-1)[0]")
    assert opened and not opened.get("calm")
    expect(page.locator(".mx-lane[data-lane='sandiego'] .mx-band")).to_have_attribute("style", re.compile(r"grid-column: 5 / span 5"))
    page.goto(page.url.split("/plan/")[0] + "/plan")
    assert page.evaluate("!document.documentElement.hasAttribute('data-liquid')")             # everywhere else the laptop stays calm


def test_save_to_trip_keeps_you_on_the_matrix(matrix):
    page = matrix(DESKTOP, signed_in=True)
    page.click(".mx-lane[data-lane='losangeles+sandiego'] .mx-sq >> nth=2")
    page.click("#mx-side .mx-save")
    expect(page.locator("#mx-side .mx-saved")).to_contain_text("Saved to your trip")
    assert "/plan/matrix" in page.url


def test_without_the_script_every_square_is_a_link_to_its_own_page(matrix, stand):
    stand.peek_all = True
    page = matrix(js=False)
    page.click(".mx-lane[data-lane='losangeles'] .mx-sq >> nth=0")
    expect(page.locator(".mx-p-h")).to_have_text("Los Angeles · Dec 10 to 14")
    expect(page.locator(".mx-back")).to_be_visible()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_it_reads_fits_and_is_easy_to_tap_in_light_and_dark(matrix, viewport, scheme):
    page = matrix(viewport, scheme=scheme)
    for y in range(0, 4000, 300):      # the audit scrolls through the page: let every card land first (step by step: a jump skips them), so it measures squares at rest
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(120)      # the observer reports on its next frame
        page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
    assert not page.evaluate("[...document.querySelectorAll('.mx-sq.is-wait')].some(e => e.offsetParent)")
    page.evaluate("window.scrollTo(0, 0)")
    if viewport is DESKTOP:
        page.click("#mx-find-a")
    page.wait_for_function("() => document.getAnimations().every(a => a.effect.getTiming().iterations === Infinity || a.playState !== 'running')")
    page.wait_for_timeout(700)      # the last arrivals' settle (--motion-settle-dur) and the find's
    seen = audit(page)
    assert seen["wide"] <= 1, seen["wide"]
    for key in ("small", "tiny", "low", "glass"):
        assert not seen[key], (key, seen[key][:6])
    if os.getenv("F222_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"matrix-{viewport['width']}-{scheme}.png"))
        if viewport is PHONE:
            page.locator(".mx-card[data-lane='losangeles+sandiego'] .mx-sq").nth(2).click()
            page.wait_for_timeout(300)
            page.screenshot(path=str(SHOTS / f"matrix-sheet-390-{scheme}.png"))


def test_the_sheet_fits_the_phone(matrix):
    page = matrix(PHONE)
    page.locator(".mx-card[data-lane='losangeles+sandiego'] .mx-sq").nth(2).click()
    expect(page.locator(".mx-sheet .mx-save")).to_be_visible()
    wide = page.evaluate("() => { const s = document.querySelector('.mx-sheet'); return [s.scrollWidth, s.clientWidth, Math.max(...[...s.querySelectorAll('.mx-r-n')].map(e => e.getBoundingClientRect().right))]; }")
    assert wide[0] <= wide[1] + 1 and wide[2] <= 390, wide


def test_the_side_starts_on_the_find_once_it_is_known(matrix):
    page = matrix(DESKTOP)
    expect(page.locator("#mx-side .mx-p-h")).to_have_text("Los Angeles + San Diego · Dec 12 to 16")
