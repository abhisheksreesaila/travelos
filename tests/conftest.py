import os
import tempfile

import pytest
from starlette.testclient import TestClient

# Before main is imported: a throwaway data folder for the SQLite files, and the local dev sign-in on.
os.environ["GITAWAY_DATA_DIR"] = os.path.realpath(tempfile.mkdtemp(prefix="gitaway-test-"))  # realpath: Windows gives the 8.3 short name (ABHISH~1)
os.environ["GITAWAY_DEV_LOGIN"] = "1"
os.environ["DB_TYPE"] = "SQLITE"
os.environ["DB_NAME"] = "app_host"
# Set empty, not removed: fh-saas loads the project's .env on import and fills in any key that is missing,
# so real Google keys in a developer's .env would hide the dev sign-in from the tests.
for _key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_VERSION", "AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "SARVAM_API_KEY", "GITAWAY_AI_TRANSCRIBE_PROVIDER", "ANTHROPIC_API_KEY"):
    os.environ[_key] = ""
for _key in [k for k in os.environ if k.startswith("GITAWAY_AI_")]:
    os.environ[_key] = ""  # per-job AI settings from a shell or .env must not reach a test (F-079)
os.environ["GITAWAY_SHOWCASE"] = ""  # empty: tests start in the default (local) mode whatever the shell says; a test sets 0 or 1 itself (F-064)
os.environ["PLAN_FOR_ME_REVIEW"] = "0"  # Plan it for me delivers at once in the tests written before the founder check (F-197); a test of the check sets 1 (the default is off since F-199)
os.environ["PLAN_FOR_ME_PAID"] = "1"   # the tests written before F-199 sell Plan it for me (Stripe, the price, the refund); the free plan's tests (tests/test_planforme_free.py) set 0 or remove it
for _key in ("GITAWAY_VAPID_PUBLIC", "GITAWAY_VAPID_PRIVATE", "GITAWAY_VAPID_SUBJECT"):
    os.environ[_key] = ""  # empty, not removed: a .env found above the folder must not switch the real push sender on in a test run (F-066)
os.environ["MET_NORWAY_TERMS_ACCEPTED"] = ""  # the real forecast is off in tests whatever a .env says; a test switches it on with its own fake MET (F-203)


@pytest.fixture(scope="session", autouse=True)
def _fast_throwaway_sqlite():
    """The test databases are thrown away, so they need no rollback journal on disk and no fsync. On Windows each journal file
    made and deleted per write cost ~17 ms (every test took about a second); on Linux it changes little."""
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def fast(dbapi_conn, _record):
        if type(dbapi_conn).__module__.startswith("sqlite3"):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA synchronous=OFF")
            try:
                cur.execute("PRAGMA journal_mode=MEMORY")
            except Exception:  # another connection holds the file right now (concurrency tests): this one keeps the default journal
                pass
            cur.close()
    event.listen(Engine, "connect", fast)
    yield
    event.remove(Engine, "connect", fast)


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
def _no_ai_network(monkeypatch):
    """No test reaches the AI service (F-079): every call fails unless the test installs its own fake `ai.TRANSPORT`."""
    from gitaway import ai

    def refuse(url, headers, body, timeout):
        raise OSError("the network is off in tests")
    monkeypatch.setattr(ai, "TRANSPORT", refuse)

    def refuse_anthropic(kwargs, timeout):
        raise OSError("the network is off in tests")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", refuse_anthropic)    # F-183: nor the Anthropic SDK
    from gitaway import safefetch

    def refuse_fetch(url, ip, timeout, kind):
        raise OSError("the network is off in tests")
    monkeypatch.setattr(safefetch, "TRANSPORT", refuse_fetch)           # F-183: nor a creator's blog (DNS is faked per test with safefetch.RESOLVER)
    monkeypatch.setattr(safefetch, "RESOLVER", lambda host: ["93.184.216.34"])
    ai._transcribe_hits.clear()     # F-102: the per-family cap on voice pieces starts empty in every test


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
    monkeypatch.setattr(geo.NOMINATIM_GATE, "shut_until", None)  # a test that triggers the back off must not leave the gate shut
    monkeypatch.setattr(geo.OSRM_GATE, "shut_until", None)
    from gitaway import around  # Around you (F-073) reaches Overpass through geo.fetch too: its gate and its 30 minute cache start fresh in every test
    around.clear_cache()
    monkeypatch.setattr(around.GATE, "gap", 0.0)
    monkeypatch.setattr(around.GATE, "shut_until", None)
    from gitaway import geopack   # F-201: nor the paper map's pack (Overpass, the terrain tiles); a pack builds in the test's own thread, its gates start open
    def refuse_pack(url, data=None, timeout=0):
        raise OSError("the network is off in tests")
    monkeypatch.setattr(geopack, "TRANSPORT", refuse_pack)
    monkeypatch.setattr(geopack, "ASYNC", False)
    for gate in (geopack.OVERPASS_GATE, geopack.TILE_GATE):
        monkeypatch.setattr(gate, "gap", 0.0)
        monkeypatch.setattr(gate, "shut_until", None)
    geopack.forget_failures()


@pytest.fixture(autouse=True)
def _no_weather_network(monkeypatch):
    """No test reaches MET Norway (F-203): every forecast call fails unless the test installs its own fake `weather.TRANSPORT`
    (tests/weather_support.Met). The forecast cache and the gate start fresh in every test."""
    from gitaway import weather

    def refuse(url, headers, timeout):
        raise OSError("the network is off in tests")
    monkeypatch.setattr(weather, "TRANSPORT", refuse)
    monkeypatch.setattr(weather.GATE, "gap", 0.0)
    monkeypatch.setattr(weather.GATE, "shut_until", None)
    weather.clear()
    yield
    weather.clear()


@pytest.fixture(autouse=True)
def _no_plan_worker():
    """A test that starts the app (a live server) starts the Plan it for me worker with it (planforme.start in on_startup), and it would go on building the paid orders of every later test
    before the test looks at them. Stop it before each test; a test that wants the worker calls `planforme.start` itself and stops it (F-193)."""
    from gitaway import planforme
    planforme.stop()


@pytest.fixture(autouse=True)
def _one_geo_module():
    """A test that removes `gitaway.geo` from sys.modules (to play "no geo module") makes the next import build a second copy, and the package attribute
    `gitaway.geo` then points at the copy while sys.modules holds the original: later tests patch one and the app reads the other. Put both back."""
    import sys
    import gitaway
    from gitaway import geo
    yield
    sys.modules["gitaway.geo"] = geo
    gitaway.geo = geo


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
