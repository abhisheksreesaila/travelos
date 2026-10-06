"""F-054 review: focus cannot leave the add sheet while it is open."""
from datetime import date

from tests_browser.test_trip_phone import phone, pin  # noqa: F401 - fixtures


def test_focus_stays_inside_the_open_sheet(phone, base_url, pin):
    pin(date(2026, 10, 17), 9 * 60)
    page = phone()
    page.goto(base_url + "/trip?tab=today")
    page.click("#tp-add")
    inside = "document.getElementById('tp-sheet').contains(document.activeElement)"
    for _ in range(14):
        page.keyboard.press("Tab")
        assert page.evaluate(inside)
    for _ in range(14):
        page.keyboard.press("Shift+Tab")
        assert page.evaluate(inside)
