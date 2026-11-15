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


def test_a_visitor_sees_plan_a_trip_community_trips_and_for_creators_and_sign_in_and_no_menu(client):
    html = client.get(MATRIX).text
    pills, menu, out = parts(html)
    assert [p[0] for p in pills] == ["Plan a trip", "Community trips", "For creators"]      # review of F-255: the one door (layout.plan_href) stays in a visitor's bar
    assert pills[1:] == [("Community trips", "/community", False), ("For creators", "/for-creators", False)] and pills[0][1].startswith("/signin")
    assert menu == [] and not out
    assert ">Sign in<" in html


def test_signed_in_without_a_trip_has_book_and_family_but_no_plan(client):
    sign_in(client)
    pills, menu, out = parts(client.get(ASK).text)
    assert pills == [("Book", ASK, True), ("Family", "/family", False)]
    assert menu == [("Family", "/family"), ("Community trips", "/community"), ("For creators", "/for-creators")]
    assert out


def test_with_a_trip_the_pill_has_plan_first_and_marks_the_page_it_is_on(client):
    book(client)
    assert parts(client.get(PLAN).text)[0] == [("Plan", PLAN, True), ("Book", ASK, False), ("Family", "/family", False)]
    assert parts(client.get(ASK).text)[0] == [("Plan", PLAN, False), ("Book", ASK, True), ("Family", "/family", False)]


def test_the_captain_alone_has_admin_in_the_menu(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "cap@example.com")
    sign_in(client, "cap@example.com")
    _, menu, _ = parts(client.get(ASK).text)
    assert menu == [("Family", "/family"), ("Admin", "/admin"), ("Community trips", "/community"), ("For creators", "/for-creators")]
    sign_in(client, "ari")
    _, menu, _ = parts(client.get(ASK).text)
    assert ("Admin", "/admin") not in menu


def test_the_refusal_leads_back_to_the_plan(crew):      # noqa: F811
    _, _, viewer = crew
    r = viewer.post("/trip/plans", data={"id": "a1", **FORM}, follow_redirects=False)
    assert r.status_code == 403 and 'href="/trip/plan"' in r.text and "Back to the trip" in r.text
