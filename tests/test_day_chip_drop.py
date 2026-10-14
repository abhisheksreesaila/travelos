"""F-151: a plan dropped on another day's chip in the desktop header is moved to that day (the same time), through HTTP. The write is the canvas's own POST /trip/canvas/plan
(op=edit with a `day`), so it reuses the toast, the Undo snapshot, the lanes and the editor-only gate. The trip is the demo booking (Fri 16 fly in, Sat 17 Universal, Sun 18 free)."""

import json
import re

from gitaway import tripcal as cal
from tests.test_canvas import azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_day_grid import blocks, day, edit, plan, style
from tests.test_signin import person
from tests.test_trip_canvas import trip  # noqa: F401 - fixtures


def test_a_plan_sent_to_another_day_keeps_its_times_says_where_and_undo_brings_it_back(trip):
    me = person("ari")
    a = plan(me, "Lunch", 12 * 60, 13 * 60)
    r = edit(trip, a.id, day=1)
    got = r.json()
    assert r.status_code == 200 and got["toast"] == "Moved to Sat 17"
    now = cal.get_activity(me, a.id)
    assert (now.day, now.start, now.end) == (1, 720, 780)
    assert got["undo"]["day"] == 2 and got["undo"]["after"]["day"] == 1
    assert a.id not in [b["data-act"] for b in blocks(day(trip, 2))] and a.id in [b["data-act"] for b in blocks(day(trip, 1))]
    back = trip.post("/trip/canvas/plan", data={"op": "undo", "undo": json.dumps(got["undo"])}, headers={"X-Canvas": "1"})
    assert back.json()["toast"] == "Put back" and cal.get_activity(me, a.id).day == 2


def test_a_plan_sent_to_a_day_outside_the_trip_or_to_its_own_day_changes_nothing(trip):
    me = person("ari")
    a = plan(me, "Lunch", 12 * 60, 13 * 60)
    assert edit(trip, a.id, day=99).status_code == 422 and edit(trip, a.id, day="x").status_code == 422
    same = edit(trip, a.id, day=2).json()
    assert same["toast"] == "" and same["undo"] is None and cal.get_activity(me, a.id).day == 2


def test_a_plan_sent_to_a_busy_day_sits_beside_what_is_there_and_nothing_is_refused(trip):
    me = person("ari")
    a = plan(me, "Lunch", 12 * 60, 13 * 60)
    b = plan(me, "Picnic", 12 * 60 + 30, 13 * 60 + 30, day=1)
    assert edit(trip, a.id, day=1).status_code == 200
    lanes = {x["data-act"]: style(x) for x in blocks(day(trip, 1)) if x.get("data-act") in (a.id, b.id)}
    assert len(lanes) == 2 and len({v["lane"] for v in lanes.values()}) == 2 and all(int(v["lanes"]) >= 2 for v in lanes.values())      # (Saturday's park block shares the hours: three lanes)


def test_a_booking_cannot_be_sent_to_another_day(trip):
    assert edit(trip, "b-out", day=1).status_code == 422


def test_the_day_chips_say_which_day_they_take_a_dropped_plan_to(trip):
    page = day(trip, 2)
    chips = re.findall(r"<a [^>]*cz-hchip[^>]*>", page)
    assert chips and all("data-move-day=" in c and "data-move-label=" in c for c in chips)
    assert 'data-move-day="1"' in page and 'data-move-label="Sat 17"' in page


def test_a_viewer_cannot_send_a_plan_to_another_day(crew, azure):
    ari, viewer = crew
    added(ari)
    a = plan(person("ari"), "Lunch", 12 * 60, 13 * 60)
    assert viewer.post("/trip/canvas/plan", data={"op": "edit", "act": a.id, "day": 1}, headers={"X-Canvas": "1"}).status_code == 403
    assert cal.get_activity(person("ari"), a.id).day == 2
