"""F-059: booked items in a real browser: a soft tint per kind (never the ink), readable text (WCAG AA), a quiet lock, in both themes and on the phone Today view."""
from pathlib import Path

import pytest

from tests_browser.helpers import DESKTOP, PHONE

TEMPLATE = (Path(__file__).resolve().parent.parent / "docs" / "trip-template.md").read_text()

# The block's own background and left edge, and the lowest WCAG contrast between it and any of its text.
MEASURE = """(sel) => { const el = document.querySelector(sel); const cs = getComputedStyle(el);
  const rgb = c => c.match(/[\\d.]+/g).map(Number);
  const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const L = c => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  const bg = rgb(cs.backgroundColor);
  const ratio = fg => { const a = L(bg) + 0.05, b = L(fg) + 0.05; return Math.max(a, b) / Math.min(a, b); };
  const texts = [...el.querySelectorAll('.cal-time, .cal-title, .cal-where, .tp-what, .tp-sub, .tp-label')].map(t => rgb(getComputedStyle(t).color));
  return { bg: cs.backgroundColor, edge: cs.borderLeftColor, edgeW: parseFloat(cs.borderLeftWidth), min: Math.min(...texts.map(ratio)), n: texts.length }; }"""

INK = "rgb(30, 26, 46)"


def tint(page, name):
    h = page.evaluate(f"getComputedStyle(document.documentElement).getPropertyValue('--{name}-tint').trim()").lstrip("#")
    return "rgb(%d, %d, %d)" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


@pytest.fixture
def signed_in(browser, base_url):
    ctxs = []

    def make(viewport):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        ctxs.append(ctx)
        page = ctx.new_page()
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)
        return page

    yield make
    for c in ctxs:
        c.close()


@pytest.mark.parametrize("block,kind", [("b-out", "sky"), ("b-in", "grape"), ("b-car-pick", "sun")])
def test_a_booked_calendar_block_is_a_soft_tint_with_readable_text_and_a_solid_edge(signed_in, base_url, block, kind):
    page = signed_in(DESKTOP)
    page.goto(f"{base_url}/calendar?view=days")
    sel = f'.cal-booked[data-block="{block}"]'
    page.wait_for_selector(sel)
    got = page.evaluate(MEASURE, sel)
    assert got["bg"] != INK and got["bg"] == tint(page, kind)
    assert got["edgeW"] >= 3 and got["edge"] != got["bg"] and got["edge"] != INK
    assert got["n"] >= 2 and got["min"] >= 4.5
    assert page.locator(f"{sel} .cal-lock svg").count() == 1 and page.locator(f"{sel} > .cal-flow svg").count() == 1
    assert page.locator(f"{sel} .cal-elsewhere").count() == 0


@pytest.mark.parametrize("theme", ["sunset", "pacific"])
def test_the_whole_trip_view_is_tinted_in_both_themes(signed_in, base_url, theme):
    page = signed_in(DESKTOP)
    page.goto(f"{base_url}/calendar?view=whole")
    page.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
    assert page.locator(".cal-w-bk").count() >= 6
    chip = page.locator(".cal-w-bk.cal-bk-flight .cal-w-booked").first
    assert chip.evaluate("e => getComputedStyle(e).backgroundColor") == tint(page, "sky")


def test_the_phone_today_cards_are_tinted_with_a_lock_and_readable_text(signed_in, base_url):
    page = signed_in(PHONE)
    page.goto(f"{base_url}/trip?day=0")
    sel = ".tp-card.tp-flight"
    page.wait_for_selector(sel)
    got = page.evaluate(MEASURE, sel)
    assert got["bg"] != INK and got["bg"] == tint(page, "sky") and got["edgeW"] >= 3 and got["min"] >= 4.5
    assert page.locator(f"{sel} .tp-lock svg").count() == 1
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
