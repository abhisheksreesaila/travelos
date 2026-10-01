"""F-046: a viewer sees no "Talk to plan" and no live "Schedule an Uber" links (like the add links); editors still do."""
import pytest

from tests.test_calendar import book
from tests.test_crew_calendar import named
from tests.test_members import browser, invite
from tests.test_signin import sign_in


@pytest.fixture
def pair(client):
    """Ari (admin) with a booking that has no car, so rides are offered; and Vi, a viewer, in another browser."""
    book(client, c="none")
    vi = named("vi.ewer")
    invite(client, vi, "viewer")
    other = browser(client)
    sign_in(other, vi)
    return client, other


def test_a_viewer_does_not_get_talk_to_plan_or_live_uber_links_on_the_calendar(pair):
    ari, vi = pair
    editor = ari.get("/calendar?view=days").text
    assert "Talk to plan" in editor and "Schedule an Uber" in editor and 'data-offer="ro-arrive"' in editor
    seen = vi.get("/calendar?view=days").text
    assert "Talk to plan" not in seen and "Schedule an Uber" not in seen and "data-offer" not in seen and "/rides/new" not in seen
    whole = vi.get("/calendar?view=whole").text
    assert "Talk to plan" not in whole and "/rides/new" not in whole


def test_a_viewer_does_not_get_schedule_links_on_the_booking_pages(pair):
    ari, vi = pair
    assert "/rides/new" in ari.get("/booked").text
    assert "/rides/new" not in vi.get("/booked").text
    assert "/rides/new" in ari.get("/plan?f=f1&h=h1&c=none").text
    assert "/rides/new" not in vi.get("/plan?f=f1&h=h1&c=none").text


def test_a_viewer_still_sees_the_rides_that_are_scheduled(pair):
    ari, vi = pair
    from tests.test_rides import schedule
    assert schedule(ari).status_code == 303
    assert "Simulated ride" in vi.get("/calendar?view=days").text
