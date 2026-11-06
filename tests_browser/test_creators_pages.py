"""F-184 to F-186 in a real browser at phone (390) and laptop (1440) width: the For creators page, the marker settings, the report form and the captain's page. The server runs in this
process, so a trip is published straight into its community database. Set F186_SHOTS=1 to save screenshots to docs/report/f186-*.png."""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import affiliate, community
from tests.live_trips import live_trip
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
IDS = ["390", "1440"]
CAPTAIN = "captain@example.com"


def shot(page, name, full=True):
    if os.getenv("F186_SHOTS"):
        page.wait_for_timeout(700)      # let the entrance settle
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f186-{name}.png"), full_page=full)


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def too_small(page, selector, limit=40):
    """Visible controls under `limit` px tall (44px is the phone target at the phone's 16px root)."""
    return page.evaluate("""([sel, limit]) => [...document.querySelectorAll(sel)].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < limit; })
        .map(e => (e.getAttribute('name') || e.id || e.textContent.trim()).slice(0, 30))""", [selector, limit])


@pytest.fixture(autouse=True)
def live(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")      # the live site: nothing sample, and the For creators page must stand on its own
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAPTAIN)


@pytest.fixture
def visitor(browser, base_url):
    contexts = []

    def make(viewport, email=""):
        ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        if email:
            ctx.request.post(f"{base_url}/signin", form={"email": email, "next": "/", "intent": "save"}, max_redirects=0)
        return ctx

    yield make
    for c in contexts:
        c.close()


def tap(page, viewport, locator):
    locator.tap() if viewport is PHONE else locator.click()


# ---- F-186: the page -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_for_creators_page_sells_in_ten_seconds_and_fits_the_screen(visitor, base_url, viewport):
    page = visitor(viewport).new_page()
    page.goto(f"{base_url}/for-creators")
    expect(page.locator("h1")).to_contain_text("Turn your post into a trip")
    box = page.locator("#fc-text").bounding_box()
    assert box["y"] + box["height"] <= viewport["height"], "the paste box is on the first screen"
    assert overflow(page) <= 1
    for width in (320, 390, 768, 1000, 1280, 1440):      # the 2026-09-30 lesson: no sideways scroll at any width
        page.set_viewport_size({"width": width, "height": 900})
        assert overflow(page) <= 1, width
    page.set_viewport_size(viewport)
    if viewport is PHONE:
        assert not too_small(page, "main a.btn, main button:not(.sr-only), main textarea, main summary")
    expect(page.locator(".fc-promise")).to_have_count(3)
    expect(page.locator("#fc-free")).to_contain_text("Free. Terms shown on day one.")
    expect(page.locator("#fc-example")).to_have_attribute("data-kind", "drawn")
    shot(page, f"page-{viewport['width']}")
    shot(page, f"fold-{viewport['width']}", full=False)


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_page_shows_a_real_trip_as_its_example_and_the_questions_open(visitor, base_url, viewport):
    live_trip(photo=True)
    page = visitor(viewport).new_page()
    page.goto(f"{base_url}/for-creators")
    expect(page.locator("#fc-example")).to_have_attribute("data-kind", "real")
    expect(page.locator("#fc-example")).to_contain_text("Three easy days in Santa Monica")
    first = page.locator(".fc-q").first
    assert first.get_attribute("open") is None
    tap(page, viewport, first.locator("summary"))
    expect(first).to_have_attribute("open", "")
    expect(first.locator("p")).to_be_visible()
    shot(page, f"real-{viewport['width']}")
    tap(page, viewport, page.get_by_role("link", name="Open the trip"))
    page.wait_for_url("**/trips/**")


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_text_pasted_before_signing_in_is_still_there_after(visitor, base_url, viewport):
    ctx = visitor(viewport)
    page = ctx.new_page()
    page.goto(f"{base_url}/for-creators")
    page.fill("#fc-text", "Day 1 we rode the wheel at the pier at 10:00 AM. Day 2 the Venice canals.")
    tap(page, viewport, page.locator("#fc-draft"))
    page.wait_for_url("**/signin**")
    ctx.request.post(f"{base_url}/signin", form={"email": "maya@example.com", "next": "/creators/import", "intent": "save"}, max_redirects=0)
    page.goto(f"{base_url}/creators/import")
    expect(page.locator("#ci-text")).to_have_value("Day 1 we rode the wheel at the pier at 10:00 AM. Day 2 the Venice canals.")
    page.reload()
    expect(page.locator("#ci-text")).to_have_value("")      # kept once only


