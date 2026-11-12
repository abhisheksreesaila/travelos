"""F-217 in a real browser: the trip grid at laptop (1440) and phone (390) width. A source of 8 flights and 10 stays stands in for a real one, so the grid is big
enough to scroll: the search folds into an island going down, the panel into a rail going sideways, and a tap opens either again. Looking at a square fills the
panel; the budget, Price or Ease and whose day change the squares on the page exactly as the server draws them. Set F217_SHOTS=1 for docs/report/f217-*.png."""
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
from playwright.sync_api import expect

from gitaway import gridsource
from gitaway.tripgrid import Flight, Stay
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
GRID = "/plan/grid?senior=Grandma&pet=dog"
TIMES = ((360, 1015, 1), (425, 930, 0), (500, 1115, 1), (580, 1090, 0), (690, 1195, 0), (795, 1305, 0), (945, 110, 1), (1370, 425, 0))


def big(trip):
    flights = tuple(Flight(f"bf{i}", f"Test Air {i}", "LAX", dep, arr, stops, 96_000 + i * 7_300, "1 stop" if stops else "Nonstop", overnight=arr < dep)
                    for i, (dep, arr, stops) in enumerate(TIMES, 1))
    stays = tuple(Stay(f"bh{i}", f"Test Stay {i}", "Town", "Two queens", 60_000 + i * 11_100, ("Pet friendly",) if i % 3 == 0 else ()) for i in range(1, 11))
    return gridsource.Found(flights, stays, lambda f, s: 25, lambda item: ((f"Book {item.name}", "/plan"),), True)


@pytest.fixture
def source(monkeypatch):
    monkeypatch.setattr(gridsource, "SOURCE", big)


@pytest.fixture
def grid(browser, base_url, source):
    contexts = []

    def grid(query="", viewport=DESKTOP, js=True, scheme="light"):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", java_script_enabled=js, color_scheme=scheme)
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.goto(base_url + GRID + query)
        if js:
            page.wait_for_selector("#tg-stage.is-live")
        return page

    yield grid
    for c in contexts:
        c.close()


def said(url):
    """An address as (path, its words in any order)."""
    parts = urlsplit(url)
    return parts.path, dict(parse_qsl(parts.query))


def squares(page):
    return page.eval_on_selector_all("[data-cell]", "els => els.map(e => [e.dataset.cell, e.className.replace(' is-look', ''), e.querySelector('.tg-sub').textContent, e.getAttribute('aria-label')])")


def scroll_to(page, x, y):
    page.evaluate("([x, y]) => document.getElementById('tg-scroll').scrollTo(x, y)", [x, y])
    page.wait_for_timeout(120)


def box(page, sel):
    return page.eval_on_selector(sel, "e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height, right: r.right, bottom: r.bottom}; }")


def test_the_grid_leads_and_nothing_overlaps_at_rest(grid):
    page = grid()
    assert page.get_attribute("#tg-stage", "data-top") == "open" and page.get_attribute("#tg-stage", "data-side") == "open"
    chrome, head, side, cell = box(page, "#tg-chrome"), box(page, ".tg-fh"), box(page, "#tg-side"), box(page, "[data-cell]")
    assert head["y"] >= chrome["bottom"] - 1                            # the first row of flights starts under the search, not behind it
    assert cell["x"] >= box(page, ".tg-sh")["right"] - 1 and cell["right"] <= side["x"] + 1
    stage = box(page, "#tg-stage")
    assert (stage["h"] - chrome["h"]) / stage["h"] > 0.8                # the squares get most of the stage
    expect(page.locator(".tg-corner .tg-sample")).to_be_in_viewport()     # and what they show is called sample where it is shown
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.errors == []
    if os.environ.get("F217_SHOTS"):
        page.screenshot(path=str(SHOTS / "f217-grid-laptop.png"))


