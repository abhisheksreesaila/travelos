"""The family thread (F-070): one conversation per trip, with messages, photos and a card for every plan change, and the pushes that tell the family.

* Items live in `thread` (gitaway/familydb_thread.py), oldest first. `items(session, since)` reads them; `post_message` and `post_photo` add what a
  person did; `change(...)` adds the automatic card and is called by every plan write (gitaway/tripcal.py, gitaway/importer.py) inside its transaction.
* Who may post. Every member can write a message, viewers too: a grandparent who may only look at the plans can still say "see you at 6". Viewers
  still cannot change a plan, so they never cause a change card. (POST /trip/family/message is on gitaway.access.OPEN_POSTS on purpose.)
* Pushes. A message or a plan change tells everyone in the family who has the Morning plan switched on for a phone (a row in `push_subscriptions`),
  except the person who did it, unless they set Quiet. `notify` sends; a person gets at most one push per WINDOW seconds, and what happens
  in between is counted and told in one push when the window ends (`flush_due`, called every minute by gitaway.morning's loop). The text is
  names and plan titles only, with prices removed: never a confirmation number or an amount.
* The sender runs off the request: `change` queues the push and a daemon thread sends it. `SENDER` replaces the real push service (tests).
"""

import json
import logging
import queue
import threading
import time
import uuid

from gitaway import familydb, members, morning

log = logging.getLogger("gitaway.thread")

WINDOW = 120          # seconds: a person gets at most one push in this time; more updates wait and are told together
MAX_MESSAGE = 500
SHOWN = 200           # the newest items the Family tab shows
URL = "/trip/family"
BODY = 90
SENDER = None         # tests: a function (subscription, payload) -> HTTP status, used instead of the push service
_PRICE = morning._PRICE


class ThreadError(ValueError):
    """A message the thread refuses; the text is fit to show."""


def first_name(traveler) -> str:
    words = (getattr(traveler, "name", "") or "").split()
    return words[0] if words else "Someone"


# ---- reading ---------------------------------------------------------------------------------------------------------------

def _item(r) -> dict:
    try:
        payload = json.loads(r["payload"]) if r["payload"] else {}
    except ValueError:
        payload = {}
    return {"n": r["n"], "id": r["id"], "kind": r["kind"], "author": r["author"], "name": r["author_name"], "text": r["text"],
            "payload": payload if isinstance(payload, dict) else {}, "at": r["created_at"]}


def items(session, since=0, limit=SHOWN) -> list:
    """The thread of the trip this person has open: items after rowid `since` (oldest first), at most the newest `limit`. [] when signed out."""
    from gitaway import session as ses
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return []
        found = familydb.rows(fam.db, "SELECT * FROM (SELECT rowid AS n, * FROM thread WHERE trip_id = :t AND rowid > :s ORDER BY rowid DESC LIMIT :l) ORDER BY n",
                              t=fam.trip_id, s=int(since or 0), l=limit)
    return [_item(r) for r in found]


# ---- writing what people do ------------------------------------------------------------------------------------------------

def _insert(db, trip_id, kind, author, name, text, payload=None):
    familydb.run(db, "INSERT INTO thread (id, trip_id, kind, author, author_name, text, payload, created_at) VALUES (:i, :t, :k, :a, :n, :x, :p, :c)",
                 i=uuid.uuid4().hex, t=trip_id, k=kind, a=author, n=name, x=text, p=json.dumps(payload, separators=(",", ":")) if payload else "", c=familydb.now())


def post_message(session, text):
    """Write a message to the thread of the open trip (any member, viewers too) and tell the family. Raises ThreadError."""
    from gitaway import session as ses
    text = " ".join((text or "").split())
    if not text:
        raise ThreadError("Write something first.")
    if len(text) > MAX_MESSAGE:
        raise ThreadError(f"Keep messages to {MAX_MESSAGE} characters.")
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise ThreadError("Open a trip first.")
        name, trip_id, me = first_name(fam.traveler), fam.trip_id, fam.traveler.id
        with familydb.transaction(fam.db):
            _insert(fam.db, trip_id, "message", me, name, text)
    announce(session, trip_id, name, _safe(text), exclude=me)


