"""F-152: Change type and Move to day in the plan menu, in a real browser. The phone's hold menu (390, a finger) and the laptop's ⋯ and right-click menu (1440, a mouse) are the same menu
(day_menu.js): "Change type" and "Move to day…" open a second step in it with large choices (no dropdown). Change type: the five kinds with their icons and colours, the plan's own marked;
one tap saves ("Lunch is now Food", Undo). Move to day: the trip's days as chips, the plan's own day marked and not a button; one tap saves ("Moved to Sat 17", Undo), the plan leaves the day
in place. On a laptop a move sends an open panel back to Up next and a type change keeps it open. A viewer has neither. Screenshots on request: F152_SHOTS=<folder>."""
import os
import re
import uuid

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_day_grid import SUNDAY, ari, box, checks, open_day, plan
from tests_browser.test_day_menu import hold_and_let_go
from tests_browser.test_day_mouse import center, scroll_to, toast
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures

SATURDAY = SUNDAY - 1


def block(act):
    return f'.cz-gb[data-act="{act}"]'


def shot(page, name):
    if os.environ.get("F152_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F152_SHOTS"], name))


def got(act):
    return cal.get_activity(ari(), act)


@pytest.fixture
def phone(canvas_page):
    page = canvas_page(viewport=PHONE, motion="no-preference")
    return page


@pytest.fixture
def desk(canvas_page):
    return canvas_page(viewport=DESKTOP, touch=False, motion="reduce")


def item(page, name):
    return page.locator(".cz-menu").get_by_role("menuitem", name=re.compile(rf"^{name}"))


def settled(page):
    page.wait_for_function("document.querySelector('.cz-menu') && document.querySelector('.cz-menu').getAnimations({subtree: true}).length === 0")


def lunch_on(page, kind="fun"):
    p = plan("Lunch", 12 * 60, 13 * 60, kind=kind)
    open_day(page, SUNDAY)
    return p


def laptop_menu(page, act, how="button"):
    scroll_to(page, 12 * 60 + 30)
    x, y = center(page, act)
    page.mouse.move(x, y)
    if how == "button":
        page.locator(".cz-g-tmenu").click()
    else:
        page.mouse.click(x, y, button="right")
    expect(page.locator(".cz-menu")).to_be_visible()


# ---- the phone ---------------------------------------------------------------------------------------------------------------------

def test_the_phone_menu_has_both_items_and_change_type_offers_the_kinds_with_the_current_one_marked(phone):
    lunch = lunch_on(phone)
    hold_and_let_go(phone, lunch.id)
    settled(phone)
    phone.wait_for_timeout(300)
    shot(phone, "menu-390.png")
    item(phone, "Change type").tap()
    kinds = phone.locator(".cz-menu-kinds .cz-mi")
    expect(kinds).to_have_count(5)
    assert [t.strip() for t in kinds.all_inner_texts()] == ["Fun", "Food", "Outdoors", "Culture", "Travel"]
    assert [kinds.nth(i).get_attribute("aria-checked") for i in range(5)] == ["true", "false", "false", "false", "false"]
    assert phone.locator(".cz-menu select, .cz-menu option").count() == 0
    phone.wait_for_timeout(500)
    shot(phone, "type-390.png")
    checks(phone)
    m, w = box(phone, ".cz-menu"), phone.viewport_size["width"]
    assert m["x"] >= 7 and m["x"] + m["width"] <= w - 7


def test_a_tap_on_a_kind_saves_it_at_once_with_a_toast_and_undo_and_the_plan_changes_colour_in_place(phone):
    lunch = lunch_on(phone)
    hold_and_let_go(phone, lunch.id)
    item(phone, "Change type").tap()
    phone.locator(".cz-menu-kinds .cz-mi", has_text="Food").tap()
    expect(toast(phone)).to_contain_text("Lunch is now Food")
    expect(phone.locator(".cz-menu")).to_have_count(0)
    assert got(lunch.id).kind == "food" and (got(lunch.id).start, got(lunch.id).end, got(lunch.id).day) == (720, 780, SUNDAY)
    expect(phone.locator(block(lunch.id))).to_have_class(re.compile(r"cz-k-food"))
    expect(phone.locator(block(lunch.id))).to_have_attribute("data-type", "food")
    toast(phone).get_by_role("button", name=re.compile("Undo")).tap()
    expect(phone.locator(block(lunch.id))).to_have_class(re.compile(r"cz-k-fun"))
    assert got(lunch.id).kind == "fun"


