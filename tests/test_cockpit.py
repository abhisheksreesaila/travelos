"""F-201: the trip cockpit's model on the founder's Tahoe trip (tests/tahoe.py): the week as a line of days with their times and weather, today's ticket
(Up next with the next leg turn by turn, worked out from gitaway.geo's line and the geo pack's named roads), the wallet's passes with masked references and
the paper map's data. "Now" is Monday Dec 21 2026, 9:12 AM at the lake."""

from datetime import date, datetime, timezone

import pytest

from gitaway import catalog, cockpit, geopack
from tests import tahoe
from tests.test_calendar import book
from tests.test_signin import person, sign_in


def at(monkeypatch, utc):
    monkeypatch.setattr(catalog, "now_utc", lambda: utc)
    monkeypatch.setattr(catalog, "today", lambda: utc.astimezone(catalog.TZ).date())


@pytest.fixture
def tahoe_trip(client, monkeypatch):
    """The Tahoe trip with its plans, its map cache and its geo pack, at the design's "now"."""
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    monkeypatch.setattr(geopack, "LONG_SIDE", 512)
    sign_in(client)
    me = tahoe.seed(client, monkeypatch)
    assert geopack.ensure(me) == "ready"
    at(monkeypatch, tahoe.NOW)
    return me


def _roads():
    return geopack.shapes(tahoe.overpass_answer(), geopack.region([tahoe.place(k) for k in ("cabin", "rno", "emerald")], tahoe.place("cabin")))["roads"]


# ---- small pieces ------------------------------------------------------------------------------------------------------

def test_a_reference_is_never_drawn_whole():
    assert cockpit.mask("KQ7821") == "••821"
    assert cockpit.mask(" VR 4821 936 ") == "••936"
    assert cockpit.mask("AB") == "•••"
    assert cockpit.mask("") == "" and cockpit.mask("none given") == ""


def test_the_party_reads_like_a_person_would_say_it():
    class T:
        adults, kid_ages = 2, (11, 8)
    assert cockpit.party_text(T) == "2 adults · kids 8 and 11"
    T.adults, T.kid_ages = 1, ()
    assert cockpit.party_text(T) == "1 adult"
    T.adults, T.kid_ages = 2, (5,)
    assert cockpit.party_text(T) == "2 adults · kid 5"


# ---- turn by turn from the line and the named roads ------------------------------------------------------------------------

def test_the_drive_to_taylor_creek_is_told_turn_by_turn():
    line, _ = tahoe._leg_line("d3", 0)
    steps = cockpit.turns(line, _roads())
    assert [(s.verb, s.road) for s in steps] == [("Head northwest", ""), ("Turn left on", "Lake Tahoe Boulevard (US 50)"), ("Turn right on", "Emerald Bay Road (CA 89)")]
    assert [s.icon for s in steps] == ["up", "turn-left", "turn-right"]
    assert steps[1].mi == pytest.approx(3.9, abs=0.3) and steps[2].mi == pytest.approx(3.4, abs=0.3)      # OSRM says 6.1 km and 5.1 km
    assert sum(s.mi for s in steps) == pytest.approx(cockpit.miles(cockpit.distance_km(line)), abs=0.15)


def test_a_road_the_pack_cannot_name_is_one_honest_step():
    line, _ = tahoe._leg_line("d3", 0)
    steps = cockpit.turns(line, [])
    assert len(steps) == 1 and steps[0].verb == "Head northwest" and steps[0].road == ""
    assert steps[0].mi == pytest.approx(8.2, abs=0.2)


def test_the_long_drive_from_reno_keeps_only_its_longest_steps_in_order():
    line, _ = tahoe._leg_line("alt", 0)
    steps = cockpit.turns(line, _roads())
    assert 2 <= len(steps) <= cockpit.MAX_STEPS
    roads = [s.road for s in steps]
    assert any("US 50" in r for r in roads) and any("580" in r or "395" in r for r in roads)
    assert cockpit.turns([], _roads()) == [] and cockpit.turns([(0, 0)], _roads()) == []


# ---- the whole cockpit ----------------------------------------------------------------------------------------------------

