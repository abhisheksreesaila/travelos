"""F-097: the day as a time grid in a real browser, at 390 and 320 wide. Blocks sized by their length with overlaps side by side; hold a block to lift it and drag it to a new
time (15-minute snap, the time under the finger, the page scrolls at the edge); hold its bottom edge to change its length while the grid zooms in around the finger (5-minute
snap) and eases back; Undo; a viewer gets no gestures; reduced motion has no zoom; a flick still changes the day and a held block never does; a real finger (CDP touch) scrolls
until it holds; phone checks. A finger is a pointer that goes down, waits, moves and lets go (synthetic pointer events, as in the F-082 tests). Screenshots on request:
F097_SHOTS=<folder>."""
import os
import re
import uuid

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT
from tests_browser.test_trip_canvas import NARROW, canvas_page, model, settle  # noqa: F401 - fixtures

SUNDAY = 2           # the free day of the demo trip: no park block, so the plans on it are ours


def ari():
    return person("ari")


def plan(title, start, end, day=SUNDAY, kind="fun"):
    return cal.add_activity(ari(), day=day, start=start, end=end, title=title, kind=kind)


def now(act):
    a = cal.get_activity(ari(), act)
    return a.start, a.end, a.title


def open_day(page, n=SUNDAY):
    page.goto(re.sub(r"^(https?://[^/]+).*", lambda m: f"{m.group(1)}/trip/canvas?day={n}", page.url))
    page.wait_for_selector(f".cz-view[data-level=day][data-day='{n}']")
    settle(page)


def checks(page):
    assert page.evaluate(OVERFLOW) <= 0
    assert page.evaluate(SMALL_TEXT) == []
    assert page.evaluate(SMALL_CONTROLS) == []


# ---- a finger ----------------------------------------------------------------------------------------------------------------

def fire(page, kind, x, y, pid=7, pointer="touch"):
    page.evaluate("""([kind, x, y, id, pt]) => { const el = document.elementFromPoint(x, y) || document.body;
      el.dispatchEvent(new PointerEvent(kind, { pointerId: id, pointerType: pt, clientX: x, clientY: y, bubbles: true, cancelable: true, isPrimary: true })); }""", [kind, x, y, pid, pointer])


def box(page, selector):
    b = page.locator(selector).first.bounding_box()
    assert b, selector
    return b


def show(page, selector, at=0.45):
    """Scroll the page so the element's middle is at `at` of the screen height, away from the header, the tab bar and the toast."""
    page.locator(selector).first.evaluate("(e, at) => { const r = e.getBoundingClientRect(); window.scrollBy(0, r.top + r.height / 2 - innerHeight * at); }", at)
    page.wait_for_timeout(30)


def ppm(page):
    """Pixels per minute of the grid at normal size."""
    return page.evaluate("() => { const z = document.querySelector('.cz-g-zoom'), g = document.querySelector('#cz-grid'); return z.offsetHeight / (+g.dataset.hi - +g.dataset.lo); }")


def slide(page, frm, to, steps=6, wait=16):
    for i in range(1, steps + 1):
        fire(page, "pointermove", frm[0] + (to[0] - frm[0]) * i / steps, frm[1] + (to[1] - frm[1]) * i / steps)
        page.wait_for_timeout(wait)
    return to


def hold_block(page, act, edge=False, wait=480):
    """Put a finger on a block (its middle, or just inside its bottom edge) and keep it there until it is lifted."""
    sel = f'.cz-gb[data-act="{act}"]'
    show(page, sel)
    b = box(page, sel)
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] - 7 if edge else b["y"] + b["height"] / 2
    fire(page, "pointerdown", x, y)
    page.wait_for_timeout(wait)
    return x, y


def label(page):
    return page.locator(".cz-g-label").inner_text().replace("\n", " | ")


def toast(page):
    return page.locator(".cz-toast")


def shot(page, name):
    """A screenshot of the moment, when F097_SHOTS names a folder (and only at 390 wide)."""
    if os.environ.get("F097_SHOTS") and page.viewport_size["width"] == 390:
        page.screenshot(path=os.path.join(os.environ["F097_SHOTS"], name))


@pytest.fixture(params=[PHONE, NARROW], ids=["390", "320"])
def phone(request, canvas_page):
    page = canvas_page(viewport=request.param)
    return page


