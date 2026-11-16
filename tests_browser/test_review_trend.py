"""F-278 (D-871) in a real browser: the opened square's hotel shows the last hundred reviews as a strip of dots with the server's plain words, the cards in the reader's order and the source as
LiteAPI labels it, on a phone and a laptop, light and dark. The recorded answer is tests/fixtures/liteapi_hotel/reviews100.json. Shots: F278_SHOTS=1 for docs/report/f278-*.png."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import liteapi
from tests_browser.helpers import DESKTOP, PHONE, set_mode
from tests_browser.test_calm_palette import ratio, rgb
from tests_browser.test_matrix_v3 import FIX, hilton  # noqa: F401 (fixture)
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)

REPORT = Path(__file__).resolve().parent.parent / "docs" / "report"


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_last_hundred_reviews_show_as_a_trend_with_words_and_their_source(matrix, hilton, monkeypatch, viewport, scheme):  # noqa: F811
    inner, asked = liteapi.TRANSPORT, []

    def transport(url, h, b, t):
        if "/data/reviews" not in url:
            return inner(url, h, b, t)
        asked.append(url)
        return 200, "application/json", (FIX / "reviews100.json").read_bytes()
    monkeypatch.setattr(liteapi, "TRANSPORT", transport)
    page = matrix(viewport)
    set_mode(page, scheme)
    page.wait_for_selector(".mx-sq.is-ok")
    page.locator(".mx-lane[data-lane='sandiego'] .mx-sq.is-ok").nth(2).click()
    strip = page.locator("#mx-drawer .tr-strip")
    expect(strip).to_be_visible()
    assert len(asked) == 1 and asked[0].endswith("limit=100&getSentiment=true")      # one call, for a hundred
    expect(strip.locator(".tr-dots .tr-d")).to_have_count(100)
    expect(strip.locator(".tr-dots")).to_have_attribute("aria-label", "The last 100 reviews, oldest to newest: 53 good, 22 mixed, 25 poor")
    expect(strip.locator(".dr-sub")).to_have_text("How the last 100 reviews went · Oct 30 to Nov 16")
    expect(strip.locator(".tr-w").nth(0)).to_have_text("The last 10 averaged 9.1, above the hotel’s 7.6.")
    expect(strip.locator(".tr-w").nth(1)).to_have_text("The last 10 were all 8 or more.")
    expect(strip.locator(".tr-w").nth(2)).to_contain_text("on average, from")      # travellers like you (the party's own type)
    expect(page.locator("#mx-drawer .tr-src")).to_have_text("Reviews from Nuitée (LiteAPI)")
    # a shape as well as a colour: circle, diamond, triangle, and three colours that read on the card (3:1 for a mark)
    look = page.evaluate("""() => ['good', 'mixed', 'poor'].map(k => { const d = document.querySelector('#mx-drawer .tr-dots .tr-d.is-' + k), s = getComputedStyle(d);
        return {k, shape: s.clipPath + '|' + s.borderRadius, bg: s.backgroundColor}; })""")
    assert len({x["shape"] for x in look}) == 3
    card = page.evaluate("getComputedStyle(document.querySelector('#mx-drawer .tr-dots')).backgroundColor")
    page_bg = page.evaluate("getComputedStyle(document.documentElement).backgroundColor")
    for x in look:
        assert ratio(rgb(x["bg"]), rgb(card) if rgb(card) != [0, 0, 0] else rgb(page_bg)) >= 3, x      # WCAG non-text contrast: 3:1 for a mark
    assert page.locator("#mx-drawer .dr-rev").count() <= 12 and page.locator("#mx-drawer .dr-revs").first.locator(".dr-rev").count() == 4
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    if os.environ.get("F278_SHOTS"):
        strip.scroll_into_view_if_needed()
        page.wait_for_timeout(700)
        page.screenshot(path=str(REPORT / f"f278-{viewport['width']}-{scheme}.png"))
