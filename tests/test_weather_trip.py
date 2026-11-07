"""F-203 (3): a trip's days get MET Norway's forecast where it reaches them and NOAA's typical weather before that. A real trip never gets sample
weather; a day gone by, or a place GitAway has nothing real for, gets nothing. The founder's test: the Tahoe trip, Dec 19-26 2026 (normals now,
the forecast later)."""

from datetime import date, datetime, timedelta, timezone

import pytest

from gitaway import catalog, tripimport as ti, weather
from tests import weather_support as ws

NOV_7 = datetime(2026, 11, 7, 18, tzinfo=timezone.utc)      # 10 AM in Tahoe, six weeks before the trip
TYPICAL_MID, TYPICAL_LATE = "Typical mid December · not a forecast yet", "Typical late December · not a forecast yet"


def tahoe_trip(destination="South Lake Tahoe"):
    """The founder's trip as a family imports it: SFO to Reno, a cabin in South Lake Tahoe, 2 adults and kids 8 and 11."""
    plan = ti.Plan("Tahoe at Christmas", destination, date(2026, 12, 19), date(2026, 12, 26), "United", "",
                   (ti.Traveler("Abhi"), ti.Traveler("Priya"), ti.Traveler("Kid 1", age=11), ti.Traveler("Kid 2", age=8)),
                   (ti.Leg("United", "UA 1", "SFO", "RNO", datetime(2026, 12, 19, 12, 5), datetime(2026, 12, 19, 13, 20)),
                    ti.Leg("United", "UA 2", "RNO", "SFO", datetime(2026, 12, 26, 13, 0), datetime(2026, 12, 26, 14, 20))))
    return ti.trip_search(plan)


@pytest.fixture
def clock(monkeypatch):
    at = {"now": NOV_7}
    monkeypatch.setattr(catalog, "now_utc", lambda: at["now"])
    monkeypatch.setattr(catalog, "today", lambda: at["now"].astimezone(ws.PST).date())
    return at


@pytest.fixture
def met(monkeypatch, clock):
    monkeypatch.setenv("MET_NORWAY_TERMS_ACCEPTED", "1")
    fake = ws.Met()
    monkeypatch.setattr(weather, "TRANSPORT", fake)
    return fake


def test_the_founders_tahoe_trip_shows_typical_december_six_weeks_out_and_asks_nobody(met):
    tw = weather.trip_weather(tahoe_trip())
    assert tw.place == "South Lake Tahoe"
    assert [d.date for d in tw.days] == ws.tahoe_dates()
    assert [d.kind for d in tw.days] == [weather.NORMAL] * 8
    assert [d.label for d in tw.days] == [TYPICAL_MID] * 2 + [TYPICAL_LATE] * 6
    assert (tw.days[-1].high_f, tw.days[-1].low_f) == (42, 17)
    assert met.calls == []                                          # MET reaches about nine days: nothing to ask yet
    assert weather.notes(tw) == [(TYPICAL_LATE, ""), ("Snow or rain about 1 day in 3. From NOAA climate normals, 1991–2020. The forecast opens around Dec 10.", "")]


def test_once_the_forecast_reaches_the_trip_its_days_are_metss_forecast(met, clock):
    clock["now"] = ws.NOW                                           # Dec 17, 6:30 AM in Tahoe
    tw = weather.trip_weather(tahoe_trip())
    assert [d.kind for d in tw.days] == [weather.FORECAST] * 7 + [weather.NORMAL]     # Dec 26 has only its morning forecast yet
    assert [(d.high_f, d.low_f, d.word) for d in tw.days[:7]] == [ws.EXPECT[n][0:2] + (ws.EXPECT[n][3],) for n in range(19, 26)]
    assert tw.days[7].label == TYPICAL_LATE
    assert tw.updated == "6:10 AM"
    (url, _), = met.calls
    st = weather.station("USW00093230")                             # asked for the station's place, at its altitude
    assert url == f"{weather.API}?lat={st.lat:.4f}&lon={st.lon:.4f}&altitude={st.elev}"
    assert weather.notes(tw) == [(f"{weather.CREDIT} · updated 6:10 AM", weather.CREDIT_URL), (TYPICAL_LATE, ""),
                                 ("Snow or rain about 1 day in 3. From NOAA climate normals, 1991–2020.", "")]


def test_without_the_terms_accepted_the_trip_keeps_typical_weather_and_promises_no_forecast(monkeypatch, clock):
    clock["now"] = ws.NOW
    fake = ws.Met()
    monkeypatch.setattr(weather, "TRANSPORT", fake)
    tw = weather.trip_weather(tahoe_trip())
    assert [d.kind for d in tw.days] == [weather.NORMAL] * 8 and fake.calls == []
    assert all("opens" not in text for text, _ in weather.notes(tw))


def test_days_gone_by_show_nothing(met, clock):
    clock["now"] = datetime(2026, 12, 23, 18, tzinfo=timezone.utc)
    met.answers = [(OSError("down"), {}, b"")]
    tw = weather.trip_weather(tahoe_trip())
    assert tw.days[:4] == (None,) * 4
    assert [d.kind for d in tw.days[4:]] == [weather.NORMAL] * 4


def test_a_place_with_no_normals_shows_nothing_before_the_forecast_and_the_forecast_once_it_reaches(met, clock):
    lisbon = tahoe_trip("Lisbon")
    assert weather.trip_weather(lisbon).days == (None,) * 8           # no coordinates, no station: nothing real to show
    far = weather.trip_weather(lisbon, coords=(38.7223, -9.1393))
    assert far.days == (None,) * 8                                     # coordinates, but no normals abroad
    assert weather.notes(far) == [("The forecast opens around Dec 10.", "")]
    clock["now"] = ws.NOW
    tw = weather.trip_weather(lisbon, coords=(38.7223, -9.1393))
    assert [d.kind if d else None for d in tw.days] == [weather.FORECAST] * 7 + [None]
    assert tw.place == "Lisbon" and met.calls[0][0].startswith(f"{weather.API}?lat=38.7223&lon=-9.1393")


def test_the_catalogs_places_use_their_stations_and_a_disneyland_trip_anaheims(clock):
    la = catalog.parse_trip("", "la", "2026-12-19", "2026-12-23", "2", "4,7")
    assert weather.where(la).station.name == "Los Angeles"
    disney = catalog.parse_trip("", "la", "2026-12-19", "2026-12-23", "2", "4,7", focus="disney")
    assert weather.where(disney).station.name == "Anaheim"
    assert weather.where(catalog.parse_trip("", "hi", "2026-12-19", "2026-12-23", "2", "")).station.name == "Honolulu"


def test_a_real_trip_never_gets_sample_weather_even_on_the_showcase(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    assert weather.sample(catalog.SAMPLE_TRIP)
    plan = ti.Plan("LA with the kids", "Los Angeles", catalog.SAMPLE_TRIP.depart, catalog.SAMPLE_TRIP.return_, "Expedia", "", (ti.Traveler("Abhi"),))
    assert not weather.sample(ti.trip_search(plan))                    # a family's imported trip on the very same dates
    assert not weather.sample(catalog.parse_trip("", "la", "2026-12-19", "2026-12-23", "2", ""))
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert not weather.sample(catalog.SAMPLE_TRIP)                      # the live site has no sample trip
