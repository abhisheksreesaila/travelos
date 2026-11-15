"""F-242: the opened square as one trip view, and the choice made on it. The view draws every flight and stay the source gave as options of a tile (the shown one first) and carries
the choice as indexes in its forms; the booking reads them again, prices the chosen trip itself, binds a held room to its choice and books what was chosen. A forged index is the
shown part. The browser flipping and the total moving are in tests_browser/test_tripview.py."""
import re
from html import unescape

from gitaway import catalog, tripmatrix as tm
from gitaway.pages import tripmatrix as page
from tests.test_matrixbook_page import FORM, GUEST, FRAG, _fresh, sample  # noqa: F401 (fixtures)
from tests.test_signin import sign_in
from tests.test_tripmatrix_page import MATRIX

SQUARE = "/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12"


def square():
    s = page.state(*(FORM[k] for k in ("to", "home", "d", "r", "a", "k", "x")))
    lane, w, sq, _ = page._square_of(s, "sandiego", "2026-12-12")
    return sq


def test_the_drawer_has_the_hotel_the_flight_the_why_and_the_total_and_a_bold_book_button(sample, client):
    html = unescape(client.get(SQUARE).text)
    sq = square()
    assert 'class="dr-book"' in html and "Book my trip" in html and html.index("Book my trip") > html.index('data-slot="total"')
    assert sq.stays[0].name in html and "typically sunny" in html
    assert tm.dollars(sq.cents) in html and html.count('data-slot="total"') == 1 and html.count('data-mirror="total"') == 1
    assert 'name="fl" value="0"' in html and 'name="st" value="0"' in html and 'name="rm" value="0"' in html
    assert html.count("dr-pn dr-") == 2 and "Illustration, not the hotel’s photo" in html      # a stay panel and a flight panel; the gallery says what it is


def test_every_hotel_room_and_flight_the_source_gave_is_drawn_with_its_own_price_and_only_the_first_is_shown(sample, client):
    html = unescape(client.get(SQUARE).text)
    sq = square()
    hotels = re.findall(r'<div [^>]*class="dr-hotel"[^>]*>', html)
    assert len(hotels) == 3 and [" hidden" in h for h in hotels] == [False, True, True]      # the shown hotel first, two waiting behind it
    alts = [int(c) for c in re.findall(r'<button[^>]*data-c="(\d+)"[^>]*class="dr-alt"', html)]
    assert alts == [x.cents for x in sq.stay_alts[0]]
    flights = [int(c) for c in re.findall(r'<button[^>]*data-fl="\d+" data-c="(\d+)"[^>]*class="dr-opt"', html)]
    assert flights == [f.cents for f in sq.flights]
    rooms = [int(c) for c in re.findall(r'<button[^>]*data-room="\d+" data-c="(\d+)"[^>]*class="dr-opt"', html)]
    assert rooms == [r.cents for st in sq.stay_alts[0] for r in st.rooms] and len(rooms) == 9      # three sample rooms at each of three hotels, the first the hotel's own price
    for alt in sq.stay_alts[0]:
        assert alt.name in html


def test_a_hotel_with_no_other_hotel_has_no_strip_of_them(sample, client):
    html = client.get("/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=orangecounty&w=2026-12-12").text
    assert "Other stays in" not in html and "dr-alts" not in html and "Book my trip" in html and "Deluxe room, king bed" in html


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


def test_a_held_room_is_used_only_while_the_square_still_names_the_same_rooms():
    """Security review of F-242: a square read again can put another hotel at the same pick; then the hold is stale, never booked under the new name."""
    from types import SimpleNamespace as N
    from gitaway.pages.matrixbook import _same_offers
    a, b, sample = N(offer_id="of-a", name="A", cents=1), N(offer_id="of-b", name="B", cents=1), N(offer_id="", name="Inn", cents=900)
    held = lambda *parts: N(rows=[N(part=p) for p in parts])
    assert _same_offers(N(stays=[a]), held(a)) and _same_offers(N(stays=[sample]), held(N(offer_id="", name="Inn", cents=900)))
    assert not _same_offers(N(stays=[b]), held(a)) and not _same_offers(N(stays=[N(offer_id="", name="Inn", cents=950)]), held(sample))


def test_a_two_place_trip_has_a_tab_and_a_pane_of_rooms_for_each_stay(sample, client):
    """Each place's stay is its own pane (a tab each), with its own hotels and rooms; the nights are each place's own."""
    html = unescape(client.get("/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=losangeles%2Bsandiego&w=2026-12-12").text)
    assert 'data-tab="0"' in html and 'data-tab="1"' in html and "Los Angeles · 2 nights" in html and "San Diego · 2 nights" in html and html.count('class="dr-stay-grid dr-sp"') == 2
    assert html.index("Los Angeles · 2 nights") < html.index("San Diego · 2 nights") and 'name="st" value="0,0"' in html and 'name="rm" value="0,0"' in html
