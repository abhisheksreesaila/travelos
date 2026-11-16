"""F-109, F-111: one liquid motion. What grows out of what was tapped and folds back into it (here: a date picker's popover on /plan-for-me/start) is paused on its first frame (the origin's box), its last (its resting box)
and at the end of the fold; the timing is the tokens; its words are never stretched; reduced motion has no animation. The old canvas's sheets, menu, card and toast (and the ledger popover on /plan) went with F-254, with their tests."""
import re

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE

SPRING = "cubic-bezier(0.3, 1.12, 0.4, 1)"
CALM = "cubic-bezier(0.22, 1, 0.36, 1)"              # screen moves: no overshoot (F-114), a long soft landing (F-137)
OUT = "cubic-bezier(0.4, 0, 0.8, 0.4)"
SPRING_MS, FOLD_MS, SCREEN_MS = 380, 240, 340          # the tokens' values (--motion-spring-dur, --motion-dur, --motion-screen-dur: a whole screen moving, F-129)
SLOW = 2500                                        # the tests that sample frames slow the tokens down so a sheet that settles its size in its first moments is caught at rest
SIZES = [(390, 844), (320, 640)]


def norm(s):
    return re.sub(r"\s+", "", s)


# Pause the element's grow (kind "open") or fold (kind "close") on its first frame, its last frame, and let it go: the bounding boxes there, and the timing.
PROBE = """([sel, kind]) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const as = el.getAnimations().filter(a => { const k = a.effect.getKeyframes(); return k.length === 2 && k[0].transform !== undefined && (kind === 'open' ? k[1].transform === 'none' && k[0].opacity !== undefined : k[1].transform !== 'none'); });
  const a = as[as.length - 1];
  if (!a) return null;
  const box = () => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; };
  const t = a.effect.getTiming();
  a.pause(); a.currentTime = 0; const first = box();
  a.currentTime = a.effect.getComputedTiming().endTime; const last = box();
  a.cancel(); const rest = box();
  return { first, last, rest, dur: t.duration, easing: t.easing };
}"""
BOX = """sel => { const r = (typeof sel === 'string' ? document.querySelector(sel) : sel).getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; }"""


def near(a, b, tol=2.5):
    return all(abs(a[k] - b[k]) <= tol for k in ("x", "y", "w", "h"))


def probe(page, sel, kind):
    got = page.evaluate(PROBE, [sel, kind])
    assert got, f"{sel} has no {kind} animation"
    return got


def grows(page, sel, origin, tol=2.5):
    """The element's first frame is the origin's box, its last frame its resting box, and the timing is the one spring."""
    page.wait_for_timeout(200)                                                                  # a sheet may settle its size in its first moments: the grow aims at where it really rests
    got = probe(page, sel, "open")
    assert near(got["first"], origin, tol), (got["first"], origin)
    assert near(got["last"], got["rest"]), (got["last"], got["rest"])
    assert got["dur"] == page.evaluate("GA.motion.t('spring')") and norm(got["easing"]) == norm(SPRING), got
    return got


def folds(page, sel, origin, tol=2.5):
    got = probe(page, sel, "close")
    assert near(got["last"], origin, tol), (got["last"], origin)
    assert got["dur"] == page.evaluate("GA.motion.t('dur')") and norm(got["easing"]) == norm(OUT), got
    return got


def slow(page):
    page.add_style_tag(content=f":root {{ --motion-spring-dur: {SLOW}ms; --motion-dur: {SLOW}ms; }}")


def calm(page, sel):
    assert page.evaluate("s => (document.querySelector(s) || { getAnimations: () => [] }).getAnimations().length", sel) == 0


NARROW = {"width": 320, "height": 640}

@pytest.fixture
def anywhere(browser, base_url):
    contexts = []

    def make(path, viewport, motion="no-preference", ready="html[data-ga-ready]"):
        ctx = browser.new_context(viewport=viewport, reduced_motion=motion)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        page = ctx.new_page()
        page.goto(f"{base_url}{path}")
        page.wait_for_selector(ready)
        page.wait_for_function("document.getAnimations().length === 0")                          # the page's own entrance has played
        slow(page)
        return page

    yield make
    for c in contexts:
        c.close()

DATES = "/plan-for-me/start?start=2026-10-16&end=2026-10-20&adults=2"      # a page with a date picker (F-231: it was on the deleted /start)


