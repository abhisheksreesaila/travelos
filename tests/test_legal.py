"""F-076: /privacy and /terms are open, truthful, linked from the footer and the sign-in page."""

import re

import pytest

PRIVACY_PHRASES = ["your email address and your Google account number", "we do not keep them", "trips, plans", "notes", "messages", "photos", "time and place", "phone numbers",
                   "push subscriptions", "passkeys", "Your family sees", "masked email", "not shown to the family", "can read the stored data", "Google sign-in", "Railway", "OpenStreetMap",
                   "place text only", "Nominatim", "router.project-osrm.org", "pairs of coordinates", "tile.openstreetmap.org", "Google Fonts", "encrypted", "confirmation numbers", "people you invite", "server logs, which can include your email address, for example when a sign-in fails", "Apple and Google push services", "Azure OpenAI", "When you tap Convert", "When you use Ask GitAway", "the plan for that day", "plan notes and booking titles", "the parts and steps with who is on each", "the first names of the family", "It never gets emails, phone numbers, confirmation numbers, prices or photos", "never what was in it", "do not sell", "do not show ads", "deleted"]
TERMS_PHRASES = ["as-is", "does not book anything", "does not take payments", "responsible for what you add", "remove content", "change GitAway or stop it",
                 "without any warranty", "United States", "not legal advice"]


@pytest.mark.parametrize("path,phrases", [("/privacy", PRIVACY_PHRASES), ("/terms", TERMS_PHRASES)])
def test_page_open_signed_out_and_says_it(client, path, phrases):
    r = client.get(path)
    assert r.status_code == 200
    for p in phrases:
        assert p in r.text, p
    assert "Effective October 3, 2026" in r.text
    assert "not legal advice" in r.text


@pytest.mark.parametrize("path", ["/privacy", "/terms"])
def test_open_in_the_live_site_mode(client, monkeypatch, path):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert client.get(path).status_code == 200


def test_contact_only_when_set(client, monkeypatch):
    monkeypatch.delenv("GITAWAY_CONTACT_EMAIL", raising=False)
    for path in ("/privacy", "/terms"):
        t = client.get(path).text
        assert "Contact the person who runs this GitAway site" in t and "mailto:" not in t
    monkeypatch.setenv("GITAWAY_CONTACT_EMAIL", "help@example.org")
    for path in ("/privacy", "/terms"):
        t = client.get(path).text
        assert 'href="mailto:help@example.org"' in t and "Contact the person who runs this GitAway site" not in t


def test_footer_and_signin_link_to_both(client):
    for path in ("/", "/signin", "/privacy"):
        t = client.get(path).text
        assert 'href="/privacy"' in t and 'href="/terms"' in t, path
    assert re.search(r'id="si-legal".*?href="/terms".*?href="/privacy"', client.get("/signin").text, re.S)
