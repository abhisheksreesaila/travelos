"""F-087: the one Ask box in a real browser at phone width: tap to talk (continuous, shown live), Paste, the count near the limit, a pasted itinerary asking its
quick questions, the day-by-day preview, Apply, "See the day" on the day view; the modes the day view links to. A fake model answers (nothing reaches Azure).
Nothing scrolls sideways at 390 and 320; text stays at the floor and every control is a full target."""
import re
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

    def make(init_script=None, permissions=None, motion="reduce"):
        ctx = browser.new_context(viewport=PHONE, reduced_motion=motion, has_touch=True, is_mobile=True, permissions=permissions)
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


# ---- F-102: where speech recognition is missing or fails (an iPhone Home Screen app) the mic records and the server transcribes ----------------------------------

FAKE_MIC = """(() => {
  navigator.mediaDevices.getUserMedia = async () => {
    const ctx = new AudioContext(); await ctx.resume();
    const osc = ctx.createOscillator(); const dest = ctx.createMediaStreamDestination();
    osc.connect(dest); osc.start();
    return dest.stream;
  };
})();"""
ERRORING_SPEECH = """
window.SpeechRecognition = window.webkitSpeechRecognition = class {
  start() { window.__started = (window.__started || 0) + 1; setTimeout(() => this.onerror && this.onerror({error: 'service-not-allowed'}), 20); }
  stop() { this.onend && this.onend(); }
  abort() {}
};"""
SILENT_SPEECH = """
window.SpeechRecognition = window.webkitSpeechRecognition = class {
  start() { window.__started = (window.__started || 0) + 1; }
  stop() { this.onend && this.onend(); }
  abort() {}
};"""
INSTALLED_IPHONE = """
Object.defineProperty(navigator, 'userAgent', {get: () => 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148'});
Object.defineProperty(navigator, 'standalone', {get: () => true});"""
HEARD = "move lunch to 12:30"


class Heard:
    """A fake `ai.TRANSPORT` for the speech-to-text call: waits a moment (so the waiting state can be seen), then answers like Azure."""

    def __init__(self, delay=0.6, status=200, text=HEARD):
        self.delay, self.status, self.text, self.sent = delay, status, text, []

    def __call__(self, url, headers, body, timeout):
        import json
        time.sleep(self.delay)
        self.sent.append(body)
        return self.status, json.dumps({"text": self.text})


@pytest.fixture
def stt(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "stt-test")
    fake = Heard()
    monkeypatch.setattr(ai, "TRANSPORT", fake)
    return fake


def record_and_stop(page, seconds=1.3):
    mic = page.locator("#ak-mic")
    mic.click()
    expect(mic).to_have_class(re.compile("is-recording"))
    page.wait_for_timeout(int(seconds * 1000))
    mic.click()


def test_without_speech_recognition_the_mic_records_shows_the_state_and_adds_the_words(phone, base_url, stt):
    page = phone(NO_SPEECH + FAKE_MIC)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    mic = page.locator("#ak-mic")
    expect(mic).to_be_visible()
    page.locator("#ak-text").fill("Hello.")
    mic.click()
    expect(mic).to_have_class(re.compile("is-recording"))
    expect(page.locator("#ak-mic-label")).to_have_text("Stop")
    expect(page.locator("#ak-mic-time")).to_be_visible()
    expect(page.locator("#ak-rec-cancel")).to_be_visible()
    expect(page.locator("#ak-paste")).to_be_hidden()
    page.wait_for_timeout(1300)
    assert page.locator("#ak-mic-time").inner_text() != "0:00"
    fits(page)
    mic.click()                                                         # Stop: it uploads and shows that it is working
    expect(page.locator("#ak-transcribing")).to_be_visible()
    expect(page.locator("#ak-transcribing")).to_contain_text("Transcribing")
    expect(mic).to_be_disabled()
    expect(page.locator("#ak-text")).to_have_value("Hello. " + HEARD)  # appended, what was typed is kept
    expect(page.locator("#ak-transcribing")).to_be_hidden()
    expect(page.locator("#ak-mic-status")).to_contain_text("Added what you said")
    expect(mic).not_to_have_class(re.compile("is-recording"))
    expect(page.locator("#ak-paste")).to_be_visible()
    assert len(stt.sent) == 1 and b"stt-test" in stt.sent[0]
    fits(page)


def test_cancel_throws_the_recording_away_without_sending_it(phone, base_url, stt):
    page = phone(NO_SPEECH + FAKE_MIC)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-mic").click()
    expect(page.locator("#ak-rec-cancel")).to_be_visible()
    page.wait_for_timeout(1200)
    page.locator("#ak-rec-cancel").click()
    expect(page.locator("#ak-mic")).not_to_have_class(re.compile("is-recording"))
    expect(page.locator("#ak-text")).to_have_value("")
    page.wait_for_timeout(300)
    assert stt.sent == []


def test_a_speech_recognition_error_switches_to_recording(phone, base_url, stt):
    page = phone(ERRORING_SPEECH + FAKE_MIC)       # the iPhone app: the API exists but answers service-not-allowed
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-mic").click()
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"))
    page.wait_for_timeout(1200)
    page.locator("#ak-mic").click()
    expect(page.locator("#ak-text")).to_have_value(HEARD)


