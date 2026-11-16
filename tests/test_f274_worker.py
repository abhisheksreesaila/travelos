"""F-274, the worker gives up on unpaid forms (D-851): a form opened and never paid is not retried every minute for ever. LiteAPI's not-paid (2014) and hold-gone (410) are their own
statuses; such a row is given up on after HOLD + an hour and deleted by the purge; other failures back off (10 min, 20, 40, to a day); the worker spends its own small budget, never the
family's own booking allowance; /admin counts only what LiteAPI did not refuse as unpaid; and a stay the worker books really lands on its trip."""
import logging
from datetime import datetime, timedelta, timezone

from gitaway import bookingjobs, familydb, liteapi, matrixbook as mb, session as ses
from tests.test_f274_review import aged
from tests.test_liteapi_pay import GUEST, Pay, live as live_key  # noqa: F401
from tests.test_matrixbook_live import pay_pane, real, token  # noqa: F401 (real is a fixture)
from tests.test_matrixbook_page import person, stays_booked
from tests.test_matrixbook_pay import family, live, pay, prepared  # noqa: F401 (fixtures)


def books(box):
    return [1 for u, *_ in box.asked if u.endswith("/rates/book")]


def tenant():
    return person()["tenant_id"]


# ---- LiteAPI's own words ---------------------------------------------------------------------------------------------------------------------

def test_not_paid_and_hold_gone_are_their_own_statuses_apart_from_liteapi_down(live_key, monkeypatch):
    got = lambda name, status=None: liteapi.book("p", GUEST, "r", "fam", transaction_id="tr_1").status
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(book="book_unpaid.json"))
    assert got("") == liteapi.NOT_PAID
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: (410, "application/json", b'{"error": {"code": 2001, "message": "gone"}}'))
    assert got("") == liteapi.GONE
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: (503, "application/json", b"{}"))
    assert got("") == liteapi.FAILED


# ---- the loop that was ------------------------------------------------------------------------------------------------------------------------

def test_sixty_passes_on_an_abandoned_form_send_a_handful_of_calls_and_the_family_can_still_book(live, family, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)                       # the form was opened and never paid
    aged(db, prep.token, minutes=30)
    box = Pay(book="book_unpaid.json")
    monkeypatch.setattr(liteapi, "TRANSPORT", box)
    start = datetime.now(timezone.utc)
    for i in range(60):
        bookingjobs.run_once(start + timedelta(minutes=i))
    assert 1 <= len(books(box)) <= 5                                               # tries at once, after 10, after 20 more, then 40 more: not every minute
    for i in range(60, 100):
        bookingjobs.run_once(start + timedelta(minutes=i))
    assert mb.payment(db, prep.token)["status"] == "unpaid" and len(books(box)) <= 5      # past the hold and an hour, LiteAPI said not paid: given up
    n = len(books(box))
    for i in range(100, 160):
        bookingjobs.run_once(start + timedelta(minutes=i))
    assert len(books(box)) == n                                                    # and never asked again
    assert liteapi.can_search(tenant(), True) is True                              # the family's own booking allowance is untouched
    assert liteapi.prebook("o", tenant(), sdk=True).ok


def test_the_worker_spends_its_own_small_budget_not_the_familys(live, family, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    aged(db, prep.token, minutes=30)
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(book="book_unpaid.json"))
    monkeypatch.setattr(liteapi, "PER_JOB_BOOK_A_DAY", 1)
    monkeypatch.setattr(bookingjobs, "BACKOFF_BASE", timedelta(0))
    now = datetime.now(timezone.utc)
    for i in range(5):
        bookingjobs.run_once(now + timedelta(seconds=i))
    assert len([1 for u, *_ in liteapi.TRANSPORT.asked if u.endswith("/rates/book")]) == 1      # the job budget of 1 call a day
    assert liteapi.can_search(tenant(), True) is True


