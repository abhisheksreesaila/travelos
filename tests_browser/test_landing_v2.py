"""F-060: Landing v2 in a real browser: no sideways scroll, tiles that animate on hover and focus, a calendar that plays and rests complete."""
import pytest

from tests_browser.helpers import PHONE

WIDE = {"width": 1280, "height": 800}
FILLED = "() => [...document.querySelectorAll('#cal .slot[data-s]')].map(s => s.classList.contains('on'))"
STATE = "() => document.querySelector('#cal').dataset.state"


@pytest.fixture
def landing(browser, base_url):
    made = []

    def open_landing(viewport=WIDE, motion="reduce"):
        ctx = browser.new_context(viewport=viewport, reduced_motion=motion)
        ctx.set_default_timeout(8000)
        made.append(ctx)
        page = ctx.new_page()
        page.goto(f"{base_url}/")
        return page

    yield open_landing
    for c in made:
        c.close()


@pytest.mark.parametrize("viewport", [WIDE, PHONE, {"width": 1000, "height": 800}, {"width": 320, "height": 700}], ids=["1280", "390", "1000", "320"])
def test_no_sideways_scroll(landing, viewport):
    page = landing(viewport)
    page.wait_for_timeout(300)
    assert page.evaluate("document.documentElement.scrollWidth") <= page.evaluate("document.documentElement.clientWidth")


def _transform(page):
    return page.eval_on_selector(".a-panes .p1", "e => getComputedStyle(e).transform")


@pytest.mark.parametrize("how", ["hover", "focus"])
def test_feature_tile_animation_changes_on_hover_and_focus(landing, how):
    page = landing()
    tile = page.locator(".feature").first
    before = _transform(page)
    assert before != "none"  # rests apart
    if how == "hover":
        tile.hover()
    else:
        tile.focus()
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")  # keyboard focus, so :focus-visible applies
    page.wait_for_function("() => getComputedStyle(document.querySelector('.a-panes .p1')).transform === 'none'")
    assert _transform(page) != before


def test_the_calendar_rests_complete_under_reduced_motion(landing):
    page = landing(motion="reduce")
    page.locator("#cal").scroll_into_view_if_needed()
    page.wait_for_timeout(1500)
    assert page.evaluate(FILLED) == [True] * 7
    assert page.locator(".cursor").count() == 0  # no cursors fly about
    assert not page.locator("#replay").is_visible()  # nothing to replay, so no button that does nothing


def test_a_calendar_block_starts_unfilled_then_fills_when_motion_is_allowed(landing):
    page = landing(motion="no-preference")
    assert page.evaluate(FILLED) == [True] * 7  # complete before it starts
    page.locator("#cal").scroll_into_view_if_needed()
    page.wait_for_function(f"() => ({STATE[6:]}) === 'playing'")
    assert page.evaluate(FILLED)[0] is False  # the first plan is not dropped yet
    page.wait_for_function("() => document.querySelector('#cal .slot[data-s=s1]').classList.contains('on')")
    assert page.evaluate(FILLED)[-1] is False  # the last one is still to come
    page.wait_for_function(f"() => ({STATE[6:]}) === 'resting'", timeout=12000)
    assert page.evaluate(FILLED) == [True] * 7
    page.wait_for_function(f"() => ({STATE[6:]}) === 'playing'", timeout=8000)  # and it loops


def test_watch_it_again_replays(landing):
    page = landing(motion="no-preference")
    page.locator("#replay").scroll_into_view_if_needed()
    page.click("#replay")
    page.wait_for_function(f"() => ({STATE[6:]}) === 'playing'")
    assert page.evaluate(FILLED)[0] is False


def test_each_tile_illustration_has_a_tint_and_hidden_parts_are_invisible_at_rest(landing):
    page = landing()
    for cls in ["a-panes", "a-total", "a-together", "a-fork"]:
        bg = page.eval_on_selector(f".anim.{cls}", "e => getComputedStyle(e).backgroundColor")
        assert bg not in ("rgb(255, 255, 255)", "rgba(0, 0, 0, 0)"), (cls, bg)
    assert page.eval_on_selector(".a-fork .dot2", "e => getComputedStyle(e).opacity") == "0"
    # the branch line is fully undrawn: the dash is longer than the path and offset past it
    assert page.eval_on_selector(".a-fork .branch", "e => parseFloat(getComputedStyle(e).strokeDashoffset) >= e.getTotalLength() && parseFloat(getComputedStyle(e).strokeDasharray) >= e.getTotalLength()")
    assert page.eval_on_selector_all(".a-together .blk, .a-together .heart", "els => els.every(e => getComputedStyle(e).opacity === '0')")


def test_the_fork_line_scrolls_to_community_trips(landing):
    page = landing()
    page.click(".forkline a")
    page.wait_for_function("location.hash === '#community-trips'")
    assert page.locator("#community-trips").is_visible()
