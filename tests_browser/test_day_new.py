"""F-101: make a plan by touching empty time on the day grid, in a real browser at 390 and 320. Hold empty time (still for about 350 ms): a one-hour block appears there snapped
to 15 minutes and follows the finger; on release its title field opens in place with the keyboard up (focused inside the pointerup, which is what iOS needs); Enter or tapping away
saves it with a toast and Undo, Escape or an empty title removes it; it can be held and moved at once; the family gets one card. A scroll or a flick is not a hold, nothing starts on a
block or a booking line, a tap shows a "+" that does the same, the keyboard has an "Add a plan" button, a viewer gets nothing, reduced motion has no pop. A finger is a pointer that goes
down, waits and lets go (synthetic pointer events, as in test_day_grid.py). Screenshots on request: F097_SHOTS=<folder> (create-390.png: mid-create with the title open)."""
import re
import uuid

import pytest
from playwright.sync_api import expect

from gitaway import familydb, session as ses, tripcal as cal
from tests_browser.helpers import PHONE
from tests_browser.test_day_grid import SUNDAY, ari, box, checks, fire, now, open_day, plan, ppm, shot, show, slide, toast
from tests_browser.test_trip_canvas import NARROW, canvas_page, model, settle  # noqa: F401 - fixtures

LOG = """() => { window.__focus = []; const real = HTMLElement.prototype.focus;
  HTMLElement.prototype.focus = function (...a) { window.__focus.push([this.tagName, window.event ? window.event.type : 'timer']); return real.apply(this, a); }; }"""


@pytest.fixture(params=[PHONE, NARROW], ids=["390", "320"])
def phone(request, canvas_page):
    return canvas_page(viewport=request.param)


def made():
    """The plans on the free day, newest last."""
    return [a for a in cal.activities(ari()) if a.day == SUNDAY]


def cards():
    with ses.family(ari()) as fam:
        return familydb.rows(fam.db, "SELECT * FROM thread WHERE kind = 'change' ORDER BY rowid")


def spot(page, minute, x=230):
    """Scroll so `minute` is on the screen and give the point of empty grid at it."""
    page.locator("#cz-grid").evaluate("(e, m) => { const z = e.querySelector('.cz-g-zoom'), r = z.getBoundingClientRect(), lo = +e.dataset.lo; window.scrollBy(0, r.top + (m - lo) * z.offsetHeight / (+e.dataset.hi - lo) - innerHeight * 0.45); }", minute)
    page.wait_for_timeout(40)
    return x, page.evaluate("""(m) => { const e = document.querySelector('#cz-grid'), z = e.querySelector('.cz-g-zoom'); return z.getBoundingClientRect().top + (m - +e.dataset.lo) * z.offsetHeight / (+e.dataset.hi - +e.dataset.lo); }""", minute)


def hold(page, minute, x=230, wait=480):
    x, y = spot(page, minute, x)
    fire(page, "pointerdown", x, y)
    page.wait_for_timeout(wait)
    return x, y


def new_block(page):
    return page.locator(".cz-gb.is-new")


def field(page):
    return page.locator(".cz-gb.is-new .cz-gb-edit")


def start_creating(page, minute=15 * 60 + 7):
    x, y = hold(page, minute)
    fire(page, "pointerup", x, y)
    expect(field(page)).to_be_focused()
    return x, y


@pytest.fixture
def day(phone):
    plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    return phone


# ---- hold, name, save ------------------------------------------------------------------------------------------------------------

