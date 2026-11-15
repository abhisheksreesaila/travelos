"""F-060, D-458: the site's header and footer. A signed-out visitor gets the cover story at / (tests/test_cover.py); the header and footer rules for a stranger are
checked on the cover. A signed-in person has no landing: / opens their trip or the trip matrix (F-231, tests/test_way_in.py)."""
import re

from gitaway import itineraries
from tests.test_signin import sign_in


def _get(client, path="/"):
    if path == "/":
        sign_in(client)       # F-206: this landing is the signed-in one now
    r = client.get(path)
    assert r.status_code == 200
    return r.text


def _tag(h, name, cls):
    m = re.search(rf'<{name}[^>]*class="[^"]*\b{cls}\b[^"]*"[^>]*>(.*?)</{name}>', h, re.S)
    assert m, f"no <{name}> with class {cls}"
    return m.group(1)


def _hrefs(fragment):
    return re.findall(r'href="([^"]*)"', fragment)


def test_landing_header_is_the_sites_way_in(client):
    """D-458 (founder, 2026-11-13): the home page introduces, and its header is the way in: For creators, Community trips, Plan a trip, Sign in."""
    header = _tag(client.get("/").text, "header", "cv-top")       # the signed-out landing is the cover (F-206)
    assert _hrefs(header) == ["/", "/for-creators", "/community", "/signin", "/signin"]
    assert header.index("For creators") < header.index("Community trips") < header.index("Plan a trip")


def test_other_pages_keep_their_header_nav(client):
    header = _tag(_get(client, "/creators"), "header", "ga-header")      # F-200: sign-in is a full-screen page with the brand and Cancel only
    assert "/community" in header and "/for-creators" in header and 'href="/signin"' in header      # signed out, Plan a trip signs in first, and / then decides (D-458, D-461)
    for path in ["/community", "/for-creators"]:       # F-253: the creator pages wear the v2 top bar, which carries the same way in
        top = re.search(r'<div class="v2-top">.*?(?=<main)', _get(client, path), re.S).group(0)
        assert _hrefs(top)[1:4] == ["/signin", "/community", "/for-creators"] and _hrefs(top)[4].startswith("/signin?next="), path      # F-255: the pill begins with Plan a trip (it signs in first), then Community trips and For creators; then Sign in


def test_footer_carries_the_links_that_left_the_header(client):
    footer = _tag(client.get("/").text, "footer", "cv-foot")      # the signed-out landing is the cover (F-206)
    assert [h for h in _hrefs(footer) if h.startswith("/")] == ["/community", "/for-creators", "/signin", "/privacy", "/terms"]   # (and the map data's credit, tests/test_cover.py)
    other = _tag(_get(client, "/community"), "footer", "cb-foot")      # F-253: the creator pages' foot
    assert _hrefs(other) == ["/privacy", "/terms"]


def test_signed_in_visitor_sees_their_account_and_no_sign_in_link(client):
    sign_in(client)
    h = _get(client, "/community")
    top = re.search(r'<div class="v2-top">.*?(?=<main)', h, re.S).group(0)      # F-253: the v2 top bar's account is the avatar to /family
    assert 'href="/family"' in top and 'href="/signin' not in top
    assert _hrefs(_tag(h, "footer", "cb-foot")) == ["/privacy", "/terms"]
