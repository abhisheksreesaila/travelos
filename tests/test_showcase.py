"""F-064: the live site shows only what's real. One switch (gitaway.showcase), tested in both modes through the HTTP seam.

`real` turns the showcase off with GITAWAY_SHOWCASE=0 (production sets it off by itself; the dev sign-in stays available locally).
"""

import re

import pytest

from gitaway import auth, itineraries, showcase
from tests.test_calendar import book
from tests.test_signin import sign_in

SLUGS = list(itineraries.ITINERARIES)
SAMPLE_WORDS = ["Community trips", "For creators", "Your forks", "Trips others loved", "Fork a trip a real family took", "Leave a trail",
                "Our LA family week", "Forked by", "312 families", "No plans yet?"] + [t.title for t in itineraries.ITINERARIES.values()]
GONE_HREF = re.compile(r'href="(/community|/discover|/creators|/forks|/share|/trips/(?!build|import|switch)[^"/?#]+)')


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

HIDDEN_GET = ["/community", "/discover", "/discover?tag=beach", "/creators", "/creators/draft", "/creators/finish", "/creators/done", "/forks", "/share", "/share/done",
              "/calendar?demo=long", "/calendar?demo=long&view=days"] + [f"/trips/{s}" for s in SLUGS] + ["/trips/anything-shared"]
HIDDEN_POST = ["/fork", "/save", "/unsave", "/share", "/share/unpublish", "/forks/apply", "/forks/undo", "/creators", "/creators/draft", "/creators/finish",
               "/calendar/friends", "/calendar/live"]


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
    for path in ["/trips/import", "/trips/build", "/start", "/calendar", "/family", "/signin", "/offline"]:
        assert client.get(path, follow_redirects=False).status_code in (200, 303), path


def test_the_404_page_links_nowhere_hidden(real, client):
    r = client.get("/community")
    assert r.status_code == 404
    assert_real(r.text, "404")


def test_the_real_production_environment_hides_them_too(prod, client):
    assert client.get("/community").status_code == 404
    assert client.get(f"/trips/{SLUGS[0]}").status_code == 404
    assert client.get("/healthz").status_code == 200


# ---- production: nothing links to them, nothing sample shows ----

PAGES_SIGNED_OUT = ["/", "/start", "/signin", "/offline", "/plan", "/plan?f=f1&h=h1&c=c1", "/trips/import", "/trips/build", "/community"]


@pytest.mark.parametrize("path", PAGES_SIGNED_OUT)
def test_signed_out_pages_have_no_sample_data_or_links_to_hidden_pages(real, client, path):
    r = client.get(path)
    assert_real(r.text, path)


def test_the_landing_keeps_its_story_without_community_and_creators(real, client):
    h = client.get("/").text
    assert "Fork a" in h and "getaway." in h and "verb" in h                       # the hero and its gloss
    assert "Everything side by side" in h and "Plan the fun part together" in h    # features and the animated calendar
    assert 'id="cal"' in h and "community-trips" not in h and 'class="forkline"' not in h
    assert 'action="/start"' in h and "Plan a trip" in h


def _search_form(html):
    return re.search(r'<form[^>]*class="search".*?</form>', html, re.S).group(0)


def test_the_landing_search_fields_are_neutral_in_production_and_the_sample_trip_locally(real, client, monkeypatch):
    form = _search_form(client.get("/").text)
    assert "Los Angeles" not in form and "Where to?" in form
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    assert "Los Angeles" in _search_form(client.get("/").text)


def test_footer_links_are_only_real_destinations(real, client):
    footer = re.search(r"<footer.*?</footer>", client.get("/").text, re.S).group(0)
    assert re.findall(r'href="([^"]*)"', footer) == ["/signin"]
    sign_in(client)
    footer = re.search(r"<footer.*?</footer>", client.get("/").text, re.S).group(0)
    assert "href=" not in footer


def test_the_workspace_is_labelled_a_preview_with_sample_prices(real, client):
    h = client.get("/plan").text
    assert "Preview: sample prices, nothing is booked." in h
    assert 'data-pane="community"' not in h and "Press 1–6" in h and 'id="ws-total"' in h and 'id="ws-book"' in h


def test_a_new_family_sees_two_ways_in_not_community(real, client):
    sign_in(client)
    for path in ["/start", "/calendar", "/trip"]:
        r = client.get(path, follow_redirects=True)
        assert r.status_code == 200, path
        assert_real(r.text, path)
    start = client.get("/start").text
    assert "fr-two" in start and "Plan a trip" in start and "Import a trip you booked" in start


def booked_then_real(client, monkeypatch):
    """A family that booked on a local copy (showcase on), then looked at in production mode."""
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    book(client)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")


def test_a_booked_trip_has_no_forks_share_or_pretend_friends(client, monkeypatch):
    booked_then_real(client, monkeypatch)
    h = client.get("/calendar").text
    assert_real(h, "/calendar")
    assert 'action="/share"' not in h and "/calendar/friends" not in h
    assert 'href="/family' in h
    invite = client.get("/calendar?invite=1")
    assert invite.status_code == 200 and "pretend" not in invite.text and "nobody is really emailed" not in invite.text


def test_the_service_worker_version_changes_with_the_mode(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    a = client.get("/sw.js").text
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    b = client.get("/sw.js").text
    assert re.search(r'VERSION = "(\w+)"', a).group(1) != re.search(r'VERSION = "(\w+)"', b).group(1)
    assert "/community" not in b


# ---- the local copy keeps everything ----

def test_the_local_copy_still_shows_all_sample_data(client):
    assert showcase.on()
    h = client.get("/").text
    for word in ["Community trips", "For creators", "No plans yet?", "Leave a trail"]:
        assert word in h
    assert "forks" in h
    for path in ["/community", "/creators", "/forks", f"/trips/{SLUGS[0]}", "/discover"]:
        assert client.get(path).status_code == 200, path
    assert client.get("/plan").text.count('data-pane="community"') == 1
    assert "Preview: sample prices" not in client.get("/plan").text
    sign_in(client)
    assert "Browse community trips" in client.get("/start").text
    book(client)
    c = client.get("/calendar").text
    assert "Your forks" in c and 'action="/share"' in c
    assert client.get("/calendar?demo=long").status_code == 200


# ---- production: no scripted demo, and the preview books nothing ----

def test_talk_to_plan_is_gone_in_production_and_its_routes_404(client, monkeypatch):
    booked_then_real(client, monkeypatch)
    h = client.get("/calendar").text
    assert "Talk to plan" not in h and "vo-open" not in h
    assert "vo-panel" not in client.get("/calendar?view=days&voice=1&hear=1").text
    for path in ["/calendar/voice/apply", "/calendar/voice/undo"]:
        assert client.post(path, data={}, follow_redirects=False).status_code == 404


def test_the_local_copy_keeps_talk_to_plan(client):
    book(client)
    assert "Talk to plan" in client.get("/calendar").text


def test_the_booking_preview_writes_nothing_in_production(real, client):
    from tests.test_calendar import PICK
    sign_in(client)
    msg = "Booking opens after your trip. Add the trip you booked instead."
    r = client.post("/pay", data=PICK, follow_redirects=False)
    assert r.status_code == 200 and msg in r.text and 'href="/trips/import"' in r.text and 'href="/trips/build"' in r.text
    r = client.get("/plan/pay?f=f1&h=h1&c=c1", follow_redirects=False)
    assert r.status_code == 200 and msg in r.text
    assert client.get("/booked", follow_redirects=False).status_code == 303
    assert "Your calendar starts with a trip" in client.get("/calendar").text
    assert client.get("/start").text.count("Continue ") == 0
