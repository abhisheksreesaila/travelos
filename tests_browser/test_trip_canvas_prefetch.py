"""F-099 (checks 3 and 4): the canvas fetches its next levels while idle, so Day | Week, a date, a flick and Back swap with no wait.
Counts the fragment requests (?frag=1) the page makes, and measures tap-to-swap in the page (a click to the new level in the DOM) against a target on a warm cache.
Also: a write empties the prefetched levels, reduced motion is still instant, Data Saver skips prefetch, and the canvas and the page changes share one motion token set."""
import json
import re

import pytest
from playwright.sync_api import expect

from gitaway import canvas
from tests.test_signin import person
from tests_browser.helpers import PHONE
from tests_browser.test_day_plan import flick, open_day
from tests_browser.test_trip_canvas import canvas_page, checks, model, open_block, settle  # noqa: F401 - fixtures and helpers

TARGET_MS = 150

# tap -> the new level in the DOM: {ms, asked} where asked lists the fragments requested between the tap and the swap (the follow-on idle prefetch comes after it)
TIMED_CLICK = """(sel) => new Promise((res, rej) => { const st = document.getElementById('cz'); const was = st.querySelector('.cz-view');
  const asked = [], real = window.fetch; window.fetch = function (u) { asked.push(String(u)); return real.apply(this, arguments); };
  const t0 = performance.now();
  const mo = new MutationObserver(() => { const v = st.querySelector('.cz-view'); if (v && v !== was) { mo.disconnect(); window.fetch = real; res({ ms: performance.now() - t0, asked }); } });
  mo.observe(st, { childList: true });
  setTimeout(() => { mo.disconnect(); window.fetch = real; rej(new Error('no swap')); }, 6000);
  document.querySelector(sel).click(); })"""


def watch(page):
    """A list that fills with every fragment url the page requests from now on."""
    seen = []
    page.on("request", lambda r: seen.append(re.sub(r"^https?://[^/]+", "", r.url)) if "frag=1" in r.url else None)
    return seen


def days_on_week(page):
    return len({a.get_attribute("href") for a in page.locator('.cz-view[data-level=week] a.cz-row-link').all()})


def wait_idle(page, seen, want):
    """Wait until the page has asked for `want` fragments (it does so in idle time), then a beat to be sure nothing more is coming."""
    page.wait_for_function("n => performance.getEntriesByType('resource').filter(e => e.name.includes('frag=1')).length >= n", arg=want, timeout=9000)
    page.wait_for_timeout(400)


def test_the_week_fetches_every_day_while_idle_and_day_then_swaps_without_a_request(canvas_page):
    page = canvas_page(motion="no-preference")
    n = days_on_week(page)
    assert n >= 3
    wait_idle(page, None, n)
    r = page.evaluate(TIMED_CLICK, "#cz-z-day")
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    settle(page)
    print(f"\nF099 week -> Day (toggle), warm cache: {r['ms']:.0f} ms")
    assert r["asked"] == [], r                         # nothing was asked for: it came from the idle fetch
    assert r["ms"] < TARGET_MS
    assert page.evaluate("window.__vt.calls") == 1 and page.evaluate("window.__vt.dir")[0] in ("in", "side")      # and it still ran the transition


def test_a_week_row_and_back_to_the_week_swap_without_a_request(canvas_page):
    page = canvas_page(motion="no-preference")
    wait_idle(page, None, days_on_week(page))
    a = page.evaluate(TIMED_CLICK, ".cz-row-link[href*='day=1']")
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    settle(page)
    page.wait_for_timeout(600)
    b = page.evaluate(TIMED_CLICK, ".cz-head .cz-back")      # a day prefetches its week too
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    settle(page)
    print(f"\nF099 week row -> day {a['ms']:.0f} ms; Week toggle -> week {b['ms']:.0f} ms")
    assert a["asked"] == [] and b["asked"] == [], (a, b)
    assert a["ms"] < TARGET_MS and b["ms"] < TARGET_MS


