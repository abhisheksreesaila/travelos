"""F-194 (8): the captain can open an unclaimed pre-draft from /admin, fix what the model got wrong and save it, before he sends its claim link. The creator's first look is then his
review, not raw model output. Nothing is public while he does (the draft stays owned by no one); once claimed, only its owner can edit it."""

import re
from html import unescape

import pytest

from gitaway import community, creatorclaim as cc, creatordraft
from tests.creator_import_support import as_post, form_of, with_edits
from tests.test_creator_claim import browser, claim_link, draft, rows, setup, stored  # noqa: F401 - fixtures and helpers of the claim tests
from tests.test_claim_preview import link_of

CAP = "cap@example.com"


def did_of():
    return rows()[0]["draft_id"]


def fields(c, did):
    r = c.get(f"/admin/drafts/{did}")
    assert r.status_code == 200, r.text[:300]
    return form_of(r.text, f"/admin/drafts/{did}", "ci-edit")


def save(c, did, edits, do="save"):
    return c.post(f"/admin/drafts/{did}", data=as_post([*with_edits(fields(c, did), **edits), ("do", do)]), follow_redirects=False)


def test_the_list_of_drafts_links_each_unclaimed_one_to_its_editor(client, setup):
    c = browser(CAP)
    html = draft(c).text
    did = did_of()
    assert f'href="/admin/drafts/{did}"' in html and "Review the draft" in unescape(html)            # in the message block the captain sees right after drafting
    page = c.get("/admin").text
    assert re.search(rf'id="cc-draft-{did}".*?href="/admin/drafts/{did}"', page, re.S)


def test_the_editor_shows_the_drafts_fields_and_says_nobody_can_see_it(client, setup):
    c = browser(CAP)
    draft(c)
    r = c.get(f"/admin/drafts/{did_of()}")
    html = unescape(r.text)
    assert "Check this pre-draft" in html and "Nothing is public. Fix what the model got wrong, then send the claim link." in html
    f = dict(form_of(r.text, f"/admin/drafts/{did_of()}", "ci-edit"))
    assert (f["title"], f["d0s0_name"], f["d0s0_time"]) == ("Three easy days in Santa Monica", "Santa Monica Pier", "10:00 AM")
    assert 'id="ci-pics"' not in html and 'id="ci-delete"' not in html and 'id="pb-unpublish"' not in html and 'name="pick"' not in html      # no pictures to pick, nothing to publish or delete here
    assert 'id="pb-preview"' not in html and 'id="pb-save"' in html


def test_the_captains_edits_are_saved_on_the_draft_and_the_claimer_sees_them(client, setup):
    c = browser(CAP)
    link = link_of(setup)
    did = did_of()
    r = save(c, did, {"title": "Three days in Santa Monica, fixed", "d0s0_name": "Pacific Park", "d0s0_note": "Go before noon", "tip": ["Bring a jacket", "", ""]})
    assert r.status_code == 303 and r.headers["location"] == f"/admin/drafts/{did}"
    f = dict(fields(c, did))
    assert (f["title"], f["d0s0_name"], f["d0s0_note"]) == ("Three days in Santa Monica, fixed", "Pacific Park", "Go before noon")
    seen = unescape(browser("sam").get(link).text)
    assert "Three days in Santa Monica, fixed" in seen and "Pacific Park" in seen and "Go before noon" in seen and "Bring a jacket" in seen
    assert community.rows(kind="scrapbook", hidden=True) == [] and stored("SELECT owner_user FROM creator_drafts")[0][0] == cc.UNCLAIMED


def test_the_claim_link_is_the_same_after_he_edits(client, setup):
    c = browser(CAP)
    link = link_of(setup)
    save(c, did_of(), {"title": "Edited"})
    assert cc.state(link.rsplit("/", 1)[1]) == "ok" and browser("sam").get(link).status_code == 200


def test_the_add_and_remove_buttons_work_here_too(client, setup):
    c = browser(CAP)
    draft(c)
    did = did_of()
    save(c, did, {}, "add_stop:0")
    assert "d0s2_name" in dict(fields(c, did))
    save(c, did, {}, "del_stop:0:0")
    f = dict(fields(c, did))
    assert f["d0s0_name"] == "Third Street Promenade"


def test_an_email_address_in_his_edit_is_refused_like_a_creators(client, setup):
    c = browser(CAP)
    draft(c)
    r = save(c, did_of(), {"tip": ["write me at a@b.co", "", ""]})
    assert r.status_code == 200 and "Take the email address out" in r.text and creatordraft.get(cc.UNCLAIMED, did_of())["tips"] != ["write me at a@b.co"]


def test_only_the_captain_can_open_or_save_it(client, setup):
    draft(browser(CAP))
    did = did_of()
    for who in (None, "sam"):
        c = browser(who)
        assert c.get(f"/admin/drafts/{did}").status_code == 404
        assert c.post(f"/admin/drafts/{did}", data={"title": "x", "do": "save"}).status_code == 404
    cap = browser(CAP)
    assert cap.post(f"/admin/drafts/{did}", data={"title": "x", "do": "save"}, headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}).status_code == 404
    assert creatordraft.get(cc.UNCLAIMED, did)["title"] == "Three easy days in Santa Monica"


def test_a_claimed_draft_is_no_longer_his_to_edit(client, setup):
    link = link_of(setup)
    did = did_of()
    browser("sam").post(link, data={"do": "edit", "confirm": "1"})
    cap = browser(CAP)
    assert cap.get(f"/admin/drafts/{did}").status_code == 404
    assert cap.post(f"/admin/drafts/{did}", data={"title": "mine now", "do": "save"}).status_code == 404
    assert "Review the draft" not in unescape(cap.get("/admin").text)


def test_a_made_up_draft_id_is_a_404(client, setup):
    c = browser(CAP)
    for bad in ("x", "0" * 16, "..%2F..", "%27%20OR%201=1"):
        assert c.get(f"/admin/drafts/{bad}").status_code == 404


def test_the_pre_draft_editor_is_not_the_creators_route(client, setup):
    """Even the captain cannot reach an unclaimed draft through a creator's editor (owner = the signed-in person): the admin route is the one door."""
    c = browser(CAP)
    draft(c)
    assert c.get(f"/creators/import/{did_of()}").status_code == 404
