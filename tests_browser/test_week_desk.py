"""F-145: the desktop week in a real browser. From 1020px up the week is one column per day under the ink trip header (kind filters, Day | Week): a day-colour header, compact rows (time, a
title on at most two lines, a kind icon), plans with their step and message summary, a dashed Free day card with Say the plan, today outlined, Open the day at the foot. Clicking a row
opens that day with the plan selected; a trip longer than five days scrolls sideways inside the week area, never the page; 1440x900 and 1280x800 need no page scroll. 1000 (tablet) and 390
(phone) keep today's rows. A viewer's page has no Say the plan: tests/test_week_desk.py. Screenshots on request: F145_SHOTS=<folder>."""
import os
import re
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect

from gitaway import catalog, plantalk, tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_topbar import LAPTOP, TABLET, signed_in  # noqa: F401 - fixture

SAT_NOON = datetime(2026, 10, 17, 19, 40, tzinfo=timezone.utc)      # Saturday 12:40 PM in Los Angeles: day 1
NO_SCROLL = "[document.documentElement.scrollWidth <= document.documentElement.clientWidth, document.documentElement.scrollHeight <= document.documentElement.clientHeight, window.scrollY]"


def shot(page, name):
    if os.environ.get("F145_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F145_SHOTS"], name))


def plans():
    me = person("ari")
    a = cal.add_activity(me, day=1, start=19 * 60 + 30, end=21 * 60, title="Dinner at CityWalk", kind="food")
    plantalk.post_message(me, a.id, "", "Book the 7:30 table")
    plantalk.post_message(me, a.id, "", "Done, for six")
    cal.add_activity(me, day=2, start=10 * 60, end=11 * 60, title="Will Rogers beach with the boogie boards", kind="outdoors")
    return a


def long_trip(browser, base_url, viewport=LAPTOP, motion="reduce"):
    ctx = browser.new_context(viewport=viewport, reduced_motion=motion)
    ctx.set_default_timeout(5000)
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
    ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1", "d": "2026-10-23", "r": "2026-11-01", "a": "2", "k": "4,7"}, max_redirects=0)
    return ctx, ctx.new_page()


@pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])
def test_five_columns_under_the_ink_header_and_the_page_does_not_scroll(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas")
    plans()
    page.reload()
    cols = page.locator(".cz-wcol")
    expect(cols).to_have_count(5)
    expect(page.locator("#cz-week")).to_be_hidden()
    assert page.evaluate(NO_SCROLL) == [True, True, 0]
    boxes = [cols.nth(i).bounding_box() for i in range(5)]
    assert all(boxes[i]["x"] + boxes[i]["width"] <= boxes[i + 1]["x"] + 0.5 for i in range(4))      # side by side, none over another
    assert abs(boxes[0]["y"] - boxes[4]["y"]) < 1 and boxes[4]["x"] + boxes[4]["width"] <= viewport["width"]
    assert max(b["width"] for b in boxes) - min(b["width"] for b in boxes) < 1
    wk = page.locator("#cz-wk").bounding_box()
    assert wk["y"] + wk["height"] <= viewport["height"]
    head = page.locator(".cz-view[data-level=week]").evaluate("""v => { const k = document.querySelector('.cz-kinds').getBoundingClientRect(), s = document.querySelector('#cz-z-week').getBoundingClientRect(),
        h = document.querySelector('#cz-title').getBoundingClientRect(), w = document.querySelector('#cz-wk').getBoundingClientRect();
        return { bg: getComputedStyle(v, '::before').backgroundColor, kinds: k.bottom <= w.top && k.top >= 0, sw: s.bottom <= w.top, title: h.bottom <= w.top, kindsAfterTitle: k.left > h.right } }""")
    assert head["bg"] == "rgb(30, 26, 46)" and head["kinds"] and head["sw"] and head["title"] and head["kindsAfterTitle"]      # the ink header holds the title, the filters and Day | Week
    expect(page.locator(".cz-kinds")).to_be_visible()
    expect(page.locator("#cz-z-week")).to_be_visible()
    shot(page, f"week-{viewport['width']}.png")


def test_each_day_has_its_colour_header_with_a_deep_ink_number(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas")
    got = page.evaluate("[...document.querySelectorAll('.cz-wcol')].map(c => [getComputedStyle(c.querySelector('.cz-wh')).backgroundColor, getComputedStyle(c.querySelector('.cz-wh-num')).color])")
    want = page.evaluate("""['sun','mint','grape','sky','bubble'].map(n => { const g = v => { const d = document.createElement('i'); d.style.color = 'var(--' + v + ')'; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; }; return [g(n + '-tint'), g(n + '-ink')]; })""")
    assert got == want


@pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])
def test_rows_are_time_title_and_icon_and_a_title_wraps_to_two_lines_without_ellipsis(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas")
    plans()
    page.reload()
    assert page.locator(".cz-wcol[data-day='0'] .cz-wi").count() >= 2
    m = page.evaluate("""() => [...document.querySelectorAll('.cz-wi')].map(r => { const t = r.querySelector('.cz-wi-t'), cs = getComputedStyle(t), lh = parseFloat(cs.lineHeight);
        return { lines: Math.round(t.getBoundingClientRect().height / lh), ellipsis: cs.textOverflow, clipped: t.scrollWidth > t.clientWidth + 1, ico: !!r.querySelector('.cz-wi-ico svg'), time: !!r.querySelector('.cz-wi-time').textContent.trim(), title: t.textContent }; })""")
    assert all(x["ico"] and x["time"] and x["ellipsis"] == "clip" and not x["clipped"] for x in m)
    assert all(x["lines"] <= 2 for x in m), [(x["title"], x["lines"]) for x in m]      # a title (40 characters at most) is two lines or fewer, and whole
    assert page.evaluate(NO_SCROLL) == [True, True, 0]


def test_plans_show_messages_and_a_free_day_is_a_dashed_card(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas")
    plans()
    page.reload()
    expect(page.locator(".cz-wi", has_text="Dinner at CityWalk")).to_contain_text("2 messages")
    free = page.locator(".cz-wcol[data-day='3'] .cz-wfree")
    expect(free).to_contain_text("Free day")
    expect(free).to_contain_text("Nothing planned yet")
    assert page.evaluate("getComputedStyle(document.querySelector('.cz-wfree')).borderTopStyle") == "dashed"
    expect(free.get_by_role("link", name="Say the plan")).to_be_visible()


def test_today_is_outlined(signed_in, monkeypatch):
    monkeypatch.setattr(catalog, "now_utc", lambda: SAT_NOON)
    monkeypatch.setattr(catalog, "today", lambda: SAT_NOON.astimezone(catalog.TZ).date())
    page = signed_in(DESKTOP, path="/trip/canvas")
    sh = page.evaluate("[...document.querySelectorAll('.cz-wcol')].map(c => getComputedStyle(c).boxShadow)")
    assert [bool(re.search(r"rgb\(30, 26, 46\) 0px 0px 0px 2(\.\d+)?px", x)) for x in sh] == [False, True, False, False, False], sh
    expect(page.locator(".cz-wcol.is-today")).to_contain_text("Today")


def test_clicking_a_plan_row_opens_that_day_with_the_plan_and_open_the_day_opens_the_day(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas")
    a = plans()
    page.reload()
    page.evaluate("window.__marker = 1")
    page.locator(".cz-wi", has_text="Dinner at CityWalk").click()
    page.wait_for_selector(".cz-view[data-level=day][data-day='1']")
    assert f"day=1&plan={a.id}" in page.url and page.evaluate("window.__marker") == 1      # the zoom, not a page load
    expect(page.locator("#cz-title")).to_have_text("Saturday")
    page.locator("#cz-z-week").click()
    page.wait_for_selector(".cz-view[data-level=week]")
    page.locator(".cz-wcol[data-day='2'] .cz-wopen").click()
    page.wait_for_selector(".cz-view[data-level=day][data-day='2']")
    assert "day=2" in page.url and "plan=" not in page.url
    expect(page.locator("#cz-title")).to_have_text("Sunday")
    page.go_back()
    page.wait_for_selector(".cz-view[data-level=week]")
    expect(page.locator(".cz-wcol")).to_have_count(5)


def test_a_booking_row_opens_its_sheet_and_say_the_plan_goes_to_ask(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas")
    page.locator(".cz-wcol[data-day='0'] .cz-wi.is-booked").first.click()
    page.wait_for_selector(".cz-sheet")
    assert "booked=" in page.url
    page.goto(page.url.split("/trip/canvas")[0] + "/trip/canvas")
    page.locator(".cz-wcol[data-day='3'] .cz-wsay").click()
    page.wait_for_selector(".cz-view[data-level=day][data-day='3']")          # F-142: the day opens with the Ask panel in it
    expect(page.locator("#cz-dock[data-mode=ask] #ak-form")).to_be_visible()


def test_the_kind_filters_in_the_header_filter_the_columns(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas")
    plans()
    page.reload()
    page.locator(".cz-kchip", has_text="Hotels").click()
    expect(page.locator(".cz-wi.is-plan:visible")).to_have_count(0)
    expect(page.locator(".cz-wcol[data-day='1'] .cz-wnone")).to_have_text("Nothing for hotels")
    page.locator(".cz-kchip", has_text="Plans").click()
    expect(page.locator(".cz-wi:visible", has_text="Dinner at CityWalk")).to_have_count(1)
    expect(page.locator(".cz-wi.is-booked:visible")).to_have_count(0)
    page.locator(".cz-kchip", has_text="All").click()
    expect(page.locator(".cz-wi.is-booked:visible").first).to_be_visible()


def test_a_day_with_many_items_scrolls_inside_its_card(signed_in):
    page = signed_in(LAPTOP, path="/trip/canvas")
    me = person("ari")
    for h in range(8, 20):
        cal.add_activity(me, day=0, start=h * 60, end=h * 60 + 30, title=f"Stop number {h} on the long first day", kind="fun")
    page.reload()
    m = page.evaluate("""(() => { const l = document.querySelector('.cz-wcol[data-day="0"] .cz-wlist'), c = l.closest('.cz-wcol');
        return { scrolls: l.scrollHeight > l.clientHeight, inside: c.getBoundingClientRect().bottom <= innerHeight, page: document.documentElement.scrollHeight <= document.documentElement.clientHeight } })()""")
    assert m == {"scrolls": True, "inside": True, "page": True}
    shot(page, "week-many-1280.png")


def test_a_trip_longer_than_five_days_scrolls_sideways_inside_the_week_area(browser, base_url):
    ctx, page = long_trip(browser, base_url)
    page.goto(f"{base_url}/trip/canvas")
    expect(page.locator(".cz-wcol")).to_have_count(10)
    m = page.evaluate("""(() => { const w = document.querySelector('#cz-wk'), c = [...document.querySelectorAll('.cz-wcol')].map(x => x.getBoundingClientRect()), cs = getComputedStyle(w);
        const inner = w.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
        return { grows: w.scrollWidth > w.clientWidth + 10, overflowX: cs.overflowX, fifth: Math.abs(c[0].width - (inner - 4 * parseFloat(cs.columnGap)) / 5) < 2,
                 page: document.documentElement.scrollWidth <= document.documentElement.clientWidth, pageH: document.documentElement.scrollHeight <= document.documentElement.clientHeight } })()""")
    assert m == {"grows": True, "overflowX": "auto", "fifth": True, "page": True, "pageH": True}
    shot(page, "week-10-days-1280-start.png")
    page.locator("#cz-wk").evaluate("w => { w.scrollLeft = w.scrollWidth }")
    assert page.evaluate("window.scrollX") == 0 and page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    shot(page, "week-10-days-1280-end.png")
    page.locator(".cz-wcol[data-day='9'] .cz-wopen").click()
    page.wait_for_selector(".cz-view[data-level=day][data-day='9']")
    ctx.close()


def test_week_to_day_zooms_about_the_clicked_row(browser, base_url):
    ctx, page = long_trip(browser, base_url, viewport=DESKTOP, motion="no-preference")
    cal.add_activity(person("ari"), day=1, start=10 * 60, end=11 * 60, title="Pier walk", kind="fun")
    page.goto(f"{base_url}/trip/canvas")

    row = page.locator(".cz-wcol[data-day='1'] .cz-wi").first
    box = row.bounding_box()
    row.click()
    page.wait_for_selector(".cz-view[data-level=day][data-day='1']")
    ox, oy = page.evaluate("[parseFloat(document.documentElement.style.getPropertyValue('--cz-ox')), parseFloat(document.documentElement.style.getPropertyValue('--cz-oy'))]")
    assert abs(ox - (box["x"] + box["width"] / 2)) < 2 and abs(oy - (box["y"] + box["height"] / 2)) < 2
    ctx.close()


@pytest.mark.parametrize("viewport,name", [(TABLET, "1000"), (PHONE, "390")], ids=["tablet", "phone"])
def test_the_tablet_and_the_phone_keep_the_rows(signed_in, viewport, name):
    page = signed_in(viewport, path="/trip/canvas")
    expect(page.locator("#cz-wk")).to_be_hidden()
    expect(page.locator("#cz-week")).to_be_visible()
    expect(page.locator("#cz-week .cz-row")).to_have_count(5)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    shot(page, f"week-{name}.png")


HERO_SPY = """() => { window.__hero = []; const real = document.startViewTransition.bind(document);
  const seen = (when) => [...document.querySelectorAll('[data-zk]')].filter(n => n.style.viewTransitionName === 'cz-hero').map(n => ({ when, zk: n.dataset.zk, tag: n.className.split(' ')[0], box: n.getClientRects().length > 0 }));
  document.startViewTransition = function (cb) { window.__hero.push(...seen('before'));
    return real(function () { const r = cb(); window.__hero.push(...seen('after')); return r; }); }; }"""


def test_the_visible_column_is_the_hero_going_in_and_coming_back(browser, base_url):
    ctx, page = long_trip(browser, base_url, viewport=DESKTOP, motion="no-preference")
    cal.add_activity(person("ari"), day=1, start=10 * 60, end=11 * 60, title="Pier walk", kind="fun")
    page.goto(f"{base_url}/trip/canvas")

    page.evaluate(HERO_SPY)
    page.locator(".cz-wcol[data-day='1'] .cz-wi").first.click()
    page.wait_for_selector(".cz-view[data-level=day][data-day='1']")
    page.wait_for_timeout(800)
    going = page.evaluate("window.__hero")
    assert {"when": "before", "zk": "day-1", "tag": "cz-wcol", "box": True} in going      # the column grows into the day header, not the hidden phone row
    assert any(x["when"] == "after" and x["tag"] == "cz-head" for x in going)
    page.evaluate("window.__hero = []")
    page.locator("#cz-z-week").click()
    page.wait_for_selector(".cz-view[data-level=week]")
    page.wait_for_timeout(800)
    back = page.evaluate("window.__hero")
    assert any(x["when"] == "before" and x["tag"] == "cz-head" and x["zk"] == "day-1"  for x in back)      # the header folds into the column
    assert {"when": "after", "zk": "day-1", "tag": "cz-wcol", "box": True} in back
    assert not any(x["tag"] == "cz-row" for x in going + back)
    ctx.close()
