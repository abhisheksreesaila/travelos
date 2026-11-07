"""F-198 review: a booking confirmation pasted into Ask, in a real browser. In the phone's sheet (390; the laptop's panel is tests_browser/test_paste_handoff_desk.py) the box answers with one card, "This looks like a
Booking.com confirmation" (or Expedia), and "Check and add it" opens the import's preview: what will be saved, before anything is. Before the fix the card came back without the sheet's
own wrapper and ended in "That did not go through"."""
import pytest
from playwright.sync_api import expect

from tests.confirmation_samples import BOOKING
from tests.expedia_samples import PLAIN as EXPEDIA
from tests_browser.test_ask_sheet import day_page, model, open_sheet, phone  # noqa: F401 - fixtures

PASTES = [(BOOKING, "Booking.com", "Lakeside Lodge Tahoe"), (EXPEDIA, "Expedia", "Check your trip")]
IDS = ["booking", "expedia"]


def press_and_check(page, partner, shown):
    expect(page.locator("#ak-handoff")).to_contain_text(f"This looks like {'an' if partner[0] in 'AE' else 'a'} {partner} confirmation")
    expect(page.locator(".ak-error, #ak-error")).to_have_count(0)
    page.locator("#ak-import").click()
    page.wait_for_url("**/trips/import")
    expect(page.locator("h1")).to_have_text("Check your trip")
    expect(page.locator("body")).to_contain_text(shown)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("text, partner, shown", PASTES, ids=IDS)
def test_a_paste_in_the_phone_sheet_reaches_the_preview(phone, base_url, model, text, partner, shown):
    page = phone()
    day_page(page, base_url)
    open_sheet(page)
    page.locator("#ak-text").fill(text)
    if page.locator("#ak-mic").get_attribute("aria-pressed") == "true":
        page.locator("#ak-mic").click()
    page.locator("#ak-go").click()
    expect(page.locator("#ak-sheet #ak-handoff")).to_be_visible()
    button = page.locator("#ak-import").bounding_box()
    assert button["height"] >= 44, button
    press_and_check(page, partner, shown)
