"""F-251 in a real browser (replaces F-242's opened-square view): the drawer. A square opens the prototype's drawer under the matrix, on a laptop (1440) and on a phone (390): the hotel and the
flight side by side, Focus shrinking the other to a summary, the gallery, the rooms, other stays and flights. Choosing in place moves the total by exactly the difference (it counts there) and the
forms carry only indexes; Book my trip then books what was chosen. A stand-in source gives each square three flights, three stays and three rooms a stay. Set F251_SHOTS=1 for docs/report/f251-*.png."""
import os
from dataclasses import replace
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import gridsource, liteapi, tripmatrix as tm
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit
from tests_browser.test_matrixbook_sheet import BookStand, _no_presses_yet, fill, open_square, states, to_review  # noqa: F401 (fixtures and helpers)
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"


class AltStand(BookStand):
    """The fixed table's squares with two more flights, two more stays and three rooms a stay behind the shown ones (cheaper and dearer), so there is something to switch to."""

    def __call__(self, *a, **k):
        sq = super().__call__(*a, **k)
        if sq is None or not sq.ok:
            return sq
        flights = (sq.flight, replace(sq.flight, airline="Nuitée Air", stops=1, cents=sq.flight.cents - 20_000), replace(sq.flight, airline="Skylark Air", cents=sq.flight.cents + 8_000))

        def rooms(st):
            return tuple(tm.RoomPart(n, st.board, st.refundable, st.due_at_stay_cents, st.cents + extra, st.offer_id) for n, extra in ((st.room, 0), ("Deluxe king", 12_000), ("Family suite", 30_000)))
        shown = replace(st := sq.stays[0], rooms=rooms(st))
        alts = [(shown, replace(st, name=f"Cheaper {st.place} Inn", cents=st.cents - 30_000, photo="", rating="8.1 of 10"),
                 replace(st, name=f"Grand {st.place} Resort", cents=st.cents + 50_000, address="1 Harbor Way, San Diego, CA"))]
        alts[0] = tuple(replace(x, rooms=rooms(x)) for x in alts[0])
        out = [alts[0]] + [(replace(x, rooms=rooms(x)),) for x in sq.stays[1:]]
        return replace(sq, flights=flights, stays=tuple(a[0] for a in out), stay_alts=tuple(out))


@pytest.fixture
def alt(monkeypatch, stand):  # noqa: F811
    monkeypatch.setattr(gridsource, "SQUARE", AltStand(sample=True))
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: (_ for _ in ()).throw(AssertionError("LiteAPI was asked")))


def shot(page, name):
    if os.environ.get("F251_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f251-{name}.png"))


def cents(text):
    return int(round(float(text.replace("$", "").replace(",", "")) * 100))


def look(view, who):
    """Looking at one side shows it: where it is a summary (the other side has focus), a tap on the summary brings it back."""
    if view.locator(f".dr-pn.dr-{who}.is-mini").count():
        view.locator(f".dr-{who} .dr-mini").click()


def chosen(view, kind):
    return view.locator(f".dr-{kind} .dr-opt[aria-checked='true']")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_choosing_a_flight_a_hotel_and_a_room_in_place_moves_the_total_by_the_difference(matrix, alt, viewport):  # noqa: F811
    page = matrix(viewport, signed_in=True)
    view = open_square(page, viewport)
    total = view.locator("[data-slot='total']")
    first = cents(total.inner_text())
    look(view, "fly")      # on a phone the flight is a one-line summary until you tap it
    view.locator(".dr-opt[data-fl='1']").click()
    expect(chosen(view, "fly")).to_contain_text("Nuitée Air")
    page.wait_for_function(f"() => document.querySelector('[data-slot=total]').textContent === '${(first - 20_000 + 50) // 100:,}'")
    assert cents(view.locator("[data-mirror='total']").inner_text()) == first - 20_000                      # the Book button's total follows
    look(view, "stay")      # touching the flight focused it: the hotel is a summary now
    view.locator(".dr-alt[data-hotel='2']").click()
    expect(view.locator(".dr-hotel:not([hidden]) .dr-hname")).to_have_text("Grand San Diego Resort")
    expect(view.locator(".dr-hotel:not([hidden]) .dr-hmeta")).to_contain_text("1 Harbor Way, San Diego, CA")
    page.wait_for_function(f"() => document.querySelector('[data-slot=total]').textContent === '${(first - 20_000 + 50_000 + 50) // 100:,}'")
    view.locator(".dr-rooms:not([hidden]) .dr-opt[data-room='2']").click()      # that hotel's third room: $300 more
    page.wait_for_function(f"() => document.querySelector('[data-slot=total]').textContent === '${(first - 20_000 + 50_000 + 30_000 + 50) // 100:,}'")
    assert [view.locator(f"input[data-pick='{k}']").first.input_value() for k in ("fl", "st", "rm")] == ["1", "2", "2"]      # only indexes travel
    assert view.locator("[data-vs]").count() == 0 or view.locator("[data-vs]").first.is_hidden()           # "vs San Diego" was for the trip shown first
    shot(page, f"{viewport['width']}-switched")
    view.locator(".dr-alt[data-hotel='0']").click()
    look(view, "fly")
    view.locator(".dr-opt[data-fl='0']").click()
    page.wait_for_function(f"() => document.querySelector('[data-slot=total]').textContent === '${(first + 50) // 100:,}'")
    assert [view.locator(f"input[data-pick='{k}']").first.input_value() for k in ("fl", "st", "rm")] == ["0", "0", "0"]
    assert page.errors == []