def test_holding_empty_time_makes_a_one_hour_block_snapped_to_15_minutes_and_naming_it_saves_it(day):
    day.evaluate(LOG)
    x, y = hold(day, 15 * 60 + 7)
    assert new_block(day).count() == 1 and day.locator(".cz-gb-edit").count() == 0                       # the block shows while the finger is down; the field waits for the pointerup
    assert new_block(day).get_attribute("data-s") == str(15 * 60) and new_block(day).get_attribute("data-e") == str(16 * 60)
    assert "3:00 – 4:00 PM" in new_block(day).locator(".cz-gb-when").inner_text()
    b, ppm1 = box(day, ".cz-gb.is-new"), ppm(day)
    assert abs(b["height"] - 60 * ppm1) < 2 and abs(b["y"] - (y - 7 * ppm1)) < 3                          # an hour tall, its top at the slot's start
    fire(day, "pointerup", x, y)
    expect(field(day)).to_be_focused()
    assert day.evaluate("window.__focus") == [["INPUT", "pointerup"]]                                       # the keyboard opens from the gesture's own pointerup, never from the hold's timer (iOS)
    assert field(day).get_attribute("enterkeyhint") == "done" and field(day).evaluate("e => parseFloat(getComputedStyle(e).fontSize)") >= 16
    shot(day, "create-390.png")
    checks(day)
    day.keyboard.type("Pier walk")
    day.keyboard.press("Enter")
    expect(toast(day)).to_contain_text("Pier walk added")
    expect(toast(day).get_by_role("button", name="Undo")).to_be_visible()
    day.wait_for_function("() => document.querySelector('.cz-gb[data-title=\"Pier walk\"]')")
    (a,) = [m for m in made() if m.title == "Pier walk"]
    assert (a.start, a.end, a.kind) == (15 * 60, 16 * 60, "fun")
    assert new_block(day).count() == 0 and day.locator(f'.cz-gb[data-act="{a.id}"]').count() == 1 and day.evaluate("CZ.held") is False
    told = [c["text"] for c in cards() if "Pier walk" in c["text"]]
    assert len(told) == 1 and "added Pier walk" in told[0] and "3:00 PM" in told[0]                         # the family is told once


def test_the_block_follows_the_finger_until_it_lets_go(day):
    x, y = hold(day, 15 * 60 + 7)
    slide(day, (x, y), (x, y + 2 * 60 * ppm(day)), steps=8)                                              # two hours down
    assert new_block(day).get_attribute("data-s") == str(17 * 60)
    fire(day, "pointerup", x, y + 2 * 60 * ppm(day))
    expect(field(day)).to_be_focused()
    day.keyboard.type("Sunset")
    day.keyboard.press("Enter")
    expect(toast(day)).to_contain_text("Sunset added")
    assert [(a.start, a.end) for a in made() if a.title == "Sunset"] == [(17 * 60, 18 * 60)]


def test_a_start_near_the_end_of_the_day_keeps_the_hour_inside_the_grid(day):
    x, y = hold(day, 21 * 60 + 40)
    assert new_block(day).get_attribute("data-s") == str(21 * 60)                                         # 9 to 10 PM: the last hour the grid has
    fire(day, "pointerup", x, y)
    day.keyboard.type("Night swim")
    day.keyboard.press("Enter")
    expect(toast(day)).to_contain_text("Night swim added")
    assert [(a.start, a.end) for a in made() if a.title == "Night swim"] == [(21 * 60, 22 * 60)]


def test_tapping_away_saves_the_title_and_opens_nothing(day):
    x, y = start_creating(day)
    day.keyboard.type("Ice cream")
    ax, ay = spot(day, 9 * 60, x=120)                                                                     # a tap on empty grid, not on a control: iOS would not blur the field
    fire(day, "pointerdown", ax, ay, pid=8)
    fire(day, "pointerup", ax, ay, pid=8)
    expect(toast(day)).to_contain_text("Ice cream added")
    assert [a.title for a in made()].count("Ice cream") == 1 and day.locator(".cz-view").get_attribute("data-level") == "day"


def test_tapping_another_block_saves_the_title_and_does_not_open_that_block(day):
    start_creating(day)
    day.keyboard.type("Ice cream")
    lunch = box(day, '.cz-gb:not(.is-new)')
    show(day, '.cz-gb:not(.is-new)')
    lunch = box(day, '.cz-gb:not(.is-new)')
    fire(day, "pointerdown", lunch["x"] + 40, lunch["y"] + 20, pid=8)
    fire(day, "pointerup", lunch["x"] + 40, lunch["y"] + 20, pid=8)
    expect(toast(day)).to_contain_text("Ice cream added")
    day.wait_for_timeout(300)
    assert "/trip/talk" not in day.url and day.locator(".cz-view").get_attribute("data-level") == "day"


# ---- cancel ----------------------------------------------------------------------------------------------------------------------------

def test_escape_an_empty_title_and_tapping_away_from_nothing_remove_the_block_and_save_nothing(day):
    base = len(made())
    start_creating(day)
    day.keyboard.type("Never mind")
    day.keyboard.press("Escape")
    expect(new_block(day)).to_have_count(0)
    start_creating(day, 16 * 60 + 7)
    day.keyboard.press("Enter")                                                                           # empty: it is no plan, and nothing is asked
    expect(new_block(day)).to_have_count(0)
    start_creating(day, 17 * 60 + 7)
    ax, ay = spot(day, 9 * 60, x=120)
    fire(day, "pointerdown", ax, ay, pid=8)
    fire(day, "pointerup", ax, ay, pid=8)
    expect(new_block(day)).to_have_count(0)
    day.wait_for_timeout(300)
    assert len(made()) == base and day.locator(".cz-toast").count() == 0 and day.evaluate("CZ.held") is False


