"""F-196 item 4: a stop can carry one link of the creator's own, limited to booking and affiliate sites (and the creator's own blog). What the model returns is kept only when it is on that
list AND written in the post. The link is drawn rel="sponsored noopener", is editable in the editor, and the page says it is theirs."""

import re
from html import unescape

import pytest

from gitaway import ai, community, creatordraft as cd, importsource, safefetch, stoplinks
from gitaway.hub import HubError
from tests.creator_import_support import Model, Web, as_post, draft_id, form_of, page, with_edits
from tests.pagebody import without_bar
from tests.test_signin import sign_in, tid

POST = "https://blog.example.com/two-days-in-honolulu"
HOTEL = "https://www.booking.com/hotel/us/the-surfjack.html?aid=12345"
TOUR = "https://www.viator.com/tours/Honolulu/Pearl-Harbor/d672-1234P1?pid=P0000&mcid=42383"
OWN = "https://blog.example.com/waikiki-with-kids"
ARTICLE = f"""<!doctype html><html><head><title>Two days in Honolulu with kids</title><meta name="author" content="Maya Chen"></head><body><article><h1>Two days in Honolulu with kids</h1>
<p>We stayed at the <a href="{HOTEL}">Surfjack Hotel</a> for two nights and loved the pool. The next morning we booked the <a href="{TOUR}">Pearl Harbor tour</a> and also read
<a href="{OWN}">our other post</a> about Waikiki with kids and strollers, which has all the beach details you could want.</p>
<p>On day two we spent the entire morning at Hanauma Bay snorkeling with the children, which was their favourite part of the whole trip, followed by shave ice on the way back to the hotel.
We wrote this up the same evening so the details are fresh, and we would go back tomorrow.</p></article></body></html>"""


# ---- the list -------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("url", ["https://www.booking.com/hotel/us/x.html?aid=1", "https://viator.com/tours/x", "http://www.getyourguide.com/a-l1/?partner_id=ABC", "https://www.amazon.com/dp/B0123?tag=maya-20",
                                 "https://amzn.to/3abcDEF", "https://getawaytoday.com/x", "https://www.stay22.com/allez/roam?aid=1", "https://www.expedia.com/Hotels", "https://www.tripadvisor.com/Hotel_Review-x.html",
                                 "https://affiliate.klook.com/redirect?aid=1", "https://BOOKING.COM/x"])
def test_booking_and_affiliate_sites_are_allowed(url):
    assert stoplinks.clean(url) == url


@pytest.mark.parametrize("url", ["https://evilbooking.com/x", "https://booking.com.evil.example/x", "https://example.com/?u=https://booking.com", "http://booking.com@evil.example/x", "https://evil.example@booking.com/x",
                                 "javascript:alert(1)", "ftp://booking.com/x", "//booking.com/x", "booking.com/x", "https://booking.com:8443/x", "https://booking.com/a b", "https://booking.com/x\nSet-Cookie: a=b",
                                 "https://booking.com/?contact=maya@example.com", "https://bücher.booking.com.evil.example/", "https://xn--booking-9qa.com/", "", "  ", None, 42, "https://booking.com/" + "a" * 400],
                         ids=lambda u: str(u)[:20])
def test_anything_else_is_refused(url):
    assert stoplinks.clean(url) == ""


@pytest.mark.parametrize("url", ["https://evil.com\\.booking.com/", "https://booking.com\\.evil.com/", "https://www.booking.com/a\\b", "https://evil.com%5c.booking.com/", "https://evil.com%2f.booking.com/",
                                 "https://a\x00.booking.com/", "https://booking.com/\x7f", "https://user:pw@booking.com/", "https://booking.com:pw@evil.example/", "HTTPS://evil.example\\@booking.com/",
                                 "https://booking.com./..", "https://.booking.com/", "https://www..booking.com/", "https://-booking.com/", "https://evil_.booking.com/", "https://evil.com#.booking.com/",
                                 "https://evil.com?.booking.com/", "http:booking.com", "https:///booking.com", "https://evil.com\t.booking.com/", "data:text/html,booking.com", "file://booking.com/x"],
                         ids=lambda u: repr(u)[:24])
