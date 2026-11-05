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


def test_plan_page_shows_the_places_own_offers_and_not_the_others(client):
    pages = {to: client.get(f"/plan?to={to}&{TRIP}").text for to in AIRPORTS}
    assert "Skylark Air 214" in pages["la"] and "Skylark Air 214" not in pages["sd"]
    assert "Coronado Shores Inn" in pages["sd"] and "Aloha Pacific 12" in pages["hi"] and "Battery Park Hotel" in pages["nyc"]
    assert "Aloha Pacific 12" not in pages["nyc"] and "Hotel Marigold" not in pages["hi"]
    assert "Nonstop to JFK" in pages["nyc"] and "Newark (EWR)" in pages["nyc"]


def test_plan_page_prices_follow_the_trip(client):
    page = text(client.get(f"/plan?to=hi&{TRIP}").text)
    hotel = catalog.offers("stay", trip("hi"))[0]
    assert hotel.name == "Waikiki Tide Resort" and f"{catalog.money(hotel.price_cents)}" in page


@pytest.mark.parametrize("to,gone", [("sd", ["Santa Monica", "Griffith", "Los Angeles", "Metro E Line"]), ("hi", ["Santa Monica", "Griffith", "Los Angeles"]), ("nyc", ["Santa Monica", "Griffith", "Los Angeles"])])
def test_context_panes_name_the_right_place(client, to, gone):
    page = client.get(f"/plan?to={to}&{TRIP}").text
    for word in gone:
        assert word not in page, word
    assert {"sd": "SAN", "hi": "HNL", "nyc": "JFK"}[to] in page


def test_a_bad_pick_falls_back_to_the_places_own_default(client):
    page = client.get(f"/plan?to=sd&f=f1&h=h2&c=c1&{TRIP}").text
    from gitaway.pages import plan
    assert plan.resolve_pick("f1", "h2", "c1", trip("sd")) == ("sdf1", "sdh1", "sdc1")
    assert plan.resolve_pick("sdf2", "sdh3", "none", trip("sd")) == ("sdf2", "sdh3", None)


def test_the_pay_sheet_and_booking_keep_the_place(client):
    sign_in(client, "ari")
    pick = f"f=nycf1&h=nych2&c=none&to=nyc&{TRIP}"
    sheet = client.get(f"/plan/pay?{pick}").text
    assert 'name="to" value="nyc"' in sheet and "Brooklyn Bridge Lofts" in sheet
    r = client.post("/pay", data={k: v[0] for k, v in parse_qs(pick).items()}, follow_redirects=False)
    assert r.status_code in (200, 303)
    trip_page = text(client.get("/trip").text)
    assert "NYC with the kids" in trip_page and "Brooklyn Bridge Lofts" in trip_page and "Los Angeles" not in trip_page


def test_the_ride_estimate_uses_the_places_airport_and_table(client):
    q = catalog.quote("hif1", "hih1", None, trip=trip("hi"))
    assert q.rides.airport == "HNL" and q.rides.legs[0].route == "HNL → Waikiki"
    q = catalog.quote("nycf4", None, None, trip=trip("nyc"))
    assert q.rides.legs[0].route == "EWR → New York" and q.rides.detail == "EWR to the city, both ways"


def test_start_remembers_the_place_of_saved_picks(client):
    sign_in(client, "ari")
    client.get(f"/plan?to=sd&{TRIP}")
    assert "SD with the kids" in client.get("/start").text
