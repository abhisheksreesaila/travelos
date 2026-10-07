"""F-112: a changed block and a sent bubble move like liquid, in a real browser at 390 wide with the real motion on. Frames are sampled with requestAnimationFrame from the moment the
finger lets go (or the menu is pressed, or Send is) through the save and the refresh to rest, and the numbers are what the captain's eye sees:
  - a dropped, resized or nudged block never jumps between two frames (a spring's steps stay a fraction of the whole move, and once it is at rest nothing moves, even when the refreshed day
    replaces the element), exactly one `land` animation moves it, and the toast's first frame comes after the block has landed (the save is slow here on purpose, so the refresh and the
    toast would otherwise arrive mid-move); Undo still works the moment the toast shows;
  - a block that another block's move pushed aside glides to its new lane (no jump);
  - a sent bubble (one plain rise, F-113) first frame sits at the box and its last in the list, the bubble before it glides up without a jump, the same element lives through the server's confirmation (no flash:
    its opacity never steps), a message that arrives settles the same way; reduced motion only fades."""
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
    assert swapped and swapped[0] > rest - 1, (swapped, rest)                             # the day was refreshed (the element replaced) only once it rested
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
    after = [v for t, v in tr if t > max(t for t, v in tr if v["lands"] or v["id"] == tr[0][1]["id"]) + 450]
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

def family(canvas_page, base_url, vp, motion="no-preference"):
    page = canvas_page(viewport=vp, motion=motion)
    page.goto(f"{base_url}/trip/family")
    page.wait_for_selector("#ft-compose")
    return page


def send_and_wait(page, text):
    page.locator("#ft-text").fill(text)
    page.locator("#ft-send").click()
    expect(page.locator("#ft-thread .is-pending")).to_have_count(0)
    page.wait_for_timeout(700)


def slow_message(page, seconds=0.8):
    def hold(route):
        time.sleep(seconds)
        route.continue_()
    page.route("**/trip/family/message", hold)


def test_the_servers_copy_waits_for_the_bubble_to_finish_growing(canvas_page, base_url, vp):
    page = family(canvas_page, base_url, vp)
    send_and_wait(page, "First")
    page.evaluate("(" + REC.strip() + ")()")                                                # (a fast answer: it arrives while the bubble is still growing out of the box)
    page.locator("#ft-text").fill("Quick answer")
    page.locator("#ft-send").click()
    rec = frames(page, 1500)
    mine = [(o, next(m for m in o["m"] if m["text"].startswith("Quick"))) for o in rec if any(m["text"].startswith("Quick") for m in o["m"])]
    growing = [m for o, m in mine if m["anims"]]
    assert growing and all(m["pending"] and m["text"].endswith("Sending") for m in growing), [m["text"] for m in growing]      # its words are not swapped under the motion
    assert not mine[-1][1]["pending"]                                                       # and it does take the server's copy once it has landed


