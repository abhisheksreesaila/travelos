"""F-057: a trip has its own time zone: from its arrival airport (or chosen on import), used by /trip's today, up next and countdowns,
stored in the family database, and the server's past-date check keeps its one "today"."""

import json
import re
from datetime import date, datetime, timezone
from html import unescape
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text as sql

from gitaway import catalog, familydb, rides, session as ses, tripcal as cal, tripday as td, tripimport, zones
from tests.test_signin import person, sign_in
from tests.test_trip_import import TEMPLATE, imported, no_car, visible

PARIS = no_car().replace("to: LAX", "to: CDG").replace("from: LAX", "from: CDG").replace("destination: Los Angeles", "destination: Paris")
# 06:00 UTC on Oct 20 is 08:00 in Paris (CEST) but 23:00 on Oct 19 in Los Angeles
INSTANT = datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc)
ZONE_LINE = "  start: 2026-10-16 "


def words(html):
    return " ".join(visible(html).split())


@pytest.fixture
def at_utc(monkeypatch):
    """Pin the instant; catalog.today is the real one again (the suite pins it to a September day)."""
    def pin(moment):
        monkeypatch.setattr(catalog, "now_utc", lambda: moment)
        monkeypatch.setattr(catalog, "today", lambda: moment.astimezone(catalog.TZ).date())
    return pin


# ---- the zone table ------------------------------------------------------------------------------------------------------

def test_an_airport_gives_its_zone_then_the_destination_state_then_los_angeles():
    assert zones.resolve("CDG", "Paris") == ("Europe/Paris", "")
    assert zones.resolve("jfk", "x") == ("America/New_York", "")
    assert zones.resolve("", "Austin, TX") == ("America/Chicago", "")
    assert zones.resolve("ZZZ", "Honolulu, Hawaii") == ("Pacific/Honolulu", "")
    zone, note = zones.resolve("ZZZ", "Somewhere")
    assert zone == "America/Los_Angeles" and "ZZZ" in note and "timezone:" in note
    assert zones.valid("Europe/Paris") == "Europe/Paris" and zones.valid("Mars/Olympus") is None and zones.valid("../etc") is None and zones.valid(5) is None


# ---- the template ----------------------------------------------------------------------------------------------------------

def test_the_zone_comes_from_the_arrival_airport_or_the_template():
    assert tripimport.parse(PARIS).plan.timezone == "Europe/Paris"
    assert tripimport.parse(TEMPLATE).plan.timezone == "America/Los_Angeles"
    chosen = tripimport.parse(TEMPLATE.replace(ZONE_LINE, "  timezone: America/New_York\n" + ZONE_LINE, 1))
    assert chosen.plan.timezone == "America/New_York" and chosen.warnings == ()
    assert tripimport.from_doc(tripimport.to_doc(chosen.plan)).timezone == "America/New_York"


def test_an_unknown_airport_falls_back_to_los_angeles_with_a_note():
    parsed = tripimport.parse(no_car().replace("to: LAX", "to: ZZZ").replace("from: LAX", "from: ZZZ"))
    assert parsed.plan.timezone == "America/Los_Angeles"
    assert any("ZZZ" in w and "Los Angeles time" in w for w in parsed.warnings)


def test_a_bad_zone_is_a_friendly_import_error_with_its_line(client):
    bad = TEMPLATE.replace(ZONE_LINE, "  timezone: Mars/Olympus\n" + ZONE_LINE, 1)
    with pytest.raises(tripimport.ImportProblem) as e:
        tripimport.parse(bad)
    assert len(e.value.errors) == 1 and "Mars/Olympus" in e.value.errors[0] and "Europe/Paris" in e.value.errors[0] and e.value.errors[0].startswith("Line ")
    sign_in(client)
    r = client.post("/trips/import", data={"text": bad})
    assert r.status_code == 422 and "Mars/Olympus" in unescape(r.text)
    with pytest.raises(tripimport.ImportProblem):
        tripimport.parse(TEMPLATE.replace(ZONE_LINE, "  timezone: 5\n" + ZONE_LINE, 1))


