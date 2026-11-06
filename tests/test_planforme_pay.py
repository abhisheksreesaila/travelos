"""F-193 Plan it for me: the money. The Checkout session is made on the server at the order's price, and the webhook (`POST /stripe/webhook`) is the only thing that marks an order paid:
signed with STRIPE_WEBHOOK_SECRET, for the order's amount, and counted once per event id. No test reaches Stripe: `planforme.CHECKOUT` stands in for the SDK, and one test hands the real SDK a
fake HTTP client to read the request it would send."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import pytest

from gitaway import planforme as pfm
from tests.test_planforme import GOOD, buyer
from tests.test_signin import sign_in

SECRET = "whsec_test_secret"
BASE = "http://127.0.0.1:5002"


@pytest.fixture(autouse=True)
def stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_not_real")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)


def order(who="ari"):
    uid, tenant, email = buyer(who)
    return pfm.create_order(uid, tenant, email, pfm.read_intake(GOOD)[0])


def event(order_id, session="cs_test_1", amount=2900, currency="usd", kind="checkout.session.completed", eid="evt_1", status="paid", **obj):
    return {"id": eid, "object": "event", "type": kind, "data": {"object": {"id": session, "object": "checkout.session", "mode": "payment", "client_reference_id": order_id, "payment_status": status,
                                                                            "amount_total": amount, "currency": currency, **obj}}}


def signed(payload, secret=SECRET, ts=None):
    body = json.dumps(payload).encode()
    ts = int(time.time()) if ts is None else ts
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"}


def hook(client, payload, **kw):
    body, headers = signed(payload, **kw)
    return client.post("/stripe/webhook", content=body, headers=headers)


# ---- the Checkout session ----------------------------------------------------------------------------------------

def test_the_checkout_session_is_one_payment_line_at_the_orders_own_price(monkeypatch):
    made = []
    monkeypatch.setattr(pfm, "CHECKOUT", lambda params: made.append(params) or {"id": "cs_test_9", "url": "https://checkout.stripe.test/c/pay/cs_test_9"})
    o = order()
    url = pfm.start_checkout(o, BASE)
    assert url == "https://checkout.stripe.test/c/pay/cs_test_9"
    (p,) = made
    assert p["mode"] == "payment" and p["client_reference_id"] == o["id"] and p["customer_email"] == "ari.rivera@example.com"
    assert p["line_items"] == [{"price_data": {"currency": "usd", "unit_amount": 2900, "product_data": {"name": "Plan it for me", "description": pfm.PROMISE}}, "quantity": 1}]
    assert p["success_url"] == f"{BASE}/plan-for-me/{o['id']}?paid=1" and p["cancel_url"] == f"{BASE}/plan-for-me/{o['id']}"
    assert p["metadata"] == {"order_id": o["id"]} and p["expires_at"] > time.time() + 1700
    assert "allow_promotion_codes" not in p and pfm.get(o["id"], o["owner_user"])["stripe_session"] == "cs_test_9"


def test_the_real_sdk_sends_the_form_stripe_expects(monkeypatch):
    """The Stripe SDK is given a fake HTTP client, so the request it really builds can be read: the key, the path and the nested price data."""
    import stripe
    sent = []

    class Fake(stripe.HTTPClient):
        name = "fake"

        def request(self, method, url, headers, post_data=None, **kw):
            sent.append((method, url, headers, post_data))
            return json.dumps({"id": "cs_test_5", "object": "checkout.session", "url": "https://checkout.stripe.test/c/pay/cs_test_5"}), 200, {}

        def request_with_retries(self, method, url, headers, post_data=None, **kw):
            return self.request(method, url, headers, post_data)

        def close(self):
            pass
    monkeypatch.setattr(stripe, "default_http_client", Fake())
    o = order()
    assert pfm.start_checkout(o, BASE) == "https://checkout.stripe.test/c/pay/cs_test_5"
    (method, url, headers, post_data), = sent
    assert (method, url) == ("post", "https://api.stripe.com/v1/checkout/sessions") and headers["Authorization"] == "Bearer sk_test_not_real"
    form = dict(parse_qsl(post_data if isinstance(post_data, str) else post_data.decode()))
    assert form["mode"] == "payment" and form["client_reference_id"] == o["id"]
    assert form["line_items[0][price_data][unit_amount]"] == "2900" and form["line_items[0][price_data][currency]"] == "usd" and form["line_items[0][quantity]"] == "1"
    assert form["line_items[0][price_data][product_data][name]"] == "Plan it for me"


# ---- the webhook -------------------------------------------------------------------------------------------------

def test_a_signed_completed_payment_marks_the_order_paid(client):
    o = order()
    r = hook(client, event(o["id"]))
    assert (r.status_code, r.text) == (200, "paid")
    got = pfm.get(o["id"], o["owner_user"])
    assert (got["status"], got["stripe_session"]) == ("paid", "cs_test_1") and got["paid_at"]


def test_a_wrong_or_missing_signature_changes_nothing(client):
    o = order()
    body, headers = signed(event(o["id"]), secret="whsec_somebody_else")
    assert client.post("/stripe/webhook", content=body, headers=headers).status_code == 400
    assert client.post("/stripe/webhook", content=body).status_code == 400
    assert client.post("/stripe/webhook", content=body, headers={"Stripe-Signature": "t=1,v1=00"}).status_code == 400
    assert hook(client, event(o["id"]), ts=int(time.time()) - 3600).status_code == 400      # a replay of an old, once-valid delivery
    assert pfm.get(o["id"], o["owner_user"])["status"] == "awaiting_payment"


def test_without_a_webhook_secret_nothing_is_ever_believed(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "")
    o = order()
    body, headers = signed(event(o["id"]), secret="")
    assert client.post("/stripe/webhook", content=body, headers=headers).status_code == 503
    assert client.post("/stripe/webhook", content=body).status_code == 503
    assert pfm.get(o["id"], o["owner_user"])["status"] == "awaiting_payment"


def test_the_same_event_twice_is_one_payment_and_does_not_undo_progress(client):
    o = order()
    assert hook(client, event(o["id"])).text == "paid"
    with pfm._db() as db:
        from sqlalchemy import text
        db.conn.execute(text("UPDATE plan_orders SET status = 'building' WHERE id = :i"), {"i": o["id"]})
        db.conn.commit()
    again = hook(client, event(o["id"]))
    assert (again.status_code, again.text) == (200, "duplicate")
    assert pfm.get(o["id"], o["owner_user"])["status"] == "building"
    with pfm._db() as db:
        assert db.conn.execute(text("SELECT COUNT(*) FROM plan_order_events")).scalar() == 1


def test_a_second_paid_session_for_the_same_order_is_flagged_not_built_twice(client, caplog):
    o = order()
    assert hook(client, event(o["id"], session="cs_a", eid="evt_a")).text == "paid"
    with caplog.at_level("WARNING", logger="gitaway.planforme"):
        assert hook(client, event(o["id"], session="cs_b", eid="evt_b")).text == "double"
    assert "paid again" in caplog.text and o["id"] in caplog.text
    assert pfm.get(o["id"], o["owner_user"])["status"] == "paid"


def test_a_payment_for_another_amount_or_currency_is_not_built_and_needs_a_refund(client):
    o = order()
    assert hook(client, event(o["id"], amount=100, eid="evt_x")).text == "mismatch"
    got = pfm.get(o["id"], o["owner_user"])
    assert (got["status"], got["error"]) == ("failed", "amount_mismatch")
    p = order()
    assert hook(client, event(p["id"], currency="eur", eid="evt_y")).text == "mismatch"


def test_an_event_for_no_order_of_ours_is_thanked_and_does_nothing(client):
    assert hook(client, event("0" * 16, eid="evt_n")).text == "unknown"
    assert hook(client, event("not-an-order", eid="evt_m")).text == "unknown"
    assert hook(client, event("0" * 16, kind="customer.created", eid="evt_c")).text == "ignored"


def test_a_session_that_is_not_paid_yet_waits_for_the_async_event(client):
    o = order()
    assert hook(client, event(o["id"], status="unpaid", eid="evt_1")).text == "waiting"
    assert pfm.get(o["id"], o["owner_user"])["status"] == "awaiting_payment"
    assert hook(client, event(o["id"], kind="checkout.session.async_payment_succeeded", eid="evt_2")).text == "paid"
    assert pfm.get(o["id"], o["owner_user"])["status"] == "paid"


def test_a_subscription_or_setup_session_is_ignored(client):
    o = order()
    assert hook(client, event(o["id"], mode="subscription")).text == "ignored"
    assert pfm.get(o["id"], o["owner_user"])["status"] == "awaiting_payment"


def test_the_webhook_needs_no_sign_in_and_a_viewer_session_does_not_matter(client):
    o = order()
    sign_in(client, "ari")
    assert hook(client, event(o["id"])).status_code == 200
