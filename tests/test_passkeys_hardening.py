"""F-074 review follow-ups: single-use challenges kept on the server, Apple's zero counter, stolen credential ids, odd input."""

from gitaway import passkeys
from tests.softkey import SoftKey
from tests.test_passkeys import HEAD, ORIGIN, add_passkey, face_id, phone, post  # noqa: F401 - phone is a fixture
from tests.test_signin import session_data, sign_in, tid


def restore_cookies(client, cookies):
    client.cookies.clear()
    for name, value in cookies.items():
        client.cookies.set(name, value)


def test_a_replayed_answer_is_refused_even_with_an_old_cookie(phone):
    key, other = phone
    opts = post(other, "/passkeys/auth/options").text
    stale = dict(other.cookies)   # the cookie as it was while the challenge was still unused
    cred = key.get(opts, ORIGIN)
    assert other.post("/passkeys/auth", json={"credential": cred}, headers=HEAD).status_code == 200
    restore_cookies(other, stale)
    r = other.post("/passkeys/auth", json={"credential": cred}, headers=HEAD)
    assert r.status_code == 400
    assert "user_id" not in session_data(other)


def test_a_registration_challenge_cannot_be_replayed_with_an_old_cookie(client):
    sign_in(client)
    opts = post(client, "/passkeys/register/options").text
    stale = dict(client.cookies)
    cred = SoftKey().create(opts, ORIGIN)
    assert client.post("/passkeys/register", json={"credential": cred}, headers=HEAD).status_code == 200
    restore_cookies(client, stale)
    assert client.post("/passkeys/register", json={"credential": cred}, headers=HEAD).status_code == 400
    assert len(passkeys.listing(tid())) == 1


def test_used_and_expired_challenges_are_cleaned_out_of_the_database(phone, monkeypatch):
    key, other = phone
    post(other, "/passkeys/auth/options")
    real = passkeys.now()
    monkeypatch.setattr(passkeys, "now", lambda: real + passkeys.CHALLENGE_SECONDS + 5)
    post(other, "/passkeys/auth/options")   # issuing sweeps the expired one
    assert passkeys.pending_challenges() == 1


def test_an_authenticator_that_always_counts_zero_can_sign_in_again_and_again(phone):
    key, other = phone   # the fixture's passkey was made with count 0, as Apple's are
    for _ in range(3):
        opts = post(other, "/passkeys/auth/options").text
        assert other.post("/passkeys/auth", json={"credential": key.get(opts, ORIGIN, count=0)}, headers=HEAD).status_code == 200
        other.post("/logout")


def test_nobody_can_register_a_credential_id_that_belongs_to_someone_else(client):
    from starlette.testclient import TestClient
    from main import app
    sign_in(client)
    key, r = add_passkey(client)
    assert r.status_code == 200
    sam = TestClient(app, client=("127.0.0.1", 50005))
    sign_in(sam, "sam")
    opts = post(sam, "/passkeys/register/options").text
    r = sam.post("/passkeys/register", json={"credential": key.create(opts, ORIGIN)}, headers=HEAD)
    assert r.status_code == 400 and passkeys.listing(tid("sam")) == [] and len(passkeys.listing(tid())) == 1


def test_a_credential_sent_as_a_string_is_a_400_not_a_crash(client):
    sign_in(client)
    post(client, "/passkeys/register/options")
    assert client.post("/passkeys/register", json={"credential": "nope"}, headers=HEAD).status_code == 400
    post(client, "/passkeys/auth/options")
    assert client.post("/passkeys/auth", json={"credential": "nope"}, headers=HEAD).status_code == 400


def test_the_media_type_is_parsed_exactly(client):
    sign_in(client)
    r = client.post("/passkeys/register/options", content=b"{}", headers={**HEAD, "content-type": "text/plain; x=application/json"})
    assert r.status_code == 400
    r = client.post("/passkeys/register/options", content=b"{}", headers={**HEAD, "content-type": "Application/JSON; charset=utf-8"})
    assert r.status_code == 200


def test_an_invalid_public_address_turns_passkeys_off(monkeypatch):
    monkeypatch.setenv("GITAWAY_ENV", "production")
    monkeypatch.setenv("GITAWAY_PUBLIC_URL", "http://not-https.example")
    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    assert passkeys.configured() is False


def test_the_script_is_on_each_page_once_and_the_welcome_moment_is_on_the_sign_in_page(client):
    page = client.get("/signin").text
    assert page.count("/assets/js/passkeys.js") == 1 and 'id="si-welcome"' in page
    assert "Signed in with Face ID. No password, no code by text." in page and "Your passkey stays on this" in page
    sign_in(client)
    assert client.get("/family").text.count("/assets/js/passkeys.js") == 1


def test_a_face_id_sign_in_with_no_destination_opens_today(phone):
    key, other = phone
    r, _ = face_id(other, key, next="/start")
    assert r.json()["next"] == "/trip"
