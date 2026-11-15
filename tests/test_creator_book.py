"""F-253: a creator's trip as the scrapbook book (docs/design/creators-v2). The post is The Planet D's "48 Hours in Lisbon" recorded through the app's own fetcher (tests/fixtures/creator_import);
nothing here reaches the network or a model. What the book may say: a quote is a sentence of the post exactly as written, a time only where the draft has one, a picture only the creator's own pick,
every drawing labelled as one. The routes: the owner's book (draft or live), the reader's book, the word fixed in place, the lead picture, Publish, and the shelf."""
import json
import re
from html import unescape

import pytest

from gitaway import ai, community, creatorbook as cb, creatordraft, importsource, safefetch
from tests.creator_import_support import Model, recorded
from tests.test_signin import sign_in, tid

KEY = "sk-ant-not-a-real-key-0000"
MAGIC, BOOK = {"X-Magic": "1"}, {"X-Book": "1"}
BELEM = "We didn’t go inside Belém Tower but admired it from the outside."
ALFAMA = "UNESCO recognizes it as part of the Intangible Cultural Heritage of Humanity, and you can also visit the Fado Museum in Alfama."


@pytest.fixture
def lisbon(monkeypatch):
    url, web, answer = recorded()
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model(answer))
    monkeypatch.setattr(safefetch, "TRANSPORT", web)
    return url


@pytest.fixture
def made(client, lisbon):
    """The draft of the recorded post, made by the magic import, for a signed-in creator: (client, the stream's draft event)."""
    sign_in(client)
    r = client.post("/creators/import", data={"do": "draft", "link": lisbon}, headers=MAGIC)
    event = [json.loads(line) for line in r.text.splitlines() if line.strip()][-1]
    return client, {**event, "slug": creatordraft.get(tid(), event["id"])["slug"]}


