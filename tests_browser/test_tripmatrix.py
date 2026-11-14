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

    def __call__(self, lane, w, adults=2, kid_ages=(), home="", family="", peek=False, rank=0, wait=None):
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
    expect(sheet).to_contain_text("Sandbox booking: nothing is charged.")
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
    expect(page.locator(".mx-lane[data-lane='sandiego'] .mx-band")).to_have_attribute("style", re.compile(r"grid-column: 7 / span 5"))
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


def test_the_phone_square_says_its_total_large_and_its_days_weather_small_under_it(matrix):
    """F-230: the number first; the start day's sky and degrees one small line under it; no weather row above the prices (the phone's cards)."""
    page = matrix(PHONE)
    assert page.locator(".mx-sky").count() == 0
    got = page.evaluate("""() => [...document.querySelectorAll('.mx-sq.is-ok')].filter(e => e.offsetParent && e.querySelector('.mx-sqw')).map(e => {
        const v = e.querySelector('.mx-v').getBoundingClientRect(), w = e.querySelector('.mx-sqw').getBoundingClientRect();
        return [parseFloat(getComputedStyle(e.querySelector('.mx-v')).fontSize), parseFloat(getComputedStyle(e.querySelector('.mx-sqw')).fontSize), v.bottom <= w.top + 1,
                w.right <= e.getBoundingClientRect().right + 1];
    })""")
    assert got
    for big, small, under, fits in got:
        assert big > small and under and fits and big >= 20, (big, small, under, fits)      # a start total is at least 20px on a phone


def test_the_laptop_lane_days_wear_their_sky_and_the_totals_are_big_and_ringed_in_a_band_inside_the_grid(matrix):
    """F-236 (docs/design/trip-matrix/matrix-c.html): every day of a lane wears its sky (icon, high, chance of a wet day), the start totals sit under their days in pills
    at least 1.4 times the sky's size, the asked day's head is ink, the nights are a band that holds its five days and never passes the grid's edge."""
    page = matrix(DESKTOP)
    lane = page.locator(".mx-lane[data-lane='sandiego']")
    assert lane.locator(".mx-day").count() == 13 and lane.locator(".mx-day.is-typ .mx-day-i").count() == 13
    assert " ".join(lane.locator(".mx-day").nth(4).inner_text().split()) == "66° 19%"      # Dec 12, San Diego: NOAA's typical high and chance of a wet day
    expect(page.locator(".mx-ad.is-ask")).to_have_text(re.compile(r"SAT\s*12", re.I))
    sizes = page.evaluate("""() => { const q = s => parseFloat(getComputedStyle(document.querySelector(s)).fontSize);
        return [q('.mx-lane .mx-sq .mx-v'), q('.mx-lane .mx-day-t'), q('.mx-l-best'), q('#mx-side .mx-p-n')]; }""")
    assert sizes[0] >= 16 and sizes[0] >= 1.4 * sizes[1] and sizes[2] >= 20 and sizes[3] >= 36, sizes
    fit = page.evaluate("""() => { const grid = document.querySelector('.mx-lanes').getBoundingClientRect();
        return [...document.querySelectorAll('.mx-band')].map(b => { const r = b.getBoundingClientRect(), lane = b.closest('.mx-lane');
          const inside = [...lane.querySelectorAll('.mx-day.is-in')].map(d => d.getBoundingClientRect());
          return [r.left >= grid.left - 1 && r.right <= grid.right + 1, inside.length, inside.every(d => d.left >= r.left - 1 && d.right <= r.right + 1)]; }); }""")
    assert len(fit) == 5 and all(ok and n == 5 and holds for ok, n, holds in fit), fit
    on = page.evaluate("() => [...document.querySelectorAll('.mx-lane .mx-sq.is-on')].map(e => e.dataset.sq)")
    assert on == ["sandiego|2026-12-13", "losangeles|2026-12-12", "orangecounty|2026-12-13", "losangeles+sandiego|2026-12-12", "orangecounty+sandiego|2026-12-12"]
    assert page.eval_on_selector(".mx-lane.is-lit .mx-band", "e => e.dataset.l").startswith("Found · +")
    colours = page.evaluate("""() => { const c = e => getComputedStyle(e).backgroundColor, f = document.querySelector('.mx-lane .mx-sq.is-find'), o = document.querySelector('.mx-lane:not(.is-lit) .mx-sq.is-on');
        return [c(f), c(o)]; }""")
    assert colours[0] == "rgb(255, 212, 59)" and colours[1] == "rgb(11, 11, 13)", colours      # the find is yellow, the nights shown are ink
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")


def test_a_start_price_tap_moves_the_band_its_label_and_the_ink_pill_and_opens_the_bar(matrix):
    page = matrix(DESKTOP)
    page.click(".mx-lane[data-lane='losangeles'] .mx-sq >> nth=3")
    lane = page.locator(".mx-lane[data-lane='losangeles']")
    expect(lane.locator(".mx-band")).to_have_attribute("data-l", re.compile(r"^4 nights · \$"))
    expect(lane.locator(".mx-sq.is-on")).to_have_attribute("data-sq", "losangeles|2026-12-13")
    expect(lane.locator(".mx-band")).to_have_attribute("style", re.compile(r"grid-column: 7 / span 5"))
    expect(lane.locator(".mx-l-best")).to_have_text("$2,400")
    expect(page.locator("#mx-side .mx-p-h")).to_have_text("Los Angeles · Dec 13 to 17")
    assert page.locator("#mx-side").bounding_box()["y"] + page.locator("#mx-side").bounding_box()["height"] <= 900      # the bar is in view, at the bottom
    assert page.errors == []