def test_a_date_and_a_flick_to_a_neighbour_swap_without_a_request(canvas_page):
    page = canvas_page(motion="no-preference")
    open_day(page, 1)
    page.wait_for_function("() => performance.getEntriesByType('resource').filter(e => e.name.includes('frag=1')).length >= 2")
    page.wait_for_timeout(1200)                         # neighbours, the week and the other dates, two at a time
    r = page.evaluate(TIMED_CLICK, ".cz-dpills a:not(.is-open)")
    expect(page.locator(".cz-view[data-level=day]")).not_to_have_attribute("data-day", "1")
    settle(page)
    assert r["asked"] == [], r
    day = page.locator(".cz-view").get_attribute("data-day")
    page.wait_for_timeout(1200)
    page.evaluate("""() => { const st = document.getElementById('cz'), was = st.querySelector('.cz-view'); const real = window.fetch;
      window.__asked = []; window.fetch = function (u) { window.__asked.push(String(u)); return real.apply(this, arguments); };
      window.__flick = new Promise(res => { const mo = new MutationObserver(() => { if (st.querySelector('.cz-view') !== was) { mo.disconnect(); window.fetch = real; res(performance.now()); } });
        mo.observe(st, { childList: true }); }); }""")
    t0 = page.evaluate("performance.now()")
    flick(page, -160 if page.locator(".cz-view").get_attribute("data-next") else 160, y=640)      # (F-103: the heading is shorter, so 420 is now on a booking line)
    t1 = page.evaluate("window.__flick")
    settle(page)
    print(f"\nF099 date pill -> day {r['ms']:.0f} ms; flick (pointer events -> new day in the DOM, synthetic gesture included) {t1 - t0:.0f} ms")
    assert page.locator(".cz-view").get_attribute("data-day") != day
    assert page.evaluate("window.__asked") == []
    assert t1 - t0 < TARGET_MS + 100                   # the synthetic gesture itself takes a few ms on top of the swap


def test_a_write_empties_the_prefetched_levels_so_the_week_shows_it(canvas_page):
    """All in the page, no reload: the week was fetched ahead before the write, and after it the week must show the step as done."""
    page = canvas_page(motion="no-preference")
    wait_idle(page, None, days_on_week(page))
    assert "1/14" not in page.locator(".cz-view[data-level=week]").inner_text()
    page.locator(".cz-row-link[href*='day=1']").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.wait_for_timeout(800)                           # the day has fetched the week ahead, from before the write
    open_block(page)
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    page.locator('.cz-step:has-text("Revenge of the Mummy")').click()
    seen = watch(page)
    page.get_by_role("button", name="Mark done").click()
    expect(page.locator(".cz-step.is-done", has_text="Revenge of the Mummy")).to_be_visible()
    settle(page)
    seen.clear()
    page.go_back()                                       # the day, fetched before the write: it must be asked for again
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    assert any("day=1" in u for u in seen), seen
    page.wait_for_timeout(300)
    page.locator(".cz-head .cz-back").click()
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    settle(page)
    expect(page.locator(".cz-view[data-level=week]")).to_contain_text("1/14")      # the week as it is now, not the copy from before the write


def test_a_level_shown_from_an_old_copy_is_brought_up_to_date_when_someone_else_changed_it(canvas_page):
    page = canvas_page(motion="no-preference")
    wait_idle(page, None, days_on_week(page))
    page.locator(".cz-row-link[href*='day=1']").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.wait_for_timeout(5800)                          # the week copy is now older than the staleness window
    ari = person("ari")
    blocks = canvas.plan(ari)["blocks"]
    step = next(st for blk in blocks.values() for pt in blk["parts"] for st in pt["steps"])
    canvas.set_done(ari, step["id"])                     # another person's tick, made on the server: nothing in this page knows
    seen = watch(page)
    page.locator(".cz-head .cz-back").click()                   # shown at once from the old copy...
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    assert "1/" not in page.locator(".cz-view[data-level=week]").inner_text()
    expect(page.locator(".cz-view[data-level=week]")).to_contain_text("1/", timeout=6000)      # ...then quietly replaced by the server's copy
    assert any("frag=1" in u for u in seen)


def test_a_quiet_update_waits_while_a_field_is_being_typed_in(canvas_page):
    page = canvas_page(motion="no-preference")
    wait_idle(page, None, days_on_week(page))
    page.locator(".cz-row-link[href*='day=1']").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.wait_for_timeout(5800)
    ari = person("ari")
    step = next(st for blk in canvas.plan(ari)["blocks"].values() for pt in blk["parts"] for st in pt["steps"])
    canvas.set_done(ari, step["id"])
    page.locator(".cz-head .cz-back").click()
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    page.evaluate("() => { const i = document.createElement('input'); i.id = 'zz-typing'; document.querySelector('.cz-view').appendChild(i); i.focus(); }")
    page.wait_for_timeout(1500)
    assert page.evaluate("document.activeElement.id") == "zz-typing"                  # the field is still there: nothing replaced the level under the cursor
    assert "1/" not in page.locator(".cz-view[data-level=week]").inner_text()


def test_coming_back_from_the_bfcache_shows_the_server_copy(canvas_page):
    page = canvas_page(motion="no-preference")
    wait_idle(page, None, days_on_week(page))
    ari = person("ari")
    step = next(st for blk in canvas.plan(ari)["blocks"].values() for pt in blk["parts"] for st in pt["steps"])
    canvas.set_done(ari, step["id"])
    page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))")
    expect(page.locator(".cz-view[data-level=week]")).to_contain_text("1/", timeout=6000)


