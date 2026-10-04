"""F-082: moving, adding and annotating steps by touch, at the model (gitaway.canvas): move_step and restore (Undo puts everything back exactly), add_step,
set_note, the list matching the filters use, and the family card that moves and adds share. The trip is the captain's Universal + California Adventure messages
through the canned model answer (no network)."""

import json

import pytest

from gitaway import canvas, familydb, session as ses
from tests.test_canvas import announced, azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added
from tests.test_signin import person


@pytest.fixture
def trip(client, azure):
    from tests.test_calendar import book
    book(client)
    added(client)
    return client


def plan():
    return canvas.plan(person("ari"))


def find(title):
    """(step, its block, its part or None when it is in the tray)."""
    for act, blk in plan()["blocks"].items():
        for p in blk["parts"]:
            for s in p["steps"]:
                if s["title"] == title:
                    return s, act, p
        for s in blk["aside"]:
            if s["title"] == title:
                return s, act, None
    raise AssertionError(title)


def part_titles(act, name):
    return [s["title"] for p in plan()["blocks"][act]["parts"] if p["name"] == name for s in p["steps"]]


def part_id(act, name):
    return next(p["id"] for p in plan()["blocks"][act]["parts"] if p["name"] == name)


def other_block(act):
    return next(a for a in plan()["blocks"] if a != act)


def cards():
    return [c["text"] for c in rows(person("ari"), "SELECT * FROM thread ORDER BY rowid")]


def set_time(title, value):
    with ses.family(person("ari")) as fam:
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "UPDATE block_steps SET time = :v WHERE title = :t", v=value, t=title)


# ---- moving ---------------------------------------------------------------------------------------------------------------

def test_a_step_dropped_before_another_lands_there(trip):
    s, act, p = find("Minion Mayhem")
    first = find("King Kong")[0]
    r = canvas.move_step(person("ari"), s["id"], part=p["id"], before=first["id"])
    assert r["changed"] and r["title"] == "Minion Mayhem" and r["act"] == act
    titles = part_titles(act, p["name"])
    assert titles.index("Minion Mayhem") == titles.index("King Kong") - 1
    assert sorted(titles) == sorted(set(titles))          # nothing doubled, nothing lost


def test_a_step_dropped_at_the_end_of_another_part_changes_part_and_the_source_closes_up(trip):
    s, act, src = find("Minion Mayhem")
    before_src = len(part_titles(act, src["name"]))
    r = canvas.move_step(person("ari"), s["id"], part=part_id(act, "Lunch"))
    assert r["where"] == "Lunch" and part_titles(act, "Lunch")[-1] == "Minion Mayhem"
    assert len(part_titles(act, src["name"])) == before_src - 1


def test_dropped_before_a_timed_step_a_step_takes_its_time_and_at_the_end_it_keeps_its_own(trip):
    set_time("King Kong", "13:00")
    set_time("Minion Mayhem", "09:30")
    s, act, p = find("Minion Mayhem")
    r = canvas.move_step(person("ari"), s["id"], part=p["id"], before=find("King Kong")[0]["id"])
    assert find("Minion Mayhem")[0]["time"] == "13:00" and r["where"] == "1:00 PM"
    set_time("Minion Mayhem", "09:30")
    canvas.move_step(person("ari"), s["id"], part=p["id"])
    assert find("Minion Mayhem")[0]["time"] == "09:30" and part_titles(act, p["name"])[-1] == "Minion Mayhem"


def test_dropping_a_step_where_it_already_is_changes_nothing_and_says_nothing(trip, announced):
    s, act, p = find("King Kong")
    order = part_titles(act, p["name"])
    nxt = find(order[order.index("King Kong") + 1])[0]
    r = canvas.move_step(person("ari"), s["id"], part=p["id"], before=nxt["id"])
    assert r["changed"] is False and part_titles(act, p["name"]) == order
    assert not any("moved" in c for c in cards())


