"""F-059: booked items in a real browser: a soft tint per kind (never the ink), readable text (WCAG AA), a quiet lock, on the phone.
M5 triage: the phone Today view is retired (F-254); the same blocks are the locked blocks of the planning calendar (`a.ev.lock`, F-252)."""
from pathlib import Path

import pytest

from tests_browser.helpers import DESKTOP, PHONE

TEMPLATE = (Path(__file__).resolve().parent.parent / "docs" / "trip-template.md").read_text()

# The block's own background and left edge, and the lowest WCAG contrast between it and any of its text.
MEASURE = """(sel) => { const el = document.querySelector(sel); const cs = getComputedStyle(el);
  const rgb = c => { const n = c.match(/[\\d.]+/g).map(Number); return c.startsWith('color(') ? n.slice(0, 3).map(v => v * 255) : n; };      // a color-mix() comes back as color(srgb 0.9 0.9 1)
  const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const L = c => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  const bg = rgb(cs.backgroundColor);
  const ratio = fg => { const a = L(bg) + 0.05, b = L(fg) + 0.05; return Math.max(a, b) / Math.min(a, b); };
  const texts = [...el.querySelectorAll('b, .tm')].map(t => rgb(getComputedStyle(t).color));
  return { bg: cs.backgroundColor, edge: cs.borderLeftColor, edgeW: parseFloat(cs.borderLeftWidth), min: Math.min(...texts.map(ratio)), n: texts.length }; }"""

TOKEN = {"flight": "flight", "stay": "stay", "car": "ride", "ride": "ride"}      # a locked block's kind -> its v2 token (v2plan.css `.k-*`)


def tint(page, name):
    h = page.evaluate(f"getComputedStyle(document.documentElement).getPropertyValue('--{name}-t').trim()").lstrip("#")
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


def test_the_phone_today_cards_are_tinted_with_a_lock_and_readable_text(signed_in, base_url):
    page = signed_in(PHONE)
    page.goto(f"{base_url}/trip/plan")
    sel = "a.ev.lock"
    page.wait_for_selector(sel)
    got = page.evaluate(MEASURE, sel)
    assert got["n"] >= 2 and got["min"] >= 4.5, got
    blocks = page.evaluate("""() => [...document.querySelectorAll('a.ev.lock')].map(e => { const cs = getComputedStyle(e);
      return [[...e.classList].find(c => c.startsWith('k-')).slice(2), cs.backgroundColor, parseFloat(cs.boxShadow.match(/([\\d.]+)px 0px 0px 0px/)[1])]; })""")
    assert blocks
    for kind, bg, edge_w in blocks:
        assert kind in TOKEN, f"a locked {kind} block has no token in this test"
        assert bg == tint(page, TOKEN[kind]), (kind, bg)      # the kind's soft tint, never the ink
        assert edge_w >= 3, (kind, edge_w)                    # the kind's solid left edge (an inset box-shadow, 0.25rem = 4px)
    assert page.locator(f"{sel} svg.lk").first.count() == 1
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
