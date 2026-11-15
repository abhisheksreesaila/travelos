"""F-242 in a real browser: the opened square as one trip view (laptop 1440: the sky over a timeline, then the stay, the flight and the cost; phone 390: coloured tiles and a
sticky total with the boldest button). The hotel and the flight switch in place and the total moves by exactly the difference; Book this trip then books what was chosen. A stand-in
source gives each square three flights and three stays. Set F242_SHOTS=1 for docs/report/f242-*.png."""
import os
from dataclasses import replace
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import gridsource, liteapi
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit
from tests_browser.test_matrixbook_sheet import BookStand, _no_presses_yet, fill, open_square, states, to_review  # noqa: F401 (fixtures and helpers)
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"


class AltStand(BookStand):
    """The fixed table's squares with two more flights and two more stays behind the shown ones (cheaper and dearer), so there is something to switch to."""

    def __call__(self, *a, **k):
        sq = super().__call__(*a, **k)
        if sq is None or not sq.ok:
            return sq
        flights = (sq.flight, replace(sq.flight, airline="Nuitée Air", stops=1, cents=sq.flight.cents - 20_000), replace(sq.flight, airline="Skylark Air", cents=sq.flight.cents + 8_000))
        alts = tuple((st, replace(st, name=f"Cheaper {st.place} Inn", cents=st.cents - 30_000, photo="", rating="8.1 of 10"), replace(st, name=f"Grand {st.place} Resort", cents=st.cents + 50_000,
                                                                                                                      address="1 Harbor Way, San Diego, CA")) for st in sq.stays)
        return replace(sq, flights=flights, stay_alts=alts)


@pytest.fixture
def alt(monkeypatch, stand):  # noqa: F811
    monkeypatch.setattr(gridsource, "SQUARE", AltStand(sample=True))
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: (_ for _ in ()).throw(AssertionError("LiteAPI was asked")))


def shot(page, name):
    if os.environ.get("F242_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f242-{name}.png"))


def cents(text):
    return int(round(float(text.replace("$", "").replace(",", "")) * 100))


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_switching_the_flight_and_the_hotel_in_place_moves_the_total_by_the_difference(matrix, alt, viewport):  # noqa: F811
    page = matrix(viewport, signed_in=True)
    view = open_square(page, viewport)
    total = view.locator("[data-slot='total']")
    first = cents(total.inner_text())
    expect(view.locator(".mx-tile-flight .mx-ct")).to_have_text("1 of 3")
    expect(view.locator(".mx-tile-flight .mx-opt:not([hidden]) .mx-o-h")).to_have_text("Test Air")
    shot(page, f"{viewport['width']}-opened")
    view.locator(".mx-tile-flight [data-flip='1']").click()
    expect(view.locator(".mx-tile-flight .mx-opt:not([hidden]) .mx-o-h")).to_have_text("Nuitée Air")
    expect(view.locator(".mx-tile-flight .mx-ct")).to_have_text("2 of 3")
    assert cents(total.inner_text()) == first - 20_000 and cents(view.locator("[data-mirror='total']").inner_text()) == first - 20_000      # the total and the sticky bar's
    view.locator(".mx-tile-stay [data-flip='-1']").click()      # the other way round: the last of three
    expect(view.locator(".mx-tile-stay .mx-opt:not([hidden]) .mx-o-h")).to_have_text("Grand San Diego Resort")
    expect(view.locator(".mx-tile-stay .mx-opt:not([hidden]) .mx-o-addr")).to_have_text("1 Harbor Way, San Diego, CA")
    assert cents(total.inner_text()) == first - 20_000 + 50_000
    assert view.locator("[data-cost='flight']").inner_text() == view.locator('.mx-tile-flight .mx-opt:not([hidden]) .mx-o-n').inner_text()      # the cost card follows the choice
    assert view.locator("input[data-pick='fl']").first.input_value() == "1" and view.locator("input[data-pick='st']").first.input_value() == "2"
    assert view.locator(".mx-vs").first.get_attribute("class").count("is-empty") == 1          # the "vs" chip was for the trip shown first
    shot(page, f"{viewport['width']}-switched")
    view.locator(".mx-tile-stay [data-flip='1']").click()      # round the ring to the first again
    view.locator(".mx-tile-flight [data-flip='-1']").click()
    assert cents(total.inner_text()) == first and view.locator("input[data-pick='fl']").first.input_value() == "0"
    assert page.errors == []