def test_a_trick_that_makes_a_browser_read_another_host_is_refused(url):
    assert stoplinks.clean(url) == ""


@pytest.mark.parametrize("url", ["https://notbooking.com/", "https://booking.com.evil.example/", "https://xn--booking-9qa.com/", "https://evil.example/booking.com", "https://booking-com.evil.example/",
                                 "https://evilviator.com/", "https://sub.evilviator.com/", "https://booking.co/", "https://com/"], ids=lambda u: u[8:28])
def test_a_lookalike_host_is_not_a_listed_one(url):
    assert stoplinks.clean(url) == ""


@pytest.mark.parametrize("url", ["https://BOOKING.com/x", "https://www.Booking.COM/x", "https://a.b.booking.com/x", "http://booking.com:80/x", "https://booking.com:443/x", "https://xn--bcher-kva.booking.com/x"])
def test_the_listed_host_and_its_subdomains_are_allowed_in_any_case(url):
    assert stoplinks.clean(url) == url


def test_a_blogs_own_domain_is_allowed_for_that_creator_only():
    own = stoplinks.own_domain("blog", "https://www.blog.example.com/post")
    assert own == "blog.example.com"
    assert stoplinks.clean(OWN, own) == OWN and stoplinks.clean("https://shop.blog.example.com/x", own) == "https://shop.blog.example.com/x"
    assert stoplinks.clean(OWN) == "" and stoplinks.clean("https://notblog.example.com/x", own) == ""
    assert [stoplinks.own_domain(k, "https://www.youtube.com/watch?v=abc123abc12") for k in ("youtube", "instagram", "text", "")] == ["", "", "", ""]


def test_a_link_from_the_model_is_kept_only_when_it_is_listed_and_written_in_the_post():
    post = f"Stay at [Surfjack]({HOTEL}) and see [more](https://evil.example/phish) or [us]({OWN})."
    assert stoplinks.keep(HOTEL, post) == HOTEL
    assert stoplinks.keep(TOUR, post) == ""                                       # a listed site, but the post never says it
    assert stoplinks.keep("https://evil.example/phish", post) == ""              # in the post, but not a listed site
    assert stoplinks.keep(OWN, post) == "" and stoplinks.keep(OWN, post, "blog.example.com") == OWN
    assert stoplinks.keep(HOTEL.replace("aid=12345", "aid=99999"), post) == ""    # changed by the model


@pytest.mark.parametrize("model_link", [HOTEL[:-2], HOTEL.split("?")[0], HOTEL + "5"], ids=["cut short", "query dropped", "longer"])
def test_a_link_that_is_only_the_front_of_a_longer_address_in_the_post_is_not_kept(model_link):
    post = f"Stay at [Surfjack]({HOTEL}) for two nights."
    assert stoplinks.keep(model_link, post) == ""


@pytest.mark.parametrize("post", [f"[Surfjack]({HOTEL})", f"stay at {HOTEL}", f"stay at {HOTEL}.", f"stay at {HOTEL}, then eat", f'<a href="{HOTEL}">x</a>', f"stay at {HOTEL}\nthen", f"(see {HOTEL}!)", f"'{HOTEL}'"],
                         ids=["markdown", "bare", "full stop", "comma", "quote", "newline", "bang", "apostrophe"])
def test_a_link_written_whole_in_the_post_is_kept(post):
    assert stoplinks.keep(HOTEL, post) == HOTEL


@pytest.mark.parametrize("url", ["https://medium.com/@maya/two-days-in-honolulu", "https://www.medium.com/@maya/x", "https://substack.com/@maya/p/x", "https://wordpress.com/post/x",
                                 "https://github.io/x", "https://www.youtube.com/watch?v=abc123abc12", "https://youtu.be/abc123abc12", "https://www.instagram.com/p/abc/"])
def test_a_shared_host_is_nobodys_own_site(url):
    assert stoplinks.own_domain("blog", url) == ""                  # every link on medium.com would otherwise count as this creator's own


def test_a_blog_on_its_own_corner_of_a_shared_host_keeps_that_corner_only():
    own = stoplinks.own_domain("blog", "https://maya.blogspot.com/2026/01/post.html")
    assert own == "maya.blogspot.com"
    assert stoplinks.clean("https://maya.blogspot.com/x", own) == "https://maya.blogspot.com/x" and stoplinks.clean("https://other.blogspot.com/x", own) == ""


