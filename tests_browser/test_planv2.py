"""F-252 in a real browser: the planning calendar at /trip/plan. A person taps empty time, names a plan and adds it; drags it to another time and day; pulls its bottom edge to make it longer; and
takes each of those back with Undo. At 390 the same moves work with a finger (a half-second hold, then drag) and with taps alone (the editor's stepper and duration chips). The page is checked
for 4.5:1 text over the frosted drawer and rail, 48px targets and no sideways scroll, in light and dark. Set F252_SHOTS=1 for docs/report/f252-*.png."""
import os
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.test_calendar import PICK
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"


@pytest.fixture
def plan(browser, base_url):
    """plan(viewport, scheme="light") -> a page on /trip/plan for a family with a booked trip (its own, so plans never carry over). Contexts are closed after the test."""
    contexts = []

    def make(viewport, scheme="light"):
        phone = viewport["width"] < 720
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=phone, is_mobile=phone)
        ctx.set_default_timeout(5000)
        if scheme == "dark":
            ctx.add_init_script("localStorage.setItem('ga-mode', 'dark')")      # the site's mode is the person's choice kept on the device (mode.js), not the system's
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": f"plan{time.time_ns()}@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form=PICK, max_redirects=0)
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.goto(f"{base_url}/trip/plan")
        page.wait_for_selector(".g-inner")
        return page

    yield make
    for c in contexts:
        c.close()


def shot(page, name):
    if os.environ.get("F252_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f252-{name}.png"))


def hh(page):
    return page.evaluate("() => { const g = document.querySelector('.g-inner'); return g.offsetHeight / parseFloat(g.style.getPropertyValue('--hours')); }")


def tap_slot(page, day, hour):
    """Tap empty time on a day's column at `hour` (the grid starts at 7 AM)."""
    col = page.locator(f".col[data-day='{day}']")
    col.scroll_into_view_if_needed()
    y = (hour - 7) * hh(page) + 6
    if page.evaluate("() => matchMedia('(pointer: coarse)').matches"):
        page.tap(f".col[data-day='{day}']", position={"x": 12, "y": y})
    else:
        page.click(f".col[data-day='{day}']", position={"x": 30, "y": y})


def add(page, day, hour, title):
    tap_slot(page, day, hour)
    expect(page.locator("#pl-pop")).to_be_visible()
    page.fill("#pl-pop .namefield input", title)
    page.click("#pl-pop .go1")
    expect(page.locator(f".ev[data-title='{title}']")).to_be_visible()
    return page.locator(f".ev[data-title='{title}']")


def times(ev):
    return int(ev.get_attribute("data-start")), int(ev.get_attribute("data-end"))


def day_of(page, title):
    return page.evaluate("(t) => document.querySelector(`.ev[data-title='${t}']`).closest('.col').dataset.day", title)


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_a_plan_is_added_moved_resized_and_each_undone(plan, viewport):
    page = plan(viewport)
    ev = add(page, 1, 12, "Pier walk")
    assert times(ev) == (720, 780)                                                    # tapped at noon: an hour long, saved as you go
    shot(page, f"{viewport['width']}-added")
    page.reload()
    page.wait_for_selector(".g-inner")
    assert times(page.locator(".ev[data-title='Pier walk']")) == (720, 780)           # it is stored, not only drawn
    # move it to 2 PM on the next day: a mouse drag, a full hour down and one column across
    ev = page.locator(".ev[data-title='Pier walk']")
    box, col2 = ev.bounding_box(), page.locator(".col[data-day='2']").bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 14)
    page.mouse.down()
    page.mouse.move(box["x"] + 20 + 10, box["y"] + 14 + 20, steps=4)
    page.mouse.move(col2["x"] + 30, box["y"] + 14 + 2 * hh(page), steps=6)
    shot(page, f"{viewport['width']}-dragging")
    page.mouse.up()
    page.wait_for_function("() => document.querySelector(\".ev[data-title='Pier walk']\").dataset.start === '840'")
    ev = page.locator(".ev[data-title='Pier walk']")
    assert times(ev) == (840, 900) and day_of(page, "Pier walk") == "2"
    # pull its bottom edge down an hour and a half
    box = ev.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] - 4)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] - 4 + hh(page) * 1.5, steps=6)
    shot(page, f"{viewport['width']}-resizing")
    page.mouse.up()
    page.wait_for_function("() => document.querySelector(\".ev[data-title='Pier walk']\").dataset.end === '990'")
    assert times(page.locator(".ev[data-title='Pier walk']")) == (840, 990)
    page.reload()
    page.wait_for_selector(".g-inner")
    assert times(page.locator(".ev[data-title='Pier walk']")) == (840, 990) and day_of(page, "Pier walk") == "2"
    # Undo takes the last change back, and the one before it
    page.locator(".ev[data-title='Pier walk']").click()
    page.locator("#pl-pop .btn2.danger").click()
    expect(page.locator(".ev[data-title='Pier walk']")).to_have_count(0)
    page.locator("#ga-toast button, .ga-toast button").first.click()                    # the toast's own Undo
    expect(page.locator(".ev[data-title='Pier walk']")).to_have_count(1)
    assert times(page.locator(".ev[data-title='Pier walk']")) == (840, 990)
    assert page.errors == []


