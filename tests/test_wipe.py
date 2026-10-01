"""The between-test wipe (tests/wipe.py) clears only the families a test opened, and still clears every one of them (F-045)."""

from fh_saas.db_tenant import _reset_tenant_db_cache

from gitaway import catalog, familydb, session as ses
from tests.test_family_storage import count
from tests.test_signin import person
from tests.wipe import wipe_everything


def test_a_family_opened_before_a_cache_reset_is_still_wiped():
    ari = person("ari")
    ses.book(ari, catalog.quote("f1", "h1", "c1"))
    assert count(ari, "trips") == 1
    _reset_tenant_db_cache()
    familydb.forget_schema_cache()  # what a restart forgets: the opened set must survive it
    wipe_everything()
    assert count(ari, "trips") == 0 and count(ari, "bookings") == 0


def test_the_wipe_takes_only_the_families_opened_since_the_last_wipe():
    ari = person("ari")
    ses.book(ari, catalog.quote("f1", "h1", "c1"))
    wipe_everything()
    assert familydb.take_opened() == set()  # nothing opened since: the next wipe has nothing to do
    ses.booking(ari)  # opens the family again
    assert ari["tenant_id"] in familydb.take_opened()
