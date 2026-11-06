"""F-186: the For creators page at /for-creators, in both showcase modes. The page must exist in production before anyone has published (D-107), sell the idea with the paste box
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
    r = client.get("/for-creators")
    assert r.status_code == 200 and "Turn your post into a trip" in words(r.text)
    sign_in(client)
    assert client.get("/for-creators").status_code == 200


def test_the_roster_at_creators_still_answers_404_in_production_until_the_first_publish(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert client.get("/creators").status_code == 404 and client.get("/for-creators").status_code == 200
    live_trip()
    assert client.get("/creators").status_code == 200


def test_it_is_linked_from_the_header_the_landing_footer_and_the_signed_in_menu(client, mode):
    assert 'href="/for-creators"' in re.search(r"<header.*?</header>", client.get("/community" if mode == "1" else "/start").text, re.S).group(0)
    footer = re.search(r"<footer.*?</footer>", client.get("/").text, re.S).group(0)
    assert 'href="/for-creators"' in footer and "For creators" in footer
    sign_in(client)
    assert 'href="/for-creators"' in client.get("/start").text


def test_the_page_carries_no_sample_content_and_links_to_nothing_hidden(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    html = client.get("/for-creators").text
    hidden = re.findall(r'href="(/community|/discover|/creators(?!/import|/settings)|/forks|/share|/rides|/sandbox)[^"]*"', without_bar(html))
    assert hidden == []
    for sample in ("Our LA family week", "312 families", "Forked by", *[t.title for t in itineraries.ITINERARIES.values()]):
        assert sample not in html


# ---- what it says --------------------------------------------------------------------------------------------------

def test_the_box_comes_first_then_the_example_the_promises_the_terms_and_the_questions(client, mode):
    html = client.get("/for-creators").text
    order = [html.index(x) for x in ('id="fc-paste"', 'id="fc-example"', 'class="fc-promises', 'id="terms"', 'id="faq"')]
    assert order == sorted(order)


def test_the_paste_box_posts_to_the_import(client, mode):
    html = client.get("/for-creators").text
    form = re.search(r'<form[^>]*id="fc-paste"[^>]*>', html).group(0)
    assert 'action="/creators/import"' in form and 'method="post"' in form
    assert re.search(r'<textarea[^>]*name="text"', html) and re.search(r'<button[^>]*name="do"[^>]*value="draft"[^>]*>(?:<svg.*?</svg>)?Draft my trip<', html)
    assert re.search(r'<button[^>]*value="manual"[^>]*>Write it myself<', html)


def test_the_three_promises_free_and_the_terms_are_there_in_plain_words(client, mode):
    text = words(client.get("/for-creators").text)
    for promise in ("Under a minute", "Flights from your trips pay you", "It links back to your post"):
        assert promise in text
    assert "Free. Terms shown on day one." in text
    for term in ("What we show", "Take it down any time", "Your marker", "Later, a share for big creators"):
        assert term in text
    assert "Stays and things to do support GitAway for now." in text and "That is a plan, not a promise of an amount." in text


def test_the_questions_say_what_to_paste_for_instagram_and_youtube(client, mode):
    text = words(client.get("/for-creators").text)
    assert "paste the caption. We keep your link as the source" in text
    assert "For a better draft, paste the transcript into the box" in text
    assert text.count("?") >= 6


def test_every_question_opens_and_closes_with_a_tap_and_no_script(client, mode):
    html = client.get("/for-creators").text
    assert len(re.findall(r"<details[^>]*class=\"fc-q\"", html)) == 7 and html.count("<summary>") == 7


# ---- the live example ----------------------------------------------------------------------------------------------

def test_with_nothing_published_the_example_is_drawn_and_says_so(client, mode):
    html = client.get("/for-creators").text
    assert 'data-kind="drawn"' in html and "Example" in html and "An example to show the shape. Your trip is drafted from your own post." in words(html)
    assert "Open the trip" not in html


def test_the_example_is_the_most_forked_real_trip(client, mode):
    one = live_trip("maya@example.com", "Maya Chen", "Three easy days in Santa Monica")[0]
    two = live_trip("lee@example.com", "Lee Park", "Two days in San Diego")[0]
    assert two["slug"] in client.get("/for-creators").text            # nothing forked yet: the newest
    for who in ("ari", "sam"):
        c = stranger(client)
        sign_in(c, who)
        assert c.post("/fork", data={"next": f"/trips/{one['slug']}"}, follow_redirects=False).status_code in (200, 303)
    html = client.get("/for-creators").text
    assert 'data-kind="real"' in html and f'href="/trips/{one["slug"]}"' in html and two["slug"] not in html
    text = words(html)
    assert "A trip made this way" in text and "2 forks" in text and "Three easy days in Santa Monica" in text and "by Maya Chen" in text
    assert "Santa Monica Pier" in text and "Lunch on Abbot Kinney" in text and "Sunset at the pier" in text


def test_a_family_forking_twice_counts_once_and_a_sample_counts_nothing(client, mode):
    slug = live_trip()[0]["slug"]
    sign_in(client)
    for _ in range(3):
        client.post("/fork", data={"next": f"/trips/{slug}"})
    assert community.fork_count(slug) == 1
    if mode == "1":
        client.post("/fork", data={"next": f"/trips/{next(iter(itineraries.ITINERARIES))}"})
    with community.connect() as db:
        from sqlalchemy import text
        assert db.conn.execute(text("SELECT COUNT(*) FROM fork_counts")).scalar() == 1


def test_a_taken_down_trip_is_never_the_example(client, mode):
    one = live_trip("maya@example.com", "Maya Chen", "Three easy days in Santa Monica")[0]
    two = live_trip("lee@example.com", "Lee Park", "Two days in San Diego")[0]
    community.take_down(two["slug"])
    html = client.get("/for-creators").text
    assert one["slug"] in html and two["slug"] not in html
    community.take_down(one["slug"])
    assert 'data-kind="drawn"' in client.get("/for-creators").text


def test_the_example_shows_the_trips_photo(client, mode):
    live_trip(photo=True)
    assert 'src="/assets/photos/venice-beach-los-angeles-hero.jpg"' in client.get("/for-creators").text


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
