"""F-053 Good when empty: a brand-new family's first screens offer the three ways in, and no screen is blank or a dead end."""

import re

import pytest

from tests.test_calendar import book
from tests.test_crew_calendar import make_trip_real, named
from tests.test_members import browser, invite
from tests.test_share import share
from tests.test_signin import sign_in
from tests.test_trip_import import imported

NEW = "first.run@example.com"
PATHS = ("Plan a trip", "Import a trip you booked", "Browse community trips")


def links(html):
    return set(re.findall(r'<a [^>]*href="([^"]*)"', html))


def welcome_of(html):
    assert 'aria-label="Start your first trip"' in html, "the first-run welcome is missing"
    return html.split('aria-label="Start your first trip"')[1].split("</section>")[0]


@pytest.fixture
def new(client):
    sign_in(client, NEW)
    return client


def test_start_welcomes_a_new_family_with_the_three_ways_in(new):
    w = welcome_of(new.get("/start").text)
    assert all(p in w for p in PATHS)
    assert {"#st-form", "/trips/import", "/community"} <= links(w)
    assert new.get("/trips/import").status_code == 200 and new.get("/community").status_code == 200


def test_start_has_no_welcome_for_signed_out_visitors_or_families_with_a_trip(client):
    assert "Start your first trip" not in client.get("/start").text
    book(client)
    assert "Start your first trip" not in client.get("/start").text


def test_the_calendar_welcomes_a_new_family_instead_of_a_dead_end(new):
    html = new.get("/calendar").text
    w = welcome_of(html)
    assert all(p in w for p in PATHS) and {"/start", "/trips/import", "/community"} <= links(w)
    assert "<h1" in html and "Book a trip first" not in html


def test_the_forks_page_has_next_steps_on_both_sides(new):
    html = new.get("/forks").text
    assert all(p in html for p in ("Plan a trip", "Import a trip you booked")) and "/community" in links(html)
    assert "Nothing forked or saved yet" in html


def test_the_forks_page_of_a_family_with_a_trip_but_no_forks_still_points_on(client):
    book(client)
    html = client.get("/forks").text
    assert "Nothing forked or saved yet" in html and "/community" in links(html)


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
    assert {"/trips/import", "/start", "/community"} <= links(r.text)


def test_the_trip_switcher_with_one_trip_offers_the_next_one(client):
    book(client)
    html = client.get("/calendar").text
    pop = html.split('class="cal-trips"')[1].split("</details>")[0]
    assert "1 trip" in pop and "Plan another trip" in pop and "Import a trip you booked" in pop
    assert "data-trip=" not in pop  # nothing to switch to yet


def test_the_community_page_invites_the_first_share_until_someone_shares(client):
    html = client.get("/community").text
    assert "Be the first to share one" in html and "sample trips" in html
    book(client)
    share(client)
    assert "Be the first to share one" not in client.get("/community").text


def test_every_first_screen_of_a_new_family_has_a_way_forward(new):
    for path in ("/", "/start", "/calendar", "/forks", "/family", "/trips/import", "/community", "/trip/details"):
        r = new.get(path)
        assert r.status_code in (200, 404), path
        assert links(r.text) & {"/start", "/trips/import", "/community", "#st-form"}, path


def test_share_without_a_trip_shows_the_first_run_ways_in(new):
    for r in (new.get("/share"), new.post("/share")):
        w = welcome_of(r.text)
        assert all(p in w for p in PATHS) and "Book a trip first" not in r.text
