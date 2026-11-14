"""Travelpayouts Drive (their site-verification script) loads only on the landing, only signed out, only when switched on."""
from tests.test_signin import sign_in

DRIVE = "tp-em.com/NTk2NTM0.js?t=596534"


def test_off_unless_switched_on(client, monkeypatch):
    monkeypatch.delenv("TRAVELPAYOUTS_DRIVE_ID", raising=False)
    assert "tp-em.com" not in client.get("/").text


def test_on_the_signed_out_landing(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_DRIVE_ID", "596534")
    assert DRIVE in client.get("/").text


def test_never_for_a_signed_in_person(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_DRIVE_ID", "596534")
    sign_in(client, "ari")
    assert "tp-em.com" not in client.get("/").text


def test_never_on_other_pages(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_DRIVE_ID", "596534")
    for path in ("/plan/matrix", "/plan", "/signin", "/privacy"):
        assert "https://tp-em.com/" not in client.get(path).text, path      # the script's address: the privacy page names the service (F-196) but never loads it


def test_a_bad_id_is_ignored(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_DRIVE_ID", "59'><script>")
    assert "tp-em.com" not in client.get("/").text
