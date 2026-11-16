"""The matrix v3 (F-275, docs/briefs/matrix-v3.md, D-860..): an obvious sentence with suggestion chips, a nights band that draws no labels across the rows, the side widgets
folded into chips that open into cards, and the opened square leading with the hotel. The hotel's data is the recorded Hilton answer (tests/fixtures/liteapi_hotel)."""
import re
from html import unescape
from urllib.parse import parse_qs, urlsplit

from gitaway import v2sentence
from gitaway.pages import tripmatrix as page
from tests.test_tripmatrix_page import MATRIX, spec

SPEC = lambda html: spec(html)      # noqa: E731


def page_html(client, url=MATRIX):
    r = client.get(url)
    assert r.status_code == 200
    return r.text


# ---- the sentence is obvious --------------------------------------------------------------------------------------------------------------------------------

def test_the_sentence_says_to_tap_a_word_and_every_word_is_a_picker_button(client):
    html = page_html(client)
    assert "Tap any word to change it" in html
    words = re.findall(r'<span role="button" tabindex="0" data-k="(\w+)" aria-haspopup="dialog" aria-expanded="false" aria-label="([^"]+)" class="v2-w">', html)
    assert [k for k, _ in words] == list(v2sentence.WORD_KEYS)
    assert dict(words)["nights"] == "How many nights: 4 nights"


def test_the_sentence_sits_on_its_own_opaque_card_with_the_suggestions_in_it(client):
    html = page_html(client)
    card = html.split('class="v2-qcard"', 1)[1].split('class="mx-results"', 1)[0]
    assert 'class="v2-sent"' in card and 'class="v2-sug"' in card and "Try" in card


# ---- the suggestion chips -----------------------------------------------------------------------------------------------------------------------------------

def _form(spec_):
    return {"to": spec_["to"], "home": spec_["home"], "d": spec_["depart"], "n": spec_["nights"], "a": spec_["adults"], "k": ",".join(map(str, spec_["kids"])),
            "x": spec_["flex"], "nb": "" if spec_["nearby"] else "0", "b": spec_["budget"] or ""}


def test_each_chip_is_the_sentence_with_one_word_changed_and_goes_through_address(client):
    html = page_html(client)
    sp = SPEC(html)
    chips = suggestions = v2sentence.suggestions(sp)
    labels = [c[0] for c in chips]
    assert "A week later" in labels and "From OAK" in labels and "3 nights" in labels and "Under $2,500" in labels
    assert any(label not in ("A week later", "From OAK", "3 nights", "Under $2,500") for label in labels)      # a different place
    by = dict(chips)
    week = parse_qs(urlsplit(by["A week later"]).query)
    assert (week["d"], week["r"]) == (["2026-12-19"], ["2026-12-23"]) and week["to"] == ["San Diego"]
    assert parse_qs(urlsplit(by["From OAK"]).query)["home"] == ["OAK"]
    assert parse_qs(urlsplit(by["3 nights"]).query)["r"] == ["2026-12-15"]
    assert parse_qs(urlsplit(by["Under $2,500"]).query)["b"] == ["2500"]
    assert by["A week later"] == v2sentence.address({**_form(sp), "d": "2026-12-19"})[0]      # the one place words become a search
    assert suggestions and all(href.startswith("/plan/matrix?") for _, href in chips)


def test_the_chips_on_the_page_are_links_with_those_addresses(client):
    html = page_html(client)
    found = re.findall(r'<a href="([^"]+)" class="v2-sug"[^>]*>(?:<svg.*?</svg>)?([^<]+)</a>', html, re.S)
    assert dict((unescape(label).strip(), unescape(href)) for href, label in found) == dict(v2sentence.suggestions(SPEC(html)))


