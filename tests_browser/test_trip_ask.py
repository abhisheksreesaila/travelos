"""F-241, F-250 in a real browser: the v2 landing ("What are you after?") at phone (390) and laptop (1440), light and dark. The sentence is the search: every part a word that opens its
picker (a popover under the word on a laptop, a bottom sheet on a phone), no box to type in; changing a word changes the sentence; Search glides the sentence up, shows the results'
skeleton and lands on the matrix on exactly what the words said. The script's words (assets/js/v2.js `text`) say what the server's do (gitaway/v2sentence.py `words`)."""
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE


@pytest.fixture
def ask(browser, base_url):
    contexts = []

    def ask(viewport=DESKTOP, scheme="light", motion=False, url="/plan/ask", idle=True):
        phone = viewport is PHONE
        ctx = browser.new_context(viewport=viewport, color_scheme=scheme, reduced_motion="no-preference" if motion else "reduce", has_touch=phone, is_mobile=phone, service_workers="block")
        ctx.set_default_timeout(8000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ask.family@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.goto(base_url + url, wait_until="networkidle" if idle else "load")
        page.evaluate("(m) => document.documentElement.setAttribute('data-mode', m)", scheme)      # the site is light whatever the system says (mode.js); this is the dark button
        return page

    yield ask
    for c in contexts:
        c.close()


def word(page, k):
    return page.locator(f'#v2-sent .v2-w[data-k="{k}"]')


def words(page):
    return page.evaluate("() => [...document.querySelectorAll('#v2-sent .v2-w')].map(e => e.textContent)")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_landing_is_one_sentence_that_fits_with_no_box_to_type_in(ask, viewport, scheme):
    page = ask(viewport, scheme)
    assert page.url.endswith("/plan/ask")
    expect(word(page, "who")).to_have_text("A family of 4")
    assert page.locator("input[type=text], textarea").count() == 0
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")      # no sideways scroll
    assert page.evaluate("getComputedStyle(document.querySelector('#v2-sent')).fontFamily").startswith("Newsreader")
    assert page.evaluate("getComputedStyle(document.body).fontFamily").find("Inter") >= 0 or page.evaluate("getComputedStyle(document.querySelector('.v2')).fontFamily").find("Inter") >= 0
    assert page.errors == []


def test_every_word_opens_its_picker_and_a_change_rewrites_the_sentence(ask):
    page = ask()
    word(page, "who").click()
    expect(page.locator("#v2-pop")).to_be_visible()
    page.locator('#v2-pop [data-st="kids"][data-dv="-1"]').click()
    expect(word(page, "who")).to_have_text("A family of 3")
    page.locator('#v2-pop [data-st="adults"][data-dv="1"]').click()
    expect(word(page, "who")).to_have_text("A family of 4")
    page.locator("#v2-pop .v2-done").click()
    expect(page.locator("#v2-pop")).to_be_hidden()
    word(page, "from").click()
    page.locator('#v2-pop [data-home="OAK"]').click()
    expect(word(page, "from")).to_have_text("OAK")
    page.keyboard.press("Escape")
    word(page, "where").click()
    page.locator('#v2-pop [data-to="Los Angeles"]').click()
    expect(word(page, "where")).to_have_text("Los Angeles, or nearby")
    page.locator('#v2-pop [data-tog="nearby"]').click()
    expect(word(page, "where")).to_have_text("Los Angeles")
    page.keyboard.press("Escape")
    word(page, "flex").click()
    page.locator('#v2-pop [data-flex="0"]').click()
    expect(word(page, "flex")).to_have_text("on the dot")
    page.keyboard.press("Escape")
    word(page, "nights").click()
    page.locator('#v2-pop input[type=range]').fill("6")
    expect(word(page, "nights")).to_have_text("6 nights")
    page.keyboard.press("Escape")
    word(page, "budget").click()
    page.locator('#v2-pop [data-tog="anybudget"]').click()
    page.locator('#v2-pop input[type=range]').fill("3000")
    expect(word(page, "budget")).to_have_text("$3,000")
    page.keyboard.press("Escape")
    word(page, "into").click()
    page.locator('#v2-pop [data-multi="hikes"]').click()
    page.locator('#v2-pop [data-multi="beaches"]').click()
    expect(word(page, "into")).to_have_text("beaches & hikes")
    page.keyboard.press("Escape")


def test_a_day_is_picked_from_a_calendar_that_cannot_reach_the_past(ask):
    page = ask()
    word(page, "start").click()
    page.locator("#v2-pop [data-month]").first.click()      # back a month: the days already gone cannot be picked
    assert page.locator("#v2-pop .v2-cal button:disabled").count() >= 1
    page.locator("#v2-pop [data-month]").last.click()
    day = page.locator("#v2-pop .v2-cal button:not(:disabled)").nth(10)
    iso = day.get_attribute("data-v")
    day.click()
    expect(word(page, "start")).to_contain_text(re.sub(r"^\d{4}-0?(\d+)-0?(\d+)$", r"\2", iso))
    page.locator('#v2-pop [data-month]').last.click()
    assert page.locator("#v2-pop .v2-cal button").count() >= 28


def test_on_a_phone_a_picker_is_a_sheet_from_the_bottom_and_on_a_laptop_a_popover_under_its_word(ask):
    page = ask(PHONE)
    word(page, "nights").click()
    box, vh = page.locator("#v2-pop").bounding_box(), page.viewport_size["height"]
    assert page.locator("#v2-pop.as-sheet").count() == 1 and box["y"] + box["height"] > vh - 20 and box["width"] > 340
    page = ask(DESKTOP)
    w = word(page, "nights")
    w.click()
    pop, at = page.locator("#v2-pop").bounding_box(), w.bounding_box()
    assert page.locator("#v2-pop.as-sheet").count() == 0 and pop["y"] >= at["y"] + at["height"] - 2 and pop["width"] <= 381


def test_the_scripts_words_say_what_the_servers_say(ask):
    """Change one, change the other: after changing a word the script's text equals a fresh server draw of the same address."""
    page = ask(url="/plan/ask?to=Lake+Tahoe&home=OAK&d=2027-01-09&r=2027-01-13&a=2&k=&x=1&nb=0&b=3000")
    server = words(page)
    assert server == ["The two of us", "OAK", "Lake Tahoe", "Sat, Jan 9", "give or take 1 day", "4 nights", "$3,000", "anything"]
    script = page.evaluate("() => ['who', 'from', 'where', 'start', 'flex', 'nights', 'budget', 'into'].map(k => V2.text(k))")
    assert script == server


def test_search_glides_the_sentence_up_shows_the_skeleton_and_lands_on_the_matrix_with_what_the_words_said(ask):
    page = ask(motion=True)
    word(page, "from").click()
    page.locator('#v2-pop [data-home="OAK"]').click()
    page.locator("#v2-pop .v2-done").click()
    page.route("**/plan/ask", lambda route: (page.wait_for_timeout(500), route.continue_())[1])      # hold the post a moment: the page is the results' skeleton meanwhile
    page.locator("#v2-go").click()
    expect(page.locator("#v2-skel")).to_be_visible()
    assert page.evaluate("document.querySelector('.v2').classList.contains('is-results')")
    page.wait_for_url("**/plan/matrix**")
    q = {k: v[0] for k, v in parse_qs(urlsplit(page.url).query).items()}
    assert q["home"] == "OAK" and q["to"] == "San Diego" and q["a"] == "2" and q["k"] == "7,10"
    page.wait_for_selector("#mx.is-live")
    page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
    expect(page.locator(".mx-sq.is-ok").first).to_be_visible()
    assert words(page)[1] == "OAK"      # the same sentence, on the results, at the top


def test_a_search_that_cannot_run_stays_here_and_says_why(ask):
    page = ask()
    page.evaluate("() => { V2.spec.to = 'Atlantis'; V2.drawSentence(); }")
    page.locator("#v2-go").click()
    expect(page.locator("#v2-error")).to_contain_text("does not know that place")
    assert page.url.endswith("/plan/ask")
    assert not page.evaluate("document.querySelector('.v2').classList.contains('is-results')")


def test_changing_a_word_on_the_results_searches_again_on_the_same_page(ask):
    page = ask(url="/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16&a=2&k=7,10&x=2", idle=False)
    page.wait_for_selector("#mx.is-live")
    word(page, "flex").click()
    page.locator('#v2-pop [data-flex="0"]').click()
    page.locator("#v2-pop .v2-done").click()
    page.wait_for_url("**x=0**")
    page.wait_for_selector("#mx.is-live")
    expect(word(page, "flex")).to_have_text("on the dot")
    assert page.locator(".mx-sq[data-sq]").count() == 5      # exactly the one start day, five places