def test_other_failures_back_off_ten_twenty_forty_minutes_and_a_day_at_most(live, family, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    aged(db, prep.token, minutes=11)
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: (503, "application/json", b"{}"))
    now = datetime.now(timezone.utc)
    gaps = []
    for _ in range(9):
        bookingjobs.run_once(now)
        row = mb.payment(db, prep.token)
        nxt = datetime.fromisoformat(row["next_try_at"])
        gaps.append(round((nxt - now).total_seconds() / 60))
        now = nxt + timedelta(seconds=1)
        aged(db, prep.token, minutes=11)      # keep it "stuck" for the stuck rule; the back-off alone decides
        familydb.run(db, "UPDATE matrix_payments SET created_at = :t", t=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        db.conn.commit()
    assert gaps[:4] == [10, 20, 40, 80] and gaps[-1] == 24 * 60 and mb.payment(db, prep.token)["attempts"] == 9
    assert mb.payment(db, prep.token)["status"] == "paying"      # a failure that is not "unpaid" or "gone" never gives up


def test_a_row_that_is_not_due_yet_is_left_alone(live, family, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    aged(db, prep.token, minutes=30)
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(book="book_unpaid.json"))
    now = datetime.now(timezone.utc)
    bookingjobs.run_once(now)
    n = len(books(liteapi.TRANSPORT))
    bookingjobs.run_once(now + timedelta(minutes=5))
    assert len(books(liteapi.TRANSPORT)) == n


# ---- counted, deleted ---------------------------------------------------------------------------------------------------------------------------

def test_admin_counts_only_what_liteapi_did_not_refuse_as_unpaid_and_the_purge_deletes_it(live, family, monkeypatch):
    db, user = family
    a, b = prepared(live), prepared(live)
    pay(db, user, a)
    pay(db, user, b)
    aged(db, a.token, minutes=120)
    aged(db, b.token, minutes=30)
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(book="book_unpaid.json"))
    assert bookingjobs.stuck_count() == 2
    bookingjobs._state["purged"] = datetime.now(timezone.utc)      # today's purge has run: this pass only tries bookings
    bookingjobs.run_once(datetime.now(timezone.utc))
    assert mb.payment(db, a.token)["status"] == "unpaid" and mb.payment(db, b.token)["status"] == "paying"
    assert bookingjobs.stuck_count() == 1
    mb.purge(db)
    assert mb.payment(db, a.token) is None and mb.payment(db, b.token)["guest_email"] == "test.traveler@example.com"


def test_a_row_still_inside_the_hold_and_an_hour_is_not_given_up_on(live, family, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    aged(db, prep.token, minutes=40)
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(book="book_unpaid.json"))
    bookingjobs.run_once(datetime.now(timezone.utc))
    assert mb.payment(db, prep.token)["status"] == "paying"


def test_a_failure_in_the_log_names_the_row_by_prefixes_and_nothing_personal(live, family, monkeypatch, caplog):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    aged(db, prep.token, minutes=30)
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(book="book_unpaid.json"))
    with caplog.at_level(logging.WARNING):
        bookingjobs.run_once(datetime.now(timezone.utc))
    line = next(r.getMessage() for r in caplog.records if r.name == "gitaway.bookingjobs")
    assert prep.token[:6] in line and tenant()[:6] in line and prep.token not in line and tenant() not in line
    assert "example.com" not in caplog.text and "Traveler" not in caplog.text


# ---- the worker's stay lands on a real trip -------------------------------------------------------------------------------------------------------

def test_a_stay_the_worker_books_is_on_the_familys_real_trip(real, client):
    html, _ = pay_pane(client)                 # the square became the family's trip; the guest was kept; the guest never came back
    with ses.family(person()) as fam:
        aged(fam.db, token(html), minutes=30)
    assert stays_booked() == []                # nothing is booked yet
    assert bookingjobs.run_once() == 1
    from gitaway import importer
    row = stays_booked()[0]
    lodging = importer.plan_of(person(), row["trip_id"]).hotels
    assert [(h.confirmation, h.booked_on) for h in lodging] == [("uuJxfM0--", "LiteAPI")]
