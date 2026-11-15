"""F-254 (D-751): a locked block on the planning calendar opens /trip/booking, the page the canvas's booking sheet became. The trip is the template import (Fri Oct 16 to Tue Oct 20 in Los Angeles: flights, the Santa Monica hotel, a Hertz car)."""

import re
from html import unescape

from tests.test_signin import sign_in
from tests.test_trip_import import imported


def words(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def locked_blocks(client):
    """The hrefs the planning calendar gives its locked (booked) blocks."""
    html = client.get("/trip/plan/cal?view=week&frm=0&cols=7&day=0").text
    return sorted({unescape(h) for h in re.findall(r'href="(/trip/booking\?[^"]+)"', html)})


def test_every_locked_block_on_the_plan_opens_its_booking_page(client):
    imported(client)
    links = locked_blocks(client)
    assert len(links) >= 3
    for href in links:
        r = client.get(href)
        assert r.status_code == 200 and 'id="bk-back"' in r.text and 'href="/trip/plan"' in r.text, href


def test_a_hotel_booking_shows_its_address_and_a_way_back(client):
    imported(client)
    page = next(client.get(h).text for h in locked_blocks(client) if "b-" in h and "check" not in h and "Santa" in client.get(h).text)
    assert "Santa Monica" in words(page) and "Back to the plan" in words(page)


def test_a_block_that_is_not_a_booking_goes_back_to_the_plan(client):
    imported(client)
    r = client.get("/trip/booking?block=nothing-here", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/plan"


def test_who_to_call_has_911_and_the_family(client):
    imported(client)
    page = client.get("/trip/booking?sos=1").text
    assert 'href="tel:911"' in page and "Who to call" in words(page)


def test_a_stranger_goes_through_sign_in_and_a_family_with_no_trip_to_the_way_in(client):
    assert client.get("/trip/booking?sos=1", follow_redirects=False).headers["location"].startswith("/signin?next=")
    sign_in(client)
    assert client.get("/trip/booking?sos=1", follow_redirects=False).headers["location"] == "/plan/ask"