def test_speech_recognition_that_hears_nothing_for_a_few_seconds_switches_to_recording(phone, base_url, stt):
    page = phone(SILENT_SPEECH + FAKE_MIC)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-mic").click()
    expect(page.locator("#ak-mic")).not_to_have_class(re.compile("is-recording"))
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"), timeout=9000)
    assert page.evaluate("window.__started") == 1


def test_in_the_installed_iphone_app_it_records_straight_away(phone, base_url, stt):
    page = phone(INSTALLED_IPHONE + FAKE_SPEECH + FAKE_MIC)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-mic").click()
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"))
    assert page.evaluate("window.__rec") is None                      # speech recognition was never started


def test_when_voice_typing_is_not_set_up_it_says_so_and_keeps_the_typed_text(phone, base_url, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "")
    page = phone(NO_SPEECH + FAKE_MIC)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-text").fill("Pool at 3")
    record_and_stop(page)
    expect(page.locator("#ak-mic-status")).to_contain_text("Voice typing isn't set up yet")
    expect(page.locator("#ak-mic-status")).to_contain_text("tap the microphone on your keyboard")
    expect(page.locator("#ak-text")).to_have_value("Pool at 3")
    expect(page.locator("#ak-mic")).to_be_enabled()


def test_a_failed_transcription_keeps_the_typed_text_and_says_so(phone, base_url, stt, monkeypatch):
    monkeypatch.setattr(ai, "TRANSPORT", Heard(delay=0.1, status=500))
    page = phone(NO_SPEECH + FAKE_MIC)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-text").fill("Pool at 3")
    record_and_stop(page)
    expect(page.locator("#ak-mic-status")).to_contain_text("could not do that")
    expect(page.locator("#ak-mic-status")).to_contain_text("What you typed is still in the box")
    expect(page.locator("#ak-text")).to_have_value("Pool at 3")


def test_a_long_recording_is_sent_in_pieces_on_one_stream_and_the_words_arrive_in_order(phone, base_url, monkeypatch):
    import json
    monkeypatch.setenv("SARVAM_API_KEY", "sk-test")
    monkeypatch.setattr(ai, "TRANSPORT", None)
    calls = []

    def transport(url, headers, body, timeout):
        time.sleep(0.15)
        calls.append(len(body))
        return 200, json.dumps({"transcript": f"part {len(calls)}", "language_code": "en-IN"})

    monkeypatch.setattr(ai, "TRANSPORT", transport)
    page = phone(NO_SPEECH + FAKE_MIC + "window.__gum = 0; const g = navigator.mediaDevices.getUserMedia; navigator.mediaDevices.getUserMedia = (...a) => { window.__gum++; return g(...a); };")
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.evaluate("document.getElementById('ak-mic').dataset.pieceSecs = '1.5'")        # the page rotates every 25 s; shortened to keep the test fast
    page.locator("#ak-text").fill("Start.")
    page.locator("#ak-mic").click()
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"))
    expect(page.locator("#ak-text")).to_have_value("Start. part 1", timeout=6000)      # the first piece's words arrive while still recording
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"))
    expect(page.locator("#ak-mic")).to_be_enabled()
    page.wait_for_timeout(1500)
    page.locator("#ak-mic").click()
    expect(page.locator("#ak-mic-status")).to_contain_text("Added what you said", timeout=9000)
    value = page.locator("#ak-text").input_value()
    assert len(calls) >= 2 and value == "Start. " + " ".join(f"part {i}" for i in range(1, len(calls) + 1))      # every piece, in order, after what was typed
    assert page.evaluate("window.__gum") == 1                                          # one microphone permission for all pieces


def test_hindi_is_kept_as_said_with_a_quiet_understood_as_line_and_the_english_goes_to_the_planner(phone, base_url, monkeypatch):
    import json
    hindi, english = "दोपहर 12:30 पर लंच", "Lunch at 12:30"
    monkeypatch.setenv("SARVAM_API_KEY", "sk-test")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    chat = samples.FakeAzure()

    def transport(url, headers, body, timeout):
        if url.endswith("/speech-to-text-translate"):
            return 200, json.dumps({"transcript": english, "language_code": "hi-IN"})
        if url.endswith("/speech-to-text"):
            return 200, json.dumps({"transcript": hindi, "language_code": "hi-IN"})
        return chat(url, headers, body, timeout)

    monkeypatch.setattr(ai, "TRANSPORT", transport)
    page = phone(NO_SPEECH + FAKE_MIC)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    expect(page.locator("#ak-understood")).to_be_hidden()
    record_and_stop(page)
    expect(page.locator("#ak-text")).to_have_value(hindi)                       # as said, in the hand font
    expect(page.locator("#ak-understood")).to_have_text("Understood as: " + english)
    fits(page)
    page.locator("#ak-go").click()
    page.wait_for_selector("#ak-questions, #ak-prop, #ak-error")
    asked = json.dumps(chat.sent[0], ensure_ascii=False)
    assert english in asked and hindi not in asked                              # the planner read English
    page.go_back()


