"""F-088: Face ID only where it is set up. The server stays the judge; the page only decides whether to offer the button."""
import re

from gitaway import passkeys
from tests.softkey import SoftKey
from tests.test_passkeys import HEAD, add_passkey, face_id, phone, post  # noqa: F401 - phone is a fixture
from tests.test_signin import sign_in, tid


def test_the_sign_in_page_never_offers_face_id_by_itself(client):
    page = client.get("/signin").text
    button = re.search(r"<button[^>]*id=\"si-faceid\"[^>]*>", page).group(0)
    assert " hidden" in button   # only passkeys.js, on a phone that remembers Face ID for this address, takes it off


def test_signing_in_reports_the_passkey_id_so_the_phone_can_remember_it(phone):
    key, other = phone
    r, _ = face_id(other, key)
    assert r.json()["passkey"] == passkeys.listing(tid())[0]["id"]


def test_registering_reports_the_passkey_id(client):
    sign_in(client)
    _, r = add_passkey(client)
    assert r.json()["id"] == passkeys.listing(tid())[0]["id"]


def test_a_passkey_the_server_does_not_know_is_reported_as_unknown(phone):
    _, other = phone
    r, _ = face_id(other, SoftKey())   # a passkey from before the move: this server has never seen it
    assert r.status_code == 400 and r.json()["ok"] is False and r.json()["unknown"] is True


def test_other_failures_are_not_reported_as_unknown(phone):
    other = phone[1]
    post(other, "/passkeys/auth/options")
    r = other.post("/passkeys/auth", json={"credential": "nope"}, headers=HEAD)
    assert r.status_code == 400 and not r.json().get("unknown")


def test_the_remove_form_names_its_passkey_so_the_phone_can_forget_it(client):
    sign_in(client)
    add_passkey(client)
    pid = passkeys.listing(tid())[0]["id"]
    assert f'data-passkey-id="{pid}"' in client.get("/family").text
