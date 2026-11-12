"""F-222: the trip matrix's pages. /plan/matrix draws every place and start day the source already knows and a skeleton for the rest; /plan/matrix/tile answers one
square for the script; /plan/matrix/square is one square as a page (the panel, for a link and without the script); /plan/matrix/save keeps a square on the family's
trip ("Booking opens soon"), reading the price again. On the showcase the sample catalog drives it and says so; off it the pages exist only with LITEAPI_KEY."""
import json
import re
from datetime import date
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest

from gitaway import gridsource, liteapi, tripmatrix as tm
from gitaway.pages import tripmatrix as page
from tests.test_liteapi import KEY, Fake
from tests.test_signin import person, sign_in

MATRIX = "/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16&a=2&k=7,10&x=2"
KEYS = [f"{lane}|2026-12-{d}" for lane in ("sandiego", "losangeles", "orangecounty", "losangeles+sandiego", "orangecounty+sandiego") for d in (10, 11, 12, 13, 14)]


def squares(html):
    """{square key: (classes, inner text)} as drawn (a key appears twice: the laptop's lane and the phone's card; both must say the same)."""
    found = {}
    for attrs, body in re.findall(r'<a ([^>]*data-sq="[^"]+"[^>]*)>(.*?)</a>', html, re.S):
        k = re.search(r'data-sq="([^"]+)"', attrs).group(1)
        cls = set(re.search(r'class="([^"]+)"', attrs).group(1).split())
        inner = re.sub(r"<[^>]+>", "", re.search(r'<span class="mx-in">(.*?)</span>\s*$', body, re.S).group(1)).strip()
        assert found.get(k, (cls, inner)) == (cls, inner), k
        found[k] = (cls, unescape(inner))
    return found


def data(html):
    return json.loads(re.search(r'<script type="application/json" id="mx-data">(.*?)</script>', html, re.S).group(1))


