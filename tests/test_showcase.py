"""F-064: the live site shows only what's real. One switch (gitaway.showcase), tested in both modes through the HTTP seam.

`real` turns the showcase off with GITAWAY_SHOWCASE=0 (production sets it off by itself; the dev sign-in stays available locally).
"""

import re

import pytest

from gitaway import auth, itineraries, showcase
from tests.test_calendar import book
from tests.test_signin import sign_in

SLUGS = list(itineraries.ITINERARIES)
SAMPLE_WORDS = ["Your forks", "Trips others loved", "Fork a trip a real family took", "Been somewhere wonderful?",   # the old landing's sample creators panel (F-206 made "Leave a trail" the product's line)
                "Our LA family week", "Forked by", "312 families", "No plans yet?"] + [t.title for t in itineraries.ITINERARIES.values()]
GONE_HREF = re.compile(r'href="(/discover|/creators|/forks|/share|/rides|/trips/(?!build|import|switch)[^"/?#]+)')


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")


@pytest.fixture
def prod(monkeypatch):
    """Real production settings: nothing but the environment decides."""
    monkeypatch.setenv("GITAWAY_ENV", "production")
    monkeypatch.setenv("GITAWAY_SECRET_KEY", "a-test-secret")
    monkeypatch.delenv("GITAWAY_SHOWCASE", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)


def assert_real(html, where=""):
    found = GONE_HREF.search(html)
    assert not found, f"{where}: a link to a hidden page: {found.group(0)}"
    for word in SAMPLE_WORDS:
        assert word not in html, f"{where}: {word!r}"
    assert not re.search(r"\b\d+ forks?\b", html), where


# ---- the switch ----

def test_showcase_follows_production_unless_overridden(monkeypatch):
    for k in ("GITAWAY_ENV", "RAILWAY_ENVIRONMENT", "GITAWAY_SHOWCASE"):
        monkeypatch.delenv(k, raising=False)
    assert showcase.on()
    monkeypatch.setenv("GITAWAY_ENV", "production")
    assert auth.production() and not showcase.on()
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    assert showcase.on()
    monkeypatch.setenv("GITAWAY_ENV", "")
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert not showcase.on()


def test_production_alone_turns_the_showcase_off_and_keeps_the_dev_sign_in_locked(prod, monkeypatch):
    monkeypatch.setenv("GITAWAY_DEV_LOGIN", "1")
    assert not showcase.on() and not auth.dev_login_enabled()


# ---- production: hidden routes ----

HIDDEN_GET = ["/creators", "/creators/draft", "/creators/finish", "/creators/done", 
              ] + [f"/trips/{s}" for s in SLUGS] + ["/trips/anything-shared"]
HIDDEN_POST = ["/save", "/unsave", "/creators", "/creators/draft", "/creators/finish"]


@pytest.mark.parametrize("path", HIDDEN_GET)
def test_hidden_pages_are_404_in_production(real, client, path):
    assert client.get(path, follow_redirects=False).status_code == 404
    sign_in(client)
    assert client.get(path, follow_redirects=False).status_code == 404


@pytest.mark.parametrize("path", HIDDEN_POST)
def test_hidden_writes_are_404_in_production(real, client, path):
    sign_in(client)
    assert client.post(path, data={"next": "/trips/" + SLUGS[0], "slug": SLUGS[0]}, follow_redirects=False).status_code == 404


def test_the_families_own_trip_routes_still_work(real, client):
    sign_in(client)
    for path in ["/trips/import", "/trips/build", "/", "/calendar", "/family", "/signin", "/offline"]:
        assert client.get(path, follow_redirects=False).status_code in (200, 303), path


@pytest.mark.parametrize("env", ["real", "prod"])
def test_guides_says_so_before_anyone_has_shared(env, request, client):
    """D-458 (founder, 2026-11-13: "the navigation should still say: if you want to look at the community trips, go at it"; F-262: the page is Guides): Guides is
    in every header, so off the showcase, before anyone has shared a guide, its page exists and says so plainly, with no sample guide on it."""
    request.getfixturevalue(env)
    r = client.get("/guides")
    assert r.status_code == 200
    assert "No guides yet" in r.text and 'href="/guides/make"' in r.text
    assert_real(r.text, "/guides")


