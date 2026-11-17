"""F-263 in a real browser: guides in context. Over booking's matrix a "Guides for Los Angeles" row opens the guide in a sheet that names your search, opens a stop in place (never a sheet on a
sheet) and closes onto exactly what you left: the same scroll, the same opened square with its drawer, the focus back on the row. Over planning's calendar the sheet names the free Saturday
morning it found, "+" and "Add this morning to Sat" drop stops into it with the guide's name on them, and Undo takes them out; on a phone the sheet shrinks to a bar so the drop can be watched.
Light and dark, 48px targets and 4.5:1 text are measured on the real page. Set F263_SHOTS=1 for docs/report/f263-*.png."""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE, open_more, open_rail
from tests_browser.look import audit
from tests_browser.test_planv2 import plan  # noqa: F401 (fixture)
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)
from tests_browser.test_v2_targets import small

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
CONTROLS = "a[href], button, summary, [role=button]"


def news(before, after):
    """What the audit finds with the sheet open that it did not find without it (the page behind has its own ledger): nothing."""
    for k in ("low", "tiny", "small", "glass"):
        assert [x for x in after[k] if x not in before[k]] == [], k
    assert after["wide"] <= max(before["wide"], 1)


def shot(page, name):
    if os.environ.get("F263_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f263-{name}.png"))


def where(page):
    """Everything the sheet must leave as it found it: the page's scroll, the grid's scroll, which square is open and what its drawer says."""
    return page.evaluate("""() => ({ y: window.scrollY, x: document.getElementById('mx-scroll').scrollLeft,
        open: [...document.querySelectorAll('.mx-sq.is-open')].map(e => e.dataset.sq), drawer: document.getElementById('mx-drawer').hidden ? '' : document.getElementById('mx-drawer').innerHTML })""")


def at_rest(page):
    """The matrix settles by itself for a moment after a square opens (its answers land, the drawer fills): read the state until two reads, half a second apart, agree."""
    last = None
    for _ in range(20):
        now = where(page)
        if now == last:
            return now
        last = now
        page.wait_for_timeout(500)
    raise AssertionError("the matrix never came to rest")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_a_guide_opens_over_the_matrix_and_closing_it_returns_exactly_where_you_were(matrix, stand, viewport):  # noqa: F811
    stand.peek_all = True      # the server knows every square: the sheet's bar names the price of the one you opened
    page = matrix(viewport, signed_in=True)
    page.locator(".mx-lane[data-lane='losangeles'] .mx-sq").nth(2).click()      # open a square of Los Angeles: its drawer under the grid, and the rail follows Los Angeles
    expect(page.locator("#mx-drawer .dr-book")).to_be_visible()
    open_rail(page)
    row = page.locator("#mx-rail .gd-row")
    expect(row).to_have_count(1)
    expect(page.locator("#mx-rail .wg").first.locator(".wg-h")).to_have_text("Guides for Los Angeles")
    expect(page.locator("#mx-rail .wg").first.locator(".smp")).to_have_text("Sample")      # the showcase's guide says it is a sample
    page.evaluate("document.getElementById('mx-scroll').scrollLeft = 40; window.scrollTo(0, 60)")
    page.evaluate("document.querySelector('#mx-rail .gd-row').scrollIntoView({block: 'center'})")      # reaching the row may scroll the page and load more squares
    at_rest(page)      # the rail asks again once every square in view has settled (v2rail.js, mx:settled) and may swap its rows: wait for that before holding one
    page.wait_for_function("""() => { const r = document.getElementById('mx-rail'), h = r.innerHTML; return new Promise(ok => setTimeout(() => ok(r.innerHTML === h), 600)); }""", polling=700)
    before = at_rest(page)
    assert before["open"] and before["drawer"]
    row.click()
    sheet = page.locator(".gsheet")
    expect(sheet).to_be_visible()
    expect(sheet.locator(".gs-ctx")).to_have_text("Your trips · Los Angeles, Dec 12 · 4 nights · $2,350 picked")      # it names your search
    expect(sheet.locator(".g-card")).to_have_count(16)
    shot(page, f"{viewport['width']}-book-sheet")
    stop = sheet.locator(".g-card").nth(2)
    stop.locator(".g-cover").click()      # a stop opens in place, inside its card
    expect(stop).to_have_class(re.compile(r"is-open"))
    expect(stop.locator(".g-inplace .g-words")).to_be_visible()
    assert page.locator("[role=dialog]:visible").evaluate_all("els => els.filter(e => !e.closest('.gsheet') && e.id !== 'mx-drawer').length") == 0      # no second sheet on the sheet
    assert sheet.locator(".gsheet, .g-panel, [role=dialog]").count() == 0
    shot(page, f"{viewport['width']}-book-stop")
    page.keyboard.press("Escape")      # closes the sheet only: the opened square and its drawer never hear it
    expect(sheet).to_have_count(0)
    after = where(page)
    assert after == before
    assert page.evaluate("document.activeElement.classList.contains('gd-row')")      # the focus is back on the row it came from


