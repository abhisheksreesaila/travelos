"""F-195 in a real browser at phone (390) and laptop (1440) width: a reader on a creator's trip taps Tickets and things to do or Plan this trip, lands on the honest page (one card
per lane, no invented offers), says where they fly from and follows the flight link. The partners' own sites are never reached: their addresses are caught and read.
Set F195_SHOTS=1 to save screenshots to docs/report/f195-*.png."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.live_trips import live_trip
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
IDS = ["390", "1440"]


def shot(page, name):
    if os.getenv("F195_SHOTS"):
        page.wait_for_timeout(400)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f195-{name}.png"), full_page=True)


@pytest.fixture(autouse=True)
def live(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    for name in ("TRAVELPAYOUTS_TOKEN", "TRAVELPAYOUTS_TRS"):
        monkeypatch.delenv(name, raising=False)


def context(browser, base_url, viewport):
    ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE, reduced_motion="reduce")
    ctx.set_default_timeout(9000)
    caught = []

    def partner(route, request):
        caught.append(request.url)
        route.fulfill(status=200, content_type="text/html", body="<html><body>the partner</body></html>")
    ctx.route("https://www.aviasales.com/**", partner)
    ctx.route("https://klook.tpx.lv/**", partner)
    return ctx, caught


def tap(el, viewport):
    el.tap() if viewport is PHONE else el.click()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_from_a_disneyland_trip_to_an_honest_flight_search_from_the_readers_airport(browser, base_url, viewport):
    row, handle, _ = live_trip(title="Three days at Disneyland with the kids")
    ctx, caught = context(browser, base_url, viewport)
    page = ctx.new_page()
    page.goto(f"{base_url}/trips/{row['slug']}")
    card = page.locator("#todo")
    expect(card).to_contain_text("Tickets and things to do")
    expect(card).to_contain_text("Disneyland Resort tickets")
    expect(card).to_contain_text("This link supports GitAway, not Maya")
    assert viewport is DESKTOP or page.locator("#todo-klook").bounding_box()["height"] >= 40, "a touch target"
    shot(page, f"{viewport['width']}-trip")
    tap(page.locator("#plan-this").first, viewport)
    page.wait_for_url("**/plan?**")
    cards = page.locator("h2.ps-name")
    expect(cards).to_have_text(["Search flights to Los Angeles", "Find stays near Anaheim", "Tickets and things to do"])
    assert "Skylark" not in page.content() and "Preview: sample prices" not in page.content()
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "the page scrolls sideways"
    sizes = page.locator("a.ps-go, .ps-from button, .ps-field input").evaluate_all("els => els.map(e => e.getBoundingClientRect().height)")
    assert viewport is DESKTOP or min(sizes) >= 43, sizes
    shot(page, f"{viewport['width']}-plan")
    page.fill("input[name=home]", "jfk")
    tap(page.get_by_role("button", name="Update"), viewport)
    expect(page.locator("#ps-lede")).to_contain_text("flying from JFK")
    tap(page.locator("a[data-lane=flight]"), viewport)
    page.wait_for_url("https://www.aviasales.com/**")
    assert caught[-1].startswith("https://www.aviasales.com/search/JFK") and "LAX" in caught[-1] and f"-flight-{handle}" in caught[-1]
    page.go_back()
    tap(page.locator("a[data-lane=todo]"), viewport)
    page.wait_for_url("https://klook.tpx.lv/**")
    ctx.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_a_bad_airport_is_said_on_the_page_and_kept_in_its_box(browser, base_url, viewport):
    _, handle, _ = live_trip()
    ctx, _ = context(browser, base_url, viewport)
    page = ctx.new_page()
    page.goto(f"{base_url}/plan?to=la&d=2027-03-05&r=2027-03-09&a=2&via={handle}")
    page.fill("input[name=home]", "S1O")
    tap(page.get_by_role("button", name="Update"), viewport)
    expect(page.locator("#ps-err")).to_have_text("Use a three-letter airport code, like SFO, or leave it empty.")
    expect(page.locator("input[name=home]")).to_have_value("S1O")
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    shot(page, f"{viewport['width']}-bad-airport")
    ctx.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_kids_set_on_the_start_form_come_back_apart_in_the_flight_link(browser, base_url, viewport):
    row, handle, _ = live_trip()
    ctx, caught = context(browser, base_url, viewport)
    page = ctx.new_page()
    page.goto(f"{base_url}/trips/{row['slug']}")
    tap(page.locator("#plan-this").first, viewport)
    page.wait_for_url("**/plan?**")
    tap(page.get_by_role("link", name="Change dates or who is coming"), viewport)
    page.wait_for_url("**/start?**")
    page.select_option("select[name=n]", "2")
    page.select_option("select[name=k1]", "4")
    page.select_option("select[name=k2]", "7")
    page.fill("input[name=from]", "ord")
    page.evaluate("document.querySelectorAll('input[type=date]').forEach(e => { e.value = e.name === 'd' ? '2027-03-05' : '2027-03-09'; })")
    tap(page.get_by_role("button", name="Find my trip"), viewport)
    page.wait_for_url("**/plan?**")
    expect(page.locator("#ps-lede")).to_contain_text("2 adults, 2 kids · flying from ORD")
    tap(page.locator("a[data-lane=flight]"), viewport)
    page.wait_for_url("https://www.aviasales.com/**")
    assert caught[-1].startswith("https://www.aviasales.com/search/ORD0503LAX090322?marker=801445.")      # 2 adults and 2 children, apart
    ctx.close()
