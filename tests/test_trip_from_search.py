"""F-210 part A: a booking search becomes the family's trip ("Make this a trip"), landing on the cockpit. (F-231: Where to? was the other form that took a typed place; it is gone.)

Off the showcase (how production runs) /plan's any-place lanes carry a "Make this a trip" form that
POSTs /trip/new. Signed out, that form goes to sign-in and comes back to /trip/new to finish; a viewer is refused by the role guard and nothing is written."""

import re
from html import unescape
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from gitaway import familydb, session as ses
from tests.test_roles import crew  # noqa: F401 (the fixture)
from tests.test_showcase import assert_real
from tests.test_signin import person, sign_in

WHEN = {"d": "2026-12-04", "r": "2026-12-09", "a": "2"}


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")


def text(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def form_html(html, form_id):
    m = re.search(r'<form\b[^>]*id="%s"[^>]*>.*?</form>' % form_id, html, re.S)
    assert m, f"no form #{form_id}"
    return m.group(0)


def open_trip(traveler="ari"):
    """The trip row `traveler` has open, read from their family database (None when there is none)."""
    with ses.family(person(traveler)) as fam:
        return dict(familydb.trip(fam.db, fam.trip_id) or {}) or None if fam else None


def trip_count(traveler="ari"):
    with ses.family(person(traveler)) as fam:
        return familydb.row(fam.db, "SELECT COUNT(*) AS n FROM trips")["n"]


# ---- the booking lanes offer it ---------------------------------------------------------------------------------------------
# (F-231: Where to? was the other place that took a typed place and made a trip; its tests went with it. An old Where to? link is tests/test_way_in.py's.)

# ---- Make this a trip ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("typed, zone", [("Paris, Texas", "America/Chicago"), ("Athens, Georgia", "America/New_York"), ("Lisbon", "Europe/Lisbon")])
def test_a_us_town_named_after_a_foreign_city_keeps_its_states_clock(typed, zone):
    """Review fix: the state the person typed outranks a zone named after the town."""
    from gitaway import tripstart
    from gitaway.partners import places
    assert tripstart.zone(places.resolve(typed)) == zone
