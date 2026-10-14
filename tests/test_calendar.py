"""The old trip calendar is retired (F-147): /calendar, /invite and /trips are only addresses now. Also the helpers many tests share (book, add, tag)."""

import re
from pathlib import Path

from tests.test_signin import sign_in

ROOT = Path(__file__).resolve().parent.parent

PICK = {"f": "f1", "h": "h1", "c": "c1"}
FORM = {"day": "1", "start": "10:00", "end": "11:30", "title": "Venice Canals stroll", "kind": "outdoors"}


def book(client, traveler="ari", **pick):
    sign_in(client, traveler)
    return client.post("/pay", data={**PICK, **pick}, follow_redirects=False)


def add(client, id="a1", **over):
    """A plan on the trip, through the same route the phone's add sheet posts to (the plan runs an hour from its start)."""
    return client.post("/trip/plans", data={"id": id, **FORM, **over}, follow_redirects=False)


def tag(html, attr, value):
    """The attributes of the first tag carrying attr="value", as a dict (attribute order is not part of the contract)."""
    m = re.search(r'<[a-z0-9]+\s[^>]*\b%s="%s"[^>]*>' % (re.escape(attr), re.escape(value)), html)
    return dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(0))) if m else None


# ---- the addresses that still answer ------------------------------------------------------------------------------

def test_calendar_goes_to_the_trips_day_for_a_booked_trip_on_any_screen(client):
    book(client)
    for headers in ({}, {"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148 Safari/604.1"}):
        r = client.get("/calendar", headers=headers, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/trip/canvas")


def test_calendar_keeps_a_day_it_was_asked_for(client):
    book(client)
    assert client.get("/calendar?day=2", follow_redirects=False).headers["location"].startswith("/trip/canvas?day=2")
    assert client.get("/calendar?view=days&add=1&at=10:00", follow_redirects=False).headers["location"].startswith("/trip/canvas?day=1")
    assert client.get("/calendar?day=999", follow_redirects=False).headers["location"].startswith("/trip/canvas")


def test_calendar_signed_out_signs_in_and_without_a_booking_starts_one(client):
    r = client.get("/calendar", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/signin?next=%2Ftrip"
    sign_in(client)
    assert client.get("/calendar", follow_redirects=False).headers["location"] == "/start"


def test_trips_goes_to_the_current_trip_instead_of_a_404(client):
    assert client.get("/trips", follow_redirects=False).headers["location"] == "/signin?next=%2Ftrip"
    book(client)
    r = client.get("/trips", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/trip/canvas")
    assert client.get("/trips/", follow_redirects=False).status_code in (303, 307, 308)


def test_invite_goes_to_the_invitations_in_family(client):
    book(client)
    r = client.get("/invite", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/family#invite"


def test_invite_signed_out_signs_in_first_and_comes_back_to_family(client):
    r = client.get("/invite", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=%2Ffamily")
    assert "intent=invite" in r.headers["location"]


def test_the_old_calendar_posts_are_gone(client):
    book(client)
    for path in ("/calendar/activities", "/calendar/notes", "/calendar/undo", "/calendar/friends", "/calendar/live", "/calendar/voice/apply"):
        assert client.post(path, data={}, follow_redirects=False).status_code in (404, 405), path


# ---- nothing links to it any more ---------------------------------------------------------------------------------

def test_no_page_or_script_links_to_the_old_calendar():
    """Only the module that redirects the address may name /calendar."""
    hits = []
    for folder in ("gitaway", "assets/js"):
        for f in (ROOT / folder).rglob("*"):
            if f.suffix not in (".py", ".js") or "vendor" in f.parts or f.name == "calendar.py":
                continue
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"""["'`(=]/calendar\b""", line):
                    hits.append(f"{f.relative_to(ROOT)}:{n}")
    assert not hits, hits


def test_the_signed_in_pages_have_no_calendar_link(client):
    book(client)
    add(client)
    for path in ("/trip", "/trip/canvas", "/trip/canvas?day=1", "/trip?add=1&day=1", "/start", "/family", "/trip/details", "/trip/map", "/trip/ask", "/forks", "/rides"):
        r = client.get(path, follow_redirects=True)
        assert 'href="/calendar' not in r.text, path


def test_the_old_calendar_code_is_gone():
    for gone in ("assets/css/calendar.css", "assets/js/calendar.js", "assets/css/voice.css", "assets/js/voice.js", "gitaway/pages/voice.py", "gitaway/voice.py"):
        assert not (ROOT / gone).exists(), gone


def test_invite_is_not_a_placeholder():
    from gitaway.pages import placeholders
    assert "/invite" not in placeholders.PLACEHOLDERS and "/calendar" not in placeholders.PLACEHOLDERS
