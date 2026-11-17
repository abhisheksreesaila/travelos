"""F-288: the wallet routes and buttons on a stay really booked here (the payment-form path's recordings): the signed download, the family and expiry checks, the buttons on the booking page,
the booked pass and the confirmation email, and nothing in the log but the booking id. Keys are made in tests/test_walletpass.py."""
import json
import logging
import re
import zipfile
from io import BytesIO

import pytest

from gitaway import bookingmail, liteapi, session as ses, walletpass as wp
from tests.test_matrixbook_live import GUEST, pay_pane, real, token  # noqa: F401 (real is the fixture)
from tests.test_matrixbook_page import person, sign_in, stays_booked
from tests.test_staycancel import booked_stay
from tests.test_walletpass import creds, keys  # noqa: F401 (fixtures)

BOOKING = "uuJxfM0--"
HOTEL = {"data": {"id": "lp1f5cb", "name": "Test Hotel", "address": "1 Harbor Dr, San Diego", "location": {"latitude": 32.7081, "longitude": -117.1665},
                  "checkinCheckoutTimes": {"checkinStart": "04:00 PM", "checkout": "11:30 AM"}}}


@pytest.fixture
def stay(real, client, creds, monkeypatch):      # noqa: F811
    monkeypatch.setattr(liteapi, "hotel", lambda hotel_id, family="": liteapi.read_hotel(HOTEL))
    trip, href = booked_stay(client)
    return href, ses.family


def tok(vendor, client, ttl=wp.PAGE_TTL, now=None, ref=BOOKING):
    return wp.sign(vendor, ref, person()["tenant_id"], ttl, now)


def test_the_signed_in_family_downloads_the_pass_with_the_hotels_facts(stay, client):
    r = client.get(wp.APPLE_PATH + tok("apple", client))
    assert r.status_code == 200 and r.headers["content-type"] == "application/vnd.apple.pkpass" and r.headers["cache-control"] == "no-store"
    assert 'filename="gitaway-stay.pkpass"' in r.headers["content-disposition"]
    p = json.loads(zipfile.ZipFile(BytesIO(r.content)).read("pass.json"))
    assert p["locations"][0]["latitude"] == 32.7081 and p["locations"][0]["longitude"] == -117.1665
    assert p["generic"]["secondaryFields"][0]["value"].endswith("4:00 PM") and p["generic"]["secondaryFields"][1]["value"].endswith("11:30 AM")
    assert {"key": "address", "label": "Address", "value": "1 Harbor Dr, San Diego"} in p["generic"]["backFields"]
    assert any(f["value"].startswith("https://") and "/trip/booking?block=" in f["value"] for f in p["generic"]["backFields"])
    assert p["barcodes"][0]["message"] == stays_booked()[0]["confirmation"]


