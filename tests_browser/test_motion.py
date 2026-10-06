"""F-109: one liquid motion everywhere (the F-106 plan card's grow-from-the-tapped-thing spring). Every sheet (booking, SOS, step, add a step, the Ask sheet), the hold menu, the date chip's
row of days, the plan card and the toast GROW out of what was tapped and FOLD back into it: each test opens the thing, pauses its animation on the first frame and measures the real bounding
box (it is the origin's box), on the last frame (it is its resting box) and, on close, the end of the fold (it is the origin's box again); the duration and easing are the tokens (--motion-spring-dur,
--motion-spring for what grows, --motion-dur and --motion-out for the fold). The screen moves (Day | Week, a plan's chat, tabs: tests/test_motion_tokens.py reads the CSS) and the new bubbles and
blocks use the same tokens. Reduced motion: no animation at all. At 390 and 320 wide."""
import re

import pytest
from playwright.sync_api import expect

from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import PHONE
from tests_browser.test_ask_sheet import day_page, phone, open_sheet  # noqa: F401 - fixtures
from tests_browser.test_day_grid import ari, open_day, plan  # noqa: F401
from tests_browser.test_trip_canvas import NARROW, canvas_page, model  # noqa: F401 - fixtures

SPRING = "cubic-bezier(0.3, 1.35, 0.5, 1)"
OUT = "cubic-bezier(0.4, 0, 0.8, 0.4)"
SPRING_MS, FOLD_MS = 380, 240                      # the tokens' values (--motion-spring-dur, --motion-dur)
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


# ---- the Ask sheet ------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("size", SIZES, ids=["390", "320"])
def test_the_ask_sheet_grows_out_of_the_ask_button_and_folds_back_into_it(phone, base_url, size):
    page = phone(size=size, motion="no-preference")
    day_page(page, base_url)
    slow(page)
    page.wait_for_timeout(400)
    origin = page.evaluate(BOX, "#ph-tab-ask .ph-ti")
    page.evaluate("document.getElementById('ph-tab-ask').click()")
    page.wait_for_selector("#ak-sheet")
    grows(page, "#ak-sheet", origin)
    page.evaluate("""() => { const o = [];
      const spy = Element.prototype.animate; Element.prototype.animate = function (...a) { const x = spy.apply(this, a); window.__fold = window.__fold || []; window.__fold.push(x); return x; }; }""")
    page.keyboard.press("Escape")
    page.wait_for_function("window.__fold && window.__fold.length")
    got = page.evaluate("""() => { const a = window.__fold.find(x => x.effect.target.id === 'ak-sheet'); const t = a.effect.getTiming(), el = a.effect.target; a.pause(); a.currentTime = a.effect.getComputedTiming().endTime;
      const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height, dur: t.duration, easing: t.easing }; }""")
    assert near(got, origin) and got["dur"] == SLOW and norm(got["easing"]) == norm(OUT), (got, origin)


def test_the_date_chip_row_grows_out_of_the_chip_and_folds_back_into_it(phone, base_url):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    slow(page)
    open_sheet(page)
    page.wait_for_timeout(SLOW + 300)                                                           # the sheet itself has landed (its transform moves everything inside it)
    page.locator("#ak-chip").click()
    expect(page.locator("#ak-days-pick")).to_be_visible()
    page.evaluate("document.getElementById('ak-sheet').getAnimations().forEach(a => a.finish())")      # the sheet's own move to its new size (below) is done: the chip is where it rests
    grows(page, "#ak-days-pick", page.evaluate(BOX, "#ak-chip"))
    page.wait_for_timeout(500)
    page.evaluate("""() => document.addEventListener('click', e => { const n = e.target.closest('#ak-chip'); if (n) { const r = n.getBoundingClientRect(); window.__tapped = { x: r.x, y: r.y, w: r.width, h: r.height }; } }, true)""")
    page.locator("#ak-chip").click()
    page.wait_for_function("document.querySelector('#ak-days-pick').getAnimations().length")
    folds(page, "#ak-days-pick", page.evaluate("window.__tapped"))                               # the chip's box where the finger was (the sheet may settle its size while the row folds)


# ---- the hold menu and the plan card ---------------------------------------------------------------------------------------------------

