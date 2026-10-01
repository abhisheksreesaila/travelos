"""F-046: a brand new invite reads "expires in 14 days"."""
from datetime import datetime, timedelta, timezone

from gitaway.pages.family import _days_left
from tests.test_calendar import book
from tests.test_members import addr, invite


def test_a_new_invite_says_14_days_on_the_family_page(client):
    book(client)
    invite(client, addr("new"), "editor")
    assert "expires in 14 days" in client.get("/family").text


def test_days_round_up_so_a_few_seconds_do_not_cost_a_day():
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)

    def at(**d):
        return (now + timedelta(**d)).isoformat()

    assert _days_left(at(days=14), now) == "expires in 14 days"
    assert _days_left(at(days=14, seconds=-3), now) == "expires in 14 days"
    assert _days_left(at(days=13, hours=1), now) == "expires in 14 days"
    assert _days_left(at(days=2, seconds=-1), now) == "expires in 2 days"
    assert _days_left(at(hours=20), now) == "expires today"
    assert _days_left(at(seconds=-5), now) == "expires today"
    assert _days_left("nonsense", now) == ""
