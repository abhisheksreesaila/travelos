"""F-265: a fair limit on visitors' searches (D-762..D-765). Each signed-out visitor has their own small daily allowance of new LiteAPI searches, found the way stats.py counts readers
(a salted hash that goes at midnight, no cookie, no address kept); what is cached is free; a signed-in family keeps its own budget; the site's total still caps everyone."""
import hashlib
from html import unescape

import pytest
from sqlalchemy import text
from starlette.requests import Request

from gitaway import community, liteapi, stats, tripmatrix as tm
from tests.test_liteapi import KEY, Fake, fake, flights, stays  # noqa: F401
from tests.test_signin import sign_in

MATRIX = "/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16&a=2&k=7,10&x=2"
TILE = "/plan/matrix/tile?" + MATRIX.split("?")[1]


def req(ip="203.0.113.7", ua="Mozilla/5.0 Firefox"):
    return Request({"type": "http", "headers": [(b"user-agent", ua.encode()), (b"x-forwarded-for", ip.encode())], "client": (ip, 1234), "method": "GET", "path": "/"})


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    fake = Fake()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    stats.reset()
    return fake


def at(client, ip, day="2026-12-12", lane="sandiego"):
    return client.get(f"{TILE}&lane={lane}&w={day}", headers={"x-forwarded-for": ip, "user-agent": "Mozilla/5.0 Firefox"}).json()


def rows():
    with community.connect() as db:
        return db.conn.execute(text("SELECT day, family, n FROM liteapi_searches ORDER BY family")).fetchall()


# ---- who a visitor is ------------------------------------------------------------------------------------------------------

def test_a_visitor_is_the_address_alone_so_a_changed_browser_is_the_same_visitor():
    assert stats.searcher(req(ua="Firefox")) == stats.searcher(req(ua="Chrome")) and stats.searcher(req()) != stats.searcher(req(ip="203.0.113.8"))


def test_an_ipv6_visitor_is_their_whole_64_bit_network_so_a_script_cannot_hop_addresses_inside_it():
    a, b = req(ip="2001:db8:1:2:aaaa::1"), req(ip="2001:db8:1:2:bbbb::9")
    assert stats.searcher(a) == stats.searcher(b) != stats.searcher(req(ip="2001:db8:1:3::1"))


def test_a_visitors_code_is_marked_salted_and_gone_with_the_day():
    who = stats.searcher(req())
    assert who.startswith(liteapi.VISITOR) and "203.0.113.7" not in who
    assert who != liteapi.VISITOR + hashlib.sha256(b"203.0.113.7").hexdigest()[:20]      # not the address's own hash: the day's random salt is in it
    stats.reset()
    assert stats.searcher(req()) != who                                                  # a new day (or a restart): nobody can match yesterday's code


# ---- the allowance ---------------------------------------------------------------------------------------------------------

def test_a_visitor_past_the_allowance_gets_no_call_and_the_next_visitor_still_searches(fake, monkeypatch):
    monkeypatch.setattr(liteapi, "PER_VISITOR_A_DAY", 2)
    one, two = stats.searcher(req()), stats.searcher(req(ip="198.51.100.4"))
    assert stays(family=one).ok and flights(family=one).ok and len(fake.asked) == 2
    over = stays(family=one, adults=3)
    assert over.status == liteapi.OVER and len(fake.asked) == 2 and liteapi.visitor_over(one)
    assert stays(family=two).ok and not liteapi.visitor_over(two)


def test_what_is_cached_is_free_for_a_visitor_past_the_allowance(fake, monkeypatch):
    monkeypatch.setattr(liteapi, "PER_VISITOR_A_DAY", 1)
    one, two = stats.searcher(req()), stats.searcher(req(ip="198.51.100.4"))
    assert stays(family=one).ok and liteapi.visitor_over(one)
    assert stays(family=one).ok and stays(family=two).ok and len(fake.asked) == 1      # the same search, kept: nobody is counted for it


def test_a_signed_in_family_keeps_its_own_budget_and_the_visitors_allowance_never_limits_it(fake, monkeypatch):
    monkeypatch.setattr(liteapi, "PER_VISITOR_A_DAY", 0)
    monkeypatch.setattr(liteapi, "PER_FAMILY_A_DAY", 2)
    assert stays(family="tenant-1").ok and flights(family="tenant-1").ok
    assert stays(family="tenant-1", adults=3).status == liteapi.OVER and not liteapi.visitor_over("tenant-1")
    assert stays(family=stats.searcher(req()), adults=4).status == liteapi.OVER      # a new search (the same one is kept, free)


