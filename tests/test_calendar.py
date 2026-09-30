"""The trip calendar screen at /calendar (F-019), through the HTTP seam."""

import re
from urllib.parse import quote

from tests.test_signin import session_data, sign_in

PICK = {"f": "f1", "h": "h1", "c": "c1"}
FORM = {"day": "1", "start": "10:00", "end": "11:30", "title": "Venice Canals stroll", "kind": "outdoors"}


def book(client, traveler="ari", **pick):
    sign_in(client, traveler)
    return client.post("/pay", data={**PICK, **pick}, follow_redirects=False)


def add(client, id="a1", demo="", **over):
    return client.post("/calendar/activities", data={"id": id, "demo": demo, **FORM, **over}, follow_redirects=False)


def tag(html, attr, value):
    """The attributes of the first tag carrying attr="value", as a dict (attribute order is not part of the contract)."""
    m = re.search(r'<[a-z0-9]+\s[^>]*\b%s="%s"[^>]*>' % (re.escape(attr), re.escape(value)), html)
    return dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(0))) if m else None


def ids(html):
    return [t["data-id"] for t in (dict(re.findall(r'([\w-]+)="([^"]*)"', m)) for m in re.findall(r'<a\s[^>]*cal-act[^>]*>', html))]


def where(html, id):
    t = tag(html, "data-id", id)
    return (int(t["data-day"]), int(t["data-start"]), int(t["data-end"])) if t else None


