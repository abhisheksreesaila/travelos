"""F-141: a clicked plan opens in the panel, in a real browser (a mouse, at 1440 and 1280). A click on a plan's block rings it in coral and opens its card in the docked panel instead of a sheet
over the day: who, the note, the steps (one click ticks one; Add a step; Set aside and Put back), the plan's chat and the message bar at the panel's foot. The panel shows the plan's outline at once
and fills in (cards fetched ahead are used), Esc or the close button returns it to Up next, and the address keeps the open plan so a reload shows it again. The panel's modes switch through
`Dock` without a page load. 1000 (tablet) keeps its card sheet. Screenshots on request: F141_SHOTS=<folder>."""
import os
import re

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import DESKTOP
from tests_browser.test_day_grid import open_day
from tests_browser.test_topbar import LAPTOP
from tests_browser.test_trip_canvas import WIDE, canvas_page, model  # noqa: F401 - fixtures

SATURDAY = 1
NO_SCROLL = "[document.documentElement.scrollWidth <= document.documentElement.clientWidth, document.documentElement.scrollHeight <= document.documentElement.clientHeight, window.scrollY]"


def shot(page, name):
    if os.environ.get("F141_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F141_SHOTS"], name))


@pytest.fixture(params=[DESKTOP, LAPTOP], ids=["1440", "1280"])
def desk(request, canvas_page):
    page = canvas_page(viewport=request.param, touch=False)
    open_day(page, SATURDAY)
    return page


def park(page):
    """The park block (it has steps): its act id."""
    return page.locator(".cz-gb.is-park").first.get_attribute("data-act")


def extra_plan(title="Slow breakfast", start=10 * 60, end=11 * 60):
    return cal.add_activity(person("ari"), day=SATURDAY, start=start, end=end, title=title, kind="food")


def block(page, act):
    return page.locator(f'.cz-gb[data-act="{act}"]')


def click_block(page, act, y=0.6):
    """A real mouse click on a block, below its title."""
    b = block(page, act)
    b.scroll_into_view_if_needed()
    box = b.bounding_box()
    page.mouse.click(box["x"] + box["width"] * 0.7, box["y"] + min(box["height"] * y, 90))


def pane(page):
    return page.locator("#cz-dock .cz-pp:not(.is-leaving)")


def mode(page):
    return page.locator("#cz-dock").get_attribute("data-mode")


def test_a_click_rings_the_plan_in_coral_and_opens_its_card_in_the_panel(desk):
    act = park(desk)
    click_block(desk, act)
    expect(pane(desk)).to_be_visible()
    expect(pane(desk).locator(".cz-pp-t")).to_have_text(re.compile("Universal"))
    expect(pane(desk).locator(".cz-pp-eb")).to_contain_text("Plan · Sat")
    assert mode(desk) == "plan" and desk.locator(".cz-card-wrap, .cz-card").count() == 0         # not a sheet over the day
    expect(block(desk, act)).to_have_class(re.compile("is-ringed"))
    coral = desk.evaluate("() => { const s = document.createElement('i'); s.style.color = 'var(--coral)'; document.body.append(s); const c = getComputedStyle(s).color; s.remove(); return c; }")
    ring = block(desk, act).evaluate("e => getComputedStyle(e).boxShadow")
    assert ring.startswith(coral) and re.search(r"0px 0px 0px 3px", ring), ring            # a 3px coral ring (the root is 12px: 0.25rem)
    expect(desk.locator("#cz-dock [data-pane=idle]")).to_be_hidden()
    expect(desk.locator("#cz-dock .cz-dock-tab.is-on")).to_have_text("Plan")
    # who, the note slip, steps, the chat, the compose bar at the foot
    expect(pane(desk).locator(".cz-pp-who")).to_be_visible()
    expect(pane(desk).locator(".cz-card-notes")).to_be_visible()
    expect(pane(desk).locator(".cz-pstep[data-step]").first).to_be_visible()
    expect(pane(desk).get_by_text("Chat on this plan")).to_be_visible()
    expect(desk.locator("#cz-dock .cz-pp-foot .cz-pp-text")).to_be_visible()
    assert desk.evaluate(NO_SCROLL) == [True, True, 0]
    assert f"plan={act}" in desk.url
    shot(desk, f"plan-open-{desk.viewport_size['width']}.png")


def test_steps_tick_with_one_click_and_the_tick_is_saved(desk):
    act = park(desk)
    click_block(desk, act)
    step = pane(desk).locator(".cz-pstep[data-step]:not(.is-done)").first
    expect(step).to_be_visible()
    sid = step.get_attribute("data-step")
    step.locator(".cz-ring").click()
    expect(pane(desk).locator(f'.cz-pstep[data-step="{sid}"]')).to_have_class(re.compile("is-done"))
    shot(desk, f"plan-ticked-{desk.viewport_size['width']}.png")
    desk.wait_for_timeout(400)
    desk.reload()
    expect(pane(desk).locator(f'.cz-pstep[data-step="{sid}"]')).to_have_class(re.compile("is-done"))        # saved, and the reload brought the panel back
    pane(desk).locator(f'.cz-pstep[data-step="{sid}"] .cz-ring').click()
    expect(pane(desk).locator(f'.cz-pstep[data-step="{sid}"]')).not_to_have_class(re.compile("is-done"))


