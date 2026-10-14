"""F-140: the desktop day in a real browser. From 1020px up the day is two columns (the ink header with the five day chips, the filters with Paste a plan and Say the plan, and the hour
grid on the left; the docked panel on the right), nothing but the grid and the panel scrolls, the page itself never does at 1440x900 and 1280x800, the grid opens at 7 AM (or at now with
the coral line during the trip), the panel shows Up next, Later today and Ask, and the chips and Day | Week move between levels without a page load. 1000 (tablet) and 390 (phone) keep
their own day. Screenshots on request: F140_SHOTS=<folder>."""
import os
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect

from gitaway import catalog, tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_topbar import LAPTOP, TABLET, signed_in  # noqa: F401 - fixture

SAT_NOON = datetime(2026, 10, 17, 19, 40, tzinfo=timezone.utc)      # Saturday 12:40 PM in Los Angeles: day 1

NO_SCROLL = "[document.documentElement.scrollWidth <= document.documentElement.clientWidth, document.documentElement.scrollHeight <= document.documentElement.clientHeight, window.scrollY]"


def at(monkeypatch, utc):
    monkeypatch.setattr(catalog, "now_utc", lambda: utc)
    monkeypatch.setattr(catalog, "today", lambda: utc.astimezone(catalog.TZ).date())


def shot(page, name):
    if os.environ.get("F140_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F140_SHOTS"], name))


def plans():
    me = person("ari")
    cal.add_activity(me, day=1, start=18 * 60, end=19 * 60, title="Dinner at CityWalk", kind="food")
    cal.add_activity(me, day=1, start=20 * 60, end=21 * 60, title="Late show", kind="fun")


def box(page, sel):
    return page.locator(sel).bounding_box()


@pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])
def test_two_columns_and_the_page_does_not_scroll(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=1")
    expect(page.locator("#cz-dock")).to_be_visible()
    grid, dock, head = box(page, ".cz-day-body"), box(page, "#cz-dock"), box(page, ".cz-head")
    assert grid["x"] + grid["width"] < dock["x"] and head["x"] + head["width"] <= dock["x"]      # the header is over the grid, the panel on the right
    assert dock["y"] < head["y"] + head["height"]                                               # and starts at the top, level with the header
    assert page.evaluate(NO_SCROLL) == [True, True, 0]
    page.mouse.move(grid["x"] + 100, grid["y"] + 100)
    page.mouse.wheel(0, 600)
    page.wait_for_timeout(100)
    assert page.evaluate("window.scrollY") == 0 and page.evaluate("document.querySelector('.cz-day-body').scrollTop") > 0      # only the grid scrolled
    assert page.evaluate("getComputedStyle(document.querySelector('.cz-dock-body')).overflowY") == "auto"
    assert box(page, ".ga-topbar")["y"] == 0


@pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])
def test_the_week_does_not_scroll_the_page_either(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas")
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    assert page.evaluate(NO_SCROLL) == [True, True, 0]
    assert page.locator(".cz-level-week .cz-head .cz-sos").is_hidden()      # the top bar has SOS


def test_the_header_chips_filters_and_buttons(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas?day=1")
    chips = page.locator(".cz-head .cz-hchip")
    expect(chips).to_have_count(5)
    expect(page.locator(".cz-head .cz-hchip.is-open")).to_contain_text("17")
    assert page.locator(".cz-head .cz-back").is_hidden() and page.locator(".cz-head .cz-sos").is_hidden()
    expect(page.locator("#cz-z-day")).to_be_visible()
    expect(page.locator("#cz-z-week")).to_be_visible()
    expect(page.locator(".cz-strip")).to_be_hidden()
    expect(page.locator(".cz-bar").get_by_text("Paste a plan")).to_be_visible()
    expect(page.locator(".cz-bar").get_by_text("Say the plan")).to_be_visible()
    shot(page, "day-before-1440.png")


def test_the_grid_opens_at_7_am_before_the_trip(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas?day=1")
    page.wait_for_function("document.querySelector('.cz-day-body')")
    first = page.evaluate("""() => { const s = document.querySelector('.cz-day-body').getBoundingClientRect(), h = [...document.querySelectorAll('.cz-g-hour')].find(e => e.textContent.trim() === '7 AM').getBoundingClientRect();
        return [h.top - s.top, h.bottom <= s.bottom] }""")
    assert 0 <= first[0] < 60 and first[1]
    assert page.locator("#cz-nowline").count() == 0


@pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])
def test_during_the_trip_the_grid_opens_at_now_with_the_coral_line_and_the_panel_shows_what_is_next(signed_in, monkeypatch, viewport):
    at(monkeypatch, SAT_NOON)
    page = signed_in(viewport, path="/trip/canvas?day=1")
    plans()
    page.reload()
    line = page.locator("#cz-nowline")
    expect(line).to_be_visible()
    inside = page.evaluate("""() => { const s = document.querySelector('.cz-day-body').getBoundingClientRect(), l = document.querySelector('#cz-nowline').getBoundingClientRect(); return l.top > s.top && l.bottom < s.bottom }""")
    assert inside
    dock = page.locator("#cz-dock")
    expect(dock.locator("#cz-up")).to_contain_text("UP NEXT")
    expect(dock.locator("#cz-later")).to_contain_text("Later today")
    expect(dock.locator("#cz-up")).to_contain_text("Dinner at CityWalk")
    expect(dock.locator("#cz-later")).to_contain_text("Late show")
    expect(dock.locator("#cz-dock-ask")).to_be_visible()
    assert page.evaluate(NO_SCROLL) == [True, True, 0]
    shot(page, f"day-during-{viewport['width']}.png")


def test_open_the_plan_opens_a_plain_plans_card(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas?day=2")
    cal.add_activity(person("ari"), day=2, start=10 * 60, end=11 * 60, title="Slow breakfast", kind="food")
    page.reload()
    up = page.locator("#cz-up")
    expect(up).to_contain_text("FIRST UP")
    expect(up).to_contain_text("Slow breakfast")
    page.locator("#cz-up-open").click()
    expect(page.locator(".cz-card")).to_be_visible()


def test_with_nothing_up_next_it_says_so_and_shows_ask(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas?day=2")
    expect(page.locator("#cz-up")).to_contain_text("Nothing up next")
    expect(page.locator("#cz-dock-ask")).to_be_visible()
    tabs = page.locator("#cz-dock .cz-dock-tab")
    expect(tabs).to_have_text(["Plan", "Family", "Ask"])
    assert page.locator("#cz-dock").get_attribute("data-mode") == "idle"
    shot(page, "day-empty-1440.png")


def test_the_panel_tabs_go_to_family_and_ask(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas?day=1")
    page.locator("#cz-dock .cz-dock-tab", has_text="Family").click()
    page.wait_for_url("**/trip/family")
    page.go_back()
    page.locator("#cz-dock .cz-dock-tab", has_text="Ask").click()
    page.wait_for_url("**/trip/ask?day=1*")


def test_the_chips_and_day_week_move_between_levels_without_a_page_load(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas?day=1")
    page.evaluate("window.__marker = 1")
    page.locator(".cz-head .cz-hchip", has_text="MON").click()
    page.wait_for_selector(".cz-view[data-level=day][data-day='3']")
    expect(page.locator("#cz-title")).to_have_text("Monday")
    expect(page.locator("#cz-dock")).to_be_visible()
    assert page.evaluate("window.__marker") == 1 and page.evaluate(NO_SCROLL) == [True, True, 0]
    page.locator("#cz-z-week").click()
    page.wait_for_selector(".cz-view[data-level=week]")
    assert page.evaluate("window.__marker") == 1 and page.locator("#cz-dock").count() == 0
    page.locator("#cz-z-day").click()
    page.wait_for_selector(".cz-view[data-level=day]")
    expect(page.locator("#cz-dock")).to_be_visible()
    assert page.evaluate("window.__marker") == 1


def test_the_chips_use_the_liquid_zoom(signed_in):
    """With motion on, a chip moves between days inside a View Transition (the existing zoom), not a plain page change."""
    page = signed_in(DESKTOP, path="/trip/canvas?day=1")
    page.evaluate("window.__vt = 0; const s = document.startViewTransition && document.startViewTransition.bind(document); if (s) document.startViewTransition = function () { window.__vt++; return s.apply(document, arguments); }")
    page.locator(".cz-head .cz-hchip", has_text="MON").click()
    page.wait_for_selector(".cz-view[data-level=day][data-day='3']")
    assert page.evaluate("window.__vt") >= 1 or page.evaluate("!document.startViewTransition")


@pytest.mark.parametrize("viewport,name", [(TABLET, "1000"), (PHONE, "390")], ids=["tablet", "phone"])
def test_the_tablet_and_the_phone_keep_their_day(signed_in, viewport, name):
    page = signed_in({"width": 1000, "height": 800} if name == "1000" else viewport, path="/trip/canvas?day=1")
    expect(page.locator("#cz-dock")).to_be_hidden()
    expect(page.locator(".cz-hchip").first).to_be_hidden()
    expect(page.locator(".cz-desk-say")).to_be_hidden()
    assert page.evaluate("document.documentElement.scrollHeight > document.documentElement.clientHeight")      # the page scrolls as before
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    shot(page, f"day-{name}.png")
