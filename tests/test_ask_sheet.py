"""F-104: Ask is a sheet over the day. The server side: the box, the follow-up questions, the preview and Apply as fragments for the sheet (X-Ask: 1), the tab marked for
editors only, /trip/ask unchanged as a page. A fake transport plays the model (nothing reaches Azure)."""

import json

import pytest

from gitaway import ai, speak, tripcal as cal
from tests import canvas_samples as samples
from tests.test_calendar import book
from tests.test_members import addr, browser, invite
from tests.test_say import fields
from tests.test_signin import person, sign_in
from tests.test_speak import answer, op

SHEET = {"X-Ask": "1"}


@pytest.fixture
def azure(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    fake = samples.FakeAzure(answer(op("add_plan", title="Pool", start="15:00", end="16:00")))
    monkeypatch.setattr(ai, "TRANSPORT", fake)
    return fake


def test_the_sheet_box_holds_only_the_chip_the_mic_the_note_paste_and_done(client):
    book(client)
    r = client.get("/trip/ask?day=1", headers=SHEET)
    assert r.status_code == 200 and "<html" not in r.text and 'id="ak-sheet-body"' in r.text
    assert 'id="ak-chip"' in r.text and "Sat Oct 17" in r.text                       # the day being looked at is already chosen, a chip changes it
    assert fields(r.text, "ak-form")["day"] == "1" and 'data-mode="talk"' in r.text      # listening starts on open where the browser allows
    assert 'id="ak-mic"' in r.text and 'id="ak-text"' in r.text and 'id="ak-paste"' in r.text
    assert ">Done<" in r.text
    for gone in ("Ask GitAway", "<select", ">Which day<", 'id="tp-title-h"', "Nothing changes until you tap Apply"):
        assert gone not in r.text, gone
    hint = r.text[r.text.index('id="ak-hint"') - 60: r.text.index('id="ak-hint"') + 40]
    assert "hidden" in hint                                                              # the keyboard-mic hint is hidden unless the phone can neither record nor recognise speech


def test_a_week_open_has_any_day_and_the_page_is_unchanged(client):
    book(client)
    assert 'id="ak-days-pick"' in client.get("/trip/ask", headers=SHEET).text and 'data-d=""' in client.get("/trip/ask", headers=SHEET).text      # "Any day": GitAway places it
    page = client.get("/trip/ask?day=1")
    assert '<select' in page.text and '>Which day<' in page.text and 'id="tp-title-h"' in page.text and "tap the microphone on the keyboard" in page.text
    assert 'id="ak-sheet-body"' not in page.text and 'data-ask="sheet"' not in page.text      # the page's own tab does not open a sheet over itself


def test_the_mic_knows_when_the_server_can_transcribe(client, monkeypatch):
    book(client)
    monkeypatch.setenv("SARVAM_API_KEY", "")
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "")
    assert 'data-server=""' in client.get("/trip/ask?day=1", headers=SHEET).text
    monkeypatch.setenv("SARVAM_API_KEY", "sk-test")
    assert 'data-server="1"' in client.get("/trip/ask?day=1", headers=SHEET).text
    assert 'data-server="1"' in client.get("/trip/ask?day=1").text          # the page records too, wherever the browser can


def test_the_centre_tab_opens_the_sheet_for_editors_only_and_not_on_the_ask_page(client):
    book(client)
    for path in ("/trip/canvas?day=1", "/trip/family", "/trip/canvas"):
        assert 'data-ask="sheet"' in client.get(path).text, path
    assert 'data-ask="sheet"' not in client.get("/trip/ask").text
    assert "/assets/js/ask_sheet.js" in client.get("/trip/family").text and "/assets/css/ask_sheet.css" in client.get("/trip/family").text
    assert "ask_sheet.js" not in client.get("/trip/ask").text


def test_a_viewer_sees_no_sheet_and_cannot_fetch_one(client):
    book(client)
    mail = addr("sheetvw")
    invite(client, mail, "viewer")
    vi = browser(client)
    sign_in(vi, mail)
    page = vi.get("/trip/family")
    assert 'id="ph-tab-ask"' in page.text and 'data-ask="sheet"' not in page.text and "ask_sheet" not in page.text
    assert vi.get("/trip/ask?day=1", headers=SHEET).status_code == 403
    assert "only editors" in vi.get("/trip/ask?day=1").text.lower()      # the page still shows the viewer card


