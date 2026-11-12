"""F-222: the trip matrix's sums. Places down (the asked one, its nearby ones, and each nearby one joined with it), start days across, each square the whole trip.
The marks are plain rules on real totals: the cheapest start in a lane, over the budget, and the find ("Los Angeles + San Diego, $50 more than San Diego alone")."""
from datetime import date

import pytest

from gitaway import tripmatrix as tm
from gitaway.partners import places

SD = places.resolve("San Diego")
D, R = date(2026, 12, 12), date(2026, 12, 16)
TODAY = date(2026, 11, 11)


def test_the_lanes_are_the_place_its_nearby_places_and_each_one_joined_with_it():
    lanes = tm.lanes(SD, nearby=True)
    assert [(l.key, l.name, l.asked, l.combo) for l in lanes] == [
        ("sandiego", "San Diego", True, False), ("losangeles", "Los Angeles", False, False), ("orangecounty", "Orange County", False, False),
        ("losangeles+sandiego", "Los Angeles + San Diego", False, True), ("orangecounty+sandiego", "Orange County + San Diego", False, True)]
    assert [l.key for l in tm.lanes(SD, nearby=False)] == ["sandiego"]
    assert [l.key for l in tm.lanes(places.resolve("Honolulu"), nearby=True)] == ["honolulu"]      # no nearby list: the place alone
    assert tm.lane(SD, "losangeles+sandiego", nearby=True).places == (places.resolve("Los Angeles"), SD)
    assert tm.lane(SD, "losangeles+sandiego", nearby=False) is None and tm.lane(SD, "nowhere", nearby=True) is None


def test_the_windows_are_the_same_nights_moved_give_or_take_never_into_the_past():
    ws = tm.windows(D, R, 2, TODAY)
    assert [(w.key, w.depart, w.return_, w.asked) for w in ws] == [
        ("2026-12-10", date(2026, 12, 10), date(2026, 12, 14), False), ("2026-12-11", date(2026, 12, 11), date(2026, 12, 15), False),
        ("2026-12-12", D, R, True), ("2026-12-13", date(2026, 12, 13), date(2026, 12, 17), False), ("2026-12-14", date(2026, 12, 14), date(2026, 12, 18), False)]
    assert [w.key for w in tm.windows(D, R, 0, TODAY)] == ["2026-12-12"]
    assert [w.key for w in tm.windows(D, R, 3, date(2026, 12, 11))][:2] == ["2026-12-11", "2026-12-12"]      # never before today
    assert len(tm.windows(D, R, 9, TODAY)) == 7                                                          # give or take is at most 3
    assert tm.window(D, R, 2, TODAY, "2026-12-14").depart == date(2026, 12, 14)
    assert tm.window(D, R, 2, TODAY, "2026-12-15") is None and tm.window(D, R, 2, TODAY, "junk") is None


def test_two_places_split_the_nights_and_fly_in_to_the_first_and_home_from_the_second():
    lane = tm.lane(SD, "losangeles+sandiego", nearby=True)
    w = tm.window(D, R, 2, TODAY, "2026-12-12")
    assert tm.stays_for(lane, w) == ((places.resolve("Los Angeles"), D, date(2026, 12, 14)), (SD, date(2026, 12, 14), R))
    assert tm.legs_for(lane, w, "SFO") == (("SFO", "LAX", D), ("SAN", "SFO", R))
    one = tm.lane(SD, "sandiego", nearby=True)
    assert tm.stays_for(one, w) == ((SD, D, R),) and tm.legs_for(one, w, "SFO") == (("SFO", "SAN", D), ("SAN", "SFO", R))
    odd = tm.Window(D, date(2026, 12, 15), True)
    assert [(a, b) for _, a, b in tm.stays_for(lane, odd)] == [(D, date(2026, 12, 13)), (date(2026, 12, 13), date(2026, 12, 15))]   # the first place gets the shorter half
    assert tm.stays_for(lane, tm.Window(D, date(2026, 12, 13), True)) is None                          # one night cannot be two places


def square(lane, w, flight, *stays, status=tm.OK):
    return tm.Square(lane, w, status, tm.FlightPart("Test Air", "SFO 8:05 AM → SAN 9:32 AM", "SAN 6:40 PM → SFO 8:10 PM", 0, flight),
                     tuple(tm.StayPart("San Diego", 4, "Hotel", "Two queens", "room only", True, 0, "", "", c) for c in stays) if status == tm.OK else ())