def test_booking_sheet_closes_with_its_buttons_and_the_page_behind_never_moved(matrix, stand):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    page.locator(".mx-lane[data-lane='losangeles'] .mx-lead").click()
    open_rail(page)
    before = where(page)
    page.locator("#mx-rail .gd-row").click()
    expect(page.locator(".gsheet")).to_be_visible()
    page.locator(".gsheet .gs-bar .v2-round").last.click()
    expect(page.locator(".gsheet")).to_have_count(0)
    page.locator("#mx-rail .gd-row").click()
    page.locator(".gsheet [data-close]").first.click()
    expect(page.locator(".gsheet")).to_have_count(0)
    assert where(page) == before


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_rail_card_and_the_sheet_are_48px_targets_and_read_4_5_to_1(matrix, stand, viewport, scheme):  # noqa: F811
    page = matrix(viewport, signed_in=True, scheme=scheme)
    page.locator(".mx-lane[data-lane='losangeles'] .mx-lead").click()
    open_rail(page)
    expect(page.locator("#mx-rail .gd-row")).to_have_count(1)
    page.wait_for_timeout(700)
    assert small(page, "#mx-rail") == []
    behind = audit(page)
    page.locator("#mx-rail .gd-row").click()
    expect(page.locator(".gsheet .g-card").first).to_be_visible()
    page.wait_for_timeout(400)
    assert small(page, ".gsheet") == [], "the sheet's controls"
    page.locator(".gsheet .g-cover").nth(1).click()
    page.wait_for_timeout(500)
    assert small(page, ".gsheet") == [], "the sheet with a stop open"
    news(behind, audit(page))



# ---- planning ------------------------------------------------------------------------------------------------------------------------

def take_the_first_day(page, base_url):
    """The family's whole first day is taken, so what is free is Saturday morning."""
    page.context.request.post(f"{base_url}/trip/plan/write", form={"op": "add", "day": "0", "start": "572", "end": "1320", "title": "Settle in, long dinner", "kind": "food"})
    page.reload()
    page.wait_for_selector(".g-inner")


def toast_undo(page):
    page.locator(".ga-toast-act").click()


