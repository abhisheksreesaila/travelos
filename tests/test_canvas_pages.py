"""F-080: the Add to the trip screens, through HTTP: paste, Convert (fake model), the two questions, Add to trip; every button pressed; viewers; and a block's
parts and steps. Nothing here reaches Azure."""

import html
import re

import pytest

from gitaway import ai, canvas, familythread
from tests import canvas_samples as samples
from tests.test_calendar import book
from tests.test_members import addr, browser, invite
from tests.test_signin import person, sign_in


@pytest.fixture
def azure(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    fake = samples.FakeAzure()
    monkeypatch.setattr(ai, "TRANSPORT", fake)
    return fake


@pytest.fixture
def announced(monkeypatch):
    seen = []
    monkeypatch.setattr(familythread, "announce", lambda session, trip_id, title, body, exclude="": seen.append((title, body, exclude)))
    return seen


@pytest.fixture
def crew(client):
    """Ari (admin, sample trip booked) and a viewer."""
    book(client)
    vi_mail = addr("vi")
    invite(client, vi_mail, "viewer")
    vi = browser(client)
    sign_in(vi, vi_mail)
    return client, vi


def fields(page, form_id):
    """{name: value} of a form's hidden inputs, checked radios and text inputs, as a browser would post them (first radio of a group left unchecked stays out)."""
    form = re.search(rf'<form[^>]*\bid="{form_id}"[^>]*>(.*?)</form>', page, re.S).group(1)
    out = {}
    for tag in re.findall(r"""<input(?:[^>"']|"[^"]*"|'[^']*')*>""", form):
        attrs = {k: html.unescape(a or b) for k, a, b in re.findall(r"""([\w-]+)=(?:"([^"]*)"|'([^']*)')""", tag)}
        if attrs.get("type") in ("radio", "checkbox") and "checked" not in tag:
            continue
        if attrs.get("name"):
            out[attrs["name"]] = attrs.get("value", "")
    for name, body in re.findall(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', form, re.S):
        out[name] = html.unescape(body)
    return out


def convert(client, text=None):
    return client.post("/trip/add/convert", data={"text": text if text is not None else samples.text()}, follow_redirects=False)


def questions(client):
    found = convert(client).text
    return client.post("/trip/add/questions", data=fields(found, "cv-found-form"), follow_redirects=False)


def answers(page, **over):
    """What a person posts from the questions page: its hidden fields, the suggested people kept, and the two parks on Sat and Mon."""
    data = fields(page, "cv-questions-form")
    data.update({"day_0": "1", "day_1": "3", **over})
    return data


# ---- the paste page ------------------------------------------------------------------------------------------------------

def test_the_paste_page_has_a_big_textarea_convert_and_the_mic_hint(client):
    book(client)
    r = client.get("/trip/add")
    assert r.status_code == 200
    for needle in ('id="cv-text"', 'id="cv-convert"', "Reading your messages…", "tap the mic on your keyboard", "copy then paste", 'action="/trip/add/convert"', 'name="trip"'):
        assert needle in r.text, needle
    assert 'id="cv-progress"' in r.text and "hidden" in re.search(r'<div[^>]*id="cv-progress"[^>]*>', r.text).group(0)


def test_today_has_a_clear_add_to_the_trip_button_for_editors_only(crew):
    owner, viewer = crew
    assert 'href="/trip/add"' in owner.get("/trip").text and 'id="tp-add-trip"' in owner.get("/trip").text
    assert 'id="tp-add-trip"' not in viewer.get("/trip").text


def test_signed_out_goes_to_sign_in_and_without_a_trip_to_start(client):
    assert client.get("/trip/add", follow_redirects=False).headers["location"].startswith("/signin")
    sign_in(client)
    assert client.get("/trip/add", follow_redirects=False).headers["location"] == "/start"


# ---- convert: step 1 -----------------------------------------------------------------------------------------------------

def test_convert_shows_what_was_found_and_saves_nothing(client, azure):
    book(client)
    r = convert(client)
    assert r.status_code == 200
    page = r.text
    stats = page[page.index('id="cv-stats"'):][:900]
    assert re.findall(r'cv-stat-n">(\d+)<', stats) == ["2", "8", "23"]
    for needle in ("Universal Studios Hollywood", "Disney California Adventure", "Lower Lot", "Harry Potter world", "Pixar Pier", "Merged", "repeated item", "Set aside: ", "Studio Tour, Simpsons",
                   "Still in the trip, just not in a day", "Kept your notes", "roughest ride", "Made a list: ", "Pregnancy-safe rides (8)", "Next: 2 quick questions", "Edit text"):
        assert needle in page, needle
    assert canvas.cal.activities(person("ari")) == []
    assert client.get("/trip").text.count("Universal Studios Hollywood") == 0


def test_a_model_failure_leaves_a_clear_message_and_the_pasted_text_intact(client, monkeypatch):
    book(client)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k"), monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://e.example.com"), monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    monkeypatch.setattr(ai, "TRANSPORT", samples.FakeAzure(failure=TimeoutError("slow")))
    r = convert(client)
    assert r.status_code == 503 and "took too long" in r.text and 'role="alert"' in r.text
    assert fields(r.text, "cv-form")["text"] == samples.text()


def test_without_the_service_switched_on_the_text_is_kept_too(client):
    book(client)
    r = convert(client)
    assert r.status_code == 503 and "not switched on" in r.text and fields(r.text, "cv-form")["text"] == samples.text()


def test_nothing_pasted_asks_for_it(client, azure):
    book(client)
    r = convert(client, "  ")
    assert r.status_code == 422 and "Paste the messages first" in r.text and azure.sent == []


# ---- every button on step 1 and step 2 ------------------------------------------------------------------------------------

def test_edit_text_goes_back_to_the_textarea_with_the_text_intact(client, azure):
    book(client)
    found = convert(client).text
    posted = fields(found, "cv-found-form")
    assert re.search(r'id="cv-edit"[^>]*formaction="/trip/add/edit"|formaction="/trip/add/edit"[^>]*id="cv-edit"', found)
    r = client.post("/trip/add/edit", data=posted, follow_redirects=False)
    assert r.status_code == 200 and fields(r.text, "cv-form")["text"] == samples.text() and 'id="cv-convert"' in r.text


def test_next_asks_who_the_initials_are_which_day_each_park_is_and_who_the_list_is_for(client, azure):
    book(client)
    r = questions(client)
    assert r.status_code == 200
    page = r.text
    assert re.findall(r'data-token="([^"]+)"', page) == ["Hrishi", "H", "B", "R", "A"]      # this family is just Ari: nobody is called Hrishi, so that name is asked too
    assert "Which day is each park?" in page and page.count('class="cv-card cv-whichday"') == 2
    assert "Pregnancy-safe rides: who&#x27;s it for?" in page or "Pregnancy-safe rides: who's it for?" in page
    assert "Nothing is saved until you tap Add to trip." in page and 'id="cv-add"' in page
    assert page.count('name="day_0"') == 5 and "Keep as R" in page and "Someone new" in page and "Just keep it as a list" in page
    assert canvas.cal.activities(person("ari")) == []


def test_back_returns_to_what_we_found(client, azure):
    book(client)
    q = questions(client).text
    r = client.post("/trip/add/found", data=fields(q, "cv-questions-form"), follow_redirects=False)
    assert r.status_code == 200 and 'id="cv-stats"' in r.text and "Next: 2 quick questions" in r.text


def test_a_lost_draft_goes_back_to_the_paste_page_with_the_text(client, azure):
    book(client)
    for path in ("/trip/add/questions", "/trip/add/save"):
        r = client.post(path, data={"draft": "not json", "text": "my messages"}, follow_redirects=False)
        assert r.status_code == 409 and "lost" in r.text and fields(r.text, "cv-form")["text"] == "my messages"


# ---- add to trip ----------------------------------------------------------------------------------------------------------

def test_add_to_trip_saves_the_days_and_the_block_shows_its_steps(client, azure, announced):
    book(client)
    page = questions(client).text
    data = answers(page)
    r = client.post("/trip/add/save", data=data, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip?day=1&new=a1"
    ari = person("ari")
    acts = canvas.cal.activities(ari)
    assert [(a.title, a.day) for a in acts] == [("Universal Studios Hollywood", 1), ("Disney California Adventure", 3)]
    assert len(announced) == 1
    today = client.get("/trip?day=1").text
    assert 'href="/trip/block?id=a1' in today and "Universal Studios Hollywood" in today
    block = client.get("/trip/block?id=a1").text
    for needle in ("Lower Lot", "Harry Potter world", "Revenge of the Mummy", "roughest ride", "H and B walk", "Set aside · 2", "Studio Tour", "Pregnancy-safe rides", "Mark done", "Golden Zephyr"):
        assert needle in block, needle
    assert "Universal Studios Hollywood on Sat" in html.unescape(client.get("/trip/family/thread").text)


def test_who_answers_reach_the_steps_someone_new_and_kept_initials(client, azure):
    book(client)
    page = questions(client).text
    r = client.post("/trip/add/save", data=answers(page, who_1="new", new_1="Bhoomija", who_2="keep"), follow_redirects=False)
    assert r.status_code == 303
    block = client.get("/trip/block?id=a1").text
    assert "Bhoomija" in block
    other = client.get("/trip/block?id=a2").text
    assert 'cv-chip">R<' in other


def test_two_parks_on_one_day_or_no_day_is_refused_and_keeps_the_choices(client, azure, announced):
    book(client)
    page = questions(client).text
    r = client.post("/trip/add/save", data=answers(page, day_1="1", new_0="x"), follow_redirects=False)
    assert r.status_code == 409 and "different day" in r.text and 'role="alert"' in r.text
    assert canvas.cal.activities(person("ari")) == [] and announced == []
    assert fields(r.text, "cv-questions-form")["day_0"] == "1"
    data = answers(page)
    data.pop("day_1")
    r = client.post("/trip/add/save", data=data, follow_redirects=False)
    assert r.status_code == 409 and "Pick a day for each park" in r.text


def test_the_flight_window_message_comes_from_the_calendar(client, azure):
    book(client)
    page = questions(client).text
    r = client.post("/trip/add/save", data=answers(page, day_0="0"), follow_redirects=False)
    assert r.status_code == 409 and ("land" in r.text or "overlaps" in r.text)
    assert canvas.cal.activities(person("ari")) == []


# ---- the block: done and set aside ---------------------------------------------------------------------------------------

def added(client):
    page = questions(client).text
    assert client.post("/trip/add/save", data=answers(page), follow_redirects=False).status_code == 303


def step_id(client, title, act="a1"):
    block = client.get(f"/trip/block?id={act}").text
    row = re.search(r'<div[^>]*data-step="([0-9a-f]+)"[^>]*>(?:(?!data-step=).)*?' + re.escape(title), block, re.S) or re.search(r'data-step="([0-9a-f]+)"[^>]*>(?:(?!data-step=).)*?' + re.escape(title), block, re.S)
    return row.group(1)


def test_mark_done_and_set_aside_are_one_tap_each(client, azure):
    book(client)
    added(client)
    sid = step_id(client, "Revenge of the Mummy")
    r = client.post("/trip/block/step", data={"step": sid, "act": "a1", "do": "done"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/trip/block?id=a1&trip=")
    assert re.search(rf'id="step-{sid}"[^>]*class="[^"]*is-done|class="[^"]*is-done[^"]*"[^>]*id="step-{sid}"', client.get("/trip/block?id=a1").text)
    assert "Not done" in client.get("/trip/block?id=a1").text
    client.post("/trip/block/step", data={"step": sid, "act": "a1", "do": "undone"})
    assert "is-done" not in client.get("/trip/block?id=a1").text
    client.post("/trip/block/step", data={"step": sid, "act": "a1", "do": "aside"})
    tray = client.get("/trip/block?id=a1").text
    assert "Set aside · 3" in tray and "Put back" in tray
    client.post("/trip/block/step", data={"step": sid, "act": "a1", "do": "back"})
    assert "Set aside · 2" in client.get("/trip/block?id=a1").text


def test_a_step_that_is_gone_just_shows_the_block(client, azure):
    book(client)
    added(client)
    r = client.post("/trip/block/step", data={"step": "nope", "act": "a1", "do": "done"}, follow_redirects=False)
    assert r.status_code == 303


def test_a_block_that_is_not_a_plan_with_steps_goes_back_to_today(client):
    book(client)
    assert client.get("/trip/block?id=a9", follow_redirects=False).headers["location"].startswith("/trip")


# ---- viewers --------------------------------------------------------------------------------------------------------------

def test_viewers_cannot_convert_save_or_tick_but_can_read_the_block(crew, azure):
    owner, viewer = crew
    added(owner)
    asked = len(azure.sent)
    assert "Only editors can add to the trip" in viewer.get("/trip/add").text and 'id="cv-form"' not in viewer.get("/trip/add").text
    for path, data in [("/trip/add/convert", {"text": samples.text()}), ("/trip/add/save", {"draft": "{}"}), ("/trip/block/step", {"step": "x", "act": "a1", "do": "done"})]:
        assert viewer.post(path, data=data, follow_redirects=False).status_code == 403, path
    assert len(azure.sent) == asked      # the refused viewer never reached the model
    block = viewer.get("/trip/block?id=a1").text
    assert "Revenge of the Mummy" in block and "Mark done" not in block and "Set aside</button>" not in block


def test_each_park_card_says_its_areas_in_order(client, azure):
    book(client)
    page = convert(client).text
    assert "Lower Lot, lunch, Harry Potter world, then Upper Lot" in page
    assert "Hollywood Land and Avengers Campus, Cars Land, Pixar Pier, lunch, Grizzly Peak, then Buena Vista" in page


def test_the_header_back_buttons_keep_the_text_and_the_draft(client, azure):
    book(client)
    found = convert(client).text
    assert 'id="cv-top-back"' in found and 'form="cv-found-form"' in found
    r = client.post("/trip/add/edit", data=fields(found, "cv-found-form"), follow_redirects=False)
    assert fields(r.text, "cv-form")["text"] == samples.text()
    q = questions(client).text
    assert 'id="cv-top-back"' in q and 'form="cv-questions-form"' in q
    r = client.post("/trip/add/found", data=fields(q, "cv-questions-form"), follow_redirects=False)
    assert 'id="cv-stats"' in r.text


def test_a_confident_suggestion_is_one_confirmed_chip_with_change(client, azure):
    book(client)
    page = questions(client).text
    a = page[page.index('data-token="A"'):][:2500]
    assert 'data-chip' in a and "the only A in the family" in a and ">change<" in a
    assert 'data-token="R"' in page and "data-chip" not in page[page.index('data-token="R"'):][:600]      # nobody to suggest: all the options show
    assert fields(page, "cv-questions-form")["who_4"].startswith("m:")      # and the suggestion is what gets posted


def test_a_second_convert_while_one_is_running_gets_the_busy_message(client, azure, monkeypatch):
    book(client)
    monkeypatch.setattr(ai, "_in_flight", {("convert", person("ari")["tenant_id"])})
    r = convert(client)
    assert r.status_code == 503 and ai.BUSY in r.text and fields(r.text, "cv-form")["text"] == samples.text() and azure.sent == []
