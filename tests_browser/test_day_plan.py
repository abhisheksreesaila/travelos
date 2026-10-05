"""F-090: the plan of the day in a real browser at 390 and 320. Flick left and right between days (synthetic touch pointers), the dates across the top, the
slide's direction, a held step still drags instead of flicking, bookings as quiet lines, "Change this day" and an empty day's Talk and Paste, phone checks,
and screenshots on request (F090_SHOTS=<folder>)."""
import os
import re

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE
from tests_browser.test_trip_canvas import NARROW, canvas_page, checks, model, settle  # noqa: F401 - fixtures


def flick(page, dx, dy=0, y=420, x=None, ms_steps=6):
    """One finger from (x, y) moving by (dx, dy), then lifting."""
    page.evaluate("""([x, y, dx, dy, n]) => { const el = document.elementFromPoint(x, y) || document.getElementById('cz');
      const fire = (type, px, py) => el.dispatchEvent(new PointerEvent(type, { pointerId: 7, pointerType: 'touch', clientX: px, clientY: py, bubbles: true, cancelable: true, isPrimary: true }));
      fire('pointerdown', x, y);
      for (let i = 1; i <= n; i++) fire('pointermove', x + dx * i / n, y + dy * i / n);
      fire('pointerup', x + dx, y + dy); }""", [x if x is not None else (195 if dx < 0 else 120), y, dx, dy, ms_steps])


def day_of(page):
    return page.locator(".cz-view").get_attribute("data-day")


def open_day(page, n):
    page.goto(re.sub(r"^(https?://[^/]+).*", lambda m: f"{m.group(1)}/trip/canvas?day={n}", page.url))
    page.wait_for_selector(f".cz-view[data-level=day][data-day='{n}']")


def test_a_flick_left_is_the_next_day_and_right_the_previous_one(canvas_page):
    page = canvas_page()
    open_day(page, 1)
    flick(page, -160)
    expect(page.locator(".cz-view")).to_have_attribute("data-day", "2")
    assert re.search(r"day=2", page.url)
    flick(page, 160)
    expect(page.locator(".cz-view")).to_have_attribute("data-day", "1")
    flick(page, 160)
    expect(page.locator(".cz-view")).to_have_attribute("data-day", "0")
    flick(page, 160)                       # nothing before the first day
    page.wait_for_timeout(300)
    assert day_of(page) == "0"


def test_a_short_or_mostly_vertical_move_is_not_a_flick(canvas_page):
    page = canvas_page()
    open_day(page, 1)
    flick(page, -30)
    flick(page, -90, dy=140)
    page.wait_for_timeout(300)
    assert day_of(page) == "1"


def test_the_last_day_does_not_flick_further(canvas_page):
    page = canvas_page()
    open_day(page, 4)
    flick(page, -160)
    page.wait_for_timeout(300)
    assert day_of(page) == "4"


def test_tapping_a_date_opens_it_and_keeps_it_in_view(canvas_page):
    page = canvas_page()
    open_day(page, 0)
    pills = page.locator("#cz-dpills .cz-dp:not(.cz-dp-week)")
    assert pills.count() == 5
    pills.nth(3).click()
    expect(page.locator(".cz-view")).to_have_attribute("data-day", "3")
    expect(page.locator("#cz-dpills .cz-dp.is-open")).to_have_attribute("aria-current", "date")
    box, bar = page.locator("#cz-dpills .is-open").bounding_box(), page.locator("#cz-dpills").bounding_box()
    assert box["x"] >= bar["x"] - 1 and box["x"] + box["width"] <= bar["x"] + bar["width"] + 1
    page.locator("#cz-z-week").click()
    expect(page.locator(".cz-view")).to_have_attribute("data-level", "week")


def test_the_slide_runs_the_way_the_days_go(canvas_page):
    page = canvas_page(motion="no-preference")
    open_day(page, 1)
    if not page.evaluate("typeof document.startViewTransition === 'function'"):
        pytest.skip("no View Transitions in this browser")
    flick(page, -160)
    expect(page.locator(".cz-view")).to_have_attribute("data-day", "2")
    settle(page)
    page.locator("#cz-dpills .cz-dp:not(.cz-dp-week)").nth(0).click()
    expect(page.locator(".cz-view")).to_have_attribute("data-day", "0")
    settle(page)
    assert page.evaluate("window.__vt.dir").count("next") == 1 and page.evaluate("window.__vt.dir")[-1] == "prev"


def test_holding_a_step_still_drags_it_and_does_not_flick(canvas_page):
    page = canvas_page()
    open_day(page, 1)
    chip = page.locator("[data-drag]").first
    b = chip.bounding_box()
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    page.evaluate("""([x, y]) => { const el = document.elementFromPoint(x, y);
      el.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 9, pointerType: 'touch', clientX: x, clientY: y, bubbles: true, isPrimary: true })); }""", [x, y])
    page.wait_for_timeout(500)
    assert page.locator("#cz.cz-dragging").count() == 1
    page.evaluate("""([x, y]) => { for (let i = 1; i <= 6; i++) document.dispatchEvent(new PointerEvent('pointermove', { pointerId: 9, pointerType: 'touch', clientX: x - 25 * i, clientY: y, bubbles: true }));
      document.dispatchEvent(new PointerEvent('pointercancel', { pointerId: 9, pointerType: 'touch', clientX: x - 150, clientY: y, bubbles: true })); }""", [x, y])
    page.wait_for_timeout(300)
    assert day_of(page) == "1"


def test_bookings_are_quiet_and_their_line_opens_help(canvas_page):
    page = canvas_page()
    open_day(page, 0)
    lines = page.locator(".cz-bk")
    assert lines.count() == 2
    assert page.locator("#cz-empty").is_visible()
    lines.nth(1).click()
    page.wait_for_url(re.compile(r"/trip/help"))


def test_change_this_day_and_an_empty_days_talk_and_paste_open_ask_on_that_day(canvas_page):
    page = canvas_page()
    open_day(page, 1)
    page.locator("#cz-say").click()
    page.wait_for_url(re.compile(r"/trip/ask\?day=1"))
    open_day(page, 2)
    page.locator("#cz-say-talk").click()
    page.wait_for_url(re.compile(r"/trip/ask\?day=2&mode=talk"))
    open_day(page, 2)
    page.locator("#cz-say-paste").click()
    page.wait_for_url(re.compile(r"/trip/ask\?day=2&mode=paste"))


def test_every_day_fits_at_390_and_320(canvas_page):
    page = canvas_page()
    for size in (PHONE, NARROW):
        page.set_viewport_size(size)
        for n in range(5):
            open_day(page, n)
            checks(page)


@pytest.mark.skipif(not os.environ.get("F090_SHOTS"), reason="screenshots are made on request: F090_SHOTS=<folder>")
def test_screenshots(canvas_page):
    out = os.environ["F090_SHOTS"]
    page = canvas_page()
    for n in range(5):
        open_day(page, n)
        page.screenshot(path=os.path.join(out, f"day{n}-390.png"), full_page=True)
    page.set_viewport_size({"width": 1280, "height": 800})
    open_day(page, 1)
    page.screenshot(path=os.path.join(out, "day1-1280.png"), full_page=True)
