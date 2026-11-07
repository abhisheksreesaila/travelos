"""F-203 (4): the places real trips show weather. The /plan weather pane, the /forks calendar's day heads and a shared trip show MET's forecast
(credited) or typical weather (labelled) for a real trip, and never invented weather; the showcase's sample trip keeps its sample weather.
/privacy names MET Norway."""

import re
from datetime import timedelta
from html import unescape

import pytest

from gitaway import catalog, share, weather
from tests import weather_support as ws
from tests.test_signin import person
from tests.test_trip_import import TEMPLATE, imported, no_car

TYPICAL = "Typical late December · not a forecast yet"


def pane(html, key="weather"):
    start = html.index(f'data-pane="{key}"')
    return html[start:html.index("</section>", start)]


def temps(html):
    return [int(t) for t in re.findall(r'class="ws-temp"[^>]*>(\d+)°', html)]


def visible(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


@pytest.fixture
def met(monkeypatch):
    """MET switched on, the clock at 6:30 AM Dec 17 2026 in California, a fake MET answering with the Tahoe story."""
    monkeypatch.setenv("MET_NORWAY_TERMS_ACCEPTED", "1")
    monkeypatch.setattr(catalog, "now_utc", lambda: ws.NOW)
    monkeypatch.setattr(catalog, "today", lambda: ws.NOW.astimezone(ws.PST).date())
    fake = ws.Met()
    monkeypatch.setattr(weather, "TRANSPORT", fake)
    return fake


# ---- the /plan weather pane ---------------------------------------------------------------------------------------------------

def test_the_showcases_sample_trip_keeps_its_sample_weather(client):
    p = pane(client.get("/plan").text)
    assert temps(p) == [75, 73, 70, 72, 77] and "Sample data" in p and "MET Norway" not in p and "Typical" not in p


def test_a_real_trip_weeks_away_shows_typical_weather_from_noaa_labelled_not_a_forecast(client):
    p = pane(client.get("/plan?d=2026-12-21&r=2026-12-24&a=2&k=4").text)     # Los Angeles, today is Sep 30 (tests/conftest.py)
    text = visible(p)
    assert re.findall(r'class="ws-wday"[^>]*>([^<]+)<', p) == ["Mon 21", "Tue 22", "Wed 23", "Thu 24"]
    assert temps(p) == [67] * 4                                               # NOAA's late-December normal high, downtown Los Angeles
    assert p.count("ws-typical") == 4
    assert TYPICAL in text and "NOAA climate normals, 1991–2020" in text and "The forecast opens around Dec 12." not in text   # off: no promise
    assert "Sample data" not in text and "MET Norway" not in text


def test_the_live_site_shows_no_sample_weather_even_for_the_sample_trips_dates(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    text = visible(pane(client.get("/plan").text))
    assert "Sample data" not in text and "Typical mid October · not a forecast yet" in text
    assert "75°" not in text


def test_once_the_forecast_reaches_a_real_trip_the_pane_shows_it_with_met_norways_credit(client, met):
    p = pane(client.get("/plan?d=2026-12-19&r=2026-12-23&a=2").text)
    assert temps(p) == [ws.EXPECT[d][0] for d in range(19, 24)]
    assert "Heavy snow" in p and "ws-typical" not in p
    link = re.search(r'<a [^>]*href="([^"]+)"[^>]*>MET Norway</a>', p)
    assert link and link.group(1) == weather.CREDIT_URL
    assert "Forecast based on data from MET Norway · updated 6:10 AM" in visible(p)
    assert len(met.calls) == 1


def test_a_trip_whose_days_have_gone_by_says_so(client, monkeypatch):
    monkeypatch.setattr(catalog, "today", lambda: catalog.SAMPLE_TRIP.return_ + timedelta(days=3))
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    p = pane(client.get("/plan").text)
    assert temps(p) == [] and "These days have gone by." in visible(p)


# ---- the /forks calendar and a shared trip ---------------------------------------------------------------------------------------

TAHOE = (no_car(TEMPLATE)
         .replace("title: LA with the kids", "title: Tahoe at Christmas").replace("destination: Los Angeles", "destination: South Lake Tahoe")
         .replace("start: 2026-10-16", "start: 2026-12-19").replace("end: 2026-10-20", "end: 2026-12-26")
         .replace("to: LAX", "to: RNO").replace("from: LAX", "from: RNO")
         .replace("depart: 2026-10-16 08:05", "depart: 2026-12-19 08:05").replace("arrive: 2026-10-16 09:32", "arrive: 2026-12-19 09:32")
         .replace("depart: 2026-10-20 14:10", "depart: 2026-12-26 14:10").replace("arrive: 2026-10-20 15:37", "arrive: 2026-12-26 15:37")
         .replace("name: The Example Hotel Santa Monica", "name: Cabin by the lake").replace("address: 123 Ocean Ave, Santa Monica, CA 90401", "address: 1 Pine St, South Lake Tahoe, CA 96150")
         .replace("check_in: 2026-10-16 15:00", "check_in: 2026-12-19 16:00").replace("check_out: 2026-10-20 11:00", "check_out: 2026-12-26 10:00"))


def _calendar(html):
    start = html.index('class="fk-cal card"')
    return html[start:html.index("</section>", start)]


def test_the_forks_calendar_shows_the_tahoe_trips_typical_weather_never_the_sample(client):
    assert imported(client, TAHOE).status_code == 303
    cal = _calendar(client.get("/forks").text)
    heads = re.findall(r'class="fk-wx[^"]*"[^>]*>(\d+)°F<', cal)
    assert len(heads) == 8 and set(heads) <= {"42"}                         # South Lake Tahoe, mid and late December
    assert cal.count("fk-wx fk-wx-typ") == 8 and TYPICAL in visible(cal)
    assert "75°F" not in cal


def test_the_forks_calendar_shows_no_weather_where_gitaway_has_nothing_real(client):
    assert imported(client, TAHOE.replace("destination: South Lake Tahoe", "destination: Lisbon")).status_code == 303
    cal = _calendar(client.get("/forks").text)
    assert "fk-wx" not in cal and "°F" not in cal


def test_a_shared_real_trip_carries_no_weather(client):
    assert imported(client, TAHOE).status_code == 303
    trip = share.build(person("ari"))
    assert trip.days and all(d.weather == "" for d in trip.days)


def test_the_privacy_page_names_met_norway_and_noaa(client):
    text = visible(client.get("/privacy").text)
    assert "MET Norway" in text and "api.met.no" in text and "NOAA" in text


def test_a_trip_under_way_shows_only_the_days_still_to_come(client, monkeypatch):
    monkeypatch.setattr(catalog, "today", lambda: catalog.SAMPLE_TRIP.depart + timedelta(days=2))      # Sun Oct 18, the trip's third day
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    p = pane(client.get("/plan").text)
    assert re.findall(r'class="ws-wday"[^>]*>([^<]+)<', p) == ["Sun 18", "Mon 19", "Tue 20"]
    assert re.search(r'class="ws-meta"[^>]*>°F<', p)                                                    # no "first 3 of 5 days"
