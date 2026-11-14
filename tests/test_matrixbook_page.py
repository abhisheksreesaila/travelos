"""F-233: the booking sheet on the trip matrix. POST /plan/matrix/book prebooks the square's stays and answers the sheet; POST /plan/matrix/book/confirm checks the lead guest,
makes the family's trip, books through LiteAPI's sandbox (answers recorded in tests/fixtures/liteapi) and answers the confirmation. On the showcase it is a sample booking and
LiteAPI is never asked. A viewer cannot book; nothing a guest typed comes back unescaped; the long offer id is never on a page."""
import re
from html import unescape

import pytest

from gitaway import familydb, liteapi, matrixbook as mb, session as ses
from gitaway.pages import tripmatrix as page
from tests.test_liteapi import KEY, Fake, raw
from tests.test_liteapi_book import BOOK, PREBOOK
from tests.test_signin import person, sign_in
from tests.test_tripmatrix_page import MATRIX

FORM = {"to": "San Diego", "home": "SFO", "d": "2026-12-12", "r": "2026-12-16", "a": "2", "k": "7,10", "x": "2", "lane": "sandiego", "w": "2026-12-12"}
GUEST = {"first": "Anne-Marie", "last": "O’Neil", "email": "anne@example.com"}
FRAG = {"X-Matrix": "1"}


class Sandbox(Fake):
    """The searches from the recordings and the booking calls from the recordings (prebook, book), each remembered."""

    def __init__(self, prebook=None, book=None):
        super().__init__()
        nights = lambda b: b.replace(b"2026-12-14", b"2026-12-12").replace(b"2026-12-17", b"2026-12-16")      # the recordings are of other dates: the square's nights  # noqa: E731
        self.prebook, self.book = prebook or (200, nights(raw("prebook.json"))), book or (200, nights(raw("book.json")))

    def __call__(self, url, headers, body, timeout):
        if url == PREBOOK or url == BOOK:
            import json
            self.asked.append((url, headers, json.loads(body)))
            status, payload = self.prebook if url == PREBOOK else self.book
            return status, "application/json", payload
        return super().__call__(url, headers, body, timeout)

    def calls(self, url):
        return [b for u, _, b in self.asked if u == url]


@pytest.fixture(autouse=True)
def _fresh():
    mb.forget()


@pytest.fixture
def sample(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    fake = Sandbox()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    return fake


def price_like_the_square(real, client, extra=0):
    """The recorded prebook, priced as the square shows its stay (the recordings of the search and of the prebook are of different rooms), plus `extra` dollars."""
    import json
    panel = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").json()["panel"]
    shown = float(re.search(r'mx-row-stay.*?mx-r-n">\$([\d,.]+)<', panel, re.S).group(1).replace(",", ""))
    doc = json.loads(real.prebook[1])
    doc["data"]["price"] = round(shown - 120 + extra, 2)
    real.prebook = (200, json.dumps(doc).encode())
    return shown


def token(html):
    return re.search(r'name="token" value="([^"]+)"', html).group(1)


def text(html):
    return unescape(re.sub(r"<[^>]+>", " ", html))


def stays_booked():
    with ses.family(person()) as fam:
        return familydb.rows(fam.db, "SELECT * FROM matrix_bookings")


def trip_lodging():
    from gitaway import importer
    with ses.family(person()) as fam:
        trips = familydb.rows(fam.db, "SELECT DISTINCT trip_id FROM matrix_bookings")
    return importer.plan_of(person(), trips[0]["trip_id"]).hotels


def test_signed_out_booking_goes_to_sign_in_and_asks_nothing(real, client):
    r = client.post("/plan/matrix/book", data=FORM, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=") and real.calls(PREBOOK) == []


def test_a_square_on_the_showcase_is_a_sample_booking_and_liteapi_is_never_asked(sample, client, monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    fake = Sandbox()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    sign_in(client)
    html = client.post("/plan/matrix/book", data=FORM).text
    words = text(html)
    assert "Sample booking: nothing is booked or charged" in words and "Who is the lead guest?" in words and "Book · $" in words
    assert 'action="/plan/matrix/book/confirm"' in html
    done = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST})
    words = text(done.text)
    assert "Booked" in words and "Anne-Marie O’Neil, your sample booking is confirmed." in words and "SAMPLE-" in words
    assert 'href="/trip/cockpit"' in done.text and "Open your trip" in words
    assert fake.calls(PREBOOK) == [] and fake.calls(BOOK) == []
    rows = stays_booked()
    assert len(rows) == 1 and rows[0]["sample"] == 1 and rows[0]["guest_email"] == "anne@example.com"
    assert [(h.name, h.confirmation, h.booked_on) for h in trip_lodging()] == [(rows[0]["hotel"], rows[0]["booking_id"], "GitAway sample")]


def test_the_sheet_prebooks_the_squares_offer_and_never_shows_its_id(real, client):
    sign_in(client)
    shown = price_like_the_square(real, client)
    j = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").json()
    assert j["s"] == "ok" and "Book the stay" in j["panel"] and 'action="/plan/matrix/book"' in j["panel"]
    html = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    offer = next(b["offerId"] for u, _, b in real.asked if u == PREBOOK)
    assert len(offer) > 100 and offer not in html and offer not in j["panel"] and "mxB7A2bfb" not in html and "<html" not in html     # a fragment; no id on it
    words = text(html)
    assert "Sandbox booking: nothing is charged" in words and "Standard Room, 2 Queen Beds" in words and "$120 of it is paid at the hotel" in words
    assert "Non-refundable" in words and f"Book · ${shown:,.2f}".replace(".00", "") in words and "The price moved" not in words and "Margaritaville Hotel San Diego Gaslamp Quarter" in words
    assert re.search(r'data-state="done"[^>]*>.*?Room', html, re.S) and html.count('data-state="active"') == 1


def test_booking_through_the_sandbox_shows_liteapis_booking_id_and_makes_the_trip(real, client):
    sign_in(client)
    html = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    done = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST}, headers=FRAG)
    words = text(done.text)
    assert "Booking id _5hnX-MI7" in re.sub(r"\s+", " ", words) and "Hotel confirmation test" in re.sub(r"\s+", " ", words)
    assert "Sandbox booking: nothing is charged" in words and "Anne-Marie O’Neil, your booking is confirmed." in words and "Search on" in words
    assert 'href="/trip/cockpit"' in done.text
    sent = real.calls(BOOK)
    assert len(sent) == 1 and sent[0]["payment"] == {"method": "ACC_CREDIT_CARD"} and sent[0]["holder"]["email"] == "anne@example.com" and sent[0]["prebookId"] == "mxB7A2bfb"
    assert [(r["booking_id"], r["sample"], r["total_cents"]) for r in stays_booked()] == [("_5hnX-MI7", 0, 35900 + 12000)]
    assert [(h.confirmation, h.booked_on) for h in trip_lodging()] == [("_5hnX-MI7", "LiteAPI sandbox")]