@pytest.mark.parametrize("old,new", [("/community", "/guides"), ("/discover", "/guides"), ("/discover?tag=beach", "/guides"), ("/for-creators", "/guides")])
def test_the_old_community_and_creator_addresses_always_go_to_guides(real, client, old, new):
    r = client.get(old, follow_redirects=False)      # a redirect, never a 404, whatever is published (F-262)
    assert r.status_code == 301 and r.headers["location"] == new


# ---- production: nothing links to them, nothing sample shows ----

PAGES_SIGNED_OUT = ["/", "/start", "/signin", "/offline", "/plan", "/plan?f=f1&h=h1&c=c1", "/plan?f=f1&h=h1&c=none", "/trips/import", "/trips/build", "/guides"]


@pytest.mark.parametrize("path", PAGES_SIGNED_OUT)
def test_signed_out_pages_have_no_sample_data_or_links_to_hidden_pages(real, client, path):
    r = client.get(path)
    assert_real(r.text, path)


def test_footer_links_are_only_real_destinations(real, client):
    footer = re.search(r"<footer.*?</footer>", client.get("/").text, re.S).group(0)
    assert re.findall(r'href="([^"]*)"', footer) == ["/guides", "/signin", "/privacy", "/terms"]  # the cover's footer (F-227: no screenshots of map data any more, so no map credit)
    sign_in(client)
    footer = re.search(r"<footer.*?</footer>", client.get("/trips/import").text, re.S).group(0)      # F-231: a signed-in person has no landing, and no page of theirs adds links to the footer
    assert re.findall(r'href="([^"]*)"', footer) == ["/privacy", "/terms"]      # F-272: a v2 reading page's foot is the legal pair and nothing else


def test_a_new_family_sees_two_ways_in_not_community(real, client):
    sign_in(client)
    assert client.get("/", follow_redirects=False).headers["location"] == "/trips/import"      # F-231: no matrix without a LiteAPI key, so the way in is the import of a trip already booked
    for path in ["/", "/calendar", "/trip"]:
        r = client.get(path, follow_redirects=True)
        assert r.status_code == 200, path
        assert_real(r.text, path)
    from fasthtml.common import to_xml
    from gitaway import firstrun
    ways = to_xml(firstrun.paths())
    assert "fr-two" in ways and "Import a trip you booked" in ways and "Find a trip" not in ways and "community" not in ways


def booked_then_real(client, monkeypatch):
    """A family that booked on a local copy (showcase on), then looked at in production mode."""
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    book(client)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")


def test_a_booked_trip_has_no_forks_share_or_pretend_friends(client, monkeypatch):
    booked_then_real(client, monkeypatch)
    h = client.get("/trip/canvas").text
    assert_real(h, "/trip/canvas")
    assert 'action="/share"' not in h and 'href="/forks' not in h


def test_the_service_worker_version_changes_with_the_mode(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    a = client.get("/sw.js").text
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    b = client.get("/sw.js").text
    assert re.search(r'VERSION = "(\w+)"', a).group(1) != re.search(r'VERSION = "(\w+)"', b).group(1)
    assert "/community" not in b


# ---- the local copy keeps everything ----

# ---- production: no scripted demo, and the preview books nothing ----

# ---- production: the simulated Uber is gone ----

@pytest.mark.parametrize("path", ["/trip/plans", "/trip/notes", "/trip/canvas/plan", "/trip/canvas/actnote"])
def test_demo_long_in_a_form_body_writes_nothing_in_production(client, monkeypatch, path):
    booked_then_real(client, monkeypatch)
    r = client.post(path, data={"demo": "long", "id": "a1", "day": "1", "start": "10:00", "end": "11:00", "title": "Sneaky", "text": "Sneaky"}, follow_redirects=False)
    assert r.status_code == 404
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    assert "Sneaky" not in client.get("/trip/canvas?demo=long&day=1").text