def post_photo(session, url, caption=""):
    """A photo card (F-071 uploads and calls this). Only an address on this site or https is kept. Raises ThreadError."""
    from gitaway import session as ses
    if not _image_url(url):
        raise ThreadError("That photo address is not valid.")
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            raise ThreadError("Open a trip first.")
        name, trip_id, me = first_name(fam.traveler), fam.trip_id, fam.traveler.id
        with familydb.transaction(fam.db):
            _insert(fam.db, trip_id, "photo", me, name, " ".join((caption or "").split())[:140], {"url": url})
    announce(session, trip_id, name, "Shared a photo", exclude=me)


def _image_url(url) -> bool:
    return isinstance(url, str) and 0 < len(url) <= 1000 and ((url.startswith("/") and not url.startswith("//")) or url.startswith("https://"))


def change(session, fam, text, *, trip_id=None, action="change"):
    """Write the card for a plan change, inside the caller's open transaction, and queue the family's push (sent off the request). `text` is
    plain: "Abhi moved Griffith Observatory to Tue 10:00 AM". `action` (add, move, remove, change) picks the card's icon."""
    trip_id = trip_id or fam.trip_id
    if not trip_id or not text:
        return
    _insert(fam.db, trip_id, "change", fam.traveler.id, first_name(fam.traveler), text, {"action": action})
    announce(session, trip_id, "Plan changed", _safe(text), exclude=fam.traveler.id)


# ---- quiet -----------------------------------------------------------------------------------------------------------------

def quiet(session) -> bool:
    from gitaway import session as ses
    with ses.family(session) as fam:
        found = familydb.row(fam.db, "SELECT quiet FROM thread_prefs WHERE user_id = :u", u=fam.traveler.id) if fam else None
    return bool(found and found["quiet"])


def set_quiet(session, on) -> bool | None:
    """Turn this person's thread pushes off (Quiet) or back on. The new state, or None when signed out."""
    from gitaway import session as ses
    with ses.family(session) as fam:
        if not fam:
            return None
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "INSERT INTO thread_prefs (user_id, quiet, last_push, pending) VALUES (:u, :q, 0, 0) ON CONFLICT(user_id) DO UPDATE SET quiet = :q, pending = 0",
                         u=fam.traveler.id, q=1 if on else 0)
    return bool(on)


# ---- pushes ----------------------------------------------------------------------------------------------------------------

def _safe(text) -> str:
    """A line fit for a lock screen: prices removed, one line, short."""
    t = " ".join(_PRICE.sub("", text or "").split())
    return t if len(t) <= BODY else t[:BODY].rsplit(" ", 1)[0].rstrip(" ,.;:·-") + "…"


def _sender(send):
    send = send or SENDER
    if send:
        return send
    return morning.push_send if morning.configured() else None


def _by_person(subs) -> dict:
    out = {}
    for s in subs:
        out.setdefault(s["user_id"], []).append(s)
    return out


def _deliver(tenant_id, subs, payload, send) -> int:
    """Send `payload` to each of one person's phones; a phone the push service refuses for good is forgotten. How many were accepted."""
    done = 0
    for sub in subs:
        try:
            code = send(sub, payload)
        except Exception as e:
            log.warning("thread push %s failed: %s", morning._tag(sub["endpoint"]), type(e).__name__)
            continue
        if 200 <= code < 300:
            done += 1
        elif 400 <= code < 500 and code != 429:
            morning._write(tenant_id, "DELETE FROM push_subscriptions WHERE endpoint = :e", e=sub["endpoint"])
        else:
            log.warning("thread push %s failed with status %s", morning._tag(sub["endpoint"]), code)
    return done


_lock = threading.Lock()


