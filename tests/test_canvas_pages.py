"""F-080: a block's parts and steps through HTTP (the Add to the trip screens became the one Ask box in F-087: tests/test_say.py). Nothing here reaches Azure."""

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


# ---- the paste page ------------------------------------------------------------------------------------------------------

# ---- convert: step 1 -----------------------------------------------------------------------------------------------------

# ---- every button on step 1 and step 2 ------------------------------------------------------------------------------------

# ---- add to trip ----------------------------------------------------------------------------------------------------------

# ---- the block: done and set aside ---------------------------------------------------------------------------------------

def added(client):
    """The captain's messages, added through the one Ask box: Universal on Sat, Disney California Adventure on Mon."""
    page = client.post("/trip/ask/propose", data={"day": "", "text": samples.text()}).text
    data = fields(page, "ak-questions-form")
    data.update({"a_park:0": "1", "a_park:1": "3"})
    r = client.post("/trip/ask/apply", data=fields(client.post("/trip/ask/answer", data=data).text, "ak-apply-form"), follow_redirects=False)
    assert r.status_code == 303


def step_id(client, title, act="a1"):
    block = client.get(f"/trip/canvas?block={act}").text
    row = re.search(r'<div[^>]*data-step="([0-9a-f]+)"[^>]*>(?:(?!data-step=).)*?' + re.escape(title), block, re.S) or re.search(r'data-step="([0-9a-f]+)"[^>]*>(?:(?!data-step=).)*?' + re.escape(title), block, re.S)
    return row.group(1)


def test_mark_done_and_set_aside_are_one_tap_each(client, azure):
    book(client)
    added(client)
    sid = step_id(client, "Revenge of the Mummy")
    r = client.post("/trip/block/step", data={"step": sid, "act": "a1", "do": "done"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/trip/canvas?block=a1")      # old forms still write, then land on the block
    block = client.get("/trip/canvas?block=a1").text
    assert re.search(rf'data-step="{sid}"[^>]*class="cz-step is-done"', block) and "1 of 14 done" in block
    assert "Not done" in client.get(f"/trip/canvas?step={sid}").text
    client.post("/trip/block/step", data={"step": sid, "act": "a1", "do": "undone"})
    assert "is-done" not in client.get("/trip/canvas?block=a1").text
    client.post("/trip/block/step", data={"step": sid, "act": "a1", "do": "aside"})
    assert "Set aside · 3" in client.get("/trip/canvas?block=a1").text and "Put back" in client.get(f"/trip/canvas?step={sid}").text
    client.post("/trip/block/step", data={"step": sid, "act": "a1", "do": "back"})
    assert "Set aside · 2" in client.get("/trip/canvas?block=a1").text


def test_the_old_block_address_goes_to_the_canvas(client, azure):
    book(client)
    added(client)
    r = client.get("/trip/block?id=a1", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/trip/canvas?block=a1")


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
    assert "Only editors can change the plan" in viewer.get("/trip/ask").text and 'id="ak-form"' not in viewer.get("/trip/ask").text
    for path, data in [("/trip/ask/propose", {"text": samples.text()}), ("/trip/ask/apply", {"plan": "{}"}), ("/trip/ask/answer", {"state": "{}"}), ("/trip/block/step", {"step": "x", "act": "a1", "do": "done"})]:
        assert viewer.post(path, data=data, follow_redirects=False).status_code == 403, path
    assert len(azure.sent) == asked      # the refused viewer never reached the model
    block = viewer.get("/trip/canvas?block=a1").text
    assert "Revenge of the Mummy" in block and "Mark done" not in block and "Set aside</button>" not in block


