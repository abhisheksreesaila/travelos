import os
import tempfile

import pytest
from starlette.testclient import TestClient

# Before main is imported: a throwaway data folder for the SQLite files, and the local dev sign-in on.
os.environ["GITAWAY_DATA_DIR"] = tempfile.mkdtemp(prefix="gitaway-test-")
os.environ["GITAWAY_DEV_LOGIN"] = "1"
os.environ["DB_TYPE"] = "SQLITE"
os.environ["DB_NAME"] = "app_host"
# Set empty, not removed: fh-saas loads the project's .env on import and fills in any key that is missing,
# so real Google keys in a developer's .env would hide the dev sign-in from the tests.
for _key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
    os.environ[_key] = ""
os.environ["GITAWAY_SHOWCASE"] = ""  # empty: tests start in the default (local) mode whatever the shell says; a test sets 0 or 1 itself (F-064)
for _key in ("GITAWAY_VAPID_PUBLIC", "GITAWAY_VAPID_PRIVATE", "GITAWAY_VAPID_SUBJECT"):
    os.environ[_key] = ""  # empty, not removed: a .env found above the folder must not switch the real push sender on in a test run (F-066)


@pytest.fixture(scope="session", autouse=True)
def _work_from_the_data_folder():
    """fh-saas opens its databases relative to the working directory, and main.py moves there only when it is first imported.

    A test that never imported main (a pure-function test run first, in reverse or random order) made the teardown wipe open a host
    database in the project folder, and later tests and subprocesses then saw another one. Do the move before any test.
    """
    from gitaway import auth
    auth.configure_storage()


@pytest.fixture
def client():
    from main import app
    return TestClient(app, client=("127.0.0.1", 50000))  # the dev sign-in only answers to this machine


@pytest.fixture(autouse=True)
def _offline_maps(monkeypatch):
    """No test reaches the map services (F-068): every lookup fails unless the test installs its own fake `geo.fetch`. Background fills stay off."""
    from gitaway import geo

    def refuse(url, timeout=0):
        raise OSError("the network is off in tests")
    monkeypatch.setattr(geo, "fetch", refuse)
    monkeypatch.setattr(geo, "ASYNC", False)
    monkeypatch.setattr(geo.NOMINATIM_GATE, "gap", 0.0)
    monkeypatch.setattr(geo.OSRM_GATE, "gap", 0.0)


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    """The demo's sample trip is in October 2026; keep "today" before it so date checks do not rot."""
    from datetime import date
    from gitaway import catalog
    monkeypatch.setattr(catalog, "today", lambda: date(2026, 9, 30), raising=False)


@pytest.fixture(autouse=True)
def _empty_community_and_families():
    """Every test starts empty: one data folder is shared by the whole run, so rows must not leak between tests.

    The community database is emptied. In every family database the family tables are cleared (trips, bookings, calendar, friends,
    rides, forks and saves: everything in familydb.FAMILY_TABLES); people and memberships stay, they are the host database's.
    """
    yield
    from tests.wipe import wipe_everything
    wipe_everything()
