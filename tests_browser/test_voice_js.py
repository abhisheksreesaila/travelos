"""F-037: after a voice Apply the keyboard lands on the toast's Undo button. Run: `pixi run test-browser`."""
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP


def test_focus_lands_on_undo_after_a_voice_apply(browser, base_url):
    ctx = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
    ctx.set_default_timeout(5000)
    try:
        ctx.request.post(f"{base_url}/signin", form={"traveler": "ari", "next": "/", "intent": "save"})
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"})
        page = ctx.new_page()
        page.goto(f"{base_url}/calendar?voice=1&night=0")
        page.locator("#vo-apply").focus()
        page.keyboard.press("Enter")  # keyboard only: Apply with Enter
        page.wait_for_selector(".cal-undo")
        expect(page.locator(".cal-undo")).to_be_focused()
    finally:
        ctx.close()
