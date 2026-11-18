"""F-276: flights booked through LiteAPI (gitaway/flightbook.py): the offer verified before paying, the travellers form's rules, the ids saved at once, the book made once and only from the payment
form's return, the passengers blanked once it is booked, the status followed to CONFIRMED with one email, the cancel quote then the cancel, the flights on the family's trip. LiteAPI's answers are the
sandbox's own recordings (tests/fixtures/liteapi_flight, 2026-11-18); nothing here reaches the network."""

import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from gitaway import auth, familydb, flightbook as fb, liteapi, matrixbook as mb, session as ses, tripmatrix as tm, tripstart
from tests.flight_support import BOOKING_ID, FLIGHT_CENTS, Fly, OFFER, PREBOOK, PREBOOK_ID, TRANSACTION, VERIFY, price, status
from tests.test_liteapi_flight import LIVE
from tests.test_signin import person, sign_in

DEPART, BACK = date(2026, 12, 18), date(2026, 12, 22)
PART = tm.FlightPart("Nuitée Air", "Fri, Dec 18 · SFO 3:50 PM → SAN 5:29 PM · Nonstop", "Tue, Dec 22 · SAN 6:55 PM → SFO 8:34 PM", 0, FLIGHT_CENTS, True, OFFER)
FORM = {"first": "Maya", "last": "Okafor", "t0_dob": "1985-04-12", "t0_sex": "F", "t0_nat": "US", "t1_first": "Daniel", "t1_last": "Okafor", "t1_dob": "1983-09-03", "t1_sex": "M", "t1_nat": "US",
        "t2_first": "Leo", "t2_last": "Okafor", "t2_dob": "2019-02-20", "t2_sex": "M", "t2_nat": "US", "email": "maya.okafor@example.com", "cc": "1", "phone": "415 555 0100"}
TODAY = date(2026, 11, 18)


def clean(values=None, abroad=False, kids=(7,), adults=2):
    return fb.clean_travellers({**FORM, **(values or {})}, adults, kids, DEPART, BACK, abroad, TODAY)


@pytest.fixture
def family(client):
    sign_in(client)
    who = person()
    with ses.family(who) as fam:
        yield fam.db, str(who["user_id"]), who


@pytest.fixture
def live(family, monkeypatch):      # signed in first: the dev sign-in is off once production is pretended
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setenv("GITAWAY_LIVE_FLIGHTS", "1")
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.delenv("GITAWAY_LIVE_BOOKING", raising=False)
    f = Fly()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    mb.forget()
    return f


def with_answers(monkeypatch, **answers):
    f = Fly(**answers)
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    return f


def prebooked(db, user, token="tok-1", trip_id="trip-1", stay_token="stay-1", fam="fam"):
    fp = fb.prepare(PART, fam)
    assert fp.ok and not fp.sample
    people, contact, errors = clean()
    assert not errors
    got = liteapi.flight_prebook(OFFER, fb.contact_body(contact), fb.passengers_body(people), fp.verified.session_id, fam)
    assert got.ok
    assert fb.save_prebook(db, token, user, fp, got.items[0], people, contact, trip_id, stay_token, "/plan/matrix?to=San+Diego", "2 adults, 1 kid (ages 7)")
    return fp


# ---- verifying ---------------------------------------------------------------------------------------------------------------

def test_the_squares_flight_is_verified_and_the_facts_before_paying_are_liteapis_own(live):
    fp = fb.prepare(PART, "fam")
    assert (fp.ok, fp.sample, fp.cents, fp.changed, live.asked[0][2]) == (True, False, FLIGHT_CENTS, False, {"offerId": OFFER})
    assert fb.facts_of(fp.verified) == {"fare": "Economy Light", "included": "Included: Personal item (backpack/handbag)", "paid": "Extra, not sold here yet: Carry-on bag $33.66, Checked bag 23kg $50.48",
                                        "refundable": False, "changeable": False}
    assert fb.refund_words(False) == "Not refundable: cancelling returns only some taxes"
    assert fb.refund_words(True) == "Refundable: you get the fare back if you cancel"


def test_a_price_that_moved_is_said_and_a_dollars_rounding_is_not(live, monkeypatch):
    with_answers(monkeypatch, verify=price(FLIGHT_CENTS + 4000))
    assert fb.prepare(PART, "fam").changed is True
    with_answers(monkeypatch, verify=price(FLIGHT_CENTS + 99))      # LiteAPI's own flag is set by the edit, so it says changed
    assert fb.prepare(PART, "fam").changed is True
    with_answers(monkeypatch)
    assert fb.prepare(replace(PART, cents=FLIGHT_CENTS - 99), "fam").changed is False
    assert fb.prepare(replace(PART, cents=FLIGHT_CENTS - 101), "fam").changed is True


