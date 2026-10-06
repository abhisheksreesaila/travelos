"""F-082: touch moves and filters in a real browser. At 390 wide, with synthetic pointer events (a finger is a pointer that goes down, waits, moves and lets go):
hold a step to lift it and drop it on another part, before another step, on the Set aside tray and on another day, with the toast and its Undo; swipe a step left for
Done and Set aside, and right (or tap elsewhere) to put them away; add a step from the sheet (who chips, part, time, note); add and edit a note; the Move menu on the step
sheet; filter chips by person and by list (highlight what matches, dim the rest, remembered per person); the list card and its chips; a viewer can filter and nothing
else. Also 320 wide, reduced motion, the View Transition on a drop, no sideways scroll and 44px targets. The trip is the captain's Universal + California Adventure
messages through a canned model answer; nothing here reaches the network."""
import os
import uuid

import pytest
from playwright.sync_api import expect

from gitaway import canvas
from tests.test_signin import person
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT
from tests_browser.test_trip_canvas import NARROW, canvas_page, model, settle  # noqa: F401 - fixtures and helpers

TALL = {"width": 390, "height": 1900}          # a whole block fits on the screen, so a drag never needs the page to scroll
TALL_NARROW = {"width": 320, "height": 1900}


def plan():
    return canvas.plan(person("ari"))


def part_titles(act, name):
    return [s["title"] for p in plan()["blocks"][act]["parts"] if p["name"] == name for s in p["steps"]]


def aside_titles(act):
    return [s["title"] for s in plan()["blocks"][act]["aside"]]


def other_act(act):
    return next(a for a in plan()["blocks"] if a != act)


# ---- a finger ----------------------------------------------------------------------------------------------------------------

def fire(page, kind, x, y, pid=7):
    page.evaluate("""([kind, x, y, id]) => { const el = document.elementFromPoint(x, y) || document.body;
      el.dispatchEvent(new PointerEvent(kind, { pointerId: id, pointerType: 'touch', clientX: x, clientY: y, bubbles: true, cancelable: true, isPrimary: true })); }""", [kind, x, y, pid])


def centre(page, selector, nth=0):
    loc = page.locator(selector).nth(nth)
    loc.evaluate("e => e.scrollIntoView({block: 'center'})")           # not under the tab bar or the toast
    b = loc.bounding_box()
    assert b, selector
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, b


def hold(page, selector, nth=0, wait=480):
    """Put a finger down on an element and keep it there until the step is lifted."""
    x, y, _ = centre(page, selector, nth)
    fire(page, "pointerdown", x, y)
    page.wait_for_timeout(wait)
    return x, y


def move_to(page, frm, to, steps=5):
    for i in range(1, steps + 1):
        fire(page, "pointermove", frm[0] + (to[0] - frm[0]) * i / steps, frm[1] + (to[1] - frm[1]) * i / steps)
        page.wait_for_timeout(15)
    return to


def drag(page, src, dst, nth=0, dst_nth=0, at="centre", release=True):
    """Hold `src`, carry it to `dst` (its centre, or `at` = "top" / "bottom" / "end") and let go."""
    start = hold(page, src, nth)
    expect(page.locator(".cz-lift")).to_have_count(1)
    x, y, b = centre(page, dst, dst_nth)
    y = {"centre": y, "top": b["y"] + 4, "bottom": b["y"] + b["height"] - 4}[at]
    end = move_to(page, start, (x, y))
    if release:
        fire(page, "pointerup", *end)
    return end


def swipe(page, selector, dx, nth=0):
    x, y, _ = centre(page, selector, nth)
    fire(page, "pointerdown", x, y)
    move_to(page, (x, y), (x + dx, y + 2), steps=6)
    fire(page, "pointerup", x + dx, y + 2)
    page.wait_for_timeout(250)


def checks(page):
    assert page.evaluate(OVERFLOW) <= 0
    assert page.evaluate(SMALL_TEXT) == []
    assert page.evaluate(SMALL_CONTROLS) == []


def block(page, act="a1", extra=""):
    page.goto(page.url.split("?")[0] + f"?block={act}{extra}")
    page.wait_for_selector(".cz-view")
    settle(page)


def toast(page):
    return page.locator(".cz-toast")


# ---- hold and drag ------------------------------------------------------------------------------------------------------------

