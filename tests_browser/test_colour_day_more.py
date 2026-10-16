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
    heading = page.locator(".cz-more-list .cz-menu-t")
    assert heading.evaluate("e => parseFloat(getComputedStyle(e).fontSize)") >= 12.99
    expect(heading).to_have_text(f"{len(ids)} more plans")
    rows.first.focus()
    page.keyboard.press("ArrowDown")
    assert page.evaluate("document.activeElement.classList.contains('cz-more-row') && document.activeElement !== document.querySelectorAll('.cz-more-row')[0]")      # the arrow keys move through the rows
    rows.first.click()
    menu = page.locator(".cz-menu:not(.cz-more-list)")
    expect(menu).to_be_visible()      # an editor gets the plan's hold menu: re-time, rename, move to another day, delete
    for name in ("Rename", "Move to day", "Later", "Delete"):
        expect(menu.get_by_role("menuitem", name=name).first).to_be_visible()
    assert titles[0] in menu.get_attribute("aria-label")


def test_a_viewer_opens_the_more_list_and_a_row_opens_the_card(signed_in, browser, base_url):
    import uuid
    owner = signed_in(PHONE, path="/trip/canvas?day=0")
    crowded(owner)
    mail = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
    assert owner.context.request.post(f"{base_url}/family/invite", form={"email": mail, "role": "viewer"}, max_redirects=0).status < 400
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce")
    try:
        ctx.set_default_timeout(9000)
        ctx.request.post(f"{base_url}/signin", form={"email": mail, "next": "/", "intent": "save"}, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/canvas?day=0")
        page.wait_for_selector("#cz-grid")
        assert page.locator("#cz").get_attribute("data-edit") is None      # a real viewer's page: nothing is editable
        card = page.locator(".cz-lanemore").first
        card.scroll_into_view_if_needed()
        card.click()
        rows = page.locator(".cz-more-list .cz-more-row")
        assert rows.count() >= 1
        title = rows.first.inner_text()
        rows.first.click()
        expect(page.locator(".cz-card")).to_be_visible()
        assert page.locator(".cz-menu:not(.cz-more-list)").count() == 0      # a viewer gets the card, not the hold menu
    finally:
        ctx.close()


COVERED = """() => {
  const cards = [...document.querySelectorAll('.cz-lanemore')].map(c => { const r = c.getBoundingClientRect(); return [r.top, r.bottom]; });
  return [...document.querySelectorAll('.cz-gb')].map(b => { const r = b.getBoundingClientRect(), drawn = !b.classList.contains('is-more');
    return {name: b.dataset.title, drawn, covered: cards.some(c => c[0] - 1 <= r.top && c[1] + 1 >= r.top)}; });
}"""

HOURS = """() => {
  const starts = [...document.querySelectorAll('.cz-g-start')].filter(s => getComputedStyle(s).display !== 'none').map(s => parseFloat(s.style.getPropertyValue('--s')));
  return [...document.querySelectorAll('.cz-g-hour')].filter(h => getComputedStyle(h).display === 'none').map(h => ({text: h.textContent, near: starts.some(y => { const d = parseFloat(h.style.getPropertyValue('--s')) - y; return d >= -30 && d <= 43; })}));
}"""


@BOTH
def test_a_planned_time_never_looks_free_and_an_hour_label_is_only_hidden_by_a_printed_one(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    crowded(page)
    for b in page.evaluate(COVERED):
        assert b["drawn"] or b["covered"], f"{b['name']} is neither drawn nor under a +N card"
    for h in page.evaluate(HOURS):
        assert h["near"], f"the {h['text']} label is hidden with no printed start beside it"
    ice = page.locator('.cz-gb[data-title="Ice cream"]')      # 4:00-4:45: its own time, so it is drawn unless it truly has no lane (beside the hotel's pill it has none)
    assert ice.count() == 1


@BOTH
def test_a_kind_filter_leaves_no_card_label_or_count_behind(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    crowded(page)
    assert page.locator(".cz-lanemore:visible").count() >= 1
    page.locator(".cz-kchip[data-k=hotel]").click()
    assert page.locator(".cz-lanemore:visible").count() == 0      # every plan behind the cards is filtered out: no card
    shot(page, f"crowd3-hotels-{viewport['width']}.png", full=False)
    shown = page.locator(".cz-g-start:visible").all_inner_texts()
    assert [t.replace("\n", " ") for t in shown] == ["3:00 PM"]      # only the hotel's start is left on the rail
    for h in page.evaluate(HOURS):
        assert h["near"], h
    page.locator(".cz-kchip[data-k=plan]").click()
    cards = page.locator(".cz-lanemore:visible")
    assert cards.count() >= 1
    for i in range(cards.count()):
        n = len([x for x in cards.nth(i).get_attribute("data-more").split()])
        expect(cards.nth(i)).to_have_text(f"+{n} more")      # plans only: nothing filtered out was behind them
    page.locator(".cz-kchip[data-k=all]").click()
    assert page.locator(".cz-g-start:visible").count() >= 5
    shot(page, f"crowd3-filter-{viewport['width']}.png", full=False)


