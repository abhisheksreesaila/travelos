"""The community database (F-041): every published trip, in one shared SQLite file everyone can browse.

This is a plain shared database, not a tenant. It lives in the data folder (`GITAWAY_DATA_DIR`, see gitaway.auth) as
`community.db`, next to the host and family databases. One table, `published`, holds both kinds of trip:

    kind "shared"   a family's own trip, published from the calendar (gitaway.share)
    kind "creator"  a trip a creator imported from a link and confirmed (gitaway.creators)
    kind "scrapbook"  a real family trip published by a person under their own name, with photos, day notes and tips (gitaway.publish, F-181):
                      the only kind that exists on the live site (showcase off); its photo copies are files under `<data folder>/public/<slug>/`

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
from types import SimpleNamespace

from fh_saas.utils_sql import delete_record, upsert
from sqlalchemy import create_engine, text

from gitaway import auth, stoplinks
from gitaway.itineraries import Day, Itinerary, Polaroid, Source, Stop, Tag

KINDS = ("shared", "creator", "scrapbook")
_SCHEMA = """CREATE TABLE IF NOT EXISTS published (
    slug TEXT PRIMARY KEY, kind TEXT NOT NULL, owner_user TEXT NOT NULL, owner_family TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]', theme TEXT NOT NULL DEFAULT 'sunset',
    snapshot TEXT NOT NULL, meta TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
