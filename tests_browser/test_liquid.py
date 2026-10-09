"""F-112: a changed block and a sent bubble move like liquid, in a real browser at 390 wide with the real motion on. Frames are sampled with requestAnimationFrame from the moment the
finger lets go (or the menu is pressed, or Send is) through the save and the refresh to rest, and the numbers are what the captain's eye sees:
  - a dropped, resized or nudged block never jumps between two frames (a spring's steps stay a fraction of the whole move, and once it is at rest nothing moves, even when the refreshed day
    replaces the element), exactly one `land` animation moves it, and the toast's first frame comes after the block has landed (the save is slow here on purpose, so the refresh and the
    toast would otherwise arrive mid-move); Undo still works the moment the toast shows;
  - a block that another block's move pushed aside glides to its new lane (no jump);
  - (the chat's bubbles no longer move at all, F-118: tests_browser/test_thread.py)."""
import re
import time

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE
from tests_browser.test_day_grid import fire, hold_block, now, open_day, plan, ppm, slide, toast
from tests_browser.test_day_menu import hold_and_let_go, menu_item
from tests_browser.test_trip_canvas import NARROW, canvas_page, model  # noqa: F401 - fixtures

# One recorder for the whole page: every frame, the geometry of the plan blocks (by act), a serial for each element (to see it being replaced), the number of land/flip animations on it,
# the toast, and the chat bubbles (by position from the end of the list).
REC = """() => { window.__rec = []; const t0 = performance.now(), ids = new WeakMap(); let n = 0; const id = e => { if (!ids.has(e)) ids.set(e, ++n); return ids.get(e); };
  (function f() {
    const o = { t: performance.now() - t0, y: scrollY, b: {}, m: [], landing: !!(window.CZ && CZ.landing && CZ.landing()) };
    document.querySelectorAll('.cz-gb[data-act]').forEach(b => { const r = b.getBoundingClientRect();
      o.b[b.dataset.act] = { top: r.top, left: r.left, height: r.height, width: r.width, id: id(b), lands: b.getAnimations().filter(a => a.id === 'ga-land').length, moving: b.getAnimations().filter(a => a.transitionProperty === undefined && a.animationName === undefined).length, sel: b.classList.contains('is-selected') }; });
    const z = document.querySelector('.cz-g-zoom'); o.zoom = !!(z && z.classList.contains('is-zooming'));
    const q = document.querySelector('.ga-toast'); if (q) { const r = q.getBoundingClientRect(); o.q = { top: r.top, op: +getComputedStyle(q).opacity }; }
    const th = document.getElementById('ft-thread'); if (th) { o.th = th.getBoundingClientRect().toJSON(); const c = document.getElementById('ft-compose'); o.c = c.getBoundingClientRect().toJSON();
      const i = document.getElementById('ft-text'); o.i = i.getBoundingClientRect().toJSON();
      Array.from(th.children).filter(e => e.classList.contains('ft-msg')).forEach((e, k, all) => { const r = e.getBoundingClientRect(), b = e.querySelector('.ft-bub');
        o.m.push({ top: r.top, left: r.left, height: r.height, width: r.width, id: id(e), pending: e.classList.contains('is-pending'), n: all.length - k, op: b ? +getComputedStyle(b).opacity : 1,
          text: e.textContent.trim(), anims: e.getAnimations().length }); }); }
    window.__rec.push(o); requestAnimationFrame(f); })(); }"""


def frames(page, ms=1700):
    page.wait_for_timeout(ms)
    return page.evaluate("window.__rec")


def trace(rec, act):
    return [(o["t"], o["b"][str(act)]) for o in rec if str(act) in o["b"]]


def steps(tr, key):
    return [abs(b[1][key] - a[1][key]) for a, b in zip(tr, tr[1:])]


def landed_at(tr):
    """The time of the last frame in which the block was being moved by its land animation (None when it never was)."""
    t = [t for t, v in tr if v["lands"]]
    return max(t) if t else None


