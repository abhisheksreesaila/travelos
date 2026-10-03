"""F-067: the phone shell in a real browser: the bottom tab bar on every trip screen (every tab pressed), the raised Ask, placeholder cards, Today v2
(Directions and Uber hrefs, Leave by, struck-through done items, the route strip), phone checks, and the laptop layout unchanged."""
import sys
import types
from datetime import date

import pytest
from playwright.sync_api import expect

from gitaway import catalog, tripday
from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT

LAPTOP = {"width": 1280, "height": 800}
NARROW = {"width": 320, "height": 640}
TABS = [("today", "Today", "/trip"), ("map", "Map", "/trip/map"), ("ask", "Ask", "/trip/ask"), ("family", "Family", "/trip/family"), ("help", "Help", "/trip/help")]


@pytest.fixture
def clock(monkeypatch):
    """clock(day, minute): pins the date and the minute of the day (default Sat Oct 17, 4:00 PM)."""
    def pin(day=date(2026, 10, 17), minute=16 * 60):
        monkeypatch.setattr(catalog, "today", lambda *_: day)
        monkeypatch.setattr(tripday, "now_minute", lambda *_: minute)
    pin()
    return pin


@pytest.fixture
def shell(browser, base_url, clock):
    """shell(viewport) -> a signed-in page on an imported trip with three plans on Saturday."""
    contexts = []

    def make(viewport=PHONE):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=viewport["width"] < 700, is_mobile=viewport["width"] < 700)
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)
        ctx.request.post(f"{base_url}/calendar/activities", form={"id": "a1", "day": "1", "start": "17:00", "end": "19:30", "title": "Griffith Observatory", "kind": "culture"}, max_redirects=0)
        ctx.request.post(f"{base_url}/calendar/activities", form={"id": "a2", "day": "1", "start": "20:00", "end": "21:00", "title": "Tacos on the pier", "kind": "food"}, max_redirects=0)
        ctx.request.post(f"{base_url}/calendar/activities", form={"id": "a3", "day": "1", "start": "09:00", "end": "10:00", "title": "Pancakes", "kind": "food"}, max_redirects=0)
        return ctx.new_page()

    yield make
    for c in contexts:
        c.close()


def checks(page):
    assert page.evaluate(OVERFLOW) == 0
    assert page.evaluate(SMALL_TEXT) == []
    assert page.evaluate(SMALL_CONTROLS) == []


def test_every_tab_is_pressed_and_lands_in_the_shell(shell, base_url):
    page = shell()
    page.goto(base_url + "/trip")
    bar = page.locator(".ph-tabs")
    expect(bar).to_be_visible()
    for key, name, path in TABS:
        page.locator(f"#ph-tab-{key}").click()
        page.wait_for_url(f"**{path}")
        expect(page.locator(f"#ph-tab-{key}")).to_have_attribute("aria-current", "page")
        expect(bar).to_be_visible()
        assert bar.locator("a").count() == 5
        box = bar.bounding_box()
        assert box["y"] + box["height"] <= PHONE["height"] + 0.5 and box["x"] >= 0 and box["x"] + box["width"] <= PHONE["width"] + 0.5
        if key == "today":
            expect(page.locator("#tp-up")).to_be_visible()
        elif key == "map":
            expect(page.locator("#tp-title-h")).to_have_text("Map")
            expect(page.locator("#mp-daychip")).to_be_visible()  # the real map (F-068), not a "coming" card
        elif key == "help":
            expect(page.locator("#hp-911")).to_be_visible()  # built in F-069
        elif key == "family":   # built in F-070: its own browser tests are in test_thread.py
            expect(page.locator("#ft")).to_be_visible()
            expect(page.locator("#tp-title-h")).to_have_text(name)
        else:
            expect(page.locator("#ph-coming")).to_contain_text(f"{name} is coming")
            expect(page.locator("#tp-title-h")).to_have_text(name)
            page.locator("#ph-coming a").click()  # the card's own button goes back to Today
            page.wait_for_url("**/trip")
            page.goto(base_url + path)
        checks(page)


def test_ask_is_raised_above_the_other_tabs(shell, base_url):
    page = shell()
    page.goto(base_url + "/trip")
    ask = page.locator("#ph-tab-ask .ph-ti").bounding_box()
    today = page.locator("#ph-tab-today .ph-ti").bounding_box()
    bar = page.locator(".ph-tabs").bounding_box()
    assert ask["y"] < today["y"] - 8 and ask["y"] < bar["y"] and ask["height"] > today["height"]


def test_the_bar_stays_put_when_the_page_scrolls_and_does_not_cover_the_end(shell, base_url):
    page = shell()
    page.goto(base_url + "/trip")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    bar = page.locator(".ph-tabs").bounding_box()
    assert bar["y"] + bar["height"] <= PHONE["height"] + 0.5 and bar["y"] > PHONE["height"] - 120
    assert page.locator(".tp-full").bounding_box()["y"] + page.locator(".tp-full").bounding_box()["height"] <= bar["y"] + 0.5


