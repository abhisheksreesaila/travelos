"""The trip, its calendar, friends and remembered picks live in the family database: the cookie holds only the sign-in (F-040)."""

from gitaway import session as ses, tripcal as cal
from tests.test_calendar import FORM, book
from tests.test_signin import session_data, sign_in, stored_calendar

LIMIT = 3600  # bytes for the cookie value; browsers drop cookies over ~4096


def cookie_size(client):
    return len(client.cookies.get("session_") or "")

