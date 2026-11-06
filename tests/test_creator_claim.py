"""F-188: the captain drafts a creator's post privately and sends a claim link; the creator signs in, claims it once and publishes. Through the HTTP seam with a fake Claude and a fake web."""

import ast
import hashlib
import importlib.util
import os
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from gitaway import ai, community, creatorclaim as cc, creatordraft, safefetch
from tests.creator_import_support import ANSWER, Model, Web, page, picture
from tests.test_signin import sign_in, tid

ROOT = Path(__file__).resolve().parent.parent
POST = "https://blog.example.com/santa-monica-with-kids"
CAP = "cap@example.com"
KEY = "sk-ant-not-a-real-key-0000"
CLEAN = {**ANSWER, "days": [ANSWER["days"][0], {"stops": [ANSWER["days"][1]["stops"][0]]}]}     # the shared answer minus its made-up "Eiffel Tower", which blocks publishing


@pytest.fixture
def setup(monkeypatch):
    m = Model(CLEAN)
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAP)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", m)
    monkeypatch.setattr(safefetch, "TRANSPORT", Web({POST: page(), "https://blog.example.com/img/cover.jpg": picture(), "https://blog.example.com/img/pier.jpg": picture(),
                                                    "https://blog.example.com/img/canals.jpg": picture("png")}))
    return m


def browser(who=None):
    """A new browser (its own cookies), signed in as `who` when given."""
    from main import app
    c = TestClient(app, client=("127.0.0.1", 50000))
    if who:
        sign_in(c, who)
    return c


def draft(c, link=POST, name="Maya Chen"):
    r = c.post("/admin/draft", data={"link": link, "name": name})
    assert r.status_code == 200, r.text[:300]
    return r


def claim_link(html) -> str:
    """The address in the first message to copy."""
    m = re.search(r"https://gitaway\.me(/claim/[A-Za-z0-9_-]{43})", unescape(html))
    assert m, html[:500]
    return m.group(1)


def rows():
    return cc.listing()


def stored(sql):
    with community.connect() as db:
        return db.conn.execute(text(sql)).fetchall()


class Pages(Web):
    """The fake web where an address nobody listed is a 404, like the real one."""

    def __call__(self, url, ip, timeout, kind):
        if url.endswith("/robots.txt"):
            return super().__call__(url, ip, timeout, kind)
        self.calls.append(url)
        return self.pages.get(url, (404, {"content-type": "text/html"}, b"not found"))


def more_posts(*urls):
    for u in urls:
        safefetch.TRANSPORT.pages[u] = page()


# ---- the token ----------------------------------------------------------------------------------------------------------------

def test_the_link_holds_a_long_random_token_and_the_database_keeps_only_its_hash(client, setup):
    token = claim_link(draft(browser(CAP)).text).rsplit("/", 1)[1]
    assert len(token) == 43                                                    # secrets.token_urlsafe(32): 256 bits
    assert stored("SELECT token_hash FROM creator_claims")[0][0] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in str(stored("SELECT * FROM creator_claims")) + str(stored("SELECT data FROM creator_drafts"))


def test_two_drafts_never_share_a_token(client, setup):
    other = "https://blog.example.com/second"
    more_posts(other)
    c = browser(CAP)
    assert claim_link(draft(c).text) != claim_link(draft(c, other).text)


def test_a_link_lasts_thirty_days_then_expires(client, setup):
    link = claim_link(draft(browser(CAP)).text)
    token = link.rsplit("/", 1)[1]
    assert cc.state(token) == "ok"
    expires = datetime.fromisoformat(stored("SELECT expires_at FROM creator_claims")[0][0])
    assert timedelta(days=29, hours=23) < expires - datetime.now(timezone.utc) <= timedelta(days=30)
    with community.connect() as db:
        db.conn.execute(text("UPDATE creator_claims SET expires_at = :e"), {"e": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(timespec="seconds")})
        db.conn.commit()
    assert cc.state(token) == "expired" and cc.claim(token, "u1") == ""
    r = browser("sam").get(link)
    assert r.status_code == 410 and "This link no longer works" in r.text and "expired" in r.text


