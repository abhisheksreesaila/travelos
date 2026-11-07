"""F-198 review: a booking confirmation pasted into Ask in the laptop's panel (1440 and 1280) reaches the import's preview through "Check and add it" (the phone's sheet is
tests_browser/test_paste_handoff.py). Its own module: the panel's trip is made by test_trip_canvas's fake model, the phone's sheet uses another."""
import pytest
from playwright.sync_api import expect

from tests_browser.test_day_ask import DOCK, desk, ready, voice  # noqa: F401 - fixtures
from tests_browser.test_paste_handoff import IDS, PASTES, press_and_check
from tests_browser.test_topbar import signed_in  # noqa: F401 - fixture
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures


@pytest.mark.parametrize("text, partner, shown", PASTES, ids=IDS)
def test_a_paste_in_the_laptop_panel_reaches_the_preview(desk, text, partner, shown):
    desk.locator(f"{DOCK} .cz-dock-tab[data-tab=ask]").click()
    ready(desk)
    desk.locator("#ak-text").fill(text)
    if desk.locator("#ak-mic").get_attribute("aria-pressed") == "true":
        desk.locator("#ak-mic").click()
    desk.locator("#ak-go").click()
    expect(desk.locator(f"{DOCK} #ak-handoff")).to_be_visible()
    press_and_check(desk, partner, shown)
