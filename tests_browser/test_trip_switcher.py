"""F-040, F-147: a family with two trips switches between them on a phone and a tablet, where the top bar is not drawn: the trip menu in the heading of the day, the week and Today
holds the trips, Plan another trip and Import a trip you booked. It opens as a bottom sheet that fits the screen. (The laptop's picker is in tests_browser/test_topbar.py.)"""
import re

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE, seed_plan

TABLET = {"width": 800, "height": 1000}
SAMPLE = {"f": "f1", "h": "h1", "c": "c1"}
THREE_NIGHTS = {**SAMPLE, "d": "2026-10-23", "r": "2026-10-26", "a": "2", "k": "4,7"}
MENU = ".ga-tb-phonepick"


@pytest.fixture
def family_with_two_trips(browser, base_url):
    contexts = []

    def make(viewport, path="/trip/canvas?day=1"):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form=SAMPLE, max_redirects=0)
        seed_plan(ctx.request, base_url, "a1", "1", "10:00", "11:30", "Venice Canals stroll", "outdoors")
        ctx.request.post(f"{base_url}/pay", form=THREE_NIGHTS, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}{path}")
        return page

    yield make
    for c in contexts:
        c.close()


def open_menu(page):
    page.click(f"{MENU} > summary")
    pop = page.locator(f"{MENU} .ga-tb-pop")
    expect(pop).to_be_visible()
    return pop


@pytest.mark.parametrize("viewport", [PHONE, TABLET], ids=["390", "800"])
def test_the_menu_fits_the_screen_and_switching_opens_the_other_trip(family_with_two_trips, viewport):
    page = family_with_two_trips(viewport)
    expect(page.locator(f"{MENU} > summary")).to_be_visible()
    root = page.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)")
    assert page.locator(f"{MENU} > summary").bounding_box()["height"] >= 2.75 * root - 0.5      # 2.75rem: 44px on a phone
    expect(page.locator(".cz-gb", has_text="Venice Canals stroll")).to_have_count(0)           # the newest trip is open and has nothing planned yet
    pop = open_menu(page)
    box = pop.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"] and box["y"] >= 0 and box["y"] + box["height"] <= viewport["height"]
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    expect(page.locator(f'{MENU} .ga-tb-sw[aria-current="true"]')).to_have_count(1)
    page.click(f"{MENU} .ga-tb-sw:not([aria-current])")
    page.wait_for_url(re.compile(r"/trip/canvas"))
    page.goto(page.url.split("?")[0] + "?day=1")
    expect(page.locator(".cz-gb", has_text="Venice Canals stroll").first).to_be_visible()


@pytest.mark.parametrize("viewport", [PHONE, TABLET], ids=["390", "800"])
def test_plan_another_and_import_are_in_the_menu(family_with_two_trips, viewport):
    page = family_with_two_trips(viewport)
    open_menu(page)
    page.click(f'{MENU} a[href="/start"]')
    page.wait_for_url(re.compile(r"/start$"))
    page.go_back()
    open_menu(page)
    page.click(f'{MENU} a[href="/trips/import"]')
    page.wait_for_url(re.compile(r"/trips/import$"))


@pytest.mark.parametrize("path", ["/trip/canvas", "/trip?tab=today"], ids=["week", "today"])
def test_the_week_and_the_old_today_page_carry_the_menu_too(family_with_two_trips, path):
    page = family_with_two_trips(PHONE, path)
    pop = open_menu(page)
    assert pop.bounding_box()["y"] + pop.bounding_box()["height"] <= PHONE["height"]
    page.keyboard.press("Escape")
    expect(page.locator(f"{MENU} .ga-tb-pop")).to_be_hidden()


def test_the_laptop_has_the_bar_picker_and_this_one_is_not_a_menu_there(family_with_two_trips):
    page = family_with_two_trips({"width": 1440, "height": 900})
    expect(page.locator(f"{MENU} .ga-tb-pop")).to_be_hidden()
    expect(page.locator(".ga-topbar .ga-tb-picker summary")).to_be_visible()


# ---- the eyebrow is the button: no extra row, readable on every level, a dimmed screen behind the sheet (F-147 re-review) ----

LEVELS = {"day": "/trip/canvas?day=1", "week": "/trip/canvas", "today": "/trip?tab=today"}
# The top of each title before this menu existed (measured on master at 390 and 800 with this fixture): the menu adds no row.
TITLE_TOP = {(390, "day"): 43.5, (390, "week"): 59, (390, "today"): 39.5, (800, "day"): 34.5, (800, "week"): 31.5, (800, "today"): 31.5}

