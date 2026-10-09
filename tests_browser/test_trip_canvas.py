"""F-081: the trip canvas in a real browser. At 390 wide: tap week > day > block > step and back, the browser's Back and Forward, the Day | Week toggle (pinch is gone, F-092; synthetic
pointer events), the View Transition (the tapped element is the one named cz-hero before and after the swap), reduced motion (no transition at all), Mark done and
Set aside from the step sheet, lanes, no sideways scroll, 44px targets, 13px text. At 1280: the wide day view. The trip is the captain's Universal + California
Adventure messages through a canned model answer; nothing here reaches the network."""
import json
import os
import re

import pytest
from playwright.sync_api import expect

from gitaway import ai, familydb, session as ses
from tests import canvas_samples as samples
from tests.test_signin import person
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT

NARROW = {"width": 320, "height": 640}
WIDE = {"width": 1280, "height": 800}
SPY = """(() => { window.__vt = { calls: 0, old: [], new: [], dir: [] };
  const real = document.startViewTransition && document.startViewTransition.bind(document);
  if (!real) return;
  document.startViewTransition = (cb) => { const w = window.__vt; w.calls++;
    const named = () => [...document.querySelectorAll('[data-zk]')].filter(n => n.style.viewTransitionName === 'cz-hero').map(n => n.dataset.zk);
    w.old.push(named()); w.dir.push(document.documentElement.dataset.czDir);
    return real(async () => { await cb(); w.new.push(named()); }); }; })();"""


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    monkeypatch.setattr(ai, "TRANSPORT", samples.FakeAzure())


@pytest.fixture
def canvas_page(browser, base_url, model):
    """canvas_page(viewport=PHONE, motion="reduce", touch=True) -> a signed-in page with the Universal + DCA trip added (Universal on Sat, DCA on Mon)."""
    contexts = []

    def make(viewport=PHONE, motion="reduce", touch=True):
        ctx = browser.new_context(viewport=viewport, reduced_motion=motion, has_touch=touch, is_mobile=touch)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/add")          # the old address lands in the one Ask box
        page.locator("#ak-text").fill(samples.text())
        page.locator("#ak-go").click()
        page.locator('[data-q="park:0"] .ak-opt').nth(1).click()
        page.locator('[data-q="park:1"] .ak-opt').nth(3).click()
        page.locator("#ak-continue").click()
        page.locator("#ak-apply").click()
        page.wait_for_selector("#ak-done")
        page.add_init_script(SPY)
        page.goto(f"{base_url}/trip/canvas")
        page.wait_for_selector(".cz-view[data-level=week]")
        return page

    yield make
    for c in contexts:
        c.close()


def level(page):
    return page.locator(".cz-view").get_attribute("data-level")


def settle(page):
    """Wait for a swap, and for any transition to finish."""
    page.wait_for_function("() => !document.documentElement.dataset.czDir")


def checks(page):
    assert page.evaluate(OVERFLOW) <= 0
    assert page.evaluate(SMALL_TEXT) == []
    assert page.evaluate(SMALL_CONTROLS) == []


def open_block(page):
    """Tap the park block on the day (F-097: it is a block on the grid, and a tap near its top opens it)."""
    page.locator(".cz-gb-open").click(position={"x": 90, "y": 40})
    page.locator("#cz-card-rides").click()      # F-106: a tap opens the card; Rides is the way to the block level


# ---- tap through every level and back ---------------------------------------------------------------------------------------

