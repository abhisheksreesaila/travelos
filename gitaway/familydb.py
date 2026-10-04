"""A family's database: the tables, how to open it, and the small SQL helpers the model modules share (F-040).

A family is an fh-saas tenant (ADR-0004), so its trips, bookings, activities, notes, friends and rides live in that
tenant's own SQLite file. The session cookie holds only the sign-in. Screens never see this module: they call
gitaway.session (trips, bookings, friends) and gitaway.tripcal (the calendar), which keep their old public functions.

Schema. Tables are plain annotated classes registered with fh-saas `register_tables` every time a family database is
opened for the first time in a process (it is idempotent: that is the baseline, "version 0"). Later changes to an
existing table are `utils_migrate` migrations in migrations/family/NNN_description.sql, applied the same moment, per
family, the first time that family is opened after a deploy. See docs/family-db.md.

FAMILY_TABLES is the list of (class, table name, primary key). Another ticket adds its tables with one line:
    familydb.FAMILY_TABLES.append((Fork, "forks", "pk"))
and FAMILY_INDEXES works the same way.

Concurrency. Two family members can edit at once. Every change is one short transaction on its own rows (an UPDATE of the
fields that changed, an INSERT, a delete): nothing reads a whole JSON document, edits it and writes it back. Writes that
read before they write (the calendar's validation, id counters) start with a write statement, which takes SQLite's
write lock, so the reads that follow cannot be stale. WAL mode keeps readers out of the writers' way.
"""

import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fh_saas.utils_auth import require_tenant_access
from fh_saas.utils_db import create_indexes, register_tables
from fh_saas.utils_migrate import apply_migrations, discover_migrations
from fh_saas.utils_sql import with_transaction
from sqlalchemy import text

from gitaway import familydb_import, hostdb
from gitaway.familydb_import import IMPORT_TABLES
from gitaway.familydb_passes import PASS_INDEXES, PASS_TABLES
from gitaway.familydb_photos import PHOTO_INDEXES, PHOTO_TABLES
from gitaway.familydb_social import SOCIAL_TABLES
from gitaway.familydb_thread import THREAD_INDEXES, THREAD_TABLES

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations" / "family"  # absolute: the process runs from the data folder
MAX_TRIPS = 20  # a demo family keeps its trips list short


# ---- the tables ----------------------------------------------------------------------------------------------------

class Member:
    """A person in this family: display info, the trip they have open, and the workspace picks they left (a /plan query)."""
    id: str            # the fh-saas user id
    email: str
    name: str
    trip_id: str = None
    plan: str = None
    created_at: str


class Trip:
    """One trip. `source` is "demo" (booked in the demo flow) or "imported" (F-042). `params` is catalog.trip_query ("" = the sample trip)."""
    id: str
    title: str
    source: str
    params: str
    depart: str        # ISO dates, for ordering and the switcher
    return_on: str
    created_by: str
    created_at: str


class Booking:
    """The picks of a demo booking, as the pay flow records them. Money is integer cents. One booking per trip."""
    id: str            # "GA-XXXXXXXX", stable for one person's picks
    trip_id: str
    flight: str = None
    stay: str = None
    car: str = None
    rooms: str = ""
    add_ons: str = ""
    fare: str = ""
    bags: str = ""
    total_cents: int
    booked_by: str
    booked_at: str


class Activity:
    """Something on the trip calendar. `scope` is "" or "long" (the ?demo=long fixture); `act_id` is the short id forms carry ("a3").

    `gone` is 0 live, 1 the last thing deleted (Undo brings it back); older deletions are removed from the file. Times are minutes after midnight.
    """
    pk: str
    trip_id: str
    scope: str = ""
    act_id: str
    seq: int
    day: int
    start_min: int
    end_min: int
    title: str
    kind: str
    author: str = ""   # the friend who added it ("Mom"); "" is a family member
    added_by: str = ""
    gone: int = 0
    created_at: str


class Note:
    """A note on the trip, or on one activity (`act_id`). `gone` follows its activity (see Activity)."""
    pk: str
    trip_id: str
    scope: str = ""
    note_id: str
    seq: int
    body: str
    act_id: str = None
    author: str = ""
    added_by: str = ""
    gone: int = 0
    created_at: str


class CalState:
    """Per trip and scope: the last id number handed out, and whether the scripted live add has happened."""
    pk: str
    trip_id: str
    scope: str = ""
    q: int = 0
    live: int = 0
    dead: str = ""    # the last few deleted activity ids, comma separated: a stale re-post of one must not bring it back


class Friend:
    """A friend invited to a trip by name (the demo's invite; real members arrive with F-043)."""
    pk: str
    trip_id: str
    name: str
    created_at: str