# ---- F-184: the marker ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_a_creator_saves_their_marker(visitor, base_url, viewport):
    page = visitor(viewport, "maya@example.com").new_page()
    page.goto(f"{base_url}/creators/settings")
    assert overflow(page) <= 1
    if viewport is PHONE:
        assert not too_small(page, "main .btn, main input, main a")
    page.fill("#st-marker", "55x")
    tap(page, viewport, page.locator("#st-save"))
    expect(page.locator("#st-error")).to_contain_text("digits only")
    shot(page, f"marker-error-{viewport['width']}", full=False)
    page.fill("#st-marker", "555111")
    tap(page, viewport, page.locator("#st-save"))
    expect(page.locator("#st-saved")).to_have_text("Saved.")
    expect(page.locator("#st-says")).to_contain_text("Flights booked from your trips carry your marker")
    shot(page, f"marker-{viewport['width']}", full=False)


# ---- F-185: report and the captain's page ----------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_a_stranger_reports_a_trip_from_its_page(visitor, base_url, viewport):
    row, _, _ = live_trip(photo=True)
    page = visitor(viewport).new_page()
    page.goto(f"{base_url}/trips/{row['slug']}")
    expect(page.locator("#who-earns")).to_have_text("Bookings from this trip support GitAway.")
    shot(page, f"trip-{viewport['width']}")
    tap(page, viewport, page.locator("#report-this"))
    page.wait_for_url("**/report?trip=**")
    assert overflow(page) <= 1
    if viewport is PHONE:
        assert not too_small(page, "main .btn, main select, main textarea, main input:not([tabindex='-1'])")
    trap = page.locator(".rp-bee input").bounding_box()
    assert trap is None or trap["x"] + trap["width"] <= 0, "the honeypot sits off-screen, where a person never sees it"
    page.select_option("#rp-reason", "copyright")
    page.fill("#rp-note", "These photos are mine.")
    shot(page, f"report-{viewport['width']}", full=False)
    tap(page, viewport, page.locator("#rp-send"))
    expect(page.locator("#rp-thanks")).to_have_text("Thank you. The person who runs GitAway will read this.")
    assert [r["note"] for r in community_reports()] == ["These photos are mine."]


def community_reports():
    from gitaway import reports
    return reports.all_reports()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_captain_reads_a_report_and_takes_the_trip_down_and_back(visitor, base_url, viewport):
    row, handle, owner = live_trip(photo=True)
    affiliate.set_marker(owner["user_id"], "555111")
    from gitaway import reports
    reports.add("trip", row["slug"], "copyright", "These photos are mine.", "mia@example.com", "", "203.0.113.7")
    stranger = visitor(viewport).new_page()
    page = visitor(viewport, CAPTAIN).new_page()
    page.goto(f"{base_url}/admin")
    assert overflow(page) <= 1
    expect(page.locator("#ad-goal")).to_have_text("1 of 150")
    expect(page.locator("#ad-report-list")).to_contain_text("These photos are mine.")
    expect(page.locator(f"#c-{handle}")).to_contain_text("marker 555111")
    if viewport is PHONE:
        assert not too_small(page, "main .btn, main a.ad-link")
    shot(page, f"admin-{viewport['width']}")
    state = page.locator(f"#c-{handle} #state-{row['slug']}")
    expect(state).to_have_text("Live")
    tap(page, viewport, page.locator(f"#c-{handle} form[action='/admin/takedown'] button"))
    expect(state).to_have_text("Taken down")
    assert stranger.goto(f"{base_url}/trips/{row['slug']}").status == 404
    tap(page, viewport, page.locator(f"#c-{handle} form[action='/admin/restore'] button"))
    expect(state).to_have_text("Live")
    assert stranger.goto(f"{base_url}/trips/{row['slug']}").status == 200


def test_the_admin_page_is_a_404_in_the_browser_for_the_wrong_person(visitor, base_url):
    page = visitor(DESKTOP, "maya@example.com").new_page()
    assert page.goto(f"{base_url}/admin").status == 404
    assert visitor(DESKTOP).new_page().goto(f"{base_url}/admin").status == 404
    assert not community.has_real()
