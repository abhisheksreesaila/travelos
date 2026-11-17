"""F-251 in a real browser (replaces F-242's opened-square view): the drawer. A square opens the prototype's drawer under the matrix, on a laptop (1440) and on a phone (390): the hotel and the
flight one at a time (F-258: the stay first, the flights a summary that opens in place), the gallery, the rooms, other stays and flights. Choosing in place moves the total by exactly the difference (it counts there) and the
forms carry only indexes; Book my trip then books what was chosen. A stand-in source gives each square three flights, three stays and three rooms a stay. Set F251_SHOTS=1 for docs/report/f251-*.png, F258_SHOTS=1 for f258-*.png."""
import os
from dataclasses import replace
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import gridsource, liteapi, tripmatrix as tm
from tests_browser.helpers import DESKTOP, PHONE, set_mode
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


def shot(page, name, ticket="f251"):
    if os.environ.get(ticket.upper() + "_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"{ticket}-{name}.png"))


def cents(text):
    return int(round(float(text.replace("$", "").replace(",", "")) * 100))


def look(view, who):
    """Looking at one side shows it: where it is a summary (F-258: one side is open at a time), a tap on the summary opens it."""
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
    assert cents(view.locator("[data-znav-total]").inner_text()) == first - 20_000 + 50_000 + 30_000      # F-283 review: the sticky nav's Total follows every choice too
    assert cents(view.locator("[data-mirror='total']").inner_text()) == first - 20_000 + 50_000 + 30_000
    assert [view.locator(f"input[data-pick='{k}']").first.input_value() for k in ("fl", "st", "rm")] == ["1", "2", "2"]      # only indexes travel
    assert view.locator("[data-vs]").count() == 0 or view.locator("[data-vs]").first.is_hidden()           # "vs San Diego" was for the trip shown first
    shot(page, f"{viewport['width']}-switched")
    view.locator(".dr-alt[data-hotel='0']").click()
    look(view, "fly")
    view.locator(".dr-opt[data-fl='0']").click()
    page.wait_for_function(f"() => document.querySelector('[data-slot=total]').textContent === '${(first + 50) // 100:,}'")
    assert [view.locator(f"input[data-pick='{k}']").first.input_value() for k in ("fl", "st", "rm")] == ["0", "0", "0"]
    assert page.errors == []


def sides(view):
    """Which of the drawer's two sides is open (full) and which is a summary card, as the person sees them."""
    return {who: view.locator(f".dr-{who} .dr-full").is_visible() for who in ("stay", "fly")}, {who: view.locator(f".dr-{who} .dr-mini").is_visible() for who in ("stay", "fly")}


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_drawer_shows_the_stay_alone_and_the_flights_open_in_place_when_tapped(matrix, alt, viewport):  # noqa: F811
    """F-258: the stay first and alone, the flights a summary card (times, airline, nonstop, price); tapping it opens the flights and folds the stay to its summary, tapping that brings it back.
    Never both open, at any width, and choosing something never moves a side."""
    w = viewport["width"]
    page = matrix(viewport, signed_in=True)
    view = open_square(page, viewport)
    page.wait_for_timeout(1000)
    assert sides(view) == ({"stay": True, "fly": False}, {"stay": False, "fly": True})
    mini = view.locator(".dr-fly .dr-mini")
    expect(mini).to_contain_text("Test Air")
    expect(mini).to_contain_text("nonstop")
    expect(mini).to_contain_text(" out")
    expect(mini).to_contain_text("$")
    first = view.locator("[data-slot='total']").inner_text()
    view.locator(".dr-alt[data-hotel='1']").click()      # choosing a hotel opens nothing else
    view.locator(".dr-rooms:not([hidden]) .dr-opt[data-room='1']").click()
    assert sides(view)[0] == {"stay": True, "fly": False}
    assert view.locator("[data-slot='total']").inner_text() != first
    view.locator(".dr-alt[data-hotel='0']").click()
    shot(page, f"drawer-stay-{w}", "f258")
    mini.click()
    page.wait_for_timeout(700)
    assert sides(view) == ({"stay": False, "fly": True}, {"stay": True, "fly": False})
    expect(view.locator(".dr-stay .dr-mini")).to_contain_text("$")
    shot(page, f"drawer-flights-{w}", "f258")
    view.locator(".dr-opt[data-fl='1']").click()      # choosing a flight keeps the flights open
    assert sides(view)[0] == {"stay": False, "fly": True}
    expect(view.locator(".dr-stay .dr-mini")).to_be_visible()
    view.locator(".dr-stay .dr-mini").click()      # the stay's summary brings it back
    page.wait_for_timeout(700)
    assert sides(view) == ({"stay": True, "fly": False}, {"stay": False, "fly": True})
    expect(view.locator(".dr-fly .dr-mini")).to_contain_text("Nuitée Air")      # the summary follows the choice
    assert page.errors == []


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_opening_the_drawer_and_choosing_in_it_moves_no_focus_and_no_side(matrix, alt, viewport):  # noqa: F811
    """F-258 ("autofocus is irritating"): opening the drawer leaves the keyboard focus where it was, and neither touching an option nor the gallery nor looking around
    ever opens the other side; only a tap on a summary does."""
    page = matrix(viewport, signed_in=True)
    page.locator(".mx-lane[data-lane='sandiego'] .mx-sq").nth(2).click()
    expect(page.locator("#mx-drawer .dr-book")).to_be_visible()
    page.wait_for_timeout(1000)
    assert page.evaluate("() => !document.activeElement.closest('#mx-drawer')")      # focus did not move into the drawer
    view = page.locator("#mx-drawer")
    before = sides(view)
    for sel in (".dr-alt[data-hotel='2']", ".dr-rooms:not([hidden]) .dr-opt[data-room='1']", ".dr-alt[data-hotel='0']"):
        view.locator(sel).dispatch_event("pointerdown")
        view.locator(sel).click()
        page.wait_for_timeout(500)
        assert sides(view) == before
    assert page.evaluate("() => document.querySelectorAll('.dr-pn:not(.is-mini)').length") == 1
    assert page.errors == []


def test_the_gallery_is_samples_or_the_hotels_own_photo_or_the_places_drawing_each_labelled_and_it_scrolls(matrix, alt):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    view = open_square(page, DESKTOP)
    slides = view.locator(".dr-hotel:not([hidden]) .dr-slide")
    expect(slides).to_have_count(6)      # a sample hotel: five generic hotel pictures, each said to be a sample (F-275), then the place's drawing, labelled
    expect(slides.first.locator(".dr-cap")).to_have_text("Sample photo · Hotel lobby")
    expect(slides.last.locator(".dr-cap")).to_have_text("Illustration, not the hotel’s photo")
    assert view.locator(".dr-hotel:not([hidden]) .dr-nav").count() == 2                  # more than one: arrows
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


# ---- F-283 (D-920..D-924): the zones, the mini-nav and the rooms row ----
def rect(page, sel):
    return page.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height, width: r.width}; }", sel)


