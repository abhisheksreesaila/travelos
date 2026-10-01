"""F-054 review fixes: note slips on Today, the pulse, the sign-in Cancel, one Los Angeles zone."""
from datetime import date

from gitaway import catalog, tripday as td
from tests.test_calendar import book, tag
from tests.test_trip_phone import at, plan, text  # noqa: F401 - `at` is a fixture


def test_today_shows_the_newest_two_note_slips_under_the_hotel_card_with_a_link_to_all_notes(client, at):
    book(client)
    for i, t in enumerate(("Oldest note", "Bring sunscreen", "Churros after the observatory"), 1):
        client.post("/calendar/notes", data={"id": f"n{i}", "text": t})
    at(date(2026, 10, 17), "09:00")
    html = client.get("/trip").text
    today = html.split('id="tp-panel-today"')[1].split('id="tp-panel-days"')[0]
    tail = today.split('id="tp-stay"')[1]
    assert "Churros after the observatory" in tail and "Bring sunscreen" in tail and "Oldest note" not in tail
    assert tail.index("Bring sunscreen") < tail.index("Churros after") and 'class="tp-notetext"' in tail
    link = tag(tail, "data-tab-link", "notes")
    assert link["href"] == "/trip?tab=notes" and "All notes" in text(tail)


def test_today_has_no_note_strip_without_notes(client, at):
    book(client)
    at(date(2026, 10, 17), "09:00")
    assert "All notes" not in client.get("/trip").text


def test_only_up_next_and_happening_now_pulse(client, at):
    book(client)
    plan(client, "a1", "1", "17:00", "19:30", "Griffith Observatory", "culture")
    at(date(2026, 10, 17), "16:20")
    assert "tp-pulse" in client.get("/trip").text
    at(date(2026, 10, 17), "18:00")
    assert "tp-pulse" in client.get("/trip").text
    at(date(2026, 10, 17), "22:00")
    html = client.get("/trip").text
    assert "ALL DONE TODAY" in html and "tp-pulse" not in html


def test_cancel_on_the_sign_in_for_the_trip_view_goes_home_not_back_to_itself(client):
    from gitaway.pages import signin
    assert signin.cancel_href("/trip") == "/"
    assert signin.cancel_href("/trip?tab=notes") == "/"
    assert tag(client.get("/signin?next=%2Ftrip").text, "id", "si-cancel")["href"] == "/"


def test_one_los_angeles_zone_is_shared():
    from gitaway import rides
    assert td.TZ is catalog.TZ and rides.TZ is catalog.TZ
