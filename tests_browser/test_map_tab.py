"""F-068: the Map tab in a real browser at phone width: numbered pins on the map, a tap on a pin opens the bottom sheet, Close and the list rows work,
and nothing scrolls sideways. The map services are faked in the server's process and the tile server is answered by the test: no network."""
import base64
import re

import pytest
from playwright.sync_api import expect

from gitaway import geo
from tests.test_map import Maps
from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT

TILE = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


@pytest.fixture
def map_page(browser, base_url, monkeypatch):
    """map_page(day="0") -> a signed-in phone page on /trip/map with an imported trip, a plan nobody can find and one they can; tiles are stubbed."""
    contexts, requested = [], []
    monkeypatch.setattr(geo, "fetch", Maps())

    def make(day="0", viewport=PHONE):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=viewport is PHONE, is_mobile=viewport is PHONE)
        ctx.set_default_timeout(5000)
        contexts.append(ctx)

        def tile(route):
            requested.append(route.request.url)
            route.fulfill(status=200, content_type="image/png", body=TILE)
        ctx.route(re.compile(r"https://[a-c]?\.?tile\.openstreetmap\.org/.*"), tile)
        ctx.route(re.compile(r"https://(?!127\.0\.0\.1).*"), lambda r: r.abort())  # nothing else leaves the machine
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)
        for id_, start, end, title in (("a1", "17:00", "19:30", "Griffith Observatory"), ("a2", "20:00", "21:00", "Mystery Cafe")):
            ctx.request.post(f"{base_url}/calendar/activities", form={"id": id_, "day": "0", "start": start, "end": end, "title": title, "kind": "culture"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/map?day={day}")
        page.wait_for_selector("#mp-map[data-ready]")
        return page

    yield make
    for c in contexts:
        c.close()


def test_pins_are_numbered_and_a_tap_opens_the_sheet(map_page):
    page = map_page()
    pins = page.locator(".mp-pin-wrap[data-stop]")
    assert pins.count() == 4  # the flight, the car desk, the hotel and Griffith; the cafe could not be found
    expect(page.locator("#mp-sheet")).to_be_hidden()
    page.locator('.mp-pin-wrap[data-stop="4"]').click()
    sheet = page.locator("#mp-sheet")
    expect(sheet).to_be_visible()
    expect(page.locator("#mp-s-name")).to_have_text("Griffith Observatory")
    expect(page.locator("#mp-s-n")).to_have_text("4")
    expect(page.locator("#mp-s-when")).to_have_text("5:00 – 7:30 PM")
    expect(page.locator("#mp-s-drive")).to_contain_text("25 min from Check in")
    assert "Griffith" in page.locator("#mp-s-dir").get_attribute("href")
    assert page.locator("#mp-s-uber").get_attribute("href").startswith("https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff[formatted_address]=")
    expect(page.locator("#mp-s-tel")).to_be_hidden()  # no phone known for a sight
    assert page.evaluate(OVERFLOW) == 0
    box = page.locator("#mp-s-dir").bounding_box()
    assert box["height"] >= 43.5


def test_the_hotel_stop_has_a_call_button_and_close_hides_the_sheet(map_page):
    page = map_page()
    page.locator('.mp-pin-wrap[data-stop="3"]').click()
    tel = page.locator("#mp-s-tel")
    expect(tel).to_be_visible()
    assert tel.get_attribute("href") == "tel:+13105550100"
    expect(page.locator("#mp-s-name")).to_contain_text("Check in")
    page.locator("#mp-close").click()
    expect(page.locator("#mp-sheet")).to_be_hidden()


def test_a_list_row_selects_its_stop_and_the_list_names_the_place_it_could_not_find(map_page):
    page = map_page()
    page.locator('.mp-li[data-stop="4"]').click()
    expect(page.locator("#mp-s-name")).to_have_text("Griffith Observatory")
    expect(page.locator('.mp-pin-wrap[data-stop="4"]')).to_have_class(re.compile("is-sel"))
    expect(page.locator('[data-unknown="5"]')).to_have_text("Couldn’t find this place on the map.")
    page.get_by_role("link", name="Fix it in the calendar").click()  # a plan is fixed in the calendar, on its day
    page.wait_for_url(re.compile(r"/calendar\?view=whole"))


def test_the_route_is_drawn_and_the_page_never_scrolls_sideways(map_page):
    page = map_page()
    expect(page.locator("path.mp-route").first).to_be_attached()
    assert page.evaluate(OVERFLOW) == 0
    page.locator("#mp-strip a[data-day='1']").click()
    page.wait_for_url(re.compile(r"day=1"))
    expect(page.locator("#mp-daychip")).to_contain_text("Saturday")


def test_phone_has_no_small_text_or_small_controls_on_the_map_page(map_page):
    page = map_page()
    page.locator('.mp-pin-wrap[data-stop="3"]').click()
    page.evaluate("document.querySelector('.leaflet-control-attribution').hidden = true")  # OpenStreetMap's required credit keeps its own small size
    assert page.evaluate(SMALL_TEXT) == []
    assert page.evaluate(SMALL_CONTROLS) == []


@pytest.mark.parametrize("viewport", [{"width": 1440, "height": 900}, {"width": 1280, "height": 800}], ids=["1440", "1280"])
def test_the_map_fits_a_laptop_window_and_fills_the_space(map_page, viewport):
    """F-148: under the top bar the page is no taller than the window, and the map takes the room the header and the stop list leave."""
    page = map_page(viewport=viewport)
    page.wait_for_timeout(300)
    assert page.evaluate("document.documentElement.scrollHeight <= document.documentElement.clientHeight"), page.evaluate("document.documentElement.scrollHeight")
    box = page.locator("#mp-map").bounding_box()
    assert box["height"] >= viewport["height"] * 0.6, box
    # the list stands beside the map from the row the map's header starts on, fits the page and scrolls on its own
    assert page.evaluate("(() => { const l = document.getElementById('mp-list'), b = document.getElementById('mp-back'); const r = l.getBoundingClientRect(); return Math.abs(r.top - b.getBoundingClientRect().top) <= 12 && r.bottom <= window.innerHeight && getComputedStyle(l).overflowY === 'auto'; })()")
    # the library follows the container when its height changes (a shorter window): it never keeps drawing for the old size
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"] - 150})
    page.wait_for_timeout(300)
    assert page.evaluate("(() => { const m = document.getElementById('mp-map'); return m._leaflet.getSize().y === m.clientHeight; })()")
    assert page.evaluate("document.documentElement.scrollHeight <= document.documentElement.clientHeight")


SEG_ROOM = "[...document.querySelectorAll('.mp-seg')].map(a => { const r = document.createRange(); r.selectNodeContents(a); return a.getBoundingClientRect().width - r.getBoundingClientRect().width; })"
SEG_BOX = "(() => { const r = document.querySelector('.mp-segs').getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map(Math.round); })()"


@pytest.mark.parametrize("width", [1280, 1020])
def test_the_stops_and_around_switch_has_room_around_its_text_and_stays_put(map_page, width):
    """F-148 review: each segment has space either side of its words, and the switch is the same size and place in both views."""
    page = map_page(viewport={"width": width, "height": 800})
    assert all(room >= 1.5 * 12 for room in page.evaluate(SEG_ROOM)), page.evaluate(SEG_ROOM)
    stops = page.evaluate(SEG_BOX)
    page.click("#mp-seg-around")
    page.wait_for_selector("#ar")
    assert all(room >= 1.5 * 12 for room in page.evaluate(SEG_ROOM)), page.evaluate(SEG_ROOM)
    assert page.evaluate(SEG_BOX) == stops
