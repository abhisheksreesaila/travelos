"""F-276 in a real browser: Book this trip with a flight. The square's flight carries a LiteAPI offer, the checkout asks the travellers an airline's questions (one card a seat), the flight is paid first
in LiteAPI's form (its script stubbed, as tests_browser/test_matrixbook_pay.py does) and booked when the browser returns, then the stay's own form is on the page that return draws, and the second return shows
the pass of both. The server side is the recordings of tests/fixtures/liteapi_flight and liteapi_pay; nothing real is paid.

What stays for a human: LiteAPI's real form in a real browser, the sandbox test card 4242 4242 4242 4242 (twice: the flight, then the stay), and the redirect back from LiteAPI's processor."""
import json
import os
import re
from dataclasses import replace
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import gridsource, liteapi, matrixbook as mb
from tests.flight_support import BOOK as FBOOK, Fly, PREBOOK as FPREBOOK, VERIFY
from tests.test_liteapi_pay import LIVE
from tests.test_matrixbook_live import BOOK, Live, PREBOOK
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit
from tests_browser.test_matrixbook_pay import SDK, with_stub
from tests_browser.test_matrixbook_sheet import BookStand, _no_presses_yet, open_square  # noqa: F401 (the autouse fixture)
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)

FLIGHT_CENTS = 60_000      # the stand's flight for four nights
PEOPLE = (("Maya", "Okafor", "1985-04-12", "F"), ("Daniel", "Okafor", "1983-09-03", "M"), ("Leo", "Okafor", "2019-06-01", "M"), ("Zoe", "Okafor", "2016-03-15", "F"))


class FlightStand(BookStand):
    """The fixed table's squares with each stay's offer id and the flight's too (a LiteAPI flight always has one)."""

    def __call__(self, *a, **k):
        sq = super().__call__(*a, **k)
        if sq is None or not sq.ok or sq.flight is None:
            return sq
        return replace(sq, flight=replace(sq.flight, offer_id="offer-flight-1"))


@pytest.fixture
def flying(monkeypatch, stand):  # noqa: F811
    """A live key where real booking is on, LiteAPI answering the stay and the flight from the recordings (the flight $600, the shown stay $1,540 with its $120 fee at the hotel)."""
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "1")
    stays = Live()
    stays.shown = 1540.0
    fly = Fly(other=stays, swap={"2026-12-18": "2026-12-12", "2026-12-22": "2026-12-16"})
    fly.answers["verify"] = lambda doc: doc["data"][0]["journey"]["pricing"]["display"].__setitem__("total", FLIGHT_CENTS / 100)
    fly.answers["prebook"] = lambda doc: doc["data"][0].__setitem__("price", FLIGHT_CENTS / 100)
    monkeypatch.setattr(liteapi, "TRANSPORT", fly)
    monkeypatch.setattr(gridsource, "SQUARE", FlightStand())
    mb.forget()
    fly.stays = stays
    return fly


def shot(page, name):
    """F276_SHOTS=<folder> writes the checkout's states there (for looking at, not asserted)."""
    if os.environ.get("F276_SHOTS"):
        Path(os.environ["F276_SHOTS"]).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(os.environ["F276_SHOTS"]) / f"f276-{name}.png"))


def travellers(page):
    """One card a seat: names as on the ID, birth date, gender (nationality starts as United States), then Continue; then the lead's email and number; then the requests."""
    for i, (first, last, born, sex) in enumerate(PEOPLE):
        names = ("first", "last") if i == 0 else (f"t{i}_first", f"t{i}_last")
        page.fill(f"#mxb-{names[0]}", first)
        page.fill(f"#mxb-{names[1]}", last)
        page.fill(f"#mxb-t{i}_dob", born)
        page.select_option(f"#mxb-t{i}_sex", sex)
    page.click("[data-cont]")
    page.fill("#mxb-email", "maya.okafor@example.com")
    page.fill("#mxb-phone", "415 555 0100")
    page.click("[data-cont]")
    page.click("[data-req='Quiet room']")
    page.click("[data-cont]")