_CREATORS = """CREATE TABLE IF NOT EXISTS creators (
    handle TEXT PRIMARY KEY, owner_user TEXT NOT NULL UNIQUE, name TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
# F-184/F-185: a creator's own Travelpayouts marker (keyed by the person, so it can be saved before a first publish), a taken-down trip, a report, and one row
# per /go click that came from a creator's trip. Plain CREATE IF NOT EXISTS: a live database gains them on first use, no migration.
_MORE = ("""CREATE TABLE IF NOT EXISTS creator_markers (owner_user TEXT PRIMARY KEY, marker TEXT NOT NULL, updated_at TEXT NOT NULL)""",
         """CREATE TABLE IF NOT EXISTS takedowns (slug TEXT PRIMARY KEY, taken_at TEXT NOT NULL)""",
         """CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, target TEXT NOT NULL, reason TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
    reporter TEXT NOT NULL DEFAULT '', ip_hash TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, seen INTEGER NOT NULL DEFAULT 0)""",
         """CREATE TABLE IF NOT EXISTS fork_counts (slug TEXT PRIMARY KEY, n INTEGER NOT NULL)""",
         """CREATE TABLE IF NOT EXISTS via_clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, handle TEXT NOT NULL, partner TEXT NOT NULL, lane TEXT NOT NULL, own_marker INTEGER NOT NULL, clicked_at TEXT NOT NULL, who TEXT NOT NULL DEFAULT '')""",
         # F-192: a count per trip per day, and who-was-here-today (hashes of the current day only: gitaway/stats.py)
         """CREATE TABLE IF NOT EXISTS trip_days (slug TEXT NOT NULL, day TEXT NOT NULL, views INTEGER NOT NULL DEFAULT 0, forks INTEGER NOT NULL DEFAULT 0, plans INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (slug, day))""",
         """CREATE TABLE IF NOT EXISTS view_seen (day TEXT NOT NULL, h TEXT NOT NULL, slug TEXT NOT NULL, kind TEXT NOT NULL, PRIMARY KEY (day, h, slug, kind))""",
         # F-194: a creator's trip whose ownership the captain has not checked: "pending" (a claim by someone not at the post's site: unlisted), "unverified" (an open import: listed, the byline waits)
         # or "approved". No row: nothing to check. Holds the slug and the post's site only; who published it is read from the trip.
         """CREATE TABLE IF NOT EXISTS trip_review (slug TEXT PRIMARY KEY, state TEXT NOT NULL, host TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)""",
         # F-195: Klook links the partner-links API could not make, per day and reason (gitaway/partners/failures.py): no person in it
         """CREATE TABLE IF NOT EXISTS klook_failures (day TEXT NOT NULL, reason TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, last_at TEXT NOT NULL, PRIMARY KEY (day, reason))""")
# Words a handle cannot be: each is (or may become) a fixed page under /creators/, which would shadow the profile (tests/test_creator_profiles.py walks the app's routes against this set).
RESERVED_HANDLES = frozenset({"draft", "finish", "done", "new", "import", "settings", "edit", "preview", "photo", "admin", "report", "go", "drafts", "stats"})
UP = " AND slug NOT IN (SELECT slug FROM takedowns)"   # the live trips: everything not taken down (F-185)
LISTED = " AND slug NOT IN (SELECT slug FROM trip_review WHERE state = 'pending')"   # the trips in the lists (hub, roster, profiles): not the ones waiting for the captain's yes (F-194)
_ready: set = set()


class HubError(ValueError):
    """A publish the app refuses; the message is fit to show the traveler."""


def _url() -> str:
    return f"sqlite:///{auth.data_dir() / 'community.db'}"


_engines: dict = {}


@contextmanager
def connect():
    """A connection to the community database (made on first use), closed when the block ends. One engine is reused for the process."""
    url = _url()
    if url not in _engines:
        _engines[url] = create_engine(url)
    conn = _engines[url].connect()
    try:
        if url not in _ready:
            conn.execute(text(_SCHEMA))
            conn.execute(text(_CREATORS))
            for stmt in _MORE:
                conn.execute(text(stmt))
            if "who" not in [r[1] for r in conn.execute(text("PRAGMA table_info(via_clicks)"))]:      # F-182: a database made before the per-person count gains the column
                conn.execute(text("ALTER TABLE via_clicks ADD COLUMN who TEXT NOT NULL DEFAULT ''"))
            if "seen" not in [r[1] for r in conn.execute(text("PRAGMA table_info(reports)"))]:      # F-196: a database made before the admin's "new" badge gains the column
                conn.execute(text("ALTER TABLE reports ADD COLUMN seen INTEGER NOT NULL DEFAULT 0"))
            conn.commit()
            _ready.add(url)
        yield SimpleNamespace(conn=conn)  # what fh-saas's utils_sql helpers read
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


# ---- snapshots -----------------------------------------------------------------------------------------------------

def dump(trip: Itinerary) -> str:
    return json.dumps(asdict(trip))


def load(raw: str) -> Itinerary:
    d = json.loads(raw)
    own = stoplinks.own_domain("blog", (d.get("source") or {}).get("url", ""))      # defence in depth: whatever a snapshot holds, only allowed links are ever drawn
    d["days"] = [Day(**{**x, "stops": [Stop(**{**s, "link": stoplinks.clean(s.get("link", ""), own)}) for s in x["stops"]], "photos": [Polaroid(**p) for p in x.get("photos", [])]}) for x in d["days"]]
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

def get(slug, hidden=False) -> dict | None:
    """A published trip, or None. A trip the captain took down (F-185) is not there for anyone unless `hidden=True` (the admin page)."""
    with connect() as db:
        r = db.conn.execute(text("SELECT * FROM published WHERE slug = :s" + ("" if hidden else UP)), {"s": slug}).fetchone()
    return _row(r) if r else None


def rows(kind="", owner="", hidden=False, pending=False) -> list:
    """Published trips, oldest first; `kind` and `owner` (a user id) narrow them. The lists leave out the trips the captain took down and the ones waiting for his yes (F-194, they
    are reached by their link only); `pending=True` keeps the waiting ones, `hidden=True` everything (the admin page)."""
    sql, args = "SELECT * FROM published WHERE 1=1" + ("" if hidden else UP) + ("" if hidden or pending else LISTED), {}
    if kind:
        sql, args["k"] = sql + " AND kind = :k", kind
    if owner:
        sql, args["o"] = sql + " AND owner_user = :o", str(owner)
    with connect() as db:
        return [_row(r) for r in db.conn.execute(text(sql + " ORDER BY created_at, rowid"), args).fetchall()]


def existing(slugs) -> int:
    """How many of `slugs` are published trips: one query, however many there are."""
    slugs = list(dict.fromkeys(slugs))
    if not slugs:
        return 0
    marks = ", ".join(f":s{i}" for i in range(len(slugs)))
    with connect() as db:
        return db.conn.execute(text(f"SELECT COUNT(*) FROM published WHERE slug IN ({marks})" + UP), {f"s{i}": s for i, s in enumerate(slugs)}).scalar()


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
        if db.conn.execute(text("SELECT 1 FROM takedowns WHERE slug = :s"), {"s": trip.slug}).fetchone():
            raise HubError("GitAway took this page down, so it cannot be published again. Write to the address on the Privacy page if you think that was a mistake.")
        old = db.conn.execute(text("SELECT owner_user, created_at FROM published WHERE slug = :s"), {"s": trip.slug}).fetchone()
        if old and old[0] != str(uid):
            raise HubError("That trip belongs to someone else.")
        upsert(db, "published", {
            "slug": trip.slug, "kind": kind, "owner_user": str(uid), "owner_family": str(session.get("tenant_id") or ""),
            "title": trip.title, "tags": json.dumps(list(tags)), "theme": theme, "snapshot": dump(trip),
            "meta": json.dumps(meta or {}), "created_at": old[1] if old else now, "updated_at": now}, ["slug"])
    return get(trip.slug)


def unpublish(session, slug) -> bool:
    """Delete the signed-in person's published trip (its snapshot), even one the captain took down: the takedown row stays, so the address can never come back (F-182).
    False when there was none of theirs."""
    row = get(slug, hidden=True)
    if not row or row["owner_user"] != str((session or {}).get("user_id") or "\0"):
        return False
    with connect() as db:
        delete_record(db, "published", slug, "slug")
        db.conn.execute(text("DELETE FROM trip_review WHERE slug = :s"), {"s": slug})      # published again, it is looked at again
        db.conn.commit()
    return True


# ---- creators (F-181): a person's public name and stable handle -------------------------------------------------------

def creator_of(owner_user) -> dict | None:
    """The creator record of a person (their user id), or None while they have never published."""
    with connect() as db:
        r = db.conn.execute(text("SELECT handle, owner_user, name FROM creators WHERE owner_user = :o"), {"o": str(owner_user)}).fetchone()
    return dict(r._mapping) if r else None


def creator(handle) -> dict | None:
    """The creator behind a profile handle, or None."""
    with connect() as db:
        r = db.conn.execute(text("SELECT handle, owner_user, name FROM creators WHERE handle = :h"), {"h": handle}).fetchone()
    return dict(r._mapping) if r else None


def slugify(text_, limit=30) -> str:
    """Lowercase letters, digits and single dashes only ("Ari & Sam's Disney!" -> "ari-sam-s-disney"); "" when nothing is left."""
    import re
    return re.sub(r"[^a-z0-9]+", "-", str(text_).casefold()).strip("-")[:limit].strip("-")


def claim_creator(owner_user, name) -> dict:
    """The person's creator record, made the first time they publish: the handle comes from the name, is unique (not a sample creator's either)
    and never changes after that. A later call only updates the name shown. Raises HubError when the name is empty."""
    from gitaway import creator_profiles
    name = " ".join(str(name or "").split())[:40]
    if not name:
        raise HubError("Add the name to show on your trip.")
    now = _now()
    with connect() as db:
        mine = db.conn.execute(text("SELECT handle FROM creators WHERE owner_user = :o"), {"o": str(owner_user)}).fetchone()
        if mine:
            db.conn.execute(text("UPDATE creators SET name = :n, updated_at = :t WHERE owner_user = :o"), {"n": name, "t": now, "o": str(owner_user)})
            db.conn.commit()
            return {"handle": mine[0], "owner_user": str(owner_user), "name": name}
        base = slugify(name, 24) or "traveler"
        taken = {r[0] for r in db.conn.execute(text("SELECT handle FROM creators")).fetchall()} | {c.handle for c in creator_profiles.CREATORS} | RESERVED_HANDLES
        handle, n = base, 1
        while handle in taken:
            n += 1
            handle = f"{base}-{n}"
        db.conn.execute(text("INSERT INTO creators (handle, owner_user, name, created_at, updated_at) VALUES (:h, :o, :n, :t, :t)"),
                        {"h": handle, "o": str(owner_user), "n": name, "t": now})
        db.conn.commit()
    return {"handle": handle, "owner_user": str(owner_user), "name": name}


def creators_all() -> list:
    with connect() as db:
        return [dict(r._mapping) for r in db.conn.execute(text("SELECT handle, owner_user, name FROM creators ORDER BY created_at, rowid")).fetchall()]


def real_creators() -> list:
    """Creators with at least one live published trip, oldest first, each with its `trips` (rows of kind scrapbook)."""
    out = []
    for c in creators_all():
        trips = rows(kind="scrapbook", owner=c["owner_user"])
        if trips:
            out.append({**c, "trips": trips})
    return out


def has_real() -> bool:
    """Is any real family trip published and listed? The live site's community and creator pages exist only from then on."""
    with connect() as db:
        return db.conn.execute(text("SELECT 1 FROM published WHERE kind = 'scrapbook'" + UP + LISTED + " LIMIT 1")).fetchone() is not None