def test_a_step_dropped_on_another_day_goes_to_that_blocks_first_part_at_the_end(trip):
    s, act, p = find("Minion Mayhem")
    other = other_block(act)
    r = canvas.move_step(person("ari"), s["id"], act=other)
    assert r["act"] == other and r["where"] in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    _, new_act, new_part = find("Minion Mayhem")
    assert new_act == other and new_part["name"] == plan()["blocks"][other]["parts"][0]["name"] and new_part["steps"][-1]["title"] == "Minion Mayhem"
    assert "Minion Mayhem" not in part_titles(act, p["name"])


def test_set_aside_by_drop_goes_to_the_tray_and_out_of_the_tray_goes_back_into_a_part(trip):
    s, act, p = find("King Kong")
    r = canvas.move_step(person("ari"), s["id"], aside=True)
    assert r["where"] == "the Set aside tray" and any(x["title"] == "King Kong" for x in plan()["blocks"][act]["aside"])
    r = canvas.move_step(person("ari"), s["id"], part=part_id(act, "Lunch"))
    assert r["where"] == "Lunch" and part_titles(act, "Lunch")[-1] == "King Kong" and not any(x["title"] == "King Kong" for x in plan()["blocks"][act]["aside"])


def test_a_move_to_a_place_that_is_not_in_the_trip_or_a_step_that_is_gone_is_refused(trip):
    s = find("King Kong")[0]
    for kw in ({"part": "nope"}, {"act": "a99"}, {}):
        with pytest.raises(canvas.CanvasError):
            canvas.move_step(person("ari"), s["id"], **kw)
    with pytest.raises(canvas.CanvasError):
        canvas.move_step(person("ari"), "nope", aside=True)


# ---- Undo -----------------------------------------------------------------------------------------------------------------

def state():
    return json.dumps([[(p["name"], [(x["id"], x["time"], x["done"], x["aside"]) for x in p["steps"]]) for p in blk["parts"]] + [[x["id"] for x in blk["aside"]]]
                       for blk in plan()["blocks"].values()])


@pytest.mark.parametrize("where", ["before", "end of another part", "another day", "tray"])
def test_undo_puts_everything_back_exactly(trip, where):
    me = person("ari")
    s, act, p = find("Minion Mayhem")
    set_time("King Kong", "13:00")
    kw = {"before": dict(part=p["id"], before=find("King Kong")[0]["id"]), "end of another part": dict(part=part_id(act, "Lunch")), "another day": dict(act=other_block(act)),
          "tray": dict(aside=True)}[where]
    before = state()
    r = canvas.move_step(me, s["id"], **kw)
    assert state() != before
    assert canvas.restore(me, json.loads(json.dumps(r["undo"]))) == act            # as it travels: through the page
    assert state() == before


def test_undo_takes_the_move_off_the_family_card(trip, announced):
    me = person("ari")
    _, act, _ = find("Minion Mayhem")
    one = canvas.move_step(me, find("Minion Mayhem")[0]["id"], part=part_id(act, "Lunch"))
    two = canvas.move_step(me, find("King Kong")[0]["id"], part=part_id(act, "Lunch"))
    assert any("moved 2 rides at" in c for c in cards()) and sum("moved" in c for c in cards()) == 1       # two moves, one card
    canvas.restore(me, two["undo"])
    assert any("moved 1 ride at" in c for c in cards())
    canvas.restore(me, one["undo"])
    assert not any("moved" in c for c in cards())


def test_a_moved_step_is_one_card_with_one_push(trip, announced):
    _, act, _ = find("Minion Mayhem")
    announced.clear()
    canvas.move_step(person("ari"), find("Minion Mayhem")[0]["id"], part=part_id(act, "Lunch"))
    assert any("moved Minion Mayhem at Universal Studios Hollywood" in c for c in cards()) and len(announced) == 1
    canvas.move_step(person("ari"), find("King Kong")[0]["id"], part=part_id(act, "Lunch"))
    assert len(announced) == 1          # changed in place, no second push


