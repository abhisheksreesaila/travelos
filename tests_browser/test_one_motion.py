"""F-171: a move is one motion and a swipe follows the finger, sampled frame by frame in a real browser.

Move (390 and 1440): the save answers while the dropped block is still landing; the toast comes with the reply (not after the landing), the refreshed day goes in at once, and the blocks the
move pushed aside glide in the same breath, so there is never a frame between the first movement and the last in which nothing moves ("land, stop, glide" is gone). Save, Undo and a refusal
are still checked in test_liquid.py, test_day_grid.py and test_day_mouse.py.

Swipe (390): the day follows the finger 1:1; on lift it does not jump back to 0, the slide goes on from where the finger let go; a short or slow swipe springs back (a move, not a jump).
A finger whose element is removed, or whose cancel comes outside the canvas, no longer leaves the canvas thinking a finger is down (CZ.gesturing())."""
import re
import time

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_day_grid import SUNDAY, fire, hold_block, now, open_day, plan, ppm, slide, toast
from tests_browser.test_liquid import REC, frames, slow_save, trace
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures

# ---- the move: one motion --------------------------------------------------------------------------------------------------------------


def reply_time(page):
    """When the browser had the save's answer, on the recorder's clock origin (performance.now())."""
    return page.evaluate("() => performance.getEntriesByType('resource').filter(e => e.name.includes('/trip/canvas/plan')).pop().responseEnd")


def check_one_motion(page, rec, t0, a, b, spring):
    """The toast and the neighbour's glide both start at the reply, while the dropped block is still moving, and nothing stands still in between."""
    reply = reply_time(page) - t0
    tr_a, tr_b = trace(rec, a), trace(rec, b)
    first_toast = min(o["t"] for o in rec if "q" in o)
    assert first_toast - reply < 150, (first_toast, reply)                                  # the toast shows with the answer
    b_start = min(t for t, v in tr_b if v["lands"] or v["moving"])
    assert b_start - reply < 150, (b_start, reply)                                           # the neighbours' glide starts with the answer
    a_end = max(t for t, v in tr_a if v["lands"] or v["moving"])
    assert b_start < a_end, (b_start, a_end)                                                 # ... while the dropped block is still moving (it lands, then takes its lane): one motion
    moving = [o["t"] for o in rec if any(v["lands"] or v["moving"] for v in o["b"].values())]
    first, last = min(moving), max(moving)
    still = [o["t"] for o in rec if first < o["t"] < last and not any(v["lands"] or v["moving"] for v in o["b"].values())]
    assert still == [], still                                                                # no frame between the first movement and the last in which nothing moves
    assert last - reply < spring + 200, (last, reply, spring)                                # it is over one spring after the answer


def test_a_move_is_one_motion_the_toast_and_the_neighbours_come_with_the_answer(canvas_page):
    page = canvas_page(viewport=PHONE, motion="no-preference")
    a = plan("Lunch", 12 * 60, 13 * 60)
    b = plan("Museum", 14 * 60, 15 * 60)
    open_day(page)
    slow_save(page, 0.2)
    start = hold_block(page, a.id)
    end = slide(page, start, (start[0], start[1] + ppm(page) * 120))                        # onto the museum's hour: they now sit side by side
    page.evaluate("(" + REC.strip() + ")()")
    t0 = page.evaluate("performance.now()")
    fire(page, "pointerup", *end)
    rec = frames(page, 2200)
    assert now(a.id)[0] == 14 * 60
    check_one_motion(page, rec, t0, a.id, b.id, page.evaluate("GA.motion.t('spring')"))
    tr = trace(rec, b.id)
    assert abs(tr[-1][1]["width"] - tr[0][1]["width"]) > 20                                  # it was made narrower for the lane
    expect(toast(page).get_by_role("button", name="Undo")).to_be_visible()
    toast(page).get_by_role("button", name="Undo").click()
    expect(toast(page)).to_have_text("Put back")
    assert now(a.id)[:2] == (12 * 60, 13 * 60)


def test_on_the_laptop_a_move_is_settled_and_toasted_as_the_answer_comes(canvas_page):
    page = canvas_page(viewport=DESKTOP, touch=False, motion="no-preference")
    a = plan("Lunch", 12 * 60, 13 * 60)
    b = plan("Museum", 14 * 60, 15 * 60)
    open_day(page, SUNDAY)
    slow_save(page, 0.2)
    box = page.locator(f'.cz-gb[data-act="{a.id}"]').bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 9):
        page.mouse.move(x, y + ppm(page) * 120 * i / 8)
        page.wait_for_timeout(16)
    page.evaluate("(" + REC.strip() + ")()")
    t0 = page.evaluate("performance.now()")
    page.mouse.up()
    rec = frames(page, 1200)
    assert now(a.id)[0] == 14 * 60
    reply = reply_time(page) - t0
    first_toast = min(o["t"] for o in rec if "q" in o)
    assert first_toast - reply < 150, (first_toast, reply)                                   # the laptop's toast is not held back either
    tr = trace(rec, b.id)
    assert abs(tr[-1][1]["width"] - tr[0][1]["width"]) > 20
    changed = [t for (t, v), (_, w) in zip(tr, tr[1:]) if abs(v["width"] - w["width"]) > 0.5]
    assert changed and max(changed) - reply < 250, (changed[-3:], reply)                     # the neighbour has its new lane within a short fade of the answer


# ---- the swipe: follows the finger, carries on from the lift ---------------------------------------------------------------------------

