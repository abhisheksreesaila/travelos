"""F-067: the phone shell (bottom tab bar on every trip screen) and Today v2: Up next with Leave by, Directions and the Uber deep link, the route strip."""

import re
import sys
import types
from datetime import date
from html import unescape

import pytest

from gitaway import catalog, phone, tripday as td
from tests.test_calendar import book
from tests.test_members import addr, browser, invite
from tests.test_signin import sign_in
from tests.test_trip_import import imported
from tests.test_trip_phone import plan, tag

PATHS = {"today": "/trip", "map": "/trip/map", "ask": "/trip/ask", "family": "/trip/family", "help": "/trip/help"}


@pytest.fixture
def at(monkeypatch):
    def pin(day, hhmm="12:00"):
        h, m = map(int, hhmm.split(":"))
        monkeypatch.setattr(catalog, "today", lambda *_: day)
        monkeypatch.setattr(td, "now_minute", lambda *_: h * 60 + m)
    return pin


@pytest.fixture
def geo(monkeypatch):
    """geo(minutes) installs a fake gitaway.geo whose drive_minutes always answers `minutes`."""
    def install(minutes):
        mod = types.ModuleType("gitaway.geo")
        mod.drive_minutes = lambda a, b: minutes
        monkeypatch.setitem(sys.modules, "gitaway.geo", mod)
    return install


def bar(html):
    nav = re.search(r'<nav[^>]*class="ph-tabs".*?</nav>', html, re.S).group(0)
    return re.findall(r'<a[^>]*href="([^"]+)"[^>]*>', nav), nav


# ---- the bar ------------------------------------------------------------------------------------------------------------

def test_the_tab_bar_has_five_tabs_in_order_and_ask_is_raised():
    nav = str(phone.tabbar("map"))
    labels = re.findall(r"</svg></span>([A-Za-z]+)</a>", nav)
    assert labels == ["Today", "Map", "Ask", "Family", "Help"]
    assert re.findall(r'href="([^"]+)"', nav) == list(PATHS.values())
    assert nav.count('aria-current="page"') == 1 and re.search(r'id="ph-tab-map"[^>]*aria-current="page"|aria-current="page"[^>]*id="ph-tab-map"', nav)
    assert "ph-ask" in re.search(r'<a[^>]*id="ph-tab-ask"[^>]*>', nav).group(0)


@pytest.mark.parametrize("key", list(PATHS))
def test_every_trip_screen_sits_in_the_shell(client, key):
    book(client)
    html = client.get(PATHS[key]).text
    hrefs, nav = bar(html)
    assert hrefs == list(PATHS.values())
    assert re.search(r'id="ph-tab-%s"[^>]*aria-current="page"' % key, nav) or re.search(r'aria-current="page"[^>]*id="ph-tab-%s"' % key, nav)
    assert nav.count('aria-current="page"') == 1
    assert "/assets/css/phone.css" in html and html.index("/assets/css/base.css") < html.index("/assets/css/phone.css")


@pytest.mark.parametrize("key", ["map", "ask", "family", "help"])
def test_a_tab_not_built_yet_shows_a_short_coming_card(client, key):
    book(client)
    html = client.get(PATHS[key]).text
    card = re.search(r'<div[^>]*id="ph-coming".*?</div>', html, re.S).group(0)
    assert f"{key.title()} is coming" in card and 'href="/trip"' in card
    assert '<h1' in html and f">{key.title()}</h1>" in html
    assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", html)


