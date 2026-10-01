"""F-046: a public shared page does not say when or where a family is away: no flight numbers, no calendar dates (Day 1…N),
and the hotel as its area, not its name. The family's own pages still show everything."""
import re
from html import unescape

import pytest

from gitaway import community, share
from tests.test_calendar import book
from tests.test_share import share as post_share, slug_of
from tests.test_signin import person, tid
from tests.test_trip_import import TEMPLATE, imported, no_car

MONTHS = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}"
WEEKDAY_DATE = r"\b(MON|TUE|WED|THU|FRI|SAT|SUN)[A-Za-z]*,?\s+" + MONTHS


def public_text(client, slug):
    """What a stranger sees and what is stored: the page's main part, the stored snapshot and the hub card."""
    client.cookies.clear()
    page = client.get(f"/trips/{slug}").text.split("<main")[1].split("</main>")[0]
    hub = client.get("/community").text.split("<main")[1].split("</main>")[0]
    row = community.get(slug)
    return unescape(page + hub + repr(row))


def assert_no_dates(text):
    assert not re.search(MONTHS, text, re.I), re.search(MONTHS, text, re.I).group(0)
    assert not re.search(r"\b20\d\d-\d\d-\d\d\b", text)
    assert not re.search(WEEKDAY_DATE, text, re.I)


def test_a_demo_trip_page_has_no_flight_numbers_dates_or_hotel_name(client):
    book(client)
    post_share(client)
    slug = slug_of(client)
    seen = public_text(client, slug)
    for hidden in ("Skylark Air 214", "Tidewater", "City-view"):
        assert hidden not in seen, hidden
    assert not re.search(r"\b214\b", seen)  # a whole number, not a piece of some random id
    assert_no_dates(seen)
    assert "Flight to LAX" in seen and "Flight home" in seen
    assert "Check in · a hotel in Santa Monica" in seen and "Check out · a hotel in Santa Monica" in seen
    assert "DAY 1" in seen and "DAY 5" in seen


def test_an_imported_trip_page_names_the_area_from_the_address_not_the_hotel(client):
    imported(client)
    post_share(client)
    seen = public_text(client, slug_of(client))
    for hidden in ("AS 1234", "AS 1235", "Alaska Airlines", "Example Hotel", "123 Ocean", "90401", "Expedia"):
        assert hidden not in seen, hidden
    assert_no_dates(seen)
    assert "Check in · a hotel in Santa Monica" in seen and "Flight to LAX" in seen


def test_two_hotels_each_get_their_own_area(client):
    two = TEMPLATE.replace("hotel:\n  name:", "hotels:\n  - name:").replace("  address: 123 Ocean Ave, Santa Monica, CA 90401\n  check_in: 2026-10-16 15:00\n  check_out: 2026-10-20 11:00\n  confirmation: \"987654321\"",
          "    address: 123 Ocean Ave, Santa Monica, CA 90401\n    check_in: 2026-10-16 15:00\n    check_out: 2026-10-18 11:00\n    confirmation: \"987654321\"\n"
          "  - name: The Second Inn\n    address: 45 Colorado Blvd, Pasadena, CA 91101\n    check_in: 2026-10-18 15:00\n    check_out: 2026-10-20 11:00\n    confirmation: \"123123123\"")
    two = re.sub(r"(    check_out: 2026-10-20 11:00\n    confirmation: \"123123123\")\n  room:.*?\n  rooms:.*?\n  phone:.*?\n", r"\1\n", two)
    imported(client, two)
    post_share(client)
    seen = public_text(client, slug_of(client))
    assert "Second Inn" not in seen and "a hotel in Pasadena" in seen and "a hotel in Santa Monica" in seen


@pytest.mark.parametrize("address,fallback,area", [
    ("123 Ocean Ave, Santa Monica, CA 90401", "LA", "Santa Monica"),
    ("123 Ocean Ave, Santa Monica, CA", "LA", "Santa Monica"),
    ("123 Ocean Ave, Santa Monica, California 90401, USA", "LA", "Santa Monica"),
    ("Santa Monica", "LA", "Santa Monica"),
    ("123 Ocean Ave", "Los Angeles", "Los Angeles"),
    ("", "Los Angeles", "Los Angeles"),
])
def test_area_of_an_address_is_the_city_never_the_street(address, fallback, area):
    assert share.area_of(address, fallback) == area


def test_the_family_still_sees_everything(client):
    imported(client)
    post_share(client)
    mine = unescape(client.get("/calendar?view=days").text + client.get("/trip/details").text)
    for shown in ("Alaska Airlines AS 1234", "The Example Hotel Santa Monica", "Oct 16"):
        assert shown in mine, shown


def test_resharing_updates_an_old_snapshot_and_an_old_one_stays_until_then(client):
    import dataclasses
    book(client)
    post_share(client)
    slug = slug_of(client)
    row = community.get(slug)
    trip = community.trip_of(row)
    # a snapshot made before F-046 held the real numbers; put one back as it was stored then
    days = [dataclasses.replace(d, date="FRI, OCT 16", stops=[dataclasses.replace(x, title=x.title.replace("Flight to LAX", "Skylark Air 214 · SFO → LAX")) for x in d.stops])
            for d in trip.days]
    community.publish(person(), dataclasses.replace(trip, days=days), kind="shared", tags=row["tags"], theme=row["theme"])
    assert "Skylark Air 214" in community.get(slug)["snapshot"]           # nothing rewrites old snapshots on its own
    post_share(client)                                                    # sharing again rebuilds it with the private wording
    fresh = community.get(slug)["snapshot"]
    assert "Skylark Air 214" not in fresh and "FRI, OCT 16" not in fresh and "Flight to LAX" in fresh


def test_a_car_pickup_at_a_street_or_hotel_address_shows_only_the_area_or_code(client):
    street = TEMPLATE.replace("pickup: LAX, 2026-10-16 10:00", "pickup: The Example Hotel, 2026-10-16 10:00")
    imported(client, street)
    post_share(client)
    seen = public_text(client, slug_of(client))
    assert "Example Hotel" not in seen
    assert "Pick up Hertz car · Los Angeles" in seen and "Drop off Hertz car · LAX" in seen


def test_public_place_is_a_code_or_an_area_never_a_street():
    assert share._public_place("LAX", "Los Angeles") == "LAX"
    assert share._public_place("123 Ocean Ave, Santa Monica, CA 90401", "Los Angeles") == "Santa Monica"
    assert share._public_place("123 Ocean Ave", "Los Angeles") == "Los Angeles"
    assert share._public_place("The Example Hotel", "Los Angeles") == "Los Angeles"
