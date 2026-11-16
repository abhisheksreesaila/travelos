"""F-222: the trip matrix's pages. /plan/matrix draws every place and start day the source already knows and a skeleton for the rest; /plan/matrix/tile answers one
square for the script; /plan/matrix/square is one square as a page (the panel, for a link and without the script); /plan/matrix/save keeps a square on the family's
trip, reading the price again. On the showcase the sample catalog drives it and says so; off it the pages exist only with LITEAPI_KEY."""
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
    """{square key: (classes, inner text)} as drawn (one square a key: the grid is the same at every width)."""
    found = {}
    for attrs, body in re.findall(r'<a ([^>]*data-sq="[^"]+"[^>]*)>(.*?)</a>', html, re.S):
        k = re.search(r'data-sq="([^"]+)"', attrs).group(1)
        cls = set(re.search(r'class="([^"]+)"', attrs).group(1).split())
        inner = re.sub(r"<[^>]+>", "", re.search(r'<span class="mx-in">(.*?)</span>\s*$', body, re.S).group(1)).strip()
        assert found.get(k, (cls, inner)) == (cls, inner), k
        found[k] = (cls, unescape(inner))
    return found


def lane_html(html, key):
    """What one laptop lane draws: from its opening tag to the next lane's."""
    return html.split(f'data-lane="{key}" class="mx-lane', 1)[1].split('data-lane="', 1)[0]


def spec(html):
    return json.loads(re.search(r'<script type="application/json" id="v2-data">(.*?)</script>', html, re.S).group(1))


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


def test_every_square_is_drawn_as_a_skeleton_and_the_tile_fills_it_with_the_samples_answer(sample, client):
    """F-250: the page never prices from the server's side: every square starts as a skeleton ("Pricing 0 of 25 trips") and fills from the tile endpoint like a map tile; on the
    showcase each tile answers the sample catalog, never "No sample"."""
    html = client.get(MATRIX).text
    drawn = squares(html)
    assert sorted(drawn) == sorted(KEYS)
    assert all("is-wait" in cls and inner == "Searching" for cls, inner in drawn.values())
    assert 'id="mx-count-n" class="num">0</b>' in html and "of 25 trips" in html and "Sample prices" in html and page.SAMPLE_FINE in html
    assert data(html)["known"] == {}
    s = page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    known = page.peek_all(s, page.lanes_of(s), page.windows_of(s))
    for k in KEYS:
        lane, w = k.split("|")
        j = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + f"&lane={lane.replace('+', '%2B')}&w={w}").json()
        assert j["c"] == known[k].cents and j["s"] == tm.OK and j["inner"] == f'<span class="mx-v">{tm.dollars(known[k].cents)}</span>', k


def test_the_sentence_is_the_pickers_words_for_the_address(sample, client):
    """F-250: the sentence on the results is the landing's (no menus of links): each word says what the address says, and the spec the script runs on carries the options."""
    html = unescape(client.get(MATRIX).text)
    words = [re.sub(r"<[^>]+>", "", t) for t in re.findall(r'<span[^>]*class="v2-w"[^>]*>.*?</span>', html)]
    assert words == ["A family of 4", "SFO", "San Diego, or nearby", "Sat, Dec 12", "give or take 2 days", "4 nights", "any budget", "anything"]
    assert "$2,300" in unescape(client.get(MATRIX + "&b=2300").text)
    only = client.get(MATRIX + "&nb=0").text
    assert sorted(squares(only)) == [k for k in KEYS if k.startswith("sandiego|")] and "San Diego</span>" in only
    exact = client.get(MATRIX.replace("x=2", "x=0")).text
    assert sorted(squares(exact)) == sorted(k for k in KEYS if k.endswith("12-12"))


def test_a_retyped_sentence_lands_on_its_plain_address_or_says_what_is_missing(sample, client):
    r = client.get("/plan/matrix", params={"q": "A family of 4, SFO to San Diego, Dec 12 to 16 give or take 1 day, under $3,000"}, follow_redirects=False)
    assert r.status_code == 303
    q = parse_qs(urlsplit(r.headers["location"]).query)
    assert (q["to"], q["home"], q["d"], q["r"], q["x"], q["b"], q["k"]) == (["San Diego"], ["SFO"], ["2026-12-12"], ["2026-12-16"], ["1"], ["3000"], ["8,8"])
    html = client.get("/plan/matrix", params={"q": "to San Diego give or take a week"}).text
    assert "Say when" in unescape(html) and "Say give or take 0 to 3 days" in unescape(html) and 'id="v2-error"' in html
    html = client.get("/plan/matrix", params={"q": "to Boise, Dec 12 to 16"}).text
    assert "does not know that place’s airport" in unescape(html) and 'id="v2-error"' in html      # said under the sentence; the matrix it had stays


