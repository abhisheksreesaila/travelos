"""F-108: the one toast. Every pop-up message is a light frosted pill at the top, just under the heading (the day's heading, the compact bar that replaces it, the phone header on Family),
centred and never wider than 22rem, its words wrapping; Undo is a clear 2.75rem button inside it; it glides down 0.75rem while fading in (no bounce), a new one takes the old one's place
without the pill moving, it fades away after 4.5 s (9 s with Undo) and waits while it is pressed; reduced motion has no glide; it never covers the heading's controls or the tab bar and
sits above the Ask sheet. At 390 and 320 wide. Screenshots on request: F108_SHOTS=<folder>."""
import os
import re

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE
from tests_browser.test_day_grid import ari, fire, hold_block, now, open_day, plan, ppm, slide
from tests_browser.test_trip_canvas import NARROW, canvas_page, model, settle  # noqa: F401 - fixtures

TEXT = "Universal Studios – Upper Lot now ends 2:55 PM"
LONG = "Universal Studios – Upper Lot now ends 2:55 PM and the family's lunch moved to a quieter place by the pier"


@pytest.fixture(params=[PHONE, NARROW], ids=["390", "320"])
def vp(request):
    return request.param


def shot(page, name):
    if os.environ.get("F108_SHOTS") and page.viewport_size["width"] == 390:
        page.screenshot(path=os.path.join(os.environ["F108_SHOTS"], name))


def toast(page):
    return page.locator(".ga-toast")


def say(page, text=TEXT, undo=False, **opts):
    page.evaluate("([t, undo, o]) => GA.toast(t, Object.assign(undo ? { undo: () => { window.__undone = (window.__undone || 0) + 1; } } : {}, o))", [text, undo, opts])


def rect(page, sel):
    return page.evaluate("s => { const n = document.querySelector(s); if (!n) return null; const r = n.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height, b: r.bottom, r: r.right }; }", sel)


def settled(page):
    expect(toast(page)).to_have_count(1)
    page.wait_for_function("() => { const t = document.querySelector('.ga-toast'); return t && t.classList.contains('is-in') && getComputedStyle(t).opacity === '1'; }")
    page.wait_for_timeout(300)


def no_cover(page):
    """Nothing of the heading (its switch, map, SOS) is under the toast."""
    return page.evaluate("""() => { const t = document.querySelector('.ga-toast').getBoundingClientRect(); let hit = [];
      document.querySelectorAll('.cz-head a, .cz-head button, .cz-fold.is-on a, .cz-fold.is-on button, .tp-head a, .tp-head button').forEach(b => { const r = b.getBoundingClientRect();
        if (r.width && r.height && !(r.right <= t.left || r.left >= t.right || r.bottom <= t.top || r.top >= t.bottom)) hit.push(b.textContent.trim() || b.id); });
      return hit; }""")


# ---- where it is --------------------------------------------------------------------------------------------------------------------

def test_the_toast_sits_centred_under_the_days_heading_above_the_grid_and_the_tab_bar(canvas_page, vp):
    page = canvas_page(viewport=vp)
    open_day(page)
    page.evaluate("window.scrollTo(0, 0)")
    say(page, undo=True)
    settled(page)
    t, head, tabs, grid = rect(page, ".ga-toast"), rect(page, ".cz-head"), rect(page, ".ph-tabs"), rect(page, "#cz-grid")
    assert t["y"] >= head["b"] - 0.5                                                      # under the heading
    assert t["b"] <= tabs["y"] and t["b"] < grid["y"] + grid["h"] / 2                     # above the tab bar, near the top of the day
    assert abs((t["x"] + t["w"] / 2) - vp["width"] / 2) <= 1 and t["w"] <= 22 * 16 + 1    # centred, at most 22rem
    assert t["x"] >= 8 and t["r"] <= vp["width"] - 8
    assert no_cover(page) == []
    box = toast(page).evaluate("t => ({ undo: t.querySelector('.ga-toast-undo').getBoundingClientRect().height, w: t.querySelector('.ga-toast-undo').getBoundingClientRect().width, role: t.getAttribute('role'), live: t.getAttribute('aria-live'), id: t.id })")
    assert box["undo"] >= 43.9 and box["w"] >= 43.9 and box["role"] == "status" and box["live"] == "polite"
    shot(page, "toast-390.png")


def test_the_toast_follows_the_compact_bar_when_the_heading_has_scrolled_away(canvas_page, vp):
    page = canvas_page(viewport=vp)
    plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    page.evaluate("window.scrollTo(0, 900)")
    page.wait_for_selector(".cz-fold.is-on .cz-fold-bar")
    page.wait_for_timeout(400)
    say(page, undo=True)
    settled(page)
    t, bar = rect(page, ".ga-toast"), rect(page, ".cz-fold.is-on .cz-fold-bar")
    assert t["y"] >= bar["b"] - 0.5 and no_cover(page) == []
    page.evaluate("window.scrollTo(0, 0)")                                                # and it comes down with the heading when the page is scrolled back
    page.wait_for_timeout(500)
    t, head = rect(page, ".ga-toast"), rect(page, ".cz-head")
    assert t["y"] >= head["b"] - 0.5 and no_cover(page) == []


