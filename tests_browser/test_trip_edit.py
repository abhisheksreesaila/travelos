"""F-061: press "Edit trip" on a saved trip in a real (headless) browser, change a flight time and a hotel name, save, and see both on the
calendar with an existing plan still there. Waits are on selectors and state, never on sleeps."""
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
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.errors = errors
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        return page

    yield make
    for c in contexts:
        c.close()


def setv(page, selector, value):
    """Set a field the themed picker has dressed (the real control is clipped behind it) and tell the page, as a pick would."""
    page.eval_on_selector(selector, "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }", value)


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("viewport,button", [(DESKTOP, "#ti-edit-trip"), (PHONE, "#ti-edit-trip")], ids=["desktop", "phone"])
def test_edit_a_flight_time_and_a_hotel_name_and_see_both_on_the_calendar(signed_in, base_url, viewport, button):
    page = signed_in(viewport)
    page.goto(f"{base_url}/trips/import")
    page.fill("#ti-text", TEMPLATE)
    page.click("#ti-preview")
    page.click("#ti-save")
    page.wait_for_url("**/calendar")
    # a plan that must survive the edit
    added = page.request.post(f"{base_url}/trip/plans", form={"id": "a1", "day": "1", "start": "12:00", "title": "Tacos", "kind": "fun"}, max_redirects=0)
    assert added.status in (200, 303)
    page.goto(f"{base_url}/calendar?view=days")
    expect(page.locator("body")).to_contain_text("Tacos")
    # the button is on the calendar's trip bar, the details page and the phone trip view
    expect(page.locator("#cal-edit-trip")).to_be_visible()
    page.goto(f"{base_url}/trip")
    expect(page.locator("#tp-edit-trip")).to_be_visible()
    page.goto(f"{base_url}/trip/details")
    page.click(button)
    expect(page.locator("#tb-form")).to_be_visible()
    expect(page.locator("#tb-heading")).to_have_text("Where are you going?")
    assert page.input_value("#tb-title") == "LA with the kids"
    for _ in range(3):  # where, dates, who: unchanged
        page.click("#tb-next")
    expect(page.locator("#tb-heading")).to_have_text("How are you getting there?")
    assert page.input_value('[name="leg0_depart_time"]') == "08:05"
    setv(page, '[name="leg0_depart_time"]', "07:20")
    page.click("#tb-next")
    expect(page.locator("#tb-heading")).to_have_text("Where are you staying?")
    assert page.input_value('[name="hotel0_name"]') == "The Example Hotel Santa Monica"
    page.fill('[name="hotel0_name"]', "The Corrected Inn")
    for _ in range(3):  # hotel, car, notes
        page.click("#tb-next")
    expect(page.locator("#ti-preview-body")).to_contain_text("The Corrected Inn")
    expect(page.locator("#ti-save-changes")).to_be_visible()
    assert page.evaluate("getComputedStyle(document.querySelector('.tb-steps')).listStyleType") == "none"  # the step list is styled like the builder's
    expect(page.locator("#ti-save")).to_have_count(0)
    expect(page.locator(".ti-match")).to_contain_text("plans, notes and rides stay")
    no_sideways_scroll(page)
    page.click("#ti-save-changes")
    page.wait_for_url("**/calendar")
    page.goto(f"{base_url}/calendar?view=days")
    expect(page.locator('[data-block="b-out"]')).to_contain_text("7:20")
    expect(page.locator('[data-block="b-in"]')).to_contain_text("The Corrected Inn")
    expect(page.locator('[data-block="b-in"]')).to_have_count(1)
    expect(page.locator("body")).to_contain_text("Tacos")  # the plan is still there
    no_sideways_scroll(page)
    assert not page.errors