def test_a_squares_own_page_is_the_panel_with_every_part_and_a_sample_booking(sample, client):
    html = unescape(client.get("/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=losangeles%2Bsandiego&w=2026-12-12").text)
    assert "Los Angeles + San Diego" in html and "Sat, Dec 12 → Wed, Dec 16 · 4 nights · 2 adults, 2 kids" in html
    assert "Sample booking: nothing is booked or charged." in html and "Book my trip" in html and 'action="/plan/matrix/book"' in html and "Save to trip" in html and "Back to the matrix" in html
    assert 'action="/plan/matrix/save"' in html and "Sample prices" in html
    assert "Los Angeles · 2 nights" in html and "San Diego · 2 nights" in html and "min from the airport" in html
    r = client.get("/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=nowhere&w=2026-12-12", follow_redirects=False)
    assert r.status_code == 303


def test_the_tile_answers_one_square_with_its_words_its_panel_and_its_estimate_inputs(sample, client):
    j = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-13").json()
    s = page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    sq = page.peek_all(s, page.lanes_of(s), page.windows_of(s))["sandiego|2026-12-13"]
    assert j["key"] == "sandiego|2026-12-13" and j["s"] == tm.OK and j["c"] == sq.cents
    assert re.sub(r"<[^>]+>", "", j["inner"]) == tm.dollars(sq.cents) and j["label"].endswith("for the whole trip")
    assert j["e"] == [sq.flight.cents, round(sq.stays[0].cents / 4)]
    assert "Save to trip" in j["drawer"]
    assert client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2027-01-01").status_code == 404


def test_off_the_showcase_the_page_draws_skeletons_and_never_a_number_until_answers_land(real, client):
    html = client.get(MATRIX).text
    drawn = squares(html)
    assert sorted(drawn) == sorted(KEYS) and real.asked == []                     # the page itself never searches
    for cls, inner in drawn.values():
        assert "is-wait" in cls and "skeleton" in cls and inner == "Searching" and not re.search(r"\d", inner)
    assert 'id="mx-count-n" class="num">0</b>' in html and "Sample prices" not in html and page.FINE in html
    j = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").json()
    assert j["s"] == tm.OK and real.asked


def test_off_the_showcase_a_spent_budget_is_said_in_the_square(real, client, monkeypatch):
    monkeypatch.setattr(liteapi, "_spend", lambda family: False)
    j = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=losangeles&w=2026-12-12").json()
    assert j["s"] == tm.OVER and j["c"] is None and "Used up today" in j["inner"] and tm.SAID[tm.OVER] in unescape(j["drawer"])


def test_off_the_showcase_without_a_home_airport_it_asks_and_searches_nothing(real, client):
    html = unescape(client.get(MATRIX.replace("home=SFO&", "")).text)
    assert "Say where you fly from" in html and "data-sq" not in html and real.asked == []


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
    assert j["saved"].startswith("Saved to your trip") and j["next"] == "Plan this trip" and j["trip"] == "/trip/plan"      # F-269: a sample square books nothing real


def test_each_place_wears_its_art_and_each_square_its_start_days_sky_above_the_total(sample, client):
    """F-250 (the prototype): every square carries its start day's weather above its total (icon and high); typical weather is dotted and said so in the head cell and the
    ⓘ, never passed off as a forecast. A place with no weather known draws none."""
    from gitaway import placeart
    from gitaway.pages.skystrip import weather_for
    html = client.get(MATRIX).text
    assert html.count(placeart.art("sandiego")[:60]) >= 1 and 'class="mx-art-i is-plain"' not in html.split('data-lane="sandiego"')[1].split("data-lane=")[0]
    tw = {p: weather_for(p, date(2026, 12, 10), date(2026, 12, 14)) for p in ("San Diego", "Los Angeles", "Orange County")}
    for attrs, body in re.findall(r'<a ([^>]*data-sq="[^"]+"[^>]*)>(.*?)</a>', html, re.S):
        k = re.search(r'data-sq="([^"]+)"', attrs).group(1)
        lane, start = k.split("|")
        first = {"sandiego": "San Diego", "losangeles": "Los Angeles", "orangecounty": "Orange County"}[lane.split("+")[0]]
        day = next((d for d in tw[first].days if d and d.date.isoformat() == start), None)
        wx = re.search(r'<span [^>]*class="mx-sqw (is-typ|is-fc)[^"]*"[^>]*>(.*?)</span>\s*<span class="mx-in">', body, re.S)
        if day is None:                                                                       # no weather known for the place (Orange County has no normals): none drawn
            assert wx is None and "mx-sqw" not in body, k
            continue
        assert wx and wx.group(1) == "is-typ" and f"{day.high_f}°" in re.sub(r"<[^>]+>", "", wx.group(2)), k
    assert "Sky: typical, not a forecast yet" in unescape(html) and "not a forecast" in unescape(html.split('data-pop="about"', 1)[1])