def is_real(slug) -> bool:
    """Is `slug` a live published real trip? (The sample slugs and the old demo kinds are not.)"""
    row = get(slug)
    return bool(row) and row["kind"] == "scrapbook"


def bump_fork(slug) -> None:
    """One more family forked this live real trip (kept only as a count, per slug: no family is named). Anything else is ignored."""
    if not is_real(slug):
        return
    from gitaway import stats   # here, not at the top: stats reads this module
    with connect() as db:
        db.conn.execute(text("INSERT INTO fork_counts (slug, n) VALUES (:s, 1) ON CONFLICT(slug) DO UPDATE SET n = n + 1"), {"s": slug})
        db.conn.execute(text("INSERT INTO trip_days (slug, day, forks) VALUES (:s, :d, 1) ON CONFLICT(slug, day) DO UPDATE SET forks = forks + 1"), {"s": slug, "d": stats._today().isoformat()})   # F-192
        db.conn.commit()


def fork_count(slug) -> int:
    with connect() as db:
        r = db.conn.execute(text("SELECT n FROM fork_counts WHERE slug = :s"), {"s": slug}).fetchone()
    return r[0] if r else 0


def most_forked() -> dict | None:
    """The live real trip forked most often (the newest when none has been forked), or None while nothing real is published. One query."""
    with connect() as db:
        r = db.conn.execute(text("SELECT p.* FROM published p LEFT JOIN fork_counts f ON f.slug = p.slug WHERE p.kind = 'scrapbook'"
                                 + (UP + LISTED).replace("slug NOT IN", "p.slug NOT IN") + " ORDER BY COALESCE(f.n, 0) DESC, p.created_at DESC LIMIT 1")).fetchone()
    return _row(r) if r else None


