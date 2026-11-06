"""F-194 (1): a trip is matched to a place GitAway can plan only when the destination is unambiguous. A Walt Disney World, Disneyland Paris or Lake Tahoe trip must not
become "Los Angeles, California" with LAX flights under a creator's name; where a place cannot be planned, the trip page says so."""

import re
from html import unescape

import pytest

from gitaway import creatordraft, publish
from tests.live_trips import live_trip
from tests.pagebody import without_bar


@pytest.mark.parametrize("destination, key", [
    ("Walt Disney World, Florida", ""), ("Walt Disney World Resort, Orlando", ""), ("Disneyland Paris", ""), ("Disneyland Resort Paris", ""), ("Hong Kong Disneyland Resort", ""), ("Tokyo Disneyland", ""), ("Disney", ""),
    ("Lake Tahoe, California", ""), ("Yosemite National Park, California", ""), ("San Francisco, California", ""), ("Napa Valley, California", ""), ("California", ""),
    ("Maui, Hawaii", ""), ("Kauai, Hawaii", ""), ("Big Island, Hawaii", ""), ("Hawaii", ""),
    ("Queenstown, New Zealand", ""),                                       # "queens" inside another word is not Queens
    ("Anaheim, California", "la"), ("Disneyland Resort, Anaheim", "la"), ("Disneyland Resort", "la"), ("Los Angeles, California", "la"), ("Santa Monica", "la"),
    ("San Diego, California", "sd"), ("La Jolla, California", "sd"), ("Coronado, California", "sd"),
    ("Honolulu, Hawaii", "hi"), ("Oahu, Hawaii", "hi"), ("Waikiki Beach", "hi"),
    ("Brooklyn, New York", "nyc"), ("New York City", "nyc"),
])
def test_a_destination_maps_to_a_place_we_plan_only_when_it_is_unambiguous(destination, key):
    assert publish.place_key(destination) == key


def test_a_family_trip_that_flies_to_an_airport_we_plan_keeps_its_place():
    assert publish.place_key("Our long weekend", {"LAX"}) == "la" and publish.place_key("Our long weekend", {"HNL"}) == "hi"
    assert publish.place_key("Maui", {"OGG"}) == ""


def _draft(place, place_name, post):
    answer = {"title": "A trip", "place": place, "place_name": place_name, "days_count": 1, "days": [{"stops": [{"name": "Anaheim", "time": "", "note": ""}]}], "tips": [], "stickers": []}
    return creatordraft.validate(answer, post)


@pytest.mark.parametrize("name", ["Walt Disney World, Florida", "Disneyland Paris", "Tokyo Disneyland", "Lake Tahoe, California", "Maui, Hawaii"])
def test_a_drafted_trip_the_model_called_other_stays_other_with_its_own_name(name):
    d = _draft("other", name, "We went to Anaheim.")
    assert (d["place"], d["place_name"]) == ("other", name)


def test_a_place_the_post_never_names_is_not_trusted_just_because_the_model_said_so():
    """The model called a Disneyland Paris post "la": the post says nothing of Los Angeles, Anaheim or the Resort, so the creator is asked where it was."""
    paris = "Day one at Disneyland Paris with the kids. We stayed at a hotel near Disneyland Paris and rode Space Mountain."
    d = _draft("la", "", paris)
    assert (d["place"], d["place_name"]) == ("other", "") and "Say where the trip was." in creatordraft.problems({**d, "name": "Maya", "title": "A trip"})


def test_a_place_the_post_names_is_kept():
    assert _draft("la", "", "Three days in Anaheim and a day in Santa Monica.")["place"] == "la"
    assert _draft("sd", "", "A weekend in La Jolla and Coronado.")["place"] == "sd"
    assert _draft("hi", "", "Our week on Oahu: Waikiki, then the North Shore.")["place"] == "hi"
    assert _draft("nyc", "", "Four days in Manhattan and Brooklyn.")["place"] == "nyc"


def test_a_post_about_the_california_disneyland_is_la_even_when_it_only_says_disneyland():
    assert _draft("la", "", "We spent two days at Disneyland with our toddlers and a third at California Adventure.")["place"] == "la"
    # ...unless it also names another Disney resort: then GitAway cannot tell which
    assert _draft("la", "", "We loved Disneyland, but our trip was to Disneyland Paris.")["place"] == "other"


def test_the_prompt_tells_the_model_which_destinations_are_not_ours():
    for words in ("Disneyland Resort", "Walt Disney World", "Disneyland Paris", "Maui", "Lake Tahoe"):
        assert words in creatordraft.SYSTEM


# ---- the trip page says when a place cannot be planned -------------------------------------------------------------------------------------------------

def _tahoe(client, marker=False):
    from gitaway import affiliate
    row, handle, owner = live_trip(place="Lake Tahoe, California", plan_to="")
    if marker:
        affiliate.set_marker(owner["user_id"], "555111")
    return without_bar(client.get(f"/trips/{row['slug']}").text)


def test_a_trip_at_a_place_we_cannot_plan_says_so_instead_of_offering_a_plan_button(client):
    page = _tahoe(client)
    assert 'id="plan-this"' not in page
    says = re.search(r'id="plan-unavailable"[^>]*>(.*?)</', page)
    assert says and unescape(says.group(1)) == "GitAway can't plan a trip to Lake Tahoe, California yet, so there is no Plan this trip button here. It plans Los Angeles, San Diego, Honolulu and New York City."


def test_the_lede_names_the_place_the_post_is_about_never_los_angeles():
    d = _draft("other", "Lake Tahoe, California", "We skied at Lake Tahoe.")
    trip = creatordraft.build({**d, "id": "0" * 16, "slug": "tahoe-a1b2c3", "live": False, "name": "Maya Chen", "source": {}, "images": [], "picks": [], "copies": {}, "cover": ""}, lambda n: "")
    assert (trip.place, trip.lede, trip.plan_to) == ("Lake Tahoe, California", "1 day in Lake Tahoe, California, from Maya Chen's own post.", "")


def test_a_trip_with_no_booking_path_does_not_claim_anyone_earns_from_bookings(client):
    page = _tahoe(client, marker=True)
    assert "Flights booked from this trip" not in page
    assert re.search(r'id="who-earns"[^>]*>Nothing on this page can be booked, so nobody earns from it\.<', page)


def test_a_trip_at_a_place_we_plan_still_has_its_plan_button_and_no_apology(client):
    row, _handle, _ = live_trip()
    page = without_bar(client.get(f"/trips/{row['slug']}").text)
    assert 'id="plan-this"' in page and "plan-unavailable" not in page
