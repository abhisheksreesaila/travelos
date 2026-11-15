"""F-262 in a real browser (docs/design/guides-v2): the guide hub and the guide page of a sample creator trip, at phone (390) and laptop (1440) width. The hub's search suggests the places GitAway
knows and its filters narrow the guides; a guide opens, a stop's card opens its details (a panel beside the sheet on a laptop, a sheet over it on a phone), the arrow keys step through the stops,
and "Add to my plan" drops the stop into the family's calendar with an Undo. The creator's own path (paste, import, the guide, publish) is tests_browser/test_creator_magic.py.
Set F262_SHOTS=1 to save docs/report/f262-test-*.png."""
import os
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.test_calendar import PICK
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
IDS = ["390", "1440"]
SAMPLE = "sun-tacos-and-tide-pools"


def shot(page, name):
    if os.environ.get("F262_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f262-test-{name}.png"))


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


@pytest.fixture
def family(browser, base_url):
    """family(viewport, booked=True) -> a page for a signed-in person whose family has a booked trip (its own, so plans never carry over). Contexts are closed after the test."""
    contexts = []

    def make(viewport, booked=True, scheme="light", still=False):
        phone = viewport["width"] < 720
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=phone, is_mobile=phone)
        ctx.set_default_timeout(8000)
        if scheme == "dark":
            ctx.add_init_script("localStorage.setItem('ga-mode', 'dark')")
        if still:
            ctx.add_init_script("delete window.IntersectionObserver")      # the day strip presses the day being read as the page scrolls; the audit scrolls the whole page and reads each text where it showed, so it is run with the first day pressed throughout
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": f"guide{time.time_ns()}@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        if booked:
            ctx.request.post(f"{base_url}/pay", form=PICK, max_redirects=0)
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        return page

    yield make
    for c in contexts:
        c.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_hub_filters_and_a_guide_opens_a_stop_and_adds_it_to_the_plan(family, base_url, viewport):
    page = family(viewport)
    page.goto(f"{base_url}/guides")
    expect(page.locator(".gcard")).to_have_count(2)
    shot(page, f"hub-{viewport['width']}")
    expect(page.locator(".v2-sections a")).to_have_text(["Book", "Plan", "Guides"])
    expect(page.locator(".v2-sections a[aria-current='page']")).to_have_text("Guides")
    # a filter is a plain link: "3 to 4 days" leaves the one three-day guide
    page.get_by_role("link", name="3 to 4 days").click()
    expect(page.locator(".gcard")).to_have_count(1)
    expect(page.locator(".gcard h3")).to_have_text("Dog-friendly Big Sur drive")
    page.get_by_role("link", name="3 to 4 days").click()      # on again: off
    expect(page.locator(".gcard")).to_have_count(2)
    # the search suggests the places GitAway knows, then looks for guides there
    page.fill("#gh-q", "San D")
    expect(page.locator("#gh-list li").first).to_contain_text("San Diego")
    page.fill("#gh-q", "")
    page.fill("#gh-q", "Big Sur")
    page.keyboard.press("Enter")
    expect(page.locator(".gcard")).to_have_count(1)
    page.locator(".gcard").click()
    page.wait_for_url("**/trips/dog-friendly-big-sur-drive")
    # the guide: tiles, the day strip, the stop cards; nothing it does not know
    expect(page.locator("h1")).to_have_text("Dog-friendly Big Sur drive")
    expect(page.locator(".gl small")).to_have_text(["Days", "Suits", "From"])
    expect(page.locator(".dbtn")).to_have_count(3)
    assert page.locator(".g-stop").count() > 3
    assert overflow(page) <= 1
    page.goto(f"{base_url}/trips/{SAMPLE}")
    shot(page, f"guide-{viewport['width']}")
    # open a stop: its details in the panel (a laptop) or the sheet (a phone); the keys step through the stops
    first = page.locator(".g-card").first
    first.locator(".g-open").first.click()
    expect(page.locator("#g-panel")).to_be_visible()
    title = page.locator("#g-pbody h2")
    expect(title).to_have_text(first.get_attribute("data-name"))
    expect(page.locator("#g-panel .g-po")).to_have_text(f"Day 1 · stop 1 of {first.get_attribute('data-of')}")
    shot(page, f"stop-{viewport['width']}")
    page.keyboard.press("ArrowDown")
    expect(page.locator("#g-panel .g-po")).to_contain_text("stop 2 of")
    page.keyboard.press("ArrowUp")
    expect(page.locator("#g-panel .g-po")).to_contain_text("stop 1 of")
    # Add to my plan: the stop lands in a free hour; the plus is ticked; the calendar has it; Undo takes it out
    page.locator("#g-pact [data-add]").click()
    expect(page.locator("#toast")).to_contain_text("added, ")
    name = first.get_attribute("data-name")[:40]
    expect(first.locator(".g-plus")).to_have_class("g-plus done")
    page.goto(f"{base_url}/trip/plan")
    page.wait_for_selector(".g-inner")
    expect(page.locator(".g-inner", has_text=name).first).to_be_visible()
    page.go_back()
    page.locator(".g-card").first.locator(".g-open").first.click()
    page.locator("#g-pact [data-add]").click()
    expect(page.locator("#toast")).to_contain_text("Already in your plan.")
    assert page.errors == []


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_adding_a_stop_can_be_undone_and_a_whole_day_says_what_it_left_out(family, base_url, viewport):
    page = family(viewport)
    page.goto(f"{base_url}/trips/{SAMPLE}")
    page.locator("#g-add").click()      # the open day's stops
    expect(page.locator("#toast")).to_contain_text("stops added to your plan")
    expect(page.locator("#g-day1 .g-plus.done")).not_to_have_count(0)
    page.locator("#toast button", has_text="Undo").click()
    expect(page.locator("#toast")).to_have_text("Taken out of your plan")
    expect(page.locator(".g-plus.done")).to_have_count(0)
    assert page.errors == []


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_without_a_trip_there_is_no_plus_and_the_page_says_why(family, base_url, viewport):
    page = family(viewport, booked=False)
    page.goto(f"{base_url}/trips/{SAMPLE}")
    expect(page.locator(".g-plus")).to_have_count(0)
    expect(page.locator("#g-note")).to_have_text("You need a trip first: add stops to its calendar from here.")
    expect(page.locator(".v2-sections a")).to_have_text(["Book", "Guides"])      # Plan appears only with a trip
    assert page.locator("#g-plan").get_attribute("href").startswith("/plan/ask?to=Los%20Angeles&d=")      # the guide's place and length go into the booking sentence
    assert page.errors == []


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_targets_and_contrast_on_the_hub_and_the_guide(family, base_url, viewport, scheme):
    page = family(viewport, scheme=scheme, still=True)
    for path in ("/guides", f"/trips/{SAMPLE}"):
        page.goto(f"{base_url}{path}")
        assert page.evaluate("document.documentElement.dataset.mode") == scheme
        m = audit(page)
        assert m["wide"] <= 1 and m["small"] == [] and m["tiny"] == [] and m["low"] == [], f"{path} {scheme} {viewport['width']}: {m}"
        shot(page, f"{'hub' if path == '/guides' else 'guide'}-{viewport['width']}-{scheme}")
    assert page.errors == []
