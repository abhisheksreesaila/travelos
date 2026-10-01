"""F-038: the RideProvider seam and the SimulatedUber behind it (gitaway/rides.py). Pure: no HTTP, no session."""
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from gitaway import catalog, rides
from gitaway.rides import RideError, SimulatedUber

FLIGHT = catalog.offer("f1")  # lands 9:32 AM at LAX, flies home at 2:10 PM
STAY = catalog.offer("h1")  # The Tidewater, Santa Monica
SAMPLE = catalog.SAMPLE_TRIP
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=rides.TZ)


@pytest.fixture(autouse=True)
def _now(monkeypatch):
    monkeypatch.setattr(rides, "now", lambda: NOW)


def plan(kind="arrive", flight=FLIGHT, stay=STAY, trip=SAMPLE):
    return rides.leg_plan(kind, flight, stay, trip)


def party(n):
    """A trip with n travelers (2 adults and n - 2 kids)."""
    kids = tuple(range(5, 5 + n - 2))
    return replace(SAMPLE, adults=2, kid_ages=kids)


def guest():
    return rides.validate_guest("Ari", "Rivera", "(310) 555-0123")


def booked(kind="arrive", product="x", **kw):
    sim = SimulatedUber()
    p = plan(kind, **kw)
    est = next(e for e in sim.estimates(p) if e.key == product)
    return sim.schedule(rides.ScheduleRequest(p, guest(), est.product_id, est.fare_id, "r1", "k1"))


# ---- the seam -----------------------------------------------------------------------------------------------------

def test_the_simulator_is_the_provider_unless_told_otherwise(monkeypatch):
    monkeypatch.delenv("UBER_MODE", raising=False)
    assert isinstance(rides.provider(), SimulatedUber)
    monkeypatch.setenv("UBER_MODE", "simulated")
    assert isinstance(rides.provider(), SimulatedUber)


def test_an_unknown_mode_is_refused_not_guessed(monkeypatch):
    monkeypatch.setenv("UBER_MODE", "production")
    with pytest.raises(RideError, match="UBER_MODE"):
        rides.provider()


def test_the_simulator_implements_the_interface():
    for name in ("estimates", "schedule", "status", "cancel"):
        assert callable(getattr(rides.RideProvider, name))
        assert callable(getattr(SimulatedUber, name))


# ---- the two legs -------------------------------------------------------------------------------------------------

def test_the_arrival_pickup_is_landing_plus_the_curb_buffer():
    p = plan("arrive")
    assert (p.pickup_time.hour * 60 + p.pickup_time.minute) == FLIGHT.arrive_min + catalog.CURB_MINUTES == 602
    assert p.pickup_time.date() == SAMPLE.depart
    assert p.pickup.area == "LAX" and p.dropoff.name == "The Tidewater"


def test_the_departure_pickup_is_flight_minus_airport_buffer_minus_drive_time():
    p = plan("depart")
    minutes = catalog.ride_base("LAX", "Santa Monica", "depart")[1]
    assert p.pickup_time.hour * 60 + p.pickup_time.minute == (FLIGHT.back_depart_min - catalog.AIRPORT_BUFFER - minutes) // 5 * 5 == 705
    assert p.pickup_time.date() == SAMPLE.return_
    assert p.pickup.name == "The Tidewater" and p.dropoff.area == "LAX"


def test_the_pickup_time_goes_out_as_milliseconds_since_the_epoch_in_los_angeles():
    p = plan("arrive")
    assert p.pickup_ms == int(datetime(2026, 10, 16, 10, 2, tzinfo=rides.TZ).timestamp() * 1000)


def test_a_flight_only_trip_rides_to_the_city_centre():
    p = plan("arrive", stay=None)
    assert p.dropoff.name == "Los Angeles city centre" and p.dropoff.area == "city"
    assert p.minutes == catalog.ride_base("LAX", "city", "arrive")[1]


def test_the_airport_leg_is_a_reserve_booking_and_the_hotel_leg_a_scheduled_one():
    assert plan("arrive").advance == "RESERVE"
    assert plan("depart").advance == "SCHEDULED"


# ---- estimates ----------------------------------------------------------------------------------------------------