class Ride:
    """One simulated Uber ride (F-038) of this family. `key` says which picks (flight, stay, trip dates) it belongs to, so any
    booking with the same picks, by any member, shows it. `data` is the compact ride dict gitaway.rides.to_dict makes (JSON).

    gitaway/rides.py is the only code that reads or writes this table (list_rides, get_ride, save_ride, cancel_ride, step_ride).
    """
    id: str            # "r1", "r2": family-wide
    seq: int
    trip_id: str = ""   # the trip booked with these picks ("" while nothing is booked with them yet)
    key: str
    leg: str
    request_id: str
    data: str
    created_by: str = ""
    created_at: str


class GeoCache:
    """What the map services answered for this family (F-068, gitaway/geo.py): where a place is (`kind` "place", `key` the lower-cased text, `found` 0 when
    the service had no such place, `data` its display name) and how long a drive takes (`kind` "drive", `key` "lat,lon;lat,lon", `data` JSON of minutes
    and the route line). Trip places are the family's own data, so the cache is per family. A failed call is never stored."""
    pk: str            # kind + "|" + key
    kind: str
    key: str
    lat: float = None
    lon: float = None
    found: int = 1
    data: str = ""
    created_at: str


FAMILY_TABLES = [
    (Member, "members", "id"),
    (Trip, "trips", "id"),
    (Booking, "bookings", "id"),
    (Activity, "activities", "pk"),
    (Note, "notes", "pk"),
    (CalState, "cal_state", "pk"),
    (Friend, "friends", "pk"),
    (Ride, "rides", "id"),
    (GeoCache, "geo_cache", "pk"),
]

FAMILY_TABLES.extend(SOCIAL_TABLES)  # forks and saves (F-041): one list, one entry point (see familydb_social)
FAMILY_TABLES.extend(IMPORT_TABLES)  # trips imported from elsewhere (F-042, see familydb_import)
FAMILY_TABLES.extend(THREAD_TABLES)  # the family thread and who wants its pushes (F-070, see familydb_thread)
FAMILY_TABLES.extend(PHOTO_TABLES)  # the trip's photos (F-071, see familydb_photos)
FAMILY_TABLES.extend(PASS_TABLES)  # the trip's flights and boarding passes (F-083, see familydb_passes)

FAMILY_INDEXES = [  # (table, columns, unique, name)
    ("bookings", ["trip_id"], True, "ux_bookings_trip"),
    ("activities", ["trip_id", "scope", "act_id"], True, "ux_activities_id"),
    ("notes", ["trip_id", "scope", "note_id"], True, "ux_notes_id"),
    ("friends", ["trip_id"], False, "ix_friends_trip"),
    ("rides", ["key"], False, "ix_rides_key"),
    ("rides", ["trip_id"], False, "ix_rides_trip"),
    *THREAD_INDEXES,
    *PHOTO_INDEXES,
    *PASS_INDEXES,
]


# ---- opening a family database -------------------------------------------------------------------------------------

_READY = set()               # tenant ids whose schema this process has already made sure of
_LOCK = threading.RLock()    # one process makes a family's tables once
_OPENED = set()              # every tenant id opened in this process since the last `take_opened`; NOT cleared by forget_schema_cache (F-045)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(db, tenant_id):
    """Create any missing family tables and indexes, then apply pending migrations. Once per tenant per process."""
    with _LOCK:
        _OPENED.add(tenant_id)
    if tenant_id in _READY:
        return
    with _LOCK:
        if tenant_id in _READY:
            return
        register_tables(db, list(FAMILY_TABLES))
        create_indexes(db, list(FAMILY_INDEXES))
        db.conn.execute(text("PRAGMA journal_mode=WAL"))  # sticks to the file; readers no longer wait for writers
        if discover_migrations(MIGRATIONS_DIR):
            apply_migrations(db, str(MIGRATIONS_DIR))
        db.conn.commit()
        _READY.add(tenant_id)


def forget_schema_cache():
    """Make the next open re-check the schema (tests that point MIGRATIONS_DIR somewhere else)."""
    with _LOCK:
        _READY.clear()


def take_opened() -> set:
    """The tenant ids opened since the last call, and forget them. Tests wipe only these families (tests/wipe.py): a family nobody
    opened has no rows to clear. Unlike the schema cache, this survives `forget_schema_cache`."""
    global _OPENED
    with _LOCK:
        opened, _OPENED = _OPENED, set()
    return opened


def family_db(source):
    """The signed-in person's family database, ready to use. `source` is a Request or a session mapping.

    Checks that the person is an active member of the family named in the session (fh-saas require_tenant_access), and
    makes sure the tables exist. The caller closes the handle (`db.conn.close()`); `using` does that for you.
    Raises ValueError when nobody is signed in and PermissionError when they are not a member.
    """
    session = getattr(source, "session", None) if hasattr(source, "scope") else source  # a Starlette Request is a Mapping too: ask it for its session
    if session is None or not session.get("user_id"):
        raise ValueError("Authentication required")
    with hostdb.locked():  # the membership check uses fh-saas's one shared host connection
        db = require_tenant_access(session)
    try:
        ensure_schema(db, session["tenant_id"])
    except Exception:
        db.conn.close()
        raise
    return db


