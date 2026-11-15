"""F-046: a public shared page does not say when or where a family is away: the hotel and the car's places are an area or a code, never a street. (The old one-tap /share page retired in F-254; the
snapshot is still built by gitaway/share.py, and a family's published trip is still read at /trips/<slug>.)"""
import re
from html import unescape

import pytest

from gitaway import community, share
from tests.test_signin import person, tid
from tests.test_trip_import import TEMPLATE, imported


def slug_of(client, who="ari"):
    return community.rows(kind="shared", owner=tid(who))[0]["slug"]


def post_share(client):
    """Share the open trip with the default tags, through the model (what the old page's button did)."""
    return share.publish(person("ari"))


def public_text(client, slug):
    """What a stranger sees and what is stored: the page's main part and the stored snapshot."""
    client.cookies.clear()
    page = client.get(f"/trips/{slug}").text.split("<main")[1].split("</main>")[0]
    row = community.get(slug)
    drawn = re.compile(r"<svg.*?</svg>", re.S)
    return unescape(drawn.sub("", page) + repr(row))





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