def test_a_sent_bubble_grows_out_of_the_box_rises_into_place_and_the_list_glides_up(canvas_page, base_url, vp):
    page = family(canvas_page, base_url, vp)
    send_and_wait(page, "First")
    slow_message(page)
    page.evaluate("(" + REC.strip() + ")()")
    page.locator("#ft-text").fill("Second one")
    page.locator("#ft-send").click()
    rec = frames(page, 2200)
    mine = [o for o in rec if any(m["text"].startswith("Second") for m in o["m"])]
    first, last = mine[0], mine[-1]
    f = next(m for m in first["m"] if m["text"].startswith("Second"))
    l = next(m for m in last["m"] if m["text"].startswith("Second"))
    assert abs(f["top"] - first["i"]["y"]) < 14 and f["top"] > last["th"]["y"] + last["th"]["height"] - 2        # the first frame is at the box (below the list)
    assert l["top"] + l["height"] <= last["c"]["y"] + 1 and l["top"] >= last["th"]["y"]                           # the last is in the list, right above the box
    ids = {next(m for m in o["m"] if m["text"].startswith("Second"))["id"] for o in mine}
    assert len(ids) == 1, "the bubble was replaced"                                                               # the server's answer takes the same element's place
    # the bubble before it glides up: one move, no jump
    prev = [next(m for m in o["m"] if m["text"].startswith("First")) for o in mine]
    total = abs(prev[-1]["top"] - prev[0]["top"])
    assert total > 20
    ds = [abs(b["top"] - a["top"]) for a, b in zip(prev, prev[1:])]
    assert max(ds) <= total * 0.35 + 2, (max(ds), total)
    # no flash when the server confirms: the pending look firms up by a fade (a step of the opacity stays small), and nothing moves at that moment
    t_conf = next(o["t"] for o in mine if not next(m for m in o["m"] if m["text"].startswith("Second"))["pending"])
    ops = [next(m for m in o["m"] if m["text"].startswith("Second"))["op"] for o in mine]
    assert max(abs(b - a) for a, b in zip(ops, ops[1:])) < 0.25, ops
    after = [next(m for m in o["m"] if m["id"] == next(iter(ids)))["top"] for o in mine if o["t"] > t_conf - 20]
    assert after and max(abs(b - a) for a, b in zip(after, after[1:])) < 8, after      # the time line the server adds makes the bubble a line taller: it grows into it by a move, not a jump
    assert abs(after[-1] - after[-2]) < 0.5
    assert page.evaluate("GA.motion.log.filter(e => e.kind === 'rise').length") >= 1


def test_a_message_that_arrives_settles_the_same_way(canvas_page, base_url, vp):
    page = family(canvas_page, base_url, vp)
    send_and_wait(page, "First")
    page.evaluate("(" + REC.strip() + ")()")
    page.evaluate("""() => { const f = new URLSearchParams(new FormData(document.getElementById('ft-compose'))); f.set('text', 'From the pool'); f.set('cid', 'other1'); f.set('since', '99999');
      return fetch('/trip/family/message', { method: 'POST', credentials: 'same-origin', headers: { 'X-Fragment': '1' }, body: f })
      .then(() => document.getElementById('ft-thread').dispatchEvent(new Event('ft-refresh'))); }""")
    rec = frames(page, 1500)
    mine = [o for o in rec if any(m["text"].startswith("From the pool") for m in o["m"])]
    assert mine
    log = page.evaluate("GA.motion.log")
    assert any(e["kind"] == "settle" for e in log)
    prev = [next(m for m in o["m"] if m["text"].startswith("First")) for o in mine]
    total = abs(prev[-1]["top"] - prev[0]["top"])
    if total > 8:
        assert max(abs(b["top"] - a["top"]) for a, b in zip(prev, prev[1:])) <= total * 0.35 + 2


def test_reduced_motion_a_sent_bubble_only_fades(canvas_page, base_url, vp):
    page = family(canvas_page, base_url, vp, motion="reduce")
    slow_message(page, 0.4)
    page.locator("#ft-text").fill("Quiet hello")
    page.evaluate("(" + REC.strip() + ")()")
    page.locator("#ft-send").click()
    rec = frames(page, 600)
    mine = [next(m for m in o["m"] if m["text"].startswith("Quiet")) for o in rec if any(m["text"].startswith("Quiet") and m["pending"] for m in o["m"])]      # (while it is sent: the server's time line then makes it a line taller)
    assert len(mine) > 3
    assert max(m["top"] for m in mine) - min(m["top"] for m in mine) < 1 and max(m["left"] for m in mine) - min(m["left"] for m in mine) < 1      # it does not travel
    log = page.evaluate("GA.motion.log")
    assert [e["kind"] for e in log] == ["fade"], log
    got = page.locator("#ft-thread .ft-msg").last.evaluate("e => e.getAnimations().length")
    assert got == 0
