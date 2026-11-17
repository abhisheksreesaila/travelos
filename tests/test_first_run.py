"""F-053 Good when empty: a brand-new family's first screens offer the three ways in, and no screen is blank or a dead end."""

import re

import pytest

from tests.test_calendar import book
from tests.test_crew_calendar import make_trip_real, named
from tests.test_members import browser, invite
from tests.test_signin import sign_in
from tests.test_trip_import import imported

NEW = "first.run@example.com"
PATHS = ("Find a trip", "Import a trip you booked", "Browse community trips")      # F-289


def links(html):
    return set(re.findall(r'<a [^>]*href="([^"]*)"', html))


def welcome_of(html):
    assert 'aria-label="Start your first trip"' in html, "the first-run welcome is missing"
    return html.split('aria-label="Start your first trip"')[1].split("</section>")[0]


@pytest.fixture
def new(client):
    sign_in(client, NEW)
    return client


def test_the_old_calendar_address_sends_a_new_family_to_the_matrix_instead_of_a_dead_end(new):
    assert new.get("/calendar", follow_redirects=False).headers["location"] == "/plan/ask"
    html = new.get("/calendar").text
    assert "<h1" in html and "Book a trip first" not in html
    assert "/trips/import" in links(html) and 'id="ak-import"' in html      # D-610: the v2 ask has no site nav, only its way to import


def test_family_with_only_the_owner_invites_someone(new):
    html = new.get("/family").text
    assert "Just you so far" in html and "#invite" in links(html) and 'id="invite"' in html


def test_family_with_a_second_person_no_longer_asks(client):
    book(client)
    invite(client, named("sam.kim"), "editor")  # a pending invite already counts as asked
    assert "Just you so far" not in client.get("/family").text


def test_trip_details_with_no_trip_points_to_the_ways_in(new):
    r = new.get("/trip/details")
    assert r.status_code == 404
    assert {"/trips/import", "/plan/ask", "/guides"} <= links(r.text)


def test_every_first_screen_of_a_new_family_has_a_way_forward(new):
    for path in ("/", "/plan/matrix", "/calendar", "/forks", "/family", "/trips/import", "/community", "/trip/details"):
        r = new.get(path)
        assert r.status_code in (200, 404), path
        assert links(r.text) & {"/plan/ask", "/trips/import", "/community"}, path