def test_tap_zooms_week_to_day_to_block_to_step_and_every_way_back(canvas_page, base_url):
    page = canvas_page()
    assert level(page) == "week" and page.title().endswith("The trip")
    checks(page)
    page.locator(".cz-row", has_text="Universal Studios Hollywood").locator(".cz-row-link").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    assert "/trip/canvas?day=1" in page.url and "Lower Lot" in page.locator("#cz").inner_text()
    checks(page)
    open_block(page)
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    assert "block=a1" in page.url and page.locator(".cz-bpart").count() >= 4
    checks(page)
    page.locator('.cz-step:has-text("King Kong")').click()
    expect(page.locator(".cz-view[data-level=step]")).to_be_visible()
    expect(page.get_by_role("dialog")).to_be_visible()
    assert page.locator("#cz-sheet-title").inner_text() == "King Kong"
    checks(page)
    page.locator(".cz-close").click()                          # the sheet shrinks back into its row
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    page.locator(".cz-back").click()                           # block > day
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.locator(".cz-head .cz-back").click()                         # day > week (F-103: on a phone the Week side of the switch is the way up; the chevron is hidden)
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    assert page.url.startswith(f"{base_url}/trip/canvas") and "day=" not in page.url and "block=" not in page.url
    for _ in range(3):                                         # the back buttons were the browser's Back: nothing piled up
        assert page.evaluate("history.length") < 12


def test_a_set_aside_chip_on_the_day_zooms_straight_into_its_sheet_and_closing_it_lands_on_the_block(canvas_page):
    page = canvas_page()
    page.goto(page.url + "?day=1")
    page.locator('.cz-tray .cz-chip:has-text("Studio Tour")').click()           # F-097: the day's steps are one tap in; the Set aside tray is still on the day
    expect(page.locator(".cz-view[data-level=step]")).to_be_visible()
    expect(page.locator("#cz-sheet-title")).to_have_text("Studio Tour")
    page.keyboard.press("Escape")                              # the keyboard's way out
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()


def test_the_today_tab_opens_the_day_and_a_week_row_zooms_in(canvas_page):
    page = canvas_page()                     # F-092: no zoom control; the Today tab is the day view, the week's rows zoom in
    assert page.locator("#cz-z-today, .cz-pinch-hint").count() == 0
    page.locator(".cz-row[data-day='3'] .cz-row-link").click()
    expect(page.locator(".cz-view[data-level=day]")).to_have_attribute("data-day", "3")
    expect(page.locator("#ph-tab-ask")).to_have_attribute("href", "/trip/ask?day=3")     # the centre Ask follows the day shown
    page.locator("#ph-tab-today").click()
    page.wait_for_url(re.compile(r"/trip/canvas\?day=0"))   # before the trip, Today is its first day
    expect(page.locator(".cz-view[data-level=day]")).to_have_attribute("data-day", "0")
    page.locator(".cz-head .cz-back").click()                       # the Day | Week toggle, both ways
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    page.locator("#cz-z-day").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()


def test_a_free_day_plus_opens_the_add_sheet_and_every_week_row_opens_its_day(canvas_page):
    page = canvas_page()
    free = page.locator(".cz-row.is-free").first
    free.locator(".cz-plus").click()
    page.wait_for_url("**/trip?add=1&day=*")
    expect(page.locator("#tp-sheet")).to_be_visible()
    page.go_back()
    rows = page.locator(".cz-row")
    for i in range(rows.count()):
        page.locator(".cz-row").nth(i).locator(".cz-row-link").click()
        expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
        assert f"day={i}" in page.url
        page.locator(".cz-head .cz-back").click()
        expect(page.locator(".cz-view[data-level=week]")).to_be_visible()


# ---- the browser's Back and Forward, and opening a level directly -----------------------------------------------------------------

def test_back_and_forward_walk_the_levels_and_a_level_opens_directly(canvas_page, base_url):
    page = canvas_page()
    page.locator(".cz-row", has_text="Universal").locator(".cz-row-link").click()
    open_block(page)
    page.locator('.cz-step:has-text("King Kong")').click()
    expect(page.locator(".cz-view[data-level=step]")).to_be_visible()
    page.go_back()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    page.go_back()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.go_back()
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    page.go_forward()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.go_forward()
    page.go_forward()
    expect(page.locator(".cz-view[data-level=step]")).to_be_visible()
    page.reload()                                                # the address is the level
    expect(page.locator(".cz-view[data-level=step]")).to_be_visible()
    expect(page.locator("#cz-sheet-title")).to_have_text("King Kong")
    page.locator(".cz-close").click()                            # a level opened directly closes to its parent level
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()


