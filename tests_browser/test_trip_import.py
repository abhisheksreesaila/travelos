"""F-042: import a trip in a real (headless) browser: paste the template, preview, save, and see the booked-elsewhere blocks on the calendar.
Waits are on selectors and state, never on sleeps."""
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE

TEMPLATE = (Path(__file__).resolve().parent.parent / "docs" / "trip-template.md").read_text()


@pytest.fixture
def signed_in(browser, base_url):
    contexts = []

    def make(viewport):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        page = ctx.new_page()
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        return page

    yield make
    for c in contexts:
        c.close()


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_paste_preview_save_and_see_it_on_the_calendar(signed_in, base_url, viewport):
    page = signed_in(viewport)
    page.goto(f"{base_url}/trips/import")
    expect(page.locator("#ti-template")).to_have_attribute("href", "/trips/import/template")
    page.fill("#ti-text", TEMPLATE)
    page.click("#ti-preview")
    expect(page.locator("#ti-preview-body")).to_contain_text("Alaska Airlines AS 1234 · SFO → LAX")
    expect(page.locator("#ti-hotel")).to_contain_text("123 Ocean Ave, Santa Monica")
    no_sideways_scroll(page)
    page.click("#ti-save")
    page.wait_for_url("**/calendar")
    expect(page.locator("h1")).to_contain_text("LA with the kids")
    expect(page.locator(".cal-tripline")).to_contain_text("booked elsewhere · Expedia")
    page.goto(f"{base_url}/calendar?view=days")
    out = page.locator('[data-block="b-out"]')
    expect(out).to_contain_text("Alaska Airlines AS 1234")
    expect(page.locator('[data-block="b-in"]')).to_have_count(1)
    no_sideways_scroll(page)
    page.goto(f"{base_url}/calendar?view=days&detail=b-out")
    expect(page.locator("#cal-confirmation")).to_have_text("ABCDEF")


def test_a_mistake_shows_a_friendly_line_specific_error_and_keeps_the_text(signed_in, base_url):
    page = signed_in(DESKTOP)
    page.goto(f"{base_url}/trips/import")
    page.fill("#ti-text", TEMPLATE.replace("from: SFO", "from: nowhere"))
    page.click("#ti-preview")
    expect(page.locator("#ti-errors")).to_contain_text("three-letter airport code")
    expect(page.locator("#ti-text")).to_have_value(TEMPLATE.replace("from: SFO", "from: nowhere"))


def test_late_events_fit_inside_the_grid(signed_in, base_url):
    late = (TEMPLATE.replace("check_in: 2026-10-16 15:00", "check_in: 2026-10-16 23:30").replace("depart: 2026-10-20 14:10", "depart: 2026-10-20 23:50")
            .replace("arrive: 2026-10-20 15:37", "arrive: 2026-10-21 01:10"))
    page = signed_in(DESKTOP)
    page.goto(f"{base_url}/trips/import")
    page.fill("#ti-text", late)
    page.click("#ti-preview")
    page.click("#ti-save")
    page.wait_for_url("**/calendar")
    page.goto(f"{base_url}/calendar?view=days")
    expect(page.locator("#cal-app")).to_have_attribute("data-grid-end", "1440")
    expect(page.locator(".cal-hour").last).to_have_text("11 PM")
    for block_id, day in (("b-in", 0), ("b-back", 4)):
        box = page.locator(f'[data-block="{block_id}"]').bounding_box()
        body = page.locator(f'.cal-body[data-day="{day}"]').bounding_box()
        assert box["y"] >= body["y"] - 1 and box["y"] + box["height"] <= body["y"] + body["height"] + 1, block_id
    no_sideways_scroll(page)
