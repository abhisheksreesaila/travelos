"""F-073: Around you in a real browser at phone width. The phone's position is faked (Playwright's geolocation), so is Overpass (in the server's process) and the clock;
nothing reaches the network. Tap a chip -> cards with distance, open now, Directions and Call; Add to plan -> the calendar's form with the name in it -> the plan is on
the day; location denied -> the hotel is used and the page says so; every button is pressed; nothing scrolls sideways. A screenshot per state goes to the scratch folder."""
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import pytest
from playwright.sync_api import expect

from gitaway import catalog, geo
from tests.test_around import World, place
from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT

SHOTS = Path(os.environ.get("F073_SHOTS", "")) if os.environ.get("F073_SHOTS") else None
HOME = {"latitude": 34.0100, "longitude": -118.4900}


@pytest.fixture
def world(monkeypatch):
    w = World(place("Green Bowl", 0.002, phone="+1 310 555 0142", opening_hours="Mo-Su 09:00-21:00", website="https://greenbowl.example", diet_vegetarian="only", cuisine="vegetarian"),
              place("Plant Cafe", 0.004, diet_vegetarian="yes"),
              place("Night Owl", 0.001, opening_hours="Mo-Su 22:00-23:00", diet_vegetarian="yes"))
    monkeypatch.setattr(geo, "fetch", w)
    from gitaway.pages import around_ui
    t = [0.0]
    around_ui.LIMITS.clear()
    monkeypatch.setattr(around_ui, "_now", lambda: t.__setitem__(0, t[0] + 3.0) or t[0])   # the per-person limit has its own test
    monkeypatch.setattr(catalog, "now_utc", lambda: datetime(2026, 10, 17, 19, 40, tzinfo=timezone.utc))   # Saturday 12:40 PM in Los Angeles
    monkeypatch.setattr(catalog, "today", lambda *_: datetime(2026, 10, 17).date())
    return w


