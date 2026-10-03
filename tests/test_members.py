"""F-043: invite family by Gmail. Invites, joining on sign-in and through the link, roles, removal, the last admin, the switcher,
Google-callback joins and a restart. Everything goes through the HTTP seam with the dev sign-in (tests/conftest.py `client`)."""

import re
import uuid
from datetime import timedelta

import pytest
from starlette.testclient import TestClient

from gitaway import members
from tests.test_auth import fake_google, google  # noqa: F401 - the Google fixture and fake
from tests.test_calendar import book
from tests.test_signin import session_data, sign_in, user_id


def addr(tag="sam"):
    """A Gmail-style address nobody else in the run uses: memberships outlive a test, so joiners must be new every time."""
    return f"{tag}.{uuid.uuid4().hex[:8]}@gmail.com"


def browser(client):
    """Another browser on this machine: its own cookie."""
    return TestClient(client.app, client=("127.0.0.1", 50001))


def tenant(client):
    return session_data(client)["tenant_id"]


def invite(client, email, role="editor"):
    """The owner invites `email`; returns the invite dict (with the token the link carries)."""
    r = client.post("/family/invite", data={"email": email, "role": role}, follow_redirects=False)
    assert r.status_code == 303, r.text[:300]
    return next(i for i in members.pending_invites(tenant(client)) if i["email"] == email.lower())


@pytest.fixture
def owner(client):
    """Ari, signed in, with a booked trip (the demo LA week)."""
    book(client)
    return client


# ---- the owner invites -----------------------------------------------------------------------------------------------

def test_the_owner_invites_an_email_and_gets_a_link_to_copy(owner):
    sam = addr()
    inv = invite(owner, sam, "viewer")
    page = owner.get("/family").text
    link = f"http://testserver/join/{inv['token']}"
    assert link in page and sam in page and "Waiting to join" in page
    assert re.search(r'data-copy="%s"' % re.escape(link), page) and "Copy link" in page
    assert inv["role"] == "viewer" and inv["state"] == "pending"


def test_the_invite_form_says_plainly_that_gitaway_sends_no_email_and_each_invite_has_a_share_button(owner):
    sam = addr()
    inv = invite(owner, sam, "editor")
    page = owner.get("/family").text
    assert "GitAway doesn't send email" in page and "share the link yourself" in page
    assert re.search(r'<button[^>]*data-share="%s"[^>]*>Share invite</button>' % re.escape(f"http://testserver/join/{inv['token']}"), page)
    assert f"Sign in with {sam} to see the plan." in page


def test_the_email_is_lowercased_and_gmail_dots_and_plus_tags_are_one_mailbox(owner):
    inv = invite(owner, "Sam.Kim+trips@Gmail.com", "editor")
    assert inv["email"] == "sam.kim+trips@gmail.com"
    assert members.match_key("sam.kim+trips@gmail.com") == members.match_key("SAMKIM@googlemail.com") == "samkim@gmail.com"
    assert members.match_key("a.b@example.com") == "a.b@example.com"  # only Gmail ignores dots


def test_inviting_the_same_address_again_keeps_one_link_and_takes_the_new_role(owner):
    sam = addr()
    first = invite(owner, sam, "viewer")
    again = invite(owner, sam, "editor")
    assert again["token"] == first["token"] and again["role"] == "editor"
    assert len(members.pending_invites(tenant(owner))) == 1


@pytest.mark.parametrize("bad", ["", "nobody", "a@b", "two@@gmail.com"])
def test_a_bad_email_is_refused_on_the_family_page(owner, bad):
    r = owner.post("/family/invite", data={"email": bad, "role": "editor"}, follow_redirects=False)
    assert r.status_code == 409 and 'role="alert"' in r.text and "full email address" in r.text
    assert members.pending_invites(tenant(owner)) == []


def test_only_editor_and_viewer_can_be_invited_and_an_existing_member_cannot(owner):
    r = owner.post("/family/invite", data={"email": addr(), "role": "admin"}, follow_redirects=False)
    assert r.status_code == 409 and "Choose Editor or Viewer" in r.text
    r = owner.post("/family/invite", data={"email": "ari.rivera@example.com", "role": "editor"}, follow_redirects=False)
    assert r.status_code == 409 and "already in your family" in r.text


