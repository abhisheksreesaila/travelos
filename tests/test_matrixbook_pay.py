"""F-274: booking through LiteAPI's payment form (gitaway/matrixbook.py): prebook with the form's keys (and a voucher), the ids saved at once, the lead guest kept only until the
booking is made, the booking made once with the transaction id, cancel. LiteAPI's answers are the sandbox's own recordings (tests/fixtures/liteapi_pay)."""

import json
from datetime import date, timedelta, timezone, datetime

import pytest

from gitaway import auth, familydb, liteapi, matrixbook as mb, session as ses, tripmatrix as tm
from tests.test_liteapi_pay import FIX, LIVE, Pay
from tests.test_signin import person, sign_in

DAYS = [("San Diego", date(2026, 12, 16), date(2026, 12, 19))]      # the recorded prebooks' nights
PART = tm.StayPart("San Diego", 3, "Margaritaville Hotel San Diego Gaslamp Quarter", "Standard Room, 2 Queen Beds", "room only", False, 12000, "", "", 46010, "offer-1")
GUEST = liteapi.Guest("Test", "Traveler", "test.traveler@example.com", "+1 415 555 0100", "Quiet room; High floor. Arriving in the evening.")
PREBOOK_ID, TRANSACTION = "nXPI8qf8C", "tr_cts_j_DBi8RkjWF1hJDzmsryP"


@pytest.fixture
def family(client):
    sign_in(client)
    who = person()
    with ses.family(who) as fam:
        yield fam.db, str(who["user_id"])


@pytest.fixture
def live(family, monkeypatch):      # signed in first: the dev sign-in is off once production is pretended
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.delenv("GITAWAY_LIVE_BOOKING", raising=False)
    f = Pay()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    mb.forget()
    return f


def prepared(live):
    prep = mb.prepare((PART,), DAYS, "fam", sdk=True)
    assert prep.ok
    return prep


# ---- prebook with the form ---------------------------------------------------------------------------------------------------

def test_a_stay_is_prebooked_for_the_payment_form_and_the_keys_and_the_card_amount_are_read(live):
    prep = prepared(live)
    pre = prep.rows[0].prebook
    assert live.asked[0][2] == {"offerId": "offer-1", "usePaymentSdk": True}
    assert (pre.transaction_id, pre.prebook_id, pre.charge_cents, prep.total_cents, prep.changed, prep.voucher) == (TRANSACTION, PREBOOK_ID, 34010, 46010, False, "")


def test_a_price_within_a_dollar_of_the_square_is_the_price_shown_and_a_dearer_one_is_said(live):
    assert mb.prepare((PART,), DAYS, "fam", sdk=True).changed is False      # 46010 on the square, 34010 + 12000 at prebook
    from dataclasses import replace
    assert mb.prepare((replace(PART, cents=46010 - 99),), DAYS, "fam", sdk=True).changed is False
    assert mb.prepare((replace(PART, cents=46010 - 101),), DAYS, "fam", sdk=True).changed is True
    assert mb.prepare((replace(PART, cents=46010 + 500),), DAYS, "fam", sdk=True).changed is True


def test_a_voucher_code_reprices_the_stay_and_only_the_card_amount_drops(live, monkeypatch):
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(prebook="prebook_voucher.json"))
    prep = mb.prepare((PART,), DAYS, "fam", sdk=True, voucher="F274SANDBOX")
    pre = prep.rows[0].prebook
    assert (prep.voucher, pre.voucher_code, pre.discount_cents, pre.charge_cents, prep.total_cents) == ("F274SANDBOX", "F274SANDBOX", 3401, 30609, 42609)
    assert prep.changed is False      # a discount is not a moved price


def test_a_code_liteapi_refuses_is_said_as_a_bad_code(live, monkeypatch):
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(prebook="prebook_bad_voucher.json"))
    prep = mb.prepare((PART,), DAYS, "fam", sdk=True, voucher="NOSUCHCODE")
    assert (prep.status, prep.rows) == (liteapi.BAD_CODE, ()) and mb.SAID[liteapi.BAD_CODE] == "That code is not valid. Check it, or book without one."


def test_a_prebook_without_the_forms_keys_is_no_payment_path(live, monkeypatch):
    doc = json.loads((FIX / "prebook_sdk.json").read_text())["body"]
    del doc["data"]["secretKey"]
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: (200, "application/json", json.dumps(doc).encode()))
    assert mb.prepare((PART,), DAYS, "fam", sdk=True).status == liteapi.FAILED


