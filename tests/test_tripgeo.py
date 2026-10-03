"""F-068: the map cache is filled for the whole trip in the background (after a save, and at most once an hour when Today draws), so "Leave by" works
without ever opening the Map. The map services are faked; background threads are joined before the page is read."""
import threading
from datetime import date

import pytest

from gitaway import catalog, geo, tripday as td, tripgeo
from tests.test_map import Maps, trip_with_plans
from tests.test_trip_import import TEMPLATE, imported, visible
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
    assert "Leave by 4:35 PM · 25 min drive" in text(client.get("/trip").text)


def test_the_first_stop_of_a_day_leaves_from_where_you_slept(client, maps, monkeypatch):
    imported(client)
    plan(client, id="a1", day="1", start="09:00", end="10:00", title="Griffith Observatory")
    client.get("/trip")
    settle()
    at(monkeypatch, date(2026, 10, 17), 8 * 60)
    assert "Leave by 8:35 AM · 25 min drive" in text(client.get("/trip?day=1").text)


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
