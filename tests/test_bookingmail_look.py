"""F-294: the booked and cancelled emails in the site's look: a deep band with the logo word, one bold action, the Wallet links when offered, who sold the stay, a short what-next, a
plain-text part, inline styles only and a colour scheme that survives a mail app's dark mode. Built from the preview script's own sample data (scripts/send_test_email.py)."""
import re
import sys
from html import unescape
from pathlib import Path

from gitaway import bookingmail, matrixbook as mb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import send_test_email as sample  # noqa: E402

LIVE = {**sample.BOOKED, "sandbox": False}
WALLET = (("Add to Apple Wallet", "/trip/booking/wallet/apple?b=1"), ("Save to Google Wallet", "/trip/booking/wallet/google?b=1"))


def words(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(style|head)[^>]*>.*?</\1>", "", html, flags=re.S))).split())


def test_the_booked_email_wears_a_deep_band_with_the_logo_word_above_the_card():
    html = bookingmail.booked_mail(LIVE).html
    band = re.search(r'<td[^>]*background:(#[0-9A-Fa-f]{6})[^>]*>\s*GitAway\s*</td>', html)
    assert band and band.group(1).upper() == bookingmail._BAND.upper()
    assert html.index("GitAway") < html.index("Your stay at")


def test_it_has_one_bold_action_open_your_booking_and_the_rest_are_quiet():
    mail = bookingmail.booked_mail({**LIVE, "wallet": WALLET})
    assert mail.html.count("Open your booking") == 1 and mail.text.count("Open your booking") == 1
    bold = re.findall(r'<a [^>]*background:' + re.escape(bookingmail._CTA) + r'[^>]*>([^<]+)</a>', mail.html)
    assert bold == ["Open your booking"]


def test_the_wallet_links_are_kept_when_offered_and_absent_when_not():
    with_w = bookingmail.booked_mail({**LIVE, "wallet": WALLET})
    assert "Add to Apple Wallet" in words(with_w.html) and "https://gitaway.me/trip/booking/wallet/google?b=1" in with_w.text
    assert "Wallet" not in bookingmail.booked_mail(LIVE).html


def test_a_live_booking_says_it_was_booked_and_paid_through_nuitee_and_a_sandbox_one_does_not_claim_a_payment():
    live = bookingmail.booked_mail(LIVE)
    assert mb.MERCHANT in live.text and mb.MERCHANT in words(live.html)
    sandbox = bookingmail.booked_mail(sample.BOOKED)
    assert mb.SANDBOX_MERCHANT in sandbox.text and "merchant of record" not in sandbox.text
    cancelled = bookingmail.cancelled_mail({**sample.CANCELLED, "sandbox": False})
    assert mb.MERCHANT in cancelled.text and mb.MERCHANT in words(cancelled.html)


def test_whats_next_gives_the_planned_check_in_time_and_todays_page_the_day_before():
    mail = bookingmail.booked_mail(LIVE)
    nxt = "Check-in is planned for 3:00 PM on Wed, Dec 16, 2026 (the usual time; the hotel can say if its own is different)."
    day_before = "The day before, Today shows the next thing."
    for part in (mail.text, words(mail.html)):
        assert "What's next" in part and nxt in part and day_before in part
    assert "https://gitaway.me/trip/today" in mail.text and 'href="https://gitaway.me/trip/today"' in mail.html


def test_the_cancelled_email_has_no_whats_next_and_still_a_plain_text_part():
    mail = bookingmail.cancelled_mail({**sample.CANCELLED, "sandbox": False})
    assert "What's next" not in mail.text and "Your stay at" in mail.text and "Plan this trip" in mail.text


def test_the_colour_scheme_is_declared_and_no_background_is_pure_white():
    for html in (bookingmail.booked_mail(LIVE).html, bookingmail.cancelled_mail({**sample.CANCELLED, "sandbox": False}).html):
        assert '<meta name="color-scheme" content="light dark">' in html and '<meta name="supported-color-schemes" content="light dark">' in html
        assert not re.search(r"background(-color)?:\s*(#fff\b|#ffffff|white)", html, re.I)


def test_styles_are_inline_only_so_gmail_and_apple_mail_read_them():
    for html in (bookingmail.booked_mail(LIVE).html, bookingmail.cancelled_mail({**sample.CANCELLED, "sandbox": False}).html):
        assert "<style" not in html and "<link" not in html and "<script" not in html and "@import" not in html


def test_the_preview_files_show_what_a_real_booking_sends(tmp_path):
    assert sample.main(["--preview", str(tmp_path)]) == 0
    booked, cancelled = (tmp_path / "booked.html").read_text(), (tmp_path / "cancelled.html").read_text()
    assert mb.MERCHANT in words(booked) and mb.MERCHANT in words(cancelled) and "Sandbox booking" not in booked
