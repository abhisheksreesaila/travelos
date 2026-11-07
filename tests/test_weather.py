"""F-203 (1): MET Norway's forecast for a place, the way their terms ask (an identifying User-Agent, at most four decimals, cache by Expires and
If-Modified-Since, a polite global gate, nothing until a person in charge has accepted the terms), read into GitAway's days. No test reaches
the network: `weather.TRANSPORT` is replaced (tests/conftest.py refuses every call unless a test installs tests/weather_support.Met)."""

import json
import logging
import time
from dataclasses import fields
from datetime import date, datetime, timedelta, timezone

import pytest

from gitaway import catalog, geo, weather
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


def test_the_forecast_says_when_met_made_it_in_the_places_time(met):
    fc = weather.forecast(*TAHOE)
    assert fc.updated == ws.UPDATED
    assert weather.updated_text(fc, "America/Los_Angeles") == "6:10 AM"



# ---- review: everything MET sends is untrusted (security F1) --------------------------------------------------------------------

def _doc(updated=None, steps=None):
    doc = ws.compact()
    if updated is not None:
        doc["properties"]["meta"]["updated_at"] = updated
    if steps is not None:
        doc["properties"]["timeseries"] = steps
    return doc


@pytest.mark.parametrize("raw", [b"[" * 100000, b'{"properties": ' * 50000], ids=["nested-lists", "nested-objects"])
def test_an_answer_that_breaks_the_reader_is_a_failed_call_and_is_not_asked_again_at_once(met, raw):
    met.answers = [(200, ws.headers(), raw)]
    assert weather.forecast(*TAHOE) is None
    assert weather.forecast(*TAHOE) is None and len(met.calls) == 1
    met.clock["now"] = ws.NOW + timedelta(minutes=6)
    weather.forecast(*TAHOE)
    assert len(met.calls) == 2


@pytest.mark.parametrize("expires", ["Fri, 31 Dec 9999 23:59:59 GMT", "Fri, 31 Dec 9999 23:59:59 -2359", "Fri, 31 Dec 100000000000000000000 23:59:59 GMT"],
                         ids=["year-9999", "past-year-9999", "overflow"])
def test_an_expires_far_off_or_absurd_neither_crashes_nor_freezes_the_place(met, expires):
    met.answers = [(200, {**ws.headers(), "expires": expires}, ws.body())]
    assert weather.forecast(*TAHOE) is not None
    met.clock["now"] = ws.NOW + timedelta(hours=12, minutes=1)
    weather.forecast(*TAHOE)
    assert len(met.calls) == 2       # at most twelve hours, whatever Expires says


@pytest.mark.parametrize("updated", ["9999-12-31T23:59:59Z", "1970-01-01T00:00:00Z", "2026-12-17T16:00:00Z"], ids=["far-future", "far-past", "ahead-of-now"])
def test_a_forecast_made_far_from_now_is_refused(met, updated):
    met.answers = [(200, ws.headers(), ws.body(_doc(updated=updated)))]
    assert weather.forecast(*TAHOE) is None
    assert weather.forecast(*TAHOE) is None and len(met.calls) == 1


def test_steps_at_absurd_or_far_off_times_are_dropped_and_the_days_still_read(met):
    doc = ws.compact()
    steps = doc["properties"]["timeseries"]
    six = json.loads(json.dumps(steps[-2]))
    for when in ("9999-12-31T18:00:00Z", "0001-01-01T00:00:00Z", "2026-12-13T12:00:00Z", "2027-01-05T00:00:00Z"):   # out of range, four days back, 19 days on
        steps.append({**six, "time": when})
    met.answers = [(200, ws.headers(), ws.body(doc))]
    fc = weather.forecast(*TAHOE)
    assert fc is not None and len(fc.points) == len(steps) - 4
    assert weather.forecast_days(fc, "America/Los_Angeles", ws.NOW)[date(2026, 12, 19)].word == "Heavy snow"


