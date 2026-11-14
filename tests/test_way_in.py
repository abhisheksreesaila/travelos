"""F-231: one way in after sign-in (D-461 on). `/` opens the family's trip (its cockpit) or, with none, the trip matrix; "Plan a trip" is the matrix; the old Where to?
form (/start) is gone and only redirects, keeping the place, dates and party the matrix reads; nothing links to a page that was deleted."""
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.test_calendar import book
from tests.test_liteapi import KEY
from tests.test_signin import sign_in

ROOT = Path(__file__).resolve().parent.parent


def where(r):
    return r.headers["location"]


def hrefs(html):
    return [h.replace("&amp;", "&") for h in re.findall(r'href="([^"]*)"', html)]


def header_of(html):
    return re.search(r"<header.*?</header>", html, re.S).group(0)


@pytest.fixture
def no_matrix(monkeypatch):
    """Production without a LiteAPI key: the matrix does not exist (showcase.LITEAPI_PAGES)."""
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.delenv("LITEAPI_KEY", raising=False)


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)


# ---- "/" decides -------------------------------------------------------------------------------------------------------

def test_a_family_with_no_trip_lands_on_the_matrix(client):
    sign_in(client, "ari")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and where(r) == "/plan/matrix"


def test_a_family_with_a_trip_lands_on_its_cockpit(client):
    assert book(client).status_code == 303
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and where(r) == "/trip/cockpit"
    assert client.get("/").status_code == 200


def test_signing_in_with_no_next_comes_to_the_front_door(client):
    r = client.post("/signin", data={"email": "ari.rivera@gmail.com"}, follow_redirects=False)
    assert where(r) == "/"
    assert where(client.get("/", follow_redirects=False)) == "/plan/matrix"


def test_without_the_matrix_a_family_with_no_trip_lands_on_the_import(client, no_matrix):
    sign_in(client, "ari")
    assert where(client.get("/", follow_redirects=False)) == "/trips/import"


# ---- Plan a trip, Start a trip -----------------------------------------------------------------------------------------

def test_signed_out_plan_a_trip_and_start_a_trip_sign_in_then_come_back_to_the_front_door(client):
    cover = client.get("/").text
    nav = re.search(r'<nav[^>]*class="cv-nav".*?</nav>', cover, re.S).group(0)
    assert hrefs(nav)[-1] == "/signin"
    assert 'href="/signin"' in re.search(r'<div class="cv-ctas">.*?</div>', cover, re.S).group(0)
    assert hrefs(header_of(client.get("/community").text)).count("/signin") >= 1       # Plan a trip (and Sign in)


def test_signed_in_plan_a_trip_opens_the_matrix(client):
    sign_in(client, "ari")
    for path in ("/community", "/for-creators", "/family"):
        assert "/plan/matrix" in hrefs(header_of(client.get(path).text)), path


def test_where_the_matrix_does_not_exist_plan_a_trip_opens_the_import(client, no_matrix):
    sign_in(client, "ari")
    assert "/trips/import" in hrefs(header_of(client.get("/community").text))
    assert client.get("/plan/matrix", follow_redirects=False).status_code == 404


def test_with_a_key_off_the_showcase_the_matrix_is_the_way_in(client, real):
    sign_in(client, "ari")
    assert where(client.get("/", follow_redirects=False)) == "/plan/matrix"


# ---- /start ------------------------------------------------------------------------------------------------------------

def words(r):
    return {k: v[0] for k, v in parse_qs(urlsplit(where(r)).query).items()}


def test_start_is_a_redirect_to_the_matrix(client):
    r = client.get("/start", follow_redirects=False)
    assert r.status_code == 303 and where(r) == "/plan/matrix"


def test_an_old_where_to_link_keeps_its_place_dates_and_party(client):
    r = client.get("/start?go=1&place=Lake+Tahoe&from=sfo&d=2027-03-05&r=2027-03-09&a=2&n=2&k1=7&k2=10&via=x", follow_redirects=False)
    assert urlsplit(where(r)).path == "/plan/matrix"
    assert words(r) == {"to": "Lake Tahoe", "home": "SFO", "d": "2027-03-05", "r": "2027-03-09", "a": "2", "k": "7,10"}


