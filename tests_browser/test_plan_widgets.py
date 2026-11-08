"""F-210 (part B) in a real browser: the trip's context beside the booking lanes for the captain's Lake Tahoe trip, in production (sample data off), light and dark.
On a phone the panel is a strip above the lanes that scrolls sideways inside itself (the page never does); from 1020px it stands beside them. The values are the real
sources' (NOAA typical weather, a stubbed Aviasales price, a stubbed router answer); nothing reaches the network."""

import pytest

from gitaway import airportdrive, geo
from gitaway.partners import prices
from tests.test_plan_widgets import Router
from tests_browser.helpers import DESKTOP, PHONE

TAHOE = "/plan?place=Lake+Tahoe&d=2026-12-19&r=2026-12-26&a=2&k=8,11&home=SFO"


@pytest.fixture(autouse=True)
def production(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    for name in ("TRAVELPAYOUTS_MARKER", "TRAVELPAYOUTS_TRS", "PARTNER_STAY", "PARTNER_TRACKED", "MET_NORWAY_TERMS_ACCEPTED"):
        monkeypatch.delenv(name, raising=False)
    prices.clear()
    airportdrive.clear()
    monkeypatch.setattr(prices, "TRANSPORT", lambda *a: {"success": True, "data": [{"price": 187}]})
    monkeypatch.setattr(geo, "fetch", Router(3900))
    yield
    prices.clear()
    airportdrive.clear()


GEOMETRY = """() => {
  const box = e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, r: r.right, b: r.bottom, w: r.width, h: r.height}; };
  const pw = document.getElementById('pw'), lanes = document.querySelector('.ps-cards');
  return {pw: box(pw), lanes: box(lanes), page: document.documentElement.scrollWidth, view: innerWidth,
          cards: [...pw.querySelectorAll('.pw-card')].map(c => c.id),
          links: [...pw.querySelectorAll('a')].map(a => a.getBoundingClientRect().height),
          small: [...pw.querySelectorAll('.pw-card *')].filter(e => e.checkVisibility() && e.childElementCount === 0 && e.textContent.trim()
                 && parseFloat(getComputedStyle(e).fontSize) < 16 && !e.matches('.pw-wday')).map(e => e.className),
          ink: getComputedStyle(pw.querySelector('.pw-value')).color, card: getComputedStyle(pw.querySelector('.pw-card')).backgroundColor};
}"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_panel_is_a_strip_above_the_lanes_on_a_phone_and_beside_them_on_a_laptop(browser, base_url, viewport, scheme):
    ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE, reduced_motion="reduce", color_scheme=scheme)
    try:
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base_url + TAHOE)
        g = page.evaluate(GEOMETRY)
        assert errors == []
        assert g["cards"] == ["pw-weather", "pw-money", "pw-drive"]
        assert g["page"] <= g["view"]                                       # nothing scrolls the page sideways
        assert all(h >= (48 if viewport is PHONE else 36) for h in g["links"])  # the credit line is one whole tap target
        assert g["ink"] != g["card"]
        if viewport is PHONE:
            assert g["pw"]["b"] <= g["lanes"]["y"] and g["pw"]["h"] < 320    # a compact strip above the lanes
            assert g["small"] == []                                         # 16px floor for words on a phone
        else:
            assert g["pw"]["x"] >= g["lanes"]["r"] and abs(g["pw"]["y"] - g["lanes"]["y"]) < 2      # beside the lanes, tops aligned
        text = page.locator("#pw").inner_text()
        assert "not a forecast yet" in text and "From $187 a person" in text and "1 h 5 min to South Lake Tahoe" in text
    finally:
        ctx.close()
