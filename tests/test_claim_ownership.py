"""F-194 (4): ownership is more than a tick. When the claimer's verified email is not at the post's own site, the trip they claim is published unlisted (reachable by its link, in no
list, not indexable) until the captain approves it on /admin; the open import's "<name> · Blog" byline waits the same way. An email at the site (or a subdomain of it), verified,
needs no one's approval."""

import re
from html import unescape

import pytest

from gitaway import community, creatorclaim as cc, creatordraft
from tests.test_claim_preview import link_of
from tests.test_creator_claim import browser, claim_link, draft, rows, setup  # noqa: F401 - fixtures and helpers of the claim tests
from tests.test_creator_import import model, named, web  # noqa: F401
from tests.test_signin import person, tid

CAP = "cap@example.com"
STRANGER = "kim.lee@gmail.com"            # not at blog.example.com
OWNER = "maya.chen@blog.example.com"      # at it


def claim_and_publish(who, link):
    c = browser(who)
    r = c.post(link, data={"do": "publish", "confirm": "1"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("?live=1"), r.text[:300]
    (row,) = community.rows(kind="scrapbook", hidden=True)
    return c, row


def noindexed(r):
    return r.headers.get("x-robots-tag") == "noindex, nofollow" and re.search(r'<meta[^>]*name="robots"[^>]*content="noindex, nofollow"', r.text) is not None


# ---- who needs no approval --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("email, host, ok", [
    ("maya@blog.example.com", "blog.example.com", True), ("maya@example.com", "blog.example.com", True), ("maya@mail.example.com", "example.com", True), ("Maya@Example.COM", "www.example.com", True),
    ("kim@gmail.com", "blog.example.com", False), ("kim@notexample.com", "example.com", False), ("kim@example.com.evil.org", "example.com", False), ("kim@gmail.com", "", False), ("", "example.com", False),
    ("kim@gmail.com", "youtube.com", False),
])
def test_an_email_is_at_the_site_when_it_is_the_site_or_its_parent_or_child_domain(email, host, ok):
    assert creatordraft.site_matches(email, host) is ok


# ---- a claim: listed at once, or unlisted until approved -----------------------------------------------------------------------

def test_a_claimer_at_the_posts_own_site_is_listed_at_once(client, setup):
    _, row = claim_and_publish(OWNER, link_of(setup))
    assert community.rows(kind="scrapbook") == [row] and community.review_state(row["slug"]) == ""
    page = browser().get(f"/trips/{row['slug']}")
    assert page.status_code == 200 and not noindexed(page) and "Maya Chen · Blog" in unescape(page.text)


def test_a_claimer_elsewhere_publishes_unlisted_and_not_indexable(client, setup):
    _, row = claim_and_publish(STRANGER, link_of(setup))
    assert community.review_state(row["slug"]) == "pending"
    page = browser().get(f"/trips/{row['slug']}")
    assert page.status_code == 200 and noindexed(page)                 # reachable by its link, not indexable


def test_an_unlisted_trip_is_in_no_list(client, setup, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    _, row = claim_and_publish(STRANGER, link_of(setup))
    assert community.rows(kind="scrapbook") == [] and community.real_creators() == [] and not community.has_real() and community.most_forked() is None
    stranger = browser()
    assert row["title"] not in stranger.get("/community").text
    assert "Maya Chen" not in stranger.get("/creators").text and stranger.get("/creators/maya-chen").status_code == 404
    assert "Three easy days in Santa Monica" not in stranger.get("/for-creators").text


def test_the_byline_of_an_unlisted_trip_is_not_a_link_to_a_profile_that_is_not_there(client, setup):
    _, row = claim_and_publish(STRANGER, link_of(setup))
    page = browser().get(f"/trips/{row['slug']}").text
    assert "By Maya Chen" in unescape(re.sub(r"<[^>]+>", "", page)) and "/creators/maya-chen" not in page


def test_an_unverified_email_at_the_site_is_not_enough(client, setup):
    token = link_of(setup).rsplit("/", 1)[1]
    s = person(OWNER)
    s["verified"] = 0                                                   # a Google address Google has not verified
    did = cc.claim(token, s["user_id"], OWNER)
    creatordraft.publish(s, creatordraft.get(s["user_id"], did), True)
    (row,) = community.rows(kind="scrapbook", hidden=True)
    assert community.review_state(row["slug"]) == "pending"


def test_editing_a_pending_trip_keeps_it_pending_and_unpublishing_starts_again(client, setup):
    c, row = claim_and_publish(STRANGER, link_of(setup))
    did = rows()[0]["draft_id"]
    c.post(f"/creators/import/{did}", data={"do": "publish", "own": "1"})
    assert community.review_state(row["slug"]) == "pending"
    c.post(f"/creators/import/{did}", data={"do": "unpublish"})
    assert community.review_state(row["slug"]) == "" and community.get(row["slug"]) is None


# ---- the captain approves --------------------------------------------------------------------------------------------------------

def admin_text(c):
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c.get("/admin").text)))