# ---- the animation -----------------------------------------------------------------------------------------------------------

def test_the_tapped_element_is_named_before_and_after_the_view_transition(canvas_page):
    page = canvas_page(motion="no-preference")
    assert page.evaluate("typeof document.startViewTransition") == "function"
    page.locator(".cz-row", has_text="Universal").locator(".cz-row-link").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    settle(page)
    vt = page.evaluate("window.__vt")
    assert vt["calls"] == 1 and vt["old"] == [["day-1"]] and vt["new"] == [["day-1"]] and vt["dir"] == ["in"]      # the day row grew into the day heading
    assert page.evaluate("[...document.querySelectorAll('[data-zk]')].filter(n => n.style.viewTransitionName).length") == 0     # and the name is gone again
    page.locator(".cz-head .cz-back").click()
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    settle(page)
    vt = page.evaluate("window.__vt")
    assert vt["calls"] == 2 and vt["old"][1] == ["day-1"] and vt["new"][1] == ["day-1"] and vt["dir"][1] == "out"   # the heading shrank back into the row
    page.locator(".cz-row", has_text="Universal").locator(".cz-row-link").click()
    open_block(page)
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    settle(page)
    assert page.evaluate("window.__vt.old[window.__vt.old.length - 1]") == [page.evaluate("document.querySelector('.cz-view').dataset.zout")]
    page.locator('.cz-step:has-text("King Kong")').click()
    expect(page.locator(".cz-view[data-level=step]")).to_be_visible()
    settle(page)
    vt = page.evaluate("window.__vt")
    assert vt["old"][-1][0].startswith("stp-") and vt["new"][-1] == vt["old"][-1]                 # the step row grew into the sheet


def test_reduced_motion_swaps_instantly_with_no_transition(canvas_page):
    page = canvas_page(motion="reduce")
    page.locator(".cz-row", has_text="Universal").locator(".cz-row-link").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    open_block(page)
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    assert page.evaluate("window.__vt.calls") == 0
    assert page.evaluate("document.documentElement.dataset.czDir") is None
    assert page.evaluate("document.querySelector('.cz-view').getAnimations().length") == 0


def test_without_view_transitions_the_new_level_still_arrives_with_a_short_fade(browser, base_url, model):
    ctx = browser.new_context(viewport=PHONE, reduced_motion="no-preference", has_touch=True, is_mobile=True)
    ctx.set_default_timeout(9000)
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
    ctx.add_init_script("document.startViewTransition = undefined")
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/canvas")
    page.locator(".cz-row-link").nth(0).click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    assert page.evaluate("document.querySelector('.cz-view').className").startswith("cz-view")
    page.locator(".cz-head .cz-back").click()
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    ctx.close()



def test_a_back_press_during_a_running_zoom_is_not_lost(canvas_page):
    page = canvas_page(motion="no-preference")
    page.evaluate("document.documentElement.style.setProperty('--cz-dur', '2500ms')")
    page.locator(".cz-row", has_text="Universal").locator(".cz-row-link").click()
    page.wait_for_url("**day=1**")                                              # the zoom is running (the address changes as it starts)
    page.wait_for_function("document.documentElement.dataset.czDir")
    page.go_back()                                                              # pressed before it finished
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible(timeout=9000)
    assert page.url.split("?")[0].endswith("/trip/canvas") and "day=" not in page.url


# ---- Mark done, Set aside, Put back from the sheet ---------------------------------------------------------------------------

