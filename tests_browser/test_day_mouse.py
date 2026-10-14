"""F-144: the desktop day with a mouse and a keyboard, in a real browser (a real mouse, at 1440 and 1280). Drag on empty time draws a new plan (a dashed outline with its times; Enter or
typing names it, Esc cancels); drag a plan to move it, pull the knob at its foot to resize (15-minute snap, the toast has Undo); hover shows the knob and a menu button, the button or a
right-click opens the phone's hold menu (rename, delete); T, the arrows, W, D and / are keys that do not fire while typing; a viewer gets none of the write moves; dragging past the
visible hours scrolls the grid card, and a wheel scroll during a hold keeps the plan under the pointer; the cards of plans scrolled into view are fetched ahead. The phone's own
touch tests (test_day_grid.py, test_day_knobs.py, test_day_new.py, test_day_menu.py) keep checking that nothing changed there. Screenshots on request: F144_SHOTS=<folder>."""
import os
import re
import uuid

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests_browser.helpers import DESKTOP
from tests_browser.test_day_grid import SUNDAY, ari, now, open_day, plan
from tests_browser.test_topbar import LAPTOP
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures

BOX = ".cz-view[data-day] .cz-day-body"


def shot(page, name):
    if os.environ.get("F144_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F144_SHOTS"], name))


@pytest.fixture(params=[DESKTOP, LAPTOP], ids=["1440", "1280"])
def desk(request, canvas_page):
    page = canvas_page(viewport=request.param, touch=False, motion="reduce")
    open_day(page, SUNDAY)
    return page


# ---- where things are ------------------------------------------------------------------------------------------------------------

def scroll_to(page, minute, at=0.4):
    """Scroll the grid card so `minute` is `at` of the way down it."""
    page.evaluate("""([m, at]) => { const b = document.querySelector('%s'), g = document.querySelector('#cz-grid'), z = g.querySelector('.cz-g-zoom');
      const ppm = z.offsetHeight / (+g.dataset.hi - +g.dataset.lo);
      const y = z.getBoundingClientRect().top - b.getBoundingClientRect().top + b.scrollTop + (m - +g.dataset.lo) * ppm;
      b.scrollTop = Math.max(0, y - b.clientHeight * at); }""" % BOX, [minute, at])
    page.wait_for_timeout(40)


def where(page, minute):
    """The screen y of a time, and the x of the middle of the plane."""
    return page.evaluate("""(m) => { const g = document.querySelector('#cz-grid'), z = g.querySelector('.cz-g-zoom'), p = g.querySelector('.cz-g-plane').getBoundingClientRect();
      return { y: z.getBoundingClientRect().top + (m - +g.dataset.lo) * z.offsetHeight / (+g.dataset.hi - +g.dataset.lo), x: p.left + p.width / 2 }; }""", minute)


def ppm(page):
    return page.evaluate("() => { const z = document.querySelector('.cz-g-zoom'), g = document.querySelector('#cz-grid'); return z.offsetHeight / (+g.dataset.hi - +g.dataset.lo); }")


def block(page, act):
    return page.locator(f'.cz-gb[data-act="{act}"]')


def center(page, act):
    b = block(page, act).bounding_box()
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


def drag(page, frm, to, steps=8):
    page.mouse.move(*frm)
    page.mouse.down()
    page.mouse.move(*to, steps=steps)
    page.mouse.up()


def toast(page):
    return page.locator(".ga-toast")


def titled(page, title):
    """The act id of the plan with this title on the page."""
    page.wait_for_function("t => [...document.querySelectorAll('.cz-gb[data-act] .cz-gb-t')].some(n => n.textContent.trim() === t)", arg=title)
    return page.locator(".cz-gb[data-act]").filter(has=page.locator(".cz-gb-t", has_text=title)).first.get_attribute("data-act")


# ---- draw ------------------------------------------------------------------------------------------------------------------------

