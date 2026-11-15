"""F-035: the trip lives in the URL through the workspace, sign-in, pay, booking and the calendar."""
import html as htmllib
import re
from datetime import date
from urllib.parse import quote, urlsplit, parse_qs

from gitaway import catalog, session as ses, tripcal
from tests.test_signin import person, session_data, sign_in, stored_booking, tid

SAMPLE = catalog.SAMPLE_TRIP
THREE_NIGHTS = "d=2026-10-16&r=2026-10-19&a=2&k=4,7"
THREE_ADULTS = "d=2026-10-16&r=2026-10-20&a=3&k=4,7"
T3 = catalog.trip_from_url("2026-10-16", "2026-10-19", "2", "4,7")
T5 = catalog.trip_from_url("2026-10-16", "2026-10-20", "3", "4,7")
PICK = "f=f1&h=h1&c=c1"


def ws_total(html):
    return re.search(r'id="ws-total"[^>]*>([^<]*)<', html).group(1)


def money(trip, f="f1", h="h1", c="c1", **kw):
    return catalog.money(catalog.quote(f, h, c, trip=trip, **kw).total_cents)


def hrefs(html):
    return [htmllib.unescape(h) for h in re.findall(r'href="([^"]*)"', html)]


def test_a_one_night_trip_still_works_on_its_days(client):
    sign_in(client)
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-16", "r": "2026-10-17", "a": "1"})
    assert client.get("/calendar").status_code == 200
    assert client.get("/trip/canvas?day=1").status_code == 200 and client.get("/trip?day=1").status_code == 200


def test_long_demo_never_returns_before_departing():
    from gitaway import tripcal
    late = catalog.TripSearch("SFO", "San Francisco", "Los Angeles", ("LAX",), date(2026, 12, 1), date(2026, 12, 3), 2, ())
    t = tripcal.trip("long", {"trip": catalog.trip_query(late)})
    assert t.return_ > t.depart

