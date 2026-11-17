"""F-287: Today in a real browser. The page at 390 and 1440 in both modes with every control 48px tall, "Use my location" (a stubbed position, only on a tap, nothing sent anywhere), and the
day's page kept by the service worker: once opened, and ahead of time from the planner's card, it shows its codes and address with no signal."""

import re

import pytest

from tests.test_signin import EMAILS, person
from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import DESKTOP, PHONE

DAY = "2026-10-16"
HOTEL_PLACE = "The Tidewater, Los Angeles"        # the sample stay, as Directions and the map's cache know it
OVERFLOW = "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"


@pytest.fixture
def ctxs(browser):
    made = []

    def make(viewport=PHONE, **kw):
        ctx = browser.new_context(viewport=viewport, service_workers="allow", **kw)
        ctx.set_default_timeout(8000)
        made.append(ctx)
        return ctx

    yield make
    for c in made:
        c.set_offline(False)
        c.close()


def sign_in(ctx, base_url, who="ari"):
    ctx.request.post(f"{base_url}/signin", form={"email": EMAILS.get(who, who), "next": "/", "intent": "save"}, max_redirects=0)


def book_sample(ctx, base_url):
    ctx.request.post(f"{base_url}/_test/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)


def book_pasted(ctx, base_url):
    ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)


def know_the_hotel(place, lat, lon):
    """The map's cache has the hotel's coordinates (the background fill puts them there; browser tests refuse the network)."""
    from gitaway import familydb, geo
    with familydb.using(person()) as db:
        geo._put(db, "place", geo._norm(place), lat=lat, lon=lon)


def go_dark(page):
    page.evaluate("localStorage.setItem('ga-mode', 'dark')")
    page.reload()
    assert page.evaluate("document.documentElement.dataset.mode") == "dark"


def small_targets(page):
    """Every link and button a person taps on the page that is under 48px tall."""
    return page.evaluate("""() => [...document.querySelectorAll('#main a.td-btn, #main button.td-btn, #main a.td-link')]
        .map(e => [e.textContent.trim(), Math.round(e.getBoundingClientRect().height)]).filter(([, h]) => h < 48)""")


def light(css):
    """The relative lightness (0..1) of an rgb() colour."""
    r, g, b = (int(x) for x in re.findall(r"\d+", css)[:3])
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "laptop"])
def test_a_travel_day_fits_the_screen_in_both_modes_with_48px_targets(ctxs, base_url, viewport):
    ctx = ctxs(viewport)
    sign_in(ctx, base_url)
    book_pasted(ctx, base_url)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/today?day={DAY}")
    page.wait_for_selector("#td-stay")
    assert page.evaluate(OVERFLOW)
    assert small_targets(page) == []
    assert page.inner_text("#td-addr").split() == ["ADDRESS", "123", "Ocean", "Ave,", "Santa", "Monica,", "CA", "90401"] or page.inner_text("#td-addr").endswith("123 Ocean Ave, Santa Monica, CA 90401")
    assert page.inner_text("#td-flight .td-code") == "ABCDEF"
    light_card = light(page.evaluate("getComputedStyle(document.querySelector('#td-stay')).backgroundColor"))
    go_dark(page)
    page.wait_for_selector("#td-stay")
    assert page.evaluate(OVERFLOW)
    dark_card, dark_ink = (light(page.evaluate(f"getComputedStyle(document.querySelector('#td-stay'){p}).{c}")) for p, c in (("", "backgroundColor"), ("", "color")))
    assert light_card > 0.9 and dark_card < 0.3 and dark_ink > 0.7      # a white card by day, a slate one with light words by night (D-925)


def test_use_my_location_measures_in_the_page_and_sends_nothing(ctxs, base_url):
    ctx = ctxs(geolocation={"latitude": 34.0, "longitude": -118.4}, permissions=["geolocation"], locale="en-US")
    sign_in(ctx, base_url)
    book_sample(ctx, base_url)
    know_the_hotel(HOTEL_PLACE, 34.0, -118.5)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/today?day={DAY}")
    page.wait_for_selector("#td-locate")
    assert page.inner_text("#td-near") == ""           # nothing is asked until the tap
    sent = []
    kept = page.evaluate("JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)])")
    page.on("request", lambda r: sent.append(r.url + (r.post_data or "")))
    page.click("#td-locate")
    page.wait_for_function("!/^(Finding|$)/.test(document.getElementById('td-near').textContent)")
    assert page.inner_text("#td-near") == "5.7 mi away, as the crow flies. Roughly 18 min at city speed, and more by road."
    assert [u for u in sent if "34.0" in u or "118.4" in u or "latitude" in u] == []
    assert page.evaluate("JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)])") == kept      # nothing was stored


def test_a_refused_location_says_so_and_changes_nothing(ctxs, base_url):
    ctx = ctxs()      # no geolocation permission: the browser refuses
    sign_in(ctx, base_url)
    book_sample(ctx, base_url)
    know_the_hotel(HOTEL_PLACE, 34.0, -118.5)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/today?day={DAY}")
    page.click("#td-locate")
    page.wait_for_function("!/^(Finding|$)/.test(document.getElementById('td-near').textContent)")
    assert page.inner_text("#td-near") == "Your location is off for this page, so there is nothing to measure. Nothing was sent."
    assert "Directions" in page.inner_text("#td-stay")      # the rest of the card is as it was


def controlled(page, base_url, path="/guides"):
    page.goto(f"{base_url}{path}")
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.reload()
    page.wait_for_function("navigator.serviceWorker.controller !== null")


def saved(page, path):
    page.wait_for_function("(p) => caches.match(p).then(r => !!r)", arg=path)


def test_the_page_once_opened_shows_its_codes_and_address_with_no_signal(ctxs, base_url):
    ctx = ctxs()
    sign_in(ctx, base_url)
    book_pasted(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url)
    path = f"/trip/today?day={DAY}"
    page.goto(f"{base_url}{path}")
    page.wait_for_selector("#td-stay")
    saved(page, path)
    ctx.set_offline(True)
    page.goto(f"{base_url}{path}")
    text = page.inner_text("#main")
    assert "987654321" in text and "123 Ocean Ave, Santa Monica, CA 90401" in text and "ABCDEF" in text


def test_the_planners_card_has_the_day_kept_before_it_is_ever_opened(ctxs, base_url):
    ctx = ctxs()
    sign_in(ctx, base_url)
    book_pasted(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url)
    page.goto(f"{base_url}/trip/plan?day=2026-10-14")
    page.wait_for_selector("#td-card")
    assert "Your trip starts in 2 days" in page.inner_text("#td-card")
    path = "/trip/today?day=2026-10-14"
    saved(page, path)
    ctx.set_offline(True)
    page.goto(f"{base_url}{path}")
    assert "Flight check-in opens" in page.inner_text("#main") and "987654321" in page.inner_text("#main")
