"""F-087: the one Ask box in a real browser at phone width: tap to talk (continuous, shown live), Paste, the count near the limit, a pasted itinerary asking its
quick questions, the day-by-day preview, Apply, "See the day" on the day view; the modes the day view links to. A fake model answers (nothing reaches Azure).
Nothing scrolls sideways at 390 and 320; text stays at the floor and every control is a full target."""
import time

import pytest
from playwright.sync_api import expect

from gitaway import ai
from tests import canvas_samples as samples
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import SMALL_CONTROLS, SMALL_TEXT

DAY = 1
NO_SPEECH = "delete window.SpeechRecognition; delete window.webkitSpeechRecognition;"
FAKE_SPEECH = """
window.SpeechRecognition = window.webkitSpeechRecognition = class {
  start() { window.__rec = this; setTimeout(() => this.onresult && this.onresult({results: [[{transcript: 'move lunch'}], [{transcript: ' to 12:30'}]]}), 20); }
  stop() { this.onend && this.onend(); }
};"""


class Slow(samples.FakeAzure):
    delay = 0.8

    def __call__(self, url, headers, body, timeout):
        time.sleep(self.delay)      # long enough to see the waiting state
        return super().__call__(url, headers, body, timeout)


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    fake = Slow()
    monkeypatch.setattr(ai, "TRANSPORT", fake)
    return fake


@pytest.fixture
def phone(browser, base_url):
    contexts = []

    def make(init_script=None, permissions=None):
        ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True, permissions=permissions)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        if init_script:
            ctx.add_init_script(init_script)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
        return ctx.new_page()

    yield make
    for c in contexts:
        c.close()


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def fits(page):
    for width in (390, 320):
        page.set_viewport_size({"width": width, "height": 700})
        assert overflow(page) <= 0 and page.evaluate(SMALL_TEXT) == [] and page.evaluate(SMALL_CONTROLS) == []
    page.set_viewport_size(PHONE)


def test_tap_to_talk_fills_the_box_while_it_listens_and_stop_ends_it(phone, base_url):
    page = phone(NO_SPEECH + FAKE_SPEECH)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    mic = page.locator("#ak-mic")
    expect(mic).to_be_visible()
    expect(page.locator("#ak-mic-label")).to_have_text("Tap to talk")
    page.locator("#ak-text").fill("Hello.")
    mic.click()
    expect(mic).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#ak-mic-label")).to_have_text("Stop")
    expect(page.locator("#ak-text")).to_have_value("Hello. move lunch to 12:30")
    mic.click()
    expect(mic).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#ak-mic-label")).to_have_text("Tap to talk")
    fits(page)