def test_the_toast_is_the_same_on_the_week_and_on_family(canvas_page, vp, base_url):
    page = canvas_page(viewport=vp)
    assert page.locator(".cz-view[data-level=week]").count() == 1
    page.evaluate("window.scrollTo(0, 0)")
    say(page)
    settled(page)
    t, head, tabs = rect(page, ".ga-toast"), rect(page, ".cz-head"), rect(page, ".ph-tabs")
    assert t["y"] >= head["b"] - 0.5 and t["b"] <= tabs["y"] and no_cover(page) == []
    page.goto(f"{base_url}/trip/family")
    page.wait_for_selector(".tp-head")
    say(page, undo=True)
    settled(page)
    t, head, tabs = rect(page, ".ga-toast"), rect(page, ".tp-head"), rect(page, ".ph-tabs")
    assert t["y"] >= head["b"] - 0.5 and t["b"] <= tabs["y"] and no_cover(page) == []
    assert abs((t["x"] + t["w"] / 2) - vp["width"] / 2) <= 1
    elsewhere = page.evaluate("() => { const r = document.querySelector('.ga-toast').getBoundingClientRect(), e = document.elementFromPoint(r.x + r.width / 2, r.y + 6); return !!e && !!e.closest('.ga-toast'); }")
    assert elsewhere
    shot(page, "toast-family-390.png")


def test_a_toast_over_the_ask_sheet_stays_on_top_and_does_not_cover_the_tab_bar(canvas_page, vp):
    page = canvas_page(viewport=vp)
    open_day(page)
    page.locator('.ph-tab[data-ask="sheet"]').tap()
    expect(page.locator("#ak-sheet")).to_be_visible()
    say(page, undo=True)
    settled(page)
    top = page.evaluate("() => { const r = document.querySelector('.ga-toast').getBoundingClientRect(), e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return !!e && !!e.closest('.ga-toast'); }")
    assert top and rect(page, ".ga-toast")["b"] <= rect(page, ".ph-tabs")["y"]


def test_long_words_wrap_and_nothing_is_cut(canvas_page, vp):
    page = canvas_page(viewport=vp)
    open_day(page)
    say(page, LONG + " " + "x" * 60, undo=True)
    settled(page)
    got = toast(page).evaluate("""t => { const s = t.querySelector('.ga-toast-t'), r = t.getBoundingClientRect(), u = t.querySelector('.ga-toast-undo').getBoundingClientRect();
      return { t: s.scrollHeight <= s.clientHeight + 1 && s.scrollWidth <= s.clientWidth + 1, box: t.scrollWidth <= t.clientWidth + 1, inside: r.left >= 0 && r.right <= innerWidth, undo: u.left >= r.left && u.right <= r.right + 0.5, ov: getComputedStyle(s).overflow, tr: getComputedStyle(s).textOverflow }; }""")
    assert got["t"] and got["box"] and got["inside"] and got["undo"] and got["tr"] != "ellipsis"
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


# ---- how it moves --------------------------------------------------------------------------------------------------------------------

def test_it_glides_down_with_the_pages_calm_motion_and_reduced_motion_has_no_glide(browser, base_url, model, vp):
    results = {}
    for motion in ("no-preference", "reduce"):
        ctx = browser.new_context(viewport=vp, reduced_motion=motion, has_touch=True, is_mobile=True)
        try:
            ctx.set_default_timeout(9000)
            ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
            ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
            page = ctx.new_page()
            page.goto(f"{base_url}/trip/family")
            page.wait_for_selector(".tp-head")
            page.evaluate("""() => { GA.toast('Calm'); window.__start = (() => { const t = document.querySelector('.ga-toast'), s = getComputedStyle(t);
                 return { opacity: s.opacity, translate: s.translate }; })(); }""")
            start = page.evaluate("window.__start")
            settled(page)
            end = toast(page).evaluate("t => { const s = getComputedStyle(t); return { opacity: s.opacity, translate: s.translate, dur: s.transitionDuration, prop: s.transitionProperty, ease: s.transitionTimingFunction }; }")
            results[motion] = (start, end)
        finally:
            ctx.close()
    start, end = results["no-preference"]
    assert start["opacity"] == "0" and start["translate"] == "0px -12px"                  # 0.75rem above where it settles
    assert end["opacity"] == "1" and end["translate"] in ("none", "0px", "0px 0px")
    assert end["dur"].startswith("0.24s") and "translate" in end["prop"] and "opacity" in end["prop"] and "cubic-bezier(0.25, 0.8, 0.25, 1)" in end["ease"]      # --motion-dur and --motion-ease: no spring
    start, end = results["reduce"]
    assert start["translate"] in ("none", "0px", "0px 0px") and end["dur"] in ("0s", "0s, 0s")


