"""F-080: Paste & Convert, the model side. The captain's real Universal Studios and California Adventure messages (tests/fixtures/universal_dca.txt) go
through the real prompt and parsing with a canned model answer (tests/canvas_samples.py): nothing here reaches Azure."""

import json

import pytest

from gitaway import ai, canvas, familydb, familythread, session as ses, tripcal as cal
from tests import canvas_samples as samples
from tests.test_calendar import book
from tests.test_signin import person, tid

PEOPLE = [{"user_id": "u-abhi", "name": "Abhi Rivera"}, {"user_id": "u-bh", "name": "Bhoomija Rao"}, {"user_id": "u-hr", "name": "Hrishi Rivera"}]


@pytest.fixture
def azure(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    fake = samples.FakeAzure()
    monkeypatch.setattr(ai, "TRANSPORT", fake)
    return fake


@pytest.fixture
def ari(client):
    book(client)
    return person("ari")


@pytest.fixture
def announced(monkeypatch):
    seen = []
    monkeypatch.setattr(familythread, "announce", lambda session, trip_id, title, body, exclude="": seen.append((title, body, exclude)))
    return seen


def rows(session, sql, **kw):
    with ses.family(session) as fam:
        return familydb.rows(fam.db, sql, **kw)


# ---- reading the captain's messages ---------------------------------------------------------------------------------------

def test_the_real_messages_become_two_park_days_with_their_areas_steps_skips_and_a_list(ari, azure):
    draft = canvas.convert(ari, samples.text())
    assert canvas.summary(draft) == {"days": 2, "areas": 8, "steps": 23, "set_aside": 2, "lists": 1, "list_items": 8}
    assert [d["place"] for d in draft["days"]] == ["Universal Studios Hollywood", "Disney California Adventure"]
    assert draft["merged_repeats"] == 1
    assert [s["title"] for s in draft["set_aside"]] == ["Studio Tour", "Simpsons"]
    assert draft["lists"][0]["name"] == "Pregnancy-safe rides"
    upper = draft["days"][0]["parts"][3]["steps"]
    assert next(s for s in upper if s["title"].startswith("Fast")) ["note"].startswith("main!!!")
    assert draft["days"][0]["parts"][0]["steps"][2]["note"] == "roughest ride"
    assert set(draft["initials"]) == {"Hrishi", "H", "B", "R", "A"}


def test_the_model_is_sent_the_pasted_text_a_strict_schema_and_the_rules(ari, azure):
    canvas.convert(ari, samples.text())
    [sent] = azure.sent
    assert sent["messages"][1]["content"] == samples.text().strip()
    assert sent["response_format"]["json_schema"]["strict"] is True
    system = sent["messages"][0]["content"]
    assert "Never invent" in system and "Skip" in system and "set aside" in system and "Fast & Furious" in system
    assert system == canvas.SYSTEM and "Ari" not in system   # no family names go to the model


def test_the_call_is_logged_as_the_convert_job_without_the_text(ari, azure):
    canvas.convert(ari, samples.text())
    [row] = ai.usage_rows()
    assert row["job"] == "convert" and row["family"] == tid_family(ari) and row["ok"] == 1 and row["tokens_in"] == 900
    assert "Revenge" not in json.dumps(row)


def tid_family(session):
    return session["tenant_id"]


@pytest.mark.parametrize("text,words", [("", "Paste the messages"), ("   \n ", "Paste the messages"), ("x" * (canvas.MAX_TEXT + 1), "a lot of text")])
def test_nothing_or_too_much_pasted_is_refused_before_the_model_is_asked(ari, azure, text, words):
    with pytest.raises(canvas.CanvasError) as e:
        canvas.convert(ari, text)
    assert words in str(e.value) and azure.sent == []


def test_a_model_failure_is_a_clear_error_and_saves_nothing(ari, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k"), monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://e.example.com"), monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    monkeypatch.setattr(ai, "TRANSPORT", samples.FakeAzure(failure=TimeoutError("slow")))
    with pytest.raises(ai.AIError) as e:
        canvas.convert(ari, samples.text())
    assert "took too long" in str(e.value)
    assert rows(ari, "SELECT * FROM block_parts") == [] and cal.activities(ari) == []


def test_a_model_that_finds_nothing_says_so(ari, azure):
    azure.answer = {"days": [], "set_aside": [], "lists": [], "initials_found": [], "notes_kept": [], "merged_repeats": 0}
    with pytest.raises(canvas.CanvasError) as e:
        canvas.convert(ari, "hello")
    assert "could not find" in str(e.value)


def test_off_without_keys_is_a_friendly_error(ari):
    with pytest.raises(ai.AIError) as e:
        canvas.convert(ari, samples.text())
    assert "not switched on" in str(e.value)


# ---- cleaning ------------------------------------------------------------------------------------------------------------

def test_clean_is_idempotent_so_a_draft_can_travel_through_a_form(ari):
    once = canvas.clean(samples.model_answer())
    assert canvas.clean(json.loads(json.dumps(once))) == once


def test_clean_caps_sizes_drops_junk_and_defaults_kinds():
    junk = {"days": [{"label": "L" * 500, "park_or_place": "P" * 500, "parts": [{"name": "", "steps": [
        {"title": "  ", "kind": "ride"}, {"title": "Ride " * 100, "kind": "spaceship", "time": "25:99", "note": "n" * 900, "who_raw": ["R&A", "everyone", "Adults"] + ["Z"] * 20}]}]}] * 30,
        "set_aside": [{"title": "x", "reason": "y", "day": 99}] * 100, "lists": [{"name": "l", "items": [{"title": f"i{n}"} for n in range(500)]}] * 20, "merged_repeats": "lots"}
    c = canvas.clean(junk)
    assert len(c["days"]) == canvas.MAX_DAYS and len(c["days"][0]["place"]) <= cal.MAX_TITLE
    step = c["days"][0]["parts"][0]["steps"][0]
    assert len(step["title"]) <= 80 and step["kind"] == "other" and step["time"] == "" and len(step["note"]) <= 200
    assert step["who_raw"][:3] == ["R", "A", "g:Adults"] and len(step["who_raw"]) <= canvas.MAX_WHO
    assert len(c["set_aside"]) == canvas.MAX_ASIDE and all(a["day"] == 0 for a in c["set_aside"])
    assert len(c["lists"]) == canvas.MAX_LISTS and len(c["lists"][0]["items"]) == canvas.MAX_ITEMS
    assert c["merged_repeats"] >= 0 and len(c["initials"]) <= canvas.MAX_INITIALS


def test_clean_survives_anything_that_is_not_a_draft():
    for odd in (None, [], "text", 7, {"days": "no"}, {"days": [None, 3, "x"]}):
        assert canvas.clean(odd)["days"] == []


def test_a_ride_sent_twice_in_one_day_is_one_step_and_counted():
    s = {"title": "King Kong", "kind": "ride", "who_raw": []}
    c = canvas.clean({"days": [{"label": "U", "park_or_place": "U", "parts": [{"name": "A", "steps": [s]}, {"name": "B", "steps": [dict(s, title="king kong")]}]}], "merged_repeats": 1})
    assert canvas.summary(c)["steps"] == 1 and c["merged_repeats"] == 2


# ---- who is who ----------------------------------------------------------------------------------------------------------

def test_suggestions_exact_name_wins_a_single_letter_needs_one_match_otherwise_nothing():
    text = samples.text()
    assert canvas.suggest("Hrishi", PEOPLE, text)["member"] == "u-hr"
    assert canvas.suggest("hrishi rivera", PEOPLE, text)["member"] == "u-hr"
    h = canvas.suggest("H", PEOPLE, text)
    assert h["member"] == "u-hr" and h["why"] == 'you wrote "Hrishi"'
    b = canvas.suggest("B", PEOPLE, "no names here")
    assert b["member"] == "u-bh" and b["why"] == "the only B in the family"
    two_a = PEOPLE + [{"user_id": "u-ann", "name": "Ann Rao"}]
    assert canvas.suggest("A", two_a)["member"] is None      # two A's: Convert never guesses
    assert canvas.suggest("R", PEOPLE)["member"] is None      # nobody starts with R
    assert canvas.suggest("Zed", PEOPLE)["member"] is None and canvas.suggest("HB", PEOPLE)["member"] is None


def test_questions_skip_names_that_already_match_a_member():
    draft = canvas.clean(samples.model_answer())
    q = canvas.questions(draft, PEOPLE, samples.text())
    assert [x["token"] for x in q["who"]] == ["H", "B", "R", "A"] and q["named"] == {"Hrishi": "u-hr"}
    assert {x["token"]: x["member"] for x in q["who"]} == {"H": "u-hr", "B": "u-bh", "R": None, "A": "u-abhi"}


# ---- nothing is saved until Add to trip, and then it is saved whole ------------------------------------------------------

def draft_and_answers(ari, **over):
    draft = canvas.clean(samples.model_answer())
    others = [p for p in canvas.family_people(ari)]
    me = others[0]["user_id"]
    answers = {"who": {"H": f"m:{me}", "B": "n:Bhoomija", "R": "i:R", "A": f"m:{me}"}, "days": [1, 3], "list_for": [f"m:{me}"], **over}
    return draft, answers


def test_converting_saves_nothing(ari, azure):
    canvas.convert(ari, samples.text())
    assert cal.activities(ari) == []
    for table in ("block_parts", "block_steps", "trip_lists", "trip_list_items"):
        assert rows(ari, f"SELECT * FROM {table}") == []
    assert rows(ari, "SELECT * FROM thread") == []


def test_adding_writes_the_days_parts_steps_set_aside_lists_one_card_and_one_notify(ari, announced):
    draft, answers = draft_and_answers(ari)
    done = canvas.save(ari, draft, answers)
    assert done["steps"] == 23 and done["lists"] == 1 and [(t, d) for _, t, d in done["acts"]] == [("Universal Studios Hollywood", 1), ("Disney California Adventure", 3)]
    acts = cal.activities(ari)
    assert [(a.title, a.day, a.start, a.end) for a in acts] == [("Universal Studios Hollywood", 1, 540, 1260), ("Disney California Adventure", 3, 540, 1260)]
    uni = acts[0].id
    parts = rows(ari, "SELECT * FROM block_parts WHERE act_id = :a ORDER BY position", a=uni)
    assert [p["name"] for p in parts] == ["Lower Lot", "Lunch", "Harry Potter world", "Upper Lot"] and parts[0]["time_of_day"] == "Morning"
    steps = rows(ari, "SELECT * FROM block_steps WHERE act_id = :a AND aside = 0 ORDER BY part_id, position", a=uni)
    assert len(steps) == 14
    aside = rows(ari, "SELECT * FROM block_steps WHERE act_id = :a AND aside = 1 ORDER BY position", a=uni)
    assert [s["title"] for s in aside] == ["Studio Tour", "Simpsons"] and aside[0]["part_id"] == "" and aside[0]["note"]
    mummy = next(s for s in steps if s["title"] == "Revenge of the Mummy")
    assert (mummy["done"], mummy["aside"], json.loads(mummy["who"])) == (0, 0, [])
    walk = next(s for s in steps if s["title"] == "Hippogriff")
    me = canvas.family_people(ari)[0]["user_id"]
    assert json.loads(walk["who"]) == [f"m:{me}", "n:Bhoomija"] and walk["note"] == "H and B walk"
    hr = next(s for s in rows(ari, "SELECT * FROM block_steps WHERE title = 'Incredicoaster'"))
    assert json.loads(hr["who"]) == ["i:R", f"m:{me}"]
    [lst] = rows(ari, "SELECT * FROM trip_lists")
    assert lst["name"] == "Pregnancy-safe rides" and lst["for_who"] == f"m:{me}"
    assert len(rows(ari, "SELECT * FROM trip_list_items WHERE list_id = :l", l=lst["id"])) == 8
    cards = rows(ari, "SELECT * FROM thread")
    assert len(cards) == 1 and cards[0]["kind"] == "change"
    assert "Universal Studios Hollywood on Sat" in cards[0]["text"] and "Disney California Adventure on Mon" in cards[0]["text"] and "23 steps" in cards[0]["text"]
    assert len(announced) == 1 and announced[0][0] == "Plan changed"


def test_a_refused_save_changes_nothing(ari, announced):
    draft, answers = draft_and_answers(ari, days=[1, 1])
    with pytest.raises(canvas.CanvasError) as e:
        canvas.save(ari, draft, answers)
    assert "different day" in str(e.value)
    draft, answers = draft_and_answers(ari, days=[1, 40])
    with pytest.raises(canvas.CanvasError):
        canvas.save(ari, draft, answers)       # the second park fails after the first was written: all of it rolls back
    assert cal.activities(ari) == [] and rows(ari, "SELECT * FROM block_steps") == [] and rows(ari, "SELECT * FROM thread") == [] and announced == []


def test_a_stranger_cannot_be_named_as_a_family_member(ari):
    draft, answers = draft_and_answers(ari, who={"H": "m:not-in-this-family"})
    with pytest.raises(canvas.CanvasError) as e:
        canvas.save(ari, draft, answers)
    assert "people in your family" in str(e.value) and cal.activities(ari) == []


def test_the_same_park_cannot_be_added_twice_on_the_same_day(ari):
    draft, answers = draft_and_answers(ari)
    canvas.save(ari, draft, answers)
    with pytest.raises(canvas.CanvasError) as e:
        canvas.save(ari, draft, answers)
    assert "already planned" in str(e.value) and len(cal.activities(ari)) == 2


def test_a_park_day_over_the_arriving_flight_is_saved(ari):
    draft, answers = draft_and_answers(ari, days=[0, 3])     # the first day starts with the flight in (F-086: overlaps are fine)
    canvas.save(ari, draft, answers)
    assert len(cal.activities(ari)) == 2


# ---- reading a block and ticking steps ------------------------------------------------------------------------------------

def test_a_block_lists_its_parts_steps_notes_and_set_aside_and_steps_can_be_ticked(ari):
    draft, answers = draft_and_answers(ari)
    canvas.save(ari, draft, answers)
    uni = cal.activities(ari)[0].id
    assert canvas.block_ids(ari) == {a.id for a in cal.activities(ari)}
    view = canvas.block(ari, uni)
    assert [p["name"] for p in view["parts"]] == ["Lower Lot", "Lunch", "Harry Potter world", "Upper Lot"]
    walk = next(s for p in view["parts"] for s in p["steps"] if s["title"] == "Hippogriff")
    assert walk["who"] == [canvas.family_people(ari)[0]["name"].split()[0], "Bhoomija"] and walk["note"] == "H and B walk" and not walk["done"]
    assert [s["title"] for s in view["aside"]] == ["Studio Tour", "Simpsons"]
    assert view["lists"][0]["name"] == "Pregnancy-safe rides" and len(view["lists"][0]["items"]) == 8
    assert canvas.set_done(ari, walk["id"]) == uni
    assert next(s for p in canvas.block(ari, uni)["parts"] for s in p["steps"] if s["id"] == walk["id"])["done"] is True
    canvas.set_done(ari, walk["id"], False)
    canvas.set_aside(ari, walk["id"])
    again = canvas.block(ari, uni)
    assert walk["id"] in [s["id"] for s in again["aside"]] and walk["id"] not in [s["id"] for p in again["parts"] for s in p["steps"]]
    canvas.set_aside(ari, walk["id"], False)
    assert walk["id"] in [s["id"] for p in canvas.block(ari, uni)["parts"] for s in p["steps"]]
    with pytest.raises(canvas.CanvasError):
        canvas.set_done(ari, "nope")


def test_a_block_without_parts_or_a_deleted_one_has_no_detail(ari):
    assert canvas.block(ari, "a1") is None and canvas.block_ids(ari) == set()
    draft, answers = draft_and_answers(ari)
    canvas.save(ari, draft, answers)
    uni = cal.activities(ari)[0].id
    cal.delete_activity(ari, uni)
    assert canvas.block(ari, uni) is None


def test_purging_a_deleted_block_takes_its_parts_steps_with_it_in_the_same_transaction(ari):
    draft, answers = draft_and_answers(ari)
    canvas.save(ari, draft, answers)
    first, second = [a.id for a in cal.activities(ari)]
    cal.delete_activity(ari, first)                    # undo is still possible: the steps are kept
    assert rows(ari, "SELECT COUNT(*) AS n FROM block_steps WHERE act_id = :a", a=first)[0]["n"] > 0
    cal.delete_activity(ari, second)                   # the earlier deletion is now permanent
    assert rows(ari, "SELECT COUNT(*) AS n FROM block_steps WHERE act_id = :a", a=first)[0]["n"] == 0
    assert rows(ari, "SELECT COUNT(*) AS n FROM block_parts WHERE act_id = :a", a=first)[0]["n"] == 0
    assert rows(ari, "SELECT COUNT(*) AS n FROM block_steps WHERE act_id = :a", a=second)[0]["n"] > 0
