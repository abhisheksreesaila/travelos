"""F-035: a trip (dates and party) drives the catalog's prices, and lives in a URL query."""
from datetime import date

import pytest

from gitaway import catalog

SAMPLE = catalog.SAMPLE_TRIP


def trip(depart=date(2026, 10, 16), ret=date(2026, 10, 20), adults=2, kids=(4, 7)):
    return catalog.TripSearch("SFO", "San Francisco", "Los Angeles", ("LAX", "BUR"), depart, ret, adults, tuple(kids))


# ---- the sample trip keeps today's prices -------------------------------------------------------------------------

def test_sample_trip_prices_are_exactly_todays():
    assert catalog.quote("f1", "h1", "c1").total_cents == 308_800
    assert [o.price_cents for o in catalog.offers("flight")] == [123_600, 110_400, 139_200, 96_800, 118_000]
    assert [o.price_cents for o in catalog.offers("stay")] == [154_000, 118_800, 89_200]
    assert [o.price_cents for o in catalog.offers("car")] == [31_200, 39_800, 18_000]
    assert [a.price_cents for a in catalog.ADDONS] == [32_000, 4_000, 18_000]
    assert [a.name for a in catalog.ADDONS] == ["Breakfast for 4", "Late checkout, 2 PM", "Parking, 4 nights"]


def test_an_equal_trip_in_other_clothes_is_still_the_sample_price():
    t = trip()
    assert t == SAMPLE
    assert catalog.quote("f1", "h1", "c1", trip=t).total_cents == 308_800


@pytest.mark.parametrize("stay", ["h1", "h2", "h3"])
def test_every_sample_room_keeps_its_price(stay):
    base = {"h1": [154_000, 106_000, 198_000], "h2": [118_800, 68_000, 142_000], "h3": [89_200, 52_000, 116_000]}[stay]
    assert [r.price_cents for r in catalog.stay_detail(stay).rooms] == base
    assert [r.price_cents for r in catalog.stay_detail(stay, SAMPLE).rooms] == base


# ---- nights and travelers drive prices -----------------------------------------------------------------------------

def test_three_nights_scale_stays_cars_and_per_night_addons():
    t3 = trip(ret=date(2026, 10, 19))
    assert t3.nights == 3
    assert catalog.offer("h1", t3).price_cents == 154_000 // 4 * 3
    assert catalog.offer("c1", t3).price_cents == 31_200 // 4 * 3
    assert catalog.offer("f1", t3).price_cents == 123_600  # flights follow travelers, not nights
    pk = catalog.addon("pk", t3)
    assert pk.price_cents == 18_000 // 4 * 3 and pk.name == "Parking, 3 nights"
    assert catalog.addon("lc", t3).price_cents == 4_000
    assert catalog.addon("bf", t3).price_cents == 32_000 // 16 * 4 * 3


def test_a_third_adult_scales_flights_and_breakfast_per_person():
    t = trip(adults=3)
    assert t.travelers == 5
    assert catalog.offer("f1", t).price_cents == 123_600 // 4 * 5
    assert catalog.offer("c1", t).price_cents == 31_200  # a car is a car
    bf = catalog.addon("bf", t)
    assert bf.price_cents == 2_000 * 5 * 4 and bf.name == "Breakfast for 5"


def test_total_follows_the_trip_consistently():
    t = trip(ret=date(2026, 10, 19), adults=3)
    q = catalog.quote("f1", "h1", "c1", trip=t)
    flight, car = catalog.offer("f1", t), catalog.offer("c1", t)
    # a party of 5 does not fit the default room alone, so the stay is two rooms
    assert q.stay.sleeps >= 5
    assert q.lane_cents("flight") == flight.price_cents
    assert q.lane_cents("car") == car.price_cents
    assert q.total_cents == q.lane_cents("flight") + q.lane_cents("stay") + q.lane_cents("car")
    assert q.trip == t


def test_room_fit_uses_the_real_party():
    t = trip(adults=1, kids=())
    pick = catalog.stay_pick("h1", trip=t)
    assert pick.fit == "full" and pick.fit_text == "Room for all 1"
    big = trip(adults=4, kids=(1, 2, 3, 4))
    p = catalog.parse_stay("h1", "ok1", trip=big)
    assert p.fit == "short" and p.fit_text == "Sleeps 2 of 8 · add a room"
    assert catalog.stay_pick("h1", "ok1", trip=big).fits  # unbookable rooms become the default for 8
    assert catalog.stay_pick("h1", trip=big).rooms == (("cq", 2),)
    assert catalog.stay_pick("h1", trip=big).rooms_code == ""  # the default for this party


