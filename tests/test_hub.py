"""The community hub at /community (F-022, F-050): the list, the filters (plain links), and the way in for published trips."""

import re

import pytest

from gitaway import hub, itineraries
from gitaway.itineraries import Source, safe_href


def titles(html):
    return re.findall(r'class="hub-title">([^<]*)<', html)


def test_the_hub_lists_the_community_and_creator_trips(client):
    html = client.get("/community").text
    assert "Community trips" in html
    assert [t.replace("&amp;", "&") for t in titles(html)] == [t.title for t in itineraries.ITINERARIES.values()]
    assert 'href="/trips/sun-tacos-and-tide-pools"' in html
    assert "312 forks" in html and "YouTube" in html


def test_community_is_no_longer_a_placeholder():
    from gitaway.pages import placeholders
    assert "/community" not in placeholders.PLACEHOLDERS


@pytest.mark.parametrize("query,expected", [
    ("kid=1", {"Sun, tacos & tide pools", "San Diego on a budget"}),
    ("pet=1", {"Sun, tacos & tide pools", "Dog-friendly Big Sur drive"}),
    ("couple=1", {"LA for two, slow mornings"}),
    ("kid=1&pet=1", {"Sun, tacos & tide pools"}),
    ("src=creators", {"Sun, tacos & tide pools", "Dog-friendly Big Sur drive"}),
    ("q=diego", {"San Diego on a budget"}),
])
def test_filters_narrow_the_list_without_javascript(client, query, expected):
    assert {t.replace("&amp;", "&") for t in titles(client.get(f"/community?{query}").text)} == expected


def test_an_empty_filter_says_so_and_offers_a_way_back(client):
    html = client.get("/community?couple=1&q=tokyo").text
    assert titles(html) == [] and "No trips match" in html and 'href="/community"' in html


def test_filter_chips_are_links_that_toggle_and_keep_the_others(client):
    html = client.get("/community?kid=1").text
    assert re.search(r'<a [^>]*aria-current="true"[^>]*href="/community"|<a [^>]*href="/community"[^>]*aria-current="true"', html)  # Kid is on: its link turns it off
    assert 'href="/community?kid=1&amp;pet=1"' in html       # adds Pet, keeps Kid
    assert 'href="/community?kid=1&amp;src=creators"' in html


def test_junk_filters_are_ignored_and_escaped(client):
    r = client.get("/community?kid=<script>&q=%3Cscript%3E&pet=1")
    assert r.status_code == 200 and "<script>" not in r.text and "&lt;script&gt;" in r.text   # the search text is echoed escaped


def _publish(session, slug, title="Reel trip", **kw):
    from gitaway import community
    trip = itineraries.Itinerary(slug=slug, title=title, headline=f"{title}:", accent="x", place="Tokyo, Japan", lede="l",
                                 days=[itineraries.Day(1, "DAY 1", "One", "70°F", [itineraries.Stop("9:00 AM", "Walk")])],
                                 tags=[itineraries.Tag("Kid friendly", "sun", "kid")], author="@me",
                                 source=itineraries.Source("@me · Instagram · 3 min", "T", "", ""))
    return community.publish(session, trip, kind="creator", tags=("kid",), **kw)


def test_publish_adds_to_the_hub_and_everyone_sees_it_even_signed_out(client):
    from gitaway import auth
    ari, sam = {}, {}
    auth.sign_in_dev(ari, "ari.rivera@example.com"), auth.sign_in_dev(sam, "sam.kim@example.com")
    _publish(ari, "my-reel")
    card = hub.cards(ari)[-1]
    assert card.slug == "my-reel" and card.tags == ("kid",) and card.source == "Instagram" and card.place == "Tokyo" and card.mine
    assert [c.mine for c in hub.cards(sam) if c.slug == "my-reel"] == [False]
    assert "my-reel" in [c.slug for c in hub.cards({})]                                         # even signed out
    _publish(ari, "my-reel", title="Renamed")
    assert [c.title for c in hub.cards(ari) if c.slug == "my-reel"] == ["Renamed"]              # same slug replaces
    with pytest.raises(hub.HubError):
        _publish(sam, "my-reel")                                                                # not yours to replace


