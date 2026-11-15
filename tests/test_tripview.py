"""F-242: the opened square as one trip view, and the choice made on it. The view draws every flight and stay the source gave as options of a tile (the shown one first) and carries
the choice as indexes in its forms; the booking reads them again, prices the chosen trip itself, binds a held room to its choice and books what was chosen. A forged index is the
shown part. The browser flipping and the total moving are in tests_browser/test_tripview.py."""
import re
from html import unescape

from gitaway import catalog, gridsource, tripmatrix as tm
from gitaway.pages import tripmatrix as page
from tests.test_matrixbook_page import FORM, GUEST, FRAG, _fresh, sample  # noqa: F401 (fixtures)
from tests.test_signin import sign_in
from tests.test_tripmatrix_page import MATRIX

SQUARE = "/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12"


def square():
    s = page.state(*(FORM[k] for k in ("to", "home", "d", "r", "a", "k", "x")))
    lane, w, sq, _ = page._square_of(s, "sandiego", "2026-12-12")
    return sq


def test_the_view_has_the_hotel_the_flight_the_sky_and_the_total_and_a_bold_book_button(sample, client):
    html = unescape(client.get(SQUARE).text)
    sq = square()
    assert 'class="mx-book"' in html and "Book this trip" in html and html.index("Book this trip") > html.index("Total for the trip")
    assert sq.stays[0].name in html and "Typical mid December" in html
    assert tm.dollars(sq.cents) in html and html.count('data-slot="total"') == 1
    assert 'name="fl" value="0"' in html and 'name="st" value="0"' in html
    assert html.count('class="mx-tile ') == 2 and html.count("1 of 3") == 2                      # a hotel tile and a flight tile, each with three to choose from


def test_every_option_the_source_gave_is_drawn_with_its_own_price_and_only_the_first_is_visible(sample, client):
    html = unescape(client.get(SQUARE).text)
    sq = square()
    options = re.findall(r'<div [^>]*class="mx-opt"[^>]*>', html)
    assert len(options) == 6 and [" hidden" in o for o in options] == [False, True, True] * 2      # the shown one first in each tile, two waiting behind it
    cents = [int(re.search(r'data-c="(\d+)"', o).group(1)) for o in options]
    assert cents[3:] == [f.cents for f in sq.flights] or cents[:3] == [f.cents for f in sq.flights]
    for alt in sq.stay_alts[0]:
        assert alt.name in html and f'data-c="{alt.cents}"' in html


def test_a_square_with_no_choice_has_no_arrows(sample, client):
    html = client.get("/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=orangecounty&w=2026-12-12").text
    assert "mx-flip" not in html and "Book this trip" in html


def test_a_still_searching_square_has_no_total_and_no_buttons(sample, client, monkeypatch):
    s = page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    lane, w, *_ = page._square_of(s, "sandiego", "2026-12-12")
    html = unescape(str(page.panel(s, lane, w, None)))
    assert "Searching this square" in html and "mx-book" not in html and 'data-slot="total"' not in html


def book_page(client, **over):
    return client.post("/plan/matrix/book", data={**FORM, **over}, headers=FRAG).text


def test_booking_a_switched_flight_and_stay_books_and_shows_the_chosen_ones_at_their_price(sample, client):
    sign_in(client)
    sq = square()
    chosen = tm.pick(sq, 1, (2,))
    html = unescape(book_page(client, fl="1", st="2"))
    assert chosen.stays[0].name in html and chosen.flight.airline in html and sq.stays[0].name not in html
    assert catalog.money(chosen.cents) in html and 'name="fl" value="1"' in html and 'name="st" value="2"' in html
    token = re.search(r'name="token" value="([^"]+)"', html).group(1)
    done = unescape(client.post("/plan/matrix/book/confirm", data={**FORM, "fl": "1", "st": "2", "token": token, **GUEST}, headers=FRAG).text)
    assert chosen.stays[0].name in done and chosen.flight.airline in done and "Plan this trip" in done and "SAMPLE-" in done


def test_a_room_held_for_one_choice_is_not_booked_as_another(sample, client):
    sign_in(client)
    html = book_page(client, fl="0", st="0")
    token = re.search(r'name="token" value="([^"]+)"', html).group(1)
    refused = unescape(client.post("/plan/matrix/book/confirm", data={**FORM, "fl": "0", "st": "1", "token": token, **GUEST}, headers=FRAG).text)
    assert "That room check has expired or is not for this square" in refused and "SAMPLE-" not in refused


def test_a_forged_choice_is_the_shown_trip(sample, client):
    sign_in(client)
    sq = square()
    html = unescape(book_page(client, fl="99", st="x"))
    assert sq.stays[0].name in html and 'name="fl" value="0"' in html and 'name="st" value="0"' in html
