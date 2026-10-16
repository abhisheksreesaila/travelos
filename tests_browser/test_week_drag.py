"""F-157: move a plan on the desktop week, in a real browser with a real mouse (at 1440 and 1280). Pressing a plan row and pulling it past the drag distance lifts it; the column under the
pointer shows it takes the drop (a coral ring), its own column does not; letting go moves the plan to that day at the same time, through the canvas's own write, with the toast "Moved to
Sat 17" and Undo, the row appearing in the new column in time order, in place (no page load). A click still opens the day with the plan in the panel. Esc, or a drop on its own column or
outside the columns, leaves it. Bookings, viewers and the phone and tablet week do not drag; a long trip's week scrolls sideways when the pointer holds near its edge. Screenshots on
request: F157_SHOTS=<folder>."""
import os
import re
import uuid

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_day_grid import SUNDAY, ari, now, plan
from tests_browser.test_topbar import LAPTOP
from tests_browser.test_trip_canvas import canvas_page, model, settle  # noqa: F401 - fixtures

SATURDAY = SUNDAY - 1
DROP = re.compile(r"is-drop-target")
TABLET = {"width": 1000, "height": 800}


def shot(page, name):
    if os.environ.get("F157_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F157_SHOTS"], name))


@pytest.fixture(params=[DESKTOP, LAPTOP], ids=["1440", "1280"])
def desk(request, canvas_page):
    page = canvas_page(viewport=request.param, touch=False, motion="reduce")
    plan("Lunch", 12 * 60, 13 * 60)
    page.reload()
    page.wait_for_selector("#cz-wk")
    return page


def row(page, act):
    return page.locator(f'.cz-wk .cz-wi[data-wk-act="{act}"]')


def col(page, day):
    return page.locator(f'.cz-wcol[data-day="{day}"]')


def mid(loc):
    b = loc.bounding_box()
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


def day_of(act):
    return cal.get_activity(ari(), act).day


def lift(page, act):
    """Press the plan row and pull it clear of where it was; the mouse is left down."""
    x, y = mid(row(page, act))
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 20, y + 20, steps=5)
    page.wait_for_selector(".cz-wi-copy")
    return x, y


def lunch(page):
    return page.locator(".cz-wcol .cz-wi[data-wk-act]", has_text="Lunch").first.get_attribute("data-wk-act")


def test_a_lifted_plan_shows_which_column_takes_it_and_its_own_column_does_not(desk):
    act = lunch(desk)
    lift(desk, act)
    expect(desk.locator(".cz-wi.is-lifted")).to_have_count(1)
    assert desk.locator(".cz-wcol.is-drop-target").count() == 0                              # still over its own column
    desk.mouse.move(*mid(col(desk, SATURDAY)), steps=6)
    expect(col(desk, SATURDAY)).to_have_class(DROP)
    assert desk.locator(".cz-wcol.is-drop-target").count() == 1
    assert "rgb(255, 115, 82)" in col(desk, SATURDAY).evaluate("n => getComputedStyle(n).boxShadow")      # the coral ring
    shot(desk, "dragging.png")
    desk.mouse.move(*mid(col(desk, SUNDAY)), steps=6)                                         # back over its own column: no ring
    assert desk.locator(".cz-wcol.is-drop-target").count() == 0
    desk.mouse.move(*mid(col(desk, 4)), steps=6)
    expect(col(desk, 4)).to_have_class(DROP)
    desk.mouse.up()
    desk.wait_for_function("() => !document.querySelector('.cz-wi-copy, .is-drop-target')")


def test_dropping_on_a_column_moves_the_plan_there_at_the_same_time_in_time_order_in_place_and_undo_puts_it_back(desk):
    act = lunch(desk)
    early = plan("Breakfast", 8 * 60, 9 * 60, day=SATURDAY)
    late = plan("Dinner", 18 * 60, 19 * 60, day=SATURDAY)
    desk.reload()
    desk.wait_for_selector("#cz-wk")
    desk.evaluate("window.__noReload = 7")
    lift(desk, act)
    desk.mouse.move(*mid(col(desk, SATURDAY)), steps=6)
    desk.mouse.up()
    expect(desk.locator(".ga-toast")).to_contain_text("Moved to Sat 17")
    expect(desk.locator(".ga-toast").get_by_role("button", name="Undo")).to_be_visible()
    shot(desk, "after-drop.png")
    expect(col(desk, SATURDAY).locator(f'.cz-wi[data-wk-act="{act}"]')).to_have_count(1)
    expect(col(desk, SUNDAY).locator(f'.cz-wi[data-wk-act="{act}"]')).to_have_count(0)
    order = col(desk, SATURDAY).locator(".cz-wi[data-wk-act]").evaluate_all("ns => ns.map(n => n.dataset.wkAct)")
    assert order.index(early.id) < order.index(act) < order.index(late.id)                       # time order
    assert desk.evaluate("window.__noReload") == 7                                               # (no page load)
    assert now(act)[:2] == (12 * 60, 13 * 60) and day_of(act) == SATURDAY
    desk.locator(".ga-toast").get_by_role("button", name="Undo").click()
    expect(col(desk, SUNDAY).locator(f'.cz-wi[data-wk-act="{act}"]')).to_have_count(1)
    assert day_of(act) == SUNDAY and desk.evaluate("window.__noReload") == 7