@pytest.fixture
def sample(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    fake = Fake()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    return fake


def test_on_the_showcase_every_square_is_drawn_at_once_with_the_samples_marks(sample, client):
    html = client.get(MATRIX).text
    drawn = squares(html)
    assert sorted(drawn) == sorted(KEYS)
    lanes, windows = page.lanes_of(page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")), None
    s = page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    known = page.peek_all(s, page.lanes_of(s), page.windows_of(s))
    marks = tm.marks(page.lanes_of(s), page.windows_of(s), page.totals_of(known))
    for k, (cls, inner) in drawn.items():
        sq = known[k]
        assert inner == (tm.dollars(sq.cents) if sq.ok else tm.SHORT[sq.status])
        assert {c[3:] for c in cls if c in ("is-low", "is-find", "is-over")} == set(marks.get(k, ()))
    assert drawn["orangecounty|2026-12-12"][1] == "No sample"                         # a place the catalog lacks says so, in words
    assert "Sample prices" in html and page.SAMPLE_FINE in html
    assert 'id="mx-count-n">25</span>' in html and data(html)["known"]["sandiego|2026-12-12"]["c"] == known["sandiego|2026-12-12"].cents
    found = tm.find(page.lanes_of(s), page.windows_of(s), page.totals_of(known))
    if found:
        assert unescape(re.search(r'id="mx-find-w">([^<]+)<', html).group(1)) == found.words


def test_the_sentence_says_or_nearby_and_give_or_take_and_its_menus_are_links(sample, client):
    html = unescape(client.get(MATRIX).text)
    assert "SFO to San Diego or nearby," in html and "give or take 2 days," in html
    links = re.findall(r'href="(/plan/matrix\?[^"]+)"', html)
    words = [parse_qs(urlsplit(h).query) for h in links]
    assert any(w.get("nb") == ["0"] for w in words) and any(w.get("x") == ["0"] for w in words) and any(w.get("b") == ["3000"] for w in words)
    only = client.get(MATRIX + "&nb=0").text
    assert sorted(squares(only)) == [k for k in KEYS if k.startswith("sandiego|")]
    exact = client.get(MATRIX.replace("x=2", "x=0")).text
    assert sorted(squares(exact)) == sorted(k for k in KEYS if k.endswith("12-12"))


def test_a_retyped_sentence_lands_on_its_plain_address_or_says_what_is_missing(sample, client):
    r = client.get("/plan/matrix", params={"q": "A family of 4, SFO to San Diego, Dec 12 to 16 give or take 1 day, under $3,000"}, follow_redirects=False)
    assert r.status_code == 303
    q = parse_qs(urlsplit(r.headers["location"]).query)
    assert (q["to"], q["home"], q["d"], q["r"], q["x"], q["b"], q["k"]) == (["San Diego"], ["SFO"], ["2026-12-12"], ["2026-12-16"], ["1"], ["3000"], ["8,8"])
    html = client.get("/plan/matrix", params={"q": "to San Diego give or take a week"}).text
    assert "Say when" in unescape(html) and "Say give or take 0 to 3 days" in unescape(html)
    html = client.get("/plan/matrix", params={"q": "to Boise, Dec 12 to 16"}).text
    assert "does not know that place’s airport" in unescape(html) and 'id="mx-q-err"' in html      # said in the open retype box; the matrix it had stays


def test_a_squares_own_page_is_the_panel_with_every_part_and_booking_opens_soon(sample, client):
    html = unescape(client.get("/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=losangeles%2Bsandiego&w=2026-12-12").text)
    assert "Los Angeles + San Diego · Dec 12 to 16" in html and "2 nights each · a family of 4" in html
    assert "Booking opens soon." in html and "Save to trip" in html and "Back to the matrix" in html
    assert 'action="/plan/matrix/save"' in html and "Sample prices" in html
    assert "2 nights in Los Angeles" in html and "2 nights in San Diego" in html and "Airport drive" in html
    r = client.get("/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=nowhere&w=2026-12-12", follow_redirects=False)
    assert r.status_code == 303


def test_the_tile_answers_one_square_as_the_page_draws_it(sample, client):
    j = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-13").json()
    html = client.get(MATRIX).text
    assert j["key"] == "sandiego|2026-12-13" and j["s"] == tm.OK
    assert re.sub(r"<[^>]+>", "", j["inner"]) == squares(html)["sandiego|2026-12-13"][1]
    assert "Save to trip" in j["panel"] and j["c"] == data(html)["known"]["sandiego|2026-12-13"]["c"]
    assert client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2027-01-01").status_code == 404


def test_off_the_showcase_the_page_draws_skeletons_and_never_a_number_until_answers_land(real, client):
    html = client.get(MATRIX).text
    drawn = squares(html)
    assert sorted(drawn) == sorted(KEYS) and real.asked == []                     # the page itself never searches
    for cls, inner in drawn.values():
        assert "is-wait" in cls and "skeleton" in cls and inner == "Searching" and not re.search(r"\d", inner)
    assert 'id="mx-count-n">0</span>' in html and "Sample prices" not in html and page.FINE in html
    j = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").json()
    assert j["s"] == tm.OK and real.asked
    again = squares(client.get(MATRIX).text)
    assert "is-ok" in again["sandiego|2026-12-12"][0] and again["sandiego|2026-12-12"][1] == tm.dollars(j["c"])     # the server draws what it now has
    assert "is-wait" in again["losangeles|2026-12-12"][0]


def test_off_the_showcase_a_spent_budget_is_said_in_the_square(real, client, monkeypatch):
    monkeypatch.setattr(liteapi, "_spend", lambda family: False)
    j = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=losangeles&w=2026-12-12").json()
    assert j["s"] == tm.OVER and j["c"] is None and "Used up today" in j["inner"] and tm.SAID[tm.OVER] in unescape(j["panel"])


def test_off_the_showcase_without_a_home_airport_it_asks_and_searches_nothing(real, client):
    html = unescape(client.get(MATRIX.replace("home=SFO&", "")).text)
    assert "Say where you fly from" in html and "data-sq" not in html and real.asked == []


@pytest.mark.parametrize("path", ["/plan/matrix", "/plan/matrix/tile", "/plan/matrix/square", "/plan/grid"])
def test_off_the_showcase_without_a_key_the_pages_are_not_there_and_with_one_they_are(client, monkeypatch, path):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.delenv("LITEAPI_KEY", raising=False)
    assert client.get(path).status_code == 404
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "TRANSPORT", Fake())
    full = path + "?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12"
    assert client.get(full, follow_redirects=False).status_code == 200
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    monkeypatch.delenv("LITEAPI_KEY", raising=False)
    assert client.get(full, follow_redirects=False).status_code == 200


def test_save_keeps_the_square_on_the_familys_trip_with_the_price_read_again(sample, client):
    form = {**{k: v[0] for k, v in parse_qs(MATRIX.split("?")[1]).items()}, "lane": "losangeles+sandiego", "w": "2026-12-12"}
    r = client.post("/plan/matrix/save", data=form, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=")
    sign_in(client)
    r = client.post("/plan/matrix/save", data={**form, "total": "1"}, follow_redirects=False)
    assert r.status_code == 303 and "saved=1" in r.headers["location"]
    assert "Saved to your trip" in unescape(client.get(r.headers["location"]).text)
    s = page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    lane, w = tm.lane(s.place, "losangeles+sandiego"), tm.window(s.depart, s.return_, 2, date(2026, 9, 30), "2026-12-12")
    want = gridsource.square(lane, w, 2, (7, 10), "SFO").cents
    from gitaway import familydb, session as ses
    who = person()
    with ses.family(who) as fam:
        rows = familydb.rows(fam.db, "SELECT * FROM matrix_saves")
    assert [(x["lane"], x["depart"], x["return_"], x["total_cents"], x["sample"]) for x in rows] == [("Los Angeles + San Diego", "2026-12-12", "2026-12-16", want, 1)]
    client.post("/plan/matrix/save", data=form, follow_redirects=False)
    with ses.family(who) as fam:
        assert len(familydb.rows(fam.db, "SELECT * FROM matrix_saves")) == 1            # saved twice: one row
    j = client.post("/plan/matrix/save", data=form, headers={"X-Matrix": "1"}).json()
    assert j["saved"].startswith("Saved to your trip")


def test_each_place_wears_its_art_and_its_days_their_sky_with_the_credit(sample, client):
    from gitaway import placeart
    html = client.get(MATRIX).text
    assert html.count(placeart.art("sandiego")[:60]) >= 2                                     # the lane's thumb and the phone's card
    assert 'class="mx-art-i is-plain"' not in html.split('data-lane="sandiego"')[1].split("data-lane=")[0]
    skies = re.findall(r'class="mx-sky (?:is-fc|is-typ)[^"]*"', html)
    assert skies and all("is-typ" in c for c in skies)                                         # December is far: typical, dotted, never a forecast
    assert "not a forecast" in unescape(html)                                                 # the normals' line, said once under the calendar


def test_the_phone_cards_carry_the_weathers_credit_since_they_say_a_sky(sample, client):
    html = client.get(MATRIX).text
    cards = html.split('class="mx-cards"', 1)[1]
    assert "mx-c-sky" in cards and 'class="mx-wx"' in cards                   # AGENTS.md: a page showing weather shows weather.notes


def test_while_squares_wait_a_sourced_fact_about_the_place_sits_in_the_waiting_space(real, client):
    from gitaway import placefacts
    html = unescape(client.get(MATRIX).text)
    facts = placefacts.facts("sandiego")
    shown = next(f for f in facts if f.text in html)
    assert f'href="{shown.source}"' in html and 'class="mx-fact"' in html and page.SLOW in html
