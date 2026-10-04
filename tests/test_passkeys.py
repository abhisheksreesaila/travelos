"""F-074: Face ID sign-in. A passkey is added once signed in, then signs the person in the way Google sign-in does.

The tests drive the routes with a software authenticator (tests/softkey.py), so py_webauthn's real verification runs."""

import json

import pytest

from gitaway import passkeys
from tests.softkey import SoftKey
from tests.test_signin import session_data, sign_in, tid

ORIGIN = "http://testserver"
HEAD = {"origin": ORIGIN}


def post(client, path, body=None, origin=ORIGIN):
    return client.post(path, json=body if body is not None else {}, headers={"origin": origin} if origin else {})


def add_passkey(client, key=None, ua="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"):
    key = key or SoftKey()
    opts = post(client, "/passkeys/register/options").text
    r = client.post("/passkeys/register", json={"credential": key.create(opts, ORIGIN)}, headers={**HEAD, "user-agent": ua})
    return key, r


def face_id(client, key, **extra):
    """Sign in with `key` in a fresh browser; returns (response, options)."""
    opts = post(client, "/passkeys/auth/options").text
    return client.post("/passkeys/auth", json={"credential": key.get(opts, ORIGIN), **extra}, headers=HEAD), opts


@pytest.fixture
def phone(client):
    """Ari, signed in once, with one passkey; and a second browser (the phone later) that is signed out."""
    from starlette.testclient import TestClient
    from main import app
    sign_in(client)
    key, r = add_passkey(client)
    assert r.status_code == 200, r.text
    return key, TestClient(app, client=("127.0.0.1", 50001))


def test_signed_in_person_can_add_a_passkey_and_it_is_listed_on_the_family_page(client):
    sign_in(client)
    key, r = add_passkey(client)
    assert r.status_code == 200 and r.json()["ok"] is True
    rows = passkeys.listing(tid())
    assert len(rows) == 1 and rows[0]["name"] == "iPhone" and rows[0]["last_used"] is None
    page = client.get("/family").text
    assert 'id="this-phone"' in page and "iPhone" in page and f'value="{rows[0]["id"]}"' in page


def test_a_passkey_is_stored_without_the_private_key_or_anything_secret_in_the_page(client):
    sign_in(client)
    key, _ = add_passkey(client)
    row = passkeys.listing(tid())[0]
    assert set(row) >= {"id", "name", "created_at", "last_used"} and "public_key" not in row   # the listing is for the page: no credential material
    assert key.id not in client.get("/family").text


def test_registering_needs_a_signed_in_person(client):
    assert post(client, "/passkeys/register/options").status_code == 401
    assert client.post("/passkeys/register", json={"credential": {}}, headers=HEAD).status_code == 401


def test_registration_asks_for_a_resident_key_and_user_verification(client):
    sign_in(client)
    opts = post(client, "/passkeys/register/options").json()
    sel = opts["authenticatorSelection"]
    assert sel["residentKey"] == "required" and sel["requireResidentKey"] is True and sel["userVerification"] == "required"
    assert opts["rp"]["id"] == "testserver" and opts["user"]["name"] == "ari.rivera@example.com"


def test_a_passkey_that_did_not_verify_the_person_is_refused(client):
    sign_in(client)
    opts = post(client, "/passkeys/register/options").text
    r = client.post("/passkeys/register", json={"credential": SoftKey(user_verified=False).create(opts, ORIGIN)}, headers=HEAD)
    assert r.status_code == 400 and passkeys.listing(tid()) == []


def test_signing_in_with_face_id_gives_the_same_session_as_google_and_says_welcome_back(phone):
    key, other = phone
    r, _ = face_id(other, key, next="/family")
    assert r.status_code == 200 and r.json() == {"ok": True, "next": "/family", "name": "Ari", "passkey": passkeys.listing(tid())[0]["id"]}
    s = session_data(other)
    assert s["user_id"] == tid() and s["tenant_id"] and s["tenant_role"] == "owner" and s["email"] == "ari.rivera@example.com"
    assert other.get("/family", follow_redirects=False).status_code == 200
    assert passkeys.listing(tid())[0]["last_used"]


def test_the_session_is_the_dev_sign_ins_session_shape(client, phone):
    key, other = phone
    face_id(other, key)
    assert set(session_data(other)) - {"pk", "seen_at"} == set(session_data(client)) - {"pk", "seen_at"}


def test_next_is_kept_local(phone):
    key, other = phone
    r, _ = face_id(other, key, next="https://evil.example/x")
    assert r.json()["next"] == "/trip"


def test_a_challenge_works_once(phone):
    key, other = phone
    opts = post(other, "/passkeys/auth/options").text
    cred = key.get(opts, ORIGIN)
    assert other.post("/passkeys/auth", json={"credential": cred}, headers=HEAD).status_code == 200
    other.post("/logout")
    assert other.post("/passkeys/auth", json={"credential": key.get(opts, ORIGIN, count=9)}, headers=HEAD).status_code == 400   # the challenge was used up


def test_a_challenge_expires(phone, monkeypatch):
    key, other = phone
    opts = post(other, "/passkeys/auth/options").text
    cred = key.get(opts, ORIGIN)
    real = passkeys.now()
    monkeypatch.setattr(passkeys, "now", lambda: real + passkeys.CHALLENGE_SECONDS + 1)
    r = other.post("/passkeys/auth", json={"credential": cred}, headers=HEAD)
    assert r.status_code == 400


def test_a_response_signed_for_another_challenge_is_refused(phone):
    key, other = phone
    post(other, "/passkeys/auth/options")
    from starlette.testclient import TestClient
    from main import app
    other_opts = post(TestClient(app, client=("127.0.0.1", 50002)), "/passkeys/auth/options").text
    assert other.post("/passkeys/auth", json={"credential": key.get(other_opts, ORIGIN)}, headers=HEAD).status_code == 400