def test_pressing_book_twice_books_once(real, client):
    sign_in(client)
    html = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    data = {**FORM, "token": token(html), **GUEST}
    first, second = client.post("/plan/matrix/book/confirm", data=data, headers=FRAG), client.post("/plan/matrix/book/confirm", data=data, headers=FRAG)
    assert "_5hnX-MI7" in first.text and "_5hnX-MI7" in second.text and len(real.calls(BOOK)) == 1 and len(stays_booked()) == 1 and len(trip_lodging()) == 1


def test_a_bad_guest_is_said_in_place_and_nothing_is_booked_or_made(real, client):
    sign_in(client)
    html = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    bad = {"first": "<script>alert(1)</script>", "last": "", "email": 'a"><img src=x onerror=1>@x.co'}
    r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **bad}, headers=FRAG).text
    assert "<script>alert" not in r and "<img" not in r and "&lt;script&gt;" in r              # what was typed comes back escaped
    words = text(r)
    assert "The first name is letters only" in words and "Add the lead guest’s last name." in words and "does not look like an email" in words
    assert 'aria-invalid="true"' in r and real.calls(BOOK) == [] and stays_booked() == []


def test_a_room_that_was_just_taken_is_said_and_the_kept_prices_are_dropped(real, client):
    sign_in(client)
    real.prebook = (400, raw("prebook_bad_offer.json"))
    squares = len([1 for u, *_ in real.asked if "/hotels/rates" in u])
    r = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    assert "That room was just taken" in text(r) and "Who is the lead guest?" not in text(r) and real.calls(BOOK) == []
    asked = len([1 for u, *_ in real.asked if "/hotels/rates" in u])
    assert asked > squares
    client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12")
    assert len([1 for u, *_ in real.asked if "/hotels/rates" in u]) > asked                       # asked again, not served from the dropped cache


def test_a_book_liteapi_will_not_take_says_so_and_keeps_the_form(real, client):
    sign_in(client)
    html = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    real.book = (503, b"{}")
    r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST}, headers=FRAG).text
    assert "did not answer just now. Nothing was booked." in text(r) and 'value="anne@example.com"' in r and stays_booked() == []


def test_a_room_check_that_timed_out_is_run_again_never_booked_on_an_unseen_price(real, client):
    sign_in(client)
    r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": "gone", **GUEST}, headers=FRAG).text
    assert "had timed out" in text(r) and len(real.calls(PREBOOK)) == 1 and real.calls(BOOK) == [] and token(r) != "gone"


def test_a_moved_price_is_said_before_booking(real, client):
    sign_in(client)
    shown = price_like_the_square(real, client, extra=41)
    words = text(client.post("/plan/matrix/book", data=FORM, headers=FRAG).text)
    was, now = f"${shown:,.2f}".replace(".00", ""), f"${shown + 41:,.2f}".replace(".00", "")
    assert f"The price moved: it was {was} on the square and is {now} now." in words and f"Book · {now}" in words


def test_without_the_script_the_two_steps_are_pages(real, client):
    sign_in(client)
    html = client.post("/plan/matrix/book", data=FORM).text
    assert "<html" in html and "Back to the matrix" in html and "Who is the lead guest?" in text(html)
    done = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST}).text
    assert "<html" in done and "_5hnX-MI7" in done


def test_a_viewer_cannot_book_and_liteapi_is_never_asked(real, client):
    from tests.test_calendar import book
    from tests.test_members import addr, browser, invite
    book(client)
    mail = addr("vi")
    invite(client, mail, "viewer")
    viewer = browser(client)
    sign_in(viewer, mail)
    for path in ("/plan/matrix/book", "/plan/matrix/book/confirm"):
        assert viewer.post(path, data={**FORM, "token": "x", **GUEST}, follow_redirects=False).status_code == 403
    assert real.calls(PREBOOK) == [] and real.calls(BOOK) == []


def test_the_panel_says_it_is_a_sandbox_not_that_booking_opens_soon(sample, client):
    html = text(client.get("/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").text)
    assert "Booking opens soon" not in html and "Sample booking: nothing is booked or charged." in html and page.SAMPLE_FINE.split(".")[0] in html
