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
    page.wait_for_timeout(200)                                                                   # the sheet settles its size as the microphone stops: the fold follows it
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
    page.evaluate("(() => { const s = document.getElementById('ak-sheet'); [s, ...s.children].forEach(n => n.getAnimations().forEach(a => a.finish())); })()")      # the sheet's own move to its new size (below), and its words' counter-scale (F-110), are done: the chip is where it rests
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


def test_without_motion_js_the_stand_in_keeps_every_sheet_working_and_throws_nothing(canvas_page):
    """F-110: the one shared stand-in (motion_fallback.js) answers when motion.js did not load: the hold menu and the plan card open and close, instantly, with no error."""
    page = canvas_page(motion="no-preference")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.evaluate("navigator.serviceWorker ? navigator.serviceWorker.getRegistrations().then(rs => Promise.all(rs.map(r => r.unregister()))) : 0")      # the page's own requests reach the route, not a cached copy
    page.route(re.compile(r"/assets/js/motion\.js"), lambda r: r.abort())
    lunch = plan("Lunch", 12 * 60, 13 * 60)
    open_day(page)
    assert page.evaluate("GA.motion.fallback === true")
    sel = f'.cz-gb[data-act="{lunch.id}"]'
    page.evaluate("b => CZ.hold(document.querySelector(b))", sel)
    expect(page.locator(".cz-menu")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".cz-menu")).to_have_count(0)
    page.evaluate("b => CZ.openCard(document.querySelector(b))", sel)
    expect(page.locator(".cz-card")).to_be_visible()
    page.evaluate("CZ.foldCard()")
    expect(page.locator(".cz-card")).to_have_count(0)
    page.evaluate("GA.toast && GA.toast('Hello')")
    assert errors == [], errors


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


def test_the_flip_never_stretches_the_words_in_the_box_it_scales(phone, base_url):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    page.evaluate("""() => { const d = document.createElement('div'); d.id = 'flipbox';
      d.style.cssText = 'position:fixed;left:20px;top:140px;width:240px;height:220px;background:#eee;overflow:hidden';
      d.innerHTML = '<span id=w1 style="display:inline-block">A line of words</span><p style="margin:12px 0 0"><span>And another one</span></p>'; document.body.appendChild(d);
      window.__flip = GA.motion.flip(d, { left: 20, top: 140, width: 240, height: 90 }, { left: 20, top: 140, width: 240, height: 220 }); }""")
    keeps_shape(page.evaluate(SHAPE, ["#flipbox", "span"]))


def test_the_ask_sheet_keeps_its_words_unsquished_while_the_chip_row_opens_and_closes(phone, base_url):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    slow(page)
    open_sheet(page)
    page.wait_for_timeout(SLOW + 300)
    page.locator("#ak-chip").click()
    expect(page.locator("#ak-days-pick")).to_be_visible()
    words = "span, label, button, p, h2, h3"      # every word in the sheet except the row of days, which is itself growing out of the chip (it has its own move)
    keeps_shape(page.evaluate(SHAPE, ["#ak-sheet", words, "#ak-days-pick"]))
    page.wait_for_timeout(SLOW + 300)
    page.locator("#ak-chip").click()
    expect(page.locator("#ak-days-pick")).to_be_hidden(timeout=9000)
    keeps_shape(page.evaluate(SHAPE, ["#ak-sheet", words, "#ak-days-pick"]))


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


@pytest.mark.parametrize("size", SIZES, ids=["390", "320"])
def test_the_days_row_keeps_its_words_unsquished_while_it_grows_and_folds(phone, base_url, size):
    page = phone(size=size, motion="no-preference")
    day_page(page, base_url)
    slow(page)
    open_sheet(page)
    page.wait_for_timeout(SLOW + 300)
    page.locator("#ak-chip").click()
    expect(page.locator("#ak-days-pick")).to_be_visible()
    page.evaluate("(() => { const s = document.getElementById('ak-sheet'); [s, ...s.children].forEach(n => n.getAnimations().forEach(a => a.finish())); })()")
    grow_keeps_shape(page, "#ak-days-pick")
    page.wait_for_timeout(SLOW + 300)
    fold_keeps_shape(page, "#ak-days-pick", lambda: page.locator("#ak-chip").click())


