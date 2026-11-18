"""F-194 (2), F-297: what a creator is told about money is what the code does. GitAway has no affiliate links: a creator's own links stay theirs, and hotels and flights are paid through Nuitée (LiteAPI).
The words are gitaway/howpaid.py, used on the For creators page, the claim page, the outreach message, the blog-button page and the trip page, so they cannot drift apart."""

import re
from html import unescape

from gitaway import creatorclaim as cc
from tests.creator_import_support import ANSWER  # noqa: F401
from tests.test_creator_claim import browser, claim_link, draft, setup  # noqa: F401 - fixtures and helpers of the claim tests
from tests.test_signin import sign_in

YOURS = "Your own links stay yours: GitAway never changes them and earns nothing from them."
PAID = "GitAway has no affiliate links. Whatever you book here is booked and paid through Nuitée (LiteAPI), the merchant."
GONE = ("marker", "Travelpayouts", "Aviasales", "Klook", "Flights pay you", "commission")


def words(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def test_the_make_a_guide_page_says_it(client):
    text = words(client.get("/guides/make").text)
    assert "The links stay yours" in text and YOURS in text and PAID in text
    assert not [g for g in GONE if g in text]


def test_the_make_a_guide_terms_say_it_too(client):
    terms = words(re.search(r'id="terms".*?</section>', client.get("/guides/make").text, re.S).group(0))
    assert "How GitAway is paid " + PAID in terms
    assert not [g for g in GONE if g in terms]


def test_the_outreach_message_says_it():
    msg = cc.outreach("Marcie Cheung", "3 days on Maui", "https://gitaway.me/claim/T", "Sam")
    assert "2. " + YOURS + "\n" in msg
    assert not [g for g in GONE if g in msg]
    assert len(msg.split()) < 150


def test_the_claim_page_hint_says_it(client, setup):
    link = claim_link(draft(browser("cap@example.com")).text)
    text = words(browser("sam").get(link).text)
    assert "Publishing says this is your own post. " + YOURS in text
    assert not [g for g in GONE if g in text]


def test_the_blog_button_page_says_it_and_has_no_marker_form(client):
    sign_in(client)
    page = client.get("/creators/settings").text
    says = re.search(r'id="st-says"[^>]*>(.*?)</p>', page, re.S)
    assert says and unescape(says.group(1)) == YOURS
    assert 'name="marker"' not in page and client.post("/creators/settings", data={"marker": "555111"}).status_code in (404, 405)


def test_the_trip_page_says_who_earns_in_the_same_terms(client):
    from tests.live_trips import live_trip
    from tests.pagebody import without_bar
    row, _handle, _owner = live_trip()
    page = without_bar(client.get(f"/trips/{row['slug']}").text)
    assert re.search(r'id="who-earns"[^>]*>' + re.escape("Nobody earns from this page: GitAway has no affiliate links. Anything booked from it is paid through Nuitée (LiteAPI).") + "<", page)
