"""F-222, F-250 in a real browser: the trip matrix (v2: one grid at every width, a place a row, a start day a column) at laptop (1440, the opened square under it) and phone (390, a sheet). A stand-in source answers every
square from a fixed table (gridsource.SQUARE), so the find and the marks are known; by default it answers nothing to a peek, so every square loads like a map tile.
Set F222_SHOTS=1 for docs/design/trip-matrix/built/*.png."""
import os
import re
import threading
from datetime import date, timedelta
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import gridsource, tripmatrix as tm
from tests_browser.helpers import DESKTOP, PHONE, open_rail
from tests_browser.look import audit

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "design" / "trip-matrix" / "built"
URL = "/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16&a=2&k=7,10&x=2&b=2300"
# dollars by lane, Dec 10 to 14: LA + San Diego is $50 less than San Diego on the 12th, the find (D-860: a dearer square is never a find)
TABLE = {"sandiego": (2310, 2260, 2140, 2080, 2390), "losangeles": (2480, 2410, 2350, 2400, 2550), "orangecounty": (2420, 2380, 2290, 2240, 2610),
         "losangeles+sandiego": (2400, 2330, 2090, 2160, 2470), "orangecounty+sandiego": (2500, 2450, 2380, None, 2600)}
STARTS = ("2026-12-10", "2026-12-11", "2026-12-12", "2026-12-13", "2026-12-14")
FLIGHT, FLIGHT_NIGHT = 60_000, 2_000      # the stand's flight: $600 at 4 nights and $20 more for each night more (F-237: a longer trip is not a pure multiple, so an estimate is not the answer)


class Stand:
    """A source with a fixed table. `peek_all`: the page's server knows every square (no script needed); else it knows none. Records what was asked for."""

    def __init__(self):
        self.peek_all, self.asked, self.asked_nights, self.lock = False, [], [], threading.Lock()

    def __call__(self, lane, w, adults=2, kid_ages=(), home="", family="", peek=False, rank=0, wait=None):
        if peek and not self.peek_all:
            return None
        if not peek:
            with self.lock:
                self.asked.append(tm.key(lane.key, w.key))
                self.asked_nights.append(w.nights)
        dollars = TABLE[lane.key][STARTS.index(w.key)]
        if dollars is None:
            return tm.Square(lane.key, w.key, tm.NONE)
        flight = tm.FlightPart("Test Air", "Sat, Dec 12 · SFO 8:05 AM → SAN 9:32 AM · Nonstop", "Wed, Dec 16 · SAN 6:40 PM → SFO 8:10 PM · Nonstop", 0, FLIGHT + FLIGHT_NIGHT * (w.nights - 4))
        nights = [(b - a).days for _, a, b in tm.stays_for(lane, w)]
        stays = tuple(tm.StayPart(p.name, n, f"Test Stay {p.name}", "Two queens", "breakfast", True, 16_000 if i == 0 else 0, "", "9.1 of 10",
                                  round((dollars * 100 - FLIGHT) / 4 * n)) for i, (p, n) in enumerate(zip(lane.places, nights)))      # the stay is a rate for a night: 4 nights make the table's dollars
        return tm.Square(lane.key, w.key, tm.OK, flight, stays, 25, None, False)


@pytest.fixture
def stand(monkeypatch):
    s = Stand()
    monkeypatch.setattr(gridsource, "SQUARE", s)
    return s


@pytest.fixture
def matrix(browser, base_url, stand):
    contexts = []

    def matrix(viewport=DESKTOP, js=True, scheme="light", motion=False, url=URL, wait=True, signed_in=False, touch=False):
        phone = viewport is PHONE or viewport["width"] < 600
        ctx = browser.new_context(viewport=viewport, reduced_motion="no-preference" if motion else "reduce", java_script_enabled=js, color_scheme=scheme,
                                  has_touch=phone or touch, is_mobile=phone)
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


def land_everything(page):
    """Scroll down the page and along the grid in steps (a jump skips squares) until every square has its answer, then back to the top left, so an audit measures squares at rest."""
    for y in range(0, 1500, 300):
        for x in (0, 9999, 0):
            page.evaluate(f"window.scrollTo(0, {y}); document.getElementById('mx-scroll').scrollLeft = {x}")
            page.wait_for_timeout(150)      # the observer reports on its next frame
            page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
    page.evaluate("window.scrollTo(0, 0); document.getElementById('mx-scroll').scrollLeft = 0")


def drawn(page):
    """{key: (marks, words)} of the squares on screen (the laptop's lanes or the phone's cards)."""
    got = page.evaluate("""() => [...document.querySelectorAll('.mx-sq[data-sq]')].filter(e => e.offsetParent).map(e =>
        [e.dataset.sq, ['find', 'low', 'over'].filter(m => e.classList.contains('is-' + m)), e.querySelector('.mx-in').textContent.trim()])""")
    return {k: (tuple(m), w) for k, m, w in got}


