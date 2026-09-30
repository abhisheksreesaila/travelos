"""The whole signed session cookie must stay well under the 4 KB browsers keep, even with a full calendar."""

from tests.test_calendar import FORM, book
from tests.test_signin import sign_in

LIMIT = 3600  # bytes for the cookie value; browsers drop cookies over ~4096


def cookie_size(client):
    return len(client.cookies.get("session_") or "")


def test_a_full_calendar_with_a_booking_and_forks_stays_under_the_cookie_limit(client):
    sign_in(client)
    for slug in ["sun-tacos-and-tide-pools", "weekend-in-the-redwoods-loop", "kid-friendly-tokyo-in-five-days", "pup-friendly-coast-road-trip", "couples-wine-country-long-weekend"]:
        sign_in(client, next=f"/trips/{slug}", intent="fork")
    book(client)
    for name in ["Mom", "Sam", "Grandma Rosalind", "Uncle Bartholomew"]:
        client.post("/calendar/friends", data={"name": name})
    client.post("/calendar/live")
    assert cookie_size(client) <= LIMIT
    refused = False
    for i in range(300):
        r = client.post("/calendar/activities", data={**FORM, "id": f"a{i + 1}", "day": str(1 + i % 3), "start": f"{8 + i % 12:02d}:00", "end": f"{8 + i % 12:02d}:30", "title": "x" * 40}, follow_redirects=False)
        if r.status_code == 409:
            refused = True
            break
        assert cookie_size(client) <= LIMIT
    assert refused, "the calendar never said it was full"
    for i in range(5):
        client.post("/calendar/notes", data={"id": f"n{900 + i}", "text": "y" * 140})
    assert cookie_size(client) <= LIMIT
    assert cookie_size(client) > 2000  # the test really filled it


def test_friends_alone_cannot_push_the_cookie_over_the_limit(client):
    sign_in(client)
    for slug in ["sun-tacos-and-tide-pools", "weekend-in-the-redwoods-loop", "kid-friendly-tokyo-in-five-days", "pup-friendly-coast-road-trip", "couples-wine-country-long-weekend"]:
        sign_in(client, next=f"/trips/{slug}", intent="fork")
    book(client)
    for i in range(10):
        client.post("/calendar/friends", data={"name": f"Friend number {i:02d} x"})
        assert cookie_size(client) <= LIMIT