def test_the_hold_menu_grows_out_of_the_held_block_and_folds_back_into_it(phone, base_url):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    slow(page)
    page.wait_for_timeout(400)
    block = '.cz-gb[data-act="a1"]'
    page.locator(block).evaluate("e => e.scrollIntoView({ block: 'center' })")
    page.wait_for_timeout(200)
    origin = page.evaluate(BOX, block)
    page.evaluate("b => CZ.hold(document.querySelector(b))", block)
    expect(page.locator(".cz-menu")).to_be_visible()
    grows(page, ".cz-menu", origin, tol=6)                                                       # the block is lifted a little (scaled, wiggling) as the menu comes out of it
    page.wait_for_timeout(500)
    page.keyboard.press("Escape")
    page.wait_for_function("document.querySelector('.cz-menu') && document.querySelector('.cz-menu').getAnimations().length")
    folds(page, ".cz-menu", page.evaluate(BOX, block), tol=6)


def test_the_plan_card_grows_out_of_its_block_and_folds_back_into_it(phone, base_url):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    slow(page)
    page.wait_for_timeout(400)
    block = '.cz-gb[data-act="a1"]'
    page.locator(block).evaluate("e => e.scrollIntoView({ block: 'center' })")
    page.wait_for_timeout(200)
    origin = page.evaluate(BOX, block)
    page.evaluate("b => CZ.openCard(document.querySelector(b))", block)
    expect(page.locator(".cz-card")).to_be_visible()
    grows(page, ".cz-card", origin, tol=6)
    page.wait_for_timeout(500)
    page.keyboard.press("Escape")
    page.wait_for_function("document.querySelector('.cz-card') && document.querySelector('.cz-card').getAnimations().length")
    folds(page, ".cz-card", page.evaluate(BOX, block), tol=6)


# ---- the toast ----------------------------------------------------------------------------------------------------------------------------

def test_the_toast_grows_out_of_what_was_tapped_and_folds_back_into_it(phone, base_url):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    slow(page)
    page.wait_for_timeout(400)
    origin = page.evaluate(BOX, "#ph-tab-ask")
    page.evaluate("""() => { document.getElementById('ph-tab-ask').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch' })); GA.toast('Lunch moved to 12:30 PM'); }""")
    expect(page.locator(".ga-toast")).to_be_visible()
    grows(page, ".ga-toast", origin)
    page.wait_for_timeout(500)
    page.evaluate("GA.hideToast()")
    page.wait_for_function("document.querySelector('.ga-toast') && document.querySelector('.ga-toast').getAnimations().length")
    folds(page, ".ga-toast", origin)


def test_a_toast_nobody_tapped_grows_from_just_above_its_own_place(phone, base_url):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    page.wait_for_timeout(400)
    page.evaluate("GA.toast('Saved')")
    got = probe(page, ".ga-toast", "open")
    assert got["first"]["w"] < got["rest"]["w"] and got["first"]["y"] < got["rest"]["y"] and got["dur"] == SPRING_MS


# ---- the sheets that are levels of the canvas (step, add a step, booking) and SOS --------------------------------------------------------

HERO = """() => document.getAnimations().filter(a => a.effect.pseudoElement === '::view-transition-group(cz-hero)').map(a => {
  const k = a.effect.getKeyframes(), t = a.effect.getTiming(), m = s => { const n = (/matrix\\(([^)]*)\\)/.exec(s || '') || [0, '1,0,0,1,0,0'])[1].split(',').map(parseFloat); return n; };
  const box = f => { const n = m(f.transform); return { x: n[4], y: n[5], w: parseFloat(f.width), h: parseFloat(f.height) }; };
  return { first: box(k[0]), last: box(k[k.length - 1]), dur: t.duration, easing: k[0].easing }; })"""


def hero(page):
    page.wait_for_function("(" + HERO + ")().length > 0")
    got = page.evaluate(HERO)
    assert len(got) == 1, got
    return got[0]


