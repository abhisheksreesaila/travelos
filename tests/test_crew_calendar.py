"""Helpers for tests with a family of several people (the old calendar's avatars, presence line and pretend friends were retired in F-147, with their tests)."""

import uuid

from gitaway import familydb
from tests.test_signin import person


def named(local):
    """An address whose display name is clean ("sam.kim" -> Sam Kim) and that nobody else in the run uses."""
    return f"{local}@{uuid.uuid4().hex[:8]}.example.com"


def make_trip_real(traveler="ari"):
    """Turn the open trip into an imported one (what F-042 makes): not a demo trip any more."""
    with familydb.using(person(traveler)) as db:
        with familydb.transaction(db):
            familydb.run(db, "UPDATE trips SET source = 'imported'")
