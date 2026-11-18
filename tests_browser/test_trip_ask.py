"""F-241, F-250, F-257 in a real browser at phone (390) and laptop (1440), light and dark. The landing ("Where would you like to go?") is one calm line, one soft box and Search: typing
shows an autocomplete (places we know, then who and when), by keys or by tap, and Search glides the box up, shows the results' skeleton and lands on the matrix on what the box said. The results
page keeps the sentence whose every word opens its picker (a popover under the word on a laptop, a bottom sheet on a phone); the script's words (assets/js/v2.js `text`) say what the server's do
(gitaway/v2sentence.py `words`)."""
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE

RESULTS = "/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16&a=2&k=7,10&x=2"


@pytest.fixture
def ask(browser, base_url):
    contexts = []

    def ask(viewport=DESKTOP, scheme="light", motion=False, url="/plan/ask", idle=True, quiet=False):
        phone = viewport is PHONE
        ctx = browser.new_context(viewport=viewport, color_scheme=scheme, reduced_motion="no-preference" if motion else "reduce", has_touch=phone, is_mobile=phone, service_workers="block")
        ctx.set_default_timeout(8000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ask.family@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        if quiet:      # the results' pickers re-search when one closes: these tests are about the pickers, so the search is answered with nothing to open
            page.route("**/plan/ask", lambda route: route.fulfill(json={}) if route.request.method == "POST" else route.continue_())
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


BOX = "#v2-q"
OPTIONS = "#v2-list [role=option]"


def typed(page, text):
    page.locator(BOX).fill(text)
    page.wait_for_selector("#v2-list:not([hidden])")


def labels(page):
    return page.evaluate("() => [...document.querySelectorAll('#v2-list .ak-l')].map(e => e.textContent)")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_landing_is_one_calm_line_and_a_soft_box_that_fit_with_48px_targets(ask, viewport, scheme):
    page = ask(viewport, scheme)
    assert page.url.endswith("/plan/ask")
    expect(page.locator("h1")).to_have_text("Where would you like to go?")
    assert page.evaluate("getComputedStyle(document.querySelector('h1')).fontFamily").startswith("Inter")      # F-296: heavy Inter headlines
    assert page.evaluate("parseFloat(getComputedStyle(document.querySelector('h1')).fontWeight)") <= 500      # a calm line, not a bold sentence
    assert page.evaluate("document.querySelectorAll('.v2-w, .v2-sent').length") == 0
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")      # no sideways scroll
    small = page.evaluate("""() => [...document.querySelectorAll('#v2-form a, #v2-form button, #v2-form input[type=text], #v2-form label')].filter(e => { const r = e.getBoundingClientRect(); return r.height > 0 && Math.min(r.width, r.height) < 47.5; }).map(e => e.textContent.trim() + ' ' + Math.round(e.getBoundingClientRect().height))""")
    assert small == []
    ratio = page.evaluate("""() => {
      const lum = c => { const v = c.match(/[\\d.]+/g).slice(0, 3).map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
      const q = document.getElementById('v2-q'), bg = getComputedStyle(document.querySelector('.ak-field')).backgroundColor;
      const f = [getComputedStyle(q, '::placeholder').color, getComputedStyle(q).color, getComputedStyle(document.querySelector('.ak-sub')).color].map(lum), b = lum(bg);
      return f.map(x => (Math.max(x, b) + 0.05) / (Math.min(x, b) + 0.05));
    }""")
    assert ratio[0] >= 4.5 and ratio[1] >= 4.5      # the placeholder and the typed words on the box (the line under the heading sits on the sky: tests/test_v2_targets.py's method)
    assert page.errors == []


def test_typing_shows_the_places_we_know_and_never_guesses_one(ask):
    page = ask()
    expect(page.locator(BOX)).to_have_attribute("aria-expanded", "false")
    typed(page, "san")
    assert labels(page) == ["San Diego", "Santa Barbara", "Los Angeles"]
    expect(page.locator(BOX)).to_have_attribute("aria-expanded", "true")
    assert page.locator(OPTIONS).count() == 3
    page.locator(BOX).fill("Narnia")
    expect(page.locator("#v2-say")).to_have_text("We don't know that place yet.")
    expect(page.locator("#v2-list")).to_be_hidden()
    expect(page.locator(BOX)).to_have_attribute("aria-expanded", "false")


def test_the_keys_walk_the_list_and_build_the_sentence(ask):
    page = ask()
    typed(page, "san")
    page.keyboard.press("ArrowDown")
    expect(page.locator(BOX)).to_have_attribute("aria-activedescendant", "ak-o0")
    expect(page.locator(OPTIONS).first).to_have_attribute("aria-selected", "true")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowUp")
    page.keyboard.press("Enter")      # takes the suggestion, never searches
    expect(page.locator(BOX)).to_have_value("San Diego")
    page.wait_for_function("document.querySelector('#v2-list .ak-party')")
    assert page.url.endswith("/plan/ask")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator(BOX)).to_have_value("San Diego · a family of 4")
    page.wait_for_function("document.querySelector('#v2-list .ak-when')")
    page.keyboard.press("Escape")
    expect(page.locator("#v2-list")).to_be_hidden()
    expect(page.locator(BOX)).to_have_attribute("aria-expanded", "false")
    expect(page.locator(BOX)).to_be_focused()