def level_grows(page, tap, origin_sel, sheet_sel):
    """Tapping `tap` opens a sheet level: the hero (what was tapped) grows into the sheet; closing it folds the sheet back into what was tapped."""
    page.evaluate("""s => document.addEventListener('click', e => { const n = e.target.closest(s); if (n) { const r = n.getBoundingClientRect(); window.__tapped = { x: r.x, y: r.y, w: r.width, h: r.height }; } }, true)""", origin_sel)
    page.locator(tap).click()
    origin = page.evaluate("window.__tapped")
    got = hero(page)
    assert near(got["first"], origin, 3), (got["first"], origin)                       # starts as the tapped thing
    expect(page.locator(sheet_sel)).to_be_visible()
    page.wait_for_timeout(SPRING_MS + 250)
    sheet = page.evaluate(BOX, sheet_sel)
    assert near(got["last"], sheet, 3), (got["last"], sheet)                             # ends as the sheet
    assert got["dur"] == SPRING_MS and norm(got["easing"]) == norm(SPRING), got           # the one spring
    page.locator(".cz-sheet .cz-close").click()
    page.wait_for_function("document.documentElement.dataset.czDir")
    back = hero(page)
    assert near(back["first"], sheet, 3), (back["first"], sheet)
    page.wait_for_timeout(SPRING_MS + 250)
    expect(page.locator(sheet_sel)).to_have_count(0)
    assert near(back["last"], page.evaluate(BOX, origin_sel), 3)                         # lands back on the tapped thing
    assert back["dur"] == SPRING_MS and norm(back["easing"]) == norm(SPRING)


@pytest.mark.parametrize("vp", [PHONE, NARROW], ids=["390", "320"])
def test_the_step_sheet_and_the_add_a_step_sheet_grow_out_of_what_was_tapped_and_fold_back(canvas_page, vp):
    page = canvas_page(viewport=vp, motion="no-preference")
    page.goto(page.url + "?block=a1")
    page.wait_for_selector(".cz-view[data-level=block]")
    page.wait_for_timeout(500)
    step = page.locator(".cz-step", has_text="Revenge of the Mummy")
    step.scroll_into_view_if_needed()
    sid = step.get_attribute("data-step")
    level_grows(page, f'.cz-step[data-step="{sid}"]', f'.cz-step[data-step="{sid}"]', ".cz-sheet")
    page.wait_for_timeout(300)
    add = page.locator("#cz-add")
    add.scroll_into_view_if_needed()
    level_grows(page, "#cz-add", "#cz-add", ".cz-sheet-add")


@pytest.fixture
def booked_page(browser, base_url):
    contexts = []

    def make(motion="no-preference", viewport=PHONE):
        ctx = browser.new_context(viewport=viewport, reduced_motion=motion, has_touch=True, is_mobile=True)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day=0")
        page.wait_for_selector(".cz-view[data-level=day][data-day='0']")
        page.wait_for_timeout(500)
        return page

    yield make
    for c in contexts:
        c.close()


@pytest.mark.parametrize("vp", [PHONE, NARROW], ids=["390", "320"])
def test_a_booking_sheet_grows_out_of_its_line_and_folds_back_into_it(booked_page, vp):
    page = booked_page(viewport=vp)
    line = page.locator(".cz-gbk[data-zk]").first
    line.scroll_into_view_if_needed()
    key = line.get_attribute("data-zk")
    level_grows(page, f'.cz-gbk[data-zk="{key}"]', f'.cz-gbk[data-zk="{key}"]', ".cz-sheet-bk")


@pytest.mark.parametrize("vp", [PHONE, NARROW], ids=["390", "320"])
def test_the_sos_sheet_grows_out_of_the_sos_button_and_folds_back_into_it(booked_page, vp):
    page = booked_page(viewport=vp)
    origin = page.evaluate(BOX, "#cz-sos")
    page.locator("#cz-sos").click()
    expect(page.locator(".cz-sheet-sos")).to_be_visible()
    grows(page, ".cz-sheet-sos", origin)
    page.wait_for_timeout(500)
    page.locator(".cz-sheet-sos .cz-close").click()
    page.wait_for_function("document.querySelector('.cz-sheet-sos') && document.querySelector('.cz-sheet-sos').getAnimations().length")
    folds(page, ".cz-sheet-sos", page.evaluate(BOX, "#cz-sos"))
    expect(page.locator(".cz-sheet-sos")).to_have_count(0)


