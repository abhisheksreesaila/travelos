"""F-110: resize knobs like Apple Calendar, and a long block keeps its name in view, in a real browser at 390 and 320 wide. At rest a block has no handle; holding a block lifts it and
shows two small round knobs (top edge, bottom edge) that change the start or the end with the F-097 zoom; dragging the body moves it; a touch elsewhere puts the knobs away; the hold
menu (F-098) still opens on a hold-and-release; a block taller than the screen keeps its title and time stuck to the top of what is visible while the day scrolls. A finger is a pointer that
goes down, waits, moves and lets go (synthetic pointer events, as in tests_browser/test_day_grid.py). Screenshots on request: F110_SHOTS=<folder>."""
import os
import re

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE
from tests_browser.test_day_grid import (box, checks, fire, hold_block, label, now, open_day, plan, ppm, show, slide, toast)
from tests_browser.test_trip_canvas import NARROW, canvas_page, model  # noqa: F401 - fixtures


@pytest.fixture(params=[PHONE, NARROW], ids=["390", "320"])
def phone(request, canvas_page):
    return canvas_page(viewport=request.param)


def shot(page, name):
    if os.environ.get("F110_SHOTS") and page.viewport_size["width"] == 390:
        page.screenshot(path=os.path.join(os.environ["F110_SHOTS"], name))


def block(act):
    return f'.cz-gb[data-act="{act}"]'


def select(page, act):
    """Hold a block and let go: it is selected, its knobs are out and its hold menu is open."""
    x, y = hold_block(page, act)
    fire(page, "pointerup", x, y)
    expect(page.locator(".cz-g-knobs")).to_have_count(1)
    return x, y


def knob(page, which):
    """The middle of a knob's touch area (it straddles the block's edge)."""
    b = box(page, f".cz-g-knob.is-{which} i")
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


def no_knob_on_words(page, act):
    """No knob (its circle and ring) touches a line of the block's words: the text nodes' own boxes, not the lines' full width."""
    return page.evaluate("""(sel) => {
      const root = document.querySelector(sel), rects = [], walk = document.createTreeWalker(root.querySelector('.cz-gb-in'), NodeFilter.SHOW_TEXT);
      while (walk.nextNode()) { if (!walk.currentNode.textContent.trim()) continue; const r = document.createRange(); r.selectNodeContents(walk.currentNode); for (const q of r.getClientRects()) rects.push(q); }
      const rad = parseFloat(getComputedStyle(document.documentElement).fontSize) * (0.375 + 0.125);
      return [...root.nextElementSibling.querySelectorAll('.cz-g-knob')].every(k => { const c = k.getBoundingClientRect(), x = c.left, y = c.top;
        return rects.every(q => x + rad < q.left || x - rad > q.right || y + rad < q.top || y - rad > q.bottom); }); }""", block(act))


def away(page):
    """A touch on bare grid, below everything: puts the knobs away."""
    page.mouse.move(0, 0)
    fire(page, "pointerdown", 4, 120, pid=3)
    fire(page, "pointerup", 4, 120, pid=3)


# ---- at rest, and after a hold ------------------------------------------------------------------------------------------------------

def test_at_rest_a_block_has_no_handle_and_a_hold_shows_two_round_knobs_and_the_menu(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    assert phone.locator(".cz-gb-grip, .cz-g-knobs, .cz-g-knob").count() == 0
    assert phone.evaluate("getComputedStyle(document.querySelector('.cz-gb'), '::after').content") in ("none", "normal")
    shot(phone, "block-rest-390.png")
    select(phone, lunch.id)
    expect(phone.locator(block(lunch.id))).to_have_class(re.compile(r"is-selected"))
    expect(phone.locator(".cz-menu")).to_be_visible()                                   # the hold menu (F-098) still opens on a hold-and-release
    assert phone.locator(".cz-g-knob").count() == 2
    root = phone.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)")
    for which in ("top", "bottom"):
        area = box(phone, f".cz-g-knob.is-{which} i")
        assert area["width"] >= 2.75 * root - 0.5 and area["height"] >= 2.75 * root - 0.5      # a 2.75rem touch area
    dot = phone.evaluate("(() => { const s = getComputedStyle(document.querySelector('.cz-g-knob i'), '::after'); return [parseFloat(s.width), s.backgroundColor, s.borderRadius]; })()")
    assert abs(dot[0] - 0.75 * root) < 0.5 and dot[1] == "rgb(255, 255, 255)"          # a small white circle (the block's colour is its ring)
    b = box(phone, block(lunch.id))
    top, bottom = knob(phone, "top"), knob(phone, "bottom")
    assert abs(top[1] - b["y"]) < 1.5 and abs(bottom[1] - (b["y"] + b["height"])) < 1.5     # one on each edge, straddling it
    assert top[0] > b["x"] + b["width"] / 2 > bottom[0]                                  # the top one at the right, the bottom one at the left
    assert no_knob_on_words(phone, lunch.id)
    shot(phone, "block-selected-390.png")
    checks(phone)


