"""F-282 in a real browser: the hotel as a decision dashboard, the fine print up front and the review drawer. The showcase's opened square carries the sample dashboard (Hilton Los Angeles Airport's
recorded LiteAPI answers, labelled a sample); its pins are the recorded OpenStreetMap answer. What is proved here: the dashboard and the fine print are on the page at 1440 and 390; the rows that
depend on the room and flight follow the choice (fees paid at the hotel and what the stay really costs, refundability, the landing against check-in); the pins arrive with their Heads up; the review
drawer opens from the score, the strip and a complaint, filters by traveller type and by a complaint, is a side sheet on a laptop and a full-height sheet on a phone, and Escape and the close button
give the focus back. Set F282_SHOTS=1 for docs/report/f282-*.png."""
import re
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import gridsource, liteapi
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_matrixbook_sheet import BookStand, open_square  # noqa: F401
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
BOTH = [DESKTOP, PHONE]
IDS = ["1440", "390"]


@pytest.fixture
def sample(monkeypatch, stand, tmp_path):  # noqa: F811
    import json
    import shutil
    from gitaway.pages import hotelview
    from tests.test_hotelfine import reviews_doc
    shutil.copy(hotelview.SAMPLE_DIR / "hotel.json", tmp_path / "hotel.json")
    (tmp_path / "reviews100.json").write_text(json.dumps(reviews_doc()), encoding="utf-8")      # three SYNTHETIC cons share two words with the Pricey complaint
    monkeypatch.setattr(hotelview, "SAMPLE_DIR", tmp_path)
    monkeypatch.setattr(gridsource, "SQUARE", BookStand(sample=True))
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: (_ for _ in ()).throw(AssertionError("LiteAPI was asked")))
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")


def shot(page, name):
    if os.environ.get("F282_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f282-{name}.png"))


def opened(matrix, viewport, **kw):  # noqa: F811
    page = matrix(viewport, signed_in=True, **kw)
    drawer = open_square(page, viewport)
    slot = drawer.locator(".dr-sampleslot")
    expect(slot).to_be_visible()
    expect(slot.locator(".fp-sample").first).to_contain_text("Sample: these scores and reviews are a real hotel’s (Hilton Los Angeles Airport)")      # above the dashboard
    return page, drawer, slot


@pytest.mark.parametrize("viewport", BOTH, ids=IDS)
def test_the_dashboard_and_the_fine_print_are_on_the_page_and_labelled_a_sample(matrix, sample, viewport):  # noqa: F811
    page, drawer, slot = opened(matrix, viewport)
    dash = slot.locator(".dr-dash")
    expect(dash.locator(".dr-score")).to_have_text("7.6")
    expect(dash).to_contain_text("Good")
    expect(dash).to_contain_text("6,263 reviews")
    expect(dash).to_contain_text("Last 100 reviews")
    expect(dash).to_contain_text("The last 10 were all 8 or more.")
    expect(dash.locator(".dr-bar").first).to_have_attribute("aria-label", "Cleanliness 8 out of 10")
    assert dash.locator(".dr-bar").count() == 8
    fine = slot.locator(".fp")
    expect(fine.locator("h3")).to_have_text("The fine print, up front")
    expect(fine.locator(".fp-sample")).to_contain_text("Sample: this is a real hotel’s recorded data")
    assert fine.locator(".fp-ct").all_inner_texts() == ["Costs not in the price", "Policies that bite", "Fits your family?", "Getting there and around", "What guests complain about"]
    expect(fine.locator(".fp-usual")).to_contain_text("The usual: ")
    expect(fine.locator(".fp-c.fp-going .av-card")).to_contain_text("See it from above")      # F-284's card lives here now
    fine.scroll_into_view_if_needed()
    shot(page, f"fine-{viewport['width']}")


