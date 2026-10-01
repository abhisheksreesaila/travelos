"""F-039: fh-saas sign-in. The dev sign-in's guards, the family tenant, Google through fh-saas, logout and the public pages."""

import os
from urllib.parse import parse_qs, urlsplit

import pytest
from fh_saas.db_host import HostDatabase
from starlette.testclient import TestClient

from gitaway import auth, session as ses
from tests.test_signin import EMAILS, session_data, sign_in, tid

PUBLIC = ["/", "/discover", "/plan", "/start", "/creators", "/signin", "/trips/sun-tacos-and-tide-pools"]


def memberships(user_id):
    return HostDatabase.from_env().memberships(where="user_id = :u", where_args={"u": user_id})


@pytest.fixture
def remote_client():
    """A client the server sees as another machine."""
    from main import app
    return TestClient(app, client=("203.0.113.9", 4000))


# ---- storage ---------------------------------------------------------------------------------------------------------

def test_data_files_live_in_the_configured_data_folder(client):
    sign_in(client, "files.check@example.com")
    folder = auth.data_dir()
    assert str(folder) == os.environ["GITAWAY_DATA_DIR"] and os.getcwd() == str(folder)
    names = os.listdir(folder)
    assert "app_host.db" in names and any(n.endswith("_db.db") for n in names)


def test_the_data_folder_defaults_under_the_project_and_relative_values_resolve_there(monkeypatch):
    monkeypatch.delenv("GITAWAY_DATA_DIR")
    assert auth.data_dir() == auth.ROOT / "data" / "db"
    monkeypatch.setenv("GITAWAY_DATA_DIR", "elsewhere/db")
    assert auth.data_dir() == auth.ROOT / "elsewhere" / "db"


def test_the_host_database_is_sqlite(client):
    assert os.environ["DB_TYPE"] == "SQLITE" and HostDatabase.from_env().engine.dialect.name == "sqlite"


# ---- the dev sign-in -------------------------------------------------------------------------------------------------

def test_dev_sign_in_makes_the_person_and_their_family_once(client):
    r = sign_in(client, "first.timer@example.com", next="/family")
    assert r.status_code == 303 and r.headers["location"] == "/family"
    data = session_data(client)
    assert data["email"] == "first.timer@example.com" and data["tenant_id"] and data["tenant_role"] == "owner"
    (m,) = memberships(data["user_id"])
    assert m.tenant_id == data["tenant_id"] and m.role == "owner"
    again = TestClient(client.app, client=("127.0.0.1", 1))
    sign_in(again, "first.timer@example.com")  # another browser, same person
    assert session_data(again)["user_id"] == data["user_id"] and session_data(again)["tenant_id"] == data["tenant_id"]
    assert len(memberships(data["user_id"])) == 1


def test_the_session_is_the_one_the_google_callback_makes(client):
    sign_in(client, "same.shape@example.com")
    keys = set(session_data(client))
    assert {"user_id", "email", "tenant_id", "tenant_role", "is_sys_admin", "login_at", "session_started_at"} <= keys


