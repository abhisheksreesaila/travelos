"""F-154: the top bar's two menus (the avatar's and the trip picker's) are people's most-used controls, so they must be usable at once: with motion ON, their items are still within 0.25s of the click
(1440 wide). They still grow out of their button and fold back with GA.motion and the --motion-* tokens (no timing of their own)."""
import pytest

from tests_browser.helpers import DESKTOP
from tests_browser.test_topbar import SAMPLE, SECOND

LIMIT_MS = 250

# Sample the menu's items every frame from the click; afterwards, the last moment (ms after the grow began) any item was more than 1px from where it ends up, or the menu was not yet fully opaque.
RECORD = """([menu, itemSel]) => new Promise(done => {
  const d = document.querySelector(menu), items = Array.from(d.querySelectorAll(itemSel)), pop = d.querySelector('.ga-tb-pop'), t0 = performance.now(), rows = [];
  const spots = () => items.map(i => { const r = i.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; });
  let anim = null, began = 0;
  d.querySelector('summary').click();
  (function look() {
    const now = performance.now() - t0;
    if (!anim) { anim = pop.getAnimations().find(a => a.effect.getKeyframes().some(f => f.opacity !== undefined)); if (anim) began = now; }      // the grow starts a moment after the click (the toggle event); a busy machine delays that, not the menu
    rows.push({ at: now, spots: spots(), opacity: parseFloat(getComputedStyle(pop).opacity) });
    if (now < 1500) return requestAnimationFrame(look);
    const rest = rows[rows.length - 1].spots;
    let lastMove = 0;
    rows.forEach(r => { if (r.at < began) return; if (r.opacity < 0.99 || r.spots.some((s, i) => s.some((v, k) => Math.abs(v - rest[i][k]) > 1))) lastMove = r.at - began; });
    done({ lastMove, duration: anim && anim.effect.getTiming().duration, n: items.length, trail: rows.filter(r => r.at < 700).map(r => Math.round(r.at) + ':' + r.spots[0].map(v => v.toFixed(1)).join(',') + ':' + r.opacity.toFixed(2)) });
  })();
})"""


@pytest.fixture
def lively(browser, base_url):
    """A signed-in page at 1440 with two trips and motion ON (the other browser tests reduce it)."""
    ctxs = []

    def make():
        ctx = browser.new_context(viewport=DESKTOP)          # no reduced_motion: the real spring runs
        ctx.set_default_timeout(5000)
        ctxs.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
        for pick in (SAMPLE, SECOND):
            ctx.request.post(f"{base_url}/pay", form=pick, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day=0")
        page.wait_for_function("window.GA && GA.motion && !GA.motion.reduced()")
        return page

    yield make
    for c in ctxs:
        c.close()


@pytest.mark.parametrize("menu,items", [(".ga-tb-account", ".ga-tb-item"), (".ga-tb-picker:not(.ga-tb-phonepick)", ".ga-tb-sw, .ga-tb-item")], ids=["avatar", "trip-picker"])
def test_the_menu_is_usable_within_a_quarter_second_with_motion_on(lively, menu, items):
    page = lively()
    page.wait_for_timeout(600)          # the page's own arrival has landed
    got = page.evaluate(RECORD, [menu, items])
    print(f"\n{menu}: {got['n']} items, last movement {got['lastMove']:.0f} ms after the grow began")
    assert got["n"] >= 2
    assert got["duration"] == 140, "F-156: on the laptop it fades with --motion-desk (140ms), not the spring"          # the animation's own length, whatever the machine's speed
    assert got["lastMove"] <= LIMIT_MS, got["trail"]


@pytest.mark.parametrize("menu", [".ga-tb-account", ".ga-tb-picker:not(.ga-tb-phonepick)"], ids=["avatar", "trip-picker"])
def test_the_menu_fades_in_and_out_with_the_desktop_token(lively, menu):
    page = lively()
    page.wait_for_timeout(600)
    desk = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--motion-desk').trim()")
    page.evaluate("GA.motion.log.length = 0")
    page.click(f"{menu} > summary")
    page.wait_for_timeout(400)
    grow = page.evaluate("GA.motion.log.filter(m => m.kind === 'open').pop()")
    assert grow and grow["calm"] and f"{grow['dur']}ms" == desk          # F-156: a short fade with the desktop token; it does not grow out of the button
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    fold = page.evaluate("GA.motion.log.filter(m => m.kind === 'close').pop()")
    assert fold and fold["calm"] and f"{fold['dur']}ms" == desk
    assert page.evaluate(f"!document.querySelector('{menu}').open")


def test_the_phone_trip_sheet_still_opens_with_the_spring(browser, base_url):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    ctx.set_default_timeout(5000)
    try:
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
        for pick in (SAMPLE, SECOND):
            ctx.request.post(f"{base_url}/pay", form=pick, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day=0")
        page.wait_for_function("window.GA && GA.motion && !GA.motion.reduced()")
        page.wait_for_timeout(600)
        spring = page.evaluate("({ dur: getComputedStyle(document.documentElement).getPropertyValue('--motion-spring-dur').trim(), ease: getComputedStyle(document.documentElement).getPropertyValue('--motion-spring').trim() })")
        page.evaluate("GA.motion.log.length = 0")
        page.click(".ga-tb-phonepick > summary")
        page.wait_for_timeout(700)
        grow = page.evaluate("GA.motion.log.filter(m => m.kind === 'open').pop()")
        assert grow and f"{grow['dur']}ms" == spring["dur"] and grow["easing"] == spring["ease"]
    finally:
        ctx.close()
