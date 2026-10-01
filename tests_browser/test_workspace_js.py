"""F-029: the workspace's page JavaScript in a real (headless) browser: the paths string-matching tests cannot cover.

Waits are on selectors and state, never on sleeps. Run: `pixi run test-browser`.
"""
import re

from playwright.sync_api import expect

from tests_browser.helpers import PHONE

QUOTE = "**/plan/quote*"


def total(page):
    return page.locator("#ws-total").inner_text()


def url_has(page, text):
    page.wait_for_function("t => location.search.includes(t)", arg=text)


def tile(page, lane, offer):
    page.click(f'.ws-offer[data-lane="{lane}"][data-pick="{offer}"]')


def expand(page, pane):
    page.click(f'.ws-expand[data-expand="{pane}"]')
    expect(page.locator("#ws-grid")).to_have_attribute("data-expanded", pane)


def collapsed(page):
    expect(page.locator("#ws-grid")).not_to_have_attribute("data-expanded", re.compile(r".+"))


def test_a_tiled_pick_then_expand_stays_opens_that_pick(open_plan):
    page = open_plan()
    tile(page, "stay", "h2")
    url_has(page, "h=h2")
    expand(page, "stays")
    expect(page.locator('.ws-detail-panel[data-detail="h2"]')).to_be_visible()
    expect(page.locator('.ws-detail-panel[data-detail="h1"]')).to_be_hidden()
    expect(page.locator('.ws-offer[data-pick="h2"]')).to_have_attribute("aria-current", "true")


def test_choose_in_the_split_view_updates_the_ledger_line_and_the_url(open_plan):
    page = open_plan()
    before = total(page)
    expand(page, "stays")
    page.click('.ws-offer[data-pick="h2"]')  # in the split view a card opens its detail; it does not pick
    expect(page.locator('.ws-detail-panel[data-detail="h2"]')).to_be_visible()
    assert total(page) == before
    page.click('.ws-choose[data-choose="h2"]')
    expect(page.locator('.ws-choose[data-choose="h2"]')).to_have_text("Chosen")
    url_has(page, "h=h2")
    expect(page.locator("#ws-total")).not_to_have_text(before)
    assert "x=stays" in page.url