def test_while_the_first_squares_load_a_fact_floats_in_and_leaves_once_they_land(matrix, slow_server):
    slow_server(r"/plan/matrix/tile", 1.5)
    for viewport in (DESKTOP, PHONE):
        page = matrix(viewport, wait=False, motion=True)
        isle = page.locator("#mx-fact")
        expect(isle).to_be_visible()
        box = isle.bounding_box()
        assert box["height"] < 200 and box["width"] <= 400, box                              # a small note, not a band across the page
        assert page.evaluate("getComputedStyle(document.getElementById('mx-fact')).position") == "sticky"
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")                      # at the very bottom it never sits on the footer's links or switches
        page.wait_for_timeout(100)
        hit = page.evaluate("""() => { const n = document.getElementById('mx-fact').getBoundingClientRect();
            return [...document.querySelectorAll('footer a, footer button, .ga-footer a, .ga-footer button')].filter(e => e.offsetParent).filter(e => {
              const r = e.getBoundingClientRect(); return r.left < n.right && r.right > n.left && r.top < n.bottom && r.bottom > n.top; }).map(e => e.textContent.trim()); }""")
        assert hit == [], (viewport["width"], hit)
        page.evaluate("window.scrollTo(0, 0)")
        assert page.evaluate("() => GA.motion.log.some(m => m.kind === 'settle')")            # it settled in (liquid)
        expect(isle).to_be_hidden(timeout=8000)                                              # the asked square landed: it leaves
        assert page.errors == []


def test_the_script_starts_the_head_start_once_and_asks_three_tiles_at_a_time(matrix, base_url, browser):
    """F-229 review: the head start comes from the script (one POST), never from drawing the page; the gate does the limiting, so 3 tiles at a time."""
    ctx = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
    page = ctx.new_page()
    posts = []
    page.on("request", lambda r: posts.append(r.method) if "/plan/matrix/warm" in r.url else None)
    page.goto(base_url + URL)
    page.wait_for_selector("#mx.is-live")
    page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
    assert posts == ["POST"]
    ctx.close()
    src = Path(__file__).resolve().parent.parent.joinpath("assets/js/tripmatrix.js").read_text()
    assert re.search(r"MAX_AT_ONCE = 3\b", src)


def test_a_busy_square_is_asked_again_and_lands(matrix, stand, monkeypatch):
    once = {"busy": True}
    real = stand.__call__

    def busy_first(lane, w, adults=2, kid_ages=(), home="", family="", peek=False, rank=0, wait=None):
        if not peek and tm.key(lane.key, w.key) == "sandiego|2026-12-12" and once.pop("busy", False):
            return tm.Square(lane.key, w.key, tm.BUSY)
        return real(lane, w, adults, kid_ages, home, family, peek, rank)
    monkeypatch.setattr(gridsource, "SQUARE", busy_first)
    page = matrix(DESKTOP, wait=False)
    sq = page.locator(".mx-lane[data-lane='sandiego'] .mx-sq[data-sq='sandiego|2026-12-12']")
    expect(sq.locator(".mx-in")).to_have_text("$2,140", timeout=15000)
    assert page.errors == []


def test_a_square_that_stays_busy_backs_off_and_then_says_so(matrix, stand, monkeypatch):
    """Review: a busy square is asked again 3 times (3, 6, 12 s apart), never forever; then it settles with words and the page stops waiting on it."""
    real = stand.__call__

    def always_busy(lane, w, adults=2, kid_ages=(), home="", family="", peek=False, rank=0, wait=None):
        if not peek and tm.key(lane.key, w.key) == "sandiego|2026-12-12":
            return tm.Square(lane.key, w.key, tm.BUSY)
        return real(lane, w, adults, kid_ages, home, family, peek, rank)
    monkeypatch.setattr(gridsource, "SQUARE", always_busy)
    page = matrix(DESKTOP, wait=False)
    asks = []
    page.on("request", lambda r: asks.append(r.url) if "/plan/matrix/tile" in r.url and "lane=sandiego&w=2026-12-12" in r.url else None)
    sq = page.locator(".mx-lane[data-lane='sandiego'] .mx-sq[data-sq='sandiego|2026-12-12']")
    expect(sq.locator(".mx-in")).to_have_text("Lots of searches right now. Try again in a minute.", timeout=40000)
    page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
    assert len(asks) <= 3 and page.errors == []      # the first ask happened before the listener; 3 more at most


def test_on_a_phone_the_note_is_just_the_fact_and_its_source(matrix):
    page = matrix(PHONE, wait=False)
    shown = page.evaluate("() => [...document.querySelectorAll('#mx-fact .mx-isle-ic, #mx-fact .mx-fact-k')].map(e => getComputedStyle(e).display === 'none' || getComputedStyle(e.parentNode).display === 'none')")
    assert shown and all(shown)


def test_the_weather_notes_under_the_cards_are_lines_of_their_own(matrix):
    page = matrix(PHONE)
    tops = page.evaluate("() => [...document.querySelectorAll('.mx-cards .mx-wx-n')].map(e => [e.getBoundingClientRect().left, getComputedStyle(e.parentNode).display])")
    assert len(tops) >= 2 and all(d == "flex" for _, d in tops)