def test_the_pending_list_is_capped(owner, monkeypatch):
    monkeypatch.setattr(members, "MAX_PENDING", 2)
    invite(owner, addr()), invite(owner, addr())
    r = owner.post("/family/invite", data={"email": addr(), "role": "editor"}, follow_redirects=False)
    assert r.status_code == 409 and "invites are waiting" in r.text


# ---- joining on sign-in ----------------------------------------------------------------------------------------------

def test_the_invited_email_signs_in_joins_the_family_and_sees_its_trips(owner):
    sam = addr()
    invite(owner, sam, "editor")
    other = browser(owner)
    assert sign_in(other, sam, next="/calendar").status_code == 303
    data = session_data(other)
    assert data["tenant_id"] == tenant(owner) and data["tenant_role"] == "editor"
    html = other.get("/calendar?view=days").text
    assert "LA with the kids" in html and "Book a trip first" not in html
    mine = other.get("/family").text
    assert sam in mine and "Role: editor" in mine and "Ari Rivera" in mine
    assert members.pending_invites(tenant(owner)) == []  # the invite was used


def test_the_person_also_keeps_the_family_fh_saas_made_for_them(owner):
    sam = addr()
    invite(owner, sam, "viewer")
    other = browser(owner)
    sign_in(other, sam)
    families = members.families_of(user_id(other))
    assert len(families) == 2 and {f["role"] for f in families} == {"admin", "viewer"}


def test_a_gmail_dot_variant_still_joins(owner):
    invite(owner, "kim.lee@gmail.com", "viewer")
    other = browser(owner)
    sign_in(other, "kimlee@gmail.com")  # the same Gmail mailbox
    assert session_data(other)["tenant_id"] == tenant(owner)


def test_viewers_see_the_calendar_but_the_members_page_has_no_invite_form(owner):
    sam = addr()
    invite(owner, sam, "viewer")
    other = browser(owner)
    sign_in(other, sam)
    page = other.get("/family").text
    assert "fam-invite-form" not in page and "Remove" not in page and "Only a family admin" in page
    assert 'data-role="viewer"' in page


def test_the_family_page_lists_members_with_role_and_joined_date_and_remove(owner):
    sam = addr()
    invite(owner, sam, "editor")
    sign_in(browser(owner), sam)
    page = owner.get("/family").text
    assert page.count('class="fam-member"') == 2 and "Joined " in page
    assert 'data-role="admin"' in page and 'data-role="editor"' in page
    assert page.count('action="/family/remove"') == 2  # the owner can leave (only while another admin remains) and remove the editor
    assert 'action="/family/role"' in page


# ---- the invite link -------------------------------------------------------------------------------------------------

def test_the_link_signs_the_person_in_first_then_joins_them(owner):
    sam = addr()
    inv = invite(owner, sam, "editor")
    other = browser(owner)
    page = other.get(f"/join/{inv['token']}")
    assert page.status_code == 200 and "Ari Rivera's family" in page.text and "Sign in to join" in page.text
    assert members.mask_email(sam) in page.text and sam not in page.text  # the full address is not shown to a stranger
    nxt = f"/join/{inv['token']}"
    assert sign_in(other, sam, next=nxt, intent="join").headers["location"] == nxt
    back = other.get(nxt, follow_redirects=False)
    assert back.status_code == 303 and back.headers["location"] == "/calendar"
    assert session_data(other)["tenant_id"] == tenant(owner)