def test_an_old_sample_city_link_names_its_city(client):
    r = client.get("/start?to=hi&d=2027-03-05&r=2027-03-09&a=3&k=4", follow_redirects=False)
    assert words(r) == {"to": "Honolulu", "d": "2027-03-05", "r": "2027-03-09", "a": "3", "k": "4"}


def test_the_matrix_reads_what_the_old_link_carried(client):
    html = client.get("/start?place=San+Diego&home=SFO&d=2027-03-05&r=2027-03-09&a=2&k=7,10").text
    assert "San Diego" in html and "Mar 5" in html


def test_without_the_matrix_an_old_link_opens_the_import(client, no_matrix):
    assert where(client.get("/start?place=Lisbon", follow_redirects=False)) == "/trips/import"


# ---- the matrix and the cockpit link the two ways ---------------------------------------------------------------------

def test_the_matrix_offers_a_trip_already_booked_to_the_import_when_signed_in(client):
    assert 'id="mx-import"' not in client.get("/plan/matrix").text
    sign_in(client, "ari")
    html = client.get("/plan/matrix").text
    assert re.search(r'<a[^>]*href="/trips/import"[^>]*id="mx-import"[^>]*>Already booked\? Bring your trip in</a>', html)


def test_the_cockpit_has_plan_another_trip_opening_the_matrix(client):
    book(client)
    html = client.get("/trip/cockpit").text
    assert re.search(r'<a[^>]*href="/plan/matrix"[^>]*id="ck-plan-another"[^>]*>.*?Plan another trip</a>', html, re.S)


def test_saving_a_square_still_makes_the_family_a_trip_and_lands_it_on_the_cockpit(client):
    sign_in(client, "ari")
    assert where(client.get("/", follow_redirects=False)) == "/plan/matrix"
    r = client.post("/trip/new", data={"place": "Lisbon", "d": "2027-03-05", "r": "2027-03-09", "a": "2", "k": "", "home": "SFO"}, follow_redirects=False)
    assert where(r) == "/trip/cockpit"
    assert where(client.get("/", follow_redirects=False)) == "/trip/cockpit"


def test_a_search_that_does_not_hold_up_goes_back_to_the_booking_lanes(client):
    sign_in(client, "ari")
    r = client.post("/trip/new", data={"place": "Lisbon", "d": "2027-03-09", "r": "2027-03-05", "a": "2"}, follow_redirects=False)
    assert urlsplit(where(r)).path == "/plan" and words(r)["place"] == "Lisbon"


# ---- nothing links to what was deleted --------------------------------------------------------------------------------

DELETED = ("/start", "/assets/css/start.css", "/assets/js/start.js", "/assets/css/landing.css", "/assets/js/landing.js")
PAGES = ("/", "/signin", "/community", "/for-creators", "/privacy", "/terms", "/plan", "/plan/matrix", "/trips/import", "/trips/build", "/family", "/trip/cockpit", "/trip/book",
         "/trip/ask", "/trip/details", "/trip", "/forks", "/offline", "/plan-for-me", "/plan-for-me/start", "/trip/canvas", "/trip/family", "/trip/today", "/trip/publish")


def swept(client):
    found = {}
    for path in PAGES:
        r = client.get(path, follow_redirects=True)
        for h in hrefs(r.text) + re.findall(r'src="([^"]*)"', r.text):
            found.setdefault(path, []).append(h)
    return found


def links_to_deleted(found):
    return {path: [h for h in hs if urlsplit(h).path in DELETED] for path, hs in found.items() if any(urlsplit(h).path in DELETED for h in hs)}


@pytest.mark.parametrize("state", ["signed out", "no trip", "with a trip"])
def test_no_main_page_links_to_a_deleted_page(client, state):
    if state == "no trip":
        sign_in(client, "ari")
    if state == "with a trip":
        book(client)
    assert links_to_deleted(swept(client)) == {}


@pytest.mark.parametrize("mode", ["0", "1"])
def test_no_main_page_links_to_a_deleted_page_in_either_showcase_mode(client, monkeypatch, mode):
    monkeypatch.setenv("GITAWAY_SHOWCASE", mode)
    monkeypatch.delenv("LITEAPI_KEY", raising=False)
    sign_in(client, "ari")
    assert links_to_deleted(swept(client)) == {}


