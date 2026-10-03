"""F-065: Today to read and share, in a real browser at phone and laptop width: Directions links carry the place, a booking's confirmation
shows only after a tap, Share hands the day's text to the share sheet (or copies it, saying "Copied"), and the day picker opens other days."""
from datetime import date

import pytest
from playwright.sync_api import expect

from gitaway import catalog, tripday
from tests.test_trip_import import SECRETS, TEMPLATE
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT

LAPTOP = {"width": 1280, "height": 800}
STUB_SHARE = "window.__shared = []; navigator.share = function (d) { window.__shared.push(d); return Promise.resolve(); };"
STUB_COPY = "delete Navigator.prototype.share; window.__copied = []; Object.defineProperty(navigator, 'clipboard', {value: {writeText: function (t) { window.__copied.push(t); return Promise.resolve(); }}, configurable: true});"


@pytest.fixture
def today(browser, base_url, monkeypatch):
    """today(viewport, script="") -> a signed-in page on an imported trip with one plan on Saturday; the clock is Fri Oct 16, 8:00 AM."""
    contexts = []
    monkeypatch.setattr(catalog, "today", lambda *_: date(2026, 10, 16))
    monkeypatch.setattr(tripday, "now_minute", lambda *_: 8 * 60)

    def make(viewport=PHONE, script=""):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=viewport is PHONE, is_mobile=viewport is PHONE)
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)
        ctx.request.post(f"{base_url}/calendar/activities", form={"id": "a1", "day": "0", "start": "17:00", "end": "19:30", "title": "Griffith Observatory", "kind": "culture"}, max_redirects=0)
        page = ctx.new_page()
        if script:
            page.add_init_script(script)
        return page

    yield make
    for c in contexts:
        c.close()


@pytest.mark.parametrize("viewport", [PHONE, LAPTOP], ids=["390", "1280"])
def test_directions_carry_the_place_and_the_confirmation_shows_only_after_a_tap(today, base_url, viewport):
    page = today(viewport)
    page.goto(base_url + "/trip")
    page.wait_for_load_state("networkidle")
    link = page.locator('[data-dir="a1"]')
    expect(link).to_be_visible()
    assert "Griffith+Observatory" in link.get_attribute("href")
    assert link.get_attribute("target") == "_blank"
    assert page.evaluate(OVERFLOW) == 0
    if viewport is PHONE:
        assert page.evaluate(SMALL_CONTROLS) == [] and page.evaluate(SMALL_TEXT) == []
    confirm = page.locator("[data-confirm]").first
    number = confirm.locator(".tp-conf-num")
    expect(number).to_be_hidden()
    confirm.locator("summary").click()
    expect(number).to_be_visible()
    assert any(s in number.inner_text() for s in SECRETS)


@pytest.mark.parametrize("viewport", [PHONE, LAPTOP], ids=["390", "1280"])
def test_share_hands_the_days_text_to_the_share_sheet(today, base_url, viewport):
    page = today(viewport, STUB_SHARE)
    page.goto(base_url + "/trip")
    page.locator("#tp-share").click()
    shared = page.evaluate("window.__shared")
    assert len(shared) == 1 and shared[0]["text"].startswith("Fri Oct 16 · ") and "5:00 PM Griffith Observatory" in shared[0]["text"]
    assert "$" not in shared[0]["text"] and not any(s in shared[0]["text"] for s in SECRETS)


@pytest.mark.parametrize("viewport", [PHONE, LAPTOP], ids=["390", "1280"])
def test_share_copies_the_text_and_says_copied_when_there_is_no_share_sheet(today, base_url, viewport):
    page = today(viewport, STUB_COPY)
    page.goto(base_url + "/trip")
    page.locator("#tp-share").click()
    expect(page.locator("#tp-share-status")).to_have_text("Copied")
    assert "5:00 PM Griffith Observatory" in page.evaluate("window.__copied")[0]


@pytest.mark.parametrize("viewport", [PHONE, LAPTOP], ids=["390", "1280"])
def test_the_day_picker_opens_another_day_and_the_share_text_follows(today, base_url, viewport):
    page = today(viewport)
    page.goto(base_url + "/trip")
    page.locator('#tp-strip [data-day="1"]').click()
    page.wait_for_url("**/trip?day=1")
    expect(page.locator("#tp-share")).to_have_attribute("data-share-text", __import__("re").compile(r"^Sat Oct 17 · "))


def test_the_plus_sits_at_the_columns_right_edge_on_a_laptop(today, base_url):
    page = today(LAPTOP)
    page.goto(base_url + "/trip")
    plus, col = page.locator("#tp-add").bounding_box(), page.locator("#tp-app").bounding_box()
    assert abs((plus["x"] + plus["width"]) - (col["x"] + col["width"])) <= 20, (plus, col)