def test_the_template_doc_shows_the_optional_line_and_stays_valid():
    assert re.search(r"^\s*#\s*timezone: Europe/Paris", TEMPLATE, re.M)
    assert tripimport.parse(TEMPLATE).warnings == ()


# ---- stored with the trip -----------------------------------------------------------------------------------------------------

def test_an_imported_trip_stores_its_zone_and_an_unknown_trip_reads_as_los_angeles(client):
    imported(client, PARIS)
    with familydb.using(person()) as db:
        trip = db.conn.execute(sql("SELECT id, timezone FROM trips")).one()
        assert trip.timezone == "Europe/Paris" and familydb.trip_zone(db, trip.id) == "Europe/Paris"
        assert familydb.trip_zone(db, "nope") == "America/Los_Angeles"


def test_the_migration_runs_on_an_existing_family_file():
    s = person("ari")
    with familydb.using(s) as db:  # a file made before F-057: no zone column, and the migration not yet recorded
        db.conn.execute(sql("INSERT INTO trips (id, title, source, params, depart, return_on, created_by, created_at) VALUES ('old1', 'Old', 'demo', '', '2026-10-16', '2026-10-20', 'u', 'x')"))
        db.conn.execute(sql("ALTER TABLE trips DROP COLUMN timezone"))
        db.conn.execute(sql("DELETE FROM _migrations WHERE version = 1"))
        db.conn.commit()
    familydb.forget_schema_cache()
    with familydb.using(s) as db:
        assert familydb.trip_zone(db, "old1") == "America/Los_Angeles"
        assert db.conn.execute(sql("SELECT title FROM trips WHERE id = 'old1'")).scalar() == "Old"
        assert 1 in db.conn.execute(sql("SELECT version FROM _migrations")).scalars().all()
        db.conn.execute(sql("DELETE FROM trips WHERE id = 'old1'"))
        db.conn.commit()


# ---- /trip --------------------------------------------------------------------------------------------------------------------

def test_a_paris_trip_shows_parisian_today_and_up_next(client, at_utc):
    imported(client, PARIS)
    at_utc(INSTANT)
    html = client.get("/trip").text
    t = words(html)
    assert "DAY 5 OF 5" in t and "Tuesday" in html.split("<h1")[1].split("</h1>")[0]
    assert "UP NEXT · IN 3 H" in t and "The Example Hotel Santa Monica" in t


def test_the_same_instant_is_a_day_earlier_for_an_la_trip_and_the_la_countdown_is_unchanged(client, at_utc):
    imported(client)
    at_utc(INSTANT)
    assert "DAY 4 OF 5" in words(client.get("/trip").text)  # 11 PM on Oct 19 in Los Angeles
    at_utc(datetime(2026, 10, 20, 21, 0, tzinfo=timezone.utc))  # 2:00 PM in Los Angeles, 10 minutes before the flight home
    t = words(client.get("/trip").text)
    assert "DAY 5 OF 5" in t and "UP NEXT · IN 10 MIN" in t


def test_the_minute_and_the_day_follow_the_zone(at_utc):
    at_utc(INSTANT)
    assert td.now_minute("Europe/Paris") == 8 * 60 and td.now_minute() == 23 * 60 and td.now_minute("America/Los_Angeles") == 23 * 60
    assert catalog.today_in("Europe/Paris") == date(2026, 10, 20) and catalog.today_in() == date(2026, 10, 19) == catalog.today()


def test_the_past_date_check_keeps_one_server_today(at_utc):
    at_utc(INSTANT)
    assert catalog.is_past(date(2026, 10, 19), date(2026, 10, 21)) is False   # Oct 19 is still "today" for the server, though it is Oct 20 in Paris
    assert catalog.is_past(date(2026, 10, 18), date(2026, 10, 21)) is True


