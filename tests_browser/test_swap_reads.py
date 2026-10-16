"""F-173: the hooks that run on every level swap (CZ.onSwap) measure first and write after. A hook that reads a box, writes a class, then reads the next box makes the browser lay the page out
again for every title (a read-after-write thrash: ~40 ms of the Week -> Day swap on a slow phone). The title-cut hooks (day_more.js on the day, canvas_filters.js on the week) are the ones that did it.
The test lets the real hooks run on the open level and lists, in order, each measuring of a title (R) and each write of its `is-cut` mark (W): all the R come before any W."""
import pytest

from tests_browser.helpers import PHONE
from tests_browser.test_day_grid import open_day, plan, settle  # noqa: F401
from tests_browser.test_trip_canvas import canvas_page, level, model  # noqa: F401 - fixtures

LOG = """() => {
  const log = [];
  const g = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollHeight');
  Object.defineProperty(Element.prototype, 'scrollHeight', { get() { if (/(^| )(cz-gb-t|cz-wi-t|cz-wr-t)( |$)/.test(this.className)) log.push('R'); return g.get.call(this); }, configurable: true });
  const t = DOMTokenList.prototype.toggle;
  DOMTokenList.prototype.toggle = function (name) { if (name === 'is-cut') log.push('W'); return t.apply(this, arguments); };
  CZ.onSwap.forEach((f) => f());
  DOMTokenList.prototype.toggle = t;
  delete Element.prototype.scrollHeight;
  Object.defineProperty(Element.prototype, 'scrollHeight', g);
  return log.join('');
}"""


@pytest.fixture
def day(canvas_page):
    page = canvas_page(viewport=PHONE)
    plan("Lunch", 12 * 60, 13 * 60)
    plan("Dinner", 18 * 60, 19 * 60 + 30)
    open_day(page)
    return page


def reads_then_writes(log):
    return log.count("R") >= 2 and log == "R" * log.count("R") + "W" * log.count("W")


def test_the_day_measures_every_title_before_it_marks_any(day):
    log = day.evaluate(LOG)
    assert reads_then_writes(log), log


def test_the_week_measures_every_title_before_it_marks_any(day):
    day.locator(".cz-head .cz-back").click()
    day.wait_for_selector(".cz-view[data-level=week]")
    settle(day)
    log = day.evaluate(LOG)
    assert reads_then_writes(log), log
