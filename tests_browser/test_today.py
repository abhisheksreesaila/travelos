"""F-287: Today in a real browser. The page at 390 and 1440 in both modes with every control 48px tall, "Use my location" (a stubbed position, only on a tap, nothing sent anywhere), and the
day's page kept by the service worker: once opened, and ahead of time from the planner's card, it shows its codes and address with no signal."""

import re

import pytest

from tests.test_signin import EMAILS, person
from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import DESKTOP, PHONE, open_more

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
    page.wait_for_selector("#td-more")
    assert page.inner_text("#td-near") == ""           # nothing is asked until the tap
    sent = []
    kept = page.evaluate("JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)])")
    page.on("request", lambda r: sent.append(r.url + (r.post_data or "")))
    open_more(page, "#td-locate", "td-more").click()      # F-293: "Use my location" is a row of the hotel's More menu
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
    open_more(page, "#td-locate", "td-more").click()
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
    assert page.is_hidden("#td-saved")          # online, it is the live page: no notice
    ctx.set_offline(True)
    page.goto(f"{base_url}{path}")
    text = page.inner_text("#main")
    assert "987654321" in text and "123 Ocean Ave, Santa Monica, CA 90401" in text and "ABCDEF" in text
    assert re.fullmatch(r"Saved copy · as of \w{3},? \d{1,2}:\d{2}\s?[AP]M", page.inner_text("#td-saved").strip())      # the copy says it is a copy, and from when


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


def test_a_saved_page_is_not_served_after_the_sign_in_it_was_saved_under_has_run_out(ctxs, base_url):
    ctx = ctxs()
    sign_in(ctx, base_url)
    book_pasted(ctx, base_url)
    page = ctx.new_page()
    controlled(page, base_url)
    path = f"/trip/today?day={DAY}"
    page.goto(f"{base_url}{path}")
    page.wait_for_selector("#td-stay")
    saved(page, path)
    record = page.evaluate("caches.open('ga-who').then(c => c.match('/__who')).then(r => r.text())")
    who, until = record.split("|")
    assert int(until) > 0                       # the page told the worker when the sign-in runs out
    page.evaluate("(w) => caches.open('ga-who').then(c => c.put('/__who', new Response(w + '|1')))", who)      # ... which was long ago
    ctx.set_offline(True)
    try:
        page.goto(f"{base_url}{path}")
    except Exception:
        pass
    text = page.locator("body").inner_text()
    assert "987654321" not in text and "ABCDEF" not in text
    assert page.evaluate("caches.keys().then(k => k.filter(n => n.startsWith('ga-pages-')).length)") == 0      # and the saved pages were let go


UNDER_THE_BAR = """() => { const bar = document.querySelector('.v2-sections'); if (!bar || getComputedStyle(bar).position !== 'fixed') return ['no floating bar'];
    const b = bar.getBoundingClientRect();
    return [...document.querySelectorAll('#main .td-btn, #main .td-link')].filter(e => { const r = e.getBoundingClientRect();
        return r.width > 0 && r.left < b.right && r.right > b.left && r.top < b.bottom && r.bottom > b.top; }).map(e => e.textContent.trim()); }"""


@pytest.mark.parametrize("day", ["2026-10-13", "2026-10-16", "2026-10-18"], ids=["before", "travel", "during"])
def test_on_a_phone_no_control_sits_under_the_floating_bar_at_rest_or_at_the_foot(ctxs, base_url, day):
    ctx = ctxs(PHONE)
    sign_in(ctx, base_url)
    book_pasted(ctx, base_url)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/today?day={day}")
    page.wait_for_selector(".td-wrap")
    assert page.evaluate(UNDER_THE_BAR) == []
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(150)
    assert page.evaluate(UNDER_THE_BAR) == []


def test_on_a_travel_day_phone_the_hotels_key_actions_are_on_the_first_screen_above_the_bar(ctxs, base_url):
    ctx = ctxs(PHONE)
    sign_in(ctx, base_url)
    book_pasted(ctx, base_url)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/today?day={DAY}")
    page.wait_for_selector("#td-directions")
    bar_top = page.evaluate("document.querySelector('.v2-sections').getBoundingClientRect().top")
    for ident in ("td-directions", "td-more"):      # F-293: the ride is a row of the hotel's More menu; the button that holds it is on the first screen
        assert page.evaluate("(i) => document.getElementById(i).getBoundingClientRect().bottom", ident) <= bar_top, ident


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_hotel_card_keeps_directions_and_its_more_menu_holds_the_ride(ctxs, base_url, viewport):
    """F-293 (D-948): at rest the card has Directions (the bold action) and Call the hotel; the ride waits in the round More button's menu, which opens, has 48px rows and gives focus back on Escape."""
    ctx = ctxs(viewport)
    sign_in(ctx, base_url)
    book_pasted(ctx, base_url)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/today?day={DAY}")
    page.wait_for_selector("#td-more")
    assert page.is_hidden("#td-ride") and page.is_visible("#td-directions") and page.is_visible("#td-call")
    box = page.locator("#td-more").bounding_box()
    assert box["width"] >= 47.5 and box["height"] >= 47.5 and page.get_attribute("#td-more", "aria-expanded") == "false"
    assert box["width"] < 60 and "More" in page.locator("#td-more").text_content()      # a round button; its word is for readers
    open_more(page, "#td-ride", "td-more")
    assert page.evaluate("document.getElementById('td-ride').getBoundingClientRect().height") >= 47.5
    assert page.get_attribute("#td-ride", "href").startswith("https://m.uber.com/")
    page.keyboard.press("Escape")
    page.wait_for_selector("#td-more-menu", state="hidden")      # it folds back into its button first
    assert page.evaluate("document.activeElement.id") == "td-more"
    assert page.evaluate(OVERFLOW)