def test_a_signed_in_person_with_the_right_email_joins_with_one_button(owner):
    sam = addr()
    other = browser(owner)
    sign_in(other, sam)  # signed in before the invite exists: the sign-in hook had nothing to join
    own = tenant(other)
    inv = invite(owner, sam, "editor")
    page = other.get(f"/join/{inv['token']}").text
    assert 'id="join-go"' in page and "Join Ari Rivera" in page
    r = other.post(f"/join/{inv['token']}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/calendar"
    assert session_data(other)["tenant_id"] == tenant(owner) != own
    assert "LA with the kids" in other.get("/calendar?view=days").text


def test_a_token_holder_with_a_different_email_cannot_join(owner, caplog):
    inv = invite(owner, addr(), "editor")
    thief = browser(owner)
    thief_email = addr("thief")
    sign_in(thief, thief_email)
    own = tenant(thief)
    with caplog.at_level("WARNING"):
        page = thief.get(f"/join/{inv['token']}")
        posted = thief.post(f"/join/{inv['token']}", follow_redirects=False)
    assert page.status_code == 403 and "someone else" in page.text
    assert posted.status_code == 403 and "different email" in posted.text
    assert tenant(thief) == own and session_data(thief)["tenant_id"] == own
    assert members.role_in(user_id(thief), tenant(owner)) is None
    assert any("email does not match" in r.message for r in caplog.records)
    assert len(members.pending_invites(tenant(owner))) == 1  # still waiting for the real person


def test_an_unknown_token_is_a_friendly_404(client):
    r = client.get("/join/not-a-real-token")
    assert r.status_code == 404 and "did not work" in r.text


def test_an_expired_invite_does_not_join_or_work_as_a_link(owner, monkeypatch):
    sam = addr()
    inv = invite(owner, sam, "editor")
    monkeypatch.setattr(members, "now", lambda: members.datetime.now(members.timezone.utc) + timedelta(days=members.INVITE_DAYS + 1))
    other = browser(owner)
    sign_in(other, sam)
    assert session_data(other)["tenant_id"] != tenant(owner)
    page = other.get(f"/join/{inv['token']}")
    assert page.status_code == 410 and "expired" in page.text
    assert other.post(f"/join/{inv['token']}", follow_redirects=False).status_code == 410
    assert members.pending_invites(tenant(owner)) == []  # an expired invite is not listed as waiting


def test_a_revoked_invite_does_not_join_or_work_as_a_link(owner):
    sam = addr()
    inv = invite(owner, sam, "editor")
    r = owner.post("/family/invite/revoke", data={"id": inv["id"]}, follow_redirects=False)
    assert r.status_code == 303 and members.pending_invites(tenant(owner)) == []
    other = browser(owner)
    sign_in(other, sam)
    assert session_data(other)["tenant_id"] != tenant(owner)
    page = other.get(f"/join/{inv['token']}")
    assert page.status_code == 410 and "taken back" in page.text


def test_a_used_link_cannot_be_used_by_the_same_person_again_after_they_were_removed(owner):
    sam = addr()
    inv = invite(owner, sam, "editor")
    other = browser(owner)
    sign_in(other, sam)
    owner.post("/family/remove", data={"user": user_id(other)})
    assert other.get(f"/join/{inv['token']}").status_code == 410  # the link was used once; ask for a new invite
    assert members.role_in(user_id(other), tenant(owner)) is None


def test_removed_members_can_be_invited_back(owner):
    sam = addr()
    invite(owner, sam, "editor")
    other = browser(owner)
    sign_in(other, sam)
    owner.post("/family/remove", data={"user": user_id(other)})
    invite(owner, sam, "viewer")
    again = browser(owner)
    sign_in(again, sam)
    assert session_data(again)["tenant_id"] == tenant(owner) and members.role_in(user_id(again), tenant(owner)) == "viewer"


def test_one_family_cannot_revoke_anothers_invite(owner, client):
    inv = invite(owner, addr(), "editor")
    rival = browser(client)
    sign_in(rival, addr("rival"))
    assert rival.post("/family/invite/revoke", data={"id": inv["id"]}, follow_redirects=False).status_code == 303
    assert len(members.pending_invites(tenant(owner))) == 1


# ---- roles, removal and the last admin -------------------------------------------------------------------------------

def test_removing_a_member_ends_their_access_on_their_next_request(owner):
    sam = addr()
    invite(owner, sam, "editor")
    other = browser(owner)
    sign_in(other, sam)
    assert other.get("/calendar?view=days").status_code == 200 and tenant(other) == tenant(owner)
    r = owner.post("/family/remove", data={"user": user_id(other)}, follow_redirects=False)
    assert r.status_code == 303
    assert members.role_in(user_id(other), tenant(owner)) is None
    html = other.get("/calendar?view=days").text  # their next request
    assert "LA with the kids" not in html and "Your calendar starts with a trip" in html
    assert session_data(other)["tenant_id"] != tenant(owner)  # moved to the family they have of their own
    assert other.post("/calendar/activities", data={"id": "a1", "day": "1", "start": "10:00", "end": "11:00", "title": "Sneak in"}, follow_redirects=False).status_code in (303, 409)
    assert "Sneak in" not in owner.get("/calendar?view=days").text
    assert sam not in owner.get("/family").text.split("Waiting to join")[0].split("Who is in")[1]


def test_a_changed_role_takes_effect_on_the_next_request(owner):
    sam = addr()
    invite(owner, sam, "editor")
    other = browser(owner)
    sign_in(other, sam)
    add = {"id": "a1", "day": "1", "start": "10:00", "end": "11:00", "title": "Venice Canals stroll", "kind": "outdoors"}
    assert other.post("/calendar/activities", data=add, follow_redirects=False).status_code == 303
    r = owner.post("/family/role", data={"user": user_id(other), "role": "viewer"}, follow_redirects=False)
    assert r.status_code == 303 and members.role_in(user_id(other), tenant(owner)) == "viewer"
    refused = other.post("/calendar/activities", data={**add, "id": "a2", "title": "Second"}, follow_redirects=False)
    assert refused.status_code == 403
    assert session_data(other)["tenant_role"] == "viewer"  # the cookie's copy follows


def test_an_admin_can_promote_a_member_who_then_invites(owner):
    sam = addr()
    invite(owner, sam, "editor")
    other = browser(owner)
    sign_in(other, sam)
    assert other.post("/family/invite", data={"email": addr(), "role": "viewer"}, follow_redirects=False).status_code == 403
    owner.post("/family/role", data={"user": user_id(other), "role": "admin"})
    assert other.post("/family/invite", data={"email": addr(), "role": "viewer"}, follow_redirects=False).status_code == 303
    assert "Role: admin" in other.get("/family").text


def test_the_last_admin_cannot_remove_themselves_or_be_demoted(owner):
    me = user_id(owner)
    r = owner.post("/family/remove", data={"user": me}, follow_redirects=False)
    assert r.status_code == 409 and "only admin" in r.text
    r = owner.post("/family/role", data={"user": me, "role": "viewer"}, follow_redirects=False)
    assert r.status_code == 409 and "at least one admin" in r.text
    assert members.role_in(me, tenant(owner)) == "admin"


def test_the_owner_can_leave_once_another_admin_exists_and_only_they_can_remove_or_demote_the_owner(owner):
    sam = addr()
    invite(owner, sam, "editor")
    other = browser(owner)
    sign_in(other, sam)
    owner.post("/family/role", data={"user": user_id(other), "role": "admin"})
    assert other.post("/family/remove", data={"user": user_id(owner)}, follow_redirects=False).status_code == 409  # sam cannot remove the owner
    assert "Only the person who made the family" in other.post("/family/role", data={"user": user_id(owner), "role": "viewer"}).text
    assert owner.post("/family/remove", data={"user": user_id(owner)}, follow_redirects=False).status_code == 303
    assert members.role_in(user_id(owner), tenant(other)) is None


def test_a_role_must_be_a_real_role(owner):
    sam = addr()
    invite(owner, sam, "editor")
    sign_in(browser(owner), sam)
    uid = next(m["user_id"] for m in members.members(tenant(owner)) if m["email"] == sam)
    assert owner.post("/family/role", data={"user": uid, "role": "god"}, follow_redirects=False).status_code == 409
    assert members.role_in(uid, tenant(owner)) == "editor"


def test_the_fh_saas_tenant_user_row_follows_the_role(owner):
    from fh_saas.db_tenant import get_or_create_tenant_db
    from sqlalchemy import text
    sam = addr()
    invite(owner, sam, "viewer")
    other = browser(owner)
    sign_in(other, sam)
    uid = user_id(other)

    def local_role():
        db = get_or_create_tenant_db(tenant(owner))
        try:
            row = db.conn.execute(text("SELECT local_role FROM core_tenant_users WHERE id = :u"), {"u": uid}).first()
            return row[0] if row else None
        finally:
            db.conn.close()

    assert local_role() == "viewer"
    owner.post("/family/role", data={"user": uid, "role": "editor"})
    assert local_role() == "editor"


# ---- two families and the switcher -----------------------------------------------------------------------------------

def test_someone_in_two_families_gets_a_switcher_that_changes_the_active_family(owner):
    sam = addr()
    invite(owner, sam, "editor")
    other = browser(owner)
    sign_in(other, sam)
    own = next(f["tenant_id"] for f in members.families_of(user_id(other)) if f["tenant_id"] != tenant(owner))
    page = other.get("/family").text
    assert 'id="fam-switcher"' in page and "Working here" in page and 'action="/family/switch"' in page
    r = other.post("/family/switch", data={"tenant": own}, follow_redirects=False)
    assert r.status_code == 303 and session_data(other)["tenant_id"] == own and session_data(other)["tenant_role"] == "owner"
    assert "Your calendar starts with a trip" in other.get("/calendar?view=days").text
    other.post("/family/switch", data={"tenant": tenant(owner)})
    assert "LA with the kids" in other.get("/calendar?view=days").text


def test_a_family_that_is_not_mine_cannot_be_switched_to(owner, client):
    stranger = browser(client)
    sign_in(stranger, addr("stranger"))
    mine = tenant(stranger)
    stranger.post("/family/switch", data={"tenant": tenant(owner)}, follow_redirects=False)
    assert tenant(stranger) == mine
    assert "LA with the kids" not in stranger.get("/calendar?view=days").text
    stranger.post("/family/switch", data={"tenant": "nonsense"}, follow_redirects=False)
    assert tenant(stranger) == mine


def test_a_forged_tenant_in_the_cookie_is_never_trusted(owner, client):
    """Whatever the cookie says, the family comes from a membership row: a person cannot name a family they are not in."""
    stranger = browser(client)
    sign_in(stranger, addr("forger"))
    mine = tenant(stranger)
    assert members.set_active({"user_id": user_id(stranger)}, tenant(owner)) is False
    assert members.role_in(user_id(stranger), tenant(owner)) is None and mine != tenant(owner)


def test_signing_in_again_lands_in_the_family_last_used(owner):
    sam = addr()
    invite(owner, sam, "editor")
    first = browser(owner)
    sign_in(first, sam)
    again = browser(owner)
    sign_in(again, sam)  # nothing to join the second time
    assert session_data(again)["tenant_id"] == tenant(owner)
    own = next(f["tenant_id"] for f in members.families_of(user_id(first)) if f["tenant_id"] != tenant(owner))
    first.post("/family/switch", data={"tenant": own})
    third = browser(owner)
    sign_in(third, sam)
    assert session_data(third)["tenant_id"] == own


# ---- Google ----------------------------------------------------------------------------------------------------------

def test_a_google_sign_in_joins_the_invited_family(owner, google, monkeypatch):  # noqa: F811
    sam = addr("gina")
    invite(owner, sam, "viewer")
    fake_google(monkeypatch, sam, sub=f"sub-{uuid.uuid4().hex}")
    other = browser(owner)
    other.get("/login?next=/calendar", follow_redirects=False)
    state = session_data(other)["oauth_state"]
    r = other.get(f"/auth/callback?code=c&state={state}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/calendar"
    assert session_data(other)["tenant_id"] == tenant(owner) and session_data(other)["tenant_role"] == "viewer"
    assert "LA with the kids" in other.get("/calendar?view=days").text
    assert members.pending_invites(tenant(owner)) == []


def test_a_google_sign_in_by_someone_not_invited_gets_only_their_own_family(owner, google, monkeypatch):  # noqa: F811
    invite(owner, addr(), "editor")
    other_mail = addr("nobody")
    fake_google(monkeypatch, other_mail, sub=f"sub-{uuid.uuid4().hex}")
    other = browser(owner)
    other.get("/login", follow_redirects=False)
    state = session_data(other)["oauth_state"]
    other.get(f"/auth/callback?code=c&state={state}", follow_redirects=False)
    assert session_data(other)["tenant_id"] != tenant(owner) and session_data(other)["tenant_role"] == "owner"


# ---- a restart -------------------------------------------------------------------------------------------------------

def test_memberships_and_pending_invites_survive_a_restart(owner):
    from tests.test_family_storage import restart
    sam, waiting = addr(), addr("later")
    invite(owner, sam, "editor")
    other = browser(owner)
    sign_in(other, sam)
    pending = invite(owner, waiting, "viewer")
    restart()
    members.forget_tables()
    assert session_data(other)["tenant_id"] == tenant(owner)
    assert "LA with the kids" in other.get("/calendar?view=days").text  # the same cookie, nothing in memory
    assert {m["email"] for m in members.members(tenant(owner))} >= {sam, "ari.rivera@example.com"}
    assert [i["token"] for i in members.pending_invites(tenant(owner))] == [pending["token"]]
    assert owner.get(f"/family").text.count("fam-invite") >= 1
