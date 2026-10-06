"""F-104: Ask is a sheet over the day, in a real browser at 390 and 320. The centre Ask tab opens a glass sheet that grows out of the button over the day (and over Family),
with the day already chosen; the fake microphone talks, Done shows the proposal in the sheet, a question chip is one tap, Apply closes it and the new block glows on the grid.
Swipe down, the scrim and Escape close it. /trip/ask still works as a page. A fake model and a fake speech service answer (nothing reaches Azure or Sarvam)."""
import json
import re
import time
import uuid

import pytest
from playwright.sync_api import expect

from gitaway import ai
from tests import canvas_samples as samples
from tests.test_speak import answer, op
from tests_browser.helpers import PHONE
from tests_browser.test_ask_box import FAKE_MIC, HEARD, NO_SPEECH
from tests_browser.test_phone_polish import SMALL_CONTROLS, SMALL_TEXT

DAY = 1
SIZES = [(390, 844), (320, 640)]


class Voice:
    """One `ai.TRANSPORT` for the speech service (answers HEARD) and the model (`chat`)."""

    def __init__(self, chat, words=HEARD, delay=0.3):
        self.chat, self.words, self.delay, self.heard = chat, words, delay, 0

    def __call__(self, url, headers, body, timeout):
        if "transcriptions" in url:
            time.sleep(self.delay)
            self.heard += 1
            return 200, json.dumps({"text": self.words})
        return self.chat(url, headers, body, timeout)


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "stt-test")
    monkeypatch.setenv("SARVAM_API_KEY", "")
    chat = samples.FakeAzure(answer(op("add_plan", title="Pool")))        # no time: it asks, and the question is a chip
    voice = Voice(chat)
    monkeypatch.setattr(ai, "TRANSPORT", voice)
    return voice


@pytest.fixture
def phone(browser, base_url):
    contexts = []

    def make(init_script=FAKE_MIC, size=(390, 844), motion="reduce", mail="ari.rivera@example.com", js=True, seed=True):
        ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, reduced_motion=motion, has_touch=True, is_mobile=True, java_script_enabled=js)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        if init_script:
            ctx.add_init_script(init_script)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        if seed:
            ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
            for id_, start, end, title, kind in (("a1", "12:00", "13:00", "Lunch", "food"), ("a2", "15:00", "17:00", "Griffith Observatory", "culture")):
                ctx.request.post(f"{base_url}/calendar/activities", form={"id": id_, "day": str(DAY), "start": start, "end": end, "title": title, "kind": kind}, max_redirects=0)
        return ctx.new_page()

    yield make
    for c in contexts:
        c.close()


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def day_page(page, base_url, day=DAY):
    page.goto(f"{base_url}/trip/canvas?day={day}")
    page.wait_for_selector(".cz-view[data-level=day]")
    page.wait_for_function("document.getElementById('ph-tab-ask').getAttribute('href').indexOf('day=') > 0")


def open_sheet(page):
    page.wait_for_timeout(400)        # the box was fetched ahead, as it is on a real phone
    page.locator("#ph-tab-ask").click()
    expect(page.locator("#ak-sheet")).to_be_visible()


def talk_and_done(page):
    """The mic starts by itself on open; talk for a moment (the fake mic), then Done: it stops, waits for the words, and sends them."""
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"))
    page.wait_for_timeout(1200)
    page.locator("#ak-go").click()


def answer_chips(page):
    """Tap a chip that is not the suggested one until the preview shows."""
    for _ in range(4):
        page.wait_for_selector("#ak-questions-form:not([data-old]), #ak-prop")
        if page.locator("#ak-prop").count():
            return
        page.evaluate("document.getElementById('ak-questions-form').setAttribute('data-old', '1')")        # so the next one is not mistaken for this one
        page.locator("#ak-questions-form .ak-opt:not(:has(input:checked))").first.click()


