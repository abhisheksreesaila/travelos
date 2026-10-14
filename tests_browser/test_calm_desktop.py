"""F-156: the laptop is calm. At 1440 with motion ON (the other browser tests reduce it), every move between levels and every thing that opens is a short fade: a frame recorder runs in the page
(every animation frame, every running animation's properties, the CSS and Web Animations and the View Transition's pseudo-elements alike) through week -> day, day -> day, day -> week, a plan click
(the panel), the panel's tabs, Ask, a toast and the top bar's menu. No frame may have a transform, scale, translate, rotate, filter or clip animation, and none may show the outline of a level that
has not arrived (.cz-skel). The phone keeps its liquid motion: the last check reads the same recorder at 390 wide, where the zoom still runs."""
import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_topbar import SAMPLE

MOVING = ("transform", "scale", "translate", "rotate", "filter", "clipPath", "clip-path", "offsetPath")

# Every frame: the properties of every running animation that is not a loop (a pulse or a shimmer is decoration, not a move), and whether the outline of a level that has not arrived is on the screen.
RECORDER = """() => { const rec = window.__rec = { frames: [], on: true };
  const SKIP = new Set(['offset', 'easing', 'composite', 'computedOffset']);
  (function look() {
    if (!rec.on) return;
    const props = {};
    document.getAnimations().forEach(a => {
      const t = a.effect && a.effect.getTiming ? a.effect.getTiming() : null;
      if (!t || t.iterations === Infinity || a.playState === 'finished' || a.playState === 'idle') return;
      const target = a.effect.target;
      let label = target ? (target.id ? '#' + target.id : target.tagName.toLowerCase() + (typeof target.className === 'string' && target.className ? '.' + target.className.split(' ')[0] : '')) : '?';
      if (a.effect.pseudoElement) label += a.effect.pseudoElement;
      (a.effect.getKeyframes ? a.effect.getKeyframes() : []).forEach(k => Object.keys(k).forEach(p => {
        if (!SKIP.has(p) && k[p] !== 'none' && k[p] !== 'auto' && k[p] !== 'normal') (props[p] = props[p] || new Set()).add(label + ':' + (a.animationName || a.transitionProperty || 'js'));
      }));
    });
    rec.frames.push({ props: Object.fromEntries(Object.entries(props).map(([k, v]) => [k, [...v]])), skel: !!document.querySelector('.cz-skel') });
    requestAnimationFrame(look);
  })(); }"""


def findings(page):
    """(the moving properties seen, frames that showed an outline, frames recorded, every property that animated)."""
    got = page.evaluate("() => { window.__rec.on = false; return window.__rec.frames; }")
    moving, every = [], set()
    for f in got:
        for p, who in f["props"].items():
            every.add(p)
            if p in MOVING or p.startswith(("scale", "translate")):
                moving.append(f"{p}: {', '.join(who[:3])}")
    return sorted(set(moving)), sum(1 for f in got if f["skel"]), len(got), sorted(every)


@pytest.fixture
def lively(browser, base_url):
    """lively(viewport, path) -> a signed-in page with a day of plans, motion ON, the recorder not yet started."""
    ctxs = []

    def make(viewport=DESKTOP, path="/trip/canvas?day=1"):
        ctx = browser.new_context(viewport=viewport)          # no reduced_motion: the real motion runs
        ctx.set_default_timeout(5000)
        ctxs.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form=SAMPLE, max_redirects=0)
        me = person("ari")
        cal.add_activity(me, day=1, start=10 * 60, end=11 * 60, title="Slow breakfast", kind="food")
        cal.add_activity(me, day=1, start=18 * 60, end=19 * 60, title="Dinner at CityWalk", kind="food")
        page = ctx.new_page()
        page.goto(f"{base_url}{path}")
        page.wait_for_function("window.GA && GA.motion && !GA.motion.reduced()")
        page.wait_for_timeout(900)      # the page's own arrival and the idle prefetch have landed
        return page

    yield make
    for c in ctxs:
        c.close()


def record(page, act, settle=700):
    page.evaluate(RECORDER)
    act()
    page.wait_for_timeout(settle)
    return findings(page)


def calm(got, what):
    moving, skel, n, every = got
    assert n > 5, f"{what}: the recorder saw {n} frames"
    assert not moving, f"{what}: {moving}"
    assert skel == 0, f"{what}: {skel} frames showed an outline"


def test_week_to_day_and_back_is_a_fade(lively):
    page = lively(path="/trip/canvas")
    calm(record(page, lambda: page.locator(".cz-wcol[data-day='1'] .cz-wopen").click()), "week -> day")
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    calm(record(page, lambda: page.locator("#cz-z-week").click()), "day -> week")
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
    calm(record(page, lambda: page.locator(".cz-wcol[data-day='1'] .cz-wi.is-plan").first.click()), "week -> day by a plan row")
    expect(page.locator("#cz-dock .cz-pp")).to_be_visible()


