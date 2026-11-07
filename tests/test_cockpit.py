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


# ---- small pieces ------------------------------------------------------------------------------------------------------

def test_a_reference_is_never_drawn_whole():
    assert cockpit.mask("KQ7821") == "••21"           # six characters or fewer: two shown
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


# ---- turn by turn: the router's own steps (F-201 review: no more guessing from the line) -----------------------------------------------

def _step(k, d="", n="", r="", m=0, b=None):
    s = {"k": k, "d": d, "n": n, "r": r, "m": m}
    if b is not None:
        s["b"] = b
    return s


def test_the_router_gives_the_steps_and_they_are_kept_with_the_leg(client, monkeypatch):
    """geo asks OSRM for its steps in the same call (steps=true) and keeps them with the cached leg, in a form any router can fill (F-204 may change it)."""
    from gitaway import familydb, geo
    asked = []

    def osrm(url, timeout=0):
        asked.append(url)
        return {"code": "Ok", "routes": [{"duration": 1080, "geometry": {"type": "LineString", "coordinates": [[-119.948, 38.936], [-120.054, 38.936]]},
                                          "legs": [{"steps": [{"maneuver": {"type": "depart", "bearing_after": 352}, "name": "Ski Run Boulevard", "ref": "", "distance": 1609.0},
                                                              {"maneuver": {"type": "turn", "modifier": "left"}, "name": "Lake Tahoe Boulevard", "ref": "US 50", "distance": 6100.4},
                                                              {"maneuver": {"type": "end of road", "modifier": "right"}, "name": "", "ref": "", "distance": 120.0},
                                                              {"maneuver": {"type": "arrive"}, "name": "", "ref": "", "distance": 0}]}]}]}
    monkeypatch.setattr(geo, "fetch", osrm)
    sign_in(client)
    me = person("ari")
    a, b = (38.936, -119.948), (38.936, -120.054)
    with familydb.using(me) as db:
        assert geo.drive_minutes(a, b, db) == 18
        assert "steps=true" in asked[0]
        assert geo.steps(a, b, db) == [_step("depart", n="Ski Run Boulevard", m=1609, b=352), _step("turn", "left", "Lake Tahoe Boulevard", "US 50", 6100),
                                       _step("turn", "right", m=120), _step("arrive")]


def test_mixed_named_and_unnamed_roads_are_told_as_the_router_gives_them():
    lines = cockpit.step_lines([_step("depart", m=300, b=4), _step("turn", "left", "Main Street", m=1609), _step("turn", "right", m=800),
                                _step("continue", "straight", "Lake Tahoe Boulevard", "US 50", 3219), _step("arrive")])
    assert [(s.verb, s.road) for s in lines] == [("Head north", ""), ("Turn left on", "Main Street"), ("Turn right", ""), ("Continue on", "Lake Tahoe Boulevard (US 50)")]
    assert [s.mi for s in lines] == [0.2, 1.0, 0.5, 2.0] and [s.icon for s in lines] == ["up", "turn-left", "turn-right", "up"]


def test_a_road_that_only_changes_its_name_continues_one_step():
    lines = cockpit.step_lines([_step("merge", "slight left", r="I 580; US 395", m=12600), _step("continue", "straight", r="I 580; US 395", m=23000),
                                _step("continue", "straight", r="I 580;US 395", m=10600), _step("turn", "slight right", "Pioneer Trail", m=1500)])
    assert [(s.verb, s.road, s.mi) for s in lines] == [("Merge onto", "I 580 / US 395", 28.7), ("Bear right onto", "Pioneer Trail", 0.9)]


def test_the_drive_to_taylor_creek_is_the_routers_own_steps(tahoe_trip):
    t = cockpit.view(tahoe_trip).ticket
    assert [(s.verb, s.road, s.mi) for s in t.steps] == [("Head northwest on", "Ski Run Boulevard", 1.0), ("Turn left on", "Lake Tahoe Boulevard (US 50)", 3.8),
                                                         ("Turn right on", "Emerald Bay Road (CA 89)", 3.2)]


def test_the_fixtures_reno_line_is_told_step_by_step(tahoe_trip, monkeypatch):
    from datetime import datetime, timezone
    at(monkeypatch, datetime(2026, 12, 19, 23, 0, tzinfo=timezone.utc))       # Saturday 3:00 PM: the car is picked up, the cabin is next
    t = cockpit.view(tahoe_trip).ticket
    assert t.title == "Check in · Cabin near Heavenly"
    assert [(s.verb, s.road) for s in t.steps] == [("Head west", ""), ("Merge onto", "I 580 / US 395"), ("Continue on", "I 580 / US 50 / US 395"), ("Continue on", "US 50"),
                                                   ("Turn left on", "Pioneer Trail")]


# ---- the whole cockpit ----------------------------------------------------------------------------------------------------

def test_the_heading_says_whose_trip_which_day_and_the_time(tahoe_trip):
    v = cockpit.view(tahoe_trip)
    assert v.title == "Tahoe at Christmas"
    assert v.eyebrow == "Ari Rivera's family · day 3 of 8 · Mon Dec 21, 9:12 AM"      # the family's own name (members.family_label), not the viewer's
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
    assert all(not d.wx.sample and d.wx.kind in dayweather.KINDS for d in v.days)          # F-203: a real trip's weather is real or typical, never sample
    assert v.days[0].wx == dayweather.NO_CLAIM and v.days[4].wx.source.endswith("not a forecast yet")      # a day gone by claims nothing
    snow = [dayweather.DayWx(31, 22, "Snow, 6–9 in", "snow", gust=20, ground=0.8, source="Forecast · MET Norway", sample=False)] * 8
    monkeypatch.setattr(dayweather, "source", lambda trip: snow)           # F-203 swaps this one function
    v = cockpit.view(tahoe_trip)
    assert v.days[2].wx.word == "Snow, 6–9 in" and v.days[2].wx.kind == "snow" and not v.days[2].wx.sample