def test_with_taps_alone_the_editor_moves_and_resizes_a_plan(plan):
    """The visible way for every gesture (touch.md): the editor's stepper and duration chips."""
    page = plan(PHONE)
    add(page, 1, 12, "Beach hour")
    page.locator(".ev[data-title='Beach hour']").tap()
    page.click("#pl-pop .step button >> nth=1")                                          # a quarter hour later
    page.click("#pl-pop .step button >> nth=1")
    page.click("#pl-pop .chips >> nth=0 >> text=2h")
    expect(page.locator("#pl-pop .go1")).to_contain_text("Save 12:30 PM, 2h")
    page.click("#pl-pop .go1")
    page.wait_for_function("() => document.querySelector(\".ev[data-title='Beach hour']\").dataset.start === '750'")
    assert times(page.locator(".ev[data-title='Beach hour']")) == (750, 870)


def test_a_finger_holds_then_drags_a_plan_and_a_plain_swipe_still_scrolls(plan):
    page = plan(PHONE)
    add(page, 1, 12, "Finger plan")
    cdp = page.context.new_cdp_session(page)

    def touch(kind, x=0, y=0):
        cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [] if kind == "touchEnd" else [{"x": x, "y": y}]})

    def centre():
        """F-255: the dock and the sections pill stack at the foot of the phone, so bring the plan to the middle of the day's own scroll, then to 560px down the screen (below the
        toolbar, clear of both bars), wait for any fling to stop, and return where a finger lands on it (checked: that point is the plan, not a bar)."""
        page.evaluate("""() => { const e = document.querySelector(".ev[data-title='Finger plan']"); e.scrollIntoView({block: 'center'}); window.scrollBy(0, e.getBoundingClientRect().top - 560); }""")
        page.wait_for_function("() => new Promise(r => { const a = [scrollY, document.querySelector('.g-body').scrollTop].join(); setTimeout(() => r(a === [scrollY, document.querySelector('.g-body').scrollTop].join()), 250); })")
        box = page.locator(".ev[data-title='Finger plan']").bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + 14
        assert page.evaluate("""([x, y]) => !!document.elementFromPoint(x, y).closest(".ev[data-title='Finger plan']")""", [x, y]), (x, y)
        return x, y
    x, y = centre()
    touch("touchStart", x, y)                                                           # no hold: a swipe moves the day, not the plan
    for i in range(1, 8):
        touch("touchMove", x, y - i * 25)
    touch("touchEnd")
    assert times(page.locator(".ev[data-title='Finger plan']")) == (720, 780)
    x, y = centre()
    touch("touchStart", x, y)
    page.wait_for_timeout(650)                                                          # the half-second hold arms it
    for i in range(1, 9):
        touch("touchMove", x, y + i * hh(page) / 4)
    touch("touchEnd")
    page.wait_for_function("() => document.querySelector(\".ev[data-title='Finger plan']\").dataset.start === '840'")
    assert times(page.locator(".ev[data-title='Finger plan']")) == (840, 900)


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_page_keeps_4_5_to_1_over_the_glass_with_48px_targets_and_no_sideways_scroll(plan, viewport, scheme):
    page = plan(viewport, scheme)
    assert page.evaluate("document.documentElement.dataset.mode") == scheme
    add(page, 1, 12, "Pier walk")
    for name in ("calendar", "drawer"):
        if name == "drawer":
            page.click("#pl-together" if viewport["width"] > 720 else ".dock [data-together]")
            expect(page.locator("#pl-side")).to_be_visible()
            page.wait_for_timeout(400)
        shot(page, f"{viewport['width']}{'-dark' if scheme == 'dark' else ''}-{name}")
        m = audit(page)
        assert m["wide"] <= 1 and m["low"] == [] and m["glass"] == [] and m["small"] == [], (name, m)
        assert all("(13px < 16)" in t and ("·" in t or "Pier" in t or "Skylark" in t or "Check" in t) for t in m["tiny"]), m["tiny"]      # only a calendar block's label on a phone (see D-632)
    assert page.errors == []


def test_the_rail_plus_drops_a_suggestion_where_it_fits_and_marks_it_done(plan):
    page = plan(DESKTOP)
    page.click("[data-sug='f0']")
    page.wait_for_selector("[data-sug='f0'].done")
    ev = page.locator(".ev[data-title='Saffron & Salt']")
    assert times(ev) == (720, 810) and day_of(page, "Saffron & Salt") == "0"            # noon, an hour and a half, the first quiet dry day (the sample's skies are dry)


def test_save_reads_the_plan_back_and_shows_what_is_stored(plan):
    page = plan(DESKTOP)
    add(page, 1, 12, "Pier walk")
    page.click("#pl-save")
    expect(page.locator("#pl-sheet")).to_be_visible()
    expect(page.locator("#pl-sheet .done-h b")).to_have_text("Plan saved")
    assert page.locator("#pl-sheet .cols").inner_text().lower().split() == ["days", "5", "plans", "1", "booked", "4"]
    shot(page, "1440-saved")