def test_an_offer_that_expired_is_gone_and_asks_nothing_more(live, monkeypatch):
    f = with_answers(monkeypatch, verify=(404, {"error": {"code": 1, "description": "expired"}}))
    assert fb.prepare(PART, "fam").status == liteapi.GONE and len(f.asked) == 1


def test_a_sample_flight_and_a_flight_with_no_offer_are_never_asked_of_liteapi(live):
    assert fb.prepare(PART, "fam", sample=True).sample and fb.prepare(replace(PART, offer_id=""), "fam").sample
    assert live.asked == []


# ---- the travellers form --------------------------------------------------------------------------------------------------

def test_a_complete_form_gives_every_traveller_and_the_lead_contact():
    people, contact, errors = clean()
    assert errors == {}
    assert [(p.kind, p.first, p.last, p.birthday, p.gender, p.nationality) for p in people] == [(0, "Maya", "Okafor", date(1985, 4, 12), "F", "US"), (0, "Daniel", "Okafor", date(1983, 9, 3), "M", "US"),
                                                                                              (1, "Leo", "Okafor", date(2019, 2, 20), "M", "US")]
    assert contact == fb.Contact("Maya", "Okafor", "maya.okafor@example.com", "1", "4155550100")
    assert fb.passengers_body(people)[0] == {"passengerType": 0, "title": "MS", "firstName": "Maya", "lastName": "Okafor", "birthday": "1985-04-12", "gender": "F", "nationality": "US"}
    assert fb.passengers_body(people)[2] == {"passengerType": 1, "firstName": "Leo", "lastName": "Okafor", "birthday": "2019-02-20", "gender": "M", "nationality": "US"}
    assert fb.contact_body(contact) == {"firstName": "Maya", "lastName": "Okafor", "email": "maya.okafor@example.com", "phoneCountryCode": "1", "phoneNumber": "4155550100"}


def test_every_traveller_is_asked_and_the_problem_names_the_field():
    people, contact, errors = clean({"t1_first": "", "t2_dob": "", "t0_sex": "", "t0_nat": "ZZ", "email": "not-an-email", "phone": "12"})
    assert (people, contact) == ((), None)
    assert errors == {"t1_first": "Add traveller 2’s first name as it is on their ID.", "t2_dob": "Add traveller 3’s birth date.", "t0_sex": "Choose the gender as on the ID: F, M or X.",
                      "t0_nat": "Choose the nationality from the list.", "email": "That does not look like an email address.", "phone": "Add a mobile number the airline can reach: 4 to 14 digits."}


def test_a_childs_birth_date_must_make_them_the_age_that_was_searched_on_the_day_they_fly():
    assert clean({"t2_dob": "2019-12-18"})[2] == {}                  # 7 today, on the day
    assert clean({"t2_dob": "2019-12-19"})[2] == {"t2_dob": "This kid was searched as 7: the birth date must make them 7 on Dec 18."}
    assert clean({"t2_dob": "2017-02-20"})[2] == {"t2_dob": "This kid was searched as 7: the birth date must make them 7 on Dec 18."}


def test_an_infant_must_stay_under_two_on_the_way_back_too():
    assert clean({"t2_dob": "2025-01-10"}, kids=(1,))[2] == {}
    assert clean({"t2_dob": "2024-12-20"}, kids=(1,))[2] == {"t2_dob": "This child turns 2 before the flight home, which needs a seat of their own. Search again with their age."}


def test_an_adult_is_eighteen_or_over_and_a_birth_date_is_a_real_past_one():
    assert clean({"t1_dob": "2008-12-19"})[2] == {"t1_dob": "An adult is 18 or over on the day of the flight. A younger traveller is added as a kid when you search."}
    assert clean({"t1_dob": "2027-01-01"})[2] == {"t1_dob": "That birth date does not look right."}
    assert clean({"t1_dob": "1890-01-01"})[2] == {"t1_dob": "That birth date does not look right."}
    assert clean({"t1_dob": "12/03/1983"})[2] == {"t1_dob": "Add traveller 2’s birth date."}


