"""Share the trip from the calendar as a scrapbook page and a hub card (F-022)."""

import json
import re

import pytest

from gitaway import catalog, community
from tests.test_calendar import FORM, add, book
from tests.test_signin import session_data, sign_in, stored_booking, tid


def slug_of(client, who="ari"):
    return community.rows(kind="shared", owner=tid(who))[0]["slug"]


def share(client, **data):
    return client.post("/share", data=data, follow_redirects=False)


def test_share_needs_a_traveler_and_a_booked_trip(client):
    r = share(client)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=")
    sign_in(client)
    r = share(client)
    assert r.status_code == 409 and "Plan a trip or import one you booked" in r.text
    assert community.rows() == []
    assert client.get("/share").status_code == 200 and "Import a trip you booked" in client.get("/share").text


def test_the_calendar_share_button_is_one_tap(client):
    book(client)
    html = client.get("/calendar").text
    assert re.search(r'<form[^>]*action="/share"[^>]*method="post"', html) or re.search(r'<form[^>]*method="post"[^>]*action="/share"', html)
    assert "Share trip" in html


def test_one_tap_publishes_and_confirms_with_a_link_to_the_page(client):
    book(client)
    r = share(client)
    assert r.status_code == 303 and r.headers["location"].startswith("/share/done")
    slug = slug_of(client)
    html = client.get("/share/done").text
    assert f'href="/trips/{slug}"' in html and 'href="/community"' in html
    assert "live" in html.lower() and "Kid friendly" in html
    assert 'href="/share"' in html  # change tags and theme


def test_sharing_twice_is_one_page(client):
    book(client)
    share(client)
    share(client)
    assert len(community.rows(kind="shared", owner=tid("ari"))) == 1


def test_the_page_has_bookings_and_activities_by_day(client):
    book(client)
    add(client, title="Venice Canals stroll")
    share(client)
    html = client.get(f"/trips/{slug_of(client)}").text
    assert "Flight to LAX" in html and "Venice Canals stroll" in html and "DAY 1" in html
    assert 'data-theme="sunset"' in html and "Kid friendly" in html
    assert 'id="day-1"' in html and 'id="day-5"' in html


def test_the_page_never_has_notes_friends_invites_or_money(client):
    book(client)
    client.post("/calendar/friends", data={"name": "Grandma Zelda"})
    add(client)
    client.post("/calendar/notes", data={"id": "n9", "text": "Secret passcode hunter2", "act": "a1"})
    client.post("/calendar/notes", data={"id": "n8", "text": "Bring the family treasure"})
    share(client)
    html = client.get(f"/trips/{slug_of(client)}").text.split("<main")[1].split("</main>")[0]  # the page, not the viewer's own header
    for private in ["hunter2", "family treasure", "Grandma Zelda", "Ari Rivera", "/join/", "GA-", "gitaway.example"]:
        assert private not in html, private
    b = stored_booking()
    assert catalog.money(b["total_cents"]) not in html and "$" not in html


def test_user_written_plan_titles_are_escaped_on_the_shared_page(client):
    book(client)
    add(client, title="<script>alert(1)</script>")
    share(client)
    html = client.get(f"/trips/{slug_of(client)}").text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_the_community_sees_each_others_shared_trips_on_any_device(client):
    book(client)
    add(client, title="Ari only plan")
    share(client)
    slug = slug_of(client)
    sign_in(client, "sam")
    page = client.get(f"/trips/{slug}")
    assert page.status_code == 200 and "Ari only plan" in page.text            # Ari's frozen copy, not Sam's calendar
    hub_html = client.get("/community").text
    assert "LA with the kids" in hub_html and "Your trip" not in hub_html
    client.post("/logout")   # signed out in the same browser
    assert client.get(f"/trips/{slug}").status_code == 200 and client.get("/trips/shared-nope").status_code == 404
    client.cookies.clear()   # a different browser: the page is still there (F-041)
    assert client.get(f"/trips/{slug}").status_code == 200