def test_add_a_step_and_set_aside_and_put_back(desk):
    act = park(desk)
    click_block(desk, act)
    expect(pane(desk).locator(".cz-pp-steps .cz-pstep[data-step]").first).to_be_visible()
    n = pane(desk).locator(".cz-pp-steps .cz-pstep[data-step]").count()
    pane(desk).get_by_role("button", name="Add a step").click()
    field = pane(desk).locator(".cz-pp-addf input[name=title]")
    expect(field).to_be_focused()
    field.fill("Pretzel stop")
    field.press("Enter")
    expect(pane(desk).locator(".cz-pp-steps .cz-pstep[data-step]")).to_have_count(n + 1)
    expect(pane(desk).locator(".cz-pp-steps").get_by_text("Pretzel stop")).to_be_visible()
    expect(field).to_have_value("")
    # set it aside
    row = pane(desk).locator(".cz-pp-steps .cz-pstep", has_text="Pretzel stop")
    row.hover()
    row.get_by_role("button", name=re.compile("Set aside")).click()
    expect(pane(desk).locator(".cz-pp-steps .cz-pstep[data-step]")).to_have_count(n)
    before = int(re.search(r"\((\d+)\)", pane(desk).locator(".cz-pp-asidebtn").inner_text()).group(1))
    pane(desk).locator(".cz-pp-asidebtn").click()
    tray = pane(desk).locator("#cz-pp-aside")
    expect(tray.get_by_text("Pretzel stop")).to_be_visible()
    tray.locator(".cz-pstep", has_text="Pretzel stop").get_by_role("button", name=re.compile("Put back")).click()
    expect(pane(desk).locator(".cz-pp-steps .cz-pstep", has_text="Pretzel stop")).to_have_count(1)
    assert before >= 1


def test_the_chat_takes_a_message_and_a_reload_shows_it(desk):
    act = park(desk)
    click_block(desk, act)
    box = desk.locator("#cz-dock .cz-pp-foot .cz-pp-text")
    box.fill("Churros after, deal")
    box.press("Enter")
    expect(pane(desk).locator("#cz-pp-msgs").get_by_text("Churros after, deal")).to_be_visible()
    expect(box).to_have_value("")
    desk.wait_for_timeout(300)
    desk.reload()
    expect(pane(desk).locator("#cz-pp-msgs").get_by_text("Churros after, deal")).to_be_visible()


def test_the_note_is_written_in_the_panel(desk):
    act = park(desk)
    click_block(desk, act)
    pane(desk).locator(".cz-card-add").click()
    area = pane(desk).locator("textarea.cz-card-edit")
    expect(area).to_be_focused()
    area.fill("kids want the ferris wheel")
    area.press("Enter")
    expect(pane(desk).locator(".cz-card-note", has_text="kids want the ferris wheel")).to_be_visible()
    expect(block(desk, act).locator(".cz-gb-note")).to_contain_text("ferris wheel")        # the block behind shows the new words


@pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])
def test_the_outline_shows_at_once_and_the_words_fill_in(canvas_page, viewport):
    desk = canvas_page(viewport=viewport, touch=False)
    seen = []

    def slow(route):
        seen.append(route.request.url)
        desk.wait_for_timeout(700)
        route.continue_()

    desk.route(re.compile(r"/trip/canvas/card\?"), slow)         # (before the day opens: a card already fetched ahead has nothing to wait for)
    open_day(desk, SATURDAY)
    act = park(desk)
    click_block(desk, act)
    expect(pane(desk).locator(".cz-pp-t")).to_have_text(re.compile("Universal"))      # the title from the clicked block, at once
    expect(pane(desk)).to_have_class(re.compile("is-loading"))
    expect(pane(desk).locator(".cz-pp-skel").first).to_be_visible()
    shot(desk, f"plan-loading-{desk.viewport_size['width']}.png")
    expect(pane(desk)).not_to_have_class(re.compile("is-loading"))
    expect(pane(desk).locator(".cz-pstep[data-step]").first).to_be_visible()
    assert any("panel=1" in u for u in seen)


def test_a_card_fetched_ahead_is_not_fetched_again(canvas_page):
    page = canvas_page(viewport=DESKTOP, touch=False)
    asked = []
    page.on("request", lambda r: asked.append(r.url) if "/trip/canvas/card" in r.url else None)
    open_day(page, SATURDAY)
    act = park(page)
    page.wait_for_function("(a) => true", arg=act)
    page.wait_for_timeout(1200)                                      # idle time: the cards on the screen come ahead
    ahead = [u for u in asked if f"act={act}" in u]
    assert ahead and all("panel=1" in u for u in ahead)              # on a laptop it is the panel's pane that comes ahead
    click_block(page, act)
    expect(pane(page).locator(".cz-pstep[data-step]").first).to_be_visible()
    assert [u for u in asked if f"act={act}" in u] == ahead          # the click asked for nothing


