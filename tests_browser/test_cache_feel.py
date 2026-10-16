"""F-170 (docs/perf-feel.md fixes 2 and 7): never wait for a copy we already have.
A level fetched ahead is shown at once whatever its age and after any write, and checked quietly behind it (changed nodes morph, nothing flashes when nothing changed);
a write's own returned level seeds the cache and the day's neighbours are fetched first; the phone week does not fetch the desktop plan rows; another trip never shows this trip's copy."""
import re

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE, seed_plan
from tests_browser.test_day_plan import open_day
from tests_browser.test_trip_switcher import MENU, family_with_two_trips  # noqa: F401 - fixture
from tests_browser.test_trip_canvas import canvas_page, model, settle  # noqa: F401 - fixtures and helpers
from tests_browser.test_trip_canvas_prefetch import TARGET_MS, TIMED_CLICK, days_on_week, watch

BOTH = pytest.mark.parametrize("form", [{}, {"viewport": DESKTOP, "touch": False}], ids=["390", "1440"])
LATER = "(ms) => { const real = Date.now.bind(Date); Date.now = () => real() + ms; }"      # the page's clock jumps ahead (a minute on the day, without the wait)
FRAGS = "performance.getEntriesByType('resource').filter(e => e.name.includes('frag=1')).map(e => e.name.replace(location.origin, ''))"
WATCH_DOM = """() => { window.__mut = 0; new MutationObserver(r => { window.__mut += r.length; }).observe(document.getElementById('cz'), { childList: true, subtree: true, attributes: true, characterData: true }); }"""


def quiet_network(page, still=1100):
    """Wait until the page has stopped asking for fragments (the idle prefetch is done)."""
    last, since = -1, 0
    for _ in range(120):
        n = page.evaluate(f"{FRAGS}.length")
        if n == last:
            since += 100
            if since >= still:
                return n
        else:
            last, since = n, 0
        page.wait_for_timeout(100)
    raise AssertionError("the prefetch never settled")


def day_with_plan(canvas_page, base_url, motion="no-preference", **kw):
    """The trip's day 1 on the phone with a plan 'Lunch F170' on it, everything the day fetches ahead already in hand."""
    page = canvas_page(motion=motion, **kw)
    seed_plan(page.request, base_url, "a9", "1", "12:00", "13:00", "Lunch F170")
    open_day(page, 1)
    quiet_network(page)
    return page


def slow(page, ms=700):
    """Every level fetch from now on answers after `ms` (the live round trip, and then some)."""
    page.route(re.compile(r"frag=1"), lambda route: (page.wait_for_timeout(ms), route.continue_()))


def slow_answers(page, ms=700):
    """The server sees each level request at once and its answer reaches the page `ms` later: a fetch sent before a write comes back after it, with what the server had then."""
    def hold(route):
        got = route.fetch()
        page.wait_for_timeout(ms)
        route.fulfill(response=got)
    page.route(re.compile(r"frag=1"), hold)


def move_plan_to_day(page, day):
    """A write made the way the app makes it (CZ.post), then the screen brought up to date."""
    return page.evaluate("""(day) => CZ.post('/trip/canvas/plan', CZ.tripBody({ op: 'edit', act: 'a9', day: String(day), next: CZ.here() })).then(() => CZ.quiet())""", day)


@BOTH
def test_a_day_switch_after_a_minute_on_the_day_asks_for_nothing_and_checks_the_copy_afterwards(canvas_page, base_url, form):
    page = day_with_plan(canvas_page, base_url, **form)
    page.evaluate(LATER, 62000)
    seen = watch(page)
    r = page.evaluate(TIMED_CLICK, ".cz-hchips a[href*='day=2']")
    expect(page.locator(".cz-view[data-level=day][data-day='2']")).to_be_visible()
    assert r["asked"] == [] and r["ms"] < 2 * TARGET_MS, r      # the copy fetched ahead is used though it is over a minute old
    settle(page)
    page.evaluate(WATCH_DOM)
    page.wait_for_timeout(2500)
    assert any("day=2" in u for u in seen), seen      # ...and is checked behind the swap
    assert page.evaluate("window.__mut") == 0         # nothing changed on the server: not one node of the screen is touched