def take_down(slug) -> bool:
    """Hide a published trip and its public photos (F-185). The row stays, and its owner cannot publish it again. False when there is no such trip."""
    if get(slug, hidden=True) is None:
        return False
    with connect() as db:
        db.conn.execute(text("INSERT OR IGNORE INTO takedowns (slug, taken_at) VALUES (:s, :t)"), {"s": slug, "t": _now()})
        db.conn.commit()
    return True


def restore(slug) -> bool:
    """Bring a taken-down trip back. False when it was not down."""
    with connect() as db:
        done = db.conn.execute(text("DELETE FROM takedowns WHERE slug = :s"), {"s": slug}).rowcount
        db.conn.commit()
    return bool(done)


# ---- the captain's check of who owns a trip (F-194) -----------------------------------------------------------------------------------

def review_state(slug) -> str:
    """"pending", "unverified", "approved", or "" when the trip has nothing to be checked."""
    with connect() as db:
        r = db.conn.execute(text("SELECT state FROM trip_review WHERE slug = :s"), {"s": slug}).fetchone()
    return r[0] if r else ""


def set_review(slug, state, host="") -> None:
    """Record that `slug` waits for the captain ("pending" or "unverified"), is "approved", or ("" ) has nothing to check."""
    with connect() as db:
        if state:
            db.conn.execute(text("INSERT INTO trip_review (slug, state, host, updated_at) VALUES (:s, :t, :h, :u) ON CONFLICT(slug) DO UPDATE SET state = :t, host = :h, updated_at = :u"),
                            {"s": slug, "t": state, "h": host, "u": _now()})
        else:
            db.conn.execute(text("DELETE FROM trip_review WHERE slug = :s"), {"s": slug})
        db.conn.commit()


def waiting() -> list:
    """The live trips waiting for the captain, oldest first: [{"slug", "state" ("pending" or "unverified"), "host", "row" (the published row)}]."""
    with connect() as db:
        found = db.conn.execute(text("SELECT r.slug, r.state, r.host FROM trip_review r JOIN published p ON p.slug = r.slug WHERE r.state IN ('pending', 'unverified')"
                                     " AND r.slug NOT IN (SELECT slug FROM takedowns) ORDER BY p.created_at, p.rowid")).fetchall()
    return [{"slug": s, "state": st, "host": h, "row": get(s)} for s, st, h in found]


def is_down(slug) -> bool:
    with connect() as db:
        return db.conn.execute(text("SELECT 1 FROM takedowns WHERE slug = :s"), {"s": slug}).fetchone() is not None


def clear() -> None:
    """Remove every published trip and creator. For tests."""
    with connect() as db:
        db.conn.execute(text("DELETE FROM published"))
        db.conn.execute(text("DELETE FROM creators"))
        for table in ("creator_markers", "takedowns", "reports", "via_clicks", "fork_counts", "trip_days", "view_seen", "trip_review", "klook_failures"):
            db.conn.execute(text(f"DELETE FROM {table}"))
        db.conn.commit()
