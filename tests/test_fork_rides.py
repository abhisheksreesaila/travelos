"""F-046: a scheduled Uber is on the forks page's "Your calendar" preview and is busy time for fork placement."""
from gitaway import tripcal as cal
from gitaway.tripcal import Plan
from tests.test_forks import TRIP, apply, fork
from tests.test_rides import schedule
from tests.test_calendar import book
from tests.test_signin import person


def ride_setup(client):
    book(client, c="none")
    assert schedule(client).status_code == 303
    s = person()
    b = cal.ses.booking(s)
    return s, next(x for x in cal.ride_blocks(s, b, cal.trip("", b)) if x.kind == "ride")


def test_the_forks_calendar_shows_the_scheduled_ride(client):
    _, ride = ride_setup(client)
    fork(client)
    html = client.get("/forks").text
    assert 'class="fk-ev fk-booked' in html and ride.title in html


def test_a_fork_plan_over_a_scheduled_ride_is_a_hard_clash(client):
    s, ride = ride_setup(client)
    over = Plan("x1", ride.day, ride.start, ride.start + 60, "Surf lesson", "fun")
    [placed] = cal.preview_plans(s, [over])
    assert placed.state == "clash" and placed.hard and ride.title in placed.clash
    added, _ = cal.apply_plans(s, [over], ["x1"])
    assert added == []  # applying skips it too


def test_a_plan_beside_the_ride_is_still_free(client):
    s, ride = ride_setup(client)
    beside = Plan("x2", ride.day, ride.end + 30, ride.end + 90, "Tacos", "food")
    [placed] = cal.preview_plans(s, [beside])
    assert placed.state in ("free", "clash") and ride.title not in placed.clash


def test_a_hand_added_or_moved_plan_over_a_scheduled_ride_is_refused_kindly(client):
    import pytest
    s, ride = ride_setup(client)
    when = cal.hhmm(ride.start)
    with pytest.raises(cal.CalendarError, match=r"That overlaps your Uber at \d+:\d\d [AP]M"):
        cal.add_activity(s, day=ride.day, start=when, end=cal.hhmm(ride.start + 60), title="Surf lesson")
    ok = cal.add_activity(s, day=ride.day, start=cal.hhmm(ride.end + 60), end=cal.hhmm(ride.end + 120), title="Tacos")
    with pytest.raises(cal.CalendarError, match="your Uber"):
        cal.update_activity(s, ok.id, start=when, end=cal.hhmm(ride.start + 60))
    assert cal.update_activity(s, ok.id, title="Tacos!")  # renaming without moving it still works


def test_renaming_a_plan_under_a_later_scheduled_ride_passes_but_moving_it_is_refused(client):
    import pytest
    book(client, c="none")
    s = person()
    b = cal.ses.booking(s)
    assert schedule(client).status_code == 303
    ride = next(x for x in cal.ride_blocks(s, b, cal.trip("", b)) if x.kind == "ride")
    # the plan came first; cancel the ride, add the plan over its slot, then schedule the ride again
    rid = ride.id
    assert client.post(f"/rides/{rid}/cancel", follow_redirects=False).status_code in (200, 303)
    plan = cal.add_activity(s, day=ride.day, start=cal.hhmm(ride.start), end=cal.hhmm(ride.start + 60), title="Surf lesson")
    assert schedule(client).status_code == 303
    assert cal.update_activity(s, plan.id, title="Surf lesson, early")  # not moved: allowed
    with pytest.raises(cal.CalendarError, match="your Uber"):
        cal.update_activity(s, plan.id, start=cal.hhmm(ride.start + 15), end=cal.hhmm(ride.start + 75))