def test_the_cheapest_combination_follows_the_trip():
    solo = trip(adults=1, kids=())
    assert catalog.quote("f1", "h1", "c1", trip=solo).above_cheapest_cents >= 0
    assert catalog.cheapest(solo).above_cheapest_cents == 0


def test_return_flight_weekday_follows_the_dates():
    t = trip(depart=date(2026, 10, 17), ret=date(2026, 10, 21))  # back on a Wednesday
    assert "back Wed 2:10 PM" in catalog.offer("f1", t).detail
    assert "back Tue 2:10 PM" in catalog.offer("f1").detail


def test_stay_policy_dates_follow_the_trip():
    assert "Oct 13" in catalog.stay_detail("h1").policy
    assert "Oct 14" in catalog.stay_detail("h1", trip(depart=date(2026, 10, 17), ret=date(2026, 10, 20))).policy


# ---- validation ----------------------------------------------------------------------------------------------------

def fields(**kw):
    base = dict(origin="SFO", to="la", depart="2026-10-16", ret="2026-10-20", adults="2", kids="4,7")
    base.update(kw)
    try:
        catalog.parse_trip(**base)
    except catalog.TripError as e:
        return dict(e.errors)
    return {}


def test_a_good_trip_parses():
    assert catalog.parse_trip("SFO", "la", "2026-10-16", "2026-10-20", "2", "4,7") == SAMPLE


@pytest.mark.parametrize("kw,field,words", [
    (dict(ret="2026-10-15"), "r", "after"),
    (dict(ret="2026-10-16"), "r", "after"),
    (dict(ret="2026-11-16"), "r", "30"),
    (dict(adults="0"), "a", "adult"),
    (dict(adults="9", kids=""), "a", "8"),
    (dict(adults="5", kids="1,2,3,4"), "a", "8"),
    (dict(depart="2026-02-31"), "d", "date"),
    (dict(ret="soon"), "r", "date"),
    (dict(depart=""), "d", "date"),
    (dict(adults="two"), "a", "adult"),
    (dict(kids="4,x"), "k", "age"),
    (dict(kids="4,18"), "k", "age"),
    (dict(to="sd"), "to", "coming soon"),
    (dict(to="hi"), "to", "coming soon"),
    (dict(to="mars"), "to", "where"),
    (dict(origin="JFK"), "from", "sfo"),
])
def test_bad_input_gives_a_friendly_message_on_the_field(kw, field, words):
    errs = fields(**kw)
    assert field in errs, errs
    assert words in errs[field].lower()


def test_thirty_nights_is_the_most_and_eight_travelers_the_most():
    assert not fields(ret="2026-11-15")  # 30 nights
    assert not fields(adults="2", kids="1,2,3,4,5,6")  # 8 travelers


# ---- the URL -------------------------------------------------------------------------------------------------------

def test_trip_query_is_empty_for_the_sample_trip():
    assert catalog.trip_query(SAMPLE) == ""


def test_trip_query_round_trips():
    from urllib.parse import parse_qs

    t = trip(depart=date(2026, 11, 3), ret=date(2026, 11, 6), adults=3, kids=(9,))
    q = catalog.trip_query(t)
    assert q == "d=2026-11-03&r=2026-11-06&a=3&k=9"
    p = {k: v[0] for k, v in parse_qs(q).items()}
    assert catalog.trip_from_url(p["d"], p["r"], p["a"], p.get("k", "")) == t
    assert catalog.trip_query(trip(adults=2, kids=())) == "d=2026-10-16&r=2026-10-20&a=2"


def test_bad_url_params_fall_back_to_the_sample_trip():
    assert catalog.trip_from_url("", "", "", "") == SAMPLE
    assert catalog.trip_from_url("nope", "2026-10-20", "2", "4,7") == SAMPLE
    assert catalog.trip_from_url("2026-10-16", "2026-10-20", "0", "") == SAMPLE
    assert catalog.trip_from_url("2026-10-16", "2026-12-20", "2", "") == SAMPLE
    assert catalog.trip_from_url("2026-10-16", None, "2", "") == SAMPLE
