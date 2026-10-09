"""F-103: a small Day | Week switch inside the heading, and the top of the day folds into one compact bar, in a real browser at 390 and 320.
The switch is a 2rem track with 44px sides, in the dark heading with no row of its own (the week has it too, in its plain heading). Scrolling the day away from its heading, filters and
dates brings in a compact sticky bar (the day's name, the small switch, SOS, map); scrolling back up or tapping the bar brings the top back. The bar takes no room, so nothing under
a finger moves, and it leaves its state alone while a block is held. Reduced motion: instant. Screenshots on request: F103_SHOTS=<folder> (day-top-390.png, day-folded-390.png)."""
import os

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE
from tests_browser.test_day_grid import SUNDAY, box, checks, fire, hold_block, open_day, plan, settle  # noqa: F401
from tests_browser.test_trip_canvas import NARROW, canvas_page, level, model  # noqa: F401 - fixtures


@pytest.fixture(params=[PHONE, NARROW], ids=["390", "320"])
def phone(request, canvas_page):
    return canvas_page(viewport=request.param)


@pytest.fixture
def day(phone):
    plan("Lunch", 12 * 60, 13 * 60)
    plan("Dinner", 18 * 60, 19 * 60 + 30)
    open_day(phone)
    return phone


def shot(page, name):
    if os.environ.get("F103_SHOTS") and page.viewport_size["width"] == 390:
        page.screenshot(path=os.path.join(os.environ["F103_SHOTS"], name))


def folded(page):
    return page.locator(".cz-fold").evaluate("e => e.classList.contains('is-on')")


def scroll_to(page, y):
    page.evaluate("y => window.scrollTo(0, y)", y)
    page.wait_for_function("y => Math.abs(window.scrollY - y) < 2 || window.scrollY + innerHeight >= document.documentElement.scrollHeight - 2", arg=y)
    page.wait_for_timeout(120)


def wait_folded(page, on):
    page.wait_for_function("on => document.querySelector('.cz-fold').classList.contains('is-on') === on", arg=on)


def test_a_phones_day_heading_has_the_named_way_back_and_no_switch(day):
    """F-134: "‹ Trip" at the left of the dark heading, 44px to tap, is the way up; the Day | Week switch stays on the week."""
    head, back = box(day, ".cz-head"), box(day, ".cz-head .cz-back")
    assert back["height"] >= 43.9 and back["width"] >= 43.9 and head["x"] <= back["x"] and back["y"] >= head["y"]
    assert day.locator(".cz-head .cz-back .cz-back-t").inner_text() == "Trip"
    assert not day.locator("#cz-z-week").is_visible() and not day.locator(".cz-head .cz-segs").is_visible()
    assert day.locator(".cz-head h1").bounding_box()["height"] > 0
    assert day.evaluate("() => { const h = document.querySelector('.cz-head h1'); return h.scrollWidth <= h.clientWidth + 1; }")      # the day's name is not cut off
    checks(day)


def test_back_goes_up_to_the_week_and_the_weeks_switch_comes_back_to_the_day(day):
    day.locator(".cz-head .cz-back").click()
    day.wait_for_selector(".cz-view[data-level=week]")
    settle(day)
    assert day.locator(".cz-head .cz-segs #cz-z-week").get_attribute("aria-current") == "page"
    shot(day, "week-390.png")
    assert day.locator(".cz-bar .cz-segs").count() == 0
    assert day.locator(".cz-fold").count() == 0                                 # the week keeps its full heading: no folded bar
    scroll_to(day, 400)
    assert box(day, ".cz-head")["y"] < 0 or day.evaluate("window.scrollY") > 100
    day.locator("#cz-z-day").click()
    day.wait_for_selector(".cz-view[data-level=day]")
    settle(day)
    assert level(day) == "day" and day.locator("#cz-z-day").get_attribute("aria-current") == "page"
    checks(day)


