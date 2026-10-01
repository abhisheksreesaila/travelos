"""The community hub at /discover (F-022): the list, the filters (plain links), and the way in for published trips."""

import re

import pytest

from gitaway import hub, itineraries
from gitaway.itineraries import Source, safe_href


def titles(html):
    return re.findall(r'class="hub-title">([^<]*)<', html)


def test_the_hub_lists_the_community_and_creator_trips(client):
    html = client.get("/discover").text
    assert "Trips worth forking" in html
    assert [t.replace("&amp;", "&") for t in titles(html)] == [t.title for t in itineraries.ITINERARIES.values()]
    assert 'href="/trips/sun-tacos-and-tide-pools"' in html
    assert "312 forks" in html and "YouTube" in html


def test_discover_is_no_longer_a_placeholder():
    from gitaway.pages import placeholders
    assert "/discover" not in placeholders.PLACEHOLDERS


@pytest.mark.parametrize("query,expected", [
    ("kid=1", {"Sun, tacos & tide pools", "San Diego on a budget"}),
    ("pet=1", {"Sun, tacos & tide pools", "Dog-friendly Big Sur drive"}),
    ("couple=1", {"LA for two, slow mornings"}),
    ("kid=1&pet=1", {"Sun, tacos & tide pools"}),
    ("src=creators", {"Sun, tacos & tide pools", "Dog-friendly Big Sur drive"}),
    ("q=diego", {"San Diego on a budget"}),
])
def test_filters_narrow_the_list_without_javascript(client, query, expected):
    assert {t.replace("&amp;", "&") for t in titles(client.get(f"/discover?{query}").text)} == expected


def test_an_empty_filter_says_so_and_offers_a_way_back(client):
    html = client.get("/discover?couple=1&q=tokyo").text
    assert titles(html) == [] and "No trips match" in html and 'href="/discover"' in html


def test_filter_chips_are_links_that_toggle_and_keep_the_others(client):
    html = client.get("/discover?kid=1").text
    assert re.search(r'<a [^>]*aria-current="true"[^>]*href="/discover"|<a [^>]*href="/discover"[^>]*aria-current="true"', html)  # Kid is on: its link turns it off
    assert 'href="/discover?kid=1&amp;pet=1"' in html       # adds Pet, keeps Kid
    assert 'href="/discover?kid=1&amp;src=creators"' in html


def test_junk_filters_are_ignored_and_escaped(client):
    r = client.get("/discover?kid=<script>&q=%3Cscript%3E&pet=1")
    assert r.status_code == 200 and "<script>" not in r.text and "&lt;script&gt;" in r.text   # the search text is echoed escaped


def test_publish_adds_to_the_signed_in_travelers_hub_only():
    s = {"traveler": "ari"}
    card = hub.publish(s, slug="my-reel", title="Reel trip", place="Tokyo", days=3, author="@me", tags=("kid", "nope"), source="Instagram")
    assert card.tags == ("kid",) and card.source == "Instagram"
    assert hub.cards(s)[-1].slug == "my-reel"
    assert "my-reel" not in [c.slug for c in hub.cards({"traveler": "sam", "hub": s["hub"]})]   # per traveler
    assert "my-reel" not in [c.slug for c in hub.cards({})]
    hub.publish(s, slug="my-reel", title="Renamed", place="Tokyo", days=3, author="@me")
    assert [e["t"] for e in hub.entries(s)] == ["Renamed"]                                    # same slug replaces


def test_publish_refuses_signed_out_bad_slugs_and_a_full_cookie():
    with pytest.raises(hub.HubError):
        hub.publish({}, slug="a", title="T", place="P", days=1, author="x")
    with pytest.raises(hub.HubError):
        hub.publish({"traveler": "ari"}, slug="../x", title="T", place="P", days=1, author="x")
    s = {"traveler": "ari", "pad": "x" * 2600}
    with pytest.raises(hub.HubError):
        hub.publish(s, slug="a", title="T", place="P", days=1, author="x")
    assert "hub" not in s


def test_user_written_hub_text_is_escaped():
    from fasthtml.common import to_xml
    from gitaway.pages import discover
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
