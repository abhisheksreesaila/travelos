"""F-040: a family with two trips gets a switcher on the calendar; its menu fits the screen and switching opens the other trip.
Layout is checked in a real browser at desktop and phone widths (lesson: layout rules are tested here, not as CSS text)."""
import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE

SAMPLE = {"f": "f1", "h": "h1", "c": "c1"}
THREE_NIGHTS = {**SAMPLE, "d": "2026-10-23", "r": "2026-10-26", "a": "2", "k": "4,7"}


@pytest.fixture
def family_with_two_trips(browser, base_url):
    contexts = []

    def make(viewport):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form=SAMPLE, max_redirects=0)
        ctx.request.post(f"{base_url}/calendar/activities", form={"id": "a1", "day": "1", "start": "10:00", "end": "11:30", "title": "Venice Canals stroll", "kind": "outdoors"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form=THREE_NIGHTS, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/calendar?view=days")
        return page

    yield make
    for c in contexts:
        c.close()


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_the_menu_fits_the_screen_and_switching_opens_the_other_trip(family_with_two_trips, viewport):
    page = family_with_two_trips(viewport)
    expect(page.locator(".cal-trips-sum")).to_contain_text("2 trips")
    expect(page.locator("text=Venice Canals stroll")).to_have_count(0)  # the newest trip is open and has nothing planned yet
    page.click(".cal-trips-sum")
    pop = page.locator(".cal-trips-pop")
    expect(pop).to_be_visible()
    box = pop.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"]
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    expect(page.locator('.cal-trip[aria-current="true"]')).to_have_count(1)
    page.click(".cal-trip:not([aria-current])")
    page.wait_for_url("**/calendar")
    page.goto(page.url + "?view=days")
    expect(page.locator("text=Venice Canals stroll").first).to_be_visible()