def test_the_captain_sees_the_pending_claim_with_who_claimed_and_whose_site(client, setup):
    _, row = claim_and_publish(STRANGER, link_of(setup))
    cap = browser(CAP)
    html = cap.get("/admin").text
    text = admin_text(cap)
    assert "Waiting for your approval" in text and "Three easy days in Santa Monica" in text and "claimed by kim.lee@gmail.com" in text and "blog.example.com" in text
    assert "Unlisted until you approve it" in text
    assert re.search(rf'<form[^>]*action="/admin/approve"[^>]*>.*?name="slug" value="{row["slug"]}".*?Approve', html, re.S)
    assert re.search(rf'action="/admin/takedown"', html)


def test_approving_lists_the_trip_and_shows_the_byline(client, setup, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    _, row = claim_and_publish(STRANGER, link_of(setup))
    cap = browser(CAP)
    r = cap.post("/admin/approve", data={"slug": row["slug"]}, follow_redirects=False)
    assert r.status_code == 303
    assert community.review_state(row["slug"]) == "approved" and [x["slug"] for x in community.rows(kind="scrapbook")] == [row["slug"]]
    page = browser().get(f"/trips/{row['slug']}")
    assert page.status_code == 200 and not noindexed(page) and "Maya Chen · Blog" in unescape(page.text)
    assert "Maya Chen" in browser().get("/creators").text
    assert "Waiting for your approval" not in admin_text(cap)


def test_an_approved_trip_stays_approved_when_the_creator_edits_it(client, setup):
    c, row = claim_and_publish(STRANGER, link_of(setup))
    browser(CAP).post("/admin/approve", data={"slug": row["slug"]})
    did = rows()[0]["draft_id"]
    assert c.post(f"/creators/import/{did}", data={"do": "publish", "own": "1"}, follow_redirects=False).status_code == 303
    assert community.review_state(row["slug"]) == "approved" and len(community.rows(kind="scrapbook")) == 1


def test_only_the_captain_can_approve_and_only_from_the_admin_page(client, setup):
    _, row = claim_and_publish(STRANGER, link_of(setup))
    assert browser("sam").post("/admin/approve", data={"slug": row["slug"]}).status_code == 404
    assert browser().post("/admin/approve", data={"slug": row["slug"]}).status_code == 404
    cap = browser(CAP)
    assert cap.post("/admin/approve", data={"slug": row["slug"]}, headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}).status_code == 404
    assert community.review_state(row["slug"]) == "pending"


def test_approving_a_slug_that_is_not_pending_changes_nothing(client, setup):
    assert browser(CAP).post("/admin/approve", data={"slug": "no-such-trip"}, follow_redirects=False).headers["location"] == "/admin"
    assert community.review_state("no-such-trip") == ""


# ---- the open import's byline ----------------------------------------------------------------------------------------------------

POST = "https://blog.example.com/santa-monica-with-kids"


def own_paste(who):
    """`who` pastes the post's link on the import page, fixes the unnamed stop and names themselves "Maya Chen". Returns (their browser, the draft id)."""
    c = browser(who)
    r = c.post("/creators/import", data={"do": "draft", "link": POST}, follow_redirects=False)
    assert r.status_code == 303, r.text[:300]
    did = re.search(r"/creators/import/([0-9a-f]{16})", r.headers["location"]).group(1)
    named(c, did)
    return c, did


def publish_own(who):
    c, did = own_paste(who)
    assert c.post(f"/creators/import/{did}", data={"do": "publish", "own": "1"}, follow_redirects=False).status_code == 303
    (row,) = community.rows(kind="scrapbook")
    return row