def test_a_copy_that_changed_meanwhile_is_corrected_in_place_after_it_is_shown(canvas_page, base_url):
    page = day_with_plan(canvas_page, base_url)
    move_plan_to_day(page, 2)                          # (day 2 now has the plan)
    quiet_network(page)
    page.request.post(f"{base_url}/trip/canvas/plan", form={"op": "edit", "act": "a9", "title": "Lunch F170 moved"}, max_redirects=0)      # someone else renames it: this page does not know
    page.evaluate(LATER, 62000)
    r = page.evaluate(TIMED_CLICK, ".cz-hchips a[href*='day=2']")
    expect(page.locator(".cz-view[data-level=day][data-day='2']")).to_be_visible()
    assert r["asked"] == [] and r["ms"] < 2 * TARGET_MS, r
    assert "Lunch F170 moved" not in page.locator(".cz-view").inner_text()           # at once: the copy we had
    expect(page.locator(".cz-view").get_by_text("Lunch F170 moved").first).to_be_visible(timeout=6000)      # then the server's


@BOTH
def test_a_day_switch_right_after_a_write_does_not_wait_and_shows_the_moved_plan_after_a_moment(canvas_page, base_url, form):
    page = day_with_plan(canvas_page, base_url, **form)
    slow(page)                                         # every fetch from now on takes 700 ms: a tap that waits for one cannot be quick
    move_plan_to_day(page, 2)                          # (the plan on day 1 goes to day 2; the copy of day 2 in hand is from before)
    r = page.evaluate(TIMED_CLICK, ".cz-hchips a[href*='day=2']")      # the tap is right after the write: the neighbours are not back yet
    expect(page.locator(".cz-view[data-level=day][data-day='2']")).to_be_visible()
    assert r["ms"] < 400, r                            # the copy in hand was used at once
    expect(page.locator(".cz-view .cz-gb", has_text="Lunch F170")).to_have_count(1, timeout=6000)      # and then corrected to what the write did
    page.unroute_all(behavior="ignoreErrors")


def test_the_neighbour_a_write_changed_is_never_left_stale(canvas_page, base_url):
    """A plan moved from day 1 to day 2: day 2, fetched before the write, shows it at once when tapped right away (then corrected), and from a fresh copy once the neighbours came back."""
    page = day_with_plan(canvas_page, base_url)
    move_plan_to_day(page, 2)
    expect(page.locator(".cz-view .cz-gb", has_text="Lunch F170")).to_have_count(0)
    quiet_network(page)                                # the neighbours (and the rest) fetched again after the write
    r = page.evaluate(TIMED_CLICK, ".cz-hchips a[href*='day=2']")
    expect(page.locator(".cz-view[data-level=day][data-day='2']")).to_be_visible()
    assert r["asked"] == [] and r["ms"] < 2 * TARGET_MS, r
    assert page.locator(".cz-view .cz-gb", has_text="Lunch F170").count() == 1      # on the first frame: no wait for a correction


def test_right_after_a_write_the_neighbours_are_fetched_before_the_rest(canvas_page, base_url):
    page = day_with_plan(canvas_page, base_url)
    n0 = page.evaluate(f"{FRAGS}.length")
    move_plan_to_day(page, 2)
    quiet_network(page)
    after = page.evaluate(FRAGS)[n0:]
    days = [(re.search(r"day=(\d)", u) or [None, "week"])[1] for u in after]
    assert sorted(days[:2]) == ["0", "2"], after       # the neighbours of day 1 first
    assert "week" in days[2:] and {"3", "4"} <= set(days[2:]), after      # the week and the far days after them