CONTRAST = """(sel) => {
  const el = document.querySelector(sel);
  const rgba = c => { const m = c.match(/[\\d.]+/g).map(Number); return [m[0], m[1], m[2], m.length > 3 ? m[3] : 1]; };
  let bg = [255, 255, 255];
  const layers = [];
  for (let n = el; n; n = n.parentElement) { const c = rgba(getComputedStyle(n).backgroundColor); if (c[3] > 0) { layers.push(c); if (c[3] >= 1) break; } }
  for (const c of layers.reverse()) bg = bg.map((v, i) => v * (1 - c[3]) + c[i] * c[3]);
  const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const L = c => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  const fg = rgba(getComputedStyle(el).color);
  const a = L(bg) + 0.05, b = L(fg) + 0.05;
  return Math.max(a, b) / Math.min(a, b);
}"""


@pytest.mark.parametrize("level", list(LEVELS))
@pytest.mark.parametrize("viewport", [PHONE, TABLET], ids=["390", "800"])
def test_the_trigger_is_readable_adds_no_height_and_is_a_44px_target(family_with_two_trips, viewport, level):
    page = family_with_two_trips(viewport, LEVELS[level])
    summary = page.locator(f"{MENU} > summary")
    expect(summary).to_be_visible()
    assert page.evaluate(CONTRAST, f"{MENU} > summary") >= 4.5, level
    root = page.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)")
    assert summary.bounding_box()["height"] >= 2.75 * root - 0.5
    top = page.locator("h1").first.bounding_box()["y"]
    assert abs(top - TITLE_TOP[(viewport["width"], level)]) <= 1, (level, top)


@pytest.mark.parametrize("level", list(LEVELS))
def test_the_sheet_has_a_dimmed_screen_and_a_tap_on_it_closes_the_sheet(family_with_two_trips, level):
    page = family_with_two_trips(PHONE, LEVELS[level])
    pop = open_menu(page)
    dim = page.evaluate(f"getComputedStyle(document.querySelector('{MENU}'), '::before').backgroundColor")
    assert dim not in ("rgba(0, 0, 0, 0)", "transparent"), dim
    page.mouse.click(PHONE["width"] / 2, max(pop.bounding_box()["y"] / 2, 5))
    expect(page.locator(f"{MENU} .ga-tb-pop")).to_be_hidden()
    assert LEVELS[level].split("?")[0] in page.url      # nothing underneath was pressed


@pytest.mark.parametrize("level,words", [("day", "SAT OCT 24"), ("week", "LA WITH THE KIDS · OCT 23 – 26"), ("today", "LA WITH THE KIDS · OCT 23 – 26")])
@pytest.mark.parametrize("width", [1440, 1280])
def test_on_a_laptop_the_eyebrow_line_stays_as_plain_text(family_with_two_trips, width, level, words):
    page = family_with_two_trips({"width": width, "height": 900}, LEVELS[level])
    line = page.locator(f"{MENU} > summary")
    expect(line).to_be_visible()
    expect(line).to_contain_text(words)
    assert page.evaluate(f"getComputedStyle(document.querySelector('{MENU} > summary')).pointerEvents") == "none"
    assert line.get_attribute("tabindex") == "-1" and line.get_attribute("role") == "presentation"
    expect(page.locator(f"{MENU} .ga-tb-chev")).to_be_hidden()
    expect(page.locator(f"{MENU} .ga-tb-pop")).to_be_hidden()
    assert line.evaluate("e => e.closest('details').open") is False


def test_the_eyebrow_stays_plain_after_the_canvas_swaps_day_and_week_in_place(family_with_two_trips):
    page = family_with_two_trips({"width": 1440, "height": 900}, LEVELS["day"])

    def plain():
        summaries = page.locator(f"{MENU} > summary")
        assert summaries.count() == 1
        s = summaries.first
        assert s.get_attribute("tabindex") == "-1" and s.get_attribute("role") == "presentation" and s.get_attribute("aria-label") is None
        expect(s).to_be_visible()

    plain()
    for name, level in (("Week", "week"), ("Day", "day"), ("Week", "week")):
        page.locator(".cz-head .cz-seg", has_text=name).first.click()
        page.wait_for_selector(f".cz-view[data-level={level}]")
        page.wait_for_timeout(700)
        plain()