def test_day_to_day_by_chips_and_arrows_is_a_fade(lively):
    page = lively()
    calm(record(page, lambda: page.locator(".cz-head .cz-hchip", has_text="MON").click()), "day -> day by a chip")
    expect(page.locator("#cz-title")).to_have_text("Monday")
    calm(record(page, lambda: page.keyboard.press("ArrowRight")), "day -> day by an arrow key")
    calm(record(page, lambda: page.keyboard.press("ArrowLeft")), "day -> day by the other arrow key")


def test_a_plan_click_and_the_panel_tabs_are_a_fade(lively):
    page = lively()
    calm(record(page, lambda: page.locator("#cz-up-open").click()), "a plan opens in the panel")
    expect(page.locator("#cz-dock[data-mode=plan]")).to_be_visible()
    for tab in ("Family", "Ask", "Plan"):
        calm(record(page, lambda: page.locator("#cz-dock .cz-dock-tab", has_text=tab).click()), f"the panel's {tab} tab")


def test_a_toast_and_the_top_bar_menu_are_a_fade(lively):
    page = lively()
    calm(record(page, lambda: page.evaluate("GA.toast('Moved to Sat 17', { undo: () => {} })"), settle=1200), "a toast")
    calm(record(page, lambda: page.click(".ga-tb-account > summary")), "the avatar menu")
    calm(record(page, lambda: page.click(".ga-tb-account > summary")), "the avatar menu closing")


SLOW_FETCH = """() => { const real = window.fetch; window.fetch = (u, o) => /frag=1/.test(String(u)) ? new Promise(r => setTimeout(r, 500)).then(() => real(u, o)) : real(u, o); CZ.forget(); }"""


def test_a_click_that_changes_the_level_keeps_the_old_view_until_the_new_one_is_ready(lively):
    page = lively(path="/trip/canvas")
    page.evaluate(SLOW_FETCH)      # nothing fetched ahead, and the server answers slowly
    page.evaluate(RECORDER)
    page.locator(".cz-wcol[data-day='1'] .cz-wopen").click()
    page.wait_for_timeout(250)
    assert page.locator(".cz-view[data-level=week]").count() == 1, "the week stays until the day is in hand"
    page.wait_for_timeout(900)
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    calm(findings(page), "a level that was not fetched ahead")


def test_the_phone_keeps_its_liquid_zoom(lively):
    page = lively(PHONE, path="/trip/canvas")
    page.evaluate(RECORDER)
    page.locator("a.cz-row-link[data-zoom=in]").first.click()
    page.wait_for_timeout(700)
    moving, skel, n, every = findings(page)
    assert moving, "the phone's zoom still scales and blurs"


BUSY = """() => { window.__busy = []; const done = () => {}; const v = () => document.querySelector('.cz-view'), seen = [];
  const t0 = performance.now(), seen2 = window.__busy; (function look() { const row = document.querySelector('.is-pending');
    seen2.push({ at: performance.now() - t0, busy: v() && v().getAttribute('aria-busy'), cursor: getComputedStyle(document.body).cursor, dim: row ? getComputedStyle(row).opacity : null });
    if (performance.now() - t0 < 2600) requestAnimationFrame(look); })(); }"""


def test_a_slow_level_shows_a_quiet_busy_state_that_clears_on_the_swap(lively):
    page = lively(path="/trip/canvas")
    page.evaluate("() => { const real = window.fetch; window.fetch = (u, o) => /frag=1/.test(String(u)) ? new Promise(r => setTimeout(r, 1500)).then(() => real(u, o)) : real(u, o); CZ.forget(); }")
    page.evaluate(RECORDER)
    page.evaluate(BUSY)
    page.locator(".cz-wcol[data-day='1'] .cz-wopen").click()
    page.wait_for_timeout(2000)
    seen = page.evaluate('window.__busy')
    early = [f for f in seen if f["at"] < 90]
    assert all(not f["busy"] for f in early), "nothing is shown for a level that is quick"
    mid = [f for f in seen if 400 < f["at"] < 1300]
    assert mid and all(f["busy"] == "true" and f["cursor"] == "progress" and f["dim"] is not None and float(f["dim"]) < 1 for f in mid), mid[:3]
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    assert page.evaluate("!document.querySelector('.cz-view').hasAttribute('aria-busy') && !document.documentElement.classList.contains('cz-pending') && !document.querySelector('.is-pending')")
    moving, skel, n, every = findings(page)
    assert not moving and skel == 0, moving


def test_escape_closes_the_menu_and_only_the_menu_then_the_next_one_zooms_out(lively):
    page = lively()
    page.click(".ga-tb-account > summary")
    expect(page.locator(".ga-tb-account")).to_have_attribute("open", "")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    assert page.evaluate("!document.querySelector('.ga-tb-account').open")
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".cz-view[data-level=week]")).to_be_visible()
