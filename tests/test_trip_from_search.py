"""F-210 part A: "Where to?" takes any place, and a booking search becomes the family's trip ("Make this a trip"), landing on the cockpit.

Off the showcase (how production runs) /start has no sample cities and no sample prices; /plan's any-place lanes and /start both carry a "Make this a trip" form that
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


# ---- Where to? takes any place ----------------------------------------------------------------------------------------

def test_where_to_off_the_showcase_has_a_place_box_and_no_sample_cities_or_prices(real, client):
    h = client.get("/start").text
    form = form_html(h, "st-form")
    assert re.search(r'<input\b[^>]*name="place"[^>]*type="text"|<input\b[^>]*type="text"[^>]*name="place"', form)
    assert 'name="to"' not in form
    for sample in ("Los Angeles", "San Diego", "Honolulu", "New York", "Sample prices"):
        assert sample not in form, sample
    assert_real(h, "/start")


def test_where_to_sends_any_typed_place_to_the_booking_lanes(real, client):
    r = client.get("/start", params={"go": "1", "place": "Lisbon", "from": "", **WHEN, "n": "1", "k1": "6"}, follow_redirects=False)
    assert r.status_code == 303
    loc = urlsplit(r.headers["location"])
    q = {k: v[0] for k, v in parse_qs(loc.query).items()}
    assert loc.path == "/plan" and q == {"place": "Lisbon", **WHEN, "k": "6"}
    page = client.get(r.headers["location"]).text
    assert "Book your trip to Lisbon" in page


def test_where_to_asks_for_a_place_when_none_is_typed(real, client):
    r = client.get("/start", params={"go": "1", "place": "  ", **WHEN, "n": "0"}, follow_redirects=False)
    assert r.status_code == 422
    assert "Type where you want to go" in r.text and 'aria-invalid="true"' in form_html(r.text, "st-form")


def test_where_to_keeps_a_typed_place_and_an_old_city_link_names_its_city(real, client):
    assert re.search(r'name="place"[^>]*value="Lake Tahoe"|value="Lake Tahoe"[^>]*name="place"', client.get("/start?place=Lake+Tahoe").text)
    assert re.search(r'name="place"[^>]*value="Honolulu"|value="Honolulu"[^>]*name="place"', client.get("/start?to=hi").text)


def test_where_to_on_the_showcase_keeps_its_four_sample_places(client):
    form = form_html(client.get("/start").text, "st-form")
    assert form.count('name="to"') == 4 and "Sample prices for Los Angeles" in form


def test_both_pages_offer_make_this_a_trip(real, client):
    start = form_html(client.get("/start").text, "st-form")
    assert re.search(r'<button\b[^>]*formaction="/trip/new"[^>]*>', start) and 'formmethod="post"' in start and "Make this a trip" in start
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


def test_where_to_makes_a_trip_from_its_own_fields(real, client):
    sign_in(client)
    r = client.post("/trip/new", data={"go": "1", "place": "Lisbon", "from": "SFO", **WHEN, "n": "0"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/cockpit" and open_trip()["title"] == "Trip to Lisbon"


def test_on_the_showcase_a_sample_city_chip_makes_its_trip(client):
    sign_in(client)
    r = client.post("/trip/new", data={"go": "1", "to": "sd", **WHEN, "n": "0"}, follow_redirects=False)
    assert r.status_code == 303 and open_trip()["title"] == "Trip to San Diego"


def test_a_bad_search_goes_back_to_where_to_with_what_is_wrong(real, client):
    sign_in(client)
    before = trip_count()
    r = client.post("/trip/new", data={"place": "Lisbon", "d": "2026-12-09", "r": "2026-12-04", "a": "2"}, follow_redirects=False)
    assert r.status_code == 303 and urlsplit(r.headers["location"]).path == "/start"
    again = client.get(r.headers["location"])
    assert again.status_code == 422 and "Lisbon" in again.text
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