# ---- the grid --------------------------------------------------------------------------------------------------------------------

def test_a_plan_is_a_block_whose_height_is_its_length_and_overlaps_sit_side_by_side(phone):
    lunch, brunch, spa = plan("Lunch", 12 * 60, 13 * 60), plan("Brunch", 9 * 60, 10 * 60 + 30), plan("Spa", 12 * 60 + 30, 13 * 60 + 30)
    open_day(phone)
    h = lambda a: box(phone, f'.cz-gb[data-act="{a.id}"]')  # noqa: E731
    assert abs(h(brunch)["height"] / h(lunch)["height"] - 1.5) < 0.02                  # 90 minutes against 60
    assert abs(h(lunch)["y"] - (h(brunch)["y"] + 180 * ppm(phone))) < 1.5               # three hours apart on the grid
    a, b = h(lunch), h(spa)
    assert a["x"] + a["width"] <= b["x"] + 0.5 and abs(a["width"] - b["width"]) < 1       # side by side, not on top of each other
    assert h(lunch)["x"] > 40 and h(lunch)["x"] + h(lunch)["width"] <= phone.viewport_size["width"]
    checks(phone)


def test_a_park_day_with_bookings_fits_and_the_park_block_opens_its_block(phone):
    open_day(phone, 1)
    assert phone.locator(".cz-gb.is-park").count() == 1 and box(phone, ".cz-gb.is-park")["height"] > 600
    checks(phone)
    open_day(phone, 0)
    plan("Beach walk", 10 * 60, 11 * 60, day=0)
    open_day(phone, 0)
    assert phone.locator(".cz-gbk").count() == 2
    checks(phone)
    open_day(phone, 1)
    phone.locator(".cz-gb-open").click(force=True)
    expect(phone.locator(".cz-view[data-level=block]")).to_be_visible()


def test_a_blank_day_keeps_talk_and_paste_and_the_week_the_filters_and_sos_still_work(phone):
    open_day(phone)
    expect(phone.locator("#cz-say-talk")).to_be_visible()
    assert phone.locator("#cz-grid").count() == 0
    plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    assert phone.locator("#cz-grid").count() == 1 and phone.locator("#cz-say-talk").count() == 0
    phone.locator(".cz-kchip", has_text="Hotels").click()
    expect(phone.locator(".cz-gb:visible")).to_have_count(0)    # the kind filter hides plans
    phone.locator(".cz-kchip", has_text="All").click()
    expect(phone.locator(".cz-gb:visible")).to_have_count(1)
    phone.locator("#cz-sos").click()
    expect(phone.get_by_role("dialog")).to_be_visible()
    phone.locator(".cz-close").click()
    phone.locator("#cz-z-week").click()
    expect(phone.locator(".cz-view[data-level=week]")).to_be_visible()


def test_a_laptop_gets_the_same_grid_wider(canvas_page):
    page = canvas_page(viewport={"width": 1280, "height": 800}, touch=False)
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    b = box(page, f'.cz-gb[data-act="{lunch.id}"]')
    assert b["width"] > 400 and page.evaluate(OVERFLOW) <= 0
    assert page.locator(".cz-strip").is_visible() and page.locator("#cz-tray, .cz-day-side").count() >= 1


# ---- move --------------------------------------------------------------------------------------------------------------------------

def test_hold_and_drag_moves_a_block_in_fifteen_minute_steps_with_a_label_and_an_undo(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    start = hold_block(phone, lunch.id)
    expect(phone.locator(f'.cz-gb[data-act="{lunch.id}"]')).to_have_class(re.compile(r"is-held"))
    expect(phone.locator(".cz-g-ghost")).to_have_count(1)
    assert "12:00 – 1:00 PM" in label(phone)
    step = ppm(phone) * 15
    end = slide(phone, start, (start[0], start[1] + step * 2 + step * 0.3))        # 30 minutes and a bit: it snaps to 30
    assert "12:30 – 1:30 PM" in label(phone) and "was 12:00 PM" in label(phone)
    assert now(lunch.id)[0] == 12 * 60                                              # nothing is saved until the finger lifts
    fire(phone, "pointerup", *end)
    expect(toast(phone)).to_contain_text("Lunch moved to 12:30 PM")
    expect(toast(phone).get_by_role("button", name="Undo")).to_be_visible()
    assert now(lunch.id)[:2] == (12 * 60 + 30, 13 * 60 + 30)
    expect(phone.locator(".cz-g-label, .cz-g-ghost")).to_have_count(0)
    expect(phone.locator(f'.cz-gb[data-act="{lunch.id}"] .cz-gb-when')).to_have_text("12:30 – 1:30 PM")
    assert phone.locator(".is-held, .is-resizing").count() == 0 and phone.evaluate("CZ.held") is False
    before = box(phone, f'.cz-gb[data-act="{lunch.id}"]')["y"]
    toast(phone).get_by_role("button", name="Undo").click()
    expect(toast(phone)).to_have_text("Put back")
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60)
    assert box(phone, f'.cz-gb[data-act="{lunch.id}"]')["y"] < before - step                 # back up where it was
    checks(phone)


