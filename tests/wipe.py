"""Empty every family database and the community database: one data folder is shared by a whole test run, so rows must not leak between tests.

Goes through every family the host database knows (not only the ones this process opened), makes sure each has its tables, then
clears them: trips, bookings, calendar, friends, rides, forks and saves (everything in familydb.FAMILY_TABLES). People and
memberships stay, they are the host database's.
"""

from fh_saas.db_host import HostDatabase
from fh_saas.db_tenant import get_or_create_tenant_db
from sqlalchemy import text

from gitaway import community, familydb, hostdb


def tenant_ids():
    with hostdb.locked():
        conn = HostDatabase.from_env().db.conn
        conn.rollback()
        try:
            return [r[0] for r in conn.execute(text("SELECT id FROM core_tenants"))]
        except Exception:  # no host database yet: nothing has been created
            conn.rollback()
            return []


def wipe_invites_and_extra_members():
    """Invites, the "last family" choices, and every membership that is not a family's owner (F-043: people joined by an invite). Each test
    uses its own addresses for the people it invites, but the owner "ari" is shared, so who is in his family must not leak between tests."""
    with hostdb.locked():
        conn = HostDatabase.from_env().db.conn
        conn.rollback()
        for sql in ("DELETE FROM ga_invites", "DELETE FROM ga_last_family", "DELETE FROM core_memberships WHERE role != 'owner'",
                    "UPDATE core_memberships SET is_active = 1 WHERE role = 'owner'"):
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:  # the invite tables are made the first time they are used
                conn.rollback()


def wipe_everything():
    community.clear()
    wipe_invites_and_extra_members()
    for tenant_id in tenant_ids():
        db = get_or_create_tenant_db(tenant_id)
        try:
            familydb.ensure_schema(db, tenant_id)
            for _model, table, _pk in familydb.FAMILY_TABLES:
                db.conn.execute(text(f"DELETE FROM {table}"))
            db.conn.commit()
        finally:
            db.conn.close()
