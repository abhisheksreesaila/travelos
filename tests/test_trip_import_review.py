"""F-042 review fixes: several hotels, late events, red-eyes, one-way connections."""

import re

import pytest
from html import unescape

from gitaway import rides, session as ses, share, tripcal as cal, tripimport
from tests.test_roles import crew  # noqa: F401 - a fixture
from tests.test_signin import person, sign_in
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
    assert blocks["b-in"].at == 23 * 60 + 30 and blocks["b-in"].end == 24 * 60 - 1
    back = blocks["b-back"]
    assert (back.day, back.at, back.end) == (4, 23 * 60 + 50, 24 * 60 - 1) and back.end - back.start >= 30 and back.start <= 23 * 60 + 29  # true time kept, readable height
    assert cal.window_problem(list(blocks.values()), 4, 20 * 60, 22 * 60)[0] == "home" and cal.window_problem(list(blocks.values()), 4, 20 * 60, 21 * 60 + 50) is None
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


OPEN_JAW = """trip:
  title: Open jaw
  destination: Los Angeles
  start: 2026-10-16
  end: 2026-10-20
travelers:
  - name: A
flights:
  - {airline: Alaska, number: AS 1, from: SFO, to: PHX, depart: 2026-10-16 05:00, arrive: 2026-10-16 08:00}
  - {airline: Alaska, number: AS 2, from: PHX, to: LAX, depart: 2026-10-16 10:00, arrive: 2026-10-16 11:00}
  - {airline: Alaska, number: AS 3, from: LAX, to: OAK, depart: 2026-10-20 14:00, arrive: 2026-10-20 15:20}
"""


def test_an_open_jaw_trip_splits_at_the_long_stay_and_a_connection_alone_is_one_way():
    plan = tripimport.parse(OPEN_JAW).plan
    assert plan.arrive_leg.dest == "LAX" and plan.depart_leg.dest == "OAK" and tripimport.flight_offer(plan, "imp-x").back_depart_min == 14 * 60
    assert [x.id for x in cal.imported_blocks(plan, tripimport.trip_search(plan))] == ["b-leg1", "b-out", "b-back"]
    one_way = tripimport.parse(OPEN_JAW.split("  - {airline: Alaska, number: AS 3")[0]).plan
    assert one_way.arrive_leg.dest == "LAX" and one_way.depart_leg is None
    overnight = OPEN_JAW.split("  - {airline: Alaska, number: AS 3")[0].replace("depart: 2026-10-16 10:00, arrive: 2026-10-16 11:00", "depart: 2026-10-17 10:00, arrive: 2026-10-17 11:00").replace("end: 2026-10-20", "end: 2026-10-20")
    assert tripimport.parse(overnight).plan.arrive_leg.dest == "PHX"  # an overnight wait is the stay, wherever it is


def test_times_with_a_utc_offset_are_read_as_local_times():
    plan = tripimport.parse(TEMPLATE.replace("check_out: 2026-10-20 11:00", "check_out: 2026-10-20 11:00:00-07:00").replace("depart: 2026-10-16 08:05", "depart: 2026-10-16T08:05Z")
                            .replace("arrive: 2026-10-16 09:32", "arrive: 2026-10-16 09:32:00+0000")).plan
    assert plan.hotels[0].check_out.hour == 11 and plan.legs[0].depart.hour == 8 and plan.legs[0].arrive.minute == 32


def test_a_correction_moves_scheduled_rides_and_the_preview_says_so(client, clock):
    imported(client, no_car())
    p = person()
    trip_id = ses.trips(p)[0].id
    b = ses.booking(p)
    plan = rides.leg_plan("arrive", cal.flight_of(b), cal.stay_for(b, "arrive"), cal.trip_of(b))
    est = next(e for e in rides.provider().estimates(plan) if e.key == "x")
    ride = rides.schedule_ride(p, rides.ScheduleRequest(plan, rides.validate_guest("Ari", "Rivera", "(310) 555-0123"), est.product_id, est.fare_id, rides.next_ride_id(p), rides.booking_key(b)))
    assert ride.pickup_time.strftime("%H:%M") == "10:02"
    later = no_car().replace("arrive: 2026-10-16 09:32", "arrive: 2026-10-16 11:15").replace("depart: 2026-10-16 08:05", "depart: 2026-10-16 09:45")
    html = client.post("/trips/import", data={"text": later}).text
    assert 'id="ti-moves"' in html and "1 scheduled Uber ride will move" in visible(html)
    assert 'id="ti-moves"' not in client.post("/trips/import", data={"text": no_car()}).text
    assert client.post("/trips/import/save", data={"text": later, "replace": trip_id}, follow_redirects=False).status_code == 303
    moved = [x for x in rides.list_rides(person()) if not x.canceled][0]
    assert moved.id == ride.id and moved.pickup_time.strftime("%H:%M") == "11:45" and moved.key == rides.booking_key(ses.booking(person()))
    # a ride with a driver on the way is left alone
    rides.step_ride(person(), moved.id)
    later2 = later.replace("arrive: 2026-10-16 11:15", "arrive: 2026-10-16 12:15").replace("depart: 2026-10-16 09:45", "depart: 2026-10-16 10:45")
    assert "ti-moves" not in client.post("/trips/import", data={"text": later2}).text
    client.post("/trips/import/save", data={"text": later2, "replace": trip_id}, follow_redirects=False)
    assert [x for x in rides.list_rides(person()) if not x.canceled][0].pickup_time.strftime("%H:%M") == "11:45"