def test_a_stored_trip_is_cleaned_again_when_it_is_read_back():
    import json
    from tests.live_trips import live_trip
    row = live_trip(source_url="https://blog.example.com/post")[0]
    d = json.loads(row["snapshot"])
    stops = d["days"][0]["stops"]
    stops[0]["link"], stops[1]["link"], stops[2]["link"] = "https://evil.example/phish", HOTEL, OWN
    got = community.load(json.dumps(d)).days[0].stops
    assert [s.link for s in got] == ["", HOTEL, OWN]               # a stranger's address that got into a snapshot is not drawn; the allowed ones are


# ---- drafting keeps them ---------------------------------------------------------------------------------------------------------------

def answer(**links):
    stop = lambda name, link="": {"name": name, "time": "", "note": "", "link": link}      # noqa: E731
    return {"title": "Two days in Honolulu", "place": "hi", "place_name": "", "days_count": 2,
            "days": [{"stops": [stop("Surfjack Hotel", links.get("hotel", "")), stop("Pearl Harbor tour", links.get("tour", ""))]}, {"stops": [stop("Hanauma Bay")]}], "tips": [], "stickers": []}


@pytest.fixture
def web(monkeypatch):
    w = Web({POST: page(ARTICLE)})
    monkeypatch.setattr(safefetch, "TRANSPORT", w)
    return w


def model_says(monkeypatch, **links):
    m = Model(answer(**links))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key-0000")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", m)
    return m


def test_a_blog_posts_links_reach_the_model_as_part_of_its_text(web):
    m = importsource.gather(POST)
    assert f"[Surfjack Hotel]({HOTEL})" in m.text and f"[Pearl Harbor tour]({TOUR})" in m.text


def test_the_request_lets_a_stop_carry_a_link_and_says_when(monkeypatch, web, client):
    model = model_says(monkeypatch)
    sign_in(client)
    client.post("/creators/import", data={"do": "draft", "link": POST}, follow_redirects=False)
    (req,) = model.requests
    stop = req["output_config"]["format"]["schema"]["properties"]["days"]["items"]["properties"]["stops"]["items"]
    assert stop["properties"]["link"] == {"type": "string"} and "link" in stop["required"]
    assert "the post itself gives a web address for this stop" in req["system"] and "copy that address exactly" in req["system"]


def test_the_drafts_stops_keep_the_listed_links_the_post_gives_and_drop_the_rest(monkeypatch, web, client):
    model_says(monkeypatch, hotel=HOTEL, tour="https://evil.example/phish")
    sign_in(client)
    r = client.post("/creators/import", data={"do": "draft", "link": POST}, follow_redirects=False)
    d = cd.get(tid(), draft_id(r))
    assert [(s["name"], s["link"]) for day in d["days"] for s in day["stops"]] == [("Surfjack Hotel", HOTEL), ("Pearl Harbor tour", ""), ("Hanauma Bay", "")]


def test_a_model_made_up_link_to_a_listed_site_is_dropped(monkeypatch, web, client):
    model_says(monkeypatch, tour="https://www.viator.com/tours/Honolulu/Made-Up/d1-9999")
    sign_in(client)
    d = cd.get(tid(), draft_id(client.post("/creators/import", data={"do": "draft", "link": POST}, follow_redirects=False)))
    assert [s["link"] for day in d["days"] for s in day["stops"]] == ["", "", ""]


def test_a_blogs_own_link_is_kept_for_a_blog_but_not_for_pasted_text(monkeypatch, web, client):
    model_says(monkeypatch, tour=OWN)
    sign_in(client)
    d = cd.get(tid(), draft_id(client.post("/creators/import", data={"do": "draft", "link": POST}, follow_redirects=False)))
    assert d["days"][0]["stops"][1]["link"] == OWN
    pasted = ARTICLE_TEXT = f"Day 1 Surfjack Hotel, Pearl Harbor tour ({OWN}) and Hanauma Bay. " * 3
    d2 = cd.get(tid(), draft_id(client.post("/creators/import", data={"do": "draft", "text": pasted}, follow_redirects=False)))
    assert [s["link"] for day in d2["days"] for s in day["stops"]] == ["", "", ""] and ARTICLE_TEXT