@pytest.mark.parametrize("name", ["", "Maya<script>", "Maya1", "x" * 41, "  ", "M@ya"])
def test_a_name_is_letters_only(name):
    assert "first" in clean({"first": name})[2]


def test_a_name_may_hold_an_apostrophe_a_hyphen_and_an_accent():
    people, _, errors = clean({"first": "Anne-Marie", "last": "O’Neil-Núñez"})
    assert errors == {} and (people[0].first, people[0].last) == ("Anne-Marie", "O’Neil-Núñez")


def test_an_international_route_asks_for_each_passport_and_a_domestic_one_does_not():
    assert clean(abroad=False)[2] == {}
    errors = clean(abroad=True)[2]
    assert set(errors) == {f"t{i}_{f}" if (i, f) not in () else "" for i in range(3) for f in ("docno", "docc", "docx")}
    doc = {f"t{i}_docno": "x1234567" for i in range(3)} | {f"t{i}_docc": "US" for i in range(3)} | {f"t{i}_docx": "2031-05-01" for i in range(3)}
    people, _, errors = clean(doc, abroad=True)
    assert errors == {} and people[0].doc == ("X1234567", "US", date(2031, 5, 1))
    assert fb.passengers_body(people)[0]["documentNumber"] == "X1234567" and fb.passengers_body(people)[0]["documentExpiry"] == "2031-05-01"
    assert clean(doc | {"t0_docx": "2026-12-22"}, abroad=True)[2] == {"t0_docx": "The passport must still be valid after the trip: add its expiry date."}


def test_the_phone_is_a_country_code_and_digits_and_the_code_defaults_to_one():
    assert clean({"cc": "+44", "phone": "(020) 7946-0018"})[1].cc == "44"
    assert clean({"cc": "", "phone": "415.555.0100"})[1] == fb.Contact("Maya", "Okafor", "maya.okafor@example.com", "1", "4155550100")
    assert clean({"cc": "12345"})[2] == {"cc": "The country code is 1 to 3 digits."}
    assert clean({"phone": "call me"})[2] == {"phone": "Add a mobile number the airline can reach: 4 to 14 digits."}


def test_the_kids_seat_in_a_party_follows_the_ages_searched():
    assert fb.seats(2, (7, 1)) == ((0, None), (0, None), (1, 7), (2, 1))


def test_the_form_names_the_lead_like_the_stays_guest():
    assert [fb.field(0, n) for n in ("first", "last", "dob")] == ["first", "last", "t0_dob"] and fb.field(2, "first") == "t2_first"


def test_a_route_leaves_the_united_states_when_an_airport_is_not_a_us_one():
    seg = lambda o, d: liteapi.Seg("OUTBOUND", o, d, datetime(2026, 12, 18, 9), datetime(2026, 12, 18, 12), "X", "X", "1", 180)      # noqa: E731
    assert fb.international([seg("SFO", "SAN")]) is False
    assert fb.international([seg("SFO", "LHR")]) is True
    assert fb.international([seg("SFO", "ZZZ")]) is True      # an airport we do not know: a passport is asked, never forgotten


def test_the_passengers_survive_the_database_round_trip_with_passports():
    doc = {f"t{i}_docno": "X1234567" for i in range(3)} | {f"t{i}_docc": "US" for i in range(3)} | {f"t{i}_docx": "2031-05-01" for i in range(3)}
    people, contact, _ = clean(doc, abroad=True)
    assert fb.load(fb.dump(people, contact)) == (people, contact)
    assert fb.load("") == (None, None)


# ---- the prebook is saved at once; the passengers stay only until it is booked ------------------------------------------------

def test_the_ids_the_flights_and_the_facts_are_saved_the_moment_the_prebook_answers_and_never_the_forms_secret(live, family):
    db, user, _ = family
    prebooked(db, user)
    rows = familydb.rows(db, "SELECT * FROM matrix_flight_payments")
    assert len(rows) == 1
    got = rows[0]
    assert (got["prebook_id"], got["transaction_id"], got["charge_cents"], got["status"], got["user_id"], got["route"], got["airline"], got["stay_token"]) == (
        PREBOOK_ID, TRANSACTION, FLIGHT_CENTS, "paying", user, "SFO to SAN", "Nuitée Air", "stay-1")
    assert [s["n"] for s in json.loads(got["legs"])] == ["6278", "3060"] and json.loads(got["facts"])["fare"] == "Economy Light"
    assert "[secretKey]" not in json.dumps(got) and "secret" not in {c["name"] for c in familydb.rows(db, "PRAGMA table_info(matrix_flight_payments)")}
    sent = live.calls(PREBOOK)[0]
    assert sent["usePaymentSdk"] is True and sent["sessionId"].startswith("session_") and [p["firstName"] for p in sent["passengers"]] == ["Maya", "Daniel", "Leo"]
    assert fb.load(got["travellers"])[1].email == "maya.okafor@example.com"      # kept only until it is booked