def test_scrolling_down_folds_the_search_into_an_island_and_a_tap_opens_it(grid):
    page = grid()
    open_h = box(page, "#tg-chrome")["h"]
    scroll_to(page, 0, 40)
    assert page.get_attribute("#tg-stage", "data-top") == "mid" and open_h > box(page, "#tg-chrome")["h"] > 60
    scroll_to(page, 0, 300)
    assert page.get_attribute("#tg-stage", "data-top") == "mini"
    mini = box(page, "#tg-chrome")
    assert mini["h"] < open_h * 0.55
    expect(page.locator("#tg-open-top")).to_be_visible()
    expect(page.locator("#tg-sent")).to_be_hidden()
    assert abs(box(page, ".tg-fh")["y"] - mini["bottom"]) < 2           # the flights ride just under the island
    assert box(page, ".tg-sh")["x"] == box(page, "#tg-stage")["x"]     # and the stays stay on the left
    if os.environ.get("F217_SHOTS"):
        page.screenshot(path=str(SHOTS / "f217-grid-folded.png"))
    page.click("#tg-open-top")
    assert page.get_attribute("#tg-stage", "data-top") == "open"
    expect(page.locator("#tg-sent")).to_be_visible()
    scroll_to(page, 0, 310)                                             # a nudge keeps it open
    assert page.get_attribute("#tg-stage", "data-top") == "open"
    scroll_to(page, 0, 380)                                             # scrolling on folds it again
    assert page.get_attribute("#tg-stage", "data-top") == "mini"
    scroll_to(page, 0, 0)
    assert page.get_attribute("#tg-stage", "data-top") == "open"


def test_scrolling_sideways_folds_the_panel_into_a_rail_and_a_tap_opens_it(grid):
    page = grid()
    wide = box(page, "#tg-side")["w"]
    scroll_to(page, 400, 0)
    assert page.get_attribute("#tg-stage", "data-side") == "mini"
    assert box(page, "#tg-side")["w"] < wide * 0.4
    expect(page.locator("#tg-open-side")).to_be_visible()
    expect(page.locator("#tg-go")).to_be_hidden()
    assert page.locator("#tg-open-side [data-slot='rail-total']").inner_text() == page.locator("[data-slot='total']").first.text_content()
    page.click("#tg-open-side")
    assert page.get_attribute("#tg-stage", "data-side") == "open"
    expect(page.locator("#tg-go")).to_be_visible()
    scroll_to(page, 300, 0)
    assert page.get_attribute("#tg-stage", "data-side") == "mini"
    last = box(page, "[data-cell='bf8|bh1']")
    scroll_to(page, 5000, 0)
    last = box(page, "[data-cell='bf8|bh1']")
    assert last["right"] <= box(page, "#tg-side")["x"] + 1              # the last flight clears the rail


def test_looking_at_a_square_fills_the_panel_and_leaving_puts_the_best_back(grid):
    page = grid()
    best = page.locator("[data-slot='total']").first.text_content()
    assert page.locator("[data-slot='title']").text_content() == "Lowest · all in"
    page.hover("[data-cell='bf4|bh3']")
    assert page.locator("[data-slot='title']").text_content() == "Looking at · all in"
    assert page.locator("[data-slot='total']").first.text_content() == page.locator("[data-cell='bf4|bh3'] .tg-total").text_content() != best
    assert page.locator("[data-slot='flight']").text_content().startswith("9:40 AM")
    assert page.locator("[data-slot='stay']").text_content().startswith("Test Stay 3")
    assert page.locator("[data-slot='v0']").text_content() == "7:10 AM"   # up 2 h 30 before the 9:40
    assert "is-look" in page.get_attribute("[data-f='bf4']", "class") and "is-look" in page.get_attribute("[data-h='bh3']", "class")
    page.mouse.move(700, 30)                                                # off the grid
    assert page.locator("[data-slot='total']").first.text_content() == best
    assert page.locator("[data-slot='title']").text_content() == "Lowest · all in"
    page.focus("[data-cell='bf2|bh2']")                                     # the keyboard looks too
    assert page.locator("[data-slot='stay']").text_content().startswith("Test Stay 2")


