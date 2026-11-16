"""The booking worker (F-274 review fixes, D-848): a daemon thread, started at boot like `draftjobs` and `planforme`, that visits every family's database once a minute.

    run_once(now)        finishes every payment left in `paying` for over STUCK_AFTER minutes (the guest paid, the browser never came back or LiteAPI did not answer then: `matrixbook.finish`
                         books it with the transaction id saved at prebook, once, under the same reference), puts the stay on its trip, and once a day runs `matrixbook.purge`
                         (unpaid prebooks dropped, guests' names, emails and numbers blanked after seven days) over every family, even one that never books again
    stuck_count()        how many payments are paid but not booked after STUCK_AFTER minutes, for /admin
    start() / stop()     the thread

Money is already taken when a row is `paying`, so this never asks whether booking is switched on: `liteapi._allowed` lets a TRANSACTION_ID book through for a live key whatever the switch says
(and never the sandbox's card), so the kill switch (`GITAWAY_LIVE_BOOKING=0`) stops new prebooks and strands nobody who has paid.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone

from fh_saas.db_tenant import get_or_create_tenant_db

from gitaway import familydb, liteapi, matrixbook as mb, members

log = logging.getLogger("gitaway.bookingjobs")
STUCK_AFTER = timedelta(minutes=10)
GIVE_UP_AFTER = timedelta(seconds=mb.HOLD) + timedelta(hours=1)      # a form older than the hold and an hour that LiteAPI says is unpaid or gone is given up on (D-851)
BACKOFF_BASE = timedelta(minutes=10)      # 10, 20, 40 minutes ... at most a day between two tries of one payment
PURGE_EVERY = timedelta(days=1)
_state = {"purged": None}
_thread = None
_lock = threading.Lock()
_stop = threading.Event()


def _tenant(tenant_id):
    db = get_or_create_tenant_db(tenant_id)
    try:
        familydb.ensure_schema(db, tenant_id)
    except Exception:
        db.conn.close()
        raise
    return db


def _before(now) -> str:
    return (now - STUCK_AFTER).isoformat(timespec="seconds")


def stuck_count(now=None) -> int:
    """Payments paid but not booked after STUCK_AFTER, over every family."""
    cut, n = _before(now or datetime.now(timezone.utc)), 0
    for tid in members.tenant_ids():
        try:
            db = _tenant(tid)
        except Exception as e:
            log.warning("booking jobs: a family could not be read (%s)", type(e).__name__)
            continue
        try:
            n += len(mb.stuck(db, cut))
        finally:
            db.conn.close()
    return n


def _finish_one(db, tenant_id, row, now) -> bool:
    got = mb.finish(db, tenant_id, row["id"], row["user_id"], budget="job:" + tenant_id)
    if not got.ok:
        age = now - datetime.fromisoformat(row["updated_at"])
        gone = got.status in (liteapi.NOT_PAID, liteapi.GONE) and age >= GIVE_UP_AFTER
        log.warning("booking jobs: stay %s of family %s is not booked (%s)%s", row["id"][:6], tenant_id[:6], got.status, ", given up: nobody paid" if gone else "")
        if gone:
            mb.give_up(db, row["id"])
        else:
            mb.back_off(db, row["id"], now, BACKOFF_BASE)
        return False
    try:      # best effort: the stay joins the trip as when the guest comes back to the return page
        mb.add_to_trip({"tenant_id": tenant_id, "user_id": row["user_id"], "email": ""}, got.done[0].trip_id, got.done)
    except Exception as e:  # noqa: BLE001
        log.warning("booking jobs: the stay could not be put on its trip (%s)", type(e).__name__)
    return True


def run_once(now=None) -> int:
    """Finish the stuck payments of every family and, once a day, purge every family's kept data. The number of stays booked."""
    now = now or datetime.now(timezone.utc)
    cut, booked = _before(now), 0
    purge = _state["purged"] is None or now - _state["purged"] >= PURGE_EVERY
    for tid in members.tenant_ids():
        try:
            db = _tenant(tid)
        except Exception as e:
            log.warning("booking jobs: a family could not be read (%s)", type(e).__name__)
            continue
        try:
            if liteapi.mode() != "off":
                for row in mb.stuck(db, cut, now.isoformat(timespec="seconds")):
                    booked += _finish_one(db, tid, row, now)
            if purge:
                mb.purge(db)
        except Exception as e:  # noqa: BLE001 - one family's trouble never stops the rest
            log.warning("booking jobs: %s", type(e).__name__)
        finally:
            db.conn.close()
    if purge:
        _state["purged"] = now
    return booked


def _loop(poll):
    while not _stop.wait(poll):
        try:
            run_once()
        except Exception:  # noqa: BLE001
            log.exception("booking worker")


def start(poll=60.0):
    """Start the worker, once per process. Returns the thread."""
    global _thread
    with _lock:
        if _thread is not None:
            return _thread
        _stop.clear()
        _thread = threading.Thread(target=_loop, args=(poll,), daemon=True, name="booking-jobs")
        _thread.start()
        return _thread


def stop() -> None:
    """Stop the worker (tests; a process just ends)."""
    global _thread
    with _lock:
        _stop.set()
        if _thread is not None:
            _thread.join(timeout=5)
        _thread = None
        _state["purged"] = None
