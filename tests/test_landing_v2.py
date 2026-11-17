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
    """D-458 (founder, 2026-11-13; F-262): the home page introduces, and its header is the way in: Guides, Plan a trip, Sign in."""
    header = _tag(client.get("/").text, "header", "cv-top")       # the signed-out landing is the cover (F-206)
    assert _hrefs(header) == ["/", "/guides", "/plan/ask", "/signin"]      # D-761: Plan a trip opens the ask without an account; Sign in is its own button
    assert header.index("Guides") < header.index("Find a trip")      # F-289


def test_other_pages_wear_the_v2_bar_with_the_same_way_in(client):
    for path in ["/creators", "/guides", "/guides/make", "/privacy"]:       # F-272: every page but the cover wears the v2 top bar, which carries the way in
        top = re.search(r'<div class="v2-top">.*?(?=<main)', _get(client, path), re.S).group(0)
        assert _hrefs(top)[1:3] == ["/plan/ask", "/guides"] and _hrefs(top)[3].startswith("/signin?next="), path      # F-255, D-761: the pill begins with Plan a trip (open to visitors), then Guides; Sign in stays its own button


def test_footer_carries_the_links_that_left_the_header(client):
    footer = _tag(client.get("/").text, "footer", "cv-foot")      # the signed-out landing is the cover (F-206)
    assert [h for h in _hrefs(footer) if h.startswith("/")] == ["/guides", "/signin", "/privacy", "/terms"]   # (and the map data's credit, tests/test_cover.py)
    other = _tag(_get(client, "/guides"), "footer", "cb-foot")      # F-253: the creator pages' foot
    assert _hrefs(other) == ["/privacy", "/terms"]


def test_signed_in_visitor_sees_their_account_and_no_sign_in_link(client):
    sign_in(client)
    h = _get(client, "/community")
    top = re.search(r'<div class="v2-top">.*?(?=<main)', h, re.S).group(0)      # F-253: the v2 top bar's account is the avatar to /family
    assert 'href="/family"' in top and 'href="/signin' not in top
    assert _hrefs(_tag(h, "footer", "cb-foot")) == ["/privacy", "/terms"]