@pytest.mark.parametrize("size", SIZES, ids=["390", "320"])
def test_the_hold_menu_and_the_plan_card_keep_their_words_unsquished_while_they_grow_and_fold(phone, base_url, size):
    page = phone(size=size, motion="no-preference")
    day_page(page, base_url)
    slow(page)
    page.wait_for_timeout(400)
    block = '.cz-gb[data-act="a1"]'
    page.locator(block).evaluate("e => e.scrollIntoView({ block: 'center' })")
    page.wait_for_timeout(200)
    page.evaluate("b => CZ.hold(document.querySelector(b))", block)
    grow_keeps_shape(page, ".cz-menu")
    page.wait_for_timeout(SLOW + 300)
    fold_keeps_shape(page, ".cz-menu", lambda: page.keyboard.press("Escape"))
    page.wait_for_timeout(SLOW + 300)
    page.evaluate("b => CZ.openCard(document.querySelector(b))", block)
    grow_keeps_shape(page, ".cz-card")
    page.wait_for_timeout(SLOW + 300)
    fold_keeps_shape(page, ".cz-card", lambda: page.keyboard.press("Escape"))


@pytest.mark.parametrize("vp", [PHONE, NARROW], ids=["390", "320"])
def test_the_sos_sheet_keeps_its_words_unsquished_while_it_grows_and_folds(booked_page, vp):
    page = booked_page(viewport=vp)
    slow(page)
    page.locator("#cz-sos").click()
    grow_keeps_shape(page, ".cz-sheet-sos")
    page.wait_for_timeout(SLOW + 300)
    fold_keeps_shape(page, ".cz-sheet-sos", lambda: page.locator(".cz-sheet-sos .cz-close").click())


@pytest.mark.parametrize("size", SIZES, ids=["390", "320"])
def test_the_toast_keeps_its_words_unsquished_while_it_grows_and_folds(phone, base_url, size):
    page = phone(size=size, motion="no-preference")
    day_page(page, base_url)
    slow(page)
    page.wait_for_timeout(400)
    page.evaluate("""() => { document.getElementById('ph-tab-ask').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch' })); GA.toast('Lunch moved to 12:30 PM'); }""")
    grow_keeps_shape(page, ".ga-toast")
    page.wait_for_timeout(SLOW + 300)
    fold_keeps_shape(page, ".ga-toast", lambda: page.evaluate("GA.hideToast()"))


@pytest.mark.parametrize("vp", [PHONE, NARROW], ids=["390", "320"])
def test_a_picker_popover_keeps_its_words_unsquished_while_it_grows_and_folds(anywhere, vp):
    page = anywhere("/start", vp)
    page.get_by_role("button", name=re.compile("^Leaving:")).click()
    grow_keeps_shape(page, ".ga-pop")
    page.wait_for_timeout(SLOW + 300)
    fold_keeps_shape(page, ".ga-pop", lambda: page.keyboard.press("Escape"))


# ---- F-111 review: a thing called back from its fold keeps no leftover counter-scale -----------------------------------------------------------------------------

@pytest.mark.parametrize("tapped", [True, False], ids=["tap", "no-tap"])
def test_a_toast_called_back_during_its_fade_has_its_words_at_their_own_size(phone, base_url, tapped):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    page.wait_for_timeout(400)
    if tapped:
        page.evaluate("document.getElementById('ph-tab-ask').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch' }))")
    page.evaluate("GA.toast('Lunch moved to 12:30 PM')")
    page.wait_for_timeout(600)
    page.evaluate("GA.hideToast()")
    page.wait_for_function("document.querySelector('.ga-toast').getAnimations().length > 1")
    page.wait_for_timeout(80)                                                                    # the fold is under way: its words are scaled down
    page.evaluate("GA.toast('Back again')")
    page.wait_for_timeout(100)
    got = page.evaluate("""() => [...document.querySelectorAll('.ga-toast, .ga-toast *')].map(e => getComputedStyle(e).transform).filter(t => t !== 'none')""")
    assert got == [], got
    page.wait_for_timeout(700)
    assert page.evaluate("document.querySelector('.ga-toast-body').getAnimations().length") == 0