def test_publish_refuses_signed_out_and_empty_titles():
    from gitaway import auth
    with pytest.raises(hub.HubError):
        _publish({}, "a")
    ari = {}
    auth.sign_in_dev(ari, "ari.rivera@example.com")
    with pytest.raises(hub.HubError):
        _publish(ari, "a", title="  ")


def test_user_written_hub_text_is_escaped():
    from fasthtml.common import to_xml
    from gitaway.pages import communitytrips as discover
    html = to_xml(discover.card(hub.HubCard("x", "<script>alert(1)</script>", "<b>P</b>", 2, "<img src=x onerror=1>", ("kid",))))
    assert "<script>" not in html and "<img src=x" not in html and "&lt;script&gt;" in html


def test_source_links_only_allow_http_and_https():
    assert safe_href("https://www.youtube.com/watch?v=1") == "https://www.youtube.com/watch?v=1"
    assert safe_href("http://example.com") == "http://example.com"
    for bad in ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,x", "//evil.example", "/relative", "#", "", None,
                "https://", "ftp://x.y", "https://a b.c", "java\nscript:alert(1)"]:
        assert safe_href(bad) == "", bad


def test_a_bad_source_link_renders_no_link(client, monkeypatch):
    trip = itineraries.get("sun-tacos-and-tide-pools")
    bad = itineraries.Itinerary(**{**trip.__dict__, "source": Source("Evil · YouTube · 1 min", "T", "", "", "javascript:alert(1)")})
    monkeypatch.setitem(itineraries.ITINERARIES, bad.slug, bad)
    html = client.get(f"/trips/{bad.slug}").text
    assert "javascript:" not in html and "Watch the original" not in html


# ---- F-050: "Discover" becomes "Community trips" ----------------------------------------------------------------------

def test_discover_redirects_to_community_and_keeps_the_filters(client):
    r = client.get("/discover?kid=1&q=tokyo", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "/community?kid=1&q=tokyo"
    assert client.get("/discover", follow_redirects=False).headers["location"] == "/community"
    assert client.get("/discover?kid=1").status_code == 200  # followed to the page


def test_the_hub_is_named_community_trips_and_never_discover(client):
    from tests.test_signin import sign_in
    for who in (None, "ari"):
        if who:
            sign_in(client, who)
        for path in ("/", "/community", "/start", "/creators", "/forks", "/family", "/signin"):
            html = client.get(path).text
            assert "Discover" not in html and "discover" not in html.lower().replace("discoverable", ""), path
            assert re.search(r'<nav[^>]*>.*?href="/community"[^>]*>Community trips<', html, re.S), path
    html = client.get("/community").text
    assert "<title>GitAway · Community trips</title>" in html
    assert "<h1>Community trips</h1>" in html


def test_the_page_says_plainly_what_it_is_with_both_calls_to_action(client):
    html = client.get("/community").text
    assert "Trips shared by travelers and creators. Fork one into your calendar." in html
    head = html[:html.index('class="hub-grid"')]  # both are up front, above the trips
    assert re.search(r'<a [^>]*href="/start"[^>]*>(<svg.*?</svg>)?Share yours<', head, re.S)  # no trip yet: start one
    assert re.search(r'<a [^>]*href="/creators"[^>]*>(<svg.*?</svg>)?Turn a link into a trip<', head, re.S)


def test_share_yours_goes_to_the_calendar_share_when_the_traveler_has_a_trip(client):
    from tests.test_trip_import import imported
    imported(client, traveler="ari")
    assert re.search(r'<a [^>]*href="/share"[^>]*>(<svg.*?</svg>)?Share yours<', client.get("/community").text, re.S)


def test_the_filters_keep_working_after_the_rename(client):
    html = client.get("/community?kid=1").text
    assert 'href="/community?kid=1&amp;pet=1"' in html and 'action="/community"' in html