def test_a_new_toast_takes_the_old_ones_place_without_stacking_or_moving(canvas_page, vp):
    page = canvas_page(viewport=vp, motion="no-preference")
    open_day(page)
    page.evaluate("window.scrollTo(0, 0)")
    say(page, "First thing", undo=True)
    settled(page)
    first = rect(page, ".ga-toast")
    page.evaluate("() => { GA.toast('Second thing, a little longer than the first'); GA.toast('Third thing'); }")
    counts = []
    for _ in range(8):
        counts.append(page.evaluate("document.querySelectorAll('.ga-toast').length"))
        page.wait_for_timeout(40)
    assert set(counts) == {1}                                                             # never two
    expect(toast(page)).to_contain_text("Third thing")
    page.wait_for_timeout(350)
    assert toast(page).locator(".ga-toast-undo").count() == 0 and toast(page).locator(".ga-toast-t").count() == 1
    again = rect(page, ".ga-toast")
    assert abs(again["y"] - first["y"]) <= 1 and page.evaluate("document.querySelector('.ga-toast').classList.contains('is-in')")      # the pill did not slide again
    assert toast(page).get_attribute("id") == "ga-toast"


def test_two_real_moves_in_a_row_leave_one_toast_and_undo_puts_the_plan_back(canvas_page, vp):
    page = canvas_page(viewport=vp)
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    start = hold_block(page, lunch.id)
    end = slide(page, start, (start[0], start[1] + ppm(page) * 30))
    fire(page, "pointerup", *end)
    expect(toast(page)).to_contain_text("Lunch moved to 12:30 PM")
    assert toast(page).count() == 1 and now(lunch.id)[:2] == (12 * 60 + 30, 13 * 60 + 30)
    undo = toast(page).get_by_role("button", name="Undo")
    expect(undo).to_be_visible()
    undo.tap()
    expect(toast(page)).to_have_text("Put back")
    assert toast(page).count() == 1 and now(lunch.id)[:2] == (12 * 60, 13 * 60)
    settled(page)
    assert no_cover(page) == []


def test_undo_in_a_toast_runs_its_action_once_and_the_toast_goes(canvas_page, vp):
    page = canvas_page(viewport=vp)
    open_day(page)
    say(page, undo=True)
    settled(page)
    toast(page).get_by_role("button", name="Undo").tap()
    expect(toast(page)).to_have_count(0)
    assert page.evaluate("window.__undone") == 1


# ---- how long it stays ---------------------------------------------------------------------------------------------------------------

def test_it_fades_after_4_and_a_half_seconds_and_9_with_undo_and_waits_while_pressed(canvas_page, vp):
    page = canvas_page(viewport=vp, motion="no-preference")
    open_day(page)
    page.clock.install()
    say(page, "Quiet")
    page.clock.run_for(100)
    expect(toast(page)).to_have_count(1)
    page.clock.run_for(4200)
    assert toast(page).count() == 1 and page.evaluate("document.querySelector('.ga-toast').classList.contains('is-in')")
    page.clock.run_for(400)
    assert not page.evaluate("document.querySelector('.ga-toast').classList.contains('is-in')")        # fading
    page.clock.run_for(500)
    assert toast(page).count() == 0
    say(page, "With undo", undo=True)
    page.clock.run_for(8800)
    assert toast(page).count() == 1 and page.evaluate("document.querySelector('.ga-toast').classList.contains('is-in')")
    page.clock.run_for(400)
    assert not page.evaluate("document.querySelector('.ga-toast').classList.contains('is-in')")
    page.clock.run_for(500)
    assert toast(page).count() == 0
    say(page, "Held down")                                                                  # a finger on it keeps it
    page.clock.run_for(100)
    page.evaluate("document.querySelector('.ga-toast').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch' }))")
    page.clock.run_for(30000)
    assert toast(page).count() == 1 and page.evaluate("document.querySelector('.ga-toast').classList.contains('is-in')")
    page.evaluate("window.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, pointerType: 'touch' }))")
    page.clock.run_for(4000)
    assert toast(page).count() == 1
    page.clock.run_for(1200)
    assert toast(page).count() == 0


def test_reduced_motion_removes_it_at_once_with_no_fade(canvas_page, vp):
    page = canvas_page(viewport=vp, motion="reduce")
    open_day(page)
    page.clock.install()
    say(page, "Quiet")
    page.clock.run_for(100)
    assert toast(page).evaluate("t => getComputedStyle(t).transitionDuration") in ("0s", "0s, 0s") and toast(page).evaluate("t => getComputedStyle(t).translate") in ("none", "0px", "0px 0px")
    page.clock.run_for(4500)
    assert toast(page).count() == 0


# ---- every other pop-up is this one -------------------------------------------------------------------------------------------------

def test_the_ask_sheets_result_is_the_same_toast_with_a_link_to_the_day(canvas_page, vp):
    page = canvas_page(viewport=vp)
    open_day(page)
    page.evaluate("GA.toast('Added 1 plan · The family has been told', { href: '/trip/canvas?day=1', label: 'See the day', ms: 7000 })")
    settled(page)
    link = toast(page).locator("a.ga-toast-act")
    expect(link).to_have_text("See the day")
    assert link.bounding_box()["height"] >= 43.9 and page.locator(".ak-toast, .cz-toast, .cal-toast").count() == 0
