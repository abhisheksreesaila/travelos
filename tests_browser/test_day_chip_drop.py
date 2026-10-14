"""F-151: drag a plan onto a day chip to move it, in a real browser with a real mouse (at 1440 and 1280). While a plan is held the chips in the ink header take drops (the one under the
pointer shows a coral ring, the open day's chip does not); letting go on a chip moves the plan to that day at the same time, saved through the canvas's own write, with the toast
"Moved to Sat 17" and Undo, the plan leaving this day in place (no page load); a plan open in the panel sends the panel back to Up next. Esc mid-drag, a drop on the open day's chip, on
the header's empty space or back on the grid leave the plan (the grid moves its time as before); a plan landing among others sits beside them (lanes); a booking is not draggable;
a viewer cannot drag; a long trip's chips scroll when a plan is held near their end. Screenshots on request: F151_SHOTS=<folder>."""
import os
import re
import uuid

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests_browser.helpers import DESKTOP
from tests_browser.test_day_grid import SUNDAY, ari, now, open_day, plan
from tests_browser.test_day_mouse import block, center, drag, scroll_to, toast, ppm  # noqa: F401
from tests_browser.test_topbar import LAPTOP
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures

SATURDAY = SUNDAY - 1
DROP = re.compile(r"is-drop-target")


def shot(page, name):
    if os.environ.get("F151_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F151_SHOTS"], name))


@pytest.fixture(params=[DESKTOP, LAPTOP], ids=["1440", "1280"])
def desk(request, canvas_page):
    page = canvas_page(viewport=request.param, touch=False, motion="reduce")
    open_day(page, SUNDAY)
    return page


def chip(page, day):
    return page.locator(f'.cz-hchip[data-move-day="{day}"]')


def mid(page, loc):
    b = loc.bounding_box()
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


def lift(page, act, minute=12 * 60 + 30):
    """Press the plan with the mouse and move it far enough to lift it; the mouse is left down over the grid."""
    scroll_to(page, minute)
    x, y = center(page, act)
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 30, y + 30, steps=5)
    page.wait_for_selector(".cz-gb.is-held")
    return x, y


def day_of(act):
    return cal.get_activity(ari(), act).day


def lunch_on_sunday(desk, title="Lunch"):
    p = plan(title, 12 * 60, 13 * 60)
    desk.reload()
    desk.wait_for_selector("#cz-grid")
    return p


# ---- the chips take the drop -------------------------------------------------------------------------------------------------------

def test_a_held_plan_shows_which_chip_will_take_it_and_the_open_day_does_not_accept(desk):
    lunch = lunch_on_sunday(desk)
    lift(desk, lunch.id)
    expect(desk.locator(".cz-hchips.is-dropping")).to_be_visible()
    desk.mouse.move(*mid(desk, chip(desk, SATURDAY)), steps=6)
    expect(chip(desk, SATURDAY)).to_have_class(DROP)
    expect(desk.locator(".cz-g-label")).to_be_hidden()                                          # the ring says it: the label is not drawn over the header
    assert desk.locator(".cz-hchip.is-drop-target").count() == 1
    ring = chip(desk, SATURDAY).evaluate("n => getComputedStyle(n).boxShadow")
    assert "rgb(255, 115, 82)" in ring                                                          # the coral ring (--coral)
    shot(desk, "hover-chip.png")
    desk.mouse.move(*mid(desk, chip(desk, SUNDAY)), steps=4)                                    # the open day: no ring, no drop
    assert desk.locator(".cz-hchip.is-drop-target").count() == 0
    desk.mouse.move(*mid(desk, chip(desk, 3)), steps=4)
    expect(chip(desk, 3)).to_have_class(DROP)
    desk.mouse.up()
    desk.wait_for_function("() => !document.querySelector('.cz-hchips.is-dropping')")
    assert desk.locator(".cz-hchip.is-drop-target").count() == 0