def test_a_title_the_calendar_refuses_stays_open_with_the_reason_and_a_tap_away_gives_it_up(day):
    start_creating(day)
    day.keyboard.type("x" * 41)
    day.keyboard.press("Enter")
    expect(day.locator(".cz-gb-err")).to_contain_text("40 characters")
    expect(field(day)).to_be_focused()
    ax, ay = spot(day, 9 * 60, x=120)
    fire(day, "pointerdown", ax, ay, pid=8)
    fire(day, "pointerup", ax, ay, pid=8)
    expect(new_block(day)).to_have_count(0)
    expect(toast(day)).to_contain_text("40 characters")
    assert not [a for a in made() if a.title.startswith("xxx")]


def test_undo_in_the_toast_removes_the_new_plan_and_its_family_card(day):
    before = len(cards())
    start_creating(day)
    day.keyboard.type("Pier walk")
    day.keyboard.press("Enter")
    expect(toast(day)).to_contain_text("Pier walk added")
    toast(day).get_by_role("button", name="Undo").click()
    expect(toast(day)).to_contain_text("Pier walk removed")
    day.wait_for_function("() => !document.querySelector('.cz-gb[data-title=\"Pier walk\"]')")
    assert not [a for a in made() if a.title == "Pier walk"] and len(cards()) == before


# ---- it is a plan at once --------------------------------------------------------------------------------------------------------------

def test_a_new_plan_can_be_held_and_moved_at_once_and_the_family_is_told_once(day):
    before = len(cards())
    start_creating(day)
    day.keyboard.type("Pier walk")
    day.keyboard.press("Enter")
    day.wait_for_function("() => document.querySelector('.cz-gb[data-title=\"Pier walk\"][data-act]')")
    toast(day).wait_for(state="visible")
    (a,) = [m for m in made() if m.title == "Pier walk"]
    sel = f'.cz-gb[data-act="{a.id}"]'
    show(day, sel)
    b = box(day, sel)
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    fire(day, "pointerdown", x, y)
    day.wait_for_timeout(480)
    end = slide(day, (x, y), (x, y + 60 * ppm(day)))
    fire(day, "pointerup", *end)
    expect(toast(day)).to_contain_text("Pier walk moved to 4:00 PM")
    assert now(a.id)[:2] == (16 * 60, 17 * 60)
    mine = cards()[before:]
    assert len(mine) == 1 and "added Pier walk" in mine[0]["text"] and "4:00 PM" in mine[0]["text"]       # one card, still saying added, with where it ended up
    expect(day.locator(sel)).to_be_visible()                                                               # the refresh after the move has landed (the page is swapped under the block)
    day.wait_for_timeout(300)
    show(day, sel)
    edge = box(day, sel)                                                                                   # and resized: the F-097 edge gesture
    ex, ey = edge["x"] + edge["width"] / 2, edge["y"] + edge["height"] - 7
    fire(day, "pointerdown", ex, ey)
    day.wait_for_timeout(480)
    end = slide(day, (ex, ey), (ex, ey + 30 * ppm(day) * 0.4), steps=8)
    fire(day, "pointerup", *end)
    day.wait_for_function(f"() => document.querySelector('{sel}').dataset.e != '{17 * 60}'")
    assert len(cards()[before:]) == 1


def test_the_week_shows_the_new_plan_even_though_it_was_fetched_ahead_before(day):
    day.wait_for_timeout(2200)                                                                             # idle time: the week and the other days are fetched ahead (F-099)
    start_creating(day)
    day.keyboard.type("Pier walk")
    day.keyboard.press("Enter")
    expect(toast(day)).to_contain_text("Pier walk added")
    day.wait_for_function("() => document.querySelector('.cz-gb[data-title=\"Pier walk\"][data-act]')")                          # the refresh has landed (a week opened meanwhile would be swapped back)
    day.evaluate("scrollTo(0, 0)")
    day.locator("#cz-z-week").click()
    settle(day)
    expect(day.locator(".cz-view[data-level=week]")).to_contain_text("Pier walk", timeout=20000)                 # (the cache was emptied by the write, so the week is fetched now, behind the idle fetches)


