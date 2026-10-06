"""F-106: tap a plan, and its note and its chat open right there, as a card over the day. At 390 and 320 wide: a block shows one line of its note that fades (nothing cut mid-word
without a fade), a chat count, and a booking a plan overlaps is a pill beside it, never under it; a tap (not a hold) grows the block into a card with the whole note and the plan's chat;
an editor edits their own note in place or adds one; a message is sent from the docked box; "Earlier" brings older messages; tap outside, Escape or a swipe down fold it back; a viewer reads
the note and may talk; a park block's card has "Rides" for its block level; holds, drags, resizes and the hold menu are untouched. A finger is a pointer that goes down, waits and lets go
(synthetic pointer events, as in the F-097 tests), or Playwright's real touch tap. Screenshots on request: F106_SHOTS=<folder>."""
import os
import re
import uuid

import pytest
from playwright.sync_api import expect

from gitaway import plantalk, tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import PHONE
from tests_browser.test_day_grid import ari, box, checks, fire, hold_block, now, open_day, plan, show, slide
from tests_browser.test_trip_canvas import NARROW, canvas_page, model, settle  # noqa: F401 - fixtures

LONG = "H and B play. You can go on the big slide twice, then Moana lagoon after, and the long walk back to the car before the gates close tonight"
SUNDAY = 2


def shot(page, name):
    if os.environ.get("F106_SHOTS") and page.viewport_size["width"] == 390:
        page.screenshot(path=os.path.join(os.environ["F106_SHOTS"], name))


@pytest.fixture(params=[PHONE, NARROW], ids=["390", "320"])
def phone(request, canvas_page):
    return canvas_page(viewport=request.param)


def block(page, act):
    return page.locator(f'.cz-gb[data-act="{act}"]')


def tap(page, act):
    """A real touch tap on a block, away from its title (two quick taps on a title rename it)."""
    sel = f'.cz-gb[data-act="{act}"]'
    show(page, sel)
    b = box(page, sel)
    top = max(b["y"], 120)                                                                    # a tall block starts above the screen: tap where it can be seen
    page.touchscreen.tap(b["x"] + b["width"] * 0.72, top + min(34, (min(b["y"] + b["height"], 700) - top) / 2))


def say(act, n, part=""):
    for i in range(n):
        plantalk.post_message(ari(), act, part, f"message {i + 1}")


def card(page):
    return page.locator(".cz-card")


def long_day():
    """The captain's day, near enough: a long note over a block, one that is cut mid-line, a short block, and the 3 PM check-in line under the first."""
    lower = plan("Universal Studios – Lower Lot", 14 * 60 + 30, 16 * 60 + 30, day=0)
    cal.add_note(ari(), LONG, act=lower.id)
    upper = plan("Universal Studios – Upper Lot", 17 * 60, 18 * 60 + 25, day=0)
    cal.add_note(ari(), "H and B walk; King Kong; Fast and Furious ride", act=upper.id)
    water = plan("Waterworld", 18 * 60 + 45, 19 * 60 + 30, day=0)
    cal.add_note(ari(), "Wet seats, bring the poncho", act=water.id)
    return lower, upper, water


# ---- the grid ------------------------------------------------------------------------------------------------------------------

def test_a_block_shows_one_line_of_its_note_that_fades_and_nothing_else_is_cut(phone):
    lower, upper, water = long_day()
    open_day(phone, 0)
    show(phone, f'.cz-gb[data-act="{lower.id}"]')
    shot(phone, "grid-390.png")
    for a in (lower, upper, water):
        note = block(phone, a.id).locator(".cz-gb-note")
        got = note.evaluate("n => ({ one: n.clientHeight < parseFloat(getComputedStyle(n).lineHeight) * 1.6, mask: getComputedStyle(n).webkitMaskImage || getComputedStyle(n).maskImage, w: n.scrollWidth, c: n.clientWidth, font: getComputedStyle(n).fontFamily })")
        assert got["one"] and "linear-gradient" in got["mask"] and "Caveat" in got["font"]
        title = block(phone, a.id).locator(".cz-gb-t")
        assert title.evaluate("t => t.scrollHeight <= t.clientHeight + 1")             # the name is never the part that is cut
    long_note = block(phone, lower.id).locator(".cz-gb-note")
    assert long_note.evaluate("n => n.scrollWidth > n.clientWidth")                      # a long note runs past its line, and fades there
    assert block(phone, lower.id).locator(".cz-sticker").count() == 0
    checks(phone)