SWIPE_REC = """() => { window.__sw = []; const t0 = performance.now(), base = window.__base;
  (function f() {
    const v = document.querySelector('.cz-view'), r = v && v.getBoundingClientRect(), o = { t: performance.now() - t0, day: v && v.dataset.day, left: r && r.left };
    o.base = base;
    const cs = getComputedStyle(document.documentElement, '::view-transition-old(root)');
    o.on = !!document.documentElement.dataset.czDir;
    const m = /matrix\\(([^)]*)\\)/.exec(cs.transform || '');
    o.tx = m ? parseFloat(m[1].split(',')[4]) : 0;
    o.op = +cs.opacity;
    window.__sw.push(o);
    requestAnimationFrame(f); })(); }"""


def visual_x(rec):
    """How far the old screen is from its resting place, frame by frame: the level itself, then (once the slide has begun, the old screen is a picture) what it was plus the picture's move."""
    out, held, began = [], 0.0, False
    for o in rec:
        if o["on"]:
            began = True
            out.append((o["t"], held + o["tx"], o["op"]))
        elif began:
            break                                                                            # (the slide is over: the new day is at rest)
        else:
            held = o["left"] - o["base"] if o["left"] is not None else 0.0
            out.append((o["t"], held, 1.0))
    return out


def finger(page, x, y):
    return lambda kind, px: page.evaluate("""([kind, x, y, id]) => { const el = document.elementFromPoint(x, y) || document.body;
      el.dispatchEvent(new PointerEvent(kind, { pointerId: id, pointerType: 'touch', clientX: x, clientY: y, bubbles: true, cancelable: true, isPrimary: true })); }""", [kind, px, y, 9])


def left_of(page):
    return page.evaluate("document.querySelector('.cz-view').getBoundingClientRect().left")


@pytest.fixture
def day_page(canvas_page):
    page = canvas_page(viewport=PHONE, motion="no-preference")
    open_day(page, SUNDAY)
    page.wait_for_timeout(600)                                                               # (the neighbours are fetched ahead)
    return page


def test_a_swipe_follows_the_finger_one_to_one_and_the_slide_goes_on_from_where_it_let_go(day_page):
    page = day_page
    rest = left_of(page)
    f = finger(page, 300, 640)
    f("pointerdown", 300)
    for i in range(1, 6):
        f("pointermove", 300 - 24 * i)
        page.wait_for_timeout(16)
        assert abs((left_of(page) - rest) - (-24 * i)) <= 1, (i, left_of(page) - rest)      # the day is exactly where the finger has gone
    page.evaluate("b => { window.__base = b; }", rest)
    page.evaluate(SWIPE_REC)
    f("pointerup", 180)
    page.wait_for_timeout(1000)
    rec = page.evaluate("window.__sw")
    expect(page.locator(".cz-view")).to_have_attribute("data-day", str(SUNDAY + 1))
    xs = [(t, x, op) for t, x, op in visual_x(rec) if t < 700]
    assert xs[0][1] == pytest.approx(-120, abs=2), xs[:3]                                    # the first frame after the lift is where the finger left it
    seen = [(t, x) for t, x, op in xs if op > 0.15]
    assert all(b[1] <= a[1] + 1 for a, b in zip(seen, seen[1:])), seen                       # it never turns back toward 0
    assert all(abs(b[1] - a[1]) < 60 for a, b in zip(seen, seen[1:])), seen                  # and never jumps between two frames
    assert min(x for _, x in seen) < -125                                                 # the slide carried on past the finger's place


@pytest.mark.parametrize("slow", [False, True], ids=["short", "slow"])
def test_a_short_or_slow_swipe_springs_back_as_a_move_and_the_day_stays(day_page, slow):
    page = day_page
    rest = left_of(page)
    f = finger(page, 300, 640)
    f("pointerdown", 300)
    dx = -120 if slow else -30
    for i in range(1, 6):
        f("pointermove", 300 + dx * i / 5)
        page.wait_for_timeout(210 if slow else 16)
    assert abs((left_of(page) - rest) - dx) <= 1
    page.evaluate("b => { window.__base = b; }", rest)
    page.evaluate(SWIPE_REC)
    f("pointerup", 300 + dx)
    page.wait_for_timeout(900)
    rec = page.evaluate("window.__sw")
    xs = [x for _, x, _ in visual_x(rec)]
    assert xs[0] < dx * 0.5, xs[:4]                                                          # the first frame is still out
    assert [x for x in xs if dx * 0.95 < x < -1] != [], xs                                   # it comes back through the places between (a move, not a jump)
    assert abs(xs[-1]) < 0.5 and abs(left_of(page) - rest) < 0.5
    assert all(b >= a - 1 for a, b in zip(xs, xs[1:])), xs                                   # (monotonic: no wobble)
    expect(page.locator(".cz-view")).to_have_attribute("data-day", str(SUNDAY))


# ---- a finger the canvas can lose ---------------------------------------------------------------------------------------------------------

def test_a_finger_whose_element_is_removed_or_whose_cancel_is_outside_the_canvas_does_not_stick(day_page):
    page = day_page
    assert page.evaluate("CZ.gesturing()") is False
    for how in ("removed", "cancel-outside"):
        page.evaluate("""(how) => { const el = document.querySelector('.cz-view .cz-head') || document.querySelector('.cz-view');
          el.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 5, pointerType: 'touch', clientX: 200, clientY: 300, bubbles: true, cancelable: true, isPrimary: true }));
          window.__down = CZ.gesturing();
          if (how === 'removed') { el.remove(); document.body.dispatchEvent(new PointerEvent('pointerup', { pointerId: 5, pointerType: 'touch', bubbles: true })); }
          else document.body.dispatchEvent(new PointerEvent('pointercancel', { pointerId: 5, pointerType: 'touch', bubbles: true })); }""", how)
        assert page.evaluate("window.__down") is True, how
        assert page.evaluate("CZ.gesturing()") is False, how
        if how == "removed":
            open_day(page, SUNDAY)