def test_dropping_on_a_chip_moves_the_plan_to_that_day_at_the_same_time_in_place_and_undo_brings_it_back(desk):
    lunch = lunch_on_sunday(desk)
    desk.evaluate("window.__noReload = 7")
    lift(desk, lunch.id)
    desk.mouse.move(*mid(desk, chip(desk, SATURDAY)), steps=6)
    desk.mouse.up()
    expect(toast(desk)).to_contain_text("Moved to Sat 17")
    expect(toast(desk).get_by_role("button", name="Undo")).to_be_visible()
    shot(desk, "after-drop.png")
    expect(block(desk, lunch.id)).to_have_count(0)                                               # it left this day, in place
    assert desk.evaluate("window.__noReload") == 7                                               # (no page load)
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60) and day_of(lunch.id) == SATURDAY
    toast(desk).get_by_role("button", name="Undo").click()
    desk.wait_for_selector(f'.cz-gb[data-act="{lunch.id}"]')
    assert day_of(lunch.id) == SUNDAY and now(lunch.id)[:2] == (12 * 60, 13 * 60)
    assert desk.evaluate("window.__noReload") == 7


def test_the_plan_is_on_the_other_day_afterwards(desk):
    lunch = lunch_on_sunday(desk)
    lift(desk, lunch.id)
    desk.mouse.move(*mid(desk, chip(desk, SATURDAY)), steps=6)
    desk.mouse.up()
    expect(toast(desk)).to_contain_text("Moved to Sat 17")
    chip(desk, SATURDAY).click()
    desk.wait_for_selector(f'.cz-view[data-level=day][data-day="{SATURDAY}"]')
    expect(block(desk, lunch.id)).to_have_count(1)
    assert block(desk, lunch.id).get_attribute("data-s") == "720"


def test_a_plan_dropped_among_others_on_the_target_day_sits_beside_them(desk):
    lunch = lunch_on_sunday(desk)
    picnic = plan("Picnic", 12 * 60 + 30, 13 * 60 + 30, day=SATURDAY)
    lift(desk, lunch.id)
    desk.mouse.move(*mid(desk, chip(desk, SATURDAY)), steps=6)
    desk.mouse.up()
    expect(toast(desk)).to_contain_text("Moved to Sat 17")
    chip(desk, SATURDAY).click()
    desk.wait_for_selector(f'.cz-view[data-level=day][data-day="{SATURDAY}"]')
    a, b = block(desk, lunch.id).bounding_box(), block(desk, picnic.id).bounding_box()
    assert a["x"] + a["width"] <= b["x"] + 1 or b["x"] + b["width"] <= a["x"] + 1              # side by side, none hidden or refused
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60) and now(picnic.id)[:2] == (12 * 60 + 30, 13 * 60 + 30)


def test_a_plan_open_in_the_panel_sends_the_panel_back_to_up_next_when_it_is_moved(desk):
    lunch = lunch_on_sunday(desk)
    scroll_to(desk, 12 * 60 + 30)
    x, y = center(desk, lunch.id)
    desk.mouse.click(x, y)
    desk.wait_for_function("() => document.querySelector('#cz-dock').dataset.mode === 'plan'")
    desk.mouse.move(x, y)
    desk.mouse.down()
    desk.mouse.move(x + 30, y + 30, steps=5)
    desk.wait_for_selector(".cz-gb.is-held")
    desk.mouse.move(*mid(desk, chip(desk, SATURDAY)), steps=6)
    desk.mouse.up()
    expect(toast(desk)).to_contain_text("Moved to Sat 17")
    desk.wait_for_function("() => document.querySelector('#cz-dock').dataset.mode === 'idle'")
    expect(desk.locator("#cz-dock .cz-pp:not(.is-leaving)")).to_have_count(0)
    shot(desk, "panel-after-move.png")


def test_a_plan_open_in_the_panel_stays_there_when_another_plan_is_moved(desk):
    lunch = lunch_on_sunday(desk)
    tea = plan("Tea", 15 * 60, 16 * 60)
    desk.reload()
    desk.wait_for_selector("#cz-grid")
    scroll_to(desk, 13 * 60 + 30)
    x, y = center(desk, tea.id)
    desk.mouse.click(x, y)
    desk.wait_for_function("() => document.querySelector('#cz-dock').dataset.mode === 'plan'")
    lift(desk, lunch.id, 13 * 60)
    desk.mouse.move(*mid(desk, chip(desk, SATURDAY)), steps=6)
    desk.mouse.up()
    expect(toast(desk)).to_contain_text("Moved to Sat 17")
    assert desk.locator("#cz-dock").get_attribute("data-mode") == "plan"
    assert desk.locator("#cz-dock .cz-pp:not(.is-leaving)").get_attribute("data-act") == tea.id