def test_the_drop_adds_no_motion_of_its_own(desk):
    act = lunch(desk)
    lift(desk, act)
    desk.mouse.move(*mid(col(desk, SATURDAY)), steps=6)
    desk.mouse.up()
    expect(desk.locator(".ga-toast")).to_contain_text("Moved to")
    assert desk.evaluate("() => [...document.querySelectorAll('.cz-wk, .cz-wk *')].flatMap(n => n.getAnimations()).length") == 0
    css = open(os.path.join(os.path.dirname(__file__), "..", "assets", "css", "week_desk.css"), encoding="utf-8").read()
    assert not re.search(r"\b\d+(\.\d+)?m?s\b", css.split("F-157")[1])                             # no literal times in the new rules


def test_a_click_without_a_drag_still_opens_the_day_with_the_plan_in_the_panel(desk):
    act = lunch(desk)
    x, y = mid(row(desk, act))
    desk.mouse.move(x, y)
    desk.mouse.down()
    desk.mouse.move(x + 2, y + 1)                                                                # a wobble inside the drag distance
    desk.mouse.up()
    desk.wait_for_selector(f'.cz-view[data-level=day][data-day="{SUNDAY}"]')
    settle(desk)
    assert day_of(act) == SUNDAY and desk.locator(".cz-wi-copy").count() == 0
    assert act in desk.url


def test_escape_mid_drag_leaves_the_plan_where_it_was_and_the_week_stays(desk):
    act = lunch(desk)
    lift(desk, act)
    desk.mouse.move(*mid(col(desk, SATURDAY)), steps=6)
    desk.keyboard.press("Escape")
    desk.wait_for_function("() => !document.querySelector('.cz-wi-copy, .is-drop-target, .is-lifted')")
    desk.mouse.up()
    desk.wait_for_timeout(300)
    assert desk.locator(".ga-toast").count() == 0 and day_of(act) == SUNDAY
    expect(desk.locator(".cz-view")).to_have_attribute("data-level", "week")                     # Esc did not zoom out or open anything
    expect(col(desk, SUNDAY).locator(f'.cz-wi[data-wk-act="{act}"]')).to_have_count(1)


def test_dropping_on_its_own_column_or_outside_the_columns_leaves_it(desk):
    act = lunch(desk)
    lift(desk, act)
    desk.mouse.move(*mid(col(desk, SATURDAY)), steps=5)
    desk.mouse.move(*mid(col(desk, SUNDAY)), steps=5)
    desk.mouse.up()
    desk.wait_for_function("() => !document.querySelector('.cz-wi-copy')")
    lift(desk, act)
    desk.mouse.move(*mid(col(desk, SATURDAY)), steps=5)
    desk.mouse.move(10, 10, steps=5)                                                             # off the week altogether
    desk.mouse.up()
    desk.wait_for_function("() => !document.querySelector('.cz-wi-copy')")
    desk.wait_for_timeout(300)
    assert desk.locator(".ga-toast").count() == 0 and day_of(act) == SUNDAY
    expect(desk.locator(".cz-view")).to_have_attribute("data-level", "week")


def test_bookings_cannot_be_dragged(desk):
    booked = desk.locator(".cz-wk .cz-wi.is-booked").first
    expect(booked).to_be_visible()
    assert booked.get_attribute("data-wk-act") is None
    x, y = mid(booked)
    desk.mouse.move(x, y)
    desk.mouse.down()
    desk.mouse.move(x + 40, y + 20, steps=5)
    assert desk.locator(".cz-wi-copy").count() == 0 and desk.locator(".cz-wk.is-dragging").count() == 0
    desk.mouse.up()


