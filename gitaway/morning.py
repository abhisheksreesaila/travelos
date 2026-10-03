"""The morning plan push (F-066): each trip morning, at the time a person picked, their phone gets "Today in <place>" with the first plans.

Pieces, all in this module so the screen (gitaway/pages/morning.py) and the app start-up only call it:

* `message(...)`          the text, a pure function: trip days only, the first plans with times, nothing else (no confirmation numbers, no prices).
* subscriptions          `push_subscriptions` in the family database (migrations/family/002): one row per device, the chosen time (`at_min`,
                         minutes after midnight in the trip's time zone), on/off, and the date it was last sent. `subscribe`, `set_time`,
                         `unsubscribe`, `status` are the only code that touches it for a signed-in person.
* the sender             `run_once(now, send)` visits every family and sends what is due; `start()` runs it every minute on a daemon thread
                         (one per process; Railway runs one). `now` and `send` are arguments, so tests drive a clock and a fake push service.
* the keys               GITAWAY_VAPID_PUBLIC / _PRIVATE / _SUBJECT, from the environment only (`pixi run vapid-keys`, docs/setup.md). Without them the
                         card is not shown and `start()` does nothing.

A push service answering 404 or 410 means the phone no longer wants it: the subscription is deleted without a word. Any other failure is
logged (never with the address, which is a capability to push to that phone) and retried on the next minute until the hour after the chosen time
has passed; the next trip morning starts fresh.
"""

import hashlib
import json
import logging
import os
import re
import threading
from zoneinfo import ZoneInfo

from fh_saas.db_tenant import get_or_create_tenant_db

from gitaway import catalog, familydb, members, session as ses, tripcal as cal, tripday as td

log = logging.getLogger("gitaway.morning")

DEFAULT_MIN = 7 * 60 + 30   # 7:30 AM
WINDOW = 60                 # minutes after the chosen time in which a missed push (a restart, a slow minute) is still sent
SHOWN = 3                   # plans named in the text
MAX_TITLE = 40
URL = "/trip"
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_PRICE = re.compile(r"\s*\$\s?\d[\d,]*(?:\.\d+)?\S*")


# ---- the keys -------------------------------------------------------------------------------------------------------------

def vapid() -> dict:
    return {"public": os.environ.get("GITAWAY_VAPID_PUBLIC", ""), "private": os.environ.get("GITAWAY_VAPID_PRIVATE", ""), "subject": os.environ.get("GITAWAY_VAPID_SUBJECT", "")}


def configured() -> bool:
    return all(vapid().values())


# ---- the text (pure) ------------------------------------------------------------------------------------------------------