def notify(family, trip, title, body, url=URL, exclude_person="", send=None, now=None) -> int:
    """Tell the family (tenant id `family`) about something on `trip`: a push to each phone of everyone with the Morning plan on, except
    `exclude_person` and anyone on Quiet. A person pushed less than WINDOW seconds ago is not pushed again: the update is counted and
    `flush_due` tells them once the window ends. How many people were pushed now. Nothing happens without a sender (no push keys)."""
    send = _sender(send)
    if send is None:
        return 0
    now = int(now if now is not None else time.time())
    payload = {"title": title, "body": _safe(body), "url": url, "tag": "family-thread"}
    pushed = 0
    with _lock:
        db = morning._tenant(family)
        try:
            people = _by_person(familydb.rows(db, "SELECT * FROM push_subscriptions WHERE enabled = 1"))
            prefs = {r["user_id"]: r for r in familydb.rows(db, "SELECT * FROM thread_prefs")}
        finally:
            db.conn.close()
        for user, subs in people.items():
            pref = prefs.get(user) or {"quiet": 0, "last_push": 0, "pending": 0}
            if user == exclude_person or pref["quiet"] or members.role_in(user, family) is None:
                continue
            if now - pref["last_push"] >= WINDOW:
                if _deliver(family, subs, payload, send):
                    pushed += 1
                morning._write(family, "INSERT INTO thread_prefs (user_id, quiet, last_push, pending) VALUES (:u, 0, :n, 0) ON CONFLICT(user_id) DO UPDATE SET last_push = :n, pending = 0", u=user, n=now)
            else:
                morning._write(family, "INSERT INTO thread_prefs (user_id, quiet, last_push, pending) VALUES (:u, 0, 0, 1) ON CONFLICT(user_id) DO UPDATE SET pending = pending + 1", u=user)
    return pushed


def flush_due(now=None, send=None) -> int:
    """Tell everyone whose window has ended about the updates that waited ("3 more updates"), once. How many people were pushed."""
    send = _sender(send)
    if send is None:
        return 0
    now = int(now if now is not None else time.time())
    pushed = 0
    for tenant_id in members.tenant_ids():
        with _lock:
            try:
                db = morning._tenant(tenant_id)
                try:
                    due = familydb.rows(db, "SELECT * FROM thread_prefs WHERE pending > 0 AND :n - last_push >= :w", n=now, w=WINDOW)
                    people = _by_person(familydb.rows(db, "SELECT * FROM push_subscriptions WHERE enabled = 1"))
                finally:
                    db.conn.close()
                for pref in due:
                    subs = people.get(pref["user_id"])
                    if subs and not pref["quiet"] and members.role_in(pref["user_id"], tenant_id) is not None:
                        n = pref["pending"]
                        payload = {"title": "Family thread", "body": f"{n} more update{'s' if n != 1 else ''} on the trip", "url": URL, "tag": "family-thread"}
                        if _deliver(tenant_id, subs, payload, send):
                            pushed += 1
                    morning._write(tenant_id, "UPDATE thread_prefs SET pending = 0, last_push = :n WHERE user_id = :u", n=now, u=pref["user_id"])
            except Exception as e:
                log.warning("thread flush: %s", type(e).__name__)
    return pushed


# ---- sending off the request -----------------------------------------------------------------------------------------------

_queue = queue.Queue()
_worker = None
_start = threading.Lock()


def _work():
    while True:
        job = _queue.get()
        try:
            notify(**job)
        except Exception as e:  # one bad push never stops the next
            log.warning("thread push: %s", type(e).__name__)
        finally:
            _queue.task_done()


def announce(session, trip_id, title, body, exclude=""):
    """Queue the push for something that just happened in this family; a daemon thread sends it. Without push keys (and no test sender) nothing is queued."""
    global _worker
    if _sender(None) is None:
        return
    with _start:
        if _worker is None:
            _worker = threading.Thread(target=_work, daemon=True, name="family-thread-push")
            _worker.start()
    _queue.put({"family": session.get("tenant_id"), "trip": trip_id, "title": title, "body": body, "exclude_person": exclude})


def drain():
    """Wait until every queued push has been handled (tests)."""
    _queue.join()