def to_review(page, viewport):
    panel = open_square(page, viewport)
    panel.locator(".dr-book").click()
    sheet = page.locator(".mxb-sheet")
    expect(sheet).to_be_visible()
    expect(sheet.locator(".mxb-pane.is-on")).to_contain_text("Who is travelling?")
    return sheet


def dark(page):
    page.evaluate("localStorage.setItem('ga-mode', 'dark')")
    page.reload()
    page.wait_for_selector("#mx.is-live")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_travellers_are_asked_the_flight_is_paid_first_then_the_stay_and_the_pass_shows_both(matrix, flying, viewport):  # noqa: F811
    page = matrix(viewport, motion=True, signed_in=True)
    with_stub(page)
    sheet = to_review(page, viewport)
    expect(sheet.locator(".mxb-tv")).to_have_count(4)
    expect(sheet.locator(".mxb-tv").nth(0)).to_contain_text("Lead traveller")
    expect(sheet.locator(".mxb-tv").nth(3)).to_contain_text("kid, age 10")
    assert page.locator("input[name*='doc']").count() == 0      # a domestic route: no passport
    page.wait_for_timeout(600)
    shot(page, f"{viewport['width']}-travellers")
    travellers(page)
    expect(page.locator(".mxb-f")).to_have_attribute("data-step", "3")
    expect(sheet.locator(".mxb-frules")).to_contain_text("Economy Light")
    expect(sheet.locator(".mxb-frules")).to_contain_text("Not refundable: cancelling returns only some taxes.")
    expect(sheet.locator(".mxb-frules")).to_contain_text("Not changeable")
    expect(sheet.locator("[data-two]")).to_contain_text("Two charges from Nuitée: the flight $600, then the stay $1,420")
    expect(sheet.locator(".mxb-go")).to_be_disabled()
    expect(sheet.locator(".mxb-go")).to_contain_text("Continue · $600")      # the flight is the first charge
    page.wait_for_timeout(700)
    shot(page, f"{viewport['width']}-review")
    assert len(flying.calls(VERIFY)) == 1 and flying.calls(FPREBOOK) == [] and len(flying.stays.calls(PREBOOK)) == 1 and page.outside == []
    page.click(".mxb-agree")
    page.click(".mxb-go")
    expect(sheet.locator("#stub-pay")).to_be_visible()      # the flight's own LiteAPI form (the stand-in) is in our sheet
    expect(sheet.locator("h3")).to_contain_text("Pay for your flight")
    config = page.evaluate("() => window.__pay.config")
    assert re.fullmatch(r"http://127\.0\.0\.1:\d+/plan/matrix/book/flight/return\?token=[A-Za-z0-9_-]+", config["returnUrl"]) and config["publicKey"] == "live"
    expect(sheet.locator(".mxb-total")).to_have_text("$600")
    assert page.locator("input[autocomplete^='cc-'], input[name*='card' i]").count() == 0      # no card field of ours
    sent = flying.calls(FPREBOOK)
    assert len(sent) == 1 and [p["firstName"] for p in sent[0]["passengers"]] == ["Maya", "Daniel", "Leo", "Zoe"] and flying.calls(FBOOK) == [] and flying.stays.calls(BOOK) == []
    page.wait_for_timeout(500)
    shot(page, f"{viewport['width']}-flight-pay")
    page.click("#stub-pay")
    page.wait_for_url("**/plan/matrix/book/flight/return**")
    expect(page.locator("body")).to_contain_text("Your flight is booked")
    expect(page.locator("[data-flight-ref]").first).to_have_text("FH-26B-1VO6TJ6Z")
    expect(page.locator("[data-status='CONFIRMED']")).to_contain_text("Tickets issued")
    expect(page.locator("body")).to_contain_text("Now pay for your stay")
    expect(page.locator("#stub-pay")).to_be_visible()      # the stay's own form, mounted when the page loads
    page.wait_for_timeout(700)
    shot(page, f"{viewport['width']}-stay-pay")
    sent = flying.calls(FBOOK)
    assert len(sent) == 1 and sent[0]["payment"]["method"] == "TRANSACTION_ID" and "ACC_CREDIT_CARD" not in json.dumps(flying.asked) and flying.stays.calls(BOOK) == []
    page.click("#stub-pay")
    page.wait_for_url("**/plan/matrix/book/return**")
    expect(page.locator("body")).to_contain_text("You’re booked")
    expect(page.locator("[data-flight-ref]").first).to_have_text("FH-26B-1VO6TJ6Z")
    expect(page.locator("[data-booking-id]")).to_have_text("uuJxfM0--")
    page.wait_for_timeout(1200)
    shot(page, f"{viewport['width']}-pass")
    assert set(page.outside) == {SDK} and len(flying.calls(FBOOK)) == 1 and len(flying.stays.calls(BOOK)) == 1
    page.reload()      # a reload shows the same pass and books nothing again
    expect(page.locator("[data-booking-id]")).to_have_text("uuJxfM0--")
    assert len(flying.calls(FBOOK)) == 1 and len(flying.stays.calls(BOOK)) == 1 and page.errors == []


