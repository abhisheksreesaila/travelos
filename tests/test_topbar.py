"""F-139: one top bar for the signed-in web. Server side: what the bar holds, which section is marked, who gets it.
Where it shows (desktop only) and what each link does are checked in a browser: tests_browser/test_topbar.py."""

import re

from gitaway import showcase
from tests.test_calendar import book
from tests.test_roles import crew  # noqa: F401 - a fixture
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


def test_signed_out_pages_keep_their_own_header(client):
    for path in ("/", "/signin", "/privacy"):
        html = client.get(path).text
        assert "ga-topbar" not in html, path
        assert ('class="cv-top"' if path == "/" else "ga-header") in html, path      # the signed-out landing is the cover, with its own header (F-206)


def test_the_front_door_opens_a_signed_in_visitors_trip_and_its_bar(client):      # F-231: no signed-in landing keeps a header of its own any more
    book(client)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == showcase.planning_path()      # D-600: the journey's first step, booked or not
    assert 'class="v2-top"' in client.get("/").text      # F-250: the journey's pages wear the v2 top bar


def test_the_old_header_stays_in_the_page_for_the_tablet(client):
    book(client)
    html = client.get("/family").text
    assert "ga-header" in html and "ga-topbar" in html            # css shows one or the other by width


def test_guides_is_in_the_avatar_menu_on_and_off_the_showcase(client, monkeypatch):
    """D-458, F-262: Guides is in every header; off the showcase, before anyone shares, its page says so."""
    book(client)
    for mode in ("1", "0"):
        monkeypatch.setenv("GITAWAY_SHOWCASE", mode)
        b = bar(client.get("/family").text)
        assert 'href="/guides"' in b and 'href="/community"' not in b and 'href="/for-creators"' not in b and 'href="/creators"' not in b, mode


def test_the_bar_is_in_rem_and_sized_by_its_own_stylesheet(client):
    book(client)
    html = client.get("/family").text
    assert "/assets/css/topbar.css" in html
    assert html.index("/assets/css/base.css") < html.index("/assets/css/topbar.css")
    css = client.get("/assets/css/topbar.css").text
    assert "min-width: 1020px" in css


# ---- the trip menu below 1020px (F-147 review) ----------------------------------------------------------------------------

def phone_pick(html):
    """The trip menu in the heading of a phone or tablet screen (the bar itself is hidden there)."""
    m = re.search(r'<details[^>]*ga-tb-phonepick.*?</details>', html, re.S)
    return m.group(0) if m else ""


def test_a_family_with_no_trip_has_no_trip_menu(client):
    sign_in(client)
    assert phone_pick(client.get("/family").text) == ""

