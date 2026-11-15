"""F-241, F-250: "What are you after?", the v2 landing (gitaway/pages/tripask.py, gitaway/v2sentence.py, gitaway/interests.py). A signed-in family with no booked trip lands here; the sentence's
words (no free typing) are the matrix's real search parameters; Search opens the matrix on them and keeps the picked interests for the family."""
import re
from urllib.parse import parse_qs, urlsplit

import pytest

from gitaway import interests, v2sentence
from gitaway.pages import tripmatrix
from tests.test_liteapi import KEY
from tests.test_signin import person, sign_in
from tests.test_roles import crew  # noqa: F401 (fixture)

WORDS = {"to": "San Diego", "home": "SFO", "d": "2026-12-12", "n": "4", "a": "2", "k": "7,10", "x": "2", "nb": "", "b": "2300"}


def where(r):
    return r.headers["location"]


@pytest.fixture
def no_matrix(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.delenv("LITEAPI_KEY", raising=False)


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)


def test_a_signed_in_person_lands_on_the_ask(client):
    sign_in(client, "ari")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and where(r) == "/plan/ask"


def test_without_the_matrix_the_door_is_still_the_import(client, no_matrix):
    sign_in(client, "ari")
    assert where(client.get("/", follow_redirects=False)) == "/trips/import"
    assert client.get("/plan/ask").status_code == 404


def test_with_a_liteapi_key_off_the_showcase_the_ask_exists(client, real):
    sign_in(client, "ari")
    assert client.get("/plan/ask").status_code == 200


def test_the_page_is_one_calm_line_one_box_and_a_search(client):
    sign_in(client, "ari")
    html = client.get("/plan/ask").text
    assert "<h1" in html and "Where would you like to go?" in html
    box = re.search(r'<input[^>]*name="q"[^>]*>', html).group(0)
    assert 'role="combobox"' in box and 'aria-autocomplete="list"' in box and 'aria-controls="v2-list"' in box and 'aria-expanded="false"' in box and 'value=""' in box
    assert 'role="listbox"' in html and ">Search<" in html and "Show me the trips" not in html
    assert 'class="v2-w"' not in html and "v2-sent" not in html      # the tappable sentence is the results page's
    assert 'class="ga-page v2"' in html and "v2-tokens.css" in html and "/assets/js/v2ask.js" in html


def test_the_results_page_is_one_sentence_of_eight_words_and_no_box_to_type_in(client):
    sign_in(client, "ari")
    html = client.get("/plan/matrix").text
    assert [re.search(r'data-k="(\w+)"', t).group(1) for t in re.findall(r'<span[^>]*class="v2-w"[^>]*>', html)] == list(v2sentence.WORD_KEYS)
    assert "A family of 4" in html and ">SFO<" in html and "San Diego, or nearby" in html and "any budget" in html and "anything" in html
    assert "<textarea" not in html and 'type="text"' not in html and 'name="q"' not in html


def test_the_examples_are_places_a_search_can_price(client):
    sign_in(client, "ari")
    html = client.get("/plan/ask").text
    assert re.findall(r'<a href="/plan/ask\?to=([^"]+)" class="ak-ex"', html) == ["San%20Diego", "Los%20Angeles", "New%20York", "Honolulu"]


def test_a_link_in_fills_the_box_with_what_it_said(client):
    sign_in(client, "ari")
    html = client.get("/plan/ask?to=San+Diego&home=OAK&d=2027-01-09&r=2027-01-13&a=2&k=7,10").text
    assert 'value="San Diego · a family of 4 · Jan 9–13"' in html
    assert 'name="home" value="OAK"' in html
    assert 'value="San Diego"' in client.get("/plan/ask?to=San+Diego").text
    assert 'value="Atlantis"' not in client.get("/plan/ask?to=Atlantis").text      # a place nothing can price is never put in the box


