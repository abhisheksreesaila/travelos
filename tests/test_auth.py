"""F-039: fh-saas sign-in. The dev sign-in's guards, the family tenant, Google through fh-saas, logout and the public pages."""

import os
from urllib.parse import parse_qs, urlsplit

import pytest
from fh_saas.db_host import HostDatabase
from starlette.testclient import TestClient

from gitaway import auth, session as ses
from tests.test_signin import EMAILS, session_data, sign_in, stored_booking, tid

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
    from tests.test_calendar import book
    sign_in(client, "ari", next="/trips/sun-tacos-and-tide-pools", intent="fork")
    assert "forks" not in session_data(client)  # forks live in the family database now (F-041), and stay when someone signs out
    book(client)
    for method in (client.post, client.get):
        sign_in(client, "ari")
        r = method("/logout", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/"
        assert not client.cookies.get("session_")  # nothing is left in the cookie: it is gone
        assert stored_booking() is not None  # the trip stays in the family's database for the next sign-in
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
    assert ses.forks(data) == ["sun-tacos-and-tide-pools"]  # the intent from before the sign-in was applied, kept in the family's database
    assert len(memberships(data["user_id"])) == 1
    assert "gina@gmail.com" in client.get("/family").text


def test_google_next_cannot_be_an_open_redirect(client, google):
    client.get("/login?next=//evil.example", follow_redirects=False)
    assert session_data(client)["login_next"] == "/start"


# ---- review fixes ----------------------------------------------------------------------------------------------------

def fake_google(monkeypatch, email, sub="sub-1"):
    class Fake:
        id_key = "sub"

        def login_link(self, redirect_uri, state):
            return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

        def retr_info(self, code, redirect_uri):
            return {"sub": sub, "email": email}

    monkeypatch.setattr("fh_saas.utils_auth.get_google_oauth_client", lambda: Fake())


def test_cancelling_at_google_shows_a_friendly_page_and_forgets_where_we_were_going(client, google):
    client.get("/login?next=/plan&intent=pay", follow_redirects=False)
    for url in ("/auth/callback?error=access_denied&state=x", "/auth/callback", "/auth/callback?error=access_denied"):
        r = client.get(url, follow_redirects=False)
        assert r.status_code == 400 and "That sign-in did not work" in r.text
    data = session_data(client) if client.cookies.get("session_") else {}
    assert not ({"login_next", "login_intent", "oauth_state", "user_id"} & set(data))


def test_a_very_long_next_is_not_kept_in_the_cookie(client, google):
    client.get("/login?next=/trips/" + "a" * 600, follow_redirects=False)
    assert session_data(client)["login_next"] == "/start"


@pytest.mark.parametrize("header", ["CF-Connecting-IP", "True-Client-IP", "X-Forwarded-Server"])
def test_more_proxy_headers_refuse_the_dev_sign_in(client, header):
    assert client.post("/signin", data={"email": "p@example.com"}, headers={header: "1.2.3.4"}, follow_redirects=False).status_code == 403


def test_an_ipv4_mapped_or_missing_client_is_refused():
    from main import app
    mapped = TestClient(app, client=("::ffff:127.0.0.1", 5000))
    assert sign_in(mapped, "mapped@example.com").status_code == 403

    class NoClient:
        client = None
        headers = {}

    assert auth.dev_login_allowed(NoClient()) is False


def test_a_full_cookie_plus_a_long_email_plus_a_google_sign_in_stays_under_the_browser_limit(client, google, monkeypatch):
    from tests.test_calendar import add, book
    book(client)
    for i in range(60):  # fill the previous person's cookie to its budget
        if add(client, id=f"a{i + 1}", day=str(1 + i % 3), start="12:00", end="12:30", title=f"Plan number {i:02d} " + "x" * 20).status_code == 409:
            break
    previous = tid("ari")
    client.post("/signout")
    email = "l" * 230 + "@example.com"
    fake_google(monkeypatch, email, "sub-long")
    client.get("/login?next=/trips/" + "b" * 150, follow_redirects=False)
    state = session_data(client)["oauth_state"]
    r = client.get(f"/auth/callback?code=c&state={state}", follow_redirects=False)
    assert r.status_code == 303
    assert len(client.cookies.get("session_")) <= 3600
    data = session_data(client)
    assert data["email"] == email and previous not in data.get("cal", {})  # the earlier person's state made room


def test_logout_does_not_hand_the_creator_draft_to_the_next_person(client):
    from tests.test_creators import paste
    sign_in(client, "ari")
    paste(client)
    assert "cr" in session_data(client)  # there is a draft to hand over
    client.post("/signout")
    assert "cr" not in (session_data(client) if client.cookies.get("session_") else {})


def test_the_family_page_has_the_house_styles(client):
    sign_in(client, "style.check@example.com")
    html = client.get("/family").text
    assert html.index("/assets/css/tokens.css") < html.index("/assets/css/base.css") < html.index("/assets/css/family.css")


# ---- with the iPhone install (F-044) ---------------------------------------------------------------------------------

def test_both_sign_out_paths_clear_the_site_data(client):
    for method, path in ((client.post, "/signout"), (client.post, "/logout"), (client.get, "/logout")):
        sign_in(client, "ari")
        r = method(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["clear-site-data"] == '"cache", "storage"', path


def test_the_install_files_are_public_signed_out(client):
    for path in ("/manifest.webmanifest", "/sw.js", "/offline", "/assets/css/tokens.css"):
        assert client.get(path, follow_redirects=False).status_code == 200, path


def test_the_cache_key_follows_the_fh_saas_user_and_the_session_secret(client, monkeypatch):
    import re
    from gitaway import layout
    key = r'<meta name="ga-user" content="([0-9a-f]{10})">'
    sign_in(client, "ari")
    a = re.search(key, client.get("/discover").text).group(1)
    assert a == layout.cache_key(ses.current_traveler(session_data(client)))
    monkeypatch.setenv("GITAWAY_SECRET_KEY", "a different secret")
    assert ses.cache_secret() == b"a different secret" and layout.cache_key(ses.current_traveler(session_data(client))) != a
