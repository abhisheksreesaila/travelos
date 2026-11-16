"""F-274: LiteAPI's payment-form booking path, as the sandbox really answered (tests/fixtures/liteapi_pay, recorded 2026-11-16 with scripts/probe_liteapi_pay.py): prebook with the
payment SDK and with a voucher, book with TRANSACTION_ID, cancel, the margin on a live search. With a live key the only payment method that can ever go out is TRANSACTION_ID."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from gitaway import auth, liteapi
from tests.test_liteapi import KEY, answer
from tests.test_liteapi_book import AT, BOOK, GUEST, PREBOOK

FIX = Path(__file__).parent / "fixtures" / "liteapi_pay"
LIVE = "live_test-key-not-real"
CANCEL = "https://book.liteapi.travel/v3.0/bookings/"


def rec(name):
    """(status, body bytes) of one recording."""
    doc = json.loads((FIX / name).read_text())
    return doc["status"], json.dumps(doc["body"]).encode()


class Pay:
    """A TRANSPORT that answers the payment-path calls from the recordings and remembers every call: (url, headers, body, method)."""

    def __init__(self, **answers):
        self.asked, self.answers = [], {"prebook": "prebook_sdk.json", "book": "book_nonrefundable.json", "cancel": "cancel_nonrefundable.json", **answers}

    def __call__(self, url, headers, body, timeout, method=""):
        self.asked.append((url, headers, json.loads(body) if body else None, method))
        what = "prebook" if url == PREBOOK else "book" if url == BOOK else "cancel"
        status, payload = rec(self.answers[what])
        return status, "application/json", payload


@pytest.fixture
def live(monkeypatch):
    """A live key where real booking is on (production)."""
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.delenv("GITAWAY_LIVE_BOOKING", raising=False)
    f = Pay()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    return f


@pytest.fixture
def sandbox(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    f = Pay()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    return f


def read(name):
    return liteapi.read_prebook(json.loads((FIX / name).read_text())["body"], AT)


# ---- what a prebook with the payment form gives ----------------------------------------------------------------------------

def test_a_prebook_with_the_payment_form_gives_the_keys_and_the_price_the_card_is_charged():
    got = read("prebook_sdk.json")
    assert (got.prebook_id, got.transaction_id, got.secret_key) == ("nXPI8qf8C", "tr_cts_j_DBi8RkjWF1hJDzmsryP", "[secretKey]")
    assert (got.cents, got.pays_cents, got.charge_cents, got.voucher_code, got.discount_cents) == (34010, 34010, 34010, "", 0)
    assert got.due_at_stay_cents == 12000 and got.refundable is False and got.changed is False


def test_a_voucher_lowers_what_the_card_pays_and_not_the_price():
    got = read("prebook_voucher.json")
    assert (got.cents, got.charge_cents, got.discount_cents, got.voucher_code) == (34010, 30609, 3401, "F274SANDBOX")


def test_a_prebook_without_the_form_has_no_keys_and_charges_its_price():
    got = liteapi.read_prebook(answer("prebook.json"), AT)
    assert (got.secret_key, got.transaction_id, got.pays_cents, got.charge_cents) == ("", "", 35900, 35900)


def test_a_cancellation_policy_is_read_in_liteapis_words():
    doc = json.loads((FIX / "prebook_sdk.json").read_text())["body"]
    rate = doc["data"]["roomTypes"][0]["rates"][0]
    rate["cancellationPolicies"] = {"cancelPolicyInfos": [{"cancelTime": "2026-12-10T18:59:00Z", "amount": 340.1, "currency": "USD", "type": "amount", "timezone": "GMT"}],
                                    "hotelRemarks": ["Cancel by 7 pm local time."], "refundableTag": "RFN"}
    got = liteapi.read_prebook(doc, AT)
    assert (got.refundable, got.deadline, got.fee_cents, got.remarks) == (True, "2026-12-10T18:59:00Z", 34010, "Cancel by 7 pm local time.")


# ---- the calls --------------------------------------------------------------------------------------------------------------

def test_prebook_asks_for_the_payment_form_and_passes_a_voucher_code(live):
    got = liteapi.prebook("offer-1", "fam", sdk=True, voucher="F274SANDBOX")
    assert got.ok and got.items[0].transaction_id == "tr_cts_j_DBi8RkjWF1hJDzmsryP"
    assert live.asked[0][:3] == (PREBOOK, live.asked[0][1], {"offerId": "offer-1", "usePaymentSdk": True, "voucherCode": "F274SANDBOX"})


def test_a_code_liteapi_refuses_is_a_bad_code_not_a_room_taken(live, monkeypatch):
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(prebook="prebook_bad_voucher.json"))
    assert liteapi.prebook("o", "fam", sdk=True, voucher="NOSUCHCODE").status == liteapi.BAD_CODE
    assert liteapi.prebook("o", "fam", sdk=True).status == liteapi.GONE      # the same 4002 without a code is the offer


def test_a_book_after_the_payment_form_pays_with_the_transaction_id(live):
    got = liteapi.book("nXPI8qf8C", GUEST, "ref-1", "fam", transaction_id="tr_cts_j_DBi8RkjWF1hJDzmsryP")
    assert got.ok and got.items[0].booking_id == "uuJxfM0--"
    person = {"firstName": "Test", "lastName": "Traveler", "email": "test.traveler@example.com"}
    assert live.asked[0][2] == {"prebookId": "nXPI8qf8C", "clientReference": "ref-1", "holder": person, "guests": [{"occupancyNumber": 1, **person}],
                                "payment": {"method": "TRANSACTION_ID", "transactionId": "tr_cts_j_DBi8RkjWF1hJDzmsryP"}}


def test_a_book_of_a_payment_never_made_is_refused_and_says_failed(live, monkeypatch):
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(book="book_unpaid.json"))
    assert liteapi.book("p", GUEST, "r", "fam", transaction_id="tr_x").status == liteapi.FAILED


def test_a_live_key_can_never_send_the_sandbox_card(live):
    """ACC_CREDIT_CARD charges the LiteAPI account's own card: with a live key a book with no transaction id is refused and nothing goes out."""
    assert liteapi.book("p", GUEST, "r", "fam").status == liteapi.OFF
    assert liteapi.book("p", GUEST, "r", "fam", transaction_id="").status == liteapi.OFF
    assert liteapi.prebook("o", "fam").status == liteapi.OFF      # and a prebook without the payment form is not a payment path either
    assert live.asked == []


