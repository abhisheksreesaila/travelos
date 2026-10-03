"""F-068: the map cache is filled for the whole trip in the background (after a save, and at most once an hour when Today draws), so "Leave by" works
without ever opening the Map. The map services are faked; background threads are joined before the page is read."""
import threading
from datetime import date

import pytest

from gitaway import catalog, geo, tripday as td, tripgeo
from tests.test_map import Maps, trip_with_plans
from tests.test_trip_import import TEMPLATE, no_car, imported, visible
from tests.test_trip_phone import plan


def settle():
    for t in list(threading.enumerate()):
        if t.name == "geo-warm":
            t.join(10)


@pytest.fixture
def maps(monkeypatch):
    m = Maps()
    monkeypatch.setattr(geo, "fetch", m)
    monkeypatch.setattr(geo, "ASYNC", True)
    monkeypatch.setattr(tripgeo, "_KICKED", {})
    yield m
    settle()


def at(monkeypatch, day, minute):
    monkeypatch.setattr(catalog, "today", lambda *_: day)
    monkeypatch.setattr(td, "now_minute", lambda *_: minute)


def text(html):
    return " ".join(visible(html).split())


def test_saving_a_trip_fills_the_cache_in_the_background(client, maps):
    imported(client)
    settle()
    assert any("nominatim" in u and "Example" in u for u in maps.calls)  # the hotel was looked up with nobody on the Map
    assert any("router.project-osrm" in u for u in maps.calls)


def test_leave_by_shows_on_today_without_opening_the_map(client, maps, monkeypatch):
    imported(client)
    plan(client, id="a1", day="0", start="17:00", end="19:30", title="Griffith Observatory")
    client.get("/trip")  # the first draw of Today starts a fill (the plan was added after the save)
    settle()
    at(monkeypatch, date(2026, 10, 16), 16 * 60 + 31)
    assert "Leave by 4:35 PM 25 min drive" in text(client.get("/trip").text)


def test_the_first_stop_of_a_day_leaves_from_where_you_slept(client, maps, monkeypatch):
    imported(client)
    plan(client, id="a1", day="1", start="09:00", end="10:00", title="Griffith Observatory")
    client.get("/trip")
    settle()
    at(monkeypatch, date(2026, 10, 17), 8 * 60)
    assert "Leave by 8:35 AM 25 min drive" in text(client.get("/trip?day=1").text)


def test_today_starts_a_fill_at_most_once_an_hour_per_trip(client, maps, monkeypatch):
    imported(client)
    settle()
    plan(client, id="a1", day="0", start="17:00", end="19:30", title="Griffith Observatory")
    started = []
    monkeypatch.setattr(geo, "warm_async", lambda s, p: started.append(p))
    monkeypatch.setattr(tripgeo, "_KICKED", {})
    client.get("/trip")
    client.get("/trip")
    assert len(started) == 1
    now = tripgeo.time.monotonic()
    monkeypatch.setattr(tripgeo.time, "monotonic", lambda: now + 3601)
    client.get("/trip")
    assert len(started) == 2


def test_old_throttle_entries_are_pruned(client, maps, monkeypatch):
    imported(client)
    settle()
    tripgeo._KICKED[("old", "trip", "x")] = tripgeo.time.monotonic() - 2 * tripgeo.HOUR
    plan(client, id="a1", day="0", start="17:00", end="19:30", title="Griffith Observatory")
    client.get("/trip")
    assert ("old", "trip", "x") not in tripgeo._KICKED


def test_a_travel_day_does_not_leave_from_the_stay(client, maps, monkeypatch):
    imported(client)
    plan(client, id="a1", day="4", start="09:00", end="10:00", title="Griffith Observatory")  # the day of the flight home
    client.get("/trip")
    settle()
    at(monkeypatch, date(2026, 10, 20), 8 * 60)
    assert "Leave by" not in text(client.get("/trip?day=4").text)


def test_today_still_draws_when_the_map_fill_breaks(client, maps, monkeypatch):
    imported(client)
    monkeypatch.setattr(tripgeo, "day_places", lambda s: 1 / 0)
    assert client.get("/trip").status_code == 200


def test_right_after_a_flight_there_is_no_leave_by_and_no_cross_country_drive_is_asked(client, maps, monkeypatch):
    imported(client)  # the arrival day: a flight SFO to LAX at 8:05, then the car pickup at 10:00
    settle()
    assert not any("router.project-osrm" in u and "-122.37" in u for u in maps.calls)  # SFO's longitude: nobody asks how long SFO to LAX takes by car
    client.get("/trip")
    settle()
    at(monkeypatch, date(2026, 10, 16), 9 * 60)
    html = text(client.get("/trip").text)
    assert "Pick up Hertz car" in html and "Leave by" not in html


# ---- F-075: Leave by for a departure flight --------------------------------------------------------------------------------

def _osrm_pairs(maps):
    """The (from longitude, to longitude) of every route asked."""
    out = []
    for u in maps.calls:
        if "router.project-osrm" in u:
            a, b = u.split("/driving/")[1].split("?")[0].split(";")[:2]
            out.append((a.split(",")[0], b.split(",")[0]))
    return out


def test_a_departure_flight_gets_leave_by_with_a_two_hour_margin_and_no_airport_to_airport_drive(client, maps, monkeypatch):
    later = no_car().replace("depart: 2026-10-20 14:10", "depart: 2026-10-20 18:10").replace("arrive: 2026-10-20 15:37", "arrive: 2026-10-20 19:37")
    imported(client, later)  # the flight home leaves LAX at 6:10 PM on the last day; the stop before it is the hotel
    client.get("/trip")
    settle()
    sfo, lax = "-122.37", "-118.40"
    pairs = _osrm_pairs(maps)
    assert not any(a.startswith(sfo) or (a.startswith(lax) and b.startswith(sfo)) for a, b in pairs)  # never asked from an airport, never airport to airport
    assert any(b.startswith(lax) and not a.startswith(lax) for a, b in pairs)  # the hotel (or the car desk) to the departure airport was asked
    at(monkeypatch, date(2026, 10, 20), 12 * 60 + 31)  # after check out; the flight is up next
    html = text(client.get("/trip?day=4").text)
    assert "Leave by 3:45 PM 25 min drive" in html and "be there 2 h early" in html


def test_an_international_departure_asks_for_three_hours(client, maps):
    from gitaway import zones
    assert zones.international("LAX", "LHR") and zones.international("SFO", "YVR")
    assert not zones.international("LAX", "SFO") and not zones.international("LAX", "ZZZ")  # an airport not in the table is treated as domestic
    assert td.flight_margin("LAX", "SFO") == 120 and td.flight_margin("LAX", "LHR") == 180


def test_an_arrival_flight_never_gets_leave_by_or_a_drive_to_it(client, maps, monkeypatch):
    imported(client)
    client.get("/trip")
    settle()
    at(monkeypatch, date(2026, 10, 16), 6 * 60)
    assert "Leave by" not in text(client.get("/trip").text)


def test_after_landing_the_car_pickup_is_up_next_with_no_drive_line(client, maps, monkeypatch):
    imported(client)
    client.get("/trip")
    settle()
    at(monkeypatch, date(2026, 10, 16), 9 * 60 + 40)  # 9:40, after landing
    html = text(client.get("/trip").text)
    assert "Pick up Hertz car" in html and "min drive" not in html