def test_a_booking_under_a_plan_is_a_pill_beside_it_never_under_it(phone):
    lower, upper, water = long_day()
    open_day(phone, 0)
    pill = phone.locator(".cz-gbk.is-pill")
    expect(pill).to_have_count(1)
    show(phone, ".cz-gbk.is-pill")
    p, b = box(phone, ".cz-gbk.is-pill"), box(phone, f'.cz-gb[data-act="{lower.id}"]')
    assert p["x"] + p["width"] <= b["x"] + 0.5 or b["x"] + b["width"] <= p["x"] + 0.5      # side by side: the boxes do not touch
    assert "3 PM" in pill.inner_text() and "Check in" in pill.inner_text()
    shot(phone, "pill-390.png")
    assert pill.evaluate("p => p.scrollWidth <= p.clientWidth + 1 && p.scrollHeight <= p.clientHeight + 1")
    pill.tap()
    expect(phone.locator(".cz-sheet")).to_be_visible()                                      # still the booking's own sheet (F-093)
    checks(phone)


def test_a_block_with_talk_shows_its_count_and_a_mic_for_a_voice_note(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    say(lunch.id, 3)
    open_day(phone)
    chip = block(phone, lunch.id).locator(".cz-gb-chat")
    expect(chip).to_contain_text("3")
    assert chip.locator("svg").count() == 1


# ---- the card --------------------------------------------------------------------------------------------------------------------

def test_a_tap_opens_a_card_over_the_block_with_the_whole_note_and_the_chat_and_the_day_dims(phone):
    lower, upper, water = long_day()
    say(lower.id, 3)
    open_day(phone, 0)
    tap(phone, lower.id)
    expect(card(phone)).to_be_visible()
    expect(card(phone).locator("#cz-card-title")).to_have_text("Universal Studios – Lower Lot")
    note = card(phone).locator(".cz-card-note").first
    expect(note).to_have_text(LONG)                                                       # the whole note, as typed
    assert note.evaluate("n => n.scrollHeight <= n.clientHeight + 1") and note.evaluate("n => getComputedStyle(n).fontFamily").find("Caveat") >= 0
    expect(card(phone).locator(".ft-bub").first).to_be_visible()
    assert phone.locator("#cz-card-earlier").count() == 0
    assert phone.evaluate("location.pathname + location.search") .startswith("/trip/canvas?day=0")      # nothing was navigated to
    assert phone.locator(".cz-card-scrim").evaluate("s => getComputedStyle(s).backgroundColor") != "rgba(0, 0, 0, 0)"
    inside = card(phone).evaluate("c => { const r = c.getBoundingClientRect(); return r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight; }")
    assert inside and phone.evaluate("CZ.cardOpen") is True
    shot(phone, "card-390.png")
    checks(phone)


def note_texts(act):
    return [n.text for n in cal.notes(ari()) if n.act == act]


def test_an_editor_edits_their_own_note_in_place_and_the_block_behind_shows_it(phone):
    lunch = plan("Lunch", 12 * 60, 14 * 60)
    mine = cal.add_note(ari(), "Tacos at the pier", act=lunch.id)
    open_day(phone)
    tap(phone, lunch.id)
    sticky = card(phone).locator(".cz-card-note.is-mine")
    sticky.tap()
    field = card(phone).locator(".cz-card-edit")
    expect(field).to_be_focused()
    assert field.input_value() == "Tacos at the pier"
    shot(phone, "note-edit-390.png")
    field.fill("Tacos at the pier, then ice cream")
    field.press("Enter")
    expect(card(phone).locator(".cz-card-note.is-mine .cz-card-text")).to_have_text("Tacos at the pier, then ice cream")
    assert note_texts(lunch.id) == ["Tacos at the pier, then ice cream"]
    expect(block(phone, lunch.id).locator(".cz-gb-note")).to_have_text("Tacos at the pier, then ice cream")      # the day behind it was brought up to date
    expect(card(phone)).to_be_visible()                                                                          # ... and the card was not taken away by it
    sticky.tap()
    card(phone).locator(".cz-card-edit").fill("never saved")
    card(phone).locator(".cz-card-edit").press("Escape")
    expect(card(phone).locator(".cz-card-edit")).to_have_count(0)
    expect(card(phone)).to_be_visible()                                                                          # Escape ends the edit first, then the card
    assert note_texts(lunch.id) == ["Tacos at the pier, then ice cream"]
    sticky.tap()
    card(phone).locator(".cz-card-edit").fill("   ")
    card(phone).locator(".cz-card-edit").press("Enter")
    assert note_texts(lunch.id) == ["Tacos at the pier, then ice cream"]                                         # an empty note changes nothing


def test_an_empty_plan_has_an_add_a_note_sticky_and_the_note_is_saved_as_theirs(phone):
    lunch = plan("Lunch", 12 * 60, 14 * 60)
    open_day(phone)
    assert block(phone, lunch.id).locator(".cz-gb-note").count() == 0
    tap(phone, lunch.id)
    add = card(phone).locator(".cz-card-add.is-empty")
    expect(add).to_have_text("Add a note")
    add.tap()
    card(phone).locator(".cz-card-edit").fill("Bring sunscreen")
    card(phone).locator(".cz-card-edit").press("Enter")
    expect(card(phone).locator(".cz-card-note.is-mine .cz-card-text")).to_have_text("Bring sunscreen")
    expect(card(phone).locator(".cz-card-add")).to_have_count(1)                                                 # a quiet "Add a note" follows it
    assert note_texts(lunch.id) == ["Bring sunscreen"]
    expect(block(phone, lunch.id).locator(".cz-gb-note")).to_have_text("Bring sunscreen")
    card(phone).locator(".cz-card-add").tap()
    card(phone).locator(".cz-card-edit").fill("And a hat")
    card(phone).locator(".cz-card-edit").press("Enter")
    expect(card(phone).locator(".cz-card-note .cz-card-text")).to_have_count(2)
    assert note_texts(lunch.id) == ["Bring sunscreen", "And a hat"]


def test_a_message_is_sent_from_the_docked_box_and_the_block_counts_it(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    tap(phone, lunch.id)
    box_ = card(phone).locator("#ft-text")
    expect(box_).to_be_visible()
    c, f = card(phone).bounding_box(), card(phone).locator("#ft-compose").bounding_box()
    assert f["y"] + f["height"] <= c["y"] + c["height"] + 1 and f["y"] > c["y"] + c["height"] * 0.6          # the box is docked at the bottom of the card
    box_.fill("Mario Kart after lunch")
    box_.press("Enter")
    expect(card(phone).locator(".ft-bub", has_text="Mario Kart after lunch")).to_be_visible()
    phone.wait_for_function("() => !document.querySelector('.cz-card .is-pending')")
    assert [i["text"] for i in plantalk.items(ari(), lunch.id)] == ["Mario Kart after lunch"]
    expect(card(phone).locator("#pt-photo-btn")).to_be_visible()
    expect(card(phone).locator("#pt-mic")).to_be_visible()                                                   # the chat's own scripts were bound in the card
    shot(phone, "chat-sent-390.png")


def test_earlier_brings_older_messages_above_without_moving_what_is_read(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    say(lunch.id, 20)
    open_day(phone)
    tap(phone, lunch.id)
    expect(card(phone).locator(".ft-msg")).to_have_count(8)
    expect(card(phone).locator(".ft-msg").last).to_contain_text("message 20")
    scroller = card(phone).locator(".cz-card-scroll")
    assert scroller.evaluate("s => s.scrollHeight - s.scrollTop - s.clientHeight < 4")                       # it opens at the newest
    scroller.evaluate("s => { s.scrollTop = 0; }")
    card(phone).locator("#cz-card-earlier").tap()
    expect(card(phone).locator(".ft-msg")).to_have_count(16)
    expect(card(phone).locator(".ft-msg").first).to_contain_text("message 5")
    scroller.evaluate("s => { s.scrollTop = 0; }")
    card(phone).locator("#cz-card-earlier").tap()
    expect(card(phone).locator(".ft-msg")).to_have_count(20)
    expect(card(phone).locator("#cz-card-earlier")).to_have_count(0)                                         # no more: the button goes


# ---- folding ---------------------------------------------------------------------------------------------------------------------

def test_tap_outside_escape_the_close_button_and_a_swipe_down_all_fold_the_card_back(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    for how in ("scrim", "escape", "close", "swipe"):
        tap(phone, lunch.id)
        expect(card(phone)).to_be_visible()
        if how == "scrim":
            c = card(phone).bounding_box()
            phone.touchscreen.tap(c["x"] / 2, c["y"] + c["height"] / 2)                               # the dimmed day beside the card (above it on a taller screen)
        elif how == "escape":
            phone.keyboard.press("Escape")
        elif how == "close":
            card(phone).locator(".cz-card-x").tap()
        else:
            h = card(phone).locator(".cz-card-head").bounding_box()
            x, y = h["x"] + 120, h["y"] + 20
            fire(phone, "pointerdown", x, y)
            slide(phone, (x, y), (x, y + 160), steps=8, wait=12)
            fire(phone, "pointerup", x, y + 160)
        expect(card(phone)).to_have_count(0)
        assert phone.evaluate("CZ.cardOpen") is False and phone.locator("#cz").get_attribute("inert") is None
        assert phone.evaluate("location.search") == "?day=2"
        assert phone.evaluate("document.activeElement.closest('.cz-gb') && document.activeElement.closest('.cz-gb').dataset.act") == lunch.id      # the block has the focus back


def test_a_short_pull_on_the_card_springs_back_and_does_not_fold(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    tap(phone, lunch.id)
    h = card(phone).locator(".cz-card-head").bounding_box()
    x, y = h["x"] + 120, h["y"] + 20
    fire(phone, "pointerdown", x, y)
    slide(phone, (x, y), (x, y + 40), steps=4, wait=12)
    fire(phone, "pointerup", x, y + 40)
    phone.wait_for_timeout(400)
    expect(card(phone)).to_be_visible()


def test_a_voice_note_being_recorded_is_not_thrown_away_by_a_stray_tap(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    tap(phone, lunch.id)
    expect(card(phone).locator("#pt-rec")).to_be_attached()
    phone.evaluate("() => { document.querySelector('.cz-card #pt-rec').hidden = false; }")                    # the bar a recording shows
    c = card(phone).bounding_box()
    phone.touchscreen.tap(c["x"] / 2, c["y"] + c["height"] / 2)
    phone.keyboard.press("Escape")
    phone.wait_for_timeout(300)
    expect(card(phone)).to_be_visible()


# ---- who, and what stays as it was ------------------------------------------------------------------------------------------------

def test_a_viewer_reads_the_note_and_may_talk_but_cannot_edit_it(canvas_page, browser, base_url):
    owner = canvas_page(viewport=PHONE)
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    cal.add_note(ari(), "Bring towels", act=lunch.id)
    mail = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
    try:
        ctx.set_default_timeout(9000)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day={SUNDAY}")
        page.wait_for_selector("#cz-grid")
        expect(block(page, lunch.id).locator(".cz-gb-note")).to_have_text("Bring towels")
        tap(page, lunch.id)
        expect(card(page)).to_be_visible()
        expect(card(page).locator(".cz-card-note .cz-card-text")).to_have_text("Bring towels")
        expect(card(page).locator(".cz-card-by")).to_have_text("Ari Rivera")                                  # whose note it is
        card(page).locator(".cz-card-note").tap()
        assert card(page).locator(".cz-card-edit").count() == 0 and card(page).locator(".cz-card-add").count() == 0
        card(page).locator("#ft-text").fill("See you there")
        card(page).locator("#ft-text").press("Enter")
        expect(card(page).locator(".ft-bub", has_text="See you there")).to_be_visible()
        page.wait_for_function("() => !document.querySelector('.cz-card .is-pending')")
        assert [i["text"] for i in plantalk.items(ari(), lunch.id)] == ["See you there"]
        assert note_texts(lunch.id) == ["Bring towels"]
    finally:
        ctx.close()


def test_a_park_block_card_has_rides_which_zooms_to_its_block_level(phone):
    open_day(phone, 1)
    tap(phone, cal.activities(ari())[0].id)
    expect(card(phone)).to_be_visible()
    assert phone.locator(".cz-view[data-level=day]").count() == 1                                              # a tap on a park block no longer leaves the day
    card(phone).locator("#cz-card-rides").tap()
    expect(phone.locator(".cz-view[data-level=block]")).to_be_visible()
    expect(card(phone)).to_have_count(0)
    assert "block=" in phone.evaluate("location.search")
    phone.go_back()
    expect(phone.locator(".cz-view[data-level=day]")).to_be_visible()


def test_a_plain_plan_tap_stays_on_the_day_and_open_chat_is_in_the_card(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    tap(phone, lunch.id)
    expect(card(phone)).to_be_visible()
    assert phone.evaluate("location.pathname") == "/trip/canvas"
    assert card(phone).locator("#cz-card-rides").count() == 0
    card(phone).locator("#cz-card-chat").tap()
    phone.wait_for_url(re.compile(r"/trip/talk\?act="))


def ppm_step(page):
    from tests_browser.test_day_grid import ppm
    return ppm(page) * 15


def test_a_hold_still_lifts_and_a_hold_without_moving_still_opens_the_menu_not_the_card(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    start = hold_block(phone, lunch.id)
    expect(block(phone, lunch.id)).to_have_class(re.compile("is-held"))
    fire(phone, "pointerup", *start)
    expect(phone.locator(".cz-menu")).to_be_visible()
    assert card(phone).count() == 0
    phone.keyboard.press("Escape")
    start = hold_block(phone, lunch.id)
    end = slide(phone, start, (start[0], start[1] + ppm_step(phone) * 2))
    fire(phone, "pointerup", *end)
    expect(phone.locator(".cz-toast")).to_contain_text("Lunch moved to 12:30 PM")
    assert card(phone).count() == 0 and now(lunch.id)[0] == 12 * 60 + 30


def test_a_double_tap_on_a_title_still_renames_it_and_opens_no_card(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    show(phone, f'.cz-gb[data-act="{lunch.id}"]')
    t = phone.locator(f'.cz-gb[data-act="{lunch.id}"] .cz-gb-t').bounding_box()
    for _ in range(2):
        phone.touchscreen.tap(t["x"] + 10, t["y"] + t["height"] / 2)
        phone.wait_for_timeout(60)
    expect(phone.locator(".cz-gb-edit")).to_be_visible()
    assert card(phone).count() == 0


# ---- motion and the keyboard --------------------------------------------------------------------------------------------------------

def test_the_card_grows_with_a_spring_and_reduced_motion_has_none(browser, base_url, model):
    for motion, grows in (("no-preference", True), ("reduce", False)):
        ctx = browser.new_context(viewport=PHONE, reduced_motion=motion, has_touch=True, is_mobile=True)
        try:
            ctx.set_default_timeout(9000)
            ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
            ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
            lunch = plan("Lunch", 12 * 60, 13 * 60)
            page = ctx.new_page()
            page.goto(f"{base_url}/trip/canvas?day={SUNDAY}")
            page.wait_for_selector("#cz-grid")
            tap(page, lunch.id)
            expect(card(page)).to_be_visible()
            running = page.evaluate("() => document.querySelector('.cz-card').getAnimations().map(a => a.effect.getKeyframes()[0].transform || '')")
            assert (len(running) > 0) is grows
            if grows:
                assert "scale(" in running[0]                          # it starts as the block's own size and place
            page.wait_for_timeout(500)
            page.keyboard.press("Escape")
            expect(card(page)).to_have_count(0)
        finally:
            ctx.close()


def test_with_the_keyboard_up_the_card_stays_inside_what_is_left_and_the_box_stays_in_view(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    say(lunch.id, 6)
    open_day(phone)
    tap(phone, lunch.id)
    expect(card(phone)).to_be_visible()
    card(phone).locator("#ft-text").tap()
    phone.set_viewport_size({"width": phone.viewport_size["width"], "height": 380})            # what the keyboard leaves
    phone.wait_for_timeout(200)
    c = card(phone).bounding_box()
    f = card(phone).locator("#ft-compose").bounding_box()
    assert c["y"] >= 0 and c["y"] + c["height"] <= 380 + 1 and f["y"] + f["height"] <= 380 + 1 and f["y"] >= c["y"]
    expect(card(phone).locator(".ft-msg").last).to_be_visible()


# ---- review fixes ------------------------------------------------------------------------------------------------------------------

def test_a_pills_words_are_never_cut_the_short_name_wraps_below_the_time(phone):
    long_day()
    open_day(phone, 0)
    show(phone, ".cz-gbk.is-pill")
    got = phone.locator(".cz-gbk.is-pill").evaluate("""p => { const t = p.querySelector('.cz-bk-t'), r = p.querySelector('.cz-bk-row');
      return { w: t.scrollWidth <= t.clientWidth + 0.5, h: p.scrollHeight <= p.clientHeight + 1, pw: p.scrollWidth <= p.clientWidth + 1, below: t.getBoundingClientRect().top >= r.getBoundingClientRect().bottom - 1, text: t.textContent }; }""")
    assert got == {"w": True, "h": True, "pw": True, "below": True, "text": "Check in"}
    assert phone.locator(".cz-bk-t").evaluate_all("els => els.every(t => t.scrollWidth <= t.clientWidth + 0.5)")
    shot(phone, "pill2-390.png")


def test_plans_sharing_lanes_keep_one_left_edge_when_one_of_them_is_over_a_booking(phone):
    a = plan("Long afternoon", 13 * 60, 16 * 60 + 30, day=0)
    b = plan("Late swim", 16 * 60 + 5, 17 * 60 + 30, day=0)
    open_day(phone, 0)
    show(phone, f'.cz-gb[data-act="{b.id}"]')
    ba, bb = box(phone, f'.cz-gb[data-act="{a.id}"]'), box(phone, f'.cz-gb[data-act="{b.id}"]')
    pill = box(phone, ".cz-gbk.is-pill")
    assert ba["x"] + ba["width"] <= bb["x"] + 0.5 or bb["x"] + bb["width"] <= ba["x"] + 0.5       # side by side, not on top of each other
    assert min(ba["x"], bb["x"]) >= pill["x"] + pill["width"] - 0.5                                 # both clear of the pill's lane
    shot(phone, "lanes-390.png")


def test_opening_and_folding_the_card_twenty_times_leaves_no_listeners_or_timers_behind(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    for i in range(20):
        tap(phone, lunch.id)
        expect(card(phone).locator("#ft-text")).to_be_visible()
        if i == 0:
            assert phone.evaluate("window.__ftBound") == {"thread": 1, "plantalk": 1}
        phone.keyboard.press("Escape")
        expect(card(phone)).to_have_count(0)
    assert phone.evaluate("window.__ftBound") == {"thread": 0, "plantalk": 0}


def test_a_strip_of_the_day_stays_above_the_card_to_tap_on_even_on_a_small_phone(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    tap(phone, lunch.id)
    expect(card(phone)).to_be_visible()
    phone.wait_for_timeout(450)
    c = card(phone).bounding_box()
    assert c["y"] >= 60
    phone.touchscreen.tap(c["x"] + c["width"] / 2, c["y"] / 2)
    expect(card(phone)).to_have_count(0)


def test_the_keyboard_stays_in_the_card_while_it_is_open_and_the_rest_of_the_page_is_inert(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    tap(phone, lunch.id)
    expect(card(phone).locator("#ft-text")).to_be_visible()
    inert = phone.evaluate("() => [...document.querySelectorAll('[inert]')].map(n => n.id || n.className)")
    assert any("ph-tabs" in x for x in inert) and "cz" in inert                                      # the tab bar and the day
    for _ in range(25):
        phone.keyboard.press("Tab")
        assert phone.evaluate("!!document.activeElement.closest('.cz-card')")
    for _ in range(25):
        phone.keyboard.press("Shift+Tab")
        assert phone.evaluate("!!document.activeElement.closest('.cz-card')")
    phone.keyboard.press("Escape")
    expect(card(phone)).to_have_count(0)
    assert phone.evaluate("document.querySelectorAll('[inert]').length") == 0


def test_a_card_does_not_fold_while_its_note_is_being_saved_and_a_failed_save_says_so_in_the_card(phone):
    lunch = plan("Lunch", 12 * 60, 14 * 60)
    open_day(phone)
    tap(phone, lunch.id)
    card(phone).locator(".cz-card-add").tap()
    field = card(phone).locator(".cz-card-edit")
    field.fill("Bring sunscreen")
    seen = []

    def slow(route):
        seen.append(1)
        phone.wait_for_timeout(700)
        route.continue_()
    phone.route("**/trip/canvas/actnote", slow)
    field.press("Enter")
    c = card(phone).bounding_box()
    phone.touchscreen.tap(c["x"] + c["width"] / 2, c["y"] / 2)                                       # tap outside while it is on its way
    phone.keyboard.press("Escape")
    phone.wait_for_timeout(200)
    expect(card(phone)).to_be_visible()
    expect(card(phone).locator(".cz-card-note .cz-card-text")).to_have_text("Bring sunscreen", timeout=6000)
    assert note_texts(lunch.id) == ["Bring sunscreen"] and len(seen) == 1
    phone.unroute("**/trip/canvas/actnote")
    phone.route("**/trip/canvas/actnote", lambda route: route.fulfill(status=500, body="no"))
    card(phone).locator(".cz-card-add").tap()
    card(phone).locator(".cz-card-edit").fill("A second one")
    c = card(phone).bounding_box()
    phone.touchscreen.tap(c["x"] + c["width"] / 2, c["y"] / 2)                                       # tapping away tries to save it, fails, and stays
    expect(card(phone).locator(".cz-card-err")).to_have_text(re.compile("could not save", re.I))
    expect(card(phone)).to_be_visible()
    assert card(phone).locator(".cz-card-edit").input_value() == "A second one" and note_texts(lunch.id) == ["Bring sunscreen"]


def test_a_message_sent_in_the_card_is_there_when_it_is_opened_again_at_once(phone):
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(phone)
    tap(phone, lunch.id)
    card(phone).locator("#ft-text").fill("Mario Kart after lunch")
    card(phone).locator("#ft-text").press("Enter")
    phone.wait_for_function("() => !document.querySelector('.cz-card .is-pending') && document.querySelector('.cz-card .ft-bub')")
    phone.keyboard.press("Escape")
    expect(card(phone)).to_have_count(0)
    tap(phone, lunch.id)
    expect(card(phone).locator(".ft-bub", has_text="Mario Kart after lunch")).to_have_count(1)
