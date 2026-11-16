"""F-280 (D-880) in a real browser: on the results a change to the sentence is only staged. Nothing is searched (no tile, peek, warm or navigation) until "Update" or Enter, which runs
ONE search; "Reset" and setting a word back unstage; the Try chips stage too; the landing's first search is unchanged. Shots: F280_SHOTS=1 for docs/report/f280-*.png."""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_tripmatrix import URL, matrix, stand  # noqa: F401 (fixtures)
from tests_browser.test_trip_ask import OPTIONS, ask, typed  # noqa: F401 (fixtures)

REPORT = Path(__file__).resolve().parent.parent / "docs" / "report"
WORD = "#v2-sent .v2-w[data-k='%s']"
SLIDE = """(n) => { const r = document.querySelector('#v2-pop input[data-nights]'); r.value = n; r.dispatchEvent(new Event('input', {bubbles: true})); r.dispatchEvent(new Event('change', {bubbles: true})); }"""


def shot(page, name):
    if os.environ.get("F280_SHOTS"):
        page.screenshot(path=str(REPORT / f"f280-{name}.png"))


def watch(page):
    """The requests the page makes from now on: (kind, url) for tiles, peeks, warms, the search post and navigations."""
    seen = []

    def on(r):
        u = r.url
        kind = ("nav" if r.is_navigation_request() else "tile" if "/plan/matrix/tile" in u else "peek" if "/plan/matrix/peek" in u else "warm" if "/plan/matrix/warm" in u
                else "ask" if u.endswith("/plan/ask") else None)
        if kind:
            seen.append((kind, u))
    page.on("request", on)
    return seen


def kinds(seen, kind):
    return [k for k, _ in seen if k == kind]


def pick(page, k, selector):
    page.click(WORD % k)
    page.click(f"#v2-pop {selector}")
    page.click("#v2-pop .v2-done")


def three_changes(page):
    pick(page, "flex", '[data-flex="0"]')
    pick(page, "who", '[data-st="adults"][data-dv="1"]')
    page.click(WORD % "nights")
    page.evaluate(SLIDE, 6)
    page.click("#v2-pop .v2-done")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_three_changes_search_nothing_until_update_then_exactly_one_navigation(matrix, stand, viewport):  # noqa: F811
    page = matrix(viewport)
    seen = watch(page)
    before = len(stand.asked)
    three_changes(page)
    page.wait_for_timeout(600)      # a timer-based search would have fired by now
    assert seen == [] and len(stand.asked) == before      # no tile, peek, warm, post or navigation, and the server searched nothing
    expect(page.locator("#v2-upd")).to_be_visible()
    expect(page.locator(".v2-update")).to_have_text("Update · 3 changes")
    assert page.locator(".v2-update").bounding_box()["height"] >= 47.5
    expect(page.locator(".v2-staged-note")).to_have_text("Your changes aren't searched yet.")
    assert page.evaluate("[...document.querySelectorAll('#v2-sent .v2-w.is-staged')].map(e => e.dataset.k)") == ["who", "flex", "nights"]
    assert float(page.evaluate("getComputedStyle(document.querySelector('.mx-results')).opacity")) < 1      # the matrix stays, dimmed
    shot(page, f"staged-{viewport['width']}")
    page.click(".v2-update")
    page.wait_for_url("**x=0**")
    page.wait_for_selector("#mx.is-live")
    assert len(kinds(seen, "nav")) == 1 and len(kinds(seen, "ask")) == 1      # one search post, one navigation
    assert "r=2026-12-18" in page.url and "a=3" in page.url and "d=2026-12-12" in page.url
    expect(page.locator(WORD % "nights")).to_have_text("6 nights")
    expect(page.locator("#v2-upd")).to_be_hidden()
    assert page.errors == []


def test_enter_runs_the_staged_search(matrix):  # noqa: F811
    page = matrix(DESKTOP)
    seen = watch(page)
    pick(page, "flex", '[data-flex="0"]')
    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("Enter")
    page.wait_for_url("**x=0**")
    assert len(kinds(seen, "nav")) == 1


def test_enter_in_the_nights_picker_runs_it_too(matrix):  # noqa: F811
    page = matrix(DESKTOP)
    page.click(WORD % "nights")
    page.evaluate("""() => { const r = document.querySelector('#v2-pop input[data-nights]'); r.value = 5; r.dispatchEvent(new Event('input', {bubbles: true})); r.focus(); }""")
    page.keyboard.press("Enter")
    page.wait_for_url("**r=2026-12-17**")


