"""F-076: /privacy and /terms are open, truthful, linked from the footer and the sign-in page."""

import re

import pytest

PRIVACY_PHRASES = ["your email address and your Google account number", "we do not keep them", "trips, plans", "notes", "messages", "photos", "time and place", "phone numbers",
                   "push subscriptions", "passkeys", "Your family sees", "masked email", "not shown to the family", "can read the stored data", "Google sign-in", "Railway", "OpenStreetMap",
                   "place text only", "Nominatim", "router.project-osrm.org", "pairs of coordinates", "tile.openstreetmap.org", "Google Fonts", "encrypted", "confirmation numbers", "people you invite", "server logs, which can include your email address, for example when a sign-in fails", "Apple and Google push services", "Azure OpenAI", "When you tap Convert", "When you use Ask GitAway", "the plan for that day", "plan notes and booking titles", "the parts and steps with who is on each", "the first names of the family", "We never add emails, phone numbers, confirmation numbers, prices or photos", "never what was in it", "Sarvam AI (India)", "When you record your voice in the Ask box", "does not keep the recording or the words", "do not sell", "do not show ads", "deleted"]
TERMS_PHRASES = ["as-is", "does not book anything", "responsible for what you add", "remove content", "change GitAway or stop it",
                 "without any warranty", "United States", "not legal advice"]


@pytest.mark.parametrize("path,phrases", [("/privacy", PRIVACY_PHRASES), ("/terms", TERMS_PHRASES)])
def test_page_open_signed_out_and_says_it(client, path, phrases):
    r = client.get(path)
    assert r.status_code == 200
    for p in phrases:
        assert p in r.text, p
    assert "Effective November 6, 2026" in r.text
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


def test_the_privacy_page_names_both_cookies_the_partner_links_anthropic_and_the_subid(client):
    """F-182 (reviewer Must 2 and 3): ga_via, partner-site tracking, Anthropic for creator import, and the SubID the partners receive were all live and unmentioned."""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", client.get("/privacy").text)).replace("&#x27;", "'")
    for phrase in ("Two cookies", "ga_via", "the public handle of the creator", "30 days", "which creator a flight you book supports", "30-day affiliate attribution cookie",
                   "Partner links", "Aviasales, Klook", "their own sites may set their own tracking cookies",
                   "Anthropic (Claude Haiku)", "Turn your post into a trip", "the text of the post, pasted or read from the link", "and nothing else",
                   "Travelpayouts", "SubID", "no name, email address or other personal detail",
                   "How readers of a creator's trip are counted", "Your address and the name of your browser are never stored"):
        assert phrase in text, phrase
    assert "One cookie keeps you signed in" not in text
    assert "no tracking or advertising cookies of our own" not in text      # F-196: ga_via is an attribution cookie, and the page says so


def test_plan_it_for_me_is_in_the_privacy_page_and_the_terms_and_the_terms_no_longer_say_gitaway_takes_no_payments(client, monkeypatch):
    """F-193: Stripe takes a payment, Claude Sonnet reads the intake, and an order keeps personal data until it is deleted. The old terms said GitAway "does not take payments": it now takes one.
    (Paid plans with Sonnet and the founder check, as F-193 and F-197 sold them; F-199's free pages are in tests/test_planforme_free.py.)"""
    monkeypatch.setenv("PLAN_FOR_ME_REVIEW", "1")
    monkeypatch.setenv("GITAWAY_AI_MODEL_PLAN_FOR_ME", "claude-sonnet-5-5")
    flat = lambda path: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", client.get(path).text)).replace("&#x27;", "'")
    privacy, terms = flat("/privacy"), flat("/terms")
    for phrase in ("Plan it for me orders: where you asked to go, the dates, your home airport, how many adults and the ages of any kids (and, if you gave them, their heights, which we delete as soon as your plan is delivered), your budget and pace, what you typed under must-dos, your email address, the amount and Stripe's code for the payment, and the trip we built. Before we send a plan, the person who runs GitAway reads the order and the plan to check it",
                   "We do not keep your card number",
                   "Stripe takes the payment for Plan it for me", "You type your card on Stripe's own page, so GitAway never sees or keeps your card number",
                   "Stripe gets your email address (for the receipt) and the amount, and keeps its own record of the payment under its own rules",
                   "Anthropic (Claude Sonnet) builds your trip when you order Plan it for me", "It never gets your name, your email address or anything from your family's other trips",
                   "Your Plan it for me orders go too. Stripe keeps its own record of a payment."):
        assert phrase in privacy, phrase
    for phrase in ("does not book anything", "The one thing you can pay GitAway for is Plan it for me: a one-time fee, shown before you pay, taken on Stripe's page",
                   "Not useful? Email us within 7 days for a full refund.", "If we cannot build your trip, we refund you in full",
                   "it can be wrong, it never states prices or opening hours, and it is your job to check every place, time and booking before you rely on it"):
        assert phrase in terms, phrase
    assert "does not take payments" not in terms


def test_every_outside_service_sits_inside_the_services_list(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_AI_MODEL_PLAN_FOR_ME", "claude-sonnet-5-5")      # Sonnet builds paid plans when the setting says so; free plans are Haiku's (F-199)
    page = client.get("/privacy").text
    start = page.index("Google sign-in")
    end = page.index("</ul>", start)
    for name in ("Azure OpenAI", "Sarvam AI", "Claude Haiku", "Stripe", "Claude Sonnet", "Travelpayouts Drive"):
        assert start < page.index(name, start) < end, name
