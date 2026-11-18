"""F-279 (D-872): the trip sentence is its own search card on the matrix: a titled section set apart from the results (a tinted outline), the words in a field, the Try chips in a footer
band that runs to the card's edges, kept inside the page gutter and aligned with the grid. Phone and laptop, light and dark. Shots: F279_SHOTS=1 for docs/report/f279-*.png."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE, set_mode
from tests_browser.test_calm_palette import ratio, rgb
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)
from tests_browser.test_v2_targets import small

REPORT = Path(__file__).resolve().parent.parent / "docs" / "report"
JS = """() => { const q = s => document.querySelector(s), box = e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height, b: r.bottom, r: r.right}; }, st = e => getComputedStyle(e);
  const card = q('.v2-qcard'), field = q('.v2-qfield'), bandEl = q('.v2-sugs'), res = q('.mx-results') || q('#mx');
  return {card: box(card), field: box(field), band: box(bandEl), grid: box(res), vw: innerWidth, cardBg: st(card).backgroundColor, fieldBg: st(field).backgroundColor, bandBg: st(bandEl).backgroundColor,
          shadow: st(card).boxShadow, title: st(q('.v2-qtitle')).color, hint: st(q('.v2-hint')).color, titleText: q('.v2-qtitle').textContent, scrollX: document.documentElement.scrollWidth > innerWidth}; }"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_sentence_is_a_search_card_set_apart_inside_the_gutter(matrix, viewport, scheme):  # noqa: F811
    page = matrix(viewport, scheme=scheme)
    set_mode(page, scheme)
    expect(page.locator(".v2-qcard h2.v2-qtitle")).to_have_text("Your search")
    expect(page.locator(".v2-qcard")).to_have_attribute("aria-labelledby", "v2-qtitle")
    d = page.evaluate(JS)
    assert d["titleText"] == "Your search" and not d["scrollX"]
    c, band, field, grid = d["card"], d["band"], d["field"], d["grid"]
    assert c["x"] >= 15.5 and c["r"] <= d["vw"] - 15.5      # never touching the screen edge
    assert abs(c["x"] - grid["x"]) <= 1.5 and abs(c["r"] - grid["r"]) <= 1.5      # the grid's own width
    assert c["x"] <= field["x"] and field["r"] <= c["r"] and c["y"] < field["y"]      # the field sits inside
    assert band["x"] >= c["x"] - 0.5 and band["r"] <= c["r"] + 0.5 and abs(band["b"] - c["b"]) <= 1      # the band runs to the card's edges and ends where the card ends
    assert d["fieldBg"] != d["cardBg"] and d["bandBg"] != d["cardBg"]      # a field and a band of their own
    assert "rgb" in d["shadow"]      # the tinted outline, deeper than the results card's hairline
    assert ratio(rgb(d["title"]), rgb(d["cardBg"])) >= 4.5 and ratio(rgb(d["hint"]), rgb(d["cardBg"])) >= 4.5
    assert small(page, ".v2-qcard") == []      # every word, chip and control is a 48px target
    if os.environ.get("F279_SHOTS"):
        page.wait_for_timeout(700)
        page.screenshot(path=str(REPORT / f"f279-{viewport['width']}-{scheme}.png"))