def current(page):
    return page.evaluate("() => [...document.querySelectorAll('.dr-znav [aria-current=\"true\"]')].map(a => a.dataset.znav)")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_stay_and_flights_are_two_zones_each_with_its_band_and_a_divider_between(matrix, alt, viewport, scheme):  # noqa: F811
    page = matrix(viewport, signed_in=True)
    set_mode(page, scheme)      # the site's dark is localStorage `ga-mode`, not the browser's colour scheme
    view = open_square(page, viewport)
    page.wait_for_timeout(900)
    expect(view.locator(".dr-zband.k-stay")).to_contain_text("Your stay")
    expect(view.locator(".dr-zband.k-stay")).to_contain_text("Test Stay San Diego · 4 nights")
    expect(view.locator(".dr-zband.k-flight")).to_contain_text("Your flights")
    expect(view.locator(".dr-zband.k-flight")).to_contain_text("SFO ⇄ SAN · 4 people")
    expect(view.locator(".dr-gap")).to_be_visible()
    stay, gap, fly = rect(page, ".dr-stay"), rect(page, ".dr-gap"), rect(page, ".dr-fly")
    assert stay["bottom"] <= gap["top"] + 1 and gap["bottom"] <= fly["top"] + 1 and gap["height"] >= 24, (stay, gap, fly)      # a divider of its own, between the two
    colours = page.evaluate("() => ['.dr-stay .dr-zi', '.dr-fly .dr-zi'].map(s => getComputedStyle(document.querySelector(s)).backgroundColor)")
    assert colours[0] != colours[1] and "rgba(0, 0, 0, 0)" not in colours, colours      # each its own accent
    expect(view.locator(".dr-fly .dr-zband")).to_be_visible()      # the band stays when its zone is a summary
    page.add_style_tag(content="#mx .mx-card, #mx-rail, .v2-hero, .dr-sampleslot { visibility: hidden; }")      # the bands, the nav and the rooms alone (the sample dashboard's loading line has its own colour check)
    seen = audit(page)
    for key in ("small", "tiny", "low", "glass"):
        assert not seen[key], ("the zones", key, seen[key][:6])
    assert seen["wide"] <= 1
    shot(page, f"{viewport['width']}-{scheme}-zones", "f283")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_mini_nav_shows_the_zone_you_are_in_and_jumps_there_and_book_focuses_the_foots_book(matrix, alt, viewport):  # noqa: F811
    page = matrix(viewport, signed_in=True)
    view = open_square(page, viewport)
    page.wait_for_timeout(900)
    items = view.locator(".dr-znav a")
    assert [t.strip() for t in items.all_inner_texts()][:2] == ["Stay", "Flights"] and items.count() == 4
    assert min(page.evaluate("() => [...document.querySelectorAll('.dr-znav a')].filter(a => a.offsetParent).map(a => a.getBoundingClientRect().height)")) >= 47.5      # 48px targets (of the ones shown)
    assert current(page) == ["stay"]
    items.nth(1).click()      # Flights: scrolls to its zone and the nav says so
    page.wait_for_function("() => document.querySelector('.dr-znav [data-znav=fly]').getAttribute('aria-current') === 'true'")
    nav, zone = rect(page, ".dr-znav"), rect(page, ".dr-fly")
    assert 0 <= nav["top"] < 60 and nav["bottom"] <= zone["top"] + 4 and zone["bottom"] <= viewport["height"] + 1, (nav, zone)      # the nav stuck to the top; the zone in view under it (the page's end may stop it short of the top)
    assert current(page) == ["fly"]
    items.nth(0).click()
    page.wait_for_function("() => document.querySelector('.dr-znav [data-znav=stay]').getAttribute('aria-current') === 'true'")
    assert current(page) == ["stay"] and rect(page, ".dr-stay")["top"] < 200
    forms = page.evaluate("() => document.querySelectorAll('#mx-drawer form[action$=\"/plan/matrix/book\"]').length")
    zbook = view.locator(".dr-zbook")
    if viewport is DESKTOP:      # F-293 founder call: one Book on a laptop, the sticky foot's, always in view there; the nav does not repeat it
        assert not zbook.is_visible() and view.locator(".dr-book").is_visible()
        assert forms == 1 and page.errors == []
        return
    zbook.click()      # Book on a phone: the foot's own Book gets the focus; it is not a second form
    page.wait_for_function("() => document.activeElement && document.activeElement.classList.contains('dr-book')")
    assert forms == 1 and page.locator(".mxb-sheet").count() == 0 and page.errors == []