def test_dragging_on_empty_time_draws_a_dashed_outline_with_its_times_then_a_name_makes_it_a_plan(desk):
    scroll_to(desk, 10 * 60)
    a, b = where(desk, 10 * 60 + 5), where(desk, 11 * 60 + 40)
    desk.mouse.move(a["x"], a["y"])
    desk.mouse.down()
    desk.mouse.move(b["x"], b["y"], steps=8)
    draft = desk.locator(".cz-gb.is-new.is-drawing")
    expect(draft).to_be_visible()
    expect(draft.locator(".cz-gb-when")).to_have_text("10:00 – 11:45 AM")                 # snapped to 15 minutes, both ends
    assert "dashed" in draft.evaluate("e => getComputedStyle(e).borderTopStyle")
    shot(desk, "draw.png")
    desk.mouse.up()
    field = desk.locator(".cz-gb-edit")
    expect(field).to_be_focused()                                                         # typing names it at once
    desk.keyboard.type("Brunch at the pier")
    desk.keyboard.press("Enter")
    act = titled(desk, "Brunch at the pier")
    assert now(act) == (10 * 60, 11 * 60 + 45, "Brunch at the pier")
    expect(toast(desk).get_by_role("button", name="Undo")).to_be_visible()
    assert desk.locator("#cz-dock").get_attribute("data-mode") == "idle"                  # drawing never opened the panel


def test_drawing_upwards_works_and_a_plan_is_never_shorter_than_15_minutes(desk):
    scroll_to(desk, 14 * 60)
    a, b = where(desk, 14 * 60 + 50), where(desk, 14 * 60 + 5)
    desk.mouse.move(a["x"], a["y"])
    desk.mouse.down()
    desk.mouse.move(b["x"], b["y"], steps=6)
    expect(desk.locator(".cz-gb.is-drawing .cz-gb-when")).to_have_text("2:00 – 3:00 PM")
    desk.mouse.move(b["x"], a["y"] - 1, steps=3)
    expect(desk.locator(".cz-gb.is-drawing .cz-gb-when")).to_have_text("2:45 – 3:00 PM")
    desk.mouse.up()
    desk.keyboard.press("Escape")


def test_escape_cancels_a_draw_in_the_air_and_a_name_being_typed(desk):
    scroll_to(desk, 10 * 60)
    a, b = where(desk, 10 * 60 + 5), where(desk, 11 * 60 + 30)
    desk.mouse.move(a["x"], a["y"])
    desk.mouse.down()
    desk.mouse.move(b["x"], b["y"], steps=6)
    expect(desk.locator(".cz-gb.is-drawing")).to_be_visible()
    desk.keyboard.press("Escape")
    expect(desk.locator(".cz-gb.is-new")).to_have_count(0)
    desk.mouse.up()
    expect(desk.locator(".cz-gb-edit")).to_have_count(0)                                  # nothing opened after the cancel
    drag(desk, (a["x"], a["y"]), (b["x"], b["y"]))
    expect(desk.locator(".cz-gb-edit")).to_be_focused()
    desk.keyboard.type("Never mind")
    desk.keyboard.press("Escape")
    expect(desk.locator(".cz-gb.is-new")).to_have_count(0)
    assert desk.locator(".cz-gb-t", has_text="Never mind").count() == 0 and desk.locator(".ga-toast").count() == 0


def test_a_plain_click_on_empty_time_still_makes_no_drag(desk):
    scroll_to(desk, 10 * 60)
    a = where(desk, 10 * 60 + 20)
    desk.mouse.click(a["x"], a["y"])
    assert desk.locator(".cz-gb.is-drawing").count() == 0


# ---- move and resize -------------------------------------------------------------------------------------------------------------

def test_dragging_a_plan_moves_it_in_15_minute_steps_and_undo_puts_it_back(desk):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    desk.reload()
    desk.wait_for_selector("#cz-grid")
    scroll_to(desk, 12 * 60 + 30)
    x, y = center(desk, lunch.id)
    pm = ppm(desk)
    desk.mouse.move(x, y)
    desk.mouse.down()
    desk.mouse.move(x, y + 3, steps=2)
    assert desk.locator(".cz-gb.is-held").count() == 0                                    # a click's own jitter is not a drag
    desk.mouse.move(x, y + 47 * pm, steps=8)                                               # about 47 minutes down
    expect(desk.locator(".cz-g-label")).to_contain_text("12:45 – 1:45 PM")                 # snapped to the nearest 15
    shot(desk, "move.png")
    desk.mouse.up()
    expect(toast(desk).get_by_role("button", name="Undo")).to_be_visible()
    desk.wait_for_function("(id) => { const b = document.querySelector('.cz-gb[data-act=\"' + id + '\"]'); return b && +b.dataset.s === 765; }", arg=lunch.id)
    assert now(lunch.id)[:2] == (12 * 60 + 45, 13 * 60 + 45)
    toast(desk).get_by_role("button", name="Undo").click()
    desk.wait_for_function("(id) => { const b = document.querySelector('.cz-gb[data-act=\"' + id + '\"]'); return b && +b.dataset.s === 720; }", arg=lunch.id)
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60)