def test_no_live_call_can_carry_the_card_method_whatever_is_asked_of_order(live):
    for body in ({"payment": {"method": "ACC_CREDIT_CARD"}}, {"payment": {"method": "TRANSACTION_ID"}}, {"payment": {"method": "WALLET", "transactionId": "t"}},
                 {"usePaymentSdk": False}, {"payment": "ACC_CREDIT_CARD"}):
        assert liteapi._order("x", "/rates/book", body, 5, "fam", liteapi.read_booking).status == liteapi.OFF, body
    assert live.asked == []


@pytest.mark.parametrize("production, flag, may", [(True, None, True), (True, "1", True), (True, "0", False), (False, None, False), (False, "0", False), (False, "1", True)])
def test_a_live_key_books_in_production_unless_switched_off_and_elsewhere_only_when_switched_on(monkeypatch, production, flag, may):
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setattr(auth, "production", lambda: production)
    monkeypatch.delenv("GITAWAY_LIVE_BOOKING", raising=False)
    if flag is not None:
        monkeypatch.setenv("GITAWAY_LIVE_BOOKING", flag)
    f = Pay()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    assert liteapi.real_booking() is may
    assert liteapi.prebook("o", "fam", sdk=True).ok is may and bool(f.asked) is may


def test_a_sandbox_key_still_books_with_its_own_card_or_through_the_form(sandbox):
    assert liteapi.book("p", GUEST, "r", "fam").ok
    assert sandbox.asked[0][2]["payment"] == {"method": "ACC_CREDIT_CARD"}
    assert liteapi.book("p", GUEST, "r2", "fam", transaction_id="tr_1").ok
    assert sandbox.asked[1][2]["payment"] == {"method": "TRANSACTION_ID", "transactionId": "tr_1"}
    assert liteapi.real_booking() is False      # a sandbox key is not "real"