def second(db, user):
    fp = fb.prepare(PART, "fam")
    people, contact, _ = clean()
    return fb.save_prebook(db, "tok-1", user, fp, liteapi.flight_prebook(OFFER, {}, [], "", "fam").items[0], people, contact, "t", "s", "/", "p")


def test_a_form_still_open_is_never_replaced_by_a_second_prebook_and_its_return_still_books(live, family):
    """D-980 review: the first form may be paid. A second prebook of the token within 15 minutes is refused, the first row (its transaction) is untouched and its return books it."""
    db, user, _ = family
    prebooked(db, user)
    assert fb.form_open(db, "tok-1") is True
    assert second(db, user) is False
    rows = familydb.rows(db, "SELECT * FROM matrix_flight_payments")
    assert len(rows) == 1 and rows[0]["transaction_id"] == TRANSACTION and rows[0]["travellers"] != ""
    assert fb.finish(db, "fam", "tok-1", user).ok      # the return of the first form
    assert second(db, user) is False and fb.form_open(db, "tok-1") is True      # and a booked one is never touched
    assert familydb.rows(db, "SELECT status FROM matrix_flight_payments")[0]["status"] == "booked"


def test_an_older_unbooked_form_is_set_aside_with_its_ids_and_no_passengers_never_deleted(live, family):
    db, user, _ = family
    prebooked(db, user)
    with familydb.transaction(db):
        familydb.run(db, "UPDATE matrix_flight_payments SET updated_at = :t", t=(datetime.fromisoformat(familydb.now()) - timedelta(minutes=16)).isoformat(timespec="seconds"))
    assert fb.form_open(db, "tok-1") is False and second(db, user) is True
    rows = familydb.rows(db, "SELECT id, status, transaction_id, travellers FROM matrix_flight_payments ORDER BY created_at")
    assert len(rows) == 2 and {r["transaction_id"] for r in rows} == {TRANSACTION}
    old = next(r for r in rows if r["id"] != "tok-1")
    assert old["id"].startswith("tok-1~") and old["status"] == "paying" and old["travellers"] == ""
    assert next(r for r in rows if r["id"] == "tok-1")["travellers"] != ""


# ---- the book: once, from the form's return only -----------------------------------------------------------------------------

def test_after_payment_the_flight_is_booked_with_the_transaction_id_and_the_passengers_are_blanked(live, family):
    db, user, _ = family
    prebooked(db, user)
    res = fb.finish(db, "fam", "tok-1", user)
    assert res.ok
    row = res.row
    assert (row["booking_id"], row["ref"], row["status"], row["total_cents"], row["sample"], row["trip_id"], row["airline"], row["party"]) == (
        BOOKING_ID, "FH-26B-1VO6TJ6Z", "PENDING_CONFIRMATION", FLIGHT_CENTS, 0, "trip-1", "Nuitée Air", "2 adults, 1 kid (ages 7)")
    book = live.calls("https://api.liteapi.travel/v3.0/flights/bookings/")
    assert book == [{"prebookId": PREBOOK_ID, "payment": {"method": "TRANSACTION_ID", "transactionId": TRANSACTION}}]
    after = fb.payment(db, "tok-1")
    assert (after["status"], after["booking_id"], after["travellers"]) == ("booked", BOOKING_ID, "")
    assert after["prebook_id"] == PREBOOK_ID and after["transaction_id"] == TRANSACTION      # the record stays: the ids are what support asks for
    assert json.loads(after["contact"]) == {"first": "Maya", "email": "maya.okafor@example.com"}      # only until the tickets email


def test_a_reload_or_a_second_return_books_once(live, family):
    db, user, _ = family
    prebooked(db, user)
    first, second = fb.finish(db, "fam", "tok-1", user), fb.finish(db, "fam", "tok-1", user)
    assert first.ok and second.ok and first.row == second.row
    assert len(live.calls("https://api.liteapi.travel/v3.0/flights/bookings/")) == 1 and len(familydb.rows(db, "SELECT * FROM matrix_flights")) == 1