@pytest.mark.parametrize("viewport", BOTH, ids=IDS)
def test_the_rows_that_depend_on_the_room_and_flight_follow_the_choice(matrix, sample, viewport):  # noqa: F811
    page, drawer, slot = opened(matrix, viewport)
    fine = slot.locator(".fp")
    due = fine.locator('[data-live="due"]')
    expect(due).to_contain_text("Paid at the hotel: $160")
    expect(due).to_have_class("fp-i is-hu")
    expect(due.locator(".fp-flag")).to_have_text("Heads up")
    real = fine.locator('[data-live="real"]')
    expect(real).to_be_visible()
    expect(real).to_contain_text("What the stay really costs")
    expect(real.locator('[data-real="words"]')).to_contain_text("plus $160 paid at the hotel.")
    expect(fine.locator('[data-live="board"]')).to_contain_text("Breakfast is included in this room’s price")
    expect(fine.locator('[data-live="refund"]')).to_contain_text("Refundable")
    expect(fine.locator('[data-live="landing"]')).to_contain_text("Your flight lands 9:32 AM, 6 h 28 min before check-in")      # the stand's flight lands 9:32 AM, the hotel opens at 4:00 PM
    expect(fine.locator('[data-live="landing"] .fp-flag')).to_have_text("Heads up")
    expect(fine.locator('[data-live="drive"]')).to_contain_text("25 min from the airport")
    before = fine.locator(".fp-count").inner_text()
    assert before.endswith("things to know")
    # a room the offer calls non-refundable and with nothing paid at the hotel: the same rows say so
    page.evaluate("""() => { const b = document.querySelector('.dr-rooms:not([hidden]) .dr-opt[aria-checked="true"]'); b.dataset.refund = ''; b.dataset.due = '0'; b.dataset.board = 'room only';
                          document.querySelector('.dr').dispatchEvent(new CustomEvent('dr:changed', { bubbles: true })); }""")
    expect(fine.locator('[data-live="refund"]')).to_contain_text("Non-refundable")
    expect(fine.locator('[data-live="refund"] .fp-flag')).to_have_text("Heads up")
    expect(fine.locator('[data-live="due"]')).to_contain_text("Fees paid at the hotel: none listed")
    expect(fine.locator('[data-live="real"]')).to_be_hidden()
    expect(fine.locator('[data-live="board"]')).to_contain_text("Breakfast is not in this room’s price")


@pytest.mark.parametrize("viewport", BOTH, ids=IDS)
def test_the_pins_arrive_when_the_section_is_seen_with_their_heads_up_and_distance(matrix, sample, viewport):  # noqa: F811
    page, drawer, slot = opened(matrix, viewport)
    going = slot.locator(".fp-going")
    going.scroll_into_view_if_needed()
    hu = going.locator(".fp-i.is-hu")
    expect(hu.first).to_contain_text("Between two flight paths")
    expect(hu.first.locator(".fp-flag")).to_have_text("Heads up")
    expect(hu.first).to_contain_text("Landing planes pass 670 m to one side")
    pins = going.locator(".fp-pin")
    expect(pins.first).to_contain_text("Runway 07L/25R")
    expect(pins.first).to_contain_text("11 min walk")
    expect(pins.first).to_contain_text("720 m")
    expect(going.locator(".fp-i.is-no").filter(has_text="No beach or shore within 2 km")).to_be_visible()      # an absence is said as what the map holds


def drawer_of(page):
    return page.locator(".rv")


@pytest.mark.parametrize("viewport", BOTH, ids=IDS)
def test_the_score_opens_the_drawer_with_every_review_and_escape_gives_the_focus_back(matrix, sample, viewport):  # noqa: F811
    page, drawer, slot = opened(matrix, viewport)
    score = slot.locator(".dr-scorebtn")
    score.focus()
    page.keyboard.press("Enter")
    rv = drawer_of(page)
    expect(rv).to_be_visible()
    expect(rv).to_have_attribute("role", "dialog")
    expect(rv.locator(".rv-title")).to_have_text("What guests said")
    assert rv.locator(".rv-item:visible").count() == 100
    dates = rv.locator(".rv-item .dr-rh small").all_inner_texts()
    days = [d.rsplit(" · ", 1)[-1] for d in dates]
    assert days == sorted(days, reverse=True)
    box = rv.bounding_box()
    if viewport is PHONE:
        assert box["width"] == 390 and box["y"] > 20 and box["y"] + box["height"] >= 844 - 1      # a full-height sheet under a small gap
    else:
        assert box["x"] + box["width"] > 1440 - 20 and box["width"] < 520 and box["height"] > 700      # a side sheet on the right
    shot(page, f"drawer-{viewport['width']}")
    assert page.evaluate("() => document.activeElement.classList.contains('rv-x')")
    page.keyboard.press("Escape")
    expect(rv).to_be_hidden()
    assert page.evaluate("() => document.activeElement.classList.contains('dr-scorebtn')")


