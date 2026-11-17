"""F-292: who sells a stay and how it is kept safe. The one sentence about the merchant sits on the checkout, the booked pass and the stay's booking page; /trust ("How GitAway keeps you
safe") says only what the code does today, is linked from the checkout, the reading-page foot and the about-prices card, and each claim is pinned here to the fact it rests on."""
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

import pytest

from gitaway import auth, familydb, liteapi, matrixbook as mb, seo
from gitaway.pages import trust
from tests.test_bookingmail import family, live, outbox  # noqa: F401 (fixtures)
from tests.test_liteapi_pay import LIVE
from tests.test_matrixbook_live import real, sheet, pay_pane, token  # noqa: F401 (real is the fixture)
from tests.test_matrixbook_page import MATRIX
from tests.test_staycancel import booked_stay

ROOT = Path(__file__).resolve().parent.parent
MERCHANT = "Booked and paid through Nuitée (LiteAPI), the merchant of record. GitAway never sees your card."


def words(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


# ---- the merchant sentence ---------------------------------------------------------------------------------------------------------------

def test_the_merchant_sentence_is_one_text_and_says_what_the_founder_asked():
    assert mb.MERCHANT == MERCHANT


def test_the_checkout_says_who_sells_it_and_links_how_it_is_kept_safe(real, client):
    html = sheet(client)
    assert MERCHANT in words(html) and 'href="/trust"' in html


def test_the_booked_pass_says_it(real, client):
    html, _ = pay_pane(client)
    r = client.get(f"/plan/matrix/book/return?token={token(html)}")
    assert MERCHANT in words(r.text)


def test_the_stays_booking_page_says_it(real, client):
    _, href = booked_stay(client)
    assert MERCHANT in words(client.get(href).text)


# ---- /trust ------------------------------------------------------------------------------------------------------------------------------

def test_the_trust_page_has_its_title_and_every_claim(client):
    r = client.get("/trust")
    assert r.status_code == 200
    page = words(r.text)
    assert "How GitAway keeps you safe" in page
    for _, claim in trust.claims():
        assert words(claim) in page, claim
    assert "not a certification" in page


def test_it_is_open_signed_out_and_in_the_sitemap(client):
    assert client.get("/trust").status_code == 200
    assert "/trust" in seo.STATIC and "/trust</loc>" in seo.sitemap_xml()


def test_the_reading_page_foot_links_to_it(client):
    foot = client.get("/privacy").text.split('class="pg-foot-nav"')[1].split("</nav>")[0]
    assert words(foot).lstrip("> ") == "Privacy Terms How GitAway keeps you safe" and 'href="/trust"' in foot


def test_the_about_prices_card_links_to_it(real, client):
    html = client.get(MATRIX).text
    foot = html.split('class="mx-tk mx-about"')[1].split("mx-about-foot")[1]
    assert 'href="/trust"' in foot.split("</nav>")[0]


def test_the_contact_is_the_sites_own_address_or_none(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_CONTACT_EMAIL", "hello@example.com")
    assert 'href="mailto:hello@example.com"' in client.get("/trust").text
    monkeypatch.delenv("GITAWAY_CONTACT_EMAIL")
    assert "Contact the person who runs this GitAway site." in words(client.get("/trust").text)


def test_a_stripe_sentence_appears_only_while_plan_it_for_me_is_paid(client, monkeypatch):
    from gitaway import planforme
    monkeypatch.setattr(planforme, "paid", lambda: False)
    assert "Stripe" not in client.get("/trust").text
    monkeypatch.setattr(planforme, "paid", lambda: True)
    assert "Stripe" in client.get("/trust").text


# ---- each claim pinned to the code fact it rests on ---------------------------------------------------------------------------------------

def test_card_claim_a_live_key_can_never_send_a_card_of_ours(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setattr(auth, "production", lambda: True)
    assert liteapi._allowed({"payment": {"method": "ACC_CREDIT_CARD"}}) is False
    assert liteapi._allowed({"usePaymentSdk": True, "payment": {"method": "ACC_CREDIT_CARD"}}) is False
    assert liteapi._allowed({"usePaymentSdk": True}) is True      # the payment form's own prebook is the one new-business call


def test_card_claim_no_page_of_ours_has_a_card_field(real, client):
    html = sheet(client)
    pane = pay_pane(client, html)[1].text
    assert not re.search(r'autocomplete="cc-|name="(card|cardnumber|cc|cvc|cvv)', html + pane, re.I)


def test_guest_claim_the_window_is_seven_days_and_the_page_says_it(client):
    assert mb.PURGE_GUEST == 7
    assert "within 7 days" in words(client.get("/trust").text)


def test_guest_claim_a_guest_never_booked_is_blank_after_seven_days_and_not_before(live, family, outbox):
    """A guest who typed their details and never finished paying: the row holds them until the purge, which blanks them from the eighth day (booked ones are blanked at once, by `finish`)."""
    from tests.test_bookingmail import paid
    db, user = family
    prep = paid(db, user)
    assert mb.payment(db, prep.token)["guest_email"] == "anne.oneil@example.com"
    for days, kept in ((mb.PURGE_GUEST - 1, True), (mb.PURGE_GUEST + 1, False)):
        familydb.run(db, "UPDATE matrix_payments SET created_at = :t", t=(datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds"))
        mb.purge(db)
        row = mb.payment(db, prep.token)
        assert (row["guest_email"] != "") is kept
    assert (row["guest_first"], row["guest_last"], row["guest_phone"]) == ("", "", "")


def test_guest_claim_the_purge_blanks_every_guest_column(tmp_path):
    src = (ROOT / "gitaway" / "matrixbook.py").read_text()
    purge = src.split("def purge(db)")[1].split("def save_prebook")[0]
    for col in ("guest_first", "guest_last", "guest_email", "guest_phone", "guest_remarks"):
        assert f"{col} = ''" in purge, col
    assert "PURGE_GUEST" in purge


def test_sign_in_claim_there_is_no_password_field_and_no_password_column(client):
    assert 'type="password"' not in client.get("/signin").text
    for name in ("auth.py", "passkeys.py", "members.py"):
        src = (ROOT / "gitaway" / name).read_text().lower()
        assert "password_hash" not in src and "bcrypt" not in src and "pbkdf2" not in src, name


def test_scripts_claim_the_only_other_sites_in_the_map_loader_are_the_two_it_names():
    js = (ROOT / "assets" / "js" / "aerial.js").read_text()
    hosts = re.search(r"var HOSTS = \{(.*?)\};", js).group(1)
    assert sorted(re.findall(r"https://([a-z.]+)/", hosts)) == ["cdn.jsdelivr.net", "unpkg.com"]
    assert liteapi.PAYMENT_SDK.startswith("https://payment-wrapper.liteapi.travel/")


def test_scripts_claim_no_analytics_service_is_in_the_code():
    needles = ("google-analytics", "googletagmanager", "gtag(", "plausible.io", "posthog", "mixpanel", "hotjar", "fbevents", "connect.facebook.net", "segment.com", "clarity.ms")
    for path in [*(ROOT / "gitaway").rglob("*.py"), *(ROOT / "assets" / "js").glob("*.js")]:
        if path == Path(__file__) or path.name == "trust.py":
            continue
        src = path.read_text(errors="ignore").lower()
        assert not [n for n in needles if n in src], path


def test_counts_claim_the_search_allowance_and_reader_counts_use_a_salted_daily_hash_and_set_no_cookie():
    src = (ROOT / "gitaway" / "stats.py").read_text()
    assert "_salt_of(day)" in src and "set_cookie" not in src.lower()


def test_email_claim_a_failed_send_logs_the_booking_id_and_never_the_address(caplog, monkeypatch):
    from gitaway import bookingmail
    def boom(to, mail):
        raise OSError("550 mailbox unavailable for " + to)
    monkeypatch.setattr(bookingmail, "deliver", boom)
    with caplog.at_level("DEBUG"):
        bookingmail._send("anne@example.com", bookingmail.Mail("s", "t", "h"), "bk-1")
    assert [r.getMessage() for r in caplog.records if r.name == "gitaway.bookingmail"] == ["booking email failed: bk-1"]
    assert "anne@example.com" not in caplog.text
