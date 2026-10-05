"""F-087: the one Ask box, the model side (gitaway/say.py) and the routes. A fake transport plays the model (tests/canvas_samples.py FakeAzure): nothing here reaches Azure.

Acceptance: any length up to the paste limit; from a day everything goes on that day, without one it is spread across the trip's days; quick follow-ups only
when needed (which day, what time, who an initial is) with a suggested answer; times written in the text are used as given; one preview day by day; one Apply
saves it and tells the family once; a model failure keeps the text; the captain's real messages still become park days, parts and steps."""

import json
import re
from html import unescape

import pytest

from gitaway import ai, canvas, familythread, say, speak, tripcal as cal
from tests import canvas_samples as samples
from tests.test_calendar import book
from tests.test_signin import person
from tests.test_speak import announced, answer, op, plans

SAT, MON = 1, 3


@pytest.fixture
def azure(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    fake = samples.FakeAzure()
    monkeypatch.setattr(ai, "TRANSPORT", fake)
    return fake


def asked(step):
    return {q["id"]: q for q in step["questions"]}


def form(step, **over):
    """What a person posts from the questions page: every suggested answer, unless `over` says otherwise."""
    out = {f"a_{q['id']}": q["suggest"] for q in step["questions"]}
    out.update({f"a_{k}": v for k, v in over.items()})
    return out


# ---- the route: short is a change, long is a plan ----------------------------------------------------------------------------

def test_a_short_request_is_a_change_and_a_long_paste_is_a_plan():
    assert say.route("Move lunch to 12:30") == "change"
    assert say.route("x" * speak.MAX_REQUEST) == "change"
    assert say.route("x" * (speak.MAX_REQUEST + 1)) == "plan"
    assert say.route(samples.text()) == "plan"
    assert say.LIMIT == canvas.MAX_TEXT == 20000


def test_nothing_and_too_much_are_refused_with_the_text_kept(client, azure):
    book(client)
    s = person("ari")
    with pytest.raises(say.SayError, match="Say, type or paste"):
        say.start(s, "   ", SAT)
    with pytest.raises(say.SayError, match="20,000"):
        say.start(s, "x" * (say.LIMIT + 1), SAT)
    assert azure.sent == []


# ---- a plan from a paste: the captain's real messages --------------------------------------------------------------------------

def test_from_a_day_everything_goes_on_that_day_with_no_day_question(client, azure, announced):
    book(client)
    s = person("ari")
    step = say.start(s, samples.text(), SAT)
    assert "park:0" not in asked(step) and not any(k.startswith("park") for k in asked(step))
    assert "Trip days:" in azure.sent[0]["messages"][1]["content"]
    assert [k for k in asked(step)] == ["who:Hrishi", "who:H", "who:B", "who:R", "who:A"]       # this family is just Ari: nobody else is known
    step = say.answer(s, step["state"], form(step))
    assert step["questions"] == [] and [g["day"] for g in step["preview"]["groups"]] == [SAT]
    group = step["preview"]["groups"][0]
    assert len(group["chips"]) == 1 and group["chips"][0]["kind"] == "new" and "Universal Studios Hollywood" in group["chips"][0]["label"]
    assert cal.activities(s) == [] and announced == []                      # a preview saves nothing
    done = say.apply(s, step["state"], step["preview"].get("token", ""), None)
    assert done["days"] == [SAT] and done["steps"] > 20
    assert [(a.title, a.day) for a in cal.activities(s)] == [("Universal Studios Hollywood", SAT)]
    assert len(announced) == 1                                              # the family is told once


def test_without_a_day_the_text_is_spread_across_the_trip_with_a_suggested_day_for_each_park(client, azure, announced):
    book(client)
    s = person("ari")
    step = say.start(s, samples.text(), None)
    qs = asked(step)
    assert qs["park:0"]["text"].startswith("Which day") and "Universal Studios Hollywood" in qs["park:0"]["text"]
    assert len(qs["park:0"]["options"]) == 5 and qs["park:0"]["suggest"] != qs["park:1"]["suggest"]
    step = say.answer(s, step["state"], form(step, **{"park:0": str(SAT), "park:1": str(MON)}))
    assert step["questions"] == [] and [g["day"] for g in step["preview"]["groups"]] == [SAT, MON]
    assert [c["label"] for g in step["preview"]["groups"] for c in g["chips"]] == ["Universal Studios Hollywood", "Disney California Adventure"]
    say.apply(s, step["state"], "", None)
    assert [(a.title, a.day) for a in cal.activities(s)] == [("Universal Studios Hollywood", SAT), ("Disney California Adventure", MON)]
    assert len(announced) == 1
    block = canvas.block(s, "a1")
    assert [p["name"] for p in block["parts"]][:2] == ["Lower Lot", "Lunch"]


def test_two_parks_on_one_day_ask_again(client, azure):
    book(client)
    s = person("ari")
    step = say.start(s, samples.text(), None)
    with pytest.raises(say.SayError, match="different day") as err:
        say.answer(s, step["state"], form(step, **{"park:0": "1", "park:1": "1"}))
    assert err.value.step["questions"]       # the questions come back with the choices kept


def test_a_date_the_model_read_is_the_suggested_day(client, azure):
    book(client)
    s = person("ari")
    reply = samples.model_answer()
    reply["days"][0]["date"] = "2026-10-20"       # the trip's fifth day
    azure.answer = reply
    step = say.start(s, samples.text(), None)
    assert asked(step)["park:0"]["suggest"] == "4"


def test_times_written_in_the_text_are_used_as_given(client, azure):
    book(client)
    s = person("ari")
    reply = samples.model_answer()
    reply["days"] = reply["days"][:1]
    reply["days"][0]["parts"][0]["steps"][0]["time"] = "10:30"
    reply["initials_found"] = []
    for p in reply["days"][0]["parts"]:
        for st in p["steps"]:
            st["who_raw"] = []
    azure.answer = reply
    step = say.start(s, samples.text(), SAT)
    assert step["questions"] == []
    assert "09:00" not in json.dumps(step["state"]["draft"]["days"][0]["parts"][0]["steps"][0]) and step["state"]["draft"]["days"][0]["parts"][0]["steps"][0]["time"] == "10:30"
    say.apply(s, step["state"], "", None)
    view = canvas.block(s, "a1")
    assert view["parts"][0]["steps"][0]["time"] == "10:30"


def test_pinned_to_a_day_several_parks_become_one_day_with_all_their_parts(client, azure):
    book(client)
    s = person("ari")
    step = say.start(s, samples.text(), MON)
    draft = step["state"]["draft"]
    assert len(draft["days"]) == 1 and draft["days"][0]["place"] == "Universal Studios Hollywood"
    names = [p["name"] for p in draft["days"][0]["parts"]]
    assert "Pixar Pier" in names and "Lower Lot" in names and len(names) == 10
    assert step["state"]["days"] == [MON]


def test_who_answers_reach_the_steps(client, azure):
    book(client)
    s = person("ari")
    step = say.start(s, samples.text(), SAT)
    q = asked(step)["who:A"]
    assert q["text"] == "Who is A?" and q["suggest"].startswith("m:") and {o["value"] for o in q["options"]} >= {q["suggest"], "i:A"}
    out = say.answer(s, step["state"], form(step, **{"who:B": "n:Bhoomija", "who:R": "i:R"}))
    say.apply(s, out["state"], "", None)
    assert "Bhoomija" in json.dumps(canvas.block(s, "a1")["parts"])


def test_a_lost_state_is_refused_and_nothing_is_saved(client, azure):
    book(client)
    s = person("ari")
    with pytest.raises(say.SayError, match="lost"):
        say.answer(s, {"kind": "plan", "draft": {"days": []}}, {})
    with pytest.raises(say.SayError, match="lost"):
        say.apply(s, {"kind": "plan", "draft": "nope"}, "", None)
    assert cal.activities(s) == []


# ---- a change: which day, what time, who ---------------------------------------------------------------------------------------

def test_a_change_without_a_day_asks_which_day_before_it_asks_the_model(client, azure):
    book(client)
    s = person("ari")
    step = say.start(s, "Move lunch to 12:30", None)
    q = asked(step)["day"]
    assert q["text"] == "Which day?" and len(q["options"]) == 5 and q["suggest"] == "0" and azure.sent == []
    azure.answer = answer(op("add_plan", title="Lunch", start="12:30", end="13:30"))
    out = say.answer(s, step["state"], {"a_day": "1"}, text="Move lunch to 12:30")
    assert out["questions"] == [] and out["preview"]["groups"][0]["day"] == 1 and len(azure.sent) == 1
    assert out["preview"]["kind"] == "change" and out["preview"]["groups"][0]["chips"][0]["kind"] == "new"


def test_a_plan_with_no_time_asks_what_time_with_a_suggestion_and_keeps_the_rest(client, azure, announced):
    book(client)
    s = person("ari")
    lunch = cal.add_activity(s, day=SAT, start="12:00", end="13:00", title="Lunch", kind="food")
    azure.answer = answer(op("add_plan", title="Pool time"), op("move_plan", id=lunch.id, start="12:30", end="13:30"))
    step = say.start(s, "Pool time, and lunch at 12:30", SAT)
    qs = asked(step)
    assert list(qs) == ["time:0"] and qs["time:0"]["text"] == "What time is Pool time?"
    assert qs["time:0"]["suggest"] == "09:00" and [o["value"] for o in qs["time:0"]["options"]] == ["09:00", "12:00", "15:00", "18:00"]
    assert plans(s) == [("Lunch", "12:00", "13:00")]
    before = len(announced)
    out = say.answer(s, step["state"], form(step, **{"time:0": "15:00"}))
    assert out["questions"] == []
    chips = out["preview"]["groups"][0]["chips"]
    assert [(c["kind"], c["label"]) for c in chips] == [("new", "Pool time"), ("moved", "Lunch")]
    assert "3:00" in chips[0]["after"] and "12:30" in chips[1]["after"]      # the given time is kept as written
    say.apply(s, out["state"], out["preview"]["token"], None)
    assert ("Pool time", "15:00", "16:00") in plans(s) and ("Lunch", "12:30", "13:30") in plans(s) and len(announced) == before + 1


def test_an_unknown_initial_on_a_step_asks_who_it_is(client, azure):
    book(client)
    s = person("ari")
    draft = {"days": [{"label": "d", "place": "Disneyland", "parts": [{"name": "Morning", "time_of_day": "", "steps": [{"title": "Space Mountain", "time": "", "who_raw": [], "note": "", "kind": "ride"}]}]}], "set_aside": [], "lists": [], "initials": []}
    done = canvas.save(s, draft, {"who": {}, "days": [SAT]})
    block = done["acts"][0][0]
    view = canvas.block(s, block)
    azure.answer = answer(op("add_step", block_id=block, title="Matterhorn", time="10:30", who=["Q"]))
    step = say.start(s, "Add the Matterhorn at 10:30 for Q", SAT)
    q = asked(step)["who:0:0"]
    assert q["text"] == "Who is Q?" and q["suggest"] == "" and {o["value"] for o in q["options"]} >= {"", "Ari"}
    out = say.answer(s, step["state"], form(step, **{"who:0:0": "Ari"}))
    chip = out["preview"]["groups"][0]["chips"][0]
    assert chip["label"] == "Matterhorn" and "Ari" in chip["after"] and "10:30" in chip["after"]


def test_a_change_the_model_cannot_use_is_refused_with_the_text_kept(client, azure):
    book(client)
    s = person("ari")
    azure.answer = answer(op("remove_plan", id="zzz"))
    with pytest.raises(speak.SpeakError, match="could not turn that"):
        say.start(s, "Delete the moon", SAT)


def test_a_model_failure_is_raised_for_the_page_to_show(client):
    book(client)
    with pytest.raises(ai.AIError):
        say.start(person("ari"), samples.text(), SAT)
    with pytest.raises(ai.AIError):
        say.start(person("ari"), "Move lunch", SAT)


# ---- the routes ----------------------------------------------------------------------------------------------------------------

def fields(html, form_id):
    body = re.search(rf'<form[^>]*\bid="{form_id}"[^>]*>(.*?)</form>', html, re.S).group(1)
    out = {}
    for tag in re.findall(r"""<input(?:[^>"']|"[^"]*"|'[^']*')*>""", body):
        attrs = {k: unescape(a or b) for k, a, b in re.findall(r"""([\w-]+)=(?:"([^"]*)"|'([^']*)')""", tag)}
        if attrs.get("type") in ("radio", "checkbox") and "checked" not in tag:
            continue
        if attrs.get("name"):
            out[attrs["name"]] = attrs.get("value", "")
    for name, text in re.findall(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', body, re.S):
        out[name] = unescape(text)
    return out


def test_the_box_has_paste_talk_and_type_and_the_day_picker_opens_on_the_day(client):
    book(client)
    html = client.get(f"/trip/ask?day={SAT}").text
    for needle in ('id="ak-text"', 'id="ak-paste"', 'id="ak-mic"', 'id="ak-count"', 'id="ak-progress"', "Paste", 'data-limit="20000"'):
        assert needle in html, needle
    assert re.search(r'<option value="1" selected', html) and html.count("<option") == 6      # the five days and "Let GitAway place it"
    assert 'maxlength' not in re.search(r'<textarea[^>]*>', html).group(0)                     # a long paste is never cut off silently
    bare = client.get("/trip/ask").text
    assert re.search(r'<option value="" selected', bare)
    assert 'data-mode="paste"' in client.get("/trip/ask?mode=paste").text and 'data-mode="talk"' in client.get("/trip/ask?mode=talk").text
    assert 'data-mode=' not in client.get("/trip/ask?mode=bogus").text


def test_the_old_add_to_the_trip_link_lands_in_the_box(client):
    book(client)
    r = client.get("/trip/add", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/ask?mode=paste"
    assert 'href="/trip/ask?mode=paste"' in client.get("/trip").text


def test_a_pasted_itinerary_goes_through_questions_a_preview_and_one_apply(client, azure, announced):
    book(client)
    r = client.post("/trip/ask/propose", data={"day": "", "text": samples.text()})
    assert r.status_code == 200 and 'id="ak-questions"' in r.text and "Which day is Universal Studios Hollywood?" in r.text
    posted = fields(r.text, "ak-questions-form")
    assert posted["text"] == samples.text() and posted["a_park:0"] != posted["a_park:1"]      # the suggestions are already chosen
    posted.update({"a_park:0": "1", "a_park:1": "3"})
    r = client.post("/trip/ask/answer", data=posted)
    assert r.status_code == 200 and 'id="ak-prop"' in r.text and 'id="ak-apply"' in r.text
    assert r.text.count('class="ak-dayh"') == 2 and "Saturday, Oct 17" in r.text and "Monday, Oct 19" in r.text
    assert cal.activities(person("ari")) == [] and announced == []
    apply = fields(r.text, "ak-apply-form")
    r = client.post("/trip/ask/apply", data=apply, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/trip/ask?day=1&done=2&kind=plan")
    done = client.get(r.headers["location"]).text
    assert 'id="ak-done"' in done and "The family has been told" in done and 'href="/trip/canvas?day=1"' in done
    assert len(announced) == 1 and [(a.title, a.day) for a in cal.activities(person("ari"))] == [("Universal Studios Hollywood", 1), ("Disney California Adventure", 3)]


def test_from_a_day_the_paste_goes_straight_to_the_preview_after_the_initials(client, azure):
    book(client)
    r = client.post("/trip/ask/propose", data={"day": str(SAT), "text": samples.text()})
    assert "Which day is" not in r.text and "Who is H?" in r.text and 'id="ak-questions-form"' in r.text
    r = client.post("/trip/ask/answer", data=fields(r.text, "ak-questions-form"))
    assert 'id="ak-prop"' in r.text and r.text.count('class="ak-dayh"') == 1


def test_a_model_failure_keeps_the_text_and_says_so(client):
    book(client)
    r = client.post("/trip/ask/propose", data={"day": str(SAT), "text": samples.text()})
    assert r.status_code == 503 and 'role="alert"' in r.text and fields(r.text, "ak-form")["text"] == samples.text()


def test_too_much_text_keeps_the_text_and_says_how_much(client, azure):
    book(client)
    text = "a" * (say.LIMIT + 5)
    r = client.post("/trip/ask/propose", data={"day": str(SAT), "text": text})
    assert r.status_code == 422 and "20,000" in r.text and azure.sent == [] and len(fields(r.text, "ak-form")["text"]) == say.LIMIT + 1


def test_an_empty_box_asks_for_something(client, azure):
    book(client)
    r = client.post("/trip/ask/propose", data={"day": str(SAT), "text": "  "})
    assert r.status_code == 422 and "Say, type or paste" in r.text


def test_a_lost_plan_goes_back_to_the_box_with_the_text(client, azure):
    book(client)
    r = client.post("/trip/ask/answer", data={"state": "not json", "text": "my words", "day": ""})
    assert r.status_code == 409 and "lost" in r.text and fields(r.text, "ak-form")["text"] == "my words"
    r = client.post("/trip/ask/apply", data={"plan": "not json", "text": "my words", "day": ""})
    assert r.status_code == 409 and "lost" in r.text


def test_change_it_on_a_preview_goes_back_to_the_box_with_the_text(client, azure):
    book(client)
    r = client.post("/trip/ask/propose", data={"day": str(SAT), "text": samples.text()})
    r = client.post("/trip/ask/answer", data=fields(r.text, "ak-questions-form"))
    back = client.post("/trip/ask/edit", data=fields(r.text, "ak-change-form"))
    assert fields(back.text, "ak-form")["text"] == samples.text()


def test_the_same_park_twice_on_a_day_keeps_the_text_and_says_why(client, azure):
    book(client)
    r = client.post("/trip/ask/propose", data={"day": str(SAT), "text": samples.text()})
    posted = fields(client.post("/trip/ask/answer", data=fields(r.text, "ak-questions-form")).text, "ak-apply-form")
    assert client.post("/trip/ask/apply", data=posted, follow_redirects=False).status_code == 303
    again = client.post("/trip/ask/apply", data=posted, follow_redirects=False)
    assert again.status_code == 409 and "already planned" in again.text and fields(again.text, "ak-form")["text"] == samples.text()


# ---- F-087 review fixes -------------------------------------------------------------------------------------------------------

from tests.test_speak import clock


def _selected_day(html):
    m = re.search(r'<option[^>]*value="(\d*)"[^>]*selected', html) or re.search(r'<option[^>]*selected[^>]*value="(\d*)"', html)
    return m.group(1) if m else None


def test_a_short_change_with_no_day_is_asked_the_day_then_applies(client, azure, announced):
    book(client)
    r = client.post("/trip/ask/propose", data={"day": "", "text": "Add a swim at 4pm"})
    posted = fields(r.text, "ak-questions-form")
    posted["a_day"] = "1"
    azure.answer = answer(op("add_plan", title="Swim", start="16:00", end="17:00"))
    r = client.post("/trip/ask/answer", data=posted)
    apply = fields(r.text, "ak-apply-form")
    assert apply["day"] == "1"
    r = client.post("/trip/ask/apply", data=apply, follow_redirects=False)
    assert r.status_code == 303 and "day=1&done=1" in r.headers["location"]
    assert [(a.title, a.day) for a in cal.activities(person("ari"))] == [("Swim", 1)] and len(announced) == 1


def test_during_the_trip_a_short_change_with_no_day_goes_to_today_without_asking(client, azure, announced, monkeypatch):
    book(client)
    clock(monkeypatch, 2026, 10, 17, 9)
    azure.answer = answer(op("add_plan", title="Swim", start="16:00", end="17:00"))
    r = client.post("/trip/ask/propose", data={"day": "", "text": "Add a swim at 4pm"})
    assert 'id="ak-questions"' not in r.text and 'id="ak-prop"' in r.text and "Saturday, Oct 17" in r.text
    r = client.post("/trip/ask/apply", data=fields(r.text, "ak-apply-form"), follow_redirects=False)
    assert r.status_code == 303 and [(a.title, a.day) for a in cal.activities(person("ari"))] == [("Swim", 1)] and len(announced) == 1


def test_during_the_trip_a_long_paste_with_no_day_still_lets_gitaway_place_it(client, azure, monkeypatch):
    book(client)
    clock(monkeypatch, 2026, 10, 17, 9)
    r = client.post("/trip/ask/propose", data={"day": "", "text": samples.text()})
    assert "Which day is Universal Studios Hollywood?" in r.text


def test_the_day_picker_opens_on_today_during_the_trip_unless_the_text_is_a_long_paste(client, azure, monkeypatch):
    book(client)
    assert _selected_day(client.get("/trip/ask").text) == ""            # before the trip: let GitAway place it
    clock(monkeypatch, 2026, 10, 18, 9)
    assert _selected_day(client.get("/trip/ask").text) == "2"
    back = client.post("/trip/ask/edit", data={"day": "", "text": samples.text()})
    assert _selected_day(back.text) == ""


def test_a_plans_apply_checks_the_trip_and_says_so_plainly(client, azure):
    book(client)
    s = person("ari")
    step = say.start(s, samples.text(), SAT)
    step = say.answer(s, step["state"], form(step))
    with pytest.raises(say.SayError, match="trip changed"):
        say.apply(s, step["state"], "", "some-other-trip")
    assert cal.activities(s) == []
    r = client.post("/trip/ask/propose", data={"day": str(SAT), "text": samples.text()})
    r = client.post("/trip/ask/answer", data=fields(r.text, "ak-questions-form"))
    posted = fields(r.text, "ak-apply-form")
    posted["trip"] = "some-other-trip"
    r = client.post("/trip/ask/apply", data=posted, follow_redirects=False)
    assert cal.activities(s) == []      # a tab drawn for a trip this family does not have reaches no trip at all (the same as a change)


def _more(reply):
    """The sample plan with one more step in Lower Lot, a new Evening part, and a repeat of a ride already there."""
    reply["days"][0]["parts"][0]["steps"].append(samples.S("Despicable Me Minion Mayhem"))
    reply["days"][0]["parts"][0]["steps"].append(samples.S("Revenge of the Mummy"))
    reply["days"][0]["parts"].append(samples.P("Evening", [samples.S("Fireworks", kind="show")], "Evening"))
    return reply


def _plan_onto_sat(client):
    r = client.post("/trip/ask/propose", data={"day": str(SAT), "text": samples.text()})
    return client.post("/trip/ask/answer", data=fields(r.text, "ak-questions-form"))


def test_a_park_pasted_onto_a_day_that_has_it_merges_and_the_preview_says_what_is_added(client, azure, announced):
    book(client)
    s = person("ari")
    assert client.post("/trip/ask/apply", data=fields(_plan_onto_sat(client).text, "ak-apply-form"), follow_redirects=False).status_code == 303
    before = canvas.block(s, "a1")
    azure.answer = _more(samples.model_answer())
    r = _plan_onto_sat(client)
    assert 'id="ak-prop"' in r.text and 'data-kind="changed"' in r.text and "Evening" in r.text and "Adds 1 area" in r.text
    r = client.post("/trip/ask/apply", data=fields(r.text, "ak-apply-form"), follow_redirects=False)
    assert r.status_code == 303 and len(announced) == 2
    block = canvas.block(s, "a1")
    assert [a.title for a in cal.activities(s)] == ["Universal Studios Hollywood"]
    assert [p["name"] for p in block["parts"]][-1] == "Evening" and len(block["parts"]) == len(before["parts"]) + 1
    lower = [p for p in block["parts"] if p["name"] == "Lower Lot"][0]["steps"]
    assert [x["title"] for x in lower].count("Revenge of the Mummy") == 1 and "Despicable Me Minion Mayhem" in [x["title"] for x in lower]
    assert [x["title"] for p in block["parts"] for x in p["steps"]].count("Fireworks") == 1


def test_pasting_exactly_what_is_already_there_is_said_in_the_preview_and_refused_at_apply(client, azure):
    book(client)
    client.post("/trip/ask/apply", data=fields(_plan_onto_sat(client).text, "ak-apply-form"), follow_redirects=False)
    r = _plan_onto_sat(client)
    assert "Nothing new" in r.text
    again = client.post("/trip/ask/apply", data=fields(r.text, "ak-apply-form"), follow_redirects=False)
    assert again.status_code == 409 and "already planned" in again.text


def test_the_done_page_opens_on_the_earliest_day(client, azure):
    book(client)
    r = client.post("/trip/ask/propose", data={"day": "", "text": samples.text()})
    posted = fields(r.text, "ak-questions-form")
    posted.update({"a_park:0": "3", "a_park:1": "1"})
    r = client.post("/trip/ask/answer", data=posted)
    r = client.post("/trip/ask/apply", data=fields(r.text, "ak-apply-form"), follow_redirects=False)
    assert r.headers["location"].startswith("/trip/ask?day=1&done=2")


def test_parts_that_do_not_fit_on_one_day_are_named_in_the_preview(client, azure):
    book(client)
    s = person("ari")
    reply = samples.model_answer()
    reply["days"][1]["parts"] += [samples.P(f"Extra {i}", [samples.S(f"Ride {i}")]) for i in range(4)]
    azure.answer = reply
    step = say.start(s, samples.text(), MON)
    step = say.answer(s, step["state"], form(step)) if step["questions"] else step
    assert len(step["state"]["draft"]["days"][0]["parts"]) == canvas.MAX_PARTS
    assert any("Extra 3" in t and "did not fit" in t for t in step["preview"]["tidy"])


def test_a_plan_cannot_be_placed_on_a_day_that_has_passed_but_today_is_fine(client, azure, monkeypatch):
    book(client)
    s = person("ari")
    clock(monkeypatch, 2026, 10, 18, 9)
    with pytest.raises(say.SayError, match="already passed"):
        say.start(s, samples.text(), 0)
    assert azure.sent == []
    assert say.start(s, samples.text(), 2)["state"]["days"] == [2]
    step = say.start(s, samples.text(), None)
    with pytest.raises(say.SayError, match="already passed") as err:
        say.answer(s, step["state"], form(step, **{"park:0": "0", "park:1": "3"}))
    assert err.value.step["questions"]
    ok = say.answer(s, step["state"], form(step, **{"park:0": "2", "park:1": "3"}))
    doctored = dict(ok["state"], days=[0, 3])
    with pytest.raises(say.SayError, match="already passed"):
        say.apply(s, doctored, "", None)
    assert cal.activities(s) == []


def test_when_every_park_has_a_date_inside_the_trip_there_is_no_day_question(client, azure):
    book(client)
    s = person("ari")
    reply = samples.model_answer()
    reply["days"][0]["date"], reply["days"][1]["date"] = "2026-10-17", "2026-10-19"
    azure.answer = reply
    step = say.start(s, samples.text(), None)
    assert not [q for q in step["questions"] if q["id"].startswith("park:")]
    step = say.answer(s, step["state"], form(step)) if step["questions"] else step
    assert [g["day"] for g in step["preview"]["groups"]] == [SAT, MON]
    reply["days"][1]["date"] = "2027-01-01"       # outside the trip: ask
    azure.answer = reply
    assert "park:1" in asked(say.start(s, samples.text(), None))