def test_a_huge_timeseries_is_cut_to_a_size_met_never_sends(met):
    tiny = [{"time": (ws.FIRST + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ"), "data": {"instant": {"details": {"air_temperature": -1.0}}}}
            for m in range(5000)]
    met.answers = [(200, ws.headers(), ws.body(_doc(steps=tiny)))]
    fc = weather.forecast(*TAHOE)
    assert fc is not None and len(fc.points) == weather.MAX_STEPS <= 250


# ---- review: the transport asks api.met.no and nothing else, within one deadline (security F2, F3) --------------------------------

@pytest.fixture
def stand_in(monkeypatch):
    """The transport's socket goes to a local stand-in instead of api.met.no; nothing may leave this machine."""
    ws.local_only(monkeypatch)
    server = ws.Server()
    monkeypatch.setattr(weather, "CONNECTION", server.connection, raising=False)
    monkeypatch.setattr(weather, "_lookup", lambda host, deadline: "127.0.0.1", raising=False)
    yield server
    server.close()


def test_a_redirect_is_never_followed_and_only_its_host_is_logged(stand_in, caplog):
    stand_in.mode = "redirect"
    with caplog.at_level(logging.WARNING, logger="gitaway.weather"):
        status, _headers, raw = weather._http(URL, {"User-Agent": "GitAway test"}, 3)
    assert (status, raw, stand_in.hits) == (302, b"", 1)
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "169.254.169.254" in said and "credentials" not in said


@pytest.mark.parametrize("url", ["http://api.met.no/weatherapi/locationforecast/2.0/compact?lat=1&lon=2", "https://169.254.169.254/latest/meta-data/",
                                 "https://api.met.no.example.com/x", "https://user@api.met.no/x", "https://api.met.no:8443/x", "https://127.0.0.1:1/x"],
                         ids=["plain-http", "metadata", "lookalike", "userinfo", "port", "local"])
def test_only_https_api_met_no_is_ever_asked(stand_in, url):
    with pytest.raises(ValueError):
        weather._http(url, {}, 3)
    assert stand_in.hits == 0


def test_a_slow_answer_is_cut_at_the_deadline(stand_in):
    stand_in.mode = "slow"
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        weather._http(URL, {}, 1.0)
    assert time.monotonic() - started < 1.5


def test_a_slow_name_lookup_is_cut_at_the_deadline_too(monkeypatch):
    """The address of api.met.no is looked up within the call's deadline: a resolver that hangs cannot hold the page."""
    import socket
    ws.local_only(monkeypatch)

    def hangs(*a, **k):
        time.sleep(3)
        raise OSError("no answer")
    monkeypatch.setattr(socket, "getaddrinfo", hangs)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        weather._http(URL, {}, 0.5)
    assert time.monotonic() - started < 1.0


def test_a_page_waits_its_turn_at_the_gate_only_until_its_own_deadline(met, monkeypatch):
    monkeypatch.setattr(weather.GATE, "gap", 5.0)
    monkeypatch.setattr(weather.GATE, "last", geo._clock())        # somebody has just asked
    started = time.monotonic()
    assert weather.forecast(*TAHOE, timeout=0.3) is None
    assert time.monotonic() - started < 1.0 and met.calls == []


def test_a_place_that_was_not_asked_leaves_no_lock_behind(met, monkeypatch):
    monkeypatch.setattr(weather.GATE, "shut_until", geo._clock() + 60)
    assert weather.forecast(*TAHOE) is None
    assert weather._ASKING == {}


# ---- review: what was there but untested (reviewer 5) ----------------------------------------------------------------------------

@pytest.fixture
def gate_clock(monkeypatch):
    """The gate's clock and sleep, faked (tests/conftest.py zeroes the gap; these tests put it back)."""
    t = {"now": 100.0, "slept": []}
    monkeypatch.setattr(geo, "_clock", lambda: t["now"])

    def sleep(s):
        t["slept"].append(round(s, 3))
        t["now"] += s
    monkeypatch.setattr(geo, "_sleep", sleep)
    monkeypatch.setattr(weather.GATE, "gap", 0.2)
    monkeypatch.setattr(weather.GATE, "last", None)
    return t


def test_two_places_asked_at_once_are_spaced_by_the_gate(met, gate_clock):
    weather.forecast(*TAHOE)
    weather.forecast(40.0, -105.0)
    assert len(met.calls) == 2 and gate_clock["slept"] == [0.2]


@pytest.mark.parametrize("status, seconds", [(429, 600), (403, 3600)])
def test_a_refusal_shuts_the_gate_for_ten_minutes_or_an_hour(met, gate_clock, status, seconds):
    met.answers = [(status, {}, b""), (200, ws.headers(), ws.body())]
    weather.forecast(*TAHOE)
    gate_clock["now"] += seconds - 1
    met.clock["now"] += timedelta(seconds=seconds - 1)
    assert weather.forecast(40.0, -105.0) is None and len(met.calls) == 1      # still shut a second before
    gate_clock["now"] += 2
    met.clock["now"] += timedelta(seconds=2)
    assert weather.forecast(40.0, -105.0) is not None and len(met.calls) == 2


# ---- review: nothing that nothing reads (reviewer 8) -------------------------------------------------------------------------------

def test_nothing_that_nothing_reads_is_left():
    from gitaway.pages import weather_ui
    assert not hasattr(weather, "Hour") and not hasattr(weather, "CACHE_MAX") and not hasattr(weather_ui, "_ICONS")
    assert {f.name for f in fields(weather.Day)}.isdisjoint({"hours", "partial"})
