"""F-165: a draft plan saved by Enter, Tab or clicking away becomes the very block a reload draws (title, time, kind tile, rail label), with no draft markup left,
at 1440 (a real mouse), 1280 and 390 (a finger). The saved block is read off the page after the refresh and compared with the one drawn after a reload."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_colour_add_move import open_draft
from tests_browser.test_colour_day import day
from tests_browser.test_topbar import signed_in  # noqa: F401 - fixture

LAPTOP = {"width": 1280, "height": 800}
SIZES = pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP, PHONE], ids=["1440", "1280", "390"])

# the saved block as the page draws it: its markup without the scripts' transient classes, and the rail label that belongs to it
BLOCK = """(title) => {
  const b = [...document.querySelectorAll('#cz-grid .cz-gb')].find(e => e.dataset.title === title);
  if (!b) return null;
  const c = b.cloneNode(true);
  ['is-landing', 'is-selected', 'is-hit', 'is-on'].forEach(k => c.classList.remove(k));
  const rail = [...document.querySelectorAll('#cz-grid .cz-g-start')].filter(l => (l.dataset.for || '').split(' ').includes(b.dataset.act)).map(l => l.outerHTML);
  return { html: c.outerHTML.replace(/>\s+</g, '><'), rail, draft: document.querySelectorAll('.cz-gb.is-new, .cz-gb-kinds, .cz-gb-edit, .is-making').length,
           liveRail: document.querySelectorAll('#cz-grid .cz-g-start.is-live').length }; }"""


def settled(page, title):
    page.wait_for_function("(t) => [...document.querySelectorAll('#cz-grid .cz-gb[data-act]')].some(e => e.dataset.title === t)", arg=title)
    page.wait_for_timeout(1200)                        # (long past the slowed refresh)
    return page.evaluate(BLOCK, title)


def save_by(page, how):
    if how == "enter":
        page.keyboard.press("Enter")
    elif how == "tab":
        for _ in range(6):
            page.keyboard.press("Tab")
    elif how == "away":
        page.mouse.click(4, 4)
    else:                                              # on the grid's own empty time, where the pointerdown could start a second draft
        box = page.locator("#cz-grid .cz-g-plane").bounding_box()
        page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + 12)


@SIZES
@pytest.mark.parametrize("how", ["enter", "tab", "away", "grid"])
def test_a_saved_draft_becomes_the_block_a_reload_draws(signed_in, viewport, how, slow_server):
    page = day(signed_in, viewport)
    title = f"Settle {how}"
    open_draft(page, viewport, title)
    slow_server(r"/trip/canvas", 0.4)                  # a distant server: the refresh comes well after the save
    save_by(page, how)
    saved = settled(page, title)
    assert saved["draft"] == 0 and saved["liveRail"] == 0
    page.reload()
    page.wait_for_selector("#cz-grid .cz-gb[data-act]")
    fresh = page.evaluate(BLOCK, title)
    assert saved["html"] == fresh["html"]
    assert saved["rail"] == fresh["rail"] and saved["rail"]
