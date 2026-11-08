"""M2/M3 in a real browser: tap "Book on <partner>" on /plan, finish the stand-in checkout, see it in the trip and on /partners. Phone and laptop."""
import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE

TRIP = "to=hi&d=2027-03-05&r=2027-03-09&a=2"


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "laptop"])
def test_book_on_a_partner_from_plan_to_the_partner_log(browser, base_url, viewport):
    ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, reduced_motion="reduce")
    ctx.set_default_timeout(5000)
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page = ctx.new_page()
    page.goto(f"{base_url}/plan?{TRIP}")
    links = page.locator("a.ws-book-on:not(.ws-todo-link)")     # the Tickets and things to do card's link is not an offer (F-195)
    assert links.count() == 9                                   # every offer in Honolulu: 4 flights, 3 stays, 2 cars
    sizes = links.evaluate_all("els => els.map(e => e.getBoundingClientRect().height)")
    assert viewport is DESKTOP or min(sizes) >= 40, "on the phone each link is a touch target"
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    first = page.locator('a[data-partner="aviasales"]').first
    first.scroll_into_view_if_needed()
    first.tap() if viewport is PHONE else first.click()
    page.wait_for_url("**/sandbox/aviasales/**")
    expect(page.get_by_text("Aloha Pacific 12")).to_be_visible()
    expect(page.get_by_text("$1,064").first).to_be_visible()
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    done = page.get_by_role("button", name="Complete booking on Aviasales")
    assert viewport is DESKTOP or done.bounding_box()["height"] >= 40
    done.tap() if viewport is PHONE else done.click()
    page.wait_for_url("**/done")
    expect(page.locator("#pt-done")).to_have_text("Booked elsewhere · Aviasales")
    page.goto(f"{base_url}/partners")
    expect(page.locator("#pt-summary")).to_have_text("1 click · 1 booked")
    expect(page.locator(".pt-row")).to_have_count(1)
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    page.goto(f"{base_url}/trip/details")
    expect(page.get_by_text("Aloha Pacific 12").first).to_be_visible()
    ctx.close()
