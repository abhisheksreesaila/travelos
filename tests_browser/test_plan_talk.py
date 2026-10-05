"""F-091: talk on the block in a real browser at phone width. The microphone is faked in the page (an oscillator stream), and MediaRecorder records it for real: tap the
mic, see the recording bar, Cancel throws it away, Send posts it, the voice note shows with its length and plays in place; a text message and a photo; the badge on the
plan's day and the Family tab's label; no sideways scroll at 390 and 320, 44px targets, 13px text. The trip is the captain's Universal + California Adventure
messages through a canned model answer; nothing here reaches the network."""
import re

import pytest
from playwright.sync_api import expect

from tests.photo_files import image
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT
from tests_browser.test_trip_canvas import NARROW, canvas_page, model  # noqa: F401 - fixtures

FAKE_MIC = """(() => {
  navigator.mediaDevices.getUserMedia = async () => {
    const ctx = new AudioContext(); await ctx.resume();
    const osc = ctx.createOscillator(); const dest = ctx.createMediaStreamDestination();
    osc.connect(dest); osc.start();
    return dest.stream;
  };
})();"""


def lunch_chat(page, base_url):
    """Open the Universal day, find Lunch and go to its chat."""
    page.goto(f"{base_url}/trip/canvas?day=1")
    page.wait_for_selector(".cz-view[data-level=day]")
    part = page.locator(".cz-part", has_text="Lunch").first.get_attribute("data-part")
    act = page.locator(".cz-block").first.get_attribute("data-act")
    page.goto(f"{base_url}/trip/talk?act={act}&part={part}")
    page.wait_for_selector("#ft-compose")
    return act, part


def checks(page):
    assert page.evaluate(OVERFLOW) <= 0
    assert page.evaluate(SMALL_TEXT) == []
    assert page.evaluate(SMALL_CONTROLS) == []


@pytest.mark.parametrize("viewport", [None, NARROW], ids=["390", "320"])
def test_text_photo_and_a_recorded_voice_note_that_plays(canvas_page, base_url, viewport):
    page = canvas_page(**({"viewport": viewport} if viewport else {}))
    page.add_init_script(FAKE_MIC)
    act, part = lunch_chat(page, base_url)
    expect(page.locator("#pt-mic")).to_be_visible()
    expect(page.locator("#pt-photo-btn")).to_be_visible()
    expect(page.locator("#ft-empty")).to_be_visible()
    checks(page)

    # a text message
    page.locator("#ft-text").fill("Mario Kart right after lunch")
    page.locator("#ft-send").click()
    expect(page.locator("#ft-thread .ft-me")).to_contain_text("Mario Kart right after lunch")
    expect(page.locator("#ft-empty")).to_be_hidden()

    # Cancel throws a recording away
    page.locator("#pt-mic").click()
    expect(page.locator("#pt-rec")).to_be_visible()
    expect(page.locator("#ft-compose")).to_be_hidden()
    checks(page)
    page.wait_for_timeout(1300)
    assert page.locator("#pt-timer").inner_text() != "0:00"
    page.locator("#pt-cancel").click()
    expect(page.locator("#ft-compose")).to_be_visible()
    expect(page.locator("#pt-rec")).to_be_hidden()
    assert page.locator("#ft-thread .ft-msg").count() == 1

    # record, send, play
    page.locator("#pt-mic").click()
    expect(page.locator("#pt-rec")).to_be_visible()
    page.wait_for_timeout(1500)
    page.locator("#pt-rec-send").click()
    expect(page.locator("#ft-thread .vn")).to_have_count(1)
    expect(page.locator("#pt-rec")).to_be_hidden()
    vn = page.locator("#ft-thread .vn")
    expect(vn.locator("[data-vn=len]")).to_have_text(re.compile(r"^0:0[1-3]$"))
    kind = page.evaluate("fetch(document.querySelector('.vn audio').src).then(r => r.headers.get('content-type'))")
    assert kind in ("audio/mp4", "audio/webm")
    vn.locator(".vn-btn").click()
    page.wait_for_function("() => { const a = document.querySelector('.vn audio'); return a && a.currentTime > 0; }")
    expect(vn).to_have_class(re.compile("is-playing"))
    vn.locator(".vn-btn").click()
    expect(vn).not_to_have_class(re.compile("is-playing"))
    checks(page)

    # a photo
    page.locator("#pt-photo").set_input_files({"name": "canal.png", "mimeType": "image/png", "buffer": image("png")})
    expect(page.locator("#ft-thread .ft-photo")).to_have_count(1)
    expect(page.locator("#ft-error")).to_be_hidden()
    checks(page)

    # the badge on the plan's day, and the Family tab's label and player
    page.goto(f"{base_url}/trip/canvas?day=1")
    page.wait_for_selector(".cz-view[data-level=day]")
    badge = page.locator(f'.cz-part a.pt-badge[href*="part={part}"]')
    expect(badge).to_be_visible()
    expect(badge.locator(".pt-n")).to_have_text("3")
    checks(page)
    badge.click()
    expect(page.locator("#ft-thread .ft-msg")).to_have_count(3)
    page.goto(f"{base_url}/trip/family")
    expect(page.locator(".ft-on").first).to_contain_text("on Lunch")
    expect(page.locator("#ft-thread .vn")).to_have_count(1)
    checks(page)


def test_a_refused_photo_shows_a_plain_message(canvas_page, base_url):
    page = canvas_page()
    lunch_chat(page, base_url)
    page.locator("#pt-photo").set_input_files({"name": "notes.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.7 not a picture"})
    expect(page.locator("#ft-error")).to_contain_text("Only JPEG")
    assert page.locator("#ft-thread .ft-msg").count() == 0


def test_the_mic_is_hidden_where_the_browser_cannot_record(canvas_page, base_url):
    page = canvas_page()
    page.add_init_script("delete window.MediaRecorder;")
    lunch_chat(page, base_url)
    expect(page.locator("#pt-mic")).to_be_hidden()
    expect(page.locator("#pt-photo-btn")).to_be_visible()


def test_a_blocked_microphone_says_so(canvas_page, base_url):
    page = canvas_page()
    page.add_init_script("navigator.mediaDevices.getUserMedia = () => Promise.reject(Object.assign(new Error('x'), {name: 'NotAllowedError'}));")
    lunch_chat(page, base_url)
    page.locator("#pt-mic").click()
    expect(page.locator("#ft-error")).to_contain_text("microphone is blocked")
    expect(page.locator("#ft-compose")).to_be_visible()