def check_smooth(rec, act, tolerance=0.3, rest_step=0.5):
    """Between two frames the block never steps more than `tolerance` of its whole move (or 6 px); after it has landed, nothing moves (0.5 px), the replaced element included."""
    tr = trace(rec, act)
    assert len(tr) > 30, len(tr)
    rest = landed_at(tr)
    assert rest is not None, "the block was never moved by a land animation"
    for key in ("top", "left", "height"):
        total = max(abs(v[key] - tr[0][1][key]) for _, v in tr) or 1
        for (t, _), s in zip(tr[1:], steps(tr, key)):
            limit = rest_step if t > rest + 20 else max(total * tolerance, 6)
            assert s <= limit, (key, t, s, limit, total)
    assert max(v["lands"] for _, v in tr) == 1, "more than one settle at once"
    return tr, rest


def check_one_settle_and_toast_after(page, rec, act, log_before, rest_step=0.5):
    tr, rest = check_smooth(rec, act, rest_step=rest_step)
    first_toast = min(o["t"] for o in rec if "q" in o)
    assert first_toast > rest, (first_toast, rest)                                        # the toast glides in after the block has landed
    swapped = [t for (t, v), (_, w) in zip(tr, tr[1:]) if v["id"] != w["id"]]
    assert not swapped or swapped[0] > rest - 1, (swapped, rest)                          # F-123: the refresh updates the day in place (the element is kept); never replaced mid-move
    lands = [e for e in page.evaluate("GA.motion.log")[log_before:] if e["kind"] in ("land", "flip")]
    assert len(lands) == 1, lands                                                         # exactly one settle ran for the change
    assert lands[0]["dur"] == page.evaluate("GA.motion.t('spring')")                      # the shared spring, from the token
    return rest


def slow_save(page, seconds=0.35):
    def hold(route):
        time.sleep(seconds)
        route.continue_()
    page.route("**/trip/canvas/plan", hold)


@pytest.fixture(params=[PHONE, NARROW], ids=['390', '320'])
def vp(request):
    return request.param


# ---- the block --------------------------------------------------------------------------------------------------------------------------

def test_a_dropped_block_lands_with_one_spring_and_the_refresh_does_not_re_draw_it(canvas_page, vp):
    page = canvas_page(viewport=vp, motion="no-preference")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    slow_save(page)
    start = hold_block(page, lunch.id)
    step = ppm(page) * 15
    end = slide(page, start, (start[0], start[1] + step * 2 + step * 0.49))             # nearly three steps: it snaps to 30 minutes, nine pixels from the finger
    log = len(page.evaluate("GA.motion.log"))
    page.evaluate("(" + REC.strip() + ")()")
    fire(page, "pointerup", *end)
    rec = frames(page)
    check_one_settle_and_toast_after(page, rec, lunch.id, log)
    assert now(lunch.id)[:2] == (12 * 60 + 30, 13 * 60 + 30)
    expect(toast(page).get_by_role("button", name="Undo")).to_be_visible()             # Undo works as soon as it shows
    toast(page).get_by_role("button", name="Undo").click()
    expect(toast(page)).to_have_text("Put back")
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60)


def test_a_resized_block_keeps_its_length_through_the_save_and_the_refresh(canvas_page, vp):
    page = canvas_page(viewport=vp, motion="no-preference")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    slow_save(page)
    base = ppm(page)
    start = hold_block(page, lunch.id, edge=True, wait=700)
    k = 2.5
    end = slide(page, start, (start[0], start[1] + base * 5 * k * 4), steps=8)           # twenty minutes longer
    page.evaluate("(" + REC.strip() + ")()")
    fire(page, "pointerup", *end)
    rec = frames(page, 2000)
    tr = trace(rec, lunch.id)
    zoom_over = max(o["t"] for o in rec if o["zoom"])
    for key in ("top", "left", "height"):
        total = max(abs(v[key] - tr[0][1][key]) for _, v in tr) or 1
        for (t, _), s in zip(tr[1:], steps(tr, key)):
            assert s <= (0.5 if t > zoom_over + 50 else max(total * 0.3, 6)), (key, t, s, total)      # the grid eases back, the refresh then changes nothing
    first_toast = min(o["t"] for o in rec if "q" in o)
    assert first_toast > zoom_over
    assert now(lunch.id)[:2] == (12 * 60, 13 * 60 + 20)


