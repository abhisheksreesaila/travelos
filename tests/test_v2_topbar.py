"""F-255: the v2 top bar can take you places. Server side: which items the sections pill and the avatar menu show (signed out, signed in with no trip, with a trip, the captain), which section
is marked, and where the refusal's way back goes. How the menu opens and closes is tests_browser/test_v2_topbar.py."""
import re

from tests.test_calendar import book
from tests.test_roles import FORM, crew  # noqa: F401 - a fixture
from tests.test_signin import sign_in

PLAN = "/trip/plan"
ASK = "/plan/ask"
MATRIX = "/plan/matrix"


def parts(html):
    """([(label, href, is current)] of the sections pill, [(label, href)] of the avatar menu, has Sign out) of a v2 page."""
    pill = re.search(r'<nav[^>]*class="v2-sections[^"]*"[^>]*>(.*?)</nav>', html, re.S).group(1)
    pills = [(re.sub(r"<[^>]+>", "", text), re.search(r'href="([^"]+)"', tag).group(1), 'aria-current="page"' in tag) for tag, text in re.findall(r"(<a [^>]*>)(.*?)</a>", pill, re.S)]
    menu = re.search(r'<div[^>]*id="v2-menu".*?</form>\s*</div>', html, re.S)
    links = [(text, href) for href, text in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', menu.group(0), re.S)] if menu else []
    return pills, links, bool(menu and 'action="/signout"' in menu.group(0) and ">Sign out<" in menu.group(0))


def test_a_visitor_sees_plan_a_trip_and_guides_and_sign_in_and_no_menu(client):
    html = client.get(MATRIX).text
    pills, menu, out = parts(html)
    assert [p[0] for p in pills] == ["Plan a trip", "Guides"]      # review of F-255: the one door (layout.plan_href) stays in a visitor's bar; F-262: Guides replaced Community trips and For creators
    assert pills[1:] == [("Guides", "/guides", False)] and pills[0][1] == "/plan/ask"      # D-761: a visitor searches without an account
    assert menu == [] and not out
    assert ">Sign in<" in html


def test_signed_in_without_a_trip_has_book_and_guides_but_no_plan_or_family(client):
    sign_in(client)
    pills, menu, out = parts(client.get(ASK).text)
    assert pills == [("Book", ASK, True), ("Guides", "/guides", False)]
    assert menu == [("Family members", "/family")]      # F-262: Family left the bar and stays one tap away in the avatar's menu
    assert out


def test_with_a_trip_the_pill_is_book_plan_guides_and_marks_the_page_it_is_on(client):
    book(client)
    assert parts(client.get(PLAN).text)[0] == [("Book", ASK, False), ("Plan", PLAN, True), ("Guides", "/guides", False)]
    assert parts(client.get(ASK).text)[0] == [("Book", ASK, True), ("Plan", PLAN, False), ("Guides", "/guides", False)]


def test_the_captain_alone_has_admin_in_the_menu(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "cap@example.com")
    sign_in(client, "cap@example.com")
    _, menu, _ = parts(client.get(ASK).text)
    assert menu == [("Family members", "/family"), ("Admin", "/admin")]
    sign_in(client, "ari")
    _, menu, _ = parts(client.get(ASK).text)
    assert ("Admin", "/admin") not in menu


def test_the_refusal_leads_back_to_the_plan(crew):      # noqa: F811
    _, _, viewer = crew
    r = viewer.post("/trip/plans", data={"id": "a1", **FORM}, follow_redirects=False)
    assert r.status_code == 403 and 'href="/trip/plan"' in r.text and "Back to the trip" in r.text


def test_with_a_trip_the_avatar_menu_has_help_who_to_call_and_it_opens(client):
    """F-254: the old SOS lives in the avatar menu (a phone has the avatar top right too), only when the family has a trip."""
    book(client)
    _, menu, _ = parts(client.get(PLAN).text)
    assert ("Help · who to call", "/trip/booking?sos=1") in menu
    assert 'href="tel:911"' in client.get("/trip/booking?sos=1").text
