"""F-235: For creators ("Golden hour") and Community trips ("Postcards") in a real browser at 390 and 1440, in light (the default, D-460) and dark, on and off the showcase: no sideways scroll,
phone targets 48px, text 4.5:1 (tests_browser/look.py; gradients are skipped there, so the hero's own pairs are measured in tests/test_creator_pages.py), the page's arrival finishes
on its own and reduced motion draws nothing animated. Set F235_SHOTS=1 to save docs/report/f235-*.png."""
import os
from pathlib import Path

import pytest

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
PAGES = (("for-creators", "/for-creators"), ("community", "/community"))


def open_page(browser, viewport, mode, path, base_url, reduced=True):
    phone = viewport is PHONE
    ctx = browser.new_context(viewport=viewport, reduced_motion="reduce" if reduced else "no-preference", has_touch=phone, is_mobile=phone)
    ctx.set_default_timeout(15000)
    ctx.add_init_script(f"try {{ localStorage.setItem('ga-mode', '{mode}') }} catch (e) {{}}" if mode == "dark" else "0")
    page = ctx.new_page()
    page.goto(base_url + path, wait_until="networkidle")
    return ctx, page


def shot(page, name):
    if os.getenv("F235_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f235-{name}.png"), full_page=True)


@pytest.mark.parametrize("showcase", ["1", "0"], ids=["showcase", "live"])
@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
@pytest.mark.parametrize("name,path", PAGES)
def test_the_joyful_pages_fit_read_and_are_easy_to_tap(browser, base_url, monkeypatch, name, path, viewport, mode, showcase):
    monkeypatch.setenv("GITAWAY_SHOWCASE", showcase)
    ctx, page = open_page(browser, viewport, mode, path, base_url)
    try:
        assert page.evaluate("document.documentElement.dataset.mode") == mode
        seen = audit(page)
        problems = [f"{key}: {seen[key][:6]}" for key in ("small", "tiny", "low", "glass") if seen[key]] + ([f"scrolls sideways by {seen['wide']}px"] if seen["wide"] > 1 else [])
        assert not problems, "\n".join(problems)
        shot(page, f"{name}-{'live-' if showcase == '0' else ''}{mode}-{viewport['width']}")
    finally:
        ctx.close()


@pytest.mark.parametrize("name,path", PAGES)
def test_with_motion_allowed_the_page_arrives_and_everything_ends_up_shown(browser, base_url, monkeypatch, name, path):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    ctx, page = open_page(browser, PHONE, "light", path, base_url, reduced=False)
    try:
        page.wait_for_timeout(2500)
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(1500)
        hidden = page.evaluate("""() => [...document.querySelectorAll('.fc-promise, .fc-faq, .fc-end-in, .hub-card, .hub-share')].filter(e => getComputedStyle(e).opacity < 0.99 && e.getBoundingClientRect().top < innerHeight).map(e => e.className)""")
        assert hidden == []
    finally:
        ctx.close()


@pytest.mark.parametrize("name,path", PAGES)
def test_reduced_motion_draws_nothing_animated(browser, base_url, monkeypatch, name, path):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    ctx, page = open_page(browser, PHONE, "light", path, base_url)
    try:
        moving = page.evaluate("""() => [...document.querySelectorAll('.fc *, .hub *')].filter(e => { const a = getComputedStyle(e).animationName; return a && a !== 'none'; }).map(e => e.className)""")
        assert moving == []
    finally:
        ctx.close()