# ---- what is not a hold --------------------------------------------------------------------------------------------------------------------

def test_a_scroll_a_flick_a_block_and_a_booking_line_never_start_a_plan(phone):
    plan("Beach walk", 10 * 60, 11 * 60, day=0)
    open_day(phone, 0)
    assert phone.locator(".cz-gbk").count() == 2
    x, y = spot(phone, 15 * 60)
    fire(phone, "pointerdown", x, y)                                                                       # moves before the hold: a scroll
    slide(phone, (x, y), (x, y - 60), steps=4)
    phone.wait_for_timeout(480)
    fire(phone, "pointerup", x, y - 60)
    assert new_block(phone).count() == 0 and phone.locator(".cz-gnew").count() == 0
    x, y = spot(phone, 16 * 60)
    fire(phone, "pointerdown", x, y)                                                                       # a quick sideways flick is the day change
    slide(phone, (x, y), (x - 170, y + 2), steps=6, wait=8)
    fire(phone, "pointerup", x - 170, y + 2)
    expect(phone.locator(".cz-view")).to_have_attribute("data-day", "1")
    assert new_block(phone).count() == 0
    open_day(phone, 0)
    bk = box(phone, ".cz-gbk")
    show(phone, ".cz-gbk")
    bk = box(phone, ".cz-gbk")
    fire(phone, "pointerdown", bk["x"] + bk["width"] / 2, bk["y"] + bk["height"] / 2)
    phone.wait_for_timeout(480)
    fire(phone, "pointerup", bk["x"] + bk["width"] / 2, bk["y"] + bk["height"] / 2)
    assert new_block(phone).count() == 0
    walk = box(phone, ".cz-gb")
    show(phone, ".cz-gb")
    walk = box(phone, ".cz-gb")
    fire(phone, "pointerdown", walk["x"] + walk["width"] / 2, walk["y"] + walk["height"] / 2)
    phone.wait_for_timeout(480)
    assert new_block(phone).count() == 0 and phone.locator(".is-held").count() == 1                         # a block is lifted, as in F-097
    fire(phone, "pointerup", walk["x"] + walk["width"] / 2, walk["y"] + walk["height"] / 2)


def test_two_fingers_never_start_a_plan(day):
    x, y = spot(day, 15 * 60)
    fire(day, "pointerdown", x, y)
    fire(day, "pointerdown", x + 30, y + 30, pid=8)
    day.wait_for_timeout(480)
    assert new_block(day).count() == 0
    fire(day, "pointerup", x + 30, y + 30, pid=8)
    fire(day, "pointerup", x, y)


def test_while_the_title_is_typed_the_rest_of_the_grid_is_calm(day):
    start_creating(day)
    assert day.locator("#cz-grid").get_attribute("class").count("is-making") == 1
    assert day.locator(".cz-gb:not(.is-new)").first.evaluate("e => getComputedStyle(e).pointerEvents") == "none"
    lunch = box(day, ".cz-gb:not(.is-new)")
    fire(day, "pointerdown", lunch["x"] + 40, lunch["y"] + 20, pid=8)                                      # the tap saves (nothing typed: removes); it never lifts the block
    day.wait_for_timeout(480)
    assert day.locator(".is-held").count() == 0
    fire(day, "pointerup", lunch["x"] + 40, lunch["y"] + 20, pid=8)
    start_creating(day, 17 * 60 + 7)
    x, y = 200, box(day, ".cz-gb.is-new")["y"] + 200
    fire(day, "pointerdown", x, y, pid=9)                                                                  # a flick on empty grid does not change the day while a title is typed
    for i in range(1, 7):
        fire(day, "pointermove", x - 170 * i / 6, y, pid=9)
    fire(day, "pointerup", x - 170, y, pid=9)
    day.wait_for_timeout(300)
    assert day.locator(".cz-view").get_attribute("data-day") == str(SUNDAY)


# ---- the "+" and the keyboard --------------------------------------------------------------------------------------------------------------

