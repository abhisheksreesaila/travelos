"""Share the trip from the calendar as a scrapbook page and a hub card (F-022)."""

import json
import re

import pytest

from gitaway import catalog
from tests.test_calendar import FORM, add, book
from tests.test_signin import session_data, sign_in, tid


def slug_of(client):
    return next(e["s"] for e in session_data(client)["hub"][tid("ari")] if e.get("m"))


def share(client, **data):
    return client.post("/share", data=data, follow_redirects=False)


def test_share_needs_a_traveler_and_a_booked_trip(client):
    r = share(client)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=")
    sign_in(client)
    r = share(client)
    assert r.status_code == 409 and "Book a trip first" in r.text
    assert "hub" not in session_data(client)
    assert client.get("/share").status_code == 200 and "Book a trip first" in client.get("/share").text


def test_the_calendar_share_button_is_one_tap(client):
    book(client)
    html = client.get("/calendar").text
    assert re.search(r'<form[^>]*action="/share"[^>]*method="post"', html) or re.search(r'<form[^>]*method="post"[^>]*action="/share"', html)
    assert "Share trip" in html


def test_one_tap_publishes_and_confirms_with_a_link_to_the_page(client):
    book(client)
    r = share(client)
    assert r.status_code == 303 and r.headers["location"] == "/share/done"
    slug = slug_of(client)
    html = client.get("/share/done").text
    assert f'href="/trips/{slug}"' in html and 'href="/discover"' in html
    assert "live" in html.lower() and "Kid friendly" in html
    assert 'href="/share"' in html  # change tags and theme


def test_sharing_twice_is_one_page(client):
    book(client)
    share(client)
    share(client)
    assert len([e for e in session_data(client)["hub"][tid("ari")] if e.get("m")]) == 1


def test_the_page_has_bookings_and_activities_by_day(client):
    book(client)
    add(client, title="Venice Canals stroll")
    share(client)
    html = client.get(f"/trips/{slug_of(client)}").text
    assert "Skylark Air 214" in html and "Venice Canals stroll" in html and "FRI, OCT 16" in html
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
    b = session_data(client)["bookings"][tid("ari")]
    assert catalog.money(b["total_cents"]) not in html and "$" not in html


def test_user_written_plan_titles_are_escaped_on_the_shared_page(client):
    book(client)
    add(client, title="<script>alert(1)</script>")
    share(client)
    html = client.get(f"/trips/{slug_of(client)}").text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_the_community_in_this_browser_sees_each_others_shared_trips(client):
    book(client)
    add(client, title="Ari only plan")
    share(client)
    slug = slug_of(client)
    sign_in(client, "sam")
    page = client.get(f"/trips/{slug}")
    assert page.status_code == 200 and "Ari only plan" in page.text            # rebuilt from Ari's booking and calendar
    hub_html = client.get("/discover").text
    assert "LA with the kids" in hub_html and "Your trip" not in hub_html
    client.post("/logout")   # signed out in the same browser
    assert client.get(f"/trips/{slug}").status_code == 200 and client.get("/trips/shared-nope").status_code == 404
    client.cookies.clear()   # a different browser: nothing is shared beyond this one
    assert client.get(f"/trips/{slug}").status_code == 404


def test_rebooking_drops_the_old_shared_card_instead_of_leaving_a_dead_link(client):
    book(client)
    share(client)
    old = slug_of(client)
    book(client, f="f2")   # different picks, a new booking
    html = client.get("/discover").text
    assert f"/trips/{old}" not in html and "LA with the kids" not in html
    assert client.get(f"/trips/{old}").status_code == 404
    share(client)
    new = slug_of(client)
    assert new != old and f"/trips/{new}" in client.get("/discover").text


def test_signed_in_travelers_own_trip_keeps_the_marker_among_the_community(client):
    book(client)
    share(client)
    book(client, "sam")
    share(client)
    html = client.get("/discover").text
    assert html.count("LA with the kids") == 2 and html.count("Your trip") == 1