# ---- cancel ---------------------------------------------------------------------------------------------------------------

def test_cancelling_a_non_refundable_stay_says_nothing_comes_back(live):
    got = liteapi.cancel("uuJxfM0--", "fam")
    assert got.ok
    c = got.items[0]
    assert (c.booking_id, c.status, c.refund_cents, c.fee_cents) == ("uuJxfM0--", "CANCELLED_WITH_CHARGES", 0, 34010)
    url, headers, body, method = live.asked[0]
    assert (url, body, method) == (CANCEL + "uuJxfM0--", None, "PUT") and headers["X-API-Key"] == LIVE


def test_cancelling_a_refundable_stay_says_what_comes_back(live, monkeypatch):
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(cancel="cancel_refundable.json"))
    c = liteapi.cancel("wyOxZDui1", "fam").items[0]
    assert (c.status, c.refund_cents, c.fee_cents) == ("CANCELLED", 34010, 0)


def test_cancelling_a_booking_liteapi_does_not_know_is_failed_and_the_id_cannot_change_the_path(live, monkeypatch):
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(cancel="cancel_unknown.json"))
    assert liteapi.cancel("nope", "fam").status == liteapi.FAILED
    f = Pay()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    liteapi.cancel("../../rates/book?x=1", "fam")
    assert f.asked[0][0] == CANCEL + "..%2F..%2Frates%2Fbook%3Fx%3D1"


def test_a_cancel_is_a_booking_call_counted_and_refused_where_booking_is_off(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setattr(auth, "production", lambda: False)
    f = Pay()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    assert liteapi.cancel("b", "fam").status == liteapi.OFF and f.asked == []


# ---- the margin ------------------------------------------------------------------------------------------------------------

def stay_body(monkeypatch, key):
    monkeypatch.setenv("LITEAPI_KEY", key)
    seen = []

    def fake(url, headers, body, timeout, method=""):
        seen.append(json.loads(body))
        return 200, "application/json", (Path(__file__).parent / "fixtures" / "liteapi" / "hotel_rates.json").read_bytes()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    liteapi.clear()
    liteapi.stays(checkin=date(2026, 12, 12), checkout=date(2026, 12, 16), adults=2, city="San Diego", country="US", family="fam")
    return seen[0]


def test_a_live_search_carries_the_margin_that_makes_the_charge_the_public_price(monkeypatch):
    monkeypatch.delenv("LITEAPI_MARGIN", raising=False)
    assert stay_body(monkeypatch, LIVE)["margin"] == 16.0


def test_a_sandbox_search_carries_no_margin(monkeypatch):
    assert "margin" not in stay_body(monkeypatch, KEY)


@pytest.mark.parametrize("env, want", [("12.5", 12.5), ("0", 0.0), ("nonsense", 16.0), ("-3", 16.0), ("90", 16.0), ("", 16.0)])
def test_the_margin_can_be_set_and_a_wrong_one_is_the_default(monkeypatch, env, want):
    monkeypatch.setenv("LITEAPI_MARGIN", env)
    assert stay_body(monkeypatch, LIVE)["margin"] == want


def test_at_the_margin_the_sandbox_recorded_the_price_charged_is_the_public_price_to_the_cent():
    """tests/fixtures/liteapi_pay/margin.json: the same search of 11 San Diego hotels with no margin and with margin 16."""
    rows = json.loads((FIX / "margin.json").read_text())
    with16, without = rows["16"], rows["None"]
    assert len(with16) == 11 and all(abs(r["retail"] - r["ssp"]) <= 0.011 for r in with16)      # what is charged is what is shown, within a cent
    assert all(r["retail"] < r["ssp"] * 0.88 for r in without)      # without it the charge is a good deal under the public price
    assert LIVE and liteapi.MARGIN == 16.0
