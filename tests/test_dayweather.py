"""F-201 review: weather is never invented on a real trip. With the showcase off (production), a trip that is not the sample shows a plain sky with no number and no
words until F-203's forecasts and climate normals plug in (gitaway/dayweather.py is the one seam); with the showcase on, the sample weather is shown and says it is a sample."""

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


def test_off_the_showcase_a_real_trip_claims_no_weather(tahoe_trip, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    days = dayweather.days(_trip())
    assert len(days) == 8 and all(d.hi is None and d.lo is None and d.word == "" and d.kind == "plain" and not d.sample for d in days)
    html = tahoe_trip.get("/trip/cockpit").text
    assert skies(html) and not any("°" in s for s in skies(html))                 # no temperature anywhere
    assert "Sample weather" not in html and "Light showers" not in html and "Mostly sunny" not in html


def test_on_the_showcase_the_sample_weather_says_it_is_a_sample(tahoe_trip, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    days = dayweather.days(_trip())
    assert all(d.sample and d.hi is not None and d.word for d in days)
    html = tahoe_trip.get("/trip/cockpit").text
    assert any("°" in s for s in skies(html))
    assert 'class="ck-chip ck-chip-sample"' in html and "Sample weather" in text(html)        # said on the laptop too, not only on the phone's ticket


def test_the_sample_trip_keeps_its_sample_weather_off_the_showcase(client, monkeypatch):
    from tests.test_calendar import book
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    book(client)
    from gitaway import session as ses, tripcal as cal
    days = dayweather.days(cal.trip("", ses.booking(person("ari"))))
    assert all(d.sample and d.hi is not None for d in days)