def test_rebooking_keeps_the_old_page_until_the_new_trip_is_shared(client):
    book(client)
    share(client)
    old = slug_of(client)
    book(client, f="f2")   # different picks, a new booking
    assert client.get(f"/trips/{old}").status_code == 200  # a snapshot does not need the old booking
    share(client)
    new = slug_of(client)
    assert new != old and f"/trips/{new}" in client.get("/community").text
    assert client.get(f"/trips/{old}").status_code == 404 and f"/trips/{old}" not in client.get("/community").text  # one shared trip at a time


def test_signed_in_travelers_own_trip_keeps_the_marker_among_the_community(client):
    book(client)
    share(client)
    book(client, "sam")
    share(client)
    html = client.get("/community").text
    assert html.count("LA with the kids") == 2 and html.count("Your trip") == 1


def test_the_shared_trip_shows_in_the_hub_and_filters(client):
    book(client)
    share(client)
    html = client.get("/community").text
    assert "LA with the kids" in html and "Your trip" in html
    assert "LA with the kids" in client.get("/community?kid=1").text
    assert "LA with the kids" not in client.get("/community?pet=1").text


def test_the_booking_reference_never_appears_anywhere_it_could_leak(client):
    book(client)
    ref = stored_booking()["id"]
    r = share(client)
    pages = [r.headers["location"], client.get("/share/done").text, client.get("/share").text, client.get("/community").text,
             client.get(f"/trips/{slug_of(client)}").text, client.get("/calendar").text]
    tail = ref.split("-")[1]
    for text in [*pages, str(community.rows())]:
        assert ref.lower() not in text.lower() and tail.lower() not in text.lower()
    assert ref.lower() not in slug_of(client)


def test_the_slug_is_stable_per_traveler_and_booking(client):
    book(client)
    share(client)
    first = slug_of(client)
    share(client)
    assert slug_of(client) == first and first.startswith("shared-")
    book(client, "sam")
    share(client)
    assert slug_of(client, "sam") != first


def test_a_one_tap_reshare_keeps_the_chosen_tags_and_theme(client):
    book(client)
    share(client, custom="1", tag=["pet"], theme="pacific")
    share(client)   # the calendar's one tap
    entry = community.rows(kind="shared", owner=tid("ari"))[0]
    assert entry["tags"] == ["pet"] and entry["theme"] == "pacific"


def test_the_privacy_copy_says_what_really_stays_private_and_pills_are_tinted(client):
    book(client)
    html = client.get("/share").text
    assert "Notes, who" in html and "booking reference" in html and "what you paid" in html
    assert "sh-pill sh-t-mint" in html and "sh-pill sh-t-bubble" in html


def test_the_customise_form_sets_tags_and_theme(client):
    book(client)
    r = share(client, custom="1", tag=["pet", "couple", "bogus"], theme="pacific")
    assert r.status_code == 303
    entry = community.rows(kind="shared", owner=tid("ari"))[0]
    assert entry["tags"] == ["pet", "couple"] and entry["theme"] == "pacific"
    html = client.get(f"/trips/{entry['slug']}").text
    assert 'data-theme="pacific"' in html and "Pet friendly" in html and "Couple friendly" in html
    form = client.get("/share").text
    assert re.search(r'name="tag"[^>]*value="pet"[^>]*checked|checked[^>]*name="tag"[^>]*value="pet"', form)
    assert "Stays private" in form and "Publish to GitAway" in form


def test_a_custom_share_with_no_tags_keeps_none(client):
    book(client)
    share(client, custom="1", theme="sunset")
    assert community.rows(kind="shared", owner=tid("ari"))[0]["tags"] == []


def test_the_shared_trip_is_a_snapshot_until_it_is_shared_again(client):
    book(client)
    share(client)
    add(client, title="Late addition")
    assert "Late addition" not in client.get(f"/trips/{slug_of(client)}").text
    share(client)
    assert "Late addition" in client.get(f"/trips/{slug_of(client)}").text


def test_sharing_signed_out_or_unbooked_changes_nothing_in_the_model():
    from gitaway import hub, share as sh
    with pytest.raises(hub.HubError):
        sh.publish({})
    with pytest.raises(hub.HubError):
        sh.publish({"user_id": "ari"})
    assert community.rows() == []