def test_the_heading_says_whose_trip_which_day_and_the_time(tahoe_trip):
    v = cockpit.view(tahoe_trip)
    assert v.title == "Tahoe at Christmas"
    assert v.eyebrow == "Ari’s family · day 3 of 8 · Mon Dec 21, 9:12 AM"
    assert v.dates == "Sat Dec 19 – Sat Dec 26" and v.party == "2 adults · kids 8 and 11"
    assert (v.phase, v.today, v.open_day, v.head_day, v.head_sub) == ("during", 2, 2, "Monday", "Dec 21 · 9:12 AM")


def test_every_day_is_a_stub_with_its_times_and_its_bookings(tahoe_trip):
    v = cockpit.view(tahoe_trip)
    assert [(d.dow, d.num) for d in v.days] == [("Sat", 19), ("Sun", 20), ("Mon", 21), ("Tue", 22), ("Wed", 23), ("Thu", 24), ("Fri", 25), ("Sat", 26)]
    assert [d.state for d in v.days] == ["done", "done", "today"] + ["later"] * 5
    first, monday, last = v.days[0], v.days[2], v.days[7]
    assert [(x.time, x.title, x.kind) for x in first.lines] == [("12:40 PM", "United UA 5521 · SFO → RNO", "flight"), ("2:20 PM", "Pick up Hertz car · RNO", "car"),
                                                                ("4:30 PM", "Check in · Cabin near Heavenly", "stay")]
    assert first.booked == ("United", "Hertz", "Stay") and first.name == "Fly in · check in"
    assert [(x.time, x.title, x.kind) for x in monday.lines] == [("10:00 AM", "Snowshoe at Taylor Creek", "outdoors"), ("12:30 PM", "Lunch in town", "food")]
    assert monday.booked == () and monday.name == "Snowshoe at Taylor Creek"
    assert last.name == "Fly home" and last.booked == ("Stay", "Hertz", "United")


def test_every_day_has_its_weather_through_the_one_interface(tahoe_trip, monkeypatch):
    from gitaway import dayweather
    v = cockpit.view(tahoe_trip)
    assert all(d.wx.sample and d.wx.source == "Sample weather" and d.wx.kind in dayweather.KINDS for d in v.days)
    snow = [dayweather.DayWx(31, 22, "Snow, 6–9 in", "snow", gust=20, ground=0.8, source="Forecast · MET Norway", sample=False)] * 8
    monkeypatch.setattr(dayweather, "source", lambda trip: snow)           # F-203 swaps this one function
    v = cockpit.view(tahoe_trip)
    assert v.days[2].wx.word == "Snow, 6–9 in" and v.days[2].wx.kind == "snow" and not v.days[2].wx.sample


def test_todays_ticket_is_up_next_with_when_to_leave_and_the_leg_turn_by_turn(tahoe_trip):
    t = cockpit.view(tahoe_trip).ticket
    assert t.kicker == "Today · up next · leave in 30 min"
    assert (t.title, t.starts, t.leave, t.drive) == ("Snowshoe at Taylor Creek", "10:00", "9:42", 18)
    assert t.mi == pytest.approx(8.2, abs=0.2)
    assert [s.road for s in t.steps] == ["", "Lake Tahoe Boulevard (US 50)", "Emerald Bay Road (CA 89)"]
    assert t.directions.startswith("https://www.google.com/maps/search/?api=1&query=Snowshoe+at+Taylor+Creek")


def test_with_no_pack_yet_the_leg_is_still_there_without_road_names(client, monkeypatch):
    sign_in(client)
    me = tahoe.seed(client, monkeypatch)
    at(monkeypatch, tahoe.NOW)
    v = cockpit.view(me)
    assert v.map["state"] == "building" and v.map["pack"] is None and v.map["box"]
    assert v.ticket.drive == 18 and [s.road for s in v.ticket.steps] == [""]


def test_while_something_is_on_the_ticket_says_so(tahoe_trip, monkeypatch):
    at(monkeypatch, datetime(2026, 12, 21, 18, 30, tzinfo=timezone.utc))     # 10:30 AM: snowshoeing
    t = cockpit.view(tahoe_trip).ticket
    assert t.kicker.startswith("Today · happening now · ends in 1 h 30 min") and t.title == "Snowshoe at Taylor Creek" and t.steps == ()


