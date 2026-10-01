"""Forks and saves, stored per family (F-041).

Each family's tenant database holds the trips it forked and the ones it saved with the heart, as slugs of published trips
(see gitaway.community) or of the sample trips. They belong to the family: everyone planning together sees the same list.

F-040 owns the family database layout. Until its `FAMILY_TABLES` list is merged this module makes its own two tables the
first time a family's database is touched; to hook it up, add `SOCIAL_TABLES` to that list and drop `family_db`'s register call.
"""

from contextlib import contextmanager
from datetime import datetime, timezone

from fh_saas.db_tenant import get_or_create_tenant_db
from fh_saas.utils_db import register_tables
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
_ready: set = set()


@contextmanager
def family_db(session):
    """The signed-in person's family database, with the social tables made, closed when the block ends. None without a family."""
    tenant = (session or {}).get("tenant_id")
    if not tenant:
        yield None
        return
    db = get_or_create_tenant_db(tenant)
    try:
        if tenant not in _ready:
            register_tables(db, SOCIAL_TABLES)
            _ready.add(tenant)
        yield db
    finally:
        db.conn.close()


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


def known_tenants() -> list:
    """The families whose social tables this process has made. For tests."""
    return sorted(_ready)


def clear_all(tenant_ids) -> None:
    """Empty both tables for these families. For tests."""
    for t in tenant_ids:
        with family_db({"tenant_id": t}) as db:
            for table in ("forks", "saves"):
                db.conn.execute(text(f"DELETE FROM {table}"))
            db.conn.commit()
