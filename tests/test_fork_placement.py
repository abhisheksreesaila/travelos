"""Placing a fork's plans around bookings and friends' items: the pure function in gitaway.tripcal (F-021)."""

from gitaway import itineraries, tripcal as cal
from gitaway.tripcal import Activity, Block, Plan

GS = 7 * 60


def h(hour, minute=0):
    return hour * 60 + minute


def plan(key, day, start, end, title="Plan"):
    return Plan(key, day, start, end, title, "fun")


def place(plans, blocks=(), acts=(), n_days=5):
    return cal.place_plans(list(plans), list(blocks), list(acts), n_days, GS)


def test_an_open_slot_is_free_and_checked():
    [x] = place([plan("d1s0", 0, h(13), h(15))])
    assert x.state == "free" and x.checked and not x.hard and x.clash == ""


def test_a_plan_over_a_booked_block_is_free_and_tagged_with_it():
    flight = Block("b-out", 0, h(8, 5), h(9, 32), "Skylark Air 214", "booked", True)
    [x] = place([plan("d1s0", 0, h(9), h(11))], blocks=[flight])
    assert x.state == "free" and x.checked and not x.hard and x.clash == "" and x.overlap == "Skylark Air 214"


def test_a_plan_over_a_friends_activity_is_free_and_tagged_with_it():
    mom = Activity("a1", 1, h(9), h(11), "Venice Canals stroll", "outdoors", "Mom")
    [x] = place([plan("d2s0", 1, h(9, 30), h(11))], acts=[mom])
    assert x.state == "free" and x.checked and not x.hard and x.overlap == "Venice Canals stroll"


def test_a_plan_over_the_travelers_own_activity_is_tagged_too():
    mine = Activity("a1", 1, h(9), h(11), "Brunch", "food")
    [x] = place([plan("d2s0", 1, h(10), h(12))], acts=[mine])
    assert x.overlap == "Brunch" and x.checked


def test_touching_edges_do_not_clash():
    mine = Activity("a1", 1, h(9), h(11), "Brunch", "food")
    assert [x.state for x in place([plan("a", 1, h(11), h(12)), plan("b", 1, h(8), h(9))], acts=[mine])] == ["free", "free"]


def test_other_days_do_not_clash():
    mine = Activity("a1", 1, h(9), h(11), "Brunch", "food")
    assert place([plan("a", 2, h(9), h(11))], acts=[mine])[0].state == "free"


def test_two_plans_of_the_fork_that_overlap_are_both_kept_and_the_later_is_tagged():
    first, second = place([plan("a", 0, h(13), h(15), "Pier"), plan("b", 0, h(14), h(16), "Tacos")])
    assert first.checked and first.overlap == "" and second.checked and not second.hard and second.overlap == "Pier"


def test_a_plan_the_calendar_already_has_is_marked_have_and_not_checked():
    have = Activity("a1", 0, h(13), h(15), "pier", "fun")
    [x] = place([plan("a", 0, h(13), h(15), "Pier")], acts=[have])
    assert x.state == "have" and not x.checked


def test_a_day_past_the_trip_and_hours_off_the_grid_are_hard_clashes():
    late, past, early = place([plan("a", 0, h(21), h(23)), plan("b", 5, h(10), h(12)), plan("c", 0, h(5), h(6))])
    assert late.hard and late.clash == "outside 7:00 AM to 10:00 PM"
    assert past.hard and past.clash == "after your trip ends"
    assert early.hard


def test_placing_does_not_change_its_inputs():
    acts = [Activity("a1", 0, h(9), h(11), "Brunch", "food")]
    blocks = [Block("b", 0, h(15), h(16), "Check in", "booked", True)]
    before = (list(acts), list(blocks))
    place([plan("a", 0, h(9), h(11))], blocks, acts)
    assert (acts, blocks) == before


def test_stop_times_parse_and_junk_is_none():
    assert cal.stop_start("1:00 PM") == h(13) and cal.stop_start("12:30 AM") == 30 and cal.stop_start("12:15 PM") == h(12, 15)
    assert cal.stop_start("8:05 AM") == h(8, 5)
    assert cal.stop_start("Evening") is None and cal.stop_start("13:00 PM") is None and cal.stop_start("") is None


def test_fork_plans_skip_the_authors_bookings_and_use_typical_lengths():
    plans = cal.fork_plans(itineraries.get("sun-tacos-and-tide-pools"))
    titles = [p.title for p in plans]
    assert "Skylark Air 214 · SFO → LAX" not in titles and not any(t.startswith("Check in") for t in titles)
    pier = next(p for p in plans if p.title.startswith("Santa Monica Pier"))
    assert (pier.day, pier.start, pier.end) == (0, h(13), h(15))
    tacos = next(p for p in plans if p.title.startswith("Tacos"))
    assert tacos.end - tacos.start == cal.FORK_MEAL_LEN and tacos.kind == "food"
    assert all(len(p.title) <= cal.MAX_TITLE for p in plans) and len({p.key for p in plans}) == len(plans)


# ---- nothing before you land, nothing too close to the flight home ---------------------------------------------------

OUT = Block("b-out", 0, h(8, 5), h(9, 32), "Skylark Air 214", "booked", True)
BACK = Block("b-back", 4, h(14, 10), h(15, 37), "Skylark Air 214", "booked", True)


def test_the_window_opens_when_you_land_and_closes_two_hours_before_the_flight_home():
    assert cal.day_window([OUT, BACK], 0) == (h(9, 32), cal.GRID_END)
    assert cal.day_window([OUT, BACK], 4) == (GS, h(12, 10))
    assert cal.day_window([OUT, BACK], 2) == (GS, cal.GRID_END)


def test_a_fork_plan_around_the_flights_is_kept_not_refused():
    early, fine, late, pool = place([plan("a", 0, h(7), h(7, 45)), plan("b", 0, h(9, 45), h(11)), plan("c", 4, h(12, 15), h(13)),
                                     plan("d", 4, h(17), h(19), "Pool time")], blocks=[OUT, BACK])
    assert early.checked and not early.hard and fine.checked and late.checked and not late.hard
    assert pool.checked and pool.overlap == ""


def test_a_plan_that_ends_exactly_at_the_buffer_still_fits():
    [ok] = place([plan("a", 4, h(10), h(12, 10))], blocks=[OUT, BACK])
    assert ok.state == "free"
