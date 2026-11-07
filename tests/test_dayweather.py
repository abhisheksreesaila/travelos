"""F-201 review, with F-203 merged: weather is never invented on a real trip. gitaway/dayweather.py is the one seam: a real trip shows MET's forecast or the
place's typical weather (NOAA normals, labelled "not a forecast yet", with the lines weather.notes asks for) and a plain sky for a day gone by, on the showcase
and off it; only the showcase's own sample trip shows sample weather, and says so."""

import re

import pytest

from gitaway import dayweather, geopack
from tests import tahoe
from tests.test_signin import person, sign_in
from tests.test_trip_canvas import text


@pytest.fixture
def tahoe_trip(client, monkeypatch):
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    monkeypatch.setattr(geopack, "LONG_SIDE", 512)
    sign_in(client)
    tahoe.seed(client, monkeypatch)
    return client


def _trip():
    from gitaway import session as ses, tripcal as cal
    return cal.trip("", ses.booking(person("ari")))


def skies(html):
    """Every sky on the page, as its markup up to its first closing div."""
    return re.findall(r'<div[^>]*class="ck-sky[^"]*"[^>]*>.*?</div>', html, re.S)


@pytest.mark.parametrize("show", ["0", "1"])
def test_a_real_trip_shows_real_or_typical_weather_and_never_a_sample(tahoe_trip, monkeypatch, show):
    monkeypatch.setenv("GITAWAY_SHOWCASE", show)
    days = dayweather.days(_trip())
    assert len(days) == 8 and not any(d.sample for d in days)
    assert all(d.hi is not None and d.source.endswith("not a forecast yet") for d in days)      # the days to come: typical weather, labelled (MET is off in tests)
    html = tahoe_trip.get("/trip/cockpit").text
    assert "Sample weather" not in html and "Light showers" not in html and "Mostly sunny" not in html
    assert "not a forecast yet" in text(html) and "NOAA climate normals" in text(html)       # weather.notes, under the map on both widths


def test_on_the_showcase_the_sample_trip_shows_sample_weather_and_says_so(client, monkeypatch):
    from tests.test_calendar import book
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    book(client)
    from gitaway import session as ses, tripcal as cal
    days = dayweather.days(cal.trip("", ses.booking(person("ari"))))
    assert all(d.sample and d.hi is not None and d.word for d in days)
    html = client.get("/trip/cockpit").text
    assert any("°" in s for s in skies(html))
    assert 'class="ck-chip ck-chip-sample"' in html and "Sample weather" in text(html)        # said on the laptop too, not only on the phone's ticket


def test_off_the_showcase_even_the_sample_trip_shows_no_sample_weather(client, monkeypatch):
    from tests.test_calendar import book
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    book(client)
    from gitaway import session as ses, tripcal as cal
    days = dayweather.days(cal.trip("", ses.booking(person("ari"))))
    assert not any(d.sample for d in days)                                        # F-203 (D-256): sample weather never reaches the live site
