"""F-081: Mark done and Set aside tell the family, in one coalesced thread card ("Abhi finished 3 rides at Universal Studios Hollywood"), and the canvas's one-pass read of
a trip's blocks (canvas.plan)."""

import json

import pytest

from gitaway import canvas, familydb, familythread, session as ses, tripcal as cal
from tests.test_canvas import announced, ari, azure, draft_and_answers, rows  # noqa: F401 - fixtures


@pytest.fixture
def uni(ari):
    draft, answers = draft_and_answers(ari)
    canvas.save(ari, draft, answers)
    return cal.activities(ari)[0].id


def steps(ari, uni, *titles):
    view = canvas.block(ari, uni)
    by = {s["title"]: s for p in view["parts"] for s in p["steps"]}
    return [by[t]["id"] for t in titles]


def cards(ari):
    return [r for r in rows(ari, "SELECT * FROM thread ORDER BY rowid") if "Universal" in r["text"] and "added" not in r["text"]]


def test_marking_rides_done_is_one_card_that_counts_up(ari, uni, announced):
    a, b, c = steps(ari, uni, "Revenge of the Mummy", "King Kong", "Kung Fu Panda")
    before = len(announced)
    canvas.set_done(ari, a)
    assert [r["text"] for r in cards(ari)][-1].endswith("finished Revenge of the Mummy at Universal Studios Hollywood")
    canvas.set_done(ari, b)
    canvas.set_done(ari, c)
    mine = cards(ari)
    assert len(mine) == 1
    assert mine[0]["text"].split(" finished ")[1] == "3 rides at Universal Studios Hollywood"
    assert json.loads(mine[0]["payload"])["n"] == 3
    assert len(announced) == before + 1       # the family is pushed once, not three times


def test_undoing_takes_one_off_and_the_last_one_removes_the_card(ari, uni, announced):
    a, b = steps(ari, uni, "Revenge of the Mummy", "King Kong")
    canvas.set_done(ari, a)
    canvas.set_done(ari, b)
    canvas.set_done(ari, b, False)
    assert cards(ari)[0]["text"].split(" finished ")[1] == "1 ride at Universal Studios Hollywood"
    canvas.set_done(ari, a, False)
    assert cards(ari) == []


def test_set_aside_has_its_own_card_and_putting_back_undoes_it(ari, uni, announced):
    a, b = steps(ari, uni, "Revenge of the Mummy", "King Kong")
    canvas.set_aside(ari, a)
    canvas.set_aside(ari, b)
    [card] = cards(ari)
    assert card["text"].split(" set aside ")[1] == "2 rides at Universal Studios Hollywood"
    canvas.set_aside(ari, a, False)
    assert cards(ari)[0]["text"].split(" set aside ")[1] == "1 ride at Universal Studios Hollywood"


def test_an_unchanged_tick_says_nothing(ari, uni, announced):
    [a] = steps(ari, uni, "King Kong")
    canvas.set_done(ari, a)
    canvas.set_done(ari, a)       # already done: no second count
    assert json.loads(cards(ari)[0]["payload"])["n"] == 1


def test_another_kind_of_card_in_between_starts_a_new_card(ari, uni, announced):
    a, b = steps(ari, uni, "Revenge of the Mummy", "King Kong")
    canvas.set_done(ari, a)
    familythread.post_message(ari, "see you at the gate")
    canvas.set_done(ari, b)
    assert len(cards(ari)) == 2


def test_an_old_card_is_not_reopened(ari, uni, announced, monkeypatch):
    a, b = steps(ari, uni, "Revenge of the Mummy", "King Kong")
    canvas.set_done(ari, a)
    monkeypatch.setattr(canvas, "CARD_WINDOW", -1)
    canvas.set_done(ari, b)
    assert len(cards(ari)) == 2


def test_plan_reads_every_block_in_one_pass(ari, uni):
    got = canvas.plan(ari)
    assert set(got["blocks"]) == {a.id for a in cal.activities(ari)}
    block = got["blocks"][uni]
    assert [p["name"] for p in block["parts"]] == ["Lower Lot", "Lunch", "Harry Potter world", "Upper Lot"]
    assert [s["title"] for s in block["aside"]] == ["Studio Tour", "Simpsons"]
    hippo = next(s for p in block["parts"] for s in p["steps"] if s["title"] == "Hippogriff")
    assert [x["kind"] for x in hippo["people"]] == ["member", "named"] and hippo["people"][1]["name"] == "Bhoomija" and hippo["people"][1]["initials"] == "B"
    assert got["lists"][0]["name"] == "Pregnancy-safe rides"
    assert canvas.plan({}) == {"blocks": {}, "lists": []}