def test_the_nav_names_the_zone_by_an_observer_not_a_scroll_handler(matrix, alt):  # noqa: F811
    js = (Path(__file__).resolve().parent.parent / "assets" / "js" / "v2drawer.js").read_text()
    assert "IntersectionObserver" in js and "znav" in js
    scrolls = [ln for ln in js.splitlines() if "addEventListener('scroll'" in ln]
    assert len(scrolls) == 1 and "the gallery's dots" in scrolls[0]      # the one scroll listener there is the gallery's dots; neither the nav nor the rooms row has one


def test_on_a_phone_the_mini_nav_never_sits_under_the_floating_bar_or_off_the_screen(matrix, alt):  # noqa: F811
    page = matrix(PHONE, signed_in=True)
    open_square(page, PHONE)
    page.wait_for_timeout(900)
    height = page.evaluate("() => document.documentElement.scrollHeight")
    checked = 0
    for y in range(0, height, 250):
        page.evaluate("(y) => window.scrollTo(0, y)", y)
        page.wait_for_timeout(120)
        got = page.evaluate("""() => { const n = document.querySelector('.dr-znav').getBoundingClientRect(), b = document.querySelector('.v2-sections').getBoundingClientRect(), d = document.querySelector('#mx-drawer .dr').getBoundingClientRect(), h = document.querySelector('#mx-drawer .dr-head').getBoundingClientRect();
            return {stuck: h.bottom < 0 && d.bottom > n.height + 40, overlap: n.top < b.bottom && n.bottom > b.top && n.left < b.right && n.right > b.left, on: n.top >= 0 && n.bottom <= innerHeight, top: n.top}; }""")
        if got["stuck"]:      # while the drawer is read the nav is stuck at the top of the screen, a whole screen above the floating bar
            checked += 1
            assert not got["overlap"] and got["on"] and got["top"] < 20, (y, got)
    assert checked >= 3
    page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")      # at the foot of the page the nav is still clear of the bar
    page.wait_for_timeout(150)
    assert page.evaluate("""() => { const n = document.querySelector('.dr-znav').getBoundingClientRect(), b = document.querySelector('.v2-sections').getBoundingClientRect();
        return !(n.top < b.bottom && n.bottom > b.top && n.left < b.right && n.right > b.left); }""")
    assert page.errors == []


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_every_room_is_in_a_scroll_snap_row_with_a_count_and_the_chosen_one_marked(matrix, alt, viewport):  # noqa: F811
    page = matrix(viewport, signed_in=True)
    view = open_square(page, viewport)
    page.wait_for_timeout(900)
    row = ".dr-rooms:not([hidden]) .dr-rrow"
    expect(view.locator(".dr-rooms:not([hidden]) .dr-rn")).to_have_text("3 room types")
    assert view.locator(f"{row} .dr-opt").count() == 3
    css = page.evaluate("(s) => { const e = document.querySelector(s), c = getComputedStyle(e); return [c.scrollSnapType, c.overflowX, c.display]; }", row)
    assert css[0].startswith("x ") and css[1] in ("auto", "scroll") and css[2] in ("flex", "grid"), css
    expect(view.locator(f"{row} .dr-opt[aria-checked='true']")).to_have_count(1)
    expect(view.locator(f"{row} .dr-opt[aria-checked='true'] .dr-d")).to_have_text("Chosen")
    assert min(page.evaluate("(s) => [...document.querySelectorAll(s + ' .dr-opt')].map(e => e.getBoundingClientRect().height)", row)) >= 47.5
    view.locator(f"{row} .dr-opt[data-room='1']").click()      # choosing still sets the index that tm.pick reads
    assert view.locator("input[data-pick='rm']").first.input_value() == "1"
    expect(view.locator(f"{row} .dr-opt[data-room='1']")).to_have_attribute("aria-checked", "true")
    shot(page, f"{viewport['width']}-rooms", "f283")


