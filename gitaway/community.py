"""The community database (F-041): every published trip, in one shared SQLite file everyone can browse.

This is a plain shared database, not a tenant. It lives in the data folder (`GITAWAY_DATA_DIR`, see gitaway.auth) as
`community.db`, next to the host and family databases. One table, `published`, holds both kinds of trip:

    kind "shared"   a family's own trip, published from the calendar (gitaway.share)
    kind "creator"  a trip a creator imported from a link and confirmed (gitaway.creators)

A published trip is a **snapshot**: the scrapbook page (days, plans, tags) frozen at publish time as JSON, plus its owner
(the fh-saas user id and the family id). The page at /trips/<slug> is served from the snapshot, so it works for anyone,
signed in or out, on any device, and does not change when the owner edits their calendar. Publishing the same slug again
replaces the snapshot; the owner can unpublish. The snapshot has no field for notes, friends, prices or booking references:
it is only ever made from an `Itinerary`.

Forks and saves are not here: they are per family (gitaway.familydb_social).
"""

import json
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone

from fastsql import Database
from fh_saas.utils_sql import delete_record, upsert
from sqlalchemy import text

from gitaway import auth
from gitaway.itineraries import Day, Itinerary, Polaroid, Source, Stop, Tag

KINDS = ("shared", "creator")
_SCHEMA = """CREATE TABLE IF NOT EXISTS published (
    slug TEXT PRIMARY KEY, kind TEXT NOT NULL, owner_user TEXT NOT NULL, owner_family TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]', theme TEXT NOT NULL DEFAULT 'sunset',
    snapshot TEXT NOT NULL, meta TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
_ready: set = set()


class HubError(ValueError):
    """A publish the app refuses; the message is fit to show the traveler."""


def _url() -> str:
    return f"sqlite:///{auth.data_dir() / 'community.db'}"


@contextmanager
def connect():
    """A connection to the community database (made on first use), closed when the block ends."""
    url = _url()
    db = Database(url)
    try:
        if url not in _ready:
            db.conn.execute(text(_SCHEMA))
            db.conn.commit()
            _ready.add(url)
        yield db
    finally:
        db.conn.close()
        db.engine.dispose()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


# ---- snapshots -----------------------------------------------------------------------------------------------------

def dump(trip: Itinerary) -> str:
    return json.dumps(asdict(trip))


def load(raw: str) -> Itinerary:
    d = json.loads(raw)
    d["days"] = [Day(**{**x, "stops": [Stop(**s) for s in x["stops"]]}) for x in d["days"]]
    d["tags"] = [Tag(**t) for t in d.get("tags", [])]
    d["polaroids"] = [Polaroid(**p) for p in d.get("polaroids", [])]
    d["source"] = Source(**d["source"]) if d.get("source") else None
    d["stats"] = [tuple(s) for s in d.get("stats", [])]
    d["weather"] = tuple(d.get("weather", ()))
    return Itinerary(**d)


def _row(r) -> dict:
    m = r._mapping
    return {"slug": m["slug"], "kind": m["kind"], "owner_user": m["owner_user"], "owner_family": m["owner_family"], "title": m["title"],
            "tags": json.loads(m["tags"]), "theme": m["theme"], "snapshot": m["snapshot"], "meta": json.loads(m["meta"]),
            "created_at": m["created_at"], "updated_at": m["updated_at"]}


def trip_of(row) -> Itinerary:
    """The scrapbook Itinerary frozen in a row."""
    return load(row["snapshot"])


# ---- reads ---------------------------------------------------------------------------------------------------------

def get(slug) -> dict | None:
    with connect() as db:
        r = db.conn.execute(text("SELECT * FROM published WHERE slug = :s"), {"s": slug}).fetchone()
    return _row(r) if r else None


def rows(kind="", owner="") -> list:
    """Published trips, oldest first; `kind` and `owner` (a user id) narrow them."""
    sql, args = "SELECT * FROM published WHERE 1=1", {}
    if kind:
        sql, args["k"] = sql + " AND kind = :k", kind
    if owner:
        sql, args["o"] = sql + " AND owner_user = :o", str(owner)
    with connect() as db:
        return [_row(r) for r in db.conn.execute(text(sql + " ORDER BY created_at, rowid"), args).fetchall()]


def find(slug, kind="") -> Itinerary | None:
    """The page behind /trips/<slug> for a published trip (of `kind`, when given), else None. No session needed."""
    row = get(slug)
    return trip_of(row) if row and (not kind or row["kind"] == kind) else None


# ---- writes --------------------------------------------------------------------------------------------------------

def publish(session, trip: Itinerary, *, kind, tags=(), theme="sunset", meta=None) -> dict:
    """Publish (or re-publish) `trip` as a snapshot owned by the signed-in person and their family.

    Re-publishing a slug replaces the snapshot and keeps its place in the hub. Raises HubError when signed out, when the
    slug belongs to someone else, or when the title is empty.
    """
    uid = (session or {}).get("user_id")
    if not uid:
        raise HubError("Sign in to share a trip.")
    if kind not in KINDS or not str(trip.title).strip():
        raise HubError("A shared trip needs a title and a place.")
    now = _now()
    with connect() as db:
        old = db.conn.execute(text("SELECT owner_user, created_at FROM published WHERE slug = :s"), {"s": trip.slug}).fetchone()
        if old and old[0] != str(uid):
            raise HubError("That trip belongs to someone else.")
        upsert(db, "published", {
            "slug": trip.slug, "kind": kind, "owner_user": str(uid), "owner_family": str(session.get("tenant_id") or ""),
            "title": trip.title, "tags": json.dumps(list(tags)), "theme": theme, "snapshot": dump(trip),
            "meta": json.dumps(meta or {}), "created_at": old[1] if old else now, "updated_at": now}, ["slug"])
    return get(trip.slug)


def unpublish(session, slug) -> bool:
    """Take the signed-in person's trip out of the community. False when there was none of theirs."""
    row = get(slug)
    if not row or row["owner_user"] != str((session or {}).get("user_id") or "\0"):
        return False
    with connect() as db:
        delete_record(db, "published", slug, "slug")
    return True


def clear() -> None:
    """Remove every published trip. For tests."""
    with connect() as db:
        db.conn.execute(text("DELETE FROM published"))
        db.conn.commit()
