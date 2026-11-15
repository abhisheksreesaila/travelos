"""M1: four places (la, sd, hi, nyc), each with its own flights, stays, cars and prices, carried by `to=` in every trip URL."""
import re
from urllib.parse import parse_qs

import pytest

from gitaway import catalog
from tests.test_signin import sign_in

TRIP = "d=2027-03-05&r=2027-03-09&a=2&k=4,7"
AIRPORTS = {"la": ["LAX", "BUR"], "sd": ["SAN"], "hi": ["HNL"], "nyc": ["JFK", "EWR"]}


def trip(to):
    return catalog.trip_from_url("2027-03-05", "2027-03-09", "2", "4,7", to)


def text(html):
    return re.sub(r"<[^>]+>", " ", html)


@pytest.mark.parametrize("to", AIRPORTS)
def test_each_place_lists_its_own_airports_and_three_lanes(to):
    t = trip(to)
    assert list(t.airports) == AIRPORTS[to]
    assert {o.airport for o in catalog.offers("flight", t)} == set(AIRPORTS[to])
    assert len(catalog.offers("stay", t)) == 3 and len(catalog.offers("car", t)) == 2
    assert len({o.id for k in ("flight", "stay", "car") for o in catalog.offers(k, t)}) >= 8


def test_prices_differ_by_place_and_are_integer_cents_that_repeat():
    cheapest = {to: catalog.cheapest(trip(to)).total_cents for to in AIRPORTS}
    assert len(set(cheapest.values())) == 4
    assert cheapest == {to: catalog.cheapest(trip(to)).total_cents for to in AIRPORTS}
    assert all(isinstance(c, int) for c in cheapest.values())
    assert cheapest["hi"] > cheapest["sd"] and cheapest["nyc"] > cheapest["la"] > cheapest["sd"]


def test_los_angeles_prices_are_unchanged():
    assert [o.price_cents for o in catalog.offers("flight")] == [123_600, 110_400, 139_200, 96_800, 118_000]
    assert catalog.trip_query(catalog.SAMPLE_TRIP) == ""
    assert catalog.trip_query(trip("la")) == "d=2027-03-05&r=2027-03-09&a=2&k=4,7"


@pytest.mark.parametrize("to", AIRPORTS)
def test_the_trip_round_trips_through_its_query(to):
    t = trip(to)
    q = {k: v[0] for k, v in parse_qs(catalog.trip_query(t)).items()}
    assert catalog.trip_from_url(q.get("d"), q.get("r"), q.get("a"), q.get("k"), q.get("to")) == t


def test_a_place_with_no_other_params_is_the_sample_dates_there():
    t = catalog.trip_from_url("", "", "", "", "hi")
    assert t.destination_name == "Honolulu" and t.depart == catalog.SAMPLE_TRIP.depart
    assert catalog.trip_from_url("", "", "", "", "mars") == catalog.SAMPLE_TRIP


def test_the_ride_estimate_uses_the_places_airport_and_table(client):
    q = catalog.quote("hif1", "hih1", None, trip=trip("hi"))
    assert q.rides.airport == "HNL" and q.rides.legs[0].route == "HNL → Waikiki"
    q = catalog.quote("nycf4", None, None, trip=trip("nyc"))
    assert q.rides.legs[0].route == "EWR → New York" and q.rides.detail == "EWR to the city, both ways"


# ---- F-222: a hand-made list of nearby places for "or nearby" ----

def test_san_diego_is_near_los_angeles_and_orange_county():
    from gitaway.partners import places
    assert [p.name for p in places.nearby(places.resolve("San Diego"))] == ["Los Angeles", "Orange County"]
    assert places.nearby(places.resolve("sd, CA")) == ()          # an unknown place has no nearby list
    assert places.nearby(None) == ()


def test_every_nearby_place_is_a_known_place_with_an_airport_and_never_itself():
    from gitaway.partners import places
    assert len(places.NEARBY) >= 10
    for name, near in places.NEARBY.items():
        here = places.resolve(name)
        assert here.known and here.name == name and here.iata, name
        assert 1 <= len(near) <= places.MAX_NEARBY and len(set(near)) == len(near), name
        for other in places.nearby(here):
            assert other.known and other.iata and other.name != name, (name, other.name)


def test_orange_county_is_a_place():
    from gitaway.partners import places
    oc = places.resolve("Orange County")
    assert (oc.known, oc.iata, oc.slug, oc.region) == (True, "SNA", "orangecounty", "California")
