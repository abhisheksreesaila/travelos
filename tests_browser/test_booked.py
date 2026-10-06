"""F-093: bookings open in place; filters; Help leaves the tab bar, in a real browser at 390 and 320. Every booking line on the day and in the week opens its sheet over the
day (hotel check in and out, flight, car pick up and drop off) and closes again; a hotel phone number is fixed and a pass added from the sheet and the page comes back to it; the
pass opens full screen in the existing gate view; each filter is pressed on the week and the day, remembered, and still works with storage blocked; SOS opens the emergency
sheet with its call links; the tab bar is Today, Map, Ask, Family with Ask in the middle; a viewer reads everything and sees no edit buttons; no sideways scroll, 44px targets, 13px text.
The trip is the template import (Fri Oct 16 to Tue Oct 20 in Los Angeles) and, for chats, the captain's Universal + California Adventure messages through a canned model answer."""
import os
import re

import pytest
from playwright.sync_api import expect
from starlette.testclient import TestClient

from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT
from tests_browser.test_plan_talk import lunch_chat  # noqa: F401
from tests_browser.test_trip_canvas import NARROW, canvas_page, model  # noqa: F401 - fixtures

EDITOR = "ari.rivera@example.com"


def checks(page):
    assert page.evaluate(OVERFLOW) <= 0
    assert page.evaluate(SMALL_TEXT) == []
    assert page.evaluate(SMALL_CONTROLS) == []


@pytest.fixture
def imported_page(browser, base_url):
    """imported_page(who=EDITOR, viewport=PHONE) -> a signed-in page on the template trip's week."""
    contexts = []

    def make(who=EDITOR, viewport=PHONE, storage=True):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=True, is_mobile=True)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": who, "next": "/", "intent": "save"}, max_redirects=0)
        if who == EDITOR:
            ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)
        page = ctx.new_page()
        if not storage:
            page.add_init_script("Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } });")
        page.goto(f"{base_url}/trip/canvas")
        page.wait_for_selector(".cz-view[data-level=week]")
        return page

    yield make
    for c in contexts:
        c.close()


def day(page, base_url, n):
    page.goto(f"{base_url}/trip/canvas?day={n}")
    page.wait_for_selector(f".cz-view[data-level=day][data-day='{n}']")


def sheet_open(page, bid):
    page.wait_for_selector(".cz-sheet-bk")
    expect(page.locator(".cz-sheet-bk")).to_have_attribute("data-booked", bid)
    assert f"booked={bid}" in page.url


def close_sheet(page, how="button"):
    if how == "button":
        page.locator(".cz-sheet .cz-close").click()
    elif how == "scrim":
        page.mouse.click(195, 60)
    else:
        page.keyboard.press("Escape")
    expect(page.locator(".cz-sheet")).to_have_count(0)


# ---- the booking sheets ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_each_booking_line_opens_its_sheet_in_place_and_closes_again(imported_page, base_url, viewport):
    page = imported_page(viewport=viewport)
    day(page, base_url, 0)
    lines = page.locator("a.cz-bk")
    assert lines.count() == 3
    # the flight
    page.locator("a.cz-bk", has_text="Alaska").click()
    sheet_open(page, "b-out")
    sheet = page.locator(".cz-sheet-bk")
    expect(sheet).to_contain_text("SFO → LAX")
    expect(sheet).to_contain_text("Alaska Airlines AS 1234")
    expect(sheet).to_contain_text("Passes & documents")
    expect(page.locator(".cz-view")).to_have_attribute("data-day", "0")          # still the day behind it
    checks(page)
    close_sheet(page)
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    assert page.url.endswith("day=0") or "booked=" not in page.url
    # the hotel
    page.locator("a.cz-bk", has_text="Check in").click()
    sheet_open(page, "b-in")
    expect(sheet).to_contain_text("The Example Hotel Santa Monica")
    expect(sheet).to_contain_text("123 Ocean Ave, Santa Monica, CA 90401")
    expect(sheet).to_contain_text("3:00 PM")
    expect(sheet).to_contain_text("11:00 AM")
    assert sheet.locator("a[href='tel:+13105550100']").count() == 1
    assert "maps" in sheet.locator("#hp-directions").get_attribute("href")
    number = sheet.locator(".tp-conf-num")
    expect(number).to_be_hidden()                                              # behind a tap
    sheet.locator(".hp-conf-sum").click()
    expect(number).to_have_text("987654321")
    checks(page)
    close_sheet(page, "key")
    # the car
    page.locator("a.cz-bk", has_text="Hertz").click()
    sheet_open(page, "b-car-pick")
    expect(sheet).to_contain_text("Hertz")
    expect(sheet).to_contain_text("Counter")
    assert sheet.locator("a[href='tel:+13105550199']").count() == 1
    assert "maps" in sheet.locator("#hp-car-directions").get_attribute("href")
    checks(page)
    close_sheet(page, "scrim" if viewport == PHONE else "button")


