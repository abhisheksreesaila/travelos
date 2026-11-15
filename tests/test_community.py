"""The community database (F-041): published trips are snapshots anyone can open; forks and saves belong to the family."""

import re

from starlette.testclient import TestClient

from gitaway import community, familydb, familydb_social as social
from tests.pagebody import without_bar
from tests.test_calendar import add, book
from tests.test_signin import session_data, sign_in, stored_booking, tid

TRIP = "sun-tacos-and-tide-pools"


def device(client):
    """Another browser: the same app with no cookies."""
    return TestClient(client.app, client=("127.0.0.1", 50000))


def shared_slug(owner="ari"):
    return community.rows(kind="shared", owner=tid(owner))[0]["slug"]


def share(client, **data):
    return client.post("/share", data=data, follow_redirects=False)


def main_html(html):
    return html.split("<main")[1].split("</main>")[0]


def _signed_in(client, who):
    other = device(client)
    sign_in(other, who)
    return other


def test_the_share_slug_is_keyed_with_the_server_secret(monkeypatch):
    from gitaway import session as ses, share as sh
    b = {"id": "GA-12345678"}
    first = sh.slug_for("u1", b)
    monkeypatch.setattr(ses, "cache_secret", lambda: b"another secret")
    assert sh.slug_for("u1", b) != first and sh.slug_for("u1", b) == sh.slug_for("u1", b)