@pytest.mark.parametrize("viewport", BOTH, ids=IDS)
def test_the_chips_filter_by_traveller_type_and_a_complaint_opens_only_its_reviews(matrix, sample, viewport):  # noqa: F811
    page, drawer, slot = opened(matrix, viewport)
    slot.locator(".tr-read").first.click()      # from the strip
    rv = drawer_of(page)
    expect(rv).to_be_visible()
    assert rv.locator(".rv-chip").all_inner_texts() == ["All 100", "Couple 51", "Solo 28", "Group 13", "Family 8"]
    rv.locator(".rv-chip", has_text="Family 8").click()
    assert rv.locator(".rv-item:visible").count() == 8
    assert all(t.startswith("Family") for t in rv.locator(".rv-item:visible .dr-rh small").all_inner_texts())
    expect(rv.locator(".rv-chip", has_text="Family 8")).to_have_attribute("aria-pressed", "true")
    rv.locator(".rv-x").click()
    expect(rv).to_be_hidden()
    assert page.evaluate("() => document.activeElement.classList.contains('tr-read')")
    gripe = slot.locator(".fp-read").first
    gripe.scroll_into_view_if_needed()
    n = int(re.search(r"Read (\d+) review", gripe.inner_text())[1])
    gripe.click()
    expect(rv).to_be_visible()
    expect(rv.locator(".rv-filter")).to_contain_text(re.compile(rf"{n} reviews mention [a-z]+( or [a-z]+)* · about “Pricey \(breakfast, taxes, parking, lobby shop\)”"))      # what they share, never "say"
    shown = rv.locator(".rv-item:visible")
    assert shown.count() == n
    assert all(any(w in t.lower() for w in ("breakfast", "tax", "parking", "lobby", "shop", "pricey")) for t in shown.locator(".dr-rc").all_inner_texts())      # each mentions one of its words in its cons
    shot(page, f"gripe-{viewport['width']}")
    rv.locator(".rv-all").click()
    assert rv.locator(".rv-item:visible").count() == 100
    page.keyboard.press("Escape")
    expect(rv).to_be_hidden()
    assert page.evaluate("() => document.activeElement.classList.contains('fp-read')")


@pytest.mark.parametrize("viewport", BOTH, ids=IDS)
def test_the_square_keeps_only_a_compact_dashboard_with_one_way_in(matrix, sample, viewport):  # noqa: F811
    page, drawer, slot = opened(matrix, viewport)
    dash = slot.locator(".dr-dash")
    expect(dash.locator(".tr-w")).to_have_count(1)
    assert dash.locator(".dr-cat").count() == 8 and dash.locator(".dr-cat p").count() == 0      # short bars with their numbers, no paragraphs
    expect(dash.locator(".dr-cat .dr-cv").first).to_have_text("8")
    assert slot.locator(".dr-top .dr-pc, .dr-top .dr-rev, .dr-reviews").count() == 0      # nothing long on the square: it is all in the drawer (hidden in the page until opened)
    way = dash.locator(".tr-read")
    expect(way).to_have_text("Read the reviews")
    assert way.bounding_box()["height"] >= 48
    way.click()
    rv = drawer_of(page)
    expect(rv).to_be_visible()
    expect(rv.locator(".rv-ai")).to_contain_text("Summary written by AI from the guest reviews")
    expect(rv.locator(".rv-ai")).to_contain_text("Frequent comments that the hotel is pricey")      # a category's paragraph
    expect(rv.locator(".rv-ai .dr-pros li").first).to_be_visible()
    expect(rv.locator(".rv-ai .dr-cons li").first).to_be_visible()
    page.keyboard.press("Escape")
    expect(rv).to_be_hidden()
    assert page.evaluate("() => document.activeElement.classList.contains('tr-read')")


def mentions(rv, word):
    return [t for t in rv.locator(".rv-item:visible").all_inner_texts() if word in t.lower()]