def parse_time(value) -> int | None:
    """"07:30" -> 450, else None."""
    m = _TIME.match(value or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def hhmm(minutes) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _clean(title) -> str:
    t = " ".join(_PRICE.sub("", title or "").split())
    if len(t) > MAX_TITLE:
        t = t[:MAX_TITLE].rsplit(" ", 1)[0].rstrip(" ,.;:·-") + "…"
    return t


def message(destination, phase, plans):
    """The push for a trip morning, or None outside the trip. `plans` is [(minute of the day, title)] in time order. Titles and times only."""
    if phase != "during":
        return None
    lines = [f"{cal.fmt_time(start)} {_clean(title)}" for start, title in plans[:SHOWN]]
    if len(plans) > SHOWN:
        lines.append(f"+{len(plans) - SHOWN} more")
    return {"title": f"Today in {destination}", "body": " · ".join(lines) or "Nothing planned yet. Tap to add something fun.", "url": URL}


def todays_message(session, now):
    """The push this person gets on the morning of the instant `now` (a UTC datetime): their open trip, in its time zone. None on a day outside it."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return None
        b = fam.booking()
        if not b:
            return None
        zone = familydb.trip_zone(fam.db, fam.trip_id)
    t = cal.trip("", b)
    ph, n = td.phase(t, now.astimezone(ZoneInfo(zone)).date())
    if ph != "during":
        return None
    items = td.timeline(n, cal.booked_blocks(b, t), cal.activities(session), [], t.destination_name, zone=zone)
    return message(t.destination_name, ph, [(x.start, x.title) for x in items if x.kind != "offer"])  # a ride offer is an invitation, not a plan


# ---- a person's subscriptions ---------------------------------------------------------------------------------------------

def _passed(zone, at_min, now) -> str:
    """Today's date in the trip zone when the chosen time has already gone by today (so it waits for tomorrow), else ""."""
    local = now.astimezone(ZoneInfo(zone))
    return local.date().isoformat() if local.hour * 60 + local.minute >= at_min else ""


def subscribe(session, endpoint, p256dh, authkey, at_min=DEFAULT_MIN, now=None):
    """Turn the morning plan on for this device (or change its keys and time). Returns {"on", "time"}, or None when nobody is signed in."""
    now = now or catalog.now_utc()
    with ses.family(session) as fam:
        if not fam:
            return None
        zone = familydb.trip_zone(fam.db, fam.trip_id)
        with familydb.transaction(fam.db):
            familydb.run(fam.db, """INSERT INTO push_subscriptions (endpoint, user_id, p256dh, auth, at_min, enabled, last_sent, created_at)
                                    VALUES (:e, :u, :p, :a, :m, 1, :s, :c)
                                    ON CONFLICT(endpoint) DO UPDATE SET user_id = :u, p256dh = :p, auth = :a, at_min = :m, enabled = 1, last_sent = :s""",
                         e=endpoint, u=fam.traveler.id, p=p256dh, a=authkey, m=at_min, s=_passed(zone, at_min, now), c=familydb.now())
        here, uid = session.get("tenant_id"), fam.traveler.id
    for other in members.families_of(uid):  # one phone is told once a day, even if its owner is in two families: the latest family to turn it on keeps it
        if other["tenant_id"] != here:
            _write(other["tenant_id"], "DELETE FROM push_subscriptions WHERE endpoint = :e", e=endpoint)
    return {"on": True, "time": hhmm(at_min)}


def set_time(session, endpoint, at_min, now=None):
    """Change this device's time. {"on", "time"}, or None when it is not subscribed. A time already gone by today waits for tomorrow."""
    now = now or catalog.now_utc()
    with ses.family(session) as fam:
        if not fam:
            return None
        zone = familydb.trip_zone(fam.db, fam.trip_id)
        with familydb.transaction(fam.db):
            changed = familydb.run(fam.db, "UPDATE push_subscriptions SET at_min = :m, last_sent = CASE WHEN :s != '' THEN :s ELSE last_sent END WHERE endpoint = :e AND user_id = :u",
                                   m=at_min, s=_passed(zone, at_min, now), e=endpoint, u=fam.traveler.id)
    return {"on": True, "time": hhmm(at_min)} if changed else None


def unsubscribe(session, endpoint):
    """Turn it off for this device: the row is deleted. Always {"on": False, ...} for a signed-in person, None for nobody."""
    with ses.family(session) as fam:
        if not fam:
            return None
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "DELETE FROM push_subscriptions WHERE endpoint = :e AND user_id = :u", e=endpoint, u=fam.traveler.id)
    return {"on": False, "time": hhmm(DEFAULT_MIN)}


def status(session, endpoint):
    """{"on", "time"} for this device (off at the default time when it never subscribed), or None when nobody is signed in."""
    with ses.family(session) as fam:
        if not fam:
            return None
        found = familydb.row(fam.db, "SELECT at_min, enabled FROM push_subscriptions WHERE endpoint = :e AND user_id = :u", e=endpoint, u=fam.traveler.id)
    return {"on": bool(found and found["enabled"]), "time": hhmm(found["at_min"] if found else DEFAULT_MIN)}


# ---- the sender -----------------------------------------------------------------------------------------------------------

def _tenant(tenant_id):
    db = get_or_create_tenant_db(tenant_id)
    try:
        familydb.ensure_schema(db, tenant_id)
    except Exception:
        db.conn.close()
        raise
    return db


def _subscriptions(tenant_id) -> list:
    db = _tenant(tenant_id)
    try:
        return familydb.rows(db, "SELECT * FROM push_subscriptions WHERE enabled = 1")
    finally:
        db.conn.close()


def _write(tenant_id, sql, **params):
    db = _tenant(tenant_id)
    try:
        with familydb.transaction(db):
            familydb.run(db, sql, **params)
    finally:
        db.conn.close()


def count_all() -> int:
    """How many devices are subscribed across every family (tests, and a glance at how many phones will be told)."""
    return sum(len(_subscriptions(t)) for t in members.tenant_ids())


def _tag(endpoint) -> str:
    return hashlib.sha256(endpoint.encode()).hexdigest()[:8]  # enough to tell devices apart in a log without revealing the address


