"""The helpers many tests share (book, add, tag, PICK, FORM) and the invitation address /invite. The old trip calendar's addresses, and every page that went with it, are in tests/test_retired.py (F-254)."""

import re
from types import SimpleNamespace

from tests.test_signin import person, sign_in

PICK = {"f": "f1", "h": "h1", "c": "c1"}
FORM = {"day": "1", "start": "10:00", "end": "11:30", "title": "Venice Canals stroll", "kind": "outdoors"}
_LAST = {"traveler": "ari"}      # who `book` signed in last: `add` writes to that family


def book(client, traveler="ari", **pick):
    """Sign `traveler` in and book the sample trip with the given picks (the default ones: f1, h1, c1), as the old checkout did: the quote is the catalog's, the booking is the family's own.
    Answers like the old POST /pay: a 303 to the trip."""
    from gitaway import catalog, session as ses
    sign_in(client, traveler)
    _LAST["traveler"] = traveler
    trip = catalog.trip_from_url("", "", "", "", "", "", "")
    picked = {**PICK, **pick}
    flight, hotel, car = (None if picked[k] in ("", "none") else picked[k] for k in ("f", "h", "c"))      # "none" skips a lane, as the old form did
    stay = catalog.stay_pick(hotel, None, None, trip) if hotel else None
    fare = catalog.flight_pick(flight, None, None, trip) if flight else None
    ses.book(person(traveler), catalog.quote(flight, hotel, car, stay, trip, fare))
    return SimpleNamespace(status_code=303, headers={"location": "/trip/plan"})


def add(client, id="a1", traveler=None, **over):
    """A plan on the trip, written as the calendar does (the plan runs an hour from its start unless `end` is given). Answers 303, or 409 with the calendar's own words in `.text`."""
    from gitaway import tripcal as cal
    vals = {**FORM, **over, "id": id}
    start = cal.snap(cal.parse_time(vals["start"], "start"))
    end = over.get("end") or cal.hhmm(start + 60)
    try:
        cal.add_activity(person(traveler or _LAST["traveler"]), day=vals["day"], start=vals["start"], end=end, title=vals["title"], kind=vals["kind"], id=id)
    except cal.CalendarError as e:
        return SimpleNamespace(status_code=409, text=str(e))
    return SimpleNamespace(status_code=303, text="")


def tag(html, attr, value):
    """The attributes of the first tag carrying attr="value", as a dict (attribute order is not part of the contract)."""
    m = re.search(r'<[a-z0-9]+\s[^>]*\b%s="%s"[^>]*>' % (re.escape(attr), re.escape(value)), html)
    return dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(0))) if m else None


def test_invite_goes_to_the_invitations_in_family(client):
    book(client)
    r = client.get("/invite", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/family#invite"


def test_invite_signed_out_signs_in_first_and_comes_back_to_family(client):
    r = client.get("/invite", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=%2Ffamily")
    assert "intent=invite" in r.headers["location"]