def test_mark_done_from_the_step_sheet_closes_it_and_the_step_is_done(canvas_page):
    page = canvas_page()
    page.goto(page.url + "?block=a1")
    page.locator('.cz-step:has-text("Revenge of the Mummy")').click()
    page.get_by_role("button", name="Mark done").click()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    expect(page.locator(".cz-step.is-done", has_text="Revenge of the Mummy")).to_be_visible()
    expect(page.locator(".cz-prog")).to_have_text("1 of 14 done")
    page.locator(".cz-step.is-done", has_text="Revenge of the Mummy").click()
    expect(page.get_by_role("button", name="Not done")).to_be_visible()
    expect(page.locator("#cz-state")).to_have_text("Done")
    page.get_by_role("button", name="Not done").click()
    expect(page.locator(".cz-prog")).to_have_text("0 of 14 done")
    assert page.locator(".cz-step.is-done").count() == 0


def test_set_aside_and_put_back_from_the_sheet_and_the_tray(canvas_page):
    page = canvas_page()
    page.goto(page.url + "?block=a1")
    page.locator('.cz-swipe:has-text("King Kong") .cz-sw-aside').evaluate("b => b.form.requestSubmit()")      # F-121: Set aside is on the swipe only, not the sheet
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    expect(page.locator(".cz-tray")).to_contain_text("Set aside · 3")
    expect(page.locator(".cz-tray")).to_contain_text("King Kong")
    page.locator(".cz-tray .cz-chip", has_text="King Kong").click()
    page.get_by_role("button", name="Put back").click()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    expect(page.locator(".cz-tray")).to_contain_text("Set aside · 2")
    page.locator(".cz-back").click()
    expect(page.locator(".cz-tray")).to_contain_text("Set aside · 2")
    assert page.locator(".cz-tray .cz-chip").count() == 2


def test_a_write_survives_the_browsers_back_and_forward_buttons(canvas_page):
    page = canvas_page()
    page.locator(".cz-row", has_text="Universal").locator(".cz-row-link").click()
    open_block(page)
    page.locator('.cz-step:has-text("King Kong")').click()
    page.get_by_role("button", name="Mark done").click()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    page.go_back()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.go_forward()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    expect(page.locator(".cz-step.is-done", has_text="King Kong")).to_be_visible()     # fresh, not what was drawn before the tap


# ---- notes, stickers and lanes -------------------------------------------------------------------------------------------------

def test_notes_show_on_their_block_and_step_and_lanes_show_when_people_split_up(canvas_page):
    page = canvas_page()
    me = person("ari")
    with ses.family(me) as fam:
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "UPDATE block_steps SET time = '13:00', who = :w WHERE title = 'Forbidden Journey'", w=json.dumps(["g:Adults"]))
            familydb.run(fam.db, "UPDATE block_steps SET time = '13:00', who = :w WHERE title = 'Hippogriff'", w=json.dumps(["g:Kids"]))
    page.goto(page.url + "?day=1")
    open_block(page)
    expect(page.locator(".cz-sticker-step", has_text="main!!!")).to_be_visible()
    lanes = page.locator(".cz-lanes")
    expect(lanes).to_have_count(1)
    expect(lanes.locator(".cz-lane")).to_have_count(2)
    a, b = [lanes.locator(".cz-lane").nth(i).bounding_box() for i in (0, 1)]
    assert abs(a["y"] - b["y"]) < 2 and b["x"] > a["x"] + a["width"] - 2                       # side by side
    expect(lanes).to_contain_text("Adults")
    expect(lanes).to_contain_text("Kids")
    assert page.evaluate(OVERFLOW) <= 0
    page.locator(".cz-lane .cz-step", has_text="Hippogriff").click()
    expect(page.locator(".cz-note-sticky")).to_have_value("H and B walk")      # F-121: an editor's note is the sticky you write on


def test_every_level_fits_at_320_and_390(canvas_page):
    page = canvas_page()
    for size in (PHONE, NARROW):
        page.set_viewport_size(size)
        for url in ("", "?day=1", "?day=3", "?day=2", "?block=a1", "?block=a2"):
            page.goto(page.url.split("?")[0] + url)
            page.wait_for_selector(".cz-view")
            checks(page)