def test_the_wallet_holds_the_next_flight_the_stay_and_the_car_with_masked_references(tahoe_trip):
    from gitaway.pages import tripcanvas
    v = cockpit.view(tahoe_trip, curl=tripcanvas.curl)
    flight, stay, car = v.passes
    assert (flight.kind, flight.eyebrow, flight.title, flight.sub, flight.ref) == ("flight", "Flight home · Sat 26", "RNO → SFO · 1:30 PM", "United UA 5522", "••821")
    assert (stay.kind, stay.eyebrow, stay.title, stay.sub, stay.ref) == ("stay", "Stay · 5 nights left", "Cabin near Heavenly", "Check out Sat 26 · 10:00 AM", "••936")
    assert (car.kind, car.title, car.sub, car.ref) == ("car", "Mid-size SUV, AWD", "Hertz · return Sat 26 11:45 AM", "••215")
    assert all(p.partner == "Expedia" and p.manage == "" for p in v.passes)            # F-198 puts the partner of each booking and its page here
    assert flight.href.startswith("/trip/canvas?day=7&booked=b-back") and stay.href.startswith("/trip/canvas?day=0&booked=b-in")
    text = repr(v)
    for whole in ("KQ7821", "VR4821936", "H77418215"):
        assert whole not in text


def test_before_the_flight_in_the_wallet_shows_the_flight_in(tahoe_trip, monkeypatch):
    at(monkeypatch, datetime(2026, 12, 19, 16, 0, tzinfo=timezone.utc))      # Saturday 8 AM in San Francisco
    v = cockpit.view(tahoe_trip)
    assert v.passes[0].eyebrow == "Flight in · Sat 19" and v.passes[0].title == "SFO → RNO · 12:40 PM" and v.passes[0].sub == "United UA 5521 · 4 seats"


def test_the_map_has_each_days_stops_and_drive_and_never_the_home_airport(tahoe_trip):
    m = cockpit.view(tahoe_trip).map
    assert m["state"] == "ready" and m["pack"]["light"].endswith("-light.webp") and m["pack"]["shapes"].endswith(".json")
    days = m["days"]
    assert len(days) == 8
    assert [s["label"] for s in days[0]["stops"]] == ["Pick up car · RNO airport", "Stay"] and days[0]["min"] == 81
    assert [(s["label"], s["time"], s["kind"]) for s in days[2]["stops"]] == [("Stay", "", "stay"), ("Snowshoe at Taylor Creek", "10:00 AM", "outdoors")]
    assert days[2]["min"] == 18 and len(days[2]["route"]) > 10
    assert [s["label"] for s in days[4]["stops"]] == ["Stay", "Ski school at Heavenly", "Emerald Bay sunset"] and days[4]["min"] == 28
    assert days[6]["route"] is None and [s["label"] for s in days[6]["stops"]] == ["Stay"]
    assert all(len(d["route"] or []) <= cockpit.ROUTE_POINTS for d in days)
    assert not any("SFO" in s["label"] for d in days for s in d["stops"])


def test_before_the_trip_the_first_day_is_open_and_there_is_no_ticket(tahoe_trip, monkeypatch):
    at(monkeypatch, datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc))
    v = cockpit.view(tahoe_trip)
    assert v.phase == "before" and v.open_day == 0 and v.ticket is None and v.today is None
    assert v.eyebrow == "Ari’s family · starts in 42 days"
    assert v.passes[0].eyebrow == "Flight in · Sat 19"


def test_after_the_trip_the_last_day_is_open(tahoe_trip, monkeypatch):
    at(monkeypatch, datetime(2027, 1, 3, 18, 0, tzinfo=timezone.utc))
    v = cockpit.view(tahoe_trip)
    assert v.phase == "after" and v.open_day == 7 and v.eyebrow == "Ari’s family · back home"


def test_a_day_asked_for_is_the_open_one(tahoe_trip):
    assert cockpit.view(tahoe_trip, day="4").open_day == 4
    assert cockpit.view(tahoe_trip, day="99").open_day == 2


def test_the_sample_trip_works_too(client):
    book(client)
    v = cockpit.view(person("ari"))
    assert v.title and len(v.days) == 5 and v.phase == "before" and v.ticket is None
    assert [p.kind for p in v.passes] == ["flight", "stay", "car"] and all(p.ref == "" for p in v.passes)
    assert v.map["state"] in ("none", "building")