def test_a_square_of_two_stays_is_not_booked_through_the_form_and_asks_liteapi_nothing(live):
    prep = mb.prepare((PART, PART), DAYS * 2, "fam", sdk=True)
    assert (prep.status, live.asked) == (mb.MANY, []) and "one stay at a time" in mb.SAID[mb.MANY]


@pytest.mark.parametrize("text, want", [("", ("", "")), ("  ", ("", "")), (" F274SANDBOX ", ("F274SANDBOX", "")), ("save-10_x", ("save-10_x", "")), ("a", ("", "A code is letters and digits, up to 32.")),
                                        ("two words", ("", "A code is letters and digits, up to 32.")), ("x" * 33, ("", "A code is letters and digits, up to 32.")),
                                        ("<script>", ("", "A code is letters and digits, up to 32.")), ("ab\ncd", ("", "A code is letters and digits, up to 32.")), ("é1", ("", "A code is letters and digits, up to 32."))])
def test_a_codes_shape_is_checked_before_liteapi_is_asked(text, want):
    assert mb.code_shape(text) == want


# ---- the ids saved at once, the booking made once ------------------------------------------------------------------------------

def test_the_ids_and_the_amount_are_saved_the_moment_the_prebook_answers_and_never_the_forms_secret(live, family):
    db, user = family
    prep = prepared(live)
    mb.save_prebook(db, prep.token, user, prep.rows[0])
    mb.save_prebook(db, prep.token, user, prep.rows[0])      # a second press saves nothing new
    rows = familydb.rows(db, "SELECT * FROM matrix_payments")
    assert len(rows) == 1
    got = rows[0]
    assert (got["prebook_id"], got["transaction_id"], got["charge_cents"], got["due_at_stay_cents"], got["status"], got["user_id"]) == (PREBOOK_ID, TRANSACTION, 34010, 12000, "prebooked", user)
    assert (got["hotel"], got["checkin"], got["checkout"], got["guest_email"] or "") == ("Margaritaville Hotel San Diego Gaslamp Quarter", "2026-12-16", "2026-12-19", "")
    assert "[secretKey]" not in json.dumps(got) and "secret" not in {c["name"] for c in familydb.rows(db, "PRAGMA table_info(matrix_payments)")}


def pay(db, user, prep, guest=GUEST):
    mb.save_prebook(db, prep.token, user, prep.rows[0])
    assert mb.pay_start(db, prep.token, user, guest, "trip-1")


def test_after_payment_the_stay_is_booked_with_the_transaction_id_and_the_guest_is_blanked(live, family):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    kept = mb.payment(db, prep.token)
    assert (kept["status"], kept["guest_first"], kept["guest_email"], kept["trip_id"]) == ("paying", "Test", "test.traveler@example.com", "trip-1")
    res = mb.finish(db, "fam", prep.token, user)
    assert res.ok and (res.done[0].booking_id, res.done[0].hotel, res.done[0].checkin, res.done[0].total_cents, res.done[0].sample) == ("uuJxfM0--", "Margaritaville Hotel San Diego Gaslamp Quarter", "2026-12-16", 46010, False)
    book = [b for u, _, b, _ in live.asked if u.endswith("/rates/book")]
    assert len(book) == 1 and book[0]["payment"] == {"method": "TRANSACTION_ID", "transactionId": TRANSACTION} and book[0]["prebookId"] == PREBOOK_ID
    person = {"firstName": "Test", "lastName": "Traveler", "email": "test.traveler@example.com", "phone": "+1 415 555 0100"}
    assert book[0]["holder"] == person and book[0]["guests"] == [{"occupancyNumber": 1, **person, "remarks": "Quiet room; High floor. Arriving in the evening."}]
    assert book[0]["clientReference"] == mb.reference("fam", prep.token, 0)
    after = mb.payment(db, prep.token)
    assert (after["status"], after["booking_id"], after["guest_first"], after["guest_last"], after["guest_email"], after["guest_phone"], after["guest_remarks"]) == ("booked", "uuJxfM0--", "", "", "", "", "")
    assert after["prebook_id"] == PREBOOK_ID and after["transaction_id"] == TRANSACTION      # the record stays: the ids are what support asks for
    stored = familydb.rows(db, "SELECT * FROM matrix_bookings")
    assert [(r["booking_id"], r["total_cents"], r["due_at_stay_cents"], r["trip_id"], r["sample"]) for r in stored] == [("uuJxfM0--", 46010, 12000, "trip-1", 0)]


