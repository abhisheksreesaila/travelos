"""F-036: the weather, events and news panes follow the trip's dates and length. Events and news are fake data, deterministic per date; since F-203
the weather is real (here NOAA's typical weather, the dates being weeks away; tests/test_weather_pages.py has the forecast)."""

import re

from gitaway import catalog, context, weather

WINTER = "/plan?d=2026-12-03&r=2026-12-06&a=2&k=4"  # Thu Dec 3 - Sun Dec 6, 2026: 3 nights, 4 days


def pane(html, key):
    start = html.index(f'data-pane="{key}"')
    return html[start:html.index("</section>", start)]


def labels(html, cls):
    return re.findall(rf'class="{cls}[^"]*">([^<]+)<', html)


def test_sample_trip_keeps_the_sample_context():
    trip = catalog.SAMPLE_TRIP
    assert weather.sample(trip)          # its weather pane shows context.WEATHER (tests/test_workspace.py)
    assert context.events_for(trip) == context.EVENTS
    assert context.news_for(trip) == context.NEWS


def test_temperatures_are_plausible_for_la_in_each_month():
    for month, (lo, hi) in {1: (55, 78), 7: (70, 92), 10: (65, 90), 12: (55, 80)}.items():
        trip = catalog.trip_from_url(f"2027-{month:02d}-10", f"2027-{month:02d}-14", "2", "")
        assert all(lo <= d.high_f <= hi and d.low_f < d.high_f for d in weather.trip_weather(trip).days), month

