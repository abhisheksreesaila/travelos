"""F-190 through the HTTP seam: the "Import several posts" box on the import page, the list of a blog's posts to tick, the queue, and the one "My drafts" list. Fake web, fake Claude."""

import re
from html import unescape

import pytest

from gitaway import creatordraft as cd, draftjobs as dj, safefetch
from tests.creator_import_support import Web, page
from tests.test_creator_import import KEY, model  # noqa: F401  (fixture)
from tests.test_signin import sign_in, tid

SITE = "https://blog.example.com"
SLUGS = ["three-days-in-san-diego-with-kids", "disneyland-itinerary-for-toddlers", "my-favourite-pancakes"]
SITEMAP = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join(f"<url><loc>{SITE}/{s}</loc><lastmod>2025-06-0{i + 1}</lastmod></url>" for i, s in enumerate(SLUGS)) + "</urlset>")


@pytest.fixture(autouse=True)
def _clean():
    dj.stop()      # no worker from another test's server may take a job these tests are looking at
    cd.clear()
    dj.clear()
    yield
    cd.clear()
    dj.clear()


@pytest.fixture
def web(monkeypatch):
    pages = {f"{SITE}/sitemap.xml": (200, {"content-type": "application/xml"}, SITEMAP.encode()), **{f"{SITE}/{s}": page() for s in SLUGS}}
    w = Web(pages)
    monkeypatch.setattr(safefetch, "TRANSPORT", w)
    return w


@pytest.fixture
def me(client):
    sign_in(client)
    return client


def text(r):
    return unescape(r.text)


def scan(client, site=SITE):
    return client.post("/creators/drafts/scan", data={"site": site})


def start(client, urls, site=SITE):
    return client.post("/creators/drafts/start", data={"site": site, "url": urls}, follow_redirects=False)


def test_the_import_page_offers_to_import_several_posts(me, model):    # noqa: F811
    html = me.get("/creators/import").text
    assert "Import several posts" in html and 'action="/creators/drafts/scan"' in html and 'href="/creators/drafts"' in html