def test_deleting_a_trip_takes_its_shared_page_down_too(client):
    from gitaway import community
    imported(client)
    trip_id = ses.trips(person())[0].id
    client.post("/share", data={"custom": "1"}, follow_redirects=False)
    assert len(community.rows(kind="shared")) == 1
    assert "shared page comes down" in client.get(f"/trip/delete?trip={trip_id}").text
    assert client.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False).status_code == 303
    assert community.rows(kind="shared") == []


def test_roles_gate_the_import_routes(crew):
    owner, editor, viewer = crew
    for path in ("/trips/import", "/trips/import/save"):
        assert viewer.post(path, data={"text": TEMPLATE}, follow_redirects=False).status_code == 403, path
    assert viewer.get("/trips/import").status_code == 403 and viewer.get("/trips/import/template").status_code == 200
    assert editor.post("/trips/import", data={"text": TEMPLATE}).status_code == 200
    r = editor.post("/trips/import/save", data={"text": TEMPLATE}, follow_redirects=False)
    assert r.status_code == 303
    trip_id = [t.id for t in ses.trips(person()) if t.source == "imported"][0]
    assert editor.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False).status_code == 403
    assert viewer.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False).status_code == 403
    assert editor.get(f"/trip/delete?trip={trip_id}").status_code == 403
    assert owner.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False).status_code == 303


def test_a_late_flight_keeps_its_true_time_in_the_share_and_in_the_overlap_message(client):
    imported(client, late())
    built = share.build(person())
    times = [s.time for s in built.days[4].stops]
    assert "11:50 PM" in times and "11:29 PM" not in times
    # a block drawn earlier than its true time quotes the true time when something overlaps it
    t = tripimport.trip_search(plan)
    assert t.airports == ("LAX",) and tripimport.flight_offer(plan, "imp-x").airport == "LAX"
    assert [x.id for x in cal.imported_blocks(plan, t)] == ["b-leg1", "b-out"]


OPEN_JAW = """trip:
  title: Open jaw
  destination: Los Angeles
  start: 2026-10-16
  end: 2026-10-20
travelers:
  - name: A
flights:
  - {airline: Alaska, number: AS 1, from: SFO, to: PHX, depart: 2026-10-16 05:00, arrive: 2026-10-16 08:00}
  - {airline: Alaska, number: AS 2, from: PHX, to: LAX, depart: 2026-10-16 10:00, arrive: 2026-10-16 11:00}
  - {airline: Alaska, number: AS 3, from: LAX, to: OAK, depart: 2026-10-20 14:00, arrive: 2026-10-20 15:20}
"""


def test_an_open_jaw_trip_splits_at_the_long_stay_and_a_connection_alone_is_one_way():
    plan = tripimport.parse(OPEN_JAW).plan
    assert plan.arrive_leg.dest == "LAX" and plan.depart_leg.dest == "OAK" and tripimport.flight_offer(plan, "imp-x").back_depart_min == 14 * 60
    assert [x.id for x in cal.imported_blocks(plan, tripimport.trip_search(plan))] == ["b-leg1", "b-out", "b-back"]
    one_way = tripimport.parse(OPEN_JAW.split("  - {airline: Alaska, number: AS 3")[0]).plan
    assert one_way.arrive_leg.dest == "LAX" and one_way.depart_leg is None
    overnight = OPEN_JAW.split("  - {airline: Alaska, number: AS 3")[0].replace("depart: 2026-10-16 10:00, arrive: 2026-10-16 11:00", "depart: 2026-10-17 10:00, arrive: 2026-10-17 11:00").replace("end: 2026-10-20", "end: 2026-10-20")
    assert tripimport.parse(overnight).plan.arrive_leg.dest == "PHX"  # an overnight wait is the stay, wherever it is