def test_esc_collapses_the_split_view_and_closes_the_popover_first(open_plan):
    page = open_plan()
    expand(page, "stays")
    page.keyboard.press("Escape")
    collapsed(page)
    expand(page, "stays")
    page.click("#ws-total")
    expect(page.locator("#ws-pop")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#ws-pop")).to_be_hidden()
    expect(page.locator("#ws-grid")).to_have_attribute("data-expanded", "stays")  # the popover took the first Esc
    page.keyboard.press("Escape")
    collapsed(page)


def test_phone_expand_open_detail_back_and_reload_stays_on_the_list(open_plan):
    page = open_plan(viewport=PHONE)
    stays = page.locator('.ws-pane[data-pane="stays"]')
    expand(page, "stays")
    expect(stays).to_have_attribute("data-screen", "list")
    page.click('.ws-offer[data-pick="h2"]')
    expect(stays).to_have_attribute("data-screen", "detail")
    expect(page.locator('.ws-detail-panel[data-detail="h2"]')).to_be_visible()
    page.click('.ws-detail-panel[data-detail="h2"] .ws-back')
    expect(stays).to_have_attribute("data-screen", "list")
    assert "v=" not in page.url
    page.reload()
    page.wait_for_selector("#ws-grid[data-focus]")
    expect(page.locator("#ws-grid")).to_have_attribute("data-expanded", "stays")
    expect(stays).to_have_attribute("data-screen", "list")
    expect(page.locator(".ws-detail-panel:visible")).to_have_count(0)


def test_picking_another_stay_tiled_resets_the_old_stays_panel(open_plan):
    page = open_plan()
    expand(page, "stays")
    h1 = page.locator('.ws-detail-panel[data-detail="h1"]')
    h1.locator('.ws-addon[data-addon="bf"]').click()
    expect(h1.locator('.ws-addon[data-addon="bf"]')).to_have_attribute("aria-pressed", "true")
    expect(h1.locator(".ws-choose")).to_be_enabled()
    h1.locator(".ws-choose").click()
    url_has(page, "add=bf")
    page.keyboard.press("Escape")
    collapsed(page)
    tile(page, "stay", "h2")
    url_has(page, "h=h2")
    expect(h1).to_have_attribute("data-add", "")
    expect(h1).to_have_attribute("data-rooms", "cq1")
    expect(h1.locator('.ws-addon[data-addon="bf"]')).to_have_attribute("aria-pressed", "false")
    expand(page, "stays")
    page.click('.ws-offer[data-pick="h1"]')
    expect(h1.locator(".ws-choose")).to_have_text("Choose this stay")  # not "Chosen": h2 holds the pick now


def edit_room(page):
    """Add an Ocean-view King to the open Tidewater panel; returns its Choose button."""
    expand(page, "stays")
    panel = page.locator('.ws-detail-panel[data-detail="h1"]')
    panel.locator('.ws-room[data-room="ok"] [data-step="1"]').click()
    return panel, panel.locator(".ws-choose")


def test_choose_is_held_while_a_room_edit_waits_for_its_price(open_plan):
    page = open_plan()
    held = []
    page.route(QUOTE, lambda route: held.append(route))
    with page.expect_request(QUOTE):
        panel, choose = edit_room(page)
    expect(choose).to_be_disabled()  # still held while the price is outstanding
    for route in held:
        route.continue_()
    expect(choose).to_be_enabled()
    expect(panel).to_have_attribute("data-rooms", re.compile("ok1"))
    expect(panel.locator("[data-cb-err]")).to_be_hidden()


def test_choose_recovers_when_the_price_request_fails(open_plan):
    page = open_plan()
    page.route(QUOTE, lambda route: route.abort())
    panel, choose = edit_room(page)
    expect(panel.locator("[data-cb-err]")).to_be_visible()
    expect(choose).to_be_enabled()  # back to the last setup the server priced, which is the pick
    expect(panel).to_have_attribute("data-rooms", "cq1")
    expect(panel.locator('.ws-room[data-room="ok"]')).to_have_attribute("data-count", "0")  # the editor shows what Choose picks


PICKS = "f=f2&h=h1&c=c2&rooms=ok2&add=bf"  # Ocean-view King x2 with breakfast, a non-default flight and car


def test_skip_the_car_and_undo_brings_the_car_back_and_leaves_the_other_picks_alone(open_plan):
    page = open_plan(PICKS)
    picks = page.evaluate("() => location.search")
    before = total(page)
    page.click('[data-skip="car"]')
    url_has(page, "c=none")
    expect(page.locator('.ws-pane[data-pane="cars"]')).to_have_attribute("data-skipped", "1")
    expect(page.locator("#ws-total")).not_to_have_text(before)
    page.click('[data-undo="car"]')
    expect(page.locator('.ws-pane[data-pane="cars"]')).not_to_have_attribute("data-skipped", "1")
    expect(page.locator("#ws-total")).to_have_text(before)
    assert page.evaluate("() => location.search") == picks
    expect(page.locator('.ws-offer[data-pick="c2"]')).to_have_attribute("aria-pressed", "true")


def test_skip_the_stay_and_undo_brings_back_its_rooms_and_add_ons(open_plan):
    page = open_plan(PICKS)
    picks = page.evaluate("() => location.search")
    before = total(page)
    page.click('[data-skip="stay"]')
    url_has(page, "h=none")
    assert "rooms=" not in page.url and "add=" not in page.url
    page.click('[data-undo="stay"]')
    expect(page.locator('.ws-pane[data-pane="stays"]')).not_to_have_attribute("data-skipped", "1")
    expect(page.locator("#ws-total")).to_have_text(before)
    assert page.evaluate("() => location.search") == picks  # the rooms and add-ons, not the default room
    expect(page.locator('.ws-detail-panel[data-detail="h1"]')).to_have_attribute("data-rooms", "ok2")
    expect(page.locator('.ws-detail-panel[data-detail="h1"]')).to_have_attribute("data-add", "bf")
