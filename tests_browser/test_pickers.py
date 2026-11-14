"""F-051: the themed pickers, in a real browser. Run: `pixi run test-browser`.

Pick a range by mouse and by keyboard on Plan it for me's intake (/plan-for-me/start; it had the Where to? form's pickers since F-231 deleted /start) and land on the right
dates, the age dropdown and a time list by keyboard, the phone bottom sheet at 390, and no browser-default control left visible. (The server side is tests/test_pickers.py.)
"""
import re

import pytest
from playwright.sync_api import expect

from gitaway.pages.planforme import MAX_KIDS
from tests_browser.helpers import DESKTOP, PHONE

DATES = "/plan-for-me/start?start=2026-10-16&end=2026-10-20&adults=2"
FAMILY = DATES + "&nkids=2&k1=7&k2=9"


@pytest.fixture
def make(browser, base_url):
    """make(path, viewport=DESKTOP, signed_in=False) -> a page with the picker script bound."""
    contexts = []

    def make(path, viewport=DESKTOP, signed_in=False):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        if signed_in:
            ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"})
            ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.errors = errors
        page.goto(f"{base_url}{path}")
        page.wait_for_selector("html[data-ga-ready]")
        return page

    yield make
    for c in contexts:
        c.close()


def day(page, name):
    return page.get_by_role("dialog").get_by_role("button", name=re.compile(rf"^{name}"))


def test_pick_a_range_with_the_mouse_and_the_fields_hold_those_dates(make):
    page = make(DATES)
    page.get_by_role("button", name=re.compile("^From:")).click()
    expect(page.get_by_role("dialog", name="Choose your dates")).to_be_visible()
    day(page, "Thursday, October 22").click()
    day(page, "Sunday, October 25").click()
    expect(page.locator(".ga-nights")).to_have_text("3 nights")
    page.get_by_role("button", name="Done").click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    assert page.input_value("#pf-start") == "2026-10-22" and page.input_value("#pf-end") == "2026-10-25"
    expect(page.get_by_role("button", name=re.compile("^To: Sun, Oct 25"))).to_be_visible()
    assert not page.errors


def test_pick_a_range_with_the_keyboard_and_focus_comes_back(make):
    page = make(DATES)
    leave = page.get_by_role("button", name=re.compile("^From:"))
    leave.focus()
    page.keyboard.press("Enter")
    expect(page.get_by_role("dialog")).to_be_visible()
    expect(day(page, "Friday, October 16")).to_be_focused()  # opens on the current leave day
    page.keyboard.press("ArrowRight")
    expect(day(page, "Saturday, October 17")).to_be_focused()
    page.keyboard.press("Enter")                              # the new leave day; the old return day is cleared
    page.keyboard.press("ArrowDown")
    expect(day(page, "Saturday, October 24")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".ga-nights")).to_have_text("7 nights")
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(leave).to_be_focused()
    assert page.input_value("#pf-start") == "2026-10-17" and page.input_value("#pf-end") == "2026-10-24"


def test_past_days_are_disabled_and_months_navigate(make):
    page = make(DATES)
    page.get_by_role("button", name=re.compile("^From:")).click()
    page.get_by_role("button", name="Previous month").click()
    expect(page.get_by_role("dialog").locator(".ga-month")).to_have_text("September 2026")
    expect(day(page, "Tuesday, September 29")).to_be_disabled()  # today is Sept 30 in the tests
    expect(day(page, "Wednesday, September 30")).to_be_enabled()
    expect(page.get_by_role("button", name="Previous month")).to_be_disabled()
    page.get_by_role("button", name="Next month").click()
    expect(page.get_by_role("dialog").locator(".ga-month")).to_have_text("October 2026")


def test_the_grid_is_an_aria_grid_and_announces_the_range(make):
    page = make(DATES)
    page.get_by_role("button", name=re.compile("^From:")).click()
    expect(page.get_by_role("grid")).to_be_visible()
    expect(page.get_by_role("gridcell").first).to_be_attached()
    day(page, "Thursday, October 22").click()
    day(page, "Sunday, October 25").click()
    live = page.locator(".ga-pop [aria-live=polite][aria-atomic]")
    expect(live).to_contain_text("Leaving Thu, Oct 22, back Sun, Oct 25, 3 nights")
    assert page.get_by_role("gridcell", selected=True).count() >= 2


def test_the_age_dropdown_works_by_keyboard(make):
    page = make(FAMILY)
    age = page.get_by_role("button", name=re.compile("^Kid 1 age:"))
    expect(age).to_contain_text("7")
    age.focus()
    page.keyboard.press("Enter")
    box = page.get_by_role("listbox", name="Kid 1 age")
    expect(box).to_be_focused()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowDown")  # one row down in the chip grid
    page.keyboard.press("Enter")
    expect(box).to_have_count(0)
    expect(age).to_be_focused()
    chosen = page.input_value("#pf-k1")
    assert chosen not in ("", "7") and int(chosen) > 8
    expect(age).to_contain_text(chosen)


def test_steppers_change_how_many_kids_and_show_their_ages(make):
    page = make(FAMILY)
    kids = page.get_by_role("group", name=re.compile("^Kids"))
    more = kids.get_by_role("button", name="More kids")
    more.click()
    assert page.input_value("#pf-nkids") == "3"
    expect(page.locator("#pf-kids .pf-kid").nth(2)).to_be_visible()  # planforme.js still follows the change
    for _ in range(MAX_KIDS - 3):
        more.click()
    assert page.input_value("#pf-nkids") == str(MAX_KIDS)
    expect(more).to_have_attribute("aria-disabled", "true")  # the most a trip can have
    kids.get_by_role("button", name="Fewer kids").click()
    assert page.input_value("#pf-nkids") == str(MAX_KIDS - 1)


