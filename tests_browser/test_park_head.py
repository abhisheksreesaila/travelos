"""F-150: on the laptop day a park block's sticky title and time stay clear of its part chips, at the top of the grid and while the grid card scrolls; the phone's sticky offset is unchanged."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_day_dock import root
from tests_browser.test_topbar import LAPTOP
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures

PARTS = ".cz-gb.is-park"


def rects(page):
    return page.evaluate("""() => { const b = document.querySelector('.cz-gb.is-park'); const r = e => { const x = e.getBoundingClientRect(); return [x.left, x.top, x.right, x.bottom]; };
      return {title: r(b.querySelector('.cz-gb-t')), when: r(b.querySelector('.cz-gb-when')), parts: [...b.querySelectorAll('.cz-gb-part')].map(r)}; }""")


def hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def assert_clear(page, scrolled=False):
    """Nothing overlaps. Once the grid has scrolled, chips pass beneath a pinned title, but only one flush at the card's top (nothing of the block shows above it)."""
    r = rects(page)
    card = page.locator(".cz-day-body").bounding_box()
    assert r["parts"] and not hit(r["title"], r["when"])
    if any(hit(r["title"], c) or hit(r["when"], c) for c in r["parts"]):
        assert scrolled and r["title"][1] - card["y"] <= 12, f"the title sits {r['title'][1] - card['y']:.0f}px below the card's top, over a part chip"


@pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])
def test_a_park_blocks_title_never_covers_its_parts(canvas_page, viewport):
    page = canvas_page(viewport=viewport, touch=False)
    page.goto(root(page) + "/trip/canvas?day=1")
    page.locator(PARTS).wait_for()
    body = page.locator(".cz-day-body")
    body.evaluate("e => { e.scrollTop = 0 }")
    assert_clear(page)
    for top in range(20, 420, 20):      # the grid card scrolls part-way into the block
        body.evaluate("(e, n) => { e.scrollTop = n }", top)
        assert_clear(page, scrolled=True)


def test_the_phones_sticky_title_keeps_its_offset(canvas_page):
    page = canvas_page(viewport=PHONE)
    page.goto(root(page) + "/trip/canvas?day=1")
    page.locator(PARTS).wait_for()
    assert page.evaluate("getComputedStyle(document.querySelector('.cz-gb.is-park .cz-gb-head')).top") == "64px"      # 4rem at the phone's 16px root; no safe-area inset here