@contextmanager
def using(source):
    """`with using(session) as db:` the family database, or None when signed out or not a member. Closed afterwards."""
    try:
        db = family_db(source)
    except (ValueError, PermissionError):
        db = None
    try:
        yield db
    finally:
        if db is not None:
            db.conn.close()


_hooks = threading.local()


def after_commit(fn):
    """Run `fn()` once the open transaction on this thread has committed (never if it rolls back); at once when none is open (F-070: pushes)."""
    pending = getattr(_hooks, "pending", None)
    if pending is None:
        fn()
    else:
        pending.append(fn)


@contextmanager
def transaction(db):
    """One transaction: commit at the end, roll back if anything raises (fh-saas with_transaction). Functions given to `after_commit` run after the commit."""
    outer = getattr(_hooks, "pending", None)
    _hooks.pending = mine = [] if outer is None else outer
    try:
        with with_transaction(db):
            yield db
    except BaseException:
        if outer is None:
            mine.clear()
        raise
    finally:
        _hooks.pending = outer
    if outer is None:
        for fn in mine:
            try:
                fn()
            except Exception:  # a push that cannot be queued never undoes the change
                pass


def lock(db):
    """Take SQLite's write lock for this transaction without changing anything: reads after this are current until commit."""
    db.conn.execute(text("UPDATE members SET id = id WHERE 0"))


# ---- small SQL helpers (reads; writes use fh-saas utils_sql: insert_only, upsert, update_record, delete_record) ------

def rows(db, sql, **params) -> list:
    return [dict(r) for r in db.conn.execute(text(sql), params).mappings()]


def row(db, sql, **params):
    found = rows(db, sql, **params)
    return found[0] if found else None


def run(db, sql, **params) -> int:
    """Run one write statement inside the caller's transaction; the number of rows it changed."""
    return db.conn.execute(text(sql), params).rowcount


# ---- members -------------------------------------------------------------------------------------------------------

def ensure_member(db, user_id, email, name) -> dict:
    """The member row for this person, created the first time they use the family database."""
    found = row(db, "SELECT * FROM members WHERE id = :id", id=user_id)
    if found:
        return found
    with transaction(db):
        run(db, "INSERT OR IGNORE INTO members (id, email, name, created_at) VALUES (:id, :email, :name, :at)",
            id=user_id, email=email or "", name=name, at=now())
    return row(db, "SELECT * FROM members WHERE id = :id", id=user_id)


# ---- trips and bookings --------------------------------------------------------------------------------------------

def trips(db) -> list:
    """Every trip of the family, newest first."""
    return rows(db, "SELECT * FROM trips ORDER BY created_at DESC, rowid DESC")


def trip(db, trip_id):
    return row(db, "SELECT * FROM trips WHERE id = :id", id=trip_id) if trip_id else None


def trip_zone(db, trip_id) -> str:
    """The IANA time zone the trip lives in (F-057; the `timezone` column, Los Angeles for demo trips and older rows)."""
    found = row(db, "SELECT timezone FROM trips WHERE id = :id", id=trip_id) if trip_id else None
    return (found or {}).get("timezone") or "America/Los_Angeles"


def current_trip_id(db, member) -> str | None:
    """The trip this person has open: the one they chose, else the family's newest."""
    if member.get("trip_id") and trip(db, member["trip_id"]):
        return member["trip_id"]
    newest = row(db, "SELECT id FROM trips ORDER BY created_at DESC, rowid DESC LIMIT 1")
    return newest["id"] if newest else None


def booking_for_trip(db, trip_id) -> dict | None:
    """The booking of a trip in the shape the model modules read ("add" and the optional keys only when set), or None."""
    imported = row(db, "SELECT * FROM trips WHERE id = :t AND source = 'imported'", t=trip_id) if trip_id else None
    if imported and (found := familydb_import.booking(db, imported)):  # a trip booked elsewhere (F-042): its booking is the stored template
        return found
    b = row(db, "SELECT b.*, t.params AS trip_params FROM bookings b JOIN trips t ON t.id = b.trip_id WHERE b.trip_id = :t", t=trip_id) if trip_id else None
    if not b:
        return None
    out = {"id": b["id"], "flight": b["flight"], "stay": b["stay"], "car": b["car"], "rooms": b["rooms"] or "", "add": b["add_ons"] or "",
           "total_cents": b["total_cents"], "booked_at": b["booked_at"], "booked_by": b["booked_by"] or ""}
    for key, value in (("fare", b["fare"]), ("bags", b["bags"]), ("trip", b["trip_params"])):
        if value:
            out[key] = value
    return out
