"""F-054: the phone-first trip home in a real browser: Today renders, + adds a plan in two taps, tabs switch, nothing scrolls sideways,
text and touch targets meet the phone rules, and the + and tab bar sit inside the screen."""
from datetime import date

import re
import pytest
from playwright.sync_api import expect

from gitaway import catalog, tripday
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT

NARROW = {"width": 320, "height": 640}
IPHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"


@pytest.fixture
def pin(monkeypatch):
    def pin(day, minute=12 * 60):
        monkeypatch.setattr(catalog, "today", lambda *_: day)
        monkeypatch.setattr(tripday, "now_minute", lambda *_: minute)
    return pin


@pytest.fixture
def phone(browser, base_url):
    """phone(viewport=PHONE, **context) -> a signed-in page with the sample trip booked and one plan on Saturday."""
    contexts = []

    def make(viewport=PHONE, motion="reduce", **ctx_args):
        ctx = browser.new_context(viewport=viewport, reduced_motion=motion, has_touch=True, is_mobile=True, **ctx_args)
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
        ctx.request.post(f"{base_url}/calendar/activities", form={"id": "a1", "day": "1", "start": "17:00", "end": "19:30", "title": "Griffith Observatory", "kind": "culture"}, max_redirects=0)
        return ctx.new_page()

    yield make
    for c in contexts:
        c.close()


@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_today_renders_during_the_trip_without_sideways_scroll_small_text_or_small_targets(phone, base_url, pin, viewport):
    pin(date(2026, 10, 17), 16 * 60 + 20)
    page = phone(viewport)
    page.goto(base_url + "/trip?tab=today")
    page.wait_for_load_state("networkidle")
    expect(page.locator("#tp-up")).to_contain_text("UP NEXT · IN 40 MIN")
    expect(page.locator("#tp-up")).to_contain_text("Griffith Observatory")
    expect(page.locator("#tp-directions")).to_be_visible()
    expect(page.locator("#tp-stay")).to_contain_text("Your hotel tonight")
    assert page.evaluate(OVERFLOW) == 0
    assert page.evaluate(SMALL_TEXT) == []
    assert page.evaluate(SMALL_CONTROLS) == []


def test_before_the_trip_it_shows_the_countdown_and_day_one(phone, base_url):
    page = phone()
    page.goto(base_url + "/trip?tab=today")
    expect(page.locator("#tp-up")).to_contain_text("TRIP STARTS IN 16 DAYS")
    expect(page.locator("#tp-list")).to_contain_text("Skylark Air 214")
    assert page.evaluate(OVERFLOW) == 0


def test_the_plus_adds_a_plan_in_two_taps_and_the_calendar_has_it(phone, base_url, pin):
    pin(date(2026, 10, 17), 9 * 60)
    page = phone()
    page.goto(base_url + "/trip?tab=today")
    expect(page.locator("#tp-sheet")).to_be_hidden()
    page.click("#tp-add")  # tap one
    expect(page.locator("#tp-sheet")).to_be_visible()
    expect(page.locator("#tp-title")).to_be_focused()
    page.fill("#tp-title", "Tacos on Abbot Kinney")
    page.click("#tp-save")  # tap two
    page.wait_for_url("**/trip?day=1&new=*")
    expect(page.locator("#tp-toast")).to_contain_text("Added “Tacos on Abbot Kinney”")
    expect(page.locator("#tp-panel-today")).to_contain_text("Tacos on Abbot Kinney")
    page.goto(base_url + "/calendar?view=whole")
    expect(page.locator(".cal-whole")).to_contain_text("Tacos on Abbot Kinney")


def test_a_plan_added_over_a_booking_is_saved_and_tagged(phone, base_url, pin):
    pin(date(2026, 10, 17), 9 * 60)
    page = phone()
    page.goto(base_url + "/trip?day=0")
    page.click("#tp-add")
    page.fill("#tp-title", "Second thing")
    page.fill("#tp-start", "09:00")
    page.click("#tp-save")
    page.wait_for_url("**/trip?day=0&new=*")
    expect(page.locator("#tp-toast")).to_contain_text("Added “Second thing”")
    expect(page.locator(".tp-overlap").first).to_contain_text("Overlaps Skylark Air 214")
    assert page.evaluate(OVERFLOW) == 0


def test_the_sheet_closes_without_adding(phone, base_url, pin):
    pin(date(2026, 10, 17), 9 * 60)
    page = phone()
    page.goto(base_url + "/trip?tab=today")
    page.click("#tp-add")
    page.keyboard.press("Escape")
    expect(page.locator("#tp-sheet")).to_be_hidden()
    page.click("#tp-add")
    page.click(".tp-sheet-actions [data-close-sheet]")
    expect(page.locator("#tp-sheet")).to_be_hidden()