def test_each_lane_rings_its_nights_on_the_asked_start_and_the_head_has_a_column_per_start_day(sample, client):
    """F-250: the band starts on the asked start (the script moves it to the find or the cheapest as answers land), spans as many start columns as the trip has nights (as far as
    the grid goes), says its nights on its edge, and the square under it is the one ringed; the head names every start day."""
    html = client.get(MATRIX).text
    s = page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    lanes = page.lanes_of(s)
    for x in lanes:
        lane = lane_html(html, x.key)
        band = re.search(r'<div [^>]*data-band="[^"]+"[^>]*>', lane).group(0)
        assert "grid-column: 4 / span 3" in band and 'data-l="4 nights"' in band                 # the third of five start days; four nights, but only three columns are left
        ons = re.findall(r'<a [^>]*data-sq="([^"]+)"[^>]*class="[^"]*\bis-on\b|<a [^>]*class="[^"]*\bis-on\b[^"]*"[^>]*data-sq="([^"]+)"', lane)
        assert [a or b for a, b in ons] == [tm.key(x.key, "2026-12-12")], x.key
    head = html.split('class="mx-head"', 1)[1].split("data-lane=", 1)[0]
    assert re.findall(r'data-day="(2026-12-\d\d)"', head) == [f"2026-12-{d}" for d in (10, 11, 12, 13, 14)]


def test_the_weathers_credit_and_labels_are_one_tap_away_in_about_these_prices(sample, client):
    """F-238 (D-540, kept in F-250): one quiet control holds the weather's credit (AGENTS.md: a page showing weather shows weather.notes), the sample fine print, Privacy and
    Terms and the one light/dark button; the legend is drawn in the card; the site footer is not drawn on the matrix."""
    html = client.get(MATRIX).text
    assert html.count('class="mx-wx"') == 1 and html.count('class="mx-legend"') == 1 and 'class="lg"' in html
    about = html.split('data-pop="about"', 1)[1].split("</details>", 1)[0]
    assert "About these prices" in about.split("</summary>", 1)[0] and 'class="mx-wx"' in about
    assert "NOAA" in about and "not a forecast" in about and page.SAMPLE_FINE in about and "ringed" in about
    assert 'href="/privacy"' in about and 'href="/terms"' in about and "ga-footer" not in html
    assert html.count("data-mode-toggle") == 2 and 'data-mode-toggle="1"' in about               # the top bar's round button, and the one here (the footer's old place)


def test_the_matrix_says_nothing_twice_no_route_under_every_lane_and_the_sample_label_is_the_top_bars(sample, client):
    """F-238 (D-541): the route is in the sentence; the sample label is the page's one badge (the top bar's)."""
    html = client.get(MATRIX).text
    assert 'class="mx-l-s"' not in html and "SFO → LAX" not in html.split('id="mx-side"', 1)[0]
    assert html.count("Sample prices") == 2 and html.count('class="v2-pill"') == 1 and "mx-sample" not in html      # the pill, and the about's fine print says "Sample prices from ..."


def test_while_squares_wait_a_sourced_fact_floats_in_a_small_note_not_a_band(real, client):
    """F-230: the fact is a floating island the script shows while the first squares load (drawn hidden: without the script nothing loads)."""
    from gitaway import placefacts
    html = unescape(client.get(MATRIX).text)
    facts = placefacts.facts("sandiego")
    shown = next(f for f in facts if f.text in html)
    isle = re.search(r'<aside [^>]*id="mx-fact"[^>]*>.*?</aside>', html, re.S).group(0)
    assert shown.text in isle and f'href="{shown.source}"' in isle and "While we search" in isle
    assert 'class="mx-isle is-gone"' in isle and 'aria-hidden="true"' in isle
    news = re.search(r'<div [^>]*id="mx-news"[^>]*>.*?</div>\s*<div class="mx-stage', html, re.S)
    assert news is None or shown.text not in news.group(0)                                  # no longer a band across the page
    assert page.SLOW in html


