"""Empty every family database and the community database: one data folder is shared by a whole test run, so rows must not leak between tests.

Goes through the families a test opened (familydb.take_opened), then clears them: trips, bookings, calendar, friends, rides, forks and saves (everything in familydb.FAMILY_TABLES). People and
memberships stay, they are the host database's.
"""

import shutil

from fh_saas.db_host import HostDatabase
from fh_saas.db_tenant import get_or_create_tenant_db
from sqlalchemy import text

from gitaway import community, familydb, hostdb, passes, photos


def wipe_invites_and_extra_members():
    """Invites, the "last family" choices, and every membership that is not a family's owner (F-043: people joined by an invite). Each test
    uses its own addresses for the people it invites, but the owner "ari" is shared, so who is in his family must not leak between tests."""
    with hostdb.locked():
        conn = HostDatabase.from_env().db.conn
        conn.rollback()
        for sql in ("DELETE FROM ga_invites", "DELETE FROM ga_last_family", "DELETE FROM ga_passkeys", "DELETE FROM ga_passkey_challenges", "DELETE FROM ga_ai_usage", "DELETE FROM core_memberships WHERE role != 'owner'",
                    "UPDATE core_memberships SET is_active = 1 WHERE role = 'owner'"):
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:  # the invite tables are made the first time they are used
                conn.rollback()


def wipe_everything():
    """Clear the community database, the invites and extra members, and the family tables of every family a test opened.

    A family's tables can only hold rows if the family was opened (familydb.ensure_schema records every open, even across
    forget_schema_cache), so the wipe skips the rest and does not re-check any schema: it was made when the family was opened.
    """
    community.clear()
    shutil.rmtree(photos.root(), ignore_errors=True)  # F-071: the files of every photo a test added
    shutil.rmtree(passes.root(), ignore_errors=True)  # F-083: and of every boarding pass
    wipe_invites_and_extra_members()
    for tenant_id in familydb.take_opened():
        db = get_or_create_tenant_db(tenant_id)
        try:
            for _model, table, _pk in familydb.FAMILY_TABLES:
                db.conn.execute(text(f"DELETE FROM {table}"))
            db.conn.commit()
            try:
                db.conn.execute(text("DELETE FROM push_subscriptions"))  # F-066: made by a migration, so it is not in FAMILY_TABLES (a test that swapped the migrations folder may not have it)
                db.conn.commit()
            except Exception:
                db.conn.rollback()
        finally:
            db.conn.close()