def test_done_shows_the_proposal_in_the_sheet_and_apply_answers_with_what_to_light_up(client, azure):
    book(client)
    r = client.post("/trip/ask/propose", data={"day": "1", "text": "add pool at 3"}, headers=SHEET)
    assert r.status_code == 200 and 'id="ak-sheet-body"' in r.text and "<html" not in r.text and 'id="ak-prop"' in r.text
    assert 'data-kind="new"' in r.text and "Pool" in r.text and 'id="ak-apply"' in r.text and 'id="ak-change"' in r.text
    assert 'id="ak-cancel"' not in r.text and "Nothing changes until" not in r.text
    assert cal.activities(person("ari")) == []
    r = client.post("/trip/ask/apply", data=fields(r.text, "ak-apply-form"), headers=SHEET)
    j = r.json()
    assert r.status_code == 200 and j["ok"] and j["day"] == 1 and len(j["ids"]) == 1 and j["toast"] == "Added 1 plan · The family has been told"
    assert [a.id for a in cal.activities(person("ari"))] == j["ids"]            # the new block's id, so the page can glow it


def test_change_it_goes_back_to_the_box_in_the_sheet_with_the_words_and_without_starting_the_mic(client, azure):
    book(client)
    r = client.post("/trip/ask/propose", data={"day": "1", "text": "add pool at 3"}, headers=SHEET)
    back = client.post("/trip/ask/edit", data=fields(r.text, "ak-change-form"), headers=SHEET)
    assert 'id="ak-sheet-body"' in back.text and fields(back.text, "ak-form")["text"] == "add pool at 3" and 'data-mode' not in back.text