def test_on_a_phone_the_calendar_is_a_bottom_sheet(make):
    page = make(DATES, viewport=PHONE)
    page.get_by_role("button", name=re.compile("^From:")).click()
    sheet = page.get_by_role("dialog")
    expect(sheet).to_be_visible()
    box = sheet.bounding_box()
    assert box["x"] == 0 and round(box["width"]) == PHONE["width"]
    assert round(box["y"] + box["height"]) == PHONE["height"]  # it sits on the bottom edge
    assert page.locator(".ga-scrim").is_visible()
    d = day(page, "Friday, October 16").bounding_box()
    assert d["height"] >= 44 and d["width"] >= 44
    assert page.get_by_role("button", name="Done").bounding_box()["height"] >= 44
    day(page, "Monday, October 19").click()
    day(page, "Thursday, October 22").click()
    page.get_by_role("button", name="Done").click()
    expect(sheet).to_have_count(0)
    assert page.input_value("#pf-start") == "2026-10-19" and page.input_value("#pf-end") == "2026-10-22"
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_no_browser_default_control_is_visible_on_the_intake(make, viewport):
    page = make(FAMILY, viewport=viewport)
    report = page.evaluate("""() => [...document.querySelectorAll('#pf-form select, #pf-form input[type=date], #pf-form input[type=time]')].map(n => {
        const r = n.getBoundingClientRect(), cs = getComputedStyle(n);
        return {name: n.name, w: r.width, h: r.height, opacity: cs.opacity, hidden: n.getAttribute('aria-hidden'), pointer: cs.pointerEvents,
                custom: !!(n.closest('label') || n.parentNode).querySelector('.ga-pick-btn, .ga-step')};
    })""")
    assert len(report) >= 7
    for c in report:
        assert c["w"] <= 1 and c["h"] <= 1 and c["opacity"] == "0" and c["hidden"] == "true" and c["pointer"] == "none", c
        assert c["custom"], c
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_reduced_motion_turns_the_picker_animation_off(make):
    page = make(DATES)
    page.get_by_role("button", name=re.compile("^From:")).click()
    assert page.evaluate("getComputedStyle(document.querySelector('.ga-pop')).animationName") == "none"


def test_a_click_on_the_stepper_label_goes_to_the_stepper_and_it_follows_the_form(make):
    page = make(DATES)
    page.locator("label.pf-field", has=page.locator("#pf-adults")).locator(".pf-lab").click()
    assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "Fewer adults"  # not the hidden select
    assert page.input_value("#pf-adults") == "2"
    # the form (or the browser restoring a value) changes the select: the stepper shows it
    page.evaluate("() => { const s = document.getElementById('pf-adults'); s.value = '5'; s.dispatchEvent(new Event('change', {bubbles: true})); }")
    expect(page.get_by_role("group", name=re.compile("^Adults")).locator(".ga-step-n")).to_have_text("5")


def test_a_server_error_shows_on_the_visible_control(make):
    page = make("/plan-for-me/start?where=Lisbon&start=2026-09-01&end=2026-09-03", signed_in=True)
    page.evaluate("document.getElementById('pf-form').noValidate = true")      # the browser would stop a past day before the server says so
    page.locator("#pf-go").click()
    page.wait_for_url("**/plan-for-me")
    page.wait_for_selector("html[data-ga-ready]")
    leaving = page.get_by_role("button", name=re.compile("^From:"))
    expect(leaving).to_have_attribute("aria-invalid", "true")
    assert "pf-err-start" in leaving.get_attribute("aria-describedby")


def test_a_new_leave_day_is_kept_with_the_old_return_day_however_the_picker_closes(make):
    for closer in ("Escape", "Done", "outside"):
        page = make(DATES)                              # leave Oct 16, back Oct 20
        page.get_by_role("button", name=re.compile("^From:")).click()
        day(page, "Saturday, October 17").click()
        if closer == "Escape":
            page.keyboard.press("Escape")
        elif closer == "Done":
            page.get_by_role("button", name="Done").click()
        else:
            page.mouse.click(5, 5)
        expect(page.get_by_role("dialog")).to_have_count(0)
        assert page.input_value("#pf-start") == "2026-10-17" and page.input_value("#pf-end") == "2026-10-20", closer


def test_day_buttons_stay_close_to_44px_on_the_narrowest_phone(make):
    page = make(DATES, viewport={"width": 320, "height": 640})
    page.get_by_role("button", name=re.compile("^From:")).click()
    box = day(page, "Friday, October 16").bounding_box()
    assert box["width"] >= 41 and box["height"] >= 44, box
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_a_phone_list_sheet_names_what_it_is_for(make):
    page = make(FAMILY, viewport=PHONE)
    page.get_by_role("button", name=re.compile("^Kid 1 age:")).click()
    title = page.locator(".ga-pop-title")
    expect(title).to_be_visible()
    expect(title).to_have_text("Kid 1 age")
    assert page.evaluate("getComputedStyle(document.querySelector('.ga-pop-title')).textTransform") == "uppercase"
