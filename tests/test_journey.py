"""F-300: My trip as a journey. What the page sends the road (gitaway/journey.py: the trip's events, its stay, the sun and the weather) and the sun's own times (gitaway/sun.py)."""

import json
import re
from datetime import date, datetime, timedelta, timezone

import pytest

from gitaway import catalog, journey, sun, weather
from tests import weather_support as ws
from tests.test_calendar import add, book
from tests.test_members import addr, browser, invite
from tests.test_signin import person, sign_in
from tests.test_weather_trip import tahoe_trip


def hm(m):
    return f"{m // 60}:{m % 60:02d}"


def road(html):
    return json.loads(re.search(r'<script type="application/json" id="pj-data">(.*?)</script>', html, re.S).group(1))


# ---- the sun ----------------------------------------------------------------------------------------------------------------

def test_south_lake_tahoe_in_december_rises_about_7_12_and_sets_about_4_40():
    """Almanac values for Tahoe on Dec 18 (Reno, 0.2 degrees east, is 7:09 and 4:39 on a flat horizon; the mountains are not counted)."""
    st = weather.station("USW00093230")
    rise, set_ = sun.times(st.lat, st.lon, date(2026, 12, 18), st.tz)
    assert abs(rise - (7 * 60 + 12)) <= 4 and abs(set_ - (16 * 60 + 40)) <= 4, (hm(rise), hm(set_))


def test_the_sun_is_local_time_and_summer_days_are_longer_than_winter_ones():
    st = weather.station("USW00093230")
    winter = sun.times(st.lat, st.lon, date(2026, 12, 18), st.tz)
    summer = sun.times(st.lat, st.lon, date(2026, 6, 21), st.tz)
    assert summer[1] - summer[0] > winter[1] - winter[0] + 5 * 60
    assert abs(summer[0] - (5 * 60 + 40)) <= 6 and abs(summer[1] - (20 * 60 + 25)) <= 6, (hm(summer[0]), hm(summer[1]))      # PDT in June


def test_polar_night_has_no_sunrise():
    assert sun.times(78.2, 15.6, date(2026, 12, 18), "Arctic/Longyearbyen") is None


def test_a_trip_day_carries_the_sun_of_its_places_station_and_a_place_with_no_station_carries_none():
    w = weather.where(tahoe_trip())
    got = journey.suns([date(2026, 12, 18), date(2026, 12, 19)], w)
    assert [abs(r - 432) <= 4 and abs(s - 1000) <= 4 for r, s in got] == [True, True]
    assert journey.suns([date(2026, 12, 18)], None) == [None]


# ---- the weather: only what weather.py says ---------------------------------------------------------------------------------

@pytest.fixture
def met(monkeypatch):
    monkeypatch.setenv("MET_NORWAY_TERMS_ACCEPTED", "1")
    monkeypatch.setattr(catalog, "now_utc", lambda: ws.NOW)
    monkeypatch.setattr(catalog, "today", lambda: ws.NOW.astimezone(ws.PST).date())
    monkeypatch.setattr(weather, "TRANSPORT", ws.Met())


def tahoe_week():
    t = tahoe_trip()
    return t, weather.where(t)


def test_forecast_hours_are_met_s_own_in_the_places_time_counted_from_the_first_day(met):
    t, w = tahoe_week()
    pts = journey.forecast_points(t, w)
    first = pts[0]
    assert first["t"] == 0 and first["h"] == 1 and (first["f"], first["c"], first["p"], first["s"]) == (26, 100.0, 0.5, "snow")      # -3.4 C at midnight
    at = {p["t"]: p for p in pts}
    heavy = at[10 * 60]                                                     # Dec 19, 10 AM: the story's heavy snow, 2.0 mm an hour
    assert heavy["s"] == "snow" and heavy["p"] == 2.0 and heavy["c"] == 100.0
    assert all(0 <= p["t"] < 8 * 1440 for p in pts)


def test_with_no_forecast_there_are_no_hours_and_nothing_is_made_up(met, monkeypatch):
    t, w = tahoe_week()
    monkeypatch.setattr(weather, "forecast", lambda st, **k: None)
    assert journey.forecast_points(t, w) == []
    assert journey.forecast_points(t, None) == []


def test_typical_weather_is_never_hours(monkeypatch):
    t, w = tahoe_week()            # six weeks before the trip (the clock is real now): MET is not asked and typical days have no hours
    monkeypatch.setattr(catalog, "today_in", lambda z=None: date(2026, 11, 7))
    assert journey.forecast_points(t, w) == []


# ---- the page's data ---------------------------------------------------------------------------------------------------------

@pytest.fixture
def booked(client):
    book(client)
    return client