def totals(nights=4):
    """The stand's totals in cents for trips of `nights`: what its squares add up to."""
    out = {}
    for lane, row in TABLE.items():
        split = [nights] if "+" not in lane else [nights // 2, nights - nights // 2]
        for w, d in zip(STARTS, row):
            if d is not None:
                rate = (d * 100 - FLIGHT) / 4
                out[tm.key(lane, w)] = FLIGHT + FLIGHT_NIGHT * (nights - 4) + sum(round(rate * n) for n in split)
    return out


def test_the_script_marks_the_squares_by_the_same_rules_as_gitaway_tripmatrix(matrix, stand):
    live = drawn(matrix())                                   # every square answered by a tile, marked by assets/js/tripmatrix.js
    assert len(live) == 25
    assert {k: v[0] for k, v in live.items()} == {k: marks_at(4).get(k, ()) for k in live}      # gitaway/tripmatrix.py `marks` (change one, change the other)
    from gitaway.partners import places
    found = tm.find(tm.lanes(places.resolve("San Diego")), tm.windows(date(2026, 12, 12), date(2026, 12, 16), 2, date(2026, 9, 30)), totals())
    assert live[found.key][0] == ("find", "low") and live["sandiego|2026-12-13"][0] == ("low",) and "over" in live["sandiego|2026-12-10"][0]
    assert live["orangecounty+sandiego|2026-12-13"] == ((), "None found")



def test_the_pick_bar_says_the_find_with_real_totals(matrix):
    page = matrix()
    expect(page.locator("#mx-find .mx-pk-h")).to_have_text("Los Angeles + San Diego, Dec 12 to 16")
    expect(page.locator("#mx-find .mx-pk-s")).to_have_text("$50 less than San Diego alone")
    expect(page.locator("#mx-find .mx-pk-p")).to_have_text("$2,090")
    expect(page.locator("#mx-find .mx-pk-badge")).to_have_text("Our pick")
    assert page.locator("#mx-find .mx-pk-art svg").count() >= 1                      # the place's own drawing
    page.click("#mx-find")
    expect(page.locator("#mx-drawer .dr-h")).to_have_text("Los Angeles + San Diego")
    expect(page.locator("#mx-drawer .dr-ti > p")).to_have_text("Sat, Dec 12 → Wed, Dec 16 · 4 nights · 2 adults, 2 kids")
    expect(page.locator("#mx-drawer [data-slot='total']")).to_have_text("$2,090")
    expect(page.locator("#mx-drawer [data-vs]")).to_contain_text("$50 less than San Diego alone")
    expect(page.locator("#mx-drawer [data-pickword]")).to_be_visible()                  # the find says "Our pick:" in its drawer
    expect(page.locator("#mx-drawer")).to_contain_text("$160 of it paid at the hotel")



def test_only_squares_in_view_are_asked_for_and_the_rest_wait_as_skeletons(matrix, stand):
    """F-250: the grid scrolls sideways on a phone; the start days off to the right are not asked for until they are scrolled near."""
    page = matrix(PHONE, wait=False)
    page.wait_for_function("() => document.querySelectorAll('.mx-lane[data-lane=\"sandiego\"] .mx-sq.is-ok').length >= 3")
    page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
    asked = set(stand.asked)
    assert {"sandiego|2026-12-10", "sandiego|2026-12-11"} <= asked
    assert not any(k.endswith("2026-12-14") for k in asked), asked                           # the last column is off the screen to the right: not asked for
    last = page.locator(".mx-lane[data-lane='sandiego'] .mx-sq").last
    assert "is-wait" in last.get_attribute("class")
    page.evaluate("document.getElementById('mx-scroll').scrollLeft = 9999")
    expect(last).not_to_have_class(re.compile("is-wait"))
    assert any(k.endswith("2026-12-14") for k in stand.asked)

def test_a_waiting_square_is_a_skeleton_never_a_number_and_the_fact_or_the_wait_is_said(matrix, slow_server):
    slow_server(r"/plan/matrix/tile", 5)
    page = matrix(DESKTOP, wait=False, motion=True)
    waits = page.locator(".mx-lane .mx-sq.is-wait")
    expect(waits.first).to_be_visible()
    for text, label in page.eval_on_selector_all(".mx-lane .mx-sq.is-wait", "els => els.map(e => [e.innerText, e.getAttribute('aria-label')])"):
        assert not re.search(r"\d", text) and label.endswith("searching")
    shimmer = page.eval_on_selector(".mx-lane .mx-sq.is-wait", "e => getComputedStyle(e, '::after').animationName")
    assert shimmer == "mx-shimmer"
    expect(page.locator(".mx-slow")).to_be_visible(timeout=8000)                            # a search that takes a while says so, never a frozen page
    expect(page.locator("#mx-count")).to_contain_text("Pricing")
    expect(page.locator("#mx-count")).to_contain_text("of 25 trips")


def test_reduced_motion_keeps_the_skeleton_still(matrix, slow_server):
    slow_server(r"/plan/matrix/tile", 3)
    page = matrix(DESKTOP, wait=False)
    assert page.eval_on_selector(".mx-lane .mx-sq.is-wait", "e => getComputedStyle(e, '::after').animationName") == "none"


def test_on_a_phone_a_square_opens_the_drawer_under_the_matrix_and_it_closes(matrix):
    page = matrix(PHONE, motion=True)
    expect(page.locator("#mx-drawer")).to_be_hidden()
    expect(page.locator(".mx-lane")).to_have_count(5)
    sq = page.locator(".mx-lane[data-lane='losangeles'] .mx-sq").nth(2)
    box = sq.bounding_box()
    assert box["height"] >= 47.5 and box["width"] >= 47.5
    sq.click()
    drawer = page.locator("#mx-drawer .dr")
    expect(drawer).to_be_visible()
    expect(drawer.locator(".dr-h")).to_have_text("Los Angeles")
    expect(drawer).to_contain_text("Sandbox booking: nothing is charged.")
    expect(drawer.locator(".dr-save")).to_be_visible()
    assert page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")      # no sideways scroll
    page.click("#mx-drawer [data-act='close']")
    expect(page.locator("#mx-drawer")).to_be_hidden()
    assert page.errors == []


def test_the_laptop_is_liquid_here_the_one_named_exception(matrix):
    page = matrix(DESKTOP, motion=True)
    assert page.evaluate("document.documentElement.hasAttribute('data-liquid') && GA.motion.calm() === false")
    page.click(".mx-lane[data-lane='sandiego'] .mx-sq >> nth=3")
    expect(page.locator("#mx-drawer .dr-h")).to_have_text("San Diego")
    expect(page.locator(".mx-lane[data-lane='sandiego'] .mx-band")).to_have_attribute("style", re.compile(r"grid-column: 5 / span 2"))
    page.goto(page.url.split("/plan/")[0] + "/plan")
    assert page.evaluate("!document.documentElement.hasAttribute('data-liquid')")             # everywhere else the laptop stays calm


def test_save_to_trip_keeps_you_on_the_matrix(matrix):
    page = matrix(DESKTOP, signed_in=True)
    page.click(".mx-lane[data-lane='losangeles+sandiego'] .mx-sq >> nth=2")
    page.click("#mx-drawer .dr-save")
    expect(page.locator("#mx-drawer .mx-saved")).to_contain_text("Saved to your trip")
    link = page.locator("#mx-drawer .mx-saved a")
    expect(link).to_have_text("Open the trip")      # F-269: this stub square is a non-sample one in sandbox mode, so unchanged (the stand-in and soon say "Plan this trip": tests/test_live_prices.py)
    assert link.get_attribute("href") == "/trip/plan" and "/plan/matrix" in page.url


def test_without_the_script_every_square_is_a_link_to_its_own_page(matrix, stand):
    page = matrix(js=False)
    page.click(".mx-lane[data-lane='losangeles'] .mx-sq >> nth=0")
    expect(page.locator(".dr-h")).to_have_text("Los Angeles")
    expect(page.locator(".dr-ti > p")).to_contain_text("Thu, Dec 10 → Mon, Dec 14")
    expect(page.locator(".mx-back")).to_be_visible()



@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_it_reads_fits_and_is_easy_to_tap_in_light_and_dark(matrix, viewport, scheme):
    page = matrix(viewport, scheme=scheme)
    land_everything(page)
    assert not page.evaluate("[...document.querySelectorAll('.mx-sq.is-wait')].length")
    page.evaluate("window.scrollTo(0, 0)")
    if viewport is DESKTOP:
        page.click("#mx-find")
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
            page.locator(".mx-lane[data-lane='losangeles+sandiego'] .mx-sq").nth(2).click()
            page.wait_for_timeout(300)
            page.screenshot(path=str(SHOTS / f"matrix-sheet-390-{scheme}.png"))


def test_the_drawer_fits_the_phone(matrix):
    page = matrix(PHONE)
    page.locator(".mx-lane[data-lane='losangeles+sandiego'] .mx-sq").nth(2).click()
    expect(page.locator("#mx-drawer .dr-save")).to_be_visible()
    wide = page.evaluate("() => { const s = document.querySelector('#mx-drawer .dr'); return [s.scrollWidth, s.clientWidth, Math.max(...[...s.querySelectorAll('.dr-d, .dr-pp, .dr-tm')].map(e => e.getBoundingClientRect().right))]; }")
    assert wide[0] <= wide[1] + 1 and wide[2] <= 390, wide


def test_the_rail_starts_on_the_finds_place_once_it_is_known_and_follows_the_place_you_tap(matrix):
    page = matrix(DESKTOP)
    expect(page.locator("#mx-rail .rl-h")).to_have_text("Around Los Angeles")           # the find is Los Angeles + San Diego: its first place
    page.click(".mx-lane[data-lane='sandiego'] .mx-lead")
    expect(page.locator("#mx-rail .rl-h")).to_have_text("Around San Diego")
    page.click(".mx-lane[data-lane='orangecounty'] .mx-sq >> nth=1")
    expect(page.locator("#mx-rail .rl-h")).to_have_text("Around Orange County")
    expect(page.locator("#mx-rail [data-w]").first).to_have_attribute("data-w", "2026-12-11")      # the start day opened
    assert page.errors == []


def test_a_square_says_its_start_days_weather_above_its_total_which_is_large(matrix):
    """F-250 (the prototype): the sky of the start day one line above the total; the total is the big number, at least 18px on a phone and 20px on a laptop."""
    for viewport, floor in ((PHONE, 18), (DESKTOP, 20)):
        page = matrix(viewport)
        got = page.evaluate("""() => [...document.querySelectorAll('.mx-sq.is-ok')].filter(e => e.querySelector('.mx-sqw')).map(e => {
            const v = e.querySelector('.mx-v').getBoundingClientRect(), w = e.querySelector('.mx-sqw').getBoundingClientRect();
            return [parseFloat(getComputedStyle(e.querySelector('.mx-v')).fontSize), parseFloat(getComputedStyle(e.querySelector('.mx-sqw')).fontSize), w.bottom <= v.top + 1,
                    w.right <= e.getBoundingClientRect().right + 1 && w.left >= e.getBoundingClientRect().left - 1];
        })""")
        assert got
        for big, small, above, fits in got:
            assert big >= small and above and fits and big >= floor, (viewport["width"], big, small, above, fits)



def test_the_laptop_grid_has_big_totals_one_ringed_band_a_lane_and_the_asked_start_in_the_head(matrix):
    """F-250 (docs/design/booking-v2): a lane's nights are a ringed band over its start columns (it never passes the grid's edge), the totals are the big numbers, the asked day's head wears
    its dot, the find is the one lit square (the flight indigo) and the nights shown a quiet tint of it."""
    page = matrix(DESKTOP)
    expect(page.locator(".mx-day.is-ask")).to_have_text(re.compile(r"Sat\s*12", re.I))
    sizes = page.evaluate("""() => { const q = s => parseFloat(getComputedStyle(document.querySelector(s)).fontSize);
        return [q('.mx-lane .mx-sq .mx-v'), q('.mx-lane .mx-sqw'), q('.mx-l-best')]; }""")
    assert sizes[0] >= 20 and sizes[0] > sizes[1], sizes
    fit = page.evaluate("""() => { const grid = document.querySelector('.mx-lanes').getBoundingClientRect();
        return [...document.querySelectorAll('.mx-band')].map(b => { const r = b.getBoundingClientRect(), lane = b.closest('.mx-lane');
          const under = [...lane.querySelectorAll('.mx-sq')].filter(q => { const x = q.getBoundingClientRect(); return x.left >= r.left - 1 && x.right <= r.right + 1; });
          return [r.left >= grid.left - 1 && r.right <= grid.right + 1, under.length]; }); }""")
    assert len(fit) == 5 and all(ok and n >= 2 for ok, n in fit), fit
    on = page.evaluate("() => [...document.querySelectorAll('.mx-lane .mx-sq.is-on')].map(e => e.dataset.sq)")
    assert on == ["sandiego|2026-12-13", "losangeles|2026-12-12", "orangecounty|2026-12-13", "losangeles+sandiego|2026-12-12", "orangecounty+sandiego|2026-12-12"]
    assert page.eval_on_selector(".mx-lane.is-lit .mx-band", "e => e.dataset.l") == "4 nights · $2,090"      # the band says its nights and total, never "Found"
    colours = page.evaluate("""() => { const c = e => getComputedStyle(e).backgroundColor, f = document.querySelector('.mx-lane .mx-sq.is-find');
        return [c(f)]; }""")
    assert colours[0] == "rgb(67, 56, 202)", colours      # the find is the one lit square (the flight indigo)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")



def test_one_square_is_lit_at_a_time(matrix):
    """F-245 (D-591), review: on load the find is the only solid indigo square; open another and that one is lit while the find steps back to the tint and ring."""
    page = matrix(DESKTOP)
    lit = "() => [...document.querySelectorAll('.mx-lane .mx-sq')].filter(e => getComputedStyle(e).backgroundColor === 'rgb(67, 56, 202)').map(e => e.dataset.sq)"
    find = page.eval_on_selector(".mx-lane .mx-sq.is-find", "e => e.dataset.sq")
    assert page.evaluate(lit) == [find]
    other = page.locator(".mx-lane[data-lane='sandiego'] .mx-sq:not(.is-find)").first
    key = other.get_attribute("data-sq")
    other.click()
    page.wait_for_function("k => document.querySelector(`.mx-sq[data-sq='${k}']`).classList.contains('is-open')", arg=key)
    page.wait_for_timeout(400)      # the background's own transition
    assert page.evaluate(lit) == [key]
    assert page.eval_on_selector(".mx-lane .mx-sq.is-find", "e => getComputedStyle(e).backgroundColor") == "rgb(36, 33, 90)" or page.eval_on_selector(".mx-lane .mx-sq.is-find", "e => getComputedStyle(e).backgroundColor") == "rgb(228, 227, 251)"

def test_a_start_price_tap_moves_the_band_its_label_and_the_ink_pill_and_opens_the_bar(matrix):
    page = matrix(DESKTOP)
    page.click(".mx-lane[data-lane='losangeles'] .mx-sq >> nth=3")
    lane = page.locator(".mx-lane[data-lane='losangeles']")
    expect(lane.locator(".mx-band")).to_have_attribute("data-l", re.compile(r"^4 nights · \$"))
    expect(lane.locator(".mx-sq.is-on")).to_have_attribute("data-sq", "losangeles|2026-12-13")
    expect(lane.locator(".mx-band")).to_have_attribute("style", re.compile(r"grid-column: 5 / span 2"))
    expect(lane.locator(".mx-l-best")).to_have_text("from $2,350")
    expect(page.locator("#mx-drawer .dr-h")).to_have_text("Los Angeles")
    expect(page.locator("#mx-drawer .dr-ti > p")).to_contain_text("Sun, Dec 13 → Thu, Dec 17")
    page.wait_for_timeout(400)
    assert page.eval_on_selector("#mx-drawer .dr-n", "e => parseFloat(getComputedStyle(e).fontSize)") >= 36      # the drawer's total is the biggest number on the page
    box = page.locator("#mx-drawer").bounding_box()
    assert box["y"] < 900 and page.locator("#mx-drawer .dr-book").is_visible()      # the drawer is under the matrix and a tap brings it into view, Book my trip with it
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


def test_the_script_starts_the_head_start_once_and_asks_every_tile_in_view_at_once(matrix, base_url, browser):
    """F-229 review: the head start comes from the script (one POST), never from drawing the page; the gate does the limiting, so every tile in view at once."""
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
    assert re.search(r"MAX_AT_ONCE = 32\b", src)


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


def test_the_weather_notes_are_lines_of_their_own_inside_about_these_prices(matrix):
    """F-238 (D-540): the notes left the foot of the page and the cards; one tap on the ⓘ shows them, one to a line."""
    page = matrix(PHONE)
    assert page.locator(".mx-about .mx-wx-n").first.is_hidden()                                 # closed: nothing at the bottom of the page
    page.click(".mx-about-btn")
    tops = page.evaluate("() => [...document.querySelectorAll('.mx-about .mx-wx-n')].map(e => [e.getBoundingClientRect().top, getComputedStyle(e.parentNode).display])")
    assert len(tops) >= 2 and all(d == "flex" for _, d in tops) and len({t for t, _ in tops}) == len(tops)


# ---- F-237: change the nights right on the matrix ------------------------------------------------------------------------

TABLET = {"width": 1100, "height": 800}      # a laptop's narrow end, and a tablet on its side (F-236 review)
NIGHTS_URL = URL.replace("r=2026-12-16", "r=2026-12-18")
WAIT_IDLE = "() => document.getElementById('mx').dataset.busy === '0'"


def open_nights(page):
    """Tap the sentence's "4 nights" word: its picker holds the slider (F-238, F-250)."""
    if not page.locator("#v2-pop input[data-nights]").is_visible():
        page.click("#v2-sent .v2-w[data-k='nights']")
        expect(page.locator("#v2-pop input[data-nights]")).to_be_visible()


def slide(page, n, release=True):
    """Move the nights slider (in the word's popover) to `n`: the `input` event is the drag, the `change` event is letting go."""
    open_nights(page)
    page.evaluate("""([n, release]) => { const r = [...document.querySelectorAll('input[data-nights]')].find(e => e.offsetParent); r.value = n;
        r.dispatchEvent(new Event('input', {bubbles: true})); if (release) r.dispatchEvent(new Event('change', {bubbles: true})); }""", [n, release])


def let_go(page):
    page.evaluate("() => { const r = [...document.querySelectorAll('input[data-nights]')].find(e => e.offsetParent); r.dispatchEvent(new Event('change', {bubbles: true})); }")


def marks_at(nights):
    from gitaway.partners import places
    lanes = tm.lanes(places.resolve("San Diego"))
    windows = tm.windows(date(2026, 12, 12), date(2026, 12, 12) + timedelta(days=nights), 2, date(2026, 9, 30))
    return {k: tuple(m) for k, m in tm.marks(lanes, windows, totals(nights), 230_000).items()}


def test_sliding_shows_every_square_as_an_estimate_at_once_marks_none_and_searches_nothing(matrix, stand):
    page = matrix(DESKTOP)
    page.click(".mx-lane[data-lane='sandiego'] .mx-sq >> nth=3")                       # open Dec 13: the bar is its real answer for four nights
    expect(page.locator("#mx-drawer [data-slot='total']")).to_have_text("$2,080")
    stand.asked.clear()
    slide(page, 6, release=False)
    sq = page.locator(".mx-lane[data-lane='sandiego'] .mx-sq[data-sq='sandiego|2026-12-12']")
    expect(sq.locator(".mx-in")).to_have_text("about $2,910")                         # $600 flight + $385 a night for six nights, from what was read at four
    expect(page.locator(".mx-lane[data-lane='losangeles+sandiego'] .mx-sq[data-sq='losangeles+sandiego|2026-12-12'] .mx-in")).to_have_text("about $2,835")      # two places: 3 nights each at their rates
    assert stand.asked == []                                                          # no search per step
    shown = page.evaluate("""() => [...document.querySelectorAll('.mx-lane .mx-sq')].map(e => [e.classList.contains('is-est'), e.getAttribute('aria-label'), ['is-find', 'is-low', 'is-over'].some(c => e.classList.contains(c))])""")
    assert len(shown) == 25 and all(est and label.endswith("an estimate") and not marked for est, label, marked in shown)      # an estimate is said as one and never marked
    expect(page.locator("#mx-find")).to_have_class(re.compile("is-empty"))
    expect(page.locator("#mx-est")).to_be_visible()
    expect(page.locator("#mx-est")).to_contain_text("estimates")
    expect(page.locator("#v2-sent .v2-w[data-k='nights']")).to_have_text("6 nights")
    expect(page.locator("#mx-count")).to_contain_text("6 nights")
    band = page.locator(".mx-lane[data-lane='sandiego'] .mx-band")
    expect(band).to_have_attribute("style", re.compile(r"grid-column: 5 / span 2"))
    expect(band).to_have_attribute("data-l", "6 nights · about $2,820")
    note = page.locator("#mx-drawer .dr-note")
    expect(note).to_have_text("Let go for the exact price of 6 nights.")               # the opened square never shows a guess as its price
    assert page.locator("#mx-drawer .dr-save, #mx-drawer .dr-book, #mx-drawer [data-slot='total']").count() == 0
    assert page.errors == []


def test_letting_go_makes_every_square_its_real_answer_marked_by_the_same_rules_as_the_server(matrix, stand):
    page = matrix(DESKTOP)
    slide(page, 6)
    page.wait_for_function(WAIT_IDLE)
    live = drawn(page)
    assert len(live) == 25
    want = marks_at(6)                                                                # gitaway/tripmatrix.py's marks
    assert {k: v[0] for k, v in live.items()} == {k: want.get(k, ()) for k in live}
    assert want != marks_at(4)                                                        # the nights moved the marks, so this is not the same check twice
    assert live["sandiego|2026-12-12"][1] == tm.dollars(totals(6)["sandiego|2026-12-12"]) == "$2,950"
    assert all(n == 6 for n in stand.asked_nights[25:])                               # everything searched after the slider moved was for six nights
    expect(page.locator("#mx-est")).to_be_hidden()


def test_the_address_keeps_the_nights_so_a_reload_or_a_shared_link_does(matrix, stand):
    page = matrix(DESKTOP)
    slide(page, 6)
    page.wait_for_function(WAIT_IDLE)
    assert "r=2026-12-18" in page.url and "d=2026-12-12" in page.url
    hrefs = page.eval_on_selector_all("a[href^='/plan/matrix']", "els => els.map(e => e.getAttribute('href'))")
    assert hrefs and all("r=2026-12-18" in h for h in hrefs if "d=2026" in h), hrefs      # the squares' and the find's links carry them too
    page.reload()
    page.wait_for_selector("#mx.is-live")
    expect(page.locator("#v2-sent .v2-w[data-k='nights']")).to_have_text("6 nights")
    page.wait_for_function(WAIT_IDLE)
    assert drawn(page)["sandiego|2026-12-12"][1] == "$2,950"


def test_going_back_to_nights_already_read_is_instant_and_asks_for_nothing(matrix, stand):
    page = matrix(DESKTOP)
    slide(page, 6)
    page.wait_for_function(WAIT_IDLE)
    stand.asked.clear()
    words = page.evaluate("""() => { const r = [...document.querySelectorAll('input[data-nights]')].find(e => e.offsetParent); r.value = 4;
        r.dispatchEvent(new Event('input', {bubbles: true}));      // in the same breath: no wait, no fetch
        return [...document.querySelectorAll('.mx-lane .mx-sq')].map(e => [e.dataset.sq, e.querySelector('.mx-in').textContent.trim()]); }""")
    want = {k: tm.dollars(c) for k, c in totals(4).items()}
    assert len(words) == 25 and all(w == want.get(k, "None found") for k, w in words), words
    let_go(page)
    page.wait_for_function(WAIT_IDLE)
    assert stand.asked == [] and "r=2026-12-16" in page.url


def test_letting_go_searches_only_the_squares_in_view_and_scrolling_asks_for_the_rest_for_those_nights(matrix, stand):
    page = matrix({"width": 320, "height": 1100})      # F-275: as tall as the sentence card and the chips need for the grid to be in view, as it was at 640 before. (at 390 the last column starts 90px past the edge, inside the 120px margin the page reads ahead by on purpose (MARGIN in tripmatrix.js), so it IS "in view"; at 320 it is not)
    page.evaluate("document.getElementById('mx-scroll').scrollLeft = 9999")
    page.wait_for_function(WAIT_IDLE)
    page.evaluate("document.getElementById('mx-scroll').scrollLeft = 0")
    page.wait_for_function(WAIT_IDLE)
    assert page.evaluate("() => document.querySelector(\".mx-sq[data-sq='sandiego|2026-12-14']\").getBoundingClientRect().left > innerWidth + 120")      # the far column is beyond the margin
    before = len(stand.asked)
    page.focus("#v2-sent .v2-w[data-k='nights']")      # by keyboard: at 320 the next word wraps over it for a mouse
    page.keyboard.press("Enter")
    slide(page, 6)
    page.wait_for_function(WAIT_IDLE)
    asked = stand.asked[before:]
    assert asked and len(asked) == len(set(asked)) and set(stand.asked_nights[before:]) == {6}      # each once, all for six nights
    assert not any(k.endswith("2026-12-14") for k in asked)                                      # the far column is not in view: not asked for
    page.evaluate("document.getElementById('mx-scroll').scrollLeft = 9999")
    page.wait_for_function(WAIT_IDLE)
    page.wait_for_function("() => document.querySelector(\".mx-sq[data-sq='sandiego|2026-12-14']\").classList.contains('is-ok')")
    assert any(k.endswith("2026-12-14") for k in stand.asked[before:]) and set(stand.asked_nights[before:]) == {6}


def test_on_the_showcase_it_is_instant_the_peek_knows_every_square_and_nothing_is_searched(matrix, stand):
    page = matrix(DESKTOP)
    stand.peek_all = True                                                             # the sample catalog: every square is known without a search
    stand.asked.clear()
    slide(page, 7)
    page.wait_for_function(WAIT_IDLE)
    assert len(stand.asked) <= 1      # nothing is searched; at most the opened square's own bar is asked for (the sample catalog's own answer)
    live = drawn(page)
    assert {k: v[0] for k, v in live.items()} == {k: marks_at(7).get(k, ()) for k in live} and live["sandiego|2026-12-13"][1] == tm.dollars(totals(7)["sandiego|2026-12-13"])


def test_the_opened_squares_bar_save_and_book_are_for_the_exact_nights_never_an_estimate(matrix, stand):
    page = matrix(DESKTOP, signed_in=True)
    page.click(".mx-lane[data-lane='sandiego'] .mx-sq >> nth=3")
    expect(page.locator("#mx-drawer .dr-save")).to_be_visible()
    slide(page, 6, release=False)
    assert page.locator("#mx-drawer .dr-save, #mx-drawer .dr-book").count() == 0
    let_go(page)
    expect(page.locator("#mx-drawer [data-slot='total']")).to_have_text(tm.dollars(totals(6)["sandiego|2026-12-13"]))
    assert page.eval_on_selector_all("#mx-drawer form input[name='r']", "els => els.map(e => e.value)") == ["2026-12-18", "2026-12-18"]      # Book and Save, for six nights
    expect(page.locator("#mx-drawer .dr-ti > p")).to_contain_text("Sun, Dec 13 → Sat, Dec 19")
    expect(page.locator(".mx-lane[data-lane='sandiego'] .mx-band")).to_have_attribute("data-l", re.compile(r"^6 nights · \$"))


def test_nights_is_a_word_on_the_phone_and_the_laptop_that_opens_a_picker_with_the_only_slider(matrix, stand):
    """F-238 (D-542), F-250: no slider inline anywhere; the word opens one picker (a sheet on a phone, a popover on a laptop), and the word says the nights at once."""
    for viewport in (PHONE, DESKTOP):
        page = matrix(viewport)
        assert page.locator("input[data-nights]").count() == 0 and page.locator("#v2-pop").is_hidden()      # closed: the sentence is only words
        word = page.locator("#v2-sent .v2-w[data-k='nights']")
        page.click("#v2-sent .v2-w[data-k='nights']")
        pop, box = page.locator("#v2-pop"), page.locator("#v2-pop").bounding_box()
        expect(pop).to_be_visible()
        assert page.locator("input[data-nights]").count() == 1
        assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"] + 0.5, box      # never off the screen
        slide(page, 6, release=False)
        expect(word).to_have_text("6 nights")
        assert page.errors == []



def test_the_picker_goes_away_on_a_tap_elsewhere_or_escape_and_one_word_opens_at_a_time(matrix, stand):
    page = matrix(DESKTOP)
    page.click("#v2-sent .v2-w[data-k='nights']")
    expect(page.locator("#v2-pop")).to_be_visible()
    page.click("#v2-sent .v2-w[data-k='flex']")
    expect(page.locator("#v2-pop h4")).to_have_text("How flexible")
    page.keyboard.press("Escape")
    expect(page.locator("#v2-pop")).to_be_hidden()
    page.click(".mx-about-btn")
    expect(page.locator(".mx-pop-about")).to_be_visible()
    page.locator(".mx-lane").last.locator(".mx-sq").first.click()      # a square the open About panel does not cover (F-251's panel is taller)
    expect(page.locator(".mx-pop-about")).to_be_hidden()



def test_the_picker_rises_as_a_sheet_on_a_phone_and_grows_under_its_word_on_a_laptop(matrix, stand):
    page = matrix(PHONE, motion=True)
    page.click("#v2-sent .v2-w[data-k='nights']")
    assert page.locator("#v2-pop.as-sheet").count() == 1 and page.evaluate("document.getAnimations().length") >= 0
    box = page.locator("#v2-pop").bounding_box()
    assert box["y"] + box["height"] >= 844 - 20
    desk = matrix(DESKTOP, motion=True)
    word = desk.locator("#v2-sent .v2-w[data-k='nights']")
    word.click()
    pop, at = desk.locator("#v2-pop").bounding_box(), word.bounding_box()
    assert desk.locator("#v2-pop.as-sheet").count() == 0 and pop["y"] >= at["y"] + at["height"] - 2 and pop["x"] <= at["x"] + at["width"] / 2 <= pop["x"] + pop["width"] and pop["x"] >= 0      # under its word (a word at the line's start leaves the popover at the page's edge)



def test_about_these_prices_holds_the_legend_the_credit_the_fine_print_privacy_and_terms_and_the_page_has_no_footer(matrix, stand):
    """F-238 (D-540): nothing is drawn under the matrix; one quiet ⓘ opens it all on tap."""
    for viewport in (PHONE, DESKTOP):
        page = matrix(viewport)
        assert page.locator("footer, .ga-footer").count() == 0
        assert page.locator(".mx-foot, .mx-key").count() == 0
        expect(page.locator(".mx-pop-about")).to_be_hidden()
        page.click(".mx-about-btn")
        panel = page.locator(".mx-pop-about")
        expect(panel).to_contain_text("ringed")
        expect(panel).to_contain_text(re.compile(r"Prices are a preview from LiteAPI|Sample prices from GitAway"))
        expect(panel).to_contain_text("NOAA")
        expect(panel.locator("a[href='/privacy']")).to_be_visible()
        expect(panel.locator("a[href='/terms']")).to_be_visible()
        assert panel.locator("a[href='/terms']").bounding_box()["height"] >= (47.5 if viewport is PHONE else 0)
        box = panel.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"] + 0.5, box
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")
        page.click(".mx-pop-about .ga-mode")                                          # the footer's one light/dark button lives here now (D-460)
        assert page.evaluate("document.documentElement.dataset.mode") == "dark"


def test_a_key_pressed_three_times_asks_once_for_where_it_stopped(matrix, stand):
    page = matrix(DESKTOP)
    before = len(stand.asked)
    open_nights(page)
    page.locator("#v2-pop input[data-nights]").focus()
    for _ in range(3):
        page.keyboard.press("ArrowRight")
    page.wait_for_function(WAIT_IDLE)
    page.wait_for_timeout(400)
    assert set(stand.asked_nights[before:]) == {7} and "r=2026-12-19" in page.url


def test_at_1100_the_band_stays_in_its_row_and_the_trip_bars_chips_stay_inside(matrix):
    """F-236 review: the band's words sit inside the band and the opened trip's tiles, timeline blocks and cost card inside it at the laptop's narrow end."""
    page = matrix(TABLET)
    page.click("#mx-find")
    fit = page.evaluate("""() => [...document.querySelectorAll('.mx-band')].map(b => { const r = b.getBoundingClientRect(), lane = b.closest('.mx-lane').getBoundingClientRect();
        return [getComputedStyle(b, '::after').content === 'none' && r.top >= lane.top - 8 && r.bottom <= lane.bottom + 8, r.width]; })""")      # F-275: the band writes nothing and stays in its own row
    assert len(fit) == 5 and all(ok for ok, _ in fit), fit
    box = page.evaluate("""() => { const d = document.getElementById('mx-drawer'), r = d.getBoundingClientRect(),
        parts = [...d.querySelectorAll('.dr-pn, .dr-foot, .dr-head')].map(e => e.getBoundingClientRect());
        return [parts.length, parts.every(c => c.left >= r.left - 1 && c.right <= r.right + 1), d.scrollWidth <= d.clientWidth + 1, document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1]; }""")
    assert box[0] >= 4 and all(box[1:]), box


def test_the_floating_note_sits_at_the_foot_of_the_screen(matrix, slow_server):
    slow_server(r"/plan/matrix/tile", 3)
    css = (Path(__file__).resolve().parent.parent / "assets" / "css" / "tripmatrix.css").read_text()
    assert "--mx-bar-h" not in css      # the bar it once sat above is gone (F-251): a plain offset from the screen's foot
    for viewport in (DESKTOP, TABLET):
        page = matrix(viewport, wait=False)
        expect(page.locator("#mx-fact")).to_be_visible()
        n, vh = page.evaluate("() => [document.getElementById('mx-fact').getBoundingClientRect().toJSON(), innerHeight]")
        assert n["bottom"] <= vh and n["top"] >= 0, (viewport, n, vh)


def test_a_touch_screen_at_the_laptops_width_gets_48px_start_prices_and_slider(matrix):
    """F-236 review: a tablet on its side is 1020px or wider and had 30px start pills."""
    page = matrix(TABLET, touch=True)
    assert page.evaluate("matchMedia('(pointer: coarse)').matches")
    heights = page.eval_on_selector_all(".mx-lane > .mx-sq", "els => els.map(e => e.getBoundingClientRect().height)")
    assert len(heights) == 25 and min(heights) >= 47.5, min(heights)
    open_nights(page)
    assert page.locator("#v2-pop input[data-nights]").bounding_box()["height"] >= 47.5



@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_estimates_and_the_slider_read_and_fit_in_light_and_dark(matrix, viewport, scheme):
    page = matrix(viewport, scheme=scheme)
    land_everything(page)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_function("() => document.getAnimations().every(a => a.effect.getTiming().iterations === Infinity || a.playState !== 'running')")
    page.wait_for_timeout(700)      # the last arrivals' settle: measure the estimates, not a square mid-fade
    slide(page, 6, release=False)
    page.wait_for_timeout(300)
    seen = audit(page)
    assert seen["wide"] <= 1, seen["wide"]
    for key in ("small", "tiny", "low", "glass"):
        assert not seen[key], (key, seen[key][:40])
    if os.getenv("F237_SHOTS"):
        out = Path(__file__).resolve().parent.parent / "docs" / "report"
        out.mkdir(parents=True, exist_ok=True)
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(out / f"f237-{viewport['width']}-{scheme}-sliding.png"))