# ---- the laptop's wide day view --------------------------------------------------------------------------------------------------

def test_desktop_shows_the_week_strip_the_parts_as_lanes_and_the_tray_at_the_side(canvas_page):
    page = canvas_page(viewport=WIDE, touch=False)
    assert page.evaluate(OVERFLOW) <= 0
    page.locator(".cz-row", has_text="Universal").locator(".cz-row-link").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    strip = page.locator(".cz-strip")
    expect(strip).to_be_visible()
    assert strip.locator(".cz-strip-day").count() == 5 and strip.locator(".is-open").count() == 1
    grid = page.locator("#cz-grid").bounding_box()                                                  # the same grid, wider
    assert grid["width"] > 700 and page.locator(".cz-gb.is-park").bounding_box()["width"] > 600
    main, tray = page.locator(".cz-day-main").bounding_box(), page.locator(".cz-tray").bounding_box()
    assert tray["x"] > main["x"] + main["width"] - 2                                                # the Set aside tray sits at the side
    assert page.evaluate(OVERFLOW) <= 0
    other = strip.locator(".cz-strip-day").nth(3)
    other.click()                                                                                   # a day in the strip swaps the day, no page load
    expect(page.locator(".cz-strip-day.is-open")).to_have_attribute("href", re.compile(r"/trip/canvas\?day=3(&|$)"))
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    page.locator(".cz-strip-day").nth(1).click()
    open_block(page)
    page.locator(".cz-step", has_text="Revenge of the Mummy").click()
    expect(page.get_by_role("dialog")).to_be_visible()
    page.get_by_role("button", name="Mark done").click()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    assert page.evaluate(SMALL_TEXT.replace("12.95", "10.95")) == []
    for w in (1000, 800):
        page.set_viewport_size({"width": w, "height": 800})
        assert page.evaluate(OVERFLOW) <= 0


@pytest.mark.skipif(not os.environ.get("F081_SHOTS"), reason="screenshots are made on request: F081_SHOTS=<folder>")
def test_screenshots(canvas_page):
    out = os.environ["F081_SHOTS"]
    page = canvas_page(motion="no-preference")
    page.screenshot(path=f"{out}/week-390.png")
    page.goto(page.url.split("?")[0] + "?day=1")
    page.wait_for_selector(".cz-view[data-level=day]")
    page.screenshot(path=f"{out}/day-390.png", full_page=True)
    page.goto(page.url.split("?")[0] + "?block=a1")
    page.screenshot(path=f"{out}/block-390.png", full_page=True)
    sid = page.locator(".cz-step", has_text="Fast & Furious").get_attribute("data-step")
    page.goto(page.url.split("?")[0] + f"?step={sid}")
    page.screenshot(path=f"{out}/step-390.png")
    page.goto(page.url.split("?")[0] + "?day=1")
    page.wait_for_selector(".cz-view[data-level=day]")
    page.evaluate("document.documentElement.style.setProperty('--cz-dur', '6000ms')")        # slow it down so the middle of the zoom can be caught
    open_block(page)
    page.wait_for_timeout(2600)
    page.screenshot(path=f"{out}/mid-transition-390.png")


@pytest.mark.skipif(not os.environ.get("F081_SHOTS"), reason="screenshots are made on request: F081_SHOTS=<folder>")
def test_screenshots_desktop(canvas_page):
    out = os.environ["F081_SHOTS"]
    page = canvas_page(viewport=WIDE, touch=False)
    page.screenshot(path=f"{out}/week-1280.png")
    page.goto(page.url.split("?")[0] + "?day=1")
    page.wait_for_selector(".cz-view[data-level=day]")
    page.screenshot(path=f"{out}/day-1280.png")
    page.goto(page.url.split("?")[0] + "?block=a1")
    page.screenshot(path=f"{out}/block-1280.png")
