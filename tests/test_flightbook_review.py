"""F-276 review round 1 (D-980): the flight switch's defence in depth, a book whose payment is not a paid one, a pending cancel followed at capped gaps, passengers of an abandoned form dropped, and what
the captain is shown. Same recordings and helpers as tests/test_flightbook.py."""

from datetime import datetime, timedelta, timezone

from gitaway import familydb, flightbook as fb, liteapi
from tests.flight_support import BOOKING_ID, status
from tests.test_flightbook import family, live, prebooked, with_answers  # noqa: F401 (fixtures)


def paid(name):
    def edit(doc):
        doc["data"][0]["booking"]["paymentStatus"] = name
    return edit


def test_a_book_whose_payment_status_is_not_a_paid_one_is_not_a_booked_flight(live, family, monkeypatch):  # noqa: F811
    db, user, _ = family
    prebooked(db, user)
    with_answers(monkeypatch, book=paid("requires_payment_method"))
    res = fb.finish(db, "fam", "tok-1", user)
    assert res.status == liteapi.FAILED and res.row is None and familydb.rows(db, "SELECT * FROM matrix_flights") == []
    row = fb.payment(db, "tok-1")
    assert (row["status"], row["booking_id"]) == ("needs_help", BOOKING_ID)
    assert [r["id"] for r in fb.to_match(db, datetime.now(timezone.utc) + timedelta(minutes=20))] == ["tok-1"]


def test_the_two_paid_statuses_liteapi_uses_are_booked(live, family, monkeypatch):  # noqa: F811
    for name in ("succeeded", "completed"):
        db, user, _ = family
        prebooked(db, user, token=f"tok-{name}", stay_token=f"s-{name}")
        with_answers(monkeypatch, book=paid(name))
        assert fb.finish(db, "fam", f"tok-{name}", user).ok


def test_a_pending_cancel_is_followed_at_capped_gaps_and_then_left(live, family, monkeypatch):  # noqa: F811
    db, user, _ = family
    prebooked(db, user)
    row = fb.finish(db, "fam", "tok-1", user).row
    fb.quote(db, "fam", BOOKING_ID, user)
    f = with_answers(monkeypatch, cancel=(202, {"data": {"bookingId": BOOKING_ID, "status": "CANCELLATION_PENDING"}}), booking=status("CONFIRMED"))
    assert fb.cancel(db, "fam", BOOKING_ID, user)[0] == liteapi.PENDING
    now = datetime.fromisoformat(familydb.now())
    asked = 0
    for gap in (1, 4, 11, 31, 61, 61, 61):
        now += timedelta(minutes=gap)
        for r in fb.due(db, now):
            fb.refresh(db, "fam", r, "job:fam", now)
            asked += 1
    lookups = [c for c in f.asked if c[0].endswith(BOOKING_ID)]
    assert asked == len(lookups) == len(fb.CHECK_AFTER)      # five lookups at growing gaps, then no more
    assert fb.due(db, now + timedelta(days=2)) == [] and row["booking_id"] == BOOKING_ID


def test_the_passengers_of_a_form_left_open_for_a_day_are_dropped_and_the_ids_stay(live, family):  # noqa: F811
    db, user, _ = family
    prebooked(db, user)
    with familydb.transaction(db):
        familydb.run(db, "UPDATE matrix_flight_payments SET created_at = :t", t=(datetime.now(timezone.utc) - timedelta(days=1, minutes=1)).isoformat(timespec="seconds"))
    fb.purge(db)
    row = fb.payment(db, "tok-1")
    assert (row["travellers"], row["status"], row["transaction_id"] != "", row["charge_cents"] > 0) == ("", "paying", True, True) and row["contact"] != ""


def test_the_captain_is_shown_only_ids_for_a_form_left_over_fifteen_minutes(live, family):  # noqa: F811
    db, user, _ = family
    prebooked(db, user)
    now = datetime.now(timezone.utc)
    assert fb.to_match(db, now + timedelta(minutes=5)) == []
    rows = fb.to_match(db, now + timedelta(minutes=20))
    assert [(r["id"], r["status"]) for r in rows] == [("tok-1", "paying")]
    assert set(rows[0]) == {"id", "status", "transaction_id", "charge_cents", "created_at", "updated_at"}      # no traveller, no contact
