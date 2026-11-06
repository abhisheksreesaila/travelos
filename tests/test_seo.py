"""F-196 item 3: public trip pages and For creators carry a description and Open Graph tags; a creator-imported copy tells Google not to index it (the founder's own trips stay
indexable); /robots.txt and /sitemap.xml list what may be found."""

import re
from html import unescape
from html.parser import HTMLParser

import pytest

from gitaway import community
from tests.live_trips import live_trip
from tests.published_support import publish_imported
from tests.test_signin import sign_in


class _Metas(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            self.tags.append(dict(attrs))


def metas(html) -> dict:
    """{name or property: content} of every <meta> in the page."""
    p = _Metas()
    p.feed(html)
    return {t.get("name") or t.get("property"): t.get("content") for t in p.tags if t.get("name") or t.get("property")}


@pytest.fixture
def me(client):
    sign_in(client)
    return client


# ---- the tags ----------------------------------------------------------------------------------------------------------------------------

def test_a_founders_own_trip_has_a_description_and_open_graph_tags_and_stays_indexable(client):
    row, _, _ = live_trip(photo=True)
    m = metas(client.get(f"/trips/{row['slug']}").text)
    assert m["description"] == "Three days from the post."
    assert (m["og:title"], m["og:description"], m["og:type"], m["og:site_name"]) == ("Three easy days in Santa Monica", "Three days from the post.", "article", "GitAway")
    assert m["og:image"] == "https://gitaway.me/assets/photos/venice-beach-los-angeles-hero.jpg"
    assert m["og:url"] == f"https://gitaway.me/trips/{row['slug']}"
    assert "robots" not in m


def test_a_trip_without_a_photo_shows_the_app_mark_as_its_image(client):
    row, _, _ = live_trip(photo=False)
    assert metas(client.get(f"/trips/{row['slug']}").text)["og:image"] == "https://gitaway.me/assets/icons/icon-512.png"


def test_the_address_follows_the_configured_public_url(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_PUBLIC_URL", "https://trips.example.org")
    row, _, _ = live_trip(photo=True)
    m = metas(client.get(f"/trips/{row['slug']}").text)
    assert m["og:image"] == "https://trips.example.org/assets/photos/venice-beach-los-angeles-hero.jpg" and m["og:url"] == f"https://trips.example.org/trips/{row['slug']}"


def test_a_creator_imported_trip_page_says_noindex(me, client):
    slug = publish_imported(me)
    m = metas(client.__class__(client.app).get(f"/trips/{slug}").text)
    assert m["robots"] == "noindex"
    assert m["og:title"] == "Three easy days in Santa Monica" and m["og:type"] == "article"      # it can still be shared with a preview


def test_for_creators_has_a_description_and_open_graph_tags_and_the_google_line(client):
    html = client.get("/for-creators").text
    m = metas(html)
    assert m["description"] == "Paste your blog link, YouTube video or Instagram caption. GitAway drafts the days, you fix what is off, and families can fork your trip into their own plans."
    assert (m["og:title"], m["og:type"], m["og:url"], m["og:image"]) == ("For creators", "website", "https://gitaway.me/for-creators", "https://gitaway.me/assets/icons/icon-512.png")
    assert "robots" not in m
    text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))
    assert "We tell Google not to index this copy, so your post keeps its ranking." in text


def test_other_pages_get_no_extra_tags(client):
    m = metas(client.get("/privacy").text)
    assert not any(k.startswith("og:") or k in ("description", "robots") for k in m)


# ---- robots.txt and the sitemap -------------------------------------------------------------------------------------------------------------

def test_robots_txt_names_the_sitemap_and_keeps_crawlers_out_of_the_private_and_redirecting_paths(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    lines = r.text.splitlines()
    assert "User-agent: *" in lines and "Sitemap: https://gitaway.me/sitemap.xml" in lines
    for path in ("/admin", "/claim/", "/go/", "/creators/import", "/report"):
        assert f"Disallow: {path}" in lines, path
    assert "Disallow: /trips" not in r.text and "Disallow: /trips/" not in r.text      # a crawler must be able to read a trip's noindex


def test_the_sitemap_lists_the_indexable_pages_and_leaves_out_copies_takedowns_and_private_pages(me, client):
    own, _, _ = live_trip()
    copy = publish_imported(me)
    gone, _, _ = live_trip("sam@example.com", "Sam Lee", "A trip that was taken down")
    community.take_down(gone["slug"])
    r = client.__class__(client.app).get("/sitemap.xml")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    urls = re.findall(r"<loc>([^<]+)</loc>", r.text)
    assert urls[:4] == ["https://gitaway.me/", "https://gitaway.me/for-creators", "https://gitaway.me/privacy", "https://gitaway.me/terms"]
    assert f"https://gitaway.me/trips/{own['slug']}" in urls
    assert not any(copy in u or gone["slug"] in u for u in urls)
    assert not any(p in u for u in urls for p in ("/admin", "/claim", "/go/", "/trip/", "/family"))
    assert 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"' in r.text
    assert re.search(rf"<loc>https://gitaway.me/trips/{own['slug']}</loc>\s*<lastmod>\d{{4}}-\d\d-\d\d</lastmod>", r.text)


def test_the_sitemap_with_nothing_published_still_lists_the_static_pages(client):
    urls = re.findall(r"<loc>([^<]+)</loc>", client.get("/sitemap.xml").text)
    assert urls == ["https://gitaway.me/", "https://gitaway.me/for-creators", "https://gitaway.me/privacy", "https://gitaway.me/terms"]


def test_both_files_are_open_signed_out_in_the_live_site_mode(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert client.get("/robots.txt").status_code == 200 and client.get("/sitemap.xml").status_code == 200