@pytest.mark.parametrize("size", SIZES, ids=["390", "320"])
def test_the_tab_opens_a_sheet_over_the_day_and_talking_ends_in_a_block_on_the_grid(phone, base_url, model, size):
    page = phone(size=size)
    day_page(page, base_url)
    url = page.url
    expect(page.locator(".cz-gb")).to_have_count(2)
    open_sheet(page)
    assert page.url == url and page.locator("#cz-title").count() == 1                     # no navigation: the day is still there
    sheet = page.locator("#ak-sheet")
    box = sheet.bounding_box()
    assert box["y"] > 90 and box["y"] + box["height"] <= size[1] and box["x"] >= 0 and box["x"] + box["width"] <= size[0]        # the day's top stays visible above it
    assert page.locator("#cz-title").bounding_box()["y"] + 10 < box["y"]
    expect(page.locator("#ak-chip-label")).to_have_text("Sat Oct 17")                     # the day being looked at is chosen
    for gone in ("#tp-title-h", "select", "#ak-hint:visible", ".ak-fine"):
        assert sheet.locator(gone).count() == 0, gone
    assert sheet.locator("button:visible").count() <= 5                                      # chip, paste, mic (+ cancel while recording), done
    expect(page.locator("#ak-mic")).to_have_class(re.compile("is-recording"))              # listening started on open (the tap was the user's gesture)
    assert overflow(page) <= 0 and page.evaluate(SMALL_TEXT) == [] and page.evaluate(SMALL_CONTROLS) == []
    talk_and_done(page)
    expect(page.locator("#ak-questions-form")).to_be_visible()                              # "What time is Pool?" as chips
    expect(page.locator("#ak-sheet")).to_contain_text("What time is Pool?")
    assert sheet.bounding_box()["y"] > 90
    answer_chips(page)
    expect(page.locator('.ak-chip[data-kind="new"]')).to_contain_text("Pool")
    expect(page.locator("#ak-apply")).to_have_text("Apply")
    expect(page.locator("#ak-change")).to_be_visible()
    assert overflow(page) <= 0 and page.evaluate(SMALL_TEXT) == [] and page.evaluate(SMALL_CONTROLS) == []
    page.locator("#ak-apply").click()
    expect(page.locator("#ak-sheet")).to_have_count(0)                                      # closed
    expect(page.locator('.cz-gb[data-title="Pool"]')).to_be_visible()                       # the day behind it was brought up to date
    expect(page.locator(".cz-gb.ak-fresh")).to_have_count(1)                                # and the new block glows for a moment
    expect(page.locator("#ak-toast")).to_contain_text("Added 1 plan")
    expect(page.locator("#ak-toast")).to_contain_text("The family has been told")
    assert page.url == url and overflow(page) <= 0
    expect(page.locator(".cz-gb.ak-fresh")).to_have_count(0, timeout=4000)
    expect(page.locator("#ph-tab-ask")).to_be_focused()


def test_the_sheet_grows_out_of_the_button_and_is_calm_under_reduced_motion(phone, base_url, model):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    page.wait_for_timeout(400)
    page.evaluate("""() => { document.getElementById('ph-tab-ask').click(); }""")
    page.wait_for_selector("#ak-sheet")
    info = page.evaluate("""() => { const s = document.getElementById('ak-sheet'), r = s.getBoundingClientRect(), b = document.querySelector('#ph-tab-ask .ph-ti').getBoundingClientRect();
        const o = getComputedStyle(s).transformOrigin.split(' ').map(parseFloat);
        return { anims: s.getAnimations().length, ox: s.offsetLeft + o[0], oy: s.offsetTop + o[1], bx: b.left + b.width / 2, by: b.top + b.height / 2 }; }""")
    assert info["anims"] >= 1                                                                # it animates in
    assert abs(info["ox"] - info["bx"]) < 3 and abs(info["oy"] - info["by"]) < 3             # from the Ask button
    page.wait_for_timeout(500)
    page.keyboard.press("Escape")
    page.wait_for_function("document.getElementById('ak-sheet') === null", timeout=3000)
    calm = phone(motion="reduce")
    day_page(calm, base_url)
    open_sheet(calm)
    assert calm.evaluate("document.getElementById('ak-sheet').getAnimations().length") == 0
    calm.keyboard.press("Escape")
    expect(calm.locator("#ak-sheet")).to_have_count(0)


