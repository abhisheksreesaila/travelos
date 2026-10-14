"""F-154: the top bar's two menus (the avatar's and the trip picker's) are people's most-used controls, so they must be usable at once: with motion ON, their items are still within 0.25s of the click
(1440 wide). They still grow out of their button and fold back with GA.motion and the --motion-* tokens (no timing of their own)."""
import pytest

from tests_browser.helpers import DESKTOP
from tests_browser.test_topbar import SAMPLE, SECOND

LIMIT_MS = 250

# Sample the menu's items every frame from the click; afterwards, the last moment (ms after the click) any item was more than 1px from where it ends up, or the menu was not yet fully opaque.
RECORD = """([menu, itemSel]) => new Promise(done => {
  const d = document.querySelector(menu), items = Array.from(d.querySelectorAll(itemSel)), pop = d.querySelector('.ga-tb-pop'), t0 = performance.now(), rows = [];
  const spots = () => items.map(i => { const r = i.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; });
  d.querySelector('summary').click();
  (function look() {
    const now = performance.now() - t0;
    rows.push({ at: now, spots: spots(), opacity: parseFloat(getComputedStyle(pop).opacity) });
    if (now < 1500) return requestAnimationFrame(look);
    const rest = rows[rows.length - 1].spots;
    let lastMove = 0;
    rows.forEach(r => { if (r.opacity < 0.99 || r.spots.some((s, i) => s.some((v, k) => Math.abs(v - rest[i][k]) > 1))) lastMove = r.at; });
    done({ lastMove, n: items.length, trail: rows.filter(r => r.at < 700).map(r => Math.round(r.at) + ':' + r.spots[0].map(v => v.toFixed(1)).join(',') + ':' + r.opacity.toFixed(2)) });
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
    print(f"\n{menu}: {got['n']} items, last movement {got['lastMove']:.0f} ms after the click")
    assert got["n"] >= 2
    assert got["lastMove"] <= LIMIT_MS, got["trail"]


@pytest.mark.parametrize("menu", [".ga-tb-account", ".ga-tb-picker:not(.ga-tb-phonepick)"], ids=["avatar", "trip-picker"])
def test_the_menu_still_grows_out_of_its_button_and_folds_back_with_the_tokens(lively, menu):
    page = lively()
    page.wait_for_timeout(600)
    tokens = page.evaluate("({ dur: getComputedStyle(document.documentElement).getPropertyValue('--motion-dur').trim(), ease: getComputedStyle(document.documentElement).getPropertyValue('--motion-ease').trim(), out: getComputedStyle(document.documentElement).getPropertyValue('--motion-out').trim() })")
    button = page.locator(f"{menu} > summary").bounding_box()
    page.evaluate("GA.motion.log.length = 0")
    page.click(f"{menu} > summary")
    page.wait_for_timeout(400)
    grow = page.evaluate("GA.motion.log.filter(m => m.kind === 'open').pop()")
    assert grow, "the menu opened with GA.motion"
    assert f"{grow['dur']}ms" == tokens["dur"] and grow["easing"] == tokens["ease"]          # a token's duration and easing, none of its own
    assert abs(grow["from"]["left"] - button["x"]) < 1 and abs(grow["from"]["top"] - button["y"]) < 1      # it grows out of its button
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    fold = page.evaluate("GA.motion.log.filter(m => m.kind === 'close').pop()")
    assert fold, "the menu folded with GA.motion"
    assert f"{fold['dur']}ms" == tokens["dur"] and fold["easing"] == tokens["out"]
    assert abs(fold["to"]["left"] - button["x"]) < 1 and abs(fold["to"]["top"] - button["y"]) < 1       # and folds back into it
    assert page.evaluate(f"!document.querySelector('{menu}').open")