def test_estimates_list_each_product_with_price_time_and_ids():
    ests = SimulatedUber().estimates(plan("arrive"))
    assert [e.key for e in ests] == ["x", "c", "xl"]
    assert [e.name for e in ests] == ["UberX", "Comfort", "UberXL"]
    assert all(e.fits and e.product_id and e.fare_id and e.cents > 0 and e.trip_minutes == 25 and e.pickup_eta_min > 0 for e in ests)
    x, c, xl = ests
    assert x.cents == 38 * 100 and x.display == "$38"
    assert x.cents < c.cents < xl.cents
    assert len({e.product_id for e in ests}) == 3 and len({e.fare_id for e in ests}) == 3


def test_estimates_are_deterministic():
    assert SimulatedUber().estimates(plan()) == SimulatedUber().estimates(plan())


def test_a_party_of_four_fits_every_product():
    assert all(e.fits for e in SimulatedUber().estimates(plan()))


def test_five_or_more_need_an_xl():
    ests = {e.key: e for e in SimulatedUber().estimates(plan(trip=party(5)))}
    assert not ests["x"].fits and not ests["c"].fits and ests["xl"].fits
    assert "XL" in ests["x"].note
    assert ests["xl"].cents == 6000  # 160% of the standard $38, in whole dollars like the rides card


def test_a_big_party_takes_several_xls():
    ests = {e.key: e for e in SimulatedUber().estimates(plan(trip=party(7)))}
    assert ests["xl"].cars == 2 and ests["xl"].cents == 12000


def test_the_departure_estimate_uses_the_departure_fare():
    assert SimulatedUber().estimates(plan("depart"))[0].cents == 35 * 100


# ---- schedule -----------------------------------------------------------------------------------------------------

def test_scheduling_returns_a_scheduled_record():
    r = booked()
    assert r.id == "r1" and r.request_id.startswith("sim_") and r.cents == 3800 and r.product == "x"
    assert SimulatedUber().status(r).name == "scheduled"


def test_the_request_id_is_stable_and_differs_per_ride():
    assert booked().request_id == booked().request_id
    assert booked("depart").request_id != booked("arrive").request_id


def test_a_changed_fare_id_is_refused_like_uber_answering_409():
    sim, p = SimulatedUber(), plan()
    est = sim.estimates(p)[0]
    with pytest.raises(RideError, match="price"):
        sim.schedule(rides.ScheduleRequest(p, guest(), est.product_id, "fare_stale", "r1", "k1"))


def test_a_product_that_does_not_seat_the_party_is_refused():
    sim, p = SimulatedUber(), plan(trip=party(5))
    est = sim.estimates(p)[0]
    with pytest.raises(RideError, match="seats"):
        sim.schedule(rides.ScheduleRequest(p, guest(), est.product_id, est.fare_id, "r1", "k1"))


def test_a_pickup_less_than_five_minutes_away_is_refused(monkeypatch):
    monkeypatch.setattr(rides, "now", lambda: plan().pickup_time - timedelta(minutes=4))
    with pytest.raises(RideError, match="5 minutes"):
        booked()


def test_a_normal_pickup_more_than_30_days_out_is_refused_but_reserve_goes_to_90(monkeypatch):
    monkeypatch.setattr(rides, "now", lambda: plan().pickup_time - timedelta(days=40))
    assert booked("arrive").leg == "arrive"  # Reserve: up to 90 days
    with pytest.raises(RideError, match="30 days"):
        booked("depart")  # five days later, still more than 30 days out


# ---- guest --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,e164", [("(310) 555-0123", "+13105550123"), ("310-555-0123", "+13105550123"), ("1 310 555 0123", "+13105550123"),
                                      ("+1 (310) 555-0123", "+13105550123"), ("+44 20 7946 0958", "+442079460958")])
def test_phone_numbers_are_normalised_to_e164(raw, e164):
    assert rides.validate_guest("Ari", "Rivera", raw).phone == e164


@pytest.mark.parametrize("raw", ["", "123", "abcdefghij", "000-000-0000", "111-111-1111", "(010) 555-0123", "+0 310 555 0123", "310555012345678901"])
def test_an_implausible_phone_is_refused(raw):
    with pytest.raises(RideError, match="phone"):
        rides.validate_guest("Ari", "Rivera", raw)


@pytest.mark.parametrize("first,last", [("", "Rivera"), ("Ari", ""), ("A" * 31, "Rivera"), ("Ari<script>", "Rivera"), ("1234", "Rivera")])
def test_a_bad_name_is_refused(first, last):
    with pytest.raises(RideError, match="name"):
        rides.validate_guest(first, last, "(310) 555-0123")


