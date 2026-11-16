"""M2/M3 in a real browser: follow an offer's /go link, finish the stand-in checkout, see it in the trip. Phone and laptop.
M5 triage: the /plan lanes that listed the offers and the /partners log are retired (F-254), so the test opens the offer's own link."""
import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE

TRIP = "to=hi&d=2027-03-05&r=2027-03-09&a=2"


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "laptop"])
def test_book_on_a_partner_from_an_offer_link_to_the_trip(browser, base_url, viewport):
    ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, reduced_motion="reduce")
    ctx.set_default_timeout(5000)
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page = ctx.new_page()
    page.goto(f"{base_url}/go/hif1?{TRIP}")
    page.wait_for_url("**/sandbox/aviasales/**")
    expect(page.get_by_text("Aloha Pacific 12")).to_be_visible()
    expect(page.get_by_text("$1,064").first).to_be_visible()
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    done = page.get_by_role("button", name="Complete booking on Aviasales")
    assert viewport is DESKTOP or done.bounding_box()["height"] >= 40
    done.tap() if viewport is PHONE else done.click()
    page.wait_for_url("**/done")
    expect(page.locator("#pt-done")).to_have_text("Booked elsewhere · Aviasales")
    page.goto(f"{base_url}/trip/details")
    expect(page.get_by_text("Aloha Pacific 12").first).to_be_visible()
    ctx.close()
