"""F-036: the weather, events and news panes follow the trip's dates and length (fake data, deterministic per date)."""

import re

from gitaway import catalog, context

WINTER = "/plan?d=2026-12-03&r=2026-12-06&a=2&k=4"  # Thu Dec 3 - Sun Dec 6, 2026: 3 nights, 4 days


def pane(html, key):
    start = html.index(f'data-pane="{key}"')
    return html[start:html.index("</section>", start)]


def labels(html, cls):
    return re.findall(rf'class="{cls}[^"]*">([^<]+)<', html)


def test_sample_trip_keeps_the_sample_context():
    trip = catalog.SAMPLE_TRIP
    assert context.weather_for(trip) == context.WEATHER
    assert context.events_for(trip) == context.EVENTS
    assert context.news_for(trip) == context.NEWS


def test_weather_pane_follows_a_non_sample_trips_dates(client):
    h = client.get(WINTER).text
    days = labels(pane(h, "weather"), "ws-wday")
    assert days == ["Thu 3", "Fri 4", "Sat 5", "Sun 6"]
    assert "Fri 16" not in pane(h, "weather")


def test_weather_pane_follows_the_trips_length(client):
    short = labels(pane(client.get("/plan?d=2026-12-03&r=2026-12-04&a=2").text, "weather"), "ws-wday")
    assert short == ["Thu 3", "Fri 4"]
    long = pane(client.get("/plan?d=2026-12-03&r=2026-12-20&a=2").text, "weather")
    shown = labels(long, "ws-wday")
    assert shown[0] == "Thu 3" and 4 < len(shown) <= context.WEATHER_DAYS_SHOWN
    assert "18 days" in long  # the pane says how many days the trip has


def test_events_fall_on_the_trips_days(client):
    h = client.get(WINTER).text
    when = labels(pane(h, "news"), "ws-when")
    assert when and set(when) <= {"Thu 3", "Fri 4", "Sat 5", "Sun 6"}
    assert len(set(when)) == len(when)


def test_the_same_dates_always_give_the_same_fake_data(client):
    a, b = client.get(WINTER).text, client.get(WINTER).text
    assert pane(a, "weather") == pane(b, "weather") and pane(a, "news") == pane(b, "news")
    # the weather for a date does not depend on which trip it is part of
    t1 = catalog.trip_from_url("2026-12-03", "2026-12-06", "2", "")
    t2 = catalog.trip_from_url("2026-12-04", "2026-12-08", "2", "")
    w1 = {w.day: w for w in context.weather_for(t1)}
    w2 = {w.day: w for w in context.weather_for(t2)}
    assert w1["Fri 4"] == w2["Fri 4"] and w1["Sat 5"] == w2["Sat 5"]


def test_temperatures_are_plausible_for_la_in_each_month():
    for month, (lo, hi) in {1: (55, 78), 7: (70, 92), 10: (65, 90), 12: (55, 80)}.items():
        trip = catalog.trip_from_url(f"2027-{month:02d}-10", f"2027-{month:02d}-14", "2", "")
        assert all(lo <= w.temp_f <= hi for w in context.weather_for(trip)), month


def test_news_sub_names_the_trips_month(client):
    h = pane(client.get(WINTER).text, "news")
    assert "December" in h and "October" not in h


def test_a_one_night_trip_still_shows_every_pane(client):
    h = client.get("/plan?d=2027-03-05&r=2027-03-06&a=1").text
    assert labels(pane(h, "weather"), "ws-wday") == ["Fri 5", "Sat 6"]
    assert pane(h, "news").count("ws-news") >= 1
