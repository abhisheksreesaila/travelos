"""F-203 (4): the places real trips show weather. The /plan weather pane, the /forks calendar's day heads and a shared trip show MET's forecast
(credited) or typical weather (labelled) for a real trip, and never invented weather; the showcase's sample trip keeps its sample weather.
/privacy names MET Norway."""

import re
from dataclasses import replace
from datetime import timedelta
from html import unescape

import pytest
from fasthtml.common import to_xml

from gitaway import catalog, community, itineraries, itinerary_view, share, weather
from tests import weather_support as ws
from tests.test_signin import person
from tests.test_trip_import import TEMPLATE, imported, no_car

TYPICAL = "Typical late December · not a forecast yet"
TYPICAL_SPAN = "Typical mid to late December · not a forecast yet"
CREDIT_LINE = re.compile(r'<a [^>]*href="([^"]+)"[^>]*>Forecast for ([^<]+), based on data from MET Norway · updated 6:10 AM</a>')


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

def live_pane():
    """The /plan weather pane for the sample trip's dates, drawn as the live site would (the showcase off); since F-198 the live /plan itself shows the lanes instead."""
    from fasthtml.common import to_xml
    from gitaway.pages import plan
    return pane(to_xml(plan.weather_pane(catalog.SAMPLE_TRIP)))


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


def test_a_shared_real_trip_carries_no_weather(client):
    assert imported(client, TAHOE).status_code == 303
    trip = share.build(person("ari"))
    assert trip.days and all(d.weather == "" for d in trip.days)


def test_the_privacy_page_names_met_norway_and_noaa(client):
    text = visible(client.get("/privacy").text)
    assert "MET Norway" in text and "api.met.no" in text and "NOAA" in text


# ---- review: a shared or published page never shows invented weather (reviewer 1) -------------------------------------------------------

def _drawn(trip):
    return to_xml(itinerary_view.itinerary_body(trip))


def test_a_shared_real_trips_page_shows_no_invented_weather(client):
    assert imported(client, TAHOE).status_code == 303
    page = _drawn(share.build(person("ari")))
    assert "74°F" not in page and "mostly sunny" not in page and 'class="weather' not in page


def test_a_published_trip_without_photos_shows_no_weather_badge():
    old_snapshot = replace(itineraries.get("sun-tacos-and-tide-pools"), polaroids=[], real=True, weather=("74°F", "mostly sunny"))
    assert "74°F" not in _drawn(old_snapshot)
    assert "74°F" not in _drawn(replace(old_snapshot, real=False, weather=()))        # the sticker collage draws a badge only when there is weather


def test_an_already_published_shared_snapshot_loses_its_invented_weather():
    row = {"kind": "shared", "snapshot": community.dump(replace(itineraries.get("sun-tacos-and-tide-pools"), weather=("74°F", "mostly sunny")))}
    assert community.trip_of(row).weather == ()


def test_the_showcases_sample_itinerary_keeps_its_sample_badge():
    assert "74°F" in _drawn(itineraries.get("sun-tacos-and-tide-pools"))


# ---- review: MET's answer can never take a page down (security F1) --------------------------------------------------------------------

# ---- review: the credit where /forks shows the forecast (reviewer 5) ----------------------------------------------------------------------

# ---- last review: an old shared snapshot's day weather never reaches the page (reviewer 3); nor does the sample's (nit) ---------------------

def test_an_old_shared_snapshots_day_weather_never_reaches_the_page():
    old = itineraries.get("sun-tacos-and-tide-pools")
    old = replace(old, polaroids=[], days=[replace(d, weather="75°F, clear skies") for d in old.days])        # as shared before F-203
    page = _drawn(community.trip_of({"kind": "shared", "snapshot": community.dump(old)}))
    assert "75°F" not in page and "clear skies" not in page and "74°F" not in page and 'class="rail-weather"' not in page

