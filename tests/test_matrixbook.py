"""F-233: booking a square's stays through LiteAPI's sandbox (gitaway/matrixbook.py): the lead guest is checked, each stay is prebooked then booked once, the booking is kept in
the family's database, and a second press never books twice. Answers are the sandbox's own recordings; no test reaches the network."""
import json
import logging
from dataclasses import replace
from datetime import date, timedelta

import pytest

from gitaway import familydb, liteapi, matrixbook as mb, session as ses, tripmatrix as tm
from tests.test_liteapi import KEY, raw
from tests.test_liteapi_book import BOOK, PREBOOK, Book
from tests.test_signin import person, sign_in

DAYS = [("San Diego", date(2026, 12, 14), date(2026, 12, 17))]
PART = tm.StayPart("San Diego", 3, "Margaritaville Hotel San Diego Gaslamp Quarter", "Standard Room, 2 Queen Beds", "room only", False, 12000, "", "", 47900, "offer-1")
GUEST = liteapi.Guest("Test", "Traveler", "test.traveler@example.com")
SQ = ("sandiego|2026-12-14", (("a", "2"), ("lane", "sandiego"), ("w", "2026-12-14")))


@pytest.fixture
def sandbox(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    f = Book()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    mb.forget()
    return f


@pytest.fixture
def family(client):
    sign_in(client)
    who = person()
    with ses.family(who) as fam:
        yield fam.db, who["tenant_id"]


def test_the_lead_guest_is_trimmed_and_checked_on_our_side():
    got, errors = mb.clean_guest("  Anne-Marie ", " O’Neil  Jr. ", " anne@example.com ")
    assert got == liteapi.Guest("Anne-Marie", "O’Neil Jr.", "anne@example.com") and errors == {}
    for first, last, email, bad in [("", "T", "a@b.co", "first"), ("T", "", "a@b.co", "last"), ("T1", "T", "a@b.co", "first"), ("<b>", "T", "a@b.co", "first"),
                                    ("T" * 41, "T", "a@b.co", "first"), ("T", "T", "nope", "email"), ("T", "T", "a@b", "email"), ("T", "T", "a@@b.co", "email"),
                                    ("T", "T", "a b@c.co", "email"), ("T", "T", "a\x00b@c.co", "email"), ("T", "T", "a\x7fb@c.co", "email"), ("T", "T", "a\u202eb@c.co", "email"), ("T", "T", "é@c.co", "email"), ("T", "T", "a..b@c.co", "email"), ("T", "T", "a@b.co" + "x" * 120, "email"), ("T", "T", "", "email")]:
        got, errors = mb.clean_guest(first, last, email)
        assert got is None and list(errors) == [bad], (first, last, email)


def test_prepare_prebooks_each_stays_offer_and_reads_its_final_price(sandbox):
    prep = mb.prepare((PART,), DAYS, "fam")
    assert prep.ok and prep.words == "Sandbox booking: nothing is charged" and prep.token
    row = prep.rows[0]
    assert (row.place, row.prebook.prebook_id, row.prebook.cents, row.total_cents) == ("San Diego", "mxB7A2bfb", 35900, 47900)
    assert prep.total_cents == 47900 and prep.changed is False      # the square said $479, the room still is
    assert [(u, b) for u, _, b in sandbox.asked] == [(PREBOOK, {"offerId": "offer-1", "usePaymentSdk": False})]


def test_a_price_that_moved_since_the_square_is_said(sandbox):
    prep = mb.prepare((replace(PART, cents=45000),), DAYS, "fam")
    assert prep.changed is True and prep.total_cents == 47900


def test_a_room_that_is_gone_ends_the_prebook_with_no_rows(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "TRANSPORT", Book(prebook=(400, raw("prebook_bad_offer.json"))))
    prep = mb.prepare((PART,), DAYS, "fam")
    assert (prep.status, prep.rows, prep.ok) == (liteapi.GONE, (), False)


def test_a_rate_for_other_nights_than_the_squares_is_never_booked_as_them(sandbox):
    prep = mb.prepare((PART,), [("San Diego", date(2026, 12, 12), date(2026, 12, 16))], "fam")
    assert (prep.status, prep.rows) == (liteapi.FAILED, ())


def test_a_sample_square_is_prebooked_by_a_stand_in_and_never_reaches_liteapi(sandbox):
    prep = mb.prepare((PART,), DAYS, "fam", sample=True)
    assert prep.ok and prep.sample and prep.words == "Sample booking: nothing is booked or charged" and prep.total_cents == 47900
    assert sandbox.asked == []


def test_a_held_room_is_kept_for_its_family_only(sandbox):
    prep = mb.prepare((PART,), DAYS, "fam")
    token = mb.hold("fam", prep, SQ)
    assert mb.held("fam", token, SQ) is prep and mb.held("other", token, SQ) is None and mb.held("fam", "nope", SQ) is None
    assert mb.held("fam", token, ("san-diego|2026-12-13", SQ[1])) is None and mb.held("fam", token, (SQ[0], (("a", "b"),))) is None      # bound to its square


def test_a_family_keeps_five_rooms_and_its_oldest_goes_first_leaving_other_families_alone(sandbox):
    preps = [mb.prepare((PART,), DAYS, "fam") for _ in range(6)]
    tokens = [mb.hold("fam", p, SQ) for p in preps]
    other = mb.prepare((PART,), DAYS, "other")
    keep = mb.hold("other", other, SQ)
    assert [mb.held("fam", t, SQ) is not None for t in tokens] == [False, True, True, True, True, True] and mb.held("other", keep, SQ) is other
    for _ in range(300):      # a flood by one family never pushes another's out
        mb.hold("fam", mb.prepare((PART,), DAYS, "fam", sample=True), SQ)
    assert mb.held("other", keep, SQ) is other


def test_a_person_may_press_book_five_times_a_minute_and_twenty_a_day(monkeypatch):
    from sqlalchemy import text
    from gitaway import community
    assert [mb.allow("p1") for _ in range(6)] == [True] * 5 + [False]
    assert mb.allow("p2") is True                                              # counted per person
    with community.connect() as db:                                            # a minute later the minute's count is clear, the day's is not
        db.conn.execute(text("UPDATE book_presses SET at = :t WHERE person = 'p1'"), {"t": (liteapi.now() - timedelta(minutes=2)).isoformat()})
        db.conn.commit()
    assert mb.allow("p1") is True
    monkeypatch.setattr(mb, "PER_DAY", 6)
    assert mb.allow("p1") is False                                             # 6 within the day


def test_nothing_about_the_guest_is_kept_in_the_family_database(sandbox, family):
    db, fam = family
    mb.book(mb.prepare((PART,), DAYS, fam), GUEST, db, fam, "trip-1", "u1")
    assert {c["name"] for c in familydb.rows(db, "PRAGMA table_info(matrix_bookings)")} >= {"booking_id", "hotel", "total_cents"}
    assert not {c["name"] for c in familydb.rows(db, "PRAGMA table_info(matrix_bookings)")} & {"guest_name", "guest_email", "email", "name"}
    assert "traveler" not in json.dumps(familydb.rows(db, "SELECT * FROM matrix_bookings")).lower()


def test_a_duplicate_reference_we_hold_no_row_for_is_looked_up_and_stored(monkeypatch, family):
    db, fam = family
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    seen = []

    def fake(url, headers, body, timeout):
        seen.append(url)
        if url == PREBOOK:
            return 200, "application/json", raw("prebook.json")
        if url == BOOK:
            return 400, "application/json", raw("book_duplicate.json")
        return 200, "application/json", raw("bookings_by_reference.json")
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    prep = mb.prepare((PART,), DAYS, fam)
    got = mb.book(prep, GUEST, db, fam, "trip-1", "u1")
    assert got.ok and got.done[0].booking_id == "_5hnX-MI7" and seen[-1].startswith("https://api.liteapi.travel/v3.0/bookings?clientReference=" + mb.reference(fam, prep.token, 0))


def test_a_duplicate_with_no_booking_to_find_is_never_said_to_be_done(monkeypatch, family):
    db, fam = family
    monkeypatch.setenv("LITEAPI_KEY", KEY)

    def fake(url, headers, body, timeout):
        if url == PREBOOK:
            return 200, "application/json", raw("prebook.json")
        if url == BOOK:
            return 400, "application/json", raw("book_duplicate.json")
        return 200, "application/json", b'{"data": []}'
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    got = mb.book(mb.prepare((PART,), DAYS, fam), GUEST, db, fam, "trip-1", "u1")
    assert (got.status, got.done, got.left, got.ok) == (liteapi.DUPLICATE, (), 1, False)
    assert "Check your bookings" in mb.SAID[liteapi.DUPLICATE]
    assert familydb.rows(db, "SELECT COUNT(*) AS n FROM matrix_bookings")[0]["n"] == 0


def test_booking_stores_the_stay_with_liteapis_id_and_a_second_press_books_nothing_more(sandbox, family):
    db, fam = family
    prep = mb.prepare((PART,), DAYS, fam)
    first = mb.book(prep, GUEST, db, fam, "trip-1", "u1")
    assert first.ok and first.left == 0
    got = first.done[0]
    assert (got.booking_id, got.hotel, got.confirmation, got.total_cents, got.due_at_stay_cents, got.sample) == \
           ("_5hnX-MI7", "Margaritaville Hotel San Diego Gaslamp Quarter", "test", 47900, 12000, False)
    assert (got.checkin, got.checkout, got.trip_id) == ("2026-12-14", "2026-12-17", "trip-1")
    again = mb.book(prep, GUEST, db, fam, "trip-1", "u1")
    assert again.ok and again.done == first.done
    assert [u for u, _, _ in sandbox.asked].count(BOOK) == 1 and again.done == first.done
    assert familydb.rows(db, "SELECT COUNT(*) AS n FROM matrix_bookings")[0]["n"] == 1


def test_a_stay_liteapi_will_not_book_stores_nothing_and_says_what_is_left(monkeypatch, family):
    db, fam = family
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "TRANSPORT", Book(book=(503, b"{}")))
    prep = mb.prepare((PART,), DAYS, fam)
    got = mb.book(prep, GUEST, db, fam, "trip-1", "u1")
    assert (got.status, got.done, got.left, got.ok) == (liteapi.FAILED, (), 1, False)
    assert familydb.rows(db, "SELECT COUNT(*) AS n FROM matrix_bookings")[0]["n"] == 0


