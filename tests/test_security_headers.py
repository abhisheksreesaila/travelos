"""F-182 fix 2 (L5): every response carries the standard security headers: nobody can frame GitAway (clickjacking), the Referer leaves only for our own pages, and a browser never guesses a type.
No script-src policy: the pages use inline scripts, so one would break them. The badge keeps its own, stricter policy; HSTS is sent only in production (a local http:// copy must not pin the browser)."""

import pytest

COMMON = {"content-security-policy": "frame-ancestors 'none'", "referrer-policy": "same-origin", "x-content-type-options": "nosniff"}


@pytest.mark.parametrize("path", ["/healthz", "/", "/for-creators", "/assets/css/tokens.css", "/no-such-page"])
def test_every_response_says_no_framing_same_origin_referrer_and_nosniff(client, path):
    r = client.get(path)
    for name, value in COMMON.items():
        assert r.headers[name] == value, (path, name)
    assert "strict-transport-security" not in r.headers          # local and tests: plain http


def test_production_adds_hsts_for_a_year_including_subdomains(client, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert client.get("/healthz").headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_the_badge_keeps_its_own_stricter_policy(client):
    from gitaway import blogbutton
    r = client.get(blogbutton.LIGHT)
    assert r.status_code == 200 and r.headers["content-security-policy"] == "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    assert r.headers["referrer-policy"] == "same-origin"


def test_the_landing_keeps_its_external_travelpayouts_script_and_sets_no_script_policy(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_DRIVE_ID", "123456")
    r = client.get("/")
    assert '<script src="https://tp-em.com/MTIzNDU2.js?t=123456" async' in r.text
    assert "script-src" not in r.headers["content-security-policy"] and "default-src" not in r.headers["content-security-policy"]
