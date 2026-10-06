"""F-100: the chat box stays at the bottom, like WhatsApp. In the Family chat and a plan chat the composer is docked right above the tab bar, the messages scroll
in the space above it (open at the newest, newest right above the box, no gap under it), and the iPhone keyboard (the visual viewport shrinking) lifts the box
with it and hides the tab bar. Checked at 390 and 320, and with the keyboard area simulated by shrinking the page's visualViewport."""
import re

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE
from tests_browser.test_plan_talk import lunch_chat
from tests_browser.test_trip_canvas import NARROW, canvas_page, model  # noqa: F401 - fixtures

SIZES = pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])

RECT = """(sel) => { const r = document.querySelector(sel).getBoundingClientRect(); return {top: r.top, bottom: r.bottom, height: r.height}; }"""
KEYBOARD = """(h) => { const v = window.visualViewport; Object.defineProperty(v, 'height', {get: () => h, configurable: true});
  Object.defineProperty(v, 'offsetTop', {get: () => 0, configurable: true}); v.dispatchEvent(new Event('resize')); }"""


def rect(page, sel):
    return page.evaluate(RECT, sel)


def send(page, text):
    page.locator("#ft-text").fill(text)
    page.locator("#ft-send").click()
    expect(page.locator("#ft-thread .is-pending")).to_have_count(0)
    expect(page.locator("#ft-thread .ft-me .ft-bub", has_text=text)).to_have_count(1)


def docked(page, tabs_up=True):
    """The box sits right above the tab bar; the newest bubble sits right above the box; the page itself does not scroll."""
    box, last = rect(page, "#ft-compose"), rect(page, "#ft-thread .ft-msg:last-of-type, #ft-thread > :last-child")
    if tabs_up:
        tabs = rect(page, ".ph-tabs")
        assert box["bottom"] <= tabs["top"] + 1, (box, tabs)
        assert tabs["top"] - box["bottom"] < 24, (box, tabs)          # nothing empty between the box and the bar
    assert last["bottom"] <= box["top"] + 1, (last, box)             # the newest is visible, above the box
    assert box["top"] - last["bottom"] < 40, (last, box)             # and right above it: no empty gap
    assert page.evaluate("window.scrollY") == 0
    assert page.evaluate("document.documentElement.scrollHeight - innerHeight") <= 1


def family(canvas_page, base_url, viewport):
    page = canvas_page(viewport=viewport)
    page.goto(f"{base_url}/trip/family")
    page.wait_for_selector("#ft-compose")
    return page


@SIZES
def test_the_family_box_is_docked_and_the_newest_stays_in_view(canvas_page, base_url, viewport):
    page = family(canvas_page, base_url, viewport)
    send(page, "First one")
    docked(page)                                                       # few messages: they sit right above the box
    start = rect(page, "#ft-compose")
    for i in range(14):
        send(page, f"Message number {i} x")
        assert rect(page, "#ft-compose") == start                      # the box never moves
        docked(page)
    assert page.evaluate("document.querySelector('#ft-thread').scrollHeight > document.querySelector('#ft-thread').clientHeight")   # the messages scrolled inside their own space
    assert page.evaluate("document.querySelector('#ft-thread').scrollTop") > 0


@SIZES
def test_a_full_family_chat_opens_at_the_newest(canvas_page, base_url, viewport):
    page = family(canvas_page, base_url, viewport)
    for i in range(14):
        send(page, f"Earlier {i} x")
    page.reload()
    page.wait_for_selector("#ft-compose")
    docked(page)
    expect(page.locator("#ft-thread .ft-me .ft-bub").last).to_contain_text("Earlier 13")


@SIZES
def test_the_keyboard_lifts_the_family_box_and_hides_the_tab_bar(canvas_page, base_url, viewport):
    page = family(canvas_page, base_url, viewport)
    for i in range(10):
        send(page, f"Keyboard {i} x")
    page.locator("#ft-text").focus()
    height = viewport["height"]
    page.evaluate(KEYBOARD, height - 300)                              # the iPhone keyboard takes 300px
    page.wait_for_function("document.querySelector('.ph-tabs').getBoundingClientRect().height === 0 || getComputedStyle(document.querySelector('.ph-tabs')).display === 'none'")
    box = rect(page, "#ft-compose")
    assert box["bottom"] <= height - 300 + 1, box                      # the box rides up with the keyboard
    assert height - 300 - box["bottom"] < 24, box                      # right on top of it
    docked(page, tabs_up=False)
    send(page, "typed with the keyboard up")
    assert rect(page, "#ft-compose")["bottom"] <= height - 300 + 1
    docked(page, tabs_up=False)
    page.evaluate(KEYBOARD, height)                                    # keyboard away: the bar is back and the box sits on it again
    expect(page.locator(".ph-tabs")).to_be_visible()
    docked(page)


def test_the_photos_view_still_scrolls_like_a_page(canvas_page, base_url):
    page = family(canvas_page, base_url, PHONE)
    page.locator("#fam-photos").click()
    expect(page.locator("#fp")).to_be_visible()
    assert page.evaluate("getComputedStyle(document.querySelector('.tp')).position") != "fixed"
    page.locator("#fam-chat").click()
    expect(page.locator("#ft-compose")).to_be_visible()
    docked(page) if page.locator("#ft-thread > *").count() else None
    assert page.evaluate("getComputedStyle(document.querySelector('.tp')).position") == "fixed"


@SIZES
def test_a_plan_chat_box_is_docked_and_the_newest_stays_in_view(canvas_page, base_url, viewport):
    page = canvas_page(viewport=viewport)
    lunch_chat(page, base_url)
    send(page, "Lunch at noon?")
    docked(page)
    start = rect(page, "#ft-compose")
    for i in range(12):
        send(page, f"Plan message {i} x")
        assert rect(page, "#ft-compose") == start
        docked(page)
    page.reload()
    page.wait_for_selector("#ft-compose")
    docked(page)
    expect(page.locator("#ft-thread .ft-me .ft-bub").last).to_contain_text("Plan message 11")
    page.locator("#ft-text").focus()
    page.evaluate(KEYBOARD, viewport["height"] - 300)
    assert rect(page, "#ft-compose")["bottom"] <= viewport["height"] - 300 + 1
    docked(page, tabs_up=False)


def test_an_empty_plan_chat_keeps_the_box_at_the_bottom(canvas_page, base_url):
    page = canvas_page()
    lunch_chat(page, base_url)
    expect(page.locator("#ft-empty")).to_be_visible()
    tabs = rect(page, ".ph-tabs")
    assert tabs["top"] - rect(page, "#ft-compose")["bottom"] < 24
    assert re.search(r"fixed", page.evaluate("getComputedStyle(document.querySelector('.tp')).position"))