def test_a_budget_already_said_offers_any_budget_and_no_chip_is_the_current_sentence(client):
    html = page_html(client, MATRIX + "&b=2000")
    chips = dict(v2sentence.suggestions(SPEC(html)))
    assert "Any budget" in chips and not [k for k in chips if k.startswith("Under")]
    assert parse_qs(urlsplit(chips["Any budget"]).query).get("b") is None
    assert page.href(page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2", "", "2000")) not in chips.values()


# ---- the hotel's page inside the opened square ----------------------------------------------------------------------------------------------------------------

import json as _json
from pathlib import Path as _Path

import pytest

from gitaway import liteapi
from gitaway.pages import hotelview
from tests.test_liteapi_hotel import FIX, Fake as HotelFake, ID, KEY
from tests.test_tripmatrix_page import real, sample  # noqa: F401 (fixtures)


@pytest.fixture
def hilton(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    f = HotelFake()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    return f


def test_the_fragment_has_the_photos_labelled_the_hotels_own_with_a_see_all_over_the_last(hilton):
    html = hotelview.to_xml(hotelview.fragment(ID))
    assert "The hotel’s own photos" in html and "See all 16 photos" in html
    assert html.count("data-lb=") == 16 and html.count("<img") >= 5      # every photo is in the page for the lightbox, only the mosaic's five load
    assert 'data-cap="Lobby"' in html and 'src="https://static.cupid.travel/hotels/490862440.jpg"' in html


def test_the_fragment_says_the_rating_the_ai_summary_and_what_guests_say_by_category(hilton):
    html = hotelview.to_xml(hotelview.fragment(ID))
    assert '<span class="dr-score num">7.6</span>' in html and "Good" in html and "6,263 reviews" in html
    assert "summary written by AI from the guest reviews" in html and "ai from" not in html
    assert "Cleanliness" in html and 'aria-label="Cleanliness 8 out of 10"' in html and "Overall reviewers frequently noted clean" in html
    assert "Maria" in html and "Group · Australia · 2026-11-14" in html and "8/10" in html
    docs = _json.loads((FIX / "reviews.json").read_text())["data"]
    bare = [r["name"] for r in docs if not (r.get("headline") or r.get("pros") or r.get("cons"))]
    assert bare and all(f">{n}<" not in html for n in bare)      # a score with no words is not a card
    assert f"Plus {len(bare)} score{'' if len(bare) == 1 else 's'} without words." in html and html.count("Plus ") == 1 and "Left a score" not in html


def test_the_hotels_facilities_check_in_and_rooms_with_their_photos_are_there(hilton):
    html = hotelview.to_xml(hotelview.fragment(ID))
    assert "Fitness facilities" in html and "All 24 amenities" in html and "Check-in from 04:00 PM" in html and "Check-out by 12:00 PM" in html
    assert "Rooms at this hotel" in html and "2 Double Hearing Accessible Room" in html and "Double bed · 30 m² · Sleeps 4" in html
    photos = _json.loads(unescape(re.search(r'class="dr-roomphotos"[^>]*>(.*?)</span>', html, re.S).group(1)))
    assert photos["2 double beds"].startswith("https://www.hilton.com/")


def test_a_review_is_text_never_markup(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    doc = _json.loads((FIX / "reviews.json").read_text())
    doc["data"][0].update(name="<script>alert(1)</script>", headline="<img src=x onerror=alert(2)>", pros="<b>great</b>", cons="a & b")
    monkeypatch.setattr(liteapi, "TRANSPORT", HotelFake(reviews=_json.dumps(doc).encode()))
    html = hotelview.to_xml(hotelview.fragment("lpx1"))
    assert "<script>" not in html and "<img src=x" not in html and "<b>great</b>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html and "&lt;img src=x onerror=alert(2)&gt;" in html and "a &amp; b" in html


def test_the_route_answers_the_fragment_and_nothing_for_a_hotel_it_does_not_have(real, client, monkeypatch):
    monkeypatch.setattr(liteapi, "TRANSPORT", HotelFake())
    got = client.get(f"/plan/matrix/hotel?id={hotelview.token(ID)}").json()["html"]
    assert "7.6" in got and "The hotel’s own photos" in got
    monkeypatch.setattr(liteapi, "TRANSPORT", HotelFake(status=404))
    assert client.get(f"/plan/matrix/hotel?id={hotelview.token('lpnone')}").json() == {"html": ""}
    assert client.get("/plan/matrix/hotel?id=../x").json() == {"html": ""}


def test_an_id_the_server_did_not_draw_is_nothing_and_spends_nobodys_allowance(real, client, monkeypatch):
    f = HotelFake()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    before = liteapi.searches_today()
    for made_up in (ID, f"{ID}.deadbeef", hotelview.token("lpother").replace("lpother", ID), "lp1.", ".x", "../x"):
        assert client.get("/plan/matrix/hotel", params={"id": made_up}).json() == {"html": ""}, made_up
    assert f.asked == [] and liteapi.searches_today() == before
    assert hotelview.unsign(hotelview.token(ID)) == ID and hotelview.unsign(hotelview.token(ID) + "0") == ""


def test_a_live_squares_drawer_has_a_slot_for_each_hotel_and_no_hotel_call_is_made_by_drawing_it(real, client):
    from gitaway import gridsource
    from gitaway.pages import v2drawer
    s = page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    lane, w = page.lanes_of(s)[0], page.windows_of(s)[2]
    sq = gridsource.square(lane, w, s.adults, s.kid_ages, s.home, "")
    assert sq.ok and sq.stays[0].hotel_id
    html = hotelview.to_xml(v2drawer.drawer(s, lane, w, sq))
    assert f'data-hid="{hotelview.token(sq.stays[0].hotel_id)}"' in html and 'data-state="idle"' in html
    assert not [u for u in real.asked if "/data/" in u[0]]      # nothing asked for the hotel's photos until the script asks


def test_the_showcase_shows_sample_photos_said_to_be_samples_and_never_a_review(sample, client):
    j = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").json()["drawer"]
    assert "Sample photo · Hotel lobby" in j and "/assets/photos/lobby-front-desk.jpg" in j
    assert "dr-rich" not in j and "dr-rev" not in j and j.index("Sample photo") < j.index("Illustration")      # the place's own drawing stays, labelled an illustration, after them


# ---- flights: the +1 ----------------------------------------------------------------------------------------------------------------------------------------

def test_a_flight_that_lands_the_next_day_says_plus_one_in_its_row_and_in_its_summary():
    from gitaway import tripmatrix as tm
    from gitaway.pages import v2drawer
    leg = "Sat, Dec 19 · SFO 11:30 PM → LAX 12:45 AM next day · Nonstop"
    row = hotelview.to_xml(v2drawer._leg("Out", "Sat, Dec 19", leg, "Alaska"))
    assert 'class="dr-p1"' in row and ">+1</sup>" in row and "12:45 AM" in row and "Nonstop" in row
    f = tm.FlightPart("Alaska", leg, "Wed, Dec 23 · LAX 6:40 PM → SFO 8:05 PM · Nonstop", 0, 50_000)
    assert v2drawer._flight_times(f) == "11:30 PM out · 6:40 PM back"
    assert v2drawer._plus(v2drawer.times(leg)) == "SFO 11:30 PM → LAX 12:45 AM +1"


# ---- the nights band and the rail ---------------------------------------------------------------------------------------------------------------------------

def test_the_rail_is_a_row_of_chips_each_asking_for_its_card_when_tapped(sample, client):
    html = unescape(client.get("/plan/matrix/rail?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").json()["html"])
    chips = re.findall(r'<button type="button" aria-expanded="false" aria-controls="wg-(\w+)" data-wg="(\w+)" class="wchip v2-glass">.*?<span>([^<]+)</span></button>', html, re.S)
    names = [c for _, _, c in chips]
    assert "Weather" in names and "Where you will be" in names and "About San Diego" in names      # the labels cost nothing: no temperature, no minutes until tapped
    assert any(c.startswith("Uber") and c.endswith("sample") for c in names)
    assert all(a == b for a, b, _ in chips) and 'id="wg-' not in html      # no card is drawn with the row
    got = client.get("/plan/matrix/rail?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12&wg=about").json()["card"]
    assert 'id="wg-about"' in got and "About San Diego" in got


# ---- the sky line: never a zero count -----------------------------------------------------------------------------------------------------------------------

def _days(kinds, kind="normal", high=40):
    from datetime import date
    from types import SimpleNamespace
    return [SimpleNamespace(date=date(2027, 1, 15 + i), kind=kind, condition=c, high_f=high) for i, c in enumerate(kinds)]


def test_the_sky_line_counts_sunny_days_only_when_there_are_some_and_else_says_what_is_typical():
    from gitaway.pages import v2drawer
    assert v2drawer.sky_words(_days(["sun", "sun", "cloud", "sun"], high=66)) == "3 of 4 days typically sunny"
    assert v2drawer.sky_words(_days(["snow", "snow", "cloud", "snow"], high=40)) == "Typically snowy · 40°"
    assert v2drawer.sky_words(_days(["cloud", "rain", "rain"], kind="forecast", high=51)) == "Rainy · 51°"
    assert "0 of" not in v2drawer.sky_words(_days(["snow"] * 4))
