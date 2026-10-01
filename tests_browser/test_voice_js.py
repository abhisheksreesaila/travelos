"""F-037: where keyboard focus goes around Talk to plan. Run: `pixi run test-browser`.

The default context uses reduced motion (hearing ends at once); the typing path runs with motion on.
"""
import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP


@pytest.fixture
def booked_page(browser, base_url):
    """booked_page(reduced=True) -> a page on the calendar for a signed-in traveler with a booking."""
    contexts = []

    def make(reduced=True):
        ctx = browser.new_context(viewport=DESKTOP, reduced_motion="reduce" if reduced else "no-preference")
        ctx.set_default_timeout(8000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"})
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"})
        page = ctx.new_page()
        page.goto(f"{base_url}/calendar?view=days")
        page.wait_for_selector(".vo-open")
        return page

    yield make
    for c in contexts:
        c.close()


def test_focus_lands_on_undo_after_a_voice_apply(browser, base_url):
    ctx = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
    ctx.set_default_timeout(5000)
    try:
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"})
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"})
        page = ctx.new_page()
        page.goto(f"{base_url}/calendar?voice=1&night=0")
        page.locator("#vo-apply").focus()
        page.keyboard.press("Enter")  # keyboard only: Apply with Enter
        page.wait_for_selector(".cal-undo")
        expect(page.locator(".cal-undo")).to_be_focused()
    finally:
        ctx.close()


@pytest.mark.parametrize("reduced", [True, False])
def test_keyboard_opening_talk_to_plan_ends_on_the_first_chip(booked_page, reduced):
    page = booked_page(reduced)
    page.locator(".vo-open").focus()
    page.keyboard.press("Enter")  # calendar.js hands focus back to this link after the swap; that is not the traveler moving
    expect(page.locator(".vo-chip").first).to_be_focused(timeout=20000)  # the typed sentence takes a few seconds


def test_tabbing_away_while_hearing_is_not_overridden(booked_page):
    page = booked_page(reduced=False)
    page.locator(".vo-open").focus()
    page.keyboard.press("Enter")
    page.wait_for_selector("#cal-voice.is-typing")
    page.keyboard.press("Tab")  # the traveler moves on while the sentence is still being heard
    moved = page.evaluate("document.activeElement.className")
    assert "vo-open" not in moved
    page.wait_for_selector("#cal-voice:not(.is-typing)")
    page.wait_for_timeout(400)  # past finish()'s beat
    assert page.evaluate("document.activeElement.className") == moved
    assert page.evaluate("document.activeElement.classList.contains('vo-chip')") is False
