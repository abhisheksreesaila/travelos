"""F-033: any mix of flight, stay and car, with a rides estimate when there is no car (catalog level)."""
import pytest

from gitaway import catalog

BIG = catalog.parse_trip("SFO", "la", "2026-10-16", "2026-10-20", "5", "")  # 5 adults: needs an XL ride
HUGE = catalog.parse_trip("SFO", "la", "2026-10-16", "2026-10-20", "8", "")  # 8 adults: two XL rides
SOLO = catalog.parse_trip("SFO", "la", "2026-10-16", "2026-10-20", "1", "")


def test_the_old_no_car_offer_is_folded_into_the_skip():
    assert [o.id for o in catalog.offers("car")] == ["c1", "c2"]
    with pytest.raises(KeyError):
        catalog.offer("c3")


def test_every_mix_with_at_least_one_lane_quotes():
    full = catalog.quote("f1", "h1", "c1")
    assert full.total_cents == 308_800 and full.rides is None and full.paid_cents == 308_800
    only = {
        "flight": catalog.quote("f1", None, None).lane_cents("flight"),
        "stay": catalog.quote(None, "h1", None).lane_cents("stay"),
        "car": catalog.quote(None, None, "c1").lane_cents("car"),
    }
    assert only == {"flight": 123_600, "stay": 154_000, "car": 31_200}
    assert catalog.quote(None, "h1", "c1").total_cents == 154_000 + 31_200
    assert catalog.quote("f1", "h1", None).paid_cents == 123_600 + 154_000


def test_no_lane_picked_is_an_empty_quote_that_cannot_be_booked():
    q = catalog.quote(None, None, None)
    assert q.empty and q.total_cents == 0 and q.items == () and q.lines == (None, None, None)


def test_a_skipped_lane_has_no_items_and_no_zero_line():
    q = catalog.quote("f1", None, "c1")
    assert {i.lane for i in q.items} == {"flight", "car"}
    assert all(i.cents > 0 for i in q.items)
    assert q.lane_cents("stay") == 0


def test_no_car_with_a_flight_adds_a_labelled_rides_estimate_to_the_total_but_not_to_what_is_paid():
    q = catalog.quote("f1", "h1", None)
    assert q.rides is not None and q.rides.cents > 0
    assert q.total_cents == 123_600 + 154_000 + q.rides.cents
    assert q.paid_cents == 123_600 + 154_000
    ride_items = [i for i in q.items if i.lane == "rides"]
    assert [(i.name, i.cents) for i in ride_items] == [("Rides, estimated", q.rides.cents)]
    assert q.lane_cents("rides") == q.rides.cents


def test_no_car_and_no_flight_means_no_airport_and_no_rides():
    q = catalog.quote(None, "h1", None)
    assert q.rides is None and q.total_cents == q.paid_cents == 154_000


def test_a_car_means_no_rides():
    assert catalog.quote("f1", "h1", "c2").rides is None
    assert catalog.quote("f1", None, "c2").rides is None


def test_rides_come_from_the_flights_airport_to_the_stays_area():
    lax = catalog.quote("f1", "h1", None).rides
    assert (lax.airport, lax.area) == ("LAX", "Santa Monica")
    bur = catalog.quote("f5", "h3", None).rides
    assert (bur.airport, bur.area) == ("BUR", "Downtown")
    assert bur.cents != lax.cents


def test_rides_with_no_stay_go_to_the_city():
    r = catalog.quote("f1", None, None).rides
    assert r.area == "Los Angeles" and r.airport == "LAX"


def test_rides_have_an_arrival_and_a_departure_each_with_uber_and_lyft_fares_and_times():
    r = catalog.quote("f1", "h1", None).rides
    assert [leg.kind for leg in r.legs] == ["arrive", "depart"]
    for leg in r.legs:
        assert [f.provider for f in leg.fares] == ["Uber", "Lyft"]
        assert all(f.cents > 0 and f.minutes > 0 for f in leg.fares)
        assert leg.when and leg.route and leg.note
    assert r.legs[0].route == "LAX → Santa Monica" and r.legs[1].route == "Santa Monica → LAX"
    # the arrival pickup is after the sample flight lands (9:32 AM), the departure leaves well before the flight home (2:10 PM)
    assert "10:" in r.legs[0].note
    assert "11:" in r.legs[1].note or "12:" in r.legs[1].note


def test_the_estimate_is_the_cheaper_fare_each_way_times_the_cars():
    r = catalog.quote("f1", "h1", None).rides
    assert r.cars == 1 and not r.xl
    assert r.cents == sum(min(f.cents for f in leg.fares) for leg in r.legs)


def test_more_than_four_travelers_ride_in_an_xl_and_more_than_six_need_two():
    base = catalog.quote("f1", "h1", None, trip=SOLO).rides
    xl = catalog.quote("f1", "h1", None, trip=BIG).rides
    two = catalog.quote("f1", "h1", None, trip=HUGE).rides
    assert (base.xl, base.cars) == (False, 1)
    assert (xl.xl, xl.cars) == (True, 1) and xl.cents > base.cents
    assert (two.xl, two.cars) == (True, 2) and two.cents == 2 * xl.cents
    assert all(f.product == "XL" for leg in xl.legs for f in leg.fares)
    assert all(f.product == "Standard" for leg in base.legs for f in leg.fares)
    assert catalog.quote("f1", "h1", None).rides.xl is False  # the sample party of four fits a standard car


def test_the_cheapest_combination_is_for_the_same_lanes():
    stay_only = catalog.quote(None, "h3", None)
    assert stay_only.above_cheapest_cents == 89_200 - 89_200 and stay_only.total_cents == 89_200
    best = catalog.quote("f4", "h3", None)
    assert best.above_cheapest_cents == 0
    assert catalog.quote("f1", "h1", None).above_cheapest_cents > 0
    assert catalog.quote("f1", "h1", "c1").above_cheapest_cents > 0
    assert catalog.cheapest().car_id == "c1"


def test_a_pick_in_the_wrong_lane_is_still_refused_with_skips_around_it():
    with pytest.raises(KeyError):
        catalog.quote("h1", None, None)
    with pytest.raises(KeyError):
        catalog.quote(None, "c1", None)


def test_stay_and_flight_picks_must_match_their_lane_when_given():
    st = catalog.stay_pick("h1")
    with pytest.raises(KeyError):
        catalog.quote("f1", None, None, st)  # a stay pick but no stay
    fp = catalog.flight_pick("f1")
    with pytest.raises(KeyError):
        catalog.quote(None, "h1", None, flight=fp)