def test_a_reload_or_a_second_press_books_once(live, family):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    first, second = mb.finish(db, "fam", prep.token, user), mb.finish(db, "fam", prep.token, user)
    assert first.ok and second.ok and first.done == second.done
    assert len([1 for u, *_ in live.asked if u.endswith("/rates/book")]) == 1 and len(familydb.rows(db, "SELECT * FROM matrix_bookings")) == 1


def test_a_book_before_the_form_was_opened_is_refused_and_asks_liteapi_nothing(live, family):
    db, user = family
    prep = prepared(live)
    mb.save_prebook(db, prep.token, user, prep.rows[0])      # prebooked, never "paying": nobody gave a guest
    assert mb.finish(db, "fam", prep.token, user).status == liteapi.FAILED
    assert mb.finish(db, "fam", "no-such-token", user).status == liteapi.GONE
    assert not [1 for u, *_ in live.asked if u.endswith("/rates/book")]


def test_another_person_cannot_pay_or_finish_a_payment_that_is_not_theirs(live, family):
    db, user = family
    prep = prepared(live)
    mb.save_prebook(db, prep.token, user, prep.rows[0])
    assert mb.pay_start(db, prep.token, "someone-else", GUEST, "t") is False
    assert mb.pay_start(db, "no-such-token", user, GUEST, "t") is False
    assert mb.finish(db, "fam", prep.token, "someone-else").status == liteapi.GONE
    assert mb.payment(db, prep.token)["status"] == "prebooked"


def test_a_payment_liteapi_has_not_got_books_nothing_and_the_row_waits_for_another_try(live, family, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(book="book_unpaid.json"))
    assert mb.finish(db, "fam", prep.token, user).status == liteapi.NOT_PAID
    kept = mb.payment(db, prep.token)
    assert (kept["status"], kept["guest_email"], familydb.rows(db, "SELECT * FROM matrix_bookings")) == ("paying", "test.traveler@example.com", [])
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay())
    assert mb.finish(db, "fam", prep.token, user).ok      # the money arrived after all: the same reference books it


