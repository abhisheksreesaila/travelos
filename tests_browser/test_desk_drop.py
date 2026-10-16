"""F-174: on the laptop a dropped plan settles at once, before the save answers (the save slowed 700 ms), sampled frame by frame at 1440."""
from tests_browser.helpers import DESKTOP
from tests_browser.test_day_grid import SUNDAY, now, open_day, plan, ppm
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures

PROBE = """(act) => { window.__p = []; 
  (function f() {
    const b = document.querySelector('.cz-gb[data-act="' + act + '"]'), r = b.getBoundingClientRect(), cs = getComputedStyle(b);
    window.__p.push({ t: performance.now(), top: r.top, scale: cs.scale, shadow: cs.boxShadow, op: +cs.opacity, tf: cs.transform,
      cls: b.className, ghost: !!document.querySelector(".cz-g-ghost"), label: !!document.querySelector(".cz-g-label, .cz-drop-label"), lifted: b.classList.contains("is-held") || getComputedStyle(b).scale !== "none" || getComputedStyle(b).boxShadow.includes("30, 26, 46"), anims: b.getAnimations().map(a => a.id || a.animationName || a.transitionProperty).join(',') });
    requestAnimationFrame(f); })(); }"""


def drop_slowly(page, act, delay=0.7, minutes=60):
    import time

    def hold(route):
        time.sleep(delay)
        route.continue_()
    page.route("**/trip/canvas/plan", hold)
    box = page.locator(f'.cz-gb[data-act="{act}"]').bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 9):
        page.mouse.move(x, y + ppm(page) * minutes * i / 8)
        page.wait_for_timeout(16)
    page.wait_for_timeout(100)
    page.evaluate(PROBE, str(act))
    t0 = page.evaluate("performance.now()")
    page.mouse.up()
    page.wait_for_timeout(1300)
    return page.evaluate("window.__p"), t0


def test_on_the_laptop_the_dropped_plan_is_settled_before_the_save_answers(canvas_page):
    page = canvas_page(viewport=DESKTOP, touch=False, motion="no-preference")
    a = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page, SUNDAY)
    rec, t0 = drop_slowly(page, a.id)
    assert now(a.id)[0] == 13 * 60
    reply = page.evaluate("performance.getEntriesByType('resource').filter(e => e.name.includes('/trip/canvas/plan')).pop().responseEnd")
    assert reply - t0 > 600, reply - t0                                           # the save really was slow
    for o in rec:
        if o["t"] >= t0 + 50 and o["t"] < reply:                             # from 50 ms after the drop until the answer
            assert o["scale"] == "none" and not o["lifted"], o                    # no lift scale and no ink ring left
            assert o["tf"] == "none" and not o["ghost"] and not o["label"] and o["anims"] == "", o      # no travel, ghost, landing slot, label or animation
    assert sum(1 for o in rec if t0 + 50 <= o["t"] < reply) > 20
