"""F-093 review fixes in a real browser: a flight added from the SOS sheet shows as a booking line with a sheet (pass, fix, remove), a refused number says why in the sheet, SOS is
pressed on the plan heading, the Family tab and the Ask page, and Help has a way back to the day."""
import re

from playwright.sync_api import expect

from tests_browser.test_booked import EDITOR, checks, close_sheet, day, imported_page, sheet_open  # noqa: F401 - fixtures and helpers
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures


def test_a_flight_is_added_from_sos_then_opened_fixed_and_removed_from_its_line(imported_page, base_url):
    page = imported_page()
    day(page, base_url, 1)
    page.locator("#cz-sos").click()
    page.locator("#sos-add-flight summary").click()
    form = page.locator("#sos-add-flight form")
    form.locator("input[name=airline]").fill("United")
    form.locator("input[name=number]").fill("1234")
    form.locator("input[name=from_code]").fill("LAX")
    form.locator("input[name=to_code]").fill("SFO")
    form.locator("input[name=fly_on]").evaluate("e => { e.value = '2026-10-17'; }")
    form.locator("input[name=time]").evaluate("e => { e.value = '14:25'; }")
    form.locator("button[type=submit]").click()
    page.wait_for_selector(".cz-sheet-sos")                                          # back where it was
    close_sheet(page)
    page.locator("a.cz-bk", has_text="United 1234").click()
    page.wait_for_selector(".cz-sheet-bk")
    expect(page.locator(".cz-sheet-bk")).to_contain_text("LAX → SFO")
    checks(page)
    page.locator(".cz-sheet-bk .hp-fix-sum", has_text="Fix this flight").click()
    page.locator(".cz-sheet-bk form[data-form=flight] input[name=number]").fill("999")
    page.locator(".cz-sheet-bk form[data-form=flight] button[type=submit]").click()
    page.wait_for_selector(".cz-sheet-bk:has-text('United 999')")
    page.locator(".cz-sheet-bk .pz-remove-sum", has_text="Remove this flight").click()
    page.locator(".cz-sheet-bk .pz-remove-yes").click()
    page.wait_for_selector(".cz-view[data-level=day]")
    assert page.locator("a.cz-bk", has_text="United").count() == 0
    assert page.locator(".cz-sheet").count() == 0


def test_a_refused_number_says_why_in_the_sheet(imported_page, base_url):
    page = imported_page()
    day(page, base_url, 0)
    page.locator("a.cz-bk", has_text="Check in").click()
    sheet_open(page, "b-in")
    page.locator(".cz-sheet-bk .hp-fix-sum").click()
    page.locator(".cz-sheet-bk input[name=phone]").fill("nope")
    page.locator(".cz-sheet-bk .hp-fix-form button[type=submit]").click()
    page.wait_for_selector("#bk-problem")
    expect(page.locator("#bk-problem")).to_contain_text("did not look right")
    assert "booked=b-in" in page.url


def test_sos_is_one_tap_on_the_plan_the_family_tab_and_the_ask_page(canvas_page, base_url):
    page = canvas_page()
    page.goto(f"{base_url}/trip/canvas?day=1")
    page.wait_for_selector(".cz-gb")
    page.locator(".cz-gb-open").first.click(position={"x": 90, "y": 40})
    page.wait_for_selector(".cz-view[data-level=block]")
    page.locator("#cz-sos").click()
    expect(page.locator(".cz-sheet-sos a[href='tel:911']")).to_be_visible()
    close_sheet(page)
    for path in ("/trip/family", "/trip/ask"):
        page.goto(base_url + path)
        checks(page)
        page.locator("#ph-sos").click()
        page.wait_for_selector(".cz-sheet-sos")
        expect(page.locator(".cz-sheet-sos a[href='tel:911']")).to_be_visible()
    page.goto(f"{base_url}/trip/map")
    assert page.locator("#ph-sos").count() == 0


def test_help_has_a_way_back_to_the_day(imported_page, base_url):
    page = imported_page()
    page.goto(f"{base_url}/trip/help")
    page.locator("#hp-back").click()
    page.wait_for_url(re.compile(r"/trip/canvas\?day="))