@pytest.mark.parametrize("size", SIZES, ids=["390", "320"])
def test_swipe_down_the_scrim_and_escape_close_it_and_the_text_is_not_lost_by_a_mis_tap(phone, base_url, model, size):
    page = phone(size=size)
    day_page(page, base_url)
    open_sheet(page)
    grab = page.locator("#ak-grab").bounding_box()
    x, y = grab["x"] + grab["width"] / 2, grab["y"] + grab["height"] / 2
    page.mouse.move(x, y)                                                                    # a small drag springs back
    page.mouse.down()
    for dy in (10, 20, 30, 40):                                                              # slowly, and not far
        page.mouse.move(x, y + dy)
        page.wait_for_timeout(90)
    page.mouse.up()
    page.wait_for_timeout(400)
    expect(page.locator("#ak-sheet")).to_be_visible()
    assert abs(page.locator("#ak-sheet").bounding_box()["y"] - page.evaluate("document.getElementById('ak-sheet').getBoundingClientRect().top")) < 1
    page.mouse.move(x, y)                                                                    # a flick down closes it
    page.mouse.down()
    page.mouse.move(x, y + 80, steps=2)
    page.mouse.move(x, y + 260, steps=3)
    page.mouse.up()
    expect(page.locator("#ak-sheet")).to_have_count(0)
    open_sheet(page)
    page.mouse.click(size[0] / 2, 40)                                                        # the scrim
    expect(page.locator("#ak-sheet")).to_have_count(0)
    open_sheet(page)
    page.keyboard.press("Escape")
    expect(page.locator("#ak-sheet")).to_have_count(0)
    assert page.locator(".cz-view[data-level=day]").count() == 1 and page.url.endswith(f"day={DAY}")


def test_the_date_chip_changes_the_day_and_apply_shows_that_day(phone, base_url, model):
    page = phone()
    day_page(page, base_url)
    open_sheet(page)
    expect(page.locator("#ak-days-pick")).to_be_hidden()
    page.locator("#ak-chip").click()
    expect(page.locator("#ak-days-pick")).to_be_visible()
    page.locator('.ak-dpick[data-d="2"]').click()
    expect(page.locator("#ak-chip-label")).to_contain_text("Sun Oct 18")
    expect(page.locator("#ak-days-pick")).to_be_hidden()
    assert page.locator("#ak-day").input_value() == "2"
    page.locator("#ak-text").fill("add pool")                                                # typing works whether or not the mic started
    page.locator("#ak-mic").click() if page.locator("#ak-mic").get_attribute("aria-pressed") == "true" else None
    page.locator("#ak-go").click()
    answer_chips(page)
    page.locator("#ak-apply").click()
    expect(page.locator("#ak-sheet")).to_have_count(0)
    expect(page.locator(".cz-view[data-level=day]")).to_have_attribute("data-day", "2")      # the day it went onto is the one in view now
    expect(page.locator('.cz-gb[data-title="Pool"]')).to_be_visible()


def test_it_opens_over_family_and_apply_leaves_a_link_to_the_day(phone, base_url, model):
    page = phone()
    page.goto(f"{base_url}/trip/family")
    page.wait_for_timeout(500)
    page.locator("#ph-tab-ask").click()
    expect(page.locator("#ak-sheet")).to_be_visible()
    assert page.url.endswith("/trip/family") and page.locator("#ph-tab-family[aria-current=page]").count() == 1
    expect(page.locator("#ak-chip-label")).to_have_text(re.compile("Any day|today|Oct"))
    talk_and_done(page)
    answer_chips(page)
    page.locator("#ak-apply").click()
    expect(page.locator("#ak-sheet")).to_have_count(0)
    expect(page.locator("#ak-toast")).to_contain_text("Added 1 plan")
    expect(page.locator("#ak-toast a")).to_have_text("See the day")
    page.locator("#ak-toast a").click()
    page.wait_for_url(re.compile(r"/trip/canvas\?day=\d"))
    expect(page.locator('.cz-gb[data-title="Pool"]')).to_be_visible()


