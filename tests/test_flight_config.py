"""F-027: flight legs, fare types and checked bags, priced by the catalog and carried through the pick URL, ledger, pay and calendar."""
import re
from urllib.parse import parse_qs, urlparse

import pytest

from gitaway import catalog, session as ses, tripcal as cal
from tests.test_signin import person, session_data, sign_in, stored_booking, tid

DONE = "f=f1&h=h1&c=c1&fare=main&bags=2"  # Skylark 214, Main fare, 2 bags
T5 = catalog.trip_from_url("2026-10-16", "2026-10-20", "3", "4,7")  # 3 adults + 2 kids = 5 travelers
T5Q = "d=2026-10-16&r=2026-10-20&a=3&k=4,7"


def ws_total(html):
    return re.search(r'id="ws-total"[^>]*>([^<]*)<', html).group(1)


def quote_json(client, qs):
    r = client.get("/plan/quote?" + qs)
    assert r.status_code == 200
    return r.json()


# ---- catalog ---------------------------------------------------------------------------------------------------

def test_every_flight_has_legs_with_stops_and_an_aircraft():
    for f in catalog.offers("flight"):
        assert f.aircraft and f.stops
    f1, f4 = catalog.offer("f1"), catalog.offer("f4")
    assert (f1.aircraft, f1.stops) == ("Airbus A320", "Nonstop")
    assert (f4.aircraft, f4.stops) == ("Embraer 175", "1 stop · SJC")


def test_the_three_fares_scale_per_traveler_and_carry_four_perks_each():
    fares = catalog.fares()
    assert [(f.id, f.name, f.extra_cents) for f in fares] == [("basic", "Basic", 0), ("main", "Main", 24_000), ("xl", "Extra legroom", 56_000)]
    assert all(len(f.perks) == 4 for f in fares)
    assert [f.included_bags for f in fares] == [0, 0, 4]
    five = catalog.fares(T5)
    assert [f.extra_cents for f in five] == [0, 30_000, 70_000] and five[2].included_bags == 5


def test_the_default_flight_pick_keeps_todays_totals():
    p = catalog.flight_pick("f1")
    assert (p.fare, p.bags, p.cents, p.query, p.summary) == ("basic", 0, 123_600, "", "Basic fare")
    assert catalog.quote("f1", "h1", "c1").total_cents == 308_800


def test_main_fare_and_two_bags_is_the_done_means_flight():
    p = catalog.flight_pick("f1", "main", "2")
    assert p.cents == 123_600 + 24_000 + 14_000 == 161_600 and catalog.money(p.cents) == "$1,616"
    assert p.summary == "Main fare + 2 checked bags" and p.short == "Main fare · 2 bags"
    q = catalog.quote("f1", "h1", "c1", flight=p)
    assert q.total_cents == 346_800 and catalog.money(q.total_cents) == "$3,468"
    assert q.lane_cents("flight") == 161_600
    assert [(i.name, i.qty, i.cents) for i in q.items if i.lane == "flight"] == [("Skylark Air 214", 1, 123_600), ("Main fare", 1, 24_000), ("Checked bag", 2, 14_000)]


@pytest.mark.parametrize("fare,bags", [("zz", "x"), ("MAIN", "-1"), ("main ", "9"), ("", ""), ("xl;", "02x"), ("basic", "99"), (None, None), ("main", "٣")])
def test_bad_values_fall_back_to_basic_and_no_bags(fare, bags):
    p = catalog.flight_pick("f1", fare, bags)
    assert p.bags == 0 and (p.fare == "main" if fare == "main" else p.fare == "basic")
    assert catalog.flight_pick("f1", "junk", bags).fare == "basic" and catalog.flight_pick("f1", fare, "junk").bags == 0


def test_the_cap_is_two_bags_per_traveler():
    assert catalog.flight_pick("f1", None, "8").bags == 8 and catalog.flight_pick("f1", None, "9").bags == 0
    assert catalog.flight_pick("f1").max_bags == 8
    assert catalog.flight_pick("f1", None, "10", T5).bags == 10 and catalog.flight_pick("f1", None, "11", T5).bags == 0


def test_extra_legroom_includes_one_checked_bag_per_traveler():
    p = catalog.flight_pick("f1", "xl", "4")
    assert p.cents == 123_600 + 56_000 and p.summary == "Extra legroom fare + 4 checked bags"
    assert [i.name for i in p.items] == ["Skylark Air 214", "Extra legroom fare"]  # no $0 bag line
    five = catalog.flight_pick("f1", "xl", "6")
    assert [(i.name, i.qty, i.cents) for i in five.items][-1] == ("Checked bag", 2, 14_000)  # 4 included on the sample trip
    assert catalog.flight_pick("f1", "xl", "5").cents == 123_600 + 56_000 + 7_000
    assert catalog.flight_pick("f1", "main", "4").cents == 123_600 + 24_000 + 28_000


def test_codes_are_compact_and_the_default_is_empty():
    assert catalog.flight_pick("f1", "main", "2").query == "&fare=main&bags=2"
    assert catalog.flight_pick("f1", "xl").query == "&fare=xl"
    assert catalog.flight_pick("f1", None, "1").query == "&bags=1"
    assert catalog.flight_pick("f1", "basic", "0").query == ""


def test_fares_follow_the_trip_like_flights_do():
    p = catalog.flight_pick("f1", "main", "2", T5)
    base = catalog.offer("f1", T5).price_cents
    assert base == 123_600 // 4 * 5 and p.cents == base + 30_000 + 14_000  # bags are per bag, not per traveler
    assert catalog.flight_pick("f1", "xl", None, T5).cents == base + 70_000


def test_a_quote_refuses_a_pick_for_another_flight_or_trip():
    with pytest.raises(KeyError):
        catalog.quote("f1", "h1", "c1", flight=catalog.flight_pick("f2", "main"))
    with pytest.raises(ValueError):
        catalog.quote("f1", "h1", "c1", flight=catalog.flight_pick("f1", "main", trip=T5))


# ---- the plan page and the quote route ---------------------------------------------------------------------------

# ---- pay ---------------------------------------------------------------------------------------------------

# ---- calendar and /booked ----------------------------------------------------------------------------------------

# ---- page script contract (string checks; the behaviour was walked in a browser) -----------------------------------
