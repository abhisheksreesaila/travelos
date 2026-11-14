"""LiteAPI booking (F-233): prebook and book as the sandbox really answered (tests/fixtures/liteapi prebook.json, book.json, book_duplicate.json, prebook_bad_offer.json,
recorded 2026-11-14 with scripts/probe_liteapi_book.py). Sandbox only: a live key never books. No call is cached, every call counts against the budgets, and a guest's
email never reaches a log line."""

import json
import logging
from datetime import date, datetime, timezone

import pytest

from gitaway import liteapi
from tests.test_liteapi import KEY, answer, raw

AT = datetime(2026, 11, 14, 9, 8, tzinfo=timezone.utc)
GUEST = liteapi.Guest("Test", "Traveler", "test.traveler@example.com")
PREBOOK, BOOK = "https://book.liteapi.travel/v3.0/rates/prebook", "https://book.liteapi.travel/v3.0/rates/book"


class Book:
    """A TRANSPORT answering the booking calls from the recordings (or one answer given), remembering what was asked."""

    def __init__(self, prebook=None, book=None):
        self.asked, self.prebook, self.book = [], prebook or (200, raw("prebook.json")), book or (200, raw("book.json"))

    def __call__(self, url, headers, body, timeout):
        self.asked.append((url, headers, json.loads(body) if body else None))
        status, payload = self.prebook if url == PREBOOK else self.book
        return status, "application/json", payload


@pytest.fixture
def sandbox(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    f = Book()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    return f


def test_a_prebook_answer_is_read_into_the_rooms_final_price_and_what_changed():
    got = liteapi.read_prebook(answer("prebook.json"), AT)
    assert (got.prebook_id, got.hotel_id, got.room) == ("mxB7A2bfb", "lp369ef", "Standard Room, 2 Queen Beds")
    assert (got.checkin, got.checkout) == (date(2026, 12, 14), date(2026, 12, 17))
    assert got.cents == 35900 and got.due_at_stay_cents == 12000      # the $120 resort fee is paid at the hotel, on top
    assert (got.refundable, got.changed, got.fetched) == (False, False, AT)


def test_a_prebook_that_moved_the_price_or_the_terms_says_it_changed():
    for field, value in (("priceDifferencePercent", 4), ("cancellationChanged", True), ("boardChanged", True)):
        doc = answer("prebook.json")
        doc["data"][field] = value
        assert liteapi.read_prebook(doc, AT).changed, field


def test_a_booking_answer_is_read_into_the_confirmation():
    got = liteapi.read_booking(answer("book.json"), AT)
    assert (got.booking_id, got.status, got.confirmation) == ("_5hnX-MI7", "CONFIRMED", "test")
    assert (got.hotel, got.checkin, got.checkout, got.cents, got.sandbox) == ("Margaritaville Hotel San Diego Gaslamp Quarter", date(2026, 12, 14), date(2026, 12, 17), 35900, True)


def test_a_booking_that_is_not_confirmed_or_not_in_dollars_is_unreadable():
    for field, value in (("status", "CANCELED"), ("currency", "EUR"), ("bookingId", "")):
        doc = answer("book.json")
        doc["data"][field] = value
        with pytest.raises(liteapi.Unreadable):
            liteapi.read_booking(doc, AT)


def test_prebook_asks_the_booking_host_with_the_offer_and_no_payment_sdk(sandbox):
    got = liteapi.prebook("offer-1", family="fam")
    assert got.status == liteapi.OK and got.items[0].prebook_id == "mxB7A2bfb"
    url, headers, body = sandbox.asked[0]
    assert (url, body) == (PREBOOK, {"offerId": "offer-1", "usePaymentSdk": False}) and headers["X-API-Key"] == KEY


def test_book_sends_the_guest_once_as_holder_and_as_the_rooms_guest_and_pays_with_the_sandbox_card(sandbox):
    got = liteapi.book("mxB7A2bfb", GUEST, "ref-1", family="fam")
    assert got.status == liteapi.OK and got.items[0].booking_id == "_5hnX-MI7"
    url, _, body = sandbox.asked[0]
    person = {"firstName": "Test", "lastName": "Traveler", "email": "test.traveler@example.com"}
    assert url == BOOK
    assert body == {"prebookId": "mxB7A2bfb", "clientReference": "ref-1", "holder": person, "guests": [{"occupancyNumber": 1, **person}], "payment": {"method": "ACC_CREDIT_CARD"}}


def test_a_live_key_never_books(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", "live_not-a-sandbox-key")
    f = Book()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    assert liteapi.prebook("offer-1").status == liteapi.OFF and liteapi.book("p", GUEST, "r").status == liteapi.OFF
    assert f.asked == []


def test_no_key_no_call(monkeypatch):
    monkeypatch.delenv("LITEAPI_KEY", raising=False)
    assert liteapi.prebook("offer-1").status == liteapi.OFF


def test_each_call_goes_out_and_counts_against_the_budget_never_kept(sandbox):
    before = liteapi.searches_today()
    liteapi.prebook("offer-1", family="fam")
    liteapi.prebook("offer-1", family="fam")
    assert len(sandbox.asked) == 2 and liteapi.searches_today() == before + 2


def test_a_gone_offer_a_gone_room_and_a_repeated_reference_say_so(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    cases = [(Book(prebook=(400, raw("prebook_bad_offer.json"))), lambda: liteapi.prebook("x"), liteapi.GONE),
             (Book(prebook=(409, raw("prebook_bad_offer.json"))), lambda: liteapi.prebook("x"), liteapi.GONE),
             (Book(book=(400, raw("book_duplicate.json"))), lambda: liteapi.book("p", GUEST, "r"), liteapi.DUPLICATE),
             (Book(book=(410, raw("book_duplicate.json"))), lambda: liteapi.book("p", GUEST, "r"), liteapi.GONE),
             (Book(book=(503, b"{}")), lambda: liteapi.book("p", GUEST, "r"), liteapi.FAILED),
             (Book(book=(200, b'{"data": {"bookingId": "b"}}')), lambda: liteapi.book("p", GUEST, "r"), liteapi.FAILED)]
    for fake, ask, status in cases:
        monkeypatch.setattr(liteapi, "TRANSPORT", fake)
        assert ask().status == status, (fake.prebook[0], fake.book[0])


def test_a_dropped_line_on_book_is_never_asked_again_by_itself(monkeypatch):
    """The sandbox sometimes drops a line; a search is asked once more, a booking never (the first may have gone through)."""
    import http.client
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    calls = []

    def drop(url, headers, body, timeout):
        calls.append(url)
        raise http.client.RemoteDisconnected("gone")
    monkeypatch.setattr(liteapi, "TRANSPORT", drop)
    assert liteapi.book("p", GUEST, "r").status == liteapi.FAILED and calls == [BOOK]


def test_a_failure_logs_no_email_and_no_key(sandbox, monkeypatch, caplog):
    monkeypatch.setattr(liteapi, "TRANSPORT", Book(book=(503, b'{"error": {"message": "bad test.traveler@example.com"}}')))
    with caplog.at_level(logging.DEBUG):
        liteapi.book("p", GUEST, "r")
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "test.traveler@example.com" not in text and KEY not in text and "LiteAPI" in text