def focused(page, selector):
    """The focus is on `selector` (waited for: a details' `toggle` event, where the script moves focus, is queued a task after the click or key)."""
    page.wait_for_function("sel => document.activeElement && document.activeElement.matches(sel)", arg=selector)
    return True


def test_a_word_opened_from_the_keyboard_puts_focus_inside_its_picker_and_escape_gives_it_back(matrix, stand):
    """F-238 review, F-250: Enter on "4 nights" lands on the slider (arrows work at once); Escape puts the picker away and focus returns to the word."""
    page = matrix(DESKTOP)
    page.locator("#v2-sent .v2-w[data-k='nights']").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#v2-pop")).to_be_visible()
    focused(page, "#v2-pop input[data-nights]")
    page.keyboard.press("ArrowRight")
    expect(page.locator("#v2-sent .v2-w[data-k='nights']")).to_have_text("5 nights")
    page.keyboard.press("Escape")
    expect(page.locator("#v2-pop")).to_be_hidden()



WORDS_JS = """() => [...document.querySelectorAll('#mx *')].filter(e => !(e instanceof SVGElement) && e.closest('.mx-sr') === null &&
  [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).map(e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return {t: e.textContent.trim().slice(0, 24), k: (e.closest('.mx-sq, .mx-find, .v2-sent, .mx-top') || e).className, c: s.color, x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height,
          shown: r.width > 2 && r.height > 2 && s.visibility === 'visible' && !e.closest('.mx-pop, .mx-isle, .mx-side, .is-off') }; })"""


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_word_on_the_translucent_card_is_4_5_to_1_on_what_is_really_painted(matrix, viewport, scheme, tmp_path):
    """F-245 (D-590): the card is see-through over a wash, which tests_browser/look.py cannot measure (it skips a gradient under the text), so measure the pixels:
    hide every word, photograph the page, and compare each word's own colour with the median of the pixels where it sits."""
    from io import BytesIO
    from PIL import Image
    page = matrix(viewport)
    page.evaluate(f"localStorage.setItem('ga-mode', '{scheme}')")
    page.reload()
    page.wait_for_selector("#mx.is-live")
    page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
    page.wait_for_timeout(700)
    words = [w for w in page.evaluate(WORDS_JS) if w["shown"]]
    assert len(words) > 30
    page.add_style_tag(content="#mx, #mx * { color: transparent !important; text-decoration-color: transparent !important; text-shadow: none !important; }")
    shot = Image.open(BytesIO(page.screenshot(full_page=True))).convert("RGB")

    def lum(c):
        v = [x / 255 for x in c[:3]]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    low = []
    for w in words:
        box = (int(w["x"]), int(w["y"]), int(w["x"] + w["w"]), int(w["y"] + w["h"]))
        if box[2] > shot.width or box[3] > shot.height:
            continue
        px = sorted(shot.crop(box).getdata(), key=lum)
        bg = px[len(px) // 2]
        m = re.findall(r"[\d.]+", w["c"])
        scale = 255 if w["c"].startswith("color(srgb") else 1      # a color-mix() answers as color(srgb 0.9 0.9 0.95 / a)
        fg = [float(x) * scale for x in m[:3]]
        a = float(m[3]) if len(m) > 3 else 1.0
        fg = [f * a + b * (1 - a) for f, b in zip(fg, bg)]
        hi, lo = max(lum(fg), lum(bg)), min(lum(fg), lum(bg))
        if (hi + 0.05) / (lo + 0.05) < 4.5:
            low.append((w["t"], round((hi + 0.05) / (lo + 0.05), 2), w["k"]))
    assert not low, low


@pytest.mark.parametrize("viewport", [DESKTOP], ids=["1440"])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_word_on_the_frosted_glass_rail_is_4_5_to_1_on_what_is_really_painted(matrix, viewport, scheme):
    """F-251 (D-610, D-622): the widget rail is the frosted glass over the sky (`.v2-glass`, a blur): every word on it is measured on the pixels the blur really paints, in light and dark."""
    from io import BytesIO
    from PIL import Image
    page = matrix(viewport)
    page.evaluate(f"localStorage.setItem('ga-mode', '{scheme}')")
    page.reload()
    page.wait_for_selector("#mx.is-live")
    page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
    expect(page.locator("#mx-rail .wchip").first).to_be_visible()
    open_rail(page)      # F-275: a widget is a chip until it is tapped; open them all, the cards and the chips are the glass
    expect(page.locator("#mx-rail .wg:not([hidden])").first).to_be_visible()
    page.wait_for_timeout(900)
    assert page.evaluate("getComputedStyle(document.querySelector('#mx-rail .wg:not([hidden])')).backdropFilter").startswith("blur")
    words = [w for w in page.evaluate(WORDS_JS.replace("'#mx *'", "'#mx-rail *'").replace("!e.closest('.mx-pop, .mx-isle, .mx-side, .is-off')", "true")) if w["shown"]]
    assert len(words) > 8
    page.add_style_tag(content="#mx-rail * { color: transparent !important; text-decoration-color: transparent !important; }")
    shot = Image.open(BytesIO(page.screenshot(full_page=True))).convert("RGB")

    def lum(c):
        v = [x / 255 for x in c[:3]]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    low = []
    for w in words:
        box = (int(w["x"]), int(w["y"]), int(w["x"] + w["w"]), int(w["y"] + w["h"]))
        if box[2] > shot.width or box[3] > shot.height:
            continue
        px = sorted(shot.crop(box).getdata(), key=lum)
        bg = px[len(px) // 2]
        m = re.findall(r"[\d.]+", w["c"])
        scale = 255 if w["c"].startswith("color(srgb") else 1
        fg = [float(x) * scale for x in m[:3]]
        a = float(m[3]) if len(m) > 3 else 1.0
        fg = [f * a + b * (1 - a) for f, b in zip(fg, bg)]
        hi, lo = max(lum(fg), lum(bg)), min(lum(fg), lum(bg))
        if (hi + 0.05) / (lo + 0.05) < 4.5:
            low.append((w["t"], round((hi + 0.05) / (lo + 0.05), 2), w["k"]))
    assert not low, low


@pytest.mark.parametrize("last", [0, 4], ids=["first-column", "last-column"])
def test_no_band_label_floats_and_the_marks_sit_inside_their_square(matrix, monkeypatch, last):
    """F-275 (D-863): the nights band's label sat on a lane's top or bottom edge and ran across the row beside it, and "Our pick" hung over the square above. The band writes nothing now;
    the marks ("Our pick", "Cheapest") are a line inside their own square."""
    row = list(TABLE["losangeles+sandiego"])
    row[last] = 1900      # the find: a nearby trip well under San Diego on that day
    monkeypatch.setitem(TABLE, "losangeles+sandiego", tuple(row))
    page = matrix(DESKTOP)
    page.wait_for_selector(".mx-sq.is-find")
    got = page.evaluate("""() => { const sq = document.querySelector('.mx-sq.is-find'), tag = getComputedStyle(sq, '::after');
        return {bands: [...document.querySelectorAll('.mx-band')].map(b => getComputedStyle(b, '::after').content), tag: tag.content, pos: tag.position, fits: sq.scrollHeight <= sq.clientHeight + 1}; }""")
    assert set(got["bands"]) == {"none"} and got["tag"] in ('"Our pick"', '"Pick · cheapest"') and got["pos"] == "static" and got["fits"], got
