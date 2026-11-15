"""F-241: "What are you after?", the search before the trip matrix (gitaway/pages/tripask.py, gitaway/interests.py). A signed-in family with no booked trip lands here; Search opens
the matrix on what the sentence said and keeps the picked interests for the family."""
import re
from urllib.parse import parse_qs, urlsplit

import pytest

from gitaway import interests, tripsentence
from gitaway.pages import tripask
from tests.test_calendar import book
from tests.test_liteapi import KEY
from tests.test_signin import person, sign_in


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


def test_a_family_with_no_trip_lands_on_the_ask(client):
    sign_in(client, "ari")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and where(r) == "/plan/ask"


def test_a_family_with_a_trip_still_lands_on_its_cockpit(client):
    assert book(client).status_code == 303
    assert where(client.get("/", follow_redirects=False)) == "/trip/cockpit"


def test_without_the_matrix_the_door_is_still_the_import(client, no_matrix):
    sign_in(client, "ari")
    assert where(client.get("/", follow_redirects=False)) == "/trips/import"
    assert client.get("/plan/ask").status_code == 404


def test_with_a_liteapi_key_off_the_showcase_the_ask_exists(client, real):
    sign_in(client, "ari")
    assert where(client.get("/", follow_redirects=False)) == "/plan/ask"
    assert client.get("/plan/ask").status_code == 200


def test_the_page_asks_and_shows_every_interest_and_idea_with_the_top_bar(client):
    sign_in(client, "ari")
    html = client.get("/plan/ask").text
    assert "What are you after?" in html and 'name="q"' in html and 'class="ga-tb' in html
    assert re.findall(r'name="i" value="([a-z]+)"', html) == list(interests.KEYS)
    assert len(re.findall(r'class="ak-ex"', html)) == 3
    assert "tripask.css" in html and "tripask.js" in html


def test_every_example_reads_whole_and_opens_a_matrix_with_no_problem(client):
    sign_in(client, "ari")
    for text in tripask.examples():
        ask = tripsentence.read(text)
        assert ask.unread == (), text
        r = client.post("/plan/ask", data={"q": text}, follow_redirects=False)
        assert r.status_code == 303, text
        assert client.get(where(r)).status_code == 200


def test_search_opens_the_matrix_on_the_sentences_place_dates_and_party(client):
    sign_in(client, "ari")
    r = client.post("/plan/ask", data={"q": "A family of 4, SFO to San Diego, Dec 12 to 16"}, follow_redirects=False)
    assert r.status_code == 303
    url = urlsplit(where(r))
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert url.path == "/plan/matrix"
    assert (q["to"], q["home"], q["d"], q["r"], q["a"]) == ("San Diego", "SFO", "2026-12-12", "2026-12-16", "2")


def test_a_place_without_dates_opens_the_matrix_on_its_own_default_dates(client):
    sign_in(client, "ari")
    r = client.post("/plan/ask", data={"q": "from SFO to Lake Tahoe"}, follow_redirects=False)
    assert r.status_code == 303
    q = {k: v[0] for k, v in parse_qs(urlsplit(where(r)).query).items()}
    assert (q["to"], q["home"]) == ("Lake Tahoe", "SFO") and q["d"] < q["r"]


@pytest.mark.parametrize("text", ["", "somewhere warm", "Lisbon", "   "])
def test_a_sentence_with_no_place_stays_here_and_says_so_in_place(client, text):
    sign_in(client, "ari")
    r = client.post("/plan/ask", data={"q": text, "i": ["seafood"]}, follow_redirects=False)
    assert r.status_code == 200
    assert "I could not find a place in that." in r.text
    assert 'aria-invalid="true"' in r.text and 'role="alert"' in r.text
    assert re.findall(r'<input[^>]*value="(\w+)"[^>]*checked|<input[^>]*checked[^>]*value="(\w+)"', r.text) == [("seafood", "")] or [a or b for a, b in re.findall(r'<input[^>]*value="(\w+)"[^>]*checked|<input[^>]*checked[^>]*value="(\w+)"', r.text)] == ["seafood"]      # what they picked is kept


def test_a_place_it_cannot_find_an_airport_for_says_so_and_never_guesses(client):
    sign_in(client, "ari")
    r = client.post("/plan/ask", data={"q": "SFO to Atlantis, Dec 12 to 16"}, follow_redirects=False)
    assert r.status_code == 200 and "does not know that place" in r.text


def test_interests_are_kept_for_the_family_in_the_lists_order(client):
    sign_in(client, "ari")
    r = client.post("/plan/ask", data={"q": tripask.examples()[0], "i": ["hikes", "vegetarian", "seafood"]}, follow_redirects=False)
    assert r.status_code == 303
    assert interests.get(person("ari")) == ("vegetarian", "seafood", "hikes")
    html = client.get("/plan/ask").text
    assert len(re.findall(r"checked", html)) == 3      # the ask shows them picked again


def test_unknown_and_repeated_interests_are_dropped_not_stored(client):
    sign_in(client, "ari")
    client.post("/plan/ask", data={"q": tripask.examples()[0], "i": ["seafood", "seafood", "skydiving", "<b>x</b>", "SEAFOOD"]}, follow_redirects=False)
    assert interests.get(person("ari")) == ("seafood",)


def test_picking_nothing_clears_the_interests(client):
    sign_in(client, "ari")
    client.post("/plan/ask", data={"q": tripask.examples()[0], "i": ["seafood"]}, follow_redirects=False)
    client.post("/plan/ask", data={"q": tripask.examples()[0]}, follow_redirects=False)
    assert interests.get(person("ari")) == ()


def test_interests_belong_to_the_family_not_to_anyone_else(client):
    sign_in(client, "ari")
    client.post("/plan/ask", data={"q": tripask.examples()[0], "i": ["beaches"]}, follow_redirects=False)
    assert interests.get(person("sam")) == ()


def test_signed_out_may_search_like_the_matrix_it_leads_to_but_keeps_nothing(client):
    assert client.get("/plan/ask").status_code == 200
    r = client.post("/plan/ask", data={"q": tripask.examples()[0], "i": ["beaches"]}, follow_redirects=False)
    assert r.status_code == 303 and urlsplit(where(r)).path == "/plan/matrix"


def test_clean_keeps_only_the_fixed_list():
    assert interests.clean(["Hikes", " beaches ", "nope", "hikes", "kids"]) == ("beaches", "hikes", "kids")
    assert interests.clean(None) == () and interests.clean([]) == ()