def plans_on(page, day):
    """The plans (not the bookings) drawn on a day: [(title, start, end, tagged)]."""
    return page.evaluate("""(d) => [...document.querySelectorAll(`.col[data-day='${d}'] .ev[data-title]`)].map(e => [e.dataset.title, +e.dataset.start, +e.dataset.end, !!e.querySelector('.gtag')])""", day)


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_a_guide_over_the_calendar_names_the_free_time_and_drops_a_morning_in_with_undo(plan, base_url, viewport):  # noqa: F811
    page = plan(viewport)
    take_the_first_day(page, base_url)
    expect(page.locator("#pl-rail .wg").first.locator(".wg-h")).to_have_text("Guides for Los Angeles")
    page.locator("#pl-rail .gd-row").click()
    sheet = page.locator(".gsheet")
    expect(sheet).to_be_visible()
    expect(sheet.locator(".gs-ctx")).to_contain_text("Your plan · Oct 16 to 20 · Saturday morning free")
    expect(sheet.locator(".gs-free")).to_contain_text("Your Saturday morning is free.")
    expect(sheet.locator(".gs-free")).to_contain_text("Day 1 fits it.")
    shot(page, f"{viewport['width']}-plan-sheet")
    sheet.locator(".gs-free .go").click()      # the morning: the day that fits, one stop after the other from 8:00, into Saturday
    expect(sheet.locator(".gs-free .go")).to_contain_text("Added to Sat")
    expect(page.locator(".ga-toast")).to_contain_text("2 stops added to Sat, 8:00 AM to 12:00 PM")
    expect(page.locator(".col[data-day='1'] .ev[data-title]")).to_have_count(2)
    assert plans_on(page, 1) == [["Skylark Air 214 · SFO → LAX", 480, 600, True], ["Check in: The Tidewater, Santa Monica", 600, 720, True]]      # tagged with the guide's name
    if viewport["width"] >= 720:
        expect(page.locator(".col[data-day='1'] .ev .gtag .gt").first).to_have_text("From Maya's guide")
        expect(page.locator(".col[data-day='1'] .ev[data-title]").first).to_have_attribute("aria-label", "Skylark Air 214 · SFO → LAX, 8:00–10:00 AM, From Maya's guide. Tap to change or drag to move")
    else:      # the sheet shrinks to a bar and the calendar is in view, so the drop can be watched
        expect(sheet).to_have_class(re.compile(r"peek"))
        assert sheet.bounding_box()["height"] < 100
        top = page.locator(".col[data-day='1'] .ev[data-title]").first.bounding_box()
        assert 0 <= top["y"] < viewport["height"] - sheet.bounding_box()["height"]
    shot(page, f"{viewport['width']}-plan-added")
    toast_undo(page)
    expect(page.locator(".col[data-day='1'] .ev[data-title]")).to_have_count(0)
    assert plans_on(page, 0) == [["Settle in, long dinner", 570, 1320, False]]      # only what Undo took out went
    if viewport["width"] < 720:
        sheet.locator("[data-unpeek]").click()
        expect(sheet).not_to_have_class(re.compile(r"peek"))
    expect(sheet.locator(".gs-free .go")).to_contain_text("Add this morning to Sat")      # and the offer is back


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_a_stop_added_with_its_plus_lands_in_dry_free_time_tagged_and_undo_takes_it_out(plan, base_url, viewport):  # noqa: F811
    page = plan(viewport)
    page.locator("#pl-rail .gd-row").click()
    sheet = page.locator(".gsheet")
    expect(sheet).to_be_visible()
    stop = sheet.locator(".g-card[data-k='d2s1']")
    stop.locator(".g-cover").click()      # in place, then its own "Add to my plan"
    stop.locator(".g-inplace .go").click()
    expect(page.locator(".ga-toast")).to_contain_text("Picnic under the oak")
    expect(stop.locator(".g-plus")).to_have_class(re.compile(r"done"))
    expect(page.locator(".ev[data-title^='Picnic under the oak'] .gtag")).to_have_count(1)
    toast_undo(page)
    expect(page.locator(".ev[data-title^='Picnic under the oak']")).to_have_count(0)
    expect(stop.locator(".g-plus")).not_to_have_class(re.compile(r"done"))


