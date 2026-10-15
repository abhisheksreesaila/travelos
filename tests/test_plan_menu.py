"""F-152: Change type and Move to day in the plan menu, through HTTP. Both are the canvas's own POST /trip/canvas/plan (op=edit) with a `kind` or a `day`; Undo puts the kind back."""

import json
import re

from gitaway import tripcal as cal
from tests.test_canvas import azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_day_grid import blocks, day, edit, plan
from tests.test_signin import person
from tests.test_trip_canvas import trip  # noqa: F401 - fixtures


def test_a_plan_changed_to_another_kind_keeps_its_time_says_so_and_undo_puts_the_kind_back(trip):
    me = person("ari")
    a = plan(me, "Lunch", 12 * 60, 13 * 60)
    got = edit(trip, a.id, kind="food").json()
    now = cal.get_activity(me, a.id)
    assert (now.kind, now.day, now.start, now.end, now.title) == ("food", 2, 720, 780, "Lunch")
    assert got["toast"] == "Lunch is now Food" and got["undo"]["kind"] == "fun" and got["undo"]["after"]["kind"] == "food"
    back = trip.post("/trip/canvas/plan", data={"op": "undo", "undo": json.dumps(got["undo"])}, headers={"X-Canvas": "1"})
    assert back.json()["toast"] == "Put back" and cal.get_activity(me, a.id).kind == "fun"


def test_the_kind_must_be_one_the_calendar_knows_and_the_same_kind_changes_nothing(trip):
    me = person("ari")
    a = plan(me, "Lunch", 12 * 60, 13 * 60)
    assert edit(trip, a.id, kind="nonsense").status_code == 422 and cal.get_activity(me, a.id).kind == "fun"
    same = edit(trip, a.id, kind="fun").json()
    assert same["toast"] == "" and same["undo"] is None


def test_every_plan_block_says_its_kind_and_the_day_has_the_choices(trip):
    me = person("ari")
    plan(me, "Lunch", 12 * 60, 13 * 60, kind="food")
    html = trip.get("/trip/canvas?day=2").text
    assert [b["data-type"] for b in blocks(day(trip, 2))] == ["food"]
    for k in cal.KINDS:
        assert f'data-pick-kind="{k}"' in html
    pills = [t for t in re.findall(r"<a\b[^>]*>", html) if re.search(r'class="cz-hchip[ "]', t)]
    assert pills and all("data-move-day=" in t and "data-move-label=" in t for t in pills)    # the day chips carry the move labels like the laptop's chips


def test_a_booking_cannot_change_kind(trip):
    assert edit(trip, "b-flight", kind="food").status_code == 422


def test_a_viewer_cannot_change_a_plans_kind(crew, azure):
    ari, viewer = crew
    added(ari)
    a = plan(person("ari"), "Lunch", 12 * 60, 13 * 60)
    assert viewer.post("/trip/canvas/plan", data={"op": "edit", "act": a.id, "kind": "food"}, headers={"X-Canvas": "1"}).status_code == 403
    assert cal.get_activity(person("ari"), a.id).kind == "fun"
