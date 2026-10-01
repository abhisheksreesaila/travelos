"""F-042 review fixes: several hotels, late events, red-eyes, one-way connections."""

import re
from html import unescape

from gitaway import rides, session as ses, tripcal as cal, tripimport
from tests.test_signin import person
from tests.test_trip_import import TEMPLATE, clock, imported, no_car, visible  # noqa: F401 - clock is a fixture


def two_hotels(text=None):
    return re.sub(r"\nhotel:.*?(?=\nnotes:)", """
hotels:
  - name: First Inn
    address: 1 First St, Santa Monica, CA 90401
    check_in: 2026-10-16 15:00
    check_out: 2026-10-18 11:00
    confirmation: "111"
  - name: Second Inn
    address: 2 Second St, Pasadena, CA 91101
    check_in: 2026-10-18 15:00
    check_out: 2026-10-20 11:00
    confirmation: "222"
""", text or no_car(), flags=re.S)


def test_two_hotels_put_both_stays_on_the_calendar_and_rides_go_to_the_hotel_of_that_night(client, clock):
    imported(client, two_hotels())
    p = person()
    b = ses.booking(p)
    blocks = {x.id: x for x in cal.booked_blocks(b, cal.trip("", b))}
    assert [(blocks[i].day, blocks[i].title) for i in ("b-in", "b-out2", "b-hin2", "b-hout2")] == [
        (0, "Check in · First Inn"), (2, "Check out · First Inn"), (2, "Check in · Second Inn"), (4, "Check out · Second Inn")]
    arrive = rides.leg_plan("arrive", cal.flight_of(b), cal.stay_for(b, "arrive"), cal.trip_of(b))
    depart = rides.leg_plan("depart", cal.flight_of(b), cal.stay_for(b, "depart"), cal.trip_of(b))
    assert arrive.dropoff.name == "First Inn" and depart.pickup.name == "Second Inn" and depart.pickup.address.startswith("2 Second St")
    html = unescape(client.get("/calendar?view=days").text)
    assert "Schedule an Uber · LAX → First Inn" in html and "Second Inn → LAX" in html
    assert "222" in client.get("/calendar?detail=b-hout2").text and "111" in client.get("/calendar?detail=b-out2").text
    text = visible(client.get("/trip/details").text)
    assert "First Inn" in text and "Second Inn" in text


def late():
    return (TEMPLATE.replace("check_in: 2026-10-16 15:00", "check_in: 2026-10-16 23:30").replace("depart: 2026-10-20 14:10", "depart: 2026-10-20 23:50")
            .replace("arrive: 2026-10-20 15:37", "arrive: 2026-10-21 01:10").replace("end: 2026-10-20", "end: 2026-10-20"))


def test_late_events_stay_inside_the_day_and_the_grid_grows_to_hold_them(client):
    imported(client, late())
    b = ses.booking(person())
    blocks = {x.id: x for x in cal.booked_blocks(b, cal.trip("", b))}
    assert blocks["b-in"].start == 23 * 60 + 30 and blocks["b-in"].end == 24 * 60 - 1
    assert (blocks["b-back"].day, blocks["b-back"].start, blocks["b-back"].end) == (4, 23 * 60 + 50, 24 * 60 - 1)  # the leaving evening, clamped
    assert "b-back-a" not in blocks  # the landing is the day after the trip ends: no column for it
    assert all(0 <= x.start and x.end <= 24 * 60 - 1 for x in blocks.values())
    assert cal.grid_end(list(blocks.values())) == 24 * 60 and cal.grid_end([]) == 22 * 60
    assert 'data-grid-end="1440"' in client.get("/calendar?view=days").text


def test_a_red_eye_blocks_the_landing_morning_and_the_leaving_evening():
    out = tripimport.parse(TEMPLATE.replace("depart: 2026-10-16 08:05", "depart: 2026-10-15 22:05").replace("arrive: 2026-10-16 09:32", "arrive: 2026-10-16 06:32")).plan
    blocks = {x.id: x for x in cal.imported_blocks(out, tripimport.trip_search(out))}
    assert (blocks["b-out"].day, blocks["b-out"].start, blocks["b-out"].end) == (0, 0, 6 * 60 + 32)  # the landing morning
    assert "b-out-d" not in blocks  # it left the evening before the trip starts
    assert cal.window_problem(list(blocks.values()), 0, 5 * 60, 6 * 60)[0] == "land"
    mid = tripimport.parse(TEMPLATE.replace("depart: 2026-10-16 08:05", "depart: 2026-10-16 22:05").replace("arrive: 2026-10-16 09:32", "arrive: 2026-10-17 06:32")).plan
    got = {x.id: x for x in cal.imported_blocks(mid, tripimport.trip_search(mid))}
    assert (got["b-out-d"].day, got["b-out-d"].start) == (0, 22 * 60 + 5) and got["b-out"].day == 1 and got["b-out"].end == 6 * 60 + 32
    assert cal.window_problem(list(got.values()), 0, 20 * 60, 21 * 60) is None  # the leaving evening is free until the flight
    assert cal.window_problem(list(got.values()), 1, 5 * 60, 6 * 60)[0] == "land"
    back = tripimport.parse(TEMPLATE.replace("depart: 2026-10-20 14:10", "depart: 2026-10-20 23:10").replace("arrive: 2026-10-20 15:37", "arrive: 2026-10-21 00:37")).plan
    blocks = {x.id: x for x in cal.imported_blocks(back, tripimport.trip_search(back))}
    assert blocks["b-back"].day == 4 and blocks["b-back"].start == 23 * 60 + 10 and "b-back-a" not in blocks
    assert cal.window_problem(list(blocks.values()), 4, 20 * 60, 21 * 60 + 30)[0] == "home"


def test_a_one_way_connection_does_not_make_the_stopover_the_stay():
    plan = tripimport.parse("""trip:
  title: One way
  destination: Los Angeles
  start: 2026-10-16
  end: 2026-10-18
travelers:
  - name: A
flights:
  - {airline: Alaska, number: AS 1, from: SFO, to: PHX, depart: 2026-10-16 05:00, arrive: 2026-10-16 08:00}
  - {airline: Alaska, number: AS 2, from: PHX, to: LAX, depart: 2026-10-16 10:00, arrive: 2026-10-16 11:00}
""").plan
    t = tripimport.trip_search(plan)
    assert t.airports == ("LAX",) and tripimport.flight_offer(plan, "imp-x").airport == "LAX"
    assert [x.id for x in cal.imported_blocks(plan, t)] == ["b-leg1", "b-out"]
