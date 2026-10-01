"""F-043 review fixes: only a verified email joins, the offline cache follows the active family, joining asks before moving someone who
already has trips, and the owner stays an admin."""

import re
import uuid
from html import unescape

import pytest

from gitaway import members
from tests.test_auth import fake_google, google  # noqa: F401
from tests.test_calendar import book
from tests.test_members import addr, browser, invite, tenant
from tests.test_signin import session_data, sign_in, user_id


@pytest.fixture
def owner(client):
    book(client)
    return client


def google_sign_in(client, monkeypatch, email, verified, nxt="/calendar"):
    fake_google(monkeypatch, email, sub=f"sub-{uuid.uuid4().hex}", verified=verified)
    client.get(f"/login?next={nxt}", follow_redirects=False)
    state = session_data(client)["oauth_state"]
    return client.get(f"/auth/callback?code=c&state={state}", follow_redirects=False)


def cache_key(client, path="/community"):
    return re.search(r'<meta name="ga-user" content="([0-9a-f]{10})">', client.get(path).text).group(1)


# ---- 1. only a verified email joins ----------------------------------------------------------------------------------

def test_an_unverified_google_email_does_not_claim_the_invite_and_is_told_why(owner, google, monkeypatch):  # noqa: F811
    mail = addr("gina")
    inv = invite(owner, mail, "editor")
    other = browser(owner)
    r = google_sign_in(other, monkeypatch, mail, verified=False)
    assert r.status_code == 303  # signed in: to a family of their own, not the invited one
    assert session_data(other)["tenant_id"] != tenant(owner) and members.role_in(user_id(other), tenant(owner)) is None
    assert "isn't verified" in unescape(other.get("/calendar").text)
    assert len(members.pending_invites(tenant(owner))) == 1  # still waiting for the real, verified person
    page = other.get(f"/join/{inv['token']}")
    assert page.status_code == 403 and "isn't verified" in unescape(page.text)
    assert other.post(f"/join/{inv['token']}", follow_redirects=False).status_code == 403
    assert members.role_in(user_id(other), tenant(owner)) is None


def test_a_verified_google_email_joins_any_domain(owner, google, monkeypatch):  # noqa: F811
    mail = f"gina@{uuid.uuid4().hex[:8]}.example.com"
    invite(owner, mail, "viewer")
    other = browser(owner)
    google_sign_in(other, monkeypatch, mail, verified=True)
    assert session_data(other)["tenant_id"] == tenant(owner) and session_data(other)["tenant_role"] == "viewer"


def test_a_missing_email_verified_counts_as_unverified(owner, google, monkeypatch):  # noqa: F811
    mail = addr("gina")
    invite(owner, mail, "viewer")
    other = browser(owner)
    google_sign_in(other, monkeypatch, mail, verified=None)
    assert members.role_in(user_id(other), tenant(owner)) is None


def test_the_dev_sign_in_counts_as_verified(owner):
    mail = addr()
    invite(owner, mail, "editor")
    other = browser(owner)
    sign_in(other, mail)
    assert session_data(other)["tenant_id"] == tenant(owner) and session_data(other)["verified"] == 1


def test_an_unverified_person_who_signs_out_and_in_verified_can_use_the_same_invite(owner, google, monkeypatch):  # noqa: F811
    mail = addr("gina")
    invite(owner, mail, "editor")
    other = browser(owner)
    google_sign_in(other, monkeypatch, mail, verified=False)
    other.post("/signout")
    google_sign_in(other, monkeypatch, mail, verified=True)
    assert members.role_in(user_id(other), tenant(owner)) == "editor"


# ---- 2. the offline cache follows the active family ------------------------------------------------------------------

