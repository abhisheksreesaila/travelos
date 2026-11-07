"""F-203 review: MET Norway's credit is one tap target, the whole line, at least 48px tall on a phone and on a touch tablet; and the weather pane does not
scroll sideways."""
import pytest

from gitaway import catalog, weather
from tests import weather_support as ws
from tests_browser.helpers import DESKTOP, PHONE

PLAN = "/plan?d=2026-12-19&r=2026-12-23&a=2"     # Los Angeles, Dec 19-23, with the forecast of tests/weather_support.py
CREDIT = "Forecast for Los Angeles, based on data from MET Norway · updated 6:10 AM"


@pytest.fixture
def forecast(monkeypatch):
    monkeypatch.setenv("MET_NORWAY_TERMS_ACCEPTED", "1")
    monkeypatch.setattr(catalog, "now_utc", lambda: ws.NOW)
    monkeypatch.setattr(catalog, "today", lambda: ws.NOW.astimezone(ws.PST).date())
    monkeypatch.setattr(weather, "TRANSPORT", ws.Met())


@pytest.fixture
def open_page(browser, base_url):
    ctxs = []

    def go(path, viewport, touch=False):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=touch)
        ctx.set_default_timeout(5000)
        ctxs.append(ctx)
        page = ctx.new_page()
        page.goto(base_url + path)
        return page
    yield go
    for c in ctxs:
        c.close()


def test_the_credit_line_is_one_link_at_least_48px_tall_on_a_phone(forecast, open_page):
    page = open_page(PLAN, PHONE)
    credit = page.locator('[data-pane="weather"] a.ws-wcredit')
    credit.scroll_into_view_if_needed()
    assert credit.inner_text().strip() == CREDIT
    assert credit.get_attribute("href") == weather.CREDIT_URL
    assert credit.bounding_box()["height"] >= 48
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_on_the_laptop_the_credit_line_stays_a_quiet_single_line(forecast, open_page):
    page = open_page(PLAN, DESKTOP)
    credit = page.locator('[data-pane="weather"] a.ws-wcredit')
    assert credit.inner_text().strip() == CREDIT
    assert credit.bounding_box()["height"] < 48


def test_on_a_touch_tablet_the_credit_line_is_a_48px_tap_target_too(forecast, open_page):
    page = open_page(PLAN, {"width": 1024, "height": 768}, touch=True)      # wider than a phone, but a finger: (pointer: coarse)
    credit = page.locator('[data-pane="weather"] a.ws-wcredit')
    credit.scroll_into_view_if_needed()
    assert credit.bounding_box()["height"] >= 48