def test_a_link_works_once_and_the_second_person_sees_already_claimed(client, setup):
    link = claim_link(draft(browser(CAP)).text)
    sam, kim = browser("sam"), browser("kim@example.com")
    assert sam.post(link, data={"do": "edit", "confirm": "1"}, follow_redirects=False).status_code == 303
    r = kim.get(link)
    assert r.status_code == 410 and "Already claimed" in r.text
    assert kim.post(link, data={"do": "publish", "confirm": "1"}).status_code == 410
    assert [x["state"] for x in rows()] == ["claimed"]
    assert stored("SELECT claimed_by FROM creator_claims")[0][0] == tid("sam")
    assert stored("SELECT owner_user FROM creator_drafts")[0][0] == tid("sam")


def test_the_same_person_coming_back_is_taken_to_their_editor(client, setup):
    link = claim_link(draft(browser(CAP)).text)
    sam = browser("sam")
    sam.post(link, data={"do": "edit", "confirm": "1"})
    r = sam.get(link, follow_redirects=False)
    assert r.status_code == 303 and re.fullmatch(r"/creators/import/[0-9a-f]{16}", r.headers["location"])


def test_two_people_racing_for_one_link_cannot_both_win(client, setup):
    token = claim_link(draft(browser(CAP)).text).rsplit("/", 1)[1]
    assert cc.claim(token, "first") != "" and cc.claim(token, "second") == ""
    assert stored("SELECT claimed_by FROM creator_claims")[0][0] == "first" and stored("SELECT owner_user FROM creator_drafts")[0][0] == "first"


def test_a_revoked_link_stops_working_and_a_new_link_replaces_the_old_one(client, setup):
    c = browser(CAP)
    link = claim_link(draft(c).text)
    did = rows()[0]["draft_id"]
    assert c.post("/admin/revoke", data={"draft_id": did}, follow_redirects=False).status_code == 303
    sam = browser("sam")
    r = sam.get(link)
    assert r.status_code == 410 and "withdrawn" in r.text and rows()[0]["state"] == "revoked"
    fresh = claim_link(c.post("/admin/link", data={"draft_id": did}).text)
    assert fresh != link and sam.get(link).status_code == 404 and sam.get(fresh).status_code == 200      # the old token is gone, the new one works


def test_a_made_up_or_malformed_token_is_a_404(client, setup):
    sam = browser("sam")
    for t in ("x", "A" * 43, "%27%20OR%201=1%20--", "..%2F..%2Fetc%2Fpasswd"):
        assert sam.get(f"/claim/{t}").status_code == 404


