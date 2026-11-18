"""F-276: LiteAPI's flight booking calls, as the sandbox really answered them (tests/fixtures/liteapi_flight, 2026-11-18): verify, prebook for the payment form, book with the transaction
id, lookup, cancel quote, cancel. The same gate, budgets and one-at-a-time rule as the stay's booking calls, and with a live key only the calls the ticket allows."""

import json
from datetime import datetime

import pytest

from gitaway import auth, liteapi
from tests.flight_support import AT, BOOK, BOOKING, BOOKING_ID, CANCELS, FLIGHT_CENTS, OFFER, PREBOOK, PREBOOK_ID, TRANSACTION, VERIFY, Fly, body_of, status
from tests.test_liteapi import KEY

LIVE = "live_test-key-not-real"
CONTACT = {"firstName": "Maya", "lastName": "Okafor", "email": "maya.okafor@example.com", "phoneCountryCode": "1", "phoneNumber": "4155550100"}
PAX = [{"passengerType": 0, "title": "MS", "firstName": "Maya", "lastName": "Okafor", "birthday": "1985-04-12", "gender": "F", "nationality": "US"}]


@pytest.fixture
def sandbox(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    f = Fly()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    return f


@pytest.fixture
def live(monkeypatch):
    """A live key where real booking is on (production)."""
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.delenv("GITAWAY_LIVE_BOOKING", raising=False)
    f = Fly()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    return f


# ---- what LiteAPI's answers say -----------------------------------------------------------------------------------------------

def test_a_verify_says_the_price_the_fares_facts_and_the_flights():
    got = liteapi.read_flight_verify(body_of("verify"), AT)
    assert (got.cents, got.price_changed, got.fare, got.refundable, got.changeable) == (FLIGHT_CENTS, False, "Economy Light", False, False)
    assert got.bags_included == ("Personal item (backpack/handbag)",) and got.bags_paid == (("Carry-on bag", 3366), ("Checked bag 23kg", 5048))
    assert got.summary == ("Non-refundable ticket", "Non-changeable ticket") and got.session_id.startswith("session_")
    out, back = got.segments
    assert (out.direction, out.origin, out.destination, out.airline, out.code, out.number) == ("OUTBOUND", "SFO", "SAN", "Nuitée Air", "ND", "6278")
    assert (out.depart, out.arrive, out.minutes) == (datetime(2026, 12, 18, 15, 50), datetime(2026, 12, 18, 17, 29), 99)
    assert (back.direction, back.origin, back.destination, back.number, back.depart) == ("INBOUND", "SAN", "SFO", "3060", datetime(2026, 12, 22, 18, 55))


def test_a_prebook_for_the_payment_form_gives_the_keys_and_the_price():
    got = liteapi.read_flight_prebook(body_of("prebook_sdk"), AT)
    assert (got.prebook_id, got.transaction_id, got.cents, got.secret_key) == (PREBOOK_ID, TRANSACTION, FLIGHT_CENTS, "[secretKey]")
    assert [s.number for s in got.segments] == ["6278", "3060"]


def test_a_new_booking_is_pending_and_a_later_lookup_is_confirmed_with_the_airlines_locator():
    new = liteapi.read_flight_booking(body_of("book"), AT)
    assert (new.booking_id, new.ref, new.status, new.pending, new.confirmed, new.cents) == (BOOKING_ID, "FH-26B-1VO6TJ6Z", "PENDING_CONFIRMATION", True, False, FLIGHT_CENTS)
    later = liteapi.read_flight_booking(body_of("booking_get"), AT)
    assert (later.status, later.confirmed, later.pnr, later.airline_pnrs, later.issued) == ("CONFIRMED", True, "JSS7LG", (("ND", "50CVYQ"),), True)
    assert later.ticket_limit == datetime.fromisoformat("2026-11-18T19:49:48.185Z".replace("Z", "+00:00"))


def test_a_cancel_quote_says_what_comes_back_and_what_it_costs():
    q = liteapi.read_flight_quote(body_of("cancel_quote"), AT)
    assert (q.refund_cents, q.penalty_cents, q.destination, q.pnr) == (7114, 49794, "original_payment", "JSS7LG")


def test_a_cancel_says_the_refund_and_the_fee():
    c = liteapi.read_flight_cancel(body_of("cancel"), AT)
    assert (c.booking_id, c.status, c.refund_cents, c.fee_cents) == (BOOKING_ID, "CANCELLED_WITH_CHARGES", 7114, 49794)


@pytest.mark.parametrize("read, name", [(liteapi.read_flight_verify, "booking_unknown"), (liteapi.read_flight_prebook, "booking_unknown"), (liteapi.read_flight_booking, "booking_unknown"),
                                        (liteapi.read_flight_quote, "booking_unknown"), (liteapi.read_flight_cancel, "booking_unknown")])
def test_an_error_body_is_never_read_as_a_flight(read, name):
    with pytest.raises(liteapi.Unreadable):
        read(body_of(name), AT)


def test_a_price_in_another_currency_is_not_read():
    doc = body_of("verify")
    doc["data"][0]["journey"]["pricing"]["display"]["currency"] = "EUR"
    with pytest.raises(liteapi.Unreadable):
        liteapi.read_flight_verify(doc, AT)


# ---- the calls (a sandbox key) ------------------------------------------------------------------------------------------------

def test_verify_asks_with_the_offer_id_alone(sandbox):
    got = liteapi.flight_verify(OFFER, "fam")
    assert got.ok and got.items[0].cents == FLIGHT_CENTS
    assert sandbox.asked[0][0] == VERIFY and sandbox.asked[0][2] == {"offerId": OFFER}


def test_a_verify_for_an_offer_that_expired_is_gone(sandbox, monkeypatch):
    monkeypatch.setattr(liteapi, "TRANSPORT", Fly(verify=(404, {"error": {"code": 40401, "description": "offer expired"}})))
    assert liteapi.flight_verify(OFFER, "fam").status == liteapi.GONE


def test_prebook_always_asks_for_the_payment_form_and_sends_the_session(sandbox):
    got = liteapi.flight_prebook(OFFER, CONTACT, PAX, "session_1", "fam")
    assert got.ok and got.items[0].transaction_id == TRANSACTION
    url, _, body, _ = sandbox.asked[0]
    assert url == PREBOOK and body == {"offerId": OFFER, "usePaymentSdk": True, "contact": CONTACT, "passengers": PAX, "sessionId": "session_1"}


def test_book_posts_to_the_path_with_the_trailing_slash_and_pays_with_the_transaction_id(sandbox):
    got = liteapi.flight_book(PREBOOK_ID, TRANSACTION, "fam")
    assert got.ok and got.items[0].booking_id == BOOKING_ID      # HTTP 201 is the answer
    url, _, body, _ = sandbox.asked[0]
    assert url == BOOK and url.endswith("/flights/bookings/")      # the bare path answers 307
    assert body == {"prebookId": PREBOOK_ID, "payment": {"method": "TRANSACTION_ID", "transactionId": TRANSACTION}}


def test_lookup_quote_and_cancel_ask_the_right_addresses(sandbox):
    assert liteapi.flight_booking(BOOKING_ID, "fam").items[0].status == "CONFIRMED"
    assert liteapi.flight_cancel_quote(BOOKING_ID, "fam").items[0].refund_cents == 7114
    assert liteapi.flight_cancel(BOOKING_ID, "fam").items[0].status == "CANCELLED_WITH_CHARGES"
    assert [(u, b) for u, _, b, _ in sandbox.asked] == [(BOOKING, None), (CANCELS, None), (CANCELS, {})]


def test_a_cancel_liteapi_has_accepted_and_not_finished_is_pending(sandbox, monkeypatch):
    monkeypatch.setattr(liteapi, "TRANSPORT", Fly(cancel=(202, {"data": {"bookingId": BOOKING_ID, "status": "CANCELLATION_PENDING"}})))
    assert liteapi.flight_cancel(BOOKING_ID, "fam").status == liteapi.PENDING


def test_a_booking_id_cannot_change_the_path(sandbox):
    liteapi.flight_booking("x/../../hotels", "fam")
    assert sandbox.asked[0][0] == "https://api.liteapi.travel/v3.0/flights/bookings/x%2F..%2F..%2Fhotels"


def test_a_book_of_a_payment_never_made_says_not_paid(sandbox, monkeypatch):
    monkeypatch.setattr(liteapi, "TRANSPORT", Fly(book=(400, {"error": {"code": 2014, "description": "payment not completed"}})))
    assert liteapi.flight_book(PREBOOK_ID, TRANSACTION, "fam").status == liteapi.NOT_PAID


def test_the_body_of_a_failed_call_is_never_logged(sandbox, monkeypatch, caplog):
    monkeypatch.setattr(liteapi, "TRANSPORT", Fly(prebook=(400, {"error": {"code": 43002, "description": "maya.okafor@example.com is not a name"}})))
    got = liteapi.flight_prebook(OFFER, CONTACT, PAX, "", "fam")
    assert got.status == liteapi.FAILED
    assert "maya.okafor" not in caplog.text and "Okafor" not in caplog.text and "43002" in caplog.text


def test_every_flight_call_is_counted_in_the_booking_budgets(sandbox):
    from gitaway import community
    from sqlalchemy import text
    liteapi.flight_verify(OFFER, "fam-x")
    liteapi.flight_booking(BOOKING_ID, "fam-x")
    with community.connect() as db:
        assert db.conn.execute(text("SELECT COALESCE(SUM(n), 0) FROM liteapi_bookings WHERE family = 'fam-x' AND day = :d"), {"d": liteapi._day()}).scalar() == 2


def test_the_booking_budget_stops_flight_calls_too(sandbox, monkeypatch):
    monkeypatch.setattr(liteapi, "PER_FAMILY_BOOK_A_DAY", 1)
    assert liteapi.flight_verify(OFFER, "fam-y").ok
    assert liteapi.flight_verify(OFFER, "fam-y").status == liteapi.OVER
    assert len(sandbox.asked) == 1


# ---- a live key: only what the ticket allows (D-972, D-978) ---------------------------------------------------------------------

def test_a_live_key_may_verify_prebook_for_the_form_book_with_the_transaction_look_up_quote_and_cancel(live):
    assert liteapi.flight_verify(OFFER, "fam").ok
    assert liteapi.flight_prebook(OFFER, CONTACT, PAX, "s", "fam").ok
    assert liteapi.flight_book(PREBOOK_ID, TRANSACTION, "fam").ok
    assert liteapi.flight_booking(BOOKING_ID, "fam").ok
    assert liteapi.flight_cancel_quote(BOOKING_ID, "fam").ok
    assert liteapi.flight_cancel(BOOKING_ID, "fam").ok
    assert len(live.asked) == 6


@pytest.mark.parametrize("flag", ["0", None])
def test_the_kill_switch_stops_a_new_flight_prebook_and_nothing_else(monkeypatch, flag):
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.delenv("GITAWAY_LIVE_BOOKING", raising=False)
    if flag is not None:
        monkeypatch.setenv("GITAWAY_LIVE_BOOKING", flag)
    f = Fly()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    assert (liteapi.flight_prebook(OFFER, CONTACT, PAX, "", "fam").ok) is (flag is None)
    for done in (liteapi.flight_book(PREBOOK_ID, TRANSACTION, "fam"), liteapi.flight_booking(BOOKING_ID, "fam"), liteapi.flight_cancel(BOOKING_ID, "fam"), liteapi.flight_verify(OFFER, "fam")):
        assert done.ok      # a guest who paid is finished, and can cancel, whatever the switch says


def test_a_live_key_off_production_prebooks_no_flight(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setattr(auth, "production", lambda: False)
    monkeypatch.delenv("GITAWAY_LIVE_BOOKING", raising=False)
    f = Fly()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    assert liteapi.flight_prebook(OFFER, CONTACT, PAX, "", "fam").status == liteapi.OFF and f.asked == []


def test_a_live_key_can_never_send_the_sandbox_card_for_a_flight(live):
    """ACC_CREDIT_CARD charges the LiteAPI account's own card: no flight call can carry it with a live key, whatever body is built."""
    for body in ({"prebookId": "p", "payment": {"method": "ACC_CREDIT_CARD"}}, {"prebookId": "p", "payment": {"method": "TRANSACTION_ID"}},
                 {"offerId": "o", "usePaymentSdk": False, "contact": CONTACT, "passengers": PAX}, {"offerId": "o", "usePaymentSdk": True, "payment": {"method": "ACC_CREDIT_CARD"}},
                 {"offerId": "o", "extra": 1}, {"offerId": ""}):
        assert liteapi._order("x", "/flights/bookings/", body, 5, "fam", liteapi.read_flight_booking, base=liteapi.API).status == liteapi.OFF, body
    assert live.asked == []


def test_a_flight_prebook_without_the_form_is_not_a_path_a_live_key_has(live):
    assert liteapi._order("x", "/flights/prebooks", {"offerId": "o", "contact": CONTACT, "passengers": PAX}, 5, "fam", liteapi.read_flight_prebook, base=liteapi.API).status == liteapi.OFF
    assert live.asked == []


def test_a_sandbox_flight_book_also_sends_only_the_transaction_id():
    """The function builds the body: there is no argument that makes it another method."""
    import inspect
    assert list(inspect.signature(liteapi.flight_book).parameters) == ["prebook_id", "transaction_id", "family"]


def test_a_flight_the_sandbox_confirms_later_reads_the_new_status(sandbox, monkeypatch):
    monkeypatch.setattr(liteapi, "TRANSPORT", Fly(booking=status("CANCELLED")))
    assert liteapi.flight_booking(BOOKING_ID, "fam").items[0].status == "CANCELLED"
