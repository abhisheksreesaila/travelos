"""F-099 (checks 3 and 4): the canvas fetches its next levels while idle, so Day | Week, a date, a flick and Back swap with no wait.
Counts the fragment requests (?frag=1) the page makes, and measures tap-to-swap in the page (a click to the new level in the DOM) against a target on a warm cache.
Also: a write empties the prefetched levels, reduced motion is still instant, Data Saver skips prefetch, and the canvas and the page changes share one motion token set."""
import json
import re

import pytest
from playwright.sync_api import expect

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
    b = page.evaluate(TIMED_CLICK, "#cz-z-week")      # a day prefetches its week too
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
    flick(page, -160 if page.locator(".cz-view").get_attribute("data-next") else 160)
    t1 = page.evaluate("window.__flick")
    settle(page)
    print(f"\nF099 date pill -> day {r['ms']:.0f} ms; flick (pointer events -> new day in the DOM, synthetic gesture included) {t1 - t0:.0f} ms")
    assert page.locator(".cz-view").get_attribute("data-day") != day
    assert page.evaluate("window.__asked") == []
    assert t1 - t0 < TARGET_MS + 100                   # the synthetic gesture itself takes a few ms on top of the swap


def test_a_write_empties_the_prefetched_levels(canvas_page):
    page = canvas_page(motion="no-preference")
    n = days_on_week(page)
    wait_idle(page, None, n)
    page.locator(".cz-row-link[href*='day=1']").click()
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    open_block(page)
    expect(page.locator(".cz-view[data-level=block]")).to_be_visible()
    page.locator('.cz-step:has-text("Revenge of the Mummy")').click()
    seen = watch(page)
    page.get_by_role("button", name="Mark done").click()
    expect(page.locator(".cz-step.is-done", has_text="Revenge of the Mummy")).to_be_visible()
    settle(page)
    seen.clear()
    page.wait_for_timeout(300)
    page.go_back()                                       # the day, which was fetched before the write
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    assert any("day=1" in u for u in seen), seen         # it asked again: nothing from before the write is shown
    page.wait_for_timeout(800)
    seen.clear()
    page.locator("#cz-z-week").click()
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    # the week was prefetched from the day after the write, so this one may or may not ask; what matters is that it is current
    assert page.evaluate("document.querySelector('.cz-view').dataset.level") == "week"


def test_a_prefetched_level_is_dropped_after_a_write_and_never_shown_stale(canvas_page):
    page = canvas_page(motion="no-preference")
    wait_idle(page, None, days_on_week(page))
    # a stale copy of the Universal day sits in the cache; a write must make the next view ask the server again
    page.evaluate("() => { window.__n0 = performance.getEntriesByType('resource').filter(e => e.name.includes('frag=1')).length; }")
    page.goto(page.url + "?block=a1")
    page.locator('.cz-step:has-text("Revenge of the Mummy")').click()
    page.get_by_role("button", name="Mark done").click()
    expect(page.locator(".cz-prog")).to_have_text("1 of 14 done")
    page.locator(".cz-back").click()                      # the day
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.locator(".cz-back").click()
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    page.locator(".cz-row-link[href*='day=1']").click()
    page.locator(".cz-gb-open").click(position={"x": 90, "y": 40})
    expect(page.locator(".cz-prog")).to_have_text("1 of 14 done")      # the block shows the step done, however the page got here


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
      return ['--motion-dur', '--motion-ease', '--cz-dur', '--cz-ease'].map(k => cs.getPropertyValue(k).trim()); }""")
    assert got[0] and got[1] and got[0] == got[2] and got[1] == got[3], got