def test_the_family_page_needs_sign_in_and_shows_the_family(client):
    r = client.get("/family", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/signin?next=%2Ffamily"
    sign_in(client, "fam.owner@example.com")
    html = client.get("/family").text
    assert "fam.owner@example.com" in html and "Role: admin" in html
    assert session_data(client)["tenant_id"] in html


def test_dev_sign_in_is_refused_when_the_flag_is_off(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_DEV_LOGIN", "0")
    r = sign_in(client, "flag.off@example.com")
    assert r.status_code == 403
    assert "user_id" not in session_data(client) if client.cookies.get("session_") else True
    page = client.get("/signin").text
    assert "Dev sign-in" not in page and "doc" in page and "setup.md" in page
    monkeypatch.delenv("GITAWAY_DEV_LOGIN")
    assert sign_in(client, "flag.off@example.com").status_code == 403


def test_dev_sign_in_is_refused_from_another_machine(remote_client):
    r = sign_in(remote_client, "remote@example.com")
    assert r.status_code == 403 and "Sign out" not in remote_client.get("/").text
    assert "Dev sign-in" not in remote_client.get("/signin").text


@pytest.mark.parametrize("header", ["X-Forwarded-For", "X-Real-IP", "Forwarded", "X-Forwarded-Host", "X-Forwarded-Proto"])
def test_dev_sign_in_is_refused_behind_a_proxy_even_from_a_local_peer(client, header):
    r = client.post("/signin", data={"email": "proxy@example.com"}, headers={header: "127.0.0.1"}, follow_redirects=False)
    assert r.status_code == 403


def test_a_forged_forwarded_address_does_not_make_a_remote_client_local(remote_client):
    r = remote_client.post("/signin", data={"email": "spoof@example.com"}, headers={"X-Forwarded-For": "127.0.0.1"}, follow_redirects=False)
    assert r.status_code == 403


def test_dev_sign_in_answers_ipv6_localhost():
    from main import app
    c = TestClient(app, client=("::1", 5000))
    assert sign_in(c, "six@example.com").status_code == 303


@pytest.mark.parametrize("bad", ["", "nobody", "a@b", "two@@example.com", "sp ace@example.com", "x" * 130 + "@example.com"])
def test_a_bad_email_is_refused_and_nobody_is_signed_in(client, bad):
    r = sign_in(client, bad)
    assert r.status_code == 400 and 'role="alert"' in r.text and 'aria-invalid="true"' in r.text
    assert "Sign out" not in client.get("/").text


def test_dev_sign_in_does_not_follow_an_open_redirect(client):
    assert sign_in(client, "open.redirect@example.com", next="https://evil.example/x").headers["location"] == "/"


def test_the_sign_in_page_offers_the_dev_form_in_the_house_style(client):
    html = client.get("/signin?intent=pay&next=/plan").text
    assert 'type="email"' in html and "Dev sign-in (local only)" in html and "Sign in with Google" not in html
    assert 'name="next" value="/plan"' in html and 'name="intent" value="pay"' in html
    assert "Local development only" in html


def test_emails_become_names_and_ids_follow_the_user(client):
    sign_in(client, "ari")
    t = ses.current_traveler(session_data(client))
    assert (t.id, t.name, t.initials) == (tid("ari"), "Ari Rivera", "AR") and t.blurb == EMAILS["ari"]
    assert ses.current_traveler({}) is None and ses.current_traveler({"email": "x@y.zz"}) is None


# ---- public pages ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", PUBLIC)
def test_public_pages_are_browsable_signed_out(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 200, path
    assert "Sign in" in r.text


def test_the_demo_workspace_works_signed_out(client):
    assert client.get("/plan?f=f1&h=h1&c=c1").status_code == 200


# ---- logout ----------------------------------------------------------------------------------------------------------

def test_logout_removes_the_sign_in_and_keeps_the_trip_state(client):
    sign_in(client, "ari", next="/trips/sun-tacos-and-tide-pools", intent="fork")
    assert session_data(client)["forks"]
    for method in (client.post, client.get):
        sign_in(client, "ari")
        r = method("/logout", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/"
        data = session_data(client)
        assert "user_id" not in data and "tenant_id" not in data and data["forks"]
        assert "Sign out" not in client.get("/").text


def test_the_header_sign_out_form_posts_to_signout_which_is_the_same_as_logout(client):
    sign_in(client, "ari")
    assert 'action="/signout"' in client.get("/discover").text  # assets/js/pwa.js (F-044) hooks this form to clear its page cache
    r = client.post("/signout", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/" and "Sign out" not in client.get("/").text


# ---- Google through fh-saas ------------------------------------------------------------------------------------------

@pytest.fixture
def google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")


def test_without_google_keys_login_is_the_sign_in_page(client):
    r = client.get("/login?next=/plan", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=%2Fplan")


def test_with_google_keys_the_page_offers_google_and_login_goes_to_google(client, google):
    html = client.get("/signin?next=/plan&intent=pay").text
    assert "Sign in with Google" in html and 'href="/login?next=%2Fplan&amp;intent=pay"' in html
    r = client.get("/login?next=/plan&intent=pay", follow_redirects=False)
    target = urlsplit(r.headers["location"])
    q = parse_qs(target.query)
    assert target.netloc == "accounts.google.com" and q["client_id"] == ["test-id.apps.googleusercontent.com"]
    assert q["redirect_uri"][0].endswith("://testserver/auth/callback") and q["state"][0] == session_data(client)["oauth_state"]
    assert session_data(client)["login_next"] == "/plan" and session_data(client)["login_intent"] == "pay"


def test_the_google_callback_rejects_a_wrong_state(client, google):
    client.get("/login", follow_redirects=False)
    r = client.get("/auth/callback?code=abc&state=forged", follow_redirects=False)
    assert r.status_code == 400 and "That sign-in did not work" in r.text
    assert not client.cookies.get("session_") or "user_id" not in session_data(client)


def test_the_google_callback_signs_in_makes_the_family_and_returns_to_next(client, google, monkeypatch):
    class FakeGoogle:
        id_key = "sub"

        def login_link(self, redirect_uri, state):
            return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

        def retr_info(self, code, redirect_uri):
            assert code == "the-code" and redirect_uri.endswith("/auth/callback")
            return {"sub": "google-sub-123", "email": "gina@gmail.com"}

    monkeypatch.setattr("fh_saas.utils_auth.get_google_oauth_client", lambda: FakeGoogle())
    assert client.get("/login?next=/trips/sun-tacos-and-tide-pools&intent=fork", follow_redirects=False).status_code == 303
    state = session_data(client)["oauth_state"]
    r = client.get(f"/auth/callback?code=the-code&state={state}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trips/sun-tacos-and-tide-pools"
    data = session_data(client)
    assert data["email"] == "gina@gmail.com" and data["tenant_role"] == "owner" and "oauth_state" not in data and "login_next" not in data
    assert data["forks"] == {data["user_id"]: ["sun-tacos-and-tide-pools"]}  # the intent from before the sign-in was applied
    assert len(memberships(data["user_id"])) == 1
    assert "gina@gmail.com" in client.get("/family").text


def test_google_next_cannot_be_an_open_redirect(client, google):
    client.get("/login?next=//evil.example", follow_redirects=False)
    assert session_data(client)["login_next"] == "/start"