def test_in_production_without_a_key_there_is_no_batch_box_and_a_scan_says_drafting_is_off(me, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert "Import several posts" not in me.get("/creators/import").text
    r = scan(me)
    assert r.status_code == 422 and cd.NOT_ON in text(r)


def test_signed_out_everything_asks_to_sign_in(client):
    assert client.get("/creators/drafts", follow_redirects=False).status_code == 303
    assert client.get("/creators/drafts/scan", follow_redirects=False).status_code == 303
    assert client.post("/creators/drafts/scan", data={"site": SITE}, follow_redirects=False).status_code == 303
    assert client.post("/creators/drafts/start", data={"site": SITE, "url": [f"{SITE}/a"]}, follow_redirects=False).status_code == 303


def test_pasting_a_blog_address_lists_its_posts_with_dates_and_how_many_drafts_are_left(me, model, web):    # noqa: F811
    r = scan(me)
    t = text(r)
    assert r.status_code == 200 and web.calls == [f"{SITE}/sitemap.xml"]            # one fetch of the sitemap, nothing drafted
    assert [m for m in re.findall(r'class="cdr-t">([^<]+)<', t)] == ["Three days in san diego with kids", "Disneyland itinerary for toddlers", "My favourite pancakes"]
    assert "Jun 1, 2025" in t and "You can have 20 more posts drafted today, up to 20 at a time." in t
    assert re.findall(r'name="url" value="([^"]+)"', t) == [f"{SITE}/{SLUGS[0]}", f"{SITE}/{SLUGS[1]}", f"{SITE}/{SLUGS[2]}"] and 'data-max="20"' in t
    assert model.requests == []


def test_a_blog_with_no_sitemap_or_feed_says_so_and_a_bad_address_is_refused(me, model, monkeypatch):    # noqa: F811
    monkeypatch.setattr(safefetch, "TRANSPORT", Web({f"{SITE}/sitemap.xml": (404, {"content-type": "text/html"}, b""), SITE + "/": page("<html></html>"), SITE + "/feed": (404, {"content-type": "text/html"}, b"")}))
    r = scan(me)
    assert r.status_code == 422 and "could not find a list of posts" in text(r) and 'value="https://blog.example.com"' in r.text
    assert scan(me, "javascript:alert(1)").status_code == 422


def test_ticking_posts_queues_them_and_my_drafts_shows_them_drafting_then_ready(me, model, web):    # noqa: F811
    r = start(me, [f"{SITE}/{SLUGS[0]}", f"{SITE}/{SLUGS[1]}"])
    assert r.status_code == 303 and r.headers["location"] == "/creators/drafts?queued=2"
    assert model.requests == [] and web.calls == []
    t = text(me.get(r.headers["location"]))
    assert "Drafting 2 posts in the background." in t and t.count("Drafting now") + t.count("Waiting") == 2 and 'data-busy="1"' in t
    dj.run_pending()
    t = text(me.get("/creators/drafts"))
    assert 'data-busy="0"' in t and t.count("Ready to check") == 2 and t.count('class="cdr-name"') == 2
    (did, *_) = re.findall(r'href="/creators/import/([0-9a-f]{16})"', t)
    assert me.get(f"/creators/import/{did}").status_code == 200       # each opens in the editor


def test_the_list_part_alone_is_what_the_page_polls(me, model, web):    # noqa: F811
    start(me, [f"{SITE}/{SLUGS[0]}"])
    r = me.get("/creators/drafts?part=1")
    assert r.status_code == 200 and r.text.startswith('<div') and "<html" not in r.text and 'data-busy="1"' in r.text and "A title" not in r.text


def test_only_posts_on_the_scanned_site_are_queued(me, model, web):    # noqa: F811
    r = start(me, ["https://evil.example/trip-guide", "http://169.254.169.254/latest", f"{SITE}/{SLUGS[0]}"])
    assert r.headers["location"] == "/creators/drafts?queued=1"
    assert len(dj.listing(tid())) == 1


def test_a_batch_stops_at_twenty_even_if_more_are_posted(me, model, web):    # noqa: F811
    r = start(me, [f"{SITE}/p{i}" for i in range(30)])
    assert r.headers["location"] == "/creators/drafts?queued=20"
    assert len(dj.listing(tid())) == 20


def test_ticking_nothing_is_a_plain_message_not_a_crash(me, model, web):    # noqa: F811
    r = start(me, [])
    assert r.status_code == 422 and "Tick at least one post" in text(r)
    assert dj.listing(tid()) == []


def test_posts_past_the_daily_limit_are_not_queued_and_the_creator_is_told(me, model, web, monkeypatch):    # noqa: F811
    monkeypatch.setattr(cd, "DAILY_LIMIT", 2)
    r = start(me, [f"{SITE}/{s}" for s in SLUGS])
    assert r.headers["location"] == "/creators/drafts?queued=2&hit=person"
    t = text(me.get(r.headers["location"]))
    assert cd.LIMIT_HIT in t and "Drafting 2 posts in the background." in t and 'id="cdr-hit"' in t
    assert "You can have 0 more posts drafted today. Come back tomorrow, or write one yourself." in t
    assert re.search(r'data-max="0"', text(scan(me))) and 'disabled' in scan(me).text


def test_a_post_that_failed_is_listed_with_why_and_can_be_removed(me, model, web):    # noqa: F811
    web.pages[f"{SITE}/{SLUGS[0]}"] = (404, {"content-type": "text/html"}, b"")
    start(me, [f"{SITE}/{SLUGS[0]}", f"{SITE}/{SLUGS[1]}"])
    dj.run_pending()
    t = text(me.get("/creators/drafts"))
    assert "Could not draft" in t and "That website would not let GitAway read the page." in t and t.count("Ready to check") == 1
    (jid,) = [r["id"] for r in dj.listing(tid()) if r["status"] == "failed"]
    r = me.post(f"/creators/drafts/{jid}", data={"do": "delete"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/creators/drafts"
    assert "Could not draft" not in text(me.get("/creators/drafts"))


def test_a_draft_is_deleted_from_the_list_and_nobody_else_can_delete_it(me, model, web, client):    # noqa: F811
    start(me, [f"{SITE}/{SLUGS[0]}"])
    dj.run_pending()
    (row,) = dj.listing(tid())
    other = type(client)(client.app)
    sign_in(other, "sam")
    other.post(f"/creators/drafts/{row['id']}", data={"do": "delete"})
    assert len(dj.listing(tid())) == 1 and dj.listing(tid("sam")) == []
    me.post(f"/creators/drafts/{row['id']}", data={"do": "delete"})
    assert dj.listing(tid()) == [] and cd.get(tid(), row["id"]) is None


def test_every_draft_is_on_the_one_list_whoever_or_however_it_was_made(me, model, web):    # noqa: F811
    r = me.post("/creators/import", data={"do": "manual", "text": "my own words"}, follow_redirects=False)
    did = r.headers["location"].rsplit("/", 1)[1]
    cd._store(tid(), cd.get(tid(), did), published_by=tid())
    t = text(me.get("/creators/drafts"))
    assert "Published" in t and f'href="/creators/import/{did}"' in t and "Untitled draft" in t


def test_an_empty_list_points_to_both_ways_to_start(me):
    t = text(me.get("/creators/drafts"))
    assert "No drafts yet" in t and 'href="/creators/import"' in t and 'href="/creators/drafts/scan"' in t


def test_in_the_showcase_without_a_key_scanning_and_drafting_use_fixtures_and_fetch_nothing(me, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(safefetch, "TRANSPORT", lambda *a: pytest.fail("fetched"))
    r = scan(me, "https://anyblog.example.org")
    urls = re.findall(r'name="url" value="([^"]+)"', r.text)
    assert r.status_code == 200 and len(urls) == 6 and all(u.startswith("https://anyblog.example.org/") for u in urls)
    start(me, urls[:2], site="https://anyblog.example.org")
    dj.run_pending()
    assert [r["status"] for r in dj.listing(tid())] == ["ready", "ready"]


def test_reading_blogs_is_limited_per_person_per_day(me, model, web, monkeypatch):    # noqa: F811
    monkeypatch.setattr(dj, "SCAN_LIMIT", 2)
    assert [scan(me).status_code for _ in range(3)] == [200, 200, 422]
    assert "most for one day" in text(scan(me))
    assert web.calls.count(f"{SITE}/sitemap.xml") == 2          # the refused ones fetched nothing