@pytest.mark.parametrize("state, shown", [("pending", False), ("unverified", False), ("approved", True), ("", True)])
def test_an_old_snapshot_shows_a_link_to_the_posts_own_site_only_when_the_trip_is_checked(state, shown):
    """F-194 re-audit: a snapshot made while a trip waited for the captain may hold an own-site link; it is not drawn until the trip is approved (or has nothing to check)."""
    import json
    from tests.live_trips import live_trip
    row = live_trip(source_url="https://blog.example.com/post")[0]
    d = json.loads(row["snapshot"])
    d["days"][0]["stops"][0]["link"], d["days"][0]["stops"][1]["link"] = HOTEL, OWN
    community.set_review(row["slug"], state)
    assert [s.link for s in community.load(json.dumps(d)).days[0].stops] == [HOTEL, OWN if shown else "", ""]


def test_links_in_notes_tips_and_titles_are_still_stripped(monkeypatch, web, client):
    a = answer(hotel=HOTEL)
    a["days"][0]["stops"][0]["note"] = f"book at {HOTEL}"
    a["tips"] = [f"tip {TOUR}"]
    m = Model(a)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key-0000")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", m)
    sign_in(client)
    d = cd.get(tid(), draft_id(client.post("/creators/import", data={"do": "draft", "link": POST}, follow_redirects=False)))
    assert d["days"][0]["stops"][0]["note"] == "book at" and d["tips"] == ["tip"] and d["days"][0]["stops"][0]["link"] == HOTEL


# ---- the editor and the page -----------------------------------------------------------------------------------------------------------

@pytest.fixture
def drafted(monkeypatch, web, client):
    model_says(monkeypatch, hotel=HOTEL, tour=TOUR)
    sign_in(client)
    r = client.post("/creators/import", data={"do": "draft", "link": POST}, follow_redirects=False)
    return client, draft_id(r)


def fields(client, did):
    return form_of(client.get(f"/creators/import/{did}").text, f"/creators/import/{did}", "ci-edit")


def save(client, did, **edits):
    return client.post(f"/creators/import/{did}", data=as_post([*with_edits(fields(client, did), **edits), ("do", "save")]), follow_redirects=False)


def test_the_editor_shows_each_stops_link_and_a_creator_can_change_it(drafted):
    client, did = drafted
    f = dict(fields(client, did))
    assert (f["d0s0_link"], f["d0s1_link"], f["d1s0_link"]) == (HOTEL, TOUR, "")
    html = client.get(f"/creators/import/{did}").text
    assert 'name="d0s0_link"' in html and 'placeholder="A booking or ticket link (optional)"' in html
    r = save(client, did, d0s0_link="https://www.getyourguide.com/oahu-l1/?partner_id=MAYA", d0s1_link="", d1s0_link=OWN)
    assert r.status_code == 303
    assert [s["link"] for day in cd.get(tid(), did)["days"] for s in day["stops"]] == ["https://www.getyourguide.com/oahu-l1/?partner_id=MAYA", "", OWN]


def test_a_link_that_is_not_on_the_list_is_refused_with_the_reason_and_nothing_else_changes(drafted):
    client, did = drafted
    before = cd.get(tid(), did)
    r = save(client, did, title="Changed title", d0s1_link="https://evil.example/phish")
    assert r.status_code == 200
    text = unescape(r.text)
    assert 'The link on "Pearl Harbor tour" can only go to booking.com, viator.com, getyourguide.com, amazon.com, amzn.to, getawaytoday.com, stay22.com, expedia.com, tripadvisor.com or klook.com, or to your own blog.' in text
    assert cd.get(tid(), did) == before                                           # nothing was stored
    form = dict(form_of(r.text, f"/creators/import/{did}", "ci-edit"))
    assert form["title"] == "Changed title" and form["d0s1_link"] == "https://evil.example/phish"      # and nothing the creator typed is lost from the page


def test_a_link_with_an_email_address_in_it_is_refused(drafted):
    client, did = drafted
    r = save(client, did, d0s0_link="https://www.booking.com/x?contact=maya@example.com")
    assert r.status_code == 200 and 'The link on "Surfjack Hotel"' in unescape(r.text)