def test_the_return_day_has_the_check_out_and_the_drop_off_sheets(imported_page, base_url):
    page = imported_page()
    day(page, base_url, 4)
    page.locator("a.cz-bk", has_text="Check out").click()
    sheet_open(page, "b-out2")
    expect(page.locator(".cz-sheet-bk")).to_contain_text("The Example Hotel Santa Monica")
    close_sheet(page)
    page.locator("a.cz-bk", has_text="Drop off").click()
    sheet_open(page, "b-car-drop")
    expect(page.locator(".cz-sheet-bk")).to_contain_text("Drop off")
    close_sheet(page)
    page.locator("a.cz-bk", has_text="AS 1235").click()
    sheet_open(page, "b-back")
    close_sheet(page)


def test_a_booking_sheet_opened_by_address_works_without_script(browser, base_url):
    ctx = browser.new_context(viewport=PHONE, java_script_enabled=False)
    ctx.request.post(f"{base_url}/signin", form={"email": EDITOR, "next": "/", "intent": "save"}, max_redirects=0)
    ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/canvas?day=0&booked=b-in")
    expect(page.locator(".cz-sheet-bk")).to_contain_text("The Example Hotel Santa Monica")
    page.locator(".cz-sheet .cz-close").click()
    expect(page.locator(".cz-sheet")).to_have_count(0)
    page.locator("a.cz-bk", has_text="Check in").click()
    expect(page.locator(".cz-sheet-bk")).to_have_attribute("data-booked", "b-in")
    ctx.close()


def test_an_editor_fixes_the_hotel_phone_in_the_sheet_and_lands_back_in_it(imported_page, base_url):
    page = imported_page()
    day(page, base_url, 0)
    page.locator("a.cz-bk", has_text="Check in").click()
    sheet_open(page, "b-in")
    page.locator(".cz-sheet-bk .hp-fix-sum").click()
    page.locator(".cz-sheet-bk input[name=phone]").fill("+1 310 555 0142")
    page.locator(".cz-sheet-bk .hp-fix-form button[type=submit]").click()
    page.wait_for_selector(".cz-sheet-bk a[href='tel:+13105550142']")
    assert "booked=b-in" in page.url
    page.locator(".cz-sheet-bk .hp-fix-sum").click()
    page.locator(".cz-sheet-bk .hp-fix-form a", has_text="Cancel").click()           # Cancel goes back to the sheet, not to Help
    expect(page.locator(".cz-sheet-bk")).to_be_visible()
    page.locator(".cz-sheet-bk .hp-fix-sum").click()
    page.locator(".cz-sheet-bk input[name=phone]").fill("+1 310 555 0100")
    page.locator(".cz-sheet-bk .hp-fix-form button[type=submit]").click()
    page.wait_for_selector(".cz-sheet-bk a[href='tel:+13105550100']")