def test_names_are_trimmed_and_may_have_hyphens_and_apostrophes():
    g = rides.validate_guest("  Mary-Ann ", "O'Neil  ", "3105550123")
    assert (g.first, g.last) == ("Mary-Ann", "O'Neil")


# ---- status, step, cancel -----------------------------------------------------------------------------------------

def at(r, delta):
    """The time `delta` minutes after the pickup."""
    return r.pickup_time + timedelta(minutes=delta)


@pytest.mark.parametrize("delta,name,step", [(-600, "scheduled", 0), (-31, "scheduled", 0), (-30, "processing", 0), (-20, "accepted", 1),
                                             (-5, "arriving", 2), (0, "in_progress", 3), (24, "in_progress", 3), (25, "completed", 4)])
def test_the_status_follows_the_clock_relative_to_the_pickup(delta, name, step):
    r = booked()
    s = SimulatedUber().status(r, at(r, delta))
    assert (s.name, s.step) == (name, step)


def test_the_status_uses_the_documented_names_and_friendly_labels():
    r = booked()
    seen = {SimulatedUber().status(r, at(r, d)).name: SimulatedUber().status(r, at(r, d)).label for d in (-600, -30, -20, -5, 0, 25)}
    assert seen == {"scheduled": "Scheduled", "processing": "Finding a driver", "accepted": "Driver assigned", "arriving": "Arriving",
                    "in_progress": "On trip", "completed": "Completed"}


def test_the_driver_and_car_appear_once_a_driver_is_assigned_and_are_stable():
    sim, r = SimulatedUber(), booked()
    assert sim.status(r, at(r, -600)).driver is None
    a, b = sim.status(r, at(r, -10)), sim.status(r, at(r, 0))
    assert a.driver and a.vehicle and a.plate and (a.driver, a.vehicle, a.plate) == (b.driver, b.vehicle, b.plate)


def test_stepping_walks_accept_arrived_begin_trip_dropoff():
    sim, r = SimulatedUber(), booked()
    seen = []
    for _ in range(4):
        r = sim.advance(r, NOW)
        seen.append(sim.status(r, NOW).name)
    assert seen == ["accepted", "arriving", "in_progress", "completed"]


def test_stepping_a_finished_ride_is_refused():
    sim, r = SimulatedUber(), booked()
    for _ in range(4):
        r = sim.advance(r, NOW)
    with pytest.raises(RideError, match="finished"):
        sim.advance(r, NOW)


def test_a_step_never_goes_backwards_from_the_clock():
    sim, r = SimulatedUber(), booked()
    later = at(r, 0)  # the clock says on trip
    assert sim.status(sim.advance(r, later), later).name == "completed"


def test_cancel_before_pickup():
    sim, r = SimulatedUber(), booked()
    c = sim.cancel(r, NOW)
    s = sim.status(c, NOW)
    assert (s.name, s.label, s.terminal) == ("rider_canceled", "Cancelled", True)


def test_cancel_works_after_a_driver_is_assigned_but_not_once_the_trip_begins():
    sim, r = SimulatedUber(), booked()
    sim.cancel(sim.advance(r, NOW), NOW)
    on_trip = sim.advance(sim.advance(sim.advance(r, NOW), NOW), NOW)
    with pytest.raises(RideError, match="trip"):
        sim.cancel(on_trip, NOW)


def test_cancelling_twice_is_refused_and_a_cancelled_ride_cannot_step():
    sim, r = SimulatedUber(), booked()
    c = sim.cancel(r, NOW)
    with pytest.raises(RideError, match="already"):
        sim.cancel(c, NOW)
    with pytest.raises(RideError):
        sim.advance(c, NOW)


# ---- the compact stored form --------------------------------------------------------------------------------------

def test_a_record_round_trips_through_its_compact_dict():
    r = booked()
    d = rides.to_dict(r)
    assert rides.from_dict(d) == r
    assert len(str(d)) < 220  # the session cookie is tiny


# ---- the Uber app deeplink ----------------------------------------------------------------------------------------

def test_the_deeplink_prefills_pickup_dropoff_and_product_and_is_not_a_booking():
    p = plan("arrive")
    url = rides.deeplink(p, "x")
    assert url.startswith("https://m.uber.com/looking?")
    assert "pickup=%7B" in url and "drop[0]=%7B" in url and "product_id=" in url and "LAX" in url
    assert "pickup_time" not in url and "scheduling" not in url  # deeplinks cannot schedule
    assert rides.deeplink(p).count("product_id") == 0