def test_only_the_person_who_prebooked_can_finish_it(live, family):
    db, user, _ = family
    prebooked(db, user)
    assert fb.finish(db, "fam", "tok-1", "someone-else").status == liteapi.GONE
    assert fb.finish(db, "fam", "no-such-token", user).status == liteapi.GONE
    assert live.calls("https://api.liteapi.travel/v3.0/flights/bookings/") == []


def test_a_form_nobody_paid_is_not_booked_and_waits(live, family, monkeypatch):
    db, user, _ = family
    prebooked(db, user)
    with_answers(monkeypatch, book=(400, {"error": {"code": 2014, "description": "payment not completed"}}))
    res = fb.finish(db, "fam", "tok-1", user)
    assert (res.status, res.row) == (liteapi.NOT_PAID, None) and fb.payment(db, "tok-1")["status"] == "paying" and familydb.rows(db, "SELECT * FROM matrix_flights") == []
    with_answers(monkeypatch)
    assert fb.finish(db, "fam", "tok-1", user).ok      # paid after all: the same row books


def test_a_booking_that_may_have_gone_through_is_kept_for_the_captain_and_never_asked_again(live, family, monkeypatch):
    db, user, _ = family
    prebooked(db, user)
    with_answers(monkeypatch, book=(500, {"error": {"code": 1, "description": "boom"}}))
    assert fb.finish(db, "fam", "tok-1", user).status == liteapi.FAILED
    assert fb.payment(db, "tok-1")["status"] == "needs_help" and fb.payment(db, "tok-1")["travellers"] != ""
    f = with_answers(monkeypatch)
    assert fb.finish(db, "fam", "tok-1", user).status == liteapi.FAILED and f.asked == []      # a second try could book twice


def test_a_prebook_liteapi_no_longer_has_is_expired_and_the_passengers_are_dropped(live, family, monkeypatch):
    db, user, _ = family
    prebooked(db, user)
    with_answers(monkeypatch, book=(410, {"error": {"code": 1, "description": "gone"}}))
    assert fb.finish(db, "fam", "tok-1", user).status == liteapi.GONE
    row = fb.payment(db, "tok-1")
    assert (row["status"], row["travellers"], row["contact"]) == ("expired", "", "")
    fb.purge(db)
    assert fb.payment(db, "tok-1")["transaction_id"] == TRANSACTION      # a paid return whose fare is gone keeps its record: the captain matches it
    assert [r["id"] for r in fb.to_match(db, datetime.now(timezone.utc) + timedelta(minutes=20))] == ["tok-1"]
    with familydb.transaction(db):
        familydb.run(db, "UPDATE matrix_flight_payments SET created_at = :t", t=(datetime.now(timezone.utc) - timedelta(days=8)).isoformat(timespec="seconds"))
    fb.purge(db)
    assert fb.payment(db, "tok-1") is None


def test_two_returns_at_once_book_one_flight(live, family):
    db, user, _ = family
    prebooked(db, user)
    fb._set(db, "tok-1", fb.BOOKING)      # another caller is making the booking now
    res = fb.finish(db, "fam", "tok-1", user)
    assert res.status == fb.BOOKING and live.calls("https://api.liteapi.travel/v3.0/flights/bookings/") == []


def test_a_book_after_payment_is_never_refused_by_the_daily_booking_budgets(live, family, monkeypatch):
    """D-980 review: the money is already taken, so neither the family's nor the site's daily booking budget may refuse the book."""
    db, user, _ = family
    prebooked(db, user)
    monkeypatch.setattr(liteapi, "PER_FAMILY_BOOK_A_DAY", 0)
    monkeypatch.setattr(liteapi, "BOOK_A_DAY", 0)
    assert fb.finish(db, "fam", "tok-1", user).ok and liteapi.flight_verify(OFFER, "fam").status == liteapi.OVER      # a verify (new business) is still counted


def test_a_sample_flight_is_a_row_with_no_call_and_pressing_book_twice_finds_it(live, family):
    db, user, _ = family
    segs = fb.sample_segments(PART, DEPART, BACK)
    assert [(s.direction, s.origin, s.destination, s.depart, s.arrive) for s in segs] == [("OUTBOUND", "SFO", "SAN", datetime(2026, 12, 18, 15, 50), datetime(2026, 12, 18, 17, 29)),
                                                                                           ("INBOUND", "SAN", "SFO", datetime(2026, 12, 22, 18, 55), datetime(2026, 12, 22, 20, 34))]
    one = fb.book_sample(db, "fam", "tok-1", "trip-1", user, fb.prepare(PART, "fam", sample=True), segs, "2 adults")
    two = fb.book_sample(db, "fam", "tok-1", "trip-1", user, fb.prepare(PART, "fam", sample=True), segs, "2 adults")
    assert one == two and one["sample"] == 1 and one["booking_id"].startswith("SAMPLE-") and fb.status_words(one) == "Sample flight booking: nothing is booked or charged"
    assert live.asked == [] or all(c[0] == VERIFY for c in live.asked)