def test_booked_things_are_locked_with_their_booking_and_plans_are_not(booked):
    add(booked, id="a1", day="1", start="10:00")
    d = road(booked.get("/trip/plan").text)
    by = {e["id"]: e for e in d["events"]}
    assert by["a1"]["locked"] is False and by["a1"]["start"] == 600 and by["a1"]["end"] == 660 and by["a1"]["day"] == 1 and by["a1"]["href"] == ""
    locked = [e for e in d["events"] if e["locked"]]
    assert {e["kind"] for e in locked} >= {"flight", "stay"} and all(e["href"].startswith("/trip/booking?block=") for e in locked)
    flights = [e for e in d["events"] if e["kind"] == "flight"]
    assert [(e["day"], e["start"], e["end"]) for e in flights] == [(0, 8 * 60 + 5, 9 * 60 + 32), (4, 14 * 60 + 10, 15 * 60 + 37)]      # out 8:05 to 9:32 on the first day, home 2:10 to 3:37 PM on the last


def test_the_stay_runs_from_check_in_to_check_out(booked):
    d = road(booked.get("/trip/plan").text)
    stay = d["stay"]
    ins = [e for e in d["events"] if e["kind"] == "stay"]
    assert stay["nights"] == 4 and stay["name"] == "The Tidewater"
    assert stay["from"] == min(e["day"] * 1440 + e["start"] for e in ins) and stay["to"] == max(e["day"] * 1440 + e["start"] for e in ins)
    assert stay["from"] // 1440 == 0 and stay["to"] // 1440 == 4


def test_the_road_starts_an_hour_before_the_first_thing_and_ends_an_hour_after_the_last(booked):
    d = road(booked.get("/trip/plan").text)
    first = min(e["day"] * 1440 + e["start"] for e in d["events"])
    last = max(e["day"] * 1440 + e["end"] for e in d["events"])
    lo, hi = d["range"]
    assert lo <= first - 60 + 59 and lo % 60 == 0 and hi >= last + 60 - 59 and hi % 60 == 0 and hi <= 5 * 1440


def test_the_days_say_their_weather_in_weather_s_words_and_the_sample_trip_says_sample(booked):
    d = road(booked.get("/trip/plan").text)
    assert [x["label"] for x in d["days"]] == ["Fri 16", "Sat 17", "Sun 18", "Mon 19", "Tue 20"]
    assert d["days"][0]["wx"]["sample"] is True and d["days"][0]["wx"]["hi"] == 75 and d["days"][0]["wx"]["lo"] == 63
    assert d["points"] == [] and d["caption"] == "Sample weather"                # the sample has no hours: nothing is made up for them
    rise, set_ = d["days"][0]["sun"]
    assert 6 * 60 + 40 <= rise <= 7 * 60 and 18 * 60 <= set_ <= 18 * 60 + 20      # Los Angeles, Oct 16, PDT


def test_the_places_own_colour_comes_with_the_data(booked):
    assert road(booked.get("/trip/plan").text)["pc"] == "#7D4CF0"            # Los Angeles


def test_nothing_is_now_before_the_trip_and_now_is_the_places_time_during_it(booked, monkeypatch):
    assert road(booked.get("/trip/plan").text)["now"] is None
    during = datetime(2026, 10, 18, 22, 20, tzinfo=timezone.utc)             # 3:20 PM on Sun Oct 18 in Los Angeles (PDT)
    monkeypatch.setattr(catalog, "now_utc", lambda: during)
    monkeypatch.setattr(catalog, "today", lambda: during.date())
    assert road(booked.get("/trip/plan").text)["now"] == 2 * 1440 + 15 * 60 + 20


@pytest.fixture
def crew(client):
    book(client)
    vi = addr("vi")
    invite(client, vi, "viewer")
    viewer = browser(client)
    sign_in(viewer, vi)
    return client, viewer


def test_a_viewer_sees_the_road_but_it_does_not_let_them_write(crew):
    owner, viewer = crew
    add(owner, id="a1")
    assert road(owner.get("/trip/plan").text)["edit"] is True
    d = road(viewer.get("/trip/plan").text)
    assert d["edit"] is False and "a1" in {e["id"] for e in d["events"]}
    assert viewer.post("/trip/plan/write", data={"op": "edit", "act": "a1", "start": "700", "end": "760", "day": "1"}, follow_redirects=False).status_code == 403


def test_the_data_alone_is_a_json_answer_for_a_refresh(booked):
    r = booked.get("/trip/plan/journey")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json") and r.headers["cache-control"] == "no-store"
    assert r.json() == road(booked.get("/trip/plan").text)