def test_the_tabs_switch_without_a_reload(phone, base_url, pin):
    pin(date(2026, 10, 17), 9 * 60)
    page = phone()
    page.goto(base_url + "/trip?tab=today")
    expect(page.locator("#tp-panel-today")).to_be_visible()
    page.click("#tp-tab-days")
    expect(page.locator("#tp-panel-days")).to_be_visible()
    expect(page.locator("#tp-panel-today")).to_be_hidden()
    expect(page.locator("#tp-title-h")).to_have_text("Your 5 days")
    assert page.locator(".tp-tile").count() == 5
    page.click("#tp-tab-notes")
    expect(page.locator("#tp-panel-notes")).to_be_visible()
    expect(page.locator("#tp-title-h")).to_have_text("Trip notes")
    page.fill("#tp-note-text", "Bring sunscreen")
    page.click("#tp-composer button")
    page.wait_for_url("**/trip?tab=notes")
    expect(page.locator("#tp-feed")).to_contain_text("Bring sunscreen")
    page.click("#tp-tab-today")
    expect(page.locator("#tp-panel-today")).to_be_visible()
    for tab in ("days", "notes"):
        page.goto(f"{base_url}/trip?tab={tab}")
        assert page.evaluate(OVERFLOW) == 0
        assert page.evaluate(SMALL_TEXT) == []
        assert page.evaluate(SMALL_CONTROLS) == []


def test_the_tab_bar_and_the_plus_stay_inside_the_screen_and_the_plus_clears_the_bar(phone, base_url):
    page = phone()
    page.goto(base_url + "/trip?tab=today")
    vh = PHONE["height"]
    bar = page.locator(".ph-tabs").bounding_box()
    plus = page.locator("#tp-add").bounding_box()
    assert bar["y"] + bar["height"] <= vh + 0.5 and bar["x"] >= 0 and bar["x"] + bar["width"] <= PHONE["width"] + 0.5
    assert plus["y"] + plus["height"] <= bar["y"] and plus["x"] + plus["width"] <= PHONE["width"]
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    last = page.locator(".tp-full").bounding_box()
    assert last["y"] + last["height"] <= page.locator(".ph-tabs").bounding_box()["y"] + 0.5  # the end of the page is not hidden behind the bar


def test_reduced_motion_stops_the_pulse_and_normal_motion_pulses(phone, base_url, pin):
    pin(date(2026, 10, 17), 16 * 60 + 20)
    calm = phone(motion="reduce")
    calm.goto(base_url + "/trip?tab=today")
    assert calm.evaluate("getComputedStyle(document.querySelector('.tp-pulse')).animationName") == "none"
    lively = phone(motion="no-preference")
    lively.goto(base_url + "/trip?tab=today")
    assert lively.evaluate("getComputedStyle(document.querySelector('.tp-pulse')).animationName") != "none"


def test_a_phone_opening_the_calendar_lands_on_the_day_view(phone, base_url):
    page = phone(user_agent=IPHONE_UA)
    page.goto(base_url + "/calendar")
    page.wait_for_url(re.compile(r"/trip/canvas\?day=\d"))      # F-092: /trip is the day view
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.goto(base_url + "/calendar?view=whole")      # the full calendar is still one address away
    assert "/calendar?view=whole" in page.url


@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_f085_notes_start_folded_and_a_tap_opens_them_in_place(phone, base_url, pin, viewport):
    pin(date(2026, 10, 17), 16 * 60 + 20)
    page = phone(viewport)
    page.request.post(f"{base_url}/calendar/activities", form={"id": "a2", "day": "1", "start": "20:00", "end": "21:00", "title": "Tacos", "kind": "food"}, max_redirects=0)
    for n, act in (("n1", "a1"), ("n2", "a2"), ("n3", "a2")):
        page.request.post(f"{base_url}/calendar/notes", form={"id": n, "text": f"Note {n}", "act": act}, max_redirects=0)
    page.goto(base_url + "/trip?tab=today")
    page.wait_for_load_state("networkidle")
    summary = page.locator("[data-notes=a2] summary")
    expect(summary).to_contain_text("2 notes")
    expect(page.locator(".tp-pnote", has_text="Note n2")).to_be_hidden()
    assert summary.bounding_box()["height"] >= 43.5
    summary.click()
    expect(page.locator(".tp-pnote", has_text="Note n2")).to_be_visible()
    expect(page.locator(".tp-pnote", has_text="Note n3")).to_be_visible()
    assert page.evaluate(OVERFLOW) == 0 and page.evaluate(SMALL_TEXT) == [] and page.evaluate(SMALL_CONTROLS) == []
    summary.click()
    expect(page.locator(".tp-pnote", has_text="Note n2")).to_be_hidden()
    up = page.locator("#tp-up [data-notes=a1] summary")
    expect(up).to_contain_text("1 note")
    expect(page.locator(".tp-pnote", has_text="Note n1")).to_be_hidden()
    up.click()
    expect(page.locator(".tp-pnote", has_text="Note n1")).to_be_visible()
    assert page.evaluate(OVERFLOW) == 0
