"""F-198: real flight prices where they are free. The Aviasales Data API's cached prices (market=us, currency=usd), kept 24 hours, shown as "from $X a person, checked <time>";
no token, no answer or a bad answer shows no price at all. Every call goes through `prices.TRANSPORT`; no test reaches the network."""

import socket
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from gitaway.partners import prices

DEP, RET = date(2026, 12, 19), date(2026, 12, 26)
GOOD = {"success": True, "currency": "usd", "data": [{"origin": "SFO", "destination": "RNO", "price": 187, "departure_at": "2026-12-19T07:10:00-08:00",
                                                      "return_at": "2026-12-26T18:00:00-08:00", "airline": "UA"}]}


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    prices.clear()
    monkeypatch.delenv("TRAVELPAYOUTS_TOKEN", raising=False)
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    yield
    prices.clear()


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "secret-token")
    calls = []

    def answer(url, headers, timeout):
        calls.append((url, headers, timeout))
        return answer.reply() if callable(answer.reply) else answer.reply
    answer.reply = GOOD
    monkeypatch.setattr(prices, "TRANSPORT", answer)
    return answer, calls


def test_no_token_no_call_no_price(monkeypatch):
    monkeypatch.setattr(prices, "TRANSPORT", lambda *a: pytest.fail("called without a token"))
    assert prices.flight_from("SFO", "RNO", DEP, RET) is None


def test_the_call_asks_for_us_dollars_on_the_us_market_with_the_token_in_a_header(api):
    _, calls = api
    p = prices.flight_from("SFO", "RNO", DEP, RET)
    assert (p.cents, p.label()) == (18_700, f"from $187 a person, checked {prices.when(p.checked)}")
    url, headers, timeout = calls[0]
    q = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    assert url.startswith("https://api.travelpayouts.com/aviasales/v3/prices_for_dates?")
    assert q == {"origin": "SFO", "destination": "RNO", "departure_at": "2026-12-19", "return_at": "2026-12-26", "currency": "usd", "market": "us",
                 "sorting": "price", "direct": "false", "one_way": "false", "limit": "1"}
    assert headers == {"X-Access-Token": "secret-token", "Accept": "application/json"} and "secret-token" not in url
    assert timeout <= 3


def test_a_price_is_cached_for_a_day(api):
    answer, calls = api
    first = prices.flight_from("SFO", "RNO", DEP, RET)
    answer.reply = {"success": True, "data": [{"price": 99}]}
    assert prices.flight_from("sfo", "rno", DEP, RET) == first and len(calls) == 1
    prices._CACHE[("SFO", "RNO", DEP, RET)] = (first, first.checked - timedelta(hours=25))      # a day and an hour later
    assert prices.flight_from("SFO", "RNO", DEP, RET).cents == 9_900 and len(calls) == 2


@pytest.mark.parametrize("reply", [{"success": True, "data": []}, {"success": False, "error": "unauthorized"}, {"data": [{"price": "a lot"}]}, {"data": [{"price": -5}]},
                                   {"data": [{"price": 0}]}, {"data": [{}]}, "not json", None])
def test_nothing_usable_means_no_price(api, reply):
    answer, _ = api
    answer.reply = reply
    assert prices.flight_from("SFO", "RNO", DEP, RET) is None


def test_a_failure_means_no_price_is_logged_without_the_token_and_is_not_retried_at_once(api, caplog):
    answer, calls = api

    def boom():
        raise TimeoutError("timed out with secret-token")
    answer.reply = boom
    assert prices.flight_from("SFO", "RNO", DEP, RET) is None
    assert prices.flight_from("SFO", "RNO", DEP, RET) is None and len(calls) == 1      # a failure is remembered for a while: a slow API is not asked on every page
    assert "secret-token" not in caplog.text and "flight price" in caplog.text


def test_bad_codes_and_past_dates_ask_nothing(api):
    _, calls = api
    assert prices.flight_from("", "RNO", DEP, RET) is None
    assert prices.flight_from("SFO", "R1O", DEP, RET) is None
    assert prices.flight_from("SFO", "SFO", DEP, RET) is None
    assert prices.flight_from("SFO", "RNO", date(2020, 1, 1), date(2020, 1, 5)) is None
    assert calls == []


def test_when_reads_like_a_person_wrote_it():
    assert prices.when(datetime(2026, 11, 6, 22, 5, tzinfo=timezone.utc)) == "Nov 6, 2:05 PM"      # Pacific time, like the rest of GitAway
