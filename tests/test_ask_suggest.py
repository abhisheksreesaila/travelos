"""F-257: the landing's search box. What the autocomplete offers (gitaway/asksuggest.py, GET /plan/ask/suggest) and how the box's sentence becomes the matrix's search."""
from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest

from gitaway import asksuggest, catalog
from gitaway.partners import places
from tests.test_signin import sign_in

TODAY = date(2026, 11, 15)


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(catalog, "today", lambda: TODAY)


def labels(r, kind=None):
    return [i["label"] for i in r["items"] if kind in (None, i["kind"])]


def test_an_empty_box_offers_the_popular_places():
    assert labels(asksuggest.suggest("", "SFO")) == ["San Diego", "Los Angeles", "New York", "Honolulu"]
    # the showcase's sample catalog prices only some places: Lake Tahoe, Las Vegas and Orlando are offered only where a real source prices them


def test_typing_offers_the_known_places_that_begin_that_way():
    assert labels(asksuggest.suggest("san", "SFO")) == ["San Diego", "Santa Barbara", "Los Angeles"]      # the last by its alias, Santa Monica
    assert labels(asksuggest.suggest("los", "SFO")) == ["Los Angeles"]


def test_a_word_inside_a_name_matches_too():
    assert labels(asksuggest.suggest("barbara", "SFO")) == ["Santa Barbara"]
    assert labels(asksuggest.suggest("diego", "SFO")) == ["San Diego"]


def test_where_a_real_source_prices_every_known_place_is_offered(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert labels(asksuggest.suggest("tah", "SFO")) == ["Tahoe City", "Lake Tahoe"]
    assert asksuggest.suggest("vegas", "SFO")["items"][0]["text"] == "Las Vegas · a family of 4"      # an alias is the place


def test_an_unknown_place_is_never_guessed_into_one():
    assert asksuggest.suggest("Narnia", "SFO") == {"items": [], "say": "We don't know that place yet."}
    assert asksuggest.suggest("xyz in december", "SFO")["say"] == "We don't know that place yet."


def test_a_whole_place_offers_who_and_when_as_one_readable_sentence():
    r = asksuggest.suggest("san diego", "SFO")
    assert labels(r, "party") == ["a family of 4", "2 adults", "just me"]
    assert r["items"][0]["text"] == "San Diego · a family of 4"
    assert labels(asksuggest.suggest("San Diego · a family of 4", "SFO"), "when") == ["Dec 19–23", "Dec 26–30", "Jan 2–6", "Jan 9–13"]


def test_picking_the_party_then_the_days_makes_a_sentence_the_reader_can_read():
    when = [i for i in asksuggest.suggest("San Diego · a family of 4", "SFO")["items"] if i["kind"] == "when"][0]
    assert when["text"] == "San Diego · a family of 4 · Dec 19–23"
    to, problem = asksuggest.search(when["text"], "SFO")
    q = parse_qs(urlsplit(to).query)
    assert problem == "" and q["to"] == ["San Diego"] and q["d"] == ["2026-12-19"] and q["r"] == ["2026-12-23"] and q["a"] == ["2"] and q["k"] == ["8,8"]


def test_a_day_typed_offers_its_nights():
    assert labels(asksuggest.suggest("San Diego · Dec 12", "SFO"), "when") == ["Dec 12–15", "Dec 12–16", "Dec 12–17", "Dec 12 for 3 nights", "Dec 12 for 4 nights", "Dec 12 for 5 nights"]
    assert asksuggest.search("San Diego · Dec 12 for 4 nights", "SFO")[1] == ""


def test_a_half_typed_part_narrows_the_completions():
    assert labels(asksuggest.suggest("San Diego · a fam", "SFO")) == ["a family of 4"]


def test_free_typing_reads_like_the_chips_do():
    to, problem = asksuggest.search("san diego, 2 adults, Dec 12 to 16", "SFO")
    q = parse_qs(urlsplit(to).query)
    assert problem == "" and q["d"] == ["2026-12-12"] and q["r"] == ["2026-12-16"] and q["a"] == ["2"] and "k" not in q


@pytest.mark.parametrize("text,problem", [
    ("", "Say where you would like to go."),
    ("Narnia", "We don't know that place yet."),
    ("San Diego", "Say when, like “Dec 12 to 16”."),
    ("San Diego · 2 adults", "Say when, like “Dec 12 to 16”."),
])
def test_a_search_that_cannot_run_says_why_in_words(text, problem):
    assert asksuggest.search(text, "SFO") == ("", problem)


def test_without_a_home_airport_it_can_be_said_in_the_box():
    assert labels(asksuggest.suggest("San Diego · a family of 4 · Dec 19–23", home=""), "from") == ["from SFO", "from OAK", "from SJC"]
    to, problem = asksuggest.search("San Diego · 2 adults · Dec 12–16 · from OAK", "")
    assert problem == "" and parse_qs(urlsplit(to).query)["home"] == ["OAK"]


def test_the_boxs_text_for_a_link_in():
    assert asksuggest.box_text("San Diego") == "San Diego"
    assert asksuggest.box_text("San Diego", date(2026, 12, 12), date(2026, 12, 16), 2, 2) == "San Diego · a family of 4 · Dec 12–16"


def test_places_matching_and_lead():
    assert [p.name for p in places.matching("tah")] == ["Tahoe City", "Lake Tahoe"]
    assert places.matching("zzz") == () and places.matching("") == ()
    p, rest = places.lead("las vegas in dec")
    assert (p.name, rest) == ("Las Vegas", "in dec")
    assert places.lead("la")[0].name == "Los Angeles" and places.lead("lake tahoe, 2 adults")[1] == "2 adults"
    assert places.lead("lax") is None


def test_the_suggest_route_returns_the_same_words(client):
    sign_in(client, "ari")
    r = client.get("/plan/ask/suggest", params={"q": "san"})
    assert r.status_code == 200 and [i["label"] for i in r.json()["items"]] == ["San Diego", "Santa Barbara", "Los Angeles"]
    assert client.get("/plan/ask/suggest", params={"q": "Narnia"}).json()["say"] == "We don't know that place yet."


def test_a_signed_out_visitor_may_ask_for_suggestions_too(client):
    assert client.get("/plan/ask/suggest", params={"q": "san"}).status_code == 200
