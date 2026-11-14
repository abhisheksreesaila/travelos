"""F-210 part A: a booking search becomes the family's trip ("Make this a trip"), landing on the cockpit. (F-231: Where to? was the other form that took a typed place; it is gone.)

Off the showcase (how production runs) /plan's any-place lanes carry a "Make this a trip" form that
POSTs /trip/new. Signed out, that form goes to sign-in and comes back to /trip/new to finish; a viewer is refused by the role guard and nothing is written."""

import re
from html import unescape
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from gitaway import familydb, session as ses
from tests.test_roles import crew  # noqa: F401 (the fixture)
from tests.test_showcase import assert_real
from tests.test_signin import person, sign_in

WHEN = {"d": "2026-12-04", "r": "2026-12-09", "a": "2"}


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")


def text(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def form_html(html, form_id):
    m = re.search(r'<form\b[^>]*id="%s"[^>]*>.*?</form>' % form_id, html, re.S)
    assert m, f"no form #{form_id}"
    return m.group(0)


def open_trip(traveler="ari"):
    """The trip row `traveler` has open, read from their family database (None when there is none)."""
    with ses.family(person(traveler)) as fam:
        return dict(familydb.trip(fam.db, fam.trip_id) or {}) or None if fam else None


def trip_count(traveler="ari"):
    with ses.family(person(traveler)) as fam:
        return familydb.row(fam.db, "SELECT COUNT(*) AS n FROM trips")["n"]


# ---- the booking lanes offer it ---------------------------------------------------------------------------------------------
# (F-231: Where to? was the other place that took a typed place and made a trip; its tests went with it. An old Where to? link is tests/test_way_in.py's.)

def test_the_booking_lanes_offer_make_this_a_trip(real, client):
    lanes = client.get("/plan", params={"place": "Lisbon", **WHEN}).text
    make = form_html(lanes, "ps-make")
    assert 'action="/trip/new"' in make and 'method="post"' in make and "Make this a trip" in make
    assert 'name="place" value="Lisbon"' in make and 'name="d" value="2026-12-04"' in make
    assert 'id="ps-make"' not in client.get("/plan").text      # nobody has said where yet: nothing to make


# ---- Make this a trip ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("place, title, zone, where", [
    ("Lisbon", "Trip to Lisbon", "Europe/Lisbon", "Lisbon"),
    ("lake tahoe", "Trip to Lake Tahoe", "America/Los_Angeles", "Lake Tahoe, California"),
])
def test_a_search_becomes_the_familys_open_trip_and_lands_on_the_cockpit(real, client, place, title, zone, where):
    sign_in(client)
    r = client.post("/trip/new", data={"place": place, **WHEN, "n": "2", "k1": "6", "k2": "9"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/cockpit"
    t = open_trip()
    assert t["title"] == title and t["depart"] == "2026-12-04" and t["return_on"] == "2026-12-09" and t["timezone"] == zone
    from gitaway import importer
    plan = importer.plan_of(person())
    assert plan.destination == where and plan.adults == 2 and plan.kid_ages == (6, 9) and not plan.legs and not plan.hotels
    cockpit = client.get("/trip/cockpit")
    assert cockpit.status_code == 200 and title.removeprefix("Trip to ") in cockpit.text


def test_making_the_same_trip_twice_makes_one(real, client):
    sign_in(client)
    before = trip_count()
    for _ in range(2):
        client.post("/trip/new", data={"place": "Lisbon", **WHEN}, follow_redirects=False)
    assert trip_count() == before + 1


def test_the_old_where_to_words_still_make_a_trip(real, client):      # (nothing sends them any more; tripstart.read still understands them)
    sign_in(client)
    r = client.post("/trip/new", data={"go": "1", "place": "Lisbon", "from": "SFO", **WHEN, "n": "0"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/cockpit" and open_trip()["title"] == "Trip to Lisbon"


def test_on_the_showcase_a_sample_city_chip_makes_its_trip(client):
    sign_in(client)
    r = client.post("/trip/new", data={"go": "1", "to": "sd", **WHEN, "n": "0"}, follow_redirects=False)
    assert r.status_code == 303 and open_trip()["title"] == "Trip to San Diego"


def test_a_bad_search_goes_back_to_the_booking_lanes_with_what_is_wrong(real, client):
    sign_in(client)
    before = trip_count()
    r = client.post("/trip/new", data={"place": "Lisbon", "d": "2026-12-09", "r": "2026-12-04", "a": "2"}, follow_redirects=False)
    assert r.status_code == 303 and urlsplit(r.headers["location"]).path == "/plan"
    again = client.get(r.headers["location"])
    assert again.status_code == 200 and "Lisbon" in again.text and 'role="alert"' in again.text and "ps-error" in again.text
    assert trip_count() == before


def test_signed_out_goes_to_sign_in_and_comes_back_to_finish(real, client):
    r = client.post("/trip/new", data={"place": "Lisbon", **WHEN, "n": "1", "k1": "6"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?")
    nxt = unquote(parse_qs(urlsplit(r.headers["location"]).query)["next"][0])
    assert nxt.startswith("/trip/new?") and "place=Lisbon" in nxt and "k=6" in nxt
    assert client.get(nxt, follow_redirects=False).headers["location"].startswith("/signin?")    # the finish page wants a sign-in too
    back = sign_in(client, next=nxt, intent="")
    assert back.status_code == 303 and back.headers["location"] == nxt
    page = client.get(nxt)
    assert page.status_code == 200
    make = form_html(page.text, "tn-make")
    assert 'action="/trip/new"' in make and 'method="post"' in make and "Make this a trip" in make and "Lisbon" in text(page.text)
    assert open_trip() is None or open_trip()["title"] != "Trip to Lisbon"      # the page alone writes nothing
    fields = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)"', make))
    done = client.post("/trip/new", data=fields, follow_redirects=False)
    assert done.headers["location"] == "/trip/cockpit" and open_trip()["title"] == "Trip to Lisbon"


def test_a_viewer_cannot_make_a_trip(real, crew):  # noqa: F811
    _, _, viewer = crew
    r = viewer.post("/trip/new", data={"place": "Lisbon", **WHEN}, follow_redirects=False)
    assert r.status_code == 403
    page = viewer.get("/trip/new", params={"place": "Lisbon", **WHEN})
    assert page.status_code == 200 and 'id="tn-make"' not in page.text and "look at this family" in page.text


@pytest.mark.parametrize("typed, zone", [("Paris, Texas", "America/Chicago"), ("Athens, Georgia", "America/New_York"), ("Lisbon", "Europe/Lisbon")])
def test_a_us_town_named_after_a_foreign_city_keeps_its_states_clock(typed, zone):
    """Review fix: the state the person typed outranks a zone named after the town."""
    from gitaway import tripstart
    from gitaway.partners import places
    assert tripstart.zone(places.resolve(typed)) == zone
