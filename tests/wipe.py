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


def wipe_everything():
    community.clear()
    for tenant_id in tenant_ids():
        db = get_or_create_tenant_db(tenant_id)
        try:
            familydb.ensure_schema(db, tenant_id)
            for _model, table, _pk in familydb.FAMILY_TABLES:
                db.conn.execute(text(f"DELETE FROM {table}"))
            db.conn.commit()
        finally:
            db.conn.close()