def test_on_a_laptop_the_arrows_show_only_when_the_row_overflows_and_move_it(matrix, alt):  # noqa: F811
    page = matrix(DESKTOP, signed_in=True)
    view = open_square(page, DESKTOP)
    page.wait_for_timeout(900)
    prev, nxt = view.locator(".dr-rooms:not([hidden]) [data-rarr='-1']"), view.locator(".dr-rooms:not([hidden]) [data-rarr='1']")
    expect(nxt).to_be_visible()
    expect(prev).to_be_disabled()      # at the start there is nothing earlier
    assert min(rect(page, ".dr-rooms:not([hidden]) [data-rarr='1']")["height"], rect(page, ".dr-rooms:not([hidden]) [data-rarr='1']")["width"]) >= 47.5
    nxt.click()
    page.wait_for_function("() => document.querySelector('.dr-rooms:not([hidden]) .dr-rrow').scrollLeft > 40")      # reduced motion: it jumps
    expect(prev).to_be_enabled()
    page.add_style_tag(content=".dr-rrow .dr-opt { flex: 0 0 4rem !important; }")      # a row that fits needs no arrows
    page.wait_for_function("() => document.querySelector('.dr-rooms:not([hidden]) [data-rarr=\"1\"]').hidden")
    expect(prev).to_be_hidden()


def test_on_a_phone_the_row_is_swiped_and_has_no_arrows_and_a_swipe_lands_on_a_room(matrix, alt):  # noqa: F811
    page = matrix(PHONE, signed_in=True)
    view = open_square(page, PHONE)
    page.wait_for_timeout(900)
    expect(view.locator(".dr-rooms:not([hidden]) [data-rarr]")).to_have_count(2)
    assert not any(page.evaluate("() => [...document.querySelectorAll('.dr-rooms:not([hidden]) [data-rarr]')].map(a => a.getBoundingClientRect().width > 0)"))
    page.evaluate("() => { document.querySelector('.dr-rooms:not([hidden]) .dr-rrow').scrollTo({left: 150, behavior: 'instant'}); }")
    page.wait_for_timeout(400)
    off = page.evaluate("""() => { const r = document.querySelector('.dr-rooms:not([hidden]) .dr-rrow'), rr = r.getBoundingClientRect();
        return [r.scrollLeft, Math.min(...[...r.children].map(c => Math.abs(c.getBoundingClientRect().left - rr.left)))]; }""")
    assert off[0] > 0 and off[1] <= 18, off      # it snapped: a room's edge sits at the row's edge
    assert page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")