@pytest.fixture
def around_page(browser, base_url, world):
    """around_page(where="here" | "denied", vegetarian=True, query="") -> a signed-in phone page on Around you, with an imported trip."""
    contexts = []

    def make(where="here", vegetarian=True, query="view=around&day=1", pos=HOME):
        kw = dict(geolocation=pos, permissions=["geolocation"]) if where == "here" else {}
        ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True, **kw)
        ctx.set_default_timeout(6000)
        contexts.append(ctx)
        ctx.route(re.compile(r"https://(?!127\.0\.0\.1).*"), lambda r: r.abort())      # nothing else leaves the machine
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)
        if vegetarian:
            ctx.request.post(f"{base_url}/family/food", form={"vegetarian": "1"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/map?{query}")
        page.wait_for_selector("#ar")
        return page

    yield make
    for c in contexts:
        c.close()


@pytest.fixture(scope="module")
def shots():
    """A scratch folder for screenshots (F073_SHOTS, else a temporary one that is deleted afterwards)."""
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        yield SHOTS
        return
    d = Path(tempfile.mkdtemp(prefix="gitaway-f073-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_tapping_a_chip_asks_the_phone_and_shows_cards_with_directions_and_call(around_page, world, shots):
    page = around_page()
    expect(page.locator("#ar-chip-veg")).to_have_attribute("aria-pressed", "true")        # the family's preference picked it
    expect(page.locator("#ar-pref")).to_contain_text("Vegetarian")
    assert world.overpass == []                                                           # nothing is asked until a tap
    page.locator("#ar-chip-veg").click()
    expect(page.locator(".ar-card").first).to_be_visible()
    names = page.locator(".ar-name").all_inner_texts()
    assert names[0] == "Green Bowl" and "Night Owl" in names and names.index("Night Owl") > 0
    expect(page.locator("#ar-near")).to_have_text("near you")
    first = page.locator(".ar-card").first
    expect(first).to_contain_text("Open now")
    expect(first).to_contain_text("min walk")
    assert first.locator(".ar-call").get_attribute("href") == "tel:+13105550142"
    assert first.locator(".ar-dir").get_attribute("href").startswith("https://www.google.com/maps/search/?api=1&query=Green%20Bowl")
    assert page.locator(".ar-card").nth(1).locator(".ar-call").count() == 0                # no phone, no Call
    q = world.overpass[0]
    assert "(around:1500,34.01,-118.49)" in q
    assert page.evaluate(OVERFLOW) == 0
    box = first.locator(".ar-dir").bounding_box()
    assert box["height"] >= 43.5
    page.screenshot(path=str(shots / "around-390.png"), full_page=True)


def test_add_to_plan_opens_the_calendar_form_and_the_plan_lands_on_the_day(around_page, world):
    page = around_page()
    page.locator("#ar-chip-veg").click()
    page.locator(".ar-card").first.locator(".ar-add").click()
    page.wait_for_url(re.compile(r"/calendar\?"))
    expect(page.locator('input[name="title"]')).to_have_value("Green Bowl")
    expect(page.locator('input[name="start"]')).to_have_value("13:00")                      # it is 12:40 on the open day: the next half hour
    expect(page.locator('input[name="kind"][value="food"]')).to_be_checked()
    page.get_by_role("button", name="Add to the trip").click()
    page.wait_for_selector(".cal-modal", state="detached")
    expect(page.locator("body")).to_contain_text("Green Bowl")
    page.goto(page.url.split("/calendar")[0] + "/trip/family")                              # the family was told: a change card is in the thread
    expect(page.locator("#ft-thread")).to_contain_text("Green Bowl")


def test_if_the_phone_says_no_the_hotel_is_used_and_the_page_says_so(around_page, world, shots):
    page = around_page(where="denied", query="view=around&day=0")
    page.locator("#ar-chip-veg").click()
    expect(page.locator("#ar-note")).to_contain_text("couldn’t use your location")
    expect(page.locator("#ar-note")).to_contain_text("The Example Hotel Santa Monica, your hotel tonight")
    expect(page.locator("#ar-loc")).to_contain_text("Near The Example Hotel Santa Monica")
    expect(page.locator(".ar-card").first).to_be_visible()
    assert page.evaluate(OVERFLOW) == 0
    page.screenshot(path=str(shots / "around-denied-390.png"), full_page=True)


def test_every_button_is_pressed(around_page, world):
    page = around_page(vegetarian=False)
    expect(page.locator("#ar-pref")).to_contain_text("none")
    expect(page.locator("#ar-chips [aria-pressed='true']")).to_have_count(0)
    page.locator("#ar-locate").click()
    expect(page.locator("#ar-loc")).to_contain_text("Now pick what you need")                # located, nothing to look for yet
    for key, label in (("veg", "Vegetarian food"), ("coffee", "Coffee"), ("groc", "Groceries"), ("big", "Costco / Walmart"), ("rx", "Pharmacy"), ("gas", "Gas"), ("wc", "Restrooms")):
        page.locator(f"#ar-chip-{key}").click()
        expect(page.locator("#ar-fragment .ar-h2")).to_have_text(label)
        expect(page.locator(f"#ar-chip-{key}")).to_have_attribute("aria-pressed", "true")
        expect(page.locator("#ar-chips [aria-pressed='true']")).to_have_count(1)
    asked = len(world.overpass)
    page.locator("#ar-mode-drive").click()
    expect(page.locator("#ar-mode-drive")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#ar-mode-walk")).to_have_attribute("aria-pressed", "false")
    page.wait_for_function("document.querySelector('#ar-fragment') !== null")
    assert len(world.overpass) == asked + 1 and "(around:8000," in world.overpass[-1]
    page.locator("#ar-mode-walk").click()
    expect(page.locator("#ar-mode-walk")).to_have_attribute("aria-pressed", "true")
    page.locator("#mp-seg-stops").click()
    page.wait_for_url(re.compile(r"/trip/map\?day=1"))
    expect(page.locator("#mp-seg-stops")).to_have_attribute("aria-current", "true")
    page.locator("#mp-seg-around").click()
    page.wait_for_url(re.compile(r"view=around"))
    expect(page.locator("#ar")).to_be_visible()


def test_the_page_never_scrolls_sideways_and_has_no_small_text_or_controls(around_page, world):
    page = around_page()
    page.locator("#ar-chip-veg").click()
    expect(page.locator(".ar-card").first).to_be_visible()
    assert page.evaluate(OVERFLOW) == 0
    assert page.evaluate(SMALL_TEXT) == []
    assert page.evaluate(SMALL_CONTROLS) == []


def test_the_position_is_never_in_a_link_or_in_the_browsers_storage(around_page, world):
    page = around_page(pos={"latitude": 34.01234, "longitude": -118.49876})
    page.locator("#ar-chip-coffee").click()
    expect(page.locator(".ar-card").first).to_be_visible()
    hrefs = " ".join(page.locator("a").evaluate_all("els => els.map(e => e.getAttribute('href') || '')"))
    assert "34.01234" not in hrefs and "118.49876" not in hrefs
    stored = page.evaluate("JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage), document.cookie])")
    assert "34.01234" not in stored and "118.49876" not in stored
    assert "(around:1500,34.012,-118.499)" in world.overpass[0] and "34.01234" not in " ".join(world.overpass)      # Overpass hears it rounded


def test_the_family_pages_vegetarian_toggle_lands_back_on_the_page_and_shows_the_pill_on_around_you(around_page, world):
    page = around_page(vegetarian=False)
    expect(page.locator("#ar-pref")).to_contain_text("none")
    page.goto(page.url.split("/trip/")[0] + "/family")
    page.locator("#fam-food-toggle").click()
    page.wait_for_url(re.compile(r"/family#fam-food"))
    expect(page.locator("#fam-food-toggle")).to_contain_text("Vegetarian: on")
    page.goto(page.url.split("/family")[0] + "/trip/map?view=around&day=1")
    expect(page.locator("#ar-pref")).to_contain_text("Vegetarian")
    expect(page.locator("#ar-chip-veg")).to_have_attribute("aria-pressed", "true")


def test_a_chip_tap_asks_the_phone_again_when_the_position_is_over_three_minutes_old(around_page, world):
    page = around_page()
    page.add_init_script("window.__asks = 0; const g = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation); navigator.geolocation.getCurrentPosition = function (a, b, c) { window.__asks++; return g(a, b, c); };")
    page.reload()
    page.wait_for_selector("#ar")
    page.evaluate("window.__now = Date.now; Date.now = () => window.__now() + window.__skew; window.__skew = 0")
    page.locator("#ar-chip-veg").click()
    expect(page.locator(".ar-card").first).to_be_visible()
    page.locator("#ar-chip-coffee").click()
    expect(page.locator("#ar-fragment .ar-h2")).to_have_text("Coffee")
    assert page.evaluate("window.__asks") == 1
    page.evaluate("window.__skew = 4 * 60 * 1000")
    page.locator("#ar-chip-gas").click()
    expect(page.locator("#ar-fragment .ar-h2")).to_have_text("Gas")
    assert page.evaluate("window.__asks") == 2