@pytest.mark.parametrize("act, query, start", [("ease", "&lens=ease", ""), ("pet", "&lens=ease&who=pet", ""), ("budget", "&b=2000", ""), ("none", "", "&b=2600"),
                                                ("ease", "&f=bf3&lens=ease", "&f=bf3"), ("ease", "&h=bh6&f=bf2&lens=ease", "&h=bh6&f=bf2"), ("budget", "&h=bh9&b=2000", "&h=bh9")])
def test_a_change_on_the_page_draws_what_the_server_would(grid, act, query, start):
    page, served = grid(start), grid(query)
    if act == "ease":
        page.click(".tg-top [data-lens='ease']")
    elif act == "pet":
        page.click(".tg-top [data-lens='ease']")
        page.click("#tg-day [data-who='pet']")
    elif act == "budget":
        page.click(".tg-tk-budget > summary")
        page.eval_on_selector("#tg-budget", "e => { e.value = 2000; e.dispatchEvent(new Event('input', {bubbles: true})); }")
    else:
        page.click(".tg-tk-budget > summary")
        page.click("#tg-budget-none")
    assert squares(page) == squares(served)
    for name in ("title", "total", "left", "flight", "stay", "k0", "v0", "verdict"):
        assert page.locator(f"[data-slot='{name}']").first.text_content() == served.locator(f"[data-slot='{name}']").first.text_content(), name
    assert said(page.url) == said(served.url)
    for link in ("[data-cell='bf1|bh1']", "#tg-go", ".tg-day", "[data-h='bh2']"):      # a square, a day or a pick taken next keeps the change
        assert said(page.get_attribute(link, "href")) == said(served.get_attribute(link, "href")), link
    marked = "els => els.filter(e => e.getAttribute('aria-current')).map(e => e.dataset.who || e.dataset.lens)"
    assert page.eval_on_selector_all("[data-who], a[data-lens]", marked) == served.eval_on_selector_all("[data-who], a[data-lens]", marked)
    assert page.locator(".tg-tk-budget > summary").text_content() == served.locator(".tg-tk-budget > summary").text_content()
    assert page.errors == []


def test_one_popover_at_a_time_and_escape_closes_it(grid):
    page = grid()
    page.click(".tg-tk-budget > summary")
    expect(page.locator("#tg-budget")).to_be_visible()
    page.click(".tg-tk-with > summary")
    expect(page.locator("#tg-budget")).to_be_hidden()
    expect(page.locator(".tg-tk-with .tg-pop")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".tg-tk-with .tg-pop")).to_be_hidden()
    page.click(".tg-pen")
    expect(page.locator("#tg-q")).to_have_value("A family of 4 with Grandma and the dog, SFO to Los Angeles, Oct 16 to 20.")
    page.fill("#tg-q", "2 adults to San Diego, Oct 20 to 23, under $2,000")
    page.press("#tg-q", "Enter")
    page.wait_for_url("**/plan/grid?to=sd&d=2026-10-20&r=2026-10-23&a=2&b=2000")


def test_a_square_opens_the_trip_and_back_returns_to_the_grid(grid):
    page = grid("&b=3000")
    page.click("[data-cell='bf2|bh4']")
    page.wait_for_url("**/plan/grid/trip?**f=bf2&h=bh4")
    expect(page.locator(".tg-rev-h")).to_contain_text("Your trip · Oct 16 to 20")
    expect(page.locator("#tg-rev-stay")).to_contain_text("Test Stay 4")
    expect(page.locator("#tg-rev-flight .tg-book")).to_have_text("Book Test Air 2")
    page.click("#tg-swaps .tg-swap >> nth=0")
    page.wait_for_url("**f=bf1&h=bh4")
    page.click(".tg-back")
    page.wait_for_url("**/plan/grid?**")
    assert "b=3000" in page.url and "is-mine" in page.get_attribute("[data-cell='bf1|bh4']", "class")


