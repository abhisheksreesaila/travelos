"""F-203 (1): MET Norway's forecast for a place, the way their terms ask (an identifying User-Agent, at most four decimals, cache by Expires and
If-Modified-Since, a polite global gate, nothing until a person in charge has accepted the terms), read into GitAway's days. No test reaches
the network: `weather.TRANSPORT` is replaced (tests/conftest.py refuses every call unless a test installs tests/weather_support.Met)."""

import logging
from datetime import date, datetime, timedelta, timezone

import pytest

from gitaway import catalog, weather
from tests import weather_support as ws

TAHOE = (38.9399, -119.9772)
URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=38.9399&lon=-119.9772"


@pytest.fixture
def met(monkeypatch):
    """MET is switched on (the terms accepted), the clock is the story's (6:30 AM Dec 17 in Tahoe), and a fake MET answers."""
    monkeypatch.setenv("MET_NORWAY_TERMS_ACCEPTED", "1")
    clock = {"now": ws.NOW}
    monkeypatch.setattr(catalog, "now_utc", lambda: clock["now"])
    monkeypatch.setattr(catalog, "today", lambda: clock["now"].astimezone(ws.PST).date())
    fake = ws.Met()
    monkeypatch.setattr(weather, "TRANSPORT", fake)
    fake.clock = clock
    return fake


# ---- asking MET Norway ----------------------------------------------------------------------------------------------------

def test_nothing_is_asked_until_the_terms_are_accepted(met, monkeypatch):
    monkeypatch.delenv("MET_NORWAY_TERMS_ACCEPTED")
    assert weather.forecast(*TAHOE) is None
    monkeypatch.setenv("MET_NORWAY_TERMS_ACCEPTED", "yes")      # only "1" switches it on
    assert weather.forecast(*TAHOE) is None
    assert met.calls == []


def test_the_request_is_the_compact_forecast_at_four_decimals_with_an_identifying_user_agent(met, monkeypatch):
    monkeypatch.setenv("GITAWAY_CONTACT_EMAIL", "hello@gitaway.me")
    monkeypatch.setenv("GITAWAY_PUBLIC_URL", "https://gitaway.me")
    assert weather.forecast(38.939912, -119.977249) is not None
    (url, headers), = met.calls
    assert url == URL
    ua = headers["User-Agent"]
    assert ua.startswith("GitAway/") and "https://gitaway.me" in ua and "hello@gitaway.me" in ua
    assert headers["Accept-Encoding"] == "gzip" and "If-Modified-Since" not in headers


def test_the_altitude_goes_along_as_whole_metres_when_it_is_known(met):
    weather.forecast(*TAHOE, altitude=1924.5)
    assert met.calls[0][0] == URL + "&altitude=1924"


def test_without_a_contact_address_the_site_still_identifies_us_and_a_bad_address_is_left_out(met, monkeypatch):
    monkeypatch.setenv("GITAWAY_CONTACT_EMAIL", "a@b.c\r\nX-Evil: 1")
    weather.forecast(*TAHOE)
    ua = met.calls[0][1]["User-Agent"]
    assert "\n" not in ua and "Evil" not in ua and "@" not in ua
    assert ua.startswith("GitAway/") and "https://" in ua


def test_coordinates_outside_the_earth_or_not_numbers_are_never_asked(met):
    for lat, lon in ((91, 0), (0, 181), (float("nan"), 0), ("38.9", "-119.9"), (None, 1)):
        assert weather.forecast(lat, lon) is None
    assert met.calls == []


def test_a_second_ask_before_it_expires_is_answered_from_the_cache(met):
    first = weather.forecast(*TAHOE)
    again = weather.forecast(38.93991, -119.97719)      # the same place at four decimals
    assert again is first and len(met.calls) == 1


def test_it_waits_at_least_three_hours_even_when_expires_is_sooner(met):
    """Locationforecast FAQ: outside the Nordic area the forecast changes every six hours; wait at least half of that before asking again."""
    weather.forecast(*TAHOE)
    met.clock["now"] = ws.NOW + timedelta(hours=2, minutes=50)       # Expires (6:43 AM) has passed, three hours have not
    weather.forecast(*TAHOE)
    assert len(met.calls) == 1
    met.clock["now"] = ws.NOW + timedelta(hours=3, minutes=1)
    weather.forecast(*TAHOE)
    assert len(met.calls) == 2


def test_after_it_expires_it_asks_with_if_modified_since_and_keeps_its_data_on_304(met):
    met.answers = [(200, ws.headers(), ws.body()), (304, ws.headers(expires=ws.NOW + timedelta(hours=9)), b"")]
    first = weather.forecast(*TAHOE)
    met.clock["now"] = ws.NOW + timedelta(hours=4)
    second = weather.forecast(*TAHOE)
    assert met.calls[1][1]["If-Modified-Since"] == ws.http_date(ws.UPDATED)      # exactly the Last-Modified it was given
    assert second is not None and second.points == first.points
    met.clock["now"] = ws.NOW + timedelta(hours=8)       # the 304's own Expires (9 hours) now holds
    weather.forecast(*TAHOE)
    assert len(met.calls) == 2