def test_esc_and_the_close_button_return_to_up_next_and_the_address_keeps_the_plan(desk):
    act = park(desk)
    click_block(desk, act)
    expect(pane(desk)).to_be_visible()
    url = desk.url
    desk.reload()                                                    # the address keeps the open plan: a reload shows it again
    expect(pane(desk)).to_be_visible()
    expect(pane(desk).locator(".cz-pp-t")).to_have_text(re.compile("Universal"))
    expect(block(desk, act)).to_have_class(re.compile("is-ringed"))
    assert desk.url == url and mode(desk) == "plan"
    desk.keyboard.press("Escape")
    expect(desk.locator("#cz-dock [data-pane=idle]")).to_be_visible()
    expect(pane(desk)).to_have_count(0)
    assert mode(desk) == "idle" and "plan=" not in desk.url and desk.locator(".cz-gb.is-ringed").count() == 0
    assert desk.locator(".cz-view[data-level=day]").count() == 1                                        # Esc did not zoom out to the week
    shot(desk, f"plan-after-esc-{desk.viewport_size['width']}.png")
    click_block(desk, act)
    expect(pane(desk)).to_be_visible()
    desk.get_by_role("button", name="Close the plan").click()
    expect(desk.locator("#cz-dock [data-pane=idle]")).to_be_visible()
    assert mode(desk) == "idle" and "plan=" not in desk.url


@pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])
def test_the_ring_follows_when_the_panel_switches_plans(canvas_page, viewport):
    desk = canvas_page(viewport=viewport, touch=False)
    other = extra_plan()                      # added before the day is opened: a day opened from the saved copy would not show it yet
    open_day(desk, SATURDAY)
    act = park(desk)
    click_block(desk, act)
    expect(pane(desk).locator(".cz-pp-t")).to_have_text(re.compile("Universal"))
    click_block(desk, other.id)
    expect(pane(desk).locator(".cz-pp-t")).to_have_text("Slow breakfast")
    expect(desk.locator(".cz-gb.is-ringed")).to_have_count(1)
    expect(block(desk, other.id)).to_have_class(re.compile("is-ringed"))
    expect(pane(desk).locator(".cz-pp-steps-sec")).to_have_count(0)      # a plan with no steps has no steps section
    assert f"plan={other.id}" in desk.url


def test_the_tabs_switch_modes_without_a_page_load(desk):
    act = park(desk)
    desk.evaluate("window.__loaded = 1")
    desk.evaluate("""Dock.register('family', { tab: 'family', enter(o, from) { document.getElementById('cz-dock').dataset.seen = from; }, leave() {} })""")
    click_block(desk, act)
    expect(pane(desk)).to_be_visible()
    desk.locator("#cz-dock .cz-dock-tab[data-tab=family]").click()
    expect(desk.locator("#cz-dock")).to_have_attribute("data-mode", "family")
    expect(desk.locator("#cz-dock .cz-dock-tab[data-tab=family]")).to_have_attribute("aria-selected", "true")
    expect(desk.locator("#cz-dock .cz-dock-tab[data-tab=plan]")).to_have_attribute("aria-selected", "false")
    expect(desk.locator("#cz-dock")).to_have_attribute("data-seen", "plan")
    expect(pane(desk)).to_have_count(0)
    assert desk.url.endswith(f"day={SATURDAY}") or "plan=" not in desk.url
    assert desk.evaluate("window.__loaded") == 1                                       # no page load
    desk.locator("#cz-dock .cz-dock-tab[data-tab=plan]").click()                       # back to Plan: the plan that was open
    expect(pane(desk)).to_be_visible()
    assert mode(desk) == "plan" and desk.evaluate("window.__loaded") == 1 and f"plan={act}" in desk.url


def test_a_tab_nobody_registered_keeps_its_link(desk):
    desk.locator("#cz-dock .cz-dock-tab[data-tab=ask]").click()
    desk.wait_for_url(re.compile(r"/trip/ask"))


def test_the_panels_change_runs_on_the_shared_motion_and_a_phone_width_is_untouched(canvas_page):
    page = canvas_page(viewport=DESKTOP, motion="no-preference", touch=False)
    open_day(page, SATURDAY)
    act = park(page)
    page.evaluate("GA.motion.log.length = 0")
    click_block(page, act)
    expect(pane(page).locator(".cz-pstep[data-step]").first).to_be_visible()
    assert "open" in page.evaluate("GA.motion.log.map(m => m.kind)")
    page.keyboard.press("Escape")
    expect(page.locator("#cz-dock [data-pane=idle]")).to_be_visible()
    page.wait_for_function("document.querySelectorAll('#cz-dock .cz-pp').length === 0")
    assert "close" in page.evaluate("GA.motion.log.map(m => m.kind)")


def test_the_tablet_keeps_its_card_sheet(canvas_page):
    page = canvas_page(viewport=WIDE, touch=False)
    open_day(page, SATURDAY)
    act = park(page)
    click_block(page, act)
    expect(page.locator(".cz-card")).to_be_visible()
    assert page.locator("#cz-dock").evaluate("e => getComputedStyle(e).display") == "none" and "plan=" not in page.url