def test_the_cache_key_changes_with_the_active_family(owner):
    mail = addr()
    invite(owner, mail, "editor")
    other = browser(owner)
    sign_in(other, mail)
    in_owners = cache_key(other)
    own = next(f["tenant_id"] for f in members.families_of(user_id(other)) if f["tenant_id"] != tenant(owner))
    other.post("/family/switch", data={"tenant": own})
    in_own = cache_key(other)
    assert in_own != in_owners
    other.post("/family/switch", data={"tenant": tenant(owner)})
    assert cache_key(other) == in_owners  # same person, same family: same key


def test_a_removal_changes_the_cache_key_so_the_other_familys_pages_are_dropped(owner):
    mail = addr()
    invite(owner, mail, "editor")
    other = browser(owner)
    sign_in(other, mail)
    before = cache_key(other)
    owner.post("/family/remove", data={"user": user_id(other)})
    assert cache_key(other) != before


# ---- 3. consent after joining ----------------------------------------------------------------------------------------

def test_a_first_sign_in_joins_and_moves_in_with_a_notice_to_dismiss(owner):
    mail = addr()
    invite(owner, mail, "editor")
    other = browser(owner)
    sign_in(other, mail)
    html = other.get("/calendar?view=days").text
    assert session_data(other)["tenant_id"] == tenant(owner)  # nothing of their own yet: moved in
    assert 'id="ga-note"' in html and "You joined Ari Rivera" in html and 'action="/family/stay"' in html and 'action="/family/switch"' not in html
    other.post("/family/stay", data={"next": "/calendar"})
    assert 'id="ga-note"' not in other.get("/calendar?view=days").text


def test_someone_with_trips_of_their_own_is_asked_before_being_moved(owner):
    mail = addr()
    mine = browser(owner)
    book(mine, mail)  # signed in, with a trip in the family fh-saas made for them
    own = tenant(mine)
    invite(owner, mail, "editor")
    again = browser(owner)
    sign_in(again, mail)
    assert session_data(again)["tenant_id"] == own and members.role_in(user_id(again), tenant(owner)) == "editor"  # joined, but not moved
    html = again.get("/calendar?view=days").text
    assert "You joined Ari Rivera" in html and 'action="/family/switch"' in html and 'action="/family/stay"' in html
    assert "Venice" not in html and 'id="cal-viewer"' not in html
    again.post("/family/switch", data={"tenant": tenant(owner), "next": "/calendar"}, follow_redirects=False)
    assert session_data(again)["tenant_id"] == tenant(owner) and 'id="ga-note"' not in again.get("/calendar?view=days").text


def test_staying_keeps_the_family_they_have_and_the_notice_goes(owner):
    mail = addr()
    mine = browser(owner)
    book(mine, mail)
    own = tenant(mine)
    invite(owner, mail, "viewer")
    again = browser(owner)
    sign_in(again, mail)
    again.post("/family/stay", data={"next": "/calendar"})
    assert session_data(again)["tenant_id"] == own and 'id="ga-note"' not in again.get("/calendar?view=days").text
    assert 'id="fam-switcher"' in again.get("/family").text  # they can still switch from the family page


def test_the_notice_is_only_for_a_family_the_person_is_still_in(owner):
    mail = addr()
    invite(owner, mail, "editor")
    other = browser(owner)
    sign_in(other, mail)
    owner.post("/family/remove", data={"user": user_id(other)})
    assert 'id="ga-note"' not in other.get("/calendar?view=days").text


# ---- 4. the owner stays an admin -------------------------------------------------------------------------------------

def test_the_owner_cannot_demote_themselves_even_with_another_admin(owner):
    mail = addr()
    invite(owner, mail, "editor")
    other = browser(owner)
    sign_in(other, mail)
    owner.post("/family/role", data={"user": user_id(other), "role": "admin"})
    me = user_id(owner)
    r = owner.post("/family/role", data={"user": me, "role": "viewer"}, follow_redirects=False)
    assert r.status_code == 409 and "stays an admin" in r.text
    assert members.role_in(me, tenant(owner)) == "admin"