def test_reduced_motion_is_still_instant_and_prefetched(canvas_page):
    page = canvas_page(motion="reduce")
    wait_idle(page, None, days_on_week(page))
    r = page.evaluate(TIMED_CLICK, "#cz-z-day")
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    print(f"\nF099 reduced motion, week -> Day: {r['ms']:.0f} ms")
    assert r["asked"] == [] and r["ms"] < TARGET_MS
    assert page.evaluate("window.__vt.calls") == 0
    assert page.evaluate("document.querySelector('.cz-view').getAnimations().length") == 0


def test_data_saver_skips_the_prefetch_and_the_tap_still_works(browser, base_url, model):
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
    ctx.set_default_timeout(9000)
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
    ctx.add_init_script("Object.defineProperty(navigator, 'connection', { value: { saveData: true, effectiveType: '4g' } })")
    page = ctx.new_page()
    seen = watch(page)
    page.goto(f"{base_url}/trip/canvas")
    page.wait_for_selector(".cz-view[data-level=week]")
    page.wait_for_timeout(2500)
    assert seen == [], seen                              # nothing fetched ahead of a tap
    page.locator("#cz-z-day").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    assert len(seen) == 1                                # the tap asked for exactly the one level
    ctx.close()


def test_the_canvas_and_the_page_changes_use_one_motion_token_set(canvas_page):
    page = canvas_page(motion="no-preference")
    got = page.evaluate("""() => { const cs = getComputedStyle(document.documentElement);
      return ['--motion-screen-dur', '--motion-ease', '--cz-dur', '--cz-ease'].map(k => cs.getPropertyValue(k).trim()); }""")      # F-114: the screen moves glide with the calm ease, no overshoot
    assert got[0] and got[1] and got[0] == got[2] and got[1] == got[3], got


def test_a_level_not_in_hand_zooms_at_once_into_its_outline_and_fills_in_when_it_comes(canvas_page):
    """F-135: a slow answer is not waited for. The tap zooms straight into the day's outline (the heading, named as the row named it, and soft rows); the day fills it in place."""
    page = canvas_page(motion="no-preference")
    page.route(re.compile(r"/trip/canvas\?day=\d+.*frag=1"), lambda route: (page.wait_for_timeout(700), route.continue_()))
    page.evaluate("window.__t0 = 0; new MutationObserver(() => { if (!window.__t0 && document.querySelector('.cz-skel')) window.__t0 = performance.now(); }).observe(document.getElementById('cz'), {childList: true, subtree: true})")
    link = page.locator("a.cz-row-link").first
    name = link.get_attribute("data-title")
    page.evaluate("CZ.forget()")                                                     # (the week fetched its days ahead; this one must come slowly)
    t = page.evaluate("() => { const t = performance.now(); document.querySelector('a.cz-row-link').click(); return t; }")
    page.wait_for_selector(".cz-view.cz-skel[data-level=day]", timeout=2000)
    assert page.evaluate("window.__t0") - t < 200                                      # the zoom started at once, not after the server answered
    assert page.locator(".cz-skel #cz-title").inner_text() == name and page.locator(".cz-skel-row").count() == 5
    page.wait_for_selector(".cz-view[data-level=day]:not(.cz-skel)", timeout=6000)
    settle(page)
    assert page.locator(".cz-skel").count() == 0 and page.locator(".cz-fold").count() == 1 and page.locator(".cz-head .cz-back-t").inner_text() == "Trip"
    assert re.search(r"[?&]day=\d+", page.url)
    page.unroute_all(behavior="ignoreErrors")      # (the idle fetches of the day's neighbours may still be held)


def test_a_swipe_in_from_the_left_edge_goes_back_a_level(canvas_page):
    """F-136: from the left edge of a day, a finger moving right is "‹ Trip"; a short one springs back."""
    page = canvas_page(motion="no-preference")
    page.locator("a.cz-row-link").first.click()
    page.wait_for_selector(".cz-view[data-level=day]:not(.cz-skel)")
    settle(page)
    swipe = """(dx) => { const st = document.getElementById('cz'), y = 400;
      const ev = (t, x) => st.dispatchEvent(new PointerEvent(t, {pointerId: 7, pointerType: 'touch', clientX: x, clientY: y, bubbles: true, isPrimary: true}));
      ev('pointerdown', 6); for (let i = 1; i <= 6; i++) ev('pointermove', 6 + dx * i / 6); ev('pointerup', 6 + dx); }"""
    page.evaluate(swipe, 40)                                        # too short: it stays on the day
    page.wait_for_timeout(500)
    assert page.locator(".cz-view").get_attribute("data-level") == "day"
    assert page.evaluate("document.querySelector('.cz-view').style.transform") == ""
    page.evaluate(swipe, 160)
    page.wait_for_selector(".cz-view[data-level=week]", timeout=4000)
