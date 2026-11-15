"""F-201 review, with F-203 merged: weather is never invented on a real trip. gitaway/dayweather.py is the one seam: a real trip shows MET's forecast or the
place's typical weather (NOAA normals, labelled "not a forecast yet") and a plain sky for a day gone by, on the showcase and off it; only the showcase's own sample trip
shows sample weather. (The cockpit that drew it retired in F-254; the planning page reads the same seam, tests/test_planv2.py.)"""

import pytest

from gitaway import dayweather
from tests import tahoe
from tests.test_signin import person, sign_in


@pytest.fixture
def tahoe_trip(client, monkeypatch):
    sign_in(client)
    tahoe.seed(client, monkeypatch)
    return client


def _trip():
    from gitaway import session as ses, tripcal as cal
    return cal.trip("", ses.booking(person("ari")))


@pytest.mark.parametrize("show", ["0", "1"])
def test_a_real_trip_shows_real_or_typical_weather_and_never_a_sample(tahoe_trip, monkeypatch, show):
    monkeypatch.setenv("GITAWAY_SHOWCASE", show)
    days = dayweather.days(_trip())
    assert len(days) == 8 and not any(d.sample for d in days)
    assert all(d.hi is not None and d.source.endswith("not a forecast yet") for d in days)      # the days to come: typical weather, labelled (MET is off in tests)


def test_on_the_showcase_the_sample_trip_shows_sample_weather(client, monkeypatch):
    from tests.test_calendar import book
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    book(client)
    days = dayweather.days(_trip())
    assert all(d.sample and d.hi is not None and d.word for d in days)


def test_off_the_showcase_even_the_sample_trip_shows_no_sample_weather(client, monkeypatch):
    from tests.test_calendar import book
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    book(client)
    days = dayweather.days(_trip())
    assert not any(d.sample for d in days)                                        # F-203 (D-256): sample weather never reaches the live site
