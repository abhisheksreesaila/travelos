"""F-198/F-199 review and security-audit fixes, each pinned by a test that failed before the fix. Through the HTTP seam and the modules' own functions; no test reaches the network."""

import logging
import re
import threading
from datetime import date
from html import unescape

import pytest
from sqlalchemy import text

from gitaway import confirmations as cf, planforme as pfm, tripimport as ti
from gitaway.partners import manage, places
from tests.confirmation_samples import AIRBNB, BOOKING
from tests.live_trips import live_trip
from tests.live_trips import TAHOE_TRIP
from tests.test_planforme import GOOD, buyer
from tests.test_signin import person, sign_in


def words(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def hidden(html, name):
    m = re.search(rf"""name="{name}" value=(?:"([^"]*)"|'([^']*)')""", html)
    return unescape(m.group(1) if m.group(1) is not None else m.group(2)) if m else None


# ---- 1. an emoji in a pasted title -----------------------------------------------------------------------------------------

EMOJI = AIRBNB.replace("Cozy A-Frame Cabin near Heavenly", "Cozy \U0001F3D4 A-Frame Cabin")


def test_an_emoji_round_trips_through_the_template_and_control_characters_go():
    plan = ti.parse(TAHOE_TRIP.replace("Lakeside Cabin", "Lakeside \U0001F3D4 Cabin")).plan
    assert ti.parse(ti.to_yaml(plan)).plan == plan
    weird = ti.Plan(**{**plan.__dict__, "title": "Tahoe\u2028with\x07 kids \U0001F3D4"})
    assert ti.parse(ti.to_yaml(weird)).plan.title == "Tahoe with kids \U0001F3D4"


def test_an_airbnb_title_with_an_emoji_previews_on_the_import_page(client):
    sign_in(client, "ari")
    r = client.post("/trips/import", data={"text": EMOJI})
    assert r.status_code == 200 and "Cozy \U0001F3D4 A-Frame Cabin" in words(r.text)


# ---- 3. a confirmation row on one line, or split by tabs -------------------------------------------------------------------

ONE_LINE = BOOKING.replace("Booking number: 4021.889.317\nPIN code: 7741", "Booking number: 4021.889.317 PIN code: 7741")
TABBED = AIRBNB.replace("Confirmation code\nHMAB12CD34\nTotal (USD) $3,112.50", "Confirmation code\tHMAB12CD34\tTotal (USD)\t$3,112.50")
JOINED = AIRBNB.replace("Confirmation code\nHMAB12CD34\nTotal (USD) $3,112.50", "Confirmation code HMAB12CD34 Total USD 3112.50")
CARD_ABOVE = BOOKING.replace("Lakeside Lodge Tahoe\n123 Lake", "Lakeside Lodge Tahoe\nPaid with Visa ending 4242\n123 Lake")


@pytest.mark.parametrize("sample, conf", [(ONE_LINE, "4021.889.317"), (TABBED, "HMAB12CD34"), (JOINED, "HMAB12CD34")], ids=["one-line", "tabs", "joined"])
def test_only_the_confirmation_number_is_kept_from_a_row(sample, conf):
    b = cf.read(sample)
    assert b.item.confirmation == conf
    out = cf.convert(sample).yaml
    for secret in ("7741", "PIN", "3112", "3,112", "Total", "USD", "$"):
        assert secret not in out, secret


def test_a_card_line_is_never_taken_for_a_name():
    b = cf.read(CARD_ABOVE)
    assert b.item.name == "Lakeside Lodge Tahoe" and "4242" not in cf.convert(CARD_ABOVE).yaml


def test_a_pin_is_never_stored(client):
    sign_in(client, "ari")
    r = client.post("/trips/import", data={"text": ONE_LINE})
    assert "7741" not in r.text
    assert client.post("/trips/import/save", data={"text": hidden(r.text, "text")}, follow_redirects=False).status_code == 303
    assert "7741" not in client.get("/trip/details").text


# ---- 4. an old unpaid order is never charged while plans are free ----------------------------------------------------------

def unpaid_order(monkeypatch, who="ari"):
    monkeypatch.setenv("PLAN_FOR_ME_PAID", "1")
    uid, tenant, email = buyer(who)
    o = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    assert o["status"] == "awaiting_payment" and o["amount_cents"] > 0
    monkeypatch.delenv("PLAN_FOR_ME_PAID")
    return o


def test_a_leftover_unpaid_order_is_made_free_and_never_sent_to_stripe(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_real")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_not_real")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setattr(pfm, "CHECKOUT", lambda params: pytest.fail("Stripe was asked for a payment page while plans are free"))
    sign_in(client, "ari")
    o = unpaid_order(monkeypatch)
    r = client.post(f"/plan-for-me/{o['id']}/pay", follow_redirects=False)
    assert r.status_code == 303 and "stripe" not in r.headers["location"]
    page = words(client.get(f"/plan-for-me/{o['id']}").text)
    assert "Pay $" not in page and "Request received" in page
    got = pfm.get(o["id"], person()["user_id"])
    assert (got["status"], got["amount_cents"]) == ("paid", 0)
    with pytest.raises(pfm.NotSold):
        pfm.start_checkout(got, "http://testserver")


def test_a_leftover_order_over_the_cap_is_expired_not_charged(client, monkeypatch):
    sign_in(client, "ari")
    o = unpaid_order(monkeypatch)
    uid, tenant, email = buyer("ari")
    for _ in range(2):
        pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    page = words(client.get(f"/plan-for-me/{o['id']}").text)
    got = pfm.get(o["id"], uid)
    assert (got["status"], got["amount_cents"], got["error"]) == ("failed", 0, "expired") and "Nothing was charged" in page and "Pay $" not in page


# ---- 5. the daily caps hold under a burst ----------------------------------------------------------------------------------

def test_twenty_simultaneous_orders_make_only_the_cap(monkeypatch):
    monkeypatch.delenv("PLAN_FOR_ME_PAID", raising=False)
    real = pfm.daily_cap

    def slow():        # reading the cap takes a moment, as a busy server does between a count and an insert: the window the audit's burst hit
        import time
        time.sleep(0.05)
        return real()
    monkeypatch.setattr(pfm, "daily_cap", slow)
    uid, tenant, email = buyer("ari")
    intake = pfm.read_intake(GOOD)[0]
    gate, made, refused, broke = threading.Barrier(20), [], [], []

    def one():
        gate.wait()
        try:
            made.append(pfm.create_order(uid, tenant, email, intake)["id"])
        except pfm.TooMany:
            refused.append(1)
        except Exception as e:      # noqa: BLE001 - a database error in a thread must fail the test, not vanish
            broke.append(repr(e))
    threads = [threading.Thread(target=one) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with pfm._db() as db:
        n = db.conn.execute(text("SELECT COUNT(*) FROM plan_orders WHERE owner_user = :o"), {"o": str(uid)}).scalar()
    assert broke == [] and (len(made), len(refused), n) == (2, 18, 2)


# ---- 6. anonymous pages cannot spend the Data API ---------------------------------------------------------------------------

# ---- 8. a partner's button only for the partner's own name --------------------------------------------------------------------

@pytest.mark.parametrize("name", ["American Express Travel", "Budget Travel", "Tahoe Booking Co", "Expedia Cruises Inc", "National Park Lodge", "The Dollar Store", "Delta Lodge"])
def test_a_name_that_only_contains_a_partners_word_has_no_button(name):
    assert manage.find(name) is None


@pytest.mark.parametrize("name, site", [("Expedia", "Expedia"), ("expedia.com", "Expedia"), ("Booking.com", "Booking.com"), ("Enterprise Rent-A-Car", "Enterprise"),
                                        ("Delta Air Lines", "Delta"), ("Alaska Airlines", "Alaska Airlines"), ("American Airlines", "American Airlines"), ("Hertz", "Hertz")])
def test_a_partners_own_name_still_finds_it(name, site):
    assert manage.find(name).name == site


# ---- 9. a typed state that is not the table's is the person's own place --------------------------------------------------------

@pytest.mark.parametrize("typed, iata", [("Portland, ME", ""), ("Portland, Maine", ""), ("Jackson, NH", ""), ("Vail, AZ", ""), ("Portland, OR", "PDX"), ("Jackson, WY", "JAC"),
                                         ("Lake Tahoe, NV", "RNO"), ("Lake Tahoe, CA", "RNO")])
def test_the_state_typed_decides(typed, iata):
    p = places.resolve(typed)
    assert p.iata == iata and p.known == bool(iata)
    if not iata:
        assert p.name == typed and p.city == typed.split(",")[0]


# ---- 11. a failed free plan is no refund ------------------------------------------------------------------------------------

def test_a_failed_free_plan_is_not_a_refund_due(client, monkeypatch, caplog):
    monkeypatch.delenv("PLAN_FOR_ME_PAID", raising=False)
    uid, tenant, email = buyer("ari")
    o = pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])
    with caplog.at_level(logging.WARNING, logger="gitaway.planforme"):
        pfm._fail(o["id"], "refusal")
    assert "refund due" not in caplog.text
    assert pfm.totals(pfm.admin_rows())["refunds"] == 0
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "ari.rivera@example.com")
    sign_in(client, "ari")
    page = client.get("/admin").text
    assert 'id="refund-' not in page and re.search(r'id="ad-refunds"[^>]*>([^<]*)<', page).group(1) == "0 · $0"


# ---- nits --------------------------------------------------------------------------------------------------------------------------

def test_the_details_page_says_where_once_not_twice(client):
    sign_in(client, "ari")
    assert client.post("/trips/import/save", data={"text": TAHOE_TRIP}, follow_redirects=False).status_code == 303
    t = words(client.get("/trip/details").text)
    assert "Booked on Expedia" in t and "Booked elsewhere · Expedia" not in t
    today = words(client.get("/trip").text)
    assert "Booked elsewhere · Expedia" not in today


# ---- 18. body limits on the paste routes ------------------------------------------------------------------------------------------

# ---- 7. no copy sells the removed workspace -----------------------------------------------------------------------------------------

# ---- 10. kids' ages are pickers, one per kid --------------------------------------------------------------------------------------