def test_a_doctored_snapshot_is_refused_and_changes_nothing(trip):
    me = person("ari")
    s, act, p = find("King Kong")
    good = canvas.move_step(me, s["id"], part=part_id(act, "Lunch"))["undo"]
    other = other_block(act)
    foreign = plan()["blocks"][other]["parts"][0]["id"]
    one = good["steps"][0]
    before = state()
    bad = [
        {"kind": "moved", "act": act, "steps": [{**one, "id": "nope"}]},
        {"kind": "moved", "act": act, "steps": [{**one, "part": foreign}]},          # a part of another block
        {"kind": "moved", "act": act, "steps": [{**one, "time": "99:99"}]},
        {"kind": "moved", "act": act, "steps": [{**one, "time": "9:5"}]},
        {"kind": "moved", "act": act, "steps": [{**one, "position": -4}]},
        {"kind": "moved", "act": act, "steps": [{**one, "position": True}]},
        {"kind": "moved", "act": act, "steps": [{**one, "aside": 7}]},
        {"kind": "moved", "act": "a99", "steps": [one]},
        {"kind": "delete", "act": act, "steps": [one]},
        {"kind": "moved", "act": act, "steps": []},
        {"kind": "moved", "act": act, "steps": [one] * 500},
        "text", None, [],
    ]
    for b in bad:
        with pytest.raises(canvas.CanvasError):
            canvas.restore(me, b)
        assert state() == before, b


# ---- adding ---------------------------------------------------------------------------------------------------------------

def test_a_new_step_lands_at_the_end_of_its_part_with_its_who_time_and_note(trip, announced):
    me = person("ari")
    _, act, p = find("Minion Mayhem")
    mine = f"m:{me['user_id']}"
    sid = canvas.add_step(me, act, p["id"], "  Churro   break ", time="10:45", who=[mine, "g:Kids"], note="Cinnamon!")
    got = find("Churro break")[0]
    assert got["id"] == sid and got["time"] == "10:45" and got["note"] == "Cinnamon!" and got["who_key"] == tuple(sorted([mine, "g:Kids"])) and not got["done"]
    assert part_titles(act, p["name"])[-1] == "Churro break"
    assert any("added Churro break at Universal Studios Hollywood" in c for c in cards())


def test_adds_coalesce_into_one_card(trip, announced):
    _, act, p = find("Minion Mayhem")
    for t in ("Churro break", "Water stop", "Photo"):
        canvas.add_step(person("ari"), act, p["id"], t)
    assert sum(" at Universal" in c and "added" in c for c in cards()) == 1 and any("added 3 steps at" in c for c in cards())


def test_a_step_with_no_who_is_for_everyone(trip):
    _, act, p = find("Minion Mayhem")
    canvas.add_step(person("ari"), act, p["id"], "Churro break")
    assert find("Churro break")[0]["people"] == []


def test_adding_refuses_what_it_cannot_keep(trip):
    me = person("ari")
    _, act, p = find("Minion Mayhem")
    with pytest.raises(canvas.CanvasError, match="name"):
        canvas.add_step(me, act, p["id"], "   ")
    for kw in (dict(time="25:61"), dict(who=["m:someone-else"]), dict(who=["n:Stranger"])):
        with pytest.raises(canvas.CanvasError):
            canvas.add_step(me, act, p["id"], "x", **kw)
    with pytest.raises(canvas.CanvasError):
        canvas.add_step(me, other_block(act), p["id"], "x")          # the part is another block's
    with pytest.raises(canvas.CanvasError):
        canvas.add_step(me, act, "nope", "x")
    assert "x" not in [x["title"] for blk in plan()["blocks"].values() for q in blk["parts"] for x in q["steps"]]


def test_a_name_or_initials_already_on_the_trip_can_be_chosen_again(trip):
    _, act, p = find("Minion Mayhem")
    seen = next(tok for blk in plan()["blocks"].values() for q in blk["parts"] for x in q["steps"] for tok in x["who_key"] if tok.startswith(("i:", "n:")))
    canvas.add_step(person("ari"), act, p["id"], "Walk", who=[seen])
    assert seen in find("Walk")[0]["who_key"]