def test_a_click_or_a_small_wobble_on_a_plan_still_opens_it_in_the_panel(desk):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    desk.reload()
    desk.wait_for_selector("#cz-grid")
    scroll_to(desk, 12 * 60 + 30)
    x, y = center(desk, lunch.id)
    drag(desk, (x, y), (x + 2, y + 3), steps=3)
    expect(desk.locator("#cz-dock .cz-pp:not(.is-leaving)")).to_be_visible()
    assert desk.locator("#cz-dock").get_attribute("data-mode") == "plan" and now(lunch.id)[:2] == (12 * 60, 13 * 60)


def test_hover_shows_the_knob_and_the_menu_button_and_the_knob_resizes(desk):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    desk.reload()
    desk.wait_for_selector("#cz-grid")
    scroll_to(desk, 12 * 60 + 30)
    expect(desk.locator(".cz-g-tools")).to_have_count(0)                                   # nothing at rest
    x, y = center(desk, lunch.id)
    desk.mouse.move(x, y)
    knob, more = desk.locator(".cz-g-tknob"), desk.locator(".cz-g-tmenu")
    expect(knob).to_be_visible()
    expect(more).to_be_visible()
    shot(desk, "hover.png")
    k = knob.bounding_box()
    b = block(desk, lunch.id).bounding_box()
    assert abs((k["x"] + k["width"] / 2) - (b["x"] + b["width"] / 2)) < 4 and abs((k["y"] + k["height"] / 2) - (b["y"] + b["height"])) < 8      # at the foot, in the middle
    pm = ppm(desk)
    kx, ky = k["x"] + k["width"] / 2, k["y"] + k["height"] / 2
    desk.mouse.move(kx, ky)
    desk.mouse.down()
    desk.mouse.move(kx, ky + 32 * pm, steps=8)                                             # about 32 minutes longer
    expect(desk.locator(".cz-g-label")).to_contain_text("12:00 – 1:30 PM")
    shot(desk, "resize.png")
    desk.mouse.up()
    expect(toast(desk).get_by_role("button", name="Undo")).to_be_visible()
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60 + 30)
    toast(desk).get_by_role("button", name="Undo").click()
    desk.wait_for_function("(id) => { const b = document.querySelector('.cz-gb[data-act=\"' + id + '\"]'); return b && +b.dataset.e === 780; }", arg=lunch.id)
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60)


def test_the_menu_button_and_a_right_click_open_rename_and_delete_and_escape_closes_the_menu_first(desk):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    desk.reload()
    desk.wait_for_selector("#cz-grid")
    scroll_to(desk, 12 * 60 + 30)
    x, y = center(desk, lunch.id)
    desk.mouse.move(x, y)
    desk.locator(".cz-g-tmenu").click()
    menu = desk.locator(".cz-menu")
    expect(menu).to_be_visible()
    expect(menu.get_by_role("menuitem", name="Rename")).to_be_visible()
    expect(menu.get_by_role("menuitem", name="Delete")).to_be_visible()
    shot(desk, "menu.png")
    desk.keyboard.press("Escape")
    expect(menu).to_have_count(0)
    assert desk.locator(".cz-view").get_attribute("data-level") == "day"                    # Esc went to the menu, not up a level
    desk.mouse.move(x, y + 4)
    block(desk, lunch.id).click(button="right", position={"x": 20, "y": 20})
    expect(desk.locator(".cz-menu")).to_be_visible()
    desk.locator(".cz-menu").get_by_role("menuitem", name="Rename").click()
    field = desk.locator(".cz-gb-edit")
    expect(field).to_be_focused()
    desk.keyboard.type("Late lunch")
    desk.keyboard.press("Enter")
    desk.wait_for_function("() => /Late lunch/.test(document.querySelector('.cz-gb[data-act] .cz-gb-t').textContent)")
    assert now(lunch.id)[2] == "Late lunch"


