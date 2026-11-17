"""F-293 (D-946..D-949) in a real browser: the secondary things are on demand. The trip's header holds one small "More" button; Plan together, Save plan and Share to Instagram are its rows,
not buttons at rest. The menu opens from the button, every row is a 48px target, Escape closes it with focus back on the button, a tap outside closes it, the arrow keys move through it, and
each row still does what its button did (the family's drawer, the saved sheet, the share sheet). On a phone only one bar floats at the bottom: the sections pill (the planner's own
Together and Save bar is gone). Set F293_SHOTS=1 for docs/report/f293-*.png."""
import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE, open_more
from tests_browser.test_planv2 import plan  # noqa: F401 (fixture: a page on /trip/plan for a family with a booked trip)

MORE, MENU = "#pl-more", "#pl-more-menu"
VIEWPORTS = pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])


@VIEWPORTS
def test_nothing_secondary_shows_at_rest_and_the_more_button_is_a_48px_target(plan, viewport):  # noqa: F811
    page = plan(viewport)
    expect(page.locator(MENU)).to_be_hidden()
    for gone in ("#pl-together", "#pl-save", "#sh-open"):
        expect(page.locator(gone)).to_be_hidden()
    box = page.locator(MORE).bounding_box()
    assert box["height"] >= 47.5 and box["width"] >= 47.5, box
    assert page.locator(MORE).inner_text().strip() == "More"


@VIEWPORTS
def test_more_opens_with_its_rows_as_48px_targets_and_escape_closes_it_with_focus_back_on_the_button(plan, viewport):  # noqa: F811
    page = plan(viewport)
    page.click(MORE)
    expect(page.locator(MENU)).to_be_visible()
    expect(page.locator(MORE)).to_have_attribute("aria-expanded", "true")
    rows = page.locator(f"{MENU} [role=menuitem]")
    assert [t.strip() for t in rows.all_inner_texts()] == ["Plan together", "Save plan", "Share to Instagram"]
    assert min(page.evaluate(f"[...document.querySelectorAll('{MENU} [role=menuitem]')].map(e => e.getBoundingClientRect().height)")) >= 47.5
    expect(rows.first).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(MENU)).to_be_hidden()
    expect(page.locator(MORE)).to_have_attribute("aria-expanded", "false")
    expect(page.locator(MORE)).to_be_focused()


def test_a_tap_outside_closes_it_and_the_arrow_keys_move_through_the_rows(plan):  # noqa: F811
    page = plan(DESKTOP)
    page.focus(MORE)
    page.keyboard.press("ArrowDown")
    expect(page.locator(MENU)).to_be_visible()
    rows = page.locator(f"{MENU} [role=menuitem]")
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("End")
    expect(rows.nth(2)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(rows.nth(0)).to_be_focused()
    page.mouse.click(700, 600)
    expect(page.locator(MENU)).to_be_hidden()


@VIEWPORTS
def test_plan_together_in_the_menu_opens_the_family_s_drawer(plan, viewport):  # noqa: F811
    page = plan(viewport)
    open_more(page, "#pl-together").click()
    expect(page.locator("#pl-side")).to_be_visible()
    expect(page.locator(MENU)).to_be_hidden()
    expect(page.locator("#pl-side .sd-sec h2", has_text="Who is in")).to_be_visible()


@VIEWPORTS
def test_save_plan_in_the_menu_reads_the_plan_back(plan, viewport):  # noqa: F811
    page = plan(viewport)
    open_more(page, "#pl-save").click()
    expect(page.locator("#pl-sheet")).to_be_visible()
    expect(page.locator("#pl-sheet .done-h b")).to_have_text("Plan saved")


@VIEWPORTS
def test_share_in_the_menu_opens_the_card_sheet_and_closing_it_returns_focus_to_more(plan, viewport):  # noqa: F811
    page = plan(viewport)
    open_more(page, "#sh-open").click()
    expect(page.locator(".sh-box")).to_be_visible()
    expect(page.locator(".sh-box h2")).to_have_text("Share to Instagram")
    page.keyboard.press("Escape")
    expect(page.locator(".sh-box")).to_have_count(0)
    expect(page.locator(MORE)).to_be_focused()


def test_on_a_phone_only_the_sections_pill_floats_at_the_bottom(plan):  # noqa: F811
    page = plan(PHONE)
    fixed = page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => {
        const s = getComputedStyle(e), r = e.getBoundingClientRect();
        return s.position === 'fixed' && s.visibility !== 'hidden' && s.display !== 'none' && r.width > 0 && r.height > 0 && r.top < innerHeight && r.bottom > innerHeight / 2;
    }).map(e => e.className)""")      # the sky and the scrim are not bars
    assert [c for c in fixed if not any(x in c for x in ("v2-bg", "pl-scrim", "ga-toast"))] == ["v2-sections v2-glass"], fixed