CLIP = """([sel, at]) => {
  const el = document.querySelector(sel), as = el.getAnimations().filter(a => a.effect.getKeyframes().some(k => k.clipPath !== undefined));
  if (!as.length) return null;
  const a = as[as.length - 1]; a.pause(); a.currentTime = a.effect.getComputedTiming().endTime * at;
  return getComputedStyle(el).clipPath;
}"""


def test_a_fold_eases_its_clip_in_and_a_fold_that_interrupts_a_grow_does_not_snap_it(phone, base_url):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    slow(page)
    page.wait_for_timeout(400)
    page.evaluate("GA.toast('Saved')")
    page.wait_for_timeout(SLOW + 400)
    page.evaluate("GA.hideToast()")
    page.wait_for_function("document.querySelector('.ga-toast').getAnimations().length > 1")
    first = page.evaluate(CLIP, [".ga-toast", 0])
    assert first not in ("inset(0px)", "none") and page.evaluate(CLIP, [".ga-toast", 0.4]) == "inset(0px)", first          # the shadow does not vanish in one frame
    page.evaluate("document.getElementById('ph-tab-ask').click()")                                       # a sheet half way through its grow: its clip is still shut
    page.wait_for_selector("#ak-sheet")
    page.wait_for_timeout(SLOW * 0.5)
    page.keyboard.press("Escape")
    page.wait_for_function("document.querySelector('#ak-sheet').getAnimations().some(a => a.effect.getKeyframes().some(k => k.clipPath !== undefined && k.offset === 0.15))")
    snap = page.evaluate(CLIP, ["#ak-sheet", 0])
    assert snap == "inset(0px)", snap                                                                   # the fold starts where the grow left it


def test_the_words_counter_scale_keeps_the_corner_as_a_style_not_in_its_keyframes(phone, base_url):
    page = phone(motion="no-preference")
    day_page(page, base_url)
    slow(page)
    page.wait_for_timeout(400)
    page.evaluate("GA.toast('Saved')")
    got = page.evaluate("""() => { const b = document.querySelector('.ga-toast-body'), a = b.getAnimations().find(x => x.id === 'ga-keep');
      return { keys: a.effect.getKeyframes().some(k => k.transformOrigin !== undefined), style: b.style.transformOrigin }; }""")
    assert got["keys"] is False and got["style"], got
    page.wait_for_timeout(SLOW + 400)
    assert page.evaluate("document.querySelector('.ga-toast-body').style.transformOrigin") == ""


@pytest.mark.parametrize("size", SIZES, ids=["390", "320"])
def test_the_ask_sheet_itself_keeps_its_words_unsquished_while_it_grows_and_folds(phone, base_url, size):
    page = phone(size=size, motion="no-preference")
    day_page(page, base_url)
    slow(page)
    page.wait_for_timeout(400)
    page.evaluate("document.getElementById('ph-tab-ask').click()")
    grow_keeps_shape(page, "#ak-sheet")
    page.wait_for_timeout(SLOW + 400)
    fold_keeps_shape(page, "#ak-sheet", lambda: page.keyboard.press("Escape"))


def test_the_ledger_popover_keeps_its_words_unsquished_while_it_grows_and_folds(anywhere):
    page = anywhere("/plan", {"width": 1440, "height": 900}, ready="#ws-grid[data-focus]")
    page.click("#ws-total")
    grow_keeps_shape(page, "#ws-pop")
    page.wait_for_timeout(SLOW + 400)
    fold_keeps_shape(page, "#ws-pop", lambda: page.click("#ws-total"))