def test_a_booking_liteapi_already_made_under_our_reference_is_found_not_booked_again(live, family, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    ref = mb.reference("fam", prep.token, 0)
    item = json.loads((FIX / "book_nonrefundable.json").read_text())["body"]["data"] | {"clientReference": ref}
    calls = []

    def fake(url, headers, body, timeout, method=""):
        calls.append(url)
        if url.endswith("/rates/book"):
            return 400, "application/json", b'{"error": {"code": 4005, "message": "duplicate booking attempt with existing client reference"}}'
        return 200, "application/json", json.dumps({"data": [item]}).encode()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    res = mb.finish(db, "fam", prep.token, user)
    assert res.ok and res.done[0].booking_id == "uuJxfM0--" and len([c for c in calls if c.endswith("/rates/book")]) == 1


def test_no_live_call_ever_carries_the_sandbox_card(live, family):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    mb.finish(db, "fam", prep.token, user)
    assert live.asked and "ACC_CREDIT_CARD" not in json.dumps([a[2] for a in live.asked])


def test_the_old_book_with_a_live_key_asks_liteapi_nothing(live, family):
    db, user = family
    prep = prepared(live)
    live.asked.clear()
    res = mb.book(prep, GUEST, db, "fam", "t", user)
    assert res.status == liteapi.OFF and live.asked == []      # no transaction id, so no card method: refused


# ---- what is kept and for how long -----------------------------------------------------------------------------------------------

def test_an_unpaid_prebook_is_dropped_after_a_day_and_a_guests_name_and_email_after_a_week(live, family):
    db, user = family
    a, b, c = (mb.prepare((PART,), DAYS, "fam", sdk=True) for _ in range(3))
    for prep in (a, b, c):
        mb.save_prebook(db, prep.token, user, prep.rows[0])
    mb.pay_start(db, b.token, user, GUEST, "t")
    mb.pay_start(db, c.token, user, GUEST, "t")
    old = lambda days: (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    familydb.run(db, "UPDATE matrix_payments SET created_at = :t WHERE id = :i", t=old(2), i=a.token)
    familydb.run(db, "UPDATE matrix_payments SET created_at = :t WHERE id = :i", t=old(8), i=b.token)
    db.conn.commit()
    mb.purge(db)
    left = {r["id"]: r for r in familydb.rows(db, "SELECT * FROM matrix_payments")}
    assert a.token not in left                                          # nobody paid: gone
    assert left[b.token]["guest_email"] == "" and left[b.token]["transaction_id"] == TRANSACTION      # eight days old: the person goes, the ids stay
    assert left[c.token]["guest_email"] == "test.traveler@example.com"      # a fresh payment keeps its guest


# ---- cancel ---------------------------------------------------------------------------------------------------------------------

def booked(db, user, live):
    prep = prepared(live)
    pay(db, user, prep)
    return mb.finish(db, "fam", prep.token, user).done[0]


def test_cancelling_a_stay_asks_liteapi_once_and_keeps_what_came_back(live, family):
    db, user = family
    done = booked(db, user, live)
    status, c = mb.cancel(db, "fam", done.booking_id, user)
    assert status == liteapi.OK and (c.status, c.refund_cents, c.fee_cents) == ("CANCELLED_WITH_CHARGES", 0, 34010)
    status2, c2 = mb.cancel(db, "fam", done.booking_id, user)
    assert status2 == liteapi.OK and (c2.status, c2.fee_cents) == ("CANCELLED_WITH_CHARGES", 34010)
    assert len([1 for u, *_ in live.asked if "/bookings/" in u]) == 1      # the second asked nothing
    assert mb.cancelled(db, done.booking_id)["fee_cents"] == 34010


def test_a_booking_we_do_not_hold_or_a_sample_one_is_not_cancelled_through_liteapi(live, family):
    db, user = family
    assert mb.cancel(db, "fam", "not-ours", user) == (liteapi.GONE, None)
    familydb.run(db, "INSERT INTO matrix_bookings (id, booking_id, hotel, checkin, checkout, sample, created_at) VALUES ('r', 'SAMPLE-1', 'H', '2026-12-16', '2026-12-19', 1, 'now')")
    db.conn.commit()
    assert mb.cancel(db, "fam", "SAMPLE-1", user) == (liteapi.GONE, None) and not [1 for u, *_ in live.asked if "/bookings/" in u]


def test_a_cancel_liteapi_refuses_is_said_and_keeps_nothing(live, family, monkeypatch):
    db, user = family
    done = booked(db, user, live)
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(cancel="cancel_unknown.json"))
    assert mb.cancel(db, "fam", done.booking_id, user) == (liteapi.FAILED, None) and mb.cancelled(db, done.booking_id) is None


def test_the_mobile_number_and_the_requests_go_with_a_real_booking_as_words_from_the_fixed_list():
    guest = liteapi.Guest("A", "B", "a@b.co")
    ex, errors = mb.clean_extras("+1 415 555 0100", "High floor|Quiet room|<script>", "Evening")
    got = mb.with_extras(guest, ex)
    assert errors == {} and (got.phone, got.remarks) == ("+1 415 555 0100", "High floor; Quiet room. Arriving in the evening.")
    assert mb.with_extras(guest, mb.Extras("+1 415 555 0100")).remarks == "" and mb.with_extras(guest, mb.Extras("+1 415 555 0100", (), "Morning")).remarks == "Arriving in the morning."
    assert mb.with_extras(guest, mb.Extras("+1 415 555 0100", ("Crib in the room",))).remarks == "Crib in the room."


# ---- the refund policy in words ------------------------------------------------------------------------------------------------------

def policy_of(name):
    return mb.policy_words(liteapi.read_prebook(json.loads((FIX / name).read_text())["body"], datetime(2026, 11, 16, tzinfo=timezone.utc)))


def test_the_policy_says_every_step_of_a_refundable_stay_as_liteapi_gave_them():
    assert policy_of("prebook_sdk_refundable.json") == "Free cancellation until Dec 10, 10:00 AM GMT. After that, cancelling costs $148.88; from Dec 11, 10:00 AM GMT, $520.66."


def test_the_policy_of_a_non_refundable_stay_and_of_a_free_one_are_plain():
    assert policy_of("prebook_sdk.json") == "Non-refundable: if you cancel, nothing comes back."
    doc = json.loads((FIX / "prebook_sdk_refundable.json").read_text())["body"]
    for info in doc["data"]["roomTypes"][0]["rates"][0]["cancellationPolicies"]["cancelPolicyInfos"]:
        info["amount"] = 0
    pre = liteapi.read_prebook(doc, datetime(2026, 11, 16, tzinfo=timezone.utc))
    assert mb.policy_words(pre) == "Free cancellation: nothing is charged if you cancel."
    doc["data"]["roomTypes"][0]["rates"][0]["cancellationPolicies"]["cancelPolicyInfos"] = []
    assert mb.policy_words(liteapi.read_prebook(doc, datetime(2026, 11, 16, tzinfo=timezone.utc))) == "Refundable: you can cancel it from the booking page."