def test_it_all_works_as_plain_links_without_the_script(grid):
    page = grid(js=False)
    chrome, head = box(page, "#tg-chrome"), box(page, ".tg-fh")
    assert head["y"] >= chrome["bottom"] - 1
    page.click(".tg-top [data-lens='ease']")
    page.wait_for_url("**lens=ease**")
    assert page.locator(".tg-cell.is-best .tg-sub").text_content().startswith("easiest · ")
    page.click("[data-h='bh2']")
    page.wait_for_url("**h=bh2**")
    assert page.get_attribute("[data-h='bh2']", "aria-current") == "true"
    page.click(".tg-tk-budget > summary")
    page.click(".tg-set")
    page.wait_for_url("**b=3000**")
    page.click("[data-cell='bf1|bh2']")
    page.wait_for_url("**/plan/grid/trip?**")


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_on_a_phone_each_stay_is_a_card_whose_squares_swipe(grid, scheme):
    page = grid("&b=2600", viewport=PHONE, scheme=scheme)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    expect(page.locator("#tg-side")).to_be_hidden()
    expect(page.locator(".tg-fh").first).to_be_hidden()
    expect(page.locator("[data-cell='bf1|bh1'] .tg-when")).to_have_text("6:00 AM · 1 stop")
    expect(page.locator(".tg-sample-top")).to_be_visible()
    assert page.eval_on_selector(".tg-cells", "e => e.scrollWidth > e.clientWidth")
    small = page.eval_on_selector_all(".tg a, .tg button, .tg summary", "els => els.filter(e => e.offsetParent && (e.getBoundingClientRect().height < 44 || e.getBoundingClientRect().width < 44)).map(e => e.className)")
    assert small == []
    assert page.eval_on_selector(".tg-day[aria-current]", "e => { const r = e.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth; }")
    tiny = page.eval_on_selector_all(".tg *", "els => els.filter(e => e.offsetParent && e.childElementCount === 0 && e.textContent.trim() && parseFloat(getComputedStyle(e).fontSize) < 13).map(e => e.className)")
    assert tiny == []
    page.click(".tg-tk-budget > summary")
    expect(page.locator("#tg-budget")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if os.environ.get("F217_SHOTS"):
        page.screenshot(path=str(SHOTS / f"f217-grid-phone-{scheme}.png"))
    page.click(".tg-tk-budget > summary")
    page.click("[data-cell='bf1|bh1']")
    page.wait_for_url("**/plan/grid/trip?**")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.errors == []


CONTRAST = """() => {
    const lum = c => {
        const unit = c.startsWith('color(');
        const v = c.match(/[0-9.]+/g).slice(0, 3).map(n => { n = unit ? +n : n / 255; return n <= 0.03928 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4; });
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
    };
    const bad = [];
    document.querySelectorAll('.tg-cell, .tg-fh, .tg-sh, .tg-sum, .tg-day, .tg-card, .tg-chip, .tg-seg-b, .tg-isle-b, .tg-rail, .tg-sample').forEach(el => {
        const s = getComputedStyle(el);
        if (!el.offsetParent || s.visibility === 'hidden') return;
        let bg = s.backgroundColor, p = el;
        while (bg === 'rgba(0, 0, 0, 0)' && (p = p.parentElement)) bg = getComputedStyle(p).backgroundColor;
        const a = lum(s.color), b = lum(bg), ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        if (ratio < 4.5) bad.push([el.className, s.color, bg, ratio.toFixed(2)]);
    });
    return bad;
}"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_square_reads_clearly_in_both_modes(grid, scheme):
    page = grid("&b=2600&f=bf2&h=bh2", scheme=scheme)
    assert page.evaluate(CONTRAST) == []
    if os.environ.get("F217_SHOTS"):
        page.screenshot(path=str(SHOTS / f"f217-grid-picked-{scheme}.png"))
    scroll_to(page, 400, 300)                                              # folded: the island and the rail too
    assert page.get_attribute("#tg-stage", "data-top") == "mini" and page.evaluate(CONTRAST) == []
