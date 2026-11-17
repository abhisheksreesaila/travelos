"""F-282 in a real browser: the hotel as a decision dashboard, the fine print up front and the review drawer. The showcase's opened square carries the sample dashboard (Hilton Los Angeles Airport's
recorded LiteAPI answers, labelled a sample); its pins are the recorded OpenStreetMap answer. What is proved here: the dashboard and the fine print are on the page at 1440 and 390; the rows that
depend on the room and flight follow the choice (fees paid at the hotel and what the stay really costs, refundability, the landing against check-in); the pins arrive with their Heads up; the review
drawer opens from the score, the strip and a complaint, filters by traveller type and by a complaint, is a side sheet on a laptop and a full-height sheet on a phone, and Escape and the close button
give the focus back. Set F282_SHOTS=1 for docs/report/f282-*.png."""
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
    expect(dash).to_contain_text("How the last 100 reviews went")
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
    n = int(gripe.inner_text().split("the ")[1].split(" ")[0])
    gripe.click()
    expect(rv).to_be_visible()
    expect(rv.locator(".rv-filter")).to_contain_text(f"{n} reviews say: “Pricey (breakfast, taxes, parking, lobby shop)”")
    shown = rv.locator(".rv-item:visible")
    assert shown.count() == n
    assert all(any(w in t.lower() for w in ("breakfast", "tax", "parking", "lobby", "shop", "pricey")) for t in shown.locator(".dr-rc").all_inner_texts())      # each says it in its cons
    shot(page, f"gripe-{viewport['width']}")
    rv.locator(".rv-all").click()
    assert rv.locator(".rv-item:visible").count() == 100
    page.keyboard.press("Escape")
    expect(rv).to_be_hidden()
    assert page.evaluate("() => document.activeElement.classList.contains('fp-read')")


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
READS = [".fp-t", ".fp-n", ".fp-flag", ".fp-count", ".fp-sample", ".fp-rk", ".fp-rn", ".fp-rw", ".fp-read", ".fp-usual", ".fp-ct", ".fp-h h3", ".fp-h p", ".tr-read"]
DRAWER_READS = [".rv-title", ".rv-top small", ".rv-n", ".rv-chip", ".rv-filter", ".rv-all", ".rv-item .dr-rn", ".rv-item .dr-rh small", ".rv-item .dr-rp", ".rv-item .dr-rc"]


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