def test_the_google_route_redirects_to_a_save_link(stay, client):
    r = client.get(wp.GOOGLE_PATH + tok("google", client), follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("https://pay.google.com/gp/v/save/") and r.headers["cache-control"] == "no-store"


def test_signed_out_goes_to_sign_in_and_comes_back(stay, client):
    t = tok("apple", client)
    client.cookies.clear()
    r = client.get(wp.APPLE_PATH + t, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/signin?next=" + (wp.APPLE_PATH + t).replace("/", "%2F")


def test_another_family_an_expired_token_and_a_forged_one_get_no_pass(stay, client):
    other = wp.sign("apple", BOOKING, "someone-elses-family", wp.PAGE_TTL)
    r = client.get(wp.APPLE_PATH + other)
    assert r.status_code == 404 and b"PK" not in r.content[:2]
    old = tok("apple", client, ttl=60, now=1000)
    r = client.get(wp.APPLE_PATH + old)
    assert r.status_code == 410 and "expired" in r.text
    assert client.get(wp.APPLE_PATH + tok("apple", client)[:-3] + "abc").status_code == 404
    assert client.get(wp.GOOGLE_PATH + tok("apple", client)).status_code == 404      # an Apple token is not a Google one
    assert client.get(wp.APPLE_PATH + tok("apple", client, ref="some-other-booking")).status_code == 404      # signed, but no such stay in this family


def test_a_second_family_signed_in_cannot_download_with_the_first_ones_token(stay, client):
    t = tok("apple", client)
    client.cookies.clear()
    sign_in(client, "sam")
    assert client.get(wp.APPLE_PATH + t).status_code == 404


def test_the_booking_page_shows_the_buttons_and_hides_them_without_credentials(stay, client, monkeypatch):
    href, _ = stay
    page = client.get(href).text
    assert "Add to Apple Wallet" in page and "Save to Google Wallet" in page and 'id="wp-apple"' in page
    monkeypatch.delenv("APPLE_PASS_TYPE_ID")
    monkeypatch.delenv("GOOGLE_WALLET_ISSUER_ID")
    assert "Wallet" not in client.get(href).text


def test_a_cancelled_stay_has_no_buttons_and_no_pass(stay, client):
    href, _ = stay
    t = tok("apple", client)
    client.post("/trip/booking/cancel", data={"booking": BOOKING, "sure": "1", "next": href})
    assert "Add to Apple Wallet" not in client.get(href).text
    assert client.get(wp.APPLE_PATH + t).status_code == 404


def test_the_booked_pass_after_paying_has_the_buttons(stay, client):
    page = client.get("/plan/matrix/book/return?token=" + _paid_token(client)).text
    assert "Add to Apple Wallet" in page and "Save to Google Wallet" in page


def _paid_token(client):
    from tests.test_matrixbook_live import payments
    return payments()[0]["id"]


def test_the_confirmation_email_links_to_our_signed_routes_not_an_attachment(creds):      # noqa: F811
    d = {"first": "Ann", "hotel": "Test Hotel", "address": "", "checkin": "2026-12-12", "checkout": "2026-12-16", "guests": "", "room": "", "booking_id": BOOKING, "confirmation": "test",
         "charge_cents": 1000, "due_cents": 0, "policy": "", "token": "tok12345", "sandbox": True, "wallet": wp.links(BOOKING, "fam1", wp.MAIL_TTL)}
    mail = bookingmail.booked_mail(d)
    assert re.search(r"Add to Apple Wallet: https://[^ ]+/wallet/apple/[\w.=-]+", mail.text) and re.search(r"Save to Google Wallet: https://[^ ]+/wallet/google/[\w.=-]+", mail.text)
    assert 'href="https://' in mail.html and "/wallet/apple/" in mail.html and "Save to Google Wallet" in mail.html
    assert wp.unsign(re.search(r"/wallet/apple/([\w.=-]+)", mail.text).group(1), "apple") == (BOOKING, "fam1", False)


def test_nothing_is_logged_but_the_booking_id(stay, client, caplog):
    caplog.set_level(logging.DEBUG)
    client.get(wp.APPLE_PATH + tok("apple", client))
    wallet = [r.getMessage() for r in caplog.records if r.name.startswith("gitaway") and "wallet" in r.getMessage().lower()]
    assert wallet == [f"wallet pass: apple {BOOKING}"]


def test_the_access_log_never_carries_a_wallet_link():
    from gitaway import accesslog
    t = wp.sign("apple", BOOKING, "fam1")
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", wp.APPLE_PATH + t, "1.1", 200), None)
    accesslog.Redact().filter(rec)
    assert t not in rec.getMessage() and "/wallet/apple/[link]" in rec.getMessage()


def test_the_access_log_never_carries_a_wallet_link_inside_the_sign_in_redirect():
    from urllib.parse import quote
    from gitaway import accesslog
    t = wp.sign("google", BOOKING, "fam1")
    for path in (f"/signin?next={quote(wp.GOOGLE_PATH + t, safe='')}", f"/login?next={quote(wp.APPLE_PATH + t, safe='').lower()}&intent=save", f"/signin?next=%2FWALLET%2FApple%2F{t}"):
        rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", path, "1.1", 303), None)
        accesslog.Redact().filter(rec)
        assert t not in rec.getMessage() and t.lower() not in rec.getMessage() and "[link]" in rec.getMessage()


def test_today_shows_the_stays_wallet_buttons_when_the_credentials_are_set(stay, client, monkeypatch):
    """F-287 + F-288: Today's hotel card carries the same two buttons as the booking page, and none without the credentials."""
    html = client.get("/trip/today").text
    if "Your hotel" not in html and "Where you are staying" not in html:
        pytest.skip("the booked stay's dates put Today outside a hotel card")
    assert 'id="wp-apple"' in html and 'id="wp-google"' in html
    monkeypatch.delenv("APPLE_PASS_TYPE_ID")
    monkeypatch.delenv("GOOGLE_WALLET_ISSUER_ID")
    assert 'id="wp-apple"' not in client.get("/trip/today").text


def test_the_booking_page_holds_the_wallet_buttons_in_its_more_menu_not_on_the_page(stay, client):
    """F-293 (D-949): the pass buttons are secondary, so they wait in the page's More menu; the page itself has the stay, its times, its code and Directions."""
    href, _ = stay
    page = client.get(href).text
    start = page.index('id="bk-more-menu"')
    end = page.index("</div>", start)
    assert page.count('id="wp-apple"') == 1 and start < page.index('id="wp-apple"') < end and start < page.index('id="wp-google"') < end
    assert page[start:end].count('role="menuitem"') == 2 and 'id="wp-btns"' not in page and "Directions" in page
