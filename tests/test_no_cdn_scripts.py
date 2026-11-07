"""F-207: every page loads its scripts from GitAway itself, never from another site.

FastHTML's default headers loaded htmx, fasthtml-js, surreal and css-scope-inline from jsDelivr on every page (the last two from a
moving @main branch, none with an integrity hash): a push to one of those repos would have run on gitaway.me with the person's
session. main.py turns them off (htmx=False, surreal=False) and keeps the charset and viewport tags. The one script allowed from
another site is Travelpayouts Drive, on the signed-out landing only, when TRAVELPAYOUTS_DRIVE_ID is set (tests/test_travelpayouts_drive.py)."""

import re
from html.parser import HTMLParser

import pytest

from tests.test_signin import sign_in

DRIVE = "https://tp-em.com/NTk2NTM0.js?t=596534"  # what TRAVELPAYOUTS_DRIVE_ID=596534 loads
CHARSET = '<meta charset="utf-8">'
VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'


class _Scripts(HTMLParser):
    """The src of every <script> on a page, read the way the browser reads the tag."""

    def __init__(self):
        super().__init__()
        self.srcs = []

    def handle_starttag(self, tag, attrs):
        src = dict(attrs).get("src")
        if tag == "script" and src is not None:
            self.srcs.append(src)


def scripts_from_elsewhere(html):
    """Every script src that leaves the site: one with a scheme (https:, http:, data:) or scheme-relative (//host/x.js; a browser reads \\ as /)."""
    found = _Scripts()
    found.feed(html)
    return [src for src in found.srcs if re.match(r"\s*(//|[a-z][a-z0-9+.-]*:)", src.replace("\\", "/"), re.I)]


def assert_own_scripts_only(r, path):
    assert r.status_code == 200, path
    assert scripts_from_elsewhere(r.text) == [], path
    assert r.text.count(CHARSET) == 1 and r.text.count(VIEWPORT) == 1, path  # FastHTML's two defaults that stay


@pytest.mark.parametrize("path", ["/", "/signin", "/privacy"])
def test_signed_out_pages_load_no_script_from_elsewhere(client, monkeypatch, path):
    monkeypatch.delenv("TRAVELPAYOUTS_DRIVE_ID", raising=False)
    assert_own_scripts_only(client.get(path), path)


@pytest.mark.parametrize("path", ["/", "/trip/canvas", "/trip/ask", "/family"])
def test_signed_in_pages_load_no_script_from_elsewhere(client, monkeypatch, path):
    monkeypatch.setenv("TRAVELPAYOUTS_DRIVE_ID", "596534")  # switched on, and still never for a signed-in person
    sign_in(client, "ari")
    assert_own_scripts_only(client.get(path), path)


def test_the_drive_is_the_one_script_allowed_from_elsewhere(client, monkeypatch):
    """Switched on, the signed-out landing loads Travelpayouts Drive and nothing else from another site; no other page loads it."""
    monkeypatch.setenv("TRAVELPAYOUTS_DRIVE_ID", "596534")
    assert scripts_from_elsewhere(client.get("/").text) == [DRIVE]
    for path in ("/signin", "/privacy", "/start"):
        assert scripts_from_elsewhere(client.get(path).text) == [], path


@pytest.mark.parametrize("signed_in", [False, True], ids=["out", "in"])
def test_no_page_loads_a_script_from_elsewhere(client, monkeypatch, signed_in):
    """Every GET page, signed out and signed in: a page's own scripts are held to the same rule as the shared head."""
    from main import app
    monkeypatch.delenv("TRAVELPAYOUTS_DRIVE_ID", raising=False)
    if signed_in:
        sign_in(client, "ari")
    paths = {r.path for r in app.routes if "GET" in (getattr(r, "methods", None) or ()) and "{" not in r.path}
    paths = sorted((paths - {"/logout"}) | {"/trips/sun-tacos-and-tide-pools"})  # /logout would sign the walk out
    assert {"/", "/signin", "/trip/canvas", "/family", "/creators"} <= set(paths)
    pages = 0
    for path in paths:
        r = client.get(path)
        if r.headers.get("content-type", "").startswith("text/html"):
            pages += 1
            assert scripts_from_elsewhere(r.text) == [], path
    assert pages > 30
