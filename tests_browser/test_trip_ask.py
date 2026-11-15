"""F-241 in a real browser: "What are you after?" at phone (390) and laptop (1440), light and dark. The audit (look.py) holds: no sideways scroll, 48px targets on the phone, 4.5:1 text,
no glass. Tapping a chip picks it (its own colour fills, an aria-checked-style state the label shows); an idea fills the box; Search shows the matrix's skeleton at once (the POST is held
to see it) and then lands on the matrix with its squares; a sentence with no place stays and says so. F241_SHOTS=1 saves docs/report/f241-*.png."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
SENTENCE = "A family of 4, SFO to San Diego, Dec 12 to 16"


@pytest.fixture
def ask(browser, base_url):
    contexts = []

    def ask(viewport=DESKTOP, scheme="light", motion=False):
        phone = viewport is PHONE
        ctx = browser.new_context(viewport=viewport, color_scheme=scheme, reduced_motion="no-preference" if motion else "reduce", has_touch=phone, is_mobile=phone, service_workers="block")
        ctx.set_default_timeout(8000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ask.family@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.goto(base_url + "/", wait_until="networkidle")      # the front door sends a family with no trip here
        page.evaluate("(m) => document.documentElement.setAttribute('data-mode', m)", scheme)      # the site is light whatever the system says (mode.js); this is the dark button
        return page

    yield ask
    for c in contexts:
        c.close()


def shot(page, name):
    if os.getenv("F241_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f241-{name}.png"))


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_front_door_opens_the_ask_and_it_reads_fits_and_is_easy_to_tap(ask, viewport, scheme):
    page = ask(viewport, scheme)
    assert page.url.endswith("/plan/ask")
    expect(page.get_by_role("heading", name="What are you after?")).to_be_visible()
    seen = audit(page)
    assert seen["wide"] <= 1, "scrolls sideways"
    for key in ("small", "tiny", "low", "glass"):
        assert not seen[key], (key, seen[key][:6])
    assert page.locator(".ak-chip").count() == 9
    name = "phone" if viewport is PHONE else "laptop"
    shot(page, f"{name}-{scheme}")
    if os.getenv("F241_SHOTS") and scheme == "light":      # the skeleton Search shows, drawn without leaving the page (a screenshot waits for a pending navigation)
        page.evaluate("document.querySelector('.ak-wrap').classList.add('is-going')")
        page.wait_for_timeout(700)
        shot(page, f"{name}-skeleton")


def test_tapping_a_chip_picks_it_in_its_kind_colour_and_again_puts_it_back(ask):
    page = ask(PHONE)
    chip = page.locator(".ak-chip", has_text="Seafood")
    off = chip.evaluate("e => getComputedStyle(e).backgroundColor")
    chip.tap()
    expect(chip.locator("input")).to_be_checked()
    on = chip.evaluate("e => getComputedStyle(e).backgroundColor")
    assert on == "rgb(201, 42, 94)" and on != off      # food's rose
    assert chip.evaluate("e => getComputedStyle(e).color") == "rgb(255, 255, 255)"
    chip.tap()
    expect(chip.locator("input")).not_to_be_checked()
    assert chip.evaluate("e => getComputedStyle(e).backgroundColor") == off


def test_an_idea_fills_the_box_and_search_opens_the_matrix_on_it(ask):
    page = ask(DESKTOP)
    page.locator(".ak-ex").first.click()
    assert page.input_value("#ak-q") == page.locator(".ak-ex").first.inner_text()
    page.locator(".ak-chip", has_text="Vegetarian").click()
    page.get_by_role("button", name="Search").click()
    page.wait_for_url("**/plan/matrix?**")
    page.wait_for_selector(".mx-sq")
    assert page.locator(".mx-sq").count() >= 5
    page.goto(page.url.split("/plan/matrix")[0] + "/plan/ask")
    expect(page.locator(".ak-chip", has_text="Vegetarian").locator("input")).to_be_checked()      # kept for the family


def test_search_shows_the_matrixs_skeleton_at_once_while_the_matrix_loads(ask, base_url):
    page = ask(PHONE, motion=True)
    held = []      # the POST waits until the test has looked at the skeleton
    page.route("**/plan/ask", lambda route: held.append(route) if route.request.method == "POST" else route.continue_())
    page.fill("#ak-q", SENTENCE)
    page.get_by_role("button", name="Search").tap()
    seen = page.evaluate("""() => { const v = (s) => { const e = document.querySelector(s); return !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility === 'visible'; };
        return {skel: v('#ak-skel'), lanes: document.querySelectorAll('.ak-sk-lane').length, days: document.querySelectorAll('.ak-sk-day').length, chips: v('.ak-chips'), busy: document.getElementById('ak-go').getAttribute('aria-busy')}; }""")      # evaluate, not a locator: a locator waits for the pending navigation to end
    assert seen == {"skel": True, "lanes": 3, "days": 15, "chips": False, "busy": "true"}
    page.wait_for_timeout(300)      # lets Playwright deliver the held request (the sync API runs handlers while it waits)
    held[0].continue_()
    page.wait_for_url("**/plan/matrix?**")
    page.wait_for_selector(".mx-sq", state="attached")


def test_a_sentence_with_no_place_stays_on_the_ask_and_says_so_in_place(ask):
    page = ask(PHONE)
    page.fill("#ak-q", "somewhere warm")
    page.get_by_role("button", name="Search").tap()
    expect(page.get_by_role("alert")).to_contain_text("I could not find a place in that.")
    assert page.url.endswith("/plan/ask") and page.input_value("#ak-q") == "somewhere warm"
    shot(page, "phone-error")


def test_it_works_without_the_script(browser, base_url):
    ctx = browser.new_context(viewport=PHONE, java_script_enabled=False)
    ctx.request.post(f"{base_url}/signin", form={"email": "ask.nojs@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page = ctx.new_page()
    page.goto(base_url + "/plan/ask")
    page.fill("#ak-q", SENTENCE)
    page.locator(".ak-chip", has_text="Hikes").click()
    page.get_by_role("button", name="Search").click()
    page.wait_for_url("**/plan/matrix?**")
    ctx.close()