def test_the_results_forms_hidden_fields_say_the_words_as_the_matrixs_parameters(client):
    sign_in(client, "ari")
    html = client.get("/plan/matrix?to=San+Diego&home=OAK&d=2027-01-09&r=2027-01-13&a=2&k=&x=1&nb=0&b=3000").text
    fields = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)"', html))
    assert (fields["to"], fields["home"], fields["a"], fields["x"], fields["nb"], fields["b"], fields["n"]) == ("San Diego", "OAK", "2", "1", "0", "3000", "4")
    assert fields["d"] == "2027-01-09"
    assert "The two of us" in html and "give or take 1 day" in html and "$3,000" in html


def test_every_interest_is_a_chip_in_the_lists_order(client):
    sign_in(client, "ari")
    html = client.get("/plan/ask").text
    assert re.findall(r'<input type="checkbox" name="i" value="(\w+)"', html) == list(interests.KEYS)
    spec = v2sentence.json.loads(re.search(r'id="v2-data">(.*?)</script>', client.get("/plan/matrix").text, re.S).group(1))
    assert [i[0] for i in spec["interests"]] == list(interests.KEYS)      # and the results' picker offers the same


def test_words_say_who_when_how_long_and_how_much():
    s = tripmatrix.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2", "", "2300")
    assert v2sentence.words(v2sentence.spec_of(s, ("beaches", "vegetarian"))) == {
        "who": "A family of 4", "from": "SFO", "where": "San Diego, or nearby", "start": "Sat, Dec 12", "flex": "give or take 2 days", "nights": "4 nights", "budget": "$2,300",
        "into": "vegetarian & beaches"}
    s = tripmatrix.state("Lake Tahoe", "OAK", "2026-12-12", "2026-12-15", "1", "", "0", "0", "")
    w = v2sentence.words(v2sentence.spec_of(s, ()))
    assert (w["who"], w["where"], w["flex"], w["nights"], w["budget"], w["into"]) == ("Just me", "Lake Tahoe", "on the dot", "3 nights", "any budget", "anything")


def test_the_words_become_the_matrixs_search_parameters():
    to, problem = v2sentence.address(WORDS)
    q = {k: v[0] for k, v in parse_qs(urlsplit(to).query).items()}
    assert problem == "" and urlsplit(to).path == "/plan/matrix"
    assert q == {"to": "San Diego", "home": "SFO", "d": "2026-12-12", "r": "2026-12-16", "a": "2", "k": "7,10", "x": "2", "b": "2300"}
    to, _ = v2sentence.address({**WORDS, "nb": "0", "n": "6", "k": "", "b": ""})
    q = {k: v[0] for k, v in parse_qs(urlsplit(to).query).items()}
    assert (q["r"], q["nb"], q["k"] if "k" in q else "", "b" in q) == ("2026-12-18", "0", "", False)


@pytest.mark.parametrize("over,words", [({"d": "soon"}, "Pick a start day"), ({"n": "0"}, "Pick how many nights"), ({"a": "9"}, "more than 8 travelers"), ({"to": "Atlantis"}, "does not know that place")])
def test_a_search_that_cannot_run_says_why_in_words(over, words):
    to, problem = v2sentence.address({**WORDS, **over})
    assert to == "" and words in problem


def test_search_opens_the_matrix_on_what_the_words_said(client):
    sign_in(client, "ari")
    r = client.post("/plan/ask", data=WORDS, follow_redirects=False)
    assert r.status_code == 303 and where(r).startswith("/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16")
    assert client.get(where(r)).status_code == 200


def test_the_scripts_own_post_answers_json_with_the_address_or_the_problem(client):
    sign_in(client, "ari")
    ok = client.post("/plan/ask", data=WORDS, headers={"x-v2": "1"})
    assert ok.json()["to"].startswith("/plan/matrix?to=San+Diego")
    bad = client.post("/plan/ask", data={**WORDS, "to": "Atlantis"}, headers={"x-v2": "1"})
    assert bad.status_code == 400 and "does not know that place" in bad.json()["error"]


def test_a_search_that_cannot_run_comes_back_here_with_the_problem_in_place(client):
    sign_in(client, "ari")
    r = client.post("/plan/ask", data={**WORDS, "to": "Atlantis"}, follow_redirects=False)
    assert r.status_code == 200 and "does not know that place" in r.text and 'role="alert"' in r.text


