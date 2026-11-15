"""F-255 in a real browser: the v2 top bar's sections pill and avatar menu. The menu opens on the avatar and closes on Escape (focus back on the avatar), on a tap outside and with Tab; the
arrow keys move through it; Sign out ends the session. At 390 the pill floats at the bottom; every control is a 48px target and every word reads 4.5:1 over the frosted glass, in light and
dark (dark is the person's choice in localStorage `ga-mode`, set by the `plan` fixture's scheme). Set F255_SHOTS=1 for docs/report/f255-*.png."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit
from tests_browser.test_planv2 import plan  # noqa: F401 (fixture: a page on /trip/plan for a family with a booked trip)

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
ME, MENU = "#v2-me", "#v2-menu"


def shot(page, name):
    if os.environ.get("F255_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f255-{name}.png"))


def test_the_pill_marks_plan_and_leads_to_book_and_guides(plan):  # noqa: F811
    page = plan(DESKTOP)
    pill = page.locator(".v2-sections")
    expect(pill.locator("a")).to_have_text(["Book", "Plan", "Guides"])      # F-262: Family left the bar
    expect(pill.locator("a[aria-current='page']")).to_have_text(["Plan"])
    pill.get_by_text("Guides").click()
    page.wait_for_url("**/guides")
    expect(page.locator(".v2-sections a[aria-current='page']")).to_have_text(["Guides"])


def test_the_avatar_opens_the_menu_and_escape_closes_it_with_focus_back_on_the_avatar(plan):  # noqa: F811
    page = plan(DESKTOP)
    expect(page.locator(MENU)).to_be_hidden()
    expect(page.locator(ME)).to_have_attribute("aria-expanded", "false")
    page.click(ME)
    expect(page.locator(MENU)).to_be_visible()
    expect(page.locator(ME)).to_have_attribute("aria-expanded", "true")
    expect(page.locator(f"{MENU} [role=menuitem]")).to_have_text(["Family members", "Help · who to call", "Sign out"])      # F-262: the family stays one tap away in the menu; F-254: and so does Help
    expect(page.locator(f"{MENU} a").first).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(MENU)).to_be_hidden()
    expect(page.locator(ME)).to_be_focused()
    expect(page.locator(ME)).to_have_attribute("aria-expanded", "false")


def test_a_tap_outside_closes_it_and_a_second_tap_on_the_avatar_does_too(plan):  # noqa: F811
    page = plan(DESKTOP)
    page.click(ME)
    expect(page.locator(MENU)).to_be_visible()
    page.mouse.click(640, 8)      # the empty sky above the bar (a click on the calendar would open its editor)
    expect(page.locator(MENU)).to_be_hidden()
    page.click(ME)
    expect(page.locator(MENU)).to_be_visible()
    page.click(ME)
    expect(page.locator(MENU)).to_be_hidden()


def test_the_keyboard_opens_walks_and_leaves_the_menu(plan):  # noqa: F811
    page = plan(DESKTOP)
    page.focus(ME)
    page.keyboard.press("Enter")
    expect(page.locator(f"{MENU} a").first).to_be_focused()
    page.keyboard.press("ArrowDown")      # F-262, F-254: the menu is two links (Family members, Help) and Sign out
    expect(page.locator(f"{MENU} a").nth(1)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(page.locator(f"{MENU} button")).to_be_focused()
    page.keyboard.press("Home")
    expect(page.locator(f"{MENU} a").first).to_be_focused()
    page.keyboard.press("End")
    expect(page.locator(f"{MENU} button")).to_be_focused()
    page.keyboard.press("ArrowDown")      # wraps to the first
    expect(page.locator(f"{MENU} a").first).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(page.locator(f"{MENU} button")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator(MENU)).to_be_hidden()


def test_sign_out_ends_the_session(plan, base_url):  # noqa: F811
    page = plan(DESKTOP)
    page.click(ME)
    page.get_by_role("menuitem", name="Sign out").click()
    page.wait_for_load_state()
    page.goto(f"{base_url}/trip/plan")
    expect(page.locator(ME)).to_have_count(0)
    expect(page.get_by_text("Sign in").first).to_be_visible()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_targets_are_48px_and_every_word_reads_over_the_glass_with_the_menu_open(plan, viewport, scheme):  # noqa: F811
    page = plan(viewport, scheme)
    name = f"{viewport['width']}{'-dark' if scheme == 'dark' else ''}"
    shot(page, f"{name}-plan")
    sizes = page.evaluate("[...document.querySelectorAll('.v2-sections a, #v2-me, #ga-mode-v2')].map(e => { const r = e.getBoundingClientRect(); return Math.min(r.width, r.height); })")
    floor = 48 if viewport["width"] < 720 else 44
    assert min(sizes) >= floor - 0.5, sizes
    page.click(ME)
    expect(page.locator(MENU)).to_be_visible()
    page.wait_for_timeout(400)
    shot(page, f"{name}-menu")
    small = page.evaluate("[...document.querySelectorAll('#v2-menu [role=menuitem]')].map(e => e.getBoundingClientRect().height)")
    assert min(small) >= 47.5, small
    m = audit(page)
    ours = lambda rows: [r for r in rows if any(w in r for w in ("Plan", "Book", "Guides", "Family", "Sign out"))]      # noqa: E731
    assert ours(m["low"]) == [] and m["glass"] == [] and m["wide"] <= 1, m
    assert [s for s in m["small"] if "Plan" in s or "Book" in s or "Guides" in s or "Family" in s or "Sign out" in s] == [], m["small"]


def test_on_a_phone_the_pill_floats_at_the_bottom_above_the_safe_area_and_the_avatar_stays_top_right(plan):  # noqa: F811
    page = plan(PHONE)
    box = page.locator(".v2-sections").bounding_box()
    assert box["y"] + box["height"] > 844 - 24 and box["y"] + box["height"] <= 844 - 8
    for label in ("Book", "Plan", "Guides"):      # nothing covers it: the calendar's own dock rides above the pill, and a tap on each word lands on that link
        assert page.evaluate("t => { const a = [...document.querySelectorAll('.v2-sections a')].find(a => a.textContent === t), r = a.getBoundingClientRect(); return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === a; }", label), label
    dock = page.locator(".dock").bounding_box()
    assert dock["y"] + dock["height"] <= box["y"], (dock, box)
    me = page.locator(ME).bounding_box()
    assert me["y"] < 80 and me["x"] + me["width"] > 390 - 40
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
