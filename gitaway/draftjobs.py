"""Drafting several of a creator's posts at once, in the background (F-190). A request never waits for a model: it queues rows, a worker thread drafts them.

    remaining(owner)                          how many more posts this person may have drafted today (their own limit, the site-wide ceiling, whichever is lower)
    enqueue(owner, name, [(url, title)])      queue up to MAX_BATCH posts, each counted like a single draft (creatordraft.allow); (queued, "" | "person" | "site")
    listing(owner)                            the one "My drafts" list: queued and drafting posts, failed ones, and every draft the person has (ready or published)
    remove(owner, id)                         take a failed post off the list (a draft is deleted through creatordraft.delete)
    start() / stop()                          the worker threads, started once per process at boot (main.py on_startup); a job that was running when the process died is queued again

A job is one row (`creator_draft_jobs`) per post: queued -> running -> gone (the draft takes its place on the list) or failed (with a sentence fit to show). The list shows queued and running
as "drafting". One post at a time per person: a worker never takes a job of someone who already has one running. The drafting itself is creatordraft's: `make` with the model (after
importsource.gather, which fetches through safefetch), or `sample` in the local showcase, which fetches nothing.
"""

import json
import logging
import re
import secrets
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import text

from gitaway import ai, community, creatordraft as cd, importsource
from gitaway.hub import HubError

log = logging.getLogger("gitaway.draftjobs")

MAX_BATCH = 20
SCAN_LIMIT = 30           # blogs one person may have read in a day: each is up to a dozen fetches, so it is counted like a picture fetch
SCAN_LIMIT_HIT = f"You have looked up {SCAN_LIMIT} blogs today, which is the most for one day. Come back tomorrow, or paste a post's link instead."
WORKERS = 2
UNEXPECTED = "Something went wrong drafting this post. Try pasting its text instead."

_ready: set = set()
_wake = threading.Event()
_stop = threading.Event()
_threads: tuple = ()
_lock = threading.Lock()


@contextmanager
def _db():
    """The community database's connection with the job table made (once per database file)."""
    with community.connect() as db:
        if community._url() not in _ready:
            db.conn.execute(text("""CREATE TABLE IF NOT EXISTS creator_draft_jobs (
                id TEXT PRIMARY KEY, owner_user TEXT NOT NULL, name TEXT NOT NULL DEFAULT '', url TEXT NOT NULL, title TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'queued', error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)"""))
            db.conn.commit()
            _ready.add(community._url())
        yield db


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def clear() -> None:
    """Remove every job. For tests."""
    with _db() as db:
        db.conn.execute(text("DELETE FROM creator_draft_jobs"))
        db.conn.commit()


def may_scan(owner) -> bool:
    """Count one blog read for `owner` today (SCAN_LIMIT): the scan is a fetcher, so it is limited like the picture fetches."""
    with cd._db() as db:
        ok = cd._take(db, f"scan:{owner}", cd._today(), SCAN_LIMIT)
        db.conn.commit()
        return ok


# ---- queueing -------------------------------------------------------------------------------------------------------------------

def remaining(owner) -> int:
    """Posts this person may still have drafted today: the lower of their own daily limit and what is left of the site-wide ceiling."""
    day = cd._today()
    with cd._db() as db:
        used = {k: n for k, n in db.conn.execute(text("SELECT owner_user, n FROM creator_import_hits WHERE day = :d AND owner_user IN (:o, :s)"), {"d": day, "o": str(owner), "s": cd.SITE_KEY})}
    return max(0, min(cd.DAILY_LIMIT - used.get(str(owner), 0), cd.site_limit() - used.get(cd.SITE_KEY, 0)))


def enqueue(owner, name, items):
    """Queue `items` ((url, title) pairs, at most MAX_BATCH), counting each against the daily limit and the site ceiling. (how many were queued, why the rest were not: "", "person" or "site")."""
    taken, why = [], ""
    for url, title in list(items)[:MAX_BATCH]:
        if (why := cd.allow(owner)):       # its own connection and commit, before the rows below are written
            break
        taken.append((url, title))
    with _db() as db:
        for url, title in taken:
            db.conn.execute(text("INSERT INTO creator_draft_jobs (id, owner_user, name, url, title, created_at) VALUES (:i, :o, :n, :u, :t, :c)"),
                            {"i": secrets.token_hex(8), "o": str(owner), "n": str(name)[:100], "u": url, "t": str(title)[:200], "c": _now()})
        db.conn.commit()
    queued = len(taken)
    if queued:
        _wake.set()
    return queued, why


# ---- the worker -----------------------------------------------------------------------------------------------------------------

def claim():
    """The oldest queued job whose owner has none running, now marked running; None when there is nothing to do. One statement, so two workers never take the same job."""
    with _db() as db:
        r = db.conn.execute(text("""UPDATE creator_draft_jobs SET status = 'running' WHERE id = (
                SELECT id FROM creator_draft_jobs WHERE status = 'queued' AND owner_user NOT IN (SELECT owner_user FROM creator_draft_jobs WHERE status = 'running')
                ORDER BY created_at, id LIMIT 1) AND status = 'queued' RETURNING id, owner_user, name, url, title""")).fetchone()
        db.conn.commit()
    return dict(zip(("id", "owner", "name", "url", "title"), r)) if r else None


