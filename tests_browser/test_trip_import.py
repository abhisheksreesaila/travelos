"""F-042: import a trip in a real (headless) browser: paste the template, preview, save, and see the booked-elsewhere blocks on the calendar.
Waits are on selectors and state, never on sleeps."""
import re
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
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        return page

    yield make
    for c in contexts:
        c.close()


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_paste_preview_save_and_see_it_on_the_calendar(signed_in, base_url, viewport):
    page = signed_in(viewport)
    page.goto(f"{base_url}/trips/import")
    expect(page.locator("#ti-template")).to_have_attribute("href", "/trips/import/template")
    page.fill("#ti-text", TEMPLATE)
    page.click("#ti-preview")
    expect(page.locator("#ti-preview-body")).to_contain_text("Alaska Airlines AS 1234 · SFO → LAX")
    expect(page.locator("#ti-hotel")).to_contain_text("123 Ocean Ave, Santa Monica")
    no_sideways_scroll(page)
    page.click("#ti-save")
    page.wait_for_url("**/calendar")
    expect(page.locator("h1")).to_contain_text("LA with the kids")
    expect(page.locator(".cal-tripline")).to_contain_text("booked elsewhere · Expedia")
    page.goto(f"{base_url}/calendar?view=days")
    out = page.locator('[data-block="b-out"]')
    expect(out).to_contain_text("Alaska Airlines AS 1234")
    expect(page.locator('[data-block="b-in"]')).to_have_count(1)
    no_sideways_scroll(page)
    page.goto(f"{base_url}/calendar?view=days&detail=b-out")
    expect(page.locator("#cal-confirmation")).to_have_text("ABCDEF")


def test_a_mistake_shows_a_friendly_line_specific_error_and_keeps_the_text(signed_in, base_url):
    page = signed_in(DESKTOP)
    page.goto(f"{base_url}/trips/import")
    page.fill("#ti-text", TEMPLATE.replace("from: SFO", "from: nowhere"))
    page.click("#ti-preview")
    expect(page.locator("#ti-errors")).to_contain_text("three-letter airport code")
    expect(page.locator("#ti-text")).to_have_value(TEMPLATE.replace("from: SFO", "from: nowhere"))


def test_late_events_fit_inside_the_grid(signed_in, base_url):
    late = (TEMPLATE.replace("check_in: 2026-10-16 15:00", "check_in: 2026-10-16 23:30").replace("depart: 2026-10-20 14:10", "depart: 2026-10-20 23:50")
            .replace("arrive: 2026-10-20 15:37", "arrive: 2026-10-21 01:10"))
    page = signed_in(DESKTOP)
    page.goto(f"{base_url}/trips/import")
    page.fill("#ti-text", late)
    page.click("#ti-preview")
    page.click("#ti-save")
    page.wait_for_url("**/calendar")
    page.goto(f"{base_url}/calendar?view=days")
    expect(page.locator("#cal-app")).to_have_attribute("data-grid-end", "1440")
    expect(page.locator(".cal-hour").last).to_have_text("11 PM")
    for block_id, day in (("b-in", 0), ("b-back", 4)):
        box = page.locator(f'[data-block="{block_id}"]').bounding_box()
        body = page.locator(f'.cal-body[data-day="{day}"]').bounding_box()
        assert box["y"] >= body["y"] - 1 and box["y"] + box["height"] <= body["y"] + body["height"] + 1, block_id
    root = page.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)")
    flight = page.locator('[data-block="b-back"]')
    assert flight.bounding_box()["height"] >= 1.2 * root  # about 30 minutes tall (1.25rem), not a line
    expect(flight.locator(".cal-time")).to_have_text("11:50 PM")  # the label keeps the true time
    no_sideways_scroll(page)


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_change_something_lands_on_the_builder_with_the_previewed_values(signed_in, base_url, viewport):
    """F-058: the main button on the preview opens the guided builder, filled, and the whole trip can be edited and previewed again."""
    page = signed_in(viewport)
    page.goto(f"{base_url}/trips/import")
    page.fill("#ti-text", TEMPLATE)
    page.click("#ti-preview")
    expect(page.locator("#ti-preview-body")).to_contain_text("Alaska Airlines AS 1234")
    expect(page.locator("#ti-edit-text")).to_be_visible()
    page.click("#ti-edit")
    page.wait_for_url("**/trips/build/from-import")
    expect(page.locator("#tb-form")).to_be_visible()
    expect(page.locator("#tb-title")).to_have_value("LA with the kids")
    expect(page.locator("#tb-destination")).to_have_value("Los Angeles")
    page.fill("#tb-title", "LA with the kids, edited")
    for _ in range(6):  # Where .. Car: every step is filled and passes as it is
        page.click("#tb-next")
        page.wait_for_load_state()
    expect(page.locator("#tb-notes")).to_have_value(re.compile("allergies, parking codes"))
    expect(page.locator("#tb-booked_on")).to_have_value("Expedia")
    page.click("#tb-next")
    expect(page.locator("#ti-trip")).to_contain_text("LA with the kids, edited")
    for text in ("Alaska Airlines AS 1234", "The Example Hotel Santa Monica", "Hertz", "ABCDEF", "987654321", "H1234567", "Kid 1", "age 7"):
        expect(page.locator("#ti-preview-body")).to_contain_text(text)
    no_sideways_scroll(page)


def test_edit_as_text_puts_the_template_back_in_the_box(signed_in, base_url):
    page = signed_in(DESKTOP)
    page.goto(f"{base_url}/trips/import")
    page.fill("#ti-text", TEMPLATE)
    page.click("#ti-preview")
    page.click("#ti-edit-text")
    expect(page.locator("#ti-text")).to_have_value(re.compile("LA with the kids"))


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_the_pdf_picker_is_a_styled_button_with_a_focus_ring_and_the_chosen_name(signed_in, base_url, tmp_path, viewport):
    page = signed_in(viewport)
    page.goto(f"{base_url}/trips/import")
    pick = page.locator(".ti-pick")
    expect(pick).to_be_visible()
    expect(page.locator("#ti-file-name")).to_have_text("No file chosen")
    assert page.evaluate("getComputedStyle(document.querySelector('.ti-pick')).borderRadius") != "0px"
    assert page.evaluate("document.getElementById('ti-file').getBoundingClientRect().width") <= 2  # the native control is not drawn
    pdf = tmp_path / "my-itinerary.pdf"
    pdf.write_bytes(b"%PDF-1.4 made up")
    page.set_input_files("#ti-file", str(pdf))
    expect(page.locator("#ti-file-name")).to_have_text("my-itinerary.pdf")
    page.focus("#ti-file")
    assert "rgb(30, 26, 46)" in page.evaluate("getComputedStyle(document.querySelector('.ti-pick')).outlineColor") or page.evaluate("getComputedStyle(document.querySelector('.ti-pick')).outlineStyle") == "solid"
    no_sideways_scroll(page)


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_import_a_booked_trip_is_a_visible_button_where_trips_start(signed_in, base_url, viewport):
    page = signed_in(viewport)
    page.goto(f"{base_url}/start")
    expect(page.locator("#st-import")).to_be_visible()
    expect(page.locator("#st-import")).to_have_text("Import a booked trip")
    page.click("#st-import")
    page.wait_for_url("**/trips/import")
    page.fill("#ti-text", TEMPLATE)
    page.click("#ti-preview")
    page.click("#ti-save")
    page.wait_for_url("**/calendar")
    expect(page.locator("#cal-import")).to_be_visible()
    no_sideways_scroll(page)