def test_a_viewer_cannot_drag_a_plan_on_the_week(canvas_page, browser, base_url):
    owner = canvas_page(viewport=DESKTOP, touch=False, motion="reduce")
    p = plan("Lunch", 12 * 60, 13 * 60)
    mail = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    ctx = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
    try:
        ctx.set_default_timeout(9000)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas")
        page.wait_for_selector("#cz-wk")
        r = page.locator(".cz-wk .cz-wi", has_text="Lunch").first
        x, y = mid(r)
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 20, y + 20, steps=4)
        page.mouse.move(*mid(col(page, SATURDAY)), steps=6)
        assert page.locator(".cz-wi-copy").count() == 0 and page.locator(".cz-wcol.is-drop-target").count() == 0
        page.mouse.up()
        page.wait_for_timeout(300)
        assert page.locator(".ga-toast").count() == 0 and day_of(p.id) == SUNDAY
        res = page.context.request.post(f"{base_url}/trip/canvas/plan", form={"op": "edit", "act": p.id, "day": str(SATURDAY)}, headers={"X-Canvas": "1"})
        assert res.status == 403 and day_of(p.id) == SUNDAY
    finally:
        ctx.close()


def test_a_long_trips_week_scrolls_sideways_when_a_plan_is_held_near_its_edge(browser, base_url):
    ctx = browser.new_context(viewport=LAPTOP, reduced_motion="reduce")
    ctx.set_default_timeout(6000)
    try:
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-23", "r": "2026-11-01", "a": "2", "k": "4,7"}, max_redirects=0)
        page = ctx.new_page()
        made = ctx.request.post(f"{base_url}/trip/canvas/plan", form={"op": "add", "day": "0", "start": str(12 * 60), "end": str(13 * 60), "title": "Lunch", "id": "a77"}, headers={"X-Canvas": "1"})
        assert made.status == 200, made.text()
        page.goto(f"{base_url}/trip/canvas")
        page.wait_for_selector("#cz-wk.is-long")
        assert page.evaluate("() => { const n = document.querySelector('#cz-wk'); return n.scrollWidth > n.clientWidth && n.scrollLeft === 0; }")
        lift(page, "a77")
        wk = page.locator("#cz-wk").bounding_box()
        page.mouse.move(wk["x"] + wk["width"] - 14, wk["y"] + wk["height"] / 2, steps=10)         # held near the right edge
        page.wait_for_function("() => document.querySelector('#cz-wk').scrollLeft > 20")
        left = page.evaluate("() => document.querySelector('#cz-wk').scrollLeft")
        page.wait_for_timeout(250)
        assert page.evaluate("() => document.querySelector('#cz-wk').scrollLeft") > left          # it keeps going while held
        page.mouse.move(wk["x"] + wk["width"] / 2, wk["y"] + wk["height"] / 2, steps=6)           # back to the middle: it stops
        page.wait_for_timeout(120)
        stop = page.evaluate("() => document.querySelector('#cz-wk').scrollLeft")
        page.wait_for_timeout(200)
        assert page.evaluate("() => document.querySelector('#cz-wk').scrollLeft") == stop
        far = page.locator(".cz-wcol.is-drop-target")
        expect(far).to_have_count(1)
        day = far.get_attribute("data-day")
        scrolled = page.evaluate("() => document.querySelector('#cz-wk').scrollLeft")
        assert scrolled > 20
        page.mouse.up()
        expect(page.locator(".ga-toast")).to_contain_text("Moved to")
        page.wait_for_timeout(300)
        assert page.evaluate("() => document.querySelector('#cz-wk').scrollLeft") == scrolled      # the refresh did not send the week back to the start
        assert cal.get_activity(ari(), "a77").day == int(day)
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    finally:
        ctx.close()


@pytest.mark.parametrize("viewport", [TABLET, PHONE], ids=["1000", "390"])
def test_the_tablet_and_phone_week_do_not_drag(canvas_page, viewport):
    page = canvas_page(viewport=viewport, touch=False, motion="reduce")
    plan("Lunch", 12 * 60, 13 * 60)
    page.reload()
    page.wait_for_selector(".cz-view[data-level=week]")
    expect(page.locator("#cz-wk")).to_be_hidden()
    r = page.locator("#cz-week a", has_text="Lunch").first
    if r.count() and r.is_visible():
        x, y = mid(r)
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 40, y + 40, steps=5)
        assert page.locator(".cz-wi-copy").count() == 0 and page.evaluate("document.documentElement.classList.contains('cz-wk-moving')") is False
        page.mouse.up()


def test_a_lifted_plan_is_put_back_when_the_window_loses_focus_or_the_button_was_let_go_out_of_sight(desk):
    act = lunch(desk)
    for how in ("blur", "nobutton"):
        lift(desk, act)
        desk.mouse.move(*mid(col(desk, SATURDAY)), steps=5)
        if how == "blur":
            desk.evaluate("window.dispatchEvent(new Event('blur'))")
        else:
            desk.evaluate("() => document.dispatchEvent(new PointerEvent('pointermove', { pointerId: 1, pointerType: 'mouse', buttons: 0, clientX: 600, clientY: 300, bubbles: true }))")
        desk.wait_for_function("() => !document.querySelector('.cz-wi-copy, .is-drop-target, .is-lifted')")
        desk.mouse.up()
        desk.wait_for_timeout(250)
        assert desk.locator(".ga-toast").count() == 0 and day_of(act) == SUNDAY
        expect(desk.locator(".cz-view")).to_have_attribute("data-level", "week")