def test_a_tap_takes_a_suggestion(ask):
    page = ask(PHONE)
    typed(page, "san")
    page.locator(OPTIONS).first.tap()
    expect(page.locator(BOX)).to_have_value("San Diego")
    page.wait_for_function("document.querySelector('#v2-list .ak-party')")
    page.locator("#v2-list .ak-party").first.tap()
    page.wait_for_function("document.querySelector('#v2-list .ak-when')")
    assert page.evaluate("document.querySelector('#v2-list').getBoundingClientRect().right <= window.innerWidth")
    assert page.evaluate("[...document.querySelectorAll('#v2-list [role=option]')].every(o => o.getBoundingClientRect().height >= 47.5)")


def test_an_example_place_fills_the_box_and_asks_what_comes_next(ask):
    page = ask()
    page.get_by_role("link", name="Honolulu").click()
    expect(page.locator(BOX)).to_have_value("Honolulu")
    page.wait_for_selector("#v2-list .ak-party")
    assert page.url.endswith("/plan/ask")


def test_search_glides_the_box_up_shows_the_skeleton_and_lands_on_the_matrix_with_what_the_box_said(ask):
    page = ask(motion=True)
    typed(page, "san")
    page.locator(OPTIONS).first.click()
    page.wait_for_selector("#v2-list .ak-party")
    page.get_by_role("option", name=re.compile("^2 adults")).click()
    page.wait_for_selector("#v2-list .ak-when")
    page.locator("#v2-list .ak-when").first.click()
    expect(page.locator(BOX)).to_have_value(re.compile(r"^San Diego · 2 adults · [A-Z][a-z]{2} \d+–(?:[A-Z][a-z]{2} )?\d+$"))
    page.route("**/plan/ask", lambda route: (page.wait_for_timeout(500), route.continue_())[1])      # hold the post a moment: the page is the results' skeleton meanwhile
    page.get_by_role("button", name="Search").click()
    expect(page.locator("#v2-skel")).to_be_visible()
    assert page.evaluate("document.querySelector('.v2').classList.contains('is-results')")
    page.wait_for_url("**/plan/matrix**")
    q = {k: v[0] for k, v in parse_qs(urlsplit(page.url).query).items()}
    assert q["to"] == "San Diego" and q["home"] == "SFO" and q["a"] == "2" and q.get("k", "") == ""
    page.wait_for_selector("#mx.is-live")
    page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
    expect(page.locator(".mx-sq.is-ok").first).to_be_visible()
    assert words(page)[0] == "The two of us"      # the results keep the tappable sentence, with the box's words in it