def test_times_with_a_utc_offset_are_read_as_local_times():
    plan = tripimport.parse(TEMPLATE.replace("check_out: 2026-10-20 11:00", "check_out: 2026-10-20 11:00:00-07:00").replace("depart: 2026-10-16 08:05", "depart: 2026-10-16T08:05Z")
                            .replace("arrive: 2026-10-16 09:32", "arrive: 2026-10-16 09:32:00+0000")).plan
    assert plan.hotels[0].check_out.hour == 11 and plan.legs[0].depart.hour == 8 and plan.legs[0].arrive.minute == 32


def test_a_correction_moves_scheduled_rides_and_the_preview_says_so(client, clock):
    imported(client, no_car())
    p = person()
    trip_id = ses.trips(p)[0].id
    b = ses.booking(p)
    plan = rides.leg_plan("arrive", cal.flight_of(b), cal.stay_for(b, "arrive"), cal.trip_of(b))
    est = next(e for e in rides.provider().estimates(plan) if e.key == "x")
    ride = rides.schedule_ride(p, rides.ScheduleRequest(plan, rides.validate_guest("Ari", "Rivera", "(310) 555-0123"), est.product_id, est.fare_id, rides.next_ride_id(p), rides.booking_key(b)))
    assert ride.pickup_time.strftime("%H:%M") == "10:02"
    later = no_car().replace("arrive: 2026-10-16 09:32", "arrive: 2026-10-16 11:15").replace("depart: 2026-10-16 08:05", "depart: 2026-10-16 09:45")
    html = client.post("/trips/import", data={"text": later}).text
    assert 'id="ti-moves"' in html and "1 scheduled Uber ride will move" in visible(html)
    assert 'id="ti-moves"' not in client.post("/trips/import", data={"text": no_car()}).text
    assert client.post("/trips/import/save", data={"text": later, "replace": trip_id}, follow_redirects=False).status_code == 303
    moved = [x for x in rides.list_rides(person()) if not x.canceled][0]
    assert moved.id == ride.id and moved.pickup_time.strftime("%H:%M") == "11:45" and moved.key == rides.booking_key(ses.booking(person()))
    # a ride with a driver on the way is left alone
    rides.step_ride(person(), moved.id)
    later2 = later.replace("arrive: 2026-10-16 11:15", "arrive: 2026-10-16 12:15").replace("depart: 2026-10-16 09:45", "depart: 2026-10-16 10:45")
    assert "ti-moves" not in client.post("/trips/import", data={"text": later2}).text
    client.post("/trips/import/save", data={"text": later2, "replace": trip_id}, follow_redirects=False)
    assert [x for x in rides.list_rides(person()) if not x.canceled][0].pickup_time.strftime("%H:%M") == "11:45"


def test_deleting_a_trip_takes_its_shared_page_down_too(client):
    from gitaway import community
    imported(client)
    trip_id = ses.trips(person())[0].id
    client.post("/share", data={"custom": "1"}, follow_redirects=False)
    assert len(community.rows(kind="shared")) == 1
    assert "shared page comes down" in client.get(f"/trip/delete?trip={trip_id}").text
    assert client.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False).status_code == 303
    assert community.rows(kind="shared") == []


def test_roles_gate_the_import_routes(crew):
    owner, editor, viewer = crew
    for path in ("/trips/import", "/trips/import/save"):
        assert viewer.post(path, data={"text": TEMPLATE}, follow_redirects=False).status_code == 403, path
    assert viewer.get("/trips/import").status_code == 403 and viewer.get("/trips/import/template").status_code == 200
    assert editor.post("/trips/import", data={"text": TEMPLATE}).status_code == 200
    r = editor.post("/trips/import/save", data={"text": TEMPLATE}, follow_redirects=False)
    assert r.status_code == 303
    trip_id = [t.id for t in ses.trips(person()) if t.source == "imported"][0]
    assert editor.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False).status_code == 403
    assert viewer.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False).status_code == 403
    assert editor.get(f"/trip/delete?trip={trip_id}").status_code == 403
    assert owner.post("/trip/delete", data={"trip": trip_id}, follow_redirects=False).status_code == 303


def test_a_late_flight_keeps_its_true_time_in_the_share_and_in_the_overlap_message(client):
    imported(client, late())
    built = share.build(person())
    times = [s.time for s in built.days[4].stops]
    assert "11:50 PM" in times and "11:29 PM" not in times
    # a block drawn earlier than its true time quotes the true time when something overlaps it
    block = cal.Block("b-back", 0, 23 * 60 + 29, 24 * 60 - 1, "Flight", "booked", True, "plane", label_start=23 * 60 + 50)
    t = tripimport.trip_search(tripimport.parse(TEMPLATE).plan)
    with pytest.raises(cal.CalendarError, match=r"10:30 AM – 11:40 AM"):
        cal._clean(t, [cal.Block("b-x", 0, 600, 700, "Flight", "booked", True, "plane", label_start=630)], day=0, start="10:15", end="11:00", title="x", kind="fun")