def test_a_gzipped_answer_is_read(met):
    met.answers = [(200, ws.headers(gz=True), ws.body(gz=True))]
    fc = weather.forecast(*TAHOE)
    assert fc is not None and len(fc.points) > 80


def test_a_deprecated_product_still_answers_and_is_logged(met, caplog):
    met.answers = [(203, ws.headers(), ws.body())]
    with caplog.at_level(logging.WARNING, logger="gitaway.weather"):
        assert weather.forecast(*TAHOE) is not None
    assert any("203" in r.getMessage() and "deprecated" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("status", [429, 403])
def test_a_refusal_shuts_the_gate_so_nobody_asks_again_for_a_while(met, status, caplog):
    met.answers = [(status, {}, b"")]
    with caplog.at_level(logging.WARNING, logger="gitaway.weather"):
        assert weather.forecast(*TAHOE) is None
    assert weather.GATE.is_shut()
    assert weather.forecast(40.0, -105.0) is None          # another place: still nobody asks
    assert len(met.calls) == 1
    assert any(str(status) in r.getMessage() for r in caplog.records)


def test_a_failed_call_is_not_repeated_at_once_but_is_tried_again_later(met):
    met.answers = [(OSError("down"), {}, b""), (200, ws.headers(expires=ws.NOW + timedelta(hours=9)), ws.body())]
    assert weather.forecast(*TAHOE) is None
    assert weather.forecast(*TAHOE) is None and len(met.calls) == 1       # a page refresh does not hammer a service that is down
    met.clock["now"] = ws.NOW + timedelta(minutes=6)
    assert weather.forecast(*TAHOE) is not None and len(met.calls) == 2


def test_garbled_or_empty_answers_give_no_forecast(met):
    for answer in ((200, ws.headers(), b"<html>busy</html>"), (200, ws.headers(), b'{"type": "Feature"}'),
                   (200, ws.headers(), b'{"properties": {"timeseries": [{"time": "soon", "data": {}}]}}'), (500, {}, b"")):
        weather.clear()
        met.answers = [answer]
        assert weather.forecast(*TAHOE) is None


def test_when_a_later_call_fails_the_last_forecast_is_kept_for_a_day(met):
    met.answers = [(200, ws.headers(), ws.body()), (OSError("down"), {}, b"")]
    first = weather.forecast(*TAHOE)
    met.clock["now"] = ws.NOW + timedelta(hours=5)
    assert weather.forecast(*TAHOE) is first
    met.clock["now"] = ws.NOW + timedelta(hours=26)
    assert weather.forecast(*TAHOE) is None


# ---- reading it into days ---------------------------------------------------------------------------------------------------

def _days():
    fc = weather.forecast(*TAHOE)
    return weather.forecast_days(fc, "America/Los_Angeles", ws.NOW)


def test_each_covered_local_day_gets_its_high_low_and_condition_in_fahrenheit(met):
    days = _days()
    for d, (hi, lo, condition, word) in ws.EXPECT.items():
        got = days[date(2026, 12, d)]
        assert (got.high_f, got.low_f, got.condition, got.word) == (hi, lo, condition, word), d
        assert got.kind == weather.FORECAST and got.label == ""


def test_the_last_day_with_only_a_morning_of_forecast_is_not_a_forecast_day(met):
    days = _days()
    assert date(2026, 12, 25) in days and date(2026, 12, 26) not in days and date(2026, 12, 16) not in days


def test_precipitation_and_wind_are_in_inches_and_miles_an_hour(met):
    days = _days()
    assert days[date(2026, 12, 19)].precip_in == 1.35
    assert days[date(2026, 12, 23)].precip_in == 0.25
    assert days[date(2026, 12, 21)].precip_in == 0.0
    assert days[date(2026, 12, 22)].wind_mph == 25


def test_hourly_steps_come_along_where_met_gives_them(met):
    days = _days()
    snow_day = days[date(2026, 12, 19)].hours
    assert [h.at for h in snow_day] == list(range(22))
    assert snow_day[10].condition == "snow" and snow_day[10].temp_f == 24      # 10 AM: -4.3 C, in the heavy snow
    assert len(days[date(2026, 12, 18)].hours) == 24 and days[date(2026, 12, 21)].hours == ()


def test_today_is_marked_partial_because_its_morning_has_gone(met):
    days = _days()
    assert days[date(2026, 12, 17)].partial and not days[date(2026, 12, 18)].partial


def test_the_forecast_says_when_met_made_it_in_the_places_time(met):
    fc = weather.forecast(*TAHOE)
    assert fc.updated == ws.UPDATED
    assert weather.updated_text(fc, "America/Los_Angeles") == "6:10 AM"
