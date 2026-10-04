"""F-054: the phone-first trip home at /trip, through the HTTP seam: before, during and after the trip, up next, directions, the add sheet
and its validation, roles, the trip field, and who is sent here."""

import re
from datetime import date
from html import unescape

import pytest

from gitaway import catalog, rides, tripday as td
from tests.test_calendar import book, tag
from tests.test_members import addr, browser, invite
from tests.test_signin import sign_in, stored_calendar
from tests.test_trip_import import SECRETS, TEMPLATE, imported, visible

IPHONE = {"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"}
ANDROID = {"user-agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile Safari/537.36"}


@pytest.fixture
def at(monkeypatch):
    """at(day, "16:20") pins today's date and the minute of the day in Los Angeles."""
    def pin(day, hhmm="12:00"):
        h, m = map(int, hhmm.split(":"))
        monkeypatch.setattr(catalog, "today", lambda *_: day)
        monkeypatch.setattr(td, "now_minute", lambda *_: h * 60 + m)
    return pin


def plan(client, id="a1", day="1", start="17:00", end="19:30", title="Griffith Observatory", kind="culture"):
    return client.post("/calendar/activities", data={"id": id, "day": day, "start": start, "end": end, "title": title, "kind": kind}, follow_redirects=False)


def raw(html, id_):
    """The opening tag with this id, as text (so boolean attributes like hidden can be seen)."""
    return re.search(r"<[a-z]+\b[^>]*\bid=\"%s\"[^>]*>" % id_, html).group(0)


def text(html):
    return " ".join(visible(html).split())


# ---- who can open it -----------------------------------------------------------------------------------------------------

