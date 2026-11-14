"""Autopilot contract (GOAL.md M1-M4, M6). Written before the work; never edited to pass. Test names start with the milestone."""
import re
from urllib.parse import parse_qs, urlparse

import pytest

from tests.test_signin import sign_in

PLACES = {"la": "Los Angeles", "sd": "San Diego", "hi": "Honolulu", "nyc": "New York"}
TRIP = "d=2027-03-05&r=2027-03-09&a=2"


def plan(client, to):
    return client.get(f"/plan?to={to}&{TRIP}")


def go_links(html):
    return re.findall(r'href="(/go/[^"]+)"', html.replace("&amp;", "&"))


# M1 four places --------------------------------------------------------------

@pytest.mark.parametrize("to", PLACES)
def test_m1_each_place_has_its_own_plan(client, to):
    r = plan(client, to)
    assert r.status_code == 200
    assert PLACES[to] in r.text


def test_m1_places_have_different_offers(client):
    pages = {to: plan(client, to).text for to in PLACES}
    prices = {to: tuple(re.findall(r"\$[\d,]+", html)[:12]) for to, html in pages.items()}
    assert len(set(prices.values())) == 4, "every place has its own prices"
    assert "Honolulu" not in pages["sd"] and "San Diego" not in pages["hi"]


def test_m1_search_offers_all_four_places(client):
    for to, name in PLACES.items():      # F-231: an old Where to? link for each sample city opens the matrix for it
        assert name in client.get(f"/start?to={to}").text, to


def test_m1_catalog_is_deterministic(client):
    assert plan(client, "hi").text.count("$") == plan(client, "hi").text.count("$")
    a = re.findall(r"\$[\d,]+", plan(client, "nyc").text)
    b = re.findall(r"\$[\d,]+", plan(client, "nyc").text)
    assert a == b


# M2 partner seam -------------------------------------------------------------

@pytest.mark.parametrize("to", PLACES)
def test_m2_every_lane_offers_a_partner_link(client, to):
    links = go_links(plan(client, to).text)
    assert len(links) >= 3, "flights, hotels and cars each link out"
    assert "Book on" in plan(client, to).text


def test_m2_go_without_keys_lands_in_the_sandbox(client, monkeypatch):
    monkeypatch.delenv("TRAVELPAYOUTS_MARKER", raising=False)
    link = go_links(plan(client, "sd").text)[0]
    r = client.get(link, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].startswith("/sandbox/")
    page = client.get(r.headers["location"])
    assert page.status_code == 200
    assert "<form" in page.text


def test_m2_go_with_a_marker_is_a_tracked_travelpayouts_link(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "123456")
    sign_in(client, "ari")
    link = go_links(plan(client, "hi").text)[0]
    r = client.get(link, follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = urlparse(r.headers["location"])
    assert loc.scheme == "https"
    q = parse_qs(loc.query)
    assert q.get("marker") == ["123456"] or "marker=123456" in r.headers["location"]
    assert "sub_id" in r.headers["location"]


def test_m2_unknown_offer_is_404(client):
    assert client.get(f"/go/nope-not-real?to=la&{TRIP}", follow_redirects=False).status_code == 404


# M3 the loop closes ----------------------------------------------------------

def _complete_sandbox(client, to="hi"):
    link = go_links(plan(client, to).text)[0]
    loc = client.get(link, follow_redirects=False).headers["location"]
    page = client.get(loc).text
    action = re.search(r'<form[^>]*action="([^"]+)"', page).group(1)
    fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
    return client.post(action, data=fields, follow_redirects=True)


def test_m3_partners_page_lists_clicks_and_bookings(client, monkeypatch):
    monkeypatch.delenv("TRAVELPAYOUTS_MARKER", raising=False)
    sign_in(client, "ari")
    done = _complete_sandbox(client, "hi")
    assert done.status_code == 200
    page = client.get("/partners")
    assert page.status_code == 200
    text = page.text.lower()
    assert "booked" in text and "sub" in text
    assert re.search(r"\$[\d,]+", page.text), "an estimated commission is shown"


def test_m3_partners_needs_sign_in(client):
    r = client.get("/partners", follow_redirects=False)
    assert r.status_code in (302, 303, 401, 403)


def test_m3_booking_lands_in_the_trip(client, monkeypatch):
    monkeypatch.delenv("TRAVELPAYOUTS_MARKER", raising=False)
    sign_in(client, "sam")
    done = _complete_sandbox(client, "nyc")
    assert "Booked elsewhere" in done.text or "booked elsewhere" in done.text.lower()


# M4 creators -----------------------------------------------------------------

def test_m4_creators_lists_four_creators(client):
    html = client.get("/creators").text
    handles = set(re.findall(r'href="/creators/([a-z0-9_-]+)"', html)) - {"draft", "finish", "done"}
    assert len(handles) >= 4


def test_m4_creator_profile_has_trips_and_plan_links(client):
    html = client.get("/creators").text
    handles = sorted(set(re.findall(r'href="/creators/([a-z0-9_-]+)"', html)) - {"draft", "finish", "done"})
    places_seen = set()
    for h in handles:
        r = client.get(f"/creators/{h}")
        assert r.status_code == 200
        assert re.search(r'href="https://(www\.)?(youtube\.com|instagram\.com)', r.text), "links back to the channel"
        found = re.findall(r'href="/plan\?[^"]*to=([a-z]+)', r.text.replace("&amp;", "&"))
        assert found, f"{h}: a 'Plan this trip' link"
        places_seen |= set(found)
    assert set(PLACES) <= places_seen, "one creator per place at least"


def test_m4_unknown_creator_404(client):
    assert client.get("/creators/nobody-here-xyz").status_code == 404


# M6 production stays honest ----------------------------------------------------

def test_m6_showcase_off_hides_sample_partner_pages(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.delenv("TRAVELPAYOUTS_MARKER", raising=False)
    assert client.get("/creators").status_code == 404
    assert client.get("/sandbox/anything").status_code == 404
    r = client.get(f"/plan?to=sd&{TRIP}")
    assert r.status_code == 200 and "Search flights to San Diego" in r.text and "sample prices" not in r.text.lower()      # F-198: production shows the honest lanes, never the samples
