"""F-098: the hold menu, rename in place and delete on the day grid, in a real browser at 390 and 320. Hold a block and let go without moving: it wiggles and a small menu offers
Chat, Rename, Delete (asks once, Undo after) and Earlier, Later, Shorter, Longer by 15 minutes; every item is pressed. Two quick taps on a title edit it in place (Enter or tapping
away saves, Escape cancels, an empty or too-long title is refused plainly); a tap still opens a park block; a viewer has none of it; the keyboard has the menu too; reduced motion
does not wiggle. A finger is a pointer that goes down, waits and lets go (synthetic pointer events) or a real touch tap (Playwright's touchscreen). Screenshots on request: F097_SHOTS=<folder>."""
import re

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests_browser.helpers import PHONE
from tests_browser.test_day_grid import (SUNDAY, ari, box, checks, fire, hold_block, now, open_day, plan, shot, show, toast)
from tests_browser.test_trip_canvas import NARROW, canvas_page, model, settle  # noqa: F401 - fixtures


@pytest.fixture(params=[PHONE, NARROW], ids=["390", "320"])
def phone(request, canvas_page):
    return canvas_page(viewport=request.param)


def block(act):
    return f'.cz-gb[data-act="{act}"]'


def hold_and_let_go(page, act):
    x, y = hold_block(page, act)
    fire(page, "pointerup", x, y)
    expect(page.locator(".cz-menu")).to_be_visible()
    return x, y


def menu_item(page, name):
    return page.locator(".cz-menu").get_by_role("menuitem", name=re.compile(rf"^{name}"))


# ---- the menu ---------------------------------------------------------------------------------------------------------------------

def test_hold_and_let_go_wiggles_the_block_and_offers_the_menu_with_every_choice(canvas_page):
    page = canvas_page(viewport=PHONE, motion="no-preference")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    hold_and_let_go(page, lunch.id)
    expect(page.locator(block(lunch.id))).to_have_class(re.compile(r"is-wiggle"))
    assert page.locator(block(lunch.id)).evaluate("e => e.getAnimations().some(a => a.animationName === 'cz-wiggle')")
    assert page.locator(".cz-g-label, .cz-g-ghost").count() == 0 and page.evaluate("CZ.held") is False        # it was not moved: nothing is lifted any more
    menu = page.locator(".cz-menu")
    assert menu.get_attribute("role") == "menu"
    names = [t.strip() for t in menu.get_by_role("menuitem").all_inner_texts()]
    assert names == ["Chat", "Rename", "Delete", "Earlier", "Later", "Shorter", "Longer"]
    assert "/trip/talk?act=" in menu.get_by_role("menuitem", name="Chat").get_attribute("href")
    shot(page, "menu-390.png")
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60) and page.locator(".ga-toast").count() == 0
    checks(page)                                                                    # 44px targets, 13px text, no sideways scroll, with the menu open


