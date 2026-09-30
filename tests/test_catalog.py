"""The fake SFO → LA catalog: what the booking workspace offers and what it costs."""

from datetime import date

import pytest

from gitaway import catalog


def test_the_sample_trip_is_a_friday_to_tuesday_family_trip_to_la():
    trip = catalog.SAMPLE_TRIP
    assert trip.origin == "SFO" and trip.origin_name == "San Francisco" and trip.destination_name == "Los Angeles"
    assert trip.airports == ("LAX", "BUR")
    assert trip.depart == date(2026, 10, 16) and trip.depart.strftime("%A") == "Friday"
    assert trip.return_ == date(2026, 10, 20) and trip.return_.strftime("%A") == "Tuesday"
    assert trip.nights == 4
    assert trip.travelers == 4 and trip.summary == "2 adults, 2 kids"


def test_workspace_lanes_offer_five_flights_three_stays_and_three_ways_to_get_around():
    assert len(catalog.offers("flight")) == 5
    assert len(catalog.offers("stay")) == 3
    assert len(catalog.offers("car")) == 3
    assert all(isinstance(o.price_cents, int) for kind in ("flight", "stay", "car") for o in catalog.offers(kind))


def test_quote_adds_the_picked_flight_stay_and_car_into_one_all_in_total():
    q = catalog.quote("f1", "h1", "c1")  # Skylark nonstop + The Tidewater + Breeze SUV, as on the artboard
    assert q.total_cents == 308_800
    assert catalog.money(q.total_cents) == "$3,088"
    assert [line.name for line in q.lines] == ["Skylark Air 214", "The Tidewater", "Breeze Rentals"]


def test_the_ledger_knows_the_cheapest_combination_and_how_far_a_pick_is_from_it():
    cheapest = catalog.cheapest()
    assert (cheapest.flight_id, cheapest.stay_id, cheapest.car_id) == ("f4", "h3", "c3")
    assert cheapest.total_cents == 204_000
    assert catalog.quote("f1", "h1", "c1").above_cheapest_cents == 104_800
    assert cheapest.above_cheapest_cents == 0


def test_an_unknown_offer_is_refused_rather_than_priced_as_zero():
    with pytest.raises(KeyError):
        catalog.quote("f1", "nope", "c1")


def test_flights_land_at_either_la_airport():
    airports = {o.airport for o in catalog.offers("flight")}
    assert airports == {"LAX", "BUR"}


def test_a_pick_in_the_wrong_lane_is_refused():
    with pytest.raises(KeyError):
        catalog.quote("h1", "f1", "c1")


def test_money_shows_cents_only_when_there_are_some():
    assert catalog.money(123_600) == "$1,236"
    assert catalog.money(3_850) == "$38.50"