def test_a_failed_save_brings_the_plan_back_with_a_toast(desk):
    lunch = lunch_on_sunday(desk)
    desk.route("**/trip/canvas/plan", lambda r: r.fulfill(status=500, body="boom"))
    lift(desk, lunch.id)
    desk.mouse.move(*mid(desk, chip(desk, SATURDAY)), steps=6)
    desk.mouse.up()
    expect(toast(desk)).to_contain_text("Could not save")
    desk.wait_for_function("(id) => { const b = document.querySelector('.cz-gb[data-act=\"' + id + '\"]'); return b && getComputedStyle(b).opacity === '1' && !b.getAnimations().length; }", arg=lunch.id)
    expect(block(desk, lunch.id)).to_be_visible()
    assert day_of(lunch.id) == SUNDAY and now(lunch.id)[:2] == (12 * 60, 13 * 60)


# ---- the plan stays ---------------------------------------------------------------------------------------------------------------

def test_escape_mid_drag_over_a_chip_leaves_the_plan_where_it_was(desk):
    lunch = lunch_on_sunday(desk)
    lift(desk, lunch.id)
    desk.mouse.move(*mid(desk, chip(desk, SATURDAY)), steps=6)
    expect(chip(desk, SATURDAY)).to_have_class(DROP)
    desk.keyboard.press("Escape")
    desk.wait_for_function("() => !document.querySelector('.cz-gb.is-held') && !document.querySelector('.cz-hchips.is-dropping')")
    desk.mouse.up()
    desk.wait_for_timeout(250)
    assert toast(desk).count() == 0 and day_of(lunch.id) == SUNDAY and now(lunch.id)[:2] == (12 * 60, 13 * 60)
    expect(block(desk, lunch.id)).to_have_count(1)


def test_dropping_on_the_open_days_chip_or_on_the_headers_empty_space_leaves_the_plan(desk):
    lunch = lunch_on_sunday(desk)
    lift(desk, lunch.id)
    desk.mouse.move(*mid(desk, chip(desk, SUNDAY)), steps=6)
    desk.mouse.up()
    desk.wait_for_timeout(300)
    assert toast(desk).count() == 0 and day_of(lunch.id) == SUNDAY and now(lunch.id)[:2] == (12 * 60, 13 * 60)
    lift(desk, lunch.id)
    head = desk.locator(".cz-head-text").bounding_box()
    desk.mouse.move(head["x"] + 40, head["y"] + head["height"] - 4, steps=6)                    # the heading's own words, not a chip
    desk.mouse.up()
    desk.wait_for_timeout(300)
    assert toast(desk).count() == 0 and day_of(lunch.id) == SUNDAY and now(lunch.id)[:2] == (12 * 60, 13 * 60)
    expect(block(desk, lunch.id)).to_have_count(1)


def test_dropping_back_on_the_grid_still_moves_its_time_as_before(desk):
    lunch = lunch_on_sunday(desk)
    x, y = lift(desk, lunch.id)
    desk.mouse.move(*mid(desk, chip(desk, SATURDAY)), steps=6)                                   # over a chip, then back down to the grid
    desk.mouse.move(x, y + 90, steps=10)
    assert desk.locator(".cz-hchip.is-drop-target").count() == 0
    desk.mouse.up()
    expect(toast(desk).get_by_role("button", name="Undo")).to_be_visible()
    desk.wait_for_function("(id) => { const b = document.querySelector('.cz-gb[data-act=\"' + id + '\"]'); return b && +b.dataset.s !== 720; }", arg=lunch.id)
    got = now(lunch.id)
    assert day_of(lunch.id) == SUNDAY and got[0] != 12 * 60 and got[1] - got[0] == 60              # (the grid moved its time; the length and the day stayed)


def test_a_booking_is_not_dragged_to_another_day(desk):
    desk.goto(desk.url.replace(f"day={SUNDAY}", "day=0"))
    desk.wait_for_selector('.cz-view[data-level=day][data-day="0"]')
    booked = desk.locator(".cz-gbk:not(.is-pill)")
    assert booked.count() > 0
    desk.evaluate("document.querySelector('.cz-day-body').scrollTop = 0")
    before = desk.locator(".cz-gb, .cz-gbk").count()
    b = booked.first.bounding_box()
    desk.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    desk.mouse.down()
    desk.mouse.move(*mid(desk, chip(desk, 1)), steps=8)
    assert desk.locator(".cz-hchip.is-drop-target").count() == 0 and desk.locator(".cz-hchips.is-dropping").count() == 0
    desk.mouse.up()
    desk.wait_for_timeout(300)
    assert toast(desk).count() == 0 and desk.locator(".cz-gb, .cz-gbk").count() == before