def test_signed_out_goes_through_sign_in_and_comes_back_to_the_calendar(client):
    r = client.get("/calendar", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/signin?next={quote('/calendar', safe='')}"
    r = client.get("/calendar?demo=long", follow_redirects=False)
    assert r.headers["location"] == f"/signin?next={quote('/calendar?demo=long', safe='')}"
    for method, path in [("post", "/calendar/activities"), ("post", "/calendar/notes"), ("post", "/calendar/undo"),
                         ("post", "/calendar/activities/a1/move"), ("post", "/calendar/activities/a1/delete"), ("post", "/calendar/activities/a1")]:
        assert getattr(client, method)(path, data={}, follow_redirects=False).status_code == 303


def test_signed_in_without_a_booking_gets_a_friendly_book_a_trip_first_page(client):
    sign_in(client)
    r = client.get("/calendar")
    assert r.status_code == 200 and "Book a trip first" in r.text
    assert 'href="/plan"' in r.text and "cal-block" not in r.text
    assert client.post("/calendar/activities", data={"id": "a1", **FORM}, follow_redirects=False).status_code == 303


def test_booked_blocks_are_locked_and_sit_at_the_picked_flights_times(client):
    book(client)
    html = client.get("/calendar").text
    assert "LA with the kids" in html and "Oct 16 – 20" in html and "$3,088" in html
    out = tag(html, "data-block", "b-out")
    assert (out["data-day"], out["data-start"], out["data-end"]) == ("0", "485", "572")
    assert "Skylark Air 214 · SFO → LAX" in html and "8:05 AM" in html
    assert tag(html, "data-block", "b-back")["data-start"] == "850" and "2:10 PM" in html
    assert "Check in · The Tidewater" in html and "Check out · The Tidewater" in html
    assert html.count("Booked, locked") >= 4
    assert 'href="/calendar?edit=b-out' not in html


def test_the_picked_flight_changes_the_blocks(client):
    book(client, f="f5", h="h3")
    html = client.get("/calendar").text
    assert tag(html, "data-block", "b-out")["data-start"] == "610" and "SFO → BUR" in html and "Check in · Hotel Marigold" in html


def test_day_chips_show_the_weather_and_the_weekday(client):
    book(client)
    html = client.get("/calendar").text
    assert html.count('data-day-head') == 5
    assert "75°F" in html and "FRI" in html.upper() and "TUE" in html.upper()


def test_adding_an_activity_shows_it_on_the_right_day_and_survives_a_reload(client):
    book(client)
    r = add(client)
    assert r.status_code == 303 and r.headers["location"] == "/calendar?new=a1"
    html = client.get("/calendar").text
    assert ids(html) == ["a1"]
    assert where(html, "a1") == (1, 600, 690)
    assert "Venice Canals stroll" in html and "10:00 AM" in html
    assert ids(client.get("/calendar").text) == ["a1"]


def test_a_refreshed_add_does_not_duplicate_and_ids_stay_stable(client):
    book(client)
    add(client)
    add(client)  # the browser re-posts the same form
    add(client, id="a2", title="Bike the Strand", day="2")
    assert sorted(ids(client.get("/calendar").text)) == ["a1", "a2"]
    assert 'name="id" value="a3"' in client.get("/calendar?add=1&at=13:00").text


def test_a_clash_with_a_booked_item_is_refused_and_the_form_shows_it(client):
    book(client)
    r = add(client, day="0", start="09:00", end="10:00", title="Clash")
    assert r.status_code == 409
    assert "overlaps Skylark Air 214 · SFO → LAX" in r.text and 'role="alert"' in r.text
    assert 'value="Clash"' in r.text and 'role="dialog"' in r.text  # the form stays open with what was typed
    assert ids(client.get("/calendar").text) == []


def test_a_bad_form_is_refused_with_the_reason(client):
    book(client)
    r = add(client, title="   ")
    assert r.status_code == 409 and "Give it a title." in r.text


def test_the_ghost_link_opens_the_add_form_for_that_gap(client):
    book(client)
    html = client.get("/calendar?add=2&at=11:00").text
    assert 'role="dialog"' in html and "Add something fun" in html
    assert 'name="start" value="11:00"' in html and 'name="end" value="12:00"' in html
    assert re.search(r'<option value="2" selected', html)


def test_editing_through_the_form_updates_the_block(client):
    book(client)
    add(client)
    html = client.get("/calendar?edit=a1").text
    assert 'role="dialog"' in html and 'value="Venice Canals stroll"' in html and 'action="/calendar/activities/a1"' in html
    r = client.post("/calendar/activities/a1", data={**FORM, "title": "Canals at sunrise", "start": "09:00", "end": "10:00", "day": "2", "kind": "fun"}, follow_redirects=False)
    assert r.status_code == 303
    html = client.get("/calendar").text
    assert "Canals at sunrise" in html and "Venice Canals stroll" not in html and ids(html) == ["a1"]
    assert where(html, "a1")[:2] == (2, 540)


def test_moving_snaps_to_fifteen_minutes_and_a_clash_snaps_it_back(client):
    book(client)
    add(client)
    r = client.post("/calendar/activities/a1/move", data={"day": "3", "start": "14:08", "end": "15:38"}, follow_redirects=False)
    assert r.status_code == 303
    assert where(client.get("/calendar").text, "a1") == (3, 855, 945)
    r = client.post("/calendar/activities/a1/move", data={"day": "0", "start": "09:00", "end": "10:00"}, follow_redirects=False)
    assert r.status_code == 409 and "overlaps" in r.text
    assert where(client.get("/calendar").text, "a1")[0] == 3


def test_a_booked_block_cannot_be_moved(client):
    book(client)
    r = client.post("/calendar/activities/b-out/move", data={"day": "0", "start": "10:00", "end": "11:00"}, follow_redirects=False)
    assert r.status_code == 409 and "locked" in r.text


def test_delete_offers_undo_and_undo_brings_it_back(client):
    book(client)
    add(client)
    client.post("/calendar/notes", data={"id": "n2", "text": "Go early", "act": "a1"})
    r = client.post("/calendar/activities/a1/delete", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/calendar?undo=a1"
    html = client.get(r.headers["location"]).text
    assert ids(html) == [] and "Undo" in html and 'action="/calendar/undo"' in html and "Venice Canals stroll" in html
    assert "Go early" not in html
    client.post("/calendar/undo", data={"id": "a1"})
    html = client.get("/calendar").text
    assert ids(html) == ["a1"] and "Go early" in html
    assert client.post("/calendar/activities/a1/delete", follow_redirects=False).status_code == 303
    assert client.post("/calendar/activities/a1/delete", follow_redirects=False).status_code == 303  # a refresh


def test_trip_notes_appear_in_the_feed_with_the_activity_they_are_about(client):
    book(client)
    add(client)
    client.post("/calendar/notes", data={"id": "n2", "text": "Bring hats for everyone"})
    client.post("/calendar/notes", data={"id": "n3", "text": "Pier first thing", "act": "a1"})
    client.post("/calendar/notes", data={"id": "n3", "text": "Pier first thing", "act": "a1"})  # refresh
    html = client.get("/calendar").text
    assert "Bring hats for everyone" in html and html.count("Pier first thing") == 1
    assert "on Venice Canals stroll" in html and "Trip notes" in html and 'name="text"' in html
    assert 'value="n4"' in html  # the composer carries the next id


def test_text_is_escaped_everywhere(client):
    book(client)
    evil = "<script>alert(1)</script>"
    add(client, title=evil[:40])
    client.post("/calendar/notes", data={"id": "n2", "text": evil, "act": "a1"})
    for url in ["/calendar", "/calendar?edit=a1", "/calendar?view=whole", "/calendar?undo=a1"]:
        html = client.get(url).text
        assert "<script>alert" not in html, url
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in client.get("/calendar").text
    r = add(client, id="a9", title='"><img src=x onerror=alert(1)>', day="0", start="09:00", end="10:00")
    assert "<img src=x" not in r.text


def test_the_long_demo_has_twenty_day_chips_and_a_month_crossing_title(client):
    book(client)
    html = client.get("/calendar?demo=long").text
    assert html.count("data-chip=") == 20 and html.count("data-day-head") == 20
    assert "Oct 16 – Nov 4" in html and "Oct 16 – 4" not in html
    chip = tag(html, "data-chip", "16")  # Nov 1
    assert "Sunday Nov 1" in chip["aria-label"]
    assert '<span class="cal-chip-mon">Nov</span><span class="cal-chip-num">1</span>' in html
    assert html.count('<span class="cal-chip-mon">Oct</span>') == 1 and html.count('<span class="cal-chip-mon">Nov</span>') == 1
    assert '<span>SUN</span><span class="cal-mon">NOV</span>' in html and '<span>FRI</span><span class="cal-mon">OCT</span>' in html  # day headers name the month when it changes
    assert html.count("data-day-head") == 20
    assert 'data-block="b-back"' in html and tag(html, "data-block", "b-back")["data-day"] == "19"
    assert 'value="long"' in html  # forms carry the demo through
    assert len(ids(html)) >= 4 and "Oct 16 – 20" not in html


def test_the_default_trip_hides_the_demo_and_keeps_its_own_activities(client):
    book(client)
    add(client, demo="long", id="a20", day="10")
    assert "a20" in ids(client.get("/calendar?demo=long").text)
    assert "a20" not in ids(client.get("/calendar").text)
    assert client.get("/calendar").text.count("data-chip=") == 5


def test_the_whole_trip_view_lists_every_day_and_calls_out_empty_ones(client):
    book(client)
    add(client)
    html = client.get("/calendar?view=whole").text
    assert html.count("data-whole-day") == 5
    assert "Venice Canals stroll" in html and "wide open" in html
    assert 'aria-current="true"' in html and "Whole trip" in html


def test_the_notes_drawer_and_top_bar_buttons_are_present(client):
    book(client)
    html = client.get("/calendar").text
    for label in ["Your forks", "Invite", "Share trip"]:
        assert label in html
    for href in ["/forks", "/invite", "/share"]:
        assert client.get(href).status_code == 200
    assert 'id="cal-notes"' in html and 'aria-label="Trip notes"' in html


def test_calendar_state_survives_the_signed_session_cookie(client):
    book(client)
    add(client)
    assert session_data(client)["cal"]["ari"]["a"][0]["t"] == "Venice Canals stroll"


def test_day_headers_show_a_weather_icon_and_temperature_without_cutting_the_words(client):
    book(client)
    html = client.get("/calendar").text
    head = html[html.index('data-day-head="0"'):html.index('data-day-head="1"')]
    assert "75°F" in head and "<svg" in head and ', clear skies' in head and 'title="clear skies"' in head


def test_the_first_trip_note_is_written_by_the_traveler(client):
    book(client, traveler="sam")
    html = client.get("/calendar").text
    feed = html[html.index('id="cal-feed"'):]
    assert "You · whole trip" in feed and ">SK<" in feed and "Trip · booked" not in html