def test_book_this_trip_books_the_chosen_flight_and_hotel_and_the_pass_shows_them(matrix, alt):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    view = open_square(page, DESKTOP)
    view.locator(".mx-tile-stay [data-flip='1']").click()
    view.locator(".mx-tile-flight [data-flip='1']").click()
    view.locator(".mx-book").click()
    sheet = page.locator(".mxb-sheet")
    expect(sheet).to_be_visible()
    fill(page)
    to_review(page)
    expect(sheet.locator("[data-card='review']")).to_contain_text("Cheaper San Diego Inn")
    expect(sheet.locator("[data-card='review']")).to_contain_text("Nuitée Air")
    page.click(".mxb-go")
    expect(sheet.locator(".mxb-stamp")).to_have_text("Sample")
    expect(sheet.locator(".mxb-pass")).to_contain_text("Cheaper San Diego Inn")
    expect(sheet.locator(".mxb-pass")).to_contain_text("Nuitée Air · 1 stop")
    assert page.errors == []


def test_book_this_trip_is_the_boldest_thing_and_on_a_phone_it_stays_in_reach(matrix, alt):  # noqa: F811
    page = matrix(PHONE, signed_in=True)
    view = open_square(page, PHONE)
    page.wait_for_timeout(500)
    book = view.locator(".mx-book")
    box = book.bounding_box()
    assert box["height"] >= 60 and box["y"] + box["height"] <= PHONE["height"] + 1          # big, and in the screen without scrolling (the sticky bar)
    biggest = page.evaluate("""() => { const q = e => e.getBoundingClientRect(), b = q(document.querySelector('.mx-sheet .mx-book')); return [...document.querySelectorAll('.mx-sheet button, .mx-sheet a')]
        .filter(e => e.offsetParent && !e.matches('.mx-book')).every(e => q(e).width * q(e).height < b.width * b.height); }""")
    assert biggest
    page.evaluate("document.querySelector('.mx-sheet').scrollTop = 9999")
    page.wait_for_timeout(200)
    box = book.bounding_box()
    assert box["y"] + box["height"] <= PHONE["height"] + 1 and book.is_visible()                  # still there at the bottom of the sheet
    colours = page.evaluate("() => { const s = getComputedStyle(document.querySelector('.mx-sheet .mx-book')); return [s.backgroundColor, s.color]; }")
    assert colours == ["rgb(255, 212, 59)", "rgb(23, 20, 10)"]                                      # the yellow, dark on it in both modes


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_opened_square_and_the_checkout_read_fit_and_are_easy_to_tap_in_light_and_dark(matrix, alt, viewport, scheme):  # noqa: F811
    page = matrix(viewport, signed_in=True, scheme=scheme)
    view = open_square(page, viewport)
    page.wait_for_timeout(700)
    if viewport is PHONE:      # the audit reads what is drawn under a sheet too: look at the sheet alone (the matrix behind it has its own audit, test_tripmatrix.py)
        page.add_style_tag(content="#mx { visibility: hidden; }")
    seen = audit(page)
    for key in ("small", "tiny", "low", "glass"):
        assert not seen[key], ("the square", key, seen[key][:6])
    assert seen["wide"] <= 1
    view.locator(".mx-book").click()
    expect(page.locator(".mxb-sheet")).to_be_visible()
    page.wait_for_timeout(900)
    page.add_style_tag(content="#mx, .mx-sheet, .mx-scrim { visibility: hidden; }")      # the checkout alone
    seen = audit(page)
    for key in ("small", "tiny", "low", "glass"):
        assert not seen[key], ("the checkout", key, seen[key][:6])
    to_review(page)
    page.click(".mxb-go")
    expect(page.locator(".mxb-id").first).to_contain_text("SAMPLE-")
    page.wait_for_timeout(900)
    seen = audit(page)
    for key in ("small", "tiny", "low", "glass"):
        assert not seen[key], ("the pass", key, seen[key][:6])
    shot(page, f"{viewport['width']}-{scheme}-pass")