def test_only_editors_get_the_grab_cursor_on_a_plan_row(desk, browser, base_url):
    assert desk.locator(".cz-wk .cz-wi[data-wk-act]").first.evaluate("n => getComputedStyle(n).cursor") == "grab"
    ctx = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
    try:
        ctx.set_default_timeout(9000)
        mail = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
        assert desk.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas")
        page.wait_for_selector("#cz-wk")
        assert page.locator(".cz-wk .cz-wi[data-wk-act]").count() > 0
        assert page.locator(".cz-wk .cz-wi[data-wk-act]").first.evaluate("n => getComputedStyle(n).cursor") != "grab"
    finally:
        ctx.close()


def test_the_moved_card_lands_in_the_new_column_at_the_same_height_on_the_axis(desk):
    """F-162: the plan keeps its time, so on the shared axis it is at the same y in its new column (a day no longer scrolls inside itself)."""
    act = lunch(desk)
    before = row(desk, act).bounding_box()
    lift(desk, act)
    desk.mouse.move(*mid(col(desk, SATURDAY)), steps=6)
    desk.mouse.up()
    expect(desk.locator(".ga-toast")).to_contain_text("Moved to")
    moved = col(desk, SATURDAY).locator(f'.cz-wi[data-wk-act="{act}"]')
    expect(moved).to_have_count(1)
    after = moved.bounding_box()
    assert abs(after["y"] - before["y"]) < 1 and abs(after["height"] - before["height"]) < 1


def test_the_drop_lands_in_the_new_column_at_once_while_the_save_is_on_its_way(desk):
    """F-176: the row is in the target column, at its time, unfaded, in the frame after the drop, with the save slowed 700 ms; the reply only tidies up and toasts. A write then
    does not fetch every plan row of the week again (each is checked when it is opened)."""
    act = lunch(desk)
    top = row(desk, act).bounding_box()["y"]
    gets = []
    desk.on("request", lambda q: gets.append(q.url) if q.method == "GET" and "plan=" in q.url else None)
    desk.wait_for_timeout(2500)                                                                 # the plan rows fetched ahead once, as the week came
    ahead = set(gets)
    desk.route("**/trip/canvas/plan", lambda r: (desk.wait_for_timeout(700), r.continue_()))
    lift(desk, act)
    desk.mouse.move(*mid(col(desk, SATURDAY)), steps=6)
    mark = len(gets)
    desk.evaluate("() => { window.__t0 = performance.now(); }")
    desk.mouse.up()
    at = desk.evaluate("""act => new Promise(ok => requestAnimationFrame(() => {
        const n = document.querySelector(`.cz-wcol[data-day="${%d}"] .cz-wi[data-wk-act="${act}"]`);
        ok(n ? { ms: performance.now() - window.__t0, op: getComputedStyle(n).opacity, y: n.getBoundingClientRect().top, saving: n.classList.contains('is-saving') } : null);
    }))""" % SATURDAY, act)
    assert at is not None, "the row is not in the new column in the frame after the drop"
    assert at["ms"] < 100 and at["op"] == "1" and not at["saving"] and abs(at["y"] - top) <= 1, at
    assert col(desk, SUNDAY).locator(f'.cz-wi[data-wk-act="{act}"]').count() == 0
    expect(desk.locator(".ga-toast")).to_contain_text("Moved to Sat 17")
    expect(col(desk, SATURDAY).locator(f'.cz-wi[data-wk-act="{act}"]')).to_have_count(1)
    assert day_of(act) == SATURDAY
    desk.wait_for_timeout(2500)                                                                 # the idle fetches after the write
    desk.unroute_all(behavior="ignoreErrors")
    again = [u for u in gets[mark:] if u in ahead]
    assert ahead and again == [], again                                                         # (the moved plan's new address is new: fetched once)


def test_a_refused_drop_puts_the_row_back_where_it_was(desk):
    act = lunch(desk)
    desk.route("**/trip/canvas/plan", lambda r: r.fulfill(status=422, content_type="application/json", body='{"error": "That overlaps."}'))
    lift(desk, act)
    desk.mouse.move(*mid(col(desk, SATURDAY)), steps=6)
    desk.mouse.up()
    expect(desk.locator(".ga-toast")).to_contain_text("That overlaps.")
    expect(col(desk, SUNDAY).locator(f'.cz-wi[data-wk-act="{act}"]')).to_have_count(1)
    expect(col(desk, SATURDAY).locator(f'.cz-wi[data-wk-act="{act}"]')).to_have_count(0)
    assert day_of(act) == SUNDAY