def test_no_source_file_names_a_deleted_page():
    """The code and the scripts never write the old addresses (the redirect in gitaway/pages/tripmatrix.py is the one place that answers them)."""
    old = re.compile(r"""(?<!\+ )["'(=](/start)(?![\w/-])|(?:start|landing)\.(?:css|js)\b""")
    hits = []
    for folder, ext in (("gitaway", "*.py"), ("assets/js", "*.js"), ("assets/css", "*.css"), ("scripts", "*.py")):
        for f in sorted((ROOT / folder).rglob(ext)):
            if f.name == "tripmatrix.py":
                continue
            hits += [f"{f.relative_to(ROOT)}:{n}" for n, line in enumerate(f.read_text().splitlines(), 1) if old.search(line)]
    assert hits == []


# ---- what the deleted pages' tests still said, said of the new way in --------------------------------------------------

def test_the_sign_in_page_comes_back_to_the_front_door_and_a_given_next_still_wins(client):
    page = client.get("/signin").text
    assert 'name="next" value="/"' in page or 'value="/" name="next"' in page
    assert where(client.post("/signin", data={"email": "ari.rivera@example.com", "next": "/plan?f=f2"}, follow_redirects=False)) == "/plan?f=f2"
    assert where(client.get("/signin", follow_redirects=False)) == "/"                    # already signed in


def test_an_old_disneyland_link_with_an_airport_keeps_both(client):
    r = client.get("/start?go=1&to=la&focus=disney&from=jfk&d=2027-03-16&r=2027-03-20&a=2&n=0", follow_redirects=False)
    assert words(r) == {"to": "Disneyland", "home": "JFK", "d": "2027-03-16", "r": "2027-03-20", "a": "2"}


def test_a_stale_pay_link_cannot_book_the_past_and_opens_the_matrix_with_what_is_wrong(client, monkeypatch):
    from datetime import date

    from gitaway import catalog
    from tests.test_signin import stored_booking
    sign_in(client)
    monkeypatch.setattr(catalog, "today", lambda: date(2026, 11, 1))
    r = client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-17", "r": "2026-10-20", "a": "2"}, follow_redirects=False)
    assert urlsplit(where(r)).path == "/plan/matrix" and words(r)["d"] == "2026-10-17"
    assert stored_booking() is None
    assert "today or later" in client.get(where(r)).text


def test_the_pages_stylesheets_still_load_tokens_then_base_then_page(client):
    h = client.get("/trips/sun-tacos-and-tide-pools").text
    idx = [h.index(f"/assets/css/{n}") for n in ("tokens.css", "base.css", "itinerary.css")]
    assert idx == sorted(idx)


# ---- "has a trip" and "has a booking" are the same family (review of F-231) -------------------------------------------------

def test_a_family_whose_trip_a_matrix_save_made_lands_on_its_cockpit_with_a_booking(client, monkeypatch):
    from gitaway import session as ses
    from tests.test_signin import person
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    sign_in(client, "ari")
    assert where(client.get("/", follow_redirects=False)) == "/plan/matrix"
    form = {"to": "San Diego", "home": "SFO", "d": "2026-12-12", "r": "2026-12-16", "a": "2", "k": "7,10", "x": "2", "lane": "losangeles+sandiego", "w": "2026-12-12"}
    assert client.post("/plan/matrix/save", data=form, follow_redirects=False).status_code == 303
    assert ses.trips(person("ari")) and ses.booking(person("ari"))      # a trip without a booking cannot be made this way
    assert where(client.get("/", follow_redirects=False)) == "/trip/cockpit" and client.get("/trip/cockpit").status_code == 200


def test_a_trip_made_from_a_search_has_a_booking_so_the_cockpit_opens(client):
    from gitaway import session as ses
    from tests.test_signin import person
    sign_in(client, "ari")
    client.post("/trip/new", data={"place": "Lisbon", "d": "2027-03-05", "r": "2027-03-09", "a": "2"}, follow_redirects=False)
    assert ses.booking(person("ari")) and client.get("/trip/cockpit").status_code == 200