def test_focus_shrinks_the_other_side_to_a_summary_and_touching_a_side_focuses_it(matrix, alt):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    view = open_square(page, DESKTOP)
    panels = view.locator(".dr-panels")
    assert panels.get_attribute("data-focus") == "" and view.locator(".dr-pn.is-mini").count() == 0           # side by side
    shot(page, "1440-drawer")
    view.locator(".dr-stay .dr-fbtn").click()
    assert panels.get_attribute("data-focus") == "stay"
    expect(view.locator(".dr-fly")).to_have_class("dr-pn dr-fly is-mini")
    expect(view.locator(".dr-fly .dr-mini")).to_contain_text("Test Air")
    expect(view.locator(".dr-stay .dr-fbtn")).to_have_text("Side by side")
    page.wait_for_timeout(900)
    shot(page, "1440-stay-focus")
    view.locator(".dr-fly .dr-mini").click()      # tapping the summary shows it
    assert panels.get_attribute("data-focus") == "fly" and view.locator(".dr-stay.is-mini").count() == 1
    page.wait_for_timeout(900)
    shot(page, "1440-flight-focus")
    view.locator(".dr-fly .dr-fbtn").click()
    assert panels.get_attribute("data-focus") == ""
    view.locator(".dr-opt[data-fl='1']").click()      # touching an option on the flight side focuses it
    page.wait_for_function("() => document.querySelector('.dr-panels').dataset.focus === 'fly'")
    assert page.errors == []


def test_the_gallery_is_the_hotels_own_photo_or_the_places_drawing_labelled_and_it_scrolls(matrix, alt):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    view = open_square(page, DESKTOP)
    slides = view.locator(".dr-hotel:not([hidden]) .dr-slide")
    expect(slides).to_have_count(1)      # the stand's hotel has no photo: the place's drawing only, and it says so
    expect(slides.first.locator(".dr-cap")).to_have_text("Illustration, not the hotel’s photo")
    assert view.locator(".dr-nav").count() == 0                                          # nothing to go through, no arrows
    shot(page, "1440-gallery")


def test_the_drawer_grows_down_out_of_the_square_and_closes_with_its_button_and_escape(matrix, alt):  # noqa: F811
    page = matrix(DESKTOP, motion=True, signed_in=True)
    sq = page.locator(".mx-lane[data-lane='sandiego'] .mx-sq").nth(2)
    sq.click()
    page.wait_for_function("() => document.querySelector('#mx-drawer .dr') && document.getAnimations().some(a => a.effect && a.effect.target && a.effect.target.classList.contains('dr'))")
    clip = page.evaluate("() => { const a = document.getAnimations().find(a => a.effect.target.classList.contains('dr')); return a.effect.getKeyframes()[0].clipPath; }")
    assert clip.startswith("inset(0px") and "round" in clip and clip != "inset(0px 0px 0px 0px round 32px)"      # a clip from the square's column, not the whole card
    page.wait_for_timeout(1200)
    expect(page.locator("#mx-drawer .dr")).to_be_visible()
    page.locator("#mx-drawer [data-act='close']").click()
    expect(page.locator("#mx-drawer")).to_be_hidden()
    sq.click()
    expect(page.locator("#mx-drawer .dr")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#mx-drawer")).to_be_hidden()
    assert page.errors == []


def test_book_my_trip_books_the_chosen_flight_hotel_and_room_and_the_pass_shows_them(matrix, alt):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    view = open_square(page, DESKTOP)
    view.locator(".dr-alt[data-hotel='1']").click()
    look(view, "fly")
    view.locator(".dr-opt[data-fl='1']").click()
    view.locator(".dr-book").click()
    sheet = page.locator(".mxb-sheet")
    expect(sheet).to_be_visible()
    fill(page)
    to_review(page)
    expect(sheet.locator("[data-pane='3']")).to_contain_text("Cheaper San Diego Inn")
    expect(sheet.locator("[data-pane='3']")).to_contain_text("Nuitée Air")
    page.click(".mxb-agree")
    page.click(".mxb-go")
    expect(sheet.locator(".mxb-stamp")).to_have_text("Sample")
    expect(sheet.locator(".mxb-pass")).to_contain_text("Cheaper San Diego Inn")
    expect(sheet.locator(".mxb-pass")).to_contain_text("Nuitée Air · 1 stop")
    assert page.errors == []


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_drawer_and_the_questions_read_fit_and_are_easy_to_tap_in_light_and_dark(matrix, alt, viewport, scheme):  # noqa: F811
    page = matrix(viewport, signed_in=True, scheme=scheme)
    view = open_square(page, viewport)
    page.wait_for_timeout(900)
    page.add_style_tag(content="#mx .mx-card, #mx-rail, .v2-hero { visibility: hidden; }")      # the drawer alone (the matrix and the rail have their own audits)
    seen = audit(page)
    for key in ("small", "tiny", "low", "glass"):
        assert not seen[key], ("the drawer", key, seen[key][:6])
    assert seen["wide"] <= 1
    view.locator(".dr-book").click()
    expect(page.locator(".mxb-sheet")).to_be_visible()
    page.wait_for_timeout(900)
    page.add_style_tag(content="#mx, .mxb-scrim { visibility: hidden; }")      # the checkout alone
    seen = audit(page)
    for key in ("small", "tiny", "low", "glass"):
        assert not seen[key], ("the checkout", key, seen[key][:6])
    fill(page)
    to_review(page)
    page.click(".mxb-agree")
    page.click(".mxb-go")
    expect(page.locator(".mxb-id").first).to_contain_text("SAMPLE-")
    page.wait_for_timeout(1200)
    seen = audit(page)
    for key in ("small", "tiny", "wide"):
        assert not seen[key] if key != "wide" else seen[key] <= 1, ("the pass", key, seen[key][:6] if key != "wide" else seen[key])
    shot(page, f"{viewport['width']}-{scheme}-pass")