def test_closing_the_planning_sheet_leaves_the_calendar_as_it_was_and_escape_closes_only_the_sheet(plan, base_url):  # noqa: F811
    page = plan(DESKTOP)
    page.evaluate("window.scrollTo(0, 50); document.querySelector('.g-body').scrollTop = 120")
    before = page.evaluate("() => [scrollY, document.querySelector('.g-body').scrollTop, document.getElementById('pl-cal').dataset.view, document.getElementById('pl-cal').innerHTML.length]")
    page.locator("#pl-rail .gd-row").click()
    expect(page.locator(".gsheet")).to_be_visible()
    before[0] = page.evaluate("scrollY")      # reaching the row may scroll the page
    page.keyboard.press("Escape")
    expect(page.locator(".gsheet")).to_have_count(0)
    assert page.evaluate("() => [scrollY, document.querySelector('.g-body').scrollTop, document.getElementById('pl-cal').dataset.view, document.getElementById('pl-cal').innerHTML.length]") == before
    assert page.evaluate("document.activeElement.classList.contains('gd-row')")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_planning_rail_card_and_sheet_are_48px_targets_and_read_4_5_to_1(plan, base_url, viewport, scheme):  # noqa: F811
    page = plan(viewport, scheme)
    take_the_first_day(page, base_url)
    page.wait_for_timeout(700)
    assert small(page, "#pl-rail") == []
    behind = audit(page)
    page.locator("#pl-rail .gd-row").click()
    expect(page.locator(".gsheet .gs-free")).to_be_visible()
    page.wait_for_timeout(400)
    assert small(page, ".gsheet") == [], "the sheet's controls"
    news(behind, audit(page))


# ---- review fixes ------------------------------------------------------------------------------------------------------------------------

def test_an_undo_the_server_refuses_says_so_and_leaves_what_was_not_undone_marked(plan, base_url):  # noqa: F811
    page = plan(DESKTOP)
    page.locator("#pl-rail .gd-row").click()
    sheet = page.locator(".gsheet")
    stop = sheet.locator(".g-card[data-k='d2s1']")
    stop.locator(".g-cover").click()
    stop.locator(".g-inplace .go").click()
    expect(stop.locator(".g-plus")).to_have_class(re.compile(r"done"))
    mine = page.locator(".ev[data-title^='Picnic under the oak']")
    expect(mine).to_have_count(1)
    act = mine.get_attribute("data-id")
    page.context.request.post(f"{base_url}/trip/plan/write", form={"op": "edit", "act": act, "title": "Picnic, moved by someone"})      # someone changed it between the add and the Undo
    toast_undo(page)
    expect(page.locator(".ga-toast")).to_contain_text("Someone changed it since. Nothing was undone.")
    expect(page.locator(".ga-toast")).not_to_contain_text("Taken out of your plan")
    expect(stop.locator(".g-plus")).to_have_class(re.compile(r"done"))      # still in the plan, still marked
    page.reload()
    page.wait_for_selector(".g-inner")
    expect(page.locator(".ev[data-title^='Picnic, moved by someone']")).to_have_count(1)


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_guide_sheet_takes_the_calm_fade_on_a_laptop_and_the_spring_on_a_phone(matrix, stand, viewport):  # noqa: F811
    page = matrix(viewport, signed_in=True, motion=True)
    page.locator(".mx-lane[data-lane='losangeles'] .mx-lead").click()
    open_rail(page)
    row = page.locator("#mx-rail .gd-row")
    expect(row).to_have_count(1)
    page.evaluate("GA.motion.log.length = 0")
    row.click()
    sheet = page.locator(".gsheet")
    expect(sheet).to_be_visible()
    page.wait_for_timeout(500)
    opens = page.evaluate("GA.motion.log.filter(l => l.kind === 'open').map(l => ({ calm: !!l.calm, dur: l.dur }))")
    if viewport["width"] >= 1020:      # the calm rule: no spring, no zoom (the matrix's own liquid exception, D-439, is not this sheet's)
        expect(sheet).to_have_class(re.compile(r"is-calm"))
        assert opens == []
    else:      # a phone: out of the row, on the v2 spring
        expect(sheet).not_to_have_class(re.compile(r"is-calm"))
        assert opens == [{"calm": False, "dur": page.evaluate("GA.motion.t('spring')")}]


def test_the_guide_will_not_open_beside_the_planning_drawer(plan, base_url):  # noqa: F811
    page = plan(DESKTOP)
    open_more(page, "#pl-together").click()      # F-293: a row of the trip's More menu; the drawer sits beside the rail on a laptop: its guides row is still there to press
    expect(page.locator("#pl-side")).to_be_visible()
    page.locator("#pl-rail .gd-row").dispatch_event("click")
    expect(page.locator(".ga-toast")).to_contain_text("Close this first")
    expect(page.locator(".gsheet")).to_have_count(0)
