"""F-046: a viewer sees no live "Schedule an Uber" links (like the add links); editors still do."""
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