def words(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def post(client, d, **form):
    return client.post(f"/creators/import/{d['id']}", data=form, headers=BOOK)


def stranger(client):
    return client.__class__(client.app, client=("127.0.0.1", 50000))


# ---- the data: the post's own sentences, laid against the stops ---------------------------------------------------------------

def test_the_draft_keeps_eighty_of_the_posts_own_sentences_and_nothing_else_of_it(made, lisbon):
    _, d = made
    stored = creatordraft.get(tid(), d["id"])
    assert len(stored["words"]) == 80 and stored["words"][0] == "Lisbon is Portugal’s coastal capital city and one of the first stops on most people’s Portugal itinerary."
    assert stored["words"] == importsource.own_words(importsource.gather(lisbon).text, creatordraft.WORDS_KEPT)
    assert stored["text"] == ""      # the post itself is not kept; only these sentences


def test_the_stream_says_which_sentence_names_each_stop_and_what_colour_it_is(made):
    _, d = made
    day1 = d["days"][0]["stops"]
    assert [(s["name"], s["kind"]) for s in day1] == [("Belem Tower", "see"), ("Jerónimos Monastery", "see"), ("Monument of Discoveries", "see"), ("Pastéis de Belém", "food"), ("MAAT", "see"),
                                                      ("LX Factory", "food"), ("Fado show", "show")]
    assert day1[0]["said"] == BELEM and day1[1]["said"].startswith("Just a short walk from Belém Tower is Jerónimos Monastery") and day1[2]["said"] == ""
    assert [s["kind"] for s in d["days"][1]["stops"]] == ["walk", "tix", "see", "ride", "food", "see", "see"]      # Alfama, the castle, a viewpoint, the tuk-tuk, the market, a street, a district: only what a name says is coloured
    assert d["book"] == f"/creators/import/{d['id']}/book"


def test_a_day_quotes_the_first_sentence_that_names_one_of_its_stops_and_never_the_same_twice():
    words_ = ["Lisbon is lovely.", BELEM, "Belém Tower again, a second sentence naming it.", ALFAMA]
    used = set()
    assert cb.day_quote(words_, ["Belem Tower", "MAAT"], used) == BELEM
    assert cb.day_quote(words_, ["Belem Tower"], used) == "Belém Tower again, a second sentence naming it."
    assert cb.day_quote(words_, ["Belem Tower"], used) == ""      # none left naming it: no quote, never an invented one
    assert cb.day_quote(words_, ["Alfama"], used) == ALFAMA
    assert cb.said(words_, ["Unnamed stop", "Fado show"]) == ["", ""]


@pytest.mark.parametrize("name,kind", [("Pastéis de Belém", "food"), ("Fado show", "show"), ("Tuk Tuk tour", "ride"), ("Castelo de São Jorge", "tix"), ("Alfama", "walk"), ("Belem Tower", "see"), ("", "see")])
def test_a_stop_gets_the_colour_its_name_says(name, kind):
    assert cb.kind_of(name) == kind


def test_a_place_gets_a_drawn_scene_that_names_it_else_gitaways_place_art_else_a_plain_one():
    assert cb.scene_of("Belém Tower", "Lisbon") == ("bookart", "belem") and cb.scene_of("Pena Palace", "Lisbon") == ("bookart", "sintra") and cb.scene_of("Lisbon") == ("bookart", "lisbon")
    assert cb.scene_of("San Diego") == ("placeart", "San Diego") and cb.scene_of("Nowhere Special") == ("generic", "")


# ---- the owner's book ----------------------------------------------------------------------------------------------------------

def test_the_owners_book_is_the_draft_as_pages_with_the_posts_words_and_no_invented_ones(made):
    client, d = made
    html = client.get(d["book"]).text
    text = words(html)
    assert "Draft · only you can see it" in text and "Before you go" in text and "The trip at a glance" in text
    assert "3 days in Lisbon" in text and "17 stops" in text.replace("17 stop", "17 stops") and "Day 1 · 7 stops" in text and "Day 2 · 7 stops" in text and "Day 3 · 3 stops" in text
    assert re.search(r'<blockquote class="quote">\s*Lisbon is Portugal’s coastal capital city[^<]*<cite>[^<]*, in the post</cite>', html)      # the intro: the post's first sentence
    assert BELEM in text and ALFAMA in text and "You’ll also visit Pena Palace, Regaleira, and Cascais." in text      # a quote on each day, each the post's
    assert text.count("Illustration") >= 4 and "Photo from the post" not in text       # no picture picked yet: every plate is a drawing, and says so
    assert "Go before the crowds." in text and '“Go before the crowds.”' not in text    # a note is shown as the draft's, never in quotation marks as if it were the post's
    assert "Each one drawn from the post and checked by its creator." in text and "word for word" not in text
    assert 'data-k="title"' in html and 'data-k="d0.head"' in html and 'data-k="d0.s0"' in html      # a word to fix in place


def test_only_its_owner_can_open_the_draft_book(made):
    client, d = made
    assert stranger(client).get(d["book"], follow_redirects=False).status_code == 303
    other = stranger(client)
    sign_in(other, "sam")
    assert other.get(d["book"]).status_code == 404 and other.get(f"/creators/import/{'0' * 16}/book").status_code == 404


def test_fixing_a_word_changes_the_draft_through_the_same_checks_as_the_editor(made):
    client, d = made
    r = post(client, d, do="word", key="d0.s0", value="  Belém   Tower  ")
    assert r.status_code == 200 and r.json() == {"ok": True, "value": "Belém Tower"}
    r = post(client, d, do="word", key="title", value="Two days and a bonus in Lisbon")
    assert r.json()["value"] == "Two days and a bonus in Lisbon"
    r = post(client, d, do="word", key="d2.head", value="Sintra, early")
    stored = creatordraft.get(tid(), d["id"])
    assert (stored["title"], stored["days"][0]["stops"][0]["name"], stored["days"][2]["title"]) == ("Two days and a bonus in Lisbon", "Belém Tower", "Sintra, early")
    assert "Sintra, early" in client.get(d["book"]).text


@pytest.mark.parametrize("key,value,error", [("title", "write to me at maya@example.com", "email"), ("title", "   ", "It cannot be empty. Press Escape to keep what it said."),
                                             ("d9.s0", "x", "That is not in the book any more. Reload the page."), ("name", "x", "That is not something to fix here.")])
def test_a_refused_word_says_why_and_changes_nothing(made, key, value, error):
    client, d = made
    r = post(client, d, do="word", key=key, value=value)
    assert r.status_code == 422 and r.json()["ok"] is False and error in r.json()["error"]
    assert creatordraft.get(tid(), d["id"])["title"] == d["title"]


def test_nobody_else_can_fix_a_word_in_a_draft(made):
    client, d = made
    other = stranger(client)
    sign_in(other, "sam")
    assert post(other, d, do="word", key="title", value="Mine now").status_code == 404
    assert creatordraft.get(tid(), d["id"])["title"] == d["title"]


def test_the_posts_lead_picture_is_used_only_when_the_creator_asks_and_is_labelled(made):
    client, d = made
    assert "Use the post&#x27;s picture" in client.get(d["book"]).text or "Use the post's picture" in unescape(client.get(d["book"]).text)
    assert post(client, d, do="lead").json() == {"ok": True}
    stored = creatordraft.get(tid(), d["id"])
    assert stored["picks"] == [0] and stored["cover"] == "0"
    html = client.get(d["book"]).text
    src = re.search(r'<img src="(/creators/import/[0-9a-f]{16}/photo/[0-9a-f]{16}-display\.jpg)"', html).group(1)
    assert client.get(src).status_code == 200 and "Photo from the post" in words(html) and "Use the post" not in unescape(html)


# ---- publishing and the reader's book ---------------------------------------------------------------------------------------------

def test_publish_needs_the_tick_then_gives_the_link_the_badge_and_the_stamp(made):
    client, d = made
    r = post(client, d, do="publish")
    assert r.status_code == 422 and "Tick" in r.json()["error"]
    r = post(client, d, do="publish", own="1")
    j = r.json()
    assert j["ok"] and j["slug"] == d["slug"] and j["link"].endswith(f"/trips/{d['slug']}/book") and j["listed"] is True
    assert j["code"].startswith("<a href=") and "/badge/plan-this-trip.svg" in j["code"] and re.fullmatch(r"[A-Z][a-z]{2} \d{1,2}, \d{4}", j["stamp"])
    assert community.get(d["slug"]) and "Published" in words(client.get(d["book"]).text) and "Share" in words(client.get(d["book"]).text)


def test_the_published_book_is_for_anyone_with_the_creators_name_held_back_until_the_site_is_theirs(made):
    client, d = made
    post(client, d, do="publish", own="1")
    html = stranger(client).get(f"/trips/{d['slug']}/book").text
    text = words(html)
    assert "From theplanetd.com" in text and "by theplanetd.com" in text.lower().replace("by theplanetd.com", "by theplanetd.com")      # unverified: the byline names the site, not the person (D-189)
    assert BELEM in text and "Plan this trip" in text and "Publish" not in text.replace("Published", "") and 'data-k=' not in html and "data-mode=\"reader\"" in html
    assert re.search(r'href="/plan/ask(\?to=[^"]*)?"', html)      # Plan this trip opens booking's sentence
    assert 'href="/theplanetd' not in html and "Read the whole post at" in text


def test_a_published_book_is_on_the_shelf_and_an_unpublished_one_is_not(made):
    client, d = made
    shelf = stranger(client).get("/community").text
    assert d["slug"] not in shelf and "No one has shared a trip yet" in words(shelf)
    post(client, d, do="publish", own="1")
    shelf = stranger(client).get("/community").text
    assert f'href="/trips/{d["slug"]}/book"' in shelf and "48 hours in Lisbon" in words(shelf) and "Sample book" not in words(shelf)      # off the showcase: only real books


def test_the_heart_is_the_existing_save(made):
    client, d = made
    post(client, d, do="publish", own="1")
    path = f"/trips/{d['slug']}/book"
    assert 'aria-pressed="false"' in re.search(r'<button[^>]*id="heartBtn"[^>]*>', client.get(path).text).group(0)
    r = client.post("/save", data={"next": path}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == path
    assert 'aria-pressed="true"' in re.search(r'<button[^>]*id="heartBtn"[^>]*>', client.get(path).text).group(0)
    client.post("/unsave", data={"next": path})
    assert 'aria-pressed="false"' in re.search(r'<button[^>]*id="heartBtn"[^>]*>', client.get(path).text).group(0)


def test_a_book_that_waits_for_the_captain_is_unlisted_and_not_for_search(made, monkeypatch):
    client, d = made
    post(client, d, do="publish", own="1")
    community.set_review(d["slug"], "pending", "theplanetd.com")
    r = stranger(client).get(f"/trips/{d['slug']}/book")
    assert r.status_code == 200 and "noindex" in r.headers["x-robots-tag"]
    assert d["slug"] not in stranger(client).get("/community").text


# ---- the showcase's sample books ----------------------------------------------------------------------------------------------------

def test_on_the_showcase_a_sample_opens_as_a_labelled_sample_book_and_off_it_there_are_none(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    text = words(client.get("/trips/dog-friendly-big-sur-drive/book").text)
    assert "Sample book" in text and "A sample book, made up so you can see the shelf." in text and "Illustration" in text
    shelf = words(client.get("/community").text)
    assert "Sample books: made up so you can see the shelf" in shelf and shelf.count("Sample book") >= 5
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert client.get("/trips/dog-friendly-big-sur-drive/book").status_code == 404