# ---- screen moves share the spring --------------------------------------------------------------------------------------------------------

def test_day_to_week_uses_the_same_spring(canvas_page):
    page = canvas_page(motion="no-preference")
    page.locator(".cz-row", has_text="Universal").locator(".cz-row-link").click()
    page.wait_for_function("document.documentElement.dataset.czDir")
    page.wait_for_function("document.getAnimations().some(a => /view-transition-(old|new)\\(root\\)/.test(a.effect.pseudoElement || ''))")
    got = page.evaluate("""() => document.getAnimations().filter(a => /view-transition-(old|new)\\(root\\)/.test(a.effect.pseudoElement || '')).map(a => { const t = a.effect.getTiming(); return [t.duration, a.effect.getKeyframes()[0].easing]; })""")
    assert got and all(d == SPRING_MS and norm(e) == norm(SPRING) for d, e in got), got


def test_a_dropped_block_settles_with_the_spring(canvas_page):
    page = canvas_page(motion="no-preference")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    got = page.locator(f'.cz-gb[data-act="{lunch.id}"]').evaluate("""e => { e.classList.add('is-landing'); const s = getComputedStyle(e); return [s.transitionDuration, s.transitionTimingFunction, s.transitionProperty]; }""")
    assert got[0].startswith("0.28s") and norm(SPRING) in norm(got[1]) and "transform" in got[2] and "height" in got[2], got


def test_a_new_block_settles_with_the_spring(canvas_page):
    page = canvas_page(motion="no-preference")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    got = page.locator(f'.cz-gb[data-act="{lunch.id}"]').evaluate("""e => { e.classList.add('is-new'); const s = getComputedStyle(e); return [s.animationName, s.animationDuration, s.animationTimingFunction]; }""")
    assert got[0] == "cz-pop" and got[1] == "0.28s" and norm(SPRING) in norm(got[2]), got


# ---- reduced motion: nothing moves, nothing fades ------------------------------------------------------------------------------------------

def test_reduced_motion_the_ask_sheet_the_chip_row_the_menu_the_card_and_the_toast_do_not_animate(phone, base_url):
    page = phone(motion="reduce")
    day_page(page, base_url)
    open_sheet(page)
    calm(page, "#ak-sheet")
    page.locator("#ak-chip").click()
    expect(page.locator("#ak-days-pick")).to_be_visible()
    calm(page, "#ak-days-pick")
    page.locator("#ak-chip").click()
    expect(page.locator("#ak-days-pick")).to_be_hidden()
    page.evaluate("GA.toast('Quiet')")
    calm(page, ".ga-toast")
    page.keyboard.press("Escape")
    expect(page.locator("#ak-sheet")).to_have_count(0)
    page.wait_for_timeout(300)
    block = '.cz-gb[data-act="a1"]'
    page.locator(block).evaluate("e => e.scrollIntoView({ block: 'center' })")
    page.evaluate("b => CZ.hold(document.querySelector(b))", block)
    expect(page.locator(".cz-menu")).to_be_visible()
    calm(page, ".cz-menu")
    page.keyboard.press("Escape")
    expect(page.locator(".cz-menu")).to_have_count(0)
    page.evaluate("b => CZ.openCard(document.querySelector(b))", block)
    expect(page.locator(".cz-card")).to_be_visible()
    calm(page, ".cz-card")
    page.keyboard.press("Escape")
    expect(page.locator(".cz-card")).to_have_count(0)
    assert page.evaluate("GA.motion.log.length") == 0                                              # the helper never moved anything


def test_reduced_motion_the_sos_and_level_sheets_do_not_animate(booked_page):
    page = booked_page(motion="reduce")
    page.locator("#cz-sos").click()
    expect(page.locator(".cz-sheet-sos")).to_be_visible()
    calm(page, ".cz-sheet-sos")
    page.locator(".cz-sheet-sos .cz-close").click()
    expect(page.locator(".cz-sheet-sos")).to_have_count(0)
    page.locator(".cz-gbk[data-zk]").first.click()
    expect(page.locator(".cz-sheet-bk")).to_be_visible()
    assert page.evaluate("document.getAnimations().length") == 0 and page.evaluate("GA.motion.log.length") == 0