def nav_plan(html):
    return (re.search(r'<nav [^>]*class="ga-nav"[^>]*>.*?</nav>', html, re.S) or re.search(r'<nav [^>]*class="v2-sections[^"]*"[^>]*>.*?</nav>', html, re.S)).group(0)      # F-255: the v2 bar's sections pill


def test_plan_a_trip_is_the_matrix_where_it_exists_and_the_import_where_it_does_not(client, monkeypatch):
    """D-461, D-463, D-761: signed in or not, it is the matrix, or off the showcase with no LiteAPI key, the import of a trip already booked."""
    for showcase, key, signed_in, want in (("0", None, False, "/trips/import"), ("0", KEY, False, "/plan/ask"), ("1", None, False, "/plan/ask"),
                                           ("0", None, True, "/trips/import"), ("0", KEY, True, "/plan/ask"), ("1", None, True, "/plan/ask")):
        monkeypatch.setenv("GITAWAY_SHOWCASE", showcase)
        if key:
            monkeypatch.setenv("LITEAPI_KEY", key)
        else:
            monkeypatch.delenv("LITEAPI_KEY", raising=False)
        if signed_in:
            sign_in(client)
        nav = nav_plan(client.get("/community").text)
        assert re.search(rf'href="{want}"[^>]*>(Plan a trip|Book)<', nav), (showcase, key, signed_in)      # F-255: a visitor's pill says Plan a trip, a family's says Book; the same one door


def test_off_the_showcase_the_bare_matrix_asks_where_you_fly_from_and_searches_nothing(real, client):
    html = unescape(client.get("/plan/matrix").text)
    assert "Say where you fly from" in html and "data-sq" not in html and real.asked == []