def test_a_touch_elsewhere_puts_the_knobs_away_and_the_page_still_scrolls(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    select(phone, lunch.id)
    away(phone)
    expect(phone.locator(".cz-g-knobs")).to_have_count(0)
    assert phone.locator(".is-selected").count() == 0 and phone.locator(".cz-menu").count() == 0
    select(phone, lunch.id)
    phone.keyboard.press("Escape")                                                       # the menu goes first, then the knobs (and the canvas does not zoom out)
    expect(phone.locator(".cz-menu")).to_have_count(0)
    assert phone.locator(".cz-g-knobs").count() == 1
    phone.keyboard.press("Escape")
    expect(phone.locator(".cz-g-knobs")).to_have_count(0)
    assert phone.locator(".cz-view").get_attribute("data-level") == "day"


def test_holding_another_block_moves_the_knobs_to_it(phone):
    a, b = plan("Lunch", 12 * 60, 13 * 60), plan("Dinner", 18 * 60, 19 * 60)
    open_day(phone)
    select(phone, a.id)
    select(phone, b.id)
    assert phone.locator(".cz-g-knobs").count() == 1 and phone.locator(".is-selected").count() == 1
    expect(phone.locator(block(b.id))).to_have_class(re.compile(r"is-selected"))


def test_the_hold_menu_never_covers_a_knob_while_it_grows_or_after(canvas_page):
    page = canvas_page(motion="no-preference")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    select(page, lunch.id)                                                              # the menu has only just started to grow out of the block
    for wait in (0, 700):
        page.wait_for_timeout(wait)
        for which in ("top", "bottom"):
            x, y = knob(page, which)
            assert page.evaluate("([x, y]) => { const e = document.elementFromPoint(x, y); return !!(e && e.closest('.cz-g-knob')); }", [x, y]), (wait, which)
        for which in ("top", "bottom"):                                                 # and its whole touch area, to the edge of the block's far side
            b = box(page, f".cz-g-knob.is-{which} i")
            m = page.locator(".cz-menu").bounding_box()
            assert b["y"] + b["height"] <= m["y"] + 1 or b["y"] >= m["y"] + m["height"] - 1 or wait == 0, (which, b, m)


# ---- the knobs ------------------------------------------------------------------------------------------------------------------------

def test_the_bottom_knob_changes_the_end_in_one_touch_with_no_second_hold(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    select(phone, lunch.id)
    start = knob(phone, "bottom")
    fire(phone, "pointerdown", *start)
    expect(phone.locator(block(lunch.id))).to_have_class(re.compile(r"is-resizing"), timeout=300)      # at once: the hold is already done
    end = slide(phone, start, (start[0], start[1] + ppm(phone) * 31))
    assert "12:00 – 1:30 PM" in label(phone)
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60)                                       # nothing is saved until the finger lifts
    fire(phone, "pointerup", *end)
    expect(toast(phone)).to_contain_text("Lunch now ends 1:30 PM")
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60 + 30)
    expect(phone.locator(".cz-g-knobs")).to_have_count(1)                                 # still selected, with its knobs, after the save
    expect(phone.locator(f"{block(lunch.id)} .cz-gb-when")).to_have_text("12:00 – 1:30 PM")
    b = box(phone, block(lunch.id))
    assert abs(knob(phone, "bottom")[1] - (b["y"] + b["height"])) < 1.5                  # on the new bottom edge
    toast(phone).get_by_role("button", name="Undo").click()
    expect(toast(phone)).to_have_text("Put back")
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60)
    checks(phone)