def reset_running() -> None:
    """Queue again every job a stopped process left running: the post is drafted again, and it was counted the first time."""
    with _db() as db:
        db.conn.execute(text("UPDATE creator_draft_jobs SET status = 'queued' WHERE status = 'running'"))
        db.conn.commit()


def _draft(job):
    owner, url, name = job["owner"], job["url"], job["name"]
    if cd.mode() == "sample":     # the local showcase: a fixture draft, nothing fetched and no model asked
        return cd.sample(owner, importsource.offline(url, ""), name, job["id"])
    return cd.make(owner, owner, importsource.gather(url, ""), name, job["id"])


def _drafted(job) -> bool:
    """Is there already a draft made by this job? A process that died after saving it but before the row was deleted must not draft the post (and ask the model) again."""
    with cd._db() as db:
        return db.conn.execute(text("SELECT 1 FROM creator_drafts WHERE owner_user = :o AND json_extract(data, '$.job') = :j"), {"o": job["owner"], "j": job["id"]}).fetchone() is not None


def _finish(job_id, error) -> None:
    with _db() as db:
        if error:
            db.conn.execute(text("UPDATE creator_draft_jobs SET status = 'failed', error = :e WHERE id = :i"), {"e": error, "i": job_id})
        else:
            db.conn.execute(text("DELETE FROM creator_draft_jobs WHERE id = :i"), {"i": job_id})
        db.conn.commit()


def run_one() -> bool:
    """Draft one queued post: its row is deleted and the draft is on the list, or the row says why not. False when nothing was waiting."""
    job = claim()
    if not job:
        return False
    try:
        if not _drafted(job):
            _draft(job)
        error = ""
    except (importsource.SourceError, ai.AIError, HubError) as e:
        error = str(e)
    except Exception:  # noqa: BLE001 - one bad post must not stop the worker; the log has the type, the person a fixed sentence
        log.exception("draft job failed")
        error = UNEXPECTED
    _finish(job["id"], error)
    return True


def run_pending() -> int:
    """Draft everything waiting, here and now (the worker's loop body; tests call it directly). How many were drafted or failed."""
    n = 0
    while run_one():
        n += 1
    return n


def _loop(poll):
    while not _stop.is_set():
        try:
            if run_one():
                continue
        except Exception:  # noqa: BLE001 - a database hiccup must not end the thread
            log.exception("draft worker")
        _wake.wait(poll)
        _wake.clear()


def start(poll=5.0):
    """Start the worker threads, once per process, after queueing again whatever a stopped process left running. Returns the threads."""
    global _threads
    with _lock:
        if _threads:
            return _threads
        _stop.clear()
        reset_running()
        _threads = tuple(threading.Thread(target=_loop, args=(poll,), daemon=True, name=f"draft-worker-{i}") for i in range(WORKERS))
        for t in _threads:
            t.start()
        return _threads


def stop() -> None:
    """Stop the worker threads (tests; a process just ends)."""
    global _threads
    with _lock:
        _stop.set()
        _wake.set()
        for t in _threads:
            t.join(timeout=5)
        _threads = ()
        _wake.clear()


# ---- the list -------------------------------------------------------------------------------------------------------------------

def listing(owner) -> list:
    """The person's one list of drafts, drafting first (oldest first), then failed, then the drafts themselves, newest change first. Each row: id, kind ("job" or "draft"), status
    ("drafting", "failed", "ready" or "published"), title, url (the post's address, or ""), error, slug (a draft's), updated, now (being drafted this moment)."""
    with _db() as db:
        jobs = db.conn.execute(text("SELECT id, status, title, url, error, created_at FROM creator_draft_jobs WHERE owner_user = :o ORDER BY created_at, id"), {"o": str(owner)}).fetchall()
    with cd._db() as db:
        drafts = db.conn.execute(text("SELECT id, slug, data, published_by, updated_at FROM creator_drafts WHERE owner_user = :o ORDER BY updated_at DESC, id"), {"o": str(owner)}).fetchall()
    out = [{"id": i, "kind": "job", "status": "failed" if s == "failed" else "drafting", "title": t or u, "url": u, "error": e, "slug": "", "updated": c, "now": s == "running"} for i, s, t, u, e, c in jobs]
    out.sort(key=lambda r: r["status"] == "failed")
    for i, slug, data, by, updated in drafts:
        d = json.loads(data)
        out.append({"id": i, "kind": "draft", "status": "published" if by else "ready", "title": d.get("title") or "Untitled draft", "url": (d.get("source") or {}).get("url", ""), "error": "",
                    "slug": slug, "updated": updated, "now": False})
    return out


def remove(owner, jid) -> bool:
    """Take a failed post off the list. A post still being drafted stays (the worker is on it); someone else's id is nothing."""
    if not re.fullmatch(r"[0-9a-f]{16}", str(jid or "")):
        return False
    with _db() as db:
        r = db.conn.execute(text("DELETE FROM creator_draft_jobs WHERE id = :i AND owner_user = :o AND status = 'failed'"), {"i": jid, "o": str(owner)})
        db.conn.commit()
    return r.rowcount == 1