def push_send(sub, payload) -> int:
    """Send one push to a phone through its push service (pywebpush, signed with the VAPID keys). The HTTP status, or 0 when it never got an answer."""
    from pywebpush import WebPushException, webpush
    keys = vapid()
    try:
        webpush({"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}}, data=json.dumps(payload), vapid_private_key=keys["private"],
                vapid_claims={"sub": keys["subject"]}, ttl=3 * 3600, timeout=15)
        return 201
    except WebPushException as e:
        return e.response.status_code if getattr(e, "response", None) is not None else 0


def due(now, zone, at_min, last_sent):
    """The date (ISO, in the trip zone) this push is for when it is due at the instant `now`, else None: the chosen time has been reached, within
    WINDOW minutes, and it was not already sent that date. Pure, so daylight-saving days and late-evening times are checked directly."""
    local = now.astimezone(ZoneInfo(zone))
    today = local.date().isoformat()
    if last_sent == today or not 0 <= local.hour * 60 + local.minute - at_min < WINDOW:
        return None
    return today


def _deliver(tenant_id, sub, now, send):
    if members.role_in(sub["user_id"], tenant_id) is None:  # no longer in this family: nobody to tell
        _write(tenant_id, "DELETE FROM push_subscriptions WHERE endpoint = :e", e=sub["endpoint"])
        return None
    session = {"user_id": sub["user_id"], "tenant_id": tenant_id, "email": ""}
    today = due(now, ses.trip_zone(session), sub["at_min"], sub["last_sent"])
    if today is None:
        return None
    payload = todays_message(session, now)
    if payload is None:
        return None
    # At most once: the day is recorded before sending, and if that write fails nothing is sent (a failed write after sending would repeat the push every minute).
    _write(tenant_id, "UPDATE push_subscriptions SET last_sent = :d WHERE endpoint = :e", d=today, e=sub["endpoint"])
    try:
        code = send(sub, payload)
    except Exception as e:  # a push service that cannot be reached is not the family's problem
        log.warning("morning plan push %s failed: %s", _tag(sub["endpoint"]), type(e).__name__)
        code = 0
    if 200 <= code < 300:
        return code
    if 400 <= code < 500 and code != 429:  # the phone or the push service says this address will never work (gone, rejected keys, bad signature): drop it quietly
        _write(tenant_id, "DELETE FROM push_subscriptions WHERE endpoint = :e", e=sub["endpoint"])
        return code
    log.warning("morning plan push %s failed with status %s", _tag(sub["endpoint"]), code)  # try again next minute, within the hour
    try:
        _write(tenant_id, "UPDATE push_subscriptions SET last_sent = '' WHERE endpoint = :e AND last_sent = :d", d=today, e=sub["endpoint"])
    except Exception:
        pass  # no retry then, which is the safe side
    return code


def run_once(now, send=None) -> list:
    """Send every morning plan that is due at the instant `now` (a UTC datetime). The status of each push tried."""
    send = send or push_send
    tried = []
    for tenant_id in members.tenant_ids():
        try:
            subs = _subscriptions(tenant_id)
        except Exception as e:
            log.warning("morning plan: could not read a family's subscriptions: %s", type(e).__name__)
            continue
        for sub in subs:
            try:
                code = _deliver(tenant_id, sub, now, send)
            except Exception as e:
                log.warning("morning plan: %s", type(e).__name__)
                continue
            if code is not None:
                tried.append(code)
    return tried


_thread = None
_lock = threading.Lock()


def _loop(stop, interval, send, clock):
    while not stop.wait(interval):
        try:
            run_once(clock(), send)
        except Exception as e:  # the loop outlives any one bad minute
            log.warning("morning plan loop: %s", type(e).__name__)
        try:
            from gitaway import familythread  # here: familythread imports this module
            familythread.flush_due(send=send)  # F-070: the family thread's waiting updates, told in one push per person
        except Exception as e:
            log.warning("family thread loop: %s", type(e).__name__)


def start(interval=60, send=None, clock=None):
    """Start the once-a-minute sender on a daemon thread, once per process. None (and nothing started) without the push keys."""
    global _thread
    with _lock:
        if _thread is not None:
            return _thread
        if not configured():
            return None
        _thread = threading.Thread(target=_loop, args=(threading.Event(), interval, send, clock or catalog.now_utc), daemon=True, name="morning-plan")
        _thread.start()
        return _thread