def test_tapping_empty_time_shows_a_plus_that_makes_the_plan(day):
    day.evaluate(LOG)
    x, y = spot(day, 15 * 60 + 20)
    fire(day, "pointerdown", x, y)
    fire(day, "pointerup", x, y)                                                                           # a quick tap
    chip = day.locator(".cz-gnew")
    expect(chip).to_have_count(1)
    assert chip.get_attribute("aria-label") == "Add a plan at 3:15 – 4:15 PM"
    cb = chip.bounding_box()
    assert cb["width"] >= 43.5 and cb["height"] >= 43.5 and cb["x"] >= 0 and cb["x"] + cb["width"] <= day.viewport_size["width"]
    assert new_block(day).count() == 0 and day.locator(".cz-gnew-ghost").count() == 1
    shot(day, "plus-390.png")
    chip.click()
    expect(field(day)).to_be_focused()
    assert new_block(day).get_attribute("data-s") == str(15 * 60 + 15) and day.locator(".cz-gnew, .cz-gnew-ghost").count() == 0
    assert day.evaluate("window.__focus")[-1] == ["INPUT", "click"]                                         # from the press on the "+": a user activation
    day.keyboard.type("Pier walk")
    day.keyboard.press("Enter")
    expect(toast(day)).to_contain_text("Pier walk added")
    assert [(a.start, a.end) for a in made() if a.title == "Pier walk"] == [(15 * 60 + 15, 16 * 60 + 15)]


def test_a_tap_elsewhere_moves_the_plus_and_it_goes_by_itself(day):
    x, y = spot(day, 15 * 60)
    fire(day, "pointerdown", x, y)
    fire(day, "pointerup", x, y)
    expect(day.locator(".cz-gnew")).to_have_count(1)
    x2, y2 = spot(day, 17 * 60 + 40)
    fire(day, "pointerdown", x2, y2, pid=8)
    fire(day, "pointerup", x2, y2, pid=8)
    expect(day.locator(".cz-gnew")).to_have_count(1)
    assert "5:30" in day.locator(".cz-gnew").get_attribute("aria-label")
    day.wait_for_timeout(6400)
    expect(day.locator(".cz-gnew")).to_have_count(0)


def test_the_keyboard_and_screen_reader_have_an_add_a_plan_button(day):
    day.locator(".cz-gadd").focus()
    day.keyboard.press("Enter")
    expect(field(day)).to_be_focused()
    assert new_block(day).get_attribute("data-s") == str(9 * 60)
    day.keyboard.type("Breakfast")
    day.keyboard.press("Enter")
    expect(toast(day)).to_contain_text("Breakfast added")
    assert any(a.title == "Breakfast" and a.start == 9 * 60 for a in made())


# ---- who may, and motion ------------------------------------------------------------------------------------------------------------------------

def test_a_viewer_holding_or_tapping_empty_time_gets_nothing(canvas_page, browser, base_url):
    owner = canvas_page(viewport=PHONE)
    plan("Lunch", 12 * 60, 13 * 60)
    mail = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
    try:
        ctx.set_default_timeout(9000)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day={SUNDAY}")
        page.wait_for_selector("#cz-grid")
        assert page.locator(".cz-gadd").count() == 0
        x, y = spot(page, 15 * 60)
        fire(page, "pointerdown", x, y)
        page.wait_for_timeout(480)
        fire(page, "pointerup", x, y)
        fire(page, "pointerdown", x, y, pid=8)
        fire(page, "pointerup", x, y, pid=8)
        page.wait_for_timeout(200)
        assert page.locator(".is-new, .cz-gnew, .cz-gb-edit, .cz-toast").count() == 0 and len(made()) == 1
    finally:
        ctx.close()


def test_the_new_block_pops_in_but_not_with_reduced_motion(canvas_page):
    page = canvas_page(viewport=PHONE, motion="no-preference")
    plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    hold(page, 15 * 60)
    assert page.locator(".cz-gb.is-new").evaluate("e => getComputedStyle(e).animationName") == "cz-pop"
    fire(page, "pointerup", *spot(page, 15 * 60))
    page.keyboard.press("Escape")
    page.emulate_media(reduced_motion="reduce")
    hold(page, 15 * 60)
    assert page.locator(".cz-gb.is-new").evaluate("e => getComputedStyle(e).animationName") == "none"
    assert page.locator(".cz-gb.is-new").count() == 1
    fire(page, "pointerup", *spot(page, 15 * 60))
    page.keyboard.press("Escape")
    expect(new_block(page)).to_have_count(0)