def test_the_shared_trip_shows_in_the_hub_and_filters(client):
    book(client)
    share(client)
    html = client.get("/discover").text
    assert "LA with the kids" in html and "Your trip" in html
    assert "LA with the kids" in client.get("/discover?kid=1").text
    assert "LA with the kids" not in client.get("/discover?pet=1").text


def test_the_booking_reference_never_appears_anywhere_it_could_leak(client):
    book(client)
    ref = session_data(client)["bookings"][tid("ari")]["id"]
    r = share(client)
    pages = [r.headers["location"], client.get("/share/done").text, client.get("/share").text, client.get("/discover").text,
             client.get(f"/trips/{slug_of(client)}").text, client.get("/calendar").text]
    tail = ref.split("-")[1]
    for text in [*pages, str(session_data(client)["hub"])]:
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
    assert next(e["s"] for e in session_data(client)["hub"][tid("sam")] if e.get("m")) != first


def test_a_one_tap_reshare_keeps_the_chosen_tags_and_theme(client):
    book(client)
    share(client, custom="1", tag=["pet"], theme="pacific")
    share(client)   # the calendar's one tap
    entry = next(e for e in session_data(client)["hub"][tid("ari")] if e.get("m"))
    assert entry["g"] == ["pet"] and entry["c"] == "pacific"


def test_the_privacy_copy_says_what_really_stays_private_and_pills_are_tinted(client):
    book(client)
    html = client.get("/share").text
    assert "Notes, who" in html and "booking reference" in html and "what you paid" in html
    assert "sh-pill sh-t-mint" in html and "sh-pill sh-t-bubble" in html


def test_the_customise_form_sets_tags_and_theme(client):
    book(client)
    r = share(client, custom="1", tag=["pet", "couple", "bogus"], theme="pacific")
    assert r.status_code == 303
    entry = next(e for e in session_data(client)["hub"][tid("ari")] if e.get("m"))
    assert entry["g"] == ["pet", "couple"] and entry["c"] == "pacific"
    html = client.get(f"/trips/{entry['s']}").text
    assert 'data-theme="pacific"' in html and "Pet friendly" in html and "Couple friendly" in html
    form = client.get("/share").text
    assert re.search(r'name="tag"[^>]*value="pet"[^>]*checked|checked[^>]*name="tag"[^>]*value="pet"', form)
    assert "Stays private" in form and "Publish to GitAway" in form


def test_a_custom_share_with_no_tags_keeps_none(client):
    book(client)
    share(client, custom="1", theme="sunset")
    entry = next(e for e in session_data(client)["hub"][tid("ari")] if e.get("m"))
    assert entry["g"] == []


def test_the_shared_trip_follows_calendar_edits(client):
    book(client)
    share(client)
    add(client, title="Late addition")
    assert "Late addition" in client.get(f"/trips/{slug_of(client)}").text


def test_a_full_cookie_is_refused_kindly(client, monkeypatch):
    from gitaway import session as ses
    book(client)
    monkeypatch.setattr(ses, "BUDGET", len(json.dumps(session_data(client))) + 5)   # no room for a hub entry
    r = share(client)
    assert r.status_code == 409 and "full" in r.text.lower()
    assert "hub" not in session_data(client)


def test_a_failed_publish_leaves_the_older_shared_entry_in_place(monkeypatch):
    from gitaway import hub, session as ses, share as sh
    s = {"user_id": "ari"}
    ses.book(s, catalog.quote("f1", "h1", "c1"))
    hub.publish(s, slug="shared-old", title="LA with the kids", place="Los Angeles", days=5, author="a traveler", tags=("kid",), mine=True)
    before = json.dumps(s["hub"], sort_keys=True)
    monkeypatch.setattr(ses, "BUDGET", len(json.dumps(s)) - 1)
    with pytest.raises(hub.HubError):
        sh.publish(s)
    assert json.dumps(s["hub"], sort_keys=True) == before