# ---- the status, the tickets, the email ---------------------------------------------------------------------------------------

SMTP = {"SMTP_HOST": "smtp.resend.com", "SMTP_USER": "resend", "SMTP_PASSWORD": "re_not_a_key", "SMTP_MAIL_FROM": "GitAway <trips@gitaway.me>", "SMTP_SSL": "true", "SMTP_PORT": "465"}


@pytest.fixture
def outbox(monkeypatch):
    from gitaway import bookingmail
    sent = []
    for k, v in SMTP.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(bookingmail, "deliver", lambda to, mail: sent.append((to, mail.subject, mail.text, mail.html)))
    monkeypatch.setattr(bookingmail, "_spawn", lambda fn, *a: fn(*a))
    return sent


def test_a_pending_booking_says_it_is_waiting_for_the_airline_and_the_booked_email_says_so(live, family, outbox):
    db, user, _ = family
    prebooked(db, user)
    row = fb.finish(db, "fam", "tok-1", user).row
    assert fb.status_words(row) == "Waiting for the airline to confirm your tickets"
    assert len(outbox) == 1
    to, subject, text, _ = outbox[0]
    assert to == "maya.okafor@example.com" and subject == "Booked: flight SFO to SAN, Fri, Dec 18, 2026"
    assert "Your flight SFO to SAN is booked and waiting for the airline." in text and "Status: Waiting for the airline to confirm your tickets" in text
    assert "LiteAPI booking reference: FH-26B-1VO6TJ6Z" in text and "Fare rules: Not refundable: cancelling returns only some taxes. Not changeable: the dates cannot be moved." in text
    assert "Okafor" not in text and "1985" not in text      # no passenger's name or birth date goes in an email


def test_the_worker_asks_again_and_one_email_goes_when_it_turns_confirmed(live, family, outbox):
    db, user, _ = family
    prebooked(db, user)
    row = fb.finish(db, "fam", "tok-1", user).row
    outbox.clear()
    now = datetime.fromisoformat(familydb.now())
    assert fb.due(db, now) == []                                 # not before the first gap
    later = now + timedelta(minutes=2)
    assert [r["booking_id"] for r in fb.due(db, later)] == [BOOKING_ID]
    got = fb.refresh(db, "fam", row, "job:fam", later)
    assert (got["status"], got["pnr"], fb.locators(got), fb.status_words(got)) == ("CONFIRMED", "JSS7LG", (("ND", "50CVYQ"),), "Tickets issued: the airline has confirmed")
    assert len(outbox) == 1 and outbox[0][1] == "Tickets issued: flight SFO to SAN, Fri, Dec 18, 2026" and "Airline booking reference: ND 50CVYQ" in outbox[0][2]
    assert fb.due(db, later + timedelta(days=1)) == []           # confirmed: no more lookups
    fb.refresh(db, "fam", got, "job:fam", later)                 # asked again by mistake: still one email
    assert len(outbox) == 1
    assert json.loads(fb.payment(db, "tok-1")["contact"] if fb.payment(db, "tok-1")["contact"] else "{}") == {}      # the address is dropped once it has been used


def test_a_booking_still_waiting_is_asked_five_times_at_growing_gaps_and_no_more(live, family, monkeypatch):
    db, user, _ = family
    prebooked(db, user)
    row = fb.finish(db, "fam", "tok-1", user).row
    f = with_answers(monkeypatch, booking=status("PENDING_CONFIRMATION"))
    now = datetime.fromisoformat(familydb.now())
    for gap in (2, 5, 14, 40, 90):
        now += timedelta(minutes=gap)
        assert [r["booking_id"] for r in fb.due(db, now)] == [BOOKING_ID], gap
        row = fb.refresh(db, "fam", row, "job:fam", now)
    assert fb.due(db, now + timedelta(days=1)) == [] and len(f.asked) == 5 and row["status"] == "PENDING_CONFIRMATION" and row["checks"] == 5