def test_the_wrong_origin_is_refused(phone):
    key, other = phone
    opts = post(other, "/passkeys/auth/options").text
    r = other.post("/passkeys/auth", json={"credential": key.get(opts, "https://evil.example")}, headers=HEAD)
    assert r.status_code == 400


def test_the_wrong_relying_party_is_refused(phone):
    key, other = phone
    opts = post(other, "/passkeys/auth/options").text
    assert other.post("/passkeys/auth", json={"credential": key.get(opts, ORIGIN, rp_id="evil.example")}, headers=HEAD).status_code == 400


def test_a_request_from_another_site_is_refused(phone):
    key, other = phone
    assert post(other, "/passkeys/auth/options", origin="https://evil.example").status_code == 403
    opts = post(other, "/passkeys/auth/options").text
    assert other.post("/passkeys/auth", json={"credential": key.get(opts, ORIGIN)}, headers={"origin": "https://evil.example"}).status_code == 403


def test_a_form_post_is_not_accepted(phone):
    _, other = phone
    assert other.post("/passkeys/auth/options", data={"a": "b"}, headers=HEAD).status_code == 400   # JSON only: a cross-site form cannot send it


def test_a_sign_count_that_goes_backwards_is_refused(phone):
    key, other = phone
    assert face_id(other, key)[0].status_code == 200
    other.post("/logout")
    assert face_id(other, key)[0].status_code == 200   # count 2
    other.post("/logout")
    opts = post(other, "/passkeys/auth/options").text
    r = other.post("/passkeys/auth", json={"credential": key.get(opts, ORIGIN, count=1)}, headers=HEAD)
    assert r.status_code == 400


def test_a_passkey_that_was_removed_cannot_sign_in(phone, client):
    key, other = phone
    pid = passkeys.listing(tid())[0]["id"]
    r = client.post("/passkeys/remove", data={"id": pid}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/family")
    assert passkeys.listing(tid()) == []
    assert face_id(other, key)[0].status_code == 400


def test_nobody_can_remove_someone_elses_passkey(phone):
    key, other = phone
    from starlette.testclient import TestClient
    from main import app
    sam = TestClient(app, client=("127.0.0.1", 50003))
    sign_in(sam, "sam")
    pid = passkeys.listing(tid())[0]["id"]
    sam.post("/passkeys/remove", data={"id": pid}, follow_redirects=False)
    assert len(passkeys.listing(tid())) == 1


def test_an_unknown_passkey_is_refused(client):
    r, _ = face_id(client, SoftKey())
    assert r.status_code == 400


def test_a_person_with_no_family_left_gets_a_new_one_as_google_sign_in_would(client):
    from starlette.testclient import TestClient
    from main import app
    from fh_saas.db_host import HostDatabase
    from sqlalchemy import text
    from gitaway import hostdb
    mail = "no.family.left@example.com"   # not ari: his family is shared by the rest of the suite
    sign_in(client, mail)
    key, _ = add_passkey(client)
    uid, old = tid(mail), session_data(client)["tenant_id"]
    with hostdb.locked():
        conn = HostDatabase.from_env().db.conn
        conn.execute(text("DELETE FROM core_memberships WHERE user_id = :u"), {"u": uid})
        conn.commit()
    other = TestClient(app, client=("127.0.0.1", 50004))
    r, _ = face_id(other, key)
    assert r.status_code == 200 and session_data(other)["tenant_id"] not in ("", old)


def test_the_same_phone_cannot_be_added_twice(client):
    sign_in(client)
    key, _ = add_passkey(client)
    opts = post(client, "/passkeys/register/options").json()
    assert [c["id"] for c in opts["excludeCredentials"]] == [key.id]


def test_the_relying_party_in_production_comes_from_the_setting_not_the_request(monkeypatch):
    monkeypatch.setenv("GITAWAY_ENV", "production")
    monkeypatch.setenv("GITAWAY_PUBLIC_URL", "https://web-production-2d117.up.railway.app/")

    class Req:
        class url:
            hostname, scheme, netloc = "evil.example", "http", "evil.example"
        headers = {"host": "evil.example", "x-forwarded-host": "evil.example"}
    assert passkeys.relying_party(Req) == ("web-production-2d117.up.railway.app", "https://web-production-2d117.up.railway.app")


def test_in_production_without_a_public_address_passkeys_are_off(monkeypatch):
    monkeypatch.setenv("GITAWAY_ENV", "production")
    for k in ("GITAWAY_PUBLIC_URL", "RAILWAY_PUBLIC_DOMAIN"):
        monkeypatch.delenv(k, raising=False)
    assert passkeys.relying_party(object()) is None


def test_railways_own_domain_setting_is_used_when_there_is_no_public_url(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("GITAWAY_PUBLIC_URL", raising=False)
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "web-production-2d117.up.railway.app")
    assert passkeys.relying_party(object())[1] == "https://web-production-2d117.up.railway.app"


def test_the_sign_in_page_offers_face_id_and_a_signed_in_phone_gets_the_card(client):
    page = client.get("/signin").text
    assert 'id="si-faceid"' in page and "Sign in with Face ID" in page and "/assets/js/passkeys.js" in page
    sign_in(client)
    assert "Use Face ID next time" in client.get("/family").text


def test_the_card_is_not_shown_to_someone_who_has_a_passkey(client):
    sign_in(client)
    add_passkey(client)
    assert "Use Face ID next time" not in client.get("/family").text
    assert "Add another phone" in client.get("/family").text