def test_a_pass_is_added_in_the_flight_sheet_and_opens_full_screen(imported_page, base_url):
    page = imported_page()
    day(page, base_url, 0)
    page.locator("a.cz-bk", has_text="Alaska").click()
    sheet_open(page, "b-out")
    page.locator(".cz-sheet-bk .hp-fix-sum", has_text="Add a pass").click()
    form = page.locator(".cz-sheet-bk form[data-form=pass]")
    form.locator("input[name=traveller]").fill("Abhi")
    form.locator("input[name=seat]").fill("21A")
    form.locator("input[name=grp]").fill("3")
    form.locator("input[name=gate]").fill("71B")
    form.locator("button[type=submit]").click()
    page.wait_for_selector(".cz-sheet-bk .pz-pass")
    assert "booked=b-out" in page.url
    card = page.locator(".cz-sheet-bk .pz-pass")
    expect(card).to_contain_text("Abhi")
    expect(card).to_contain_text("21A")
    expect(card).to_contain_text("71B")
    page.locator("#bk-show-passes").click()                                             # the existing full-screen gate view
    page.wait_for_selector("#gp")
    expect(page.locator(".gp-slide").first).to_contain_text("Abhi")
    page.locator("#gp-close").click()
    page.wait_for_url(re.compile(r"/trip/canvas\?day="))                                 # the gate's close goes to Today, which is the day
    page.goto(f"{base_url}/trip/canvas?day=0&booked=b-out")
    page.locator(".cz-sheet-bk .hp-fix-sum", has_text="Fix this pass").click()           # an editor fixes it there too
    page.locator(".cz-sheet-bk .pz-pass input[name=seat]").fill("22C")
    page.locator(".cz-sheet-bk .pz-pass form[data-form=pass] button[type=submit]").click()
    page.wait_for_selector(".cz-sheet-bk .pz-pass:has-text('22C')")
    page.locator(".cz-sheet-bk .pz-remove-sum").click()                                  # and removes it, two taps
    page.locator(".cz-sheet-bk .pz-remove-yes").click()
    page.wait_for_selector(".cz-sheet-bk [data-none=passes]")


# ---- the week -----------------------------------------------------------------------------------------------------------------

def test_a_booking_in_the_week_opens_the_same_sheet_on_that_day(imported_page, base_url):
    page = imported_page()
    page.locator("a.cz-wcard.is-booked", has_text="Check out").click()
    sheet_open(page, "b-out2")
    expect(page.locator(".cz-view")).to_have_attribute("data-day", "4")
    expect(page.locator(".cz-sheet-bk")).to_contain_text("The Example Hotel Santa Monica")
    close_sheet(page)
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    assert page.locator(".cz-view").get_attribute("data-day") == "4"


def test_the_week_row_link_still_opens_the_day(imported_page):
    page = imported_page()
    page.locator(".cz-row[data-day='2'] .cz-row-link").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.locator("#cz-z-week").click()
    page.locator(".cz-row[data-day='0'] .cz-row-link").click()                        # a row of only bookings has its Open the day link
    expect(page.locator(".cz-view[data-level=day][data-day='0']")).to_be_visible()


# ---- the kind filter ----------------------------------------------------------------------------------------------------------

def visible_titles(page, scope):
    return page.locator(f"{scope} [data-kind]:not(.is-off)").evaluate_all("els => els.filter(e => e.offsetParent !== null).map(e => e.dataset.kind)")