def test_escape_closes_the_panel_only_when_nothing_inner_is_open(desk):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    desk.reload()
    desk.wait_for_selector("#cz-grid")
    scroll_to(desk, 12 * 60 + 30)
    x, y = center(desk, lunch.id)
    desk.mouse.click(x, y)
    expect(desk.locator("#cz-dock .cz-pp:not(.is-leaving)")).to_be_visible()
    desk.mouse.move(x, y + 2)
    desk.locator(".cz-g-tmenu").click()
    expect(desk.locator(".cz-menu")).to_be_visible()
    desk.keyboard.press("Escape")
    expect(desk.locator(".cz-menu")).to_have_count(0)
    assert desk.locator("#cz-dock").get_attribute("data-mode") == "plan"                    # the menu went first
    desk.keyboard.press("Escape")
    desk.wait_for_function("() => document.getElementById('cz-dock').dataset.mode === 'idle'")


# ---- keys ------------------------------------------------------------------------------------------------------------------------

def day_now(page):
    return page.locator(".cz-view").get_attribute("data-day")


def test_the_arrows_change_the_day_and_w_and_d_switch_week_and_day(desk):
    assert day_now(desk) == str(SUNDAY)
    desk.keyboard.press("ArrowRight")
    desk.wait_for_function("d => document.querySelector('.cz-view').dataset.day === d", arg=str(SUNDAY + 1))
    desk.keyboard.press("ArrowLeft")
    desk.wait_for_function("d => document.querySelector('.cz-view').dataset.day === d", arg=str(SUNDAY))
    desk.keyboard.press("w")
    desk.wait_for_selector(".cz-view[data-level=week]")
    desk.keyboard.press("d")
    desk.wait_for_selector(".cz-view[data-level=day]")


def test_t_goes_to_today_when_the_trip_has_it_and_says_so_when_it_does_not(desk):
    desk.keyboard.press("ArrowRight")
    desk.wait_for_function("d => document.querySelector('.cz-view').dataset.day === d", arg=str(SUNDAY + 1))
    today = desk.locator(".cz-hchip.is-today")
    if today.count():
        want = re.search(r"day=(\d+)", today.get_attribute("href")).group(1)
        desk.keyboard.press("t")
        desk.wait_for_function("d => document.querySelector('.cz-view').dataset.day === d", arg=want)
    else:
        desk.keyboard.press("t")
        expect(toast(desk)).to_contain_text("Today")
        assert day_now(desk) == str(SUNDAY + 1)


def test_slash_goes_to_ask_for_the_day_until_the_ask_mode_is_there(desk):
    has = desk.evaluate("() => !!(window.Dock && Dock.has('ask'))")
    desk.keyboard.press("/")
    if has:
        desk.wait_for_function("() => document.getElementById('cz-dock').dataset.mode === 'ask'")
    else:
        desk.wait_for_url(re.compile(r"/trip/ask"))      # (the Ask tab's own link; the page drops the day from the address)


def test_no_key_fires_while_typing(desk):
    scroll_to(desk, 10 * 60)
    a, b = where(desk, 10 * 60 + 5), where(desk, 11 * 60)
    drag(desk, (a["x"], a["y"]), (b["x"], b["y"]))
    field = desk.locator(".cz-gb-edit")
    expect(field).to_be_focused()
    desk.keyboard.type("t w d / ")
    desk.keyboard.press("ArrowLeft")
    assert field.input_value().startswith("t w d /") and day_now(desk) == str(SUNDAY) and "/trip/canvas" in desk.url
    desk.keyboard.press("Escape")
    desk.keyboard.press("w")                                                              # and once nothing is being typed, they work
    desk.wait_for_selector(".cz-view[data-level=week]")


def test_the_modifier_keys_are_left_to_the_browser(desk):
    desk.keyboard.press("Control+ArrowRight")
    desk.wait_for_timeout(150)
    assert day_now(desk) == str(SUNDAY)