def test_the_week_heading_stays_whole_while_the_week_scrolls(canvas_page):
    page = canvas_page(viewport=PHONE)
    assert page.locator(".cz-fold").count() == 0 and page.locator(".cz-head .cz-segs").count() == 1
    page.evaluate("window.scrollTo(0, 600)")
    page.wait_for_timeout(150)
    assert page.locator(".cz-fold").count() == 0
    box_ = page.locator(".cz-head .cz-segs").bounding_box()
    assert box_["height"] <= 34
    checks(page)


def test_scrolling_the_day_folds_the_top_into_one_compact_bar_and_scrolling_back_opens_it(day):
    bar = day.locator(".cz-fold-bar")
    scroll_to(day, 0)                                                           # (a day with plans opens scrolled to them, so the bar is already there; start at the very top)
    wait_folded(day, False)
    assert day.locator(".cz-fold").get_attribute("inert") is not None and not bar.is_visible()
    assert box(day, ".cz-head")["y"] >= 0 and day.locator("#cz-title").is_visible()      # the whole top is there
    shot(day, "day-top-390.png")
    scroll_to(day, 700)
    wait_folded(day, True)
    assert bar.is_visible() and day.locator(".cz-fold").get_attribute("inert") is None
    b = bar.bounding_box()
    assert 0 <= b["y"] <= 12 and b["height"] < 80 and b["x"] >= 0 and b["x"] + b["width"] <= day.viewport_size["width"]      # one compact bar at the top
    assert bar.locator(".cz-fold-name").inner_text().startswith("Sunday")
    for part in (".cz-fold-back", ".cz-sos", ".cz-mapbtn"):
        pb = bar.locator(part).bounding_box()
        assert pb and pb["x"] >= b["x"] and pb["x"] + pb["width"] <= b["x"] + b["width"] + 0.5 and pb["height"] >= 43.9, part      # the switch, SOS and the map, each 44px to tap, none outside it (F-134: the way back, not the switch)
    nb = bar.locator(".cz-fold-name").bounding_box()
    assert nb["width"] > 40 and bar.locator(".cz-fold-name").evaluate("e => e.scrollWidth <= e.clientWidth + 1")      # the name is not cut off
    shot(day, "day-folded-390.png")
    # nothing on the page moved: the grid is where it was
    assert day.evaluate("() => document.querySelector('#cz-grid').getBoundingClientRect().top + scrollY") > 0
    checks(day)
    scroll_to(day, 0)
    wait_folded(day, False)
    expect(bar).to_be_hidden()
    assert day.locator(".cz-fold").get_attribute("inert") is not None


def test_folding_never_moves_the_grid_under_a_finger(day):
    before = day.evaluate("() => document.querySelector('#cz-grid').getBoundingClientRect().top + scrollY")
    scroll_to(day, 700)
    wait_folded(day, True)
    mid = day.evaluate("() => document.querySelector('#cz-grid').getBoundingClientRect().top + scrollY")
    scroll_to(day, 0)
    wait_folded(day, False)
    assert before == mid == day.evaluate("() => document.querySelector('#cz-grid').getBoundingClientRect().top + scrollY")


def test_tapping_the_bar_opens_the_top_again(day):
    scroll_to(day, 900)
    wait_folded(day, True)
    day.locator(".cz-fold-name").click()
    day.wait_for_function("window.scrollY < 4")
    wait_folded(day, False)
    assert day.locator("#cz-title").is_visible()
    assert day.evaluate("document.activeElement.id") == "cz-title"
    scroll_to(day, 900)
    wait_folded(day, True)
    b = box(day, ".cz-fold-bar")
    assert day.evaluate("([x, y]) => document.elementFromPoint(x, y).className", [b["x"] + 5, b["y"] + b["height"] / 2]) == "cz-fold-bar"      # the padding at its left end: bare bar
    day.mouse.click(b["x"] + 5, b["y"] + b["height"] / 2)                       # a bare part of the bar works too
    day.wait_for_function("window.scrollY < 4")


