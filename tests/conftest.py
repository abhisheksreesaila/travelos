import os
import tempfile

import pytest
from starlette.testclient import TestClient

# Before main is imported: a throwaway data folder for the SQLite files, and the local dev sign-in on.
os.environ["GITAWAY_DATA_DIR"] = tempfile.mkdtemp(prefix="gitaway-test-")
os.environ["GITAWAY_DEV_LOGIN"] = "1"
os.environ["DB_TYPE"] = "SQLITE"
os.environ["DB_NAME"] = "app_host"
for _key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
    os.environ.pop(_key, None)


@pytest.fixture
def client():
    from main import app
    return TestClient(app, client=("127.0.0.1", 50000))  # the dev sign-in only answers to this machine


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    """The demo's sample trip is in October 2026; keep "today" before it so date checks do not rot."""
    from datetime import date
    from gitaway import catalog
    monkeypatch.setattr(catalog, "today", lambda: date(2026, 9, 30), raising=False)


@pytest.fixture(autouse=True)
def _clean_community_and_family_social():
    """Every test starts with an empty community and no forks or saves (the data folder is shared by the whole run)."""
    yield
    from gitaway import community, familydb_social
    community.clear()
    familydb_social.clear_all(familydb_social.known_tenants())
