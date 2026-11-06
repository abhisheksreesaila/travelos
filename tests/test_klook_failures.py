"""F-195 (7): a Klook link that cannot be made is logged at WARNING with its reason, counted, and the count is on /admin, so a wrong TRAVELPAYOUTS_TRS is noticed.

No test reaches the network: the partner-links call is the FakeApi of test_partners.
"""

import logging
import re
import socket
import urllib.error
from html import unescape

import pytest

from gitaway.partners import failures, travelpayouts
from tests.test_partners import FakeApi, TRIP, nokeys  # noqa: F401 (the fixture)
from tests.test_signin import sign_in

SECRET = "tok-SECRET-9f3a"
PAGE = "https://www.klook.com/en-US/search/result/?query=Honolulu%20hotels"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a code path tried to use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


@pytest.fixture
def keys(nokeys, monkeypatch):
    from gitaway import community
    community.clear()
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", SECRET)
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")


def warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING and r.name == "gitaway.partners.travelpayouts"]


def test_a_refusing_api_is_a_warning_that_says_why_and_never_the_token(keys, monkeypatch, caplog):
    err = urllib.error.HTTPError(API := travelpayouts.API, 400, f"invalid trs, token {SECRET}", {}, None)
    monkeypatch.setattr(travelpayouts, "_post", FakeApi(error=err))
    with caplog.at_level(logging.INFO, logger="gitaway.partners.travelpayouts"):
        assert travelpayouts.klook_link(PAGE, "s") == "https://klook.tpx.lv/s1rIcwCA"
    (line,) = warnings(caplog)
    assert "HTTPError" in line and "400" in line and "invalid trs" in line
    assert SECRET not in line and SECRET not in " ".join(r.getMessage() for r in caplog.records)
    assert failures.recent() == (1, "HTTPError: HTTP Error 400: invalid trs, token ***")


def test_a_wrong_answer_and_a_timeout_are_failures_too(keys, monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="gitaway.partners.travelpayouts"):
        monkeypatch.setattr(travelpayouts, "_post", FakeApi(answer={"code": 200, "result": {"links": [{"code": "invalid_trs", "partner_url": ""}]}}))
        travelpayouts.klook_link(PAGE, "a")
        monkeypatch.setattr(travelpayouts, "_post", FakeApi(error=TimeoutError("timed out")))
        travelpayouts.klook_link(PAGE, "b")
    assert warnings(caplog) == ["partner-links API failed, the click goes to the plain Klook link (LookupError: the API refused the link: invalid_trs)",
                                "partner-links API failed, the click goes to the plain Klook link (TimeoutError: timed out)"]
    count, last = failures.recent()
    assert count == 2 and last == "TimeoutError: timed out"


def test_a_token_without_a_numeric_project_id_is_a_failure_every_click_would_lose_its_tracking(keys, monkeypatch, caplog):
    monkeypatch.delenv("TRAVELPAYOUTS_TRS")
    with caplog.at_level(logging.WARNING, logger="gitaway.partners.travelpayouts"):
        travelpayouts.klook_link(PAGE, "s")
    assert "TRAVELPAYOUTS_TRS" in warnings(caplog)[0] and failures.recent()[0] == 1


def test_no_token_is_not_a_failure_it_is_not_being_used(nokeys, monkeypatch, caplog):
    from gitaway import community
    community.clear()
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    with caplog.at_level(logging.INFO, logger="gitaway.partners.travelpayouts"):
        travelpayouts.klook_link(PAGE, "s")
    assert warnings(caplog) == [] and failures.recent() == (0, "")


def test_a_good_link_is_not_counted_and_a_cached_one_is_not_asked_again(keys, monkeypatch):
    travelpayouts._CACHE.clear()
    api = FakeApi()
    monkeypatch.setattr(travelpayouts, "_post", api)
    travelpayouts.klook_link(PAGE, "s"), travelpayouts.klook_link(PAGE, "s")
    assert failures.recent() == (0, "") and len(api.calls) == 1


def test_only_the_last_week_is_counted():
    from datetime import date, timedelta
    from sqlalchemy import text
    from gitaway import community
    community.clear()
    failures.record("TimeoutError: old")
    with community.connect() as db:
        db.conn.execute(text("UPDATE klook_failures SET day = :d"), {"d": (date.today() - timedelta(days=8)).isoformat()})
        db.conn.commit()
    failures.record("TimeoutError: new")
    assert failures.recent(7) == (1, "TimeoutError: new") and failures.recent(30)[0] == 2


def test_a_click_still_lands_somewhere_when_even_the_failure_cannot_be_written(keys, monkeypatch):
    monkeypatch.setattr(travelpayouts, "_post", FakeApi(error=TimeoutError("slow")))
    monkeypatch.setattr(failures, "record", lambda reason: 1 / 0)
    assert travelpayouts.klook_link(PAGE, "s") == "https://klook.tpx.lv/s1rIcwCA"


def numbers(html):
    return {k: unescape(re.search(rf'id="{k}"[^>]*>([^<]*)<', html).group(1)) for k in ("ad-klook-failures",)}


@pytest.fixture
def captain(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "cap@example.com")
    sign_in(client, "cap@example.com")
    return client


def test_admin_shows_how_many_klook_links_failed_this_week_and_why(captain, keys, monkeypatch):
    html = captain.get("/admin").text
    assert numbers(html) == {"ad-klook-failures": "0"} and 'id="ad-klook-last"' not in html
    monkeypatch.setattr(travelpayouts, "_post", FakeApi(error=TimeoutError("slow")))
    travelpayouts._CACHE.clear()
    captain.get(f"/go/hih1?to=hi&{TRIP}", follow_redirects=False)       # a click that went through the failing API
    captain.get(f"/go/hic1?to=hi&{TRIP}", follow_redirects=False)
    html = captain.get("/admin").text
    assert numbers(html) == {"ad-klook-failures": "2"}
    last = unescape(re.search(r'id="ad-klook-last"[^>]*>([^<]*)<', html).group(1))
    assert "TimeoutError: slow" in last and "TRAVELPAYOUTS_TRS" in last and "last 7 days" in last and SECRET not in html