@pytest.mark.parametrize("viewport", BOTH, ids=IDS)
def test_ask_the_reviews_filters_live_as_you_type_and_says_how_many_mention_it(matrix, sample, viewport):  # noqa: F811
    page, drawer, slot = opened(matrix, viewport)
    slot.locator(".dr-scorebtn").click()
    rv = drawer_of(page)
    ask = rv.locator(".rv-q")
    assert rv.locator(".rv-ask").bounding_box()["height"] >= 48 and ask.get_attribute("aria-label") == "Ask the reviews"
    assert rv.locator(".rv-ask").bounding_box()["y"] < rv.locator(".rv-chips").bounding_box()["y"]      # at the drawer's top, above the chips
    asked = []
    page.on("request", lambda r: asked.append(r.url))
    ask.press_sequentially("park", delay=20)
    n = rv.locator(".rv-item:visible").count()
    assert 0 < n < 100 and len(mentions(rv, "park")) == n
    expect(rv.locator(".rv-found")).to_have_text(f"park · {n} of 100 reviews mention it")
    expect(rv.locator(".rv-ai")).to_be_hidden()
    shot(page, f"ask-{viewport['width']}")
    ask.fill("PARKING  fee")      # every word must be in the review, any case
    m = rv.locator(".rv-item:visible").count()
    assert m <= n and len(mentions(rv, "fee")) == m
    ask.fill("")
    assert rv.locator(".rv-item:visible").count() == 100
    expect(rv.locator(".rv-found")).to_be_hidden()
    expect(rv.locator(".rv-ai")).to_be_visible()
    ask.fill("zzzzqq")
    expect(rv.locator(".rv-found")).to_have_text("zzzzqq · 0 of 100 reviews mention it")
    assert [u for u in asked if "/plan/matrix" in u or "/data/" in u] == []      # client side only: no network


@pytest.mark.parametrize("viewport", BOTH, ids=IDS)
def test_the_search_combines_with_the_traveller_chips_and_a_complaint(matrix, sample, viewport):  # noqa: F811
    page, drawer, slot = opened(matrix, viewport)
    slot.locator(".dr-scorebtn").click()
    rv = drawer_of(page)
    rv.locator(".rv-ask .rv-q").fill("the")
    all_n = rv.locator(".rv-item:visible").count()
    rv.locator(".rv-chip", has_text="Family 8").click()
    n = rv.locator(".rv-item:visible").count()
    assert 0 < n <= 8 and n < all_n
    assert all(t.startswith("Family") for t in rv.locator(".rv-item:visible .dr-rh small").all_inner_texts())
    expect(rv.locator(".rv-found")).to_have_text(f"the · {n} of 8 reviews mention it")      # out of the reviews the chip leaves
    rv.locator(".rv-chip", has_text="All 100").click()
    rv.locator(".rv-q").fill("")
    rv.locator(".rv-x").click()
    gripe = slot.locator(".fp-read").first
    gripe.scroll_into_view_if_needed()
    gripe.click()
    k = rv.locator(".rv-item:visible").count()
    assert rv.locator(".rv-q").input_value() == ""      # opening clears a search left behind
    rv.locator(".rv-q").fill("breakfast")
    j = rv.locator(".rv-item:visible").count()
    assert j <= k and all("breakfast" in t.lower() for t in rv.locator(".rv-item:visible").all_inner_texts())
    expect(rv.locator(".rv-filter")).to_be_visible()
    rv.locator(".rv-all").click()
    assert rv.locator(".rv-item:visible").count() == 100 and rv.locator(".rv-q").input_value() == ""


@pytest.mark.parametrize("viewport", BOTH, ids=IDS)
def test_the_focus_trap_includes_the_search_box_and_escape_still_closes(matrix, sample, viewport):  # noqa: F811
    page, drawer, slot = opened(matrix, viewport)
    slot.locator(".dr-scorebtn").click()
    rv = drawer_of(page)
    assert page.evaluate("() => document.activeElement.classList.contains('rv-x')")
    page.keyboard.press("Tab")
    assert page.evaluate("() => document.activeElement.classList.contains('rv-q')")
    for _ in range(12):
        page.keyboard.press("Tab")
        assert page.evaluate("() => !!document.activeElement.closest('.rv')")      # never leaves the drawer
    page.keyboard.press("Shift+Tab")
    assert page.evaluate("() => !!document.activeElement.closest('.rv')")
    rv.locator(".rv-q").fill("park")
    page.keyboard.press("Escape")
    expect(rv).to_be_hidden()
    assert page.evaluate("() => document.activeElement.classList.contains('dr-scorebtn')")