def test_the_week_filter_shows_only_what_matches_and_collapses_the_rest(imported_page):
    page = imported_page()
    row = page.locator(".cz-kinds")
    expect(row).to_be_visible()
    assert [c.inner_text() for c in row.locator("button").all()] == ["All", "Plans", "Hotels", "Flights", "Car", "Chats"]
    expect(row.locator("[aria-pressed=true]")).to_have_text("All")
    checks(page)
    page.locator(".cz-kchip", has_text="Hotels").click()
    expect(row.locator("[aria-pressed=true]")).to_have_text("Hotels")
    assert set(visible_titles(page, ".cz-week")) == {"hotel"}
    assert page.locator(".cz-row.is-thin").count() == 3                              # the days with no hotel booking are thin lines
    thin = page.locator(".cz-row.is-thin").first
    expect(thin.locator(".cz-thin-t")).to_have_text("Nothing for hotels")
    assert thin.bounding_box()["height"] < 90
    page.locator(".cz-kchip", has_text="Flights").click()
    assert set(visible_titles(page, ".cz-week")) == {"flight"}
    page.locator(".cz-kchip", has_text="Car").click()
    assert set(visible_titles(page, ".cz-week")) == {"car"}
    page.locator(".cz-kchip", has_text="Plans").click()
    assert visible_titles(page, ".cz-week") == [] and page.locator(".cz-row.is-thin").count() == 5
    page.locator(".cz-kchip", has_text="Chats").click()
    assert visible_titles(page, ".cz-week") == []
    checks(page)
    page.locator(".cz-kchip", has_text="All").click()
    assert page.locator(".cz-row.is-thin").count() == 0
    assert set(visible_titles(page, ".cz-week")) == {"hotel", "flight", "car"}


def test_the_choice_is_remembered_per_person_and_works_with_storage_blocked(imported_page, base_url):
    page = imported_page()
    page.locator(".cz-kchip", has_text="Flights").click()
    page.reload()
    page.wait_for_selector(".cz-kinds [aria-pressed=true]")
    expect(page.locator(".cz-kinds [aria-pressed=true]")).to_have_text("Flights")
    day(page, base_url, 0)                                                            # the same choice follows to the day
    expect(page.locator(".cz-kinds [aria-pressed=true]")).to_have_text("Flights")
    assert visible_titles(page, ".cz-day-body") == ["flight"]
    page.locator(".cz-kchip", has_text="All").click()
    page.reload()
    expect(page.locator(".cz-kinds [aria-pressed=true]")).to_have_text("All")
    blocked = imported_page(storage=False)
    blocked.locator(".cz-kchip", has_text="Car").click()
    assert set(visible_titles(blocked, ".cz-week")) == {"car"}
    blocked.locator(".cz-row[data-day='0'] .cz-wcard.is-booked:not(.is-off)").first.click()          # and the page carries on
    blocked.wait_for_selector(".cz-sheet-bk")


def test_the_day_filter_hides_what_does_not_match_and_keeps_the_sheet_working(imported_page, base_url):
    page = imported_page()
    day(page, base_url, 0)
    expect(page.locator(".cz-kinds")).to_be_visible()
    for word, kind in (("Hotels", "hotel"), ("Flights", "flight"), ("Car", "car")):
        page.locator(".cz-kchip", has_text=word).click()
        assert visible_titles(page, ".cz-day-body") == [kind], word
    page.locator(".cz-kchip", has_text="Plans").click()
    assert visible_titles(page, ".cz-day-body") == []
    expect(page.locator(".cz-kind-none")).to_be_visible()
    page.locator(".cz-kchip", has_text="Hotels").click()
    page.locator("a.cz-bk:not(.is-off)").click()
    sheet_open(page, "b-in")
    close_sheet(page)
    expect(page.locator(".cz-kinds [aria-pressed=true]")).to_have_text("Hotels")


