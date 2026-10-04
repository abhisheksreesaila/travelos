"""F-080: Add to the trip in a real browser at phone width: paste the captain's Universal Studios and California Adventure messages, press Convert (a fake model
answers), see what was found, answer the questions, Add to trip, open the block, see its steps and notes, mark a step done. Nothing scrolls sideways."""
import time

import pytest
from playwright.sync_api import expect

from gitaway import ai
from tests import canvas_samples as samples
from tests_browser.helpers import PHONE

NARROW = {"width": 320, "height": 640}


class SlowAzure(samples.FakeAzure):
    delay = 0.8

    def __call__(self, url, headers, body, timeout):
        time.sleep(self.delay)      # long enough to see the waiting state
        return super().__call__(url, headers, body, timeout)


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    fake = SlowAzure()
    monkeypatch.setattr(ai, "TRANSPORT", fake)
    return fake


@pytest.fixture
def phone(browser, base_url):
    contexts = []

    def make(viewport=PHONE):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=True, is_mobile=True)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
        return ctx.new_page()

    yield make
    for c in contexts:
        c.close()


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def test_paste_convert_answer_add_and_use_the_block(phone, base_url, model):
    page = phone()
    page.goto(f"{base_url}/trip")
    page.locator("#tp-add-trip").click()
    expect(page.locator("#cv-text")).to_be_visible()
    assert overflow(page) <= 0
    page.locator("#cv-text").fill(samples.text())
    state = page.evaluate("""() => { const f = document.getElementById('cv-form'); f.requestSubmit(document.getElementById('cv-convert'));
        return new Promise(r => setTimeout(() => r({disabled: document.getElementById('cv-convert').disabled, shown: !document.getElementById('cv-progress').hidden,
        words: document.getElementById('cv-progress').textContent, busy: f.getAttribute('aria-busy')}), 150)); }""")
    assert state["disabled"] and state["shown"] and "Reading your messages" in state["words"] and state["busy"] == "true"    # the page says it is working
    expect(page.locator("#cv-stats")).to_be_visible()
    assert page.locator("#cv-stats .cv-stat-n").all_inner_texts() == ["2", "8", "23"]
    expect(page.locator("#cv-tidied")).to_contain_text("Studio Tour, Simpsons")
    assert overflow(page) <= 0

    page.locator("#cv-edit").click()                                        # Edit text: back with the text intact
    expect(page.locator("#cv-text")).to_have_value(samples.text())
    page.locator("#cv-convert").click()
    expect(page.locator("#cv-stats")).to_be_visible()
    page.locator("#cv-next").click()
    expect(page.locator("#cv-questions-form")).to_be_visible()
    assert overflow(page) <= 0
    page.locator("#cv-back").click()                                        # Back: what we found again
    expect(page.locator("#cv-stats")).to_be_visible()
    page.locator("#cv-next").click()

    page.locator('.cv-whoq[data-token="R"] input[value="keep"]').check()
    page.locator('.cv-whoq[data-token="B"] input[value="new"]').check()
    page.locator('.cv-whoq[data-token="B"] .cv-new').fill("Bhoomija")
    page.locator('[data-park="0"] .cv-day-chip').nth(1).click()             # Sat
    page.locator('[data-park="1"] .cv-day-chip').nth(3).click()             # Mon
    page.locator("#cv-add").click()

    expect(page.locator("#tp-toast")).to_contain_text("Universal Studios Hollywood")
    page.locator('.tp-card[href*="/trip/block"]').first.click()
    expect(page.locator("h1")).to_have_text("Universal Studios Hollywood")
    expect(page.locator(".cv-block-part")).to_have_count(4)
    expect(page.locator("#cv-tray")).to_contain_text("Studio Tour")
    assert overflow(page) <= 0
    mummy = page.locator(".cv-step-row", has_text="Revenge of the Mummy")
    mummy.get_by_role("button", name="Mark done").click()
    expect(page.locator(".cv-step-row.is-done", has_text="Revenge of the Mummy")).to_be_visible()
    kong = page.locator(".cv-step-row", has_text="King Kong")
    kong.get_by_role("button", name="Set aside").click()
    expect(page.locator("#cv-tray")).to_contain_text("King Kong")
    expect(page.locator(".cv-step-row", has_text="Hippogriff")).to_contain_text("Bhoomija")
    expect(page.locator(".cv-step-row", has_text="Hippogriff")).to_contain_text("H and B walk")
    page.locator("#cv-back-day").click()
    expect(page.locator("#tp-list")).to_contain_text("Universal Studios Hollywood")


def test_a_failed_conversion_keeps_the_text_and_says_so(phone, base_url, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k"), monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://e.example.com"), monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    monkeypatch.setattr(ai, "TRANSPORT", samples.FakeAzure(failure=TimeoutError("slow")))
    page = phone(NARROW)
    page.goto(f"{base_url}/trip/add")
    page.locator("#cv-text").fill(samples.text())
    page.locator("#cv-convert").click()
    expect(page.locator("#cv-error")).to_contain_text("took too long")
    expect(page.locator("#cv-text")).to_have_value(samples.text())
    expect(page.locator("#cv-convert")).to_be_enabled()
    assert overflow(page) <= 0


def test_the_site_keeps_answering_while_the_model_is_slow(phone, base_url, model):
    """The model call runs off the event loop: /healthz answers at once while a Convert is waiting for it."""
    import threading
    import urllib.request
    model.delay = 2.0
    page = phone()
    waits, stop = [], threading.Event()

    def poll():
        time.sleep(0.4)                   # the convert is now inside the fake model
        while not stop.is_set():
            start = time.monotonic()
            with urllib.request.urlopen(f"{base_url}/healthz", timeout=5) as r:
                assert r.status == 200
            waits.append(time.monotonic() - start)
            time.sleep(0.2)

    worker = threading.Thread(target=poll)
    worker.start()
    status = page.request.post(f"{base_url}/trip/add/convert", form={"text": samples.text()}).status
    stop.set()
    worker.join(10)
    assert status == 200 and model.sent       # the model really was asked
    assert len(waits) >= 3 and max(waits) < 0.5, waits
