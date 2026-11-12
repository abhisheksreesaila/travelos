"""F-217: the trip grid's sums. Every flight against every stay; the first day as each traveler lives it; which square is marked."""
import pytest

from gitaway import catalog, gridsource, showcase, tripgrid
from gitaway.tripgrid import Flight, Stay


def flight(id="f", depart=8 * 60, arrive=14 * 60, stops=0, cents=100_000, overnight=False):
    return Flight(id, f"Air {id}", "XXX", depart, arrive, stops, cents, cents // 4, "Nonstop" if not stops else f"{stops} stop", overnight)


def stay(id="s", cents=80_000, tags=()):
    return Stay(id, f"Hotel {id}", "Town", "A room", cents, tags)


def grid(flights, stays, whos=("kids", "senior", "pet"), drive=30, shift=0):
    return tripgrid.build(flights, stays, whos, lambda f, s: drive, shift)


def test_a_square_is_the_flight_plus_the_stay():
    g = grid([flight("a", cents=100_000), flight("b", cents=90_000)], [stay("x", 80_000), stay("y", 60_000)])
    assert {k: c.cents for k, c in g.cells.items()} == {("a", "x"): 180_000, ("b", "x"): 170_000, ("a", "y"): 160_000, ("b", "y"): 150_000}
    assert (g.lowest.flight.id, g.lowest.stay.id) == ("b", "y")


def test_the_kids_day_is_the_flights_times_plus_the_stated_allowances():
    d = tripgrid.day("kids", flight(depart=7 * 60 + 5, arrive=15 * 60 + 30), stay(), 25, clock_shift=180)
    assert d.facts == (("Up at", "4:35 AM"), ("At the door", "4:40 PM"), ("Feels like", "1:40 PM"))
    assert (d.score, d.word) == (2, "fair day")
    assert "2 h 30 min before take-off" in d.note and "25 min drive" in d.note


def test_no_drive_known_ends_the_day_at_the_kerb_and_says_so():
    d = tripgrid.day("kids", flight(), stay(), None)
    assert d.facts[1] == ("Out of the airport", "2:45 PM")
    assert "drive" not in d.note


@pytest.mark.parametrize("f, word", [(flight(), "easy day"), (flight(depart=6 * 60), "fair day"), (flight(stops=1), "fair day"), (flight(arrive=21 * 60), "hard day"),
                                     (flight(depart=6 * 60, arrive=21 * 60, stops=1), "very hard day"), (flight(depart=23 * 60, arrive=7 * 60, overnight=True), "hard day")])
def test_how_hard_the_kids_day_is(f, word):
    assert tripgrid.day("kids", f, stay(), 30).word == word


def test_a_seniors_day_counts_changes_and_never_claims_a_lift():
    d = tripgrid.day("senior", flight(stops=1), stay(), 30)
    assert d.facts[0] == ("Changes", "1") and d.word == "hard day"
    assert "do not know" in d.note and "lift" in d.note


def test_a_pets_day_reads_the_stays_own_tag_and_never_an_airline_rule():
    yes, no = tripgrid.day("pet", flight(), stay(tags=("Pet friendly",)), 30), tripgrid.day("pet", flight(), stay(), 30)
    assert (yes.facts[0], yes.word) == (("Stay", "Takes pets"), "easy day")
    assert (no.facts[0], no.word) == (("Stay", "Ask first"), "very hard day")
    assert "not listed as taking pets" in no.verdict and "Ask the airline" in no.note


def test_the_easiest_square_is_the_cheaper_of_two_as_easy():
    g = grid([flight("a", cents=100_000), flight("b", cents=90_000), flight("c", cents=50_000, stops=1)], [stay("x")])
    assert g.easiest("kids").flight.id == "b"
    assert g.lowest.flight.id == "c"
    assert grid([flight()], [stay()], whos=()).easiest("kids") is None


def test_how_each_square_is_drawn():
    g = grid([flight("a", cents=100_000), flight("b", cents=90_000), flight("c", cents=150_000, depart=6 * 60, arrive=21 * 60, stops=1)], [stay("x")])
    a, b, c = (g.cell(i, "x") for i in "abc")
    assert [g.tone(x, ("a", "x"), "price", "kids", 200_000) for x in (a, b, c)] == ["mine", "best", "bad"]
    assert [g.tone(x, ("a", "x"), "price", "kids", None) for x in (a, b, c)] == ["mine", "best", "plain"]
    assert [g.tone(x, None, "ease", "kids", 200_000) for x in (a, b, c)] == ["plain", "best", "bad"]
    assert g.tone(c, None, "ease", "pet-not-here", 200_000) == "bad"      # nobody like that going: the price rules


def test_the_showcase_source_is_the_catalog_and_says_sample(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    trip = catalog.sample_trip("la")
    flights, stays, drive_min, sample = gridsource.offers(trip)
    assert sample is True and len(flights) == 5 and len(stays) == 3
    by = {o.id: o for o in catalog.offers("flight", trip)}
    assert all(f.cents == by[f.id].price_cents and f.depart_min == by[f.id].depart_min for f in flights)
    assert [f.stops for f in flights] == [0, 0, 0, 1, 0]
    assert drive_min(flights[0], stays[0]) == 25                           # LAX to Santa Monica, the rides table's own minutes


def test_off_the_showcase_there_is_no_source(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert showcase.on() is False
    assert gridsource.offers(catalog.sample_trip("la")) is None