def test_the_site_total_still_caps_visitors_and_that_is_not_the_visitors_own_limit(fake, monkeypatch):
    monkeypatch.setattr(liteapi, "A_DAY", 1)
    assert stays(family=stats.searcher(req())).ok
    other = stats.searcher(req(ip="198.51.100.4"))
    assert flights(family=other).status == liteapi.OVER and not liteapi.visitor_over(other)


def test_only_a_count_is_kept_under_a_salted_code_and_yesterdays_visitor_rows_go(fake):
    who = stats.searcher(req())
    with community.connect() as db:
        db.conn.execute(text("INSERT INTO liteapi_searches (day, family, n) VALUES ('2020-01-01', 'v:old', 3), ('2020-01-01', 'tenant-9', 3)"))
        db.conn.commit()
    assert stays(family=who).ok
    today = [r[1:] for r in rows() if r[0] != "2020-01-01"]
    old = [r[1:] for r in rows() if r[0] == "2020-01-01"]
    assert today == [(who, 1)] and old == [("tenant-9", 3)]      # a family's old row stays as it was; a visitor's old row is gone


# ---- the matrix, as a visitor sees it --------------------------------------------------------------------------------------

def test_a_visitor_past_the_allowance_is_told_calmly_with_a_way_on_and_nothing_is_asked_of_liteapi(real, client, monkeypatch):
    monkeypatch.setattr(liteapi, "PER_VISITOR_A_DAY", 2)
    assert at(client, "203.0.113.7")["s"] == tm.OK and len(real.asked) == 2      # a square is a flight search and a stay search
    over = at(client, "203.0.113.7", day="2026-12-13")
    assert over["s"] == tm.LIMIT and over["c"] is None and len(real.asked) == 2
    assert tm.SHORT[tm.LIMIT] in over["inner"]
    drawer = unescape(over["drawer"])
    assert tm.SAID[tm.LIMIT] in drawer and 'href="/signin?next=%2Fplan%2Fmatrix%3Fto%3DSan%2BDiego' in drawer and "Sign in to keep comparing" in drawer
    assert at(client, "198.51.100.4", day="2026-12-13")["s"] == tm.OK and len(real.asked) == 4      # another visitor still searches


def test_the_square_a_visitor_already_has_stays_theirs_and_everyones_past_the_allowance(real, client, monkeypatch):
    monkeypatch.setattr(liteapi, "PER_VISITOR_A_DAY", 2)
    cents = at(client, "203.0.113.7")["c"]
    assert at(client, "203.0.113.7")["c"] == cents and at(client, "198.51.100.4")["c"] == cents and len(real.asked) == 2


def test_a_visitors_tile_sets_no_cookie_for_it(real, client):
    r = client.get(f"{TILE}&lane=sandiego&w=2026-12-12", headers={"x-forwarded-for": "203.0.113.7"})
    assert r.status_code == 200 and "set-cookie" not in r.headers


def test_the_head_start_for_a_visitor_with_no_allowance_left_queues_nothing(real, client, monkeypatch):
    monkeypatch.setattr(liteapi, "PER_VISITOR_A_DAY", 0)
    r = client.post("/plan/matrix/warm?" + MATRIX.split("?")[1], headers={"x-forwarded-for": "203.0.113.7"})
    assert r.json() == {"queued": 0} and real.asked == []


def test_a_signed_in_family_is_not_limited_by_the_visitors_allowance(real, client, monkeypatch):
    monkeypatch.setattr(liteapi, "PER_VISITOR_A_DAY", 0)
    assert at(client, "203.0.113.7")["s"] == tm.LIMIT
    sign_in(client)
    assert at(client, "203.0.113.7")["s"] == tm.OK
    spent = rows()
    assert len(spent) == 1 and not spent[0][1].startswith(liteapi.VISITOR) and spent[0][2] == 2      # counted to the family, never to the visitor


def test_on_the_showcase_the_visitor_allowance_is_never_in_play(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    monkeypatch.setattr(liteapi, "PER_VISITOR_A_DAY", 0)
    j = at(client, "203.0.113.7")
    assert j["s"] == tm.OK and j["c"] > 0 and rows() == []