def test_the_box_is_a_handwritten_note_and_words_still_being_heard_look_lighter(phone, base_url):
    page = phone(NO_SPEECH + FAKE_SPEECH)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    style = "() => { const s = getComputedStyle(document.getElementById('ak-text')); return {font: s.fontFamily, size: parseFloat(s.fontSize), bg: s.backgroundColor, color: s.color}; }"
    typed = page.evaluate(style)
    assert "Caveat" in typed["font"] and typed["size"] >= 13
    page.locator("#ak-text").fill("Typed words look like the others.")
    assert page.evaluate(style)["font"] == typed["font"]
    page.locator("#ak-mic").click()
    expect(page.locator("#ak-text")).to_have_attribute("data-words", "interim")      # the fake recogniser never says a result is final
    interim = page.evaluate(style)
    assert interim["color"] != typed["color"] and interim["font"] == typed["font"]
    page.locator("#ak-mic").click()
    expect(page.locator("#ak-text")).to_have_attribute("data-words", "final")
    page.wait_for_timeout(500)
    assert page.evaluate(style)["color"] == typed["color"]
    fits(page)


# ---- F-102 review fixes ---------------------------------------------------------------------------------------------------------------

def test_words_type_in_one_by_one_when_motion_is_allowed(phone, base_url, stt, monkeypatch):
    monkeypatch.setattr(ai, "TRANSPORT", Heard(delay=0.1, text="one two three four five six seven eight nine ten eleven twelve"))
    page = phone(NO_SPEECH + FAKE_MIC, motion="no-preference")
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.evaluate("""() => { window.__seen = []; const b = document.getElementById('ak-text');
        new MutationObserver(() => {}).observe(b, {attributes: true});
        setInterval(() => window.__seen.push([b.value, b.classList.contains('is-typing-in'), b.getAttribute('data-words')]), 40); }""")
    record_and_stop(page)
    expect(page.locator("#ak-mic-status")).to_contain_text("Added what you said", timeout=9000)
    seen = page.evaluate("window.__seen")
    lengths = sorted({len(v.split()) for v, _, _ in seen if v})
    assert len(lengths) >= 4 and 12 in lengths                              # words arrived over time, not all at once
    assert any(typing and w == "interim" for v, typing, w in seen if v)      # the class and the lighter look are on while they come in
    final = seen[-1]
    assert final[1] is False and final[2] == "final"


def test_a_piece_that_finds_the_line_busy_is_tried_again_in_order(phone, base_url, monkeypatch):
    import json
    monkeypatch.setenv("SARVAM_API_KEY", "sk-test")
    monkeypatch.setattr(ai, "TRANSPORT", lambda url, headers, body, timeout: (200, json.dumps({"transcript": "after the wait", "language_code": "en-IN"})))
    real, calls = ai.transcribe, []

    def flaky(*a, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise ai.AIError(ai.BUSY, "busy")
        return real(*a, **kw)
    monkeypatch.setattr(ai, "transcribe", flaky)
    page = phone(NO_SPEECH + FAKE_MIC)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    record_and_stop(page)
    expect(page.locator("#ak-text")).to_have_value("after the wait", timeout=12000)
    assert len(calls) == 2


def test_a_rotation_that_cannot_start_ends_the_recording_with_what_was_said(phone, base_url, stt, monkeypatch):
    monkeypatch.setattr(ai, "TRANSPORT", Heard(delay=0.1))
    breaks = "(() => { const Real = window.MediaRecorder; window.__starts = 0; window.MediaRecorder = class extends Real { start(...a) { window.__starts++; if (window.__starts === 2) throw new Error('no'); return super.start(...a); } }; })();"
    page = phone(NO_SPEECH + FAKE_MIC + breaks)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.evaluate("document.getElementById('ak-mic').dataset.pieceSecs = '1'")
    page.locator("#ak-mic").click()
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"))
    expect(page.locator("#ak-mic")).not_to_have_class(re.compile("is-recording"), timeout=6000)      # the second recorder would not start: the recording closed
    expect(page.locator("#ak-text")).to_have_value(HEARD, timeout=6000)                               # what was said up to then is kept
    expect(page.locator("#ak-mic")).to_be_enabled()
    assert page.evaluate("window.__starts") == 2


def test_hiding_the_page_finishes_the_piece_and_cancel_returns_focus_to_the_mic(phone, base_url, stt):
    page = phone(NO_SPEECH + FAKE_MIC)
    page.goto(f"{base_url}/trip/ask?day={DAY}")
    page.locator("#ak-mic").click()
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"))
    page.wait_for_timeout(1300)
    page.evaluate("() => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => true}); document.dispatchEvent(new Event('visibilitychange')); }")
    expect(page.locator("#ak-text")).to_have_value(HEARD, timeout=6000)                  # the piece was sent without waiting for the 25 s timer
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"))             # and recording goes on
    page.locator("#ak-rec-cancel").click()
    expect(page.locator("#ak-mic")).not_to_have_class(re.compile("is-recording"))
    expect(page.locator("#ak-mic")).to_be_focused()