def test_after_a_swap_the_neighbours_are_fetched_before_anything_else(canvas_page):
    page = canvas_page(motion="no-preference")
    open_day(page, 1)
    quiet_network(page)
    page.evaluate("CZ.forget(true)")                    # nothing in hand: the chip's swap asks for day 2, and then the prefetch starts again
    n0 = page.evaluate(f"{FRAGS}.length")
    page.locator(".cz-hchips a[href*='day=2']").click()
    expect(page.locator(".cz-view[data-level=day][data-day='2']")).to_be_visible()
    quiet_network(page)
    got = page.evaluate(FRAGS)[n0:]
    days = [(re.search(r"day=(\d)", u) or [None, "week"])[1] for u in got]
    assert days[0] == "2" and sorted(days[1:3]) == ["1", "3"], got      # the day itself, then its neighbours, then the rest


def test_the_phone_week_fetches_exactly_the_day_cards_and_nothing_hidden(canvas_page):
    page = canvas_page(motion="no-preference")
    days = days_on_week(page)
    n = quiet_network(page)
    urls = page.evaluate(FRAGS)
    assert n == len(urls) == days, urls                                  # one fragment per day card, nothing else
    assert [u for u in urls if "plan=" in u] == [], urls                  # a hidden row is never tapped
    assert len({re.search(r"day=(\d+)", u).group(1) for u in urls}) == days
    size = page.evaluate("performance.getEntriesByType('resource').filter(e => e.name.includes('frag=1')).reduce((a, e) => a + e.encodedBodySize, 0)")
    one = size / len(urls)
    print(f"\nF170 phone week visit: {len(urls)} fragments, {size / 1000:.0f} KB prefetched")
    assert size <= days * 40_000, size                                    # (a day fragment is about 28 to 35 KB)
    assert one < 40_000, one


def test_a_tap_on_the_last_day_of_the_phone_week_does_not_wait(canvas_page):
    page = canvas_page(motion="no-preference")
    quiet_network(page)
    slow(page)
    last = page.locator(".cz-view[data-level=week] a.cz-row-link").last.get_attribute("href")
    r = page.evaluate(TIMED_CLICK, f"a.cz-row-link[href='{last}']")
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    assert page.locator(".cz-view.cz-skel").count() == 0                 # no outline first
    assert r["ms"] < 400, r        # swapped from the copy in hand, not after the 700 ms answer
    page.unroute_all(behavior="ignoreErrors")


def test_the_laptop_week_still_fetches_its_visible_plan_rows(canvas_page):
    page = canvas_page(viewport=DESKTOP, motion="no-preference", touch=False)
    quiet_network(page)
    assert any("plan=" in u for u in page.evaluate(FRAGS))


def test_another_trip_never_shows_this_trips_copy(family_with_two_trips):
    """Addresses carry the trip, so a level fetched (and cached) for one trip is not the answer for another."""
    page = family_with_two_trips(PHONE, "/trip/canvas?day=1")
    page.wait_for_selector(".cz-view[data-level=day][data-day='1']")
    quiet_network(page)
    second = page.evaluate("CZ.stage.dataset.trip")
    first = page.locator(f"{MENU} form:has(.ga-tb-sw:not([aria-current])) input[name=trip]").first.get_attribute("value")
    assert first != second
    assert page.locator(".cz-gb", has_text="Venice Canals stroll").count() == 0          # the open (newest) trip has no such plan
    go = "(t) => CZ.goto('/trip/canvas?day=1&trip=' + t, { mode: 'replace', dir: 'side' })"
    here = lambda: page.locator(".cz-gb", has_text="Venice Canals stroll")
    for t, plans in ((first, 1), (second, 0), (first, 1), (second, 0)):      # (the third and fourth swaps come from the copies of the first two)
        page.evaluate(go, t)
        page.wait_for_function("() => !document.documentElement.dataset.czDir")
        expect(here()).to_have_count(plans)


