"""F-160: a crowded phone or tablet day never splits a word, never puts more than three plans side by side, and shows "+N more" (with a list) for the rest. 390 and 800."""
import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests_browser.helpers import PHONE
from tests_browser.test_colour_day import CARD
from tests_browser.test_colour_day_phone import BOTH, crowded, shot
from tests_browser.test_topbar import TABLET, signed_in  # noqa: F401 - fixture


WORDS = """() => {
  const broken = [];
  document.querySelectorAll('.cz-gb:not(.is-more) .cz-gb-t, .cz-gb:not(.is-more) .cz-gb-when, .cz-gb:not(.is-more) .cz-gb-st, .cz-lanemore-t').forEach(el => {
    if (!el.getClientRects().length || getComputedStyle(el).display === 'none') return;
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      for (const m of n.textContent.matchAll(/\\S+/g)) {
        const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
        const lines = new Set([...r.getClientRects()].filter(q => q.width > 0).map(q => Math.round(q.top)));
        if (lines.size > 1) broken.push(m[0]);      // one word on two lines: it was split inside
      }
    }
  });
  return broken;
}"""

ACROSS = """() => {
  const boxes = [...document.querySelectorAll('.cz-gb:not(.is-new):not(.is-more), .cz-lanemore')].map(e => { const r = e.getBoundingClientRect(); return {t: r.top + scrollY, b: r.bottom + scrollY}; });
  return Math.max(...boxes.map(a => boxes.filter(b => b.t <= a.t + 1 && b.b > a.t + 1).length));      // the plans in one horizontal slice of the day, at each card's top
}"""


@BOTH
def test_no_word_in_a_card_is_split_and_at_most_three_plans_stand_side_by_side(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    crowded(page)
    assert page.evaluate(WORDS) == []
    assert page.evaluate(ACROSS) <= 3
    shot(page, f"crowd3-{viewport['width']}.png")
    page.evaluate("window.scrollTo(0, 330)")
    shot(page, f"crowd3-view-{viewport['width']}.png", full=False)


@BOTH
def test_the_more_card_counts_the_plans_behind_it_and_its_list_opens_each(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    crowded(page)
    card = page.locator(".cz-lanemore").first
    ids = card.get_attribute("data-more").split()
    expect(card).to_have_text(f"+{len(ids)} more")
    assert card.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).borderTopWidth, e.getBoundingClientRect().height >= 43.5]") == [CARD, "1px", True]      # white, a hairline, 44px
    for i in ids:
        assert page.locator(f'.cz-gb[data-act="{i}"]').evaluate("e => [e.classList.contains('is-more'), getComputedStyle(e).visibility]") == [True, "hidden"]
    titles = [page.locator(f'.cz-gb[data-act="{i}"]').get_attribute("data-title") for i in ids]
    starts = [page.locator(f'.cz-gb[data-act="{i}"]').get_attribute("data-s") for i in ids]
    card.scroll_into_view_if_needed()
    card.click()
    rows = page.locator(".cz-more-list .cz-more-row")
    expect(rows).to_have_count(len(ids))
    for title, start, text in zip(titles, starts, [t.replace("\n", " ") for t in rows.all_inner_texts()]):
        assert title in text and cal.fmt_time(int(start)) in text, (title, start, text)      # each row: its start time and its title
    assert all(r.bounding_box()["height"] >= 43.5 for r in rows.all())
    rows.first.click()
    expect(page.locator(".cz-card")).to_be_visible()      # the plan's own card
    assert titles[0] in page.locator(".cz-card").inner_text()


def test_a_viewer_can_open_the_more_list_too(browser, base_url):
    """The list changes nothing, so it needs no editing: it opens on a page whose stage says it is not editable (a viewer's)."""
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce")
    page = ctx.new_page()
    try:
        page.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
        page.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
        page.goto(f"{base_url}/trip/canvas?day=0")
        crowded(page)
        page.evaluate("document.querySelector('#cz').dataset.edit = '0'")
        page.locator(".cz-lanemore").first.scroll_into_view_if_needed()
        page.locator(".cz-lanemore").first.click()
        expect(page.locator(".cz-more-list")).to_be_visible()
    finally:
        ctx.close()