def test_the_top_knob_changes_the_start_and_keeps_the_end(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    select(phone, lunch.id)
    start = knob(phone, "top")
    fire(phone, "pointerdown", *start)
    end = slide(phone, start, (start[0], start[1] - ppm(phone) * 31))                   # 31 minutes up: the start snaps to 11:30
    assert "11:30 AM – 1:00 PM" in label(phone) and "1 h 30 min" in label(phone)
    top = box(phone, block(lunch.id))
    assert abs(top["height"] - 90 * ppm(phone)) < 2                                      # the block grew upwards, not downwards
    fire(phone, "pointerup", *end)
    expect(toast(phone)).to_contain_text("Lunch now starts 11:30 AM")
    assert now(lunch.id)[:2] == (11 * 60 + 30, 13 * 60)
    expect(phone.locator(".cz-g-knobs")).to_have_count(1)
    expect(phone.locator(f"{block(lunch.id)} .cz-gb-when")).to_have_text("11:30 AM – 1:00 PM")
    b = box(phone, block(lunch.id))
    assert abs(knob(phone, "top")[1] - b["y"]) < 1.5
    toast(phone).get_by_role("button", name="Undo").click()
    expect(toast(phone)).to_have_text("Put back")
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60)
    checks(phone)


def test_the_top_knob_cannot_pass_fifteen_minutes_before_the_end(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    select(phone, lunch.id)
    start = knob(phone, "top")
    fire(phone, "pointerdown", *start)
    slide(phone, start, (start[0], start[1] + ppm(phone) * 120), steps=5)               # far past the end
    assert "12:45 – 1:00 PM" in label(phone) and "15 min" in label(phone)
    fire(phone, "pointerup", start[0], start[1] + ppm(phone) * 120)
    expect(toast(phone)).to_contain_text("Lunch now starts 12:45 PM")
    assert now(lunch.id)[:2] == (12 * 60 + 45, 13 * 60)


def test_a_knob_touched_and_let_go_changes_nothing_and_opens_no_menu(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    select(phone, lunch.id)
    away_menu = phone.locator(".cz-menu")
    start = knob(phone, "bottom")
    fire(phone, "pointerdown", *start)
    fire(phone, "pointerup", *start)
    phone.wait_for_timeout(350)
    assert toast(phone).count() == 0 and now(lunch.id)[:2] == (12 * 60, 13 * 60)
    assert away_menu.count() == 0 and phone.locator(".cz-g-knobs").count() == 1 and phone.evaluate("CZ.held") is False


def test_a_knob_drag_zooms_with_five_minute_steps_and_the_words_keep_their_size(canvas_page):
    page = canvas_page(motion="no-preference")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    base = ppm(page)
    select(page, lunch.id)
    start = knob(page, "top")
    fire(page, "pointerdown", *start)
    page.wait_for_timeout(400)
    k = page.evaluate("+getComputedStyle(document.querySelector('#cz-grid')).getPropertyValue('--zk')")
    assert 2.4 < k <= 2.5                                                                # the F-097 zoom
    dot = page.evaluate("document.querySelector('.cz-g-knob i').getBoundingClientRect().width")
    assert dot < 50                                                                      # the knob is not stretched by the zoom
    px5 = base * 5 * k
    end = slide(page, start, (start[0], start[1] - px5 * 2 - px5 * 0.3), steps=8)
    assert "11:50 AM – 1:00 PM" in label(page)                                           # ten minutes and a bit up: a five-minute step
    fire(page, "pointerup", *end)
    expect(toast(page)).to_contain_text("Lunch now starts 11:50 AM")
    expect(page.locator(".cz-g-zoom.is-zooming")).to_have_count(0, timeout=3000)
    assert now(lunch.id)[:2] == (11 * 60 + 50, 13 * 60)


# ---- the body ------------------------------------------------------------------------------------------------------------------------

def test_dragging_the_selected_body_moves_the_block_at_once(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    x, y = select(phone, lunch.id)
    fire(phone, "pointerdown", x, y)
    phone.wait_for_timeout(40)                                                           # far less than a hold
    end = slide(phone, (x, y), (x, y + ppm(phone) * 31))
    assert "12:30 – 1:30 PM" in label(phone) and "was 12:00 PM" in label(phone)
    fire(phone, "pointerup", *end)
    expect(toast(phone)).to_contain_text("Lunch moved to 12:30 PM")
    assert now(lunch.id)[:2] == (12 * 60 + 30, 13 * 60 + 30)
    expect(phone.locator(".cz-g-knobs")).to_have_count(1)                                 # still selected
    assert phone.evaluate("CZ.held") is False


def test_a_tap_on_a_selected_body_only_puts_the_knobs_away_and_opens_no_card(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    select(phone, lunch.id)
    phone.locator(".cz-menu").evaluate("m => m.remove()")
    phone.locator(f"{block(lunch.id)} .cz-gb-open").click(position={"x": 60, "y": 40})
    expect(phone.locator(".cz-g-knobs")).to_have_count(0)
    phone.wait_for_timeout(500)
    assert phone.locator(".cz-card").count() == 0                                        # the next tap opens it
    phone.locator(f"{block(lunch.id)} .cz-gb-open").click(position={"x": 60, "y": 40})
    expect(phone.locator(".cz-card")).to_be_visible()


def test_a_selected_block_taller_than_most_of_the_screen_still_scrolls_under_a_flick_and_needs_a_fresh_hold_to_move(phone):
    big = plan("Beach day", 8 * 60, 18 * 60)                                             # ten hours: taller than 60% of the screen
    small = plan("Lunch", 19 * 60, 20 * 60)
    open_day(phone)
    x, y = select(phone, big.id)
    assert phone.evaluate("s => getComputedStyle(document.querySelector(s)).touchAction", block(big.id)) == "pan-y pinch-zoom"
    fire(phone, "pointerdown", x, y)
    phone.wait_for_timeout(40)
    slide(phone, (x, y), (x, y + 60))
    assert phone.locator(".cz-g-label").count() == 0 and phone.locator(".is-held").count() == 0     # a drag is a scroll: it moved nothing
    fire(phone, "pointerup", x, y + 60)
    phone.wait_for_timeout(300)
    assert now(big.id)[:2] == (8 * 60, 18 * 60)
    select(phone, small.id)                                                               # a short block keeps the move-at-once body
    assert phone.evaluate("s => getComputedStyle(document.querySelector(s)).touchAction", block(small.id)) == "none"
    select(phone, big.id)
    phone.keyboard.press("Escape")                                                        # the menu away (the knobs stay)
    expect(phone.locator(".cz-menu")).to_have_count(0)
    x, y = hold_block(phone, big.id)                                                  # held again (a fresh hold) it lifts, and then it moves
    expect(phone.locator(block(big.id))).to_have_class(re.compile(r"is-held"))
    fire(phone, "pointerup", x, y)


def test_a_selected_block_resized_past_most_of_the_screen_switches_to_scrolling_touch_and_back(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    select(phone, lunch.id)
    touch = "s => getComputedStyle(document.querySelector(s)).touchAction"
    assert phone.evaluate(touch, block(lunch.id)) == "none"
    phone.evaluate("s => { const e = document.querySelector(s); e.style.height = Math.round(innerHeight * 0.7) + 'px'; }", block(lunch.id))
    phone.wait_for_function("s => getComputedStyle(document.querySelector(s)).touchAction === 'pan-y pinch-zoom'", arg=block(lunch.id))
    phone.evaluate("s => { document.querySelector(s).style.height = '60px'; }", block(lunch.id))
    phone.wait_for_function("s => getComputedStyle(document.querySelector(s)).touchAction === 'none'", arg=block(lunch.id))


def test_renaming_puts_the_knobs_away_so_they_never_sit_on_the_title_field(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    select(phone, lunch.id)
    phone.locator('.cz-mi[data-do="rename"]').click()
    expect(phone.locator(".cz-gb-edit")).to_be_visible()
    assert phone.locator(".cz-g-knobs, .is-selected").count() == 0
    phone.keyboard.press("Escape")
    expect(phone.locator(".cz-gb-edit")).to_have_count(0)
    select(phone, lunch.id)                                                               # (a double tap cannot rename a selected block: its first tap only deselects)
    phone.locator(".cz-menu").evaluate("m => m.remove()")
    t = box(phone, f"{block(lunch.id)} .cz-gb-t")
    phone.touchscreen.tap(t["x"] + 10, t["y"] + t["height"] / 2)
    expect(phone.locator(".cz-g-knobs")).to_have_count(0)
    phone.wait_for_timeout(700)
    for _ in range(2):
        phone.touchscreen.tap(t["x"] + 10, t["y"] + t["height"] / 2)
        phone.wait_for_timeout(60)
    expect(phone.locator(".cz-gb-edit")).to_be_visible()
    assert phone.locator(".cz-g-knobs").count() == 0


def test_a_viewer_gets_no_knobs(canvas_page, browser, base_url):
    import uuid
    owner = canvas_page(viewport=PHONE)
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    mail = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
    try:
        ctx.set_default_timeout(9000)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day=2")
        page.wait_for_selector("#cz-grid")
        x, y = hold_block(page, lunch.id)
        fire(page, "pointerup", x, y)
        page.wait_for_timeout(300)
        assert page.locator(".cz-g-knobs, .is-selected").count() == 0
    finally:
        ctx.close()


# ---- a long block keeps its name in view -----------------------------------------------------------------------------------------------

def test_a_block_taller_than_the_screen_keeps_its_title_and_time_at_the_top_of_what_is_visible(phone):
    big = plan("Beach day with everyone", 7 * 60, 22 * 60)                                # fifteen hours: taller than the screen
    open_day(phone)
    sel = block(big.id)
    h = phone.viewport_size["height"]
    assert box(phone, sel)["height"] > h
    phone.evaluate("(sel) => { const r = document.querySelector(sel).getBoundingClientRect(); window.scrollBy(0, r.top - 200); }", sel)      # its top is 200px down: its title is where it was put
    phone.wait_for_timeout(60)
    natural = box(phone, f"{sel} .cz-gb-t")["y"]
    phone.evaluate("(sel) => { const r = document.querySelector(sel).getBoundingClientRect(); window.scrollBy(0, r.top + 150); }", sel)      # now its first 150px are above the top of the screen
    phone.wait_for_timeout(80)
    b = box(phone, sel)
    assert b["y"] < -140 and b["y"] + b["height"] > h                                     # the block's own top has gone off the screen
    t, w = box(phone, f"{sel} .cz-gb-t"), box(phone, f"{sel} .cz-gb-when")
    root = phone.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)")
    assert 0 <= t["y"] < 5.5 * root and w["y"] > t["y"] and w["y"] + w["height"] < 8 * root      # both are in view, just under the top of the screen (the folded bar's place)
    assert t["y"] < natural                                                              # it moved to keep up: the title is not where it began
    shot(phone, "sticky-title-390.png")
    phone.evaluate("(sel) => { const r = document.querySelector(sel).getBoundingClientRect(); window.scrollBy(0, r.bottom - 120); }", sel)      # the block's end is at the top: the title leaves with it
    phone.wait_for_timeout(80)
    t = box(phone, f"{sel} .cz-gb-t")
    assert t["y"] + t["height"] <= box(phone, sel)["y"] + box(phone, sel)["height"] + 1
    checks(phone)


def test_a_short_block_and_its_note_and_chat_count_still_show_all_their_words(phone):
    short = plan("Coffee", 10 * 60, 10 * 60 + 30)
    mid = plan("Museum visit", 13 * 60, 14 * 60 + 30)
    open_day(phone)
    for a in (short, mid):
        t = box(phone, f"{block(a.id)} .cz-gb-t")
        w = box(phone, f"{block(a.id)} .cz-gb-when")
        b = box(phone, block(a.id))
        assert t["y"] >= b["y"] - 0.5 and w["x"] >= b["x"]
    assert phone.evaluate(f"getComputedStyle(document.querySelector('{block(short.id)} .cz-gb-head')).display") == "contents"
    checks(phone)