def test_a_failed_lookup_counts_as_a_try_and_changes_nothing(live, family, monkeypatch):
    db, user, _ = family
    prebooked(db, user)
    row = fb.finish(db, "fam", "tok-1", user).row
    with_answers(monkeypatch, booking=(500, {"error": {"code": 1}}))
    got = fb.refresh(db, "fam", row, "job:fam")
    assert (got["status"], got["checks"]) == ("PENDING_CONFIRMATION", 1)


def test_the_worker_never_books_a_flight_whose_form_was_only_opened(live, family):
    db, user, _ = family
    prebooked(db, user)
    assert fb.stuck(db, "2999-01-01T00:00:00") == []              # a form left open is not a payment
    fb._set(db, "tok-1", fb.NEEDS_HELP)
    assert [r["id"] for r in fb.stuck(db, "2999-01-01T00:00:00")] == ["tok-1"]


# ---- cancelling --------------------------------------------------------------------------------------------------------------

def booked_flight(db, user):
    prebooked(db, user)
    return fb.finish(db, "fam", "tok-1", user).row


def test_the_quote_comes_first_and_says_the_refund_and_the_penalty_in_money(live, family):
    db, user, _ = family
    booked_flight(db, user)
    st, q = fb.quote(db, "fam", BOOKING_ID, user)
    assert st == liteapi.OK and (q.refund_cents, q.penalty_cents) == (7114, 49794)
    row = fb.row_for(db, BOOKING_ID)
    assert (row["quote_refund_cents"], row["quote_fee_cents"], fb.quoted(row)) == (7114, 49794, True)


def test_a_cancel_is_only_made_after_a_quote_and_says_what_liteapi_reported(live, family):
    db, user, _ = family
    booked_flight(db, user)
    assert fb.cancel(db, "fam", BOOKING_ID, user) == (fb.NEEDS_QUOTE, None)
    assert [c for c in live.asked if c[0].endswith("/cancellations") and c[2] == {}] == []      # nothing was cancelled
    fb.quote(db, "fam", BOOKING_ID, user)
    st, c = fb.cancel(db, "fam", BOOKING_ID, user)
    assert (st, c.status, c.refund_cents, c.fee_cents) == (liteapi.OK, "CANCELLED_WITH_CHARGES", 7114, 49794)
    assert fb.row_for(db, BOOKING_ID)["status"] == "CANCELLED_WITH_CHARGES"
    again = fb.cancel(db, "fam", BOOKING_ID, user)      # cancelling again answers what was found and asks LiteAPI nothing more
    assert again[0] == liteapi.OK and again[1].refund_cents == 7114 and len([c for c in live.asked if c[0].endswith("/cancellations") and c[2] == {}]) == 1


def test_a_quote_left_too_long_is_asked_again(live, family):
    db, user, _ = family
    booked_flight(db, user)
    fb.quote(db, "fam", BOOKING_ID, user)
    with familydb.transaction(db):
        familydb.run(db, "UPDATE matrix_flights SET quote_at = :t", t=(datetime.fromisoformat(familydb.now()) - timedelta(minutes=16)).isoformat())
    assert fb.cancel(db, "fam", BOOKING_ID, user) == (fb.NEEDS_QUOTE, None)


def test_a_cancel_liteapi_has_accepted_is_pending_with_the_quoted_amounts_and_the_worker_finishes_it(live, family, monkeypatch):
    db, user, _ = family
    booked_flight(db, user)
    fb.quote(db, "fam", BOOKING_ID, user)
    with_answers(monkeypatch, cancel=(202, {"data": {"bookingId": BOOKING_ID, "status": "CANCELLATION_PENDING"}}), booking=status("CANCELLED_WITH_CHARGES"))
    st, c = fb.cancel(db, "fam", BOOKING_ID, user)
    assert (st, c.status, c.refund_cents) == (liteapi.PENDING, "PENDING", 7114)
    assert fb.row_for(db, BOOKING_ID)["status"] == "PENDING_CONFIRMATION"
    assert [r["booking_id"] for r in fb.due(db, datetime.fromisoformat(familydb.now()))] == [BOOKING_ID]
    fb.refresh(db, "fam", fb.row_for(db, BOOKING_ID), "job:fam")
    assert fb.cancelled(db, BOOKING_ID)["status"] == "CANCELLED_WITH_CHARGES" and fb.row_for(db, BOOKING_ID)["status"] == "CANCELLED_WITH_CHARGES"