def test_reduced_motion_new_bubbles_and_blocks_do_not_settle(canvas_page):
    page = canvas_page(motion="reduce")
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    got = page.locator(f'.cz-gb[data-act="{lunch.id}"]').evaluate("""e => { e.classList.add('is-new', 'is-landing'); const s = getComputedStyle(e); return [s.animationName, s.transitionDuration]; }""")
    assert got[0] == "none"
    assert got[1] in ("0s", "0s, 0s, 0s, 0s")


# ---- the Ask sheet does not jump when the date chip's row opens or closes (it moves from its old size to its new one) --------------------------

TOPS = """sel => { const el = document.querySelector(sel);
  const as = el.getAnimations().filter(a => { const k = a.effect.getKeyframes(); return k.length === 2 && k[0].transform !== undefined && k[1].transform === 'none' && k[0].opacity === undefined; });
  const a = as[as.length - 1]; if (!a) return null;
  const end = a.effect.getComputedTiming().endTime, tops = []; a.pause();
  for (let i = 0; i <= 20; i++) { a.currentTime = end * i / 20; tops.push(el.getBoundingClientRect().top); }
  a.cancel(); return { tops, rest: el.getBoundingClientRect().top }; }"""


def smooth(page, before_top):
    got = page.evaluate(TOPS, "#ak-sheet")
    assert got, "the sheet did not move"
    tops, rest = got["tops"], got["rest"]
    delta = abs(rest - before_top)
    assert delta > 20, delta                                                                    # the row really changes the sheet's size
    assert abs(tops[0] - before_top) <= 3 and abs(tops[-1] - rest) <= 3, (tops[0], before_top, tops[-1], rest)       # starts where the sheet was, ends where it is
    assert max(abs(b - a) for a, b in zip(tops, tops[1:])) <= delta * 0.4, tops                # no single step is a jump


def test_the_ask_sheet_moves_smoothly_when_the_chip_row_opens_and_closes(phone, base_url):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    slow(page)
    open_sheet(page)
    page.wait_for_timeout(SLOW + 300)
    top = page.evaluate("document.getElementById('ak-sheet').getBoundingClientRect().top")
    page.locator("#ak-chip").click()                                                            # taller: the row opens
    expect(page.locator("#ak-days-pick")).to_be_visible()
    smooth(page, top)
    page.wait_for_timeout(300)
    top = page.evaluate("document.getElementById('ak-sheet').getBoundingClientRect().top")
    page.locator("#ak-chip").click()                                                            # shorter: the row folds, then the sheet settles
    expect(page.locator("#ak-days-pick")).to_be_hidden(timeout=9000)
    smooth(page, top)


# ---- an interrupted move: closing in the middle of opening, and tapping twice ----------------------------------------------------------------

def closing_keyframe(page, sel):
    return page.evaluate("""s => { const el = document.querySelector(s); const as = el.getAnimations().filter(a => { const k = a.effect.getKeyframes(); return k.length === 2 && k[1].transform !== 'none' && k[0].transform !== undefined; });
        const a = as[as.length - 1]; return a ? a.effect.getKeyframes()[0].opacity : null; }""", sel)


def test_closing_in_the_middle_of_opening_starts_from_where_it_is(phone, base_url):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    slow(page)
    open_sheet(page)
    page.wait_for_timeout(150)
    page.keyboard.press("Escape")
    page.wait_for_function("document.querySelector('#ak-sheet') && document.querySelector('#ak-sheet').getAnimations().length")
    op = closing_keyframe(page, "#ak-sheet")
    assert op is not None and 0.3 < float(op) < 0.8, op                                         # the sheet was about half there: it folds from that, not from fully opaque


