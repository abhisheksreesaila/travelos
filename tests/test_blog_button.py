"""F-191: the "Plan this trip on GitAway" button for a creator's blog: the snippet, the badge file, and who sees the panel, in both showcase modes."""

import re
from html import unescape

import pytest

from gitaway import blogbutton
from tests.live_trips import live_trip
from tests.test_signin import sign_in


@pytest.fixture(params=["1", "0"], ids=["showcase", "live"])
def mode(request, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", request.param)
    return request.param


@pytest.fixture(autouse=True)
def public(monkeypatch):
    monkeypatch.setenv("GITAWAY_PUBLIC_URL", "https://gitaway.me")


def stranger(client):
    return client.__class__(client.app, client=("127.0.0.1", 50000))


def box(html, name, uid="bb"):
    """The text inside a read-only box, as the creator would copy it."""
    return unescape(re.search(rf'<textarea[^>]*id="{uid}-{name}"[^>]*>(.*?)</textarea>', html, re.S).group(1))


# ---- the text ------------------------------------------------------------------------------------------------------

def test_the_snippet_is_one_plain_link_around_one_picture_with_no_script():
    s = blogbutton.html_snippet("three-easy-days-a1b2c3", "maya-chen")
    assert s == ('<a href="https://gitaway.me/trips/three-easy-days-a1b2c3?via=maya-chen" target="_blank" rel="noopener">'
                 '<picture><source media="(prefers-color-scheme: dark)" srcset="https://gitaway.me/badge/plan-this-trip-dark.svg">'
                 '<img src="https://gitaway.me/badge/plan-this-trip.svg" alt="Plan this trip on GitAway" width="248" height="56"></picture></a>')
    assert "<script" not in s and "<iframe" not in s
    assert blogbutton.text_link("three-easy-days-a1b2c3", "maya-chen") == "https://gitaway.me/trips/three-easy-days-a1b2c3?via=maya-chen"


def test_everything_in_the_snippet_is_escaped():
    s = blogbutton.html_snippet('x"><script>alert(1)</script>', 'a&b"c')
    assert s.count("<") == 6 and s.count('"') == 18      # <a> <picture> <source> <img> </picture> </a>: nothing the slug or handle held opened a tag or closed an attribute
    assert 'href="https://gitaway.me/trips/x%22%3E%3Cscript%3Ealert%281%29%3C%2Fscript%3E?via=a%26b%22c"' in s


def test_links_use_the_public_url_setting_and_never_the_request_host(client, monkeypatch, mode):
    monkeypatch.setenv("GITAWAY_PUBLIC_URL", "https://trips.example.org/")
    row, handle, _ = live_trip()
    sign_in(client, "maya@example.com", next="/")
    html = client.get(f"/trips/{row['slug']}", headers={"host": "evil.example.net"}).text
    assert box(html, "link") == f"https://trips.example.org/trips/{row['slug']}?via={handle}"
    assert "evil.example.net" not in box(html, "html")
    monkeypatch.delenv("GITAWAY_PUBLIC_URL")
    assert blogbutton.text_link("s", "h") == "https://gitaway.me/trips/s?via=h"


# ---- the badge -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path,dark", [("/badge/plan-this-trip.svg", False), ("/badge/plan-this-trip-dark.svg", True)])
def test_the_badge_is_a_public_cacheable_svg_with_no_script(client, mode, path, dark):
    r = client.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    assert r.headers["cache-control"] == "public, max-age=86400"
    assert r.headers["etag"] and r.headers["x-content-type-options"] == "nosniff"
    assert "set-cookie" not in r.headers
    assert "Plan this trip on" in r.text and "GitAway" in r.text and "#FF7352" in r.text
    assert ("#1e1a2e" in r.text) is dark
    assert "<script" not in r.text and "href=" not in r.text and "<image" not in r.text
    assert stranger(client).get(path).status_code == 200      # nobody needs to be signed in to see a blog's badge


# ---- who sees the panel --------------------------------------------------------------------------------------------

def test_the_creator_sees_the_panel_on_their_live_trip_and_copies_the_right_text(client, mode):
    row, handle, _ = live_trip()
    sign_in(client, "maya@example.com")
    html = client.get(f"/trips/{row['slug']}").text
    assert "Put this on your blog" in html and 'data-copy="bb-html"' in html and 'data-copy="bb-link"' in html
    assert box(html, "html") == blogbutton.html_snippet(row["slug"], handle)
    assert box(html, "link") == f"https://gitaway.me/trips/{row['slug']}?via={handle}"


def test_nobody_else_sees_the_panel(client, mode):
    row, _, _ = live_trip()
    page = f"/trips/{row['slug']}"
    assert "Put this on your blog" not in stranger(client).get(page).text      # a signed-out reader
    sign_in(client, "sam@example.com")
    live_trip("sam@example.com", "Sam Rivera", "A week in Lisbon")                # another creator, with a trip of their own
    assert "Put this on your blog" not in client.get(page).text
    assert "Put this on your blog" not in client.get(f"/trips/{row['slug']}?via=maya").text


def test_a_taken_down_trip_has_no_panel_for_its_creator(client, mode):
    from gitaway import community
    row, _, _ = live_trip()
    sign_in(client, "maya@example.com")
    assert "Put this on your blog" in client.get(f"/trips/{row['slug']}").text
    community.take_down(row["slug"])
    assert "Put this on your blog" not in client.get(f"/trips/{row['slug']}").text


def test_settings_lists_a_panel_for_each_of_the_creators_live_trips(client, mode):
    a, handle, _ = live_trip()
    sign_in(client, "maya@example.com")
    html = client.get("/creators/settings").text
    assert html.count("Put this on your blog") == 1
    assert box(html, "link", "bb0") == f"https://gitaway.me/trips/{a['slug']}?via={handle}"


def test_settings_for_someone_who_has_not_published_has_no_panel(client, mode):
    sign_in(client, "newcomer@example.com")
    r = client.get("/creators/settings")
    assert r.status_code == 200 and "Put this on your blog" not in r.text