def test_signed_out_goes_through_sign_in_and_a_signed_in_family_with_no_trip_goes_to_start(client):
    r = client.get("/trip", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/signin?next=%2Ftrip"
    for path in ("/trip/plans", "/trip/notes"):
        assert client.post(path, data={}, follow_redirects=False).status_code == 303
    sign_in(client)
    r = client.get("/trip", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/start"


def test_phones_are_sent_to_the_trip_view_from_a_plain_calendar_but_not_from_a_calendar_with_a_view(client):
    book(client)
    r = client.get("/calendar", headers=IPHONE, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip"
    assert client.get("/calendar", headers=ANDROID, follow_redirects=False).headers["location"] == "/trip"
    assert client.get("/calendar?view=whole", headers=IPHONE, follow_redirects=False).status_code == 200  # the "full calendar" link
    assert client.get("/calendar?view=days&add=1", headers=IPHONE, follow_redirects=False).status_code == 200
    assert client.get("/calendar", follow_redirects=False).status_code == 200  # a desktop keeps today's calendar
    assert client.get("/calendar", headers={"user-agent": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) Mobile/15E148 Safari/604.1"}, follow_redirects=False).status_code == 200


def test_the_installed_app_opens_on_the_trip_view_and_the_continue_card_lands_there_on_a_phone(client):
    assert client.get("/manifest.webmanifest").json()["start_url"] == "/trip"
    book(client)
    assert 'href="/calendar"' in client.get("/start").text
    assert 'href="/trip"' in client.get("/start", headers=IPHONE).text


# ---- before, during and after ----------------------------------------------------------------------------------------------

def test_before_the_trip_it_counts_the_days_and_shows_day_one(client, at):
    book(client)
    at(date(2026, 10, 12))
    html = client.get("/trip").text
    t = text(html)
    assert "TRIP STARTS IN 4 DAYS" in t and "Friday, Oct 16" in t
    assert "First up: Skylark Air 214 · SFO → LAX at 8:05 AM" in t
    assert 'id="tp-list"' in html and "Skylark Air 214" in html  # day one's plan is listed
    assert "UP NEXT" not in t
    at(date(2026, 10, 15))
    assert "TRIP STARTS TOMORROW" in text(client.get("/trip").text)


def test_after_the_trip_it_is_a_recap(client, at):
    book(client)
    plan(client)
    client.post("/calendar/notes", data={"id": "n1", "text": "Great trip"})
    at(date(2026, 10, 25))
    t = text(client.get("/trip").text)
    assert "WELCOME HOME" in t and "5 days in LA" in t and "1 plan · 1 note" in t
    assert "UP NEXT" not in t


def test_during_the_trip_the_next_thing_is_a_dark_card_with_a_countdown_and_the_past_is_faded(client, at):
    book(client)
    plan(client, "a1", "1", "09:00", "10:00", "Breakfast at the hotel", "food")
    plan(client, "a2", "1", "17:00", "19:30", "Griffith Observatory", "culture")
    plan(client, "a3", "1", "20:00", "21:00", "Tacos on Abbot Kinney", "food")
    at(date(2026, 10, 17), "16:20")
    html = client.get("/trip", headers=ANDROID).text
    up = html.split('id="tp-up"')[1].split('id="tp-list"')[0]
    assert "UP NEXT · IN 40 MIN" in text(up) and "Griffith Observatory" in up and "5:00 – 7:30 PM" in text(up)
    assert text(html).count("Griffith Observatory") >= 1  # in the card; the list below is "the rest of today" (F-067)
    states = re.findall(r'class="tp-row is-(\w+)"', html)
    assert states == ["done", "later"]
    assert "Saturday" in html.split("<h1")[1].split("</h1>")[0]
    assert "DAY 2 OF 5" in text(html)


def test_something_in_progress_says_happening_now(client, at):
    book(client)
    plan(client, "a1", "1", "17:00", "19:30", "Griffith Observatory", "culture")
    at(date(2026, 10, 17), "18:00")
    assert "HAPPENING NOW · ENDS IN 1 H 30 MIN" in text(client.get("/trip").text)


def test_nothing_left_today_says_so_and_names_tomorrows_first_plan(client, at):
    book(client)
    plan(client, "a1", "2", "09:30", "11:00", "Venice Canals stroll", "outdoors")
    at(date(2026, 10, 17), "22:00")
    t = text(client.get("/trip").text)
    assert "ALL DONE TODAY" in t and "Tomorrow starts with Venice Canals stroll at 9:30 AM." in t


# ---- directions, rides, flight and hotel cards -------------------------------------------------------------------------------

def test_directions_go_to_apple_or_google_maps_with_the_place_and_never_a_confirmation_number(client, at):
    imported(client)
    plan(client, "a1", "1", "17:00", "19:30", "Griffith Observatory", "culture")
    at(date(2026, 10, 17), "16:20")
    apple = client.get("/trip", headers=IPHONE).text
    assert unescape(tag(apple, "id", "tp-directions")["href"]) == "https://maps.apple.com/?q=Griffith+Observatory%2C+Los+Angeles"
    google = client.get("/trip", headers=ANDROID).text
    assert "https://www.google.com/maps/search/?api=1&amp;query=Griffith+Observatory%2C+Los+Angeles" in google
    for secret in SECRETS:
        assert secret not in apple and secret not in google


def test_a_ride_still_to_schedule_is_an_offer_card_and_a_scheduled_one_links_to_its_ride(client, at):
    """F-067: the up-next card's Uber is the keyless deep link; scheduling the simulated Uber moved to its card in the day's list."""
    from tests.test_rides import schedule
    book(client, f="f1", h="h1", c="none")
    at(date(2026, 10, 16), "06:00")
    html = client.get("/trip").text
    offer = re.search(r'<a[^>]*class="tp-card [^"]*tp-offer[^"]*"[^>]*>', html)
    assert offer and 'href="/rides/new?' in offer.group(0).replace("&amp;", "&")
    assert schedule(client, "arrive", pick="f=f1&h=h1&c=none").status_code == 303
    html = client.get("/trip").text
    ride = re.search(r'<a[^>]*class="tp-card [^"]*tp-ride[^"]*"[^>]*>', html)
    assert ride and 'href="/rides/r1"' in ride.group(0)


def test_the_arrival_day_has_a_flight_card_and_a_hotel_card_and_the_last_day_a_checkout_card(client, at):
    book(client)
    at(date(2026, 10, 17), "07:00")  # the arrival day, looked at from the next morning: its whole list shows
    html = client.get("/trip?day=0").text
    row = re.search(r'<a[^>]*class="tp-card [^"]*tp-flight[^"]*"|<div[^>]*class="tp-card [^"]*tp-flight[^"]*"', html)
    assert row and "FLIGHT" in text(html) and "Skylark Air 214 · SFO → LAX" in text(html)
    stay = html.split('id="tp-stay"')[1].split("</div></div>")[0]
    assert "Your hotel tonight" in text(stay) and "The Tidewater" in text(stay)
    at(date(2026, 10, 20), "10:00")
    assert "Checking out today" in text(client.get("/trip").text)


def test_an_imported_trip_shows_its_hotel_with_a_link_to_the_details_but_no_confirmation(client, at):
    imported(client)
    at(date(2026, 10, 17), "09:00")
    html = client.get("/trip").text
    assert "The Example Hotel Santa Monica" in text(html) and 'href="/trip/details"' in html
    for secret in SECRETS:
        assert secret not in html
    at(date(2026, 10, 16), "07:00")
    assert "Booked elsewhere" in text(client.get("/trip?day=0").text) or "booked on Expedia" in text(client.get("/trip?day=0").text)


# ---- the tabs ----------------------------------------------------------------------------------------------------------------

def test_all_days_has_a_tinted_tile_per_day_and_a_swipeable_strip_picks_the_day(client, at):
    book(client)
    plan(client, "a1", "1", "10:00", "11:30", "Pier", "outdoors")
    at(date(2026, 10, 17), "09:00")
    html = client.get("/trip?tab=days").text
    tiles = re.findall(r'<a[^>]*class="tp-tile[^"]*"[^>]*>', html)
    assert len(tiles) == 5 and "is-today" in tiles[1]
    assert "Fly in · check in" in text(html) and "Pier" in text(html) and "Wide open" in text(html) and "Fly home" in text(html)
    assert len(re.findall(r'class="tp-chip ', html)) == 5
    assert "DAY 2 OF 5" not in text(html) and "OCT 16 – 20" in text(html)  # the heading line is about the trip on this tab, not about today
    other = client.get("/trip?day=2").text
    assert "Sunday, Oct 18 · day 3 of 5" in text(other) and "Back to today" in text(other) and "UP NEXT" not in text(other)
    assert re.findall(r'class="tp-row is-(\w+)"', client.get("/trip?day=0").text) == ["done"] * len(re.findall(r'class="tp-row ', client.get("/trip?day=0").text))
    assert client.get("/trip?day=99").status_code == 200  # a day outside the trip falls back to today


def test_the_notes_tab_lists_the_feed_and_posting_a_note_goes_back_to_it(client):
    book(client)
    r = client.get("/trip?tab=notes")
    assert 'id="tp-composer"' in r.text and "Booked!" in text(r.text)
    html = r.text
    assert ["hidden" in raw(html, "tp-panel-" + n) for n in ("today", "days", "notes")] == [True, True, False]
    r = client.post("/trip/notes", data={"id": "n1", "text": "Bring sunscreen"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip?tab=notes"
    assert "Bring sunscreen" in client.get("/trip?tab=notes").text
    assert [n["t"] for n in stored_calendar()["n"]] == ["Bring sunscreen"]
    r = client.post("/trip/notes", data={"id": "n2", "text": "  "})
    assert r.status_code == 409 and "Write something first." in r.text


# ---- the + and the add sheet -------------------------------------------------------------------------------------------------

def test_the_add_sheet_has_a_title_a_start_time_and_a_kind_and_the_plus_opens_it(client, at):
    book(client)
    at(date(2026, 10, 17), "09:10")
    html = client.get("/trip").text
    assert 'id="tp-add"' in html and 'aria-label="Add a plan"' in html
    sheet = html.split('id="tp-sheet"')[1]
    assert 'name="title"' in sheet and 'type="time"' in sheet and 'name="start"' in sheet and 'data-time-picker' in sheet
    assert len(re.findall(r'name="kind"', sheet)) == 5
    assert re.search(r'name="start" value="09:30"', sheet)  # the first free half hour from now
    assert "data-open" not in tag(html, "id", "tp-sheet")
    opened = client.get("/trip?add=1&day=2").text
    assert "data-open" in tag(opened, "id", "tp-sheet") and "Add to Sunday, Oct 18" in text(opened)


def test_saving_the_sheet_adds_the_plan_with_the_calendars_validation(client, at):
    book(client)
    at(date(2026, 10, 12))
    r = client.post("/trip/plans", data={"id": "a1", "day": "2", "start": "10:00", "title": "Travel Town trains", "kind": "fun"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip?day=2&new=a1"
    assert [(a["d"], a["s"], a["e"], a["t"], a["k"]) for a in stored_calendar()["a"]] == [(2, 600, 660, "Travel Town trains", "fun")]  # an hour long
    assert "Added “Travel Town trains” at 10:00 AM" in text(client.get(r.headers["location"]).text)
    again = client.post("/trip/plans", data={"id": "a1", "day": "2", "start": "10:00", "title": "Travel Town trains", "kind": "fun"}, follow_redirects=False)
    assert again.status_code == 303 and len(stored_calendar()["a"]) == 1  # a refresh adds nothing
    # it shows on the calendar too: one source of truth
    assert "Travel Town trains" in client.get("/calendar?view=whole").text


def test_the_sheet_saves_plans_over_bookings_and_refuses_the_rest_keeping_what_was_typed(client):
    book(client)
    for i, (day, start, title) in enumerate((("0", "08:00", "Early swim"), ("0", "15:00", "Pool"), ("4", "13:30", "Last lunch"))):
        r = client.post("/trip/plans", data={"id": f"a{i + 1}", "day": day, "start": start, "title": title, "kind": "fun"}, follow_redirects=False)
        assert r.status_code == 303, title  # the arriving flight, the check in and the flight home are booked blocks: overlapping is fine (F-086)
    assert len(stored_calendar()["a"]) == 3
    r = client.post("/trip/plans", data={"id": "a7", "day": "9", "start": "10:00", "title": "Nowhere", "kind": "fun"})
    assert r.status_code == 409 and "data-open" in tag(r.text, "id", "tp-sheet") and 'value="Nowhere"' in r.text and 'value="10:00"' in r.text
    for bad in ({"day": "9", "start": "10:00", "title": "x"}, {"day": "1", "start": "", "title": "x"}, {"day": "1", "start": "10:00", "title": ""}, {"day": "1", "start": "10:00", "title": "x", "kind": "nope"}):
        assert client.post("/trip/plans", data={"id": "a9", **bad}).status_code == 409, bad
    assert len(stored_calendar()["a"]) == 3


def test_the_sheet_saves_a_time_that_overlaps_a_scheduled_ride(client):
    from tests.test_rides import schedule
    book(client, f="f1", h="h1", c="none")
    schedule(client, "arrive", pick="f=f1&h=h1&c=none")
    from gitaway import tripcal as cal
    from tests.test_signin import person
    s = person()
    t = cal.trip("", __import__("gitaway.session", fromlist=["x"]).booking(s))
    ride = next(b for b in cal.ride_blocks(s, __import__("gitaway.session", fromlist=["x"]).booking(s), t))
    r = client.post("/trip/plans", data={"id": "a1", "day": str(ride.day), "start": cal.hhmm(ride.start), "title": "Snack", "kind": "food"})
    assert r.status_code == 200 and stored_calendar()["a"]  # F-086


def test_every_post_form_on_the_trip_view_names_its_trip(client):
    book(client)
    for path in ("/trip", "/trip?tab=notes", "/trip?add=1"):
        html = client.get(path).text
        forms = [f for f in re.findall(r"<form\b[^>]*>.*?</form>", html, re.S) if 'method="post"' in f[:f.index(">")]]
        assert len(forms) >= 1
        for f in forms:
            assert 'name="trip"' in f, (path, f[:80])


def test_a_stale_tab_cannot_add_to_the_wrong_trip(client):
    book(client)
    from tests.test_signin import tid
    r = client.post("/trip/plans", data={"id": "a1", "day": "1", "start": "10:00", "title": "Nowhere", "trip": "t-not-ours", "kind": "fun"}, follow_redirects=False)
    assert stored_calendar()["a"] == [] and r.status_code in (303, 409)


# ---- roles -------------------------------------------------------------------------------------------------------------------

def test_a_viewer_sees_no_plus_no_sheet_no_composer_and_cannot_post(client):
    book(client)
    mail = addr("vi")
    invite(client, mail, "viewer")
    viewer = browser(client)
    sign_in(viewer, mail)
    for path in ("/trip", "/trip?tab=notes", "/trip?add=1"):
        html = viewer.get(path).text
        assert 'id="tp-add"' not in html and 'id="tp-sheet"' not in html and 'id="tp-composer"' not in html, path
        assert "You are a viewer in this family" in text(html)
        assert 'name="text"' not in html and 'name="title"' not in html
    assert viewer.post("/trip/plans", data={"id": "a1", "day": "1", "start": "10:00", "title": "Sneaky", "kind": "fun"}).status_code == 403
    assert viewer.post("/trip/notes", data={"id": "n1", "text": "Sneaky"}).status_code == 403
    assert stored_calendar()["a"] == [] and stored_calendar()["n"] == []


def test_an_editor_can_add(client):
    book(client)
    mail = addr("ed")
    invite(client, mail, "editor")
    editor = browser(client)
    sign_in(editor, mail)
    assert 'id="tp-add"' in editor.get("/trip").text
    assert editor.post("/trip/plans", data={"id": "a1", "day": "1", "start": "10:00", "title": "Pier", "kind": "outdoors"}, follow_redirects=False).status_code == 303


# ---- the page itself ---------------------------------------------------------------------------------------------------------

def test_the_page_has_the_tab_bar_the_phone_stylesheet_and_no_emoji(client):
    book(client)
    html = client.get("/trip").text
    assert re.findall(r'class="tp-tab"|class="tp-tab" ', html) or html.count("tp-tab")
    for name in ("Today", "All days", "Notes"):
        assert f">{name}</a>" in html
    assert html.index("/assets/css/base.css") < html.index("/assets/css/trip.css")
    assert "/assets/js/trip.js" in html and 'aria-current="page"' in html
    assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", html)


# ---- F-065: Today, laid out to read and share ----------------------------------------------------------------------------------

def share_attr(html):
    return unescape(tag(html, "id", "tp-share")["data-share-text"])


def test_each_place_has_a_directions_link_and_a_booking_shows_its_confirmation_only_after_a_tap(client, at):
    imported(client)
    plan(client, "a1", "1", "17:00", "19:30", "Griffith Observatory", "culture")
    at(date(2026, 10, 16), "08:00")
    html = client.get("/trip", headers=IPHONE).text
    assert html.count('data-dir="') >= 2  # the flight's airport and the hotel
    assert "https://maps.apple.com/?q=" in html
    inside = re.findall(r"<details.*?</details>", html, re.S)
    assert inside and any(s in "".join(inside) for s in SECRETS)  # the confirmation is in the tap
    assert not any(s in re.sub(r"<details.*?</details>", "", html, flags=re.S) for s in SECRETS)  # and nowhere else
    assert not any(s in share_attr(html) for s in SECRETS)
    at(date(2026, 10, 17), "12:00")
    plan_day = client.get("/trip", headers=ANDROID).text
    assert "https://www.google.com/maps/search/?api=1&amp;query=Griffith+Observatory" in plan_day


def test_a_plan_says_who_added_it_and_shows_the_notes_written_on_it(client, at):
    book(client)
    plan(client)
    client.post("/calendar/notes", data={"id": "n1", "text": "Bring jackets", "act": "a1"})
    at(date(2026, 10, 17), "12:00")
    html = text(client.get("/trip").text)
    assert "added by you" in html and "Bring jackets" in html


def test_the_shared_text_is_the_days_times_and_plans_with_no_prices_confirmations_or_notes(client, at):
    imported(client)
    plan(client, "a1", "0", "17:00", "19:30", "Griffith Observatory", "culture")
    client.post("/calendar/notes", data={"id": "n1", "text": "private-ish note", "act": "a1"})
    at(date(2026, 10, 16), "08:00")
    out = share_attr(client.get("/trip").text)
    lines = out.split("\n")
    assert lines[0].startswith("Fri Oct 16 · ") and "5:00 PM Griffith Observatory" in lines
    assert "$" not in out and "private-ish" not in out and not any(s in out for s in SECRETS)
    assert lines[-1].startswith("Hotel tonight: ")


def test_any_day_opens_with_day_and_today_is_the_default_before_during_and_after_the_trip(client, at):
    book(client)
    plan(client, "a1", "2", "10:00", "11:00", "Sunday brunch", "food")
    at(date(2026, 10, 10), "12:00")
    assert 'data-day="0"' in raw(client.get("/trip").text, "tp-app") and "Sun Oct 18" not in share_attr(client.get("/trip").text)
    at(date(2026, 10, 17), "12:00")
    assert 'data-day="1"' in raw(client.get("/trip").text, "tp-app")
    page = client.get("/trip?day=2").text
    assert 'data-day="2"' in raw(page, "tp-app") and "Sunday brunch" in page and "Sun Oct 18" in share_attr(page)
    at(date(2026, 10, 30), "12:00")
    assert 'data-day="4"' in raw(client.get("/trip").text, "tp-app")
    assert 'data-day="0"' in raw(client.get("/trip?day=0").text, "tp-app")


def test_a_viewer_can_share_the_day_and_the_calendar_links_to_it(client, at):
    book(client)
    plan(client)
    assert 'id="cal-today-view"' in client.get("/calendar?view=whole").text and "Today, to share" in text(client.get("/calendar?view=whole").text)
    mail = addr("vi2")
    invite(client, mail, "viewer")
    viewer = browser(client)
    sign_in(viewer, mail)
    at(date(2026, 10, 17), "12:00")
    html = viewer.get("/trip").text
    assert 'id="tp-share"' in html and "Griffith Observatory" in share_attr(html) and 'id="tp-add"' not in html
    assert 'id="cal-today-view"' in viewer.get("/calendar?view=whole").text


def test_the_calendars_today_link_carries_the_open_trip_and_lands_on_the_trip_view(client, at):
    book(client)
    plan(client)
    at(date(2026, 10, 17), "12:00")
    link = tag(client.get("/calendar?view=whole").text, "id", "cal-today-view")
    href = unescape(link["href"])
    assert re.fullmatch(r"/trip\?trip=\w+", href)
    r = client.get(href)
    assert r.status_code == 200 and 'id="tp-app"' in r.text and f'data-trip="{href.split("=")[1]}"' in r.text


def test_the_demo_bookings_share_text_has_no_prices(client, at):
    book(client)
    for day in (date(2026, 10, 16), date(2026, 10, 17), date(2026, 10, 20)):
        at(day, "08:00")
        out = share_attr(client.get("/trip").text)
        assert "$" not in out and out.startswith(day.strftime("%a %b") + f" {day.day} · ")


def test_a_plan_over_a_booking_or_another_plan_shows_an_overlaps_tag_on_the_day_list(client):
    book(client)
    assert plan(client, id="a1", day="0", start="09:00", end="10:00", title="Early swim", kind="fun").status_code == 303   # over the arriving flight
    assert plan(client, id="a2", day="0", start="09:30", end="10:30", title="Bagels", kind="food").status_code == 303      # and over the swim
    assert plan(client, id="a3", day="1", start="10:00", end="11:00", title="Alone", kind="fun").status_code == 303
    html = client.get("/trip?day=0").text
    tags = re.findall(r'<span[^>]*data-overlap="(\w+)"[^>]*>(.*?)</span>', html, re.S)
    said = {i: " ".join(visible(t).split()) for i, t in tags}
    assert said["a1"].startswith("Overlaps Skylark Air 214") and "Bagels" in said["a1"]
    assert said["a2"].startswith("Overlaps") and "Early swim" in said["a2"]
    assert 'data-overlap="a3"' not in client.get("/trip?day=1").text