def test_a_question_is_one_tap_in_the_sheet(client, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    monkeypatch.setattr(ai, "TRANSPORT", samples.FakeAzure(answer(op("add_plan", title="Pool"))))      # no time: GitAway asks
    book(client)
    r = client.post("/trip/ask/propose", data={"day": "1", "text": "add pool"}, headers=SHEET)
    assert 'id="ak-questions-form"' in r.text and 'data-tap="1"' in r.text and "What time is Pool?" in r.text and "Change the words" in r.text
    page = client.post("/trip/ask/propose", data={"day": "1", "text": "add pool"})
    assert 'data-tap' not in page.text and 'id="ak-sheet-body"' not in page.text           # the page keeps its Continue button
    r2 = client.post("/trip/ask/answer", data=fields(r.text, "ak-questions-form"), headers=SHEET)
    assert 'id="ak-prop"' in r2.text and "<html" not in r2.text


def test_a_failure_keeps_the_text_in_the_sheet(client, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    monkeypatch.setattr(ai, "TRANSPORT", samples.FakeAzure(failure=TimeoutError("slow")))
    book(client)
    r = client.post("/trip/ask/propose", data={"day": "1", "text": "add pool at 3"}, headers=SHEET)
    assert r.status_code == 503 and 'id="ak-error"' in r.text and fields(r.text, "ak-form")["text"] == "add pool at 3" and 'id="ak-sheet-body"' in r.text


def test_a_stale_proposal_fails_in_the_sheet_and_keeps_the_words(client, azure):
    book(client)
    r = client.post("/trip/ask/propose", data={"day": "1", "text": "add pool at 3"}, headers=SHEET)
    posted = fields(r.text, "ak-apply-form")
    client.post("/calendar/activities", data={"id": "a9", "day": "1", "start": "10:00", "end": "11:00", "title": "Breakfast", "kind": "food"})      # the day moved on
    again = client.post("/trip/ask/apply", data=posted, headers=SHEET)
    assert again.status_code == 409 and "changed while you were deciding" in again.text and fields(again.text, "ak-form")["text"] == "add pool at 3"
    assert len(cal.activities(person("ari"))) == 1


def test_the_toast_says_what_was_done():
    from gitaway.pages import tab_ask
    assert tab_ask._toast(["add_plan", "add_plan", "add_plan"], 3) == "Added 3 plans · The family has been told"
    assert tab_ask._toast(["add_plan", "move_plan", "remove_plan"], 3) == "Added 1 plan · Moved 1 · Removed 1 · The family has been told"
    assert tab_ask._toast(["add_step", "set_aside_step"], 2) == "Added 1 step · Changed 1 · The family has been told"
    assert tab_ask._toast([], 2, plan=True) == "Added 2 days · The family has been told"


def test_apply_reports_the_plans_it_moved_and_added(client, azure):
    book(client)
    client.post("/calendar/activities", data={"id": "a1", "day": "1", "start": "12:00", "end": "13:00", "title": "Lunch", "kind": "food"})
    azure.answer = answer(op("move_plan", id="a1", start="12:30", end="13:30"), op("add_plan", title="Pool", start="15:00", end="16:00"))
    r = client.post("/trip/ask/propose", data={"day": "1", "text": "move lunch, add pool"}, headers=SHEET)
    j = client.post("/trip/ask/apply", data=fields(r.text, "ak-apply-form"), headers=SHEET).json()
    assert "a1" in j["ids"] and len(j["ids"]) == 2 and j["toast"].startswith("Added 1 plan · Moved 1")


# ---- where the microphone path stops: one log line per step, nothing stored (F-104) ------------------------------------------------

def test_a_mic_event_is_one_log_line_with_no_audio_and_no_words(client, caplog):
    import logging
    from gitaway.pages import tab_ask
    book(client)
    tab_ask._mic_hits.clear()
    with caplog.at_level(logging.INFO, logger="gitaway.ask"):
        r = client.post("/trip/ask/mic-event", json={"stage": "gum", "name": "refused", "detail": "NotAllowedError", "text": "move Bhoomija's ride", "audio": "AAAA"})
    assert r.status_code == 204
    lines = [x.getMessage() for x in caplog.records if x.name == "gitaway.ask"]
    assert lines == ["ask mic stage=gum name=refused detail=NotAllowedError"]
    assert "Bhoomija" not in caplog.text and "AAAA" not in caplog.text


def test_a_mic_event_cannot_forge_a_log_line_or_carry_a_long_story(client, caplog):
    import logging
    from gitaway.pages import tab_ask
    book(client)
    tab_ask._mic_hits.clear()
    with caplog.at_level(logging.INFO, logger="gitaway.ask"):
        client.post("/trip/ask/mic-event", json={"stage": "mode", "name": "record\nask mic stage=fake", "detail": "x" * 500 + "<script>"})
    line = [x.getMessage() for x in caplog.records if x.name == "gitaway.ask"][0]
    assert "\n" not in line and len(line) < 200 and "<" not in line


def test_a_mic_event_needs_its_length_and_old_rate_entries_are_pruned(client):
    from gitaway.pages import tab_ask
    book(client)
    tab_ask._mic_hits.clear()
    sent = client.post("/trip/ask/mic-event", content=b'{"stage":"tap"}', headers={"content-type": "text/plain", "transfer-encoding": "chunked"})
    assert sent.status_code in (204, 411)
    assert tab_ask.mic_allowed("someone", now=0.0) and tab_ask.mic_allowed("other", now=1.0)
    assert tab_ask.mic_allowed("other", now=500.0)
    assert "someone" not in tab_ask._mic_hits or not tab_ask._mic_hits["someone"]        # the window passed: nobody keeps a list for ever
    assert len(tab_ask._mic_hits) <= 1


def test_a_mic_event_is_checked_gated_and_rate_limited(client):
    from gitaway.pages import tab_ask
    book(client)
    tab_ask._mic_hits.clear()
    assert client.post("/trip/ask/mic-event", json={"stage": "bogus"}).status_code == 400
    assert client.post("/trip/ask/mic-event", content=b"not json", headers={"content-type": "text/plain"}).status_code == 400
    assert client.post("/trip/ask/mic-event", json={"stage": "tap", "detail": "y" * 3000}).status_code == 413
    mail = addr("micvw")
    invite(client, mail, "viewer")
    vi = browser(client)
    sign_in(vi, mail)
    assert vi.post("/trip/ask/mic-event", json={"stage": "tap"}).status_code == 403            # editors only, like every Ask write
    assert browser(client).post("/trip/ask/mic-event", json={"stage": "tap"}).status_code != 204        # signed out
    tab_ask._mic_hits.clear()
    codes = [client.post("/trip/ask/mic-event", json={"stage": "tap", "name": "mic"}).status_code for _ in range(62)]
    assert codes[:60] == [204] * 60 and codes[60:] == [429, 429]
    assert cal.activities(person("ari")) == []                                                   # nothing is stored anywhere