def test_a_square_is_the_flight_and_every_stay_added_and_a_problem_has_no_total():
    sq = square("sandiego", "2026-12-12", 56_800, 100_000, 49_250)
    assert sq.ok and sq.cents == 206_050 and sq.key == "sandiego|2026-12-12"
    for status in (tm.OVER, tm.FAILED, tm.NONE, tm.NO_SAMPLE):
        bad = tm.Square("sandiego", "2026-12-12", status)
        assert not bad.ok and bad.cents is None and tm.SAID[status] and tm.SHORT[status]
    assert tm.dollars(206_050) == "$2,061" and tm.dollars(206_049) == "$2,060" and tm.dollars(5_000) == "$50"


LANES = tm.lanes(SD, nearby=True)
WINDOWS = tm.windows(D, R, 2, TODAY)


def totals(**by_lane):
    """{square key: cents} from lane=[dollars per window or None]."""
    return {tm.key(lane.replace("_", "+"), w.key): c * 100 for lane, row in by_lane.items() for w, c in zip(WINDOWS, row) if c is not None}


def test_the_cheapest_start_in_each_lane_is_marked_and_a_budget_marks_what_is_over_it():
    t = totals(sandiego=[2310, 2260, 2140, 2080, 2390], losangeles=[1980, None, 1840, 1840, None], orangecounty=[2400, None, None, None, None])
    marks = tm.marks(LANES, WINDOWS, t, budget_cents=230_000)
    assert marks["sandiego|2026-12-13"] == ("low",)
    assert marks["losangeles|2026-12-12"] == ("low",)                     # a tie goes to the earlier start
    assert marks["losangeles|2026-12-13"] == ()
    assert marks["orangecounty|2026-12-10"] == ("over",)                 # one answer in a lane is nothing to compare
    assert marks["sandiego|2026-12-14"] == ("over",) and marks["sandiego|2026-12-10"] == ("over",)
    assert "losangeles|2026-12-11" not in marks                          # still waiting: no mark at all


def test_the_find_is_a_nearby_trip_that_beats_or_nearly_matches_the_asked_place_on_the_same_dates():
    t = totals(sandiego=[2310, 2260, 2140, 2080, 2390], losangeles_sandiego=[2400, 2330, 2190, 2160, 2470], orangecounty=[2600, 2600, 2600, 2600, 2600])
    found = tm.find(LANES, WINDOWS, t)
    assert (found.lane, found.window, found.diff_cents) == ("losangeles+sandiego", "2026-12-12", 5_000)
    assert found.words == "Los Angeles + San Diego, $50 more than San Diego alone"
    assert found.when == "Dec 12 to 16"
    assert tm.marks(LANES, WINDOWS, t)[found.key] == ("find",)


def test_a_cheaper_nearby_place_is_the_find_and_said_as_less():
    t = totals(sandiego=[None, None, 2140, None, None], losangeles=[None, None, 1840, None, None], losangeles_sandiego=[None, None, 2190, None, None])
    found = tm.find(LANES, WINDOWS, t)
    assert (found.lane, found.words) == ("losangeles", "Los Angeles, $300 less than San Diego")
    t = totals(sandiego=[None, None, 2140, None, None], orangecounty=[None, None, 2140, None, None])
    assert tm.find(LANES, WINDOWS, t).words == "Orange County, the same as San Diego"


def test_no_find_without_both_real_totals_or_when_nothing_comes_close():
    assert tm.find(LANES, WINDOWS, totals(losangeles=[1, 1, 1, 1, 1])) is None                  # the asked place has no answer yet: nothing to compare
    assert tm.find(LANES, WINDOWS, totals(sandiego=[2000] * 5, losangeles=[None, None, None, None, 1000], orangecounty=[2151, None, None, None, None])) is not None
    far = totals(sandiego=[2000] * 5, losangeles=[2151] * 5, orangecounty=[2500] * 5)
    assert tm.find(LANES, WINDOWS, far) is None                                                  # $151 more is not nearly
    assert tm.find(tm.lanes(SD, nearby=False), WINDOWS, totals(sandiego=[2000] * 5)) is None


def test_the_order_squares_are_asked_for_is_the_asked_square_then_nearest_dates_then_likeliest_places():
    order = tm.order(LANES, WINDOWS)
    assert order[:3] == ["sandiego|2026-12-12", "sandiego|2026-12-11", "sandiego|2026-12-13"]
    assert order.index("losangeles|2026-12-12") < order.index("sandiego|2026-12-10")
    assert len(order) == len(set(order)) == 25


@pytest.mark.parametrize("cents, budget, marks", [(300_000, 300_000, ()), (300_001, 300_000, ("over",)), (300_001, None, ())])
def test_over_is_strictly_over(cents, budget, marks):
    lanes, ws = tm.lanes(SD, nearby=False), tm.windows(D, R, 0, TODAY)
    assert tm.marks(lanes, ws, {tm.key("sandiego", "2026-12-12"): cents}, budget)["sandiego|2026-12-12"] == marks