def test_the_title_and_note_are_capped(trip):
    _, act, p = find("Minion Mayhem")
    canvas.add_step(person("ari"), act, p["id"], "T" * 500, note="n" * 900)
    got = [x for blk in plan()["blocks"].values() for q in blk["parts"] for x in q["steps"] if x["title"].startswith("TTTT")][0]
    assert len(got["title"]) == 80 and len(got["note"]) == canvas.MAX_NOTE


# ---- notes ----------------------------------------------------------------------------------------------------------------

def test_a_note_is_written_replaced_and_cleared_without_a_card(trip, announced):
    s, act, _ = find("King Kong")
    before = len(cards())
    assert canvas.set_note(person("ari"), s["id"], "  Ride  it   first ") == act
    assert find("King Kong")[0]["note"] == "Ride it first"
    canvas.set_note(person("ari"), s["id"], "")
    assert find("King Kong")[0]["note"] == "" and len(cards()) == before
    with pytest.raises(canvas.CanvasError):
        canvas.set_note(person("ari"), "nope", "x")


# ---- lists ----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("step,item,expected", [
    ("Soarin'", "Soarin' Around the World", True), ("The Little Mermaid", "Little Mermaid", True), ("Web Slingers", "web slingers", True),
    ("Toy Story Midway Mania", "Toy Story Midway Mania", True), ("Toy Story", "Toy Story Midway Mania", True), ("King Kong", "Kong", False), ("Rat", "Rated R", False),
    ("", "x", False), ("Cars", "Racers", False)])
def test_a_step_is_a_list_item_when_the_names_match_by_whole_words(step, item, expected):
    assert canvas.same_step(step, item) is expected


def test_the_pregnancy_safe_list_has_four_rides_in_the_california_day_and_four_not_in_it(trip):
    lists = plan()["lists"]
    day = next(a for a, blk in plan()["blocks"].items() if any(x["title"] == "Web Slingers" for p in blk["parts"] for x in p["steps"]))
    steps = [x for p in plan()["blocks"][day]["parts"] for x in p["steps"]]
    hits = [x["title"] for x in steps if canvas.list_hits(x["title"], lists)]
    assert sorted(hits) == sorted(["Web Slingers", "Toy Story Midway Mania", "Soarin'", "The Little Mermaid"])
    missing = [i["title"] for i in lists[0]["items"] if not any(canvas.same_step(x["title"], i["title"]) for x in steps)]
    assert len(missing) == 4 and "Golden Zephyr" in missing


# ---- review fixes ----------------------------------------------------------------------------------------------------------

def test_restore_needs_a_part_for_a_step_that_is_not_in_the_tray(trip):
    me = person("ari")
    s, act, p = find("King Kong")
    good = canvas.move_step(me, s["id"], part=part_id(act, "Lunch"))["undo"]
    before = state()
    bad = {**good, "steps": [{**good["steps"][0], "part": "", "aside": 0}]}
    with pytest.raises(canvas.CanvasError):
        canvas.restore(me, bad)
    assert state() == before


def set_gone(act):
    with ses.family(person("ari")) as fam:
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "UPDATE activities SET gone = 1 WHERE act_id = :a", a=act)


def test_moving_or_adding_into_a_deleted_block_is_refused(trip):
    me = person("ari")
    s, act, p = find("King Kong")
    other = other_block(act)
    target_part = plan()["blocks"][other]["parts"][0]["id"]
    set_gone(other)
    before = state()
    for kw in (dict(act=other), dict(part=target_part)):
        with pytest.raises(canvas.CanvasError):
            canvas.move_step(me, s["id"], **kw)
    with pytest.raises(canvas.CanvasError):
        canvas.add_step(me, other, target_part, "Ghost")
    assert state() == before