def test_on_the_showcase_a_nearby_place_without_a_sample_is_not_a_lane(sample):
    """F-236: San Francisco's nearby places (Napa, Monterey) have no sample: their rows would say "No sample" in every square, so they are not drawn; the asked place stays."""
    s = page.state("San Francisco", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    assert [x.key for x in page.lanes_of(s)] == ["sanfrancisco"]
    sd = page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    assert [x.key for x in page.lanes_of(sd)] == ["sandiego", "losangeles", "orangecounty", "losangeles+sandiego", "orangecounty+sandiego"]


# ---- F-237: change the nights right on the matrix ------------------------------------------------------------------------

def test_nights_is_a_word_of_the_sentence_and_its_picker_is_one_slider_two_to_seven(sample, client):
    """F-250: "4 nights" is a word like the others; its picker (built by assets/js/v2.js from the spec) is the only slider, two to seven nights."""
    html = client.get(MATRIX).text
    assert 'data-k="nights"' in html and ">4 nights</span>" in html and 'type="range"' not in html
    assert spec(html)["limits"]["nights"] == [2, 7] and spec(html)["nights"] == 4


def test_a_trip_already_longer_in_the_address_widens_the_slider_to_hold_it(sample, client):
    html = client.get(MATRIX.replace("r=2026-12-16", "r=2026-12-22")).text
    assert spec(html)["limits"]["nights"] == [2, 10] and spec(html)["nights"] == 10
    d = data(html)
    assert (d["nights"], d["lo"], d["hi"]) == (10, 2, 10) and d["returns"]["10"] == "2026-12-22"


def test_the_page_data_says_every_nights_trip_its_last_day_and_its_words(sample, client):
    d = data(client.get(MATRIX).text)
    assert (d["nights"], d["lo"], d["hi"]) == (4, 2, 7)
    assert d["returns"] == {str(n): f"2026-12-{12 + n}" for n in range(2, 8)}
    assert [w["when"] for w in d["windows"]] == ["Dec 10 to 14", "Dec 11 to 15", "Dec 12 to 16", "Dec 13 to 17", "Dec 14 to 18"]
    assert d["whens"]["6"] == ["Dec 10 to 16", "Dec 11 to 17", "Dec 12 to 18", "Dec 13 to 19", "Dec 14 to 20"]
    assert "days" not in d and "nlast" not in d      # one column a start day: the calendar of every day is gone


def test_the_head_has_one_column_a_start_day_with_its_weekday_and_the_weekend_tinted(sample, client):
    head = client.get(MATRIX).text.split('class="mx-head"', 1)[1].split("data-lane=", 1)[0]
    cells = re.findall(r'<div data-day="(2026-12-\d\d)" class="(mx-day[^"]*)"[^>]*>(.*?)</div>', head, re.S)
    assert [(d, "".join(re.sub(r"<[^>]+>", "", t).split())) for d, _, t in cells] == [("2026-12-10", "DecThu10"), ("2026-12-11", "Fri11"), ("2026-12-12", "Sat12"), ("2026-12-13", "Sun13"), ("2026-12-14", "Mon14")]
    assert [("is-wkend" in c) for _, c, _ in cells] == [False, False, True, True, False] and [("is-ask" in c) for _, c, _ in cells] == [False, False, True, False, False]


def test_a_square_says_its_estimate_inputs_the_flight_and_each_stays_nightly_rate(sample, client):
    s = page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    known = page.peek_all(s, page.lanes_of(s), page.windows_of(s))
    sq, combo = known["sandiego|2026-12-12"], known["losangeles+sandiego|2026-12-12"]
    j = client.get("/plan/matrix/peek?" + MATRIX.split("?")[1]).json()["known"]
    assert j["sandiego|2026-12-12"]["e"] == [sq.flight.cents, round(sq.stays[0].cents / 4)]
    assert j["losangeles+sandiego|2026-12-12"]["e"] == [combo.flight.cents, round(combo.stays[0].cents / 2), round(combo.stays[1].cents / 2)]
    assert j["sandiego|2026-12-12"]["inner"] == f'<span class="mx-v">{tm.dollars(sq.cents)}</span>' and j["sandiego|2026-12-12"]["label"].endswith("for the whole trip")


def test_peek_answers_every_square_the_showcase_knows_for_other_nights(sample, client):
    q = MATRIX.split("?")[1]
    j = client.get("/plan/matrix/peek?" + q.replace("r=2026-12-16", "r=2026-12-18")).json()["known"]
    assert sorted(j) == sorted(KEYS)
    four = client.get("/plan/matrix/peek?" + q).json()["known"]
    assert j["sandiego|2026-12-12"]["c"] != four["sandiego|2026-12-12"]["c"]        # six nights cost more than four
    assert j["sandiego|2026-12-12"]["label"].startswith("San Diego, Dec 12 to 18:")


def test_off_the_showcase_peek_reads_only_the_cache_and_never_searches(real, client):
    q = MATRIX.split("?")[1]
    first = client.get("/plan/matrix/peek?" + q).json()
    assert first == {"known": {}} and real.asked == []
    client.get("/plan/matrix/tile?" + q + "&lane=sandiego&w=2026-12-12")
    asked = len(real.asked)
    assert asked
    again = client.get("/plan/matrix/peek?" + q).json()["known"]
    assert list(again) == ["sandiego|2026-12-12"] and len(real.asked) == asked                      # the answer came from the cache
    other = client.get("/plan/matrix/peek?" + q.replace("r=2026-12-16", "r=2026-12-18")).json()
    assert other == {"known": {}} and len(real.asked) == asked                                     # other nights: not known, not searched
    assert client.get("/plan/matrix/peek?to=Nowhere+Land").status_code == 400


def test_the_tile_carries_the_estimate_inputs_too(sample, client):
    j = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-13").json()
    assert j["e"] == client.get("/plan/matrix/peek?" + MATRIX.split("?")[1]).json()["known"]["sandiego|2026-12-13"]["e"] and len(j["e"]) == 2


# ---- F-238 review: MET Norway's credit beside a forecast --------------------------------------------------------------------

def test_a_forecast_day_on_screen_shows_met_norways_credit_a_typical_one_does_not(sample, client, monkeypatch):
    """CC BY 4.0 asks for appropriate credit, a link to the licence and a note of changes, "in any reasonable manner" (D-540). weather.py promises the credit wherever a forecast
    shows, so a matrix with a forecast day shows one small visible, linked line; typical weather alone shows none (its NOAA label is in the days and the ⓘ)."""
    from gitaway import weather
    from gitaway.pages import tripmatrix as page
    assert 'class="mx-credit"' not in client.get(MATRIX).text
    real = page.skies_of

    def forecast(lanes, windows):
        out = real(lanes, windows)
        return {n: weather.TripWeather(tuple(weather.Day(d.date, weather.FORECAST, d.high_f, d.low_f, d.condition, d.word, precip_in=0, wind_mph=5) if d else None for d in tw.days),
                                       place=tw.place, updated="6:10 AM") for n, tw in out.items()}
    monkeypatch.setattr(page, "skies_of", forecast)
    html = client.get(MATRIX).text
    line = re.search(r'<p class="mx-credit">(.*?)</p>', html, re.S).group(1)
    assert "based on data from MET Norway" in line and 'href="https://docs.api.met.no/doc/License"' in line and "updated 6:10 AM" in line
