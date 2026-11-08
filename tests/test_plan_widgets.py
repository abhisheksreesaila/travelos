"""F-210 (part B): the trip's context beside the booking lanes on /plan: weather, money and drive time. "No fakes please": each widget shows a real,
sourced value with its credit, or says plainly what is missing (money), or does not appear (weather, drive). Both showcase modes; no test reaches the network."""

import re
import socket
from datetime import date
from html import unescape

import pytest

from gitaway import airportdrive, catalog, geo, weather
from gitaway.partners import prices, travelpayouts
from tests import weather_support as ws
from tests.pagebody import without_bar

TAHOE = "/plan?place=Lake+Tahoe&d=2026-12-19&r=2026-12-26&a=2&k=8,11&home=SFO"
LISBON = "/plan?place=Lisbon&d=2026-10-10&r=2026-10-17&a=2"
KEYS = ("TRAVELPAYOUTS_MARKER", "TRAVELPAYOUTS_TOKEN", "TRAVELPAYOUTS_TRS", "KLOOK_FALLBACK_URL", "PARTNER_TRACKED", "PARTNER_FLIGHT", "PARTNER_STAY", "PARTNER_CAR",
        "PARTNER_TODO", "MET_NORWAY_TERMS_ACCEPTED")


@pytest.fixture(autouse=True, params=["0", "1"], ids=["live", "showcase"])
def mode(request, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", request.param)
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    travelpayouts._CACHE.clear()
    prices.clear()
    airportdrive.clear()
    monkeypatch.setattr(prices, "TRANSPORT", lambda *a: {"success": True, "data": []})

    def refuse(*a, **k):
        raise AssertionError("a code path tried to use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    yield request.param
    airportdrive.clear()


class Router:
    """A fake Nominatim and OSRM behind geo.fetch: South Lake Tahoe is found, and the drive from RNO takes `seconds`."""

    def __init__(self, seconds=3900):
        self.seconds, self.urls = seconds, []

    def __call__(self, url, timeout=None):
        self.urls.append(url)
        if "nominatim" in url:
            return [{"lat": "38.9399", "lon": "-119.9772", "display_name": "South Lake Tahoe, El Dorado County, California, United States"}]
        if "osrm" in url:
            return {"code": "Ok", "routes": [{"duration": self.seconds, "distance": 95000, "geometry": {"type": "LineString", "coordinates": [[-119.77, 39.50], [-119.98, 38.94]]},
                                              "legs": []}]}
        raise AssertionError(url)


def panel(html):
    """The side panel's HTML, or "" when the page has none."""
    m = re.search(r'<aside[^>]*id="pw"[^>]*>.*?</aside>', html, re.S)
    return m.group(0) if m else ""


def widget(html, name):
    m = re.search(rf'<section[^>]*id="pw-{name}"[^>]*>.*?</section>', panel(html), re.S)
    return m.group(0) if m else ""


def words(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


# ---- weather ---------------------------------------------------------------------------------------------------------------------

def test_tahoe_weeks_away_shows_noaa_typical_weather_labelled_not_a_forecast(client):
    w = words(widget(client.get(TAHOE).text, "weather"))
    st = weather.station_named("Lake Tahoe")
    lows = {weather.normal_day(st, date(2026, 12, d)).low_f for d in range(19, 27)}
    highs = {weather.normal_day(st, date(2026, 12, d)).high_f for d in range(19, 27)}
    assert "Weather in South Lake Tahoe" in w
    assert f"Highs {min(highs)}" in w and f"lows {min(lows)}" in w
    assert "Typical mid to late December · not a forecast yet" in w and "From NOAA climate normals for South Lake Tahoe, 1991–2020" in w
    assert "MET Norway" not in w


def test_tahoe_within_reach_shows_met_norways_forecast_with_its_credit_as_a_link(client, monkeypatch):
    monkeypatch.setenv("MET_NORWAY_TERMS_ACCEPTED", "1")
    monkeypatch.setattr(catalog, "now_utc", lambda: ws.NOW)
    monkeypatch.setattr(catalog, "today", lambda: ws.NOW.astimezone(ws.PST).date())
    monkeypatch.setattr(weather, "TRANSPORT", ws.Met())
    html = widget(client.get(TAHOE).text, "weather")
    assert re.search(r'<a [^>]*href="https://docs.api.met.no/doc/License"[^>]*>Forecast for South Lake Tahoe, based on data from MET Norway · updated 6:10 AM</a>', html)
    assert "Heavy snow" in words(html)          # Dec 19 in the story


def test_a_place_with_no_real_weather_shows_no_weather_widget(client):
    html = client.get(LISBON).text
    assert panel(html) and widget(html, "weather") == ""
    assert "Weather in" not in words(panel(html))


# ---- money -----------------------------------------------------------------------------------------------------------------------

def test_money_without_a_price_says_what_is_missing_and_shows_no_number(client):
    m = widget(client.get(TAHOE).text, "money")
    w = words(m)
    assert "Cost so far" in w and "No prices yet" in w
    assert "No price yet — check on Aviasales" in w
    assert "$" not in w and not re.search(r"\d+\s*a person", w)


def test_money_shows_the_real_aviasales_price_with_when_it_was_checked(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "t" * 32)
    monkeypatch.setattr(prices, "TRANSPORT", lambda *a: {"success": True, "data": [{"price": 187}]})
    w = words(widget(client.get(TAHOE).text, "money"))
    assert "From $187 a person" in w and "flights only" in w
    assert "Aviasales" in w and "checked" in w and "not a quote" in w
    assert "$374" not in w and "$748" not in w            # never multiplied out into a party total: a kid's fare is not an adult's


def test_money_for_a_place_without_an_airport_asks_for_one(client):
    w = words(widget(client.get(LISBON).text, "money"))
    assert "No prices yet" in w and "$" not in w


# ---- drive -----------------------------------------------------------------------------------------------------------------------

def test_the_drive_from_the_airport_is_the_routers_own_time_with_its_credit(client, monkeypatch):
    router = Router(3900)
    monkeypatch.setattr(geo, "fetch", router)
    d = widget(client.get(TAHOE).text, "drive")
    w = words(d)
    assert "Drive from RNO" in w and "1 h 5 min to South Lake Tahoe" in w
    assert 'href="https://www.openstreetmap.org/copyright"' in d and "OpenStreetMap" in w and "OSRM" in w
    asked = len(router.urls)
    assert asked == 2
    client.get(TAHOE)
    assert len(router.urls) == asked                      # kept: asked once


def test_no_router_answer_means_no_drive_widget(client):
    html = client.get(TAHOE).text                         # geo.fetch refuses (tests/conftest.py)
    assert widget(html, "drive") == "" and "Drive from" not in words(panel(html))


def test_a_drive_too_long_to_be_an_airport_run_is_not_shown(client, monkeypatch):
    monkeypatch.setattr(geo, "fetch", Router(11 * 3600))
    assert widget(client.get(TAHOE).text, "drive") == ""


def test_an_airport_outside_the_table_is_never_looked_up_by_its_code(client, monkeypatch):
    router = Router()
    monkeypatch.setattr(geo, "fetch", router)
    html = client.get(LISBON + "&iata=LIS").text
    assert widget(html, "drive") == "" and router.urls == []


# ---- the page ----------------------------------------------------------------------------------------------------------------------

def test_the_panel_sits_beside_the_lanes_and_loads_its_styles(client):
    html = without_bar(client.get(TAHOE).text)
    assert 'href="/assets/css/planwidgets.css' in html
    assert html.index('id="pw"') < html.index('class="ps-cards"')   # first in the source: above the lanes on a phone, beside them from 1020px
    assert 'class="pw-with"' in html


def test_no_panel_before_a_place_is_named(client):
    assert panel(client.get("/plan?place=").text) == ""


def test_every_lane_place_with_an_airport_has_its_coordinates():
    from gitaway.partners import places
    assert {p.iata for _, p in places._TABLE if p.iata} <= set(airportdrive.AIRPORTS)