@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_chats_shows_the_plans_and_parts_with_messages_and_the_step_filters_stay(canvas_page, base_url, viewport):
    page = canvas_page(**({"viewport": viewport} if viewport != PHONE else {}))
    lunch_chat(page, base_url)
    page.locator("#ft-text").fill("Mario Kart right after lunch")
    page.locator("#ft-send").click()
    expect(page.locator("#ft-thread .ft-me")).to_contain_text("Mario Kart")
    day(page, base_url, 1)
    kinds = page.locator(".cz-kinds")
    filters = page.locator(".cz-filters")
    assert kinds.bounding_box()["y"] < filters.bounding_box()["y"]                          # the new row comes first, both are compact
    assert filters.bounding_box()["height"] < 120
    page.locator(".cz-kchip", has_text="Chats").click()
    expect(page.locator(".cz-gb")).to_be_visible()                                            # F-097: the block with a message on one of its parts
    assert page.locator(".cz-gb:visible").count() == 1 and page.locator(".cz-gb .cz-gb-chat").count() == 1
    checks(page)
    page.locator(".cz-fchip", has_text="Everyone").click()                                    # the who and list filters still work
    page.locator(".cz-kchip", has_text="Plans").click()
    assert page.locator(".cz-gb:visible").count() == 1
    day(page, base_url, 3)                                                                    # California Adventure: nothing said yet
    expect(page.locator(".cz-kinds [aria-pressed=true]")).to_have_text("Plans")
    page.locator(".cz-kchip", has_text="Chats").click()
    expect(page.locator(".cz-gb")).to_be_hidden()
    expect(page.locator(".cz-kind-none")).to_be_visible()
    page.goto(f"{base_url}/trip/canvas")
    page.wait_for_selector(".cz-week")
    assert page.locator(".cz-row.is-thin").count() >= 4                                       # the week: only Saturday has a chat


# ---- SOS, the tab bar, Help ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_sos_opens_the_emergency_sheet_with_every_call_link(imported_page, base_url, viewport, monkeypatch):
    monkeypatch.setenv("GITAWAY_VAPID_PUBLIC", "BPublicKey"), monkeypatch.setenv("GITAWAY_VAPID_PRIVATE", "p"), monkeypatch.setenv("GITAWAY_VAPID_SUBJECT", "mailto:a@b.co")
    page = imported_page(viewport=viewport)
    sos = page.locator("#cz-sos")
    expect(sos).to_be_visible()
    checks(page)
    sos.click()
    page.wait_for_selector(".cz-sheet-sos")
    sheet = page.locator(".cz-sheet-sos")
    assert sheet.locator("a[href='tel:911']").count() == 1
    assert sheet.locator("#sos-hotel a[href='tel:+13105550100']").count() == 1
    expect(sheet.locator("#sos-hotel")).to_contain_text("The Example Hotel Santa Monica")
    assert sheet.locator("#sos-car a[href='tel:+13105550199']").count() == 1
    expect(sheet.locator("#sos-nocontacts")).to_be_visible()                       # nobody has a number yet
    checks(page)
    page.locator("#sos-add-mine").click()                                           # Add your number: the family page
    page.wait_for_url(re.compile(r"/family"))
    page.go_back()
    page.wait_for_selector(".cz-view")
    page.goto(f"{base_url}/trip/canvas?day=2")
    page.locator("#cz-sos").click()
    page.wait_for_selector(".cz-sheet-sos")
    page.locator(".cz-sheet .cz-close").click()
    expect(page.locator(".cz-sheet")).to_have_count(0)
    expect(page.locator(".cz-view")).to_have_attribute("data-day", "2")
    page.locator("#cz-sos").click()
    page.locator("#sos-phone").click()                                              # "This phone": two taps from the day to the morning plan and Face ID
    page.wait_for_url(re.compile(r"/family#morning-plan"))
    expect(page.locator("#morning-plan #tp-morning")).to_be_visible()


def test_sos_opens_with_no_connection_and_closes_three_ways(imported_page, base_url):
    page = imported_page()
    day(page, base_url, 1)
    page.context.set_offline(True)                                                  # Help's emergency card promised to open offline: SOS does too
    url = page.url
    for how in ("button", "scrim", "key"):
        page.locator("#cz-sos").click()
        expect(page.locator(".cz-sheet-sos")).to_be_visible()
        assert page.locator(".cz-sheet-sos a[href='tel:911']").count() == 1 and page.url == url
        close_sheet(page, how)
    page.locator("#cz-sos").click()
    expect(page.locator(".cz-sheet-sos")).to_have_count(1)                           # a second tap on the button does not stack a second sheet
    page.context.set_offline(False)