def test_a_failure_keeps_the_words_in_the_sheet(phone, base_url, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    monkeypatch.setattr(ai, "TRANSPORT", samples.FakeAzure(failure=TimeoutError("slow")))
    page = phone(NO_SPEECH)
    day_page(page, base_url)
    open_sheet(page)
    page.locator("#ak-text").fill("add pool at 3")
    page.locator("#ak-go").click()
    expect(page.locator("#ak-error")).to_contain_text("took too long")
    expect(page.locator("#ak-text")).to_have_value("add pool at 3")
    expect(page.locator("#ak-go")).to_be_enabled()
    expect(page.locator("#ak-sheet")).to_be_visible()


def test_without_recording_or_speech_the_keyboard_hint_shows_and_with_it_it_does_not(phone, base_url, model):
    page = phone(NO_SPEECH + "delete window.MediaRecorder;")
    day_page(page, base_url)
    open_sheet(page)
    expect(page.locator("#ak-hint")).to_be_visible()
    expect(page.locator("#ak-mic")).to_be_hidden()
    expect(page.locator("#ak-text")).to_be_focused()
    page.keyboard.press("Escape")
    ok = phone()
    day_page(ok, base_url)
    open_sheet(ok)
    expect(ok.locator("#ak-hint")).to_be_hidden()


def test_a_paste_icon_fills_the_note_and_done_waits_for_a_recording_to_be_written(phone, base_url, model):
    page = phone()
    day_page(page, base_url)
    open_sheet(page)
    expect(page.locator("#ak-paste")).to_have_attribute("aria-label", "Paste")
    assert page.locator("#ak-paste").bounding_box()["width"] >= 44
    talk_and_done(page)                                                                      # Done while recording: stop, wait for the words, then send
    expect(page.locator("#ak-questions-form, #ak-prop")).to_be_visible()
    assert model.heard == 1


def test_the_page_still_works_with_no_script_and_a_viewer_gets_the_page_not_a_sheet(phone, base_url, model):
    page = phone(js=False)
    page.goto(f"{base_url}/trip/canvas?day={DAY}")
    page.locator("#ph-tab-ask").click()
    page.wait_for_url(re.compile(r"/trip/ask"))
    expect(page.locator("#tp-title-h")).to_have_text("Ask GitAway")
    expect(page.locator("#ak-day")).to_be_visible()
    owner = phone()
    mail = f"vi.sheet@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    viewer = phone(mail=mail, seed=False)
    viewer.goto(f"{base_url}/trip/canvas?day={DAY}")
    viewer.wait_for_selector(".cz-view[data-level=day]")
    viewer.wait_for_timeout(400)
    assert viewer.locator("#ph-tab-ask").get_attribute("data-ask") is None
    viewer.locator("#ph-tab-ask").click()
    viewer.wait_for_url(re.compile(r"/trip/ask"))
    expect(viewer.locator("#ak-viewer")).to_be_visible()


def test_every_step_of_the_microphone_is_reported_to_the_server_log_without_audio_or_words(phone, base_url, model):
    page = phone()
    events = []
    page.on("request", lambda r: events.append(json.loads(r.post_data)) if r.url.endswith("/trip/ask/mic-event") else None)
    day_page(page, base_url)
    open_sheet(page)
    talk_and_done(page)
    page.wait_for_selector("#ak-questions-form, #ak-prop")
    page.wait_for_timeout(300)
    stages = [(e["stage"], e["name"]) for e in events]
    assert stages[:2] == [("tap", "mic"), ("mode", "record")] and ("gum", "granted") in stages and ("recorder", "start") in stages
    assert ("piece", "upload") in stages and ("result", "ok") in stages
    mode = [e for e in events if e["stage"] == "mode"][0]["detail"]
    assert "canRecord=1" in mode and "recognition=" in mode and "ios=" in mode and "installed=" in mode and "server=1" in mode
    assert "bytes=" in [e for e in events if e["stage"] == "piece"][0]["detail"]
    assert HEARD not in json.dumps(events)                                                      # no words, no audio


def test_a_blocked_microphone_says_so_in_plain_words_and_reports_it(phone, base_url, model):
    refused = "navigator.mediaDevices.getUserMedia = () => Promise.reject(Object.assign(new Error('no'), {name: 'NotAllowedError'}));"
    page = phone(refused)
    events = []
    page.on("request", lambda r: events.append(json.loads(r.post_data)) if r.url.endswith("/trip/ask/mic-event") else None)
    day_page(page, base_url)
    open_sheet(page)
    expect(page.locator("#ak-mic-status")).to_contain_text("The microphone is blocked for GitAway. Allow it in Settings > GitAway (or Safari > Microphone)")
    page.wait_for_timeout(300)
    assert ("gum", "refused") in [(e["stage"], e["name"]) for e in events] and [e for e in events if e["stage"] == "gum"][0]["detail"] == "NotAllowedError"


def test_screenshots(phone, base_url, model):
    """F104_SHOTS=<folder> pixi run pytest -p no:randomly tests_browser/test_ask_sheet.py -k screenshots"""
    import os
    folder = os.environ.get("F104_SHOTS")
    if not folder:
        pytest.skip("set F104_SHOTS to a folder to take the screenshots")
    os.makedirs(folder, exist_ok=True)
    page = phone(motion="reduce")
    day_page(page, base_url)
    open_sheet(page)
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(folder, "sheet-open-390.png"))
    talk_and_done(page)
    answer_chips(page)
    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(folder, "sheet-proposal-390.png"))