# ---- a viewer, a long trip --------------------------------------------------------------------------------------------------------

def test_a_viewer_cannot_drag_a_plan_to_a_chip(canvas_page, browser, base_url):
    owner = canvas_page(viewport=DESKTOP, touch=False, motion="reduce")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    mail = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    ctx = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
    try:
        ctx.set_default_timeout(9000)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day={SUNDAY}")
        page.wait_for_selector("#cz-grid")
        scroll_to(page, 12 * 60 + 30)
        x, y = center(page, lunch.id)
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 30, y + 30, steps=4)
        page.mouse.move(*mid(page, chip(page, SATURDAY)), steps=6)
        assert page.locator(".cz-hchips.is-dropping").count() == 0
        page.mouse.up()
        page.wait_for_timeout(300)
        assert page.locator(".ga-toast").count() == 0 and day_of(lunch.id) == SUNDAY
        # and the write itself is refused for a viewer
        r = page.context.request.post(f"{base_url}/trip/canvas/plan", form={"op": "edit", "act": lunch.id, "day": str(SATURDAY)}, headers={"X-Canvas": "1"})
        assert r.status == 403 and day_of(lunch.id) == SUNDAY
    finally:
        ctx.close()


def test_a_long_trips_chips_scroll_when_a_plan_is_held_near_their_end(browser, base_url):
    ctx = browser.new_context(viewport=LAPTOP, reduced_motion="reduce")
    ctx.set_default_timeout(6000)
    try:
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-23", "r": "2026-11-01", "a": "2", "k": "4,7"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day=0")
        expect(page.locator(".cz-hchip")).to_have_count(10)
        made = page.context.request.post(f"{base_url}/trip/canvas/plan", form={"op": "add", "day": "0", "start": str(12 * 60), "end": str(13 * 60), "title": "Lunch", "id": "a77"}, headers={"X-Canvas": "1"})
        assert made.status == 200, made.text()
        page.goto(f"{base_url}/trip/canvas?day=0")
        page.wait_for_selector('.cz-gb[data-act="a77"]')
        assert page.evaluate("() => { const n = document.querySelector('.cz-hchips'); return n.scrollWidth > n.clientWidth && n.scrollLeft === 0; }")
        scroll_to(page, 12 * 60 + 30)
        x, y = center(page, "a77")
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 30, y + 30, steps=4)
        nav = page.locator(".cz-hchips").bounding_box()
        page.mouse.move(nav["x"] + nav["width"] - 12, nav["y"] + nav["height"] / 2, steps=10)       # held near the end of the row
        page.wait_for_function("() => document.querySelector('.cz-hchips').scrollLeft > 20")
        left = page.evaluate("() => document.querySelector('.cz-hchips').scrollLeft")
        page.wait_for_timeout(250)
        assert page.evaluate("() => document.querySelector('.cz-hchips').scrollLeft") > left       # it keeps going while held
        page.mouse.move(nav["x"] + nav["width"] / 2, nav["y"] + nav["height"] / 2, steps=6)          # back to the middle: it stops
        page.wait_for_timeout(120)
        stop = page.evaluate("() => document.querySelector('.cz-hchips').scrollLeft")
        page.wait_for_timeout(200)
        assert page.evaluate("() => document.querySelector('.cz-hchips').scrollLeft") == stop
        page.mouse.move(nav["x"] + nav["width"] - 12, nav["y"] + nav["height"] / 2, steps=6)         # F-158: the tabs are wider, so hold at the end until the row reaches it
        page.wait_for_function("() => { const n = document.querySelector('.cz-hchips'); return n.scrollLeft + n.clientWidth >= n.scrollWidth - 2; }")
        far = page.locator('.cz-hchip[data-move-day="8"]')
        page.mouse.move(*mid(page, far), steps=4)
        expect(far).to_have_class(DROP)
        page.mouse.up()
        expect(page.locator(".ga-toast")).to_contain_text("Moved to")
        page.wait_for_selector('.cz-gb[data-act="a77"]', state="detached")
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    finally:
        ctx.close()