def test_the_tab_bar_is_three_tabs_with_ask_in_the_middle(imported_page):
    page = imported_page()
    labels = page.locator(".ph-tab").all_inner_texts()
    assert [x.strip() for x in labels] == ["Today", "Ask", "Family"]
    ask = page.locator("#ph-tab-ask").bounding_box()
    assert abs((ask["x"] + ask["width"] / 2) - PHONE["width"] / 2) < 2
    bar = page.locator(".ph-tabs").bounding_box()
    for tab in page.locator(".ph-tab").all():
        box = tab.bounding_box()
        assert box["x"] >= bar["x"] and box["x"] + box["width"] <= bar["x"] + bar["width"] + 1 and box["height"] >= 43.5
    page.locator("#ph-tab-family").click()
    page.wait_for_url(re.compile(r"/trip/family"))


def test_help_still_opens_for_old_links_and_has_no_settings_cards(imported_page, base_url):
    page = imported_page()
    page.goto(f"{base_url}/trip/help")
    expect(page.locator("#hp-hotel")).to_contain_text("The Example Hotel Santa Monica")
    expect(page.locator("#hp-911")).to_have_attribute("href", "tel:911")
    assert page.locator("#tp-morning, #pk-card").count() == 0
    assert page.locator(".ph-tab[aria-current=page]").count() == 0


# ---- a viewer -----------------------------------------------------------------------------------------------------------------

def test_a_viewer_reads_every_sheet_and_sees_no_edit_buttons(imported_page, base_url):
    from main import app
    from tests.test_members import addr, invite
    from tests.test_signin import sign_in
    owner = TestClient(app, client=("127.0.0.1", 50002))
    sign_in(owner, "ari")
    mail = addr("vi")
    invite(owner, mail, "viewer")
    imported_page()                                                                  # the owner's page makes sure the trip is imported
    page = imported_page(who=mail)
    day(page, base_url, 0)
    for text in ("Alaska", "Check in", "Hertz"):
        page.locator("a.cz-bk", has_text=text).click()
        page.wait_for_selector(".cz-sheet-bk")
        sheet = page.locator(".cz-sheet-bk")
        assert sheet.locator("form, input, .hp-fix-sum").count() == 0, text
        expect(sheet.locator("#bk-passes, #hp-directions, #bk-counter").first).to_be_attached()
        close_sheet(page)
    page.locator("#cz-sos").click()
    page.wait_for_selector(".cz-sheet-sos")
    assert page.locator(".cz-sheet-sos a[href='tel:911']").count() == 1 and page.locator(".cz-sheet-sos form").count() == 0


# ---- screenshots on request: F093_SHOTS=<folder> pixi run pytest -p no:randomly tests_browser/test_booked.py -k screenshots ---------------------------

@pytest.mark.skipif(not os.environ.get("F093_SHOTS"), reason="set F093_SHOTS=<folder> to write screenshots")
@pytest.mark.parametrize("viewport,name", [(PHONE, "390"), (NARROW, "320"), ({"width": 1280, "height": 800}, "1280")], ids=["390", "320", "1280"])
def test_screenshots(imported_page, base_url, viewport, name):
    out = os.environ["F093_SHOTS"]
    os.makedirs(out, exist_ok=True)
    page = imported_page(viewport=viewport)
    page.screenshot(path=f"{out}/week-{name}.png")
    page.locator(".cz-kchip", has_text="Hotels").click()
    page.screenshot(path=f"{out}/week-hotels-{name}.png")
    page.locator(".cz-kchip", has_text="All").click()
    day(page, base_url, 0)
    page.screenshot(path=f"{out}/day-{name}.png")
    for text, tag in (("Alaska", "flight"), ("Check in", "hotel"), ("Hertz", "car")):
        page.locator("a.cz-bk", has_text=text).click()
        page.wait_for_selector(".cz-sheet-bk")
        page.wait_for_timeout(400)
        page.screenshot(path=f"{out}/sheet-{tag}-{name}.png")
        close_sheet(page)
    page.locator("#cz-sos").click()
    page.wait_for_selector(".cz-sheet-sos")
    page.wait_for_timeout(400)
    page.screenshot(path=f"{out}/sos-{name}.png")