def test_interests_are_kept_for_the_family_in_the_lists_order(client):
    sign_in(client, "ari")
    r = client.post("/plan/ask", data={**WORDS, "i": ["hikes", "vegetarian", "seafood"]}, follow_redirects=False)
    assert r.status_code == 303
    assert interests.get(person("ari")) == ("vegetarian", "seafood", "hikes")
    html = client.get("/plan/ask").text
    assert re.findall(r'<input type="checkbox" name="i" value="(\w+)" checked', html) == ["vegetarian", "seafood", "hikes"]      # the chips show them again


def test_unknown_and_repeated_interests_are_dropped_not_stored(client):
    sign_in(client, "ari")
    client.post("/plan/ask", data={**WORDS, "i": ["seafood", "seafood", "skydiving", "<b>x</b>", "SEAFOOD"]}, follow_redirects=False)
    assert interests.get(person("ari")) == ("seafood",)


def test_picking_nothing_clears_the_interests(client):
    sign_in(client, "ari")
    client.post("/plan/ask", data={**WORDS, "i": ["seafood"]}, follow_redirects=False)
    client.post("/plan/ask", data=WORDS, follow_redirects=False)
    assert interests.get(person("ari")) == ()


def test_interests_belong_to_the_family_not_to_anyone_else(client):
    sign_in(client, "ari")
    client.post("/plan/ask", data={**WORDS, "i": ["beaches"]}, follow_redirects=False)
    assert interests.get(person("sam")) == ()


def test_signed_out_may_search_like_the_matrix_it_leads_to_but_keeps_nothing(client):
    assert client.get("/plan/ask").status_code == 200
    r = client.post("/plan/ask", data={**WORDS, "i": ["beaches"]}, follow_redirects=False)
    assert r.status_code == 303 and urlsplit(where(r)).path == "/plan/matrix"


def test_clean_keeps_only_the_fixed_list():
    assert interests.clean(["Hikes", " beaches ", "nope", "hikes", "kids"]) == ("beaches", "hikes", "kids")
    assert interests.clean(None) == () and interests.clean([]) == ()


def test_a_viewer_may_search_but_never_changes_the_familys_interests(crew):
    """Review of F-241: /plan/ask is an open post (a viewer may search), so the one write behind it, the family's interests, is an editor's or admin's alone."""
    admin, _, viewer = crew
    r = viewer.post("/plan/ask", data={**WORDS, "i": ["seafood", "hikes"]}, follow_redirects=False)
    assert r.status_code == 303 and interests.get(person("ari")) == ()


def test_the_boxs_sentence_opens_the_matrix_on_what_it_said(client):
    sign_in(client, "ari")
    r = client.post("/plan/ask", data={"q": "San Diego · 2 adults · Dec 19–23", "home": "SFO", "i": ["hikes"]}, follow_redirects=False)
    assert r.status_code == 303 and where(r).startswith("/plan/matrix?to=San+Diego&home=SFO&d=2026-12-19&r=2026-12-23&a=2")
    assert interests.get(person("ari")) == ("hikes",)
    ok = client.post("/plan/ask", data={"q": "san diego, a family of 4, Dec 19 to 23", "home": "SFO"}, headers={"x-v2": "1"})
    assert ok.json()["to"].startswith("/plan/matrix?to=San+Diego&home=SFO&d=2026-12-19&r=2026-12-23&a=2&k=8%2C8")


def test_a_box_that_cannot_search_says_why_in_words_and_keeps_what_was_typed(client):
    sign_in(client, "ari")
    r = client.post("/plan/ask", data={"q": "Narnia", "home": "SFO"}, follow_redirects=False)
    assert r.status_code == 200 and 'value="Narnia"' in r.text and "know that place yet" in r.text
    bad = client.post("/plan/ask", data={"q": "San Diego", "home": "SFO"}, headers={"x-v2": "1"})
    assert bad.status_code == 400 and bad.json()["error"] == "Say when, like “Dec 12 to 16”."
