"""F-139: one top bar for the signed-in web. Server side: what the bar holds, which section is marked, who gets it.
Where it shows (desktop only) and what each link does are checked in a browser: tests_browser/test_topbar.py."""

import re

from tests.test_calendar import book
from tests.test_signin import sign_in
from tests.test_trip_import import imported


def bar(html):
    """The top bar's markup ("" when the page has none)."""
    m = re.search(r'<header[^>]*class="ga-topbar".*?</header>', html, re.S)
    return m.group(0) if m else ""


def marked(html):
    """The labels of the nav links marked as the current section."""
    links = re.findall(r'<a [^>]*aria-current="page"[^>]*>(.*?)</a>', bar(html).split("</nav>")[0], re.S)
    return [re.sub(r"<[^>]+>", "", x).replace("/", "").strip() for x in links]


def test_a_signed_in_page_has_the_bar_with_trip_family_ask_picker_sos_and_the_avatar_menu(client):
    book(client)
    b = bar(client.get("/family").text)
    assert b
    nav = b.split("</nav>")[0]
    for href in ("/trip", "/trip/family", "/trip/ask"):
        assert f'href="{href}"' in nav
    for label in ("Trip", "Family", "Ask"):
        assert f">{label}<" in nav.replace(" <kbd>", "<") or label in nav
    assert "<kbd" in nav                                           # the "/" key hint beside Ask
    assert "ga-tb-picker" in b                                     # the trip picker
    assert 'href="/trip/canvas?sos=1&amp;trip=' in b              # SOS, on the trip this page shows
    assert 'action="/signout"' in b and "Sign out" in b           # the avatar menu
    assert 'href="/family"' in b                                   # People and invites


def test_the_picker_names_the_open_trip_with_its_dates_and_lists_every_trip(client):
    book(client)
    book(client, d="2026-10-23", r="2026-10-26", a="2", k="4,7")
    b = bar(client.get("/family").text)
    assert len(re.findall(r'name="trip" value="', b)) == 2        # one switch form per trip
    assert 'aria-current="true"' in b                              # the open one is marked
    assert re.search(r"Oct \d+ . \d+", b)                          # its dates, as the phone header writes them


def test_the_current_section_is_marked(client):
    book(client)
    assert marked(client.get("/trip/ask").text) == ["Ask"]
    assert marked(client.get("/trip/family").text) == ["Family"]
    assert marked(client.get("/family").text) == ["Family"]
    assert marked(client.get("/trip/canvas?day=0").text) == ["Trip"]
    assert marked(client.get("/trip/canvas?day=0&panel=family").text) == ["Family"]          # F-143: the day with the Family chats open in the panel
    imported(client)                                               # /trip/details is the imported trip's page
    r = client.get("/trip/details")
    assert r.status_code == 200 and marked(r.text) == ["Trip"]


def test_the_trip_canvas_and_the_phone_tabs_carry_the_bar(client):
    book(client)
    for path in ("/trip/canvas?day=0", "/trip/canvas", "/trip/ask", "/trip/family", "/trip/help", "/trip/map", "/trip?tab=notes", "/calendar"):
        assert bar(client.get(path).text), path


def test_a_family_with_no_trip_gets_start_instead_of_trip(client):
    sign_in(client)
    b = bar(client.get("/family").text)
    nav = b.split("</nav>")[0]
    assert 'href="/start"' in nav and ">Start<" in nav
    assert 'href="/trip"' not in nav
    assert "/trips/switch" not in b                                # no trips to pick
    assert "sos=1" not in b                                        # nothing to send help about


def test_signed_out_pages_keep_their_own_header(client):
    for path in ("/", "/signin", "/community", "/privacy"):
        html = client.get(path).text
        assert "ga-topbar" not in html, path
        assert "ga-header" in html, path


def test_the_landing_keeps_its_own_header_for_a_signed_in_visitor_too(client):
    book(client)
    assert "ga-topbar" not in client.get("/").text


def test_the_old_header_stays_in_the_page_for_the_tablet(client):
    book(client)
    html = client.get("/family").text
    assert "ga-header" in html and "ga-topbar" in html            # css shows one or the other by width


def test_community_is_in_the_avatar_menu_only_with_the_showcase_on(client, monkeypatch):
    book(client)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    assert 'href="/community"' in bar(client.get("/family").text)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    b = bar(client.get("/family").text)
    assert "Community" not in b and "/creators" not in b


def test_the_bar_is_in_rem_and_sized_by_its_own_stylesheet(client):
    book(client)
    html = client.get("/family").text
    assert "/assets/css/topbar.css" in html
    assert html.index("/assets/css/base.css") < html.index("/assets/css/topbar.css")
    css = client.get("/assets/css/topbar.css").text
    assert "min-width: 1020px" in css


def test_trip_opens_day_one_before_the_trip_and_today_during_it(client, monkeypatch):
    """The bar's Trip link is /trip, which lands on the trip's day: the first before the trip, today's during it (F-092's rule, which the bar relies on)."""
    from datetime import date

    from gitaway import catalog
    from tests.test_family_storage import THREE_NIGHTS
    book(client, **THREE_NIGHTS)
    assert 'href="/trip"' in bar(client.get("/family").text)
    assert client.get("/trip", follow_redirects=False).headers["location"].startswith("/trip/canvas?day=0")      # today is Sep 30
    monkeypatch.setattr(catalog, "today", lambda: date(2026, 10, 18), raising=False)
    assert client.get("/trip", follow_redirects=False).headers["location"].startswith("/trip/canvas?day=2")      # Oct 18 is the trip's third day
