"""The trip, its calendar, friends and remembered picks live in the family database: the cookie holds only the sign-in (F-040)."""

from gitaway import session as ses, tripcal as cal
from tests.test_calendar import FORM, book
from tests.test_signin import session_data, sign_in, stored_calendar

LIMIT = 3600  # bytes for the cookie value; browsers drop cookies over ~4096


def cookie_size(client):
    return len(client.cookies.get("session_") or "")


def test_a_full_calendar_with_a_booking_and_friends_leaves_the_cookie_holding_only_the_sign_in(client):
    sign_in(client)
    book(client)
    empty = cookie_size(client)
    for name in ["Mom", "Sam", "Grandma Rosalind", "Uncle Bartholomew"]:
        client.post("/calendar/friends", data={"name": name})
    client.post("/calendar/live")
    for i in range(60):
        r = client.post("/calendar/activities", data={**FORM, "id": f"a{i + 1}", "day": str(1 + i % 3), "start": f"{8 + i % 12:02d}:00", "end": f"{8 + i % 12:02d}:30", "title": "x" * 40}, follow_redirects=False)
        assert r.status_code == 303
    for i in range(20):
        client.post("/calendar/notes", data={"id": f"n{900 + i}", "text": "y" * 140})
    client.get("/plan?f=f2&h=h3&c=c1&rooms=cy1&add=bf&d=2026-10-16&r=2026-10-19&a=3&k=4,7")
    assert len(stored_calendar()["a"]) > 60 and len(stored_calendar()["n"]) >= 20  # it all went to the database
    assert set(session_data(client)) <= set(ses.AUTH_KEYS)  # and none of it to the cookie
    assert cookie_size(client) <= empty + 40  # the cookie did not grow (the one login timestamp aside)
    assert cookie_size(client) <= LIMIT


def test_the_calendar_has_a_ceiling_so_a_family_cannot_grow_its_database_without_end(client, monkeypatch):
    monkeypatch.setattr(cal, "MAX_ACTIVITIES", 5)
    book(client)
    codes = [client.post("/calendar/activities", data={**FORM, "id": f"a{i + 1}", "day": str(1 + i % 3), "start": f"{8 + i:02d}:00", "end": f"{8 + i:02d}:30"}).status_code for i in range(8)]
    assert 409 in codes and len(stored_calendar()["a"]) == 5
    assert "a lot planned" in client.post("/calendar/activities", data={**FORM, "id": "a99", "start": "19:00", "end": "19:30"}).text
