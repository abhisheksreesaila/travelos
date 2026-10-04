"""F-085: a plan's notes on Today start folded behind a "1 note" / "N notes" tap, on the list rows and on the up-next card."""
from datetime import date

from tests.test_calendar import book
from tests.test_trip_phone import at, plan  # noqa: F401 - `at` is a fixture


def _today(client):
    html = client.get("/trip").text
    return html.split('id="tp-panel-today"')[1].split('id="tp-panel-days"')[0]


def _fold(html, act):
    """The opening <details ...> tag and the rest of the fold for one plan's notes."""
    head, tail = html.split(f'data-notes="{act}"')
    return head.rsplit("<details", 1)[1], tail.split("</details>")[0]


def test_a_list_rows_notes_are_folded_behind_a_note_count(client, at):
    book(client)
    plan(client, "a1", "1", "17:00", "19:30", "Griffith Observatory", "culture")
    plan(client, "a2", "1", "20:00", "21:00", "Tacos", "food")
    client.post("/calendar/notes", data={"id": "n1", "text": "Bring a jacket", "act": "a2"})
    client.post("/calendar/notes", data={"id": "n2", "text": "Park on Vermont", "act": "a2"})
    at(date(2026, 10, 17), "16:20")  # the observatory is up next, so Tacos is a list row
    opening, fold = _fold(_today(client), "a2")
    assert " open" not in opening + ">"  # folded by default
    assert "<summary" in fold and "2 notes" in fold.split("</summary>")[0]
    assert "Bring a jacket" in fold and "Park on Vermont" in fold


def test_one_note_says_1_note_and_a_plan_without_notes_has_no_fold(client, at):
    book(client)
    plan(client, "a1", "1", "17:00", "19:30", "Griffith Observatory", "culture")
    plan(client, "a2", "1", "20:00", "21:00", "Tacos", "food")
    client.post("/calendar/notes", data={"id": "n1", "text": "Bring a jacket", "act": "a2"})
    at(date(2026, 10, 17), "16:20")
    today = _today(client)
    assert "1 note<" in _fold(today, "a2")[1] and 'data-notes="a1"' not in today


def test_the_up_next_cards_notes_are_folded_too(client, at):
    book(client)
    plan(client, "a1", "1", "17:00", "19:30", "Griffith Observatory", "culture")
    client.post("/calendar/notes", data={"id": "n1", "text": "Bring a jacket", "act": "a1"})
    at(date(2026, 10, 17), "16:20")
    up = _today(client).split('id="tp-up"')[1].split('id="tp-stay"')[0]
    opening, fold = _fold(up, "a1")
    assert " open" not in opening + ">" and "1 note" in fold.split("</summary>")[0] and "Bring a jacket" in fold
