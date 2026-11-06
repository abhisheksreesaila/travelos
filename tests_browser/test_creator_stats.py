"""F-192 in a real browser at phone (390) and laptop (1440) width: the creator's stats page. The server runs in this process, so trips and counts are written straight into its community
database. Set F192_SHOTS=1 to save screenshots to docs/report/f192-*.png."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from gitaway import affiliate, community
from tests.live_trips import live_trip
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
IDS = ["390", "1440"]
SHAPE = [0, 1, 0, 3, 2, 5, 4, 0, 6, 8, 5, 7, 12, 9, 6, 14, 10, 11, 18, 13, 9, 15, 20, 17, 12, 22, 19, 25, 21, 28]   # readers a day, oldest first


def shot(page, name):
    if os.getenv("F192_SHOTS"):
        page.wait_for_timeout(500)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f192-{name}.png"), full_page=True)


@pytest.fixture(autouse=True)
def live(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")


def seed():
    row, handle, s = live_trip()
    other, _, _ = live_trip(title="A long weekend in Malibu")
    today = datetime.now(timezone.utc).date()
    with community.connect() as db:
        for i, v in enumerate(SHAPE):
            day = (today - timedelta(days=len(SHAPE) - 1 - i)).isoformat()
            db.conn.execute(text("INSERT INTO trip_days (slug, day, views, forks, plans) VALUES (:s, :d, :v, :f, :p)"), {"s": row["slug"], "d": day, "v": v, "f": v // 6, "p": v // 3})
        db.conn.execute(text("INSERT INTO trip_days (slug, day, views) VALUES (:s, :d, 3)"), {"s": other["slug"], "d": today.isoformat()})
        db.conn.commit()
    for own in (True, True, True, False, False):
        affiliate.log_click(handle, "aviasales" if own else "klook", "flight" if own else "stay", own)
    return row


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_stats_page_reads_well_and_never_scrolls_sideways(browser, base_url, viewport):
    seed()
    ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE)
    ctx.set_default_timeout(9000)
    ctx.request.post(f"{base_url}/signin", form={"email": "maya@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page = ctx.new_page()
    page.goto(f"{base_url}/creators/stats")
    expect(page.locator("h1")).to_have_text("Your stats")
    expect(page.locator("#cs-readers")).to_have_text(str(sum(SHAPE) + 3))
    expect(page.locator("#cs-clicks")).to_have_text("5")
    expect(page.locator("#cs-marker")).to_contain_text("3 with your marker")
    expect(page.locator(".cs-spark")).to_have_count(2)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "the page scrolls sideways"
    if viewport is PHONE:   # the laptop scales its root down (0.75rem), so 44px is the phone's bar
        for target in page.locator(".cs-chip, .cs-name, .cs-more a").all():
            assert target.bounding_box()["height"] >= 43.5, target.inner_text()
    shot(page, f"stats-{viewport['width']}")
    page.get_by_role("link", name="7 days").click()
    expect(page).to_have_url(f"{base_url}/creators/stats?w=7")
    expect(page.locator(".cs-chip[aria-current=true]")).to_have_text("7 days")
    shot(page, f"stats-7-{viewport['width']}")
    page.goto(f"{base_url}/creators/stats?w=all")
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    ctx.close()