def test_a_wrong_birth_date_is_stopped_by_the_picker_and_by_the_server_with_the_typed_words_kept(matrix, flying):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    with_stub(page)
    to_review(page, DESKTOP)
    for i, (first, last, born, sex) in enumerate(PEOPLE):
        names = ("first", "last") if i == 0 else (f"t{i}_first", f"t{i}_last")
        page.fill(f"#mxb-{names[0]}", first)
        page.fill(f"#mxb-{names[1]}", last)
        page.fill(f"#mxb-t{i}_dob", "2016-12-31" if i == 3 else born)      # the kid searched as 10 is 9 on the day they fly
        page.select_option(f"#mxb-t{i}_sex", sex)
    page.click("[data-cont]")
    expect(page.locator(".mxb-f")).to_have_attribute("data-step", "0")      # the date picker's own range stops it before the server is asked
    assert page.eval_on_selector("#mxb-t3_dob", "e => e.validity.rangeOverflow || e.validity.rangeUnderflow")
    page.evaluate("() => document.querySelectorAll('input[type=date]').forEach(e => { e.removeAttribute('min'); e.removeAttribute('max'); })")      # a browser without the hint: the server decides
    page.click("[data-cont]")
    page.fill("#mxb-email", "maya.okafor@example.com")
    page.fill("#mxb-phone", "415 555 0100")
    page.click("[data-cont]")
    page.click("[data-cont]")
    page.click(".mxb-agree")
    page.click(".mxb-go")
    expect(page.locator("#mxb-t3_dob-e")).to_contain_text("This kid was searched as 10")
    expect(page.locator("#mxb-first")).to_have_value("Maya")
    expect(page.locator("#mxb-t1_first")).to_have_value("Daniel")
    assert flying.calls(FPREBOOK) == [] and page.errors == []


def test_a_flight_price_that_moved_is_said_before_the_checkout_goes_on(matrix, flying):  # noqa: F811
    flying.answers["verify"] = lambda doc: (doc["data"][0]["journey"]["pricing"]["display"].__setitem__("total", 640.0), doc["data"][0]["changes"].__setitem__("priceChanged", True))
    page = matrix(DESKTOP, signed_in=True)
    with_stub(page)
    sheet = to_review(page, DESKTOP)
    travellers(page)
    expect(sheet.locator("[data-moved]")).to_contain_text("The flight’s price moved: it was $600 on the square and is $640 now.")
    expect(sheet.locator(".mxb-go")).to_contain_text("Continue · $640")
    assert flying.calls(FPREBOOK) == []


def test_the_flights_form_failing_to_load_says_so_and_nothing_is_booked(matrix, flying):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    with_stub(page, fail=True)
    to_review(page, DESKTOP)
    travellers(page)
    page.click(".mxb-agree")
    page.click(".mxb-go")
    expect(page.locator("[data-pay-wait]")).to_contain_text("did not load. Nothing was charged.")
    assert flying.calls(FBOOK) == []


