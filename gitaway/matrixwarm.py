"""The trip matrix's head start (F-229, D-447): when /plan/matrix is drawn off the showcase, the squares the family will look at first start searching at
once, on worker threads, so they are under way before the page's script asks for them; /plan/matrix/tile then joins the search in flight (liteapi's
single flight) or reads the answer it left in the cache.

    warm(squares, adults=, kid_ages=, home=, family=)   queue squares ((Lane, Window), ...) in the order given; returns how many were queued. Never waits.
    run_pending()                                       do every queued square now, on this thread (tests; the workers do it otherwise)
    stop()                                              stop the workers (tests)

What is queued is `tripmatrix.head_start`: the asked square, the asked start day for every place, the asked place on every day. Nothing is queued for a
family whose daily LiteAPI budget (or the site's) is spent, and a worker asks again before each square. One small pool (WORKERS) and a bounded queue
(QUEUE_MAX, the rest dropped): a tab that keeps reloading cannot start unbounded work, and every real call still goes through liteapi's gate. The queue
lives in the process: a restart loses a head start, never an answer. `ASYNC` is False in the tests (conftest), which run the queue themselves.
"""

import logging
import queue
import threading

from gitaway import gridsource, liteapi

WORKERS = 3                  # squares searched at once; their calls share liteapi's gate (AT_ONCE)
QUEUE_MAX = 64
ASYNC = True
_Q: queue.Queue = queue.Queue(QUEUE_MAX)
_queued: set = set()
_lock = threading.Lock()
_threads: list = []
_stop = threading.Event()
log = logging.getLogger(__name__)


def _job_key(lane, w, adults, kid_ages, home, family):
    return (lane.key, w.key, adults, tuple(kid_ages), home, family)


def warm(squares, adults=2, kid_ages=(), home="", family="") -> int:
    if not liteapi.key() or not home or not liteapi.can_search(family):
        return 0
    n = 0
    for lane, w in squares:
        k = _job_key(lane, w, adults, kid_ages, home, family)
        with _lock:
            if k in _queued:
                continue
            try:
                _Q.put_nowait((lane, w, adults, tuple(kid_ages), home, family))
            except queue.Full:
                break
            _queued.add(k)
        n += 1
    if n and ASYNC:
        _start()
    return n


def _one(job) -> None:
    lane, w, adults, kid_ages, home, family = job
    try:
        if not liteapi.can_search(family) or gridsource.square(lane, w, adults, kid_ages, home, family, peek=True) is not None:
            return
        gridsource.square(lane, w, adults, kid_ages, home, family)
    except Exception:      # noqa: BLE001 (a head start that fails leaves the square to its tile)
        log.exception("matrix head start failed for %s|%s", lane.key, w.key)
    finally:
        with _lock:
            _queued.discard(_job_key(lane, w, adults, kid_ages, home, family))


def _work() -> None:
    while not _stop.is_set():
        try:
            job = _Q.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            _one(job)
        finally:
            _Q.task_done()


def _start() -> None:
    with _lock:
        _threads[:] = [t for t in _threads if t.is_alive()]
        while len(_threads) < WORKERS:
            t = threading.Thread(target=_work, daemon=True, name=f"matrix-warm-{len(_threads)}")
            t.start()
            _threads.append(t)


def stop() -> None:
    """Stop the workers (tests: a worker left from one test must not take the next test's queue)."""
    _stop.set()
    with _lock:
        threads = list(_threads)
        _threads.clear()
    for t in threads:
        t.join(5)
    _stop.clear()


def run_pending() -> int:
    n = 0
    while True:
        try:
            job = _Q.get_nowait()
        except queue.Empty:
            return n
        try:
            _one(job)
            n += 1
        finally:
            _Q.task_done()


def clear() -> None:
    with _lock:
        while True:
            try:
                _Q.get_nowait()
                _Q.task_done()
            except queue.Empty:
                break
        _queued.clear()


def pending() -> list:
    """The queued squares' keys, in order (for tests and /admin)."""
    with _lock:
        return [f"{j[0].key}|{j[1].key}" for j in list(_Q.queue)]
