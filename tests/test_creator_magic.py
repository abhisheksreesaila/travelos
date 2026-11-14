"""F-235: the magic import. A creator pastes a popular post (here The Planet D's "48 Hours in Lisbon", recorded through the app's own safe fetcher and robots check: tests/fixtures/creator_import)
and the page is told what was read as soon as it is read (the post's title, its lead picture, its own sentences), then the draft. The draft stored, and every rule about it, is the F-183 one:
the stream only says it sooner. Nothing here reaches the network or the model (`safefetch.TRANSPORT`, `ai.ANTHROPIC_TRANSPORT`)."""

import json
import re

import pytest

from gitaway import ai, creatordraft, importsource, safefetch
from tests.creator_import_support import Model, recorded
from tests.test_signin import sign_in

KEY = "sk-ant-not-a-real-key-0000"
MAGIC = {"X-Magic": "1"}


@pytest.fixture
def lisbon(monkeypatch):
    url, web, answer = recorded()
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model(answer))
    monkeypatch.setattr(safefetch, "TRANSPORT", web)
    return url, web


@pytest.fixture
def me(client):
    sign_in(client)
    return client


def events(response):
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def magic(client, **data):
    return client.post("/creators/import", data={"do": "draft", **data}, headers=MAGIC)


def test_the_page_is_told_what_was_read_then_the_draft(me, lisbon):
    url, _ = lisbon
    read, draft = events(magic(me, link=url))
    assert read["event"] == "read"
    assert read["title"] == "48 Hours in Lisbon, Itinerary" and read["by"] == "The Planet D"
    assert read["image"] == "https://theplanetd.com/images/why-visit-portugal-lisbon.jpg"
    assert draft["event"] == "draft" and draft["title"] == "48 hours in Lisbon" and draft["place"] == "Lisbon, Portugal"
    assert [d["title"] for d in draft["days"]] == ["Belem Tower", "Alfama", "Pena Palace"]
    assert [s["name"] for s in draft["days"][0]["stops"]][:3] == ["Belem Tower", "Jerónimos Monastery", "Monument of Discoveries"]
    assert draft["days"][0]["stops"][0]["note"] == "Go before the crowds."
    assert draft["tips"][0] == "Go to Belém Tower before the crowds."


def test_the_draft_is_the_stored_one_and_nothing_is_public(me, lisbon):
    url, _ = lisbon
    _, draft = events(magic(me, link=url))
    assert draft["editor"] == f"/creators/import/{draft['id']}" and draft["preview"] == draft["editor"] + "/preview"
    page = me.get(draft["editor"]).text
    assert "Pastéis de Belém" in page and "Draft: nobody can see this yet" in page
    assert me.get("/community").status_code == 200 and draft["id"] not in me.get("/community").text


def test_the_words_it_shows_while_waiting_are_the_posts_own(me, lisbon):
    url, _ = lisbon
    read, _ = events(magic(me, link=url))
    material = importsource.gather(url)
    prose = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", material.text)
    assert len(read["words"]) >= 5
    for line in read["words"]:
        assert 30 <= len(line) <= 160 and line in prose
        assert "http" not in line and "[" not in line


def test_a_site_that_turns_ai_away_says_so_in_the_stream(me, lisbon, monkeypatch):
    url, web = lisbon
    robots = "https://theplanetd.com/robots.txt"
    web.pages[robots] = (200, {"content-type": "text/plain"}, b"User-agent: *\nDisallow: /\n")
    (got,) = events(magic(me, link=url))
    assert got["event"] == "error" and "robots.txt asks AI tools not to read this page" in got["message"]


def test_nothing_pasted_is_a_plain_422_with_the_sentence(me, lisbon):
    r = magic(me)
    assert r.status_code == 422
    (got,) = events(r)
    assert got == {"event": "error", "message": "Paste the link to your post, or the text of it."}


def test_the_daily_limit_is_said_in_the_stream(me, lisbon, monkeypatch):
    url, _ = lisbon
    monkeypatch.setattr(creatordraft, "allow", lambda owner: "person")
    (got,) = events(magic(me, link=url))
    assert got == {"event": "error", "message": creatordraft.LIMIT_HIT}


def test_a_copy_with_no_key_drafts_the_made_up_sample_and_reads_nothing(me, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(safefetch, "TRANSPORT", lambda *a: pytest.fail("the network was asked"))
    read, draft = events(magic(me, text="Day 1 we went to the pier. " * 20))
    assert read["event"] == "read" and read["title"] == "" and read["image"] == ""
    assert draft["event"] == "draft" and draft["days"]


def test_without_the_header_the_form_still_redirects_to_the_editor(me, lisbon):
    url, _ = lisbon
    r = me.post("/creators/import", data={"do": "draft", "link": url}, follow_redirects=False)
    assert r.status_code == 303 and re.fullmatch(r"/creators/import/[0-9a-f]{16}", r.headers["location"])


def test_signed_out_gets_the_sign_in_not_a_draft(client, lisbon):
    url, _ = lisbon
    r = client.post("/creators/import", data={"do": "draft", "link": url}, headers=MAGIC, follow_redirects=False)
    assert r.status_code in (303, 401) and "ndjson" not in r.headers.get("content-type", "")