def test_a_search_that_cannot_run_stays_here_and_says_why(ask):
    page = ask()
    page.locator(BOX).fill("San Diego Dec 12 to 16 give or take 9 days")      # M5 triage (F-268, D-772): a place alone is not an error any more (the matrix opens on a default window); a flex the page cannot read still is
    page.get_by_role("button", name="Search").click()
    expect(page.locator("#v2-error")).to_have_text("Say give or take 0 to 3 days, like “give or take 2 days”.")
    assert page.url.endswith("/plan/ask")
    assert not page.evaluate("document.querySelector('.v2').classList.contains('is-results')")
    page.locator(BOX).fill("Narnia")
    expect(page.locator("#v2-error")).to_be_hidden()
    page.get_by_role("button", name="Search").click()
    expect(page.locator("#v2-error")).to_have_text("We don't know that place yet.")


def test_every_word_opens_its_picker_and_a_change_rewrites_the_sentence(ask):
    page = ask(url=RESULTS, idle=False, quiet=True)
    page.wait_for_selector("#v2-sent")
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
    page = ask(url="/plan/matrix", idle=False, quiet=True)      # the default start day: a few weeks ahead, so the month before it holds days already gone
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
    page = ask(PHONE, url=RESULTS, idle=False, quiet=True)
    word(page, "nights").click()
    box, vh = page.locator("#v2-pop").bounding_box(), page.viewport_size["height"]
    assert page.locator("#v2-pop.as-sheet").count() == 1 and box["y"] + box["height"] > vh - 20 and box["width"] > 340
    page = ask(DESKTOP, url=RESULTS, idle=False, quiet=True)
    w = word(page, "nights")
    w.click()
    pop, at = page.locator("#v2-pop").bounding_box(), w.bounding_box()
    assert page.locator("#v2-pop.as-sheet").count() == 0 and pop["y"] >= at["y"] + at["height"] - 2 and pop["width"] <= 381


def test_the_scripts_words_say_what_the_servers_say(ask):
    """Change one, change the other: after changing a word the script's text equals a fresh server draw of the same address."""
    page = ask(url="/plan/matrix?to=San+Diego&home=OAK&d=2027-01-09&r=2027-01-13&a=2&k=&x=1&nb=0&b=3000", idle=False)
    server = words(page)
    assert server == ["The two of us", "OAK", "San Diego", "Sat, Jan 9", "give or take 1 day", "4 nights", "$3,000", "anything"]
    script = page.evaluate("() => ['who', 'from', 'where', 'start', 'flex', 'nights', 'budget', 'into'].map(k => V2.text(k))")
    assert script == server


def test_changing_a_word_on_the_results_waits_for_update_and_then_searches_again(ask):      # F-280: the change is staged; Update is the search
    page = ask(url="/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16&a=2&k=7,10&x=2", idle=False)
    page.wait_for_selector("#mx.is-live")
    word(page, "flex").click()
    page.locator('#v2-pop [data-flex="0"]').click()
    page.locator("#v2-pop .v2-done").click()
    assert "x=0" not in page.url      # staged, not searched
    page.locator(".v2-update").click()
    page.wait_for_url("**x=0**")
    page.wait_for_selector("#mx.is-live")
    expect(word(page, "flex")).to_have_text("on the dot")
    assert page.locator(".mx-sq[data-sq]").count() == 5      # exactly the one start day, five places


def test_on_a_phone_the_boxs_example_fits_and_on_a_laptop_it_is_the_long_one(ask):
    """Overnight walk 2026-11-17: at 390 the long example was cut mid-word ("or “a f"); a phone shows the short one, whole."""
    page = ask(PHONE)
    box = page.locator("#v2-q")
    assert box.get_attribute("placeholder") == "Try “Tahoe with kids”"
    assert page.evaluate("""() => { const q = document.getElementById('v2-q'), c = document.createElement('canvas').getContext('2d'), s = getComputedStyle(q);
      c.font = s.font; return c.measureText(q.placeholder).width <= q.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight); }""")
    assert ask(DESKTOP).locator("#v2-q").get_attribute("placeholder").startswith("Try “San Diego” or")
