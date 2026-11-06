"""F-190: a creator pastes their blog's address and GitAway lists its trip-like posts (gitaway/blogscan.py). The web is the fake one (`safefetch.TRANSPORT`): nothing here reaches the network."""

import pytest

from gitaway import blogscan, safefetch
from tests.creator_import_support import Web, page

SITE = "https://blog.example.com"
GONE = (404, {"content-type": "text/html"}, b"")


def xml(body, kind="application/xml"):
    return 200, {"content-type": f"{kind}; charset=utf-8"}, body.encode()


def urlset(*entries):
    rows = "".join(f"<url><loc>{u}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>" for u, d in entries)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'


SITEMAP = urlset((f"{SITE}/", ""), (f"{SITE}/about", "2024-01-01"), (f"{SITE}/three-days-in-san-diego-with-kids", "2025-06-03T10:00:00+00:00"),
                 (f"{SITE}/my-favourite-pancakes", "2025-02-01"), (f"{SITE}/disneyland-itinerary-for-toddlers", "2025-08-20"), ("https://evil.example/three-days-in-paris", "2025-09-09"),
                 (f"{SITE}/category/travel", ""), (f"{SITE}/privacy-policy", ""), (f"{SITE}/photo.jpg", ""))


@pytest.fixture
def web(monkeypatch):
    def make(pages):
        w = Web(pages)
        monkeypatch.setattr(safefetch, "TRANSPORT", w)
        return w
    return make


def test_a_sitemap_lists_the_same_site_posts_best_trip_first_with_titles_and_dates(web):
    web({f"{SITE}/sitemap.xml": xml(SITEMAP)})
    posts = blogscan.discover(SITE)
    assert [(p.url, p.title, p.date) for p in posts] == [
        (f"{SITE}/three-days-in-san-diego-with-kids", "Three days in san diego with kids", "2025-06-03"),
        (f"{SITE}/disneyland-itinerary-for-toddlers", "Disneyland itinerary for toddlers", "2025-08-20"),
        (f"{SITE}/my-favourite-pancakes", "My favourite pancakes", "2025-02-01"),
    ]       # not the home page, about, category, privacy, a picture, or another site's post


def test_a_sitemap_index_is_followed_one_level_and_no_deeper(web):
    index = f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>{SITE}/post-sitemap.xml</loc></sitemap><sitemap><loc>{SITE}/page-sitemap.xml</loc></sitemap></sitemapindex>'
    deeper = f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>{SITE}/too-deep.xml</loc></sitemap></sitemapindex>'
    w = web({f"{SITE}/sitemap.xml": xml(index), f"{SITE}/post-sitemap.xml": xml(urlset((f"{SITE}/a-weekend-itinerary-in-maui", "2025-01-01"))),
             f"{SITE}/page-sitemap.xml": xml(deeper), f"{SITE}/too-deep.xml": xml(urlset((f"{SITE}/never-read-trip-guide", "")))})
    assert [p.url for p in blogscan.discover(SITE)] == [f"{SITE}/a-weekend-itinerary-in-maui"]
    assert f"{SITE}/too-deep.xml" not in w.calls


def test_a_sitemap_index_naming_other_sites_is_not_followed_there(web):
    index = '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://evil.example/sitemap.xml</loc></sitemap></sitemapindex>'
    w = web({f"{SITE}/sitemap.xml": xml(index), SITE + "/": page("<html></html>"), SITE + "/feed": GONE})
    with pytest.raises(blogscan.ScanError):
        blogscan.discover(SITE)
    assert "https://evil.example/sitemap.xml" not in w.calls


def test_at_most_2000_urls_are_read_from_a_sitemap(web):
    web({f"{SITE}/sitemap.xml": xml(urlset(*[(f"{SITE}/post-{i}-trip", "") for i in range(2600)]))})
    assert len(blogscan.read_sitemaps(SITE)) == 2000


def test_no_more_than_fifty_posts_are_offered(web):
    web({f"{SITE}/sitemap.xml": xml(urlset(*[(f"{SITE}/post-{i}-trip", "") for i in range(120)]))})
    assert len(blogscan.discover(SITE)) == 50


RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Blog</title>
<item><title>Our 4-day Hawaii itinerary</title><link>https://blog.example.com/hawaii</link><pubDate>Tue, 03 Jun 2025 10:00:00 +0000</pubDate></item>
<item><title>Why I quit coffee</title><link>https://blog.example.com/coffee</link><pubDate>Mon, 02 Jun 2025 10:00:00 +0000</pubDate></item>
<item><title>Elsewhere</title><link>https://other.example/trip-guide</link></item></channel></rss>"""
ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Blog</title>
<entry><title>Things to do in Lake Tahoe with kids</title><link rel="alternate" href="https://blog.example.com/tahoe"/><link rel="edit" href="https://blog.example.com/edit/1"/><published>2025-07-04T09:00:00Z</published></entry></feed>"""
HOME = '<html><head><link rel="alternate" type="application/rss+xml" title="feed" href="/feed.xml"><link rel="stylesheet" href="/x.css"></head><body></body></html>'


def test_with_no_sitemap_the_feed_found_on_the_home_page_is_read(web):
    web({f"{SITE}/sitemap.xml": GONE, SITE + "/": page(HOME), f"{SITE}/feed.xml": xml(RSS, "application/rss+xml")})
    posts = blogscan.discover(SITE)
    assert [(p.url, p.title, p.date) for p in posts] == [(f"{SITE}/hawaii", "Our 4-day Hawaii itinerary", "2025-06-03"), (f"{SITE}/coffee", "Why I quit coffee", "2025-06-02")]


def test_an_atom_feed_works_too(web):
    web({f"{SITE}/sitemap.xml": GONE, SITE + "/": page('<link rel="alternate" type="application/atom+xml" href="https://blog.example.com/atom">'), f"{SITE}/atom": xml(ATOM, "application/atom+xml")})
    assert [(p.url, p.title, p.date) for p in blogscan.discover(SITE)] == [(f"{SITE}/tahoe", "Things to do in Lake Tahoe with kids", "2025-07-04")]


def test_a_site_with_neither_says_so_in_a_plain_sentence(web):
    web({f"{SITE}/sitemap.xml": GONE, SITE + "/": page("<html><body>hi</body></html>"), SITE + "/feed": GONE})
    with pytest.raises(blogscan.ScanError) as e:
        blogscan.discover(SITE)
    assert str(e.value) == blogscan.NONE_FOUND


@pytest.mark.parametrize("bad", ["", "ftp://blog.example.com", "not a link", "javascript:alert(1)"])
def test_a_bad_address_is_refused_before_anything_is_fetched(web, bad):
    w = web({})
    with pytest.raises(blogscan.ScanError):
        blogscan.discover(bad)
    assert w.calls == []


def test_an_address_inside_our_network_is_refused_by_the_safe_fetcher(monkeypatch):
    monkeypatch.setattr(safefetch, "RESOLVER", lambda host: ["127.0.0.1"])
    monkeypatch.setattr(safefetch, "TRANSPORT", lambda *a: pytest.fail("fetched"))
    with pytest.raises(blogscan.ScanError) as e:
        blogscan.discover("https://sneaky.example.com")
    assert str(e.value) == blogscan.NONE_FOUND


BILLION = '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;"><!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]><urlset><url><loc>&lol3;</loc></url></urlset>'
EXTERNAL = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>&xxe;</loc></url></urlset>'


@pytest.mark.parametrize("evil", [BILLION, EXTERNAL, "<urlset><url><loc>unclosed", "not xml at all"])
def test_malicious_or_broken_xml_is_never_expanded_and_never_crashes(web, evil):
    web({f"{SITE}/sitemap.xml": xml(evil), SITE + "/": page("<html></html>"), SITE + "/feed": GONE})
    with pytest.raises(blogscan.ScanError) as e:
        blogscan.discover(SITE)
    assert str(e.value) == blogscan.NONE_FOUND


def test_a_poisoned_sitemap_falls_back_to_the_feed(web):
    web({f"{SITE}/sitemap.xml": xml(BILLION), SITE + "/": page(HOME), f"{SITE}/feed.xml": xml(RSS, "application/rss+xml")})
    assert [p.url for p in blogscan.discover(SITE)] == [f"{SITE}/hawaii", f"{SITE}/coffee"]


@pytest.mark.parametrize("url,same", [("https://blog.example.com/a", True), ("https://www.blog.example.com/a", True), ("http://BLOG.example.com/a", True),
                                      ("https://blog.example.com.evil.example/a", False), ("https://evil.example/blog.example.com", False),
                                      ("https://user@blog.example.com/a", False), ("ftp://blog.example.com/a", False), ("//blog.example.com/a", False)])
def test_the_same_site_filter(url, same):
    assert blogscan.same_site(url, "blog.example.com") is same


def test_ranking_puts_trip_words_and_place_names_first_and_drops_non_posts():
    def s(path):
        return blogscan.score(f"https://b.example.com{path}", "")
    assert s("/about") < 0 and s("/tag/travel") < 0 and s("/contact-us") < 0
    assert s("/cooking-pancakes") == 0
    assert s("/three-day-yosemite-itinerary") > s("/cooking-pancakes") and s("/things-to-do-in-honolulu-with-kids") > s("/cooking-pancakes")
    assert s("/best-trip-guide-new-york-city") > s("/trip-notes")


def test_a_real_feed_title_counts_for_ranking():
    assert blogscan.score("https://b.example.com/p/123", "Our 4-day Hawaii itinerary") > blogscan.score("https://b.example.com/p/123", "Why I quit coffee")


def test_the_title_comes_from_the_last_part_of_the_address():
    assert blogscan.title_from_url("https://b.example.com/2025/06/three-days-in-san-diego/") == "Three days in san diego"
    assert blogscan.title_from_url("https://b.example.com/p/12345.html") == "12345"