def test_a_page_brought_back_from_the_back_forward_cache_drops_every_copy(canvas_page, base_url):
    """Coming back to a page left in the bfcache (after a sign-out, say) must not show levels fetched in the earlier session."""
    page = day_with_plan(canvas_page, base_url)
    page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))")
    r = page.evaluate(TIMED_CLICK, ".cz-hchips a[href*='day=2']")
    expect(page.locator(".cz-view[data-level=day][data-day='2']")).to_be_visible()
    assert any("day=2" in u for u in r["asked"]), r      # nothing in hand: the tap asked the server


def test_a_day_fetched_before_a_write_and_tapped_after_it_is_corrected(canvas_page, base_url):
    """The week, a plan moved onto day 2 with the day-2 request already sent (its answer, from before the write, comes late), then a tap on day 2: it fills the outline with the old copy and is corrected."""
    page = canvas_page(motion="no-preference")
    seed_plan(page.request, base_url, "a9", "1", "12:00", "13:00", "Lunch F170")
    page.reload()
    page.wait_for_selector(".cz-view[data-level=week]")
    quiet_network(page)
    page.evaluate("CZ.forget(true)")
    slow_answers(page, 900)
    row = ".cz-view[data-level=week] a.cz-row-link[href*='day=2']"
    page.evaluate("(sel) => { const a = document.querySelector(sel); a.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); a.dispatchEvent(new PointerEvent('pointercancel', { bubbles: true })); }", row)      # day 2 asked for now: the server answers with the plan on day 1
    page.wait_for_timeout(200)
    page.evaluate("CZ.post('/trip/canvas/plan', CZ.tripBody({ op: 'edit', act: 'a9', day: '2', next: CZ.here() }))")
    page.locator(row).click()
    expect(page.locator(".cz-view[data-level=day][data-day='2']")).to_be_visible(timeout=6000)
    expect(page.locator(".cz-view .cz-gb", has_text="Lunch F170")).to_have_count(1, timeout=8000)
    page.unroute_all(behavior="ignoreErrors")


def test_a_check_behind_a_shown_day_waits_for_a_calm_moment_instead_of_giving_up(canvas_page, base_url):
    page = day_with_plan(canvas_page, base_url)
    slow_answers(page, 900)
    move_plan_to_day(page, 2)                          # day 2's copy in hand is from before; its new copy is on the way
    page.locator(".cz-hchips a[href*='day=2']").click()
    expect(page.locator(".cz-view[data-level=day][data-day='2']")).to_be_visible()
    page.evaluate("() => { const i = document.createElement('input'); i.id = 'zz-typing'; document.querySelector('.cz-view').appendChild(i); i.focus(); }")      # a field is being typed in
    page.wait_for_timeout(2500)                        # the answer has come and the screen was not calm: nothing may be swapped under the cursor
    assert page.evaluate("document.activeElement.id") == "zz-typing"
    assert page.locator(".cz-view .cz-gb", has_text="Lunch F170").count() == 0
    page.evaluate("document.getElementById('zz-typing').remove()")      # cancelled
    expect(page.locator(".cz-view .cz-gb", has_text="Lunch F170")).to_have_count(1, timeout=8000)
    page.unroute_all(behavior="ignoreErrors")


def test_a_step_sheet_fetched_before_a_write_never_says_mark_done_for_a_done_step(canvas_page):
    page = canvas_page(motion="no-preference")
    page.goto(page.url.split("?")[0] + "?block=a1")
    page.wait_for_selector(".cz-view[data-level=block]")
    quiet_network(page)                                # the steps' sheets are in hand (fetched before the write)
    step = page.locator('.cz-step:has-text("Revenge of the Mummy")')
    sid = step.get_attribute("data-step")
    page.evaluate("(id) => CZ.post('/trip/canvas/step', CZ.tripBody({ step: id, do: 'done', next: CZ.here() })).then(() => CZ.quiet())", sid)
    expect(page.locator(".cz-step.is-done", has_text="Revenge of the Mummy")).to_be_visible()
    page.locator(".cz-step.is-done", has_text="Revenge of the Mummy").click()
    expect(page.get_by_role("button", name="Not done")).to_be_visible()
    assert page.get_by_role("button", name="Mark done").count() == 0
