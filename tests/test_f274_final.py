"""F-274 final security check (D-852): a paid guest is never deleted by a guess (only LiteAPI's "not paid" gives up; anything else past the hour is `needs_help`, counted and listed on /admin and
kept), the worker's own budget never spends or blocks anything else, a paid row is tried before abandoned ones, the back-off columns come by migration for fresh and older family databases."""
import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from gitaway import bookingjobs, familydb, liteapi, matrixbook as mb, session as ses
from tests.test_f274_review import aged
from tests.test_liteapi_pay import Pay
from tests.test_matrixbook_page import person
from tests.test_matrixbook_pay import family, live, pay, prepared  # noqa: F401 (fixtures)


@pytest.fixture(autouse=True)
def _fresh_budgets():
    """The booking budgets are per day and kept in community.db: each test starts with none spent."""
    from gitaway import community
    with community.connect() as db:
        db.conn.execute(text("DELETE FROM liteapi_bookings"))
        db.conn.commit()


def books(box):
    return [json.loads(b) if isinstance(b, (str, bytes)) else b for u, _, b, _ in box.asked if u.endswith("/rates/book")]


def tenant():
    return person()["tenant_id"]


# ---- HIGH: a paid guest after an outage and a 410 --------------------------------------------------------------------------------------------

def test_paid_then_an_outage_then_410_is_needs_help_visible_on_admin_and_never_deleted(live, family, client, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    aged(db, prep.token, minutes=11)
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: (503, "application/json", b"{}"))
    start = datetime.now(timezone.utc)
    for i in range(0, 120):
        bookingjobs.run_once(start + timedelta(minutes=i))
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: (410, "application/json", b'{"error": {"code": 2001}}'))
    for i in range(120, 3000, 7):
        bookingjobs.run_once(start + timedelta(minutes=i))
    row = mb.payment(db, prep.token)
    assert row["status"] == "needs_help" and row["guest_email"] == "test.traveler@example.com"      # not unpaid, not blanked, not deleted
    assert bookingjobs.stuck_count(start + timedelta(minutes=3000)) == 1
    bookingjobs._state["purged"] = None
    bookingjobs.run_once(start + timedelta(minutes=3001))      # a purge pass
    assert mb.payment(db, prep.token) is not None
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "ari.rivera@example.com")
    html = client.get("/admin").text
    assert re.search(r'id="ad-stuck"[^>]*>\s*1\s*<', html)
    ref = mb.reference(tenant(), prep.token, 0)
    assert prep.token[:6] in html and "tr_cts_j_DBi8RkjWF1hJDzmsryP" in html and ref in html and "Needs a look" in html


def test_a_needs_help_row_is_still_tried_and_books_when_liteapi_recovers_and_gives_up_only_on_not_paid(live, family, monkeypatch):
    db, user = family
    a, b = prepared(live), prepared(live)
    pay(db, user, a)
    pay(db, user, b)
    for p in (a, b):
        aged(db, p.token, minutes=120)
        familydb.run(db, "UPDATE matrix_payments SET status = 'needs_help' WHERE id = :i", i=p.token)
    db.conn.commit()
    bookingjobs._state["purged"] = datetime.now(timezone.utc)

    ref_b = mb.reference(tenant(), b.token, 0)

    def box(url, headers, body, timeout, method=""):
        sent = json.loads(body)
        return Pay(book="book_unpaid.json" if sent["clientReference"] == ref_b else "book_nonrefundable.json")(url, headers, body, timeout, method)
    monkeypatch.setattr(liteapi, "TRANSPORT", box)
    bookingjobs.run_once(datetime.now(timezone.utc))
    assert mb.payment(db, a.token)["status"] == "booked" and mb.payment(db, b.token)["status"] == "unpaid"      # LiteAPI's own "not paid" is the one thing that ends it