def test_a_refresh_dropped_as_stale_is_asked_for_again_so_a_failed_write_cannot_leave_a_draft_on_screen(day):
    """Review: the refresh after a create was fetched, then another write (which failed, so brought no refresh of its own) bumped the write count: the stale copy is dropped and
    the page must still end up showing what is saved (a real block, not the draft with no data-act)."""
    held = []
    pattern = re.compile(rf".*day={SUNDAY}&frag=1$")
    day.route(pattern, lambda route: held.append((route, route.fetch())) if not held else route.continue_())      # only the create's own refresh is held back
    start_creating(day)
    day.keyboard.type("Pier walk")
    day.keyboard.press("Enter")
    for _ in range(60):
        if held:
            break
        day.wait_for_timeout(50)
    assert held, "the create's refresh was never asked for"
    day.route("**/trip/canvas/plan", lambda route: route.abort())
    day.evaluate("CZ.post('/trip/canvas/plan', new URLSearchParams({ op: 'delete', act: 'a99' })).catch(() => {})")      # a later write that fails
    day.wait_for_timeout(300)
    day.unroute("**/trip/canvas/plan")
    held[0][0].fulfill(response=held[0][1])                      # the old answer arrives: dropped, and asked for again (now unrouted)
    day.wait_for_function("() => document.querySelector('.cz-gb[data-title=\"Pier walk\"][data-act]')")
    assert day.locator(".cz-gb.is-new").count() == 0


def test_a_blank_day_can_be_held_too_with_one_compact_row_of_talk_and_paste(phone):
    open_day(phone)                                                                                          # the free day, nothing planned
    assert phone.locator("#cz-grid").count() == 1 and phone.locator(".cz-gb").count() == 0
    row = box(phone, "#cz-empty")
    assert row["height"] < 90 and phone.locator("#cz-say-talk").is_visible() and phone.locator("#cz-say-paste").is_visible()
    assert abs(box(phone, "#cz-say-talk")["y"] - box(phone, "#cz-say-paste")["y"]) < 4                        # one row
    checks(phone)
    start_creating(phone, 10 * 60 + 5)
    phone.keyboard.type("First plan")
    phone.keyboard.press("Enter")
    expect(toast(phone)).to_contain_text("First plan added")
    assert [(a.start, a.end) for a in made() if a.title == "First plan"] == [(10 * 60, 11 * 60)]
    phone.wait_for_function("() => document.querySelector('.cz-gb[data-title=\"First plan\"][data-act]')")
    assert phone.locator("#cz-empty").count() == 0                                                           # it has a plan now: the card is gone


def test_a_viewer_of_a_blank_day_has_no_grid_to_hold(canvas_page, browser, base_url):
    owner = canvas_page(viewport=PHONE)
    mail = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
    try:
        ctx.set_default_timeout(9000)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day={SUNDAY}")
        page.wait_for_selector(".cz-view[data-level=day]")
        assert page.locator("#cz-grid").count() == 0 and "Nothing planned yet" in page.locator("#main").inner_text()
    finally:
        ctx.close()


def test_a_retry_after_a_lost_reply_does_not_make_the_plan_twice(day):
    start_creating(day)
    day.keyboard.type("Pier walk")
    day.route("**/trip/canvas/plan", lambda route: (route.fetch(), route.abort()))                           # the server makes it, the reply never comes
    day.keyboard.press("Enter")
    expect(day.locator(".cz-gb-err")).to_contain_text("Could not save", timeout=15000)
    day.unroute("**/trip/canvas/plan")
    expect(field(day)).to_be_focused()
    day.keyboard.press("Enter")                                                                              # the finger tries again with the same plan
    expect(toast(day)).to_contain_text("Pier walk added")
    assert [a.title for a in made()].count("Pier walk") == 1
    assert len([c for c in cards() if "added Pier walk" in c["text"]]) == 1


def test_losing_the_focus_right_after_it_opens_keeps_the_field_and_does_not_refocus_from_the_blur(day):
    day.evaluate(LOG)
    start_creating(day)
    field(day).evaluate("e => e.blur()")                                                                      # the touch's own mouse events take the focus at once
    day.wait_for_timeout(120)
    assert field(day).count() == 1 and day.evaluate("window.__focus") == [["INPUT", "pointerup"]]             # still open, and nothing tried to focus it again from a blur
    field(day).tap()                                                                                          # a tap on it brings the keyboard back
    expect(field(day)).to_be_focused()


def test_the_add_a_plan_button_shows_when_the_keyboard_reaches_it(day):
    day.locator(".cz-gadd").focus()
    day.keyboard.press("Shift+Tab")
    day.keyboard.press("Tab")                                                                                 # a keyboard move, so focus-visible
    b = box(day, ".cz-gadd")
    assert b["width"] > 40 and b["height"] >= 43.5
    expect(day.locator(".cz-gadd")).to_be_in_viewport()