def byline(row):
    return re.search(r'class="src-by">([^<]*)<', unescape(browser().get(f"/trips/{row['slug']}").text)).group(1)


def test_an_open_import_by_someone_elsewhere_shows_the_site_not_the_name_until_approved(client, model, web, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAP)
    row = publish_own(STRANGER)
    assert community.review_state(row["slug"]) == "unverified"
    assert byline(row) == "blog.example.com · Blog"                       # the trip is listed (it is the person's own paste), but the byline does not name them yet
    text = admin_text(browser(CAP))
    assert "Byline waits for your approval" in text and "published by kim.lee@gmail.com" in text and "blog.example.com" in text
    assert browser(CAP).post("/admin/approve", data={"slug": row["slug"]}, follow_redirects=False).status_code == 303
    assert byline(row) == "Maya Chen · Blog" and community.review_state(row["slug"]) == "approved"


def test_an_open_import_by_someone_at_the_site_shows_the_name_at_once(client, model, web):
    row = publish_own(OWNER)
    assert community.review_state(row["slug"]) == "" and byline(row) == "Maya Chen · Blog"


def test_the_preview_says_what_the_byline_will_be_and_why(client, model, web):
    c, did = own_paste(STRANGER)
    html = unescape(c.get(f"/creators/import/{did}/preview").text)
    assert re.search(r'class="src-by">([^<]*)<', html).group(1) == "blog.example.com · Blog"
    assert "Its byline shows blog.example.com for now, and your name once the captain has checked that the post is yours." in html
    c, did = own_paste(OWNER)
    html = unescape(c.get(f"/creators/import/{did}/preview").text)
    assert re.search(r'class="src-by">([^<]*)<', html).group(1) == "Maya Chen · Blog" and "the captain has checked" not in html


def test_a_claimer_elsewhere_is_told_before_and_after_that_the_captain_looks_first(client, setup):
    link = link_of(setup)
    sam = browser(STRANGER)
    assert "Your sign-in email is not at blog.example.com, so the captain looks at the trip before it is listed." in unescape(sam.get(link).text)
    sam.post(link, data={"do": "publish", "confirm": "1"})
    did = rows()[0]["draft_id"]
    html = unescape(sam.get(f"/creators/import/{did}?live=1").text)
    assert "It is published but unlisted: only people with its link can see it until the captain approves it." in html and "See it in Community trips" not in html
    assert "Your sign-in email is not at" not in unescape(browser(OWNER).get(link_of_other(setup)).text)


def link_of_other(setup_):
    """A second claim link, for a second post."""
    other = "https://blog.example.com/second"
    from tests.test_creator_claim import more_posts
    more_posts(other)
    return claim_link(draft(browser(CAP), other).text)


def test_forgetting_the_publisher_forgets_the_captains_note_on_their_trip(client, setup):
    import os
    from pathlib import Path

    from tests.test_creator_claim import _load
    _, row = claim_and_publish(STRANGER, link_of(setup))
    plan, _paths = _load("forget_person").community_plan(Path(os.environ["GITAWAY_DATA_DIR"]), tid(STRANGER), STRANGER)
    assert ("the captain's approval of their trips", "trip_review") in [(label, table) for label, _f, table, _w, _p in plan] and row["slug"] in str(plan)


# ---- until the captain looks, the claimer earns nothing from the post --------------------------------------------------------------

def test_a_claimer_elsewhere_has_no_marker_on_flights_until_the_captain_approves(client, setup):
    from gitaway import affiliate
    _, row = claim_and_publish(STRANGER, link_of(setup))
    (creator,) = community.creators_all()
    affiliate.set_marker(creator["owner_user"], "555111")
    assert affiliate.marker_for(creator["handle"]) == ""
    browser(CAP).post("/admin/approve", data={"slug": row["slug"]})
    assert affiliate.marker_for(creator["handle"]) == "555111"


def test_a_claimer_at_the_posts_own_site_has_their_marker_at_once(client, setup):
    from gitaway import affiliate
    claim_and_publish(OWNER, link_of(setup))
    (creator,) = community.creators_all()
    affiliate.set_marker(creator["owner_user"], "555111")
    assert affiliate.marker_for(creator["handle"]) == "555111"
