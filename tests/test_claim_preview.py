"""F-194 (3): a creator who opens a claim link sees their post as a trip straight away, read-only, before anything asks them to sign in; sign-in is asked only to claim. The page is
never indexed or cached, and looking claims nothing."""

import re
from html import unescape

from gitaway import creatorclaim as cc
from tests.test_creator_claim import browser, claim_link, draft, rows, setup  # noqa: F401 - fixtures and helpers of the claim tests

CAP = "cap@example.com"


def link_of(setup_):
    return claim_link(draft(browser(CAP)).text)


def private(r):
    assert "no-store" in r.headers["cache-control"] and r.headers["x-robots-tag"] == "noindex, nofollow"
    assert re.search(r'<meta[^>]*name="robots"[^>]*content="noindex, nofollow"', r.text) or re.search(r'<meta[^>]*content="noindex, nofollow"[^>]*name="robots"', r.text)


def test_a_signed_out_visitor_sees_their_post_as_a_trip_with_no_redirect(client, setup):
    link = link_of(setup)
    r = browser().get(link, follow_redirects=False)
    assert r.status_code == 200
    html = unescape(r.text)
    assert "Maya Chen, your post is ready as a trip" in html and "Santa Monica Pier" in html and "Three easy days in Santa Monica" in html
    assert "Nothing is public until you sign in and publish it, and looking at this page does not claim it." in html


def test_the_preview_asks_to_sign_in_only_to_claim_and_has_no_claim_form(client, setup):
    link = link_of(setup)
    html = browser().get(link).text
    assert re.search(rf'<a[^>]*id="cl-signin"[^>]*href="/signin\?next={re.escape(link)}&amp;intent=publish"|<a[^>]*href="/signin\?next={re.escape(link)}&amp;intent=publish"[^>]*id="cl-signin"', html)
    assert "Sign in to claim it" in html and "You will be asked to confirm that blog.example.com is your site." in unescape(html)
    assert 'name="confirm"' not in html and 'id="cl-publish"' not in html and 'id="cl-edit"' not in html


def test_the_preview_is_never_indexed_or_cached(client, setup):
    private(browser().get(link_of(setup)))


def test_looking_claims_nothing(client, setup):
    link = link_of(setup)
    for _ in range(2):
        browser().get(link)
    assert [r["state"] for r in rows()] == ["waiting"] and cc.state(link.rsplit("/", 1)[1]) == "ok"


def test_signing_in_from_the_preview_comes_back_to_the_claim_page(client, setup):
    link = link_of(setup)
    sam = browser()
    r = sam.post("/signin", data={"email": "sam.kim@example.com", "next": link, "intent": "publish"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == link
    page = sam.get(link).text
    assert 'name="confirm"' in page and 'id="cl-publish"' in page and "cl-signin" not in page


def test_the_signed_in_page_is_just_as_private(client, setup):
    link = link_of(setup)
    private(browser("sam").get(link))


def test_a_link_that_cannot_be_claimed_says_why_signed_out_too_and_is_just_as_private(client, setup):
    link = link_of(setup)
    c = browser(CAP)
    did = rows()[0]["draft_id"]
    gone = browser().get("/claim/" + "A" * 43)
    assert gone.status_code == 404 and "This link does not work" in gone.text
    private(gone)
    c.post("/admin/revoke", data={"draft_id": did})
    r = browser().get(link, follow_redirects=False)
    assert r.status_code == 410 and "withdrawn" in r.text
    private(r)
    fresh = claim_link(c.post("/admin/link", data={"draft_id": did}).text)
    browser("sam").post(fresh, data={"do": "edit", "confirm": "1"})
    r = browser().get(fresh, follow_redirects=False)
    assert r.status_code == 410 and "Already claimed" in r.text
    private(r)


def test_claiming_still_needs_a_sign_in(client, setup):
    link = link_of(setup)
    r = browser().post(link, data={"do": "publish", "confirm": "1"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=") and [x["state"] for x in rows()] == ["waiting"]
