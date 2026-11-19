"""F-186, F-262: the page that makes a guide from a post, at /guides/make (it was For creators), in both showcase modes. The page must exist in production before anyone has published (D-107), sell the idea with the paste box
first, show a real example when there is one and a labelled drawn one when there is not, and carry the terms and the questions."""

import re
from html import unescape

import pytest

from gitaway import community, itineraries
from tests.live_trips import live_trip
from tests.pagebody import without_bar
from tests.test_creator_import import POST, model, web  # noqa: F401 (fixtures)
from tests.test_signin import sign_in


@pytest.fixture(params=["1", "0"], ids=["showcase", "live"])
def mode(request, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", request.param)
    return request.param


def words(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def stranger(client):
    return client.__class__(client.app, client=("127.0.0.1", 50000))


# ---- it exists, always ---------------------------------------------------------------------------------------------

def test_the_page_is_open_to_everyone_before_anyone_has_published(client, mode):
    assert not community.has_real()
    r = client.get("/guides/make")
    assert r.status_code == 200 and "Your post deserves more than a scroll. It becomes a trip people plan, book and take, in one place. Your words and your links stay yours." in words(r.text)
    sign_in(client)
    assert client.get("/guides/make").status_code == 200


def test_the_roster_at_creators_still_answers_404_in_production_until_the_first_publish(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert client.get("/creators").status_code == 404 and client.get("/guides/make").status_code == 200
    live_trip()
    assert client.get("/creators").status_code == 200


def test_it_is_linked_from_the_hub_the_header_and_the_landing_footer(client, mode):
    top = re.search(r'<div class="v2-top">.*?</nav>', client.get("/guides").text, re.S).group(0)         # F-253, F-262: the hub's top bar carries Guides; its Make a guide panel leads here
    assert 'href="/guides"' in top
    assert 'href="/guides/make"' in client.get("/guides").text
    footer = re.search(r"<footer.*?</footer>", client.get("/").text, re.S).group(0)
    assert 'href="/guides"' in footer
    sign_in(client)
    assert 'href="/guides/make"' in client.get("/guides").text


def test_the_page_carries_no_sample_content_and_links_to_nothing_hidden(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    html = client.get("/guides/make").text
    hidden = re.findall(r'href="(/discover|/creators(?!/import|/settings)|/forks|/share|/rides|/sandbox)[^"]*"', without_bar(html))
    assert hidden == []
    for sample in ("Our LA family week", "312 families", "Forked by", *[t.title for t in itineraries.ITINERARIES.values()]):
        assert sample not in html


# ---- what it says --------------------------------------------------------------------------------------------------

def test_the_box_comes_first_then_the_example_the_promises_the_terms_and_the_questions(client, mode):
    html = client.get("/guides/make").text
    order = [html.index(x) for x in ('id="fc-paste"', 'class="fc-promises', 'id="fc-example"', 'id="terms"', 'id="faq"')]      # F-253 the box first; F-295 then why it helps the creator, then the example
    assert order == sorted(order)


def test_the_paste_box_posts_to_the_import(client, mode):
    html = client.get("/guides/make").text
    form = re.search(r'<form[^>]*id="fc-paste"[^>]*>', html).group(0)
    assert 'action="/creators/import"' in form and 'method="post"' in form
    assert re.search(r'<textarea[^>]*name="text"', html) and re.search(r'<button[^>]*name="do"[^>]*value="draft"[^>]*>(?:Make my postcard|Start my postcard)(?:<svg.*?</svg>)?<', html)
    assert re.search(r'<button[^>]*value="manual"[^>]*>Or write it yourself<', html)


def test_the_three_promises_free_and_the_terms_are_there_in_plain_words(client, mode):
    text = words(client.get("/guides/make").text)
    for promise in ("Another place your post travels", "Readers can plan the trip", "The links stay yours", "You can see who reads it"):
        assert promise in text
    assert "Free. Terms shown on day one." in text
    for term in ("What we show", "Take it down any time", "How GitAway is paid"):
        assert term in text
    assert "GitAway has no affiliate links." in text and "Nothing on a postcard carries a tracking code of ours." in text
    assert "marker" not in text and "Klook" not in text and "Travelpayouts" not in text


def test_the_questions_say_what_to_paste_for_instagram_and_youtube(client, mode):
    text = words(client.get("/guides/make").text)
    assert "paste the caption. We keep your link as the source" in text
    assert "For a better draft, paste the transcript into the box" in text
    assert text.count("?") >= 6


def test_every_question_opens_and_closes_with_a_tap_and_no_script(client, mode):
    html = client.get("/guides/make").text
    assert len(re.findall(r"<details[^>]*class=\"fc-q\"", html)) == 7 and html.count("<summary>") == 7


# ---- the live example ----------------------------------------------------------------------------------------------

def test_with_nothing_published_the_example_is_drawn_and_says_so(client, mode):
    html = client.get("/guides/make").text
    assert 'data-kind="drawn"' in html and "Example" in html and "An example to show the shape. Your trip is drafted from your own post." in words(html)
    assert "Open the trip" not in html


def test_a_taken_down_trip_is_never_the_example(client, mode):
    one = live_trip("maya@example.com", "Maya Chen", "Three easy days in Santa Monica")[0]
    two = live_trip("lee@example.com", "Lee Park", "Two days in San Diego")[0]
    community.take_down(two["slug"])
    html = client.get("/guides/make").text
    assert one["slug"] in html and two["slug"] not in html
    community.take_down(one["slug"])
    assert 'data-kind="drawn"' in client.get("/guides/make").text


def test_the_example_shows_the_trips_photo(client, mode):
    live_trip(photo=True)
    assert 'src="/assets/photos/venice-beach-los-angeles-hero.jpg"' in client.get("/guides/make").text


# ---- the box posts to the import -----------------------------------------------------------------------------------

def test_a_signed_out_visitor_is_sent_to_sign_in_and_back_to_the_paste_page(client, mode):
    r = client.post("/creators/import", data={"text": "My trip to the pier", "do": "draft"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=/creators/import")


def test_one_address_in_the_box_is_read_as_the_link(client, mode, model, web):
    sign_in(client)
    r = client.post("/creators/import", data={"text": f"  {POST}  ", "do": "draft"}, follow_redirects=False)
    assert r.status_code == 303 and re.search(r"/creators/import/[0-9a-f]{16}$", r.headers["location"])
    assert web.calls[0] == POST and len(model.requests) == 1


def test_text_in_the_box_is_the_text_and_write_it_myself_needs_nothing(client, mode, model):
    sign_in(client)
    r = client.post("/creators/import", data={"text": "Day 1 we went to the pier and rode the wheel at 10:00 AM. Day 2 the Venice canals.", "do": "draft"}, follow_redirects=False)
    assert r.status_code == 303
    r = client.post("/creators/import", data={"text": "", "do": "manual"}, follow_redirects=False)
    assert r.status_code == 303 and re.search(r"/creators/import/[0-9a-f]{16}$", r.headers["location"])


def test_an_empty_box_asks_for_something_instead_of_drafting(client, mode):
    sign_in(client)
    r = client.post("/creators/import", data={"text": "  ", "do": "draft"})
    assert r.status_code == 422 and "Paste the link to your post, or the text of it." in unescape(r.text)


def test_without_an_ai_key_the_page_says_a_link_is_not_read_yet_and_asks_for_the_text(client, mode):
    html = client.get("/guides/make").text
    text = words(html)
    if mode == "0":      # production's case today: no key, no sample draft
        assert "Reading a link is not switched on yet. Paste the text of your post and lay it out yourself." in text
        assert 'placeholder="Paste the text of your post"' in html and 'id="fc-example-chip"' not in html
    else:               # the showcase's simulated draft reads a link
        assert 'id="fc-off"' not in html and 'id="fc-example-chip"' in html
