"""F-048 / F-049: production settings, the health check and the 30-day sliding sign-in."""

import pytest
from starlette.testclient import TestClient

from gitaway import auth, members
from tests.test_members import addr, browser, invite, tenant
from tests.test_members import owner  # noqa: F401 - fixture
from tests.test_signin import session_data, sign_in, user_id

THIRTY_DAYS = 30 * 24 * 3600


@pytest.fixture
def prod(monkeypatch):
    monkeypatch.setenv("GITAWAY_ENV", "production")
    monkeypatch.setenv("GITAWAY_SECRET_KEY", "a-test-secret")
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)


def _session_middleware(app):
    return next(m for m in app.user_middleware if m.cls.__name__ == "SessionMiddleware")


# ---- production mode ----

def test_production_is_detected_from_either_variable(monkeypatch):
    for k in ("GITAWAY_ENV", "RAILWAY_ENVIRONMENT"):
        monkeypatch.delenv(k, raising=False)
    assert not auth.production()
    monkeypatch.setenv("GITAWAY_ENV", "production")
    assert auth.production()
    monkeypatch.delenv("GITAWAY_ENV")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert auth.production()


def test_production_refuses_to_start_without_a_secret_key(prod, monkeypatch):
    monkeypatch.delenv("GITAWAY_SECRET_KEY")
    with pytest.raises(RuntimeError, match="GITAWAY_SECRET_KEY"):
        auth.check_production_settings()
    monkeypatch.setenv("GITAWAY_SECRET_KEY", "  ")
    with pytest.raises(RuntimeError):
        auth.check_production_settings()


def test_production_with_a_secret_key_starts(prod):
    auth.check_production_settings()


def test_development_does_not_need_a_secret_key(monkeypatch):
    monkeypatch.delenv("GITAWAY_ENV", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("GITAWAY_SECRET_KEY", raising=False)
    auth.check_production_settings()


def test_the_dev_sign_in_is_off_in_production_even_when_the_flag_is_set(prod, monkeypatch):
    monkeypatch.setenv("GITAWAY_DEV_LOGIN", "1")
    assert not auth.dev_login_enabled()

    class Req:  # straight from this machine with no proxy header: only production stops it
        client = type("C", (), {"host": "127.0.0.1"})()
        headers = {}
    assert not auth.dev_login_allowed(Req())


def test_the_dev_sign_in_endpoint_answers_403_in_production(prod, monkeypatch):
    from main import make_app
    monkeypatch.setenv("GITAWAY_DEV_LOGIN", "1")
    c = TestClient(make_app(), client=("127.0.0.1", 5))
    assert c.post("/signin", data={"email": "x@example.com"}, follow_redirects=False).status_code == 403


def test_production_serves_with_proxy_headers_trusted_and_no_reload(prod):
    opts = auth.server_options()
    assert opts["reload"] is False and opts["host"] == "0.0.0.0" and opts["proxy_headers"] is True
    assert opts["forwarded_allow_ips"] == "*"


def test_development_serves_with_reload_and_without_trusting_proxy_headers(monkeypatch):
    monkeypatch.delenv("GITAWAY_ENV", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    opts = auth.server_options()
    assert opts["reload"] is True and opts["proxy_headers"] is False


# ---- the cookie ----

def test_session_cookie_is_https_only_in_production_and_works_on_localhost(prod, monkeypatch):
    from main import make_app
    assert _session_middleware(make_app()).kwargs["https_only"] is True
    monkeypatch.delenv("GITAWAY_ENV")
    assert _session_middleware(make_app()).kwargs["https_only"] is False


def test_the_cookie_lasts_about_30_days(client):
    r = sign_in(client)
    assert _session_middleware(client.app).kwargs["max_age"] == THIRTY_DAYS
    assert f"Max-Age={THIRTY_DAYS}" in r.headers["set-cookie"]


def test_the_cookie_slides_a_visit_a_day_later_re_issues_it_and_a_quick_one_does_not(client, monkeypatch):
    from gitaway import session as ses
    sign_in(client)
    clock = [1_800_000_000.0]
    monkeypatch.setattr(ses, "now", lambda: clock[0])
    assert f"Max-Age={THIRTY_DAYS}" in client.get("/family").headers["set-cookie"]  # first visit stamps seen_at
    assert "set-cookie" not in client.get("/family").headers  # same day: no cookie churn
    clock[0] += 25 * 3600
    assert f"Max-Age={THIRTY_DAYS}" in client.get("/family").headers["set-cookie"]  # next day: the 30 days start over
    clock[0] += 29 * 24 * 3600
    assert client.get("/family").headers["set-cookie"]  # and again 29 days on: still signed in, cookie renewed


def test_signed_out_visits_never_write_a_cookie(client):
    assert "set-cookie" not in client.get("/").headers


def test_sign_out_ends_access_immediately(client):
    sign_in(client, "out.slide@example.com")
    assert client.get("/family", follow_redirects=False).status_code == 200
    client.post("/signout", follow_redirects=False)
    assert client.get("/family", follow_redirects=False).status_code in (302, 303, 307)


def test_a_removed_member_loses_the_family_on_the_next_request_with_a_still_valid_cookie(owner):
    sam = addr()
    invite(owner, sam, "editor")
    other = browser(owner)
    sign_in(other, sam)
    other.get("/family")  # a fresh, slid cookie
    assert members.role_in(user_id(other), tenant(owner)) == "editor"
    owner.post("/family/remove", data={"user": user_id(other)})
    other.get("/family")  # the same, still valid cookie
    assert members.role_in(user_id(other), tenant(owner)) is None
    assert session_data(other).get("tenant_id") != tenant(owner)


# ---- health check ----

def test_healthz_is_200_without_a_session_cookie(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.text.strip() == "ok"
    assert "set-cookie" not in r.headers