@pytest.mark.parametrize("vp", [{"width": 1000, "height": 800}, PHONE], ids=["tablet", "390"])      # (F-156: from 1020px the laptop only fades; tests_browser/test_calm_desktop.py)
def test_a_picker_popover_grows_out_of_its_field_and_folds_back_into_it(anywhere, vp):
    page = anywhere(DATES, vp)
    trigger = page.get_by_role("button", name=re.compile("^From:"))
    page.evaluate("""() => document.addEventListener('click', e => { const n = e.target.closest('.ga-pick-btn, button'); if (n) { const r = n.getBoundingClientRect(); window.__tapped = { x: r.x, y: r.y, w: r.width, h: r.height }; } }, true)""")
    trigger.click()                                                                              # (the field's box where the finger was: it is pressed a little)
    origin = page.evaluate("window.__tapped")
    expect(page.locator(".ga-pop")).to_be_visible()
    grows(page, ".ga-pop", origin)
    page.wait_for_timeout(300)
    page.keyboard.press("Escape")
    page.wait_for_function("document.querySelector('.ga-pop') && document.querySelector('.ga-pop').getAnimations().length")
    folds(page, ".ga-pop", page.evaluate(BOX, trigger.element_handle()))


# ---- F-110: while a box changes size, its words keep their shape ------------------------------------------------------------------------------------------
# A box that is scaled from its old size to its new one used to squish the words in it for a moment. Each test pauses every animation under the box, steps through the move
# in twenty frames and measures the words' own boxes (a span's width over its height): within 2% of what it is at rest, in every frame, while the box itself really changes size.

SHAPE = """([sel, words, skip]) => {
  const root = document.querySelector(sel), kids = [root, ...root.querySelectorAll('*')];
  const spans = [...root.querySelectorAll(words)].filter(e => !e.children.length && e.textContent.trim() && e.getClientRects().length && !(skip && e.closest(skip)));
  const as = kids.flatMap(k => k.getAnimations()).filter(a => a.playState === 'running' && Number.isFinite(a.effect.getComputedTiming().endTime));
  if (!as.length || !spans.length) return null;
  const ratio = e => { const r = e.getBoundingClientRect(); return r.width / r.height; };
  const rootBox = () => { const r = root.getBoundingClientRect(); return [r.width, r.height]; };
  const end = Math.max(...as.map(a => a.effect.getComputedTiming().endTime));
  as.forEach(a => a.pause());
  const frames = [];
  for (let i = 0; i <= 20; i++) { as.forEach(a => { a.currentTime = Math.min(end, a.effect.getComputedTiming().endTime) * i / 20; }); frames.push({ box: rootBox(), ratios: spans.map(ratio) }); }
  as.forEach(a => a.cancel());
  const rest = spans.map(ratio);
  return { frames, rest, count: spans.length, names: spans.map(e => e.tagName + '#' + e.id + '.' + e.className + ':' + e.textContent.trim().slice(0, 20) + ' in ' + (e.parentElement.closest('[id]') || {}).id) };
}"""


def keeps_shape(got):
    assert got and got["count"], "nothing moved, or no words to measure"
    first, last = got["frames"][0]["box"], got["frames"][-1]["box"]
    assert abs(first[1] - last[1]) > 15 or abs(first[0] - last[0]) > 15, got["frames"][0]["box"]      # the box really changes size
    worst = max(abs(r / rest - 1) for f in got["frames"] for r, rest in zip(f["ratios"], got["rest"]))
    assert worst <= 0.02, (worst, [(n, round(max(abs(f['ratios'][i] / got['rest'][i] - 1) for f in got['frames']), 3)) for i, n in enumerate(got['names'])])


def test_reduced_motion_the_pickers_do_not_animate(anywhere):
    page = anywhere(DATES, PHONE, motion="reduce")
    page.get_by_role("button", name=re.compile("^From:")).click()
    expect(page.locator(".ga-pop")).to_be_visible()
    calm(page, ".ga-pop")
    page.keyboard.press("Escape")
    expect(page.locator(".ga-pop")).to_have_count(0)



# ---- F-111: what GROWS or FOLDS (open/close) never stretches its words either ---------------------------------------------------------------------------------
# The same measure as above, taken on the first moments of every thing that grows out of what was tapped: the row of days, the hold menu, the SOS sheet, the plan card, a picker's
# popover and the toast, at 390 and 320 wide, while it opens and again while it folds.

EVERY_WORD = "*"


def grow_keeps_shape(page, sel, skip=None):
    page.wait_for_selector(sel)
    keeps_shape(page.evaluate(SHAPE, [sel, EVERY_WORD, skip]))


def fold_keeps_shape(page, sel, trigger):
    trigger()
    page.wait_for_function("s => { const e = document.querySelector(s); return e && e.getAnimations().length }", arg=sel)
    keeps_shape(page.evaluate(SHAPE, [sel, EVERY_WORD, None]))





@pytest.mark.parametrize("vp", [PHONE, NARROW], ids=["390", "320"])
def test_a_picker_popover_keeps_its_words_unsquished_while_it_grows_and_folds(anywhere, vp):
    page = anywhere(DATES, vp)
    page.get_by_role("button", name=re.compile("^From:")).click()
    grow_keeps_shape(page, ".ga-pop")
    page.wait_for_timeout(SLOW + 300)
    fold_keeps_shape(page, ".ga-pop", lambda: page.keyboard.press("Escape"))

