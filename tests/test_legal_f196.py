"""F-196 item 7: what /terms and /privacy say about what creators publish, a takedown, a repeat infringer, the cookie and the script on the landing, and who the DMCA agent is."""

import re
from html import unescape

import pytest


def words(html) -> str:
    inline = re.sub(r"</?(?:strong|a|em)\b[^>]*>", "", html)      # a bold word or a link does not break the sentence it is in
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", inline)))


@pytest.fixture
def terms(client):
    return words(client.get("/terms").text)


@pytest.fixture
def privacy(client):
    return words(client.get("/privacy").text)


# ---- terms ----------------------------------------------------------------------------------------------------------------------------

def test_terms_grant_a_license_for_what_creators_publish_and_say_how_it_ends(terms):
    for phrase in ("What creators publish", "you keep your rights", "worldwide, non-exclusive, royalty-free license", "host, copy, reformat and show what you publish",
                   "read it, fork it into their own plans and share its link", "Unpublish and we delete the page and its picture copies",
                   "Plans a family has already put into its own calendar stay in that family's calendar", "you are the author, or have the right to publish"):
        assert phrase in terms, phrase


def test_terms_say_how_to_report_a_copy_and_what_a_notice_holds(terms):
    for phrase in ("Copyright takedown", "Report this trip", "the web address of the copy on GitAway", "your name and contact details", "in good faith",
                   "under penalty of perjury", "your signature, typed is fine"):
        assert phrase in terms, phrase


def test_terms_say_how_to_answer_a_takedown_with_a_counter_notice(terms):
    for phrase in ("Counter-notice", "removed by mistake or misidentification", "consent to the jurisdiction of the federal court", "10 business days"):
        assert phrase in terms, phrase


def test_terms_have_a_repeat_infringer_policy(terms):
    assert "Repeat infringers" in terms
    assert "valid copyright notices on two different pages" in terms and "remove all of that person's pages and close their account" in terms


def test_the_sample_prices_sentence_is_gone_but_terms_still_say_nothing_is_booked_here(terms):
    assert "sample prices" not in terms
    assert "GitAway does not book anything. A Book button takes you to a partner's own site, and you book and pay there" in terms and "Check every flight, stay and time" in terms      # F-193: the one payment GitAway takes is Plan it for me, said in the next paragraph


def test_the_dmca_agent_is_pending_until_the_environment_names_one(client, monkeypatch):
    monkeypatch.delenv("DMCA_AGENT", raising=False)
    html = client.get("/terms").text
    assert re.search(r'id="dmca-agent"[^>]*>[^<]*pending registration with the U\.S\. Copyright Office', unescape(html))
    assert "Our designated copyright agent:" not in words(html)


def test_the_dmca_agent_is_read_from_the_environment_and_shown_as_text(client, monkeypatch):
    monkeypatch.setenv("DMCA_AGENT", "Priya Rao, 1 Main St, Oakland CA <script>x</script>")
    html = client.get("/terms").text
    assert "Our designated copyright agent: Priya Rao, 1 Main St, Oakland CA &lt;script&gt;x&lt;/script&gt;" in re.sub(r"<[^>]+>", "", html).replace("&#x27;", "'") or \
        "Priya Rao, 1 Main St, Oakland CA &lt;script&gt;x&lt;/script&gt;" in html
    assert "<script>x</script>" not in html and "pending registration" not in words(html)


def test_takedown_notices_go_to_the_contact_address_when_one_is_set(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_CONTACT_EMAIL", "help@example.org")
    html = client.get("/terms").text
    assert html.count('href="mailto:help@example.org"') == 2      # the takedown section and the deletion section
    assert len(set(re.findall(r'id="([^"]+)"', html))) == len(re.findall(r'id="([^"]+)"', html))      # no id twice


# ---- privacy --------------------------------------------------------------------------------------------------------------------------

def test_privacy_says_what_ga_via_is_and_no_longer_claims_no_tracking_cookies(privacy):
    assert "ga_via, is a 30-day affiliate attribution cookie" in privacy
    assert "exists to credit the creator, not to build a profile of you" in privacy
    assert "no tracking or advertising cookies of our own" not in privacy
    assert "GitAway sets no analytics or advertising cookie" in privacy


def test_privacy_names_the_travelpayouts_drive_script_on_the_signed_out_landing(privacy):
    for phrase in ("Travelpayouts Drive", "only on the landing page you see signed out", "tp-em.com", "turn travel links on that page into partner links",
                   "never on a page you see signed in", "may set its own cookies"):
        assert phrase in privacy, phrase