def test_back_sos_and_map_in_the_folded_bar_work_directly(day):
    scroll_to(day, 900)
    wait_folded(day, True)
    assert day.locator(".cz-fold-bar .cz-mapbtn").get_attribute("href") == f"/trip/map?day={SUNDAY}"
    day.locator(".cz-fold-bar .cz-sos").click()
    expect(day.locator(".cz-sheet-sos")).to_be_visible()
    y = day.evaluate("scrollY")
    day.locator(".cz-sheet-wrap .cz-close").first.click()
    expect(day.locator(".cz-sheet-sos")).to_have_count(0)
    assert abs(day.evaluate("scrollY") - y) < 3                                 # closing does not jump up to the heading's SOS
    day.locator(".cz-fold-bar .cz-fold-back").click()                           # "‹ Trip", from the folded bar
    day.wait_for_selector(".cz-view[data-level=week]")
    settle(day)
    assert level(day) == "week"
    day.locator("#cz-z-day").click()                                            # and Day from the week's heading, back to the same kind of day
    day.wait_for_selector(".cz-view[data-level=day]")
    settle(day)
    assert day.locator(".cz-fold").count() == 1


def test_a_held_block_keeps_the_bar_as_it_is_and_it_catches_up_when_the_hold_ends(phone):
    act = plan("Lunch", 12 * 60, 13 * 60).id
    plan("Dinner", 18 * 60, 19 * 60)
    open_day(phone)
    scroll_to(phone, 700)
    wait_folded(phone, True)
    hold_block(phone, act)
    assert phone.evaluate("CZ.held") is True
    phone.evaluate("window.scrollTo(0, 0)")                                     # the page goes back to the top while the finger still holds
    phone.wait_for_timeout(250)
    assert folded(phone) is True                                                # not folded or unfolded mid-hold: the bar stays as it was
    fire(phone, "pointercancel", 200, 300)                                      # the hold ends
    wait_folded(phone, False)                                                   # and the bar catches up with where the page is


def test_a_title_field_being_typed_keeps_the_bar_as_it_is(phone):
    plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    scroll_to(phone, 700)
    wait_folded(phone, True)
    phone.evaluate("CZ.editing = () => true")                                   # what day_new.js answers while a new plan's title is open
    phone.evaluate("window.scrollTo(0, 0)")
    phone.wait_for_timeout(250)
    assert folded(phone) is True
    phone.evaluate("CZ.editing = () => false")
    phone.evaluate("window.scrollTo(0, 1)")
    wait_folded(phone, False)


def test_the_bar_just_appears_with_a_short_fade_and_at_once_under_reduced_motion(canvas_page):
    page = canvas_page(viewport=PHONE, motion="no-preference")
    plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    css = "e => { const s = getComputedStyle(e); return [s.transitionProperty, s.transitionDuration]; }"
    props, dur = page.locator(".cz-fold-bar").evaluate(css)
    assert "opacity" in props and "transform" not in props and "height" not in props and "top" not in props      # F-117: a short fade, it does not slide in
    assert dur.split(",")[0] != "0s"
    page.emulate_media(reduced_motion="reduce")
    props, dur = page.locator(".cz-fold-bar").evaluate(css)
    assert set(dur.replace(" ", "").split(",")) == {"0s"}                        # reduced motion: instant
    scroll_to(page, 900)
    wait_folded(page, True)
    expect(page.locator(".cz-fold-bar")).to_be_visible()
    page.locator(".cz-fold-name").click()
    page.wait_for_function("window.scrollY < 4")                                # the tap scrolls at once


def test_a_laptop_gets_the_bar_too(canvas_page):
    page = canvas_page(viewport={"width": 1280, "height": 800}, touch=False)
    plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    scroll_to(page, 1200)
    wait_folded(page, True)
    expect(page.locator(".cz-fold-bar")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