def test_a_sample_booking_is_never_quoted_or_cancelled_through_liteapi(live, family):
    db, user, _ = family
    fb.book_sample(db, "fam", "tok-1", "trip-1", user, fb.prepare(PART, "fam", sample=True), fb.sample_segments(PART, DEPART, BACK), "2 adults")
    sid = familydb.rows(db, "SELECT booking_id FROM matrix_flights")[0]["booking_id"]
    assert fb.quote(db, "fam", sid, user) == (liteapi.GONE, None) and fb.cancel(db, "fam", sid, user) == (liteapi.GONE, None) and live.asked == []


def test_the_cancelled_email_goes_once_with_what_liteapi_reported(live, family, outbox):
    from gitaway import bookingmail
    db, user, _ = family
    booked_flight(db, user)
    outbox.clear()
    bookingmail.flight_cancelled(db, BOOKING_ID, "maya.okafor@example.com", 7114, 49794)
    bookingmail.flight_cancelled(db, BOOKING_ID, "maya.okafor@example.com", 7114, 49794)
    assert len(outbox) == 1 and outbox[0][1] == "Cancelled: flight SFO to SAN"
    assert "LiteAPI charged $497.94 for cancelling, and $71.14 comes back to the card you paid with." in outbox[0][2]


# ---- the family's trip ---------------------------------------------------------------------------------------------------

def a_trip(who):
    search, errors = tripstart.read({"place": "San Diego", "d": DEPART.isoformat(), "r": BACK.isoformat(), "a": "2", "k": "7", "home": "SFO"})
    assert not errors
    return tripstart.start(who, search)


def test_the_booked_flights_become_legs_on_the_trip_and_adding_twice_adds_once(live, family):
    from gitaway import importer
    db, user, who = family
    trip_id = a_trip(who)
    prebooked(db, user, trip_id=trip_id)
    row = fb.finish(db, "fam", "tok-1", user).row
    fb.add_to_trip(who, trip_id, row)
    fb.add_to_trip(who, trip_id, row)
    plan = importer.plan_of(who, trip_id)
    assert [(leg.name, leg.origin, leg.dest, leg.depart, leg.arrive, leg.confirmation, leg.booked_on) for leg in plan.legs] == [
        ("Nuitée Air 6278", "SFO", "SAN", datetime(2026, 12, 18, 15, 50), datetime(2026, 12, 18, 17, 29), "FH-26B-1VO6TJ6Z", "LiteAPI"),
        ("Nuitée Air 3060", "SAN", "SFO", datetime(2026, 12, 22, 18, 55), datetime(2026, 12, 22, 20, 34), "FH-26B-1VO6TJ6Z", "LiteAPI")]
    assert (plan.arrive_leg.dest, plan.depart_leg.origin) == ("SAN", "SAN")


def test_a_cancelled_flight_stays_on_the_trip_and_says_so(live, family):
    from gitaway import importer
    db, user, who = family
    trip_id = a_trip(who)
    prebooked(db, user, trip_id=trip_id)
    row = fb.finish(db, "fam", "tok-1", user).row
    fb.add_to_trip(who, trip_id, row)
    fb.mark_cancelled(who, trip_id, row["ref"])
    assert [leg.booked_on for leg in importer.plan_of(who, trip_id).legs] == ["Cancelled on LiteAPI"] * 2


# ---- what is kept ------------------------------------------------------------------------------------------------------------

def test_every_passenger_and_contact_is_dropped_after_seven_days_whatever_happened(live, family):
    db, user, _ = family
    prebooked(db, user)
    with familydb.transaction(db):
        familydb.run(db, "UPDATE matrix_flight_payments SET created_at = :t", t=(datetime.fromisoformat(familydb.now()) - timedelta(days=mb.PURGE_GUEST, minutes=1)).isoformat(timespec="seconds"))
    fb.purge(db)
    row = fb.payment(db, "tok-1")
    assert (row["travellers"], row["contact"], row["prebook_id"]) == ("", "", PREBOOK_ID)


def test_no_log_line_holds_a_passengers_name_or_email(live, family, caplog, monkeypatch):
    db, user, _ = family
    prebooked(db, user)
    with_answers(monkeypatch, book=(500, {"error": {"code": 1, "description": "maya.okafor@example.com Okafor"}}))
    fb.finish(db, "fam", "tok-1", user)
    assert "okafor" not in caplog.text.lower() and "maya" not in caplog.text.lower()