@pytest.mark.parametrize("key", ["map", "ask", "family", "help"])
def test_a_tab_needs_sign_in_and_a_trip(client, key):
    r = client.get(PATHS[key], follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/signin?next=%2Ftrip%2F{key}"
    sign_in(client)
    r = client.get(PATHS[key], follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/start"


@pytest.mark.parametrize("role", ["viewer", "editor"])
def test_every_role_gets_the_same_tabs_with_no_edit_controls_on_the_placeholders(client, role):
    book(client)
    mail = addr(role[:2])
    invite(client, mail, role)
    other = browser(client)
    sign_in(other, mail)
    for key, path in PATHS.items():
        r = other.get(path)
        assert r.status_code == 200 and bar(r.text)[0] == list(PATHS.values()), path
        if key != "today":
            main = re.search(r"<main.*?</main>", r.text, re.S).group(0)
            assert "<form" not in main and "<input" not in main, path


def test_each_tab_has_its_own_module_with_the_contract():
    from gitaway.pages import tab_ask, tab_family, tab_help, tab_map
    for mod in (tab_map, tab_ask, tab_family, tab_help):
        assert callable(mod.content) and mod.TITLE


def test_a_tab_module_can_be_swapped_without_touching_the_shell(client, monkeypatch):
    from fasthtml.common import Div
    from gitaway.pages import tab_map
    monkeypatch.setattr(tab_map, "content", lambda request, session: Div("Real map here", id="real"))
    monkeypatch.setattr(tab_map, "SCRIPTS", ("/assets/js/map.js",), raising=False)
    book(client)
    html = client.get("/trip/map").text
    assert 'id="real"' in html and "is coming" not in html and "/assets/js/map.js" in html
    assert bar(html)[0] == list(PATHS.values())


def test_today_sits_in_the_same_shell_and_keeps_its_own_switch(client):
    book(client)
    html = client.get("/trip").text
    hrefs, nav = bar(html)
    assert hrefs == list(PATHS.values()) and 'id="ph-tab-today"' in nav
    for name in ("Today", "All days", "Notes"):
        assert f">{name}</a>" in html


# ---- the pure parts -------------------------------------------------------------------------------------------------------

def test_the_uber_link_carries_the_destination_and_nothing_else():
    url = td.uber_url("Griffith Observatory, Los Angeles")
    assert url == "https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff[formatted_address]=Griffith%20Observatory%2C%20Los%20Angeles"
    assert td.uber_url("Joe's & Sons, 5th Ave") .endswith("Joe%27s%20%26%20Sons%2C%205th%20Ave")
    assert td.uber_url("") == ""


def test_drive_minutes_is_unknown_without_the_geo_module_and_asks_it_when_present(geo, monkeypatch):
    monkeypatch.delitem(sys.modules, "gitaway.geo", raising=False)
    assert td.drive_minutes("a", "b") is None
    geo(18)
    assert td.drive_minutes("a", "b") == 18
    geo(None)
    assert td.drive_minutes("a", "b") is None
    geo(0)
    assert td.drive_minutes("a", "b") is None
    mod = types.ModuleType("gitaway.geo")
    mod.drive_minutes = lambda a, b: 1 / 0
    monkeypatch.setitem(sys.modules, "gitaway.geo", mod)
    assert td.drive_minutes("a", "b") is None  # a routing service that is down never breaks Today


def test_leave_by_is_the_start_minus_the_drive_and_counts_down_from_now(geo):
    geo(18)
    item = td.Item("a1", 10 * 60, 11 * 60, "Six Flags", "plan", "Fun", "sun", "", "", place="Six Flags, Valencia")
    assert td.leave_by(item, "Hotel", 9 * 60 + 12) == (9 * 60 + 42, 18, 30)
    assert td.leave_by(item, "", 9 * 60) is None
    assert td.leave_by(td.Item("a2", 600, 660, "x", "plan", "", "", "", ""), "Hotel", 0) is None


# ---- Today v2 ----------------------------------------------------------------------------------------------------------

def _today(client, at, hhmm="16:00"):
    imported(client)
    plan(client, "a1", "1", "17:00", "19:30", "Griffith Observatory", "culture")
    at(date(2026, 10, 17), hhmm)
    return client.get("/trip").text


def test_up_next_has_directions_and_an_uber_deep_link_with_the_destination(client, at):
    html = _today(client, at)
    uber = unescape(tag(html, "id", "tp-uber")["href"])
    assert uber == "https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff[formatted_address]=Griffith%20Observatory%2C%20Los%20Angeles"
    assert "Griffith+Observatory" in unescape(tag(html, "id", "tp-directions")["href"])


def test_no_leave_by_line_while_the_drive_time_is_unknown(client, at, monkeypatch):
    monkeypatch.delitem(sys.modules, "gitaway.geo", raising=False)
    html = _today(client, at)
    assert 'id="tp-leave"' not in html and "Leave by" not in html


def test_leave_by_and_a_countdown_show_when_the_drive_time_is_known(client, at, geo):
    geo(20)
    html = _today(client, at, "16:00")
    leave = re.search(r'<div[^>]*id="tp-leave".*?</div>', html, re.S).group(0)
    assert "Leave by 4:40 PM" in leave and "20 min drive" in leave
    assert '<span class="ph-ring-n">40</span>' in leave


def test_time_to_leave_when_the_leave_by_has_passed(client, at, geo):
    geo(20)
    html = _today(client, at, "16:50")
    assert "Time to leave" in html and '<span class="ph-ring-n">0</span>' in html


def test_the_day_has_a_route_strip_of_its_stops_and_a_section_label(client, at):
    html = _today(client, at)
    strip = re.search(r'<div[^>]*id="tp-route".*?</div>', html, re.S).group(0)
    assert "<svg" in strip and strip.count('class="ph-stop') >= 2 and "stops" in strip
    assert "Griffith Observatory" in strip  # in the accessible name
    assert "THE REST OF TODAY" in html and 'id="tp-stay"' in html


def test_what_f065_added_is_still_there(client, at):
    html = _today(client, at)
    for hook in ('id="tp-share"', 'data-dir="a1"'):
        assert hook in html
    assert "data-confirm=" in client.get("/trip?day=0").text
