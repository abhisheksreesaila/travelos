"""Forks and saves, stored per family (F-041).

Each family's tenant database holds the trips it forked and the ones it saved with the heart, as slugs of published trips
(see gitaway.community) or of the sample trips. They belong to the family: everyone planning together sees the same list.

The tables are part of the family database (gitaway.familydb appends SOCIAL_TABLES to its FAMILY_TABLES), so there is one entry
point: `familydb.using` checks the person is a member of the family named in the session and makes sure every family table exists.
"""

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import text


class Fork:
    slug: str
    user_id: str
    created_at: str


class Save:
    slug: str
    user_id: str
    created_at: str


SOCIAL_TABLES = [(Fork, "forks", "slug"), (Save, "saves", "slug")]


@contextmanager
def family_db(session):
    """The signed-in person's family database, closed when the block ends. None without a family (or when not a member of it)."""
    from gitaway import familydb  # here, not at the top: familydb adds SOCIAL_TABLES to its list when it loads
    with familydb.using(session) as db:
        yield db


def slugs(session, table) -> list:
    """The trip slugs in `table` (forks or saves), oldest first. Empty when signed out."""
    with family_db(session) as db:
        if db is None:
            return []
        return [r[0] for r in db.conn.execute(text(f"SELECT slug FROM {table} ORDER BY created_at, rowid")).fetchall()]


def add(session, table, slug) -> bool:
    """Keep `slug` in `table` for the family. False when it is already there or there is no family."""
    with family_db(session) as db:
        if db is None:
            return False
        r = db.conn.execute(text(f"INSERT OR IGNORE INTO {table} (slug, user_id, created_at) VALUES (:s, :u, :t)"),
                            {"s": slug, "u": str(session.get("user_id")), "t": datetime.now(timezone.utc).isoformat(timespec="microseconds")})
        db.conn.commit()
        return r.rowcount > 0


def remove(session, table, slug) -> bool:
    with family_db(session) as db:
        if db is None:
            return False
        r = db.conn.execute(text(f"DELETE FROM {table} WHERE slug = :s"), {"s": slug})
        db.conn.commit()
        return r.rowcount > 0