def test_an_admin_resolves_a_needs_help_row_and_the_purge_then_deletes_it(live, family, client, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    familydb.run(db, "UPDATE matrix_payments SET status = 'needs_help' WHERE id = :i", i=prep.token)
    db.conn.commit()
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "ari.rivera@example.com")
    r = client.post("/admin/payments/resolve", data={"family": tenant(), "token": prep.token}, follow_redirects=False)
    assert r.status_code == 303
    row = mb.payment(db, prep.token)
    assert row["status"] == "resolved" and not row["guest_email"] and row["transaction_id"]
    mb.purge(db)
    assert mb.payment(db, prep.token) is None
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "someone.else@example.com")
    again = prepared(live)
    pay(db, user, again)
    familydb.run(db, "UPDATE matrix_payments SET status = 'needs_help' WHERE id = :i", i=again.token)
    db.conn.commit()
    assert client.post("/admin/payments/resolve", data={"family": tenant(), "token": again.token}).status_code == 404 and mb.payment(db, again.token)["status"] == "needs_help"


# ---- MEDIUM: our own limits are not LiteAPI's failures ---------------------------------------------------------------------------------------

def test_a_spent_allowance_waits_for_midnight_does_not_count_an_attempt_and_stops_that_family(live, family, monkeypatch):
    db, user = family
    toks = []
    for _ in range(3):
        p = prepared(live)
        pay(db, user, p)
        aged(db, p.token, minutes=30)
        toks.append(p.token)
    box = Pay(book="book_unpaid.json")
    monkeypatch.setattr(liteapi, "TRANSPORT", box)
    monkeypatch.setattr(liteapi, "PER_JOB_BOOK_A_DAY", 1)
    monkeypatch.setattr(bookingjobs, "BACKOFF_BASE", timedelta(0))
    now = datetime.now(timezone.utc)
    bookingjobs._state["purged"] = now
    bookingjobs.run_once(now)
    assert len(books(box)) == 1      # one call spent the day's allowance
    bookingjobs.run_once(now + timedelta(minutes=1))
    assert len(books(box)) == 1      # and the rest are not even tried, in this pass or the next
    rows = [mb.payment(db, t) for t in toks]
    waiting = [r for r in rows if r["next_try_at"].startswith((now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00"))]
    assert len(waiting) >= 1 and all((r["attempts"] or 0) <= 1 for r in rows) and sum((r["attempts"] or 0) for r in rows) == 1      # only the real LiteAPI answer counted


def test_a_busy_gate_waits_a_few_minutes_without_an_attempt(live, family, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    aged(db, prep.token, minutes=30)
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay())
    monkeypatch.setattr(liteapi, "_BOOK_TURN", type("T", (), {"acquire": lambda self, timeout=None: False, "release": lambda self: None})())
    now = datetime(2026, 12, 1, 15, 30, tzinfo=timezone.utc)
    bookingjobs._state["purged"] = now
    bookingjobs.run_once(now)
    row = mb.payment(db, prep.token)
    assert (row["attempts"] or 0) == 0 and datetime.fromisoformat(row["next_try_at"]) == now + timedelta(minutes=bookingjobs.BUSY_WAIT_MINUTES)


def test_a_fresh_row_is_tried_before_abandoned_ones(live, family, monkeypatch):
    """Six abandoned forms and one paid, in one family: the paid one (the newest) is tried first, whatever the others do."""
    db, user = family
    old = []
    for i in range(6):
        p = prepared(live)
        pay(db, user, p)
        aged(db, p.token, minutes=60 + i)
        old.append(p.token)
    paid = prepared(live)
    pay(db, user, paid)
    aged(db, paid.token, minutes=11)
    good = mb.reference(tenant(), paid.token, 0)
    order = []

    def box(url, headers, body, timeout, method=""):
        sent = json.loads(body)
        order.append(sent["clientReference"])
        return Pay(book="book_nonrefundable.json" if sent["clientReference"] == good else "book_unpaid.json")(url, headers, body, timeout, method)
    monkeypatch.setattr(liteapi, "TRANSPORT", box)
    bookingjobs._state["purged"] = datetime.now(timezone.utc)
    bookingjobs.run_once(datetime.now(timezone.utc))
    assert order[0] == good and mb.payment(db, paid.token)["status"] == "booked"


# ---- LOW: the worker's calls are its own at the site level too -------------------------------------------------------------------------------------

def test_worker_calls_do_not_count_against_the_sites_booking_total_and_have_a_site_cap_of_their_own(monkeypatch):
    live_box = Pay()
    monkeypatch.setenv("LITEAPI_KEY", "live_not-real")
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "1")
    monkeypatch.setattr(liteapi, "TRANSPORT", live_box)
    monkeypatch.setattr(liteapi, "BOOK_A_DAY", 2)
    monkeypatch.setattr(liteapi, "JOB_BOOK_A_DAY", 3)
    from tests.test_liteapi_pay import GUEST
    jobs = [liteapi.book("p", GUEST, f"r{i}", f"job:fam{i}", transaction_id="tr_1").status for i in range(5)]
    assert jobs == [liteapi.OK, liteapi.OK, liteapi.OK, liteapi.OVER, liteapi.OVER]      # the jobs' own site cap of 3; they spent none of the interactive 2
    assert [liteapi.prebook("o", f"fam{i}", sdk=True).status for i in range(3)] == [liteapi.OK, liteapi.OK, liteapi.OVER]
    assert liteapi.can_search("job:famX", True) is False and liteapi.can_search("famX", True) is False


# ---- LOW: the columns come by migration -------------------------------------------------------------------------------------------------------------

def columns(db):
    return {c["name"] for c in familydb.rows(db, "PRAGMA table_info(matrix_payments)")}


def test_a_fresh_family_database_gets_the_back_off_columns_by_migration(live, family):
    db, user = family
    assert {"attempts", "next_try_at"} <= columns(db)
    assert (familydb.MIGRATIONS_DIR / "004_payment_backoff.sql").exists()
    assert {4, 5} <= set(db.conn.execute(text("SELECT version FROM _migrations")).scalars().all())
    baseline = {t[1]: t[0] for t in familydb.FAMILY_TABLES}["matrix_payments"] if False else None  # noqa: F841
    from gitaway.familydb_matrix import MatrixPayment
    assert "attempts" not in MatrixPayment.__annotations__ and "next_try_at" not in MatrixPayment.__annotations__      # not in the baseline: the migration adds them


def test_an_older_family_database_with_the_old_table_gets_them_too(live, family):
    db, user = family
    prep = prepared(live)
    mb.save_prebook(db, prep.token, user, prep.rows[0])
    db.conn.execute(text("ALTER TABLE matrix_payments DROP COLUMN attempts"))
    db.conn.execute(text("ALTER TABLE matrix_payments DROP COLUMN next_try_at"))
    db.conn.execute(text("DELETE FROM _migrations WHERE version IN (4, 5)"))
    db.conn.commit()
    assert not {"attempts", "next_try_at"} & columns(db)
    familydb.forget_schema_cache()
    with ses.family(person()) as fam:
        assert {"attempts", "next_try_at"} <= columns(fam.db)
        row = mb.payment(fam.db, prep.token)
        assert row["status"] == "prebooked" and (row["attempts"] or 0) == 0 and (row["next_try_at"] or "") == ""      # the row kept, the columns empty


# ---- LOW: the purge has its own try -----------------------------------------------------------------------------------------------------------------

def test_a_worker_error_never_skips_the_purge(live, family, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    aged(db, prep.token, days=8)

    def boom(*a, **k):
        raise RuntimeError("worker trouble")
    monkeypatch.setattr(mb, "stuck", boom)
    bookingjobs.stop()
    bookingjobs.run_once()
    assert mb.payment(db, prep.token)["guest_email"] in ("", None)