def test_todays_ticket_is_up_next_with_when_to_leave_and_the_leg_turn_by_turn(tahoe_trip):
    t = cockpit.view(tahoe_trip).ticket
    assert t.kicker == "Today · up next · leave in 30 min"
    assert (t.title, t.starts, t.leave, t.drive) == ("Snowshoe at Taylor Creek", "10:00", "9:42", 18)
    assert t.mi == pytest.approx(8.2, abs=0.2)
    assert [s.road for s in t.steps] == ["Ski Run Boulevard", "Lake Tahoe Boulevard (US 50)", "Emerald Bay Road (CA 89)"]
    assert t.directions.startswith("https://www.google.com/maps/search/?api=1&query=Snowshoe+at+Taylor+Creek")


def test_with_no_pack_yet_the_leg_and_its_steps_are_still_there(client, monkeypatch):
    sign_in(client)
    me = tahoe.seed(client, monkeypatch)
    at(monkeypatch, tahoe.NOW)
    v = cockpit.view(me)
    assert v.map["state"] == "building" and v.map["pack"] is None and v.map["box"]
    assert v.ticket.drive == 18 and [s.road for s in v.ticket.steps][-1] == "Emerald Bay Road (CA 89)"      # the steps are the router's: they need no pack


def test_while_something_is_on_the_ticket_says_so(tahoe_trip, monkeypatch):
    at(monkeypatch, datetime(2026, 12, 21, 18, 30, tzinfo=timezone.utc))     # 10:30 AM: snowshoeing
    t = cockpit.view(tahoe_trip).ticket
    assert t.kicker.startswith("Today · happening now · ends in 1 h 30 min") and t.title == "Snowshoe at Taylor Creek" and t.steps == ()


def test_the_wallet_holds_the_next_flight_the_stay_and_the_car_with_masked_references(tahoe_trip):
    from gitaway.pages import tripcanvas
    v = cockpit.view(tahoe_trip, curl=tripcanvas.curl)
    flight, stay, car = v.passes
    assert (flight.kind, flight.eyebrow, flight.title, flight.sub, flight.ref) == ("flight", "Flight home · Sat 26", "RNO → SFO · 1:30 PM", "United UA 5522", "••21")
    assert (stay.kind, stay.eyebrow, stay.title, stay.sub, stay.ref) == ("stay", "Stay · 5 nights left", "Cabin near Heavenly", "Check out Sat 26 · 10:00 AM", "••936")
    assert (car.kind, car.title, car.sub, car.ref) == ("car", "Mid-size SUV, AWD", "Hertz · return Sat 26 11:45 AM", "••215")
    assert all(p.partner == "" and p.manage == "" for p in v.passes)            # the trip's one "booked on" is not each booking's partner; F-198 fills these per booking
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
    assert v.eyebrow == "Ari Rivera's family · starts in 42 days"
    assert v.passes[0].eyebrow == "Flight in · Sat 19"


def test_after_the_trip_the_last_day_is_open(tahoe_trip, monkeypatch):
    at(monkeypatch, datetime(2027, 1, 3, 18, 0, tzinfo=timezone.utc))
    v = cockpit.view(tahoe_trip)
    assert v.phase == "after" and v.open_day == 7 and v.eyebrow == "Ari Rivera's family · back home"


def test_a_day_asked_for_is_the_open_one(tahoe_trip):
    assert cockpit.view(tahoe_trip, day="4").open_day == 4
    assert cockpit.view(tahoe_trip, day="99").open_day == 2


def test_the_sample_trip_works_too(client):
    book(client)
    v = cockpit.view(person("ari"))
    assert v.title and len(v.days) == 5 and v.phase == "before" and v.ticket is None
    assert [p.kind for p in v.passes] == ["flight", "stay", "car"] and all(p.ref == "" for p in v.passes)
    assert v.map["state"] in ("none", "building")


# ---- review fixes (F-201 review) ----------------------------------------------------------------------------------------

def test_a_short_reference_shows_two_characters_a_long_one_three():
    assert cockpit.mask("KQ7821") == "••21" and cockpit.mask("H77418215") == "••215" and cockpit.mask("ABC") == "•••"


@pytest.mark.parametrize("booked_on", ["elsewhere", "GitAway", "Elsewhere", ""])
def test_a_booking_with_no_known_partner_is_just_booked(booked_on):
    assert cockpit.partner_name(booked_on) == ""
    assert cockpit.partner_name("Vrbo") == "Vrbo"


@pytest.mark.parametrize("url,ok", [("https://www.expedia.com/trips/123", True), ("https://expedia.com/x", True), ("http://www.expedia.com/x", False),
                                    ("https://evil.com/expedia.com", False), ("https://expedia.com.evil.com/x", False), ("https://evil.com\\.expedia.com/x", False),
                                    ("javascript:alert(1)", False), ("https://www.vrbo.com/x", False)])
def test_change_or_cancel_goes_only_to_the_partners_own_https_site(url, ok):
    assert (cockpit.safe_manage(url, "Expedia") == url) is ok