def test_reset_and_setting_a_word_back_unstage(matrix):  # noqa: F811
    page = matrix(DESKTOP)
    seen = watch(page)
    pick(page, "flex", '[data-flex="0"]')
    expect(page.locator(".v2-update")).to_have_text("Update · 1 change")
    pick(page, "flex", '[data-flex="2"]')      # back to what it was
    expect(page.locator("#v2-upd")).to_be_hidden()
    expect(page.locator(WORD % "flex")).to_have_text("give or take 2 days")
    three_changes(page)
    expect(page.locator(".v2-update")).to_have_text("Update · 3 changes")
    page.click(".v2-reset")
    expect(page.locator("#v2-upd")).to_be_hidden()
    expect(page.locator(WORD % "who")).to_have_text("A family of 4")
    expect(page.locator(WORD % "nights")).to_have_text("4 nights")
    expect(page.locator(WORD % "flex")).to_have_text("give or take 2 days")
    assert page.evaluate("document.querySelectorAll('.is-staged').length") == 0
    assert float(page.evaluate("getComputedStyle(document.querySelector('.mx-results')).opacity")) == 1
    assert seen == []


def test_try_chips_stage_one_change_each_and_combine_with_words(matrix):  # noqa: F811
    page = matrix(DESKTOP)
    seen = watch(page)
    page.locator(".v2-sug", has_text="A week later").click()
    expect(page.locator(".v2-update")).to_have_text("Update · 1 change")
    expect(page.locator(WORD % "start")).to_have_text("Sat, Dec 19")
    page.locator(".v2-sug", has_text="3 nights").click()
    expect(page.locator(".v2-update")).to_have_text("Update · 2 changes")
    expect(page.locator(WORD % "start")).to_have_text("Sat, Dec 19")      # the second chip kept the first one's change
    pick(page, "flex", '[data-flex="0"]')
    expect(page.locator(".v2-update")).to_have_text("Update · 3 changes")
    page.locator(".v2-sug", has_text="3 nights").click()      # tapped again: taken back
    expect(page.locator(".v2-update")).to_have_text("Update · 2 changes")
    assert seen == []
    page.click(".v2-update")
    page.wait_for_url("**d=2026-12-19**")
    assert "x=0" in page.url and len(kinds(seen, "nav")) == 1


def test_the_nights_slider_estimates_while_sliding_but_letting_go_asks_for_nothing_until_update(matrix, stand):  # noqa: F811
    page = matrix(DESKTOP)
    seen = watch(page)
    before = len(stand.asked)
    page.click(WORD % "nights")
    page.evaluate(SLIDE, 6)
    page.wait_for_timeout(600)
    sq = page.locator(".mx-lane[data-lane='sandiego'] .mx-sq[data-sq='sandiego|2026-12-12'] .mx-in")
    expect(sq).to_have_text("about $2,910")      # the labelled estimate stays
    assert seen == [] and len(stand.asked) == before and "r=2026-12-16" in page.url
    page.click("#v2-pop .v2-done")
    page.click(".v2-reset")
    expect(sq).to_have_text("$2,140")      # back to the real answers
    assert seen == []


def test_the_landings_first_search_is_still_immediate(ask):
    page = ask()
    assert page.locator(".v2-update, #v2-upd").count() == 0
    typed(page, "san")
    page.locator(OPTIONS).first.click()
    page.wait_for_selector("#v2-list .ak-party")
    page.get_by_role("option", name=re.compile("^2 adults")).click()
    page.wait_for_selector("#v2-list .ak-when")
    page.locator("#v2-list .ak-when").first.click()
    page.get_by_role("button", name="Search").click()
    page.wait_for_url("**/plan/matrix**")      # no Update step: the first search is at once
    page.wait_for_selector("#mx.is-live")
    assert page.errors == []


def test_without_script_the_plain_form_still_searches(matrix):  # noqa: F811
    page = matrix(DESKTOP, js=False)
    expect(page.locator(".v2-update")).to_be_visible()
    page.click(".v2-update")
    page.wait_for_url("**/plan/matrix**")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_update_bar_and_staged_words_are_48px_and_4_5_to_1(matrix, stand, viewport, scheme):  # noqa: F811
    page = matrix(viewport)
    if scheme == "dark":
        page.evaluate("localStorage.setItem('ga-mode', 'dark')")
        page.reload()
        page.wait_for_selector("#mx.is-live")
        assert page.evaluate("document.documentElement.dataset.mode") == "dark"
    three_changes(page)
    page.wait_for_function("() => document.getAnimations().length === 0")      # the words' one-off flash has ended
    got = page.evaluate("""() => {
      const rgb = s => s.match(/[\\d.]+/g).map(Number).map(v => s.startsWith('color(') ? v * 255 : v), lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]); };
      const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
      const pair = (el, bgEl) => ratio(rgb(getComputedStyle(el).color), rgb(getComputedStyle(bgEl).backgroundColor));
      const card = document.querySelector('.v2-qcard'), u = document.querySelector('.v2-update'), r = document.querySelector('.v2-reset'), n = document.querySelector('.v2-staged-note');
      const w = document.querySelector('#v2-sent .v2-w.is-staged');
      return { update: pair(u, u), reset: pair(r, card), note: pair(n, card), word: pair(w, w), h: [u, r].map(e => e.getBoundingClientRect().height) };
    }""")
    assert min(got["update"], got["reset"], got["note"], got["word"]) >= 4.5, got
    assert all(h >= 47.5 for h in got["h"]), got
    shot(page, f"staged-{viewport['width']}-{scheme}")