def test_a_ride_is_picked_up_at_the_airports_local_time(client):
    imported(client, no_car())
    b = ses.booking(person())
    flight = tripimport.flight_offer(tripimport.from_doc(b["imported"]), b["flight"])
    plan = rides.leg_plan("arrive", flight, None, cal.trip("", b))
    assert plan.pickup_time.tzinfo.key == "America/Los_Angeles"
    other = plan.pickup_time.astimezone(ZoneInfo("America/New_York"))
    rec = rides.RideRecord("r1", "q", "k", "arrive", "x", "x", "f", 100, 1, other, 30, 2, "LAX", "", rides.Guest("A", "B", "1"))
    back = rides.from_dict(json.loads(json.dumps(rides.to_dict(rec))))  # a ride in another zone remembers it
    assert back.pickup_time == other and back.pickup_time.tzinfo.key == "America/New_York"


def test_a_plan_built_without_a_zone_gets_the_arrival_airports():
    parsed = tripimport.parse(PARIS).plan
    bare = tripimport.Plan(parsed.title, parsed.destination, parsed.start, parsed.end, parsed.booked_on, parsed.itinerary, parsed.travelers, parsed.legs, parsed.hotels)
    assert bare.timezone == "Europe/Paris" and tripimport.zone_for(parsed.legs, "x") == ("Europe/Paris", "")
    assert tripimport.Plan("T", "Austin, TX", parsed.start, parsed.end, "", "", parsed.travelers).timezone == "America/Chicago"


# ---- the day you fly (the clock is the departure airport's until you land) ---------------------------------------------------------

def leaving(frm, to, depart, arrive, tail=""):
    t = no_car()
    t = t.replace("from: SFO\n    to: LAX\n    depart: 2026-10-16 08:05\n    arrive: 2026-10-16 09:32", f"from: {frm}\n    to: {to}\n    depart: {depart}\n    arrive: {arrive}")
    t = t.replace("from: LAX\n    to: SFO\n    depart: 2026-10-20 14:10\n    arrive: 2026-10-20 15:37", f"from: {to}\n    to: {frm}\n    depart: 2026-10-20 14:10\n    arrive: 2026-10-20 16:40")
    return t.replace("check_in: 2026-10-16 15:00", "check_in: 2026-10-17 15:00").replace("destination: Los Angeles", "destination: Paris")


def trip_text(client, moment, at_utc):
    at_utc(moment)
    return words(client.get("/trip").text)


def test_on_the_morning_you_fly_to_paris_the_flight_is_hours_away_in_la_time(client, at_utc):
    imported(client, leaving("LAX", "CDG", "2026-10-16 15:00", "2026-10-17 11:00"))
    t = trip_text(client, datetime(2026, 10, 16, 16, 0, tzinfo=timezone.utc), at_utc)  # 9:00 AM in Los Angeles, 6 PM in Paris
    assert "UP NEXT · IN 6 H" in t and "HAPPENING NOW" not in t and "DAY 1 OF" in t


def test_the_evening_before_you_fly_it_is_still_before_the_trip(client, at_utc):
    imported(client, leaving("LAX", "CDG", "2026-10-16 15:00", "2026-10-17 11:00"))
    t = trip_text(client, datetime(2026, 10, 16, 1, 0, tzinfo=timezone.utc), at_utc)  # 6 PM on Oct 15 in Los Angeles, 3 AM on Oct 16 in Paris
    assert "TRIP STARTS TOMORROW" in t and "DAY 1 OF" not in t


def test_after_you_land_the_clock_is_the_destinations(client, at_utc):
    imported(client, leaving("LAX", "CDG", "2026-10-16 15:00", "2026-10-17 11:00"))
    t = trip_text(client, datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc), at_utc)  # 12:00 in Paris, an hour after landing
    assert "DAY 2 OF" in t and "UP NEXT · IN 3 H" in t  # hotel check in at 3 PM Paris time


def test_a_flight_across_the_date_line_stays_on_the_departure_day_until_it_lands(client, at_utc):
    imported(client, leaving("SFO", "NRT", "2026-10-16 11:00", "2026-10-17 15:00"))
    t = trip_text(client, datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc), at_utc)  # 10:00 AM Oct 16 in San Francisco, already Oct 17 in Tokyo
    assert "DAY 1 OF" in t and "UP NEXT · IN 1 H" in t
    t = trip_text(client, datetime(2026, 10, 17, 7, 0, tzinfo=timezone.utc), at_utc)  # 4 PM on Oct 17 in Tokyo, landed
    assert "DAY 2 OF" in t