def test_today_has_directions_uber_and_the_route_strip(shell, base_url):
    page = shell()
    page.goto(base_url + "/trip")
    directions, uber = page.locator("#tp-directions"), page.locator("#tp-uber")
    expect(directions).to_be_visible()
    expect(uber).to_be_visible()
    assert uber.get_attribute("href").startswith("https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff[formatted_address]=")
    assert directions.get_attribute("href")
    assert uber.get_attribute("href").split("=")[-1] == "Griffith%20Observatory%2C%20Los%20Angeles"
    expect(page.locator("#tp-route")).to_be_visible()
    assert page.locator("#tp-route .ph-stop").count() >= 2
    expect(page.locator(".ph-sec")).to_have_text("THE REST OF TODAY")
    expect(page.locator("#tp-stay")).to_be_visible()
    checks(page)


def test_done_items_are_struck_through(shell, base_url, clock):
    page = shell()
    page.goto(base_url + "/trip")
    done = page.locator('.tp-row.is-done .tp-what', has_text="Pancakes")
    expect(done).to_be_visible()
    assert "line-through" in done.evaluate("e => getComputedStyle(e).textDecorationLine")
    live = page.locator('.tp-row:not(.is-done) .tp-what').first
    assert "line-through" not in live.evaluate("e => getComputedStyle(e).textDecorationLine")


def test_leave_by_shows_only_when_a_drive_time_is_known(shell, base_url, clock, monkeypatch):
    page = shell()
    monkeypatch.delitem(sys.modules, "gitaway.geo", raising=False)
    page.goto(base_url + "/trip")
    expect(page.locator("#tp-up")).to_be_visible()
    expect(page.locator("#tp-leave")).to_have_count(0)
    mod = types.ModuleType("gitaway.geo")
    mod.drive_minutes = lambda a, b: 20
    monkeypatch.setitem(sys.modules, "gitaway.geo", mod)
    page.goto(base_url + "/trip")
    expect(page.locator("#tp-leave")).to_contain_text("Leave by 4:40 PM")
    expect(page.locator(".ph-ring-n")).to_have_text("40")
    checks(page)


@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_no_sideways_scroll_on_any_screen(shell, base_url, viewport):
    page = shell(viewport)
    for path in ("/trip", "/trip?tab=days", "/trip?tab=notes", "/trip/map", "/trip/ask", "/trip/family", "/trip/help"):
        page.goto(base_url + path)
        assert page.evaluate(OVERFLOW) == 0, path


def test_the_laptop_keeps_its_layout(shell, base_url):
    page = shell(LAPTOP)
    page.goto(base_url + "/trip")
    expect(page.locator(".ph-tabs")).to_be_hidden()
    bar = page.locator(".tp-tabs").bounding_box()  # the old Today / All days / Notes bar, fixed at the bottom
    assert bar["y"] + bar["height"] >= LAPTOP["height"] - 1 and bar["height"] < 100
    page.locator("#tp-tab-days").click()
    expect(page.locator("#tp-panel-days")).to_be_visible()
    assert page.evaluate(OVERFLOW) == 0
    page.goto(base_url + "/trip/map")
    expect(page.locator(".ph-tabs")).to_be_hidden()
    expect(page.locator("#mp-daychip")).to_be_visible()
    page.locator(".ph-back").click()
    page.wait_for_url("**/trip")
    assert page.evaluate(OVERFLOW) == 0


OVERLAPS = """() => { const f = document.getElementById('tp-add').getBoundingClientRect(); const hit = e => { const r = e.getBoundingClientRect();
  return r.width && r.height && r.left < f.right && r.right > f.left && r.top < f.bottom && r.bottom > f.top; };
  return [...document.querySelectorAll('%s')].filter(hit).map(e => e.className || e.id); }"""


def test_the_floating_plus_never_covers_a_pill_or_the_end_of_the_page(shell, base_url):
    page = shell()
    page.goto(base_url + "/trip")
    height = page.evaluate("document.documentElement.scrollHeight")
    for y in range(0, height, 120):
        page.evaluate(f"window.scrollTo(0, {y})")
        assert page.evaluate(OVERLAPS % ".tp-mini, .tp-state, .tp-go, .tp-btn:not(.tp-plus)") == [], y
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    assert page.evaluate(OVERLAPS % ".tp-full, .tp-sharebar, #tp-stay, .tp-card") == []


def test_up_next_details_reach_who_added_it(shell, base_url):
    page = shell()
    page.goto(base_url + "/trip")
    expect(page.locator('[data-item="a1"]')).to_have_count(0)
    summary = page.locator("#tp-up [data-up-details] summary")
    summary.click()
    expect(page.locator("#tp-up [data-up-details]")).to_contain_text("added by")