def test_move_to_day_offers_the_trips_days_without_the_plans_own_and_one_tap_moves_it(phone):
    lunch = lunch_on(phone)
    hold_and_let_go(phone, lunch.id)
    settled(phone)
    item(phone, "Move to day").tap()
    days = phone.locator(".cz-menu-days .cz-dc")
    n = len(cal.get_activity(ari(), lunch.id) and phone.locator(".cz-dpills [data-move-day]").all())
    expect(days).to_have_count(n)
    here = phone.locator(".cz-menu-days .cz-dc.is-here")
    expect(here).to_have_count(1)
    assert here.evaluate("e => e.tagName") == "SPAN" and "where it is now" in here.get_attribute("aria-label")
    expect(phone.locator(".cz-menu-days button.cz-dc")).to_have_count(n - 1)
    phone.wait_for_timeout(500)
    shot(phone, "day-390.png")
    checks(phone)
    phone.locator('.cz-menu-days button[aria-label="Move to Sat 17"]').tap()
    expect(toast(phone)).to_contain_text("Moved to Sat 17")
    assert got(lunch.id).day == SATURDAY and (got(lunch.id).start, got(lunch.id).end) == (720, 780)
    expect(phone.locator(block(lunch.id))).to_have_count(0)
    toast(phone).get_by_role("button", name=re.compile("Undo")).tap()
    phone.wait_for_function("([a, d]) => !!document.querySelector(`.cz-gb[data-act=\"${a}\"]`)", arg=[lunch.id, SUNDAY])
    assert got(lunch.id).day == SUNDAY


def test_back_returns_to_the_first_step_and_the_nudges_still_work(phone):
    lunch = lunch_on(phone)
    hold_and_let_go(phone, lunch.id)
    settled(phone)
    item(phone, "Change type").tap()
    item(phone, "Back").tap()
    expect(item(phone, "Rename")).to_be_visible()
    item(phone, "Later").tap()
    expect(toast(phone)).to_contain_text("moved")
    assert got(lunch.id).start == 735 and got(lunch.id).kind == "fun"


def test_a_failed_save_says_so_and_changes_nothing(phone):
    lunch = lunch_on(phone)
    hold_and_let_go(phone, lunch.id)
    item(phone, "Change type").tap()
    phone.route("**/trip/canvas/plan", lambda r: r.abort())
    phone.locator(".cz-menu-kinds .cz-mi", has_text="Travel").tap()
    expect(toast(phone)).to_contain_text("Could not save")
    assert got(lunch.id).kind == "fun"


# ---- the laptop --------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("how", ["button", "right-click"])
def test_the_laptop_menu_opened_by_the_dots_or_a_right_click_has_both_steps_and_a_mouse_picks(desk, how):
    lunch = lunch_on(desk)
    laptop_menu(desk, lunch.id, how)
    desk.wait_for_timeout(400)
    shot(desk, f"menu-1440-{how}.png")
    item(desk, "Change type").click()
    expect(desk.locator(".cz-menu-kinds .cz-mi")).to_have_count(5)
    desk.wait_for_timeout(400)
    shot(desk, f"type-1440-{how}.png")
    desk.locator(".cz-menu-kinds .cz-mi", has_text="Culture").click()
    expect(toast(desk)).to_contain_text("Lunch is now Culture")
    assert got(lunch.id).kind == "culture"
    expect(desk.locator(block(lunch.id))).to_have_class(re.compile(r"cz-k-culture"))
    laptop_menu(desk, lunch.id, how)
    item(desk, "Move to day").click()
    desk.wait_for_timeout(400)
    shot(desk, f"day-1440-{how}.png")
    desk.locator('.cz-menu-days button[aria-label="Move to Sat 17"]').click()
    expect(toast(desk)).to_contain_text("Moved to Sat 17")
    assert got(lunch.id).day == SATURDAY
    expect(desk.locator(block(lunch.id))).to_have_count(0)


def test_a_move_sends_an_open_panel_back_to_up_next_and_a_type_change_keeps_it_open_and_up_to_date(desk):
    lunch = lunch_on(desk)
    scroll_to(desk, 12 * 60 + 30)
    x, y = center(desk, lunch.id)
    desk.mouse.click(x, y)
    desk.wait_for_function("() => document.querySelector('#cz-dock').dataset.mode === 'plan'")
    laptop_menu(desk, lunch.id)
    item(desk, "Change type").click()
    desk.locator(".cz-menu-kinds .cz-mi", has_text="Outdoors").click()
    expect(toast(desk)).to_contain_text("Lunch is now Outdoors")
    desk.wait_for_function("() => document.querySelector('#cz-dock').dataset.mode === 'plan'")
    pane = desk.locator("#cz-dock .cz-pp:not(.is-leaving)")
    assert pane.get_attribute("data-act") == lunch.id
    desk.wait_for_function("() => /cz-k-outdoors/.test(document.querySelector('#cz-dock .cz-pp-ic').className)")
    shot(desk, "panel-type-1440.png")
    laptop_menu(desk, lunch.id)
    item(desk, "Move to day").click()
    desk.locator('.cz-menu-days button[aria-label="Move to Sat 17"]').click()
    expect(toast(desk)).to_contain_text("Moved to Sat 17")
    desk.wait_for_function("() => document.querySelector('#cz-dock').dataset.mode === 'idle'")


# ---- who gets it -------------------------------------------------------------------------------------------------------------------

def test_a_viewer_has_neither_item_and_the_choices_are_not_even_on_the_page(canvas_page, browser, base_url):
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
        page.mouse.click(x, y, button="right")
        page.wait_for_timeout(300)
        assert page.locator(".cz-menu").count() == 0 and page.locator(".cz-g-tmenu").count() == 0 and page.locator("#cz-kinds-tpl").count() == 0
    finally:
        ctx.close()