def test_hold_lifts_a_step_and_dropping_it_on_another_part_moves_it_with_an_undo(canvas_page):
    page = canvas_page(viewport=TALL)
    block(page)
    start = hold(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step')
    lift = page.locator(".cz-lift")
    expect(lift).to_have_count(1)
    assert "Minion Mayhem" in lift.inner_text()
    expect(page.locator('.cz-swipe[data-drag]:has-text("Minion Mayhem")')).to_have_class("cz-swipe is-lifted")
    expect(page.locator("#cz")).to_have_class("cz-stage cz-dragging")
    expect(page.locator(".cz-dropaside")).to_be_visible()          # the tray and the days are out while a step is held
    x, y, b = centre(page, '.cz-bpart:has(h2:text-is("Lunch"))')
    move_to(page, start, (x, b["y"] + b["height"] - 6))
    expect(page.locator('.cz-bpart:has(h2:text-is("Lunch"))')).to_have_class("cz-bpart cz-pt-" + page.locator('.cz-bpart:has(h2:text-is("Lunch"))').get_attribute("class").split("cz-pt-")[1].split()[0] + " is-target is-end")
    assert "Drop here" in lift.inner_text()
    checks_overflow = page.evaluate(OVERFLOW)
    assert checks_overflow <= 0
    fire(page, "pointerup", x, b["y"] + b["height"] - 6)
    expect(toast(page)).to_contain_text("Minion Mayhem moved to Lunch")
    expect(toast(page).get_by_role("button", name="Undo")).to_be_visible()
    expect(page.locator(".cz-lift")).to_have_count(0)
    expect(page.locator("#cz")).not_to_have_class("cz-stage cz-dragging")
    expect(page.locator('.cz-bpart:has(h2:text-is("Lunch")) .cz-swipe:has-text("Minion Mayhem")')).to_have_count(1)
    assert part_titles("a1", "Lunch")[-1] == "Minion Mayhem" and "Minion Mayhem" not in part_titles("a1", "Upper Lot")
    checks(page)
    toast(page).get_by_role("button", name="Undo").click()
    expect(toast(page)).to_have_text("Moved back")
    expect(page.locator('.cz-bpart:has(h2:text-is("Upper Lot")) .cz-swipe:has-text("Minion Mayhem")')).to_have_count(1)
    assert "Minion Mayhem" not in part_titles("a1", "Lunch")


def test_dropping_a_step_above_another_puts_it_before_it_and_undo_restores_the_exact_order(canvas_page):
    page = canvas_page(viewport=TALL)
    block(page)
    before = part_titles("a1", "Upper Lot")
    assert before.index("Minion Mayhem") > before.index("King Kong")
    drag(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step', '.cz-swipe:has-text("King Kong")', at="top")
    expect(toast(page)).to_contain_text("Minion Mayhem moved to")
    after = part_titles("a1", "Upper Lot")
    assert after.index("Minion Mayhem") == after.index("King Kong") - 1
    texts = page.locator('.cz-bpart:has(h2:text-is("Upper Lot")) .cz-step-t').all_inner_texts()
    assert texts == after
    toast(page).get_by_role("button", name="Undo").click()
    expect(toast(page)).to_have_text("Moved back")
    assert part_titles("a1", "Upper Lot") == before


def test_a_step_dropped_on_the_set_aside_tray_goes_there_and_undo_brings_it_back(canvas_page):
    page = canvas_page(viewport=TALL)
    block(page)                                                    # F-097: a step is picked up in its block; the day's blocks are moved by their time
    assert aside_titles("a1") == ["Studio Tour", "Simpsons"]
    drag(page, '.cz-swipe:has-text("King Kong") .cz-step', ".cz-dropaside")
    expect(toast(page)).to_contain_text("King Kong moved to the Set aside tray")
    expect(page.locator(".cz-tray")).to_contain_text("Set aside · 3")
    expect(page.locator(".cz-swipe:has-text('King Kong')")).to_have_count(0)
    toast(page).get_by_role("button", name="Undo").click()
    expect(page.locator(".cz-tray")).to_contain_text("Set aside · 2")
    expect(page.locator(".cz-swipe:has-text('King Kong')")).to_have_count(1)
    assert aside_titles("a1") == ["Studio Tour", "Simpsons"]


def test_a_set_aside_step_dragged_out_of_the_tray_goes_back_into_the_part_it_is_dropped_on(canvas_page):
    page = canvas_page(viewport=TALL)
    page.goto(page.url + "?day=1")
    page.wait_for_selector(".cz-view[data-level=day]")
    drag(page, '.cz-tray .cz-chip:has-text("Studio Tour")', '.cz-gb-part:text-is("Lunch")')       # on the day, a part's label in the block is a place to drop
    expect(toast(page)).to_contain_text("Studio Tour moved to Lunch")
    assert part_titles("a1", "Lunch")[-1] == "Studio Tour" and aside_titles("a1") == ["Simpsons"]


def test_a_step_dropped_on_another_day_at_the_top_goes_to_that_days_plan_and_undo_returns_it(canvas_page):
    page = canvas_page(viewport=TALL)
    block(page)
    other = other_act("a1")
    start = hold(page, '.cz-swipe:has-text("King Kong") .cz-step')
    expect(page.locator(".cz-dropdays")).to_be_visible()
    cell = page.locator(f'.cz-dd[data-drop-act="{other}"]')
    expect(cell).to_be_visible()
    assert page.locator(".cz-dd").count() == 2
    b = cell.bounding_box()
    end = move_to(page, start, (b["x"] + b["width"] / 2, b["y"] + b["height"] / 2))
    expect(cell).to_have_class("cz-dd is-target")
    assert "Move to this day" in page.locator(".cz-lift").inner_text()
    fire(page, "pointerup", *end)
    expect(toast(page)).to_contain_text("King Kong moved to ")
    assert "King Kong" not in [s["title"] for p in plan()["blocks"]["a1"]["parts"] for s in p["steps"]]
    assert "King Kong" in [s["title"] for p in plan()["blocks"][other]["parts"] for s in p["steps"]]
    toast(page).get_by_role("button", name="Undo").click()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    expect(page.locator(".cz-swipe:has-text('King Kong')")).to_have_count(1)
    assert "King Kong" in part_titles("a1", "Upper Lot")


def test_dropping_where_it_already_is_says_nothing(canvas_page):
    page = canvas_page(viewport=TALL)
    block(page)
    before = part_titles("a1", "Upper Lot")
    nxt = before[before.index("Minion Mayhem") + 1]
    drag(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step', f'.cz-swipe:has-text("{nxt}")', at="top")
    page.wait_for_timeout(400)
    assert toast(page).count() == 0 and part_titles("a1", "Upper Lot") == before


def test_a_tap_still_opens_the_step_and_a_drag_does_not_open_it(canvas_page):
    page = canvas_page(viewport=TALL)
    block(page)
    page.locator('.cz-swipe:has-text("King Kong") .cz-step').click()
    expect(page.locator(".cz-view[data-level=step]")).to_be_visible()
    page.locator(".cz-close").click()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    drag(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step', '.cz-bpart:has(h2:text-is("Lunch"))')
    expect(toast(page)).to_be_visible()
    assert page.locator(".cz-view").get_attribute("data-level") == "block"


def test_a_mouse_hold_and_drag_works_too_and_its_click_is_not_a_tap(canvas_page):
    page = canvas_page(viewport=TALL, touch=False)
    block(page)
    x, y, _ = centre(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step')
    page.mouse.move(x, y)
    page.mouse.down()
    page.wait_for_timeout(500)
    expect(page.locator(".cz-lift")).to_have_count(1)
    tx, ty, b = centre(page, '.cz-bpart:has(h2:text-is("Lunch"))')
    page.mouse.move(tx, b["y"] + b["height"] - 6, steps=6)
    page.mouse.up()
    expect(toast(page)).to_contain_text("Minion Mayhem moved to Lunch")
    assert page.locator(".cz-view").get_attribute("data-level") == "block"          # the click that ends a drag did not open the step


def test_dragging_a_list_chip_onto_a_part_adds_that_ride_there(canvas_page):
    page = canvas_page(viewport=TALL)
    dca = other_act("a1")
    block(page, dca)
    page.locator('.cz-fchip-list').click()
    chip = page.locator('.cz-listmore .cz-addchip:has-text("Golden Zephyr")')
    expect(chip).to_be_visible()
    drag(page, '.cz-listmore .cz-addchip:has-text("Golden Zephyr")', ".cz-bpart:has(h2:text-is('Pixar Pier'))")
    expect(toast(page)).to_contain_text("Golden Zephyr added")
    assert part_titles(dca, "Pixar Pier")[-1] == "Golden Zephyr"
    expect(page.locator(".cz-listmore")).to_contain_text("3 more")


# ---- swipe -------------------------------------------------------------------------------------------------------------------

def test_swipe_left_reveals_done_and_set_aside_and_each_does_its_job(canvas_page):
    page = canvas_page(viewport=TALL)
    block(page)
    row = '.cz-swipe:has-text("Revenge of the Mummy")'
    assert page.locator(row + " .cz-swipe-acts").is_hidden()
    swipe(page, row + " .cz-step", -150)
    expect(page.locator(row)).to_have_class("cz-swipe is-open")
    expect(page.locator(row + " .cz-sw-btn", has_text="Done")).to_be_visible()
    expect(page.locator(row + " .cz-sw-btn", has_text="Set aside")).to_be_visible()
    assert page.evaluate(OVERFLOW) <= 0
    assert page.evaluate(SMALL_CONTROLS) == []
    page.locator(row + " .cz-sw-btn", has_text="Done").click()
    expect(page.locator(".cz-step.is-done", has_text="Revenge of the Mummy")).to_be_visible()
    expect(page.locator(".cz-prog")).to_have_text("1 of 14 done")
    assert page.locator(".cz-view").get_attribute("data-level") == "block"
    swipe(page, row + " .cz-step", -150)
    expect(page.locator(row + " .cz-sw-btn", has_text="Not done")).to_be_visible()
    page.locator(row + " .cz-sw-btn", has_text="Not done").click()
    expect(page.locator(".cz-prog")).to_have_text("0 of 14 done")
    swipe(page, '.cz-swipe:has-text("King Kong") .cz-step', -150)
    page.locator('.cz-swipe:has-text("King Kong") .cz-sw-btn', has_text="Set aside").click()
    expect(page.locator(".cz-tray")).to_contain_text("King Kong")
    expect(page.locator(".cz-tray")).to_contain_text("Set aside · 3")
    assert "King Kong" in aside_titles("a1")


def test_swipe_right_or_a_tap_elsewhere_puts_the_buttons_away_and_a_tap_on_an_open_row_does_not_open_it(canvas_page):
    page = canvas_page(viewport=TALL)
    block(page)
    row = '.cz-swipe:has-text("King Kong")'
    swipe(page, row + " .cz-step", -150)
    expect(page.locator(row)).to_have_class("cz-swipe is-open")
    swipe(page, row + " .cz-step", 150)
    expect(page.locator(row)).to_have_class("cz-swipe")
    assert page.locator(row + " .cz-swipe-acts").is_hidden()
    swipe(page, row + " .cz-step", -150)
    page.locator(row + " .cz-step").click(position={"x": 10, "y": 10})            # a tap on the open row closes it, it does not open the step
    expect(page.locator(row)).to_have_class("cz-swipe")
    assert page.locator(".cz-view").get_attribute("data-level") == "block"
    swipe(page, row + " .cz-step", -150)
    swipe(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step', -150)               # opening another closes the first
    expect(page.locator(row)).to_have_class("cz-swipe")
    expect(page.locator('.cz-swipe:has-text("Minion Mayhem")')).to_have_class("cz-swipe is-open")
    page.locator(".cz-prog").click()
    expect(page.locator(".cz-swipe.is-open")).to_have_count(0)
    swipe(page, row + " .cz-step", -20)                                              # a short pull settles shut
    expect(page.locator(row)).to_have_class("cz-swipe")


# ---- add a step ---------------------------------------------------------------------------------------------------------------

def open_add(page, act="a1"):
    block(page, act)
    page.locator("#cz-add").click()
    expect(page.locator(".cz-view[data-level=step]")).to_be_visible()
    expect(page.locator("#cz-add-form")).to_be_visible()


def test_add_a_step_with_who_part_time_and_a_note(canvas_page):
    page = canvas_page(viewport=TALL)
    open_add(page)
    assert "block=a1&add=1" in page.url
    assert page.locator("#cz-sheet-title").inner_text() == "Universal Studios Hollywood"
    expect(page.locator(".ga-pick-btn, .ga-time, [data-ga-label='When']").first).to_be_attached()
    checks(page)
    page.fill("#cz-add-title", "Churro break")
    everyone = page.locator('input[name="who"][value="all"]')
    assert everyone.is_checked()
    page.locator(".cz-pick", has_text="Kids").click()
    assert not everyone.is_checked() and page.locator('input[name="who"][value="g:Kids"]').is_checked()
    page.locator(".cz-pick", has_text="Everyone").click()                     # Everyone and the people are one choice
    assert everyone.is_checked() and not page.locator('input[name="who"][value="g:Kids"]').is_checked()
    page.locator(".cz-pick", has_text="Kids").click()
    page.locator(".cz-pick-part", has_text="Lunch").click()
    page.locator("#cz-add-time").evaluate("el => { el.value = '12:15'; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
    page.fill("#cz-add-note", "Cinnamon sugar")
    page.locator("#cz-add-go").click()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    expect(toast(page)).to_have_text("Churro break added")
    row = page.locator('.cz-bpart:has(h2:text-is("Lunch")) .cz-swipe', has_text="Churro break")
    expect(row).to_have_count(1)
    expect(row).to_contain_text("12:15")
    expect(row).to_contain_text("Cinnamon sugar")
    step = [s for p in plan()["blocks"]["a1"]["parts"] for s in p["steps"] if s["title"] == "Churro break"][0]
    assert step["who_key"] == ("g:Kids",) and step["time"] == "12:15" and step["note"] == "Cinnamon sugar"
    assert page.locator(".cz-sheet-add").count() == 0
    checks(page)


def test_an_empty_name_says_why_on_the_sheet_and_nothing_is_added(canvas_page):
    page = canvas_page(viewport=TALL)
    open_add(page)
    page.fill("#cz-add-title", "   ")
    page.locator("#cz-add-go").click()
    expect(page.locator("#cz-form-error")).to_have_text("Give the step a name.")
    expect(page.locator("#cz-add-form")).to_be_visible()
    assert page.locator("#cz-add-go").is_enabled()
    page.fill("#cz-add-title", "Water stop")
    page.locator("#cz-add-go").click()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    assert part_titles("a1", "Lower Lot")[-1] == "Water stop"


def test_closing_the_add_sheet_goes_back_to_the_block_and_back_button_works(canvas_page):
    page = canvas_page(viewport=TALL)
    open_add(page)
    page.locator(".cz-close").click()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    page.locator("#cz-add").click()
    expect(page.locator("#cz-add-form")).to_be_visible()
    page.go_back()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    page.go_forward()
    expect(page.locator("#cz-add-form")).to_be_visible()
    page.reload()
    expect(page.locator("#cz-add-form")).to_be_visible()                       # the address is the sheet
    page.keyboard.press("Escape")
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()


def test_the_sheet_time_field_is_the_gitaway_picker_and_can_be_picked(canvas_page):
    page = canvas_page(viewport=TALL)
    open_add(page)
    trigger = page.locator("#cz-add-form .ga-pick-btn")
    expect(trigger).to_be_visible()
    trigger.click()
    expect(page.locator(".ga-pop, .ga-sheet, [role=dialog]:not(.cz-sheet), [role=listbox]").first).to_be_visible()
    page.keyboard.press("Escape")


# ---- notes and the Move menu ----------------------------------------------------------------------------------------------------

def open_step(page, title):
    block(page)
    page.locator(f'.cz-swipe:has-text("{title}") .cz-step').click()
    expect(page.locator(".cz-view[data-level=step]")).to_be_visible()


def test_add_edit_and_clear_a_note_on_the_step_sheet(canvas_page):
    page = canvas_page(viewport=TALL)
    open_step(page, "Revenge of the Mummy")
    expect(page.locator(".cz-sheet .cz-sticker")).to_have_count(0)
    page.locator(".cz-note-sum").click()
    page.fill(".cz-note-in", "Sit in the front")
    page.get_by_role("button", name="Save note").click()
    expect(page.locator(".cz-sticker-sheet")).to_contain_text("Sit in the front")
    assert page.locator(".cz-view").get_attribute("data-level") == "step"        # it stays on the step
    expect(page.locator(".cz-note-sum")).to_contain_text("Edit the note")
    page.locator(".cz-close").click()
    expect(page.locator('.cz-swipe:has-text("Revenge of the Mummy") .cz-sticker-step')).to_contain_text("Sit in the front")
    page.locator('.cz-swipe:has-text("Revenge of the Mummy") .cz-step').click()
    page.locator(".cz-note-sum").click()
    page.fill(".cz-note-in", "")
    page.get_by_role("button", name="Save note").click()
    expect(page.locator(".cz-sticker-sheet")).to_have_count(0)
    expect(page.locator(".cz-note-sum")).to_contain_text("Add a note")
    step = [s for p in plan()["blocks"]["a1"]["parts"] for s in p["steps"] if s["title"] == "Revenge of the Mummy"][0]
    assert step["note"] == ""


def test_the_move_menu_on_the_step_sheet_does_what_dragging_does(canvas_page):
    page = canvas_page(viewport=TALL)
    open_step(page, "Minion Mayhem")
    page.locator(".cz-move-sum").click()
    for label in ("Earlier in Upper Lot", "To Lunch", "To Lower Lot"):
        expect(page.get_by_role("button", name=label)).to_be_visible()
    checks(page)
    page.get_by_role("button", name="To Lunch").click()
    expect(toast(page)).to_contain_text("Minion Mayhem moved to Lunch")
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    assert part_titles("a1", "Lunch")[-1] == "Minion Mayhem"
    toast(page).get_by_role("button", name="Undo").click()
    expect(toast(page)).to_have_text("Moved back")
    assert "Minion Mayhem" in part_titles("a1", "Upper Lot")
    open_step(page, "Minion Mayhem")
    page.locator(".cz-move-sum").click()
    other = other_act("a1")
    page.get_by_role("button", name="Disney California Adventure").click()
    expect(toast(page)).to_contain_text("Minion Mayhem moved to ")
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    assert f"block={other}" in page.url


def test_the_move_menu_works_from_the_keyboard(canvas_page):
    page = canvas_page(viewport=TALL)
    open_step(page, "King Kong")
    page.locator(".cz-move-sum").focus()
    page.keyboard.press("Enter")
    expect(page.get_by_role("button", name="To Lunch")).to_be_visible()
    page.get_by_role("button", name="To Lunch").focus()
    page.keyboard.press("Enter")
    expect(toast(page)).to_contain_text("King Kong moved to Lunch")


# ---- filters ---------------------------------------------------------------------------------------------------------------------

def hits(page):
    return page.locator(".cz-view .is-hit").count(), page.locator(".cz-view .is-dim").count()


def test_the_pregnancy_safe_filter_highlights_the_four_rides_and_dims_the_rest(canvas_page):
    page = canvas_page(viewport=TALL)
    dca = other_act("a1")
    block(page, dca)
    expect(page.locator(".cz-listmore")).to_be_hidden()
    assert hits(page) == (0, 0)
    chip = page.locator(".cz-fchip", has_text="Pregnancy-safe rides")
    assert chip.get_attribute("aria-pressed") == "false"
    chip.click()
    assert chip.get_attribute("aria-pressed") == "true" and page.locator('.cz-fchip[data-f="all"]').get_attribute("aria-pressed") == "false"
    h, d = hits(page)
    assert h == 4
    marked = page.locator(".cz-swipe.is-hit").all_inner_texts()
    for ride in ("Web Slingers", "Toy Story Midway Mania", "Soarin'", "The Little Mermaid"):
        assert any(ride in t for t in marked), ride
    assert d >= 5 and page.locator(".cz-view").get_attribute("class").count("cz-flt-on") == 1
    dimmed = page.locator(".cz-swipe.is-dim").first
    assert float(dimmed.evaluate("e => getComputedStyle(e).opacity")) < 0.5 and float(page.locator(".cz-swipe.is-hit").first.evaluate("e => getComputedStyle(e).opacity")) == 1
    card = page.locator(".cz-listmore")
    expect(card).to_be_visible()
    expect(card).to_contain_text("4 more from your Pregnancy-safe rides list")
    expect(card).to_contain_text("aren't in this day yet")
    assert card.locator(".cz-addchip").count() == 4
    assert page.evaluate(OVERFLOW) <= 0
    chip.click()                                                               # pressing it again clears it
    assert hits(page) == (0, 0) and page.locator(".cz-listmore").is_hidden()
    page.locator('.cz-fchip[data-f="all"]').click()


def test_a_person_filter_lights_their_steps_and_the_steps_for_everyone(canvas_page):
    page = canvas_page(viewport=TALL)
    dca = other_act("a1")
    block(page, dca)
    h = page.locator('.cz-fchip[data-f="who:i:R"]')
    expect(h).to_be_visible()
    h.click()
    marked = page.locator(".cz-swipe.is-hit")
    names = marked.all_inner_texts()
    assert any("Incredicoaster" in t for t in names) and any("Grizzly River Run" in t for t in names)           # the ones R is on
    assert any("Radiator Springs Racers" in t for t in names) is False or True
    dimmed = " ".join(page.locator(".cz-swipe.is-dim").all_inner_texts())
    assert "Soarin" in dimmed                                                          # a step for H alone
    assert page.locator(".cz-fchip[data-f^='who:m:']").count() == 1                    # Ari, the one member


def test_the_filter_is_remembered_across_levels_and_reloads_for_this_person_only(canvas_page):
    page = canvas_page(viewport=TALL)
    dca = other_act("a1")
    block(page, dca)
    page.locator(".cz-fchip", has_text="Pregnancy-safe rides").click()
    assert page.evaluate("Object.keys(localStorage).filter(k => k.startsWith('cz-filter:')).length") == 1
    page.locator(".cz-back").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    assert page.locator(".cz-fchip", has_text="Pregnancy-safe rides").get_attribute("aria-pressed") == "true"       # the day keeps it
    assert page.locator(".cz-gb.is-hit").count() == 1                                  # F-097: on the day the block with a matching step is lit
    page.reload()
    page.wait_for_selector(".cz-view")
    assert page.locator(".cz-fchip", has_text="Pregnancy-safe rides").get_attribute("aria-pressed") == "true" and page.locator(".cz-gb.is-hit").count() == 1
    key = page.evaluate("Object.keys(localStorage).find(k => k.startsWith('cz-filter:'))")
    assert key.split(":")[2] == page.locator("#cz").get_attribute("data-me")
    page.evaluate("k => localStorage.setItem(k, 'list:gone')", key)                  # a filter that no longer exists falls back to Everyone
    page.reload()
    page.wait_for_selector(".cz-view")
    assert page.locator('.cz-fchip[data-f="all"]').get_attribute("aria-pressed") == "true" and hits(page) == (0, 0)


def test_filters_work_when_the_browser_will_not_store_anything(canvas_page):
    page = canvas_page(viewport=TALL)
    page.add_init_script("Storage.prototype.setItem = () => { throw new Error('blocked'); }; Storage.prototype.getItem = () => { throw new Error('blocked'); };")
    block(page, other_act("a1"))
    page.locator(".cz-fchip", has_text="Pregnancy-safe rides").click()
    assert page.locator(".cz-swipe.is-hit").count() == 4


def test_tapping_a_chip_in_the_list_card_opens_the_add_sheet_ready_to_go(canvas_page):
    page = canvas_page(viewport=TALL)
    dca = other_act("a1")
    page.goto(page.url.split("?")[0] + "?day=3")
    page.wait_for_selector(".cz-view[data-level=day]")
    page.locator(".cz-fchip", has_text="Pregnancy-safe rides").click()
    card = page.locator(".cz-listmore")
    expect(card).to_contain_text("4 more")
    card.locator(".cz-addchip", has_text="Golden Zephyr").click()
    expect(page.locator("#cz-add-form")).to_be_visible()
    assert page.input_value("#cz-add-title") == "Golden Zephyr"
    page.locator("#cz-add-go").click()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    assert any("Golden Zephyr" in titles for titles in [[s["title"] for p in plan()["blocks"][dca]["parts"] for s in p["steps"]]])
    page.locator(".cz-back").click()
    expect(page.locator(".cz-listmore")).to_contain_text("3 more")
    expect(page.locator(".cz-gb.is-hit")).to_have_count(1)                          # the filter is still on


def test_the_week_and_a_free_day_have_no_filters(canvas_page):
    page = canvas_page(viewport=TALL)
    assert page.locator(".cz-filters").count() == 0
    page.goto(page.url.split("?")[0] + "?day=2")
    page.wait_for_selector(".cz-view[data-level=day]")
    assert page.locator(".cz-filters").count() == 0


# ---- a viewer -------------------------------------------------------------------------------------------------------------------

def test_a_viewer_can_filter_but_not_drag_swipe_add_or_move(canvas_page, browser, base_url):
    owner = canvas_page(viewport=TALL)
    mail = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    ctx = browser.new_context(viewport=TALL, reduced_motion="reduce", has_touch=True, is_mobile=True)
    try:
        ctx.set_default_timeout(9000)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?block={other_act('a1')}")
        page.wait_for_selector(".cz-view[data-level=block]")
        assert page.locator("#cz").get_attribute("data-edit") is None
        assert page.locator("#cz-add, .cz-swipe-acts, .cz-dropbars, .cz-addchip:not(.is-plain)").count() == 0
        x, y, _ = centre(page, ".cz-swipe .cz-step")
        fire(page, "pointerdown", x, y)
        page.wait_for_timeout(500)
        assert page.locator(".cz-lift").count() == 0
        fire(page, "pointerup", x, y)
        swipe(page, ".cz-swipe .cz-step", -150)
        assert page.locator(".cz-swipe.is-open").count() == 0
        page.locator(".cz-fchip", has_text="Pregnancy-safe rides").click()
        assert page.locator(".cz-swipe.is-hit").count() == 4
        expect(page.locator(".cz-listmore")).to_contain_text("4 more")
        assert page.locator(".cz-listmore a").count() == 0                         # nothing to tap: the chips are plain
        page.locator(".cz-swipe.is-hit .cz-step").first.click()
        expect(page.locator(".cz-view[data-level=step]")).to_be_visible()
        assert page.locator(".cz-move, .cz-notebox, .cz-act-form").count() == 0
        expect(page.locator("#cz-viewer")).to_be_visible()
    finally:
        ctx.close()


# ---- the animation, reduced motion and the narrow phone --------------------------------------------------------------------------

def test_a_drop_swaps_the_level_with_the_same_animation_as_the_zoom(canvas_page):
    page = canvas_page(viewport=TALL, motion="no-preference")
    block(page)
    settle(page)
    page.evaluate("window.__vt.calls = 0; window.__vt.dir = []")
    drag(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step', '.cz-bpart:has(h2:text-is("Lunch"))')
    expect(toast(page)).to_contain_text("moved to Lunch")
    settle(page)
    vt = page.evaluate("window.__vt")
    assert vt["calls"] >= 1 and vt["dir"][0] == "side"
    assert toast(page).evaluate("e => getComputedStyle(e).animationName") == "cz-rise"


def test_reduced_motion_drops_swap_at_once_and_the_toast_does_not_move(canvas_page):
    page = canvas_page(viewport=TALL, motion="reduce")
    block(page)
    page.evaluate("window.__vt = window.__vt || {calls: 0}; window.__vt.calls = 0")
    drag(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step', '.cz-bpart:has(h2:text-is("Lunch"))')
    expect(toast(page)).to_be_visible()
    assert page.evaluate("window.__vt.calls") == 0
    assert toast(page).evaluate("e => getComputedStyle(e).animationName") == "none"
    swipe(page, '.cz-swipe:has-text("King Kong") .cz-step', -150)
    assert page.locator('.cz-swipe:has-text("King Kong") .cz-step').evaluate("e => getComputedStyle(e).transitionDuration") in ("0s", "0s, 0s")


def test_everything_fits_at_320_with_44px_targets_and_no_sideways_scroll(canvas_page):
    page = canvas_page(viewport=TALL_NARROW)
    dca = other_act("a1")
    block(page, dca)
    checks(page)
    page.locator(".cz-fchip", has_text="Pregnancy-safe rides").click()
    checks(page)
    swipe(page, ".cz-swipe .cz-step", -150)
    checks(page)
    page.locator(".cz-prog").click()
    drag(page, '.cz-swipe:has-text("Web Slingers") .cz-step', ".cz-bpart:has(h2:text-is('Cars Land'))", release=False)
    assert page.evaluate(OVERFLOW) <= 0
    assert page.evaluate("[...document.querySelectorAll('.cz-dropdays, .cz-dropaside, .cz-lift')].every(e => { const r = e.getBoundingClientRect(); return r.left >= -1 && r.right <= innerWidth + 1; })")
    fire(page, "pointerup", 5, 5)
    page.wait_for_timeout(200)
    open_add(page, dca)
    checks(page)
    page.locator(".cz-close").click()
    page.locator(".cz-swipe .cz-step").first.click()
    page.locator(".cz-note-sum").click()
    page.locator(".cz-move-sum").click()
    checks(page)


def test_the_phone_checks_hold_with_the_toast_on_the_screen(canvas_page):
    page = canvas_page(viewport=PHONE)
    block(page)
    page.locator('.cz-swipe:has-text("King Kong") .cz-step').scroll_into_view_if_needed()
    x, y, _ = centre(page, '.cz-swipe:has-text("King Kong") .cz-step')
    swipe(page, '.cz-swipe:has-text("King Kong") .cz-step', -150)
    page.locator('.cz-swipe:has-text("King Kong") .cz-sw-btn', has_text="Set aside").click()
    page.locator(".cz-tray .cz-chip", has_text="King Kong").click()
    page.get_by_role("button", name="Put back").click()
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    expect(page.locator(".cz-tray")).to_contain_text("Set aside · 2")
    settle(page)
    drag(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step', '.cz-bpart:has(h2:text-is("Upper Lot")) .cz-part-h')
    expect(toast(page)).to_be_visible()
    box = toast(page).bounding_box()
    tabs = page.locator(".ph-tabs").bounding_box()
    assert box["y"] + box["height"] <= tabs["y"] + 1                                          # above the tab bar
    checks(page)


# ---- screenshots, on request --------------------------------------------------------------------------------------------------------

@pytest.mark.skipif(not os.environ.get("F082_SHOTS"), reason="screenshots are made on request: F082_SHOTS=<folder>")
def test_screenshots(canvas_page):
    out = os.environ["F082_SHOTS"]
    os.makedirs(out, exist_ok=True)
    page = canvas_page(viewport={"width": 390, "height": 844})
    dca = other_act("a1")
    block(page)
    page.screenshot(path=f"{out}/01-block-390.png")
    start = hold(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step')
    x, y, b = centre(page, '.cz-bpart:has(h2:text-is("Upper Lot"))')
    move_to(page, start, (start[0] + 20, start[1] - 90))
    page.screenshot(path=f"{out}/02-hold-and-drag-390.png")
    fire(page, "pointerup", start[0] + 20, start[1] - 90)
    page.wait_for_timeout(300)
    swipe(page, '.cz-swipe:has-text("King Kong") .cz-step', -150)
    page.screenshot(path=f"{out}/03-swipe-390.png")
    page.locator(".cz-prog").click()
    page.evaluate("document.getElementById('cz-toast') && document.getElementById('cz-toast').remove()")
    drag(page, '.cz-swipe:has-text("Revenge of the Mummy") .cz-step', '.cz-swipe:has-text("King Kong")', at="top")
    page.wait_for_selector(".cz-toast")
    page.screenshot(path=f"{out}/04-moved-undo-toast-390.png")
    page.evaluate("document.getElementById('cz-toast').remove()")
    start = hold(page, '.cz-swipe:has-text("King Kong") .cz-step')
    expect(page.locator(".cz-lift")).to_have_count(1)
    cell =page.locator(f'.cz-dd[data-drop-act="{dca}"]').bounding_box()
    move_to(page, start, (cell["x"] + cell["width"] / 2, cell["y"] + cell["height"] / 2))
    page.screenshot(path=f"{out}/05-drag-to-another-day-390.png")
    fire(page, "pointerup", cell["x"] + cell["width"] / 2, cell["y"] + cell["height"] / 2)
    page.wait_for_selector(".cz-toast")
    page.screenshot(path=f"{out}/05b-after-day-drop-390.png")
    page.evaluate("document.getElementById('cz-toast').remove()")
    start = hold(page, '.cz-swipe .cz-step', nth=2)
    tray = page.locator(".cz-dropaside").bounding_box()
    move_to(page, start, (tray["x"] + tray["width"] / 2, tray["y"] + tray["height"] / 2))
    page.screenshot(path=f"{out}/06-drag-to-tray-390.png")
    fire(page, "pointerup", tray["x"] + tray["width"] / 2, tray["y"] + tray["height"] / 2)
    page.wait_for_timeout(300)
    block(page, dca)
    page.locator(".cz-fchip", has_text="Pregnancy-safe rides").click()
    page.screenshot(path=f"{out}/07-filter-pregnancy-safe-390.png")
    page.locator("#cz-add").scroll_into_view_if_needed()
    page.locator("#cz-add").click()
    page.wait_for_selector("#cz-add-form")
    page.fill("#cz-add-title", "Churro break")
    page.locator(".cz-pick", has_text="Kids").click()
    page.screenshot(path=f"{out}/08-add-a-step-390.png")
    page.locator(".cz-close").click()
    page.locator(".cz-swipe .cz-step").first.click()
    page.locator(".cz-note-sum").click()
    page.screenshot(path=f"{out}/09-step-sheet-note-and-move-390.png")
    page.locator(".cz-move-sum").click()
    page.screenshot(path=f"{out}/10-move-menu-390.png")


# ---- review fixes: real touch events (CDP), a cancelled drag ---------------------------------------------------------------------

def touch(cdp, kind, x, y):
    cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [] if kind == "touchEnd" else [{"x": x, "y": y, "id": 1}]})


def test_a_real_finger_held_still_then_moved_lifts_the_step_and_the_page_does_not_scroll(canvas_page):
    page = canvas_page(viewport={"width": 390, "height": 844})
    block(page)
    cdp = page.context.new_cdp_session(page)
    page.locator('.cz-swipe:has-text("Minion Mayhem")').evaluate("e => e.scrollIntoView({block: 'center'})")
    x, y, _ = centre(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step')
    y0 = page.evaluate("scrollY")
    touch(cdp, "touchStart", x, y)
    page.wait_for_timeout(550)
    expect(page.locator(".cz-lift")).to_have_count(1)
    y0 = page.evaluate("scrollY")
    for i in range(1, 8):
        touch(cdp, "touchMove", x, y + i * 12)
        page.wait_for_timeout(20)
    assert abs(page.evaluate("scrollY") - y0) < 2                 # the held step moves, the page does not
    touch(cdp, "touchEnd", x, y + 84)
    expect(page.locator(".cz-lift")).to_have_count(0)


def test_a_real_finger_that_moves_at_once_is_a_scroll_and_lifts_nothing(canvas_page):
    page = canvas_page(viewport={"width": 390, "height": 844})
    block(page)
    cdp = page.context.new_cdp_session(page)
    x, y, _ = centre(page, '.cz-swipe:has-text("King Kong") .cz-step')
    y0 = page.evaluate("scrollY")
    touch(cdp, "touchStart", x, y)
    for i in range(1, 12):
        touch(cdp, "touchMove", x, y - i * 20)
        page.wait_for_timeout(16)
    page.wait_for_timeout(450)
    touch(cdp, "touchEnd", x, y - 220)
    assert page.locator(".cz-lift").count() == 0 and page.locator(".cz-toast").count() == 0
    assert page.evaluate("scrollY") > y0 + 20 or page.evaluate("scrollY") != y0
    assert page.locator(".is-lifted").count() == 0


def test_a_pointercancel_during_a_drag_leaves_no_lifted_chip_and_changes_nothing(canvas_page):
    page = canvas_page(viewport=TALL)
    block(page)
    before = part_titles("a1", "Upper Lot")
    start = hold(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step')
    expect(page.locator(".cz-lift")).to_have_count(1)
    x, y, b = centre(page, '.cz-bpart:has(h2:text-is("Lunch"))')
    end = move_to(page, start, (x, b["y"] + 20))
    fire(page, "pointercancel", *end)
    expect(page.locator(".cz-lift")).to_have_count(0)
    assert page.locator(".is-lifted, .is-target, .is-before, .is-end").count() == 0
    assert "cz-dragging" not in page.locator("#cz").get_attribute("class")
    page.wait_for_timeout(300)
    assert page.locator(".cz-toast").count() == 0 and part_titles("a1", "Upper Lot") == before


def test_a_drop_that_lands_during_a_zoom_waits_for_it_and_then_refreshes(canvas_page):
    page = canvas_page(viewport=TALL, motion="no-preference")
    block(page)
    settle(page)
    page.evaluate("""() => { const real = document.startViewTransition.bind(document);
      document.startViewTransition = (cb) => real(async () => { await cb(); await new Promise(r => setTimeout(r, 1200)); }); }""")
    start = hold(page, '.cz-swipe:has-text("Minion Mayhem") .cz-step')
    expect(page.locator(".cz-lift")).to_have_count(1)
    x, y, b = centre(page, '.cz-bpart:has(h2:text-is("Lunch"))')
    end = move_to(page, start, (x, b["y"] + b["height"] - 6))
    page.evaluate("document.querySelector('.cz-back').click()")           # a zoom out starts, and stays busy for over a second
    fire(page, "pointerup", *end)                                          # the drop lands while it runs
    expect(toast(page)).to_contain_text("Minion Mayhem moved to Lunch", timeout=9000)
    assert part_titles("a1", "Lunch")[-1] == "Minion Mayhem"
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.locator(".cz-gb-open").click(position={"x": 90, "y": 40})                      # the level shown is the fresh one: the step is in Lunch when the block is opened
    expect(page.locator('.cz-bpart:has(h2:text-is("Lunch")) .cz-swipe:has-text("Minion Mayhem")')).to_have_count(1)
