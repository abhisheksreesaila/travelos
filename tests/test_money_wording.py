"""F-194 (2): what a creator is told about money is what the code does. Flights booked from their trips carry their marker; stays and things to do (Klook) support GitAway for now.
One sentence (gitaway/affiliate.py) is used on the For creators page, the claim page, the outreach message and the settings page, so they cannot drift apart."""

import re
from html import unescape

import pytest

from gitaway import creatorclaim as cc
from tests.creator_import_support import ANSWER  # noqa: F401
from tests.test_creator_claim import browser, claim_link, draft, setup  # noqa: F401 - fixtures and helpers of the claim tests
from tests.test_signin import sign_in

NO_MARKER = "Add your Travelpayouts marker and flights booked from your trips carry it, so Aviasales pays you. Stays and things to do support GitAway for now."
WITH_MARKER = "Flights booked from your trips carry your Travelpayouts marker, so Aviasales pays you. Stays and things to do support GitAway for now."
OLD = ("Your links keep paying you", "Book buttons on your trips use it", "Book buttons on your trips")


def words(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def test_the_for_creators_page_says_it(client):
    text = words(client.get("/for-creators").text)
    assert NO_MARKER in text and "Flights from your trips pay you" in text
    assert not [o for o in OLD if o in text]


def test_the_for_creators_terms_say_it_too(client):
    terms = words(re.search(r'id="terms".*?</section>', client.get("/for-creators").text, re.S).group(0))
    assert "Paste your own Travelpayouts marker once. " + NO_MARKER in terms


def test_the_outreach_message_says_it():
    msg = cc.outreach("Marcie Cheung", "3 days on Maui", "https://gitaway.me/claim/T", "Sam")
    assert "2. Flights pay you: " + NO_MARKER + "\n" in msg
    assert not [o for o in OLD if o in msg]
    assert len(msg.split()) < 150


def test_the_claim_page_hint_says_it(client, setup):
    link = claim_link(draft(browser("cap@example.com")).text)
    text = words(browser("sam").get(link).text)
    assert "Publishing says this is your own post. " + NO_MARKER in text
    assert not [o for o in OLD if o in text]


@pytest.mark.parametrize("marker, line", [("", NO_MARKER), ("555111", WITH_MARKER)])
def test_the_settings_page_says_it_for_each_state(client, marker, line):
    sign_in(client)
    if marker:
        client.post("/creators/settings", data={"marker": marker})
    says = re.search(r'id="st-says"[^>]*>(.*?)</p>', client.get("/creators/settings").text, re.S)
    assert says and unescape(says.group(1)) == line


def test_the_trip_page_says_who_earns_in_the_same_terms(client):
    from gitaway import affiliate
    from tests.live_trips import live_trip
    from tests.pagebody import without_bar
    row, _handle, owner = live_trip()
    affiliate.set_marker(owner["user_id"], "555111")
    page = without_bar(client.get(f"/trips/{row['slug']}").text)
    assert re.search(r'id="who-earns"[^>]*>Flights booked from this trip support Maya Chen\. Stays and things to do support GitAway for now\.<', page)
