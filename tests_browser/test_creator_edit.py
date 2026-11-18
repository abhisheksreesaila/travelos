"""F-259: a creator opens a draft's guide, taps "Edit details", changes the details in the guide's own look (the v2 editor, not the old form), moves and removes a stop, and sees it all saved in the
book. The post is the recorded "48 Hours in Lisbon" (tests/fixtures/creator_import), the model's answer recorded too. Phone (390) and laptop (1440), light and dark; every control is 48px or more.
Set F259_SHOTS=1 to save docs/report/f259-*.png."""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import ai, safefetch
from tests.creator_import_support import Model, recorded
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
IDS = ["390", "1440"]


def shot(page, name, full=False):
    if os.getenv("F259_SHOTS"):
        page.wait_for_timeout(900)      # the page change settles first
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f259-{name}.png"), full_page=full)


@pytest.fixture
def lisbon(monkeypatch):
    url, web, answer = recorded()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model(answer))
    monkeypatch.setattr(safefetch, "TRANSPORT", web)
    return url


def drafted(browser, base_url, viewport, link, dark=False):
    """A signed-in creator's context with the recorded post already drafted: (context, page, the draft's id)."""
    c = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE)
    c.set_default_timeout(15000)
    c.request.post(f"{base_url}/signin", form={"email": "maya.chen@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    r = c.request.post(f"{base_url}/creators/import", form={"do": "draft", "link": link}, headers={"X-Magic": "1"})
    event = [json.loads(line) for line in r.text().splitlines() if line.strip()][-1]
    if dark:
        c.add_init_script("try { localStorage.setItem('ga-mode', 'dark'); } catch (e) {}")
    return c, c.new_page(), event["id"]


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def too_small(page, selector):
    return page.evaluate("""(sel) => [...document.querySelectorAll(sel)].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < 47.5; })
        .map(e => (e.getAttribute('aria-label') || e.getAttribute('name') || e.id || e.textContent.trim()).slice(0, 40))""", selector)


def stop_names(page, day=0):
    return page.eval_on_selector_all(f"#ed-day-{day} input[name$='_name']", "els => els.map(e => e.value)")


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_guides_edit_details_opens_the_v2_editor_and_what_is_changed_is_saved_in_the_guide(lisbon, browser, base_url, viewport):
    ctx, page, did = drafted(browser, base_url, viewport, lisbon)
    page.goto(f"{base_url}/creators/import/{did}/guide")
    page.click("#detailsBtn")
    page.wait_for_url(f"**/creators/import/{did}")
    expect(page.locator("main .ed")).to_be_visible()
    expect(page.locator("h1")).to_have_text("The details of your guide")
    assert page.locator("link[href*='scrapbook.css']").count() == 0 and page.locator("link[href*='cvedit.css']").count() == 1      # the old form's look is not on this page
    assert page.evaluate("getComputedStyle(document.querySelector('h1')).fontFamily").startswith("Inter")      # F-296: heavy Inter headlines
    assert overflow(page) <= 1
    assert not too_small(page, ".ed .go, .ed .tonal, .ed .ed-op, .ed .ed-chip, .ed .ed-in, .ed .ed-cover, .ed summary"), "every control is 48px or more"
    shot(page, f"editor-{viewport['width']}-light")
    # the details: the title, the first day's heading, a stop's time and note; the first two stops swap; the third is removed
    first, second, third = stop_names(page)[:3]
    page.fill("#ci-title", "Lisbon in two days")
    page.fill("input[name='d0_title']", "Belém, slowly")
    page.fill("input[name='d0s0_time']", "9:00 AM")
    page.fill("input[name='d0s0_note']", "Go before the queues")
    page.click(f"button[aria-label='Move {first} down']")
    page.wait_for_url(f"**/creators/import/{did}")
    expect(page.locator("#ci-title")).to_have_value("Lisbon in two days")      # a move saves the rest of the form too: nothing typed is lost
    assert stop_names(page)[:3] == [second, first, third]
    page.click(f"button[aria-label='Remove {third} from day 1']")
    page.wait_for_url(f"**/creators/import/{did}")
    assert third not in stop_names(page)
    page.click("#ed-save-book")
    page.wait_for_url(f"**/creators/import/{did}/guide")
    expect(page.locator("h1 .ed")).to_have_text("Lisbon in two days")
    expect(page.locator("#g-day1")).to_contain_text("Belém, slowly")
    shot(page, f"guide-{viewport['width']}")
    # the details were really kept: back in the editor they are still there
    page.click("#detailsBtn")
    expect(page.locator("input[name='d0s1_note']")).to_have_value("Go before the queues")      # the stop that moved down took its time and note with it
    expect(page.locator("input[name='d0s1_time']")).to_have_value("9:00 AM")
    assert stop_names(page)[:2] == [second, first] and third not in stop_names(page)
    ctx.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_editor_in_dark_mode_keeps_its_contrast_and_fits(lisbon, browser, base_url, viewport):
    ctx, page, did = drafted(browser, base_url, viewport, lisbon, dark=True)
    page.goto(f"{base_url}/creators/import/{did}")
    expect(page.locator("main .ed")).to_be_visible()
    assert page.evaluate("document.documentElement.dataset.mode") == "dark"
    assert overflow(page) <= 1
    low = page.evaluate("""() => {
      const lum = (c) => { const v = c.match(/[\\d.]+/g).slice(0, 3).map(Number).map(x => { x /= 255; return x <= .03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4; }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
      const bg = (e) => { for (; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; const a = c.match(/[\\d.]+/g); if (a && (a.length < 4 || +a[3] > .9)) return c; } return 'rgb(255,255,255)'; };
      const bad = [];
      document.querySelectorAll('.ed label, .ed h1, .ed h2, .ed p, .ed .ed-in, .ed .tonal, .ed .go, .ed .tag').forEach(e => {
        if (!e.textContent.trim() && !e.value) return;
        const f = lum(getComputedStyle(e).color), b = lum(bg(e)), r = (Math.max(f, b) + .05) / (Math.min(f, b) + .05);
        if (r < 4.5 && getComputedStyle(e).visibility !== 'hidden') bad.push([e.className || e.tagName, Math.round(r * 100) / 100]);
      });
      return bad; }""")
    assert not low, low
    shot(page, f"editor-{viewport['width']}-dark")
    ctx.close()


def test_a_refused_publish_links_to_the_details(lisbon, browser, base_url):
    ctx, page, did = drafted(browser, base_url, PHONE, lisbon)
    page.goto(f"{base_url}/creators/import/{did}/guide")
    page.click("#pubBtn")
    page.click("#mine")
    page.evaluate("document.getElementById('mine').setAttribute('aria-checked', 'true'); document.getElementById('pubGo').disabled = false")
    page.route(f"**/creators/import/{did}", lambda r: r.fulfill(status=422, content_type="application/json", body=json.dumps({"ok": False, "error": "Nothing yet.", "editor": f"/creators/import/{did}"}))
              if r.request.method == "POST" else r.continue_())
    page.click("#pubGo")
    expect(page.locator("#pubError")).to_contain_text("Nothing yet.")
    page.click("#pubError a")
    page.wait_for_url(f"**/creators/import/{did}")
    expect(page.locator("h1")).to_have_text("The details of your guide")
    ctx.close()