def test_letting_go_where_it_began_saves_nothing_and_a_refusal_snaps_back_with_the_reason(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    start = hold_block(phone, lunch.id)
    end = slide(phone, start, (start[0], start[1] + 3))
    fire(phone, "pointerup", *end)
    phone.wait_for_timeout(300)
    assert toast(phone).count() == 0 and now(lunch.id)[:2] == (12 * 60, 13 * 60)
    start = hold_block(phone, lunch.id)
    slide(phone, start, (start[0], start[1] - 300 * ppm(phone)))                    # dragged off the top: the grid ends at 7 AM
    assert "7:00 – 8:00 AM" in label(phone)
    cal.delete_activity(ari(), lunch.id)                                            # someone else deletes it while the finger is down
    fire(phone, "pointerup", start[0], start[1] - 300 * ppm(phone))
    expect(toast(phone)).to_contain_text("gone")
    expect(phone.locator(".cz-gb")).to_have_count(0)


def test_dragging_near_the_bottom_edge_scrolls_the_page_and_the_block_keeps_up(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    start = hold_block(phone, lunch.id)
    y0 = phone.evaluate("scrollY")
    h = phone.viewport_size["height"]
    end = slide(phone, start, (start[0], h - 150), steps=4)
    phone.mouse.move(0, 0)
    fire(phone, "pointermove", end[0], h - 120)
    phone.wait_for_timeout(700)
    assert phone.evaluate("scrollY") > y0 + 40                                       # edge scroll
    assert "PM" in label(phone) and label(phone).split("|")[0].strip() != "12:00 – 1:00 PM"      # the time followed the scroll as well as the finger
    fire(phone, "pointerup", end[0], h - 120)
    expect(toast(phone)).to_contain_text("Lunch moved to")


def test_a_move_cannot_leave_the_day(phone):
    late = plan("Dinner", 20 * 60, 21 * 60)
    open_day(phone)
    start = hold_block(phone, late.id)
    slide(phone, start, (start[0], start[1] + 600), steps=3)
    fire(phone, "pointerup", start[0], start[1] + 600)
    expect(toast(phone)).to_contain_text("Dinner moved to 9:00 PM")                  # the last place a one-hour plan fits: it ends at 10:00 PM
    assert now(late.id)[:2] == (21 * 60, 22 * 60)


# ---- resize with a zoom ---------------------------------------------------------------------------------------------------------

def test_hold_the_bottom_edge_zooms_in_resizes_in_five_minute_steps_and_eases_back(canvas_page):
    page = canvas_page(motion="no-preference")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    base = ppm(page)
    start = hold_block(page, lunch.id, edge=True, wait=700)
    expect(page.locator(f'.cz-gb[data-act="{lunch.id}"]')).to_have_class(re.compile(r"is-resizing"))
    k = page.evaluate("+getComputedStyle(document.querySelector('#cz-grid')).getPropertyValue('--zk')")
    assert 2.4 < k <= 2.5 and "matrix" in page.evaluate("getComputedStyle(document.querySelector('.cz-g-zoom')).transform")
    assert page.evaluate("document.querySelector('.cz-g-zoom').classList.contains('is-zooming')")
    text_h = page.evaluate("document.querySelector('.cz-gb-t').getBoundingClientRect().height")
    assert text_h < 40                                                                # the words did not stretch with the grid
    px5 = base * 5 * k                                                                # five minutes, on the screen, while zoomed
    end = slide(page, start, (start[0], start[1] + px5 * 2 + px5 * 0.3), steps=8)    # ten minutes and a bit: 1:10 PM, not a 15-minute step
    assert "12:00 – 1:10 PM" in label(page) and "1 h 10 min" in label(page)
    shot(page, "resize-zoom-390.png")
    fire(page, "pointerup", *end)
    expect(page.locator(".cz-g-zoom.is-zooming")).to_have_count(0, timeout=3000)       # eased back
    assert page.evaluate("getComputedStyle(document.querySelector('#cz-grid')).getPropertyValue('--zk').trim()") in ("", "1")
    expect(toast(page)).to_contain_text("Lunch now ends 1:10 PM")
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60 + 10)
    expect(page.locator(f'.cz-gb[data-act="{lunch.id}"] .cz-gb-when')).to_have_text("12:00 – 1:10 PM")
    toast(page).get_by_role("button", name="Undo").click()
    expect(toast(page)).to_have_text("Put back")
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60)
    checks(page)


