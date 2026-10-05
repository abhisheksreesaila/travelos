"""F-068: the Map tab through the HTTP seam, with the map services faked: the day's stops numbered in order with their coordinates, the places that could
not be found listed under the map, the sheet's facts (address, time, drive, Directions, Uber, call), and Today's "Leave by" from the cached drive."""
import json
import re
import sys
from datetime import date
from urllib.parse import unquote

import pytest

from gitaway import catalog, geo, tripday as td
from tests.test_signin import sign_in
from tests.test_trip_import import TEMPLATE, imported, visible
from tests.test_trip_phone import plan

PLACES = {"example hotel": ("34.0100", "-118.4900"), "griffith": ("34.1184", "-118.3004")}


class Maps:
    """The faked services: a place is found when its query has one of PLACES' words in it; `Mystery` is never found."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, timeout=0):
        self.calls.append(url)
        if "nominatim" in url:
            q = unquote(url.split("&q=")[1].split("&")[0]).replace("+", " ").lower()
            for word, (lat, lon) in PLACES.items():
                if word in q:
                    return [{"lat": lat, "lon": lon, "display_name": f"{word.title()}, Los Angeles County, California"}]
            return []
        return {"code": "Ok", "routes": [{"duration": 1500.0, "geometry": {"type": "LineString", "coordinates": [[-118.49, 34.01], [-118.30, 34.1184]]}}]}


@pytest.fixture
def maps(monkeypatch):
    m = Maps()
    monkeypatch.setattr(geo, "fetch", m)
    return m


def data_of(html):
    return json.loads(re.search(r'<script type="application/json" id="mp-data">(.*?)</script>', html, re.S).group(1))


def trip_with_plans(client):
    imported(client)
    plan(client, id="a1", day="0", start="17:00", end="19:30", title="Griffith Observatory")
    plan(client, id="a2", day="0", start="20:00", end="21:00", title="Mystery Cafe")


def test_signed_out_goes_through_sign_in_and_no_trip_goes_to_start(client):
    r = client.get("/trip/map", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin")
    sign_in(client)
    assert client.get("/trip/map", follow_redirects=False).headers["location"] == "/start"


def test_the_days_stops_are_numbered_in_order_and_placed_from_the_geocoder(client, maps):
    trip_with_plans(client)
    html = client.get("/trip/map?day=0").text
    stops = data_of(html)["stops"]
    assert [s["n"] for s in stops] == list(range(1, len(stops) + 1))
    titles = [s["title"] for s in stops]
    assert titles.index("Griffith Observatory") > 0  # after the flight and the check in
    hotel = next(s for s in stops if s["title"].startswith("Check in"))
    assert (hotel["lat"], hotel["lon"]) == (34.01, -118.49)
    flight = stops[0]
    assert 37 < flight["lat"] < 38  # SFO comes from the airport table
    assert not any("airport" in u.lower() or "SFO" in u for u in maps.calls)  # an airport is never looked up
    assert 'id="mp-map"' in html and "/assets/vendor/leaflet/leaflet.js" in html


def test_a_place_the_geocoder_cannot_find_is_listed_under_the_map_with_a_way_to_fix_it(client, maps):
    trip_with_plans(client)
    html = client.get("/trip/map?day=0").text
    assert "Mystery Cafe" not in [s["title"] for s in data_of(html)["stops"]]  # no pin without coordinates
    text = " ".join(visible(html).split())
    assert "Couldn’t find this place on the map." in text
    assert "Mystery Cafe" in text and "Fix it in the calendar" in text
    assert 'href="/calendar?view=whole#d0"' in html  # a plan is fixed in the calendar, not in Edit trip


def test_a_booking_that_cannot_be_found_links_to_edit_trip(client, maps, monkeypatch):
    trip_with_plans(client)
    monkeypatch.setattr(sys.modules[__name__], "PLACES", {"griffith": PLACES["griffith"]})  # the hotel is unknown to the geocoder
    html = client.get("/trip/map?day=0").text
    assert 'href="/trips/build/edit?trip=' in html and "Edit trip" in visible(html)


def test_the_uber_link_is_the_real_one_in_production(client, maps, monkeypatch):
    trip_with_plans(client)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")  # the live site: no simulated Uber, no /rides
    r = client.get("/trip/map?day=0")
    assert r.status_code == 200
    griffith = next(s for s in data_of(r.text)["stops"] if s["title"] == "Griffith Observatory")
    assert griffith["uber"].startswith("https://m.uber.com/ul/?action=setPickup") and "/rides" not in griffith["uber"]


def test_the_sheet_facts_for_each_stop(client, maps):
    trip_with_plans(client)
    stops = data_of(client.get("/trip/map?day=0").text)["stops"]
    griffith = next(s for s in stops if s["title"] == "Griffith Observatory")
    assert griffith["when"] == "5:00 – 7:30 PM"
    assert griffith["addr"].startswith("Griffith")
    assert "Griffith+Observatory" in griffith["dir"] or "Griffith%20Observatory" in griffith["dir"]
    assert griffith["uber"].startswith("https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff[formatted_address]=Griffith%20Observatory")
    assert griffith["tel"] == ""
    hotel = next(s for s in stops if s["title"].startswith("Check in"))
    assert hotel["tel"] == "+1 310 555 0100"
    assert hotel["addr"].startswith("The Example Hotel Santa Monica, 123 Ocean Ave")


def test_drive_times_between_stops_come_from_the_router_and_are_cached(client, maps):
    trip_with_plans(client)
    stops = data_of(client.get("/trip/map?day=0").text)["stops"]
    griffith = next(s for s in stops if s["title"] == "Griffith Observatory")
    assert griffith["drive"] == 25 and griffith["frm"].startswith("Check in")
    assert next(s for s in stops if s["n"] == 1)["drive"] is None  # nothing before the first stop
    calls = len(maps.calls)
    client.get("/trip/map?day=0")
    assert len(maps.calls) == calls  # a second visit asks nobody


def test_the_route_line_joins_the_stops_when_the_router_answers(client, maps):
    trip_with_plans(client)
    route = data_of(client.get("/trip/map?day=0").text)["route"]
    assert route["type"] == "LineString" and len(route["coordinates"]) >= 2


def test_with_the_services_down_the_page_still_works_and_says_it_is_looking(client):
    trip_with_plans(client)  # no `maps` fixture: every call fails
    html = client.get("/trip/map?day=0").text
    assert client.get("/trip/map?day=0").status_code == 200
    data = data_of(html)
    assert data["route"] is None and data["pending"] > 0
    assert "Finding places on the map" in visible(html)
    assert all(s["title"] != "Griffith Observatory" for s in data["stops"])


def test_the_day_picker_changes_the_day(client, maps):
    trip_with_plans(client)
    html = client.get("/trip/map?day=0").text
    assert 'href="/trip/map?day=1"' in html
    empty = client.get("/trip/map?day=2").text
    assert "Nothing with a place today" in visible(empty) or "nothing with a place today" in visible(empty).lower()


def test_today_leave_by_uses_the_cached_drive_and_never_calls_out(client, maps, monkeypatch):
    trip_with_plans(client)
    monkeypatch.setattr(catalog, "today", lambda *_: date(2026, 10, 16))
    monkeypatch.setattr(td, "now_minute", lambda *_: 16 * 60 + 31)
    before = client.get("/trip?tab=today").text
    assert "tp-leave" not in before  # nothing cached yet: no guess
    client.get("/trip/map?day=0")  # opening the Map fills the cache
    calls = len(maps.calls)
    after = client.get("/trip?tab=today").text
    assert len(maps.calls) == calls
    assert "Leave by 4:35 PM 25 min drive" in " ".join(visible(after).split())

def test_the_day_views_now_card_has_leave_by_from_the_cache_too(client, maps, monkeypatch):    trip_with_plans(client)                                                      # F-092: Today is the day view, and it keeps Leave by    monkeypatch.setattr(catalog, "today", lambda *_: date(2026, 10, 16))    monkeypatch.setattr(td, "now_minute", lambda *_: 16 * 60 + 31)    client.get("/trip/map?day=0")    for url in ("/trip/canvas?day=0", "/trip/canvas?day=0&frag=1"):        assert "Leave by 4:35 PM 25 min drive" in " ".join(visible(client.get(url).text).split()), url

def test_a_slow_geocoder_cannot_hold_the_map_page_for_more_than_a_couple_of_seconds(client, monkeypatch):
    import time

    def slow(url, timeout=0):
        time.sleep(timeout)  # never answers: the call ends only when its timeout does
        raise TimeoutError("slow")
    trip_with_plans(client)
    monkeypatch.setattr(geo, "fetch", slow)
    monkeypatch.setattr(geo.NOMINATIM_GATE, "gap", 1.0)
    monkeypatch.setattr(geo.OSRM_GATE, "gap", 0.25)
    start = time.monotonic()
    r = client.get("/trip/map?day=0")
    assert r.status_code == 200 and time.monotonic() - start < 3.5
