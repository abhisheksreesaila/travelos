"""F-203 (2): before MET's forecast opens, typical weather from NOAA's 1991-2020 U.S. Climate Normals (public domain), kept in gitaway/normals.json
and always labelled as typical, never as a forecast. A place GitAway has no normals for gets none."""

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

from gitaway import weather

ROOT = Path(__file__).resolve().parent.parent
TAHOE = (38.9399, -119.9772)     # the founder's cabin in South Lake Tahoe


def test_tahoe_in_late_december_is_noaas_typical_weather_labelled_as_such():
    st = weather.station_near(*TAHOE)
    assert (st.id, st.name) == ("USW00093230", "South Lake Tahoe")     # South Lake Tahoe airport, 5 km away
    d = weather.normal_day(st, date(2026, 12, 24))
    assert (d.kind, d.date, d.high_f, d.low_f) == (weather.NORMAL, date(2026, 12, 24), 42, 17)
    assert d.label == "Typical late December · not a forecast yet"
    assert (d.condition, d.word) == ("snow", "Snow or rain about 1 day in 3")     # the station counts wet days, not snow; its days average 30 F
    assert d.precip_in is None and d.wind_mph is None and d.hours == ()


def test_the_label_follows_the_third_of_the_month():
    st = weather.station("USW00093230")
    assert weather.normal_day(st, date(2026, 12, 19)).label == "Typical mid December · not a forecast yet"
    assert weather.normal_day(st, date(2026, 12, 10)).label == "Typical early December · not a forecast yet"
    assert weather.normal_day(st, date(2027, 1, 31)).label == "Typical late January · not a forecast yet"
    assert weather.normal_day(st, date(2028, 2, 29)).label == "Typical late February · not a forecast yet"


@pytest.mark.parametrize("sid, day, word, condition", [
    ("USC00048758", date(2026, 12, 24), "Snow about 1 day in 5", "snow"),      # Tahoe City measures snow: 22% of late-December days
    ("USW00093134", date(2026, 12, 24), "Rain about 1 day in 5", "sun"),       # Los Angeles: 19% wet
    ("USW00024233", date(2026, 12, 24), "Rain about 1 day in 2", "rain"),      # Seattle: 61%
    ("USW00093138", date(2026, 12, 24), "Usually dry", "sun"),                 # Palm Springs: 9%
    ("USW00003017", date(2026, 12, 24), "Snow or rain about 1 day in 7", "snow"),   # Denver: no snow normals, days average 30 F
])
def test_the_words_say_how_often_it_is_wet_and_whether_that_is_snow(sid, day, word, condition):
    d = weather.normal_day(weather.station(sid), day)
    assert (d.word, d.condition) == (word, condition)


def test_a_place_far_from_every_station_has_no_normals():
    assert weather.station_near(47.0, -100.0) is None      # the middle of North Dakota
    assert weather.station_near(48.8566, 2.3522) is None   # Paris
    assert weather.station_near(None, 2.0) is None


def test_names_find_a_station_by_whole_words_and_the_longest_name_wins():
    assert weather.station_named("Lake Tahoe, California").name == "South Lake Tahoe"
    assert weather.station_named("South Lake Tahoe, CA").name == "South Lake Tahoe"
    assert weather.station_named("North Lake Tahoe").name == "Tahoe City"
    assert weather.station_named("New Orleans, LA").name == "New Orleans"
    assert weather.station_named("Walt Disney World, Florida").name == "Orlando"
    assert weather.station_named("Washington, D.C.").name == "Washington, D.C."
    for nowhere in ("Paris", "Portland, Maine", "Charleston, West Virginia", "Mammoth Cave", "Losangeles", "", None, "LA"):
        assert weather.station_named(nowhere) is None, nowhere


def test_the_catalogs_four_places_have_their_stations():
    for key, name in (("la", "Los Angeles"), ("sd", "San Diego"), ("hi", "Honolulu"), ("nyc", "New York City")):
        assert weather.station(weather.CATALOG[key]).name == name


def test_the_table_is_whole_and_plausible():
    stations = weather.stations()
    assert len(stations) >= 50
    for st in stations:
        assert len(st.normals) == 36, st.id
        assert st.tz and weather.station_near(st.lat, st.lon) is not None
        for hi, lo, wet, snow in st.normals:
            assert -40 < lo <= hi < 125 and 0 <= wet <= 100 and (snow is None or 0 <= snow <= 100), st.id


def test_the_table_is_what_the_build_script_makes():
    """Editing the station list in scripts/build_normals.py without running `pixi run build-normals` leaves the app on the old table."""
    spec = importlib.util.spec_from_file_location("build_normals", ROOT / "scripts" / "build_normals.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    table = json.loads((ROOT / "gitaway" / "normals.json").read_text(encoding="utf-8"))["stations"]
    assert {sid: (name, tz, list(aliases)) for sid, name, tz, aliases in build.STATIONS} == {
        sid: (s["name"], s["tz"], s["aliases"]) for sid, s in table.items()}
    names = [a for _sid, _n, _tz, aliases in build.STATIONS for a in aliases]
    assert len(names) == len(set(names)), "a name may point at one station only"