def test_a_square_of_two_stays_books_both_and_a_failed_second_keeps_the_first(monkeypatch, family):
    db, fam = family
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    ok = Book()
    monkeypatch.setattr(liteapi, "TRANSPORT", ok)
    parts, days = (PART, PART), DAYS + [("Los Angeles", date(2026, 12, 14), date(2026, 12, 17))]
    prep = mb.prepare(parts, days, fam)
    calls = {"n": 0}

    def second_fails(url, headers, body, timeout):
        if url == BOOK:
            calls["n"] += 1
            if calls["n"] == 2:
                return 503, "application/json", b"{}"
        return ok(url, headers, body, timeout)
    monkeypatch.setattr(liteapi, "TRANSPORT", second_fails)
    got = mb.book(prep, GUEST, db, fam, "trip-1", "u1")
    assert (got.status, len(got.done), got.left) == (liteapi.FAILED, 1, 1)
    monkeypatch.setattr(liteapi, "TRANSPORT", ok)
    final = mb.book(prep, GUEST, db, fam, "trip-1", "u1")
    assert final.ok and len(final.done) == 2 and [u for u, _, _ in ok.asked].count(BOOK) == 2      # the first stay once, then only the second on the retry


def test_a_sample_booking_is_stored_as_sample_with_no_call(sandbox, family):
    db, fam = family
    prep = mb.prepare((PART,), DAYS, fam, sample=True)
    got = mb.book(prep, GUEST, db, fam, "trip-1", "u1").done[0]
    assert got.sample and got.booking_id.startswith("SAMPLE-") and got.confirmation == "SAMPLE" and sandbox.asked == []


def test_nothing_the_guest_typed_reaches_a_log(sandbox, family, caplog):
    db, fam = family
    with caplog.at_level(logging.DEBUG):
        mb.book(mb.prepare((PART,), DAYS, fam), GUEST, db, fam, "trip-1", "u1")
    assert "test.traveler" not in " ".join(r.getMessage() for r in caplog.records)