def test_the_menu_is_beside_the_block_on_the_screen_at_both_widths(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    late = plan("Dinner", 20 * 60, 21 * 60)
    open_day(phone)
    for act in (lunch.id, late.id):
        hold_and_let_go(phone, act)
        m, b, w, h = box(phone, ".cz-menu"), box(phone, block(act)), phone.viewport_size["width"], phone.viewport_size["height"]
        assert m["x"] >= 7 and m["x"] + m["width"] <= w - 7 and m["y"] >= 7 and m["y"] + m["height"] <= h
        assert m["y"] >= b["y"] + b["height"] - 1 or m["y"] + m["height"] <= b["y"] + 1                            # under the block or over it, never across it
        phone.keyboard.press("Escape")
        expect(phone.locator(".cz-menu")).to_have_count(0)


def test_chat_opens_the_plans_chat(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    hold_and_let_go(phone, lunch.id)
    menu_item(phone, "Chat").click()
    phone.wait_for_url(re.compile(r"/trip/talk\?act=" + lunch.id))
    expect(phone.locator("#ft-compose")).to_be_visible()


def test_rename_in_the_menu_edits_the_title_in_place_and_saves_with_enter(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    hold_and_let_go(phone, lunch.id)
    menu_item(phone, "Rename").click()
    field = phone.locator(f"{block(lunch.id)} .cz-gb-edit")
    expect(field).to_be_focused()
    assert field.input_value() == "Lunch" and phone.locator(".cz-menu").count() == 0
    field.fill("Tacos at the pier")
    field.press("Enter")
    expect(toast(phone)).to_contain_text("Renamed to Tacos at the pier")
    assert now(lunch.id)[2] == "Tacos at the pier"
    expect(phone.locator(f"{block(lunch.id)} .cz-gb-t")).to_have_text("Tacos at the pier")
    assert phone.locator(".cz-gb-edit").count() == 0
    toast(phone).get_by_role("button", name="Undo").click()
    expect(toast(phone)).to_have_text("Put back")
    assert now(lunch.id)[2] == "Lunch"
    checks(phone)


def test_delete_asks_once_keep_it_goes_back_and_delete_has_an_undo(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    hold_and_let_go(phone, lunch.id)
    menu_item(phone, "Delete").click()
    expect(phone.locator(".cz-menu")).to_contain_text("Delete Lunch?")
    assert cal.get_activity(ari(), lunch.id) is not None
    checks(phone)
    phone.get_by_role("menuitem", name=re.compile("^Keep")).click()               # changed its mind
    expect(phone.locator(".cz-menu").get_by_role("menuitem", name="Chat")).to_be_visible()
    assert cal.get_activity(ari(), lunch.id) is not None
    menu_item(phone, "Delete").click()
    phone.get_by_role("menuitem", name=re.compile("^Delete")).click()
    expect(toast(phone)).to_contain_text("Lunch deleted")
    expect(phone.locator(block(lunch.id))).to_have_count(0)
    assert cal.get_activity(ari(), lunch.id) is None and phone.locator(".cz-menu").count() == 0
    toast(phone).get_by_role("button", name="Undo").click()
    expect(toast(phone)).to_contain_text("Lunch is back")
    expect(phone.locator(block(lunch.id))).to_have_count(1)
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60)


def test_deleting_a_park_day_says_what_goes_with_it_and_undo_brings_every_step_back(phone):
    open_day(phone, 1)
    act = phone.locator(".cz-gb.is-park").get_attribute("data-act")
    hold_and_let_go(phone, act)
    menu_item(phone, "Delete").click()
    expect(phone.locator(".cz-menu")).to_contain_text("Its 16 steps go with it")
    phone.get_by_role("menuitem", name=re.compile("^Delete")).click()
    expect(toast(phone)).to_contain_text("Universal Studios Hollywood and its 16 steps deleted")
    toast(phone).get_by_role("button", name="Undo").click()
    expect(toast(phone)).to_contain_text("is back")
    phone.locator(".cz-gb-open").click(position={"x": 90, "y": 40})
    phone.locator("#cz-card-rides").click()      # F-106: a tap opens the card; Rides is the way to the block level
    expect(phone.locator(".cz-view[data-level=block]")).to_be_visible()
    assert phone.locator(".cz-swipe").count() == 14


def test_earlier_later_shorter_and_longer_move_by_fifteen_minutes_and_the_menu_stays(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    hold_and_let_go(phone, lunch.id)
    for name, expect_times, words in (("Later", (12 * 60 + 15, 13 * 60 + 15), "moved to 12:15 PM"), ("Earlier", (12 * 60, 13 * 60), "moved to 12:00 PM"),
                                      ("Longer", (12 * 60, 13 * 60 + 15), "now ends 1:15 PM"), ("Shorter", (12 * 60, 13 * 60), "now ends 1:00 PM")):
        menu_item(phone, name).click()
        expect(toast(phone)).to_contain_text(words)
        assert now(lunch.id)[:2] == expect_times, name
        expect(phone.locator(".cz-menu")).to_be_visible()                       # still there for the next nudge
        expect(menu_item(phone, name)).to_be_focused()
    expect(toast(phone).get_by_role("button", name="Undo")).to_be_visible()
    toast(phone).get_by_role("button", name="Undo").click()
    expect(toast(phone)).to_have_text("Put back")
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60 + 15)                         # undid the last nudge only
    checks(phone)


def test_a_nudge_that_would_leave_the_day_or_the_minimum_is_not_offered(phone):
    from gitaway import planedit
    first = plan("Early", 7 * 60, 7 * 60 + 30)
    planedit.change(ari(), first.id, end=7 * 60 + 15)                                  # a 15-minute plan, which only the grid can make
    last = plan("Late", 21 * 60 + 30, 22 * 60)
    planedit.change(ari(), last.id, start=21 * 60 + 45)
    open_day(phone)
    hold_and_let_go(phone, first.id)
    assert menu_item(phone, "Earlier").is_disabled() and menu_item(phone, "Shorter").is_disabled()
    assert menu_item(phone, "Later").is_enabled() and menu_item(phone, "Longer").is_enabled()
    phone.keyboard.press("Escape")
    hold_and_let_go(phone, last.id)
    assert menu_item(phone, "Later").is_disabled() and menu_item(phone, "Longer").is_disabled() and menu_item(phone, "Earlier").is_enabled()


def test_a_refresh_that_was_fetched_before_a_nudge_never_redraws_the_block_as_it_was(phone):
    """Review (F-101 session): under load a nudge's refresh answered after the next nudge had started and redrew the block as it was before, so the next tap started from the
    old time (Shorter applied twice: "now ends 12:45 PM"). Each refresh is fetched at once but answered by the test late, in the order it likes."""
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    held = []

    def hold_back(route):
        if held:
            route.continue_()
        else:
            held.append((route, route.fetch()))                # the first refresh only: the server's answer as it is now, handed to the page later

    phone.route(re.compile(rf".*day={SUNDAY}&frag=1$"), hold_back)
    hold_and_let_go(phone, lunch.id)
    menu_item(phone, "Longer").click()
    expect(toast(phone)).to_contain_text("now ends 1:15 PM")
    deadline = 40
    while not held and deadline:
        phone.wait_for_timeout(50)
        deadline -= 1
    assert held, "the first nudge's refresh was never asked for"
    menu_item(phone, "Shorter").click()
    expect(toast(phone)).to_contain_text("now ends 1:00 PM")
    first = held[0]
    first[0].fulfill(response=first[1])                          # the old answer (the block as it was after the first nudge only) arrives now
    phone.wait_for_timeout(400)
    assert phone.locator(block(lunch.id)).get_attribute("data-e") == str(13 * 60)            # it is not drawn again
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60)
    menu_item(phone, "Shorter").click()                          # and the next tap starts from the true time
    expect(toast(phone)).to_contain_text("now ends 12:45 PM")


def test_tapping_away_puts_the_menu_away_and_does_nothing_else(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    hold_and_let_go(phone, lunch.id)
    b = box(phone, block(lunch.id))
    phone.touchscreen.tap(8, b["y"] + b["height"] / 2)                                # empty grid beside the hours, clear of the menu
    expect(phone.locator(".cz-menu")).to_have_count(0)
    expect(phone.locator(".is-wiggle, .is-menu")).to_have_count(0)
    assert phone.locator(".ga-toast").count() == 0 and phone.locator(".cz-view").get_attribute("data-level") == "day"


def test_a_park_block_menu_and_a_tap_that_still_opens_it(phone):
    open_day(phone, 1)
    act = phone.locator(".cz-gb.is-park").get_attribute("data-act")
    hold_and_let_go(phone, act)
    phone.keyboard.press("Escape")
    expect(phone.locator(".cz-menu")).to_have_count(0)
    assert phone.locator(".cz-view").get_attribute("data-level") == "day"
    phone.wait_for_timeout(400)                                                    # the click a lifting finger makes is not a tap: a real tap comes later
    phone.locator(".cz-gb-open").click(position={"x": 90, "y": 120})               # a tap on the body of the block opens it at once
    phone.locator("#cz-card-rides").click()      # F-106: a tap opens the card; Rides is the way to the block level
    expect(phone.locator(".cz-view[data-level=block]")).to_be_visible()


# ---- the keyboard and the screen reader ---------------------------------------------------------------------------------------------

def test_the_keyboard_has_the_menu_too_and_escape_closes_it_without_zooming_out(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    btn = phone.locator(f"{block(lunch.id)} .cz-gb-menubtn")
    btn.focus()
    phone.keyboard.press("Enter")
    expect(phone.locator(".cz-menu")).to_be_visible()
    expect(menu_item(phone, "Chat")).to_be_focused()
    phone.keyboard.press("ArrowRight")
    expect(menu_item(phone, "Rename")).to_be_focused()
    phone.keyboard.press("End")
    expect(phone.get_by_role("menuitemcheckbox", name=re.compile("^Fine"))).to_be_focused()
    phone.keyboard.press("ArrowUp")
    expect(menu_item(phone, "Longer")).to_be_focused()
    phone.keyboard.press("Enter")
    expect(toast(phone)).to_contain_text("now ends 1:15 PM")
    phone.keyboard.press("Escape")
    expect(phone.locator(".cz-menu")).to_have_count(0)
    assert phone.locator(".cz-view").get_attribute("data-level") == "day"           # Escape put the menu away, not the day
    expect(phone.locator(f"{block(lunch.id)} .cz-gb-menubtn")).to_be_focused()
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60 + 15)


# ---- rename in place --------------------------------------------------------------------------------------------------------------------

def double_tap_title(page, act):
    t = box(page, f"{block(act)} .cz-gb-t")
    x, y = t["x"] + min(t["width"] / 2, 30), t["y"] + t["height"] / 2
    page.touchscreen.tap(x, y)
    page.wait_for_timeout(110)
    page.touchscreen.tap(x, y)


def test_a_double_tap_on_the_title_edits_it_in_place_and_enter_saves(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    show(phone, block(lunch.id))
    double_tap_title(phone, lunch.id)
    field = phone.locator(f"{block(lunch.id)} .cz-gb-edit")
    expect(field).to_be_focused()
    assert box(phone, ".cz-gb-edit")["height"] >= 40 and phone.evaluate("parseFloat(getComputedStyle(document.querySelector('.cz-gb-edit')).fontSize)") >= 16
    field.fill("Late lunch")
    field.press("Enter")
    expect(toast(phone)).to_contain_text("Renamed to Late lunch")
    assert now(lunch.id)[2] == "Late lunch" and phone.locator(".cz-gb-edit").count() == 0
    checks(phone)


def test_escape_cancels_and_tapping_away_saves(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    show(phone, block(lunch.id))
    double_tap_title(phone, lunch.id)
    field = phone.locator(f"{block(lunch.id)} .cz-gb-edit")
    field.fill("Nothing")
    field.press("Escape")
    expect(field).to_have_count(0)
    assert now(lunch.id)[2] == "Lunch" and phone.locator(".ga-toast").count() == 0 and phone.locator(".cz-view").get_attribute("data-level") == "day"
    expect(phone.locator(f"{block(lunch.id)} .cz-gb-t")).to_have_text("Lunch")
    double_tap_title(phone, lunch.id)
    field = phone.locator(f"{block(lunch.id)} .cz-gb-edit")
    field.fill("Picnic")
    b = box(phone, block(lunch.id))
    phone.touchscreen.tap(8, b["y"] + b["height"] + 60 if b["y"] + b["height"] + 60 < phone.viewport_size["height"] - 120 else b["y"] - 50)      # tapped away
    expect(toast(phone)).to_contain_text("Renamed to Picnic")
    assert now(lunch.id)[2] == "Picnic"


def test_an_empty_or_too_long_title_is_refused_in_plain_words_and_nothing_is_saved(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    show(phone, block(lunch.id))
    double_tap_title(phone, lunch.id)
    field = phone.locator(f"{block(lunch.id)} .cz-gb-edit")
    field.fill("   ")
    field.press("Enter")
    expect(phone.locator(".cz-gb-err")).to_have_text("Give it a title.")
    expect(field).to_be_focused()                                                          # still editing: fix it
    assert field.get_attribute("aria-invalid") == "true"
    field.fill("x" * 41)
    field.press("Enter")
    expect(phone.locator(".cz-gb-err")).to_have_text("Keep the title to 40 characters.")
    assert now(lunch.id)[2] == "Lunch" and phone.locator(".ga-toast").count() == 0
    field.fill("Lunch with the whole family")
    expect(phone.locator(".cz-gb-err")).to_have_text("")                                   # typing clears the reason
    field.fill("")
    b = box(phone, block(lunch.id))
    phone.touchscreen.tap(8, b["y"] + b["height"] + 60 if b["y"] + b["height"] + 60 < phone.viewport_size["height"] - 120 else b["y"] - 50)      # tapped away from an empty title
    expect(toast(phone)).to_have_text("Give it a title.")
    expect(phone.locator(".cz-gb-edit")).to_have_count(0)
    expect(phone.locator(f"{block(lunch.id)} .cz-gb-t")).to_have_text("Lunch")
    assert now(lunch.id)[2] == "Lunch"
    checks(phone)


def test_saving_an_unchanged_title_says_nothing(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    show(phone, block(lunch.id))
    double_tap_title(phone, lunch.id)
    phone.locator(f"{block(lunch.id)} .cz-gb-edit").press("Enter")
    expect(phone.locator(".cz-gb-edit")).to_have_count(0)
    assert phone.locator(".ga-toast").count() == 0


def test_a_double_tap_on_a_park_blocks_title_edits_it_and_does_not_open_it_while_one_tap_does(phone):
    open_day(phone, 1)
    act = phone.locator(".cz-gb.is-park").get_attribute("data-act")
    double_tap_title(phone, act)
    expect(phone.locator(f"{block(act)} .cz-gb-edit")).to_be_focused()
    phone.wait_for_timeout(500)
    assert phone.locator(".cz-view").get_attribute("data-level") == "day"
    phone.locator(f"{block(act)} .cz-gb-edit").press("Escape")
    phone.wait_for_timeout(600)                                                           # the double tap's own clicks are over
    t = box(phone, f"{block(act)} .cz-gb-t")
    phone.touchscreen.tap(t["x"] + 20, t["y"] + t["height"] / 2)                          # one tap on the title still opens it, after a moment (F-106: the card; Rides goes on to the block)
    expect(phone.locator(".cz-card")).to_be_visible()
    phone.locator("#cz-card-rides").click()
    expect(phone.locator(".cz-view[data-level=block]")).to_be_visible()


# ---- who may -------------------------------------------------------------------------------------------------------------------------

def test_a_viewer_has_no_menu_and_no_rename(canvas_page, browser, base_url):
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
        page.goto(f"{base_url}/trip/canvas?day={SUNDAY}")
        page.wait_for_selector("#cz-grid")
        x, y = hold_block(page, lunch.id)
        fire(page, "pointerup", x, y)
        page.wait_for_timeout(250)
        assert page.locator(".cz-menu, .is-wiggle").count() == 0
        t = box(page, f"{block(lunch.id)} .cz-gb-t")
        page.touchscreen.tap(t["x"] + 10, t["y"] + 5)
        page.wait_for_timeout(110)
        page.touchscreen.tap(t["x"] + 10, t["y"] + 5)
        page.wait_for_timeout(300)
        assert page.locator(".cz-gb-edit, .cz-menu").count() == 0 and now(lunch.id)[2] == "Lunch"
    finally:
        ctx.close()


def test_reduced_motion_does_not_wiggle(canvas_page):
    page = canvas_page(viewport=PHONE, motion="reduce")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    hold_and_let_go(page, lunch.id)
    assert page.locator(block(lunch.id)).evaluate("e => e.getAnimations().length") == 0
    expect(page.locator(block(lunch.id))).to_have_class(re.compile(r"is-menu"))              # the block still shows which one the menu is for


def test_the_menu_has_a_five_minute_switch_so_precision_needs_no_zoom(canvas_page):
    page = canvas_page(viewport=PHONE, motion="reduce")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    hold_and_let_go(page, lunch.id)
    fine = page.get_by_role("menuitemcheckbox", name=re.compile("^Fine"))
    assert fine.get_attribute("aria-checked") == "false"
    fine.click()
    assert fine.get_attribute("aria-checked") == "true" and menu_item(page, "Later").get_attribute("aria-label") == "Later by 5 minutes"
    menu_item(page, "Later").click()
    expect(toast(page)).to_contain_text("Lunch moved to 12:05 PM")
    assert now(lunch.id)[:2] == (12 * 60 + 5, 13 * 60 + 5)
    expect(page.get_by_role("menuitemcheckbox", name=re.compile("^Fine"))).to_have_attribute("aria-checked", "true")
    menu_item(page, "Shorter").click()
    expect(toast(page)).to_contain_text("now ends 1:00 PM")
    assert now(lunch.id)[:2] == (12 * 60 + 5, 13 * 60)
    checks(page)


def test_holding_the_bottom_edge_and_letting_go_without_moving_opens_the_menu_and_changes_nothing(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    x, y = hold_block(phone, lunch.id, edge=True)
    fire(phone, "pointerup", x, y)
    expect(phone.locator(".cz-menu")).to_be_visible()
    expect(phone.locator(".cz-g-zoom.is-zooming")).to_have_count(0, timeout=3000)
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60) and phone.locator(".ga-toast").count() == 0 and phone.evaluate("CZ.held") is False


def test_a_move_by_dragging_still_works_and_does_not_open_the_menu(phone):
    from tests_browser.test_day_grid import ppm, slide
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    x, y = hold_block(phone, lunch.id)
    end = slide(phone, (x, y), (x, y + ppm(phone) * 30))
    fire(phone, "pointerup", *end)
    expect(toast(phone)).to_contain_text("Lunch moved to 12:30 PM")
    assert phone.locator(".cz-menu").count() == 0