def test_a_block_cannot_be_made_shorter_than_fifteen_minutes(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    start = hold_block(phone, lunch.id, edge=True)
    end = slide(phone, start, (start[0], start[1] - 2000 * 0 - 60 * ppm(phone) * 0.9 - 40), steps=6)
    fire(phone, "pointermove", end[0], end[1] - 400)
    assert "12:00 – 12:15 PM" in label(phone) and "15 min" in label(phone)
    fire(phone, "pointerup", end[0], end[1] - 400)
    expect(toast(phone)).to_contain_text("Lunch now ends 12:15 PM")
    assert now(lunch.id)[:2] == (12 * 60, 12 * 60 + 15)
    open_day(phone)
    assert box(phone, f'.cz-gb[data-act="{lunch.id}"]')["height"] > 10
    checks(phone)


def test_reduced_motion_has_no_zoom_and_keeps_the_fifteen_minute_snap(canvas_page):
    page = canvas_page(motion="reduce")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    start = hold_block(page, lunch.id, edge=True)
    assert page.evaluate("getComputedStyle(document.querySelector('.cz-g-zoom')).transform") == "none"
    end = slide(page, start, (start[0], start[1] + ppm(page) * 21))                  # 21 minutes: a 15-minute step
    assert "12:00 – 1:15 PM" in label(page)
    fire(page, "pointerup", *end)
    expect(toast(page)).to_contain_text("Lunch now ends 1:15 PM")


# ---- who may, and the gestures that must not mix --------------------------------------------------------------------------------

def test_a_viewer_sees_the_grid_and_holding_a_block_does_nothing(canvas_page, browser, base_url):
    owner = canvas_page(viewport=PHONE)
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    mail = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
    try:
        ctx.set_default_timeout(9000)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day={SUNDAY}")
        page.wait_for_selector("#cz-grid")
        assert page.locator("#cz").get_attribute("data-edit") is None and page.locator(".cz-gb-grip, .cz-gb-menubtn").count() == 0
        start = hold_block(page, lunch.id)
        assert page.locator(".is-held, .cz-g-label, .cz-g-ghost").count() == 0
        end = slide(page, start, (start[0], start[1] + 80))
        fire(page, "pointerup", *end)
        page.wait_for_timeout(300)
        assert page.locator(".cz-toast").count() == 0 and now(lunch.id)[:2] == (12 * 60, 13 * 60)
        assert page.evaluate(OVERFLOW) <= 0
    finally:
        ctx.close()


def test_a_flick_on_empty_grid_still_changes_the_day_and_a_held_block_never_does(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    show(phone, f'.cz-gb[data-act="{lunch.id}"]')
    b = box(phone, f'.cz-gb[data-act="{lunch.id}"]')
    y = b["y"] + b["height"] + 40                                                      # empty grid below the block
    phone.evaluate("""([x, y, dx]) => { const el = document.elementFromPoint(x, y); const f = (t, px) => el.dispatchEvent(new PointerEvent(t, { pointerId: 9, pointerType: 'touch', clientX: px, clientY: y, bubbles: true, cancelable: true, isPrimary: true }));
      f('pointerdown', x); for (let i = 1; i <= 6; i++) f('pointermove', x + dx * i / 6); f('pointerup', x + dx); }""", [200, y, -160])
    expect(phone.locator(".cz-view")).to_have_attribute("data-day", "3")
    open_day(phone)
    start = hold_block(phone, lunch.id)
    end = slide(phone, start, (start[0] - 170, start[1] + 2), steps=8)                  # held, then dragged sideways: never a flick
    fire(phone, "pointerup", *end)
    phone.wait_for_timeout(450)
    assert phone.locator(".cz-view").get_attribute("data-day") == str(SUNDAY) and now(lunch.id)[:2] == (12 * 60, 13 * 60)
    open_day(phone)
    show(phone, f'.cz-gb[data-act="{lunch.id}"]')
    b = box(phone, f'.cz-gb[data-act="{lunch.id}"]')                                   # a quick sideways swipe that starts on a block, before the hold, is the flick
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    phone.evaluate("""([x, y, dx]) => { const el = document.elementFromPoint(x, y); const f = (t, px) => el.dispatchEvent(new PointerEvent(t, { pointerId: 9, pointerType: 'touch', clientX: px, clientY: y, bubbles: true, cancelable: true, isPrimary: true }));
      f('pointerdown', x); for (let i = 1; i <= 6; i++) f('pointermove', x + dx * i / 6); f('pointerup', x + dx); }""", [x, y, -150])
    expect(phone.locator(".cz-view")).to_have_attribute("data-day", "3")


def test_two_fingers_never_lift_and_a_tap_on_a_plain_plan_opens_its_chat(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    sel = f'.cz-gb[data-act="{lunch.id}"]'
    show(phone, sel)
    b = box(phone, sel)
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    fire(phone, "pointerdown", x, y)
    fire(phone, "pointerdown", x + 20, y + 20, pid=8)               # a second finger: no gesture
    phone.wait_for_timeout(520)
    assert phone.locator(".is-held").count() == 0 and phone.evaluate("CZ.held") is False
    fire(phone, "pointerup", x + 20, y + 20, pid=8)
    fire(phone, "pointerup", x, y)
    phone.wait_for_timeout(200)
    assert phone.locator(".cz-view").get_attribute("data-level") == "day" and phone.locator(".cz-toast").count() == 0
    phone.locator(f"{sel} .cz-gb-open").click(position={"x": 60, "y": 40})      # the captain's call: a tap on a plan opens its chat (a park block opens its block)
    phone.wait_for_url(re.compile(r"/trip/talk\?act=" + lunch.id))
    expect(phone.locator("#ft-compose")).to_be_visible()


def test_every_block_is_a_44px_target_even_a_15_minute_one_and_its_words_are_not_cut_by_the_phone_checks(phone):
    from gitaway import planedit
    a = plan("Coffee with the family", 10 * 60, 10 * 60 + 30)
    planedit.change(ari(), a.id, end=10 * 60 + 15)
    b = plan("Pick up the rental car", 11 * 60, 11 * 60 + 30)
    open_day(phone)
    sizes = phone.evaluate("[...document.querySelectorAll('.cz-gb')].map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })")
    assert sizes and all(w >= 44 and h >= 43.5 for w, h in sizes), sizes
    checks(phone)
    sel = f'.cz-gb[data-act="{a.id}"]'
    show(phone, sel)
    phone.locator(f"{sel} .cz-gb-menubtn").focus()                    # focused, a short block shows all of itself, and the keyboard sees where it is
    assert phone.evaluate(f"document.querySelector('{sel} .cz-gb-in').scrollHeight <= document.querySelector('{sel}').getBoundingClientRect().height + 1")
    phone.keyboard.press("Shift+Tab")                                  # a keyboard move, so the focus ring is the keyboard's
    phone.keyboard.press("Tab")
    assert phone.evaluate(f"getComputedStyle(document.querySelector('{sel}')).outlineStyle") == "solid"


def test_a_failed_save_puts_the_block_back_even_when_the_refresh_cannot_load(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    phone.route("**/trip/canvas/plan", lambda r: r.abort())
    phone.route(re.compile(r".*frag=1.*"), lambda r: r.abort())
    start = hold_block(phone, lunch.id)
    end = slide(phone, start, (start[0], start[1] + ppm(phone) * 45))
    fire(phone, "pointerup", *end)
    expect(toast(phone)).to_contain_text("Could not save")
    sel = f'.cz-gb[data-act="{lunch.id}"]'
    assert phone.locator(sel).get_attribute("data-s") == str(12 * 60) and "12:00 – 1:00 PM" in phone.locator(f"{sel} .cz-gb-when").inner_text()
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60) and phone.evaluate("CZ.held") is False
    phone.unroute("**/trip/canvas/plan")
    phone.unroute(re.compile(r".*frag=1.*"))
    start = hold_block(phone, lunch.id)                                # gestures are not stuck waiting
    expect(phone.locator(".cz-g-label")).to_have_count(1)
    fire(phone, "pointerup", *start)


def touch(cdp, kind, x, y):
    cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [] if kind == "touchEnd" else [{"x": x, "y": y, "id": 1}]})


def test_a_real_finger_scrolls_the_page_until_it_holds_and_then_the_page_stays_still(canvas_page):
    page = canvas_page(viewport=PHONE)
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    cdp = page.context.new_cdp_session(page)
    show(page, f'.cz-gb[data-act="{lunch.id}"]', at=0.5)
    b = box(page, f'.cz-gb[data-act="{lunch.id}"]')
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    y0 = page.evaluate("scrollY")
    touch(cdp, "touchStart", x, y)                                                     # a finger that moves at once is a scroll
    for i in range(1, 12):
        touch(cdp, "touchMove", x, y - i * 18)
        page.wait_for_timeout(16)
    page.wait_for_timeout(450)
    touch(cdp, "touchEnd", x, y - 198)
    assert page.locator(".is-held").count() == 0 and page.evaluate("scrollY") != y0
    show(page, f'.cz-gb[data-act="{lunch.id}"]', at=0.5)
    b = box(page, f'.cz-gb[data-act="{lunch.id}"]')
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    touch(cdp, "touchStart", x, y)                                                     # one that holds still first lifts the block
    page.wait_for_timeout(550)
    expect(page.locator(".is-held")).to_have_count(1)
    y0 = page.evaluate("scrollY")
    for i in range(1, 9):
        touch(cdp, "touchMove", x, y + i * 12)
        page.wait_for_timeout(20)
    assert abs(page.evaluate("scrollY") - y0) < 2
    assert "12:" in label(page) or "1:" in label(page)
    touch(cdp, "touchEnd", x, y + 96)
    expect(toast(page)).to_contain_text("Lunch moved to")


def test_a_pointercancel_while_held_puts_everything_back(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    start = hold_block(phone, lunch.id)
    end = slide(phone, start, (start[0], start[1] + 60))
    fire(phone, "pointercancel", *end)
    phone.wait_for_timeout(200)
    assert phone.locator(".is-held, .cz-g-ghost, .cz-g-label").count() == 0 and phone.evaluate("CZ.held") is False
    assert phone.locator(".cz-toast").count() == 0 and now(lunch.id)[:2] == (12 * 60, 13 * 60)
    assert phone.evaluate(f"document.querySelector('.cz-gb[data-act=\"{lunch.id}\"]').style.transform") == ""


@pytest.mark.skipif(not os.environ.get("F097_SHOTS"), reason="screenshots are made on request: F097_SHOTS=<folder>")
def test_screenshots(canvas_page):
    out = os.environ["F097_SHOTS"]
    page = canvas_page(viewport=PHONE)
    plan("Brunch at the pier", 9 * 60, 10 * 60 + 30, kind="food")
    lunch = plan("Lunch", 12 * 60, 13 * 60, kind="food")
    plan("Spa", 12 * 60 + 30, 14 * 60, kind="culture")
    plan("Sunset swim", 17 * 60, 18 * 60, kind="outdoors")
    plan("Beach walk", 10 * 60, 11 * 60, day=0)
    open_day(page)
    page.screenshot(path=os.path.join(out, "day-390.png"), full_page=True)
    open_day(page, 0)
    page.screenshot(path=os.path.join(out, "day0-390.png"), full_page=True)
    open_day(page, 1)
    page.screenshot(path=os.path.join(out, "park-390.png"), full_page=False)
    page.set_viewport_size({"width": 1280, "height": 800})
    open_day(page)
    page.screenshot(path=os.path.join(out, "day-1280.png"), full_page=True)