def test_a_double_tap_or_an_early_close_never_throws_and_leaves_nothing_behind(phone, base_url):
    page = phone(motion="no-preference")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    day_page(page, base_url)
    page.wait_for_timeout(400)
    block = '.cz-gb[data-act="a1"]'
    page.locator(block).evaluate("e => e.scrollIntoView({ block: 'center' })")
    page.wait_for_timeout(200)
    page.evaluate("b => CZ.openCard(document.querySelector(b))", block)                       # the card: closed at 100 ms, twice
    page.wait_for_timeout(100)
    page.keyboard.press("Escape")
    page.evaluate("CZ.foldCard()")
    expect(page.locator(".cz-card")).to_have_count(0)
    assert page.evaluate("!!document.activeElement.closest('.cz-gb')")
    page.evaluate("b => CZ.hold(document.querySelector(b))", block)                           # the hold menu
    page.wait_for_timeout(100)
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".cz-menu")).to_have_count(0)
    page.evaluate("document.getElementById('ph-tab-ask').click(); document.getElementById('ph-tab-ask').click()")      # the Ask sheet: two taps, then closed early
    page.wait_for_selector("#ak-sheet")
    page.wait_for_timeout(100)
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator("#ak-sheet")).to_have_count(0)
    expect(page.locator("#ph-tab-ask")).to_be_focused()
    assert errors == [], errors


def test_the_sos_sheet_closed_at_100_ms_or_twice_is_removed_and_focus_returns(booked_page):
    page = booked_page(motion="no-preference")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.locator("#cz-sos").click()
    page.wait_for_timeout(100)
    page.locator(".cz-sheet-sos .cz-close").dispatch_event("click")
    page.keyboard.press("Escape")
    expect(page.locator(".cz-sheet-sos")).to_have_count(0)
    assert page.evaluate("document.activeElement.id") == "cz-sos"
    page.locator("#cz-sos").click()                                                             # and it opens again
    expect(page.locator(".cz-sheet-sos")).to_have_count(1)
    assert errors == [], errors


# ---- the pickers and the booking workspace's popover -----------------------------------------------------------------------------------------

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


@pytest.mark.parametrize("vp", [{"width": 1440, "height": 900}, PHONE], ids=["desktop", "390"])
def test_a_picker_popover_grows_out_of_its_field_and_folds_back_into_it(anywhere, vp):
    page = anywhere("/start", vp)
    trigger = page.get_by_role("button", name=re.compile("^Leaving:"))
    page.evaluate("""() => document.addEventListener('click', e => { const n = e.target.closest('.ga-pick-btn, button'); if (n) { const r = n.getBoundingClientRect(); window.__tapped = { x: r.x, y: r.y, w: r.width, h: r.height }; } }, true)""")
    trigger.click()                                                                              # (the field's box where the finger was: it is pressed a little)
    origin = page.evaluate("window.__tapped")
    expect(page.locator(".ga-pop")).to_be_visible()
    grows(page, ".ga-pop", origin)
    page.wait_for_timeout(300)
    page.keyboard.press("Escape")
    page.wait_for_function("document.querySelector('.ga-pop') && document.querySelector('.ga-pop').getAnimations().length")
    folds(page, ".ga-pop", page.evaluate(BOX, trigger.element_handle()))


def test_the_ledger_breakdown_grows_out_of_the_total_and_folds_back_into_it(anywhere):
    page = anywhere("/plan", {"width": 1440, "height": 900}, ready="#ws-grid[data-focus]")
    origin = page.evaluate(BOX, "#ws-total")
    page.click("#ws-total")
    expect(page.locator("#ws-pop")).to_be_visible()
    grows(page, "#ws-pop", origin)
    page.wait_for_timeout(300)
    page.click("#ws-total")
    page.wait_for_function("document.querySelector('#ws-pop').getAnimations().length")
    folds(page, "#ws-pop", origin)


def test_reduced_motion_the_pickers_and_the_ledger_popover_do_not_animate(anywhere):
    page = anywhere("/start", PHONE, motion="reduce")
    page.get_by_role("button", name=re.compile("^Leaving:")).click()
    expect(page.locator(".ga-pop")).to_be_visible()
    calm(page, ".ga-pop")
    page.keyboard.press("Escape")
    expect(page.locator(".ga-pop")).to_have_count(0)
    page = anywhere("/plan", {"width": 1440, "height": 900}, motion="reduce", ready="#ws-grid[data-focus]")
    page.click("#ws-total")
    calm(page, "#ws-pop")
    page.click("#ws-total")
    expect(page.locator("#ws-pop")).to_be_hidden()