@pytest.mark.parametrize("viewport", BOTH, ids=IDS)
def test_the_heads_up_line_has_a_chip_for_each_flagged_row_and_each_opens_its_row(matrix, sample, viewport):  # noqa: F811
    page, drawer, slot = opened(matrix, viewport)
    line = slot.locator("[data-hu]")
    expect(line).to_be_visible()
    slot.locator(".fp-going .fp-i.is-hu").first.wait_for()      # the pins have come
    flagged = slot.locator(".fp .fp-i.is-hu")
    texts = [t.replace("Heads up", "").strip() for t in flagged.locator(".fp-t").evaluate_all("els => els.map(e => e.textContent)")]
    chips = line.locator(".hu-chip")
    assert chips.all_inner_texts() == texts and len(texts) >= 3      # the room's fees, the refund or flight rows, the pins: only what the fine print flags
    assert any("Paid at the hotel: $160" in t for t in texts) and any("flight paths" in t for t in texts)
    assert line.bounding_box()["y"] < slot.locator(".dr-dash").bounding_box()["y"] + 1      # above the dashboard
    assert all(c.bounding_box()["height"] >= 48 for c in chips.all())
    shot(page, f"heads-{viewport['width']}")
    last = chips.last
    last.click()
    row = flagged.last
    expect(row).to_have_class(re.compile(r"\bis-hit\b"))
    box = row.bounding_box()
    vp = page.viewport_size
    assert 0 <= box["y"] and box["y"] + box["height"] <= vp["height"]      # scrolled into view
    page.wait_for_function("() => !document.querySelector('.fp-i.is-hit')", timeout=4000)      # the highlight is brief
    chips.first.click()
    expect(flagged.first).to_have_class(re.compile(r"\bis-hit\b"))


def test_without_a_flagged_row_there_is_no_heads_up_line(matrix, sample):  # noqa: F811
    page, drawer, slot = opened(matrix, DESKTOP)
    slot.locator(".fp-going .fp-i.is-hu").first.wait_for()
    page.evaluate("""() => { const b = document.querySelector('.dr-rooms:not([hidden]) .dr-opt[aria-checked="true"]'); b.dataset.refund = '1'; b.dataset.due = '0';
        document.querySelectorAll('.fp-going .fp-i.is-hu').forEach(e => e.classList.remove('is-hu'));
        document.querySelector('.dr-fly .dr-opt[aria-checked="true"]').dataset.land = '5:00 PM';
        document.querySelector('.dr').dispatchEvent(new CustomEvent('dr:changed', { bubbles: true })); }""")
    expect(slot.locator("[data-hu]")).to_be_hidden()
    assert slot.locator(".hu-chip").count() == 0


def test_with_reduced_motion_the_highlight_does_not_animate(matrix, sample):  # noqa: F811
    page, drawer, slot = opened(matrix, DESKTOP)      # reduced motion is the fixture's default
    slot.locator(".hu-chip").first.click()
    row = slot.locator(".fp-i.is-hit")
    expect(row).to_have_count(1)
    assert row.evaluate("el => el.getAnimations().length") == 0 and row.evaluate("el => getComputedStyle(el).transitionDuration") == "0s"


def test_with_reduced_motion_the_drawer_simply_appears_and_goes(matrix, sample):  # noqa: F811
    page, drawer, slot = opened(matrix, DESKTOP)      # the matrix fixture's default is reduced motion
    slot.locator(".dr-scorebtn").click()
    rv = drawer_of(page)
    expect(rv).to_be_visible()
    assert rv.evaluate("el => getComputedStyle(el).opacity") == "1" and not rv.evaluate("el => el.getAnimations().length")
    assert rv.evaluate("el => getComputedStyle(el).transitionDuration") == "0s" and rv.locator(".rv-chip").first.evaluate("el => getComputedStyle(el).transitionDuration") == "0s"
    page.keyboard.press("Escape")
    expect(rv).to_be_hidden()


