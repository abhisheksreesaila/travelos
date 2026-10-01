"""Share the trip from the calendar as a scrapbook page and a hub card (F-022)."""

import re

from gitaway import catalog
from tests.test_calendar import FORM, add, book
from tests.test_signin import session_data, sign_in


def slug_of(client):
    return next(e["s"] for e in session_data(client)["hub"]["ari"] if e.get("m"))


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
    assert len([e for e in session_data(client)["hub"]["ari"] if e.get("m")]) == 1


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
    b = session_data(client)["bookings"]["ari"]
    assert catalog.money(b["total_cents"]) not in html and "$" not in html


def test_user_written_plan_titles_are_escaped_on_the_shared_page(client):
    book(client)
    add(client, title="<script>alert(1)</script>")
    share(client)
    html = client.get(f"/trips/{slug_of(client)}").text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_the_shared_page_is_only_for_its_traveler(client):
    book(client)
    share(client)
    slug = slug_of(client)
    sign_in(client, "sam")
    assert client.get(f"/trips/{slug}").status_code == 404
    client.cookies.clear()
    assert client.get(f"/trips/{slug}").status_code == 404


def test_the_shared_trip_shows_in_the_hub_and_filters(client):
    book(client)
    share(client)
    html = client.get("/discover").text
    assert "LA with the kids" in html and "Your trip" in html
    assert "LA with the kids" in client.get("/discover?kid=1").text
    assert "LA with the kids" not in client.get("/discover?pet=1").text
    sign_in(client, "sam")
    assert "LA with the kids" not in client.get("/discover").text   # per traveler


def test_the_customise_form_sets_tags_and_theme(client):
    book(client)
    r = share(client, custom="1", tag=["pet", "couple", "bogus"], theme="pacific")
    assert r.status_code == 303
    entry = next(e for e in session_data(client)["hub"]["ari"] if e.get("m"))
    assert entry["g"] == ["pet", "couple"] and entry["c"] == "pacific"
    html = client.get(f"/trips/{entry['s']}").text
    assert 'data-theme="pacific"' in html and "Pet friendly" in html and "Couple friendly" in html
    form = client.get("/share").text
    assert re.search(r'name="tag"[^>]*value="pet"[^>]*checked|checked[^>]*name="tag"[^>]*value="pet"', form)
    assert "Stays private" in form and "Publish to GitAway" in form


def test_a_custom_share_with_no_tags_keeps_none(client):
    book(client)
    share(client, custom="1", theme="sunset")
    entry = next(e for e in session_data(client)["hub"]["ari"] if e.get("m"))
    assert entry["g"] == []


def test_the_shared_trip_follows_calendar_edits(client):
    book(client)
    share(client)
    add(client, title="Late addition")
    assert "Late addition" in client.get(f"/trips/{slug_of(client)}").text


def test_a_full_cookie_is_refused_kindly(client):
    book(client)
    for n in range(1, 12):
        add(client, id=f"a{n}", title=f"Plan number {n} with a long title", start=f"{7 + n}:00", end=f"{7 + n}:30", day="1")
    r = share(client)
    assert r.status_code in (303, 409)
    if r.status_code == 409:
        assert "full" in r.text.lower() or "room" in r.text.lower()
