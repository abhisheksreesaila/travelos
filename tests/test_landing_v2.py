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
    for path in ["/community", "/creators"]:      # F-200: sign-in is a full-screen page with the brand and Cancel only
        header = _tag(_get(client, path), "header", "ga-header")
        assert "/community" in header and "/for-creators" in header and 'href="/signin"' in header, path      # signed out, Plan a trip signs in first, and / then decides (D-458, D-461)


def test_footer_carries_the_links_that_left_the_header(client):
    footer = _tag(client.get("/").text, "footer", "cv-foot")      # the signed-out landing is the cover (F-206)
    assert [h for h in _hrefs(footer) if h.startswith("/")] == ["/community", "/for-creators", "/signin", "/privacy", "/terms"]   # (and the map data's credit, tests/test_cover.py)
    other = _tag(_get(client, "/community"), "footer", "ga-footer")
    assert "/creators" not in other  # only the landing gets the extra links


def test_signed_in_visitor_sees_their_account_and_no_sign_in_link(client):
    sign_in(client)
    h = _get(client, "/community")
    header = _tag(h, "header", "ga-header")
    assert "ga-account" in header and 'href="/family"' in header and "Sign out" in header and 'href="/signin' not in header
    footer = _tag(h, "footer", "ga-footer")
    assert _hrefs(footer) == ["/privacy", "/terms"]
