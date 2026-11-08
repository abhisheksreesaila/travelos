"""F-191 in a real browser at phone (390) and laptop (1440) width: the creator's "Put this on your blog" panel, the Copy buttons and the toast. The server runs in this process, so a trip
is published straight into its community database. Set F191_SHOTS=1 to save screenshots to docs/report/f191-*.png."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import blogbutton
from tests.live_trips import live_trip
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
IDS = ["390", "1440"]


def shot(page, name):
    if os.getenv("F191_SHOTS"):
        page.wait_for_timeout(700)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f191-{name}.png"), full_page=True)


@pytest.fixture(autouse=True)
def live(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("GITAWAY_PUBLIC_URL", "https://gitaway.me")


@pytest.fixture
def visitor(browser, base_url):
    contexts = []

    def make(viewport, email=""):
        ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE, permissions=["clipboard-read", "clipboard-write"])
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        if email:
            ctx.request.post(f"{base_url}/signin", form={"email": email, "next": "/", "intent": "save"}, max_redirects=0)
        return ctx

    yield make
    for c in contexts:
        c.close()


def tap(viewport, locator):
    locator.tap() if viewport is PHONE else locator.click()


@pytest.mark.parametrize("path", ["trip", "settings"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_a_tap_on_copy_puts_the_snippet_on_the_clipboard_and_says_copied(visitor, base_url, viewport, path):
    row, handle, _ = live_trip()
    page = visitor(viewport, "maya@example.com").new_page()
    page.goto(f"{base_url}/trips/{row['slug']}" if path == "trip" else f"{base_url}/creators/settings")
    uid = "bb" if path == "trip" else "bb0"
    panel = page.locator(f"#{uid}")
    panel.scroll_into_view_if_needed()
    expect(panel.locator("h2")).to_have_text("Put this on your blog")
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1
    copy = page.locator(f"#{uid}-html-copy")
    assert copy.bounding_box()["height"] >= 44 and copy.bounding_box()["width"] >= 44
    for img in panel.locator("img").all():
        assert img.evaluate("i => i.complete && i.naturalWidth > 0"), "the badge draws"
    tap(viewport, copy)
    expect(page.locator("#ga-toast")).to_contain_text("Copied")
    assert page.evaluate("navigator.clipboard.readText()") == blogbutton.html_snippet(row["slug"], handle)
    page.wait_for_timeout(300)
    tap(viewport, page.locator(f"#{uid}-link-copy"))
    expect(page.locator("#ga-toast")).to_contain_text("Copied")
    assert page.evaluate("navigator.clipboard.readText()") == f"https://gitaway.me/trips/{row['slug']}?via={handle}"
    shot(page, f"{path}-{viewport['width']}")


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_a_reader_does_not_see_the_panel(visitor, base_url, viewport):
    row, _, _ = live_trip()
    page = visitor(viewport).new_page()
    page.goto(f"{base_url}/trips/{row['slug']}")
    expect(page.locator("h1")).to_be_visible()
    expect(page.locator("#bb")).to_have_count(0)