def test_mode_talk_starts_dictation_and_without_speech_focuses_the_box(phone, base_url):
    page = phone(NO_SPEECH + FAKE_SPEECH)
    page.goto(f"{base_url}/trip/ask?day={DAY}&mode=talk")
    expect(page.locator("#ak-mic")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#ak-text")).to_have_value("move lunch to 12:30")
    plain = phone(NO_SPEECH)
    plain.goto(f"{base_url}/trip/ask?day={DAY}&mode=talk")
    expect(plain.locator("#ak-text")).to_be_focused()
    expect(plain.locator("#ak-hint")).to_be_visible()


def test_the_paste_button_reads_the_clipboard_and_mode_paste_focuses_it(phone, base_url):
    page = phone(permissions=["clipboard-read", "clipboard-write"])
    page.goto(f"{base_url}/trip/ask?day={DAY}&mode=paste")
    expect(page.locator("#ak-paste")).to_be_focused()
    page.evaluate("navigator.clipboard.writeText('Lunch at 12:30\\nPool 3 to 5')")
    page.locator("#ak-paste").click()
    expect(page.locator("#ak-text")).to_have_value("Lunch at 12:30\nPool 3 to 5")
    expect(page.locator("#ak-mic-status")).to_contain_text("Pasted")
    fits(page)


def test_paste_without_clipboard_access_points_at_the_box(phone, base_url):
    page = phone("Object.defineProperty(navigator, 'clipboard', {value: undefined});")
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-paste").click()
    expect(page.locator("#ak-text")).to_be_focused()
    expect(page.locator("#ak-mic-status")).to_contain_text("Touch and hold")


def test_the_count_shows_near_the_limit_and_over_it_blocks_asking(phone, base_url):
    page = phone()
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    expect(page.locator("#ak-count")).to_be_hidden()
    set_text = "(n) => { const b = document.getElementById('ak-text'); b.value = 'a'.repeat(n); b.dispatchEvent(new Event('input')); }"
    page.evaluate(set_text, 17000)
    expect(page.locator("#ak-count")).to_have_text("17,000 of 20,000 characters")
    page.evaluate(set_text, 20010)
    expect(page.locator("#ak-count")).to_contain_text("10 characters over")
    expect(page.locator("#ak-go")).to_be_disabled()
    fits(page)
    page.evaluate(set_text, 5)
    expect(page.locator("#ak-go")).to_be_enabled()


def test_a_pasted_itinerary_asks_which_day_shows_a_day_by_day_preview_and_applies(phone, base_url, model):
    page = phone()
    page.goto(f"{base_url}/trip/ask")
    page.locator("#ak-text").fill(samples.text())
    state = page.evaluate("""() => { const f = document.getElementById('ak-form'); f.requestSubmit(document.getElementById('ak-go'));
        return new Promise(r => setTimeout(() => r({disabled: document.getElementById('ak-go').disabled, shown: !document.getElementById('ak-progress').hidden,
        busy: f.getAttribute('aria-busy')}), 150)); }""")
    assert state["disabled"] and state["shown"] and state["busy"] == "true"          # the page says it is working
    expect(page.locator("#ak-questions")).to_be_visible()
    assert page.locator('[data-q="park:0"] .ak-opt').count() == 5 and page.locator(".ak-opt:has(input:checked)").count() >= 7      # every suggestion is already chosen
    fits(page)
    page.locator('[data-q="park:0"] .ak-opt').nth(1).click()          # Sat
    page.locator('[data-q="park:1"] .ak-opt').nth(3).click()          # Mon
    page.locator("#ak-continue").click()
    expect(page.locator("#ak-prop")).to_be_visible()
    expect(page.locator(".ak-dayh")).to_have_text(["Saturday, Oct 17", "Monday, Oct 19"])
    expect(page.locator(".ak-chip")).to_have_count(2)
    expect(page.locator("#ak-tidy")).to_contain_text("Studio Tour")
    fits(page)
    page.locator("#ak-change").click()                                  # Change it: the text is intact
    expect(page.locator("#ak-text")).to_have_value(samples.text())
    page.locator("#ak-go").click()
    page.locator("#ak-change-text").click()                             # Change the words, from the questions
    expect(page.locator("#ak-text")).to_have_value(samples.text())
    page.locator("#ak-go").click()
    page.locator('[data-q="park:0"] .ak-opt').nth(1).click()
    page.locator('[data-q="park:1"] .ak-opt').nth(3).click()
    page.locator("#ak-continue").click()
    page.locator("#ak-apply").click()
    expect(page.locator("#ak-done")).to_contain_text("2 days added")
    expect(page.locator("#ak-done")).to_contain_text("The family has been told")
    page.locator("#ak-see").click()
    page.wait_for_url("**/trip/canvas?day=1")


def test_from_a_day_the_paste_needs_no_day_question_and_cancel_goes_back(phone, base_url, model):
    page = phone()
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-text").fill(samples.text())
    page.locator("#ak-go").click()
    expect(page.locator("#ak-questions")).to_be_visible()
    assert page.locator('[data-q^="park"]').count() == 0 and page.locator('[data-q="who:H"]').count() == 1
    page.locator("#ak-continue").click()
    expect(page.locator(".ak-dayh")).to_have_text(["Saturday, Oct 17"])
    page.locator("#ak-cancel").click()
    page.wait_for_url(f"**/trip/ask?day={DAY}")
    expect(page.locator("#ak-text")).to_have_value("")


def test_a_failed_long_paste_keeps_the_text_and_says_so(phone, base_url, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://e.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    monkeypatch.setattr(ai, "TRANSPORT", samples.FakeAzure(failure=TimeoutError("slow")))
    page = phone()
    page.set_viewport_size({"width": 320, "height": 640})
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-text").fill(samples.text())
    page.locator("#ak-go").click()
    expect(page.locator("#ak-error")).to_contain_text("took too long")
    expect(page.locator("#ak-text")).to_have_value(samples.text())
    expect(page.locator("#ak-go")).to_be_enabled()
    assert overflow(page) <= 0


def test_the_site_keeps_answering_while_the_model_is_slow(phone, base_url, model):
    """The model call runs off the event loop: /healthz answers at once while a long paste waits for the model."""
    import threading
    import urllib.request
    model.delay = 2.0
    page = phone()
    waits, stop = [], threading.Event()

    def poll():
        time.sleep(0.4)
        while not stop.is_set():
            start = time.monotonic()
            with urllib.request.urlopen(f"{base_url}/healthz", timeout=5) as r:
                assert r.status == 200
            waits.append(time.monotonic() - start)
            time.sleep(0.2)

    worker = threading.Thread(target=poll)
    worker.start()
    status = page.request.post(f"{base_url}/trip/ask/propose", form={"text": samples.text(), "day": str(DAY)}).status
    stop.set()
    worker.join(10)
    assert status == 200 and model.sent
    assert len(waits) >= 3 and max(waits) < 0.5, waits


def test_the_day_picker_that_opened_on_today_follows_a_long_paste_until_a_day_is_picked(phone, base_url):
    page = phone()
    page.goto(f"{base_url}/trip/ask")
    page.evaluate("() => { const s = document.getElementById('ak-day'); s.dataset.auto = '2'; s.value = '2'; }")     # as drawn on a trip day
    page.locator("#ak-text").fill("move lunch to 12:30")
    expect(page.locator("#ak-day")).to_have_value("2")
    page.locator("#ak-text").fill("Universal day. " * 80)
    expect(page.locator("#ak-day")).to_have_value("")
    page.locator("#ak-text").fill("move lunch")
    expect(page.locator("#ak-day")).to_have_value("2")
    page.locator("#ak-day").select_option("1")
    page.locator("#ak-text").fill("Universal day. " * 80)
    expect(page.locator("#ak-day")).to_have_value("1")
    assert page.evaluate("() => parseFloat(document.getElementById('ak-text').style.height) >= 13 * parseFloat(getComputedStyle(document.documentElement).fontSize) - 1")
