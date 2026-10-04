"""F-072: Ask GitAway in a real browser at phone width: type a request, see the proposal as before and after, Apply, see the day changed; Cancel and Change it change
nothing; the microphone exists only where the browser has speech recognition. A fake model answers (nothing reaches Azure). Nothing scrolls sideways."""
import time

import pytest
from playwright.sync_api import expect

from gitaway import ai
from tests import canvas_samples as samples
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import SMALL_CONTROLS, SMALL_TEXT

DAY = 1


def op(kind, **kw):
    return {"op": kind, "id": None, "title": None, "start": None, "end": None, "note": None, "block_id": None, "part_id": None, "time": None, "who": [], **kw}


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    fake = samples.FakeAzure({"summary": "I'd block 3 to 5 for a rest and move lunch to 12:30.",
                              "ops": [op("add_plan", title="Rest at the hotel", start="15:00", end="17:00"), op("move_plan", id="a1", start="12:30", end="13:30"), op("remove_plan", id="a2")]})
    monkeypatch.setattr(ai, "TRANSPORT", fake)
    return fake


@pytest.fixture
def phone(browser, base_url):
    contexts = []

    def make(init_script=None, role_mail="ari.rivera@example.com"):
        ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        if init_script:
            ctx.add_init_script(init_script)
        ctx.request.post(f"{base_url}/signin", form={"email": role_mail, "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
        for id_, start, end, title, kind in (("a1", "12:00", "13:00", "Lunch", "food"), ("a2", "15:00", "17:00", "Griffith Observatory", "culture")):
            ctx.request.post(f"{base_url}/calendar/activities", form={"id": id_, "day": str(DAY), "start": start, "end": end, "title": title, "kind": kind}, max_redirects=0)
        return ctx.new_page()

    yield make
    for c in contexts:
        c.close()


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def plan_titles(page, base_url):
    page.goto(f"{base_url}/trip?day={DAY}")
    return page.locator("#tp-list").inner_text()


def test_type_a_request_see_the_proposal_apply_and_see_the_day_changed(phone, base_url, model):
    page = phone()
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    expect(page.locator("#tp-title-h")).to_have_text("Ask GitAway")
    expect(page.locator("#ak-hint")).to_contain_text("microphone on the keyboard")
    expect(page.locator("#ak-day")).to_have_value(str(DAY))
    assert overflow(page) <= 0 and page.evaluate(SMALL_TEXT) == [] and page.evaluate(SMALL_CONTROLS) == []
    page.set_viewport_size({"width": 320, "height": 640})
    assert overflow(page) <= 0
    page.set_viewport_size(PHONE)
    page.locator("#ak-text").fill("We're tired. Block the next two hours and move lunch to 12:30.")
    page.locator("#ak-go").click()

    expect(page.locator("#ak-prop")).to_be_visible()
    expect(page.locator("#ak-say")).to_have_count(0)      # a removal is in the list: the model's own sentence is not shown
    expect(page.locator(".ak-chip")).to_have_count(3)
    expect(page.locator('.ak-chip[data-kind="new"]')).to_contain_text("Rest at the hotel")
    expect(page.locator('.ak-chip[data-kind="moved"]')).to_contain_text("12:30")
    expect(page.locator('.ak-chip[data-kind="removed"]')).to_contain_text("Griffith Observatory")
    expect(page.locator('.ak-chip[data-kind="removed"]')).to_contain_text("Can't be undone")
    assert overflow(page) <= 0 and page.evaluate(SMALL_TEXT) == [] and page.evaluate(SMALL_CONTROLS) == []
    page.set_viewport_size({"width": 320, "height": 640})
    assert overflow(page) <= 0
    page.set_viewport_size(PHONE)
    # nothing has changed yet: look at the day from a second page of the same session
    same = page.context.new_page()
    try:
        titles = plan_titles(same, base_url)
        assert "Lunch" in titles and "Griffith Observatory" in titles and "Rest at the hotel" not in titles
    finally:
        same.close()

    page.locator("#ak-apply").click()
    expect(page.locator("#ak-done")).to_contain_text("3 changes on Saturday, Oct 17")
    expect(page.locator("#ak-done")).to_contain_text("The family has been told")
    assert overflow(page) <= 0
    page.locator("#ak-see").click()
    page.wait_for_url(f"**/trip?day={DAY}")
    expect(page.locator("#tp-list")).to_contain_text("Rest at the hotel")
    expect(page.locator("#tp-list")).not_to_contain_text("Griffith Observatory")
    expect(page.locator("#tp-list")).to_contain_text("12:30")
    # Ask again from the day: the small button opens the tab on this day
    page.locator("#ak-open").click()
    page.wait_for_url(f"**/trip/ask?day={DAY}")
    expect(page.locator("#ak-day")).to_have_value(str(DAY))


def test_cancel_and_change_it_change_nothing(phone, base_url, model):
    page = phone()
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-text").fill("Skip Griffith, then lunch later")
    page.locator("#ak-go").click()
    expect(page.locator("#ak-prop")).to_be_visible()

    page.locator("#ak-change").click()                 # Change it: back to the text, kept
    expect(page.locator("#ak-text")).to_have_value("Skip Griffith, then lunch later")
    page.locator("#ak-text").fill("Skip Griffith, then lunch later please")
    page.locator("#ak-go").click()
    expect(page.locator("#ak-prop")).to_be_visible()

    page.locator("#ak-cancel").click()                 # Cancel: an empty box
    expect(page.locator("#ak-text")).to_have_value("")
    assert overflow(page) <= 0
    titles = plan_titles(page, base_url)
    assert "Lunch" in titles and "Griffith Observatory" in titles and "Rest at the hotel" not in titles


def test_a_model_failure_keeps_the_request_and_says_so(phone, base_url, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k"), monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://e.example.com"), monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    monkeypatch.setattr(ai, "TRANSPORT", samples.FakeAzure(failure=TimeoutError("slow")))
    page = phone()
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-text").fill("Move lunch to one")
    page.locator("#ak-go").click()
    expect(page.locator("#ak-error")).to_contain_text("Nothing was lost")
    expect(page.locator("#ak-text")).to_have_value("Move lunch to one")
    assert overflow(page) <= 0


class Slow(samples.FakeAzure):
    def __call__(self, url, headers, body, timeout):
        time.sleep(0.8)      # long enough to see the waiting state
        return super().__call__(url, headers, body, timeout)


def test_the_busy_state_is_shown_while_the_model_works(phone, base_url, model, monkeypatch):
    monkeypatch.setattr(ai, "TRANSPORT", Slow(model.answer))
    page = phone()
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-text").fill("Move lunch to one")
    state = page.evaluate("""() => { const f = document.getElementById('ak-form'); f.requestSubmit(document.getElementById('ak-go'));
        return new Promise(r => setTimeout(() => r({disabled: document.getElementById('ak-go').disabled, shown: !document.getElementById('ak-progress').hidden, busy: f.getAttribute('aria-busy')}), 100)); }""")
    assert state["disabled"] and state["shown"] and state["busy"] == "true"
    expect(page.locator("#ak-prop")).to_be_visible()      # let the call finish: the next test is the same family


NO_SPEECH = "delete window.SpeechRecognition; delete window.webkitSpeechRecognition;"
FAKE_SPEECH = """
window.SpeechRecognition = window.webkitSpeechRecognition = class {
  start() { window.__rec = this; setTimeout(() => this.onresult && this.onresult({results: [[{transcript: 'move lunch'}], [{transcript: ' to 12:30'}]]}), 20); }
  stop() { this.onend && this.onend(); }
};"""


def test_the_microphone_button_is_hidden_when_the_browser_cannot_listen(phone, base_url):
    page = phone(NO_SPEECH)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    expect(page.locator("#ak-text")).to_be_visible()
    expect(page.locator("#ak-mic")).to_be_hidden()
    expect(page.locator("#ak-hint")).to_be_visible()         # dictation from the keyboard still works
    assert overflow(page) <= 0


def test_hold_to_talk_fills_the_box_while_it_listens(phone, base_url):
    page = phone(NO_SPEECH + FAKE_SPEECH)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    mic = page.locator("#ak-mic")
    expect(mic).to_be_visible()
    page.locator("#ak-text").fill("Hello.")
    box = mic.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    expect(mic).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#ak-text")).to_have_value("Hello. move lunch to 12:30")
    page.mouse.up()
    expect(mic).to_have_attribute("aria-pressed", "false")
    assert overflow(page) <= 0