# ---- who may ---------------------------------------------------------------------------------------------------------------------

def test_a_viewer_gets_no_write_moves_but_keeps_the_keys(canvas_page, browser, base_url):
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
        assert page.locator("#cz").get_attribute("data-edit") is None
        scroll_to(page, 12 * 60 + 30)
        x, y = center(page, lunch.id)
        page.mouse.move(x, y)
        page.wait_for_timeout(150)
        assert page.locator(".cz-g-tools").count() == 0
        a, b = where(page, 9 * 60 + 5), where(page, 10 * 60 + 40)
        drag(page, (a["x"], a["y"]), (b["x"], b["y"]))
        assert page.locator(".cz-gb.is-new, .cz-gb-edit").count() == 0
        pm = ppm(page)
        drag(page, (x, y), (x, y + 60 * pm))
        page.wait_for_timeout(200)
        assert now(lunch.id)[:2] == (12 * 60, 13 * 60) and page.locator(".ga-toast").count() == 0
        page.mouse.click(x, y)                                                             # (a click still opens the plan: that is reading)
        page.keyboard.press("Escape")
        page.keyboard.press("ArrowRight")
        page.wait_for_function("d => document.querySelector('.cz-view').dataset.day === d", arg=str(SUNDAY + 1))
    finally:
        ctx.close()


# ---- the grid card scrolls, not the window ----------------------------------------------------------------------------------------

def card_scroll(page):
    return page.evaluate("(sel) => document.querySelector(sel).scrollTop", BOX)


def test_dragging_past_the_visible_hours_scrolls_the_card_and_a_wheel_keeps_the_plan_under_the_pointer(desk):
    early = plan("Early walk", 8 * 60, 9 * 60)
    desk.reload()
    desk.wait_for_selector("#cz-grid")
    desk.evaluate("(sel) => { document.querySelector(sel).scrollTop = 0; }", BOX)
    desk.wait_for_timeout(50)
    x, y = center(desk, early.id)
    box = desk.locator(BOX).bounding_box()
    desk.mouse.move(x, y)
    desk.mouse.down()
    desk.mouse.move(x, y + 30, steps=4)                                                    # lifted
    expect(desk.locator(".cz-g-label")).to_be_visible()
    before = card_scroll(desk)
    desk.mouse.move(x, box["y"] + box["height"] - 6, steps=6)                              # at the card's foot
    desk.wait_for_timeout(700)
    assert card_scroll(desk) > before + 40                                                 # the card scrolled
    assert desk.evaluate("window.scrollY") == 0                                            # the window did not
    # a wheel during the hold: the plan stays where the pointer is
    py = box["y"] + box["height"] / 2
    desk.mouse.move(x, py, steps=4)
    desk.wait_for_timeout(120)
    grab = py - block(desk, early.id).bounding_box()["y"]
    at = card_scroll(desk)
    desk.mouse.wheel(0, -90)
    desk.wait_for_timeout(300)
    assert card_scroll(desk) != at
    now_top = block(desk, early.id).bounding_box()["y"]
    assert abs((py - now_top) - grab) < 4, (py, now_top, grab)                             # still under the pointer, same grab
    desk.mouse.up()
    desk.wait_for_timeout(300)
    assert now(early.id)[0] > 8 * 60 and now(early.id)[0] % 15 == 0


def test_the_cards_of_plans_scrolled_into_view_in_the_grid_card_are_fetched_ahead(desk):
    late = plan("Late show", 21 * 60, 22 * 60 - 15)
    desk.reload()
    desk.wait_for_selector("#cz-grid")
    desk.evaluate("(sel) => { document.querySelector(sel).scrollTop = 0; }", BOX)
    desk.wait_for_timeout(900)
    asked = []
    desk.on("request", lambda r: asked.append(r.url) if "/trip/canvas/card" in r.url and late.id in r.url else None)
    desk.evaluate("(sel) => { const b = document.querySelector(sel); b.scrollTop = b.scrollHeight; }", BOX)
    desk.wait_for_timeout(1200)
    assert asked, "the card of the plan that scrolled into view was not fetched"