def test_a_signed_out_visitor_sees_the_post_as_a_trip_and_is_sent_to_sign_in_only_to_claim(client, setup):      # the preview itself: tests/test_claim_preview.py (F-194)
    link = claim_link(draft(browser(CAP)).text)
    r = browser().get(link, follow_redirects=False)
    assert r.status_code == 200 and f'href="/signin?next={link}&amp;intent=publish"' in r.text
    r = browser().post(link, data={"do": "publish", "confirm": "1"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/signin?next={link}&intent=publish"


# ---- nothing is public before the claim and the publish --------------------------------------------------------------------------

def test_a_drafted_post_is_private_and_belongs_to_no_one(client, setup):
    c = browser(CAP)
    draft(c)
    assert community.rows(kind="scrapbook", hidden=True) == []
    did = rows()[0]["draft_id"]
    assert stored("SELECT owner_user FROM creator_drafts")[0][0] == cc.UNCLAIMED
    assert c.get(f"/creators/import/{did}").status_code == 404                          # not even the captain can open it as a creator
    assert c.post(f"/creators/import/{did}", data={"do": "publish", "own": "1"}).status_code == 404
    assert community.rows(kind="scrapbook", hidden=True) == []


def test_claiming_alone_publishes_nothing(client, setup):
    link = claim_link(draft(browser(CAP)).text)
    browser("sam").post(link, data={"do": "edit", "confirm": "1"})
    assert community.rows(kind="scrapbook", hidden=True) == []
    assert [(r["state"], r["published"]) for r in rows()] == [("claimed", False)]


def test_this_is_my_post_publish_it_claims_and_publishes_in_one_tap_under_their_name(client, setup):
    link = claim_link(draft(browser(CAP)).text)
    sam = browser("sam")
    html = sam.get(link).text
    assert "Maya Chen, your post is ready as a trip" in html and "This is my post — publish it" in html and "Edit first" in html
    assert community.rows(kind="scrapbook", hidden=True) == []                         # looking is not claiming
    r = sam.post(link, data={"do": "publish", "confirm": "1"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("?live=1")
    (row,) = community.rows(kind="scrapbook")
    assert row["owner_user"] == tid("sam") and row["title"] == "Three easy days in Santa Monica"
    assert community.creator_of(tid("sam"))["name"] == "Maya Chen"
    assert [(x["state"], x["published"]) for x in rows()] == [("claimed", True)]
    public = browser().get(f"/trips/{row['slug']}")
    assert public.status_code == 200 and "Santa Monica Pier" in public.text


def test_a_publish_that_cannot_go_ahead_lands_in_their_editor_with_the_sentence(client, setup):
    setup.answer = {**CLEAN, "place": "other", "place_name": ""}
    link = claim_link(draft(browser(CAP)).text)
    sam = browser("sam")
    r = sam.post(link, data={"do": "publish", "confirm": "1"})
    assert r.status_code == 422 and "Say where the trip was." in r.text and community.rows(kind="scrapbook", hidden=True) == []
    assert sam.get(link, follow_redirects=False).status_code == 303                   # it is theirs now: the link leads to the editor


def test_edit_first_opens_the_editor_with_the_draft(client, setup):
    link = claim_link(draft(browser(CAP)).text)
    sam = browser("sam")
    r = sam.post(link, data={"do": "edit", "confirm": "1"}, follow_redirects=False)
    html = sam.get(r.headers["location"]).text
    assert 'value="Three easy days in Santa Monica"' in html and 'value="Maya Chen"' in html


# ---- the captain's side ----------------------------------------------------------------------------------------------------------

def test_the_admin_routes_are_404_for_everyone_else_and_make_nothing(client, setup):
    for who in (browser("sam"), browser()):
        for path, data in (("/admin/draft", {"link": POST}), ("/admin/link", {"draft_id": "x"}), ("/admin/revoke", {"draft_id": "x"})):
            assert who.post(path, data=data).status_code == 404
    assert rows() == [] and setup.requests == []


def test_a_cross_site_post_from_the_captains_browser_is_refused(client, setup):
    r = browser(CAP).post("/admin/draft", data={"link": POST}, headers={"origin": "https://evil.example"})
    assert r.status_code == 404 and rows() == []


def test_the_admin_page_counts_drafts_made_claimed_and_published(client, setup):
    c = browser(CAP)
    other = "https://blog.example.com/second"
    more_posts(other)
    a, b = claim_link(draft(c).text), claim_link(draft(c, other, "Leslie Harvey").text)
    browser("sam").post(a, data={"do": "publish", "confirm": "1"})
    html = c.get("/admin").text
    for i, n in (("cc-made", "2"), ("cc-claimed", "1"), ("cc-published", "1")):
        assert re.search(rf'id="{i}"[^>]*>{n}<', html), i
    assert "1 of 150 creators published from drafts." in html
    assert b.rsplit("/", 1)[1] not in html                                         # a link is shown once, in the answer to the POST, never on the list


def test_the_outreach_message_is_short_warm_personal_and_signed_with_the_captains_first_name(client, setup, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "abhishek.rao@example.com")
    c = browser("abhishek.rao@example.com")
    html = draft(c).text
    link = claim_link(html)
    msg = unescape(re.search(r'<textarea[^>]*id="cc-msg-0"[^>]*>(.*?)</textarea>', html, re.S).group(1)).strip()
    assert msg.startswith("Hi Maya,\n") and 'I loved your post "Three easy days in Santa Monica".' in msg
    assert f"https://gitaway.me{link}" in msg
    for promise in ("under a minute", "Flights pay you", "links back to your post"):
        assert promise in msg
    assert msg.endswith("\n\nAbhishek") and "It is free" in msg and len(msg.split()) < 130
    assert 'data-copy="cc-msg-0"' in html and "GitAway does not send this" in html


def test_outreach_text_is_exactly_this():
    assert cc.outreach("Marcie Cheung", "3 days on Maui", "https://gitaway.me/claim/T", "Sam") == (
        "Hi Marcie,\n\nI loved your post \"3 days on Maui\". I'm Sam, and I'm building GitAway, an app where families fork a trip and plan it together. "
        "I turned your post into a trip so you can see how it looks. Nothing is public until you say so:\n\nhttps://gitaway.me/claim/T\n\nThree promises:\n"
        "1. It takes under a minute: one tap to publish, or edit first.\n2. Flights pay you: Add your Travelpayouts marker and flights booked from your trips carry it, so Aviasales pays you. Stays and things to do support GitAway for now.\n"
        "3. Every trip links back to your post.\n\nIt is free, and you can take it down any time.\n\nSam")


def test_the_csv_gives_the_creators_with_a_priority_first_and_the_person_from_the_brackets():
    people = cc.candidates()
    assert len(people) >= 40 and people[0]["person"] == "Marcie Cheung" and people[0]["example_post_url"].startswith("https://hawaiitravelwithkids.com/")
    prio = [p["priority"].strip() for p in people]
    assert prio == sorted(prio, key=lambda p: p != "A") and prio[0] == "A"
    assert cc.creator_name("Trips With Tykes") == "Trips With Tykes"


def test_ticking_a_row_of_the_list_drafts_it_with_the_name_from_the_csv(client, setup):
    first = cc.candidates()[0]
    more_posts(first["example_post_url"])
    c = browser(CAP)
    r = c.post("/admin/draft", data={"url": first["example_post_url"]})
    assert "for Marcie Cheung" in r.text and [x["name"] for x in rows()] == ["Marcie Cheung"] and cc.candidates()[0]["drafted"] is True
    c.post("/admin/draft", data={"url": "https://example.com/not-in-the-list"})
    assert len(rows()) == 1                                                            # an address that is not in the list is not fetched


def test_a_post_that_is_already_drafted_is_not_drafted_twice(client, setup):
    c = browser(CAP)
    draft(c)
    assert "already drafted" in draft(c).text and len(rows()) == 1 and len(setup.requests) == 1


def test_a_post_that_cannot_be_read_shows_the_sentence_and_makes_nothing(client, setup):
    r = draft(browser(CAP), "ftp://blog.example.com/gone")
    assert 'role="alert"' in r.text and rows() == []


def test_drafting_respects_the_site_wide_daily_ceiling(client, setup, monkeypatch):
    monkeypatch.setenv("GITAWAY_CREATOR_IMPORT_SITE_LIMIT", "1")
    other = "https://blog.example.com/second"
    more_posts(other)
    c = browser(CAP)
    draft(c)
    assert creatordraft.SITE_LIMIT_HIT in unescape(draft(c, other).text) and len(rows()) == 1 and len(setup.requests) == 1


def test_without_a_key_in_production_the_section_says_drafting_is_off_and_drafts_nothing(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAP)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    c = browser(CAP)
    assert "drafting is switched off here" in c.get("/admin").text
    assert "Drafting needs ANTHROPIC_API_KEY" in draft(c).text and rows() == []


def test_on_the_local_showcase_three_demo_drafts_are_seeded_and_claimable_without_a_key(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAP)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    c = browser(CAP)
    assert "made-up sample drafts" in c.get("/admin").text
    assert [r["state"] for r in rows()] == ["waiting"] * 3
    c.get("/admin")
    assert len(rows()) == 3                                                           # once only
    assert browser("sam").get(claim_link(c.post("/admin/link", data={"draft_id": rows()[0]["draft_id"]}).text)).status_code == 200


def test_the_demo_drafts_are_never_seeded_on_the_live_site(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAP)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    browser(CAP).get("/admin")
    assert rows() == []


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _drafting_script():
    """scripts/draft_creators.py as if it ran on the live data folder (it refuses anywhere else: tests/test_draft_creators_script.py): its production folder is this test's."""
    m = _load("draft_creators")
    m.PRODUCTION_DATA_DIR = os.environ["GITAWAY_DATA_DIR"]
    return m


def test_forgetting_a_person_removes_the_claim_they_used(client, setup):
    link = claim_link(draft(browser(CAP)).text)
    browser("sam").post(link, data={"do": "edit", "confirm": "1"})
    plan, _paths = _load("forget_person").community_plan(Path(os.environ["GITAWAY_DATA_DIR"]), tid("sam"), "sam")
    assert "claim links they used" in [p[0] for p in plan]


# ---- the script ------------------------------------------------------------------------------------------------------------------

def test_the_script_without_a_key_explains_and_exits_1(capsys, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert _drafting_script().main([]) == 1
    out = capsys.readouterr().out
    assert "ANTHROPIC_API_KEY must be set" in out and "pixi run dev" in out and rows() == []


def _a_priority():
    return [p["example_post_url"].strip() for p in cc.candidates() if p["priority"].strip() == "A"]


def test_the_script_drafts_every_a_priority_creator_once_and_writes_the_links_to_a_file(client, capsys, monkeypatch, setup):
    blogs = [u for u in _a_priority() if "youtube.com" not in u]
    monkeypatch.setattr(safefetch, "TRANSPORT", Pages({u: page() for u in blogs}))
    out_file = Path(os.environ["GITAWAY_DATA_DIR"]) / "claim-links.csv"
    out_file.unlink(missing_ok=True)
    script = _drafting_script()
    assert script.main([]) == 3                                                       # the one YouTube video in the list cannot be read here: reported, not hidden
    printed = capsys.readouterr().out
    assert f"{len(blogs)} drafted, 0 already had a draft, 1 failed." in printed and printed.count("https://gitaway.me/claim/") == len(blogs) and "FAILED" in printed
    lines = out_file.read_text().splitlines()
    assert lines[0] == "creator,title,post_url,claim_link" and len(lines) == len(blogs) + 1
    assert [r["state"] for r in rows()] == ["waiting"] * len(blogs) and community.rows(kind="scrapbook", hidden=True) == []
    calls = len(setup.requests)
    assert script.main([]) == 3                                                       # again: the drafted ones are skipped and cost nothing
    assert f"0 drafted, {len(blogs)} already had a draft" in capsys.readouterr().out and len(setup.requests) == calls == len(blogs)
    assert oct(out_file.stat().st_mode & 0o777) == "0o600"
    out_file.unlink()


def test_the_script_stops_at_the_site_wide_ceiling(client, capsys, monkeypatch, setup):
    monkeypatch.setattr(safefetch, "TRANSPORT", Pages({u: page() for u in _a_priority()}))
    monkeypatch.setenv("GITAWAY_CREATOR_IMPORT_SITE_LIMIT", "2")
    out_file = Path(os.environ["GITAWAY_DATA_DIR"]) / "claim-links.csv"
    out_file.unlink(missing_ok=True)
    assert _drafting_script().main([]) == 3
    assert "2 drafted, 0 already had a draft, 1 failed." in capsys.readouterr().out and len(rows()) == 2
    out_file.unlink(missing_ok=True)


def test_the_links_file_is_never_committed():
    assert "claim-links.csv" in (ROOT / ".gitignore").read_text().split()
    assert "draft-creators" in (ROOT / "pixi.toml").read_text()


# ---- the event loop (F-182) ------------------------------------------------------------------------------------------------------

def test_the_new_async_handlers_never_do_blocking_work_on_the_loop():
    """The scan of tests/test_event_loop.py aimed at this ticket's page module (which that test also walks): drafting and publishing go through run_in_threadpool."""
    from tests.test_event_loop import BLOCKING, _own_calls
    tree = ast.parse((ROOT / "gitaway" / "pages" / "creatorclaim.py").read_text())
    handlers = [f for f in ast.walk(tree) if isinstance(f, ast.AsyncFunctionDef)]
    assert {f.name for f in handlers} >= {"claim", "draft", "link", "revoke"}
    assert [f"{f.name}: {ast.unparse(c.func)}" for f in handlers for c in _own_calls(f) if BLOCKING.match(ast.unparse(c.func))] == []
    calls = " ".join(ast.unparse(c) for f in handlers for c in _own_calls(f))
    assert "run_in_threadpool(_draft_all" in calls and "run_in_threadpool(cd.publish" in calls


# ---- F-182 fix 2 (L4): the claimer confirms the site, and the captain sees who claimed ---------------------------------------------

def test_the_claim_page_shows_the_posts_domain_and_asks_to_confirm_it_is_their_site(client, setup):
    link = claim_link(draft(browser(CAP)).text)
    html = browser("sam").get(link).text
    assert re.search(r'<input[^>]*type="checkbox"[^>]*name="confirm"[^>]*required', html) or re.search(r'<input[^>]*name="confirm"[^>]*type="checkbox"[^>]*required', html)
    assert re.search(r"This is my site <span[^>]*id=\"cl-domain\"[^>]*>blog\.example\.com</span>", html)


def test_claiming_without_the_confirmation_claims_nothing_and_says_why(client, setup):
    link = claim_link(draft(browser(CAP)).text)
    sam = browser("sam")
    for do in ("publish", "edit"):
        r = sam.post(link, data={"do": do}, follow_redirects=False)
        assert r.status_code == 422 and "Tick the box to say blog.example.com is your site" in unescape(r.text)
    assert [x["state"] for x in rows()] == ["waiting"] and stored("SELECT owner_user FROM creator_drafts")[0][0] == cc.UNCLAIMED
    assert community.rows(kind="scrapbook", hidden=True) == []


def test_the_captain_sees_the_email_of_whoever_claimed_next_to_the_draft(client, setup):
    cap = browser(CAP)
    link = claim_link(draft(cap).text)
    assert "kim@example.com" not in cap.get("/admin").text
    browser("kim@example.com").post(link, data={"do": "edit", "confirm": "1"})
    assert stored("SELECT claimed_email FROM creator_claims")[0][0] == "kim@example.com"
    assert "claimed by kim@example.com" in re.search(r'<li id="cc-draft-[0-9a-f]+" class="cc-draft">.*?</li>', cap.get("/admin").text, re.S).group(0)


def test_forgetting_the_person_who_claimed_removes_their_email_with_the_claim_row(client, setup):
    link = claim_link(draft(browser(CAP)).text)
    browser("sam").post(link, data={"do": "edit", "confirm": "1"})
    plan, _paths = _load("forget_person").community_plan(Path(os.environ["GITAWAY_DATA_DIR"]), tid("sam"), "sam")
    assert any(t == "creator_claims" and "claimed_by" in where for _l, _f, t, where, _p in plan)


def test_the_access_log_never_carries_a_claim_token():
    import logging
    from gitaway import accesslog
    token = "A" * 43
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", f"/claim/{token}?x=1", "1.1", 200), None)
    assert accesslog.Redact().filter(rec) is True
    assert token not in rec.getMessage() and "/claim/[link]?x=1" in rec.getMessage()
    other = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", "/trips/abc", "1.1", 200), None)
    accesslog.Redact().filter(other)
    assert "/trips/abc" in other.getMessage()
