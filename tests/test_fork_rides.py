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