def test_the_flight_is_on_the_trip_and_its_page_cancels_with_the_quote_first(matrix, flying):  # noqa: F811
    page = matrix(DESKTOP, motion=False, signed_in=True)
    with_stub(page)
    to_review(page, DESKTOP)
    travellers(page)
    page.click(".mxb-agree")
    page.click(".mxb-go")
    page.click("#stub-pay")
    page.wait_for_url("**/plan/matrix/book/flight/return**")
    page.click("#stub-pay")
    page.wait_for_url("**/plan/matrix/book/return**")
    page.goto(page.url.split("/plan/")[0] + "/trip/plan?day=2026-12-12")
    page.locator("a[href*='/trip/booking?block=b-out']").first.click()
    expect(page.locator("#bk-fstatus")).to_contain_text("Tickets issued")
    expect(page.locator("#bk-fpnr")).to_contain_text("ND 50CVYQ")
    expect(page.locator("#bk-fcancel-go")).to_have_count(0)      # nothing can be cancelled before the quote
    shot(page, "1440-booking")
    page.click("#bk-fquote-go")
    expect(page.locator("#bk-fquote")).to_have_text("If you cancel now: $71.14 comes back to the card you paid with, and cancelling costs $497.94.")
    page.check("input[name='sure']")
    page.click("#bk-fcancel-go")
    expect(page.locator("#bk-cancelled")).to_contain_text("LiteAPI charged $497.94 for cancelling, and $71.14 comes back")
    shot(page, "1440-cancelled")
    assert page.errors == []


def clean(page, where, in_sheet=False):
    """The page as drawn measures clean: no sideways scroll, no tap target under 48px on a phone, no text under the type floor or under 4.5:1 (tests_browser/look.py). `in_sheet`: the sheet is open, so
    what is behind it is hidden for the measure (the matrix's own words are another test's); LiteAPI's stand-in button is not ours to measure."""
    hide = "() => document.querySelectorAll('body > *:not(.mxb-sheet)').forEach(e => { e.dataset.v = e.style.display; e.style.display = 'none'; })"
    show = "() => document.querySelectorAll('body > *:not(.mxb-sheet)').forEach(e => { e.style.display = e.dataset.v || ''; })"
    if in_sheet:
        page.evaluate(hide)
    a = audit(page)
    if in_sheet:
        page.evaluate(show)
    mine = {k: [x for x in v if "stub" not in x] if isinstance(v, list) else v for k, v in a.items()}
    assert mine["wide"] <= 1 and mine["small"] == [] and mine["tiny"] == [] and mine["low"] == [] and mine["glass"] == [], (where, mine)


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_every_state_of_the_flight_checkout_measures_clean_in_both_modes(matrix, flying, viewport, mode):  # noqa: F811
    page = matrix(viewport, motion=False, signed_in=True)
    with_stub(page)
    if mode == "dark":
        dark(page)
    sheet = to_review(page, viewport)
    page.wait_for_timeout(500)
    shot(page, f"{viewport['width']}-{mode}-travellers")
    clean(page, "travellers", True)
    travellers(page)
    page.wait_for_timeout(500)
    shot(page, f"{viewport['width']}-{mode}-review")
    clean(page, "review", True)
    page.click(".mxb-agree")
    page.click(".mxb-go")
    expect(sheet.locator("#stub-pay")).to_be_visible()
    page.wait_for_timeout(500)
    shot(page, f"{viewport['width']}-{mode}-flight-pay")
    clean(page, "flight pay", True)
    page.click("#stub-pay")
    page.wait_for_url("**/plan/matrix/book/flight/return**")
    expect(page.locator("#stub-pay")).to_be_visible()
    page.wait_for_timeout(500)
    shot(page, f"{viewport['width']}-{mode}-stay-pay")
    clean(page, "stay pay")
    page.click("#stub-pay")
    page.wait_for_url("**/plan/matrix/book/return**")
    expect(page.locator("[data-booking-id]")).to_have_text("uuJxfM0--")
    page.wait_for_timeout(1500)
    shot(page, f"{viewport['width']}-{mode}-pass")
    clean(page, "pass")
    assert page.errors == []