def named_publish(client, did):
    assert client.post(f"/creators/import/{did}", data={"do": "publish", "own": "1"}, follow_redirects=False).status_code == 303
    return cd.get(tid(), did)["slug"]


def test_the_public_page_draws_the_link_sponsored_and_says_it_is_the_creators(drafted):
    client, did = drafted
    save(client, did, name="Maya Chen")
    slug = named_publish(client, did)
    html = without_bar(client.__class__(client.app).get(f"/trips/{slug}").text)
    tags = re.findall(r'<a [^>]*class="stop-link"[^>]*>', html)
    assert len(tags) == 2
    one = unescape(tags[0])
    assert f'href="{HOTEL}"' in one and 'rel="sponsored noopener"' in one and 'target="_blank"' in one and "noreferrer" not in one
    assert re.search(r'<a [^>]*class="stop-link"[^>]*>.*?<span>booking\.com</span>', html, re.S) and "<span>viator.com</span>" in html
    assert re.search(r'id="own-links"[^>]*>Links on a stop are Maya Chen&#x27;s own. They may earn them a commission\.<', html) or "Links on a stop are Maya Chen's own. They may earn them a commission." in unescape(html)
    (row,) = community.rows(kind="scrapbook")
    assert [s.link for d in community.trip_of(row).days for s in d.stops] == [HOTEL, TOUR, ""]


def test_a_link_to_the_posts_own_site_is_drawn_only_once_the_captain_has_said_yes(monkeypatch, web, client):
    """F-194 audit: until the captain has checked the post is theirs, a creator's link to "their own" domain is not drawn (a stranger could name any blog as theirs)."""
    model_says(monkeypatch, hotel=HOTEL, tour=TOUR)
    sign_in(client, "kim.lee@gmail.com")                                    # not at blog.example.com
    did = draft_id(client.post("/creators/import", data={"do": "draft", "link": POST}, follow_redirects=False))
    save(client, did, name="Maya Chen", d1s0_link=OWN)
    assert client.post(f"/creators/import/{did}", data={"do": "publish", "own": "1"}, follow_redirects=False).status_code == 303
    slug = cd.get(tid("kim.lee@gmail.com"), did)["slug"]
    assert community.review_state(slug) == "unverified"
    page = lambda: client.__class__(client.app).get(f"/trips/{slug}").text      # noqa: E731
    assert OWN not in unescape(page()) and HOTEL in unescape(page())        # the booking sites stay, the "own" site waits
    assert [s.link for d in community.trip_of(community.get(slug)).days for s in d.stops] == [HOTEL, TOUR, ""]
    assert cd.get(tid("kim.lee@gmail.com"), did)["days"][1]["stops"][0]["link"] == OWN         # the creator's own draft still has it
    assert OWN not in unescape(client.get(f"/creators/import/{did}/preview").text)       # and the preview shows what will be drawn
    assert cd.approve(slug) is True
    assert OWN in unescape(page())
    assert [s.link for d in community.trip_of(community.get(slug)).days for s in d.stops] == [HOTEL, TOUR, OWN]


def test_a_page_without_links_has_no_such_line(client, monkeypatch, web):
    model_says(monkeypatch)
    sign_in(client)
    did = draft_id(client.post("/creators/import", data={"do": "draft", "link": POST}, follow_redirects=False))
    save(client, did, name="Maya Chen")
    slug = named_publish(client, did)
    html = client.__class__(client.app).get(f"/trips/{slug}").text
    assert "own-links" not in html and "stop-link" not in html


def test_the_preview_shows_the_same_links(drafted):
    client, did = drafted
    save(client, did, name="Maya Chen")
    assert HOTEL in unescape(client.get(f"/creators/import/{did}/preview").text)


def test_an_old_snapshot_without_a_link_field_still_loads(client):
    from tests.live_trips import live_trip
    row, _, _ = live_trip()
    assert '"link"' in row["snapshot"] and client.get(f"/trips/{row['slug']}").status_code == 200
    stripped = re.sub(r', "link": ""', "", row["snapshot"])
    assert '"link"' not in stripped and community.load(stripped).days[0].stops[0].link == ""