def test_a_menu_nudge_lands_the_same_way_and_the_menu_and_knobs_come_through_the_refresh(canvas_page, vp):
    page = canvas_page(viewport=vp, motion="no-preference")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    hold_and_let_go(page, lunch.id)
    slow_save(page)
    log = len(page.evaluate("GA.motion.log"))
    menu_item(page, "Later").scroll_into_view_if_needed()                                  # (Playwright's own scroll to the button is not part of what is measured)
    page.wait_for_timeout(300)
    page.evaluate("(" + REC.strip() + ")()")
    menu_item(page, "Later").click()
    rec = frames(page)
    check_one_settle_and_toast_after(page, rec, lunch.id, log, rest_step=3)                # (the open menu's wiggle tilts the block a little, a pixel or two, all the time)
    assert now(lunch.id)[:2] == (12 * 60 + 15, 13 * 60 + 15)
    tr = trace(rec, lunch.id)
    assert tr[-1][1]["sel"]                                                              # selected again after the refresh (F-110)
    expect(page.locator(".cz-g-knobs")).to_have_count(1)


def test_a_block_pushed_aside_by_a_move_glides_to_its_new_lane(canvas_page, vp):
    page = canvas_page(viewport=vp, motion="no-preference")
    a = plan("Lunch", 12 * 60, 13 * 60)
    b = plan("Museum", 14 * 60, 15 * 60)
    open_day(page)
    slow_save(page)
    start = hold_block(page, a.id)
    end = slide(page, start, (start[0], start[1] + ppm(page) * 120))                      # onto the museum's hour: they now sit side by side
    page.evaluate("(" + REC.strip() + ")()")
    fire(page, "pointerup", *end)
    rec = frames(page, 2000)
    assert now(a.id)[0] == 14 * 60
    tr = trace(rec, b.id)
    assert abs(tr[-1][1]["width"] - tr[0][1]["width"]) > 20                                # it was made narrower for the lane
    ws = steps(tr, "width")
    assert max(ws) <= max(0.5 * abs(tr[-1][1]["width"] - tr[0][1]["width"]), 6) or max(ws) < 30, ws
    assert [o["t"] for o in rec if any(v["moving"] for v in o["b"].values()) and not o["landing"]] == []      # a refresh never swaps the day under a glide (CZ.landing covers the neighbours' too)
    glide_b = [o for o in rec if o["b"].get(str(b.id), {}).get("moving")]
    assert glide_b and all(o["landing"] for o in glide_b)
    after = [v for t, v in tr if t > max(t for t, v in tr if v["lands"] or v["moving"]) + 450]      # (F-123: the element is kept through the refresh)
    assert max(abs(after[0][k] - after[-1][k]) for k in ("top", "left", "width", "height")) < 0.5


def test_reduced_motion_a_dropped_block_does_not_travel(canvas_page, vp):
    page = canvas_page(viewport=vp, motion="reduce")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    start = hold_block(page, lunch.id)
    end = slide(page, start, (start[0], start[1] + ppm(page) * 30))
    fire(page, "pointerup", *end)
    expect(toast(page)).to_contain_text("Lunch moved")
    assert page.evaluate("GA.motion.log.filter(e => e.kind === 'land' || e.kind === 'flip').length") == 0
    assert page.locator(f'.cz-gb[data-act="{lunch.id}"]').evaluate("e => e.getAnimations().length") == 0


# ---- the chat -----------------------------------------------------------------------------------------------------------------------------