def test_with_motion_on_the_drawer_opens_and_folds_back(matrix, sample):  # noqa: F811
    page, drawer, slot = opened(matrix, PHONE, motion=True)
    slot.locator(".dr-scorebtn").click()
    rv = drawer_of(page)
    expect(rv).to_be_visible()
    page.wait_for_function("() => !document.querySelector('.rv').getAnimations().length", timeout=4000)
    page.keyboard.press("Escape")
    expect(rv).to_be_hidden()
    assert page.evaluate("() => document.body.classList.contains('rv-open')") is False


# ---- every word reads (WCAG AA, 4.5:1) in both modes, on the fine print's own tints, the Heads up flag, the real-cost box and the drawer ----

PAINT_JS = """
sel => {
  const parse = c => { const m = c.match(/[\\d.]+/g).map(Number), k = c.startsWith('color(') ? 255 : 1; return { r: m[0] * k, g: m[1] * k, b: m[2] * k, a: m.length > 3 ? m[3] : 1 }; };
  const over = (top, under) => ({ r: top.r * top.a + under.r * (1 - top.a), g: top.g * top.a + under.g * (1 - top.a), b: top.b * top.a + under.b * (1 - top.a), a: 1 });
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    if (!el.getClientRects().length) continue;
    let bg = { r: 255, g: 255, b: 255, a: 0 }, chain = [];
    for (let n = el; n; n = n.parentElement) chain.push(parse(getComputedStyle(n).backgroundColor));
    let base = { r: 255, g: 255, b: 255, a: 1 };
    for (const c of chain.reverse()) base = c.a ? over(c, base) : base;
    out.push({ text: el.textContent.trim().slice(0, 40), fg: parse(getComputedStyle(el).color), bg: base });
  }
  return out;
}
"""
READS = [".hu-k", ".hu-chip", ".dr-cn", ".dr-cv", ".fp-t", ".fp-n", ".fp-flag", ".fp-count", ".fp-sample", ".fp-rk", ".fp-rn", ".fp-rw", ".fp-read", ".fp-usual", ".fp-ct", ".fp-h h3", ".fp-h p", ".tr-read"]
DRAWER_READS = [".rv-found", ".rv-q", ".rv-ai .dr-sub", ".rv-ai .dr-fine", ".rv-cat p", ".rv-h", ".rv-title", ".rv-top small", ".rv-n", ".rv-chip", ".rv-filter", ".rv-all", ".rv-item .dr-rn", ".rv-item .dr-rh small", ".rv-item .dr-rp", ".rv-item .dr-rc"]


LARGE = (".fp-rn", ".rv-n")      # 24px and bolder: WCAG AA large text, 3:1


def luminance(c):
    f = lambda v: (v / 255 / 12.92) if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4      # noqa: E731
    return 0.2126 * f(c["r"]) + 0.7152 * f(c["g"]) + 0.0722 * f(c["b"])


def contrast(fg, bg):
    a, b = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("viewport", BOTH, ids=IDS)
def test_every_word_of_the_fine_print_and_the_drawer_reads_in_both_modes(matrix, sample, viewport, mode):  # noqa: F811
    from tests_browser.helpers import set_mode
    page = matrix(viewport, signed_in=True)
    set_mode(page, mode)
    open_square(page, viewport)
    page.locator(".dr-sampleslot .fp-going").scroll_into_view_if_needed()
    page.wait_for_selector(".fp-going .fp-pin")
    bad = []
    for sel in READS:
        for p in page.evaluate(PAINT_JS, ".dr-sampleslot " + sel):
            if contrast(p["fg"], p["bg"]) < (3 if sel in LARGE else 4.5):
                bad.append((sel, p["text"], round(contrast(p["fg"], p["bg"]), 2)))
    page.locator(".dr-sampleslot .fp-read").first.click()
    page.locator(".rv").wait_for(state="visible")
    for sel in DRAWER_READS:
        for p in page.evaluate(PAINT_JS, ".rv " + sel):
            if contrast(p["fg"], p["bg"]) < (3 if sel in LARGE else 4.5):
                bad.append((sel, p["text"], round(contrast(p["fg"], p["bg"]), 2)))
    assert not bad, bad
    shot(page, f"{mode}-{viewport['width']}")
